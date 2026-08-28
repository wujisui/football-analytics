"""Joint consistency gate for visible 1X2, AH and existing score candidates."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.services.ah_features import (
    ASIAN_HALF_WIN,
    ASIAN_PUSH,
    ASIAN_WIN,
    extract_main_ah_line,
    format_handicap_lean_text,
    handicap_pick_from_lean,
    parse_score_hint,
    settle_handicap_pick,
)
from app.services.prediction import recommendation_outcomes

logger = logging.getLogger(__name__)

_NON_LOSING_AH_RESULTS = {ASIAN_WIN, ASIAN_HALF_WIN, ASIAN_PUSH}
_LINE_EPSILON = 1e-9


@dataclass(frozen=True)
class ConsistencyDecision:
    is_consistent: bool
    handicap_lean: str | None
    score_hint: str | None
    conflict_reason: str
    conflict_detail: str
    corrected: bool = False


def _reject(
    detail: str,
    *,
    handicap_lean: str | None,
    score_hint: str | None,
) -> ConsistencyDecision:
    return ConsistencyDecision(
        is_consistent=False,
        handicap_lean=handicap_lean,
        score_hint=score_hint,
        conflict_reason="无法修正，跳过",
        conflict_detail=detail,
    )


def _preferred_pick(
    outcomes: set[str],
    line_f: float,
) -> tuple[str | None, str | None]:
    """Map a visible 1X2 result set to one actionable side on the real AH line."""
    if outcomes == {"home"}:
        if line_f < -1.0 - _LINE_EPSILON:
            return None, "主胜不能保证穿过深于主让1球的盘口"
        return "让胜", None
    if outcomes == {"away"}:
        if line_f > 1.0 + _LINE_EPSILON:
            return None, "客胜不能保证穿过深于客让1球的盘口"
        return "让负", None
    if outcomes == {"draw"}:
        if abs(line_f) > 0.25 + _LINE_EPSILON:
            return None, "平局只允许在±0.25以内映射让球方向"
        if line_f < -_LINE_EPSILON:
            return "让负", None
        if line_f > _LINE_EPSILON:
            return "让胜", None
        return None, "平手盘遇平局只有走水，没有可推荐方向"
    if outcomes == {"home", "draw"}:
        if line_f < -0.25 - _LINE_EPSILON or line_f > _LINE_EPSILON:
            return None, "胜/平只允许匹配主让0/0.25的让胜方向"
        return "让胜", None
    if outcomes == {"away", "draw"}:
        if line_f < -_LINE_EPSILON or line_f > 0.25 + _LINE_EPSILON:
            return None, "负/平只允许匹配客让0/0.25的让负方向"
        return "让负", None
    return None, "该1X2组合没有唯一且可审计的让球方向"


def _market_supports_pick(
    pick: str,
    home_odd: float | None,
    away_odd: float | None,
) -> bool:
    """A correction may not oppose the de-vigged AH market majority."""
    if home_odd is None or away_odd is None or home_odd <= 0 or away_odd <= 0:
        return False
    home_weight = 1.0 / float(home_odd)
    away_weight = 1.0 / float(away_odd)
    total = home_weight + away_weight
    if total <= 0:
        return False
    fair_home = home_weight / total
    return fair_home >= 0.5 if pick == "让胜" else (1.0 - fair_home) >= 0.5


def _score_outcome(home_goals: int, away_goals: int) -> str:
    if home_goals > away_goals:
        return "home"
    if home_goals < away_goals:
        return "away"
    return "draw"


def validate_pick_consistency(
    *,
    recommendation: str,
    daily_lean: str,
    handicap_lean: str | None,
    score_hint: str | None,
    odds: dict[str, Any] | None,
) -> ConsistencyDecision:
    """Validate before Top-N; never invent a line or a new score candidate."""
    visible_1x2 = (recommendation or "").strip() or (daily_lean or "").strip()
    outcomes = recommendation_outcomes(visible_1x2)
    if not outcomes:
        return _reject(
            "缺少可解析的1X2推荐",
            handicap_lean=handicap_lean,
            score_hint=score_hint,
        )
    line_f, home_odd, away_odd = extract_main_ah_line(odds)
    text = (handicap_lean or "").strip()
    if line_f is None or not text or "待分析" in text or "缺少" in text:
        return ConsistencyDecision(
            is_consistent=True,
            handicap_lean=handicap_lean,
            score_hint=score_hint,
            conflict_reason="原始匹配",
            conflict_detail="没有可比较的让球行",
        )

    preferred, line_error = _preferred_pick(outcomes, line_f)
    if preferred is None:
        return _reject(
            line_error or "真实盘口无法映射到1X2推荐",
            handicap_lean=handicap_lean,
            score_hint=score_hint,
        )

    original_pick = handicap_pick_from_lean(text)
    corrected = original_pick != preferred
    if corrected and not _market_supports_pick(preferred, home_odd, away_odd):
        return _reject(
            f"盘口水位不支持由{text}修正为{preferred}",
            handicap_lean=handicap_lean,
            score_hint=score_hint,
        )

    scores = parse_score_hint(score_hint)
    if not scores:
        return _reject(
            "缺少可复用的比分候选",
            handicap_lean=handicap_lean,
            score_hint=score_hint,
        )
    matching_scores = [
        (home_goals, away_goals)
        for home_goals, away_goals in scores
        if _score_outcome(home_goals, away_goals) in outcomes
        and settle_handicap_pick(home_goals, away_goals, line_f, preferred)
        in _NON_LOSING_AH_RESULTS
    ]
    if not matching_scores:
        return _reject(
            "已有比分候选无法同时匹配1X2与修正后的让球方向",
            handicap_lean=handicap_lean,
            score_hint=score_hint,
        )

    aligned_handicap = format_handicap_lean_text(preferred, line_f)
    aligned_score = "比分:" + "/".join(
        f"{home_goals}-{away_goals}" for home_goals, away_goals in matching_scores
    )
    corrected = corrected or aligned_score != (score_hint or "").strip()
    return ConsistencyDecision(
        is_consistent=True,
        handicap_lean=aligned_handicap,
        score_hint=aligned_score,
        conflict_reason="修正后匹配" if corrected else "原始匹配",
        conflict_detail=(
            f"{visible_1x2}、{aligned_handicap}与已有比分候选一致"
            if corrected
            else "原始1X2、让球与比分方向一致"
        ),
        corrected=corrected,
    )


def validate_consistency_batch(
    picks: list[Any],
    *,
    recommendation_by_fixture: dict[int, str | None],
    score_hint_by_fixture: dict[int, str | None],
    odds_by_fixture: dict[int, dict[str, Any] | None],
    stored_handicap_by_fixture: dict[int, str | None],
) -> tuple[list[tuple[Any, ConsistencyDecision]], list[dict[str, Any]]]:
    """Gate the complete ranked pool so rejected fixtures can be backfilled."""
    accepted: list[tuple[Any, ConsistencyDecision]] = []
    rejected: list[dict[str, Any]] = []
    for pick in picks:
        fixture_id = int(pick.fixture_id)
        decision = validate_pick_consistency(
            recommendation=recommendation_by_fixture.get(fixture_id) or "",
            daily_lean=str(pick.lean),
            handicap_lean=stored_handicap_by_fixture.get(fixture_id),
            score_hint=score_hint_by_fixture.get(fixture_id),
            odds=odds_by_fixture.get(fixture_id),
        )
        if decision.is_consistent:
            accepted.append((pick, decision))
            if decision.corrected:
                logger.info(
                    "Daily pick corrected by consistency gate fixture=%s 1x2=%s "
                    "handicap=%s score=%s detail=%s",
                    fixture_id,
                    recommendation_by_fixture.get(fixture_id) or pick.lean,
                    decision.handicap_lean,
                    decision.score_hint,
                    decision.conflict_detail,
                )
            continue
        rejected.append(
            {
                "fixture_id": fixture_id,
                "match_day": pick.match_day,
                "is_consistent": False,
                "conflict_reason": decision.conflict_reason,
                "conflict_detail": decision.conflict_detail,
            }
        )
        logger.warning(
            "Daily pick rejected by consistency gate fixture=%s 1x2=%s handicap=%s "
            "score=%s reason=%s",
            fixture_id,
            recommendation_by_fixture.get(fixture_id) or pick.lean,
            stored_handicap_by_fixture.get(fixture_id),
            score_hint_by_fixture.get(fixture_id),
            decision.conflict_detail,
        )
    return accepted, rejected
