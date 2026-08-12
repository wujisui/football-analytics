import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.models.fixture import Fixture
from app.models.pre_match_data import PreMatchData
from app.services.data_cleanup import prune_low_value_data
from app.services.fixtures_sync import scheduled_fixtures_sync

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()
active_tasks: dict[str, dict[str, Any]] = {}
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
        "jobs": jobs,
    }


async def run_scheduled_fixtures_sync(task_name: str = "scheduled_fixtures_sync") -> None:
    """Run one fixed daily fixtures/odds/results synchronization batch."""
    _set_task_status(task_name, "running", started_at=_utc_now().isoformat())
    logger.info("Task %s started.", task_name)
    try:
        await scheduled_fixtures_sync()
        _set_task_status(task_name, "completed", finished_at=_utc_now().isoformat())
        logger.info("Task %s completed.", task_name)
    except Exception as exc:
        _set_task_status(
            task_name,
            "failed",
            error=str(exc),
            finished_at=_utc_now().isoformat(),
        )
        logger.error("Task %s failed: %s", task_name, exc, exc_info=True)


async def clean_old_data() -> None:
    settings = get_settings()
    task_name = "clean_old_data"
    _set_task_status(task_name, "running", started_at=_utc_now().isoformat())
    logger.info("Task clean_old_data started.")

    cutoff = _utc_now().replace(tzinfo=None) - timedelta(days=settings.CLEANUP_DAYS)
    deleted_analysis = 0
    removed_logs = 0
    prune_report: dict[str, Any] = {}

    try:
        async with AsyncSessionLocal() as session:
            prune_report = (await prune_low_value_data(session, apply=True)).to_dict()
            old_fixtures = await session.execute(
                select(Fixture.id).where(
                    Fixture.date < cutoff,
                    Fixture.status.in_(["finished", "cancelled", "postponed"]),
                )
            )
            fixture_ids = [row[0] for row in old_fixtures.all()]

            if fixture_ids:
                # Keep match_features for ML training; only drop display analysis JSON.
                result = await session.execute(
                    delete(PreMatchData).where(PreMatchData.fixture_id.in_(fixture_ids))
                )
                deleted_analysis = result.rowcount or 0
                await session.commit()

            if prune_report.get("features_deleted"):
                from app.services.ah_predictor import (
                    train_model_from_db as train_ah_model_from_db,
                )
                from app.services.goal_predictor import (
                    train_model_from_db as train_goal_model_from_db,
                )
                from app.services.ml_predictor import train_model_from_db

                await train_model_from_db(session)
                await train_ah_model_from_db(session)
                await train_goal_model_from_db(session)

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
            prune=prune_report,
            removed_logs=removed_logs,
            finished_at=_utc_now().isoformat(),
        )
        logger.info(
            "Task clean_old_data completed. deleted_analysis=%s prune=%s removed_logs=%s",
            deleted_analysis,
            prune_report,
            removed_logs,
        )
    except Exception as exc:
        _set_task_status(task_name, "failed", error=str(exc), finished_at=_utc_now().isoformat())
        logger.error("Task clean_old_data failed: %s", exc, exc_info=True)


async def train_model() -> None:
    """Manual / scheduled: backfill features + train if enough labeled rows."""
    task_name = "train_model"
    _set_task_status(task_name, "running", started_at=_utc_now().isoformat())
    logger.info("Task train_model started.")
    try:
        from app.services.ml_predictor import maybe_auto_train_model, model_status

        # Force attempt even if ML_AUTO_TRAIN is false when manually triggered:
        # temporarily rely on train_model_from_db via maybe with auto flag check.
        from app.core.config import get_settings
        from app.core.database import AsyncSessionLocal
        from app.services.ml_predictor import train_model_from_db

        settings = get_settings()
        async with AsyncSessionLocal() as session:
            if settings.ML_AUTO_TRAIN:
                result = await maybe_auto_train_model(session)
                # maybe skips when no new labels; manual task should still refit if enough.
                if result.get("skipped") and result.get("reason") == "no_new_labels":
                    result = await train_model_from_db(session)
            else:
                result = await train_model_from_db(session)

        status = model_status()
        _set_task_status(
            task_name,
            "completed",
            train=result,
            model_status=status,
            finished_at=_utc_now().isoformat(),
        )
        logger.info("Task train_model completed. result=%s status=%s", result.get("ok"), status)
    except Exception as exc:
        _set_task_status(task_name, "failed", error=str(exc), finished_at=_utc_now().isoformat())
        logger.error("Task train_model failed: %s", exc, exc_info=True)


async def run_daily_auto_favorites() -> None:
    """Manual/admin trigger: refresh auto favorites (also runs after each sync)."""
    task_name = "daily_auto_favorites"
    _set_task_status(task_name, "running", started_at=_utc_now().isoformat())
    logger.info("Task %s started.", task_name)
    try:
        from app.services.auto_favorites import sync_daily_auto_favorites

        async with AsyncSessionLocal() as session:
            result = await sync_daily_auto_favorites(session)
        _set_task_status(
            task_name,
            "completed",
            result=result,
            finished_at=_utc_now().isoformat(),
        )
        logger.info(
            "Task %s completed. selected=%s",
            task_name,
            len(result.get("selected") or []),
        )
    except Exception as exc:
        _set_task_status(
            task_name,
            "failed",
            error=str(exc),
            finished_at=_utc_now().isoformat(),
        )
        logger.error("Task %s failed: %s", task_name, exc, exc_info=True)


TASK_HANDLERS = {
    "scheduled_fixtures_sync": run_scheduled_fixtures_sync,
    "clean_old_data": clean_old_data,
    "train_model": train_model,
    "daily_auto_favorites": run_daily_auto_favorites,
}


async def trigger_task(task_name: str) -> None:
    handler = TASK_HANDLERS.get(task_name)
    if handler is None:
        raise ValueError(f"Unknown task: {task_name}")
    await handler()


def register_jobs() -> None:
    settings = get_settings()
    timezone = settings.SCHEDULER_TIMEZONE

    # Remove legacy 06:00 daily_init if still registered from an older process.
    if scheduler.get_job("daily_init") is not None:
        scheduler.remove_job("daily_init")
    for hour in (0, 6, 11, 16, 19, 22):
        job_id = f"scheduled_fixtures_sync_{hour:02d}"
        if scheduler.get_job(job_id) is None:
            scheduler.add_job(
                run_scheduled_fixtures_sync,
                CronTrigger(hour=hour, minute=0, timezone=timezone),
                id=job_id,
                name=job_id,
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )

    # Auto favorites refresh inside scheduled_fixtures_sync after odds update.
    if scheduler.get_job("daily_auto_favorites") is not None:
        scheduler.remove_job("daily_auto_favorites")

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
