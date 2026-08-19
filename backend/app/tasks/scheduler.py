import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.services.api_quota import FREE_QUOTA_EVENING_HOUR
from app.services.data_cleanup import prune_low_value_data, slim_expired_packages
from app.services.fixtures_sync import scheduled_fixtures_sync
from app.services.runtime_settings import get_enable_free_quota

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()
active_tasks: dict[str, dict[str, Any]] = {}
_scheduler_started = False

# Paid / full schedule vs free-quota mode (admin toggle, default ON).
SYNC_HOURS_FULL = (0, 6, 11, 16, 19, 22)
# 11:00 = full free batch (results + today fixtures/odds); 22:00 = odds refresh only.
SYNC_HOURS_FREE_QUOTA = (11, FREE_QUOTA_EVENING_HOUR)
FREE_QUOTA_SYNC_HOUR = 11


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


def _should_clean_after_sync(sync_hour: int | None) -> bool:
    """Run low-value cleanup with the morning full batch (11:00 / admin「立即同步」).

    Skip evening odds-light (22:00) and other free-quota-off slots so prune/retrain
    does not run multiple times a day.
    """
    return sync_hour is None or int(sync_hour) == 11


async def run_scheduled_fixtures_sync(
    task_name: str = "scheduled_fixtures_sync",
    *,
    sync_hour: int | None = None,
) -> None:
    """Run one fixed daily fixtures/odds/results synchronization batch."""
    from app.services.fetcher import ApiAccountBlockedError, ApiKeyNotConfiguredError

    _set_task_status(task_name, "running", started_at=_utc_now().isoformat())
    logger.info("Task %s started (sync_hour=%s).", task_name, sync_hour)
    try:
        await scheduled_fixtures_sync(sync_hour=sync_hour)
        _set_task_status(task_name, "completed", finished_at=_utc_now().isoformat())
        logger.info("Task %s completed.", task_name)
        if _should_clean_after_sync(sync_hour):
            await clean_old_data()
    except ApiAccountBlockedError as exc:
        # Known account state, not a code fault: no traceback, but never "completed".
        _set_task_status(
            task_name,
            "failed",
            error=str(exc),
            finished_at=_utc_now().isoformat(),
        )
        logger.error("Task %s failed: %s", task_name, exc)
    except ApiKeyNotConfiguredError as exc:
        # Deploy may start without keys; admin configures later. Do not crash the process.
        _set_task_status(
            task_name,
            "skipped",
            error=str(exc),
            finished_at=_utc_now().isoformat(),
        )
        logger.warning(
            "Task %s skipped (no API key): %s. "
            "Configure via Mine admin or: python manage.py set-api-sports-key …",
            task_name,
            exc,
        )
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
    slimmed_packages = 0
    removed_logs = 0
    prune_report: dict[str, Any] = {}

    try:
        async with AsyncSessionLocal() as session:
            prune_report = (await prune_low_value_data(session, apply=True)).to_dict()
            slimmed_packages = await slim_expired_packages(session, cutoff=cutoff)

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
            slimmed_packages=slimmed_packages,
            prune=prune_report,
            removed_logs=removed_logs,
            finished_at=_utc_now().isoformat(),
        )
        logger.info(
            "Task clean_old_data completed. slimmed_packages=%s prune=%s removed_logs=%s",
            slimmed_packages,
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


def register_jobs(*, free_quota: bool | None = None) -> None:
    """Register cron jobs. Free-quota mode keeps 11:00 full + 22:00 odds refresh."""
    settings = get_settings()
    timezone = settings.SCHEDULER_TIMEZONE
    if free_quota is None:
        free_quota = bool(settings.ENABLE_FREE_QUOTA)
    sync_hours = SYNC_HOURS_FREE_QUOTA if free_quota else SYNC_HOURS_FULL

    # Remove legacy 06:00 daily_init if still registered from an older process.
    if scheduler.get_job("daily_init") is not None:
        scheduler.remove_job("daily_init")

    # Drop every fixtures-sync slot first so toggling free-quota rewrites cron.
    for hour in SYNC_HOURS_FULL:
        job_id = f"scheduled_fixtures_sync_{hour:02d}"
        if scheduler.get_job(job_id) is not None:
            scheduler.remove_job(job_id)

    for hour in sync_hours:
        job_id = f"scheduled_fixtures_sync_{hour:02d}"
        scheduler.add_job(
            run_scheduled_fixtures_sync,
            CronTrigger(hour=hour, minute=0, timezone=timezone),
            id=job_id,
            name=job_id,
            kwargs={"sync_hour": hour},
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    # Auto favorites refresh inside scheduled_fixtures_sync after odds update.
    if scheduler.get_job("daily_auto_favorites") is not None:
        scheduler.remove_job("daily_auto_favorites")

    # Low-value cleanup runs after the 11:00 full sync (and admin「立即同步」),
    # not as a separate Monday 03:00 cron — machines often off overnight.
    if scheduler.get_job("clean_old_data") is not None:
        scheduler.remove_job("clean_old_data")


async def refresh_fixture_sync_jobs() -> bool:
    """Re-read free-quota flag from DB/env and rewrite fixtures-sync cron slots."""
    enabled, source = await get_enable_free_quota()
    register_jobs(free_quota=enabled)
    if _scheduler_started:
        for job in scheduler.get_jobs():
            if str(job.id).startswith("scheduled_fixtures_sync_"):
                logger.info(
                    "Refreshed scheduler job: id=%s trigger=%s next_run=%s "
                    "(free_quota=%s source=%s)",
                    job.id,
                    job.trigger,
                    job.next_run_time,
                    enabled,
                    source,
                )
    return enabled


def free_quota_catch_up_due(now: datetime | None = None) -> bool:
    """True when local clock is past today's 11:00 free-quota sync slot."""
    settings = get_settings()
    tz = ZoneInfo(settings.SCHEDULER_TIMEZONE)
    local_now = now or datetime.now(tz)
    if local_now.tzinfo is None:
        local_now = local_now.replace(tzinfo=tz)
    else:
        local_now = local_now.astimezone(tz)
    return (local_now.hour, local_now.minute) > (FREE_QUOTA_SYNC_HOUR, 0)


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
