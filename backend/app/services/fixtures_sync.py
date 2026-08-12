"""Fixed-schedule official fixtures, odds, results, and league standings sync."""

from __future__ import annotations

import asyncio
import importlib
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.config import get_settings
from app.services.fetcher import FootballFetcher
from app.services.league_standings import sync_league_standings_for_dates
from app.services.runtime_settings import get_enable_scheduled_full_detail

logger = logging.getLogger(__name__)

_sync_lock = asyncio.Lock()


async def scheduled_fixtures_sync() -> None:
    """Refresh the local DB in one of the six daily scheduler batches."""
    if _sync_lock.locked():
        logger.info("Scheduled fixtures sync already running; skipping overlap")
        return

    settings = get_settings()
    today = datetime.now(ZoneInfo(settings.SCHEDULER_TIMEZONE)).date()
    window = max(1, min(int(settings.FIXTURES_LOOKAHEAD_DAYS), 14))
    days = [today + timedelta(days=offset) for offset in range(window)]
    result_days = [today - timedelta(days=offset) for offset in range(3, -1, -1)]
    primary_league_ids = list(settings.LEAGUE_IDS.values())
    # Standings cover the same upcoming window plus recent result days so list
    # ranks work for both pending and finished cards.
    standings_days = sorted({*days, *result_days})

    async with _sync_lock:
        async with FootballFetcher() as fetcher:
            fixtures_saved = await fetcher.fetch_fixtures_window(
                days[0],
                days[-1],
                force=True,
                league_ids=None,
            )
            await fetcher.sync_odds_for_dates(
                days,
                refresh_existing=True,
                league_ids=primary_league_ids,
                budget=100,
                set_opening=True,
            )
            results_saved = await fetcher.capture_finished_results(on_days=result_days)
            standings_stats = await sync_league_standings_for_dates(
                fetcher,
                standings_days,
            )

        # Batch scope is fixtures + odds + results + league standings. Full
        # display packages stay on-demand via analyze_fixture until this flag
        # is on *and* bulk enrich is wired. Toggle via admin UI / env.
        full_detail_enabled, full_detail_source = await get_enable_scheduled_full_detail()
        if full_detail_enabled:
            logger.info(
                "scheduled full detail enabled (source=%s) but bulk package "
                "enrich is not wired yet; skipping (detail click still enriches)",
                full_detail_source,
            )

        for module_path, function_name, label in (
            ("app.services.ml_predictor", "maybe_auto_train_model", "1X2"),
            ("app.services.ah_predictor", "maybe_auto_train_model", "AH"),
            ("app.services.goal_predictor", "maybe_auto_train_model", "goals"),
        ):
            try:
                module = importlib.import_module(module_path)
                await getattr(module, function_name)()
            except Exception as exc:
                logger.warning(
                    "scheduled_fixtures_sync %s auto-train skipped: %s",
                    label,
                    exc,
                )

        # Odds just refreshed — recompute auto favorites so picks track lines.
        try:
            from app.core.database import AsyncSessionLocal
            from app.services.auto_favorites import sync_daily_auto_favorites

            async with AsyncSessionLocal() as session:
                auto_result = await sync_daily_auto_favorites(session)
            logger.info(
                "scheduled_fixtures_sync auto-favorites selected=%s",
                len(auto_result.get("selected") or []),
            )
        except Exception as exc:
            logger.warning(
                "scheduled_fixtures_sync auto-favorites skipped: %s",
                exc,
            )

    logger.info(
        "scheduled_fixtures_sync done fixtures_saved=%s results_saved=%s "
        "standings=%s",
        fixtures_saved,
        results_saved,
        standings_stats,
    )
