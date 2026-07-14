import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.models.fixture import Fixture
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


async def midday_fixtures_sync() -> None:
    """每天中午：强制从官方拉取近期窗口赛程（对齐首页），并补缺盘口。"""
    settings = get_settings()
    task_name = "midday_fixtures_sync"
    _set_task_status(task_name, "running", started_at=_utc_now().isoformat())
    logger.info("Task midday_fixtures_sync started.")

    try:
        tz = ZoneInfo(settings.SCHEDULER_TIMEZONE)
        today = datetime.now(tz).date()
        window = max(1, min(int(settings.FIXTURES_LOOKAHEAD_DAYS), 14))
        day_list: list[date] = [today + timedelta(days=i) for i in range(window)]

        async with FootballFetcher() as fetcher:
            saved = await fetcher.fetch_fixtures_window(
                day_list[0],
                day_list[-1],
                force=True,
            )
            odds_updated = 0
            try:
                # 中午盘口：缺盘补全；首次有盘记为初盘，已有盘口再同步只动即时盘。
                odds_updated = await fetcher.sync_odds_for_dates(
                    day_list,
                    refresh_existing=False,
                    set_opening=True,
                )
            except Exception as exc:
                logger.warning("midday_fixtures_sync odds gap-fill skipped: %s", exc)
            try:
                await fetcher.capture_finished_results(lookback_days=2)
            except Exception as exc:
                logger.warning("midday_fixtures_sync capture_results skipped: %s", exc)
            try:
                from app.services.ml_predictor import maybe_auto_train_model

                await maybe_auto_train_model()
            except Exception as exc:
                logger.warning("midday_fixtures_sync ML auto-train skipped: %s", exc)

        _set_task_status(
            task_name,
            "completed",
            fixtures_saved=saved,
            odds_updated=odds_updated,
            window_start=day_list[0].isoformat(),
            window_days=window,
            finished_at=_utc_now().isoformat(),
        )
        logger.info(
            "Task midday_fixtures_sync completed. fixtures_saved=%s odds_updated=%s window=%s+%sd",
            saved,
            odds_updated,
            day_list[0],
            window,
        )
    except Exception as exc:
        _set_task_status(
            task_name,
            "failed",
            error=str(exc),
            finished_at=_utc_now().isoformat(),
        )
        logger.error("Task midday_fixtures_sync failed: %s", exc, exc_info=True)


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
                # Keep match_features for ML training; only drop display analysis JSON.
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


async def capture_results() -> None:
    """Backfill FT scores for recently finished fixtures (by calendar date, not live)."""
    task_name = "capture_results"
    _set_task_status(task_name, "running", started_at=_utc_now().isoformat())
    logger.info("Task capture_results started.")

    try:
        async with FootballFetcher() as fetcher:
            saved = await fetcher.capture_finished_results(lookback_days=3)

        # After new FT labels land, try auto-train so inference can switch to ml.
        train_info: dict[str, Any] = {}
        try:
            from app.services.ml_predictor import maybe_auto_train_model

            train_info = await maybe_auto_train_model()
        except Exception as train_exc:
            logger.warning("ML auto-train after capture_results failed: %s", train_exc)
            train_info = {"ok": False, "error": str(train_exc)}

        _set_task_status(
            task_name,
            "completed",
            fixtures_saved=saved,
            ml_train=train_info,
            finished_at=_utc_now().isoformat(),
        )
        logger.info(
            "Task capture_results completed. fixtures_saved=%s ml_train=%s",
            saved,
            train_info.get("reason") or train_info.get("inference") or train_info.get("ok"),
        )
    except Exception as exc:
        _set_task_status(task_name, "failed", error=str(exc), finished_at=_utc_now().isoformat())
        logger.error("Task capture_results failed: %s", exc, exc_info=True)


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


TASK_HANDLERS = {
    "midday_fixtures_sync": midday_fixtures_sync,
    "pre_match_update": pre_match_update,
    "capture_results": capture_results,
    "clean_old_data": clean_old_data,
    "train_model": train_model,
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

    if scheduler.get_job("midday_fixtures_sync") is None:
        scheduler.add_job(
            midday_fixtures_sync,
            CronTrigger(hour=12, minute=0, timezone=timezone),
            id="midday_fixtures_sync",
            name="midday_fixtures_sync",
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

    if scheduler.get_job("capture_results") is None:
        scheduler.add_job(
            capture_results,
            IntervalTrigger(minutes=30),
            id="capture_results",
            name="capture_results",
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
