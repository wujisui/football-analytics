"""Fixed-schedule official fixtures, odds, results, and league standings sync."""

from __future__ import annotations

import asyncio
import importlib
import logging
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.core.config import get_settings
from app.services.api_quota import clip_fixture_dates_for_plan
from app.services.fetcher import FootballFetcher
from app.services.league_standings import sync_league_standings_for_dates
from app.services.runtime_settings import (
    get_enable_free_quota,
    get_enable_scheduled_full_detail,
)

logger = logging.getLogger(__name__)

_sync_lock = asyncio.Lock()


def sync_dates(
    today: date,
    *,
    lookahead_days: int,
    free_quota: bool,
) -> tuple[list[date], list[date]]:
    """Return (fixture days, result days) for one batch.

    Free-quota mode deliberately spends fixture calls on only yesterday and
    today: yesterday closes statistics / ML labels, today keeps the match list
    and odds usable. Full mode retains the configured future window and short
    result lookback.
    """
    if free_quota:
        return [today], [today - timedelta(days=1)]
    window = max(1, min(int(lookahead_days), 14))
    fixture_days = [today + timedelta(days=offset) for offset in range(window)]
    result_days = [today - timedelta(days=offset) for offset in range(3, -1, -1)]
    return fixture_days, result_days


async def scheduled_fixtures_sync() -> None:
    """Refresh the local DB in one scheduled (or manual) sync batch.

    Order matters for free-tier quota: settle recent match-day scores before
    burning calls on odds / standings, otherwise ML labels and 赛果统计 stall.
    """
    if _sync_lock.locked():
        logger.info("Scheduled fixtures sync already running; skipping overlap")
        return

    settings = get_settings()
    today = datetime.now(ZoneInfo(settings.SCHEDULER_TIMEZONE)).date()
    free_quota, _ = await get_enable_free_quota()
    days, result_days = sync_dates(
        today,
        lookahead_days=settings.FIXTURES_LOOKAHEAD_DAYS,
        free_quota=free_quota,
    )
    # Free plan cannot request far-future / old dates — clip before any call.
    days = clip_fixture_dates_for_plan(days, today)
    result_days = clip_fixture_dates_for_plan(result_days, today)
    primary_league_ids = list(settings.LEAGUE_IDS.values())
    # Standings cover the same upcoming window plus recent result days so list
    # ranks work for both pending and finished cards. Free quota skips standings
    # entirely: 积分榜 per-league calls can drain the daily budget before odds
    # finish, leaving today's schedule/odds incomplete. Ranks read the last
    # local snapshot instead; they refresh again whenever free quota is off.
    standings_days = [] if free_quota else sorted({*days, *result_days})

    async with _sync_lock:
        async with FootballFetcher() as fetcher:
            # 1) Results first — one worldwide date= call per day, then labels.
            results_saved = 0
            if result_days and not fetcher.quota_exhausted:
                results_saved = await fetcher.capture_finished_results(
                    on_days=result_days,
                    today=today,
                )

            # 2) Upcoming fixtures window (may overlap today already refreshed).
            fixtures_saved = 0
            upcoming = [d for d in days if d not in set(result_days)]
            if upcoming and not fetcher.quota_exhausted:
                fixtures_saved = await fetcher.fetch_fixtures_window(
                    upcoming[0],
                    upcoming[-1],
                    force=True,
                    league_ids=None,
                )
            elif not days and not result_days:
                logger.warning(
                    "scheduled_fixtures_sync: no fixture dates left after "
                    "free-plan window clip; skipping fixtures fetch"
                )

            odds_days = days or result_days
            if odds_days and not fetcher.quota_exhausted:
                await fetcher.sync_odds_for_dates(
                    odds_days,
                    refresh_existing=True,
                    league_ids=primary_league_ids,
                    budget=100,
                    set_opening=True,
                )

            standings_stats = {
                "leagues": 0,
                "fetched": 0,
                "skipped": 0,
                "failed": 0,
            }
            if standings_days and not fetcher.quota_exhausted:
                # Catalog leagues only — date-strip extras must not burn quota.
                standings_stats = await sync_league_standings_for_dates(
                    fetcher,
                    standings_days,
                    league_ids=primary_league_ids,
                )
            elif not standings_days:
                logger.info(
                    "scheduled_fixtures_sync: skipping standings "
                    "(free-quota mode prioritizes fixtures/odds)"
                )
            elif fetcher.quota_exhausted:
                logger.warning(
                    "scheduled_fixtures_sync: skipping standings "
                    "(official quota exhausted earlier in this batch)"
                )

        # Optional: pre-pull detail packages for catalog prematch fixtures that
        # still lack a display package. Same path as GET /fixtures/{id}/analysis.
        # Default off — burns official quota; admin toggles via Mine UI / env.
        full_detail_enabled, full_detail_source = await get_enable_scheduled_full_detail()
        full_detail_stats: dict = {
            "enabled": full_detail_enabled,
            "source": full_detail_source,
        }
        if full_detail_enabled:
            try:
                from app.services.scheduled_detail_enrich import (
                    run_scheduled_full_detail_enrich,
                )

                detail_before = None
                if free_quota:
                    local_midnight = datetime.combine(
                        today + timedelta(days=1),
                        datetime.min.time(),
                        tzinfo=ZoneInfo(settings.SCHEDULER_TIMEZONE),
                    )
                    detail_before = (
                        local_midnight.astimezone(timezone.utc)
                        .replace(tzinfo=None)
                    )
                full_detail_stats.update(
                    await run_scheduled_full_detail_enrich(before=detail_before)
                )
            except Exception as exc:
                logger.warning(
                    "scheduled_fixtures_sync full-detail enrich skipped: %s",
                    exc,
                )
                full_detail_stats["error"] = str(exc)

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
        "standings=%s full_detail=%s",
        fixtures_saved,
        results_saved,
        standings_stats,
        full_detail_stats,
    )
