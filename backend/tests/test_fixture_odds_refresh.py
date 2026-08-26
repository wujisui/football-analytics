"""Admin single-fixture odds refresh boundaries."""

import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

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

        with patch.object(fixtures, "FootballFetcher", return_value=fetcher):
            result = await fixtures.refresh_fixture_odds(987, None, db)

        fetcher.refresh_odds_for_fixture.assert_awaited_once_with(987)
        assert result == {
            "fixture_id": 987,
            "updated": True,
            "api_remaining": 6999,
        }

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
