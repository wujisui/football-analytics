"""Build one self-consistent bundle for each daily pick's own 1X2 direction.

日推按校准置信度单选，分析器按最可能结果推导，两者允许不同向。卡片上标 `[荐]`
的那一行必须整行同源：这里以日推方向为唯一基准，配一条真实盘口上的让球表达
和一份同方向的比分候选。无法自洽的场次直接淘汰，由后续候选补位。
"""

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
    parse_score_hint,
    settle_handicap_pick,
)
from app.services.prediction import recommendation_outcomes, score_hint_for_lean

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


def _reject(detail: str) -> ConsistencyDecision:
    return ConsistencyDecision(
        is_consistent=False,
        handicap_lean=None,
        score_hint=None,
        conflict_reason="无法自洽，跳过",
        conflict_detail=detail,
    )


def _handicap_side(outcome: str, line_f: float) -> tuple[str | None, str | None]:
    """The AH side that cannot lose when this single 1X2 outcome lands.

    平手盘同样是可下注的让球盘：主胜配让0胜、客胜配让0负，赛果打平按走水退本，
    不算输，所以这里照常给出方向。只有主客两侧会走到这里，平局在上游已被淘汰。
    """
    if outcome == "home":
        if line_f < -1.0 - _LINE_EPSILON:
            return None, "主胜不能保证穿过深于主让1球的盘口"
        return "让胜", None
    if line_f > 1.0 + _LINE_EPSILON:
        return None, "客胜不能保证穿过深于客让1球的盘口"
    return "让负", None


def validate_pick_consistency(
    *,
    daily_lean: str,
    probs: dict[str, float],
    goal_lean: str | None,
    both_score_lean: str | None,
    odds: dict[str, Any] | None,
) -> ConsistencyDecision:
    """Validate before Top-N; never reshape the real line."""
    outcomes = recommendation_outcomes(daily_lean)
    if not outcomes or len(outcomes) != 1:
        return _reject(f"日推方向{daily_lean!r}不是可结算的单选")
    outcome = next(iter(outcomes))
    if outcome == "draw":
        return _reject("平局命中率低，日推只取主客单选")

    score_hint = score_hint_for_lean(
        daily_lean,
        probs,
        goal_lean=goal_lean,
        both_score_lean=both_score_lean,
    )
    if not score_hint:
        return _reject("无法在大小球/双进结论下给出该方向的比分")

    line_f, _home_odd, _away_odd = extract_main_ah_line(odds)
    if line_f is None:
        return ConsistencyDecision(
            is_consistent=True,
            handicap_lean=None,
            score_hint=score_hint,
            conflict_reason="自洽",
            conflict_detail="没有可展示的让球行",
        )

    side, line_error = _handicap_side(outcome, line_f)
    if side is None:
        return _reject(line_error or "真实盘口无法表达该日推方向")

    scores = parse_score_hint(score_hint)
    if not all(
        settle_handicap_pick(home_goals, away_goals, line_f, side)
        in _NON_LOSING_AH_RESULTS
        for home_goals, away_goals in scores
    ):
        return _reject(f"比分候选在{side}上会输，方向表达不成立")

    return ConsistencyDecision(
        is_consistent=True,
        handicap_lean=format_handicap_lean_text(side, line_f),
        score_hint=score_hint,
        conflict_reason="自洽",
        conflict_detail=f"{daily_lean}、{side}与比分候选同向",
    )


def validate_consistency_batch(
    picks: list[Any],
    *,
    probs_by_fixture: dict[int, dict[str, float]],
    goal_lean_by_fixture: dict[int, str | None],
    both_score_lean_by_fixture: dict[int, str | None],
    odds_by_fixture: dict[int, dict[str, Any] | None],
) -> tuple[list[tuple[Any, ConsistencyDecision]], list[dict[str, Any]]]:
    """Gate the complete ranked pool so rejected fixtures can be backfilled."""
    accepted: list[tuple[Any, ConsistencyDecision]] = []
    rejected: list[dict[str, Any]] = []
    for pick in picks:
        fixture_id = int(pick.fixture_id)
        decision = validate_pick_consistency(
            daily_lean=str(pick.lean),
            probs=probs_by_fixture.get(fixture_id) or {},
            goal_lean=goal_lean_by_fixture.get(fixture_id),
            both_score_lean=both_score_lean_by_fixture.get(fixture_id),
            odds=odds_by_fixture.get(fixture_id),
        )
        if decision.is_consistent:
            accepted.append((pick, decision))
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
            "Daily pick rejected by consistency gate fixture=%s lean=%s reason=%s",
            fixture_id,
            pick.lean,
            decision.conflict_detail,
        )
    return accepted, rejected
