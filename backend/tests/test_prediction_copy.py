import unittest

from app.services.prediction import (
    canonical_btts_lean,
    canonical_goal_lean,
    canonical_recommendation,
    canonical_score_hint,
    evaluate_prediction_vs_score,
    get_recommendation,
    summarize_accuracy,
)


class PredictionCopyTests(unittest.TestCase):
    def test_new_recommendations_are_compact(self) -> None:
        self.assertEqual(
            get_recommendation({"home": 0.7, "draw": 0.2, "away": 0.1}),
            "胜",
        )
        self.assertEqual(
            get_recommendation({"home": 0.45, "draw": 0.42, "away": 0.13}),
            "胜/平",
        )

    def test_historical_copy_is_canonicalized(self) -> None:
        self.assertEqual(canonical_recommendation("客胜"), "负")
        self.assertEqual(canonical_recommendation("主胜/平（主队不败）"), "胜/平")
        self.assertEqual(canonical_goal_lean("倾向小球（2.5）"), "小（2.5）")
        self.assertEqual(canonical_btts_lean("双方进球：是"), "双进:是")
        self.assertEqual(canonical_score_hint("2-1"), "比分:2-1")
        self.assertEqual(canonical_score_hint("比分：2-1"), "比分:2-1")

    def test_accuracy_accepts_new_and_historical_copy(self) -> None:
        common = {
            "home_goals": 2,
            "away_goals": 1,
            "score_hint": "比分:2-1",
            "goal_lean": "大（2.5）",
            "both_score_lean": "双进:是",
        }
        compact = evaluate_prediction_vs_score(**common, recommendation="胜")
        historical = evaluate_prediction_vs_score(
            **{
                **common,
                "score_hint": "2-1",
                "goal_lean": "倾向大球（2.5）",
                "both_score_lean": "双方进球：是",
            },
            recommendation="主胜",
        )
        for key in ("result_hit", "score_hit", "ou_hit", "btts_hit"):
            self.assertTrue(compact[key])
            self.assertTrue(historical[key])

    def test_summary_includes_handicap_accuracy(self) -> None:
        summary = summarize_accuracy(
            [
                {"has_prediction": True, "evaluable": True, "handicap_hit": True},
                {"has_prediction": True, "evaluable": True, "handicap_hit": False},
                {"has_prediction": True, "evaluable": True, "handicap_hit": None},
            ]
        )
        self.assertEqual(summary["handicap"], {"hits": 1, "total": 2, "rate": 0.5})


if __name__ == "__main__":
    unittest.main()
