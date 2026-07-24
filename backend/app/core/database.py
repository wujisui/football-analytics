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


async def _ensure_sqlite_columns(conn) -> None:
    """Add newly introduced columns on existing SQLite databases."""
    await _ensure_table_columns(
        conn,
        "pre_match_data",
        {
            "odds_json": "TEXT",
            "odds_opening_json": "TEXT",
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
            "home_goals": "INTEGER",
            "away_goals": "INTEGER",
            "status_short": "TEXT",
            "et_home_goals": "INTEGER",
            "et_away_goals": "INTEGER",
            "pen_home": "INTEGER",
            "pen_away": "INTEGER",
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


async def init_db() -> None:
    # Import models so they are registered with Base.metadata.
    import app.models  # noqa: F401

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if settings.DATABASE_URL.startswith("sqlite"):
            await _ensure_sqlite_columns(conn)
