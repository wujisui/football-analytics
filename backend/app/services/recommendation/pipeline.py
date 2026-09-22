"""Unified recommendation pipeline: 概率 → Platt → 每场参考 → 分层 Top 4.

Ranking is the calibrated hit probability of a single reference per match, taken
layer by layer (合格 AH → 大小球/双进 → 无盘独赢).  EV rides along for auditing only:
while probabilities come from the board being bet, ``EV = 1/超额 − 1`` is negative
by construction, so gating on it empties the pool instead of finding value.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.auto_pick_snapshot import AutoPickSnapshot
from app.models.favorite_fixture import (
    FAVORITE_SOURCE_AUTO,
    FAVORITE_SOURCE_MANUAL,
    FavoriteFixture,
)
from app.models.fixture import Fixture
from app.models.match_feature import MatchFeature
from app.models.pre_match_data import PreMatchData
from app.models.recommendation_candidate import RecommendationCandidateSnapshot
from app.services.auto_favorites import AUTO_PICK_LIMIT
from app.services.ah_features import format_handicap_lean_text
from app.services.ah_market_structure import companion_side_for_result
from app.services.match_day import fixture_match_day
from app.services.prematch_package import package_from_record, rehydrate_odds_markets
from app.services.prediction import (
    recommendation_outcomes,
    score_hint_for_consistent_bundle,
)
from app.services.probability_calibration import (
    load_calibration_artifact,
    train_from_frozen_history,
)
from app.services.recommendation.decision import (
    MARKET_1X2,
    MARKET_AH,
    MARKET_BTTS,
    MARKET_OU,
    MatchDecision,
    RecommendationCandidate,
    build_match_decision,
)
from app.services.results_capture import prematch_list_clause
from app.services.user_scope import ANON_OWNER_ID

logger = logging.getLogger(__name__)

# 合格亚洲让球 → 大小球/双进 → 无有效 AH 盘的独赢。大小球与双进在同一层按
# 调整后概率竞争；更低层只补更高层留下的席位。
MARKET_FALLBACK_TIER = {
    MARKET_AH: 0,
    MARKET_OU: 1,
    MARKET_BTTS: 1,
    MARKET_1X2: 2,
}
# 池子小于这个数时给不满 4 场属正常，不告警。
MIN_MATCHES_FOR_FULL_QUOTA = 6


@dataclass(frozen=True)
class MatchPipelineInput:
    fixture_id: int
    league_id: int
    kickoff: datetime
    match_day: str
    odds: dict[str, Any] | None
    package: dict[str, Any] | None = None
    recommendation: str | None = None
    handicap_lean: str | None = None
    score_hint: str | None = None
    goal_lean: str | None = None
    both_score_lean: str | None = None
    home_win_prob: float | None = None
    draw_prob: float | None = None
    away_win_prob: float | None = None


@dataclass(frozen=True)
class DailyRecommendationPick:
    fixture_id: int
    league_id: int
    kickoff: datetime
    match_day: str
    market: str
    lean: str
    recommended_choice: str
    confidence: float
    reason: str
    decimal_odd: float
    raw_confidence: float
    # 校准命中概率减方向惩罚；赔率不参与。
    score: float
    probability_source: str = "market"
    ev: float | None = None
    market_lean: str | None = None
    handicap_lean: str | None = None
    score_hint: str | None = None
    implied_probability: float | None = None
    model_source: str | None = None
    model_version: str | None = None
    calibrator_version: str | None = None
    market_direction: str | None = None
    direction_strength: str = "none"
    direction_alignment: str = "unknown"
    direction_penalty: float = 0.01
    adjusted_ev: float | None = None
    is_consistent: bool = True
    conflict_reason: str = "统一决策链路"
    conflict_detail: str = ""

    @property
    def tier(self) -> int:
        return MARKET_FALLBACK_TIER.get(self.market, len(MARKET_FALLBACK_TIER))


def _result_leans_for_candidate(
    match: MatchPipelineInput,
    candidate: RecommendationCandidate,
) -> list[str]:
    """胜负行的候选顺序；调用方按顺序试到能生成自洽比分为止。

    让球 / 独赢注只有一个答案：胜负方向恒等于所投那一侧（深盘受让侧在决策层就已
    不可入选）。大小球 / 双进注的胜负行只是**伴随展示**，挡住比分时应当让步，而不是
    把那一注毙掉——西雅图那场「双进:是」去水 60.9% 是全池最高的候选，却因为伴随行
    固定写「主胜」（主胜 + 双方进球 + 总进球小于 3 无解）整注被淘汰，席位让给了低
    9.5 个点的小(3)；而「双进:是 + 小(3)」本身不矛盾，1-1 同时满足两者。
    先取最可能结果，再按概率退让。和局只作伴随展示，仍不是可投注方向
    （真源 ``strategy.DAILY_PICK_OUTCOMES``）。
    """
    if candidate.market in {MARKET_AH, MARKET_1X2}:
        return ["主胜" if candidate.direction == "home" else "客胜"]
    home = float(match.home_win_prob or 0.0)
    away = float(match.away_win_prob or 0.0)
    probs = {
        "主胜": home,
        "客胜": away,
        "和局": (
            float(match.draw_prob)
            if match.draw_prob is not None
            else max(0.0, 1.0 - home - away)
        ),
    }
    stored = str(match.recommendation or "").strip()
    first = (
        "主胜"
        if stored in {"主胜", "胜"}
        else "客胜"
        if stored in {"客胜", "负"}
        else max(("主胜", "客胜"), key=lambda lean: probs[lean])
    )
    rest = sorted(
        (lean for lean in probs if lean != first),
        key=lambda lean: probs[lean],
        reverse=True,
    )
    return [first, *rest]


def _display_handicap_for_candidate(
    decision: MatchDecision,
    candidate: RecommendationCandidate,
    result_lean: str,
) -> str | None:
    """Return the handicap row that the companion result can honestly support.

    An AH pick shows its actual betting side. For every other market the row is
    only a companion, so it shows whichever side that result keeps from losing
    the board — including the receiving side on a draw — and is hidden only when
    no side qualifies. 真源 ``ah_market_structure.companion_side_for_result``。
    """
    if candidate.market == MARKET_AH:
        return candidate.lean
    outcomes = recommendation_outcomes(result_lean)
    if not outcomes or len(outcomes) != 1:
        return None
    ah_candidates = [
        item
        for item in decision.candidates
        if item.market == MARKET_AH and item.line is not None
    ]
    if not ah_candidates:
        return None
    line = float(ah_candidates[0].line)
    side = companion_side_for_result(line, next(iter(outcomes)))
    if side is None:
        return None
    return format_handicap_lean_text("让胜" if side == "home" else "让负", line)


def _declined_board_lean(
    decision: MatchDecision,
    candidate: RecommendationCandidate,
    handicap_lean: str | None,
) -> str | None:
    """让球层放弃掉的那一侧，仅当它的让球行被隐藏时才需要约束比分。

    降到大小球 / 双进的理由就是让球方穿盘概率不足，所以参考比分不能反过来写成
    轻松穿盘：哥伦甲那场主 -1.5 去水 48.7%，卡片却配了 3-0。浅盘的伴随让球行照常
    展示并只要求「不输」，不适用本约束。
    """
    if candidate.market == MARKET_AH or handicap_lean is not None:
        return None
    for item in decision.candidates:
        if item.market == MARKET_AH and item.line is not None and item.tellable:
            return item.lean
    return None


def _consistent_bundle(
    match: MatchPipelineInput,
    decision: MatchDecision,
    candidate: RecommendationCandidate,
) -> tuple[str, str | None, str] | None:
    """Build result / handicap / score from the same selected direction.

    所投那一注的方向固定不动；只有伴随的胜负行会让步（见
    ``_result_leans_for_candidate`` 的候选顺序），逐个试到能生成自洽比分为止。
    """
    goal_lean = candidate.lean if candidate.market == MARKET_OU else match.goal_lean
    both_score_lean = (
        candidate.lean if candidate.market == MARKET_BTTS else match.both_score_lean
    )
    home = float(match.home_win_prob or 0.0)
    away = float(match.away_win_prob or 0.0)
    draw = (
        float(match.draw_prob)
        if match.draw_prob is not None
        else max(0.0, 1.0 - home - away)
    )
    for result_lean in _result_leans_for_candidate(match, candidate):
        handicap_lean = _display_handicap_for_candidate(
            decision, candidate, result_lean
        )
        score_hint = score_hint_for_consistent_bundle(
            result_lean,
            handicap_lean,
            {"home": home, "draw": draw, "away": away},
            goal_lean=goal_lean,
            both_score_lean=both_score_lean,
            declined_handicap_lean=_declined_board_lean(
                decision, candidate, handicap_lean
            ),
        )
        if score_hint is not None:
            return result_lean, handicap_lean, score_hint
    return None


def _reason(candidate: RecommendationCandidate) -> str:
    relation = {
        "aligned_strong": "强一致",
        "aligned_weak": "一致",
        "unknown": "方向不明确",
        "reverse_weak": "逆向推荐（弱）",
        "reverse_strong": "逆向推荐（强）",
    }.get(candidate.direction_alignment, candidate.direction_alignment)
    source = "盘口去水" if candidate.probability_source == "market" else "模型"
    probability = (
        f"{candidate.calibrated_probability:.1%}"
        if candidate.calibrated_probability is not None
        else "不可用"
    )
    ev = (
        f"{candidate.expected_return:+.2%}"
        if candidate.expected_return is not None
        else "不可计算"
    )
    return (
        f"玩法：{candidate.market}；概率来源：{source}；命中概率：{probability}；"
        f"与盘口方向：{relation}；EV：{ev}（含庄家抽水，仅供审计）"
    )


def _skip_reason_text(candidate: RecommendationCandidate) -> str:
    reason = {
        "probability_unavailable": "这块盘没有可用报价，算不出命中概率",
        "odds_missing": "缺少可结算赔率，只能给方向",
        "deep_board_receiving_side": "深盘受让侧赢在「输一球以内」，卡片的胜负方向讲不圆，不推这一侧",
        "odds_and_model_unavailable": "盘口与模型数据均不足，暂时给不出方向",
    }.get(candidate.skip_reason or "")
    return reason or _reason(candidate)


def _to_pick(
    match: MatchPipelineInput,
    decision: MatchDecision,
) -> DailyRecommendationPick | None:
    """Turn a match reference into a daily candidate, or drop it.

    Drops are only for missing numbers, a sub-floor probability, or a direction
    that fights a strongly-moved board — never for negative EV.
    """
    has_ah = any(
        item.market == MARKET_AH
        and item.line is not None
        and item.decimal_odd is not None
        for item in decision.candidates
    )
    allowed_markets = (
        {MARKET_AH, MARKET_OU, MARKET_BTTS}
        if has_ah
        else {MARKET_1X2, MARKET_OU, MARKET_BTTS}
    )
    candidates = sorted(
        (
            item
            for item in decision.candidates
            if item.market in allowed_markets and item.eligible_for_daily_pick()
        ),
        key=lambda item: (
            MARKET_FALLBACK_TIER.get(item.market, 99),
            -float(item.ranking_score or 0.0),
        ),
    )
    selected: tuple[
        RecommendationCandidate, tuple[str, str | None, str]
    ] | None = None
    for candidate in candidates:
        bundle = _consistent_bundle(match, decision, candidate)
        if bundle is not None:
            selected = candidate, bundle
            break
    if selected is None:
        return None
    candidate, (result_lean, handicap_lean, score_hint) = selected
    score = candidate.ranking_score
    if score is None or candidate.raw_probability is None:
        return None
    return DailyRecommendationPick(
        fixture_id=match.fixture_id,
        league_id=match.league_id,
        kickoff=match.kickoff,
        match_day=match.match_day,
        market=candidate.market,
        lean=result_lean,
        recommended_choice=candidate.direction,
        ev=candidate.expected_return,
        confidence=candidate.calibrated_probability,
        reason=_reason(candidate),
        decimal_odd=candidate.decimal_odd,
        raw_confidence=candidate.raw_probability,
        score=score,
        probability_source=candidate.probability_source,
        market_lean=candidate.lean,
        handicap_lean=handicap_lean,
        score_hint=score_hint,
        implied_probability=candidate.implied_probability,
        model_source=candidate.model_source,
        model_version=candidate.model_version,
        calibrator_version=candidate.calibrator_version,
        market_direction=candidate.market_direction,
        direction_strength=candidate.direction_strength,
        direction_alignment=candidate.direction_alignment,
        direction_penalty=candidate.direction_penalty,
        adjusted_ev=candidate.adjusted_ev,
        conflict_detail=(
            "玩法降级：调整后达标的 AH 优先；否则大小球与双进按概率竞争；"
            "仅无 AH 盘时以独赢兜底"
        ),
    )


def select_daily_picks_by_match_day(
    picks: list[DailyRecommendationPick],
    *,
    limit_per_day: int = AUTO_PICK_LIMIT,
    skip_fixture_ids: set[int] | None = None,
) -> list[DailyRecommendationPick]:
    """Take each venue-local day's picks, layer by layer.

    Sorting by tier first keeps qualifying AH ahead of fallbacks. O/U and BTTS
    share one tier and therefore compete on adjusted probability; board-free
    1X2 only fills the final layer.
    """
    skip = skip_fixture_ids or set()
    by_day: dict[str, list[DailyRecommendationPick]] = {}
    for pick in picks:
        if pick.fixture_id not in skip:
            by_day.setdefault(pick.match_day, []).append(pick)
    selected: list[DailyRecommendationPick] = []
    for match_day in sorted(by_day):
        ranked = sorted(
            by_day[match_day],
            key=lambda pick: (
                pick.tier,
                -float(pick.score),
                pick.kickoff,
                pick.fixture_id,
            ),
        )
        selected.extend(ranked[: max(0, limit_per_day)])
    return selected


def _candidate_payload(candidate: RecommendationCandidate, reference: bool) -> dict[str, Any]:
    return {
        "fixture_id": candidate.fixture_id,
        "match_day": candidate.match_day,
        "market": candidate.market,
        "direction": candidate.direction,
        "lean": candidate.lean,
        "line": candidate.line,
        "model_source": candidate.model_source,
        "model_version": candidate.model_version,
        "implied_probability": candidate.implied_probability,
        "model_probability": candidate.model_probability,
        "probability_source": candidate.probability_source,
        "raw_probability": candidate.raw_probability,
        "calibrator_version": candidate.calibrator_version,
        "calibrated_probability": candidate.calibrated_probability,
        "decimal_odd": candidate.decimal_odd,
        "expected_return": candidate.expected_return,
        "market_direction": candidate.market_direction,
        "direction_strength": candidate.direction_strength,
        "direction_alignment": candidate.direction_alignment,
        "direction_penalty": candidate.direction_penalty,
        "adjusted_ev": candidate.adjusted_ev,
        "skip_reason": candidate.skip_reason,
        "chosen_as_reference": reference,
    }


def run_pipeline(
    matches: list[MatchPipelineInput],
    *,
    market_artifact: dict[str, Any] | None = None,
    limit_per_day: int = AUTO_PICK_LIMIT,
    skip_fixture_ids: set[int] | None = None,
) -> dict[str, Any]:
    """Build every reference, then fill each day's four seats layer by layer."""
    calibration = (
        market_artifact
        if market_artifact is not None
        else load_calibration_artifact()
    )
    decisions: list[MatchDecision] = []
    match_by_id = {match.fixture_id: match for match in matches}
    for match in matches:
        decisions.append(
            build_match_decision(
                fixture_id=match.fixture_id,
                league_id=match.league_id,
                match_day=match.match_day,
                odds=match.odds,
                package=match.package,
                calibration_artifact=calibration,
            )
        )

    eligible = [
        pick
        for decision in decisions
        if (pick := _to_pick(match_by_id[decision.fixture_id], decision)) is not None
    ]
    selected = select_daily_picks_by_match_day(
        eligible,
        limit_per_day=limit_per_day,
        skip_fixture_ids=skip_fixture_ids,
    )
    selected_ids = {pick.fixture_id for pick in selected}
    matches_by_day: dict[str, int] = {}
    eligible_by_day: dict[str, int] = {}
    selected_by_day: dict[str, int] = {}
    # 只有已开出盘口的场次才算进池子：未来日期通常整天没有报价，按「选不满」
    # 报警等于每轮刷一屏噪声。
    for decision in decisions:
        if any(
            candidate.decimal_odd is not None for candidate in decision.candidates
        ):
            matches_by_day[decision.match_day] = (
                matches_by_day.get(decision.match_day, 0) + 1
            )
    for pick in eligible:
        eligible_by_day[pick.match_day] = eligible_by_day.get(pick.match_day, 0) + 1
    for pick in selected:
        selected_by_day[pick.match_day] = selected_by_day.get(pick.match_day, 0) + 1
    alerts: list[dict[str, Any]] = []
    for match_day, pool in matches_by_day.items():
        selected_count = selected_by_day.get(match_day, 0)
        # A thin day short of the quota is normal, not a defect worth alerting.
        if selected_count < limit_per_day and pool >= MIN_MATCHES_FOR_FULL_QUOTA:
            alerts.append(
                {
                    "code": "daily_pick_shortfall",
                    "match_day": match_day,
                    "selected": selected_count,
                    "expected": limit_per_day,
                    "matches": pool,
                    "eligible": eligible_by_day.get(match_day, 0),
                }
            )
            logger.warning(
                "Daily Top-4 incomplete match_day=%s selected=%s expected=%s "
                "matches=%s eligible=%s",
                match_day,
                selected_count,
                limit_per_day,
                pool,
                eligible_by_day.get(match_day, 0),
            )

    return {
        "total_matches": len(matches),
        "matches_by_day": matches_by_day,
        "processed_count": len(decisions),
        "candidate_count": len(eligible),
        "selected_count": len(selected),
        "by_day": selected_by_day,
        "eligible_by_day": eligible_by_day,
        "consistency_rejected_count": 0,
        "direction_rejected_count": 0,
        "feedback": {"enabled": False, "replaced_by": "candidate_calibration"},
        "selected": [
            {
                "fixture_id": pick.fixture_id,
                "match_day": pick.match_day,
                "market": pick.market,
                "lean": pick.market_lean or pick.lean,
                "result_lean": pick.lean,
                "handicap_lean": pick.handicap_lean,
                "recommended_choice": pick.recommended_choice,
                "ev": round(pick.ev, 4) if pick.ev is not None else None,
                "adjusted_ev": (
                    round(pick.adjusted_ev, 4) if pick.adjusted_ev is not None else None
                ),
                "confidence": round(pick.confidence, 4),
                "score": round(pick.score, 4),
                "probability_source": pick.probability_source,
                "raw_probability": round(pick.raw_confidence, 4),
                "implied_probability": (
                    round(pick.implied_probability, 4)
                    if pick.implied_probability is not None
                    else None
                ),
                "reason": pick.reason,
                "market_direction": pick.market_direction,
                "direction_strength": pick.direction_strength,
                "direction_alignment": pick.direction_alignment,
                "direction_penalty": pick.direction_penalty,
                "decimal_odd": round(pick.decimal_odd, 3),
                "score_hint": pick.score_hint,
            }
            for pick in selected
        ],
        "references": [
            _candidate_payload(decision.reference, True)
            for decision in decisions
        ],
        "candidates": [
            _candidate_payload(
                candidate,
                candidate.market == decision.reference.market
                and candidate.direction == decision.reference.direction,
            )
            for decision in decisions
            for candidate in decision.candidates
        ],
        "rejected": [],
        "picks": selected,
        "decisions": decisions,
        "selected_ids": selected_ids,
        "alerts": alerts,
    }


def match_input_from_fixture_row(
    fixture: Fixture,
    stored: PreMatchData | None,
    feature: MatchFeature | None = None,
) -> MatchPipelineInput:
    del feature
    package = (
        package_from_record(stored, match_start_time=fixture.date)
        if stored is not None
        else {}
    )
    odds_raw = package.get("odds") if isinstance(package, dict) else None
    odds = rehydrate_odds_markets(odds_raw) if isinstance(odds_raw, dict) else None
    return MatchPipelineInput(
        fixture_id=int(fixture.id),
        league_id=int(fixture.league_id),
        kickoff=fixture.date,
        match_day=fixture_match_day(fixture),
        odds=odds if isinstance(odds, dict) else None,
        package=package if isinstance(package, dict) else None,
        recommendation=stored.recommendation if stored is not None else None,
        handicap_lean=stored.handicap_lean if stored is not None else None,
        score_hint=stored.score_hint if stored is not None else None,
        goal_lean=stored.goal_lean if stored is not None else None,
        both_score_lean=stored.both_score_lean if stored is not None else None,
        home_win_prob=stored.home_win_prob if stored is not None else None,
        draw_prob=stored.draw_prob if stored is not None else None,
        away_win_prob=stored.away_win_prob if stored is not None else None,
    )


async def collect_prematch_pipeline_inputs(
    db: AsyncSession,
    *,
    now: datetime | None = None,
) -> list[MatchPipelineInput]:
    current = now or datetime.now(timezone.utc).replace(tzinfo=None)
    rows = (
        await db.execute(
            select(Fixture, PreMatchData, MatchFeature)
            .outerjoin(PreMatchData, PreMatchData.fixture_id == Fixture.id)
            .outerjoin(MatchFeature, MatchFeature.fixture_id == Fixture.id)
            .where(prematch_list_clause(current))
            .order_by(Fixture.date, Fixture.id)
        )
    ).all()
    by_fixture: dict[int, tuple[Fixture, PreMatchData | None, MatchFeature | None]] = {}
    for fixture, stored, feature in rows:
        previous = by_fixture.get(int(fixture.id))
        if previous is None or (feature is not None and previous[2] is None):
            by_fixture[int(fixture.id)] = (fixture, stored, feature)
    return [
        match_input_from_fixture_row(fixture, stored, feature)
        for fixture, stored, feature in by_fixture.values()
    ]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _persist_candidates_and_references(
    db: AsyncSession,
    *,
    matches: list[MatchPipelineInput],
    decisions: list[MatchDecision],
    selected: list[DailyRecommendationPick],
    captured_at: datetime,
) -> None:
    prematch_ids = {match.fixture_id for match in matches}
    selected_keys = {
        (pick.fixture_id, pick.market, pick.recommended_choice)
        for pick in selected
    }
    if prematch_ids:
        await db.execute(
            delete(RecommendationCandidateSnapshot).where(
                RecommendationCandidateSnapshot.fixture_id.in_(prematch_ids)
            )
        )
    stored_rows = {
        int(row.fixture_id): row
        for row in (
            await db.execute(
                select(PreMatchData).where(PreMatchData.fixture_id.in_(prematch_ids))
            )
        ).scalars()
    }
    for decision in decisions:
        reference = decision.reference
        stored = stored_rows.get(decision.fixture_id)
        if stored is None:
            stored = PreMatchData(fixture_id=decision.fixture_id)
            db.add(stored)
            stored_rows[decision.fixture_id] = stored
        stored.reference_market = reference.market
        stored.reference_lean = reference.lean
        stored.reference_ev = reference.expected_return
        stored.reference_source = reference.probability_source
        stored.reference_probability = reference.calibrated_probability
        stored.reference_alignment = reference.direction_alignment
        stored.reference_reason = _skip_reason_text(reference)
        for candidate in decision.candidates:
            is_reference = (
                candidate.market == reference.market
                and candidate.direction == reference.direction
            )
            db.add(
                RecommendationCandidateSnapshot(
                    fixture_id=candidate.fixture_id,
                    match_day=candidate.match_day,
                    market=candidate.market,
                    direction=candidate.direction,
                    lean=candidate.lean,
                    line=candidate.line,
                    model_source=candidate.model_source,
                    model_version=candidate.model_version,
                    implied_probability=candidate.implied_probability,
                    model_probability=candidate.model_probability,
                    probability_source=candidate.probability_source,
                    raw_probability=candidate.raw_probability,
                    calibrator_version=candidate.calibrator_version,
                    calibrated_probability=candidate.calibrated_probability,
                    decimal_odd=candidate.decimal_odd,
                    settlement_distribution_json=candidate.settlement_json(),
                    expected_return=candidate.expected_return,
                    market_direction=candidate.market_direction,
                    direction_strength=candidate.direction_strength,
                    direction_alignment=candidate.direction_alignment,
                    direction_penalty=candidate.direction_penalty,
                    adjusted_ev=candidate.adjusted_ev,
                    chosen_as_reference=is_reference,
                    chosen_as_daily_pick=(
                        (
                            candidate.fixture_id,
                            candidate.market,
                            candidate.direction,
                        )
                        in selected_keys
                    ),
                    skip_reason=candidate.skip_reason,
                    captured_at=captured_at,
                )
            )


async def sync_daily_recommendations(
    db: AsyncSession,
    *,
    user_id: str | None = None,
    limit: int = AUTO_PICK_LIMIT,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Refresh all-match references and the layered daily Top 4."""
    del user_id
    owner = ANON_OWNER_ID
    settings = get_settings()
    current = now or _utc_now()
    calibration = await train_from_frozen_history(db, now=current)
    matches = await collect_prematch_pipeline_inputs(db, now=current)
    manual_ids = {
        int(row[0])
        for row in (
            await db.execute(
                select(FavoriteFixture.fixture_id).where(
                    FavoriteFixture.user_id == owner,
                    FavoriteFixture.source == FAVORITE_SOURCE_MANUAL,
                )
            )
        ).all()
    }
    pipeline_result = run_pipeline(
        matches,
        market_artifact=calibration,
        limit_per_day=limit,
        skip_fixture_ids=manual_ids,
    )
    selected: list[DailyRecommendationPick] = pipeline_result["picks"]
    selected_ids = {pick.fixture_id for pick in selected}
    prematch_ids = {match.fixture_id for match in matches}
    saved_at = _utc_now()

    await _persist_candidates_and_references(
        db,
        matches=matches,
        decisions=pipeline_result["decisions"],
        selected=selected,
        captured_at=saved_at,
    )
    await db.execute(
        delete(FavoriteFixture).where(
            FavoriteFixture.user_id == owner,
            FavoriteFixture.source == FAVORITE_SOURCE_AUTO,
        )
    )
    for pick in selected:
        db.add(
            FavoriteFixture(
                fixture_id=pick.fixture_id,
                user_id=owner,
                source=FAVORITE_SOURCE_AUTO,
                auto_market=pick.market,
                auto_market_lean=pick.market_lean,
                auto_lean=pick.lean,
                auto_handicap_lean=pick.handicap_lean,
                auto_score_hint=pick.score_hint,
                saved_at=saved_at,
            )
        )

    if prematch_ids - selected_ids:
        await db.execute(
            delete(AutoPickSnapshot).where(
                AutoPickSnapshot.fixture_id.in_(prematch_ids - selected_ids)
            )
        )
    if selected_ids:
        await db.execute(
            delete(AutoPickSnapshot).where(
                AutoPickSnapshot.fixture_id.in_(selected_ids)
            )
        )
    for pick in selected:
        db.add(
            AutoPickSnapshot(
                fixture_id=pick.fixture_id,
                match_day=pick.match_day,
                market=pick.market,
                lean=pick.market_lean or pick.lean,
                handicap_lean=pick.handicap_lean,
                score_hint=pick.score_hint,
                raw_confidence=pick.raw_confidence,
                confidence=pick.confidence,
                decimal_odd=pick.decimal_odd,
                expected_return=pick.ev,
                adjusted_ev=pick.adjusted_ev,
                implied_probability=pick.implied_probability,
                probability_source=pick.probability_source,
                model_source=pick.model_source,
                model_version=pick.model_version,
                calibrator_version=pick.calibrator_version,
                direction_alignment=pick.direction_alignment,
                score=pick.score,
                picked_at=saved_at,
            )
        )
    await db.commit()

    try:
        local_day = datetime.now(ZoneInfo(settings.SCHEDULER_TIMEZONE)).date().isoformat()
    except Exception:
        local_day = saved_at.date().isoformat()
    result = {
        "day": local_day,
        "total_matches": pipeline_result["total_matches"],
        "candidates": pipeline_result["candidate_count"],
        "selected_count": pipeline_result["selected_count"],
        "by_day": pipeline_result["by_day"],
        "eligible_by_day": pipeline_result["eligible_by_day"],
        "selected": pipeline_result["selected"],
        "alerts": pipeline_result["alerts"],
        "calibration": {
            "version": calibration.get("version"),
            "n_samples": calibration.get("n_samples"),
            "markets": len(calibration.get("markets") or {}),
        },
        "skipped_manual": sorted(manual_ids & prematch_ids),
    }
    log_sync_summary(
        total_matches=result["total_matches"],
        candidate_count=result["candidates"],
        selected_count=result["selected_count"],
        feedback_written=False,
        day=local_day,
        matches_by_day=pipeline_result["matches_by_day"],
        selected_by_day=pipeline_result["by_day"],
    )
    return result


def log_sync_summary(
    *,
    total_matches: int,
    candidate_count: int,
    selected_count: int,
    feedback_written: bool,
    consistency_rejected: int = 0,
    day: str | None = None,
    matches_by_day: dict[str, int] | None = None,
    selected_by_day: dict[str, int] | None = None,
) -> None:
    del feedback_written, consistency_rejected
    logger.info(
        "Recommendation sync summary day=%s total=%s eligible=%s selected=%s",
        day or "unknown",
        total_matches,
        candidate_count,
        selected_count,
    )
    for match_day, pool in sorted((matches_by_day or {}).items()):
        count = int((selected_by_day or {}).get(match_day, 0))
        if count < AUTO_PICK_LIMIT and pool >= MIN_MATCHES_FOR_FULL_QUOTA:
            logger.warning(
                "Recommendation day incomplete match_day=%s pool=%s selected=%s expected=%s",
                match_day,
                pool,
                count,
                AUTO_PICK_LIMIT,
            )
