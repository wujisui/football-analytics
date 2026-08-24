"""Tests for free-plan date clipping and standings season clamp."""

from datetime import date
from unittest.mock import patch

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
