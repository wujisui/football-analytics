"""Shared helpers for unfinished fixtures that should already have FT scores."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.sql import ColumnElement

from app.models.fixture import Fixture

STALE_RESULT_HOURS = 2
# No match runs this long — past it, a live row means the feed has not settled yet.
STUCK_LIVE_HOURS = 4
# Feed codes reached only after the 90 minutes are over, so ``fulltime`` is final.
POST_REGULATION_SHORT = frozenset({"ET", "BT", "P"})


def results_capture_cutoff(now: datetime | None = None) -> datetime:
    return (now or datetime.utcnow()) - timedelta(hours=STALE_RESULT_HOURS)


def is_stale_live_row(previous_status: str | None, incoming_status: str) -> bool:
    """Official day feeds sometimes replay a live code for an already finished match."""
    return previous_status == "finished" and incoming_status in {"pending", "live"}


def stuck_live_clause(now: datetime | None = None) -> ColumnElement[bool]:
    """Kicked off long ago, yet the feed still reports it as in play."""
    cutoff = (now or datetime.utcnow()) - timedelta(hours=STUCK_LIVE_HOURS)
    return and_(Fixture.status == "live", Fixture.date <= cutoff)


def settled_by_full_time(
    *,
    status: str,
    status_short: str | None,
    fixture_date: datetime,
    has_full_time_score: bool,
    now: datetime | None = None,
) -> str:
    """Close out stuck rows whose 90' score is already final.

    The feed sometimes never leaves a post-regulation code (e.g. ``P`` while the
    shootout is being taken). ``score.fulltime`` is settled by then, and every
    prediction is graded on regulation time, so such rows count as finished.
    """
    if status != "live" or not has_full_time_score:
        return status
    if (status_short or "").upper() not in POST_REGULATION_SHORT:
        return status
    kickoff = fixture_date
    if kickoff.tzinfo is not None:
        # Feed payloads carry UTC offsets; fixtures are stored naive UTC.
        kickoff = kickoff.astimezone(timezone.utc).replace(tzinfo=None)
    cutoff = (now or datetime.utcnow()) - timedelta(hours=STUCK_LIVE_HOURS)
    return "finished" if kickoff <= cutoff else status


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
