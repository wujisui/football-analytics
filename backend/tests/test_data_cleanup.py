import unittest
from datetime import datetime
from types import SimpleNamespace

from app.services.data_cleanup import (
    record_has_algorithm_recommendation,
    should_prune_terminal_fixture,
)


def _fixture(status: str = "finished"):
    return SimpleNamespace(status=status, date=datetime(2026, 7, 25, 12, 0, 0))


class PruneJudgmentTests(unittest.TestCase):
    def test_flat_probs_alone_do_not_keep_finished_fixture(self) -> None:
        stored = SimpleNamespace(
            recommendation="待分析",
            score_hint="比分:待分析",
            goal_lean="大小：待分析",
            both_score_lean="双进:待分析",
            handicap_lean="让球：待分析",
            home_win_prob=1 / 3,
            draw_prob=1 / 3,
            away_win_prob=1 / 3,
            odds_json=None,
            odds_opening_json=None,
        )
        feature = SimpleNamespace(
            features_json='{"has_odds": 0}',
            home_win_prob=1 / 3,
            draw_prob=1 / 3,
            away_win_prob=1 / 3,
        )
        self.assertFalse(record_has_algorithm_recommendation(stored, feature))
        self.assertTrue(should_prune_terminal_fixture(_fixture(), stored, feature))

    def test_real_recommendation_keeps_fixture(self) -> None:
        stored = SimpleNamespace(
            recommendation="胜",
            score_hint="比分:2-1",
            goal_lean="大（2.5）",
            both_score_lean="双进:是",
            handicap_lean="让球胜（-0.5）",
            home_win_prob=0.48,
            draw_prob=0.27,
            away_win_prob=0.25,
            odds_json=None,
            odds_opening_json=None,
        )
        self.assertTrue(record_has_algorithm_recommendation(stored, None))
        self.assertFalse(should_prune_terminal_fixture(_fixture(), stored, None))

    def test_pending_never_pruned(self) -> None:
        self.assertFalse(
            should_prune_terminal_fixture(_fixture(status="pending"), None, None)
        )


if __name__ == "__main__":
    unittest.main()
