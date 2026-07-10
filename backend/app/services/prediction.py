"""Backend prediction leans + opinion-factor fusion (not free-text NLP)."""

from __future__ import annotations

from typing import Any

DEFAULT_PROB = 1 / 3
# Only treat as "no real model output" when all three sit on the flat prior.
_FLAT_EPS = 0.02
# Below this gap between #1 and #2 → double-chance (双选) instead of single.
_DOUBLE_CHANCE_EDGE = 0.08

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

_LABEL = {"home": "主胜", "draw": "平局", "away": "客胜"}
_DOUBLE = {
    frozenset({"home", "draw"}): "主胜/平",
    frozenset({"away", "draw"}): "客胜/平",
    frozenset({"home", "away"}): "主胜/客胜",
}


def normalize_probabilities(probs: dict[str, float]) -> dict[str, float]:
    total = sum(max(float(v), 0.0) for v in probs.values())
    if total <= 0:
        return {"home": DEFAULT_PROB, "draw": DEFAULT_PROB, "away": DEFAULT_PROB}
    return {k: max(float(v), 0.0) / total for k, v in probs.items()}


def _is_flat_prior(probs: dict[str, float]) -> bool:
    """True only for placeholder 1/3·1/3·1/3 (no real analysis yet)."""
    return all(
        abs(float(probs.get(k, 0)) - DEFAULT_PROB) < _FLAT_EPS
        for k in ("home", "draw", "away")
    )


def get_recommendation(probs: dict[str, float]) -> str:
    """Single pick or 双选 (主胜/平 etc.). Flat prior → 待分析.

    No ML required: rank 1X2 probabilities; if top-2 are close, cover both.
    """
    normalized = normalize_probabilities(probs)
    if _is_flat_prior(normalized):
        return "待分析"
    ranked = sorted(
        (("home", normalized["home"]), ("draw", normalized["draw"]), ("away", normalized["away"])),
        key=lambda x: x[1],
        reverse=True,
    )
    top_key, top_p = ranked[0]
    second_key, second_p = ranked[1]
    if top_p - second_p < _DOUBLE_CHANCE_EDGE:
        return _DOUBLE[frozenset({top_key, second_key})]
    return _LABEL[top_key]


def _odd_float(value: Any) -> float | None:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


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


def _target_total(line: float, side: str) -> int:
    if side == "under":
        return max(0, int(line // 1))
    return max(1, int(-(-line // 1)))  # ceil


def _primary_1x2_key(probs: dict[str, float]) -> str:
    return max(("home", "draw", "away"), key=lambda k: probs[k])


def _split_score(total: int, probs: dict[str, float]) -> tuple[int, int]:
    """Build a concrete scoreline from total goals + primary 1X2 winner."""
    key = _primary_1x2_key(probs)
    h, d, a = probs["home"], probs["draw"], probs["away"]
    if total <= 0:
        return 0, 0
    if key == "draw":
        home = total // 2
        return home, total - home
    if key == "home":
        if h >= 0.55 and d < 0.24 and total <= 3:
            return total, 0
        away = (total - 1) // 2
        if away >= total - away:
            away = max(0, total - away - 1)
        if total >= 3 and away == 0:
            away = 1
        home = total - away
        if home <= away:
            return away + 1, max(0, total - away - 1)
        return home, away
    if a >= 0.55 and d < 0.24 and total <= 3:
        return 0, total
    home = (total - 1) // 2
    if home >= total - home:
        home = max(0, total - home - 1)
    if total >= 3 and home == 0:
        home = 1
    away = total - home
    if away <= home:
        return max(0, total - home - 1), home + 1
    return home, away


def _handicap_lean(odds: dict[str, Any] | None) -> str:
    """竞彩风格让球倾向 from Asian handicap market — rule-based, no ML."""
    ah = (odds or {}).get("asian_handicap") if isinstance(odds, dict) else None
    if not isinstance(ah, dict):
        return "让球：暂无盘口"
    line_raw = ah.get("line")
    if line_raw is None or line_raw == "":
        return "让球：暂无盘口"
    line = _format_line(line_raw)
    home_odd = _odd_float(ah.get("home"))
    away_odd = _odd_float(ah.get("away"))
    if home_odd is None or away_odd is None:
        return f"让球盘（{line}）"

    # Lower odd ≈ market favorite on that AH side (home = 让球主队方向).
    ratio = home_odd / away_odd
    if ratio <= 0.88:
        return f"让球胜（{line}）"
    if ratio >= 1.12:
        return f"让球负（{line}）"
    if home_odd <= away_odd:
        return f"让球胜平（{line}）"
    return f"让球负平（{line}）"


def derive_prediction_leans(
    probs: dict[str, float],
    odds: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Derive O/U, BTTS, score and handicap leans from 1X2 + markets.

    Always commits when real probabilities exist. Flat prior → 待分析.
    """
    normalized = normalize_probabilities(
        {
            "home": float(probs.get("home", DEFAULT_PROB)),
            "draw": float(probs.get("draw", DEFAULT_PROB)),
            "away": float(probs.get("away", DEFAULT_PROB)),
        }
    )
    if _is_flat_prior(normalized):
        return {
            "goal_lean": "大小球：待分析",
            "both_score_lean": "双方进球：待分析",
            "score_hint": "待分析",
            "handicap_lean": "让球：待分析",
        }

    ou = (odds or {}).get("goals_ou") if isinstance(odds, dict) else None
    ou = ou if isinstance(ou, dict) else {}
    line = _parse_ou_line(ou.get("line")) or 2.5
    over = _odd_float(ou.get("home"))
    under = _odd_float(ou.get("away"))
    side = _market_ou_side(over, under) or _side_from_probs(normalized)
    total = _target_total(line, side)
    line_label = _format_line(line)
    goal_lean = (
        f"倾向大球（{line_label}）" if side == "over" else f"倾向小球（{line_label}）"
    )

    hg, ag = _split_score(total, normalized)
    return {
        "goal_lean": goal_lean,
        "both_score_lean": "双方进球：是" if hg > 0 and ag > 0 else "双方进球：否",
        "score_hint": f"{hg}-{ag}",
        "handicap_lean": _handicap_lean(odds if isinstance(odds, dict) else None),
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
) -> dict[str, Any]:
    normalized = normalize_probabilities(probs)
    leans = derive_prediction_leans(normalized, odds)
    return {
        "home_win_prob": round(normalized["home"], 4),
        "draw_prob": round(normalized["draw"], 4),
        "away_win_prob": round(normalized["away"], 4),
        "recommendation": get_recommendation(normalized),
        **leans,
    }
