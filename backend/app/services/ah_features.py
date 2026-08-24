"""Asian handicap (让球穿盘) features and label settlement."""

from __future__ import annotations

import json
import math
import re
from typing import Any

from app.services.features import FEATURE_NAMES, extract_features

AH_FEATURE_VERSION = "ah_v2"

TOP5_LEAGUE_IDS = frozenset({39, 140, 78, 135, 61})
ASIA_LEAGUE_IDS = frozenset({169, 98, 292, 253})

# Appended to frozen 1X2 feature vector for AH training / inference.
AH_EXTRA_NAMES: list[str] = [
    "ah_line_norm",
    "ah_home_odd_inv",
    "ah_away_odd_inv",
    "ah_water_diff",
    "ah_implied_cover",
    "ah_line_abs_norm",
    "ah_tier_shallow",
    "ah_tier_medium",
    "ah_tier_deep",
    "ah_is_giving",
    "mx_home_prob",
    "mx_draw_prob",
    "mx_away_prob",
    "mx_vs_ah_gap",
    "league_tier_top5",
    "league_tier_asia",
    "has_ah_market",
    # 副盘：让 0 与其它档只作主盘参考，不改训练标签。
    "ah_has_level_line",
    "ah_level_water_diff",
    "ah_level_away_hot",
    "ah_has_aux_lines",
    "ah_aux_away_hot_share",
    # 初盘 → 即时盘：同线升降水。
    "ah_opening_same_line",
    "ah_home_odd_drift",
    "ah_away_odd_drift",
    "ah_water_drift",
    "ah_away_steam",
]

AH_FEATURE_NAMES: list[str] = [*FEATURE_NAMES, *AH_EXTRA_NAMES]


def dumps_ah_features(features: dict[str, float]) -> str:
    ordered = {name: float(features.get(name, 0.0)) for name in AH_FEATURE_NAMES}
    return json.dumps(ordered, ensure_ascii=False)


def loads_ah_features(raw: str | None) -> dict[str, float]:
    if not raw:
        return {name: 0.0 for name in AH_FEATURE_NAMES}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {name: 0.0 for name in AH_FEATURE_NAMES}
    if not isinstance(data, dict):
        return {name: 0.0 for name in AH_FEATURE_NAMES}
    return {name: float(data.get(name, 0.0)) for name in AH_FEATURE_NAMES}


def ah_feature_vector(features: dict[str, float]) -> list[float]:
    return [float(features.get(name, 0.0)) for name in AH_FEATURE_NAMES]


def _odd_float(value: Any) -> float | None:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def _parse_line_float(line_raw: Any) -> float | None:
    if line_raw is None or line_raw == "":
        return None
    text = str(line_raw).strip().replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def extract_main_ah_line(
    odds: dict[str, Any] | None,
) -> tuple[float | None, float | None, float | None]:
    """Main AH line + home/away decimal odds from parsed odds package."""
    if not isinstance(odds, dict) or not odds.get("available", True):
        return None, None, None
    ah = odds.get("asian_handicap")
    if not isinstance(ah, dict):
        return None, None, None

    line_raw = ah.get("line")
    home_raw = ah.get("home")
    away_raw = ah.get("away")
    lines = ah.get("lines")
    if (line_raw is None or home_raw is None or away_raw is None) and isinstance(lines, list):
        for item in lines:
            if not isinstance(item, dict):
                continue
            line_raw = item.get("line")
            home_raw = item.get("home")
            away_raw = item.get("away")
            if line_raw is not None and home_raw is not None and away_raw is not None:
                break

    line_f = _parse_line_float(line_raw)
    home_f = _odd_float(home_raw)
    away_f = _odd_float(away_raw)
    if line_f is None or home_f is None or away_f is None:
        return None, None, None
    return line_f, home_f, away_f


def iter_ah_quotes(odds: dict[str, Any] | None) -> list[tuple[float, float, float]]:
    """Complete AH quotes ``(line, home_odd, away_odd)``; main line first."""
    if not isinstance(odds, dict) or not odds.get("available", True):
        return []
    ah = odds.get("asian_handicap")
    if not isinstance(ah, dict):
        return []
    quotes: list[tuple[float, float, float]] = []
    seen: set[float] = set()

    def _add(line_raw: Any, home_raw: Any, away_raw: Any) -> None:
        line_f = _parse_line_float(line_raw)
        home_f = _odd_float(home_raw)
        away_f = _odd_float(away_raw)
        if line_f is None or home_f is None or away_f is None:
            return
        key = round(line_f, 2)
        if key in seen:
            return
        seen.add(key)
        quotes.append((line_f, home_f, away_f))

    _add(ah.get("line"), ah.get("home"), ah.get("away"))
    lines = ah.get("lines")
    if isinstance(lines, list):
        for item in lines:
            if isinstance(item, dict):
                _add(item.get("line"), item.get("home"), item.get("away"))
    return quotes


def _find_level_quote(
    quotes: list[tuple[float, float, float]],
) -> tuple[float, float, float] | None:
    for line_f, home_f, away_f in quotes:
        if abs(line_f) < 0.05:
            return line_f, home_f, away_f
    return None


def _clip(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _board_context_features(
    current: dict[str, Any] | None,
    opening: dict[str, Any] | None,
    *,
    main_line: float,
    main_home: float,
    main_away: float,
) -> dict[str, float]:
    quotes = iter_ah_quotes(current)
    level = _find_level_quote(quotes)
    aux = [(ln, h, a) for ln, h, a in quotes if abs(ln - main_line) > 0.04]
    if aux:
        away_hot_n = sum(1 for _, h, a in aux if a < h)
        aux_share = away_hot_n / len(aux)
    else:
        aux_share = 0.5

    open_line, open_home, open_away = extract_main_ah_line(opening)
    same_line = (
        open_line is not None
        and open_home is not None
        and open_away is not None
        and abs(open_line - main_line) < 0.04
    )
    home_drift = (main_home - open_home) if same_line else 0.0
    away_drift = (main_away - open_away) if same_line else 0.0
    open_water = (open_home - open_away) if same_line else (main_home - main_away)
    water_drift = (main_home - main_away) - open_water if same_line else 0.0
    steam = 1.0 if same_line and home_drift > 0.02 and away_drift < -0.02 else 0.0

    return {
        "ah_has_level_line": 1.0 if level else 0.0,
        "ah_level_water_diff": (level[1] - level[2]) if level else 0.0,
        "ah_level_away_hot": 1.0 if level and level[2] < level[1] else 0.0,
        "ah_has_aux_lines": 1.0 if aux else 0.0,
        "ah_aux_away_hot_share": aux_share,
        "ah_opening_same_line": 1.0 if same_line else 0.0,
        "ah_home_odd_drift": _clip(home_drift, -0.8, 0.8),
        "ah_away_odd_drift": _clip(away_drift, -0.8, 0.8),
        "ah_water_drift": _clip(water_drift, -0.8, 0.8),
        "ah_away_steam": steam,
    }


def _empty_board_context() -> dict[str, float]:
    return {
        "ah_has_level_line": 0.0,
        "ah_level_water_diff": 0.0,
        "ah_level_away_hot": 0.0,
        "ah_has_aux_lines": 0.0,
        "ah_aux_away_hot_share": 0.5,
        "ah_opening_same_line": 0.0,
        "ah_home_odd_drift": 0.0,
        "ah_away_odd_drift": 0.0,
        "ah_water_drift": 0.0,
        "ah_away_steam": 0.0,
    }


def _league_tier_flags(league_id: int | None) -> tuple[float, float]:
    if league_id in TOP5_LEAGUE_IDS:
        return 1.0, 0.0
    if league_id in ASIA_LEAGUE_IDS:
        return 0.0, 1.0
    return 0.0, 0.0


def _implied_cover_prob(home_odd: float, away_odd: float) -> float:
    inv_h, inv_a = 1.0 / home_odd, 1.0 / away_odd
    total = inv_h + inv_a
    if total <= 0:
        return 0.5
    return inv_h / total


def _market_1x2_probs(base: dict[str, float]) -> tuple[float, float, float]:
    """Normalize 1X2 implied probs from frozen market odds (never model output)."""
    ph = float(base.get("odds_home", 1 / 3))
    pd = float(base.get("odds_draw", 1 / 3))
    pa = float(base.get("odds_away", 1 / 3))
    total = ph + pd + pa
    if total <= 0:
        return 1 / 3, 1 / 3, 1 / 3
    return ph / total, pd / total, pa / total


def _line_tier_flags(line_f: float) -> tuple[float, float, float]:
    al = abs(line_f)
    if al <= 0.75:
        return 1.0, 0.0, 0.0
    if al <= 1.35:
        return 0.0, 1.0, 0.0
    return 0.0, 0.0, 1.0


ASIAN_WIN = "win"
ASIAN_HALF_WIN = "half_win"
ASIAN_PUSH = "push"
ASIAN_HALF_LOSS = "half_loss"
ASIAN_LOSS = "loss"

HANDICAP_RULESET_ASIAN = "asian"
HANDICAP_RULESET_JC = "jc"
HandicapRuleset = str


def parse_handicap_ruleset(value: str | None) -> str:
    text = (value or "").strip().lower()
    if text in {"jc", "jingcai", "lottery", "three-way", "three_way"}:
        return HANDICAP_RULESET_JC
    return HANDICAP_RULESET_ASIAN


def jc_handicap_line(line_f: float) -> float:
    """竞彩只挂整数让球线：非整数按绝对值向上取整（-0.25/-0.5/-0.75 → -1）。"""
    value = float(line_f)
    magnitude = math.ceil(abs(value) - 1e-9)
    if magnitude <= 0:
        return 0.0
    return float(magnitude) if value > 0 else float(-magnitude)


def _split_quarter_line(line_f: float) -> tuple[float, ...]:
    """Split x.25/x.75 into the two adjacent half-goal boards."""
    quarters = round(float(line_f) * 4)
    if abs(float(line_f) * 4 - quarters) > 1e-7 or quarters % 2 == 0:
        return (float(line_f),)
    lower = (quarters - 1) / 4
    upper = (quarters + 1) / 4
    return (lower, upper)


def _combine_split_results(parts: list[int]) -> str:
    """Combine split-board wins (1), pushes (0), and losses (-1)."""
    if all(part > 0 for part in parts):
        return ASIAN_WIN
    if any(part > 0 for part in parts) and any(part == 0 for part in parts):
        return ASIAN_HALF_WIN
    if all(part == 0 for part in parts):
        return ASIAN_PUSH
    if any(part < 0 for part in parts) and any(part == 0 for part in parts):
        return ASIAN_HALF_LOSS
    return ASIAN_LOSS


def settle_asian_total(
    total_goals: int | None,
    line_f: float | None,
    *,
    over: bool,
) -> str | None:
    """Settle an O/U selection, including x.25/x.75 split boards."""
    if total_goals is None or line_f is None:
        return None
    parts: list[int] = []
    for split_line in _split_quarter_line(line_f):
        margin = float(total_goals) - split_line
        if not over:
            margin = -margin
        parts.append(0 if abs(margin) < 1e-9 else (1 if margin > 0 else -1))
    return _combine_split_results(parts)


def settle_handicap_pick(
    home_goals: int | None,
    away_goals: int | None,
    line_f: float | None,
    pick: str,
    *,
    ruleset: str = HANDICAP_RULESET_ASIAN,
) -> str | None:
    """Settle one 让胜/让平/让负 selection.

    Asian (default): integer exact handicap is a walk for every selection;
    quarter lines use true split boards (赢半 / 输半).
    Jingcai: the line is first rounded away from zero to a whole goal, then
    settled three-way — never half win / half loss.
    """
    if home_goals is None or away_goals is None or line_f is None:
        return None
    mode = parse_handicap_ruleset(ruleset)
    line = float(line_f)
    if mode == HANDICAP_RULESET_JC:
        line = jc_handicap_line(line)
        margin = float(home_goals) + line - float(away_goals)
        if abs(margin) < 1e-9:
            # 平手盘打平没有让球可言，仍按走水处理
            if abs(line) < 1e-9:
                return ASIAN_PUSH
            return ASIAN_WIN if pick == "让平" else ASIAN_LOSS
        actual = "让胜" if margin > 0 else "让负"
        return ASIAN_WIN if pick == actual else ASIAN_LOSS

    margin = float(home_goals) + line - float(away_goals)
    integer_line = abs(line - round(line)) < 1e-9
    if integer_line:
        if abs(margin) < 1e-9:
            return ASIAN_PUSH
        actual = "让胜" if margin > 0 else "让负"
        return ASIAN_WIN if pick == actual else ASIAN_LOSS
    if pick == "让平":
        return ASIAN_LOSS

    parts: list[int] = []
    for split_line in _split_quarter_line(line):
        split_margin = float(home_goals) + split_line - float(away_goals)
        if pick == "让负":
            split_margin = -split_margin
        elif pick != "让胜":
            return None
        parts.append(
            0
            if abs(split_margin) < 1e-9
            else (1 if split_margin > 0 else -1)
        )
    return _combine_split_results(parts)


def asian_result_counts_as_hit(result: str | None) -> bool | None:
    """Product accuracy: full/half win and half loss count; pushes are separate."""
    if result is None or result == ASIAN_PUSH:
        return None
    return result in {ASIAN_WIN, ASIAN_HALF_WIN, ASIAN_HALF_LOSS}


def settle_ah_label(
    home_goals: int | None,
    away_goals: int | None,
    line_f: float | None,
) -> str | None:
    """Return cover | no_cover | push | None."""
    if home_goals is None or away_goals is None or line_f is None:
        return None
    margin = float(home_goals) + float(line_f) - float(away_goals)
    if abs(margin) < 1e-9:
        return "push"
    return "cover" if margin > 0 else "no_cover"


def settle_handicap_result(
    home_goals: int | None,
    away_goals: int | None,
    line_f: float | None,
    *,
    ruleset: str = HANDICAP_RULESET_ASIAN,
) -> str | None:
    """Display the handicap result, including split-board outcomes."""
    if home_goals is None or away_goals is None or line_f is None:
        return None
    mode = parse_handicap_ruleset(ruleset)
    line = float(line_f)
    if mode == HANDICAP_RULESET_JC:
        line = jc_handicap_line(line)
        margin = float(home_goals) + line - float(away_goals)
        if abs(margin) < 1e-9:
            return "走水" if abs(line) < 1e-9 else "让平"
        return "让胜" if margin > 0 else "让负"

    margin = float(home_goals) + line - float(away_goals)
    integer_line = abs(line - round(line)) < 1e-9
    if integer_line and abs(margin) < 1e-9:
        return "走水"
    home_result = settle_handicap_pick(
        home_goals, away_goals, line, "让胜", ruleset=mode
    )
    if home_result == ASIAN_HALF_WIN:
        return "让胜赢半 / 让负输半"
    if home_result == ASIAN_HALF_LOSS:
        return "让胜输半 / 让负赢半"
    label = settle_ah_label(home_goals, away_goals, line_f)
    if label is None:
        return None
    return pick_to_lean(label)


def handicap_picks_from_lean(lean: str | None) -> set[str]:
    """Parse one or two frozen AH picks from display text.

    Tolerates both the current 「让胜」 labels and legacy 「让球胜」 snapshots.
    """
    text = (lean or "").strip()
    pick_text = re.split(r"[（(]", text, maxsplit=1)[0]
    picks: set[str] = set()
    if "胜" in pick_text:
        picks.add("让胜")
    if "平" in pick_text:
        picks.add("让平")
    if "负" in pick_text:
        picks.add("让负")
    return picks


def handicap_pick_from_lean(lean: str | None) -> str | None:
    """Backward-compatible single pick; dual picks have no single answer."""
    picks = handicap_picks_from_lean(lean)
    return next(iter(picks)) if len(picks) == 1 else None


def handicap_line_from_lean(lean: str | None) -> float | None:
    """Fallback line parser for frozen rows whose odds package is unavailable."""
    text = (lean or "").strip()
    home_give = re.search(r"[（(]\s*主让\s*(\d+(?:\.\d+)?)\s*[）)]", text)
    if home_give:
        try:
            return -float(home_give.group(1))
        except ValueError:
            return None
    away_give = re.search(r"[（(]\s*客让\s*(\d+(?:\.\d+)?)\s*[）)]", text)
    if away_give:
        try:
            return float(away_give.group(1))
        except ValueError:
            return None
    if re.search(r"[（(]\s*平手\s*[）)]", text):
        return 0.0
    # Legacy signed home-side line: 让胜（-1） / 让负（+0.5）
    match = re.search(r"[（(]\s*([+-]?\d+(?:\.\d+)?)\s*[）)]", text)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _line_magnitude_text(line_f: float) -> str:
    mag = abs(float(line_f))
    if mag == int(mag):
        return str(int(mag))
    return str(mag)


def format_ah_line(line_f: float) -> str:
    """Signed home-side AH line: 主让为负、客让为正、平手为 0。"""
    value = float(line_f)
    if abs(value) < 1e-9:
        return "0"
    text = _line_magnitude_text(value)
    return f"-{text}" if value < 0 else f"+{text}"


def format_handicap_lean_text(pick: str, line_f: float | None) -> str:
    """Canonical lean for storage/UI: 让负(-1) / 让胜(+0.5) / 让平(0).

    Half-width parentheses keep recommendation tags narrower on phone.
    """
    base = pick_to_lean(pick)
    if line_f is None:
        return base
    return f"{base}({format_ah_line(line_f)})"


def _lean_base(picks: set[str]) -> str:
    """Canonical 让X / 让X/Y copy for one or two picks."""
    if picks == {"让胜", "让负"}:
        base = "胜/负"
    elif picks == {"让负", "让平"}:
        base = "负/平"
    elif picks == {"让胜", "让平"}:
        base = "胜/平"
    else:
        base = next(iter(picks)).removeprefix("让")
    return f"让{base}"


def display_handicap_lean(lean: str | None, line_f: float | None = None) -> str | None:
    """Normalize frozen lean for display; attach signed line when known."""
    text = (lean or "").strip()
    if not text:
        return None
    picks = handicap_picks_from_lean(text)
    if not picks:
        return text
    resolved = handicap_line_from_lean(text)
    if resolved is None:
        resolved = line_f
    return format_handicap_lean_text(_lean_base(picks), resolved)


def adapt_handicap_lean_for_ruleset(
    lean: str | None,
    line_f: float | None = None,
    *,
    ruleset: str = HANDICAP_RULESET_ASIAN,
) -> str | None:
    """Remap frozen lean copy for the reader's ruleset without mutating storage.

    Asian drops 让平 from dual picks; Jingcai shows the whole-goal line it
    actually settles on, so 让胜(-0.5) reads 让胜(-1).
    """
    shown = display_handicap_lean(lean, line_f)
    if not shown:
        return shown
    picks = handicap_picks_from_lean(shown)
    if not picks:
        return shown
    resolved = handicap_line_from_lean(shown)
    if resolved is None:
        resolved = line_f
    if parse_handicap_ruleset(ruleset) == HANDICAP_RULESET_JC:
        if resolved is None:
            return shown
        return format_handicap_lean_text(_lean_base(picks), jc_handicap_line(resolved))
    if "让平" not in picks:
        return shown
    remaining = {pick for pick in picks if pick != "让平"}
    if not remaining:
        return shown
    return format_handicap_lean_text(_lean_base(remaining), resolved)


def build_ah_features(
    package: dict[str, Any] | None,
    *,
    league_id: int | None = None,
) -> tuple[dict[str, float], float | None, float | None, float | None]:
    """Build AH features using market inputs only, plus raw main-line values."""
    package = package or {}
    base = extract_features(package)
    odds = package.get("odds") if isinstance(package.get("odds"), dict) else {}
    opening = (
        package.get("odds_opening")
        if isinstance(package.get("odds_opening"), dict)
        else {}
    )
    line_f, home_f, away_f = extract_main_ah_line(odds)

    ph, pd, pa = _market_1x2_probs(base)

    top5, asia = _league_tier_flags(league_id)
    has_ah = 1.0 if line_f is not None and home_f and away_f else 0.0
    board = _empty_board_context()

    if line_f is None or home_f is None or away_f is None:
        extra = {
            "ah_line_norm": 0.0,
            "ah_home_odd_inv": 0.0,
            "ah_away_odd_inv": 0.0,
            "ah_water_diff": 0.0,
            "ah_implied_cover": 0.5,
            "ah_line_abs_norm": 0.0,
            "ah_tier_shallow": 0.0,
            "ah_tier_medium": 0.0,
            "ah_tier_deep": 0.0,
            "ah_is_giving": 0.0,
            "mx_home_prob": ph,
            "mx_draw_prob": pd,
            "mx_away_prob": pa,
            "mx_vs_ah_gap": 0.0,
            "league_tier_top5": top5,
            "league_tier_asia": asia,
            "has_ah_market": 0.0,
            **board,
        }
        return {**base, **extra}, None, None, None

    implied = _implied_cover_prob(home_f, away_f)
    shallow, medium, deep = _line_tier_flags(line_f)
    line_norm = max(-1.0, min(1.0, line_f / 2.5))
    board = _board_context_features(
        odds,
        opening,
        main_line=line_f,
        main_home=home_f,
        main_away=away_f,
    )
    extra = {
        "ah_line_norm": line_norm,
        "ah_home_odd_inv": 1.0 / home_f,
        "ah_away_odd_inv": 1.0 / away_f,
        "ah_water_diff": home_f - away_f,
        "ah_implied_cover": implied,
        "ah_line_abs_norm": min(1.0, abs(line_f) / 2.5),
        "ah_tier_shallow": shallow,
        "ah_tier_medium": medium,
        "ah_tier_deep": deep,
        "ah_is_giving": 1.0 if line_f < -0.05 else 0.0,
        "mx_home_prob": ph,
        "mx_draw_prob": pd,
        "mx_away_prob": pa,
        "mx_vs_ah_gap": ph - implied,
        "league_tier_top5": top5,
        "league_tier_asia": asia,
        "has_ah_market": has_ah,
        **board,
    }
    return {**base, **extra}, line_f, home_f, away_f


def pick_to_lean(pick: str) -> str:
    """Canonical pick token. Display drops 「球」 to keep list tags on one line."""
    if pick == "cover/no_cover":
        return "让胜/负"
    if pick == "cover/push":
        return "让胜/平"
    if pick == "no_cover/push":
        return "让负/平"
    if pick.startswith("让球"):
        # Frozen snapshots written before the shorter labels.
        return f"让{pick.removeprefix('让球')}"
    if pick.startswith("让"):
        return pick
    if pick == "cover":
        return "让胜"
    if pick == "push":
        return "让平"
    return "让负"


def parse_score_hint(score_hint: str | None) -> list[tuple[int, int]]:
    """Extract scores from ``2-1`` or ``0-1 / 1-1`` style hints."""
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
