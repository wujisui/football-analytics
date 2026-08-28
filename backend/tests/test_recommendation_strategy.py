"""EV-max recommendation strategy (no official API calls)."""

from app.services.recommendation.strategy import (
    REASON_NO_POSITIVE_EV,
    REASON_POSITIVE_EV,
    decide_match,
    expected_value,
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


def test_picks_highest_positive_ev_outcome() -> None:
    # Home: 2.0 * 0.55 - 1 = 0.10
    # Draw: 3.4 * 0.25 - 1 = -0.15
    # Away: 4.0 * 0.20 - 1 = -0.20
    payload = decide_match(
        match_id=1001,
        calibration=_calibration(),
        odds=_odds(),
    )
    assert payload["recommended_choice"] == "home"
    assert abs(payload["ev"] - 0.10) < 1e-9
    assert payload["reason"] == REASON_POSITIVE_EV
    assert abs(payload["confidence"] - 0.55) < 1e-9


def test_skips_when_all_ev_non_positive() -> None:
    payload = decide_match(
        match_id=1002,
        calibration=_calibration(home=0.40, draw=0.30, away=0.30),
        odds=_odds(home=2.0, draw=3.0, away=3.5),
    )
    assert payload["recommended_choice"] is None
    assert payload["ev"] <= 0.0
    assert payload["confidence"] == 0.0
    assert payload["reason"] == REASON_NO_POSITIVE_EV


def test_missing_odds_is_not_recommended() -> None:
    payload = decide_match(
        match_id=1003,
        calibration=_calibration(),
        odds=None,
    )
    assert payload["recommended_choice"] is None
    assert payload["reason"] == REASON_NO_POSITIVE_EV
