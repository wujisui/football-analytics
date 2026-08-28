"""Daily recommendation pipeline: calibration → strategy → Top-N picks."""

from __future__ import annotations

import logging
from dataclasses import dataclass
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
from app.services.recommendation.strategy import OUTCOMES, decide_match
from app.services.results_capture import prematch_list_clause
from app.services.user_scope import ANON_OWNER_ID

logger = logging.getLogger(__name__)

MARKET_1X2 = "1x2"
OUTCOME_TO_LEAN = {"home": "胜", "draw": "平", "away": "负"}


@dataclass(frozen=True)
class MatchPipelineInput:
    fixture_id: int
    league_id: int
    kickoff: datetime
    match_day: str
    odds: dict[str, Any] | None
    package: dict[str, Any] | None = None


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


def build_features_placeholder(match: MatchPipelineInput) -> dict[str, Any]:
    """Reserved for ``features.py``; returns an empty feature vector for now."""
    del match
    return {}


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
    """Run one fixture through features (placeholder) → calibration → strategy."""
    features = build_features_placeholder(match)
    calibration = calibrate_match(
        match_id=match.fixture_id,
        league_id=match.league_id,
        odds=match.odds,
        artifact=artifact,
    )
    if calibration is None:
        return None

    strategy = decide_match(
        match_id=match.fixture_id,
        calibration=calibration,
        odds=match.odds,
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
) -> list[DailyRecommendationPick]:
    """Keep up to ``limit_per_day`` positive-EV picks per venue-local match day."""
    skip = skip_fixture_ids or set()
    by_day: dict[str, list[DailyRecommendationPick]] = {}
    for pick in picks:
        by_day.setdefault(pick.match_day, []).append(pick)

    selected: list[DailyRecommendationPick] = []
    for day in sorted(by_day):
        day_picks = sorted(
            by_day[day],
            key=lambda item: (-item.ev, item.kickoff, item.fixture_id),
        )
        count = 0
        for pick in day_picks:
            if pick.fixture_id in skip:
                continue
            selected.append(pick)
            count += 1
            if count >= limit_per_day:
                break
    return selected


def run_pipeline(
    matches: list[MatchPipelineInput],
    *,
    artifact: dict[str, Any] | None = None,
    limit_per_day: int = AUTO_PICK_LIMIT,
    skip_fixture_ids: set[int] | None = None,
) -> dict[str, Any]:
    """Score prematch fixtures and return per-day Top-N positive-EV 1X2 picks."""
    artifact = artifact if artifact is not None else load_calibration_artifact()
    odds_by_fixture = {match.fixture_id: match.odds for match in matches}

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

    picks.sort(key=lambda item: (-item.ev, item.kickoff, item.fixture_id))
    selected = select_daily_picks_by_match_day(
        picks,
        limit_per_day=limit_per_day,
        skip_fixture_ids=skip_fixture_ids,
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
        "processed_count": len(processed),
        "positive_ev_count": len(picks),
        "selected_count": len(selected),
        "by_day": by_day_counts,
        "selected": [
            {
                "fixture_id": pick.fixture_id,
                "match_day": pick.match_day,
                "market": pick.market,
                "lean": pick.lean,
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
            }
            for pick in selected
        ],
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

    result = {
        "day": local_day,
        "candidates": pipeline_result["positive_ev_count"],
        "selected_count": pipeline_result["selected_count"],
        "calibration": {
            "version": calibration.get("version"),
            "n_matches": calibration.get("n_matches"),
            "leagues": len(calibration.get("leagues") or {}),
        },
        "by_day": pipeline_result["by_day"],
        "selected": pipeline_result["selected"],
        "skipped_manual": sorted(
            {
                pick.fixture_id
                for pick in selected
                if pick.fixture_id in manual_ids
            }
        ),
    }
    logger.info(
        "Recommendation pipeline day=%s selected=%s positive_ev=%s by_day=%s",
        local_day,
        len(selected),
        pipeline_result["positive_ev_count"],
        pipeline_result["by_day"],
    )
    return result
