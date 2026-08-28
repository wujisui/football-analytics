"""Recommendation feature vectors."""

from app.services.recommendation.features import FEATURE_KEYS, build_match_features


def test_build_match_features_returns_required_keys() -> None:
    payload = build_match_features(
        match_id=1001,
        league_id=39,
        odds={
            "available": True,
            "match_winner": {"home": 2.0, "draw": 3.4, "away": 4.0},
            "asian_handicap": {
                "line": "-0.25",
                "home": 1.95,
                "away": 1.90,
            },
        },
        package={
            "odds_opening": {
                "available": True,
                "asian_handicap": {
                    "line": "0",
                    "home": 1.90,
                    "away": 1.95,
                },
            },
            "home_form": {"matches": [{"result": "W"}, {"result": "W"}, {"result": "D"}]},
            "away_form": {"matches": [{"result": "L"}, {"result": "D"}, {"result": "L"}]},
            "injuries": {"home": [{"name": "A"}], "away": [{"name": "B"}, {"name": "C"}]},
        },
        calibration={"reliability": 0.72},
    )
    assert payload["match_id"] == 1001
    for key in FEATURE_KEYS:
        assert key in payload
    assert payload["league_reliability"] == 0.72
    assert payload["ah_line_shift"] == -0.25
    assert payload["form_wr5_diff"] > 0
