"""Published 1X2 probabilities must be verifiable from quoted match-winner odds."""

from app.services.prediction import (
    implied_probs_from_odds,
    published_match_probabilities,
    working_match_probabilities,
)


def _board(home: str, draw: str, away: str) -> dict:
    return {
        "available": True,
        "match_winner": {"home": home, "draw": draw, "away": away},
    }


def test_published_probabilities_follow_de_vigged_odds_not_ml_softmax() -> None:
    odds = _board("1.21", "6.86", "11.39")
    extreme_ml = {"home": 0.999, "draw": 0.0005, "away": 0.0005}
    published = published_match_probabilities(extreme_ml, odds)
    expected = implied_probs_from_odds(odds)
    assert expected is not None
    assert abs(published["home"] - expected["home"]) < 1e-6
    assert published["home"] < 0.85
    assert published["home"] > 0.70


def test_working_probabilities_keep_model_when_not_flat() -> None:
    odds = _board("1.21", "6.86", "11.39")
    model = {"home": 0.62, "draw": 0.22, "away": 0.16}
    working = working_match_probabilities(model, odds)
    assert abs(working["home"] - 0.62) < 1e-6


def test_published_without_board_falls_back_to_model() -> None:
    model = {"home": 0.62, "draw": 0.22, "away": 0.16}
    published = published_match_probabilities(model, {"available": False})
    assert abs(published["home"] - 0.62) < 1e-6
