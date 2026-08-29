"""Subscription schedule and rolling fixture-window helpers."""

import asyncio
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.fixtures_sync import sync_dates
from app.tasks.scheduler import (
    FULL_SYNC_HOUR,
    RESULTS_SYNC_HOUR,
    RESULTS_SYNC_JOB_ID,
    SUBSCRIBED_DEFAULT_ODDS_SLOTS,
    SUBSCRIBED_DENSE_ODDS_SLOTS,
    SUBSCRIBED_EARLY_ODDS_HOURS,
    UNSUBSCRIBED_ODDS_HOURS,
    odds_job_id,
    register_jobs,
    scheduler,
)


def test_subscription_schedule_constants() -> None:
    assert FULL_SYNC_HOUR == 11
    assert RESULTS_SYNC_HOUR == 7
    assert RESULTS_SYNC_JOB_ID == "scheduled_results_sync_07"
    assert SUBSCRIBED_EARLY_ODDS_HOURS == (4, 6, 8, 10)
    assert SUBSCRIBED_DEFAULT_ODDS_SLOTS == (
        (2, 0), (11, 55), (14, 0), (16, 0), (18, 0), (20, 0),
        (21, 0), (21, 30), (22, 0), (22, 30), (23, 0), (23, 30), (0, 0),
    )
    assert UNSUBSCRIBED_ODDS_HOURS == (22,)
    assert SUBSCRIBED_DENSE_ODDS_SLOTS[:5] == (
        (2, 0), (11, 55), (14, 0), (16, 0), (16, 55),
    )
    assert SUBSCRIBED_DENSE_ODDS_SLOTS[-1] == (1, 55)
    assert len(SUBSCRIBED_DENSE_ODDS_SLOTS) == 23
    assert odds_job_id(21, 30) == "scheduled_fixtures_sync_odds_2130"
    assert odds_job_id(16, 55) == "scheduled_fixtures_sync_odds_1655"
    assert odds_job_id(0) == "scheduled_fixtures_sync_odds_00"


def test_unsubscribed_full_batch_dates() -> None:
    today = date(2026, 8, 17)
    fixture_days, result_days = sync_dates(
        today,
        lookahead_days=8,
        free_quota=True,
    )
    assert fixture_days == [today]
    assert result_days == [date(2026, 8, 16), today]


def test_result_days_are_yesterday_and_today() -> None:
    from app.services.fixtures_sync import result_days_for_batch

    today = date(2026, 8, 17)
    assert result_days_for_batch(today) == [date(2026, 8, 16), today]


def test_subscribed_window_and_result_lookback() -> None:
    today = date(2026, 8, 17)
    fixture_days, result_days = sync_dates(
        today,
        lookahead_days=8,
        free_quota=False,
    )
    assert fixture_days == [date(2026, 8, 17 + offset) for offset in range(8)]
    assert result_days == [date(2026, 8, 16), date(2026, 8, 17)]


def test_registered_subscription_jobs_respect_early_switch() -> None:
    register_jobs(subscribed=True, early_odds=False)
    job_ids = {str(job.id) for job in scheduler.get_jobs()}
    assert "scheduled_fixtures_sync_11" in job_ids
    assert RESULTS_SYNC_JOB_ID in job_ids
    assert "scheduled_fixtures_sync_odds_1155" in job_ids
    assert "scheduled_fixtures_sync_odds_02" in job_ids
    assert "scheduled_fixtures_sync_odds_04" not in job_ids
    assert "scheduled_fixtures_sync_odds_2130" in job_ids
    assert "scheduled_fixtures_sync_odds_22" in job_ids
    assert "scheduled_fixtures_sync_odds_2330" in job_ids
    assert "scheduled_fixtures_sync_odds_00" in job_ids
    assert "free_quota_fixture_rollover" not in job_ids

    register_jobs(subscribed=True, early_odds=True)
    job_ids = {str(job.id) for job in scheduler.get_jobs()}
    assert "scheduled_fixtures_sync_odds_04" in job_ids
    assert "scheduled_fixtures_sync_odds_10" in job_ids
    assert "scheduled_fixtures_sync_odds_2130" in job_ids

    register_jobs(subscribed=False)
    job_ids = {str(job.id) for job in scheduler.get_jobs()}
    assert RESULTS_SYNC_JOB_ID in job_ids
    assert "scheduled_fixtures_sync_odds_22" in job_ids
    assert "scheduled_fixtures_sync_odds_02" not in job_ids
    assert "scheduled_fixtures_sync_odds_2130" not in job_ids
    assert "scheduled_fixtures_sync_odds_00" not in job_ids
    assert "free_quota_fixture_rollover" in job_ids


def test_registered_subscription_jobs_respect_dense_switch() -> None:
    register_jobs(subscribed=True, early_odds=False, dense_odds=True)
    job_ids = {str(job.id) for job in scheduler.get_jobs()}
    assert "scheduled_fixtures_sync_11" in job_ids
    assert RESULTS_SYNC_JOB_ID in job_ids
    assert "scheduled_fixtures_sync_odds_1155" in job_ids
    assert "scheduled_fixtures_sync_odds_02" in job_ids
    assert "scheduled_fixtures_sync_odds_14" in job_ids
    assert "scheduled_fixtures_sync_odds_16" in job_ids
    assert "scheduled_fixtures_sync_odds_1655" in job_ids
    assert "scheduled_fixtures_sync_odds_1725" in job_ids
    assert "scheduled_fixtures_sync_odds_0155" in job_ids
    assert "scheduled_fixtures_sync_odds_18" not in job_ids
    assert "scheduled_fixtures_sync_odds_20" not in job_ids
    assert "scheduled_fixtures_sync_odds_2130" not in job_ids
    assert "scheduled_fixtures_sync_odds_22" not in job_ids
    assert "scheduled_fixtures_sync_odds_00" not in job_ids

    register_jobs(subscribed=True, early_odds=True, dense_odds=True)
    job_ids = {str(job.id) for job in scheduler.get_jobs()}
    assert "scheduled_fixtures_sync_odds_04" in job_ids
    assert "scheduled_fixtures_sync_odds_1655" in job_ids
    assert "scheduled_fixtures_sync_odds_18" not in job_ids


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
        future_call, today_call = fetcher.sync_odds_for_dates.await_args_list
        future_days = future_call.args[0]
        assert len(future_days) == fs.FULL_BATCH_FUTURE_ODDS_DAYS
        assert future_days[0] + timedelta(days=2) == future_days[-1]
        assert future_call.kwargs["refresh_existing"] is False
        assert future_call.kwargs["set_opening"] is True
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


def test_prematch_odds_batch_only_refreshes_explicit_fixture_ids() -> None:
    from app.services import fixtures_sync as fs

    fetcher = MagicMock()
    fetcher.quota_exhausted = False
    fetcher.capture_finished_results = AsyncMock()
    fetcher.fetch_fixtures_for_date = AsyncMock()
    fetcher.sync_odds_for_dates = AsyncMock()
    fetcher.sync_odds_for_prematch_fixtures = AsyncMock(
        return_value={
            "candidates": 3,
            "attempted": 3,
            "updated": 2,
            "truncated": 0,
        }
    )
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
                fs, "get_enable_free_quota", AsyncMock(return_value=(True, "db"))
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
            return await fs.scheduled_fixtures_sync(
                mode="prematch_odds",
                fixture_ids=[101, 102, 103],
            )

    try:
        result = asyncio.run(_run())
        assert result["odds_updated"] == 2
        assert result["prematch_odds"]["attempted"] == 3
        fetcher.sync_odds_for_prematch_fixtures.assert_awaited_once_with(
            [101, 102, 103]
        )
        fetcher.capture_finished_results.assert_not_awaited()
        fetcher.fetch_fixtures_for_date.assert_not_awaited()
        fetcher.sync_odds_for_dates.assert_not_awaited()
    finally:
        asyncio.set_event_loop(asyncio.new_event_loop())


def test_client_data_revision_is_persisted_after_batch_mutation() -> None:
    from app.services import runtime_settings

    row = MagicMock(value="old")
    session = AsyncMock()

    async def _run() -> str:
        with (
            patch.object(
                runtime_settings,
                "get_setting_row",
                AsyncMock(return_value=row),
            ),
            patch.object(runtime_settings.time, "time_ns", return_value=123456),
        ):
            return await runtime_settings.touch_client_data_revision(session)

    revision = asyncio.run(_run())
    assert revision == "123456"
    assert row.value == revision
    session.commit.assert_awaited_once()


def test_results_batch_only_captures_scores() -> None:
    from app.services import fixtures_sync as fs

    fetcher = MagicMock()
    fetcher.quota_exhausted = False
    fetcher.capture_finished_results = AsyncMock(return_value=6)
    fetcher.fetch_fixtures_for_date = AsyncMock()
    fetcher.sync_odds_for_dates = AsyncMock()
    fetcher.__aenter__ = AsyncMock(return_value=fetcher)
    fetcher.__aexit__ = AsyncMock(return_value=False)
    settings = MagicMock(
        SCHEDULER_TIMEZONE="Asia/Shanghai",
        FIXTURES_LOOKAHEAD_DAYS=8,
    )
    auto_fav = AsyncMock(return_value={"selected": []})

    async def _run() -> dict:
        with (
            patch.object(fs, "FootballFetcher", return_value=fetcher),
            patch.object(fs, "get_settings", return_value=settings),
            patch.object(
                fs, "get_enable_free_quota", AsyncMock(return_value=(True, "db"))
            ),
            patch.object(
                fs, "get_hot_league_ids", AsyncMock(return_value=([39], "db"))
            ),
            patch(
                "app.services.auto_favorites.sync_daily_auto_favorites",
                auto_fav,
            ),
            patch("app.core.database.AsyncSessionLocal"),
        ):
            return await fs.scheduled_fixtures_sync(mode="results")

    try:
        result = asyncio.run(_run())
        assert result["status"] == "completed"
        assert result["mode"] == "results"
        assert result["results_saved"] == 6
        assert result["odds_updated"] == 0
        fetcher.capture_finished_results.assert_awaited_once()
        on_days = fetcher.capture_finished_results.await_args.kwargs["on_days"]
        assert len(on_days) == 2
        fetcher.fetch_fixtures_for_date.assert_not_awaited()
        fetcher.sync_odds_for_dates.assert_not_awaited()
        auto_fav.assert_not_awaited()
    finally:
        asyncio.set_event_loop(asyncio.new_event_loop())
