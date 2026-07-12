import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_snapshot import ApiSnapshot

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class SnapshotStore:
    """SQLite-backed store for raw API payloads."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_valid(self, cache_key: str) -> dict[str, Any] | None:
        result = await self.session.execute(
            select(ApiSnapshot).where(ApiSnapshot.cache_key == cache_key)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None

        now = _utc_now()
        if row.expires_at <= now:
            logger.info("DB snapshot expired for %s", cache_key)
            return None

        try:
            payload = json.loads(row.payload_json)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON in api_snapshots for %s", cache_key)
            return None

        if not isinstance(payload, dict):
            return None

        logger.info(
            "DB snapshot hit for %s (fetched_at=%s, expires_at=%s)",
            cache_key,
            row.fetched_at,
            row.expires_at,
        )
        return payload

    async def save(self, cache_key: str, payload: dict[str, Any], ttl_seconds: int) -> None:
        now = _utc_now()
        expires_at = now + timedelta(seconds=max(ttl_seconds, 1))
        payload_json = json.dumps(payload, ensure_ascii=False, default=str)

        row = await self.session.get(ApiSnapshot, cache_key)
        if row is None:
            self.session.add(
                ApiSnapshot(
                    cache_key=cache_key,
                    payload_json=payload_json,
                    fetched_at=now,
                    expires_at=expires_at,
                )
            )
        else:
            row.payload_json = payload_json
            row.fetched_at = now
            row.expires_at = expires_at

        await self.session.commit()
        logger.info("Saved DB snapshot for %s (ttl=%ss)", cache_key, ttl_seconds)

    async def invalidate(self, cache_key: str) -> None:
        """Expire a snapshot so the next local-first read misses and re-fetches."""
        row = await self.session.get(ApiSnapshot, cache_key)
        if row is None:
            return
        row.expires_at = _utc_now() - timedelta(seconds=1)
        await self.session.commit()
        logger.info("Invalidated DB snapshot for %s", cache_key)
