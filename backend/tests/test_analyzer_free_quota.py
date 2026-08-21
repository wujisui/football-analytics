"""Free-quota detail clicks must never amplify official API usage."""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.services.analyzer import AnalyzerService


def test_free_quota_detail_without_stored_package_is_local_only() -> None:
    async def _run() -> None:
        service = AnalyzerService(AsyncMock())
        service.cache = SimpleNamespace(get=AsyncMock(return_value=None))
        fixture = SimpleNamespace(
            id=1001,
            league_id=39,
            home_team_id=10,
            away_team_id=20,
            date=datetime.now(timezone.utc).replace(tzinfo=None)
            + timedelta(hours=4),
            status="pending",
            home_team=SimpleNamespace(name="Arsenal"),
            away_team=SimpleNamespace(name="Chelsea"),
            league=SimpleNamespace(name="英超", season="2026"),
        )
        service._load_fixture = AsyncMock(return_value=fixture)
        service._get_stored_pre_match_row = AsyncMock(return_value=None)
        service._try_serve_after_early_odds = AsyncMock()
        service._collect_prematch_package = AsyncMock()

        with (
            patch(
                "app.services.analyzer.get_enable_free_quota",
                AsyncMock(return_value=(True, "db")),
            ),
            patch("app.services.analyzer.FootballFetcher") as fetcher,
        ):
            result = await service.analyze_fixture(fixture.id)

        assert result.data_source == "database"
        assert result.recommendation == "待分析"
        assert result.package is not None
        assert result.package["odds"]["available"] is False
        fetcher.assert_not_called()
        service._try_serve_after_early_odds.assert_not_called()
        service._collect_prematch_package.assert_not_called()

    asyncio.run(_run())
