"""Backend prediction leans + opinion-factor fusion (not free-text NLP)."""

from __future__ import annotations

import re
from typing import Any

DEFAULT_PROB = 1 / 3
# Only treat as "no real model output" when all three sit on the flat prior.
_FLAT_EPS = 0.02
# Below this gap between #1 and #2 → double-chance (双选) instead of single.
_DOUBLE_CHANCE_EDGE = 0.08
# Market-structure gates for 1X2 recommendation (not per-league tuning).
_MARKET_FLAT_SPREAD = 0.10
_SINGLE_PICK_GAP = 0.10
_DRAW_INCLUDE_MIN = 0.26

# Explicit factors users can toggle — same IDs used by POST /fixtures/{id}/adjust
OPINION_FACTORS: list[dict[str, str]] = [
    {"id": "home_stronger", "label": "主队更强 / 占优", "group": "方向"},
    {"id": "away_stronger", "label": "客队更强 / 占优", "group": "方向"},
    {"id": "draw_likely", "label": "倾向平局", "group": "方向"},
    {"id": "home_injury", "label": "主队伤停 / 缺阵", "group": "伤病体能"},
    {"id": "away_injury", "label": "客队伤停 / 缺阵", "group": "伤病体能"},
    {"id": "home_fatigue", "label": "主队赛程密集 / 疲劳", "group": "伤病体能"},
    {"id": "away_fatigue", "label": "客队赛程密集 / 疲劳", "group": "伤病体能"},
    {"id": "home_form_up", "label": "主队状态出色 / 复出", "group": "状态"},
    {"id": "away_form_up", "label": "客队状态出色 / 复出", "group": "状态"},
    {"id": "over_goals", "label": "倾向大球 / 对攻", "group": "进球"},
    {"id": "under_goals", "label": "倾向小球 / 闷平", "group": "进球"},
]

_FACTOR_DELTAS: dict[str, dict[str, float]] = {
    "home_stronger": {"home": 0.08, "draw": -0.03, "away": -0.05},
    "away_stronger": {"home": -0.05, "draw": -0.03, "away": 0.08},
    "draw_likely": {"home": -0.035, "draw": 0.07, "away": -0.035},
    "home_injury": {"home": -0.06, "draw": 0.03, "away": 0.03},
    "away_injury": {"home": 0.03, "draw": 0.03, "away": -0.06},
    "home_fatigue": {"home": -0.06, "draw": 0.03, "away": 0.03},
    "away_fatigue": {"home": 0.03, "draw": 0.03, "away": -0.06},
    "home_form_up": {"home": 0.04, "draw": -0.02, "away": -0.02},
    "away_form_up": {"home": -0.02, "draw": -0.02, "away": 0.04},
    "over_goals": {"home": 0.015, "draw": -0.03, "away": 0.015},
    "under_goals": {"home": -0.025, "draw": 0.05, "away": -0.025},
}

_LABEL = {"home": "胜", "draw": "平", "away": "负"}
_DOUBLE = {
    frozenset({"home", "draw"}): "胜/平",
    frozenset({"away", "draw"}): "负/平",
    frozenset({"home", "away"}): "胜/负",
}


def canonical_recommendation(text: str | None) -> str:
    """Return compact 1X2 copy while accepting historical stored wording."""
    rec = (text or "").strip()
    outcomes = recommendation_outcomes(rec)
    if outcomes is None:
        return rec
    if len(outcomes) == 1:
        return _LABEL[next(iter(outcomes))]
    return _DOUBLE[frozenset(outcomes)]


def canonical_goal_lean(text: str | None) -> str:
    value = (text or "").strip()
    return (
        value.replace("倾向大球", "大")
        .replace("倾向小球", "小")
        .replace("大小球：", "大小：")
        .replace("（", "(")
        .replace("）", ")")
    )


def canonical_btts_lean(text: str | None) -> str:
    return (text or "").strip().replace("双方进球：", "双进:").replace(
        "双方进球:", "双进:"
    )


def canonical_score_hint(text: str | None) -> str:
    value = (text or "").strip()
    if not value:
        return ""
    if value.startswith("比分:"):
        return value
    if value.startswith("比分："):
        return f"比分:{value[3:]}"
    return f"比分:{value}"


def normalize_probabilities(probs: dict[str, float]) -> dict[str, float]:
    total = sum(max(float(v), 0.0) for v in probs.values())
    if total <= 0:
        return {"home": DEFAULT_PROB, "draw": DEFAULT_PROB, "away": DEFAULT_PROB}
    return {k: max(float(v), 0.0) / total for k, v in probs.items()}


def is_flat_prior(probs: dict[str, float]) -> bool:
    """True only for placeholder 1/3·1/3·1/3 (no real analysis yet)."""
    return all(
        abs(float(probs.get(k, 0)) - DEFAULT_PROB) < _FLAT_EPS
        for k in ("home", "draw", "away")
    )


def implied_probs_from_odds(odds: dict[str, Any] | None) -> dict[str, float] | None:
    """Derive 1X2 probabilities from match-winner odds (local, no API).

    Uses inverse-odds normalized to remove bookmaker margin.
    """
    if not isinstance(odds, dict) or not odds.get("available"):
        return None
    mw = odds.get("match_winner")
    if not isinstance(mw, dict):
        return None
    home = _odd_float(mw.get("home"))
    draw = _odd_float(mw.get("draw"))
    away = _odd_float(mw.get("away"))
    if home is None or draw is None or away is None:
        return None
    inv_h, inv_d, inv_a = 1.0 / home, 1.0 / draw, 1.0 / away
    total = inv_h + inv_d + inv_a
    if total <= 0:
        return None
    return normalize_probabilities(
        {"home": inv_h / total, "draw": inv_d / total, "away": inv_a / total}
    )


def resolve_match_probabilities(
    probs: dict[str, float] | None,
    odds: dict[str, Any] | None = None,
) -> dict[str, float]:
    """Prefer stored model probs; if still flat prior, fall back to odds-implied."""
    normalized = normalize_probabilities(
        {
            "home": float((probs or {}).get("home", DEFAULT_PROB)),
            "draw": float((probs or {}).get("draw", DEFAULT_PROB)),
            "away": float((probs or {}).get("away", DEFAULT_PROB)),
        }
    )
    if not is_flat_prior(normalized):
        return normalized
    implied = implied_probs_from_odds(odds)
    return implied if implied is not None else normalized


def get_recommendation(
    probs: dict[str, float],
    *,
    odds: dict[str, Any] | None = None,
    features: dict[str, float] | None = None,
) -> str:
    """Market-structured 1X2 lean; model only breaks ties / upgrades clear edges.

    Uses de-vigged 1X2 odds for market shape (flat vs favorite). Display probabilities
    may come from ML; recommendation follows盘口胶着度 + AH 水位, not argmax alone.
    """
    model = normalize_probabilities(probs)
    market = implied_probs_from_odds(odds)
    if market is None:
        market = model
    if is_flat_prior(model) and is_flat_prior(market):
        return "待分析"

    def _ranked(p: dict[str, float]) -> list[tuple[str, float]]:
        return sorted(
            (
                ("home", p["home"]),
                ("draw", p["draw"]),
                ("away", p["away"]),
            ),
            key=lambda x: x[1],
            reverse=True,
        )

    m_rank = _ranked(market)
    d_rank = _ranked(model)
    m_top, m_second, m_third = m_rank[0], m_rank[1], m_rank[2]
    d_top, d_second = d_rank[0], d_rank[1]
    m_spread = m_top[1] - m_third[1]
    m_gap = m_top[1] - m_second[1]
    d_gap = d_top[1] - d_second[1]
    d_draw = model["draw"]
    m_draw = market["draw"]

    d_spread = d_top[1] - d_rank[2][1]

    # Draw is market top.
    if m_rank[0][0] == "draw":
        if m_gap >= _SINGLE_PICK_GAP:
            return "平"
        other = "home" if market["home"] >= market["away"] else "away"
        return _DOUBLE[frozenset({"draw", other})]

    # Contested board: tight triangle on market or model, or weak single favorite.
    weak_home = d_top[0] == "home" and model["home"] < 0.50 and d_draw >= 0.24
    weak_away = d_top[0] == "away" and model["away"] < 0.50 and d_draw >= 0.24
    contested = (
        m_spread <= _MARKET_FLAT_SPREAD
        or d_spread <= _MARKET_FLAT_SPREAD
        or (m_draw >= _DRAW_INCLUDE_MIN and m_gap < _SINGLE_PICK_GAP)
        or weak_home
        or weak_away
    )
    if contested:
        fav = d_top[0]
        if fav == "home":
            return "胜/平" if d_draw >= _DRAW_INCLUDE_MIN - 0.02 else "胜/负"
        if fav == "away":
            return "负/平" if d_draw >= _DRAW_INCLUDE_MIN - 0.02 else "胜/负"
        return "胜/平"

    # Clear market favorite — allow single pick when model agrees or extends edge.
    if m_gap >= _SINGLE_PICK_GAP:
        if d_top[0] == m_top[0] and d_gap >= 0.08:
            return _LABEL[m_top[0]]
        if model[m_top[0]] - market[m_top[0]] >= 0.04 and d_gap >= 0.08:
            return _LABEL[m_top[0]]
        if d_second[0] == "draw" or d_draw >= _DRAW_INCLUDE_MIN:
            return _DOUBLE[frozenset({m_top[0], "draw"})]
        ah_side = _ah_market_favorite(odds)
        if ah_side:
            return _LABEL[ah_side]
        return _LABEL[m_top[0]]

    # Moderate gap → double chance (include draw when non-trivial).
    if m_second[0] == "draw" or m_draw >= _DRAW_INCLUDE_MIN:
        return _DOUBLE[frozenset({m_top[0], "draw"})]
    if frozenset({m_top[0], m_second[0]}) == frozenset({"home", "away"}):
        ah_side = _ah_market_favorite(odds)
        if ah_side:
            return _LABEL[ah_side]
        return _DOUBLE[frozenset({m_top[0], "draw"})]
    return _LABEL[m_top[0]]


def recommendation_outcomes(recommendation: str) -> set[str] | None:
    """Map recommendation text → {home,draw,away} outcomes that count as hit."""
    rec = (recommendation or "").strip()
    if not rec or "待分析" in rec:
        return None
    if rec == "胜/平" or "主队不败" in rec or rec.startswith("主胜/平"):
        return {"home", "draw"}
    if rec == "负/平" or "客队不败" in rec or rec.startswith("客胜/平"):
        return {"away", "draw"}
    if rec == "胜/负" or "防平" in rec or rec.startswith("主胜/客胜"):
        return {"home", "away"}
    if rec in {"胜", "主胜"}:
        return {"home"}
    if rec in {"平", "平局"}:
        return {"draw"}
    if rec in {"负", "客胜"}:
        return {"away"}
    return None


def _odd_float(value: Any) -> float | None:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def _implied_two_way(
    first: float | None,
    second: float | None,
) -> tuple[float, float]:
    if first is None or second is None:
        return 0.5, 0.5
    inv_first, inv_second = 1.0 / first, 1.0 / second
    total = inv_first + inv_second
    if total <= 0:
        return 0.5, 0.5
    return inv_first / total, inv_second / total


def _parse_ou_line(line: Any) -> float | None:
    if line is None or line == "":
        return None
    text = str(line)
    digits = "".join(ch if (ch.isdigit() or ch == ".") else " " for ch in text).split()
    if not digits:
        return None
    try:
        n = float(digits[0])
    except ValueError:
        return None
    return n if n > 0 else None


def _format_line(line: float | str) -> str:
    try:
        n = float(str(line).replace(",", "."))
    except ValueError:
        return str(line)
    if float(n).is_integer():
        return str(int(n))
    return str(n)


def _ah_market_favorite(odds: dict[str, Any] | None) -> str | None:
    """Lower AH price ≈ market lean (home-side line)."""
    if not isinstance(odds, dict):
        return None
    ah = odds.get("asian_handicap")
    if not isinstance(ah, dict):
        return None
    home = _odd_float(ah.get("home"))
    away = _odd_float(ah.get("away"))
    if home is None or away is None:
        return None
    gap = abs(home - away) / max(min(home, away), 1e-6)
    if gap < 0.04:
        return None
    return "home" if home < away else "away"


def _market_ou_side(over: float | None, under: float | None) -> str | None:
    """Lower odd ≈ more likely. Always pick a side when both odds exist."""
    if over is None or under is None:
        return None
    if under < over:
        return "under"
    if over < under:
        return "over"
    return None


def _side_from_probs(probs: dict[str, float]) -> str:
    """Always return over|under."""
    spread = abs(probs["home"] - probs["away"])
    if probs["draw"] >= 0.28 and spread < 0.15:
        return "under"
    if max(probs["home"], probs["away"]) >= 0.48:
        return "over"
    if probs["draw"] >= max(probs["home"], probs["away"]) - 0.02:
        return "under"
    return "over"


def _ou_side_from_features(features: dict[str, float] | None) -> str | None:
    """Soft O/U hint from recent goal-diff / draw rates (local features only)."""
    if not features:
        return None
    hgd = float(features.get("home_gd_avg_5", 0.0) or 0.0)
    agd = float(features.get("away_gd_avg_5", 0.0) or 0.0)
    drawish = float(features.get("home_dr_5", 0.0) or 0.0) + float(
        features.get("away_dr_5", 0.0) or 0.0
    )
    if hgd >= 0.55 and agd >= 0.35:
        return "over"
    if hgd <= 0.15 and agd <= 0.15 and drawish >= 0.45:
        return "under"
    return None


def _resolve_ou_side(
    probs: dict[str, float],
    *,
    over: float | None,
    under: float | None,
    model_driven: bool,
    features: dict[str, float] | None,
) -> str:
    """Blend model / market / form for O/U. Prefer stable signals over one source."""
    model_side = _side_from_probs(probs)
    market_side = _market_ou_side(over, under)
    feat_side = _ou_side_from_features(features)

    if not model_driven:
        return market_side or feat_side or model_side

    # Clear market price on O/U → follow market over multifactor noise.
    if market_side and over is not None and under is not None:
        gap = abs(over - under) / max(min(over, under), 1e-6)
        if gap >= 0.06:
            return market_side

    # Form agrees with market → that side.
    if feat_side and market_side and feat_side == market_side:
        return feat_side

    # Drawish board + form under → under even if model says over lightly.
    if feat_side == "under" and probs["draw"] >= 0.30:
        return "under"

    return model_side


def _btts_yes(
    probs: dict[str, float],
    *,
    ou_side: str,
    line: float,
    features: dict[str, float] | None,
    odds: dict[str, Any] | None = None,
) -> bool:
    """BTTS lean from O/U market shape + 1X2 balance (+ optional form)."""
    score = 0.0
    ou = (odds or {}).get("goals_ou") if isinstance(odds, dict) else None
    ou = ou if isinstance(ou, dict) else {}
    over_odd = _odd_float(ou.get("home"))
    under_odd = _odd_float(ou.get("away"))
    market_side = _market_ou_side(over_odd, under_odd)
    if market_side == "under" and under_odd and over_odd:
        score -= 1.0 if line <= 2.5 else 0.75
    elif market_side == "over" and under_odd and over_odd:
        score += 1.0 if line >= 2.5 else 0.55

    if ou_side == "over":
        score += 0.35 if line >= 2.5 else 0.15
    else:
        score -= 0.35 if line <= 2.5 else 0.20

    spread = abs(probs["home"] - probs["away"])
    top = max(probs["home"], probs["away"])
    favorite = _primary_1x2_key(probs)
    if probs["draw"] >= 0.30:
        score += 0.1 if ou_side == "over" else -0.35
    if top >= 0.55 and probs["draw"] < 0.24:
        score -= 0.75
    if ou_side == "under" and favorite in ("home", "away") and top >= 0.45:
        score -= 0.40
    if spread < 0.10 and top < 0.46:
        score += 0.35

    if features:
        hgd = float(features.get("home_gd_avg_5", 0.0) or 0.0)
        agd = float(features.get("away_gd_avg_5", 0.0) or 0.0)
        if hgd > 0.35 and agd > 0.25:
            score += 0.45
        if hgd < 0.05 and agd < 0.05:
            score -= 0.45

    return score >= 0.0


def _reconcile_btts_with_scores(
    lines: list[tuple[int, int]],
    model_btts: bool,
) -> bool:
    """Tighten BTTS only when every reference score is a clean sheet.

    BTTS lean is model/market driven; do **not** promote 否→是 just because a
    secondary reference scoreline shows both teams scoring.
    """
    if not lines:
        return model_btts
    if all(h == 0 or a == 0 for h, a in lines):
        return False
    return model_btts


def _btts_score_for_outcomes(
    outcomes: set[str],
    probs: dict[str, float],
) -> tuple[int, int] | None:
    """Both-teams-score reference line consistent with 1X2 outcomes + strength."""
    h, d, a = probs["home"], probs["draw"], probs["away"]
    if outcomes == {"home"}:
        if h >= 0.54 and h - a >= 0.18:
            return (3, 1)
        if h >= 0.52:
            return (2, 1)
        return (3, 2) if d >= 0.27 else (2, 1)
    if outcomes == {"away"}:
        if a >= 0.54 and a - h >= 0.18:
            return (1, 3)
        if a >= 0.50:
            return (1, 2)
        return (1, 2)
    if outcomes == {"draw"}:
        return (1, 1)
    if outcomes == {"home", "draw"}:
        return (1, 1) if d >= 0.26 else (2, 1)
    if outcomes == {"away", "draw"}:
        return (1, 1) if d >= 0.26 else (1, 2)
    return None


def _score_matches_outcomes(h: int, a: int, outcomes: set[str]) -> bool:
    if "home" in outcomes and h > a:
        return True
    if "away" in outcomes and a > h:
        return True
    if "draw" in outcomes and h == a:
        return True
    return False


def _align_score_with_btts(
    lines: list[tuple[int, int]],
    *,
    btts_yes: bool,
    probs: dict[str, float],
    total: int,
    recommendation: str = "",
    ou_line: float | None = None,
    ou_side: str | None = None,
) -> list[tuple[int, int]]:
    """Keep score as display reference; nudge so it does not fight BTTS / 1X2 leans.

    When O/U is provided, never leave a score that fights the size lean (O/U
    outranks BTTS): e.g. 小 2.5 must not stay at 2-1 just to keep 双进:是.
    """
    if not lines:
        return lines
    outcomes = recommendation_outcomes(recommendation) or {_primary_1x2_key(probs)}
    single_outcome = len(outcomes) == 1
    out: list[tuple[int, int]] = []
    for h, a in lines:
        if btts_yes:
            if single_outcome:
                fixed = _btts_score_for_outcomes(outcomes, probs)
                if fixed and (h == 0 or a == 0 or not _score_matches_outcomes(h, a, outcomes)):
                    pair = fixed
                elif h == 0 and a == 0:
                    pair = (1, 1)
                elif h == 0:
                    pair = (1, max(1, a))
                elif a == 0:
                    pair = (max(1, h), 1)
                else:
                    pair = (h, a)
            elif h == 0 and a == 0:
                pair = (1, 1)
            elif h == 0:
                pair = (1, max(1, a))
            elif a == 0:
                pair = (max(1, h), 1)
            else:
                pair = (h, a)
        elif not btts_yes and h > 0 and a > 0:
            key = _primary_1x2_key(probs)
            if key == "draw":
                pair = (0, 0)
            elif key == "home":
                # Keep winner's goals; drop opponent only (2-1 → 2-0, not 3-0).
                pair = (max(h, 1), 0)
            else:
                pair = (0, max(a, 1))
        else:
            pair = (h, a)
        if ou_line is not None and ou_side in ("over", "under"):
            pair = _nudge_score_for_ou(
                pair[0],
                pair[1],
                line=ou_line,
                side=ou_side,
                btts_yes=btts_yes,
            )
        out.append(pair)
    seen: set[tuple[int, int]] = set()
    unique: list[tuple[int, int]] = []
    for pair in out:
        if pair not in seen:
            seen.add(pair)
            unique.append(pair)
    return unique


def _target_total(line: float, side: str) -> int:
    """Map O/U line + side to a reference goal total for score hints."""
    if side == "under":
        return max(0, _max_goals_under(line))
    return max(1, _min_goals_over(line))

def _primary_1x2_key(probs: dict[str, float]) -> str:
    return max(("home", "draw", "away"), key=lambda k: probs[k])


def _split_score(total: int, probs: dict[str, float]) -> tuple[int, int]:
    """Build a concrete scoreline from total goals + primary 1X2 winner.

    When home/away are nearly tied, avoid blowouts like 2-0 that fight a weak edge.
    """
    key = _primary_1x2_key(probs)
    h, d, a = probs["home"], probs["draw"], probs["away"]
    if total <= 0:
        return 0, 0
    close_sides = abs(h - a) < _DOUBLE_CHANCE_EDGE
    if key == "draw":
        home = total // 2
        return home, total - home
    if key == "home":
        if close_sides:
            return (1, 0) if total <= 2 else (2, 1)
        if h >= 0.55 and d < 0.24 and total >= 3:
            return min(total, 3), 0
        if total == 2:
            return (2, 0) if h >= 0.50 else (1, 0)
        away = (total - 1) // 2
        if away >= total - away:
            away = max(0, total - away - 1)
        if total >= 3 and away == 0:
            away = 1
        home = total - away
        if home <= away:
            return away + 1, max(0, total - away - 1)
        return home, away
    if close_sides:
        return (0, 1) if total <= 2 else (1, 2)
    if a >= 0.55 and d < 0.24 and total >= 3:
        return 0, min(total, 3)
    if total == 2:
        return (0, 2) if a >= 0.50 else (0, 1)
    home = (total - 1) // 2
    if home >= total - home:
        home = max(0, total - home - 1)
    if total >= 3 and home == 0:
        home = 1
    away = total - home
    if away <= home:
        return max(0, total - home - 1), home + 1
    return home, away


def _handicap_bundle(
    odds: dict[str, Any] | None,
    recommendation: str | None = None,
    *,
    league_id: int | None = None,
    features: dict[str, float] | None = None,
    score_hint: str | None = None,
) -> tuple[str, str]:
    from app.services.ah_predictor import handicap_bundle_from_markets

    return handicap_bundle_from_markets(
        odds,
        recommendation,
        league_id=league_id,
        features=features,
        score_hint=score_hint,
    )


def resolve_handicap_bundle(
    odds: dict[str, Any] | None,
    recommendation: str | None,
    *,
    league_id: int | None = None,
    features: dict[str, float] | None = None,
    stored: str | None = None,
    score_hint: str | None = None,
    prefer_stored: bool = False,
) -> tuple[str, str]:
    """Resolve handicap lean; frozen exam snapshots must not be recomputed."""
    from app.services.ah_features import display_handicap_lean, extract_main_ah_line

    text = (stored or "").strip()
    if prefer_stored and text:
        line_f, _, _ = extract_main_ah_line(odds if isinstance(odds, dict) else None)
        return display_handicap_lean(text, line_f) or text, ""

    ah = (odds or {}).get("asian_handicap") if isinstance(odds, dict) else None
    if isinstance(odds, dict) and odds.get("available") and isinstance(ah, dict):
        return _handicap_bundle(
            odds,
            recommendation,
            league_id=league_id,
            features=features,
            score_hint=score_hint,
        )
    if text:
        line_f, _, _ = extract_main_ah_line(odds if isinstance(odds, dict) else None)
        return display_handicap_lean(text, line_f) or text, ""
    return "缺少盘口数据分析", ""


def _score_settles_ou(home: int, away: int, line: float, side: str) -> bool:
    goals = home + away
    if side == "over":
        return goals > line
    return goals < line


def _min_goals_over(line: float) -> int:
    """Smallest integer total that settles over (2.5 → 3, 3.0 → 4)."""
    return int(line) + 1


def _max_goals_under(line: float) -> int:
    """Largest integer total that settles under (2.5 → 2, 3.0 → 2)."""
    whole = int(line)
    if line > whole:
        return whole
    return max(0, whole - 1)


def _draw_scoreline_for_ou(
    preferred_total: int,
    line: float,
    side: str,
) -> tuple[int, int]:
    """Draw scoreline that settles the O/U lean (1-1 never with 大 2.5)."""
    preferred = max(0, int(preferred_total))
    if side == "over":
        need = _min_goals_over(line)
        if need % 2 == 1:
            need += 1
        total = max(preferred if preferred % 2 == 0 else preferred + 1, need)
        if total % 2 == 1:
            total += 1
        while not _score_settles_ou(total // 2, total // 2, line, "over"):
            total += 2
        return total // 2, total // 2

    cap = _max_goals_under(line)
    if cap % 2 == 1:
        cap -= 1
    total = min(preferred if preferred % 2 == 0 else preferred - 1, cap)
    total = max(0, total)
    if total % 2 == 1:
        total -= 1
    while total > 0 and not _score_settles_ou(total // 2, total // 2, line, "under"):
        total -= 2
    return total // 2, total // 2


def _nudge_score_for_ou(
    home: int,
    away: int,
    *,
    line: float,
    side: str,
    btts_yes: bool,
) -> tuple[int, int]:
    """Keep this scoreline's 1X2 result; bump/cut goals so O/U does not fight."""
    h, a = int(home), int(away)
    if _score_settles_ou(h, a, line, side):
        return h, a
    if h == a:
        return _draw_scoreline_for_ou(h + a, line, side)

    home_win = h > a
    if side == "over":
        need = _min_goals_over(line)
        if btts_yes:
            if home_win:
                na = max(a, 1)
                nh = max(h, na + 1, need - na)
                if nh <= na:
                    nh = na + 1
                return nh, na
            nh = max(h, 1)
            na = max(a, nh + 1, need - nh)
            if na <= nh:
                na = nh + 1
            return nh, na
        if home_win:
            return max(need, 1), 0
        return 0, max(need, 1)

    cap = _max_goals_under(line)
    if cap <= 0:
        return 0, 0
    if btts_yes and cap >= 3:
        # 2-1 / 1-2 is the leanest both-score win under a high line.
        return (2, 1) if home_win else (1, 2)
    # O/U outranks BTTS when under line cannot host both teams scoring.
    if home_win:
        return min(max(h, 1), cap), 0
    return 0, min(max(a, 1), cap)


def _align_score_with_ou(
    lines: list[tuple[int, int]],
    *,
    line: float,
    ou_side: str,
    btts_yes: bool,
) -> list[tuple[int, int]]:
    """Nudge reference scores so none fight the O/U lean."""
    if not lines:
        return lines
    out: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for home, away in lines:
        fixed = _nudge_score_for_ou(
            home,
            away,
            line=line,
            side=ou_side,
            btts_yes=btts_yes,
        )
        if fixed not in seen:
            seen.add(fixed)
            out.append(fixed)
    return out


def _score_hints_for_recommendation(
    recommendation: str,
    probs: dict[str, float],
    total: int,
    *,
    btts_yes: bool,
    ou_side: str,
    ou_line: float,
) -> tuple[str, list[tuple[int, int]]]:
    """Build reference score(s) consistent with 胜平负推荐.

    双选时给多个比分（用 / 连接），避免「主胜/平却只给 2-0」这类打架。
    平局参考分必须能结算大小球：大 2.5 → 2-2，不能再落到 1-1。
    """
    rec = (recommendation or "").strip()
    outcomes = recommendation_outcomes(rec) or {_primary_1x2_key(probs)}
    lines: list[tuple[int, int]] = []

    def _draw_ref() -> tuple[int, int]:
        if ou_side == "under" and not btts_yes:
            return _draw_scoreline_for_ou(0, ou_line, ou_side)
        return _draw_scoreline_for_ou(total, ou_line, ou_side)

    def _side_win_ref(winner: str) -> tuple[int, int]:
        """Winner home|away; always settle O/U and keep that side winning."""
        if winner == "home":
            raw_h, raw_a = (2, 1) if btts_yes else (max(total, 1), 0)
            if raw_h <= raw_a:
                raw_h, raw_a = raw_a + 1, raw_a
        else:
            raw_h, raw_a = (1, 2) if btts_yes else (0, max(total, 1))
            if raw_a <= raw_h:
                raw_h, raw_a = raw_h, raw_h + 1
        return _nudge_score_for_ou(
            raw_h, raw_a, line=ou_line, side=ou_side, btts_yes=btts_yes
        )

    if outcomes == {"draw"}:
        lines.append(_draw_ref())
    elif outcomes == {"home", "draw"}:
        lines.append(_side_win_ref("home"))
        lines.append(_draw_ref())
    elif outcomes == {"away", "draw"}:
        lines.append(_side_win_ref("away"))
        lines.append(_draw_ref())
    elif outcomes == {"home", "away"}:
        lines.append(_side_win_ref("home"))
        lines.append(_side_win_ref("away"))
    elif outcomes == {"home"}:
        split = _split_score(max(1, total), probs)
        lines.append(
            _nudge_score_for_ou(
                split[0], split[1], line=ou_line, side=ou_side, btts_yes=btts_yes
            )
        )
    elif outcomes == {"away"}:
        split = _split_score(max(1, total), probs)
        lines.append(
            _nudge_score_for_ou(
                split[0], split[1], line=ou_line, side=ou_side, btts_yes=btts_yes
            )
        )
    else:
        split = _split_score(max(0, total), probs)
        lines.append(
            _nudge_score_for_ou(
                split[0], split[1], line=ou_line, side=ou_side, btts_yes=btts_yes
            )
        )

    # Deduplicate while preserving order.
    seen: set[tuple[int, int]] = set()
    unique: list[tuple[int, int]] = []
    for pair in lines:
        if pair not in seen:
            seen.add(pair)
            unique.append(pair)
    text = " / ".join(f"{h}-{a}" for h, a in unique)
    return text, unique


def derive_prediction_leans(
    probs: dict[str, float],
    odds: dict[str, Any] | None = None,
    features: dict[str, float] | None = None,
    *,
    league_id: int | None = None,
) -> dict[str, str]:
    """Derive O/U, BTTS, score and handicap leans from 1X2 + markets.

    Priority for product accuracy: 1X2 → O/U → BTTS. Reference scorelines are
    reconciled with O/U then BTTS so「1-1」never pairs with「大（2.5）」or「双进:否」.

    Flat prior with local odds → use odds-implied 1X2 (no API).
    Flat prior and no usable odds → 待分析.

    ML goal model only **overrides** a lean when that target gate is open.
    Closed gates keep the heuristic/market lean — never blank to 待分析.

    Frozen ``pre_match_data`` snapshots are written at analysis time; changing
    this function only affects **future** analyses (historical audit stays).
    """
    normalized = resolve_match_probabilities(probs, odds)
    if is_flat_prior(normalized):
        has_ah = isinstance((odds or {}).get("asian_handicap"), dict) if odds else False
        return {
            "goal_lean": "大小：待分析",
            "both_score_lean": "双进:待分析",
            "score_hint": "比分:待分析",
            "handicap_lean": "让球：待分析" if has_ah else "缺少盘口数据分析",
            "handicap_market_note": "",
        }

    ou = (odds or {}).get("goals_ou") if isinstance(odds, dict) else None
    ou = ou if isinstance(ou, dict) else {}
    line = _parse_ou_line(ou.get("line")) or 2.5
    from app.services.goal_predictor import distribution_summary, predict_goals

    goal_prediction = predict_goals(features, odds)
    distribution = (
        distribution_summary(goal_prediction, total_line=line)
        if goal_prediction is not None
        else None
    )

    over = _odd_float(ou.get("home"))
    under = _odd_float(ou.get("away"))
    model_driven = not is_flat_prior(normalize_probabilities(probs or {}))
    side = _resolve_ou_side(
        normalized,
        over=over,
        under=under,
        model_driven=model_driven,
        features=features,
    )
    if (
        goal_prediction is not None
        and goal_prediction.deploy_ou
        and distribution is not None
    ):
        side = "over" if distribution["over_prob"] >= 0.5 else "under"
    total = _target_total(line, side)
    line_label = _format_line(line)
    goal_lean = (
        f"大({line_label})" if side == "over" else f"小({line_label})"
    )

    recommendation = get_recommendation(
        normalized, odds=odds, features=features
    )
    btts_yes = _btts_yes(
        normalized,
        ou_side=side,
        line=line,
        features=features,
        odds=odds if isinstance(odds, dict) else None,
    )
    if (
        goal_prediction is not None
        and goal_prediction.deploy_btts
        and distribution is not None
    ):
        btts_yes = distribution["btts_prob"] >= 0.5

    score_lines: list[tuple[int, int]] = []
    if (
        goal_prediction is not None
        and goal_prediction.deploy_score
        and distribution is not None
    ):
        score_lines = [(h, a) for h, a, _ in distribution["scores"]]
    if not score_lines:
        _, score_lines = _score_hints_for_recommendation(
            recommendation,
            normalized,
            total,
            btts_yes=btts_yes,
            ou_side=side,
            ou_line=line,
        )
    score_lines = _align_score_with_btts(
        score_lines,
        btts_yes=btts_yes,
        probs=normalized,
        total=total,
        recommendation=recommendation,
        ou_line=line,
        ou_side=side,
    )
    score_lines = _align_score_with_ou(
        score_lines,
        line=line,
        ou_side=side,
        btts_yes=btts_yes,
    )
    btts_yes = _reconcile_btts_with_scores(score_lines, btts_yes)
    score_hint = (
        f"比分:{' / '.join(f'{h}-{a}' for h, a in score_lines)}"
        if score_lines
        else "比分:待分析"
    )
    both_score_lean = "双进:是" if btts_yes else "双进:否"
    handicap_lean, handicap_market_note = _handicap_bundle(
        odds if isinstance(odds, dict) else None,
        recommendation=recommendation,
        league_id=league_id,
        features=features,
        score_hint=score_hint,
    )
    return {
        "recommendation": recommendation,
        "goal_lean": goal_lean,
        "both_score_lean": both_score_lean,
        "score_hint": score_hint,
        "handicap_lean": handicap_lean,
        "handicap_market_note": handicap_market_note,
    }


def _clamp(n: float, lo: float, hi: float) -> float:
    return min(hi, max(lo, n))


def adjust_probabilities_with_factors(
    base: dict[str, float],
    factor_ids: list[str],
) -> dict[str, float]:
    """Apply explicit opinion tags to 1X2 probabilities (transparent deltas)."""
    home = float(base.get("home", DEFAULT_PROB))
    draw = float(base.get("draw", DEFAULT_PROB))
    away = float(base.get("away", DEFAULT_PROB))
    seen: set[str] = set()
    for fid in factor_ids:
        if fid in seen:
            continue
        seen.add(fid)
        delta = _FACTOR_DELTAS.get(fid)
        if not delta:
            continue
        home += delta.get("home", 0.0)
        draw += delta.get("draw", 0.0)
        away += delta.get("away", 0.0)
    home = _clamp(home, 0.05, 0.85)
    draw = _clamp(draw, 0.05, 0.7)
    away = _clamp(away, 0.05, 0.85)
    return normalize_probabilities({"home": home, "draw": draw, "away": away})


def build_prediction_snapshot(
    probs: dict[str, float],
    odds: dict[str, Any] | None = None,
    features: dict[str, float] | None = None,
    *,
    league_id: int | None = None,
) -> dict[str, Any]:
    # Odds-implied fills flat placeholders so 1X2 + leans stay consistent.
    normalized = resolve_match_probabilities(probs, odds)
    leans = derive_prediction_leans(
        normalized, odds, features=features, league_id=league_id
    )
    return {
        "home_win_prob": round(normalized["home"], 4),
        "draw_prob": round(normalized["draw"], 4),
        "away_win_prob": round(normalized["away"], 4),
        **leans,
    }


def _parse_score_hint(score_hint: str) -> list[tuple[int, int]]:
    """Extract all candidate scores from hints like ``2-1`` or ``2-1 / 1-1``."""
    text = (score_hint or "").strip()
    if not text or "待分析" in text:
        return []
    found: list[tuple[int, int]] = []
    for match in re.finditer(r"(\d+)\s*[-:]\s*(\d+)", text):
        try:
            found.append((int(match.group(1)), int(match.group(2))))
        except ValueError:
            continue
    return found


def _parse_goal_lean(goal_lean: str) -> tuple[str, float] | None:
    """Parse current ``大(2.5)`` and historical ``倾向大球（2.5）`` / ``大（2.5）``."""
    text = (goal_lean or "").strip()
    match = re.search(r"(?:倾向)?(大球|小球|大|小)[（(](.+?)[）)]", text)
    if not match:
        return None
    side = "over" if match.group(1) in {"大球", "大"} else "under"
    try:
        line = float(str(match.group(2)).replace(",", ".").strip())
    except ValueError:
        return None
    return side, line


def evaluate_prediction_vs_score(
    *,
    home_goals: int | None,
    away_goals: int | None,
    score_hint: str,
    goal_lean: str,
    both_score_lean: str,
    recommendation: str = "",
) -> dict[str, Any]:
    """Compare pre-match leans against regulation-time (90') score.

    ``home_goals`` / ``away_goals`` must be fulltime, not AET/PEN boards.
    Returns hit flags (True/False/None). None = not evaluable (no FT / 待分析 / push).
    """
    result: dict[str, Any] = {
        "result_hit": None,
        "score_hit": None,
        "ou_hit": None,
        "btts_hit": None,
        "evaluable": False,
    }
    if home_goals is None or away_goals is None:
        return result

    total = home_goals + away_goals
    actual_btts = home_goals > 0 and away_goals > 0
    result["evaluable"] = True

    if home_goals > away_goals:
        actual_1x2 = "home"
    elif home_goals < away_goals:
        actual_1x2 = "away"
    else:
        actual_1x2 = "draw"

    rec = (recommendation or "").strip()
    outcomes = recommendation_outcomes(rec)
    if outcomes is not None:
        result["result_hit"] = actual_1x2 in outcomes

    pred_scores = _parse_score_hint(score_hint)
    if pred_scores:
        actual = (home_goals, away_goals)
        result["score_hit"] = actual in pred_scores

    parsed_ou = _parse_goal_lean(goal_lean)
    if parsed_ou is not None:
        side, line = parsed_ou
        # Half-lines never push; integer lines push when total == line.
        if abs(total - line) < 1e-9:
            result["ou_hit"] = None
        elif side == "over":
            result["ou_hit"] = total > line
        else:
            result["ou_hit"] = total < line

    lean = (both_score_lean or "").strip()
    if lean.endswith("：是") or lean.endswith(":是"):
        result["btts_hit"] = actual_btts is True
    elif lean.endswith("：否") or lean.endswith(":否"):
        result["btts_hit"] = actual_btts is False

    return result


def summarize_accuracy(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate hit rates for all frozen pre-match prediction dimensions."""

    def _rate(key: str) -> dict[str, Any]:
        judged = [r[key] for r in rows if r.get(key) is not None]
        hits = sum(1 for v in judged if v is True)
        total = len(judged)
        return {
            "hits": hits,
            "total": total,
            "rate": round(hits / total, 4) if total else None,
        }

    return {
        "result": _rate("result_hit"),
        "single_result": _rate("single_result_hit"),
        "score": _rate("score_hit"),
        "ou": _rate("ou_hit"),
        "btts": _rate("btts_hit"),
        "handicap": _rate("handicap_hit"),
        "fixtures_with_prediction": sum(1 for r in rows if r.get("has_prediction")),
        "fixtures_finished": sum(1 for r in rows if r.get("evaluable")),
    }
