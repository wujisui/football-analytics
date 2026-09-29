"""Hot-match score refresh wakes only when there is something to fetch."""

import asyncio
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

from app.services.live_results import plan_live_results

TZ = ZoneInfo("Asia/Shanghai")
SLOTS = ((4, 55), (10, 55), (16, 55), (22, 55))


def utc(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def test_idle_window_waits_for_the_next_hot_kickoff() -> None:
    now = utc(2026, 9, 29, 10, 0)
    kickoff = utc(2026, 9, 29, 12, 0)
    plan = plan_live_results(
        now=now,
        active_kickoffs=[],
        next_kickoff=kickoff,
        full_slots=SLOTS,
        scheduler_tz=TZ,
    )
    assert plan.fetch_dates == ()
    assert plan.next_run == kickoff


def test_active_matches_on_one_utc_date_take_one_call() -> None:
    now = utc(2026, 9, 29, 12, 30)
    plan = plan_live_results(
        now=now,
        active_kickoffs=[utc(2026, 9, 29, 12, 0), utc(2026, 9, 29, 11, 0)],
        next_kickoff=None,
        full_slots=SLOTS,
        scheduler_tz=TZ,
    )
    assert plan.fetch_dates == (date(2026, 9, 29),)
    assert plan.next_run == now + timedelta(minutes=30)


def test_active_matches_spanning_utc_midnight_take_both_dates() -> None:
    now = utc(2026, 9, 30, 0, 30)
    plan = plan_live_results(
        now=now,
        active_kickoffs=[utc(2026, 9, 29, 23, 30), utc(2026, 9, 30, 0, 15)],
        next_kickoff=None,
        full_slots=SLOTS,
        scheduler_tz=TZ,
    )
    assert plan.fetch_dates == (date(2026, 9, 29), date(2026, 9, 30))


def test_kickoff_older_than_four_hours_is_not_polled() -> None:
    now = utc(2026, 9, 29, 18, 0)
    later = utc(2026, 9, 29, 20, 0)
    plan = plan_live_results(
        now=now,
        active_kickoffs=[utc(2026, 9, 29, 12, 0)],
        next_kickoff=later,
        full_slots=SLOTS,
        scheduler_tz=TZ,
    )
    assert plan.fetch_dates == ()
    assert plan.next_run == later


def test_full_batch_cooldown_skips_the_official_call() -> None:
    now = utc(2026, 9, 29, 2, 57)
    plan = plan_live_results(
        now=now,
        active_kickoffs=[utc(2026, 9, 29, 2, 0)],
        next_kickoff=None,
        full_slots=SLOTS,
        scheduler_tz=TZ,
    )
    assert plan.fetch_dates == ()
    assert plan.next_run == utc(2026, 9, 29, 3, 25)


def test_next_pass_does_not_land_on_the_full_batch() -> None:
    now = utc(2026, 9, 29, 2, 28)
    plan = plan_live_results(
        now=now,
        active_kickoffs=[utc(2026, 9, 29, 2, 0)],
        next_kickoff=None,
        full_slots=SLOTS,
        scheduler_tz=TZ,
    )
    assert plan.fetch_dates == (date(2026, 9, 29),)
    assert plan.next_run == utc(2026, 9, 29, 3, 25)


def test_without_a_future_hot_match_waits_for_the_next_full_batch() -> None:
    now = utc(2026, 9, 29, 3, 0)
    plan = plan_live_results(
        now=now,
        active_kickoffs=[],
        next_kickoff=None,
        full_slots=SLOTS,
        scheduler_tz=TZ,
    )
    assert plan.fetch_dates == ()
    assert plan.next_run == utc(2026, 9, 29, 8, 57)


def test_results_batch_can_target_explicit_dates() -> None:
    from app.services import fixtures_sync as fs

    target = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    fetcher = MagicMock()
    fetcher.quota_exhausted = False
    fetcher.capture_finished_results = AsyncMock(return_value=2)
    fetcher.fetch_fixtures_for_date = AsyncMock()
    fetcher.sync_odds_for_dates = AsyncMock()
    fetcher.__aenter__ = AsyncMock(return_value=fetcher)
    fetcher.__aexit__ = AsyncMock(return_value=False)
    settings = MagicMock(SCHEDULER_TIMEZONE="Asia/Shanghai", FIXTURES_LOOKAHEAD_DAYS=8)

    async def _run() -> dict:
        with (
            patch.object(fs, "FootballFetcher", return_value=fetcher),
            patch.object(fs, "get_settings", return_value=settings),
            patch.object(
                fs, "get_enable_free_quota", AsyncMock(return_value=(False, "db"))
            ),
            patch.object(fs, "get_hot_league_ids", AsyncMock(return_value=([39], "db"))),
            patch.object(
                fs, "get_catalog_league_ids", AsyncMock(return_value=([39], "db"))
            ),
            patch.object(fs, "resolve_odds_today", AsyncMock(return_value=target)),
            patch("app.services.auto_favorites.sync_daily_auto_favorites", AsyncMock()),
            patch("app.core.database.AsyncSessionLocal"),
        ):
            return await fs.scheduled_fixtures_sync(
                mode="results",
                result_on_days=[target],
            )

    try:
        result = asyncio.run(_run())
        assert result["status"] == "completed"
        on_days = fetcher.capture_finished_results.await_args.kwargs["on_days"]
        assert on_days == [target]
        fetcher.fetch_fixtures_for_date.assert_not_awaited()
        fetcher.sync_odds_for_dates.assert_not_awaited()
    finally:
        asyncio.set_event_loop(asyncio.new_event_loop())
