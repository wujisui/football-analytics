from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

async_engine = create_async_engine(settings.DATABASE_URL, echo=False)

if settings.DATABASE_URL.startswith("sqlite"):
    @event.listens_for(async_engine.sync_engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def _ensure_table_columns(conn, table: str, additions: dict[str, str]) -> None:
    """Add newly introduced columns on an existing SQLite table."""
    from sqlalchemy import text

    try:
        result = await conn.execute(text(f"PRAGMA table_info({table})"))
        existing = {row[1] for row in result.fetchall()}
    except Exception:
        return
    if not existing:
        return

    for column, col_type in additions.items():
        if column not in existing:
            await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))


async def _drop_table_columns(conn, table: str, columns: tuple[str, ...]) -> None:
    """Drop retired columns on an existing SQLite table (no-op when unsupported)."""
    from sqlalchemy import text

    try:
        result = await conn.execute(text(f"PRAGMA table_info({table})"))
        existing = {row[1] for row in result.fetchall()}
    except Exception:
        return

    for column in columns:
        if column not in existing:
            continue
        try:
            await conn.execute(text(f"ALTER TABLE {table} DROP COLUMN {column}"))
        except Exception:
            return


async def _migrate_favorite_fixtures_owner_pk(conn) -> None:
    """Rebuild favorite_fixtures with composite PK (user_id, fixture_id).

    Legacy rows used ``fixture_id`` alone and nullable ``user_id``. Anonymous
    ownership is normalized to empty string so uniqueness works on SQLite.
    """
    from sqlalchemy import text

    try:
        info = await conn.execute(text("PRAGMA table_info(favorite_fixtures)"))
        cols = list(info.fetchall())
    except Exception:
        return
    if not cols:
        return

    col_names = {row[1] for row in cols}
    pk_cols = [row[1] for row in cols if row[5]]
    needs_rebuild = pk_cols == ["fixture_id"] or (
        "user_id" in col_names and pk_cols == ["fixture_id"]
    )
    # Also rebuild when PK is missing user_id entirely.
    if "user_id" in pk_cols and "fixture_id" in pk_cols:
        # Normalize any leftover NULL owner keys.
        await conn.execute(
            text(
                "UPDATE favorite_fixtures SET user_id = '' "
                "WHERE user_id IS NULL"
            )
        )
        return
    if not needs_rebuild and pk_cols != ["fixture_id"]:
        # Unexpected shape — still try NULL normalize if column exists.
        if "user_id" in col_names:
            await conn.execute(
                text(
                    "UPDATE favorite_fixtures SET user_id = '' "
                    "WHERE user_id IS NULL"
                )
            )
        return

    await conn.execute(text("ALTER TABLE favorite_fixtures RENAME TO favorite_fixtures_legacy"))
    await conn.execute(
        text(
            """
            CREATE TABLE favorite_fixtures (
                user_id TEXT NOT NULL DEFAULT '',
                fixture_id INTEGER NOT NULL,
                source TEXT NOT NULL DEFAULT 'manual',
                auto_market TEXT,
                auto_lean TEXT,
                quality_rating REAL,
                saved_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                PRIMARY KEY (user_id, fixture_id),
                FOREIGN KEY(fixture_id) REFERENCES fixtures (id) ON DELETE CASCADE
            )
            """
        )
    )
    legacy_cols = {row[1] for row in (
        await conn.execute(text("PRAGMA table_info(favorite_fixtures_legacy)"))
    ).fetchall()}
    has_source = "source" in legacy_cols
    # Legacy quality_low was a boolean gate; ratings are recomputed on next sync.
    quality_expr = (
        "quality_rating" if "quality_rating" in legacy_cols else "NULL"
    )
    source_expr = "COALESCE(source, 'manual')" if has_source else "'manual'"
    await conn.execute(
        text(
            f"""
            INSERT OR IGNORE INTO favorite_fixtures
                (user_id, fixture_id, source, auto_market, auto_lean, quality_rating, saved_at)
            SELECT
                COALESCE(user_id, ''),
                fixture_id,
                {source_expr},
                auto_market,
                auto_lean,
                {quality_expr},
                saved_at
            FROM favorite_fixtures_legacy
            """
        )
    )
    await conn.execute(text("DROP TABLE favorite_fixtures_legacy"))


async def _ensure_sqlite_columns(conn) -> None:
    """Add newly introduced columns on existing SQLite databases."""
    from sqlalchemy import text

    await _ensure_table_columns(
        conn,
        "pre_match_data",
        {
            "odds_json": "TEXT",
            "odds_opening_json": "TEXT",
            "odds_mid_json": "TEXT",
            "odds_late_json": "TEXT",
            "lineups_json": "TEXT",
            "injuries_json": "TEXT",
            "h2h_json": "TEXT",
            "home_form_json": "TEXT",
            "away_form_json": "TEXT",
            "standings_json": "TEXT",
            "briefing_json": "TEXT",
            "recommendation": "TEXT",
            "score_hint": "TEXT",
            "goal_lean": "TEXT",
            "both_score_lean": "TEXT",
            "handicap_lean": "TEXT",
        },
    )
    await _ensure_table_columns(
        conn,
        "fixtures",
        {
            "venue_city": "TEXT",
            "match_timezone": "TEXT",
            "match_day": "TEXT",
            "match_day_source": "TEXT",
            "home_goals": "INTEGER",
            "away_goals": "INTEGER",
            "status_short": "TEXT",
            "et_home_goals": "INTEGER",
            "et_away_goals": "INTEGER",
            "pen_home": "INTEGER",
            "pen_away": "INTEGER",
        },
    )
    await conn.execute(
        text("CREATE INDEX IF NOT EXISTS ix_fixtures_match_day ON fixtures (match_day)")
    )
    await _ensure_table_columns(
        conn,
        "teams",
        {
            "country": "TEXT",
            "venue_city": "TEXT",
            "timezone": "TEXT",
        },
    )
    await _ensure_table_columns(
        conn,
        "match_features",
        {
            "ah_line": "REAL",
            "ah_home_odd": "REAL",
            "ah_away_odd": "REAL",
            "ah_features_json": "TEXT",
            "ah_label": "TEXT",
            "ah_cover_prob": "REAL",
            "ah_model_source": "TEXT",
            "ah_feature_version": "TEXT",
            "goal_features_json": "TEXT",
            "goal_feature_version": "TEXT",
            "home_goals_label": "INTEGER",
            "away_goals_label": "INTEGER",
        },
    )
    await _ensure_table_columns(
        conn,
        "favorite_fixtures",
        {
            # Owner bucket; "" = guest (AUTH_VIP_QUOTA §4.4).
            "user_id": "TEXT",
            "source": "TEXT DEFAULT 'manual'",
            "auto_market": "TEXT",
            "auto_lean": "TEXT",
            "quality_rating": "REAL",
        },
    )
    await _ensure_table_columns(
        conn,
        "auto_pick_snapshots",
        {
            "raw_confidence": "REAL",
            "score": "REAL",
            "quality_rating": "REAL",
        },
    )
    await _ensure_table_columns(
        conn,
        "bet_plans",
        {
            "user_id": "TEXT DEFAULT ''",
        },
    )
    await _ensure_table_columns(
        conn,
        "users",
        {
            "is_admin": "INTEGER DEFAULT 0",
        },
    )
    await conn.execute(
        text("UPDATE bet_plans SET user_id = '' WHERE user_id IS NULL")
    )
    # quality_low 已被 0.5–5 星的 quality_rating 取代。
    await _drop_table_columns(conn, "favorite_fixtures", ("quality_low",))
    await _drop_table_columns(conn, "auto_pick_snapshots", ("quality_low",))
    await _drop_table_columns(conn, "match_features", ("audit_snapshot_json",))
    await _migrate_favorite_fixtures_owner_pk(conn)


async def init_db() -> None:
    # Import models so they are registered with Base.metadata.
    import app.models  # noqa: F401

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if settings.DATABASE_URL.startswith("sqlite"):
            await _ensure_sqlite_columns(conn)
