"""Optional scheduled prematch display-package enrich (admin toggle).

Default off. When enabled, each ``scheduled_fixtures_sync`` batch fills missing
detail packages for catalog-league prematch fixtures via the same
``AnalyzerService.analyze_fixture`` path used by detail clicks — then stops on
quota exhaustion or the per-batch budget.
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
    limit: int,
) -> list[int]:
    """Catalog-league prematch fixtures whose stored display package is incomplete."""
    settings = get_settings()
    catalog_ids = list(settings.LEAGUE_IDS.values())
    if not catalog_ids or limit <= 0:
        return []

    current = now or datetime.utcnow()
    rows = (
        await session.execute(
            select(Fixture, PreMatchData)
            .outerjoin(PreMatchData, PreMatchData.fixture_id == Fixture.id)
            .options(
                selectinload(Fixture.home_team),
                selectinload(Fixture.away_team),
                selectinload(Fixture.league),
            )
            .where(
                Fixture.league_id.in_(catalog_ids),
                prematch_list_clause(current),
            )
            .order_by(Fixture.date, Fixture.id)
        )
    ).all()

    history_tag = settings.history_source_tag
    needed: list[int] = []
    for fixture, stored in rows:
        if stored is None or prematch_package_needs_refresh_from_stored(
            stored,
            history_tag=history_tag,
            standings_overlay=None,
        ):
            needed.append(int(fixture.id))
            if len(needed) >= limit:
                break
    return needed


async def run_scheduled_full_detail_enrich(
    *,
    budget: int | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Enrich up to ``budget`` incomplete catalog prematch packages.

    Returns counts for logging / admin diagnostics. Never raises for per-fixture
    failures; stops early when official quota looks exhausted.
    """
    settings = get_settings()
    limit = (
        budget
        if budget is not None
        else max(0, int(settings.SCHEDULED_FULL_DETAIL_BUDGET))
    )
    stats: dict[str, Any] = {
        "candidates": 0,
        "enriched": 0,
        "failed": 0,
        "skipped_quota": 0,
        "budget": limit,
    }
    if limit <= 0:
        return stats

    async with AsyncSessionLocal() as session:
        ids = await list_prematch_fixtures_needing_package(
            session, now=now, limit=limit
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
        "skipped_quota=%s budget=%s",
        stats["candidates"],
        stats["enriched"],
        stats["failed"],
        stats["skipped_quota"],
        stats["budget"],
    )
    return stats
