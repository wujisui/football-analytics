"""Feature engineering for 1X2 probability models.

Features emphasize form, H2H, standings, injuries, **market odds** (strong
prior while samples are scarce), and streak / mean-reversion. Odds are a major
input in the multifactor stage, not a token nudge — bookmakers price risk;
upsets / manipulation are possible but not assumed every match.
"""

from __future__ import annotations

import json
import math
from typing import Any

FEATURE_VERSION = "v1"
DEFAULT_PROB = 1 / 3

# Stable column order for training / inference vectors.
FEATURE_NAMES: list[str] = [
    # Form strength (recent windows)
    "home_wr_5",
    "home_dr_5",
    "home_wr_10",
    "away_wr_5",
    "away_dr_5",
    "away_wr_10",
    "home_gd_avg_5",
    "away_gd_avg_5",
    # Streak / mean-reversion
    "home_win_streak",
    "home_unbeaten_streak",
    "home_winless_streak",
    "home_loss_streak",
    "away_win_streak",
    "away_unbeaten_streak",
    "away_winless_streak",
    "away_loss_streak",
    "home_reversion",  # signed: +bounce / -fade
    "away_reversion",
    # H2H (from current home perspective)
    "h2h_home_rate",
    "h2h_draw_rate",
    "h2h_away_rate",
    "h2h_played_n",
    # Standings / injuries
    "rank_diff",  # away_rank - home_rank (positive → home higher table)
    "home_injuries_n",
    "away_injuries_n",
    # Market prior (strong in multifactor / thin-data stage)
    "odds_home",
    "odds_draw",
    "odds_away",
    "has_odds",
    # Meta
    "home_advantage",
]


def dumps_features(features: dict[str, float]) -> str:
    ordered = {name: float(features.get(name, 0.0)) for name in FEATURE_NAMES}
    return json.dumps(ordered, ensure_ascii=False)


def loads_features(raw: str | None) -> dict[str, float]:
    if not raw:
        return {name: 0.0 for name in FEATURE_NAMES}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {name: 0.0 for name in FEATURE_NAMES}
    return {name: float(data.get(name, 0.0)) for name in FEATURE_NAMES}


def feature_vector(features: dict[str, float]) -> list[float]:
    return [float(features.get(name, 0.0)) for name in FEATURE_NAMES]


def _safe_rate(num: int, den: int, default: float = DEFAULT_PROB) -> float:
    return (num / den) if den > 0 else default


def _form_string(form: dict[str, Any] | None) -> str:
    if not isinstance(form, dict):
        return ""
    text = str(form.get("form") or "")
    if text:
        return text.upper()
    matches = form.get("matches") or []
    return "".join(str(m.get("result") or "") for m in matches).upper()


def _window_rates(form_str: str, window: int) -> tuple[float, float, float]:
    chunk = form_str[:window]
    if not chunk:
        return DEFAULT_PROB, DEFAULT_PROB, DEFAULT_PROB
    n = len(chunk)
    w = chunk.count("W")
    d = chunk.count("D")
    l = chunk.count("L")
    return w / n, d / n, l / n


def _rates_from_form(form: dict[str, Any] | None, window: int) -> tuple[float, float, float]:
    """Prefer chronological form window; fall back to aggregate W/D/L counts."""
    form_str = _form_string(form)
    if form_str:
        return _window_rates(form_str, window)
    if not isinstance(form, dict):
        return DEFAULT_PROB, DEFAULT_PROB, DEFAULT_PROB
    played = int(form.get("played") or 0)
    if played <= 0:
        return DEFAULT_PROB, DEFAULT_PROB, DEFAULT_PROB
    w = int(form.get("wins") or 0)
    d = int(form.get("draws") or 0)
    l = int(form.get("losses") or 0)
    return _safe_rate(w, played), _safe_rate(d, played), _safe_rate(l, played)


def _streak_stats(form_str: str) -> dict[str, int]:
    """Streaks from most-recent match (index 0 of form string)."""
    if not form_str:
        return {
            "win_streak": 0,
            "unbeaten_streak": 0,
            "winless_streak": 0,
            "loss_streak": 0,
        }

    def _count(pred) -> int:
        n = 0
        for ch in form_str:
            if pred(ch):
                n += 1
            else:
                break
        return n

    return {
        "win_streak": _count(lambda c: c == "W"),
        "unbeaten_streak": _count(lambda c: c in ("W", "D")),
        "winless_streak": _count(lambda c: c in ("L", "D")),
        "loss_streak": _count(lambda c: c == "L"),
    }


def mean_reversion_score(
    *,
    win_streak: int,
    winless_streak: int,
    loss_streak: int,
    unbeaten_streak: int,
) -> float:
    """Signed regression-to-mean pressure on *win* probability.

    Positive → historically due a bounce (long winless / losing run).
    Negative → fade risk after extended winning / unbeaten run.

    No team wins forever; long droughts also reverse more often than naive
    form rates imply. Caps keep the effect mild so it never dominates.
    """
    bounce = 0.0
    fade = 0.0

    if winless_streak >= 3:
        bounce += 0.025 * min(winless_streak - 2, 6)
    if loss_streak >= 3:
        bounce += 0.02 * min(loss_streak - 2, 5)

    if win_streak >= 3:
        fade += 0.03 * min(win_streak - 2, 6)
    if unbeaten_streak >= 5:
        fade += 0.015 * min(unbeaten_streak - 4, 6)

    return max(-0.18, min(0.18, bounce - fade))


def _goal_diff_avg(form: dict[str, Any] | None, window: int = 5) -> float:
    if not isinstance(form, dict):
        return 0.0
    matches = form.get("matches") or []
    diffs: list[float] = []
    for m in matches[:window]:
        score = str(m.get("score") or "")
        if "-" not in score:
            continue
        left, _, right = score.partition("-")
        try:
            hg, ag = int(left.strip()), int(right.strip())
        except ValueError:
            continue
        result = str(m.get("result") or "").upper()
        # Score is always home-away of that past match; convert to team GD.
        home_name = str(m.get("home") or "")
        away_name = str(m.get("away") or "")
        # Prefer result letter: W → positive contribution via goals for/against.
        if result == "W":
            # Approximate: team scored more; use absolute margin.
            diffs.append(abs(hg - ag))
        elif result == "L":
            diffs.append(-abs(hg - ag))
        elif result == "D":
            diffs.append(0.0)
        else:
            # Fallback if side unknown
            _ = (home_name, away_name)
            diffs.append(float(hg - ag))
    if not diffs:
        return 0.0
    return sum(diffs) / len(diffs)


def _injury_count(injuries: dict[str, Any] | None, side: str) -> float:
    if not isinstance(injuries, dict):
        return 0.0
    block = injuries.get(side)
    if isinstance(block, list):
        return float(len(block))
    if isinstance(block, dict):
        players = block.get("players") or block.get("items") or []
        if isinstance(players, list):
            return float(len(players))
        return float(block.get("count") or 0)
    return 0.0


def has_match_winner_odds(odds: dict[str, Any] | None) -> bool:
    """Whether a package contains a complete, positive pre-match 1X2 board."""
    if not isinstance(odds, dict) or not odds.get("available"):
        return False
    mw = odds.get("match_winner")
    if not isinstance(mw, dict):
        return False
    try:
        h, d, a = float(mw["home"]), float(mw["draw"]), float(mw["away"])
    except (KeyError, TypeError, ValueError):
        return False
    return min(h, d, a) > 0


def _odds_implied(odds: dict[str, Any] | None) -> tuple[float, float, float, float]:
    if not has_match_winner_odds(odds):
        return DEFAULT_PROB, DEFAULT_PROB, DEFAULT_PROB, 0.0
    mw = odds["match_winner"]
    h, d, a = float(mw["home"]), float(mw["draw"]), float(mw["away"])
    inv_h, inv_d, inv_a = 1.0 / h, 1.0 / d, 1.0 / a
    total = inv_h + inv_d + inv_a
    if total <= 0:
        return DEFAULT_PROB, DEFAULT_PROB, DEFAULT_PROB, 0.0
    return inv_h / total, inv_d / total, inv_a / total, 1.0


def _rank_diff(standings: dict[str, Any] | None) -> float:
    if not isinstance(standings, dict):
        return 0.0
    home = standings.get("home_rank")
    away = standings.get("away_rank")
    try:
        hr, ar = int(home), int(away)
    except (TypeError, ValueError):
        return 0.0
    if hr <= 0 or ar <= 0:
        return 0.0
    # Positive when home sits above away (lower rank number).
    return float(ar - hr) / 20.0


def _h2h_rates(h2h: dict[str, Any] | None) -> tuple[float, float, float, float]:
    if not isinstance(h2h, dict):
        return DEFAULT_PROB, DEFAULT_PROB, DEFAULT_PROB, 0.0
    played = int(h2h.get("played") or 0)
    if played <= 0:
        return DEFAULT_PROB, DEFAULT_PROB, DEFAULT_PROB, 0.0
    hw = int(h2h.get("home_wins") or 0)
    dr = int(h2h.get("draws") or 0)
    aw = int(h2h.get("away_wins") or 0)
    return hw / played, dr / played, aw / played, min(played / 10.0, 1.0)


def extract_features(package: dict[str, Any] | None) -> dict[str, float]:
    """Build v1 feature dict from a pre-match package."""
    package = package or {}
    home_form = package.get("home_form") if isinstance(package.get("home_form"), dict) else {}
    away_form = package.get("away_form") if isinstance(package.get("away_form"), dict) else {}
    h2h = package.get("head_to_head") or package.get("h2h")
    odds = package.get("odds")
    standings = package.get("standings")
    injuries = package.get("injuries")

    home_s = _form_string(home_form)
    away_s = _form_string(away_form)
    h_wr5, h_dr5, _ = _rates_from_form(home_form, 5)
    a_wr5, a_dr5, _ = _rates_from_form(away_form, 5)
    h_wr10, _, _ = _rates_from_form(home_form, 10)
    a_wr10, _, _ = _rates_from_form(away_form, 10)

    hs = _streak_stats(home_s)
    aws = _streak_stats(away_s)
    h_rev = mean_reversion_score(
        win_streak=hs["win_streak"],
        winless_streak=hs["winless_streak"],
        loss_streak=hs["loss_streak"],
        unbeaten_streak=hs["unbeaten_streak"],
    )
    a_rev = mean_reversion_score(
        win_streak=aws["win_streak"],
        winless_streak=aws["winless_streak"],
        loss_streak=aws["loss_streak"],
        unbeaten_streak=aws["unbeaten_streak"],
    )

    h2h_h, h2h_d, h2h_a, h2h_n = _h2h_rates(h2h if isinstance(h2h, dict) else None)
    oh, od, oa, has_odds = _odds_implied(odds if isinstance(odds, dict) else None)

    features = {
        "home_wr_5": h_wr5,
        "home_dr_5": h_dr5,
        "home_wr_10": h_wr10,
        "away_wr_5": a_wr5,
        "away_dr_5": a_dr5,
        "away_wr_10": a_wr10,
        "home_gd_avg_5": _goal_diff_avg(home_form, 5),
        "away_gd_avg_5": _goal_diff_avg(away_form, 5),
        "home_win_streak": float(hs["win_streak"]),
        "home_unbeaten_streak": float(hs["unbeaten_streak"]),
        "home_winless_streak": float(hs["winless_streak"]),
        "home_loss_streak": float(hs["loss_streak"]),
        "away_win_streak": float(aws["win_streak"]),
        "away_unbeaten_streak": float(aws["unbeaten_streak"]),
        "away_winless_streak": float(aws["winless_streak"]),
        "away_loss_streak": float(aws["loss_streak"]),
        "home_reversion": h_rev,
        "away_reversion": a_rev,
        "h2h_home_rate": h2h_h,
        "h2h_draw_rate": h2h_d,
        "h2h_away_rate": h2h_a,
        "h2h_played_n": h2h_n,
        "rank_diff": _rank_diff(standings if isinstance(standings, dict) else None),
        "home_injuries_n": min(_injury_count(injuries if isinstance(injuries, dict) else None, "home"), 8.0) / 8.0,
        "away_injuries_n": min(_injury_count(injuries if isinstance(injuries, dict) else None, "away"), 8.0) / 8.0,
        "odds_home": oh,
        "odds_draw": od,
        "odds_away": oa,
        "has_odds": has_odds,
        "home_advantage": 1.0,
    }
    return {name: float(features.get(name, 0.0)) for name in FEATURE_NAMES}


def softmax3(home: float, draw: float, away: float) -> dict[str, float]:
    # Numerically stable softmax over logits.
    m = max(home, draw, away)
    eh, ed, ea = math.exp(home - m), math.exp(draw - m), math.exp(away - m)
    total = eh + ed + ea
    if total <= 0:
        return {"home": DEFAULT_PROB, "draw": DEFAULT_PROB, "away": DEFAULT_PROB}
    return {"home": eh / total, "draw": ed / total, "away": ea / total}
