"""Recommendation feedback adapter (wraps auto_pick_incentive)."""

from datetime import datetime, timezone

from app.services.auto_pick_incentive import IncentiveParams, IncentiveState
from app.services.recommendation.feedback import (
    apply_feedback_to_pick,
    apply_feedback_to_picks,
    feedback_adjusted_score,
    pick_rank_key,
)
from app.services.recommendation.pipeline import DailyRecommendationPick


def _pick(
    fixture_id: int,
    *,
    league_id: int = 39,
    ev: float = 0.10,
    score: float | None = None,
) -> DailyRecommendationPick:
    return DailyRecommendationPick(
        fixture_id=fixture_id,
        league_id=league_id,
        kickoff=datetime(2026, 8, 28, 15, 0, tzinfo=timezone.utc),
        match_day="2026-08-28",
        market="1x2",
        lean="胜",
        recommended_choice="home",
        ev=ev,
        confidence=0.56,
        reason="EV最大",
        decimal_odd=2.0,
        raw_confidence=0.50,
        calibrated_home_prob=0.56,
        calibrated_draw_prob=0.24,
        calibrated_away_prob=0.20,
        reliability=0.7,
        sample_size=100,
        score=ev if score is None else score,
    )


def test_feedback_keeps_raw_ev() -> None:
    state = IncentiveState(
        params=IncentiveParams(),
        ema_market={"1x2": 0.2},
        ema_league={"39": 0.1},
        soft_weights={"39|1x2": 1.1},
    )
    adjusted = apply_feedback_to_pick(_pick(1, ev=0.10), state=state)
    assert adjusted.ev == 0.10
    assert adjusted.score > 0.10


def test_feedback_does_not_change_pool_membership() -> None:
    picks = [_pick(1, ev=0.12), _pick(2, ev=0.08)]
    state = IncentiveState(
        params=IncentiveParams(),
        ema_market={"1x2": 0.3},
        ema_league={"40": 0.2},
        soft_weights={"global": 1.0, "40|1x2": 1.2},
    )
    boosted = apply_feedback_to_picks(picks, state=state)
    assert len(boosted) == 2
    assert all(item.ev > 0 for item in boosted)


def test_feedback_can_reorder_by_adjusted_score() -> None:
    low_ev = _pick(1, league_id=39, ev=0.11)
    high_ev = _pick(2, league_id=40, ev=0.10)
    state = IncentiveState(
        params=IncentiveParams(),
        ema_market={"1x2": 0.0},
        ema_league={"39": 0.0, "40": 0.3},
        soft_weights={"39|1x2": 0.9, "40|1x2": 1.25},
    )
    adjusted = apply_feedback_to_picks([low_ev, high_ev], state=state)
    assert feedback_adjusted_score(0.11, league_id=39, market="1x2", state=state) < (
        feedback_adjusted_score(0.10, league_id=40, market="1x2", state=state)
    )
    ranked = sorted(adjusted, key=pick_rank_key)
    assert ranked[0].fixture_id == 2
