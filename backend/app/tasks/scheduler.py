import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.services.data_cleanup import prune_low_value_data, slim_expired_packages
from app.services.fixtures_sync import (
    scheduled_fixtures_sync,
    sync_free_quota_rollover_fixtures,
)
from app.services.cache import get_cache_service
from app.services.runtime_settings import (
    get_last_full_sync_day,
    get_subscription_early_odds,
    get_subscription_enabled,
    set_last_full_sync_day,
    set_last_sync_run,
)

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()
active_tasks: dict[str, dict[str, Any]] = {}
_scheduler_started = False

FULL_SYNC_HOUR = 11
UNSUBSCRIBED_ODDS_HOURS = (22,)
# Hourly light odds outside the 21:00–24:00 half-hour window.
SUBSCRIBED_ODDS_HOURS = (2, 14, 16, 18, 20)
SUBSCRIBED_EARLY_ODDS_HOURS = (4, 6, 8, 10)
SUBSCRIBED_FIRST_ODDS_MINUTE = 55
# 21:00 through 24:00 (00:00) every 30 minutes; subscribed only.
SUBSCRIBED_EVENING_ODDS_SLOTS: tuple[tuple[int, int], ...] = (
    (21, 0),
    (21, 30),
    (22, 0),
    (22, 30),
    (23, 0),
    (23, 30),
    (0, 0),
)
FREE_QUOTA_ROLLOVER_JOB_ID = "free_quota_fixture_rollover"
RESULTS_SYNC_TASK = "scheduled_results_sync"


def odds_job_id(hour: int, minute: int = 0) -> str:
    if minute:
        return f"scheduled_fixtures_sync_odds_{hour:02d}{minute:02d}"
    return f"scheduled_fixtures_sync_odds_{hour:02d}"


def subscribed_light_odds_slots(*, early_odds: bool) -> list[tuple[int, int]]:
    slots = [(hour, 0) for hour in SUBSCRIBED_ODDS_HOURS]
    if early_odds:
        slots.extend((hour, 0) for hour in SUBSCRIBED_EARLY_ODDS_HOURS)
    slots.extend(SUBSCRIBED_EVENING_ODDS_SLOTS)
    slots.append((FULL_SYNC_HOUR, SUBSCRIBED_FIRST_ODDS_MINUTE))
    return sorted(set(slots), key=lambda item: (item[0], item[1]))


def format_clock(hour: int, minute: int = 0) -> str:
    return f"{hour:02d}:{minute:02d}"


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


def scheduler_today() -> str:
    settings = get_settings()
    return datetime.now(ZoneInfo(settings.SCHEDULER_TIMEZONE)).date().isoformat()


async def full_sync_completed_today() -> bool:
    return await get_last_full_sync_day() == scheduler_today()


async def _record_sync_run(task_name: str, mode: str, start_count: int) -> None:
    """Persist a finished official batch so the admin page can show 上次同步.

    Skipped batches (already synced today, no key) burn no quota and must not
    overwrite the last real run.
    """
    entry = active_tasks.get(task_name) or {}
    status = entry.get("status")
    if status not in {"completed", "failed"}:
        return
    cache = get_cache_service()
    run: dict[str, Any] = {
        "task": task_name,
        "mode": mode,
        "status": status,
        "finished_at": entry.get("finished_at") or _utc_now().isoformat(),
        "quota_used": max(cache.api_request_count - start_count, 0),
        "api_remaining": cache.last_api_remaining,
    }
    error = entry.get("error")
    if error:
        run["error"] = str(error)[:300]
    try:
        async with AsyncSessionLocal() as session:
            await set_last_sync_run(session, run)
    except Exception as exc:
        logger.warning("Failed to persist last sync run for %s: %s", task_name, exc)


async def run_scheduled_fixtures_sync(
    task_name: str = "scheduled_fixtures_sync",
    *,
    mode: str = "full",
) -> None:
    """Run the daily full batch or a today's-hot-odds light batch."""
    from app.services.fetcher import ApiAccountBlockedError, ApiKeyNotConfiguredError

    _set_task_status(task_name, "running", started_at=_utc_now().isoformat())
    logger.info("Task %s started (mode=%s).", task_name, mode)
    start_count = get_cache_service().api_request_count
    try:
        if mode == "full" and await full_sync_completed_today():
            _set_task_status(
                task_name,
                "skipped",
                reason="full_sync_completed_today",
                finished_at=_utc_now().isoformat(),
            )
            logger.info("Task %s skipped: full batch already completed today.", task_name)
            return
        result = await scheduled_fixtures_sync(mode=mode)
        if result.get("status") != "completed":
            _set_task_status(
                task_name,
                "skipped",
                reason=result.get("reason", "sync_not_completed"),
                finished_at=_utc_now().isoformat(),
            )
            return
        if mode == "full":
            async with AsyncSessionLocal() as session:
                await set_last_full_sync_day(session, scheduler_today())
        if mode == "full":
            await clean_old_data()
        _set_task_status(
            task_name,
            "completed",
            mode=mode,
            result=result,
            finished_at=_utc_now().isoformat(),
        )
        logger.info("Task %s completed.", task_name)
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
    finally:
        await _record_sync_run(task_name, mode, start_count)


async def run_scheduled_results_sync() -> None:
    """Admin-only FT backfill; does not consume the day's full-batch slot."""
    await run_scheduled_fixtures_sync(task_name=RESULTS_SYNC_TASK, mode="results")


async def run_free_quota_fixture_rollover() -> None:
    """One-call UTC-day schedule ingest; no odds or enrichment."""
    from app.services.fetcher import ApiAccountBlockedError, ApiKeyNotConfiguredError

    task_name = FREE_QUOTA_ROLLOVER_JOB_ID
    _set_task_status(task_name, "running", started_at=_utc_now().isoformat())
    start_count = get_cache_service().api_request_count
    try:
        saved = await sync_free_quota_rollover_fixtures()
        _set_task_status(
            task_name,
            "completed",
            fixtures_saved=saved,
            finished_at=_utc_now().isoformat(),
        )
    except (ApiAccountBlockedError, ApiKeyNotConfiguredError) as exc:
        _set_task_status(
            task_name,
            "skipped",
            error=str(exc),
            finished_at=_utc_now().isoformat(),
        )
        logger.warning("Task %s skipped: %s", task_name, exc)
    except Exception as exc:
        _set_task_status(
            task_name,
            "failed",
            error=str(exc),
            finished_at=_utc_now().isoformat(),
        )
        logger.error("Task %s failed: %s", task_name, exc, exc_info=True)
    finally:
        await _record_sync_run(task_name, "fixtures", start_count)


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
    RESULTS_SYNC_TASK: run_scheduled_results_sync,
    "clean_old_data": clean_old_data,
    "train_model": train_model,
    "daily_auto_favorites": run_daily_auto_favorites,
}


async def trigger_task(task_name: str) -> None:
    handler = TASK_HANDLERS.get(task_name)
    if handler is None:
        raise ValueError(f"Unknown task: {task_name}")
    await handler()


def register_jobs(
    *,
    subscribed: bool | None = None,
    early_odds: bool = True,
) -> None:
    """Register one 11:00 full batch plus subscription-specific light jobs."""
    settings = get_settings()
    timezone = settings.SCHEDULER_TIMEZONE
    if subscribed is None:
        subscribed = not bool(settings.ENABLE_FREE_QUOTA)

    for job in list(scheduler.get_jobs()):
        if str(job.id).startswith("scheduled_fixtures_sync_"):
            scheduler.remove_job(job.id)

    full_job_id = "scheduled_fixtures_sync_11"
    scheduler.add_job(
        run_scheduled_fixtures_sync,
        CronTrigger(hour=FULL_SYNC_HOUR, minute=0, timezone=timezone),
        id=full_job_id,
        name=full_job_id,
        kwargs={"mode": "full"},
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    odds_slots: list[tuple[int, int]]
    if subscribed:
        odds_slots = subscribed_light_odds_slots(early_odds=early_odds)
    else:
        odds_slots = [(hour, 0) for hour in UNSUBSCRIBED_ODDS_HOURS]
    for hour, minute in odds_slots:
        job_id = odds_job_id(hour, minute)
        scheduler.add_job(
            run_scheduled_fixtures_sync,
            CronTrigger(hour=hour, minute=minute, timezone=timezone),
            id=job_id,
            name=job_id,
            kwargs={"task_name": job_id, "mode": "odds"},
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    if scheduler.get_job(FREE_QUOTA_ROLLOVER_JOB_ID) is not None:
        scheduler.remove_job(FREE_QUOTA_ROLLOVER_JOB_ID)
    if not subscribed:
        scheduler.add_job(
            run_free_quota_fixture_rollover,
            CronTrigger(hour=0, minute=5, timezone="UTC"),
            id=FREE_QUOTA_ROLLOVER_JOB_ID,
            name=FREE_QUOTA_ROLLOVER_JOB_ID,
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
    """Re-read subscription flags and rewrite fixture/odds cron slots."""
    subscribed, source = await get_subscription_enabled()
    early_odds, _ = await get_subscription_early_odds()
    register_jobs(subscribed=subscribed, early_odds=early_odds)
    if _scheduler_started:
        for job in scheduler.get_jobs():
            if str(job.id).startswith("scheduled_fixtures_sync_"):
                logger.info(
                    "Refreshed scheduler job: id=%s trigger=%s next_run=%s "
                    "(subscribed=%s early_odds=%s source=%s)",
                    job.id,
                    job.trigger,
                    job.next_run_time,
                    subscribed,
                    early_odds,
                    source,
                )
    return subscribed


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
