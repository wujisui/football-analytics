"""Shared helpers for unfinished fixtures that should already have FT scores."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import Select, or_, select
from sqlalchemy.sql import ColumnElement

from app.models.fixture import Fixture

STALE_RESULT_HOURS = 2


def results_capture_cutoff(now: datetime | None = None) -> datetime:
    return (now or datetime.utcnow()) - timedelta(hours=STALE_RESULT_HOURS)


def stale_missing_score_clause() -> ColumnElement[bool]:
    return or_(
        Fixture.status.in_(["pending", "live"]),
        Fixture.home_goals.is_(None),
        Fixture.away_goals.is_(None),
    )


def select_stale_pending_fixtures(
    *,
    start: datetime,
    cutoff: datetime,
) -> Select[tuple[Fixture]]:
    return select(Fixture).where(
        Fixture.date >= start,
        Fixture.date <= cutoff,
        stale_missing_score_clause(),
    )
