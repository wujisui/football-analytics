"""Subscription schedule and rolling fixture-window helpers."""

import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.fixtures_sync import sync_dates
from app.tasks.scheduler import (
    FULL_SYNC_HOUR,
    SUBSCRIBED_EARLY_ODDS_HOURS,
    SUBSCRIBED_FIRST_ODDS_MINUTE,
    SUBSCRIBED_ODDS_HOURS,
    UNSUBSCRIBED_ODDS_HOURS,
    register_jobs,
    scheduler,
)


def test_subscription_schedule_constants() -> None:
    assert FULL_SYNC_HOUR == 11
    assert SUBSCRIBED_FIRST_ODDS_MINUTE == 55
    assert SUBSCRIBED_ODDS_HOURS == (0, 2, 14, 16, 18, 20, 22)
    assert SUBSCRIBED_EARLY_ODDS_HOURS == (4, 6, 8, 10)
    assert UNSUBSCRIBED_ODDS_HOURS == (22,)


def test_unsubscribed_full_batch_dates() -> None:
    today = date(2026, 8, 17)
    fixture_days, result_days = sync_dates(
        today,
        lookahead_days=8,
        free_quota=True,
    )
    assert fixture_days == [today]
    assert result_days == [date(2026, 8, 16)]


def test_subscribed_window_and_result_lookback() -> None:
    today = date(2026, 8, 17)
    fixture_days, result_days = sync_dates(
        today,
        lookahead_days=8,
        free_quota=False,
    )
    assert fixture_days == [date(2026, 8, 17 + offset) for offset in range(8)]
    assert result_days == [
        date(2026, 8, 14),
        date(2026, 8, 15),
        date(2026, 8, 16),
        date(2026, 8, 17),
    ]


def test_registered_subscription_jobs_respect_early_switch() -> None:
    register_jobs(subscribed=True, early_odds=False)
    job_ids = {str(job.id) for job in scheduler.get_jobs()}
    assert "scheduled_fixtures_sync_11" in job_ids
    assert "scheduled_fixtures_sync_odds_1155" in job_ids
    assert "scheduled_fixtures_sync_odds_02" in job_ids
    assert "scheduled_fixtures_sync_odds_04" not in job_ids
    assert "free_quota_fixture_rollover" not in job_ids

    register_jobs(subscribed=True, early_odds=True)
    job_ids = {str(job.id) for job in scheduler.get_jobs()}
    assert "scheduled_fixtures_sync_odds_04" in job_ids
    assert "scheduled_fixtures_sync_odds_10" in job_ids

    register_jobs(subscribed=False)
    job_ids = {str(job.id) for job in scheduler.get_jobs()}
    assert "scheduled_fixtures_sync_odds_22" in job_ids
    assert "scheduled_fixtures_sync_odds_02" not in job_ids
    assert "free_quota_fixture_rollover" in job_ids


def test_subscribed_full_batch_only_fetches_missing_future_days() -> None:
    from app.services import fixtures_sync as fs

    fetcher = MagicMock()
    fetcher.quota_exhausted = False
    fetcher.capture_finished_results = AsyncMock(return_value=8)
    fetcher.fetch_fixtures_for_date = AsyncMock(return_value=12)
    fetcher.sync_odds_for_dates = AsyncMock(side_effect=[3, 5])
    fetcher.__aenter__ = AsyncMock(return_value=fetcher)
    fetcher.__aexit__ = AsyncMock(return_value=False)
    settings = MagicMock(
        SCHEDULER_TIMEZONE="Asia/Shanghai",
        FIXTURES_LOOKAHEAD_DAYS=8,
    )
    standings = AsyncMock(
        return_value={"leagues": 1, "fetched": 1, "skipped": 0, "failed": 0}
    )
    missing = AsyncMock(return_value=[date(2026, 8, 31)])
    detail = AsyncMock(return_value={"enriched": 2})

    async def _run() -> dict:
        with (
            patch.object(fs, "FootballFetcher", return_value=fetcher),
            patch.object(fs, "get_settings", return_value=settings),
            patch.object(
                fs, "get_enable_free_quota", AsyncMock(return_value=(False, "db"))
            ),
            patch.object(
                fs, "get_hot_league_ids", AsyncMock(return_value=([39], "db"))
            ),
            patch.object(fs, "missing_subscribed_fixture_days", missing),
            patch.object(fs, "sync_league_standings_for_dates", standings),
            patch.object(fs, "importlib", MagicMock()),
            patch(
                "app.services.scheduled_detail_enrich.run_scheduled_full_detail_enrich",
                detail,
            ),
            patch(
                "app.services.auto_favorites.sync_daily_auto_favorites",
                AsyncMock(return_value={"selected": []}),
            ),
            patch("app.core.database.AsyncSessionLocal"),
        ):
            return await fs.scheduled_fixtures_sync(mode="full")

    try:
        result = asyncio.run(_run())
        assert result["status"] == "completed"
        fetcher.fetch_fixtures_for_date.assert_awaited_once_with(
            date(2026, 8, 31),
            force=True,
            league_ids=None,
        )
        assert fetcher.sync_odds_for_dates.await_count == 2
        tomorrow_call, today_call = fetcher.sync_odds_for_dates.await_args_list
        assert tomorrow_call.kwargs["refresh_existing"] is False
        assert tomorrow_call.kwargs["set_opening"] is True
        assert today_call.kwargs["refresh_existing"] is True
        assert today_call.kwargs["set_opening"] is True
        detail.assert_awaited_once()
    finally:
        asyncio.set_event_loop(asyncio.new_event_loop())


def test_light_batch_only_refreshes_today_odds() -> None:
    from app.services import fixtures_sync as fs

    fetcher = MagicMock()
    fetcher.quota_exhausted = False
    fetcher.capture_finished_results = AsyncMock()
    fetcher.fetch_fixtures_for_date = AsyncMock()
    fetcher.sync_odds_for_dates = AsyncMock(return_value=4)
    fetcher.__aenter__ = AsyncMock(return_value=fetcher)
    fetcher.__aexit__ = AsyncMock(return_value=False)
    settings = MagicMock(
        SCHEDULER_TIMEZONE="Asia/Shanghai",
        FIXTURES_LOOKAHEAD_DAYS=8,
    )

    async def _run() -> dict:
        with (
            patch.object(fs, "FootballFetcher", return_value=fetcher),
            patch.object(fs, "get_settings", return_value=settings),
            patch.object(
                fs, "get_enable_free_quota", AsyncMock(return_value=(False, "db"))
            ),
            patch.object(
                fs, "get_hot_league_ids", AsyncMock(return_value=([39], "db"))
            ),
            patch(
                "app.services.auto_favorites.sync_daily_auto_favorites",
                AsyncMock(return_value={"selected": []}),
            ),
            patch("app.core.database.AsyncSessionLocal"),
        ):
            return await fs.scheduled_fixtures_sync(mode="odds")

    try:
        result = asyncio.run(_run())
        assert result["odds_updated"] == 4
        fetcher.capture_finished_results.assert_not_awaited()
        fetcher.fetch_fixtures_for_date.assert_not_awaited()
        fetcher.sync_odds_for_dates.assert_awaited_once()
        assert fetcher.sync_odds_for_dates.await_args.kwargs["refresh_existing"] is True
        assert fetcher.sync_odds_for_dates.await_args.kwargs["set_opening"] is False
    finally:
        asyncio.set_event_loop(asyncio.new_event_loop())
