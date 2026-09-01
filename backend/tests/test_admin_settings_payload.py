"""Admin settings payload builders must execute, not just import.

A missing module-level import only blows up when the endpoint body runs, so
these tests call the builders instead of importing the module.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints import admin


def test_hot_leagues_payload_translates_every_catalog_league() -> None:
    async def _run() -> object:
        categories = [SimpleNamespace(id=1, name="五大联赛")]
        leagues = [
            SimpleNamespace(
                id=39,
                name="英超",
                country="England",
                category_id=1,
                is_hot=True,
                is_protected=True,
            )
        ]
        with (
            patch.object(
                admin, "league_categories", AsyncMock(return_value=categories)
            ),
            patch.object(admin, "catalog_leagues", AsyncMock(return_value=leagues)),
        ):
            return await admin._hot_leagues_payload(AsyncMock())

    payload = asyncio.run(_run())
    assert payload.source == "db"
    assert payload.league_ids == [39]
    assert payload.leagues, "catalog must not be empty"
    assert all(item.league_name for item in payload.leagues)
    assert [item.league_id for item in payload.leagues if item.selected] == [39]
    assert payload.categories[0].category_name == "五大联赛"


def _subscription_payload(
    subscribed: bool,
    *,
    dense_odds: bool = False,
) -> object:
    async def _run() -> object:
        with (
            patch.object(
                admin,
                "get_subscription_dense_odds",
                AsyncMock(return_value=(dense_odds, "db")),
            ),
            patch.object(admin, "get_last_sync_run", AsyncMock(return_value=None)),
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


def test_subscriber_without_dense_uses_sparse_times() -> None:
    payload = _subscription_payload(True, dense_odds=False)

    assert payload.subscribed is True
    assert payload.dense_odds_enabled is False
    assert payload.api_remaining == 7000
    assert payload.sync_times == ["07:00", "08:05", "10:55", "22:00"]


def test_subscribed_dense_sync_times_cover_all_half_hours() -> None:
    payload = _subscription_payload(True, dense_odds=True)

    assert payload.dense_odds_enabled is True
    for clock in ("00:25", "10:25", "10:55", "11:25", "11:55", "23:55"):
        assert clock in payload.sync_times
    for clock in ("04:00", "11:00", "22:00"):
        assert clock not in payload.sync_times


def test_unsubscribed_sync_times_include_morning_results() -> None:
    payload = _subscription_payload(False, dense_odds=True)

    assert payload.sync_times == ["07:00", "08:05", "10:55", "22:00"]
    assert payload.dense_odds_enabled is False


def test_manual_full_sync_requires_subscription_but_has_no_daily_limit() -> None:
    async def _run_unsubscribed() -> None:
        with patch.object(
            admin,
            "get_subscription_enabled",
            AsyncMock(return_value=(False, "db")),
        ):
            with pytest.raises(HTTPException) as exc:
                await admin.trigger_task_endpoint(
                    admin.TriggerTaskRequest(name="scheduled_fixtures_sync"),
                    None,
                )
            assert exc.value.status_code == 409

    async def _run_subscribed() -> dict:
        with (
            patch.object(
                admin,
                "get_subscription_enabled",
                AsyncMock(return_value=(True, "db")),
            ),
            patch.object(admin, "official_sync_busy", return_value=False),
            patch.object(
                admin,
                "get_task_status",
                return_value={"active_tasks": {}},
            ),
            patch.object(admin, "trigger_task", AsyncMock()),
            patch.object(admin.asyncio, "sleep", AsyncMock()),
        ):
            return await admin.trigger_task_endpoint(
                admin.TriggerTaskRequest(name="scheduled_fixtures_sync"),
                None,
            )

    asyncio.run(_run_unsubscribed())
    response = asyncio.run(_run_subscribed())
    assert response["status"] == "accepted"
