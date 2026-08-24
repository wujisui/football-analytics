"""Tests for free-plan date clipping, standings season clamp and quota accounting."""

import asyncio
import importlib
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.api_quota import (
    api_errors_plan_blocked,
    api_errors_quota_exhausted,
    clip_fixture_dates_for_plan,
    free_plan_fixture_date_bounds,
)
from app.services.league_standings import standings_season_for_league


def test_free_plan_fixture_date_bounds() -> None:
    start, end = free_plan_fixture_date_bounds(date(2026, 8, 14))
    assert start == date(2026, 8, 12)
    assert end == date(2026, 8, 14)


def test_clip_fixture_dates_free_mode() -> None:
    today = date(2026, 8, 14)
    days = [today + __import__("datetime").timedelta(days=i) for i in range(-3, 8)]
    with patch("app.services.api_quota.get_settings") as gs:
        gs.return_value.uses_full_history = False
        clipped = clip_fixture_dates_for_plan(days, today)
    assert clipped == [date(2026, 8, 12), date(2026, 8, 13), date(2026, 8, 14)]


def test_clip_fixture_dates_full_mode_keeps_all() -> None:
    today = date(2026, 8, 14)
    days = [today, today + __import__("datetime").timedelta(days=7)]
    with patch("app.services.api_quota.get_settings") as gs:
        gs.return_value.uses_full_history = True
        clipped = clip_fixture_dates_for_plan(days, today)
    assert clipped == days


def test_quota_exhausted_detection() -> None:
    assert api_errors_quota_exhausted(
        {"requests": "You have reached the request limit for the day"}
    )
    assert not api_errors_quota_exhausted(
        {"plan": "Free plans do not have access to this date"}
    )
    assert api_errors_plan_blocked(
        {"plan": "Free plans do not have access to this season, try from 2022 to 2024."}
    )


def test_standings_season_clamped_on_free() -> None:
    with patch("app.services.league_standings.get_settings") as gs:
        gs.return_value.uses_full_history = False
        assert standings_season_for_league("2026") == "2024"
        assert standings_season_for_league("2023") == "2023"


def test_standings_season_full_keeps_current() -> None:
    with patch("app.services.league_standings.get_settings") as gs:
        gs.return_value.uses_full_history = True
        assert standings_season_for_league("2026") == "2026"


def test_uses_full_history_when_free_quota_turned_off() -> None:
    from app.core.config import Settings
    from app.services.runtime_settings import set_cached_enable_free_quota

    settings = Settings.model_construct(API_HISTORY_MODE="free")
    set_cached_enable_free_quota(False)
    assert settings.uses_full_history is True
    set_cached_enable_free_quota(True)
    assert settings.uses_full_history is False


def test_uses_full_history_env_full_ignores_free_quota() -> None:
    from app.core.config import Settings
    from app.services.runtime_settings import set_cached_enable_free_quota

    settings = Settings.model_construct(API_HISTORY_MODE="full")
    set_cached_enable_free_quota(True)
    assert settings.uses_full_history is True


def test_cache_counts_official_responses() -> None:
    from app.services.cache import CacheService

    cache = CacheService()
    cache.note_api_response(7499)
    cache.note_api_response(7498)
    assert cache.api_request_count == 2
    assert cache.last_api_remaining == 7498


def test_record_sync_run_persists_quota_delta_of_finished_batches() -> None:
    # ``app.tasks.scheduler`` also names an AsyncIOScheduler instance, so grab
    # the module itself rather than the package attribute.
    sched = importlib.import_module("app.tasks.scheduler")

    saved: list[dict] = []

    async def _fake_set(_session, run: dict) -> dict:
        saved.append(run)
        return run

    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=MagicMock())
    session_cm.__aexit__ = AsyncMock(return_value=False)

    async def _run() -> None:
        with (
            patch.object(sched, "set_last_sync_run", _fake_set),
            patch.object(sched, "AsyncSessionLocal", MagicMock(return_value=session_cm)),
            patch.object(
                sched,
                "get_cache_service",
                lambda: SimpleNamespace(api_request_count=130, last_api_remaining=7370),
            ),
        ):
            sched.active_tasks["quota_probe"] = {"status": "skipped"}
            await sched._record_sync_run("quota_probe", "full", 100)
            sched.active_tasks["quota_probe"] = {
                "status": "completed",
                "finished_at": "2026-08-24T03:00:00+00:00",
            }
            await sched._record_sync_run("quota_probe", "full", 100)

    try:
        asyncio.run(_run())
    finally:
        sched.active_tasks.pop("quota_probe", None)
        asyncio.set_event_loop(asyncio.new_event_loop())

    # Skipped batches burn nothing and must not overwrite the last real run.
    assert len(saved) == 1
    assert saved[0]["status"] == "completed"
    assert saved[0]["quota_used"] == 30
    assert saved[0]["api_remaining"] == 7370
    assert saved[0]["finished_at"] == "2026-08-24T03:00:00+00:00"
