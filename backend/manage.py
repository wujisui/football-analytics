import argparse
import asyncio
import sys

from app.core.config import load_local_env

load_local_env()


def _setup_cli_logging() -> None:
    from app.core.config import get_settings
    from app.core.logging import setup_logging

    settings = get_settings()
    setup_logging(settings.LOG_LEVEL, settings.LOG_DIR)


async def run_init_db() -> None:
    from app.core.database import init_db

    await init_db()
    print("Database initialized successfully.")


async def run_fetch_leagues() -> None:
    from app.core.config import get_settings
    from app.services.fetcher import ApiKeyNotConfiguredError, FootballFetcher

    settings = get_settings()
    try:
        async with FootballFetcher() as fetcher:
            count = await fetcher.fetch_leagues(list(settings.LEAGUE_IDS.values()))
            print(f"Fetched and saved {count} leagues.")
            if fetcher.last_remaining_requests is not None:
                print(f"Remaining API requests: {fetcher.last_remaining_requests}")
    except ApiKeyNotConfiguredError as exc:
        print(f"Skipped: {exc}")
        sys.exit(1)


async def run_fetch_today() -> None:
    from app.services.fetcher import ApiKeyNotConfiguredError, FootballFetcher

    try:
        async with FootballFetcher() as fetcher:
            count = await fetcher.fetch_today_fixtures()
            print(f"Fetched and saved {count} fixtures for today.")
            if fetcher.last_remaining_requests is not None:
                print(f"Remaining API requests: {fetcher.last_remaining_requests}")
    except ApiKeyNotConfiguredError as exc:
        print(f"Skipped: {exc}")
        sys.exit(1)


async def run_fetch_upcoming(days: int | None) -> None:
    from app.core.config import get_settings
    from app.services.fetcher import ApiKeyNotConfiguredError, FootballFetcher

    settings = get_settings()
    window = days if days is not None else settings.FIXTURES_LOOKAHEAD_DAYS
    try:
        async with FootballFetcher() as fetcher:
            count = await fetcher.fetch_upcoming_fixtures(window)
            print(f"Fetched and saved {count} fixtures for the next {window} day(s).")
            if fetcher.last_remaining_requests is not None:
                print(f"Remaining API requests: {fetcher.last_remaining_requests}")
    except ApiKeyNotConfiguredError as exc:
        print(f"Skipped: {exc}")
        sys.exit(1)


async def run_check_quota() -> None:
    from app.services.fetcher import ApiKeyNotConfiguredError, FootballFetcher

    try:
        async with FootballFetcher() as fetcher:
            remaining = await fetcher.check_quota()
            if remaining is None:
                print("API call succeeded, but remaining quota header was not returned.")
            else:
                print(f"Remaining API requests: {remaining}")
    except ApiKeyNotConfiguredError as exc:
        print(f"Skipped: {exc}")
        sys.exit(1)


async def run_test_api() -> None:
    from app.services.fetcher import ApiKeyNotConfiguredError, FootballFetcher

    try:
        async with FootballFetcher() as fetcher:
            result = await fetcher.test_connection()
            print("API connection test succeeded.")
            print(f"Provider: {result['provider']}")
            print(f"Host: {result['host']}")
            print(f"Remaining requests: {result['remaining_requests']}")
            print(f"Response keys: {result['sample_keys']}")
            print(f"Cache stats: {result['cache_stats']}")
    except ApiKeyNotConfiguredError as exc:
        print(f"Skipped: {exc}")
        sys.exit(1)


async def run_clear_cache() -> None:
    from app.services.cache import get_cache_service

    cache = get_cache_service()
    deleted = await cache.clear_pattern("api:football:*")
    print(f"Cleared {deleted} cache entries.")


async def run_cache_stats() -> None:
    from app.services.cache import get_cache_service

    cache = get_cache_service()
    await cache.connect()
    stats = cache.get_stats()
    print(f"Cache enabled: {stats['cache_enabled']}")
    print(f"Using fakeredis: {stats['using_fakeredis']}")
    print(f"Cache hits: {stats['cache_hits']}")
    print(f"Cache misses: {stats['cache_misses']}")
    print(f"Cache hit rate: {stats['cache_hit_rate']}")
    print(f"Last API remaining: {stats['api_remaining']}")


async def run_list_tasks() -> None:
    from app.tasks.scheduler import get_task_status, register_jobs, scheduler, start_scheduler

    register_jobs()
    if not scheduler.running:
        start_scheduler()

    status = get_task_status()
    print(f"Scheduler running: {status['scheduler_running']}")
    for job in status["jobs"]:
        print(
            f"- {job['id']}: trigger={job['trigger']} next_run={job['next_run_time']}"
        )
    if status["active_tasks"]:
        print("Active task states:")
        for name, info in status["active_tasks"].items():
            print(f"  {name}: {info}")


async def run_trigger_task(task_name: str) -> None:
    from app.tasks.scheduler import get_task_status, trigger_task

    print(f"Triggering task: {task_name}")
    await trigger_task(task_name)
    print("Task finished.")
    print(get_task_status())


async def run_scheduler_loop() -> None:
    from app.tasks import shutdown_scheduler, start_scheduler

    start_scheduler()
    print("Scheduler started. Press Ctrl+C to stop.")
    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        print("Stopping scheduler...")
    finally:
        shutdown_scheduler()


async def run_backfill_features() -> None:
    from app.core.database import AsyncSessionLocal, init_db
    from app.services.ml_predictor import collect_training_rows

    await init_db()
    async with AsyncSessionLocal() as session:
        rows = await collect_training_rows(session)
    print(f"Backfilled / collected {len(rows)} labeled training row(s).")


async def run_train_model() -> None:
    from app.core.database import AsyncSessionLocal, init_db
    from app.services.ml_predictor import (
        MIN_TRAIN_SAMPLES,
        min_train_samples,
        model_status,
        train_model_from_db,
    )

    await init_db()
    threshold = min_train_samples()
    async with AsyncSessionLocal() as session:
        result = await train_model_from_db(session)
    status = model_status()
    if not result.get("ok"):
        print(
            f"Training skipped: {result.get('reason')} "
            f"(need >={threshold} finished fixtures with features; default {MIN_TRAIN_SAMPLES})."
        )
        print(f"Current labeled samples: {result.get('n_samples', 0)}")
        print(f"Current inference mode: {status['inference_mode']}")
        return
    print("Training succeeded — inference will auto-switch to source=ml.")
    print(f"Samples: {result.get('n_samples')}")
    print(f"Val log-loss: {result.get('val_metrics', {}).get('log_loss')}")
    print(f"Val accuracy: {result.get('val_metrics', {}).get('accuracy')}")
    print(f"Weights: {result.get('weights_path')}")
    print(f"Model status: {status}")


async def run_model_status() -> None:
    from app.core.database import AsyncSessionLocal, init_db
    from app.models.match_feature import MatchFeature
    from app.services.ml_predictor import model_status
    from sqlalchemy import func, select

    await init_db()
    status = model_status()
    async with AsyncSessionLocal() as session:
        total = await session.scalar(select(func.count()).select_from(MatchFeature))
        labeled = await session.scalar(
            select(func.count()).select_from(MatchFeature).where(MatchFeature.label.is_not(None))
        )
    print(f"inference_mode: {status['inference_mode']}")
    print(f"artifact_ready: {status['artifact_ready']}")
    print(f"trained_n_samples: {status['trained_n_samples']}")
    print(f"min_train_samples: {status['min_train_samples']}")
    print(f"match_features_total: {total or 0}")
    print(f"match_features_labeled: {labeled or 0}")
    print(f"trained_at: {status.get('trained_at')}")


def main() -> None:
    _setup_cli_logging()

    parser = argparse.ArgumentParser(description="Football Analytics management CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db", help="Initialize database tables")
    subparsers.add_parser("fetch-leagues", help="Fetch configured leagues from API-Football")
    subparsers.add_parser("fetch-today", help="Fetch today's fixtures from API-Football")
    upcoming_parser = subparsers.add_parser(
        "fetch-upcoming",
        help="Fetch fixtures for today + next N-1 days (default FIXTURES_LOOKAHEAD_DAYS)",
    )
    upcoming_parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Window size in days including today (default from settings)",
    )
    subparsers.add_parser("check-quota", help="Check remaining API-Football request quota")
    subparsers.add_parser("test-api", help="Test API connection and print response metadata")
    subparsers.add_parser("clear-cache", help="Clear all football API cache entries")
    subparsers.add_parser("cache-stats", help="Show cache hit/miss statistics")
    subparsers.add_parser("list-tasks", help="List registered scheduler tasks")
    subparsers.add_parser("run-scheduler", help="Run scheduler in foreground for debugging")
    subparsers.add_parser(
        "backfill-features",
        help="Build match_features from finished fixtures + pre_match packages",
    )
    subparsers.add_parser(
        "train-model",
        help="Train 1X2 probability model from labeled match_features (needs >= ML_MIN_TRAIN_SAMPLES)",
    )
    subparsers.add_parser(
        "model-status",
        help="Show labeled sample count and whether inference is multifactor or ml",
    )

    trigger_parser = subparsers.add_parser("trigger-task", help="Manually trigger a scheduler task")
    trigger_parser.add_argument(
        "--name",
        required=True,
        choices=[
            "midday_fixtures_sync",
            "pre_match_update",
            "capture_results",
            "clean_old_data",
            "train_model",
        ],
        help="Task name to trigger",
    )

    args = parser.parse_args()

    if args.command == "trigger-task":
        asyncio.run(run_trigger_task(args.name))
        return

    if args.command == "fetch-upcoming":
        asyncio.run(run_fetch_upcoming(args.days))
        return

    commands = {
        "init-db": run_init_db,
        "fetch-leagues": run_fetch_leagues,
        "fetch-today": run_fetch_today,
        "check-quota": run_check_quota,
        "test-api": run_test_api,
        "clear-cache": run_clear_cache,
        "cache-stats": run_cache_stats,
        "list-tasks": run_list_tasks,
        "run-scheduler": run_scheduler_loop,
        "backfill-features": run_backfill_features,
        "train-model": run_train_model,
        "model-status": run_model_status,
    }

    asyncio.run(commands[args.command]())


if __name__ == "__main__":
    main()
