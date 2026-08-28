"""Risk-adjusted recommendation strategy (no official API calls)."""

from app.services.recommendation.strategy import (
    REASON_NO_MARKET,
    REASON_RISK_ADJUSTED_RETURN,
    decide_match,
    expected_value,
    risk_adjusted_return_score,
)


def _calibration(
    *,
    match_id: int = 1001,
    home: float = 0.55,
    draw: float = 0.25,
    away: float = 0.20,
    reliability: float = 0.8,
) -> dict:
    return {
        "match_id": match_id,
        "calibrated_home_prob": home,
        "calibrated_draw_prob": draw,
        "calibrated_away_prob": away,
        "reliability": reliability,
        "sample_size": 120,
        "calibration_bias": {"home": 0.0, "draw": 0.0, "away": 0.0},
    }


def _odds(home: float = 2.0, draw: float = 3.4, away: float = 4.0) -> dict:
    return {
        "available": True,
        "match_winner": {"home": home, "draw": draw, "away": away},
    }


def test_expected_value_formula() -> None:
    assert abs(expected_value(2.0, 0.55) - 0.10) < 1e-9


def test_risk_score_rewards_payout_but_dampens_long_odds() -> None:
    assert risk_adjusted_return_score(0.50, 2.0) > risk_adjusted_return_score(
        0.625, 1.6
    )
    assert risk_adjusted_return_score(0.50, 2.0) > risk_adjusted_return_score(
        0.25, 4.0
    )


def test_picks_the_best_risk_adjusted_side() -> None:
    payload = decide_match(
        match_id=1001,
        calibration=_calibration(),
        odds=_odds(),
    )
    assert payload["recommended_choice"] == "home"
    assert payload["reason"] == REASON_RISK_ADJUSTED_RETURN
    assert abs(payload["confidence"] - 0.55) < 1e-9
    # EV rides along for audit even though it did not drive the choice.
    assert abs(payload["ev"] - 0.10) < 1e-9


def test_negative_ev_still_produces_a_payout_aware_pick() -> None:
    """EV 为负仍可入池；较高赔率在风险调整后可以胜过单纯高置信度。"""
    payload = decide_match(
        match_id=1002,
        calibration=_calibration(home=0.45, draw=0.14, away=0.41),
        odds=_odds(home=2.0, draw=6.0, away=2.3),
    )
    assert payload["recommended_choice"] == "away"
    assert payload["ev"] < 0.0
    assert abs(payload["confidence"] - 0.41) < 1e-9


def test_draw_is_never_picked_even_when_most_likely() -> None:
    payload = decide_match(
        match_id=1004,
        calibration=_calibration(home=0.30, draw=0.45, away=0.25),
        odds=_odds(),
    )
    assert payload["recommended_choice"] == "away"
    assert abs(payload["confidence"] - 0.25) < 1e-9


def test_confidence_shrinks_on_low_reliability_leagues() -> None:
    payload = decide_match(
        match_id=1005,
        calibration=_calibration(),
        odds=_odds(),
        features={"league_reliability": 0.4},
    )
    assert abs(payload["confidence"] - 0.55 * (0.75 + 0.25 * 0.4)) < 1e-9


def test_missing_odds_is_not_recommended() -> None:
    payload = decide_match(
        match_id=1003,
        calibration=_calibration(),
        odds=None,
    )
    assert payload["recommended_choice"] is None
    assert payload["reason"] == REASON_NO_MARKET
