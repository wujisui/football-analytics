"""Unified recommendation pipeline: model → Platt → EV → reference → Top 4."""

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
from app.services.match_day import fixture_match_day
from app.services.prematch_package import package_from_record, rehydrate_odds_markets
from app.services.probability_calibration import (
    load_calibration_artifact,
    train_from_frozen_history,
)
from app.services.recommendation.decision import (
    MatchDecision,
    RecommendationCandidate,
    build_match_decision,
    star_rating,
)
from app.services.results_capture import prematch_list_clause
from app.services.user_scope import ANON_OWNER_ID

logger = logging.getLogger(__name__)


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
    ev: float
    confidence: float
    reason: str
    decimal_odd: float
    raw_confidence: float
    score: float
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
    adjusted_ev: float = 0.0
    is_consistent: bool = True
    conflict_reason: str = "统一决策链路"
    conflict_detail: str = ""


def _companion_lean(match: MatchPipelineInput) -> str:
    text = str(match.recommendation or "").strip()
    if text in {"主胜", "胜"}:
        return "主胜"
    if text in {"客胜", "负"}:
        return "客胜"
    return (
        "主胜"
        if float(match.home_win_prob or 0.0) >= float(match.away_win_prob or 0.0)
        else "客胜"
    )


def _reason(candidate: RecommendationCandidate) -> str:
    relation = {
        "aligned_strong": "强一致",
        "aligned_weak": "一致",
        "unknown": "方向不明确",
        "reverse_weak": "逆向推荐（弱）",
        "reverse_strong": "逆向推荐（强）",
    }.get(candidate.direction_alignment, candidate.direction_alignment)
    ev = (
        f"{candidate.expected_return:+.2%}"
        if candidate.expected_return is not None
        else "不可计算"
    )
    adjusted = (
        f"{candidate.adjusted_ev:+.2%}"
        if candidate.adjusted_ev is not None
        else "不可计算"
    )
    return (
        f"玩法：{candidate.market}；模型与盘口：{relation}；"
        f"EV：{ev}；方向修正后：{adjusted}"
    )


def _skip_reason_text(candidate: RecommendationCandidate) -> str:
    reason = {
        "model_not_deployable": "该玩法模型尚未通过时间留出验证，方向仅供参考，EV 暂不可算",
        "calibrator_unavailable": "该玩法尚无通过验证的 Platt 校准器，EV 暂不可算",
        "odds_missing": "缺少可结算赔率，EV 暂不可算",
        "settlement_distribution_unavailable": "缺少真实盘口结算分布，EV 暂不可算",
        "odds_and_model_unavailable": "模型与盘口数据均不足，暂不能给出可靠 EV",
    }.get(candidate.skip_reason or "")
    return reason or _reason(candidate)


def _to_pick(
    match: MatchPipelineInput,
    decision: MatchDecision,
) -> DailyRecommendationPick | None:
    candidate = decision.reference
    if (
        candidate.expected_return is None
        or candidate.adjusted_ev is None
        or candidate.calibrated_probability is None
        or candidate.decimal_odd is None
        or candidate.raw_model_probability is None
    ):
        return None
    result_lean = (
        candidate.lean if candidate.market == "1x2" else _companion_lean(match)
    )
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
        raw_confidence=candidate.raw_model_probability,
        score=candidate.adjusted_ev,
        market_lean=candidate.lean,
        handicap_lean=(
            candidate.lean if candidate.market == "ah" else match.handicap_lean
        ),
        score_hint=match.score_hint,
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
            "严格玩法顺序：有 AH 时 AH→大小球→双进；"
            "无 AH 时 1X2→大小球→双进"
        ),
    )


def select_daily_picks_by_match_day(
    picks: list[DailyRecommendationPick],
    *,
    limit_per_day: int = AUTO_PICK_LIMIT,
    skip_fixture_ids: set[int] | None = None,
) -> list[DailyRecommendationPick]:
    """Take each venue-local day's highest adjusted-EV fixtures."""
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
                -float(pick.adjusted_ev),
                -float(pick.confidence),
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
        "raw_model_probability": candidate.raw_model_probability,
        "calibrator_version": candidate.calibrator_version,
        "calibrated_probability": candidate.calibrated_probability,
        "implied_probability": candidate.implied_probability,
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
    """Build every reference, then rank only EV-computable references."""
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
    ratings = {
        pick.fixture_id: star_rating(pick.adjusted_ev)
        for pick in selected
    }
    matches_by_day: dict[str, int] = {}
    eligible_by_day: dict[str, int] = {}
    selected_by_day: dict[str, int] = {}
    for match in matches:
        matches_by_day[match.match_day] = matches_by_day.get(match.match_day, 0) + 1
    for pick in eligible:
        eligible_by_day[pick.match_day] = eligible_by_day.get(pick.match_day, 0) + 1
    for pick in selected:
        selected_by_day[pick.match_day] = selected_by_day.get(pick.match_day, 0) + 1
    alerts: list[dict[str, Any]] = []
    for match_day, pool in matches_by_day.items():
        selected_count = selected_by_day.get(match_day, 0)
        if selected_count < limit_per_day:
            alerts.append(
                {
                    "code": "daily_pick_shortfall",
                    "match_day": match_day,
                    "selected": selected_count,
                    "expected": limit_per_day,
                    "matches": pool,
                    "ev_computable": eligible_by_day.get(match_day, 0),
                }
            )
            logger.warning(
                "Daily Top-4 incomplete match_day=%s selected=%s expected=%s "
                "matches=%s ev_computable=%s",
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
                "ev": round(pick.ev, 4),
                "adjusted_ev": round(pick.adjusted_ev, 4),
                "confidence": round(pick.confidence, 4),
                "raw_model_probability": round(pick.raw_confidence, 4),
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
                "quality_rating": ratings[pick.fixture_id],
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
        "ratings": ratings,
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
    selected_ids: set[int],
    captured_at: datetime,
) -> None:
    prematch_ids = {match.fixture_id for match in matches}
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
        stored.reference_adjusted_ev = reference.adjusted_ev
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
                    raw_model_probability=candidate.raw_model_probability,
                    calibrator_version=candidate.calibrator_version,
                    calibrated_probability=candidate.calibrated_probability,
                    implied_probability=candidate.implied_probability,
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
                        is_reference and candidate.fixture_id in selected_ids
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
    """Refresh all-match references and the adjusted-EV daily Top 4."""
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
    ratings: dict[int, float] = pipeline_result["ratings"]
    selected_ids = {pick.fixture_id for pick in selected}
    prematch_ids = {match.fixture_id for match in matches}
    saved_at = _utc_now()

    await _persist_candidates_and_references(
        db,
        matches=matches,
        decisions=pipeline_result["decisions"],
        selected_ids=selected_ids,
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
                quality_rating=ratings[pick.fixture_id],
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
                model_source=pick.model_source,
                model_version=pick.model_version,
                calibrator_version=pick.calibrator_version,
                direction_alignment=pick.direction_alignment,
                score=pick.adjusted_ev,
                quality_rating=ratings[pick.fixture_id],
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
        "Recommendation sync summary day=%s total=%s ev_computable=%s selected=%s",
        day or "unknown",
        total_matches,
        candidate_count,
        selected_count,
    )
    for match_day, pool in sorted((matches_by_day or {}).items()):
        count = int((selected_by_day or {}).get(match_day, 0))
        if count < AUTO_PICK_LIMIT:
            logger.warning(
                "Recommendation day incomplete match_day=%s pool=%s selected=%s expected=%s",
                match_day,
                pool,
                count,
                AUTO_PICK_LIMIT,
            )
