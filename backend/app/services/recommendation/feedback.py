"""Historical feedback layer for the recommendation pipeline.

The strategy decides *which* side of a fixture is recommendable. This module
applies persisted daily-pick EMA + league×market soft weights to the ranking
score only — the base is the probability/payout risk-adjusted return score, so
a boost always moves a pick up and a penalty always moves it down.

Persistence and learning logic live in ``auto_pick_incentive``; this file
is the pipeline-facing adapter so calibration / strategy stay unchanged.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.auto_pick_incentive import (
    IncentiveState,
    adjust_pick_score,
    ensure_incentives_for_picks,
)

if TYPE_CHECKING:
    from app.services.recommendation.pipeline import DailyRecommendationPick


async def ensure_feedback_state(
    db: AsyncSession,
    *,
    now: datetime | None = None,
) -> IncentiveState:
    """Load or refresh once-per-day incentive state from settled picks."""
    return await ensure_incentives_for_picks(db, now=now)


def feedback_adjusted_score(
    base_score: float,
    *,
    league_id: int,
    market: str,
    state: IncentiveState | None,
) -> float:
    """Apply EMA + soft-weight multipliers to a risk-adjusted return base."""
    if state is None:
        return float(base_score)
    return adjust_pick_score(
        float(base_score),
        league_id=int(league_id),
        market=market,
        state=state,
    )


def apply_feedback_to_pick(
    pick: DailyRecommendationPick,
    *,
    state: IncentiveState | None,
) -> DailyRecommendationPick:
    """Return a copy whose ``score`` reflects historical feedback; ``ev`` unchanged."""
    adjusted = feedback_adjusted_score(
        pick.score,
        league_id=pick.league_id,
        market=pick.market,
        state=state,
    )
    if adjusted == pick.score:
        return pick
    return replace(pick, score=adjusted)


def apply_feedback_to_picks(
    picks: list[DailyRecommendationPick],
    *,
    state: IncentiveState | None,
) -> list[DailyRecommendationPick]:
    if state is None:
        return picks
    return [apply_feedback_to_pick(pick, state=state) for pick in picks]


def pick_rank_key(pick: DailyRecommendationPick) -> tuple[float, datetime, int]:
    """Sort key: feedback-adjusted score desc, then kickoff, then fixture id."""
    return (-float(pick.score), pick.kickoff, pick.fixture_id)


def feedback_summary(state: IncentiveState | None) -> dict[str, Any]:
    if state is None:
        return {"enabled": False}
    return {
        "enabled": True,
        "updated_day": state.updated_day,
        "ema_markets": sorted((state.ema_market or {}).keys()),
        "ema_leagues": len(state.ema_league or {}),
        "soft_weight_keys": len(state.soft_weights or {}),
    }
