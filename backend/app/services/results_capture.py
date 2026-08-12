"""Kickoff-time boundary between 未开赛 lists and 赛果, plus FT score backfill."""

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
# 用户点开详情时补拉比分的时间上限；更早的场次交给定时批次回写。
LIVE_SCORE_REFRESH_HOURS = 12
UNFINISHED_STATUSES = frozenset({"pending", "live"})


def results_capture_cutoff(now: datetime | None = None) -> datetime:
    return (now or datetime.utcnow()) - timedelta(hours=STALE_RESULT_HOURS)


def is_stale_live_row(previous_status: str | None, incoming_status: str) -> bool:
    """Official day feeds sometimes replay a live code for an already finished match."""
    return previous_status == "finished" and incoming_status in {"pending", "live"}


def stuck_live_clause(now: datetime | None = None) -> ColumnElement[bool]:
    """Kicked off long ago, yet the feed still reports it as in play."""
    cutoff = (now or datetime.utcnow()) - timedelta(hours=STUCK_LIVE_HOURS)
    return and_(Fixture.status == "live", Fixture.date <= cutoff)


def as_naive_utc(value: datetime) -> datetime:
    """Fixtures are stored naive UTC; feed payloads carry offsets."""
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def prematch_list_clause(now: datetime | None = None) -> ColumnElement[bool]:
    """【比赛】：开赛时刻仍在未来；不依赖可能滞后的本地状态。"""
    return Fixture.date > (now or datetime.utcnow())


def results_list_clause(now: datetime | None = None) -> ColumnElement[bool]:
    """【赛果】：开赛时刻已到；不依赖可能仍是 pending 的本地状态。"""
    return Fixture.date <= (now or datetime.utcnow())


def results_list_score(
    status: str | None,
    home_goals: int | None,
    away_goals: int | None,
) -> tuple[int | None, int | None]:
    """进行中但尚无官方比分时，赛果列表统一展示 0:0 占位。"""
    if (status or "").strip().lower() in UNFINISHED_STATUSES and (
        home_goals is None or away_goals is None
    ):
        return 0, 0
    return home_goals, away_goals


def needs_live_score_refresh(
    status: str | None,
    fixture_date: datetime,
    now: datetime | None = None,
) -> bool:
    """已开赛未完场：用户打开详情时值得为它补一次官方比分。"""
    if (status or "").strip().lower() not in UNFINISHED_STATUSES:
        return False
    current = now or datetime.utcnow()
    kickoff = as_naive_utc(fixture_date)
    if kickoff > current:
        return False
    return current - kickoff <= timedelta(hours=LIVE_SCORE_REFRESH_HOURS)


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
    kickoff = as_naive_utc(fixture_date)
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
