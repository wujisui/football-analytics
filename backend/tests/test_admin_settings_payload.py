"""Admin settings payload builders must execute, not just import.

A missing module-level import only blows up when the endpoint body runs, so
these tests call the builders instead of importing the module.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.v1.endpoints import admin


def test_hot_leagues_payload_translates_every_catalog_league() -> None:
    payload = admin._hot_leagues_payload([39], "db")

    assert payload.source == "db"
    assert payload.league_ids == [39]
    assert payload.leagues, "catalog must not be empty"
    assert all(item.league_name for item in payload.leagues)
    assert [item.league_id for item in payload.leagues if item.selected] == [39]


def _subscription_payload(subscribed: bool, *, early_odds: bool) -> object:
    async def _run() -> object:
        with (
            patch.object(
                admin,
                "get_subscription_early_odds",
                AsyncMock(return_value=(early_odds, "db")),
            ),
            patch.object(admin, "get_last_sync_run", AsyncMock(return_value=None)),
            patch.object(
                admin, "full_sync_completed_today", AsyncMock(return_value=False)
            ),
            patch.object(
                admin,
                "get_cache_service",
                MagicMock(return_value=MagicMock(last_api_remaining=7000)),
            ),
        ):
            return await admin._subscription_payload(subscribed, "db")

    try:
        return asyncio.run(_run())
    finally:
        asyncio.set_event_loop(asyncio.new_event_loop())


def test_subscribed_sync_times_include_evening_half_hours() -> None:
    payload = _subscription_payload(True, early_odds=False)

    assert payload.subscribed is True
    assert payload.api_remaining == 7000
    for clock in ("11:00", "11:55", "21:30", "22:30", "23:30", "00:00"):
        assert clock in payload.sync_times
    # Early switch off keeps 04/06/08/10 out of the advertised times.
    assert "04:00" not in payload.sync_times

    with_early = _subscription_payload(True, early_odds=True)
    assert "04:00" in with_early.sync_times
    assert "21:30" in with_early.sync_times


def test_unsubscribed_sync_times_stay_on_three_slots() -> None:
    payload = _subscription_payload(False, early_odds=True)

    assert payload.sync_times == ["08:05", "11:00", "22:00"]
