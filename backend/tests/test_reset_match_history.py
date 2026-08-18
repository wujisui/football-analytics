"""reset-match-history keeps accounts/catalog; dry-run must not mutate."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.data_cleanup import _RESET_MATCH_HISTORY_KEPT, reset_match_history


class ResetMatchHistoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_dry_run_counts_without_commit(self) -> None:
        session = AsyncMock()
        session.scalar = AsyncMock(side_effect=[3, 2, 4, 1, 5, 0, 7])
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )
        session.commit = AsyncMock()

        model_dir = MagicMock()
        model_dir.is_dir.return_value = False

        with patch("app.core.config.BACKEND_ROOT") as root:
            root.__truediv__ = lambda _self, _other: model_dir
            report = await reset_match_history(session, apply=False)

        self.assertFalse(report.apply)
        self.assertEqual(report.fixtures, 3)
        self.assertEqual(report.match_features, 4)
        self.assertEqual(report.kept, _RESET_MATCH_HISTORY_KEPT)
        session.commit.assert_not_awaited()

    async def test_apply_clears_cache_pattern(self) -> None:
        session = AsyncMock()
        session.scalar = AsyncMock(side_effect=[1, 1, 1, 1, 1, 1, 1])
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )
        session.commit = AsyncMock()

        cache = MagicMock()
        cache.clear_pattern = AsyncMock(return_value=0)
        model_dir = MagicMock()
        model_dir.is_dir.return_value = False

        with (
            patch("app.core.config.BACKEND_ROOT") as root,
            patch(
                "app.services.data_cleanup.get_cache_service",
                return_value=cache,
            ),
        ):
            root.__truediv__ = lambda _self, _other: model_dir
            report = await reset_match_history(session, apply=True)

        self.assertTrue(report.apply)
        self.assertTrue(report.cache_cleared)
        session.commit.assert_awaited()
        cache.clear_pattern.assert_awaited_once_with("api:football:*")


if __name__ == "__main__":
    unittest.main()
