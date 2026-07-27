"""UTC match-day helpers.

API-Sports kickoffs are stored as naive UTC. A fixture's schedule day is the
UTC calendar date of kickoff (e.g. Brasileirão evening = still that UTC day,
even when Beijing clock already shows next morning).
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone


def utc_today() -> date:
    return datetime.now(timezone.utc).date()


def utc_day_range(day: date) -> tuple[datetime, datetime]:
    """Naive UTC [start, end) for one match day."""
    start = datetime.combine(day, time.min)
    end = datetime.combine(day + timedelta(days=1), time.min)
    return start, end


def utc_span_range(start_day: date, end_day: date) -> tuple[datetime, datetime]:
    """Naive UTC [start, end) spanning inclusive match days."""
    start, _ = utc_day_range(start_day)
    _, end = utc_day_range(end_day)
    return start, end
