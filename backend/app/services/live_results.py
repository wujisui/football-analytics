"""Subscribed hot-match score refresh.

The daily 07:00 results job is unchanged. This planner only decides when a
subscribed extra pass should call the official date feed: while a hot match
is inside its post-kickoff window, and only for those kickoff UTC dates.
When nothing is in that window, the next run is the next hot kickoff, not
another 30-minute wake-up.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.models.fixture import Fixture
from app.models.league import League

LIVE_RESULTS_WINDOW = timedelta(hours=4)
LIVE_RESULTS_INTERVAL = timedelta(minutes=30)
FULL_BATCH_COOLDOWN = timedelta(minutes=5)
# Local rows stay pending until a post-kickoff fetch rewrites them.
ACTIVE_STATUSES = ("pending", "live")


@dataclass(frozen=True)
class LiveResultsPlan:
    fetch_dates: tuple[date, ...]
    next_run: datetime


def _as_utc(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def _slot_on_local_day(local_now: datetime, hour: int, minute: int) -> datetime:
    return local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)


def _cooldown_slot(
    now: datetime,
    full_slots: tuple[tuple[int, int], ...],
    scheduler_tz: ZoneInfo,
    cooldown: timedelta,
) -> datetime | None:
    local_now = now.astimezone(scheduler_tz)
    for hour, minute in full_slots:
        slot = _slot_on_local_day(local_now, hour, minute)
        if slot <= local_now < slot + cooldown:
            return slot
    return None


def _after_interval(
    candidate: datetime,
    full_slots: tuple[tuple[int, int], ...],
    scheduler_tz: ZoneInfo,
    interval: timedelta,
    cooldown: timedelta,
) -> datetime:
    """Keep the next pass off the minutes a full batch already spends on scores."""
    local = candidate.astimezone(scheduler_tz)
    for hour, minute in full_slots:
        slot = _slot_on_local_day(local, hour, minute)
        if slot <= local < slot + cooldown:
            return (slot + interval).astimezone(timezone.utc)
    return candidate


def _next_full_slot(
    now: datetime,
    full_slots: tuple[tuple[int, int], ...],
    scheduler_tz: ZoneInfo,
) -> datetime:
    local_now = now.astimezone(scheduler_tz)
    candidates: list[datetime] = []
    for hour, minute in full_slots:
        slot = _slot_on_local_day(local_now, hour, minute)
        if slot <= local_now:
            slot += timedelta(days=1)
        candidates.append(slot)
    return min(candidates).astimezone(timezone.utc)


def plan_live_results(
    *,
    now: datetime,
    active_kickoffs: list[datetime],
    next_kickoff: datetime | None,
    full_slots: tuple[tuple[int, int], ...],
    scheduler_tz: ZoneInfo,
    interval: timedelta = LIVE_RESULTS_INTERVAL,
    window: timedelta = LIVE_RESULTS_WINDOW,
    cooldown: timedelta = FULL_BATCH_COOLDOWN,
) -> LiveResultsPlan:
    """Choose the UTC dates to fetch and the single next wake-up."""
    current = _as_utc(now)
    active = [
        _as_utc(kickoff)
        for kickoff in active_kickoffs
        if current - window < _as_utc(kickoff) <= current
    ]
    upcoming = _as_utc(next_kickoff) if next_kickoff is not None else None
    if upcoming is not None and upcoming <= current:
        upcoming = None

    if active:
        blocked = _cooldown_slot(current, full_slots, scheduler_tz, cooldown)
        fetch_dates = (
            ()
            if blocked is not None
            else tuple(sorted({kickoff.date() for kickoff in active}))
        )
        if blocked is not None:
            next_run = (blocked + interval).astimezone(timezone.utc)
        else:
            next_run = _after_interval(
                current + interval,
                full_slots,
                scheduler_tz,
                interval,
                cooldown,
            )
        return LiveResultsPlan(fetch_dates, next_run)

    if upcoming is not None:
        return LiveResultsPlan((), upcoming)

    return LiveResultsPlan(
        (),
        _next_full_slot(current, full_slots, scheduler_tz) + timedelta(minutes=2),
    )


def _naive_utc(moment: datetime) -> datetime:
    return _as_utc(moment).replace(tzinfo=None)


async def load_live_results_candidates(
    now: datetime,
) -> tuple[list[datetime], datetime | None]:
    """Hot kickoffs inside the live window, and the next hot kickoff after now."""
    current = _naive_utc(now)
    window_start = current - LIVE_RESULTS_WINDOW
    async with AsyncSessionLocal() as session:
        active_rows = (
            await session.execute(
                select(Fixture.date)
                .join(League, League.id == Fixture.league_id)
                .where(
                    League.is_hot.is_(True),
                    Fixture.status.in_(ACTIVE_STATUSES),
                    Fixture.date > window_start,
                    Fixture.date <= current,
                )
            )
        ).scalars().all()
        upcoming = (
            await session.execute(
                select(Fixture.date)
                .join(League, League.id == Fixture.league_id)
                .where(
                    League.is_hot.is_(True),
                    Fixture.status.in_(ACTIVE_STATUSES),
                    Fixture.date > current,
                )
                .order_by(Fixture.date.asc())
                .limit(1)
            )
        ).scalar_one_or_none()
    active = [_as_utc(kickoff) for kickoff in active_rows]
    return active, (_as_utc(upcoming) if upcoming is not None else None)


async def build_live_results_plan(now: datetime | None = None) -> LiveResultsPlan:
    from app.tasks.scheduler import SUBSCRIBED_FULL_SYNC_SLOTS

    current = _as_utc(now or datetime.now(timezone.utc))
    active, upcoming = await load_live_results_candidates(current)
    return plan_live_results(
        now=current,
        active_kickoffs=active,
        next_kickoff=upcoming,
        full_slots=SUBSCRIBED_FULL_SYNC_SLOTS,
        scheduler_tz=ZoneInfo(get_settings().SCHEDULER_TIMEZONE),
    )


async def scoreboard_fingerprint(days: list[date]) -> tuple:
    """Identity of scores and statuses on the UTC dates just requested."""
    if not days:
        return ()
    clauses = []
    for day in sorted(set(days)):
        start = datetime(day.year, day.month, day.day)
        clauses.append((Fixture.date >= start) & (Fixture.date < start + timedelta(days=1)))
    window = clauses[0]
    for clause in clauses[1:]:
        window = window | clause
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(
                    Fixture.id,
                    Fixture.status,
                    Fixture.status_short,
                    Fixture.home_goals,
                    Fixture.away_goals,
                ).where(window)
            )
        ).all()
    return tuple(sorted(rows, key=lambda row: row[0]))
