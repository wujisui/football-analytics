"""Free-quota schedule helpers and runtime setting defaults."""

from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

from app.tasks.scheduler import (
    FREE_QUOTA_SYNC_HOUR,
    SYNC_HOURS_FREE_QUOTA,
    SYNC_HOURS_FULL,
    free_quota_catch_up_due,
    register_jobs,
    scheduler,
)
from app.services.fixtures_sync import sync_dates


def test_sync_hour_constants() -> None:
    assert SYNC_HOURS_FREE_QUOTA == (11, 22)
    assert FREE_QUOTA_SYNC_HOUR == 11
    assert SYNC_HOURS_FULL == (0, 6, 11, 16, 19, 22)


def test_free_quota_syncs_only_yesterday_results_and_today_fixtures() -> None:
    today = date(2026, 8, 17)
    fixture_days, result_days = sync_dates(
        today,
        lookahead_days=8,
        free_quota=True,
    )
    assert fixture_days == [today]
    assert result_days == [date(2026, 8, 16)]


def test_full_schedule_retains_configured_future_window() -> None:
    today = date(2026, 8, 17)
    fixture_days, result_days = sync_dates(
        today,
        lookahead_days=3,
        free_quota=False,
    )
    assert fixture_days == [
        date(2026, 8, 17),
        date(2026, 8, 18),
        date(2026, 8, 19),
    ]
    assert result_days == [
        date(2026, 8, 14),
        date(2026, 8, 15),
        date(2026, 8, 16),
        date(2026, 8, 17),
    ]


def test_free_quota_skips_standings_but_full_keeps_them() -> None:
    """Free-quota batch must not spend quota on 积分榜 before odds finish."""
    import asyncio

    from app.services import fixtures_sync as fs

    async def _run(free_quota: bool) -> MagicMock:
        fetcher = MagicMock()
        fetcher.quota_exhausted = False
        fetcher.capture_finished_results = AsyncMock(return_value=0)
        fetcher.fetch_fixtures_window = AsyncMock(return_value=0)
        fetcher.sync_odds_for_dates = AsyncMock(return_value=None)
        fetcher.__aenter__ = AsyncMock(return_value=fetcher)
        fetcher.__aexit__ = AsyncMock(return_value=False)

        standings = AsyncMock(
            return_value={"leagues": 0, "fetched": 0, "skipped": 0, "failed": 0}
        )
        settings = MagicMock()
        settings.SCHEDULER_TIMEZONE = "Asia/Shanghai"
        settings.FIXTURES_LOOKAHEAD_DAYS = 8
        settings.LEAGUE_IDS = {"英超": 39}
        settings.uses_full_history = True

        with (
            patch.object(fs, "FootballFetcher", return_value=fetcher),
            patch.object(fs, "sync_league_standings_for_dates", standings),
            patch.object(fs, "get_settings", return_value=settings),
            patch.object(
                fs, "get_enable_free_quota", AsyncMock(return_value=(free_quota, "db"))
            ),
            patch.object(
                fs,
                "get_enable_scheduled_full_detail",
                AsyncMock(return_value=(False, "env")),
            ),
            patch.object(fs, "clip_fixture_dates_for_plan", lambda days, today: days),
            patch.object(fs, "importlib", MagicMock()),
            patch(
                "app.services.auto_favorites.sync_daily_auto_favorites",
                AsyncMock(return_value={"selected": []}),
            ),
            patch("app.core.database.AsyncSessionLocal"),
        ):
            await fs.scheduled_fixtures_sync(sync_hour=11)
        return standings

    try:
        standings_free = asyncio.run(_run(True))
        standings_free.assert_not_called()

        standings_full = asyncio.run(_run(False))
        standings_full.assert_called_once()
    finally:
        # asyncio.run leaves the thread without a current loop; APScheduler's
        # legacy get_event_loop() in later tests needs one to exist.
        asyncio.set_event_loop(asyncio.new_event_loop())


def test_free_quota_evening_only_refreshes_odds() -> None:
    """22:00 free slot skips results/fixtures/standings; odds + auto picks only."""
    import asyncio

    from app.services import fixtures_sync as fs
    from app.services.api_quota import FREE_QUOTA_EVENING_ODDS_BUDGET

    async def _run() -> MagicMock:
        fetcher = MagicMock()
        fetcher.quota_exhausted = False
        fetcher.capture_finished_results = AsyncMock(return_value=0)
        fetcher.fetch_fixtures_window = AsyncMock(return_value=0)
        fetcher.sync_odds_for_dates = AsyncMock(return_value=None)
        fetcher.__aenter__ = AsyncMock(return_value=fetcher)
        fetcher.__aexit__ = AsyncMock(return_value=False)

        standings = AsyncMock(
            return_value={"leagues": 0, "fetched": 0, "skipped": 0, "failed": 0}
        )
        settings = MagicMock()
        settings.SCHEDULER_TIMEZONE = "Asia/Shanghai"
        settings.FIXTURES_LOOKAHEAD_DAYS = 8
        settings.LEAGUE_IDS = {"英超": 39}
        settings.uses_full_history = True

        with (
            patch.object(fs, "FootballFetcher", return_value=fetcher),
            patch.object(fs, "sync_league_standings_for_dates", standings),
            patch.object(fs, "get_settings", return_value=settings),
            patch.object(
                fs, "get_enable_free_quota", AsyncMock(return_value=(True, "db"))
            ),
            patch.object(
                fs,
                "get_enable_scheduled_full_detail",
                AsyncMock(return_value=(True, "env")),
            ),
            patch.object(fs, "clip_fixture_dates_for_plan", lambda days, today: days),
            patch.object(fs, "importlib", MagicMock()),
            patch(
                "app.services.auto_favorites.sync_daily_auto_favorites",
                AsyncMock(return_value={"selected": []}),
            ),
            patch("app.core.database.AsyncSessionLocal"),
        ):
            await fs.scheduled_fixtures_sync(sync_hour=22)

        fetcher.capture_finished_results.assert_not_called()
        fetcher.fetch_fixtures_window.assert_not_called()
        standings.assert_not_called()
        fetcher.sync_odds_for_dates.assert_awaited_once()
        kwargs = fetcher.sync_odds_for_dates.await_args.kwargs
        assert kwargs["budget"] == FREE_QUOTA_EVENING_ODDS_BUDGET
        assert kwargs["set_opening"] is False
        assert kwargs["refresh_existing"] is True
        return fetcher

    try:
        asyncio.run(_run())
    finally:
        asyncio.set_event_loop(asyncio.new_event_loop())


def test_free_quota_catch_up_due_before_and_after_slot() -> None:
    tz = ZoneInfo("Asia/Shanghai")
    before = datetime(2026, 8, 17, 10, 59, tzinfo=tz)
    at_slot = datetime(2026, 8, 17, 11, 0, tzinfo=tz)
    after = datetime(2026, 8, 17, 11, 1, tzinfo=tz)
    assert free_quota_catch_up_due(before) is False
    assert free_quota_catch_up_due(at_slot) is False
    assert free_quota_catch_up_due(after) is True


def test_register_jobs_free_quota_keeps_11_and_22() -> None:
    with patch("app.tasks.scheduler.get_settings") as gs:
        gs.return_value.SCHEDULER_TIMEZONE = "Asia/Shanghai"
        gs.return_value.ENABLE_FREE_QUOTA = True
        if not scheduler.running:
            scheduler.start(paused=True)
        try:
            register_jobs(free_quota=True)
            sync_ids = sorted(
                job.id
                for job in scheduler.get_jobs()
                if str(job.id).startswith("scheduled_fixtures_sync_")
            )
            assert sync_ids == [
                "scheduled_fixtures_sync_11",
                "scheduled_fixtures_sync_22",
            ]

            register_jobs(free_quota=False)
            sync_ids = sorted(
                job.id
                for job in scheduler.get_jobs()
                if str(job.id).startswith("scheduled_fixtures_sync_")
            )
            assert sync_ids == [
                "scheduled_fixtures_sync_00",
                "scheduled_fixtures_sync_06",
                "scheduled_fixtures_sync_11",
                "scheduled_fixtures_sync_16",
                "scheduled_fixtures_sync_19",
                "scheduled_fixtures_sync_22",
            ]
        finally:
            for job in list(scheduler.get_jobs()):
                if str(job.id).startswith("scheduled_fixtures_sync_"):
                    scheduler.remove_job(job.id)


def test_enable_free_quota_defaults_on_from_env() -> None:
    import asyncio

    from app.services import runtime_settings as rs

    async def _run() -> None:
        settings = MagicMock()
        settings.ENABLE_FREE_QUOTA = True
        session = AsyncMock()
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )
        with patch.object(rs, "get_settings", return_value=settings):
            enabled, source = await rs.get_enable_free_quota(session)
        assert enabled is True
        assert source == "env"

    asyncio.run(_run())
