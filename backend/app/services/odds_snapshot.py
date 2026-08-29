"""Single source of truth for pre-match odds snapshot clocks and validity."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

ODDS_SNAPSHOT_COLUMNS = (
    "odds_json",
    "odds_opening_json",
    "odds_mid_json",
    "odds_late_json",
)


def as_utc(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def utc_iso(value: datetime) -> str:
    parsed = as_utc(value)
    if parsed is None:  # pragma: no cover - datetime input is always parseable
        raise ValueError("A valid datetime is required")
    return parsed.isoformat().replace("+00:00", "Z")


def is_fixture_prematch(
    *,
    match_start_time: datetime | str | None,
    now: datetime | None = None,
) -> bool:
    """Mirror the product's 【比赛】 boundary: kickoff is still in the future."""
    kickoff = as_utc(match_start_time)
    clock = as_utc(now or datetime.now(timezone.utc))
    return bool(kickoff is not None and clock is not None and clock < kickoff)


def annotate_odds_snapshot(
    board: dict[str, Any],
    *,
    scraped_at: datetime | str,
    match_start_time: datetime | str,
    role: str | None = None,
) -> dict[str, Any]:
    """Attach immutable collection clocks and the live/valid classification."""
    scraped = as_utc(scraped_at)
    kickoff = as_utc(match_start_time)
    if scraped is None or kickoff is None:
        raise ValueError("Odds snapshots require scraped_at and match_start_time")
    is_live = scraped >= kickoff
    result = {
        **board,
        "captured_at": utc_iso(scraped),  # compatibility for existing clients
        "scraped_at": utc_iso(scraped),
        "match_start_time": utc_iso(kickoff),
        "is_live": is_live,
        "valid": not is_live,
    }
    if role is not None:
        result["role"] = role
    return result


def normalize_odds_snapshot(
    board: Any,
    *,
    match_start_time: datetime | str | None = None,
    fixture_id: int | None = None,
    stage: str = "current",
    log_invalid: bool = True,
) -> dict[str, Any]:
    """Drop only boards proven to be live. Frozen pre-match rows stay as-is.

    Legacy ``captured_at`` is accepted as ``scraped_at``. Missing clocks cannot
    prove a live board, so those frozen snapshots remain available for analysis.
    """
    if not isinstance(board, dict):
        return {"available": False}
    if not board.get("available"):
        return board

    scraped = as_utc(board.get("scraped_at") or board.get("captured_at"))
    kickoff = as_utc(board.get("match_start_time") or match_start_time)
    invalid_reason: str | None = None
    if bool(board.get("is_live")) or board.get("valid") is False:
        invalid_reason = "live_odds"
    elif scraped is not None and kickoff is not None and scraped >= kickoff:
        invalid_reason = "live_odds"

    if invalid_reason:
        if log_invalid:
            logger.warning(
                "Skipping invalid odds snapshot fixture=%s stage=%s reason=%s "
                "scraped_at=%s match_start_time=%s",
                fixture_id,
                stage,
                invalid_reason,
                board.get("scraped_at") or board.get("captured_at"),
                board.get("match_start_time") or match_start_time,
            )
        return {
            "available": False,
            "invalid": True,
            "invalid_reason": invalid_reason,
            "scraped_at": utc_iso(scraped) if scraped else None,
            "captured_at": utc_iso(scraped) if scraped else None,
            "match_start_time": utc_iso(kickoff) if kickoff else None,
            "is_live": bool(scraped and kickoff and scraped >= kickoff),
            "valid": False,
        }

    if scraped is not None and kickoff is not None:
        return annotate_odds_snapshot(
            board,
            scraped_at=scraped,
            match_start_time=kickoff,
            role=str(board.get("role")) if board.get("role") is not None else None,
        )
    result = dict(board)
    if scraped is not None:
        result["scraped_at"] = utc_iso(scraped)
        result["captured_at"] = utc_iso(scraped)
    if kickoff is not None:
        result["match_start_time"] = utc_iso(kickoff)
    result["is_live"] = False
    result["valid"] = True
    return result


def classify_board_clock(
    board: Any,
    *,
    match_start_time: datetime | str | None,
) -> str | None:
    """Return ``live``, ``ok``, or None when the JSON is not an available board."""
    if not isinstance(board, dict) or not board.get("available"):
        return None
    scraped = as_utc(board.get("scraped_at") or board.get("captured_at"))
    kickoff = as_utc(board.get("match_start_time") or match_start_time)
    if scraped is not None and kickoff is not None and scraped >= kickoff:
        return "live"
    return "ok"


def _load_board_json(raw: str | None) -> dict[str, Any]:
    import json

    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


async def audit_stored_live_odds(session: Any) -> dict[str, Any]:
    """Read-only scan: count frozen boards whose capture time is at/after kickoff."""
    from sqlalchemy import select

    from app.models.fixture import Fixture
    from app.models.pre_match_data import PreMatchData
    from app.models.team import Team

    rows = (
        await session.execute(
            select(PreMatchData, Fixture)
            .join(Fixture, Fixture.id == PreMatchData.fixture_id)
            .order_by(Fixture.date.asc(), Fixture.id.asc())
        )
    ).all()
    live_items: list[dict[str, Any]] = []
    missing_clock = 0
    boards_scanned = 0
    for stored, fixture in rows:
        stages: dict[str, dict[str, Any]] = {}
        live_stages: list[str] = []
        for column, stage in (
            ("odds_json", "current"),
            ("odds_opening_json", "opening"),
            ("odds_mid_json", "mid"),
            ("odds_late_json", "late"),
        ):
            board = _load_board_json(getattr(stored, column, None))
            if not board.get("available"):
                continue
            boards_scanned += 1
            scraped = as_utc(board.get("scraped_at") or board.get("captured_at"))
            kickoff = as_utc(board.get("match_start_time") or fixture.date)
            status = classify_board_clock(board, match_start_time=fixture.date)
            if status is None:
                continue
            if scraped is None:
                missing_clock += 1
            detail = {
                "stage": stage,
                "scraped_at": utc_iso(scraped) if scraped else None,
                "match_start_time": utc_iso(kickoff) if kickoff else None,
                "status": status,
            }
            if scraped is not None and kickoff is not None:
                detail["delta_sec"] = int((scraped - kickoff).total_seconds())
            stages[stage] = detail
            if status == "live":
                live_stages.append(stage)
        if not live_stages:
            continue
        home = await session.get(Team, fixture.home_team_id)
        away = await session.get(Team, fixture.away_team_id)
        live_items.append(
            {
                "fixture_id": int(fixture.id),
                "kickoff": utc_iso(as_utc(fixture.date)) if as_utc(fixture.date) else None,
                "status": fixture.status,
                "league_id": int(fixture.league_id),
                "home": getattr(home, "name", None),
                "away": getattr(away, "name", None),
                "live_stages": live_stages,
                "stages": stages,
            }
        )
    return {
        "generated_at": utc_iso(datetime.now(timezone.utc)),
        "rows_scanned": len(rows),
        "boards_scanned": boards_scanned,
        "missing_clock_boards": missing_clock,
        "live_board_fixtures": len(live_items),
        "live_boards": sum(len(item["live_stages"]) for item in live_items),
        "items": live_items,
    }
