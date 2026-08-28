"""Daily recommendation pipeline: calibration → strategy → Top-N picks."""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import datetime, timezone
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
from app.services.auto_favorites import (
    AUTO_PICK_LIMIT,
    AutoPickCandidate,
    within_day_quality_ratings,
)
from app.services.prediction import implied_probs_from_odds
from app.services.prematch_package import package_from_record, rehydrate_odds_markets
from app.services.recommendation.calibration import (
    calibrate_match,
    load_calibration_artifact,
    train_from_frozen_history,
)
from app.services.recommendation.feedback import (
    apply_feedback_to_picks,
    ensure_feedback_state,
    feedback_summary,
    pick_rank_key,
)
from app.services.recommendation.consistency import validate_consistency_batch
from app.services.recommendation.features import build_match_features
from app.services.results_capture import prematch_list_clause
from app.services.user_scope import ANON_OWNER_ID

from app.services.recommendation.strategy import OUTCOMES, decide_match

logger = logging.getLogger(__name__)

MARKET_1X2 = "1x2"
OUTCOME_TO_LEAN = {"home": "胜", "draw": "平", "away": "负"}
MIN_MATCHES_FOR_FULL_QUOTA = 6


@dataclass(frozen=True)
class MatchPipelineInput:
    fixture_id: int
    league_id: int
    kickoff: datetime
    match_day: str
    odds: dict[str, Any] | None
    package: dict[str, Any] | None = None
    # 大小球 / 双方进球是与方向无关的结论，日推重算比分时沿用本场这两条。
    goal_lean: str | None = None
    both_score_lean: str | None = None


@dataclass(frozen=True)
class PipelineMatchResult:
    fixture_id: int
    league_id: int
    kickoff: datetime
    match_day: str
    features: dict[str, Any]
    calibration: dict[str, Any] | None
    strategy: dict[str, Any]


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
    calibrated_home_prob: float
    calibrated_draw_prob: float
    calibrated_away_prob: float
    reliability: float
    sample_size: int
    score: float
    handicap_lean: str | None = None
    score_hint: str | None = None
    is_consistent: bool = True
    conflict_reason: str = "自洽"
    conflict_detail: str = ""


def _count_matches_by_day(matches: list[MatchPipelineInput]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for match in matches:
        counts[match.match_day] = counts.get(match.match_day, 0) + 1
    return counts


def log_sync_summary(
    *,
    total_matches: int,
    positive_ev_count: int,
    selected_count: int,
    feedback_written: bool,
    consistency_rejected: int = 0,
    day: str | None = None,
) -> None:
    """Emit structured daily sync metrics; warn when picks < 4 on busy days."""
    day_label = day or "unknown"
    logger.info(
        "Recommendation sync summary day=%s total_matches=%s positive_ev=%s selected=%s "
        "feedback_written=%s consistency_rejected=%s",
        day_label,
        total_matches,
        positive_ev_count,
        selected_count,
        feedback_written,
        consistency_rejected,
    )
    if total_matches >= MIN_MATCHES_FOR_FULL_QUOTA and selected_count < AUTO_PICK_LIMIT:
        logger.warning(
            "Recommendation sync alert day=%s selected=%s<%s while total_matches=%s>=%s",
            day_label,
            selected_count,
            AUTO_PICK_LIMIT,
            total_matches,
            MIN_MATCHES_FOR_FULL_QUOTA,
        )
    elif total_matches < MIN_MATCHES_FOR_FULL_QUOTA:
        logger.info(
            "Recommendation sync day=%s total_matches=%s<%s; selected all positive EV=%s",
            day_label,
            total_matches,
            MIN_MATCHES_FOR_FULL_QUOTA,
            selected_count,
        )


def _decimal_odd_for_choice(
    odds: dict[str, Any] | None,
    choice: str,
) -> float | None:
    if not isinstance(odds, dict) or not odds.get("available"):
        return None
    mw = odds.get("match_winner")
    if not isinstance(mw, dict):
        return None
    try:
        value = float(mw.get(choice))
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def process_match(
    match: MatchPipelineInput,
    *,
    artifact: dict[str, Any] | None = None,
) -> PipelineMatchResult | None:
    """Run one fixture through calibration → features → strategy."""
    calibration = calibrate_match(
        match_id=match.fixture_id,
        league_id=match.league_id,
        odds=match.odds,
        artifact=artifact,
    )
    if calibration is None:
        return None

    features = build_match_features(
        match_id=match.fixture_id,
        league_id=match.league_id,
        odds=match.odds,
        package=match.package,
        calibration=calibration,
    )
    strategy = decide_match(
        match_id=match.fixture_id,
        calibration=calibration,
        odds=match.odds,
        features=features,
    )
    return PipelineMatchResult(
        fixture_id=match.fixture_id,
        league_id=match.league_id,
        kickoff=match.kickoff,
        match_day=match.match_day,
        features=features,
        calibration=calibration,
        strategy=strategy,
    )


def _positive_ev_results(
    results: list[PipelineMatchResult],
) -> list[PipelineMatchResult]:
    return [
        item
        for item in results
        if item.strategy.get("recommended_choice") in OUTCOMES
        and float(item.strategy.get("ev") or 0.0) > 0.0
    ]


def _to_daily_pick(
    result: PipelineMatchResult,
    *,
    odds: dict[str, Any] | None,
) -> DailyRecommendationPick | None:
    choice = result.strategy.get("recommended_choice")
    if choice not in OUTCOMES:
        return None
    ev = float(result.strategy.get("ev") or 0.0)
    if ev <= 0.0:
        return None

    decimal_odd = _decimal_odd_for_choice(odds, choice)
    if decimal_odd is None:
        return None

    calibration = result.calibration or {}
    implied = implied_probs_from_odds(odds) or {}
    confidence = float(result.strategy.get("confidence") or 0.0)
    raw_confidence = float(implied.get(choice, confidence))

    return DailyRecommendationPick(
        fixture_id=result.fixture_id,
        league_id=result.league_id,
        kickoff=result.kickoff,
        match_day=result.match_day,
        market=MARKET_1X2,
        lean=OUTCOME_TO_LEAN[choice],
        recommended_choice=choice,
        ev=ev,
        confidence=confidence,
        reason=str(result.strategy.get("reason") or ""),
        decimal_odd=decimal_odd,
        raw_confidence=raw_confidence,
        calibrated_home_prob=float(calibration.get("calibrated_home_prob") or 0.0),
        calibrated_draw_prob=float(calibration.get("calibrated_draw_prob") or 0.0),
        calibrated_away_prob=float(calibration.get("calibrated_away_prob") or 0.0),
        reliability=float(calibration.get("reliability") or 0.0),
        sample_size=int(calibration.get("sample_size") or 0),
        score=ev,
    )


def select_daily_picks_by_match_day(
    picks: list[DailyRecommendationPick],
    *,
    limit_per_day: int = AUTO_PICK_LIMIT,
    skip_fixture_ids: set[int] | None = None,
    matches_count_by_day: dict[str, int] | None = None,
) -> list[DailyRecommendationPick]:
    """Keep up to ``limit_per_day`` positive-EV picks per venue-local match day."""
    skip = skip_fixture_ids or set()
    day_totals = matches_count_by_day or {}
    by_day: dict[str, list[DailyRecommendationPick]] = {}
    for pick in picks:
        by_day.setdefault(pick.match_day, []).append(pick)

    selected: list[DailyRecommendationPick] = []
    for day in sorted(by_day):
        day_picks = sorted(by_day[day], key=pick_rank_key)
        day_total = int(day_totals.get(day, 0))
        day_limit = (
            limit_per_day
            if day_total >= MIN_MATCHES_FOR_FULL_QUOTA
            else len(day_picks)
        )
        count = 0
        for pick in day_picks:
            if pick.fixture_id in skip:
                continue
            selected.append(pick)
            count += 1
            if count >= day_limit:
                break
    return selected


def run_pipeline(
    matches: list[MatchPipelineInput],
    *,
    artifact: dict[str, Any] | None = None,
    incentive_state: Any | None = None,
    limit_per_day: int = AUTO_PICK_LIMIT,
    skip_fixture_ids: set[int] | None = None,
) -> dict[str, Any]:
    """Score prematch fixtures and return per-day Top-N positive-EV 1X2 picks."""
    artifact = artifact if artifact is not None else load_calibration_artifact()
    odds_by_fixture = {match.fixture_id: match.odds for match in matches}
    goal_lean_by_fixture = {match.fixture_id: match.goal_lean for match in matches}
    both_score_lean_by_fixture = {
        match.fixture_id: match.both_score_lean for match in matches
    }
    matches_count_by_day = _count_matches_by_day(matches)

    processed: list[PipelineMatchResult] = []
    for match in matches:
        result = process_match(match, artifact=artifact)
        if result is not None:
            processed.append(result)

    positive = _positive_ev_results(processed)
    picks: list[DailyRecommendationPick] = []
    for result in positive:
        pick = _to_daily_pick(result, odds=odds_by_fixture.get(result.fixture_id))
        if pick is not None:
            picks.append(pick)

    picks = apply_feedback_to_picks(picks, state=incentive_state)
    picks.sort(key=pick_rank_key)
    positive_ev_count = len(picks)
    skipped = skip_fixture_ids or set()
    consistency_pool = [pick for pick in picks if pick.fixture_id not in skipped]
    consistent_pairs, rejected = validate_consistency_batch(
        consistency_pool,
        probs_by_fixture={
            pick.fixture_id: {
                "home": pick.calibrated_home_prob,
                "draw": pick.calibrated_draw_prob,
                "away": pick.calibrated_away_prob,
            }
            for pick in consistency_pool
        },
        goal_lean_by_fixture=goal_lean_by_fixture,
        both_score_lean_by_fixture=both_score_lean_by_fixture,
        odds_by_fixture=odds_by_fixture,
    )
    picks = [
        replace(
            pick,
            handicap_lean=decision.handicap_lean,
            score_hint=decision.score_hint,
            is_consistent=decision.is_consistent,
            conflict_reason=decision.conflict_reason,
            conflict_detail=decision.conflict_detail,
        )
        for pick, decision in consistent_pairs
    ]
    selected = select_daily_picks_by_match_day(
        picks,
        limit_per_day=limit_per_day,
        skip_fixture_ids=skip_fixture_ids,
        matches_count_by_day=matches_count_by_day,
    )

    ratings = within_day_quality_ratings(
        [
            AutoPickCandidate(
                fixture_id=pick.fixture_id,
                league_id=pick.league_id,
                kickoff=pick.kickoff,
                match_day=pick.match_day,
                score=pick.score,
                market=pick.market,
                lean=pick.lean,
                raw_confidence=pick.raw_confidence,
                confidence=pick.confidence,
                decimal_odd=pick.decimal_odd,
                expected_return=pick.ev,
            )
            for pick in selected
        ]
    )

    by_day_counts: dict[str, int] = {}
    for pick in selected:
        by_day_counts[pick.match_day] = by_day_counts.get(pick.match_day, 0) + 1

    return {
        "total_matches": len(matches),
        "processed_count": len(processed),
        "positive_ev_count": positive_ev_count,
        "consistency_rejected_count": len(rejected),
        "selected_count": len(selected),
        "by_day": by_day_counts,
        "feedback": feedback_summary(incentive_state),
        "selected": [
            {
                "fixture_id": pick.fixture_id,
                "match_day": pick.match_day,
                "market": pick.market,
                "lean": pick.lean,
                "handicap_lean": pick.handicap_lean,
                "recommended_choice": pick.recommended_choice,
                "ev": round(pick.ev, 4),
                "confidence": round(pick.confidence, 4),
                "reason": pick.reason,
                "decimal_odd": round(pick.decimal_odd, 3),
                "expected_return": round(pick.ev, 4),
                "score": round(pick.score, 4),
                "raw_confidence": round(pick.raw_confidence, 4),
                "calibrated_home_prob": round(pick.calibrated_home_prob, 4),
                "calibrated_draw_prob": round(pick.calibrated_draw_prob, 4),
                "calibrated_away_prob": round(pick.calibrated_away_prob, 4),
                "reliability": round(pick.reliability, 4),
                "sample_size": pick.sample_size,
                "quality_rating": ratings.get(pick.fixture_id),
                "score_hint": pick.score_hint,
                "is_consistent": pick.is_consistent,
                "conflict_reason": pick.conflict_reason,
                "conflict_detail": pick.conflict_detail,
            }
            for pick in selected
        ],
        "rejected": rejected,
        "picks": selected,
        "ratings": ratings,
    }


def match_input_from_fixture_row(
    fixture: Fixture,
    stored: PreMatchData,
) -> MatchPipelineInput:
    package = package_from_record(stored)
    odds_raw = package.get("odds") if isinstance(package, dict) else None
    odds = (
        rehydrate_odds_markets(odds_raw)
        if isinstance(odds_raw, dict)
        else None
    )
    match_day = str(getattr(fixture, "match_day", None) or fixture.date.strftime("%Y-%m-%d"))
    return MatchPipelineInput(
        fixture_id=int(fixture.id),
        league_id=int(fixture.league_id),
        kickoff=fixture.date,
        match_day=match_day,
        odds=odds if isinstance(odds, dict) else None,
        package=package if isinstance(package, dict) else None,
        goal_lean=stored.goal_lean,
        both_score_lean=stored.both_score_lean,
    )


async def collect_prematch_pipeline_inputs(
    db: AsyncSession,
    *,
    now: datetime | None = None,
) -> list[MatchPipelineInput]:
    """Load prematch fixtures that already have a stored pre-match package."""
    current = now or datetime.now(timezone.utc).replace(tzinfo=None)
    rows = (
        await db.execute(
            select(Fixture, PreMatchData, MatchFeature)
            .join(PreMatchData, PreMatchData.fixture_id == Fixture.id)
            .outerjoin(MatchFeature, MatchFeature.fixture_id == Fixture.id)
            .where(prematch_list_clause(current))
            .order_by(Fixture.date, Fixture.id)
        )
    ).all()

    by_fixture: dict[int, tuple[Fixture, PreMatchData, MatchFeature | None]] = {}
    for fixture, stored, feature in rows:
        prev = by_fixture.get(fixture.id)
        if prev is None or (feature is not None and prev[2] is None):
            by_fixture[fixture.id] = (fixture, stored, feature)

    return [
        match_input_from_fixture_row(fixture, stored)
        for fixture, stored, _feature in by_fixture.values()
    ]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def sync_daily_recommendations(
    db: AsyncSession,
    *,
    user_id: str | None = None,
    limit: int = AUTO_PICK_LIMIT,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Replace guest-bucket auto tips with pipeline Top-N positive-EV 1X2 picks."""
    del user_id  # product-wide tips; kept for call-site compat
    owner = ANON_OWNER_ID
    settings = get_settings()
    current = now or _utc_now()

    incentive_state = await ensure_feedback_state(db, now=current)
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
        artifact=calibration,
        incentive_state=incentive_state,
        limit_per_day=limit,
        skip_fixture_ids=manual_ids,
    )
    selected: list[DailyRecommendationPick] = pipeline_result["picks"]
    ratings: dict[int, float] = pipeline_result["ratings"]
    prematch_ids = {match.fixture_id for match in matches}
    selected_ids = {pick.fixture_id for pick in selected}

    await db.execute(
        delete(FavoriteFixture).where(
            FavoriteFixture.user_id == owner,
            FavoriteFixture.source == FAVORITE_SOURCE_AUTO,
        )
    )

    saved_at = _utc_now()
    for pick in selected:
        db.add(
            FavoriteFixture(
                fixture_id=pick.fixture_id,
                user_id=owner,
                source=FAVORITE_SOURCE_AUTO,
                auto_market=pick.market,
                auto_lean=pick.lean,
                auto_handicap_lean=pick.handicap_lean,
                auto_score_hint=pick.score_hint,
                quality_rating=ratings.get(pick.fixture_id),
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
                lean=pick.lean,
                handicap_lean=pick.handicap_lean,
                score_hint=pick.score_hint,
                raw_confidence=pick.raw_confidence,
                confidence=pick.confidence,
                decimal_odd=pick.decimal_odd,
                expected_return=pick.ev,
                score=pick.score,
                quality_rating=ratings.get(pick.fixture_id),
                picked_at=saved_at,
            )
        )

    await db.commit()

    tz_name = settings.SCHEDULER_TIMEZONE
    try:
        local_day = datetime.now(ZoneInfo(tz_name)).date().isoformat()
    except Exception:
        local_day = saved_at.date().isoformat()

    feedback_meta = pipeline_result.get("feedback") or {}
    feedback_written = bool(
        feedback_meta.get("enabled")
        and feedback_meta.get("updated_day") == local_day
    )

    result = {
        "day": local_day,
        "total_matches": pipeline_result.get("total_matches", len(matches)),
        "candidates": pipeline_result["positive_ev_count"],
        "selected_count": pipeline_result["selected_count"],
        "consistency_rejected_count": pipeline_result.get(
            "consistency_rejected_count", 0
        ),
        "feedback_written": feedback_written,
        "calibration": {
            "version": calibration.get("version"),
            "n_matches": calibration.get("n_matches"),
            "leagues": len(calibration.get("leagues") or {}),
        },
        "feedback": feedback_meta,
        "by_day": pipeline_result["by_day"],
        "selected": pipeline_result["selected"],
        "rejected": pipeline_result.get("rejected", []),
        "skipped_manual": sorted(
            {
                pick.fixture_id
                for pick in selected
                if pick.fixture_id in manual_ids
            }
        ),
    }
    log_sync_summary(
        total_matches=int(result["total_matches"]),
        positive_ev_count=int(result["candidates"]),
        selected_count=int(result["selected_count"]),
        feedback_written=feedback_written,
        consistency_rejected=int(result["consistency_rejected_count"]),
        day=local_day,
    )
    return result
