import unittest

from app.services.goal_predictor import (
    GoalPrediction,
    distribution_summary,
    extract_goal_features,
)


class GoalPredictorTests(unittest.TestCase):
    def test_market_features_use_prematch_boards(self) -> None:
        base = {
            "odds_home": 0.5,
            "odds_draw": 0.3,
            "odds_away": 0.2,
            "home_wr_5": 0.6,
            "away_wr_5": 0.2,
            "home_dr_5": 0.2,
            "away_dr_5": 0.3,
            "home_gd_avg_5": 0.8,
            "away_gd_avg_5": -0.2,
            "rank_diff": 0.4,
            "home_advantage": 1.0,
        }
        odds = {
            "available": True,
            "goals_ou": {"line": "2.5", "home": 2.0, "away": 1.8},
            "asian_handicap": {"line": "-0.5", "home": 1.9, "away": 1.9},
        }
        features = extract_goal_features(base, odds)
        self.assertEqual(features["ou_line"], 2.5)
        self.assertEqual(features["ah_line"], -0.5)
        self.assertEqual(features["has_ou"], 1.0)
        self.assertEqual(features["has_ah"], 1.0)
        self.assertAlmostEqual(
            features["ou_over_prob"] + features["ou_under_prob"], 1.0
        )

    def test_distribution_is_normalized_and_consistent(self) -> None:
        summary = distribution_summary(
            GoalPrediction(1.55, 1.2, "test"),
            total_line=2.5,
        )
        self.assertAlmostEqual(
            summary["home_prob"] + summary["draw_prob"] + summary["away_prob"],
            1.0,
            places=7,
        )
        self.assertAlmostEqual(
            summary["over_prob"] + summary["under_prob"],
            1.0,
            places=7,
        )
        self.assertEqual(len(summary["scores"]), 2)
        self.assertGreater(summary["btts_prob"], 0.0)
        self.assertLess(summary["btts_prob"], 1.0)


if __name__ == "__main__":
    unittest.main()
