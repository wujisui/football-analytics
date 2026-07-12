"""Smoke checks for mean-reversion features and multi-factor probs."""

from app.services.features import extract_features, mean_reversion_score
from app.services.ml_predictor import multifactor_probabilities, predict_probabilities


def test_long_win_streak_fades():
    fade = mean_reversion_score(win_streak=6, winless_streak=0, loss_streak=0, unbeaten_streak=6)
    assert fade < 0, fade


def test_long_winless_bounces():
    bounce = mean_reversion_score(win_streak=0, winless_streak=6, loss_streak=4, unbeaten_streak=0)
    assert bounce > 0, bounce


def test_streak_affects_probs():
    hot = extract_features(
        {
            "home_form": {"played": 6, "wins": 6, "draws": 0, "losses": 0, "form": "WWWWWW"},
            "away_form": {"played": 6, "wins": 1, "draws": 2, "losses": 3, "form": "LLDWLD"},
            "odds": {"available": False},
        }
    )
    cold = extract_features(
        {
            "home_form": {"played": 6, "wins": 0, "draws": 2, "losses": 4, "form": "LLDLLD"},
            "away_form": {"played": 6, "wins": 1, "draws": 2, "losses": 3, "form": "LLDWLD"},
            "odds": {"available": False},
        }
    )
    assert hot["home_reversion"] < 0
    assert cold["home_reversion"] > 0
    p_hot = multifactor_probabilities(hot)
    p_cold = multifactor_probabilities(cold)
    # Hot streak still favored by form, but less than a naive win-rate+0.1 would imply;
    # cold home should get bounce lift vs pure loss rate.
    assert p_hot["home"] > p_cold["home"]
    assert cold["home_reversion"] > hot["home_reversion"]


def test_odds_not_sole_driver():
    # Strong odds favorite but terrible winless streak / weak form → model should not
    # just mirror ~70% odds home.
    package = {
        "home_form": {"played": 8, "wins": 0, "draws": 2, "losses": 6, "form": "LLDLLDLL"},
        "away_form": {"played": 8, "wins": 5, "draws": 2, "losses": 1, "form": "WWDLWWW"},
        "odds": {
            "available": True,
            "match_winner": {"home": 1.40, "draw": 4.50, "away": 7.50},
        },
        "head_to_head": {"played": 0},
    }
    pred = predict_probabilities(package)
    assert pred.source == "multifactor"
    # Odds-implied home ≈ 1/1.4 / (1/1.4+1/4.5+1/7.5) ≈ 0.66+
    assert pred.probs["home"] < 0.55, pred.probs
    assert pred.features["home_reversion"] > 0


if __name__ == "__main__":
    test_long_win_streak_fades()
    test_long_winless_bounces()
    test_streak_affects_probs()
    test_odds_not_sole_driver()
    print("ok")
