"""Daily auto-pick settlement for the 「每日推荐」 accuracy track."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.services.results_accuracy import settle_auto_pick_hit
from app.services.prediction import summarize_accuracy


class AutoPickAccuracyTests(unittest.TestCase):
    def test_1x2_single_lean(self) -> None:
        self.assertTrue(
            settle_auto_pick_hit(
                market="1x2",
                lean="主胜",
                home_goals=2,
                away_goals=1,
            )
        )
        self.assertFalse(
            settle_auto_pick_hit(
                market="1x2",
                lean="主胜",
                home_goals=0,
                away_goals=1,
            )
        )
        # Double-chance tips are rejected from auto picks; do not grade.
        self.assertIsNone(
            settle_auto_pick_hit(
                market="1x2",
                lean="胜/平",
                home_goals=1,
                away_goals=0,
            )
        )

    def test_ah_single_lean(self) -> None:
        self.assertTrue(
            settle_auto_pick_hit(
                market="ah",
                lean="让胜(-0.5)",
                home_goals=2,
                away_goals=1,
                handicap_line=-0.5,
            )
        )
        self.assertFalse(
            settle_auto_pick_hit(
                market="ah",
                lean="让胜(-0.5)",
                home_goals=1,
                away_goals=1,
                handicap_line=-0.5,
            )
        )
        self.assertIsNone(
            settle_auto_pick_hit(
                market="ah",
                lean="让胜(-1)",
                home_goals=2,
                away_goals=1,
                handicap_line=-1.0,
            )
        )
        self.assertFalse(
            settle_auto_pick_hit(
                market="ah",
                lean="让胜(-1)",
                home_goals=2,
                away_goals=1,
                handicap_line=-1.0,
                handicap_ruleset="jc",
            )
        )
        # 让胜 -0.25 at a draw is 输半 — wrong side, not a hit.
        self.assertFalse(
            settle_auto_pick_hit(
                market="ah",
                lean="让胜(-0.25)",
                home_goals=3,
                away_goals=3,
                handicap_line=-0.25,
            )
        )
        self.assertIsNone(
            settle_auto_pick_hit(
                market="ah",
                lean="让胜(0)",
                home_goals=2,
                away_goals=2,
                handicap_line=0.0,
            )
        )

    def test_ou_and_btts(self) -> None:
        self.assertTrue(
            settle_auto_pick_hit(
                market="ou",
                lean="大(2.5)",
                home_goals=2,
                away_goals=1,
            )
        )
        self.assertFalse(
            settle_auto_pick_hit(
                market="ou",
                lean="小(2.5)",
                home_goals=2,
                away_goals=1,
            )
        )
        self.assertTrue(
            settle_auto_pick_hit(
                market="ou",
                lean="大(2.75)",
                home_goals=2,
                away_goals=1,
            )
        )
        # 3 goals vs 2.75: 大 is 赢半, 小 is 输半 — only the over side hits.
        self.assertFalse(
            settle_auto_pick_hit(
                market="ou",
                lean="小(2.75)",
                home_goals=2,
                away_goals=1,
            )
        )
        self.assertIsNone(
            settle_auto_pick_hit(
                market="ou",
                lean="大(3)",
                home_goals=2,
                away_goals=1,
            )
        )
        self.assertTrue(
            settle_auto_pick_hit(
                market="btts",
                lean="双进:是",
                home_goals=1,
                away_goals=1,
            )
        )
        self.assertFalse(
            settle_auto_pick_hit(
                market="btts",
                lean="双进:否",
                home_goals=1,
                away_goals=1,
            )
        )

    def test_score_market_not_graded(self) -> None:
        self.assertIsNone(
            settle_auto_pick_hit(
                market="score",
                lean="比分:2-1",
                home_goals=2,
                away_goals=1,
            )
        )

    def test_summary_uses_auto_pick_key(self) -> None:
        summary = summarize_accuracy(
            [
                {
                    "has_prediction": True,
                    "evaluable": True,
                    "auto_pick_hit": True,
                },
                {
                    "has_prediction": False,
                    "evaluable": True,
                    "auto_pick_hit": False,
                },
                {
                    "has_prediction": True,
                    "evaluable": True,
                    "auto_pick_hit": None,
                },
            ]
        )
        self.assertEqual(summary["auto_pick"], {"hits": 1, "total": 2, "rate": 0.5})
        self.assertNotIn("single_result", summary)

    def test_duck_typed_snapshot_attrs(self) -> None:
        """Favorites path may pass SimpleNamespace(market/lean)."""
        pick = SimpleNamespace(market="1x2", lean="客胜")
        self.assertTrue(
            settle_auto_pick_hit(
                market=pick.market,
                lean=pick.lean,
                home_goals=0,
                away_goals=2,
            )
        )


if __name__ == "__main__":
    unittest.main()
