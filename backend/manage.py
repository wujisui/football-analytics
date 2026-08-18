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


async def run_backfill_team_names() -> None:
    """Rewrite teams.name to Chinese for every mapped club/national team."""
    from app.core.database import AsyncSessionLocal, init_db
    from app.services.team_names import backfill_team_names

    await init_db()
    async with AsyncSessionLocal() as session:
        updated = await backfill_team_names(session)
    print(f"Updated {updated} team display name(s) to Chinese.")


async def run_backfill_match_days() -> None:
    """Rebuild venue-local fixture days from local snapshots (no API calls)."""
    from app.core.database import AsyncSessionLocal, init_db
    from app.services.match_day import backfill_fixture_match_days

    await init_db()
    async with AsyncSessionLocal() as session:
        result = await backfill_fixture_match_days(session)
    print(
        f"Enriched {result['teams_enriched']} team location(s); "
        f"updated {result['fixtures_updated']} fixture match day(s)."
    )
    print(f"Sources: {result['by_source']}")


async def run_audit_team_names() -> None:
    """Report curated team ids that disagree with the provider's own labels."""
    from app.core.database import AsyncSessionLocal, init_db
    from app.services.team_names import audit_curated_ids

    await init_db()
    async with AsyncSessionLocal() as session:
        result = await audit_curated_ids(session)

    stream = getattr(sys.stdout, "buffer", None)
    enc = getattr(sys.stdout, "encoding", None) or "utf-8"

    def _out(msg: str) -> None:
        if stream is None:
            print(msg)
        else:
            stream.write((msg + "\n").encode(enc, errors="replace"))

    _out(
        f"Curated ids: {result['curated']} | cross-checked ok: {result['verified']} "
        f"| conflicts: {len(result['conflicts'])} | no local evidence: {len(result['unverified'])}"
    )
    for row in result["conflicts"]:
        _out(
            f"  {row['team_id']}: curated={row['curated']} "
            f"expected={'/'.join(row['expected'])} official={'/'.join(row['official'])}"
        )
    if not result["conflicts"]:
        _out("No conflicts. Short forms such as 拜仁 / 多特 are kept on purpose.")


async def run_translate_catalog_teams(dry_run: bool = False) -> None:
    """Auto-translate unmapped clubs that appear in config/leagues.json leagues."""
    import sys

    from app.core.database import AsyncSessionLocal, init_db
    from app.services.team_translate import auto_translate_catalog_teams

    def _out(msg: str) -> None:
        stream = getattr(sys.stdout, "buffer", None)
        if stream is None:
            print(msg)
            return
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        stream.write((msg + "\n").encode(enc, errors="replace"))

    await init_db()
    async with AsyncSessionLocal() as session:
        result = await auto_translate_catalog_teams(session, dry_run=dry_run)
    _out(
        "Catalog teams: "
        f"missing={result['catalog_missing']} attempted={result['attempted']} "
        f"translated={result['translated']} rejected={result.get('rejected')} "
        f"stored={result['stored']} "
        f"backfilled={result['backfilled']} dry_run={result['dry_run']} "
        f"aborted={result.get('aborted')}"
    )
    for sample in result.get("samples") or []:
        _out(f"  {sample['id']}: {sample['zh']}")
    still = result.get("still_missing") or []
    if still:
        _out(f"Still missing ({len(still)} shown):")
        for item in still:
            _out(f"  {item['id']}: {item['name']}")


async def run_backfill_features() -> None:
    from app.core.database import AsyncSessionLocal, init_db
    from app.services.ml_predictor import collect_training_rows

    await init_db()
    async with AsyncSessionLocal() as session:
        rows = await collect_training_rows(session)
    print(f"Backfilled / collected {len(rows)} labeled training row(s).")


async def run_refresh_pending_predictions() -> None:
    from app.core.database import AsyncSessionLocal, init_db
    from app.services.ml_predictor import refresh_pending_prediction_snapshots

    await init_db()
    async with AsyncSessionLocal() as session:
        result = await refresh_pending_prediction_snapshots(session)
    print(
        f"Refreshed pending predictions: updated={result['updated']} "
        f"skipped_no_odds={result['skipped_no_odds']}"
    )


async def run_upgrade_models() -> None:
    """Backfill odds+FT labels, retrain 1X2/AH/goals, refresh pending leans."""
    from app.core.database import AsyncSessionLocal, init_db
    from app.services.ah_predictor import (
        backfill_ah_features,
        train_model_from_db as train_ah,
    )
    from app.services.goal_predictor import train_model_from_db as train_goals
    from app.services.ml_predictor import (
        collect_training_rows,
        refresh_pending_prediction_snapshots,
        train_model_from_db,
    )

    await init_db()
    async with AsyncSessionLocal() as session:
        rows = await collect_training_rows(session)
        print(f"1X2 labeled rows: {len(rows)}")
        ah_n = await backfill_ah_features(session)
        print(f"AH features backfilled: {ah_n}")

    async with AsyncSessionLocal() as session:
        r1 = await train_model_from_db(session)
        print(f"1X2 train: ok={r1.get('ok')} deployable={r1.get('deployable')} n={r1.get('n_samples')} reason={r1.get('reason')}")
    async with AsyncSessionLocal() as session:
        r2 = await train_ah(session)
        print(f"AH train: ok={r2.get('ok')} n={r2.get('n_samples')} reason={r2.get('reason')}")
    async with AsyncSessionLocal() as session:
        r3 = await train_goals(session)
        print(f"Goals train: ok={r3.get('ok')} deployable={r3.get('deployable')} n={r3.get('n_samples')} gates={r3.get('target_gates')} reason={r3.get('reason')}")
    async with AsyncSessionLocal() as session:
        refreshed = await refresh_pending_prediction_snapshots(session)
        print(
            f"Pending refresh: updated={refreshed['updated']} "
            f"skipped_no_odds={refreshed['skipped_no_odds']}"
        )


async def run_prune_low_value_data(*, apply: bool) -> None:
    from app.core.database import AsyncSessionLocal, init_db
    from app.services.data_cleanup import prune_low_value_data

    await init_db()
    async with AsyncSessionLocal() as session:
        report = await prune_low_value_data(session, apply=apply)
    print(report.to_dict())


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
    print("Training completed.")
    print(f"Samples: {result.get('n_samples')}")
    print(f"Val log-loss: {result.get('val_metrics', {}).get('log_loss')}")
    print(f"Val accuracy: {result.get('val_metrics', {}).get('accuracy')}")
    print(f"Market baseline: {result.get('market_val_metrics')}")
    print(f"Deployable: {result.get('deployable')}")
    print(f"Weights: {result.get('weights_path')}")
    print(f"Model status: {status}")


async def run_model_status() -> None:
    from app.core.database import AsyncSessionLocal, init_db
    from app.models.match_feature import MatchFeature
    from app.services.ah_predictor import model_status as ah_model_status
    from app.services.goal_predictor import model_status as goal_model_status
    from app.services.ml_predictor import model_status
    from app.services.probability_calibration import load_calibration_artifact
    from sqlalchemy import func, select

    await init_db()
    status = model_status()
    ah_status = ah_model_status()
    goal_status = goal_model_status()
    calibration = load_calibration_artifact()
    async with AsyncSessionLocal() as session:
        total = await session.scalar(select(func.count()).select_from(MatchFeature))
        labeled = await session.scalar(
            select(func.count()).select_from(MatchFeature).where(MatchFeature.label.is_not(None))
        )
        ah_labeled = await session.scalar(
            select(func.count())
            .select_from(MatchFeature)
            .where(MatchFeature.ah_label.in_(("cover", "no_cover")))
        )
    print("--- 1X2 ---")
    print(f"inference_mode: {status['inference_mode']}")
    print(f"artifact_ready: {status['artifact_ready']}")
    print(f"trained_n_samples: {status['trained_n_samples']}")
    print(f"min_train_samples: {status['min_train_samples']}")
    print(f"match_features_total: {total or 0}")
    print(f"match_features_labeled: {labeled or 0}")
    print(f"val_metrics: {status.get('val_metrics')}")
    print(f"market_val_metrics: {status.get('market_val_metrics')}")
    print(f"confidence_metrics: {status.get('confidence_metrics')}")
    print(f"trained_at: {status.get('trained_at')}")
    print("--- 让球 (AH) ---")
    print(f"inference_mode: {ah_status['inference_mode']}")
    print(f"artifact_ready: {ah_status['artifact_ready']}")
    print(f"trained_n_samples: {ah_status['trained_n_samples']}")
    print(f"min_train_samples: {ah_status['min_train_samples']}")
    print(f"ah_labeled: {ah_labeled or 0}")
    print(f"trained_at: {ah_status.get('trained_at')}")
    print("--- 进球分布 (Poisson) ---")
    print(f"artifact_ready: {goal_status['artifact_ready']}")
    print(f"deployable: {goal_status['deployable']}")
    print(f"trained_n_samples: {goal_status['trained_n_samples']}")
    print(f"val_metrics: {goal_status.get('val_metrics')}")
    print(f"baseline_total_mae: {goal_status.get('baseline_total_mae')}")
    print(f"trained_at: {goal_status.get('trained_at')}")
    print("--- 日推概率校准 (time holdout) ---")
    print(f"trained_n_samples: {calibration.get('n_samples', 0)}")
    print(f"trained_at: {calibration.get('trained_at')}")
    for market, row in (calibration.get("markets") or {}).items():
        print(
            f"{market}: deployable={row.get('deployable')} "
            f"n={row.get('n_samples', 0)} "
            f"raw={row.get('raw_holdout')} "
            f"calibrated={row.get('calibrated_holdout')}"
        )


async def run_backfill_ah_features() -> None:
    from app.core.database import AsyncSessionLocal, init_db
    from app.services.ah_predictor import backfill_ah_features

    await init_db()
    async with AsyncSessionLocal() as session:
        updated = await backfill_ah_features(session)
    print(f"Backfilled AH fields for {updated} match_features row(s).")


async def run_train_ah_model() -> None:
    from app.core.database import AsyncSessionLocal, init_db
    from app.services.ah_predictor import min_train_samples, model_status, train_model_from_db

    await init_db()
    threshold = min_train_samples()
    async with AsyncSessionLocal() as session:
        result = await train_model_from_db(session)
    status = model_status()
    if not result.get("ok"):
        print(
            f"AH training skipped: {result.get('reason')} "
            f"(need >={threshold} finished fixtures with AH labels)."
        )
        print(f"Current labeled samples: {result.get('n_samples', 0)}")
        print(f"Current inference mode: {status['inference_mode']}")
        return
    print("AH training succeeded — inference will auto-switch to source=ml.")
    print(f"Samples: {result.get('n_samples')}")
    print(f"Val log-loss: {result.get('val_metrics', {}).get('log_loss')}")
    print(f"Val accuracy: {result.get('val_metrics', {}).get('accuracy')}")
    print(f"Weights: {result.get('weights_path')}")
    print(f"Model status: {status}")


async def run_train_goals_model() -> None:
    from app.core.database import AsyncSessionLocal, init_db
    from app.services.goal_predictor import model_status, train_model_from_db

    await init_db()
    async with AsyncSessionLocal() as session:
        result = await train_model_from_db(session)
    if not result.get("ok"):
        print(f"Goal training skipped: {result.get('reason')}")
        return
    print("Goal-distribution training completed.")
    print(f"Samples: {result.get('n_samples')}")
    print(f"Deployable: {result.get('deployable')}")
    print(f"Validation: {result.get('val_metrics')}")
    print(f"Constant baseline total MAE: {result.get('baseline_total_mae')}")
    print(f"Model status: {model_status()}")


async def run_set_admin(account: str, *, revoke: bool = False) -> None:
    from app.core.database import AsyncSessionLocal, init_db
    from app.services import auth as auth_service

    await init_db()
    async with AsyncSessionLocal() as db:
        try:
            user = await auth_service.set_user_admin(
                db, account, is_admin=not revoke
            )
            await db.commit()
        except LookupError as exc:
            print(f"Failed: {exc}")
            sys.exit(1)
    flag = "revoked" if revoke else "granted"
    print(f"Admin {flag} for {user.username} (id={user.id})")


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
        "backfill-team-names",
        help="Rewrite teams.name to Chinese from the built-in id/name map",
    )
    subparsers.add_parser(
        "backfill-match-days",
        help="Rebuild fixture-local match days from cached official location data",
    )
    subparsers.add_parser(
        "audit-team-names",
        help="Cross-check curated team ids against official names in api_snapshots",
    )
    translate_parser = subparsers.add_parser(
        "translate-catalog-teams",
        help=(
            "Auto-translate clubs that appear in config/leagues.json fixtures "
            "but still lack Chinese names"
        ),
    )
    translate_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only report proposed translations; do not write auto map or DB",
    )
    subparsers.add_parser(
        "backfill-features",
        help="Build match_features from finished fixtures + pre_match packages",
    )
    subparsers.add_parser(
        "refresh-pending-predictions",
        help="Recompute pending recommendation leans from local odds (no API)",
    )
    subparsers.add_parser(
        "upgrade-models",
        help="Backfill odds+FT samples, retrain 1X2/AH/goals, refresh pending leans",
    )
    prune_parser = subparsers.add_parser(
        "prune-low-value-data",
        help=(
            "Delete finished/cancelled/postponed fixtures that have neither "
            "pre-match 1X2 nor an algorithm recommendation (never deletes pending)"
        ),
    )
    prune_parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply physical deletion; omitted means dry-run",
    )
    subparsers.add_parser(
        "train-model",
        help="Train 1X2 probability model from labeled match_features (needs >= ML_MIN_TRAIN_SAMPLES)",
    )
    subparsers.add_parser(
        "model-status",
        help="Show labeled sample count and 1X2 inference mode (ml / market_baseline / multifactor)",
    )
    subparsers.add_parser(
        "backfill-ah-features",
        help="Backfill AH features/labels on match_features from stored pre_match packages",
    )
    subparsers.add_parser(
        "train-ah-model",
        help="Train Asian handicap cover model (needs >= ML_AH_MIN_TRAIN_SAMPLES)",
    )
    subparsers.add_parser(
        "train-goals-model",
        help="Train Poisson goal-distribution model from pre-match markets and FT scores",
    )

    trigger_parser = subparsers.add_parser("trigger-task", help="Manually trigger a scheduler task")
    trigger_parser.add_argument(
        "--name",
        required=True,
        choices=[
            "scheduled_fixtures_sync",
            "clean_old_data",
            "train_model",
            "daily_auto_favorites",
        ],
        help="Task name to trigger",
    )

    set_admin_parser = subparsers.add_parser(
        "set-admin",
        help="Grant is_admin on an existing account",
    )
    set_admin_parser.add_argument(
        "account",
        help="Username or email (must already be registered)",
    )

    unset_admin_parser = subparsers.add_parser(
        "unset-admin",
        help="Revoke is_admin on an existing account",
    )
    unset_admin_parser.add_argument(
        "account",
        help="Username or email",
    )

    args = parser.parse_args()

    if args.command == "trigger-task":
        asyncio.run(run_trigger_task(args.name))
        return

    if args.command == "set-admin":
        asyncio.run(run_set_admin(args.account, revoke=False))
        return

    if args.command == "unset-admin":
        asyncio.run(run_set_admin(args.account, revoke=True))
        return

    if args.command == "fetch-upcoming":
        asyncio.run(run_fetch_upcoming(args.days))
        return

    if args.command == "translate-catalog-teams":
        asyncio.run(run_translate_catalog_teams(dry_run=args.dry_run))
        return
    if args.command == "prune-low-value-data":
        asyncio.run(run_prune_low_value_data(apply=args.apply))
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
        "backfill-team-names": run_backfill_team_names,
        "backfill-match-days": run_backfill_match_days,
        "audit-team-names": run_audit_team_names,
        "backfill-features": run_backfill_features,
        "refresh-pending-predictions": run_refresh_pending_predictions,
        "upgrade-models": run_upgrade_models,
        "train-model": run_train_model,
        "model-status": run_model_status,
        "backfill-ah-features": run_backfill_ah_features,
        "train-ah-model": run_train_ah_model,
        "train-goals-model": run_train_goals_model,
    }

    asyncio.run(commands[args.command]())


if __name__ == "__main__":
    main()
