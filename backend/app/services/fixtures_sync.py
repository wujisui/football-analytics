"""Fixed-schedule official fixtures, odds, results, and league standings sync."""

from __future__ import annotations

import asyncio
import importlib
import logging
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.core.config import get_settings
from app.services.api_quota import (
    FREE_QUOTA_EVENING_HOUR,
    FREE_QUOTA_EVENING_ODDS_BUDGET,
    clip_fixture_dates_for_plan,
)
from app.services.fetcher import FootballFetcher
from app.services.league_standings import sync_league_standings_for_dates
from app.services.runtime_settings import (
    get_enable_free_quota,
    get_enable_scheduled_full_detail,
    get_hot_league_ids,
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


async def sync_free_quota_rollover_fixtures() -> int:
    """At official UTC-day rollover, ingest today's worldwide schedule in one call.

    The free API plan cannot request tomorrow. Running just after the official
    UTC date rolls over makes that date legal early enough for 08:30+ Beijing
    American fixtures to enter 【比赛】 before kickoff. This path deliberately skips
    odds, standings, details, training, and recommendations.
    """
    if _sync_lock.locked():
        logger.info("Fixture rollover sync already running elsewhere; skipping overlap")
        return 0

    today = datetime.now(timezone.utc).date()
    free_quota, _ = await get_enable_free_quota()
    if not free_quota:
        logger.info("Fixture rollover sync skipped because free quota is disabled")
        return 0

    async with _sync_lock:
        async with FootballFetcher() as fetcher:
            saved = await fetcher.fetch_fixtures_for_date(
                today,
                force=True,
                league_ids=None,
            )
    logger.info(
        "Fixture rollover sync done date=%s fixtures_saved=%s official_calls=1",
        today,
        saved,
    )
    return saved


async def scheduled_fixtures_sync(*, sync_hour: int | None = None) -> None:
    """Refresh the local DB in one scheduled (or manual) sync batch.

    Order matters for free-tier quota: settle recent match-day scores before
    burning calls on odds / standings, otherwise ML labels and 赛果统计 stall.

    Free-quota ``sync_hour=22`` is odds-light: refresh today's catalog boards
    and recompute auto picks only, so morning + evening fit a ~100-call day.
    Manual sync / 11:00 keep the full free batch.
    """
    if _sync_lock.locked():
        logger.info("Scheduled fixtures sync already running; skipping overlap")
        return

    settings = get_settings()
    today = datetime.now(ZoneInfo(settings.SCHEDULER_TIMEZONE)).date()
    free_quota, _ = await get_enable_free_quota()
    evening_odds_only = (
        free_quota
        and sync_hour is not None
        and int(sync_hour) == FREE_QUOTA_EVENING_HOUR
    )
    days, result_days = sync_dates(
        today,
        lookahead_days=settings.FIXTURES_LOOKAHEAD_DAYS,
        free_quota=free_quota,
    )
    # Free plan cannot request far-future / old dates — clip before any call.
    days = clip_fixture_dates_for_plan(days, today)
    result_days = clip_fixture_dates_for_plan(result_days, today)
    primary_league_ids, _ = await get_hot_league_ids()
    # Standings cover the same upcoming window plus recent result days so list
    # ranks work for both pending and finished cards. Free quota skips standings
    # entirely: 积分榜 per-league calls can drain the daily budget before odds
    # finish, leaving today's schedule/odds incomplete. Ranks read the last
    # local snapshot instead; they refresh again whenever free quota is off.
    standings_days = [] if free_quota else sorted({*days, *result_days})

    async with _sync_lock:
        async with FootballFetcher() as fetcher:
            results_saved = 0
            fixtures_saved = 0
            standings_stats = {
                "leagues": 0,
                "fetched": 0,
                "skipped": 0,
                "failed": 0,
            }

            if evening_odds_only:
                odds_days = days or [today]
                odds_days = clip_fixture_dates_for_plan(odds_days, today)
                if odds_days and not fetcher.quota_exhausted:
                    await fetcher.sync_odds_for_dates(
                        odds_days,
                        refresh_existing=True,
                        league_ids=primary_league_ids,
                        budget=FREE_QUOTA_EVENING_ODDS_BUDGET,
                        set_opening=False,
                    )
                logger.info(
                    "scheduled_fixtures_sync evening odds-light "
                    "hour=%s budget=%s days=%s",
                    sync_hour,
                    FREE_QUOTA_EVENING_ODDS_BUDGET,
                    odds_days,
                )
            else:
                # 1) Results first — one worldwide date= call per day, then labels.
                if result_days and not fetcher.quota_exhausted:
                    results_saved = await fetcher.capture_finished_results(
                        on_days=result_days,
                        today=today,
                    )

                # 2) Upcoming fixtures window (may overlap today already refreshed).
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

        # Optional: pre-pull detail packages for hot prematch fixtures that
        # still lack a display package. Same path as GET /fixtures/{id}/analysis.
        # Default off and always suppressed by free-quota mode.
        full_detail_enabled, full_detail_source = await get_enable_scheduled_full_detail()
        full_detail_stats: dict = {
            "enabled": full_detail_enabled,
            "source": full_detail_source,
        }
        if full_detail_enabled and not free_quota:
            try:
                from app.services.scheduled_detail_enrich import (
                    UNLIMITED_DETAIL_BUDGET,
                    run_scheduled_full_detail_enrich,
                )

                full_detail_stats.update(
                    await run_scheduled_full_detail_enrich(
                        # Admin「立即同步」has no hour: pull every missing package.
                        budget=(
                            None
                            if sync_hour is not None
                            else UNLIMITED_DETAIL_BUDGET
                        ),
                    )
                )
            except Exception as exc:
                logger.warning(
                    "scheduled_fixtures_sync full-detail enrich skipped: %s",
                    exc,
                )
                full_detail_stats["error"] = str(exc)
        elif free_quota and full_detail_enabled:
            full_detail_stats["skipped"] = "free_quota_local_detail"

        if not evening_odds_only:
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
        "standings=%s full_detail=%s evening_odds_only=%s",
        fixtures_saved,
        results_saved,
        standings_stats,
        full_detail_stats,
        evening_odds_only,
    )
