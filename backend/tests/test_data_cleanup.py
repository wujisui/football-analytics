import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace

import json

from app.services.data_cleanup import should_prune_terminal_fixture

NOW = datetime(2026, 7, 26, 12, 0, 0)


def _fixture(
    status: str = "finished",
    *,
    date: datetime | None = None,
    home_goals: int | None = 2,
    away_goals: int | None = 1,
):
    return SimpleNamespace(
        status=status,
        date=date or datetime(2026, 7, 25, 12, 0, 0),
        home_goals=home_goals,
        away_goals=away_goals,
    )


def _analyzed_stored(*, board: bool = False):
    """Complete frozen prediction; ``board`` decides whether it had any basis."""
    odds = (
        json.dumps(
            {
                "available": True,
                "match_winner": {"home": "2.10", "draw": "3.30", "away": "3.40"},
            }
        )
        if board
        else None
    )
    return SimpleNamespace(
        recommendation="胜",
        score_hint="比分:2-1",
        goal_lean="大（2.5）",
        both_score_lean="双进:是",
        handicap_lean="让球胜（-0.5）",
        home_win_prob=0.48,
        draw_prob=0.27,
        away_win_prob=0.25,
        odds_json=odds,
        odds_opening_json=None,
    )


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
        self.assertTrue(should_prune_terminal_fixture(_fixture(), stored, feature))

    def test_prediction_without_board_is_pruned(self) -> None:
        """有预测但没赛前盘口 = 无依据预测，物理删除，不进历史统计。"""
        self.assertTrue(
            should_prune_terminal_fixture(_fixture(), _analyzed_stored(), None)
        )

    def test_prediction_with_board_keeps_fixture(self) -> None:
        self.assertFalse(
            should_prune_terminal_fixture(
                _fixture(), _analyzed_stored(board=True), None
            )
        )

    def test_board_only_from_feature_keeps_fixture(self) -> None:
        """盘口凭证也可以来自冻结特征（has_odds=1）。"""
        feature = SimpleNamespace(features_json='{"has_odds": 1}')
        self.assertFalse(should_prune_terminal_fixture(_fixture(), None, feature))

    def test_pending_never_pruned(self) -> None:
        self.assertFalse(
            should_prune_terminal_fixture(_fixture(status="pending"), None, None)
        )

    def test_cancelled_pruned_even_with_full_prematch(self) -> None:
        """No full-time score will ever arrive, so the prediction can't be graded."""
        self.assertTrue(
            should_prune_terminal_fixture(
                _fixture(status="cancelled", home_goals=None, away_goals=None),
                _analyzed_stored(board=True),
                None,
                now=NOW,
            )
        )

    def test_finished_without_score_pruned_even_with_full_prematch(self) -> None:
        self.assertTrue(
            should_prune_terminal_fixture(
                _fixture(home_goals=None, away_goals=None),
                _analyzed_stored(board=True),
                None,
                now=NOW,
            )
        )

    def test_stale_postponed_pruned_but_fresh_one_kept(self) -> None:
        """Fresh postponed rows still show as upcoming; stale ones are dead weight."""
        stored = _analyzed_stored(board=True)
        fresh = _fixture(
            status="postponed",
            date=NOW - timedelta(hours=2),
            home_goals=None,
            away_goals=None,
        )
        stale = _fixture(
            status="postponed",
            date=NOW - timedelta(days=3),
            home_goals=None,
            away_goals=None,
        )
        self.assertFalse(should_prune_terminal_fixture(fresh, stored, None, now=NOW))
        self.assertTrue(should_prune_terminal_fixture(stale, stored, None, now=NOW))
        # 刚延期且还没开盘也留着：盘口常常临近开赛才开。
        self.assertFalse(should_prune_terminal_fixture(fresh, None, None, now=NOW))


if __name__ == "__main__":
    unittest.main()
