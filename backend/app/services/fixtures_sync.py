"""Fixed-schedule official fixtures, odds, results, and league standings sync."""

from __future__ import annotations

import asyncio
import importlib
import logging
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.models.api_snapshot import ApiSnapshot
from app.models.fixture import Fixture
from app.services.api_quota import (
    FREE_QUOTA_EVENING_ODDS_BUDGET,
    clip_fixture_dates_for_plan,
)
from app.services.cache import fixtures_cache_key
from app.services.fetcher import FootballFetcher
from app.services.league_standings import sync_league_standings_for_dates
from app.services.runtime_settings import (
    get_catalog_league_ids,
    get_enable_free_quota,
    get_hot_league_ids,
)

logger = logging.getLogger(__name__)

_sync_lock = asyncio.Lock()
SUBSCRIBED_LIGHT_ODDS_BUDGET = 100
# 11:00 / 立即同步：今天刷即时盘，另拉未来三天缺盘（首次可用冻初盘）。
FULL_BATCH_FUTURE_ODDS_DAYS = 3


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
        return [today], result_days_for_batch(today)
    window = max(1, min(int(lookahead_days), 14))
    fixture_days = [today + timedelta(days=offset) for offset in range(window)]
    return fixture_days, result_days_for_batch(today)


def result_days_for_batch(today: date) -> list[date]:
    """Yesterday and today: two worldwide ``fixtures?date=`` calls.

    Yesterday closes overnight finishes (Saturday backfills Friday night).
    Today lets afternoon/evening FT land the same day instead of waiting for
    the next 07:00. Older days are not re-fetched. Callers still clip with
    ``clip_fixture_dates_for_plan``.
    """
    return [today - timedelta(days=1), today]


def official_sync_busy() -> bool:
    """True while any full / odds-light / results batch holds the official lock."""
    return _sync_lock.locked()


async def missing_subscribed_fixture_days(
    today: date,
    *,
    lookahead_days: int,
) -> list[date]:
    """Missing official days in the rolling 8-day local schedule window.

    Existing future days are not fetched again. A successful empty-day response
    is still considered known through its persisted API snapshot.
    """
    window = max(1, min(int(lookahead_days), 14))
    wanted = [today + timedelta(days=offset) for offset in range(1, window)]
    if not wanted:
        return []

    start = datetime.combine(wanted[0], datetime.min.time())
    end = datetime.combine(wanted[-1] + timedelta(days=1), datetime.min.time())
    keys = {fixtures_cache_key(day.isoformat()): day for day in wanted}
    async with AsyncSessionLocal() as session:
        fixture_days = {
            date.fromisoformat(str(value))
            for (value,) in (
                await session.execute(
                    select(func.date(Fixture.date))
                    .where(Fixture.date >= start, Fixture.date < end)
                    .distinct()
                )
            ).all()
            if value
        }
        snapshot_keys = {
            str(value)
            for (value,) in (
                await session.execute(
                    select(ApiSnapshot.cache_key).where(
                        ApiSnapshot.cache_key.in_(list(keys))
                    )
                )
            ).all()
        }
    known = fixture_days | {keys[key] for key in snapshot_keys if key in keys}
    return [day for day in wanted if day not in known]


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


async def scheduled_fixtures_sync(
    *,
    mode: str = "full",
    fixture_ids: list[int] | None = None,
) -> dict:
    """Run a full, light-odds, results, or explicit prematch odds batch."""
    if _sync_lock.locked():
        logger.info("Scheduled fixtures sync already running; skipping overlap")
        return {"status": "skipped", "reason": "locked", "mode": mode}
    if mode not in {"full", "odds", "results", "prematch_odds"}:
        raise ValueError(f"Unknown sync mode: {mode}")

    settings = get_settings()
    today = datetime.now(ZoneInfo(settings.SCHEDULER_TIMEZONE)).date()
    free_quota, _ = await get_enable_free_quota()
    subscribed = not free_quota
    primary_league_ids, _ = await get_hot_league_ids()
    odds_league_ids, _ = await get_catalog_league_ids()
    tomorrow = today + timedelta(days=1)
    future_odds_days = [
        today + timedelta(days=offset)
        for offset in range(1, FULL_BATCH_FUTURE_ODDS_DAYS + 1)
    ]
    result_days = clip_fixture_dates_for_plan(
        result_days_for_batch(today),
        today,
    )

    async with _sync_lock:
        async with FootballFetcher() as fetcher:
            results_saved = 0
            fixtures_saved = 0
            odds_updated = 0
            prematch_odds_stats: dict[str, int | str | None] = {}
            standings_stats = {
                "leagues": 0,
                "fetched": 0,
                "skipped": 0,
                "failed": 0,
            }

            if mode == "prematch_odds":
                if not fetcher.quota_exhausted:
                    prematch_odds_stats = (
                        await fetcher.sync_odds_for_prematch_fixtures(
                            fixture_ids or []
                        )
                    )
                    odds_updated = int(prematch_odds_stats.get("updated") or 0)
                logger.info(
                    "scheduled_fixtures_sync prematch-odds stats=%s",
                    prematch_odds_stats,
                )
            elif mode == "results":
                if result_days and not fetcher.quota_exhausted:
                    results_saved = await fetcher.capture_finished_results(
                        on_days=result_days,
                        today=today,
                    )
                logger.info(
                    "scheduled_fixtures_sync results-only subscribed=%s day=%s",
                    subscribed,
                    today,
                )
            elif mode == "odds":
                if not fetcher.quota_exhausted:
                    odds_updated = await fetcher.sync_odds_for_dates(
                        [today],
                        refresh_existing=True,
                        league_ids=odds_league_ids,
                        budget=(
                            SUBSCRIBED_LIGHT_ODDS_BUDGET
                            if subscribed
                            else FREE_QUOTA_EVENING_ODDS_BUDGET
                        ),
                    )
                logger.info(
                    "scheduled_fixtures_sync odds-light subscribed=%s day=%s",
                    subscribed,
                    today,
                )
            else:
                # 1) Results first — one worldwide date= call per day, then labels.
                if result_days and not fetcher.quota_exhausted:
                    results_saved = await fetcher.capture_finished_results(
                        on_days=result_days,
                        today=today,
                    )

                # 2) Free plan refreshes today. Subscription keeps a rolling
                # 8-day window but only requests future days not already known.
                fixture_days = (
                    [today]
                    if free_quota
                    else await missing_subscribed_fixture_days(
                        today,
                        lookahead_days=settings.FIXTURES_LOOKAHEAD_DAYS,
                    )
                )
                for fixture_day in fixture_days:
                    if fetcher.quota_exhausted:
                        break
                    fixtures_saved += await fetcher.fetch_fixtures_for_date(
                        fixture_day,
                        force=True,
                        league_ids=None,
                    )

                # 3) Future three days only fill missing boards; the first
                # successful pull freezes opening. Existing future boards stay untouched.
                if subscribed and not fetcher.quota_exhausted:
                    odds_updated += await fetcher.sync_odds_for_dates(
                        future_odds_days,
                        refresh_existing=False,
                        league_ids=odds_league_ids,
                        budget=SUBSCRIBED_LIGHT_ODDS_BUDGET,
                    )
                if not fetcher.quota_exhausted:
                    odds_updated += await fetcher.sync_odds_for_dates(
                        [today],
                        refresh_existing=True,
                        league_ids=odds_league_ids,
                        budget=(
                            SUBSCRIBED_LIGHT_ODDS_BUDGET
                            if subscribed
                            else FREE_QUOTA_EVENING_ODDS_BUDGET
                        ),
                    )

                # 4) Subscription standings only. Details stay today/tomorrow;
                # odds already covered today plus the next three days above.
                if subscribed and not fetcher.quota_exhausted:
                    standings_stats = await sync_league_standings_for_dates(
                        fetcher,
                        [today, tomorrow],
                        league_ids=primary_league_ids,
                    )
                elif free_quota:
                    logger.info(
                        "scheduled_fixtures_sync: skipping standings "
                        "(unsubscribed mode prioritizes fixtures/odds)"
                    )

        detail_stats: dict = {"enabled": subscribed}
        if mode == "full" and subscribed:
            try:
                from app.services.scheduled_detail_enrich import run_scheduled_full_detail_enrich

                detail_stats.update(
                    await run_scheduled_full_detail_enrich(
                        before=datetime.combine(
                            tomorrow + timedelta(days=1),
                            datetime.min.time(),
                            tzinfo=ZoneInfo(settings.SCHEDULER_TIMEZONE),
                        )
                        .astimezone(timezone.utc)
                        .replace(tzinfo=None),
                    )
                )
            except Exception as exc:
                logger.warning(
                    "scheduled_fixtures_sync subscribed detail enrich skipped: %s",
                    exc,
                )
                detail_stats["error"] = str(exc)

        if mode == "full":
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
        # Results-only does not touch boards, so skip the pick rewrite.
        if mode != "results":
            try:
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
        "odds_updated=%s standings=%s detail=%s mode=%s",
        fixtures_saved,
        results_saved,
        odds_updated,
        standings_stats,
        detail_stats,
        mode,
    )
    return {
        "status": "completed",
        "mode": mode,
        "fixtures_saved": fixtures_saved,
        "results_saved": results_saved,
        "odds_updated": odds_updated,
        "prematch_odds": prematch_odds_stats,
        "standings": standings_stats,
        "detail": detail_stats,
    }
