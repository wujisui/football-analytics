"""API-Sports multi-key pool parsing and same-day failover."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services import api_key_pool as pool


class ApiKeyPoolTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        from app.services.runtime_settings import set_runtime_api_sports_keys_blob

        pool._day = None
        pool._active_index = 0
        pool._exhausted = set()
        pool._hydrated = False
        set_runtime_api_sports_keys_blob(None)

    def test_mask_hides_secret_body(self) -> None:
        masked = pool.mask_api_sports_keys_blob("abcdefghij,klmnopqrst")
        self.assertEqual(masked, "…ghij,…qrst")
        self.assertNotIn("abcdef", masked)

    def test_official_keys_only_use_admin_db_blob(self) -> None:
        from app.services.runtime_settings import set_runtime_api_sports_keys_blob

        settings = MagicMock()
        settings.API_SPORTS_KEY = "legacy-env-key"
        settings.SCHEDULER_TIMEZONE = "Asia/Shanghai"
        self.assertEqual(pool.official_keys(settings), [])

        set_runtime_api_sports_keys_blob("db-key-one,db-key-two")
        try:
            self.assertEqual(
                pool.official_keys(settings),
                ["db-key-one", "db-key-two"],
            )
        finally:
            set_runtime_api_sports_keys_blob(None)

    def test_active_key_skips_exhausted(self) -> None:
        from app.services.runtime_settings import set_runtime_api_sports_keys_blob

        settings = MagicMock()
        settings.SCHEDULER_TIMEZONE = "Asia/Shanghai"
        set_runtime_api_sports_keys_blob("key-one,key-two")
        pool._day = pool._scheduler_day(settings)
        pool._exhausted = {0}
        pool._active_index = 0
        pool._hydrated = True
        self.assertEqual(pool.active_official_key(settings), "key-two")

    async def test_rotate_marks_exhausted_and_switches(self) -> None:
        from app.services.runtime_settings import set_runtime_api_sports_keys_blob

        settings = MagicMock()
        settings.SCHEDULER_TIMEZONE = "Asia/Shanghai"
        set_runtime_api_sports_keys_blob("key-one,key-two")
        pool._day = pool._scheduler_day(settings)
        pool._active_index = 0
        pool._exhausted = set()
        pool._hydrated = True

        with (
            patch.object(pool, "hydrate_key_pool", AsyncMock(return_value=None)),
            patch.object(pool, "_persist_state", AsyncMock()),
        ):
            nxt = await pool.mark_active_exhausted_and_rotate(
                None, settings, reason="test"
            )

        self.assertEqual(nxt, "key-two")
        self.assertEqual(pool._active_index, 1)
        self.assertEqual(pool._exhausted, {0})

    async def test_rotate_returns_none_when_all_exhausted(self) -> None:
        from app.services.runtime_settings import set_runtime_api_sports_keys_blob

        settings = MagicMock()
        settings.SCHEDULER_TIMEZONE = "Asia/Shanghai"
        set_runtime_api_sports_keys_blob("key-one,key-two")
        pool._day = pool._scheduler_day(settings)
        pool._active_index = 1
        pool._exhausted = {0}
        pool._hydrated = True

        with (
            patch.object(pool, "hydrate_key_pool", AsyncMock(return_value=None)),
            patch.object(pool, "_persist_state", AsyncMock()),
        ):
            nxt = await pool.mark_active_exhausted_and_rotate(
                None, settings, reason="test"
            )

        self.assertIsNone(nxt)
        self.assertEqual(pool._exhausted, {0, 1})


if __name__ == "__main__":
    unittest.main()
