"""League-season standings snapshots for list ranks (shared, not per-fixture)."""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.fixture import Fixture
from app.models.league import League
from app.models.league_standing import LeagueStanding
from app.services.api_utils import extract_items, first_value
from app.services.calendar_tz import utc_span_range
from app.services.prematch_package import dumps_json, loads_json

logger = logging.getLogger(__name__)


def standings_season_for_league(season: str | None) -> str:
    """Resolve the season string used for /standings (free plan clamps to 2024)."""
    text = (season or str(datetime.utcnow().year)).strip() or str(datetime.utcnow().year)
    if get_settings().uses_full_history:
        return text
    try:
        year = int(str(text)[:4])
        if year > 2024:
            return "2024"
    except ValueError:
        return "2024"
    return text


def parse_standings_table(
    payload: dict[str, Any],
    *,
    league_id: int | None = None,
    league_name: str | None = None,
) -> dict[str, Any]:
    """Flatten official /standings into team_id → rank for local reuse."""
    by_team: dict[str, dict[str, Any]] = {}
    resolved_league_id = league_id
    resolved_league_name = league_name or ""

    for item in extract_items(payload):
        league = item.get("league") if isinstance(item.get("league"), dict) else item
        if not isinstance(league, dict):
            continue
        if resolved_league_id is None:
            lid = first_value(league, [["id"]])
            if lid is not None:
                resolved_league_id = int(lid)
        if not resolved_league_name:
            resolved_league_name = str(first_value(league, [["name"]], "") or "")
        tables = league.get("standings") or item.get("standings") or []
        groups = tables if isinstance(tables, list) else []
        for group in groups:
            rows = group if isinstance(group, list) else [group]
            for row in rows:
                if not isinstance(row, dict):
                    continue
                tid = first_value(row, [["team", "id"]])
                if tid is None:
                    continue
                rank = first_value(row, [["rank"], ["position"]])
                rank_i = int(rank) if rank is not None else None
                if rank_i is None:
                    continue
                gname = first_value(row, [["group"], ["description"]])
                entry: dict[str, Any] = {"rank": rank_i}
                if gname:
                    entry["group"] = str(gname)
                by_team[str(int(tid))] = entry

    return {
        "by_team_id": by_team,
        "league_id": resolved_league_id,
        "league_name": resolved_league_name,
        "fetched": True,
        "available": bool(by_team),
        "scope": "competition",
    }


def snippet_from_ranks(
    ranks_payload: dict[str, Any] | None,
    home_team_id: int,
    away_team_id: int,
    *,
    league_id: int | None = None,
    league_name: str | None = None,
) -> dict[str, Any]:
    """Build the per-fixture standings snippet used by list/detail/ML."""
    payload = ranks_payload if isinstance(ranks_payload, dict) else {}
    by_team = payload.get("by_team_id") if isinstance(payload.get("by_team_id"), dict) else {}
    home = by_team.get(str(int(home_team_id)))
    away = by_team.get(str(int(away_team_id)))
    home_rank = home.get("rank") if isinstance(home, dict) else None
    away_rank = away.get("rank") if isinstance(away, dict) else None
    group = None
    if isinstance(home, dict) and home.get("group"):
        group = str(home["group"])
    elif isinstance(away, dict) and away.get("group"):
        group = str(away["group"])
    return {
        "available": home_rank is not None or away_rank is not None,
        "league_id": payload.get("league_id") or league_id,
        "league_name": payload.get("league_name") or league_name or "",
        "group": group,
        "home_rank": home_rank,
        "away_rank": away_rank,
        "scope": "competition",
        "fetched": bool(payload.get("fetched")),
    }


async def get_league_standing(
    session: AsyncSession,
    league_id: int,
    season: str,
) -> LeagueStanding | None:
    return (
        await session.execute(
            select(LeagueStanding).where(
                LeagueStanding.league_id == int(league_id),
                LeagueStanding.season == str(season),
            )
        )
    ).scalar_one_or_none()


async def load_standings_maps(
    session: AsyncSession,
    league_seasons: set[tuple[int, str]],
) -> dict[tuple[int, str], dict[str, Any]]:
    """Bulk-load ranks payloads keyed by (league_id, season)."""
    if not league_seasons:
        return {}
    league_ids = {lid for lid, _ in league_seasons}
    rows = (
        await session.execute(
            select(LeagueStanding).where(LeagueStanding.league_id.in_(list(league_ids)))
        )
    ).scalars().all()
    out: dict[tuple[int, str], dict[str, Any]] = {}
    wanted = {(int(lid), str(season)) for lid, season in league_seasons}
    for row in rows:
        key = (int(row.league_id), str(row.season))
        if key not in wanted:
            continue
        payload = loads_json(row.ranks_json, {}) or {}
        if isinstance(payload, dict):
            out[key] = payload
    return out


def fixture_standing_key(fixture: Fixture) -> tuple[int, str] | None:
    league = fixture.league
    if league is None:
        return None
    season = standings_season_for_league(league.season)
    return int(fixture.league_id), season


async def upsert_league_standing(
    session: AsyncSession,
    *,
    league_id: int,
    season: str,
    payload: dict[str, Any],
    league_name: str | None = None,
) -> LeagueStanding:
    table = parse_standings_table(
        payload,
        league_id=league_id,
        league_name=league_name,
    )
    row = await get_league_standing(session, league_id, season)
    text = dumps_json(table) or "{}"
    name = str(table.get("league_name") or league_name or "")
    if row is None:
        row = LeagueStanding(
            league_id=int(league_id),
            season=str(season),
            league_name=name,
            ranks_json=text,
        )
        session.add(row)
    else:
        row.league_name = name or row.league_name
        row.ranks_json = text
        row.updated_at = datetime.utcnow()
    await session.flush()
    return row


def _updated_on_local_day(updated_at: datetime | None, local_today: date, tz: ZoneInfo) -> bool:
    if updated_at is None:
        return False
    if updated_at.tzinfo is None:
        # Stored as naive UTC-ish timestamps from server_default / utcnow.
        local = updated_at.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz).date()
    else:
        local = updated_at.astimezone(tz).date()
    return local == local_today


async def sync_league_standings_for_dates(
    fetcher: Any,
    days: list[date],
    *,
    force: bool = False,
) -> dict[str, int]:
    """Fetch standings once per league+season that has fixtures on ``days``.

    Same local calendar day skips leagues already refreshed (unless ``force``).
    """
    assert fetcher.session is not None
    session: AsyncSession = fetcher.session
    settings = get_settings()
    tz = ZoneInfo(settings.SCHEDULER_TIMEZONE)
    local_today = datetime.now(tz).date()

    if not days:
        return {"leagues": 0, "fetched": 0, "skipped": 0, "failed": 0}

    start, end = utc_span_range(min(days), max(days))
    fixtures = (
        await session.execute(
            select(Fixture).where(Fixture.date >= start, Fixture.date < end)
        )
    ).scalars().all()
    league_ids = sorted({int(f.league_id) for f in fixtures})
    if not league_ids:
        return {"leagues": 0, "fetched": 0, "skipped": 0, "failed": 0}

    leagues = {
        int(row.id): row
        for row in (
            await session.execute(select(League).where(League.id.in_(league_ids)))
        ).scalars().all()
    }

    fetched = 0
    skipped = 0
    failed = 0
    for league_id in league_ids:
        league = leagues.get(league_id)
        season = standings_season_for_league(league.season if league else None)
        existing = await get_league_standing(session, league_id, season)
        if (
            not force
            and existing is not None
            and _updated_on_local_day(existing.updated_at, local_today, tz)
        ):
            skipped += 1
            continue
        try:
            payload = await fetcher.fetch_standings(league_id, season)
            await upsert_league_standing(
                session,
                league_id=league_id,
                season=season,
                payload=payload,
                league_name=league.name if league else None,
            )
            fetched += 1
        except Exception as exc:
            failed += 1
            logger.warning(
                "league standings sync failed league=%s season=%s: %s",
                league_id,
                season,
                exc,
            )

    await session.commit()
    logger.info(
        "league standings sync leagues=%s fetched=%s skipped=%s failed=%s",
        len(league_ids),
        fetched,
        skipped,
        failed,
    )
    return {
        "leagues": len(league_ids),
        "fetched": fetched,
        "skipped": skipped,
        "failed": failed,
    }


async def resolve_fixture_standings(
    session: AsyncSession,
    fixture: Fixture,
    *,
    stored_snippet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Prefer shared league snapshot; fall back to per-fixture standings_json."""
    key = fixture_standing_key(fixture)
    if key is not None:
        row = await get_league_standing(session, key[0], key[1])
        if row is not None:
            payload = loads_json(row.ranks_json, {}) or {}
            snippet = snippet_from_ranks(
                payload if isinstance(payload, dict) else {},
                fixture.home_team_id,
                fixture.away_team_id,
                league_id=fixture.league_id,
                league_name=fixture.league.name if fixture.league else None,
            )
            if snippet.get("available") or snippet.get("fetched"):
                return snippet
    if isinstance(stored_snippet, dict) and stored_snippet:
        return stored_snippet
    return {
        "available": False,
        "league_id": fixture.league_id,
        "league_name": fixture.league.name if fixture.league else "",
        "home_rank": None,
        "away_rank": None,
        "scope": "competition",
        "fetched": False,
    }


# Re-exported helpers used by list / detail / sync callers.
__all__ = [
    "fixture_standing_key",
    "get_league_standing",
    "load_standings_maps",
    "parse_standings_table",
    "resolve_fixture_standings",
    "snippet_from_ranks",
    "standings_season_for_league",
    "sync_league_standings_for_dates",
    "upsert_league_standing",
]
