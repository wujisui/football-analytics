"""Scheduled entry point for the unified recommendation pipeline."""

from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

AUTO_PICK_LIMIT = 4


async def sync_daily_auto_favorites(
    db: AsyncSession,
    *,
    user_id: str | None = None,
    limit: int = AUTO_PICK_LIMIT,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Refresh references and daily picks after a batch odds update."""
    from app.services.recommendation.pipeline import sync_daily_recommendations

    return await sync_daily_recommendations(
        db,
        user_id=user_id,
        limit=limit,
        now=now,
    )
