"""Admin single-fixture odds refresh boundaries."""

import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

from app.api.v1.endpoints import fixtures


def test_admin_refresh_accepts_today_catalog_prematch_fixture() -> None:
    """Manual detail refresh uses the same today/catalog boundary as 【比赛】."""

    async def _run() -> None:
        fixture = SimpleNamespace(
            id=987,
            league_id=999_999,  # deliberately outside configured hot leagues
            status="pending",
            date=datetime.utcnow() + timedelta(hours=2),
        )
        db = MagicMock()
        query_result = MagicMock()
        query_result.scalar_one_or_none.return_value = fixture
        db.execute = AsyncMock(return_value=query_result)

        fetcher = MagicMock()
        fetcher.refresh_odds_for_fixture = AsyncMock(return_value=True)
        fetcher.last_remaining_requests = 6999
        fetcher.__aenter__ = AsyncMock(return_value=fetcher)
        fetcher.__aexit__ = AsyncMock(return_value=False)

        publish = AsyncMock()
        with (
            patch.object(fixtures, "FootballFetcher", return_value=fetcher),
            patch.object(fixtures, "official_sync_busy", return_value=False),
            patch.object(
                fixtures, "current_prematch_match_day", AsyncMock(return_value="2026-08-30")
            ),
            patch.object(
                fixtures, "allowed_league_ids", AsyncMock(return_value={39})
            ),
            patch.object(fixtures, "_odds_refresh_allowed", return_value=True),
            patch.object(fixtures, "touch_client_data_revision", publish),
        ):
            result = await fixtures.refresh_fixture_odds(987, None, db)

        fetcher.refresh_odds_for_fixture.assert_awaited_once_with(987)
        publish.assert_awaited_once_with(db)
        assert result == {
            "fixture_id": 987,
            "updated": True,
            "api_remaining": 6999,
        }

    asyncio.run(_run())


def test_admin_refresh_rejects_while_official_batch_is_running() -> None:
    async def _run() -> None:
        db = MagicMock()
        db.get = AsyncMock()
        with patch.object(fixtures, "official_sync_busy", return_value=True):
            try:
                await fixtures.refresh_fixture_odds(987, None, db)
            except HTTPException as exc:
                assert exc.status_code == 409
                assert exc.detail == "后台官方同步正在执行，本次盘口未更新，请稍后再试"
            else:
                raise AssertionError("Expected busy refresh to return HTTP 409")
        db.execute.assert_not_called()

    asyncio.run(_run())


def test_odds_refresh_route_requires_admin_dependency() -> None:
    route = next(
        route
        for route in fixtures.router.routes
        if getattr(route, "path", "") == "/fixtures/{fixture_id}/odds/refresh"
    )
    dependency_calls = {
        dependency.call
        for dependency in route.dependant.dependencies
    }

    assert fixtures.require_admin in dependency_calls
