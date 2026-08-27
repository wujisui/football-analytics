"""Admin single-fixture odds refresh boundaries."""

import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

from app.api.v1.endpoints import fixtures


def test_admin_refresh_accepts_non_hot_prematch_fixture() -> None:
    """Manual detail refresh is scoped by admin + kickoff, not hot leagues."""

    async def _run() -> None:
        fixture = SimpleNamespace(
            id=987,
            league_id=999_999,  # deliberately outside configured hot leagues
            status="pending",
            date=datetime.utcnow() + timedelta(hours=2),
        )
        db = MagicMock()
        db.get = AsyncMock(return_value=fixture)

        fetcher = MagicMock()
        fetcher.refresh_odds_for_fixture = AsyncMock(return_value=True)
        fetcher.last_remaining_requests = 6999
        fetcher.__aenter__ = AsyncMock(return_value=fetcher)
        fetcher.__aexit__ = AsyncMock(return_value=False)

        publish = AsyncMock()
        with (
            patch.object(fixtures, "FootballFetcher", return_value=fetcher),
            patch.object(fixtures, "official_sync_busy", return_value=False),
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
        db.get.assert_not_awaited()

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
