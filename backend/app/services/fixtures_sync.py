"""Shared fixtures + odds sync for HTTP ``/fixtures/sync`` and scheduler."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

from app.core.config import Settings, get_settings
from app.schemas.response import SyncFixturesResponse, SyncFixturesStatusResponse
from app.services.fetcher import ApiKeyNotConfiguredError, FootballFetcher

logger = logging.getLogger(__name__)

_sync_lock = asyncio.Lock()
_odds_followup_lock = asyncio.Lock()
_sync_state: dict[str, Any] = {
    "running": False,
    "last_status": None,
    "last_message": "",
    "last_error": None,
    "fixtures_saved": 0,
    "finished_at": None,
}


@dataclass(frozen=True)
class FixturesSyncParams:
    start: date
    window: int
    day_list: list[date]
    selected: list[int] | None
    include_results: bool
    include_odds: bool
    odds_refresh_existing: bool
    odds_budget: int
    odds_only: bool
    set_opening: bool = False


def build_sync_params(
    *,
    date_str: str | None = None,
    days: int | None = None,
    include_results: bool = True,
    include_odds: bool = True,
    odds_refresh_existing: bool = True,
    odds_budget: int = 100,
    league_ids: list[int] | None = None,
    odds_only: bool = False,
    set_opening: bool = False,
    settings: Settings | None = None,
) -> FixturesSyncParams:
    cfg = settings or get_settings()
    start = date.fromisoformat(date_str) if date_str else date.today()
    window = days if days is not None else min(cfg.FIXTURES_LOOKAHEAD_DAYS, 7)
    window = max(1, min(window, 14))
    day_list = [start + timedelta(days=i) for i in range(window)]
    selected = league_ids
    if selected is not None and not selected:
        raise ValueError("league_ids 不能为空")
    return FixturesSyncParams(
        start=start,
        window=window,
        day_list=day_list,
        selected=selected,
        include_results=include_results,
        include_odds=include_odds,
        odds_refresh_existing=odds_refresh_existing,
        odds_budget=odds_budget,
        odds_only=odds_only,
        set_opening=set_opening,
    )


async def _sync_odds_and_results_followup(
    day_list: list[date],
    selected: list[int] | None,
    *,
    include_odds: bool,
    include_results: bool,
    odds_refresh_existing: bool = True,
    odds_budget: int = 40,
    set_opening: bool = False,
) -> None:
    if _odds_followup_lock.locked():
        logger.info("Odds/results follow-up already running; skip duplicate")
        return
    async with _odds_followup_lock:
        try:
            async with FootballFetcher() as fetcher:
                if include_odds:
                    try:
                        await fetcher.sync_odds_for_dates(
                            day_list,
                            refresh_existing=odds_refresh_existing,
                            league_ids=selected,
                            budget=odds_budget,
                            set_opening=set_opening,
                        )
                    except Exception as exc:
                        logger.warning("include_odds batch failed: %s", exc)
                if include_results:
                    try:
                        await fetcher.capture_finished_results(lookback_days=2)
                    except Exception as exc:
                        logger.warning("include_results capture failed: %s", exc)
        except Exception as exc:
            logger.warning("sync follow-up failed: %s", exc, exc_info=True)


def _result_message(params: FixturesSyncParams) -> str:
    if params.odds_only:
        return "缺失盘口已补全" if params.include_odds else "无变更"
    msg = "赛程已刷新"
    if params.include_odds:
        msg += "，盘口已同步" if params.odds_refresh_existing else "，缺失盘口已补全"
    return msg


async def execute_fixtures_sync(params: FixturesSyncParams) -> SyncFixturesResponse:
    """Run sync work (fixtures window + optional odds/results follow-up)."""
    async with _sync_lock:
        saved = 0
        if not params.odds_only:
            async with FootballFetcher() as fetcher:
                saved = await fetcher.fetch_fixtures_window(
                    params.day_list[0],
                    params.day_list[-1],
                    force=True,
                    league_ids=params.selected,
                )

        if params.include_odds or params.include_results:
            await _sync_odds_and_results_followup(
                params.day_list,
                params.selected,
                include_odds=params.include_odds,
                include_results=params.include_results,
                odds_refresh_existing=params.odds_refresh_existing,
                odds_budget=params.odds_budget,
                set_opening=params.set_opening,
            )

        return SyncFixturesResponse(
            status="ok",
            fixtures_saved=saved,
            days=params.window,
            date=params.start.isoformat(),
            message=_result_message(params),
        )


def sync_status_response() -> SyncFixturesStatusResponse:
    return SyncFixturesStatusResponse.model_validate(_sync_state)


def is_sync_running() -> bool:
    return bool(_sync_state["running"])


async def _run_background(params: FixturesSyncParams) -> None:
    _sync_state["running"] = True
    _sync_state["last_error"] = None
    try:
        result = await execute_fixtures_sync(params)
        _sync_state["last_status"] = result.status
        _sync_state["last_message"] = result.message
        _sync_state["fixtures_saved"] = result.fixtures_saved
    except ApiKeyNotConfiguredError as exc:
        _sync_state["last_status"] = "failed"
        _sync_state["last_error"] = str(exc)
        _sync_state["last_message"] = str(exc)
        logger.warning("background fixtures sync unavailable: %s", exc)
    except Exception as exc:
        _sync_state["last_status"] = "failed"
        _sync_state["last_error"] = str(exc)
        _sync_state["last_message"] = f"同步失败：{exc}"
        logger.error("background fixtures sync failed: %s", exc, exc_info=True)
    finally:
        _sync_state["running"] = False
        _sync_state["finished_at"] = datetime.now(timezone.utc).isoformat()


async def enqueue_fixtures_sync(params: FixturesSyncParams) -> SyncFixturesResponse:
    """Start sync in background; return immediately unless already running."""
    if _sync_state["running"]:
        return SyncFixturesResponse(
            status="running",
            fixtures_saved=0,
            days=params.window,
            date=params.start.isoformat(),
            message="同步任务进行中，请稍候",
        )
    asyncio.create_task(_run_background(params))
    return SyncFixturesResponse(
        status="accepted",
        fixtures_saved=0,
        days=params.window,
        date=params.start.isoformat(),
        message="已在后台开始同步官方数据",
    )


async def scheduled_fixtures_sync() -> None:
    """Scheduler: refresh fixture window + gap-fill odds (+ recent results)."""
    settings = get_settings()
    from zoneinfo import ZoneInfo

    today = datetime.now(ZoneInfo(settings.SCHEDULER_TIMEZONE)).date()
    window = max(1, min(int(settings.FIXTURES_LOOKAHEAD_DAYS), 14))
    params = build_sync_params(
        date_str=today.isoformat(),
        days=window,
        include_results=True,
        include_odds=True,
        odds_refresh_existing=False,
        odds_budget=100,
        set_opening=True,
    )
    result = await execute_fixtures_sync(params)
    try:
        from app.services.ml_predictor import maybe_auto_train_model

        await maybe_auto_train_model()
    except Exception as exc:
        logger.warning("scheduled_fixtures_sync ML auto-train skipped: %s", exc)
    logger.info(
        "scheduled_fixtures_sync done fixtures_saved=%s message=%s",
        result.fixtures_saved,
        result.message,
    )
