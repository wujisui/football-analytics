"""Build one self-consistent bundle for each daily pick's selected market.

日推核心玩法是独赢 / 亚洲让球，不足时按大小球、双方进球降级补位。卡片上标
`[荐]` 的那一行及其胜负方向、真实让球和比分必须同源；无法自洽的市场候选直接
淘汰，由同场下一层玩法或后续场次补位。

让球行只是伴随展示，不是这注本身：深于 1 球的盘口上任何胜负方向都担保不了某一
侧，此时隐藏让球行，不淘汰大小球 / 双进候选。
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
    handicap_pick_from_lean,
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


def _handicap_side(outcome: str, line_f: float) -> str | None:
    """The AH side that cannot lose when this single 1X2 outcome lands.

    平手盘同样是可下注的让球盘：主胜配让0胜、客胜配让0负，赛果打平按走水退本，
    不算输，所以这里照常给出方向。只有主客两侧会走到这里，平局在上游已被淘汰。
    深于 1 球时两侧都担保不了（主胜可能只赢一球、客胜也可能输一球），返回 None
    表示这张卡没有可展示的让球行。
    """
    if outcome == "home":
        return None if line_f < -1.0 - _LINE_EPSILON else "让胜"
    return None if line_f > 1.0 + _LINE_EPSILON else "让负"


def validate_pick_consistency(
    *,
    daily_lean: str,
    probs: dict[str, float],
    goal_lean: str | None,
    both_score_lean: str | None,
    odds: dict[str, Any] | None,
    market: str = "1x2",
    market_lean: str | None = None,
) -> ConsistencyDecision:
    """Validate before Top-N; never reshape the real line."""
    outcomes = recommendation_outcomes(daily_lean)
    if not outcomes or len(outcomes) != 1:
        return _reject(f"日推方向{daily_lean!r}不是可结算的单选")
    outcome = next(iter(outcomes))
    if outcome == "draw":
        return _reject("平局命中率低，日推只取主客单选")

    selected_goal_lean = market_lean if market == "ou" else goal_lean
    selected_both_score_lean = market_lean if market == "btts" else both_score_lean
    score_hint = score_hint_for_lean(
        daily_lean,
        probs,
        goal_lean=selected_goal_lean,
        both_score_lean=selected_both_score_lean,
        allow_missing_goal=market == "btts",
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

    if market == "ah":
        side = handicap_pick_from_lean(market_lean)
        if side not in {"让胜", "让负"}:
            return _reject("让球日推不是主客单选")
    else:
        side = _handicap_side(outcome, line_f)
        if side is None:
            # 大小球 / 双进这注本身成立，只是深盘上没有任何让球侧能被该胜负方向
            # 担保。隐藏让球行即可，不该连候选一起淘汰。
            return ConsistencyDecision(
                is_consistent=True,
                handicap_lean=None,
                score_hint=score_hint,
                conflict_reason="自洽",
                conflict_detail=(
                    f"{market_lean or daily_lean}与比分候选同向；"
                    "真实盘口深于该方向可担保的范围，不展示让球行"
                ),
            )

    scores = parse_score_hint(score_hint)
    if not all(
        settle_handicap_pick(home_goals, away_goals, line_f, side)
        in _NON_LOSING_AH_RESULTS
        for home_goals, away_goals in scores
    ):
        return _reject(f"比分候选在{side}上会输，方向表达不成立")

    return ConsistencyDecision(
        is_consistent=True,
        handicap_lean=(
            format_handicap_lean_text(side, line_f)
            if market != "ah"
            else str(market_lean)
        ),
        score_hint=score_hint,
        conflict_reason="自洽",
        conflict_detail=f"{market_lean or daily_lean}、{daily_lean}、{side}与比分候选同向",
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
            market=str(pick.market),
            market_lean=str(pick.market_lean or pick.lean),
        )
        if decision.is_consistent:
            accepted.append((pick, decision))
            continue
        rejected.append(
            {
                "fixture_id": fixture_id,
                "match_day": pick.match_day,
                "market": pick.market,
                "lean": pick.market_lean or pick.lean,
                "is_consistent": False,
                "conflict_reason": decision.conflict_reason,
                "conflict_detail": decision.conflict_detail,
            }
        )
        logger.warning(
            "Daily candidate rejected fixture=%s market=%s lean=%s reason=%s",
            fixture_id,
            pick.market,
            pick.market_lean or pick.lean,
            decision.conflict_detail,
        )
    return accepted, rejected
