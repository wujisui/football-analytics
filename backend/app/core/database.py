from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

async_engine = create_async_engine(settings.DATABASE_URL, echo=False)
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


async def _ensure_sqlite_columns(conn) -> None:
    """Add newly introduced columns on existing SQLite databases."""
    from sqlalchemy import text

    try:
        result = await conn.execute(text("PRAGMA table_info(pre_match_data)"))
        existing = {row[1] for row in result.fetchall()}
    except Exception:
        return
    if not existing:
        return

    additions = {
        "odds_json": "TEXT",
        "lineups_json": "TEXT",
        "injuries_json": "TEXT",
        "h2h_json": "TEXT",
        "home_form_json": "TEXT",
        "away_form_json": "TEXT",
        "standings_json": "TEXT",
    }
    for column, col_type in additions.items():
        if column not in existing:
            await conn.execute(
                text(f"ALTER TABLE pre_match_data ADD COLUMN {column} {col_type}")
            )


async def init_db() -> None:
    # Import models so they are registered with Base.metadata.
    import app.models  # noqa: F401

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if settings.DATABASE_URL.startswith("sqlite"):
            await _ensure_sqlite_columns(conn)
