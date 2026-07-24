"""Backend prediction leans + opinion-factor fusion (not free-text NLP)."""

from __future__ import annotations

import re
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
    return value.replace("倾向大球", "大").replace("倾向小球", "小").replace(
        "大小球：", "大小："
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
    features: dict[str, float] | None = None,
) -> str:
    """Single pick or 双选 (主胜/平、客胜/平). Flat prior → 待分析.

    仅在「胜+平」或「负+平」接近时双选。主客接近时不推「防平」
   （几乎包圆且易与参考比分打架），改为单选概率更高的一侧。

    When streak/mean-reversion features are extreme, widen the double-chance
    edge so we do not over-commit to a side that is statistically due to fade
    or bounce. When model top disagrees with odds-implied top and the edge is
    thin, also soften toward 双选 (future matches only; frozen snaps untouched).
    """
    normalized = normalize_probabilities(probs)
    if is_flat_prior(normalized):
        return "待分析"
    edge = _DOUBLE_CHANCE_EDGE
    if features:
        # Long winning streak on the favorite → prefer softer (双选) picks.
        top_key = max(("home", "draw", "away"), key=lambda k: normalized[k])
        if top_key == "home" and features.get("home_win_streak", 0) >= 4:
            edge = 0.12
        elif top_key == "away" and features.get("away_win_streak", 0) >= 4:
            edge = 0.12
        # Long winless underdog as top pick → also soften (bounce is noisy).
        if top_key == "home" and features.get("home_winless_streak", 0) >= 5:
            edge = max(edge, 0.11)
        elif top_key == "away" and features.get("away_winless_streak", 0) >= 5:
            edge = max(edge, 0.11)
        # Model vs market disagreement → widen edge slightly.
        if float(features.get("has_odds", 0) or 0) >= 1.0:
            odds_top = max(
                (
                    ("home", float(features.get("odds_home", 0) or 0)),
                    ("draw", float(features.get("odds_draw", 0) or 0)),
                    ("away", float(features.get("odds_away", 0) or 0)),
                ),
                key=lambda x: x[1],
            )[0]
            if odds_top != top_key:
                edge = max(edge, 0.11)
    ranked = sorted(
        (("home", normalized["home"]), ("draw", normalized["draw"]), ("away", normalized["away"])),
        key=lambda x: x[1],
        reverse=True,
    )
    top_key, top_p = ranked[0]
    second_key, second_p = ranked[1]
    if top_p - second_p < edge:
        pair = frozenset({top_key, second_key})
        if pair == frozenset({"home", "away"}):
            return _LABEL[top_key]
        return _DOUBLE[pair]
    return _LABEL[top_key]


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

    # Soft model + clear market price gap → follow market.
    if market_side and market_side != model_side and over is not None and under is not None:
        gap = abs(over - under) / max(min(over, under), 1e-6)
        soft = probs["draw"] >= 0.28 or abs(probs["home"] - probs["away"]) < 0.12
        if soft and gap >= 0.08:
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
) -> bool:
    """Independent BTTS lean — not derived from reference scorelines.

    Score is the hardest market; BTTS is a binary product lean driven by O/U
    shape, 1X2 balance, and recent goal-diff features when present.
    """
    score = 0.0
    if ou_side == "over":
        score += 1.15 if line >= 2.5 else 0.55
    else:
        score -= 1.15 if line <= 2.5 else 0.45

    spread = abs(probs["home"] - probs["away"])
    top = max(probs["home"], probs["away"])
    if probs["draw"] >= 0.30:
        score += 0.1 if ou_side == "over" else -0.5
    if top >= 0.55 and probs["draw"] < 0.24:
        # Blowout favorites more often keep a clean sheet.
        score -= 0.75
    if spread < 0.10 and top < 0.46:
        score += 0.5

    if features:
        hgd = float(features.get("home_gd_avg_5", 0.0) or 0.0)
        agd = float(features.get("away_gd_avg_5", 0.0) or 0.0)
        if hgd > 0.35 and agd > 0.25:
            score += 0.55
        if hgd < 0.05 and agd < 0.05:
            score -= 0.55

    return score >= 0.0


def _reconcile_btts_with_scores(
    lines: list[tuple[int, int]],
    model_btts: bool,
) -> bool:
    """Align BTTS lean with reference scorelines when they are unambiguous."""
    if not lines:
        return model_btts
    any_both = any(h > 0 and a > 0 for h, a in lines)
    all_one_sided = all(h == 0 or a == 0 for h, a in lines)
    if any_both:
        return True
    if all_one_sided:
        return False
    return model_btts


def _align_score_with_btts(
    lines: list[tuple[int, int]],
    *,
    btts_yes: bool,
    probs: dict[str, float],
    total: int,
) -> list[tuple[int, int]]:
    """Keep score as display reference; nudge so it does not fight BTTS lean."""
    if not lines:
        return lines
    out: list[tuple[int, int]] = []
    for h, a in lines:
        if btts_yes and (h == 0 or a == 0):
            if h == 0 and a == 0:
                out.append((1, 1))
            elif h == 0:
                out.append((1, max(1, a)))
            else:
                out.append((max(1, h), 1))
        elif not btts_yes and h > 0 and a > 0:
            key = _primary_1x2_key(probs)
            if key == "draw":
                out.append((0, 0))
            elif key == "home":
                t = max(1, h + a)
                out.append((t, 0) if t <= 3 else (t - 1, 0))
            else:
                t = max(1, h + a)
                out.append((0, t) if t <= 3 else (0, t - 1))
        else:
            out.append((h, a))
    seen: set[tuple[int, int]] = set()
    unique: list[tuple[int, int]] = []
    for pair in out:
        if pair not in seen:
            seen.add(pair)
            unique.append(pair)
    return unique


def _target_total(line: float, side: str) -> int:
    if side == "under":
        return max(0, int(line // 1))
    return max(1, int(-(-line // 1)))  # ceil


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
    if close_sides:
        return (0, 1) if total <= 2 else (1, 2)
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
) -> tuple[str, str]:
    """Recompute handicap lean + optional market note for detail views."""
    ah = (odds or {}).get("asian_handicap") if isinstance(odds, dict) else None
    if isinstance(odds, dict) and odds.get("available") and isinstance(ah, dict):
        return _handicap_bundle(
            odds,
            recommendation,
            league_id=league_id,
            features=features,
            score_hint=score_hint,
        )
    text = (stored or "").strip()
    return (text if text else "缺少盘口数据分析"), ""


def _draw_scoreline(preferred_total: int) -> tuple[int, int]:
    """Even scoreline closest to preferred total (0-0 / 1-1 / 2-2…)."""
    total = max(0, int(preferred_total))
    if total % 2 == 1:
        total -= 1
    half = total // 2
    return half, half


def _score_hints_for_recommendation(
    recommendation: str,
    probs: dict[str, float],
    total: int,
    *,
    btts_yes: bool,
    ou_side: str,
) -> tuple[str, list[tuple[int, int]]]:
    """Build reference score(s) consistent with 胜平负推荐.

    双选时给多个比分（用 / 连接），避免「主胜/平却只给 2-0」这类打架。
    平局：小球/双方否 → 0-0；大球/双方是 → 1-1、2-2 等对称比分。
    """
    rec = (recommendation or "").strip()
    outcomes = recommendation_outcomes(rec) or {_primary_1x2_key(probs)}
    lines: list[tuple[int, int]] = []

    def _draw_ref() -> tuple[int, int]:
        draw_total = total if total > 0 else 0
        if ou_side == "over":
            if draw_total < 2:
                draw_total = 2
            return _draw_scoreline(draw_total)
        if not btts_yes:
            return 0, 0
        return _draw_scoreline(draw_total)

    if outcomes == {"draw"}:
        lines.append(_draw_ref())
    elif outcomes == {"home", "draw"}:
        lines.append((1, 0) if total <= 2 else (2, 1))
        if btts_yes:
            draw_total = 2 if total <= 2 else min(4, total if total % 2 == 0 else total - 1)
            lines.append(_draw_scoreline(draw_total))
        else:
            lines.append((0, 0))
    elif outcomes == {"away", "draw"}:
        lines.append((0, 1) if total <= 2 else (1, 2))
        if btts_yes:
            draw_total = 2 if total <= 2 else min(4, total if total % 2 == 0 else total - 1)
            lines.append(_draw_scoreline(draw_total))
        else:
            lines.append((0, 0))
    elif outcomes == {"home", "away"}:
        ht = max(1, total if total > 0 else 1)
        lines.append((1, 0) if ht <= 2 else (2, 1))
        lines.append((0, 1) if ht <= 2 else (1, 2))
    elif outcomes == {"home"}:
        lines.append(_split_score(max(1, total), probs))
    elif outcomes == {"away"}:
        lines.append(_split_score(max(1, total), probs))
    else:
        lines.append(_split_score(max(0, total), probs))

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
    reconciled with the BTTS lean so「1-1」never pairs with「双方进球：否」.

    Flat prior with local odds → use odds-implied 1X2 (no API).
    Flat prior and no usable odds → 待分析.

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
        f"大（{line_label}）" if side == "over" else f"小（{line_label}）"
    )

    recommendation = get_recommendation(normalized, features=features)
    btts_yes = _btts_yes(
        normalized, ou_side=side, line=line, features=features
    )
    if (
        goal_prediction is not None
        and goal_prediction.deploy_btts
        and distribution is not None
    ):
        btts_yes = distribution["btts_prob"] >= 0.5
    if (
        goal_prediction is not None
        and goal_prediction.deploy_score
        and distribution is not None
    ):
        score_lines = [(h, a) for h, a, _ in distribution["scores"]]
    else:
        _, score_lines = _score_hints_for_recommendation(
            recommendation,
            normalized,
            total,
            btts_yes=btts_yes,
            ou_side=side,
        )
        score_lines = _align_score_with_btts(
            score_lines, btts_yes=btts_yes, probs=normalized, total=total
        )
        btts_yes = _reconcile_btts_with_scores(score_lines, btts_yes)
    score_hint = (
        f"比分:{' / '.join(f'{h}-{a}' for h, a in score_lines)}"
        if score_lines
        else "比分:待分析"
    )
    both_score_lean = "双进:是" if btts_yes else "双进:否"
    if goal_prediction is not None:
        if not goal_prediction.deploy_score:
            score_hint = "比分:待分析"
        if not goal_prediction.deploy_btts:
            both_score_lean = "双进:待分析"
        if not goal_prediction.deploy_ou:
            market_over, market_under = _implied_two_way(over, under)
            if max(market_over, market_under) >= 0.56:
                market_side = "over" if market_over > market_under else "under"
                goal_lean = (
                    f"大（{line_label}）"
                    if market_side == "over"
                    else f"小（{line_label}）"
                )
            else:
                goal_lean = "大小：待分析"
    handicap_lean, handicap_market_note = _handicap_bundle(
        odds if isinstance(odds, dict) else None,
        recommendation=recommendation,
        league_id=league_id,
        features=features,
        score_hint=score_hint,
    )
    return {
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
    normalized = normalize_probabilities(probs)
    leans = derive_prediction_leans(
        normalized, odds, features=features, league_id=league_id
    )
    return {
        "home_win_prob": round(normalized["home"], 4),
        "draw_prob": round(normalized["draw"], 4),
        "away_win_prob": round(normalized["away"], 4),
        "recommendation": get_recommendation(normalized, features=features),
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
    """Parse current ``大（2.5）`` and historical ``倾向大球（2.5）``."""
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
