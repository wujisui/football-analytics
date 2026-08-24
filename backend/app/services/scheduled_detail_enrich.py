"""Optional scheduled prematch display-package enrich (admin toggle).

Subscribed full batches fill missing detail packages for today/tomorrow
hot-league prematch fixtures via the same ``AnalyzerService.analyze_fixture``
path used by detail clicks, then stop on quota exhaustion.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.models.fixture import Fixture
from app.models.pre_match_data import PreMatchData
from app.services.runtime_settings import get_hot_league_ids
from app.services.analyzer import (
    AnalyzerService,
    prematch_package_needs_refresh_from_stored,
)
from app.services.cache import get_cache_service
from app.services.results_capture import prematch_list_clause

logger = logging.getLogger(__name__)


def _quota_looks_exhausted() -> bool:
    cache = get_cache_service()
    remaining = getattr(cache, "last_api_remaining", None) if cache else None
    return remaining is not None and int(remaining) <= 0


def _is_quota_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(
        token in text
        for token in (
            "request limit",
            "rate limit",
            "quota",
            "plan does not allow",
            "reached the request limit",
        )
    )


async def list_prematch_fixtures_needing_package(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    before: datetime | None = None,
    limit: int | None,
) -> list[int]:
    """Hot-league prematch fixtures whose stored display package is incomplete."""
    hot_ids, _ = await get_hot_league_ids(session)
    if not hot_ids or (limit is not None and limit <= 0):
        return []

    current = now or datetime.utcnow()
    query = (
        select(Fixture, PreMatchData)
        .outerjoin(PreMatchData, PreMatchData.fixture_id == Fixture.id)
        .options(
            selectinload(Fixture.home_team),
            selectinload(Fixture.away_team),
            selectinload(Fixture.league),
        )
        .where(
            Fixture.league_id.in_(hot_ids),
            prematch_list_clause(current),
        )
    )
    if before is not None:
        query = query.where(Fixture.date < before)
    rows = (await session.execute(query.order_by(Fixture.date, Fixture.id))).all()

    history_tag = get_settings().history_source_tag
    needed: list[int] = []
    for fixture, stored in rows:
        if stored is None or prematch_package_needs_refresh_from_stored(
            stored,
            history_tag=history_tag,
            standings_overlay=None,
        ):
            needed.append(int(fixture.id))
            if limit is not None and len(needed) >= limit:
                break
    return needed


async def run_scheduled_full_detail_enrich(
    *,
    now: datetime | None = None,
    before: datetime | None = None,
) -> dict[str, Any]:
    """Enrich subscribed today/tomorrow packages until quota is exhausted."""
    stats: dict[str, Any] = {
        "candidates": 0,
        "enriched": 0,
        "failed": 0,
        "skipped_quota": 0,
        "unlimited": True,
    }

    async with AsyncSessionLocal() as session:
        ids = await list_prematch_fixtures_needing_package(
            session, now=now, before=before, limit=None
        )
        stats["candidates"] = len(ids)
        if not ids:
            return stats

        analyzer = AnalyzerService(session)
        for fixture_id in ids:
            if _quota_looks_exhausted():
                stats["skipped_quota"] = len(ids) - stats["enriched"] - stats["failed"]
                logger.warning(
                    "scheduled full detail: stopping early (quota remaining<=0) "
                    "after enriched=%s",
                    stats["enriched"],
                )
                break
            try:
                await analyzer.analyze_fixture(fixture_id, include_package=True)
                stats["enriched"] += 1
            except Exception as exc:
                if _is_quota_error(exc) or _quota_looks_exhausted():
                    stats["skipped_quota"] = (
                        len(ids) - stats["enriched"] - stats["failed"]
                    )
                    logger.warning(
                        "scheduled full detail: quota/plan stop on fixture %s: %s",
                        fixture_id,
                        exc,
                    )
                    break
                stats["failed"] += 1
                logger.warning(
                    "scheduled full detail: fixture %s failed: %s",
                    fixture_id,
                    exc,
                )

    logger.info(
        "scheduled full detail done candidates=%s enriched=%s failed=%s "
        "skipped_quota=%s",
        stats["candidates"],
        stats["enriched"],
        stats["failed"],
        stats["skipped_quota"],
    )
    return stats
