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


HOME_BOARD = {
    "available": True,
    "match_winner": {"home": "1.70", "draw": "3.60", "away": "5.00"},
}


class PredictionCopyTests(unittest.TestCase):
    def test_new_recommendations_are_compact(self) -> None:
        self.assertEqual(
            get_recommendation({"home": 0.7, "draw": 0.2, "away": 0.1}, odds=HOME_BOARD),
            "胜",
        )
        self.assertEqual(
            get_recommendation(
                {"home": 0.45, "draw": 0.42, "away": 0.13}, odds=HOME_BOARD
            ),
            "胜/平",
        )

    def test_historical_copy_is_canonicalized(self) -> None:
        self.assertEqual(canonical_recommendation("客胜"), "负")
        self.assertEqual(canonical_recommendation("主胜/平（主队不败）"), "胜/平")
        self.assertEqual(canonical_goal_lean("倾向小球（2.5）"), "小(2.5)")
        self.assertEqual(canonical_btts_lean("双方进球：是"), "双进:是")
        self.assertEqual(canonical_score_hint("2-1"), "比分:2-1")
        self.assertEqual(canonical_score_hint("比分：2-1"), "比分:2-1")

    def test_accuracy_accepts_new_and_historical_copy(self) -> None:
        common = {
            "home_goals": 2,
            "away_goals": 1,
            "score_hint": "比分:2-1",
            "goal_lean": "大(2.5)",
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

    def test_resolve_handicap_prefers_frozen_stored(self) -> None:
        from app.services.prediction import resolve_handicap_bundle

        odds = {
            "available": True,
            "asian_handicap": {"line": -0.5, "home": 1.95, "away": 1.80},
        }
        frozen = "让球负（-0.5）"
        lean, _ = resolve_handicap_bundle(
            odds,
            "胜",
            league_id=253,
            stored=frozen,
            prefer_stored=True,
        )
        # Frozen pick kept; label/paren normalized to the compact display form.
        self.assertEqual(lean, "让负(-0.5)")

    def test_summary_includes_handicap_accuracy(self) -> None:
        summary = summarize_accuracy(
            [
                {"has_prediction": True, "evaluable": True, "handicap_hit": True},
                {"has_prediction": True, "evaluable": True, "handicap_hit": False},
                {"has_prediction": True, "evaluable": True, "handicap_hit": None},
            ]
        )
        self.assertEqual(summary["handicap"], {"hits": 1, "total": 2, "rate": 0.5})

    def test_closed_goal_gates_keep_heuristic_leans(self) -> None:
        """ML OU/BTTS/score gates must not blank already-computed market leans."""
        from unittest.mock import patch

        from app.services.goal_predictor import GoalPrediction
        from app.services.prediction import derive_prediction_leans

        odds = {
            "available": True,
            "match_winner": {"home": 2.1, "draw": 3.3, "away": 3.4},
            "goals_ou": {"line": 2.5, "home": 1.95, "away": 1.85},
            "asian_handicap": {"line": -0.25, "home": 1.9, "away": 1.9},
        }
        probs = {"home": 0.46, "draw": 0.28, "away": 0.26}
        fake = GoalPrediction(
            home_lambda=1.2,
            away_lambda=1.1,
            source="poisson_ml",
            deploy_score=False,
            deploy_ou=False,
            deploy_btts=False,
        )
        with patch("app.services.goal_predictor.predict_goals", return_value=fake):
            leans = derive_prediction_leans(probs, odds, features={"has_odds": 1.0})
        self.assertNotIn("待分析", leans["goal_lean"])
        self.assertNotIn("待分析", leans["both_score_lean"])
        self.assertNotIn("待分析", leans["score_hint"])
        self.assertTrue(leans["goal_lean"].startswith("大") or leans["goal_lean"].startswith("小"))
        self.assertTrue(leans["score_hint"].startswith("比分:"))

    def test_draw_scoreline_for_ou_over_25(self) -> None:
        from app.services.prediction import (
            _align_score_with_ou,
            _draw_scoreline_for_ou,
            _nudge_score_for_ou,
            _score_settles_ou,
            _target_total,
        )

        self.assertEqual(_target_total(2.5, "over"), 3)
        self.assertEqual(_target_total(1.5, "over"), 2)
        self.assertEqual(_target_total(2.5, "under"), 2)
        self.assertEqual(_target_total(3.5, "under"), 3)
        self.assertEqual(_draw_scoreline_for_ou(3, 2.5, "over"), (2, 2))
        self.assertEqual(_draw_scoreline_for_ou(2, 2.5, "under"), (1, 1))
        self.assertFalse(_score_settles_ou(1, 1, 2.5, "over"))
        self.assertTrue(_score_settles_ou(2, 2, 2.5, "over"))
        # 图一：2-1 vs 小 2.5
        self.assertEqual(
            _nudge_score_for_ou(2, 1, line=2.5, side="under", btts_yes=True),
            (2, 0),
        )
        # 图二：1-3 vs 小 3.5
        self.assertEqual(
            _nudge_score_for_ou(1, 3, line=3.5, side="under", btts_yes=True),
            (1, 2),
        )
        # 图三：1-0 vs 大 1.5
        self.assertEqual(
            _nudge_score_for_ou(1, 0, line=1.5, side="over", btts_yes=False),
            (2, 0),
        )
        aligned = _align_score_with_ou(
            [(1, 1), (2, 1)],
            line=2.5,
            ou_side="over",
            btts_yes=True,
        )
        self.assertEqual(aligned, [(2, 2), (2, 1)])

    def test_score_ou_conflicts_from_screenshots(self) -> None:
        """比分总进球必须能结算大小球（覆盖非平局打架）。"""
        from app.services.prediction import _align_score_with_ou, _score_settles_ou

        cases = [
            ([(2, 1)], 2.5, "under", True),
            ([(1, 3)], 3.5, "under", True),
            ([(1, 0)], 1.5, "over", False),
            ([(1, 0), (0, 0)], 1.5, "over", False),
        ]
        for lines, line, side, btts in cases:
            aligned = _align_score_with_ou(
                lines, line=line, ou_side=side, btts_yes=btts
            )
            self.assertTrue(aligned, msg=f"empty align for {lines}")
            for h, a in aligned:
                self.assertTrue(
                    _score_settles_ou(h, a, line, side),
                    msg=f"{h}-{a} fights {side} {line}",
                )

    def test_score_hint_does_not_fight_over_25_on_draw(self) -> None:
        """大（2.5）不得配 1-1；平局参考分至少 2-2。"""
        from unittest.mock import patch

        from app.services.goal_predictor import GoalPrediction
        from app.services.prediction import derive_prediction_leans

        odds = {
            "available": True,
            "match_winner": {"home": 3.2, "draw": 2.9, "away": 2.6},
            "goals_ou": {"line": 2.5, "home": 1.75, "away": 2.05},
            "asian_handicap": {"line": 0.0, "home": 1.9, "away": 1.9},
        }
        # Drawish board; market prefers over 2.5.
        probs = {"home": 0.30, "draw": 0.38, "away": 0.32}
        fake = GoalPrediction(
            home_lambda=1.1,
            away_lambda=1.1,
            source="poisson_ml",
            deploy_score=False,
            deploy_ou=False,
            deploy_btts=False,
        )
        with patch("app.services.goal_predictor.predict_goals", return_value=fake):
            leans = derive_prediction_leans(probs, odds, features={"has_odds": 1.0})
        self.assertTrue(leans["goal_lean"].startswith("大"))
        self.assertIn("2.5", leans["goal_lean"])
        self.assertNotIn("1-1", leans["score_hint"])
        self.assertRegex(leans["score_hint"], r"比分:.*\d+-\d+")
        for part in leans["score_hint"].removeprefix("比分:").split("/"):
            h, a = part.split("-")
            self.assertGreater(int(h) + int(a), 2.5)

if __name__ == "__main__":
    unittest.main()
