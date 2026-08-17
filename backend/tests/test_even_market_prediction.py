"""均势盘（三路都贴近 1/3）不等于「没跑过分析」。

真实案例：阿甲 1493067（2.94 / 2.84 / 2.65，亚盘平手 1.95/1.80）曾整场输出「待分析」。
只放开这一种情形：**有可用 1X2 盘口**时不再置为待分析；缺盘口的场次行为不变。
"""

import unittest

from app.services.prediction import (
    derive_prediction_leans,
    get_recommendation,
    has_1x2_market,
    probabilities_ready,
)

# 真实库里那场的盘口与模型概率
EVEN_ODDS = {
    "available": True,
    "match_winner": {"home": "2.94", "draw": "2.84", "away": "2.65"},
    "asian_handicap": {"line": "0", "home": "1.95", "away": "1.80"},
    "goals_ou": {"line": "1.5", "home": "1.65", "away": "2.20"},
    "both_teams_score": {"home": "2.25", "away": "1.57"},
}
EVEN_PROBS = {"home": 0.318, "draw": 0.3292, "away": 0.3528}

# 只有亚盘、没有 1X2：这才是真的没来源
AH_ONLY_ODDS = {
    "available": True,
    "asian_handicap": {"line": "0", "home": "1.95", "away": "1.80"},
}
FLAT_PROBS = {"home": 1 / 3, "draw": 1 / 3, "away": 1 / 3}


class EvenMarketPredictionTests(unittest.TestCase):
    def test_even_board_counts_as_real_probability_source(self) -> None:
        self.assertTrue(has_1x2_market(EVEN_ODDS))
        self.assertTrue(probabilities_ready(EVEN_PROBS, EVEN_ODDS))
        self.assertTrue(probabilities_ready(FLAT_PROBS, EVEN_ODDS))

    def test_even_board_gets_double_chance_instead_of_pending(self) -> None:
        rec = get_recommendation(EVEN_PROBS, odds=EVEN_ODDS)
        self.assertNotIn("待分析", rec)
        # 胶着盘只给双选，不允许升级成单选。
        self.assertIn(rec, {"胜/平", "负/平", "胜/负"})

        leans = derive_prediction_leans(EVEN_PROBS, EVEN_ODDS)
        for key in ("recommendation", "goal_lean", "both_score_lean", "score_hint"):
            self.assertNotIn("待分析", leans[key], key)
        self.assertNotIn("待分析", leans["handicap_lean"])

    def test_missing_1x2_board_still_pending(self) -> None:
        self.assertFalse(has_1x2_market(AH_ONLY_ODDS))
        self.assertFalse(probabilities_ready(FLAT_PROBS, AH_ONLY_ODDS))
        self.assertEqual(get_recommendation(FLAT_PROBS, odds=AH_ONLY_ODDS), "待分析")
        leans = derive_prediction_leans(FLAT_PROBS, AH_ONLY_ODDS)
        self.assertEqual(leans["goal_lean"], "大小：待分析")
        self.assertEqual(leans["both_score_lean"], "双进:待分析")
        self.assertEqual(leans["score_hint"], "比分:待分析")
        self.assertEqual(leans["handicap_lean"], "让球：待分析")

    def test_no_odds_at_all_still_pending(self) -> None:
        self.assertFalse(probabilities_ready(FLAT_PROBS, None))
        self.assertEqual(get_recommendation(FLAT_PROBS), "待分析")
        leans = derive_prediction_leans(FLAT_PROBS, None)
        self.assertEqual(leans["handicap_lean"], "缺少盘口数据分析")

    def test_normal_boards_keep_previous_output(self) -> None:
        """有边缘的场次不受影响：模型概率仍主导，单选/双选判定不变。"""
        self.assertEqual(get_recommendation({"home": 0.7, "draw": 0.2, "away": 0.1}), "胜")
        self.assertEqual(
            get_recommendation({"home": 0.45, "draw": 0.42, "away": 0.13}), "胜/平"
        )
        favorite_board = {
            "available": True,
            "match_winner": {"home": "1.45", "draw": "4.20", "away": "6.50"},
        }
        rec = get_recommendation(
            {"home": 0.62, "draw": 0.24, "away": 0.14}, odds=favorite_board
        )
        self.assertNotIn("待分析", rec)


if __name__ == "__main__":
    unittest.main()
