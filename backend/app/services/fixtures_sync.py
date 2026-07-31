"""Shared fixtures + odds sync for HTTP ``/fixtures/sync`` and scheduler."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.core.config import Settings, get_settings
from app.schemas.response import SyncFixturesResponse
from app.services.fetcher import FootballFetcher

logger = logging.getLogger(__name__)

_sync_lock = asyncio.Lock()
_odds_followup_lock = asyncio.Lock()


@dataclass(frozen=True)
class FixturesSyncParams:
    start: date
    window: int
    day_list: list[date]
    # None = persist every league returned by official date= (full schedule).
    fixture_league_ids: list[int] | None
    # Odds follow-up stay scoped (primary catalog / client selection) for quota.
    odds_league_ids: list[int]
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
    # Inclusive window: today .. today+(N-1). Default matches date-strip forward span.
    window = days if days is not None else int(cfg.FIXTURES_LOOKAHEAD_DAYS)
    window = max(1, min(window, 14))
    day_list = [start + timedelta(days=i) for i in range(window)]
    # Schedule: always ingest every league for the day(s).
    # Odds: client selection when provided, else primary catalog only.
    odds_selected = (
        [int(x) for x in league_ids]
        if league_ids is not None
        else list(cfg.LEAGUE_IDS.values())
    )
    if include_odds and not odds_selected:
        raise ValueError("odds league_ids 不能为空")
    return FixturesSyncParams(
        start=start,
        window=window,
        day_list=day_list,
        fixture_league_ids=None,
        odds_league_ids=odds_selected,
        include_results=include_results,
        include_odds=include_odds,
        odds_refresh_existing=odds_refresh_existing,
        odds_budget=odds_budget,
        odds_only=odds_only,
        set_opening=set_opening,
    )


async def _sync_odds_and_results_followup(
    day_list: list[date],
    odds_league_ids: list[int],
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
                            league_ids=odds_league_ids,
                            budget=odds_budget,
                            set_opening=set_opening,
                        )
                    except Exception as exc:
                        logger.warning("include_odds batch failed: %s", exc)
                if include_results:
                    try:
                        # Prefer the sync window so date-strip days beyond default
                        # lookback still get FT backfill when the user opens 赛果.
                        await fetcher.capture_finished_results(on_days=list(day_list))
                    except Exception as exc:
                        logger.warning("include_results capture failed: %s", exc)
        except Exception as exc:
            logger.warning("sync follow-up failed: %s", exc, exc_info=True)


def _result_message(params: FixturesSyncParams) -> str:
    if params.odds_only:
        if params.include_results and not params.include_odds:
            return "赛果已回写"
        if params.include_odds:
            return "缺失盘口已补全"
        return "无变更"
    msg = "赛程已刷新"
    if params.include_odds:
        msg += "，盘口已同步" if params.odds_refresh_existing else "，缺失盘口已补全"
    if params.include_results:
        msg += "，赛果已回写"
    return msg


async def execute_fixtures_sync(
    params: FixturesSyncParams,
    *,
    wait_followup: bool = True,
) -> SyncFixturesResponse:
    """Run sync work (fixtures window + optional odds/results follow-up).

    ``wait_followup=False`` (HTTP toolbar sync): return after fixtures so the UI
    is not blocked for 1+ minutes of per-fixture odds pacing; odds/results continue
    in the background under ``_odds_followup_lock``.
    """
    async with _sync_lock:
        saved = 0
        if not params.odds_only:
            async with FootballFetcher() as fetcher:
                saved = await fetcher.fetch_fixtures_window(
                    params.day_list[0],
                    params.day_list[-1],
                    force=True,
                    league_ids=params.fixture_league_ids,
                )

        need_followup = params.include_odds or params.include_results
        if need_followup and wait_followup:
            await _sync_odds_and_results_followup(
                params.day_list,
                params.odds_league_ids,
                include_odds=params.include_odds,
                include_results=params.include_results,
                odds_refresh_existing=params.odds_refresh_existing,
                odds_budget=params.odds_budget,
                set_opening=params.set_opening,
            )

        if need_followup and not wait_followup:
            day_list = list(params.day_list)
            odds_league_ids = list(params.odds_league_ids)
            include_odds = params.include_odds
            include_results = params.include_results
            odds_refresh_existing = params.odds_refresh_existing
            odds_budget = params.odds_budget
            set_opening = params.set_opening

            async def _bg_followup() -> None:
                try:
                    await _sync_odds_and_results_followup(
                        day_list,
                        odds_league_ids,
                        include_odds=include_odds,
                        include_results=include_results,
                        odds_refresh_existing=odds_refresh_existing,
                        odds_budget=odds_budget,
                        set_opening=set_opening,
                    )
                except Exception as exc:
                    logger.warning("background sync follow-up failed: %s", exc, exc_info=True)

            task = asyncio.create_task(_bg_followup())
            task.add_done_callback(
                lambda t: (
                    logger.warning(
                        "background sync follow-up crashed: %s",
                        t.exception(),
                    )
                    if not t.cancelled() and t.exception()
                    else None
                )
            )
            message = "赛程已刷新，盘口与赛果正在后台同步"
        else:
            message = _result_message(params)

        return SyncFixturesResponse(
            status="ok",
            fixtures_saved=saved,
            days=params.window,
            date=params.start.isoformat(),
            message=message,
        )


async def scheduled_fixtures_sync() -> None:
    """Scheduler: full-schedule window + primary-league odds gap-fill (+ results)."""
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
    for mod_path, fn_name, label in (
        ("app.services.ml_predictor", "maybe_auto_train_model", "1X2"),
        ("app.services.ah_predictor", "maybe_auto_train_model", "AH"),
        ("app.services.goal_predictor", "maybe_auto_train_model", "goals"),
    ):
        try:
            import importlib

            mod = importlib.import_module(mod_path)
            await getattr(mod, fn_name)()
        except Exception as exc:
            logger.warning(
                "scheduled_fixtures_sync %s auto-train skipped: %s", label, exc
            )
    logger.info(
        "scheduled_fixtures_sync done fixtures_saved=%s message=%s",
        result.fixtures_saved,
        result.message,
    )
