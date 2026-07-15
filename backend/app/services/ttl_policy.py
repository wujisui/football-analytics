"""Pre-match analysis TTL policy (not live-score oriented).

Product goal:
- Prepare odds / H2H / lineups / injuries before kickoff
- After kickoff (or finished): never call API-Sports again for that fixture
- Historical review always reads local DB snapshots / pre_match_data
"""

from __future__ import annotations

from datetime import datetime, timezone

# Stable catalog
TTL_LEAGUES = 7 * 24 * 3600
TTL_TEAMS = 7 * 24 * 3600

# Schedule discovery (how often we refresh "today / upcoming" lists)
TTL_FIXTURES_TODAY = 60 * 60
TTL_FIXTURES_UPCOMING = 6 * 3600

# Pre-match analysis refresh (only while kickoff is still in the future)
TTL_ANALYSIS_FAR = 24 * 3600  # > 72h — World Cup etc., prepare early
TTL_ANALYSIS_MID = 12 * 3600  # 24–72h
TTL_ANALYSIS_MATCHDAY = 3 * 3600  # 6–24h — odds start to move
TTL_ANALYSIS_NEAR = 60 * 60  # 0–6h — lineups / late odds, still not live polling

TTL_SNAPSHOT_FAR = 48 * 3600
TTL_SNAPSHOT_MID = 24 * 3600
TTL_SNAPSHOT_MATCHDAY = 3 * 3600
TTL_SNAPSHOT_NEAR = 60 * 3600

# Short Redis hot layer; durable truth is SQLite
TTL_ANALYSIS_REDIS = 10 * 60

TTL_FIXTURE_DETAIL_NEAR = 30 * 60
TTL_FIXTURE_DETAIL_MATCHDAY = 2 * 3600
TTL_FIXTURE_DETAIL_FAR = 12 * 3600

FINISHED_STATUSES = {
    "finished",
    "ft",
    "aet",
    "pen",
    "cancelled",
    "postponed",
    "abandoned",
}

# Mapped statuses from our own DB (see api_utils.map_fixture_status)
LIVE_OR_DONE_BLOCK_REFRESH = FINISHED_STATUSES | {
    "live",
}


def ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def hours_until_kickoff(fixture_date: datetime | None, now: datetime | None = None) -> float | None:
    kickoff = ensure_utc(fixture_date)
    if kickoff is None:
        return None
    current = ensure_utc(now) or datetime.now(timezone.utc)
    return (kickoff - current).total_seconds() / 3600


def is_finished_status(status: str | None) -> bool:
    if not status:
        return False
    return status.strip().lower() in FINISHED_STATUSES


def should_stop_api_refresh(
    fixture_date: datetime | None,
    status: str | None = None,
    now: datetime | None = None,
) -> bool:
    """True once the match has started or is finished — analysis product freezes."""
    if status and status.strip().lower() in LIVE_OR_DONE_BLOCK_REFRESH:
        return True
    hours = hours_until_kickoff(fixture_date, now=now)
    if hours is not None and hours < 0:
        return True
    return False


# Exam fields: once kickoff has passed, these must never be rewritten
# (rewriting after the fact = grading with answers known).
PREDICTION_EXAM_FIELDS: tuple[str, ...] = (
    "home_win_prob",
    "draw_prob",
    "away_win_prob",
    "recommendation",
    "score_hint",
    "goal_lean",
    "both_score_lean",
    "handicap_lean",
)


def is_prediction_exam_locked(
    fixture_date: datetime | None,
    status: str | None = None,
    now: datetime | None = None,
) -> bool:
    """True → refuse to write/overwrite prediction snapshot fields."""
    return should_stop_api_refresh(fixture_date, status=status, now=now)


def has_exam_prediction_snapshot(record: object | None) -> bool:
    """True when a real (non-placeholder) recommendation was already stored."""
    if record is None:
        return False
    rec = (getattr(record, "recommendation", None) or "").strip()
    return bool(rec and rec != "待分析")


def refresh_ttl_seconds(
    fixture_date: datetime | None,
    *,
    status: str | None = None,
    kind: str = "analysis",
) -> int | None:
    """Seconds until next allowed API refresh, or None = never refresh (local only)."""
    if should_stop_api_refresh(fixture_date, status=status):
        return None

    hours = hours_until_kickoff(fixture_date)
    if hours is None:
        return TTL_ANALYSIS_MID if kind == "analysis" else TTL_SNAPSHOT_MID

    if kind == "analysis":
        far, mid, matchday, near = (
            TTL_ANALYSIS_FAR,
            TTL_ANALYSIS_MID,
            TTL_ANALYSIS_MATCHDAY,
            TTL_ANALYSIS_NEAR,
        )
        near_hours = 6
        matchday_hours = 24
    else:
        far, mid, matchday, near = (
            TTL_SNAPSHOT_FAR,
            TTL_SNAPSHOT_MID,
            TTL_SNAPSHOT_MATCHDAY,
            TTL_SNAPSHOT_NEAR,
        )
        near_hours = 6
        matchday_hours = 24

    if hours > 72:
        return far
    if hours > matchday_hours:
        return mid
    if hours > near_hours:
        return matchday
    return near


def fixture_detail_ttl(fixture_date: datetime | None, status: str | None = None) -> int:
    ttl = refresh_ttl_seconds(fixture_date, status=status, kind="snapshot")
    if ttl is None:
        # Kickoff passed: keep a long local TTL so Redis/DB still serve without API
        return TTL_FIXTURE_DETAIL_FAR
    hours = hours_until_kickoff(fixture_date)
    if hours is not None and 0 <= hours <= 6:
        return TTL_FIXTURE_DETAIL_NEAR
    if hours is not None and hours <= 24:
        return TTL_FIXTURE_DETAIL_MATCHDAY
    return min(ttl, TTL_FIXTURE_DETAIL_FAR)


def describe_ttl_policy() -> dict[str, str]:
    return {
        "product": "pre-match analysis only (not live scores)",
        "after_kickoff": "no API refresh; serve local DB forever until cleanup",
        "far_>72h": f"analysis refresh every {TTL_ANALYSIS_FAR // 3600}h",
        "mid_24_72h": f"analysis refresh every {TTL_ANALYSIS_MID // 3600}h",
        "matchday_6_24h": f"analysis refresh every {TTL_ANALYSIS_MATCHDAY // 3600}h",
        "near_0_6h": f"analysis refresh every {TTL_ANALYSIS_NEAR // 60}min",
        "inputs": "pre-match odds, H2H, lineups, injuries, bench — freeze at kickoff",
    }
