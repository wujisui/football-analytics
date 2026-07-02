import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.models.fixture import Fixture
from app.models.league import League
from app.models.pre_match_data import PreMatchData
from app.services.analyzer import AnalyzerService
from app.services.api_utils import extract_items, first_value, map_fixture_status
from app.services.fetcher import FootballFetcher

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()
active_tasks: dict[str, dict[str, Any]] = {}
active_fixtures: set[int] = set()
_scheduler_started = False


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _set_task_status(name: str, status: str, **extra: Any) -> None:
    active_tasks[name] = {
        "status": status,
        "updated_at": _utc_now().isoformat(),
        **extra,
    }


def get_task_status() -> dict[str, Any]:
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append(
            {
                "id": job.id,
                "name": job.name,
                "next_run_time": (
                    job.next_run_time.isoformat() if job.next_run_time else None
                ),
                "trigger": str(job.trigger),
            }
        )

    return {
        "scheduler_running": _scheduler_started,
        "active_tasks": active_tasks,
        "active_fixtures": sorted(active_fixtures),
        "jobs": jobs,
    }


async def daily_init() -> None:
    settings = get_settings()
    task_name = "daily_init"
    _set_task_status(task_name, "running", started_at=_utc_now().isoformat())
    logger.info("Task daily_init started.")

    try:
        async with FootballFetcher() as fetcher:
            league_ids = list(settings.LEAGUE_IDS.values())
            await fetcher.fetch_leagues(league_ids)

            async with AsyncSessionLocal() as session:
                result = await session.execute(select(League).where(League.id.in_(league_ids)))
                leagues = result.scalars().all()

            for league in leagues:
                try:
                    await fetcher.fetch_teams_by_league(league.id, league.season)
                except Exception as exc:
                    logger.error(
                        "daily_init failed to fetch teams for league %s: %s",
                        league.id,
                        exc,
                        exc_info=True,
                    )

            saved = await fetcher.fetch_today_fixtures()
            _set_task_status(
                task_name,
                "completed",
                fixtures_saved=saved,
                finished_at=_utc_now().isoformat(),
            )
            logger.info("Task daily_init completed. fixtures_saved=%s", saved)
    except Exception as exc:
        _set_task_status(task_name, "failed", error=str(exc), finished_at=_utc_now().isoformat())
        logger.error("Task daily_init failed: %s", exc, exc_info=True)


async def pre_match_update() -> None:
    settings = get_settings()
    task_name = "pre_match_update"
    _set_task_status(task_name, "running", started_at=_utc_now().isoformat())
    logger.info("Task pre_match_update started.")

    now = _utc_now().replace(tzinfo=None)
    window_end = now + timedelta(hours=settings.PRE_MATCH_WINDOW_HOURS)
    updated = 0
    errors = 0

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Fixture).where(
                    Fixture.status == "pending",
                    Fixture.date >= now,
                    Fixture.date <= window_end,
                )
            )
            fixtures = result.scalars().all()

        if not fixtures:
            _set_task_status(
                task_name,
                "completed",
                updated=0,
                message="No pending fixtures in pre-match window.",
                finished_at=_utc_now().isoformat(),
            )
            logger.info("Task pre_match_update completed. No fixtures in window.")
            return

        async with FootballFetcher() as fetcher:
            for fixture in fixtures:
                if fixture.id in active_fixtures:
                    logger.info("Skipping fixture %s, update already in progress.", fixture.id)
                    continue

                active_fixtures.add(fixture.id)
                try:
                    payload = await fetcher.fetch_fixture_details(fixture.id)
                    items = extract_items(payload)
                    item = items[0] if items else {}
                    new_status = map_fixture_status(
                        first_value(item, [["fixture", "status", "short"], ["status", "short"]])
                    )

                    async with AsyncSessionLocal() as session:
                        db_fixture = await session.get(Fixture, fixture.id)
                        if db_fixture is not None and new_status:
                            db_fixture.status = new_status
                            await session.commit()

                        if new_status == "live":
                            logger.info(
                                "Fixture %s is live, skipping further pre-match updates.",
                                fixture.id,
                            )
                            continue

                        analyzer = AnalyzerService(session)
                        await analyzer.analyze_fixture(fixture.id)
                        updated += 1
                except Exception as exc:
                    errors += 1
                    logger.error(
                        "pre_match_update failed for fixture %s: %s",
                        fixture.id,
                        exc,
                        exc_info=True,
                    )
                finally:
                    active_fixtures.discard(fixture.id)

        _set_task_status(
            task_name,
            "completed",
            updated=updated,
            errors=errors,
            finished_at=_utc_now().isoformat(),
        )
        logger.info(
            "Task pre_match_update completed. updated=%s errors=%s",
            updated,
            errors,
        )
    except Exception as exc:
        _set_task_status(task_name, "failed", error=str(exc), finished_at=_utc_now().isoformat())
        logger.error("Task pre_match_update failed: %s", exc, exc_info=True)


async def clean_old_data() -> None:
    settings = get_settings()
    task_name = "clean_old_data"
    _set_task_status(task_name, "running", started_at=_utc_now().isoformat())
    logger.info("Task clean_old_data started.")

    cutoff = _utc_now().replace(tzinfo=None) - timedelta(days=settings.CLEANUP_DAYS)
    deleted_analysis = 0
    removed_logs = 0

    try:
        async with AsyncSessionLocal() as session:
            old_fixtures = await session.execute(
                select(Fixture.id).where(
                    Fixture.date < cutoff,
                    Fixture.status.in_(["finished", "cancelled", "postponed"]),
                )
            )
            fixture_ids = [row[0] for row in old_fixtures.all()]

            if fixture_ids:
                result = await session.execute(
                    delete(PreMatchData).where(PreMatchData.fixture_id.in_(fixture_ids))
                )
                deleted_analysis = result.rowcount or 0
                await session.commit()

        log_dir = Path(settings.LOG_DIR)
        if log_dir.exists():
            for log_file in log_dir.glob("football-analytics.log.*"):
                try:
                    mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                    if mtime < cutoff:
                        log_file.unlink(missing_ok=True)
                        removed_logs += 1
                except OSError as exc:
                    logger.warning("Failed to remove log file %s: %s", log_file, exc)

        _set_task_status(
            task_name,
            "completed",
            deleted_analysis=deleted_analysis,
            removed_logs=removed_logs,
            finished_at=_utc_now().isoformat(),
        )
        logger.info(
            "Task clean_old_data completed. deleted_analysis=%s removed_logs=%s",
            deleted_analysis,
            removed_logs,
        )
    except Exception as exc:
        _set_task_status(task_name, "failed", error=str(exc), finished_at=_utc_now().isoformat())
        logger.error("Task clean_old_data failed: %s", exc, exc_info=True)


TASK_HANDLERS = {
    "daily_init": daily_init,
    "pre_match_update": pre_match_update,
    "clean_old_data": clean_old_data,
}


async def trigger_task(task_name: str) -> None:
    handler = TASK_HANDLERS.get(task_name)
    if handler is None:
        raise ValueError(f"Unknown task: {task_name}")
    await handler()


def register_jobs() -> None:
    settings = get_settings()
    timezone = settings.SCHEDULER_TIMEZONE

    if scheduler.get_job("daily_init") is None:
        scheduler.add_job(
            daily_init,
            CronTrigger(hour=6, minute=0, timezone=timezone),
            id="daily_init",
            name="daily_init",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    if scheduler.get_job("pre_match_update") is None:
        scheduler.add_job(
            pre_match_update,
            IntervalTrigger(minutes=5),
            id="pre_match_update",
            name="pre_match_update",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    if scheduler.get_job("clean_old_data") is None:
        scheduler.add_job(
            clean_old_data,
            CronTrigger(day_of_week="mon", hour=3, minute=0, timezone=timezone),
            id="clean_old_data",
            name="clean_old_data",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )


def start_scheduler() -> None:
    global _scheduler_started
    if _scheduler_started:
        return

    register_jobs()
    scheduler.start()
    _scheduler_started = True

    for job in scheduler.get_jobs():
        logger.info(
            "Registered scheduler job: id=%s trigger=%s next_run=%s",
            job.id,
            job.trigger,
            job.next_run_time,
        )


def shutdown_scheduler() -> None:
    global _scheduler_started
    if not _scheduler_started:
        return

    scheduler.shutdown(wait=False)
    _scheduler_started = False
    logger.info("Scheduler shut down.")
