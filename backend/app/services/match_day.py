"""Fixture-local match-day resolution from offline geographic data.

The provider returns kickoff instants in UTC.  Its ``fixture.timezone`` field is
the requested response timezone (also UTC in our feeds), not the venue's zone.
Resolve the venue independently and persist the result so every downstream
consumer uses the same match-day key.
"""

from __future__ import annotations

import re
import json
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import geonamescache
import pytz
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import ColumnElement

UTC_ZONE = "UTC"

# API-Sports uses constituent-country labels that are not ISO sovereign names.
_COUNTRY_ALIASES = {
    "england": "GB",
    "northern ireland": "GB",
    "scotland": "GB",
    "wales": "GB",
    "usa": "US",
    "united states": "US",
    "south korea": "KR",
    "north korea": "KP",
    "russia": "RU",
    "turkiye": "TR",
}


@dataclass(frozen=True)
class MatchDayResolution:
    match_day: str
    timezone: str
    source: str


def fixture_match_day_expr() -> ColumnElement[str]:
    """SQL expression for the persisted venue-local day, with legacy fallback."""
    from app.models.fixture import Fixture

    return func.coalesce(Fixture.match_day, func.date(Fixture.date))


def fixture_match_day(fixture: Any) -> str:
    """Persisted venue-local day of one loaded row; UTC fallback for legacy rows.

    Python-side twin of :func:`fixture_match_day_expr` so every response and
    bucketing path spells the fallback the same way.
    """

    day = getattr(fixture, "match_day", None)
    return str(day) if day else fixture.date.strftime("%Y-%m-%d")


def _norm(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


@lru_cache(maxsize=1)
def _geo_data() -> tuple[
    dict[str, list[dict[str, Any]]],
    dict[str, str],
    dict[str, dict[str, Any]],
]:
    cache = geonamescache.GeonamesCache()
    countries = cache.get_countries()

    country_codes: dict[str, str] = {}
    for code, row in countries.items():
        for value in (row.get("name"), row.get("iso"), row.get("iso3")):
            key = _norm(str(value or ""))
            if key:
                country_codes[key] = code
    country_codes.update(_COUNTRY_ALIASES)

    cities_by_name: dict[str, list[dict[str, Any]]] = {}
    largest_city_by_country: dict[str, dict[str, Any]] = {}
    for row in cache.get_cities().values():
        code = str(row.get("countrycode") or "")
        population = int(row.get("population") or 0)
        largest = largest_city_by_country.get(code)
        if largest is None or population > int(largest.get("population") or 0):
            largest_city_by_country[code] = row

        names = {
            str(row.get("name") or ""),
            str(row.get("asciiname") or ""),
        }
        alternatives = row.get("alternatenames")
        if isinstance(alternatives, list):
            names.update(str(item) for item in alternatives)
        for name in names:
            key = _norm(name)
            if key:
                cities_by_name.setdefault(key, []).append(row)

    return cities_by_name, country_codes, largest_city_by_country


def country_code(country: str | None) -> str | None:
    key = _norm(country)
    if not key or key in {"world", "unknown"}:
        return None
    return _geo_data()[1].get(key)


@lru_cache(maxsize=2048)
def timezone_for_city(city: str | None, country: str | None = None) -> str | None:
    """Resolve an IANA zone for an official venue city.

    Venue values sometimes append a state/province (``São Paulo, São Paulo``);
    try the full value first, then its first comma-separated segment.
    """

    raw = str(city or "").strip()
    if not raw:
        return None
    code = country_code(country)
    cities_by_name = _geo_data()[0]
    keys = [_norm(raw)]
    if "," in raw:
        keys.append(_norm(raw.split(",", 1)[0]))

    candidates: list[dict[str, Any]] = []
    for key in keys:
        candidates = cities_by_name.get(key, [])
        if candidates:
            break
    if code:
        matching = [row for row in candidates if row.get("countrycode") == code]
        if matching:
            candidates = matching
    if not candidates:
        return None
    row = max(candidates, key=lambda item: int(item.get("population") or 0))
    zone = str(row.get("timezone") or "").strip()
    return zone or None


@lru_cache(maxsize=256)
def timezone_for_country(country: str | None) -> str | None:
    """Resolve a representative football timezone for a country.

    Single-zone countries are exact.  For multi-zone countries use their
    largest city from the same offline GeoNames dataset instead of maintaining
    a hand-written timezone table.
    """

    code = country_code(country)
    if not code:
        return None
    zones = list(pytz.country_timezones.get(code, ()))
    if len(zones) == 1:
        return zones[0]
    largest = _geo_data()[2].get(code)
    zone = str((largest or {}).get("timezone") or "").strip()
    if zone:
        return zone
    return zones[0] if zones else None


def valid_timezone(value: str | None) -> str | None:
    zone = str(value or "").strip()
    if not zone:
        return None
    try:
        ZoneInfo(zone)
    except ZoneInfoNotFoundError:
        return None
    return zone


def infer_team_timezone(
    *,
    venue_city: str | None,
    country: str | None,
) -> tuple[str | None, str | None]:
    zone = timezone_for_city(venue_city, country)
    if zone:
        return zone, "team_venue_city"
    zone = timezone_for_country(country)
    if zone:
        return zone, "team_country"
    return None, None


def resolve_match_day(
    kickoff: datetime,
    *,
    venue_city: str | None = None,
    league_country: str | None = None,
    home_team_timezone: str | None = None,
) -> MatchDayResolution:
    """Resolve fixture-local calendar day with an auditable fallback source."""

    zone = timezone_for_city(venue_city, league_country)
    source = "venue_city"
    if not zone:
        zone = timezone_for_country(league_country)
        source = "league_country"
    if not zone:
        zone = valid_timezone(home_team_timezone)
        source = "home_team"
    if not zone:
        zone = UTC_ZONE
        source = "utc"

    aware = kickoff
    if aware.tzinfo is None:
        aware = aware.replace(tzinfo=timezone.utc)
    else:
        aware = aware.astimezone(timezone.utc)
    day = aware.astimezone(ZoneInfo(zone)).date().isoformat()
    return MatchDayResolution(match_day=day, timezone=zone, source=source)


async def backfill_fixture_match_days(db: AsyncSession) -> dict[str, Any]:
    """Enrich locations from local snapshots and rebuild every fixture day.

    This is deliberately local-only: no provider request and no API quota use.
    """

    from app.models.api_snapshot import ApiSnapshot
    from app.models.fixture import Fixture
    from app.models.team import Team
    from app.core.config import get_settings
    from app.services.providers import get_api_provider

    provider = get_api_provider(get_settings())
    snapshots = (
        await db.execute(
            select(ApiSnapshot).where(
                or_(
                    ApiSnapshot.cache_key.like("api:football:teams:league:%"),
                    ApiSnapshot.cache_key.like("api:football:fixtures:date:%"),
                )
            )
        )
    ).scalars()

    team_metadata: dict[int, dict[str, Any]] = {}
    fixture_cities: dict[int, str] = {}
    for snapshot in snapshots:
        try:
            payload = json.loads(snapshot.payload_json)
        except (TypeError, ValueError):
            continue
        if ":teams:league:" in snapshot.cache_key:
            for row in provider.parse_teams(payload):
                team_metadata[int(row["id"])] = row
        elif ":fixtures:date:" in snapshot.cache_key:
            for row in provider.parse_fixtures(payload):
                city = str(row.get("venue_city") or "").strip()
                if city:
                    fixture_cities[int(row["id"])] = city

    enriched_teams = 0
    if team_metadata:
        teams = (
            await db.execute(select(Team).where(Team.id.in_(team_metadata)))
        ).scalars()
        for team in teams:
            row = team_metadata[team.id]
            country = str(row.get("country") or "").strip() or None
            venue_city = str(row.get("venue_city") or "").strip() or None
            zone, _source = infer_team_timezone(
                venue_city=venue_city,
                country=country,
            )
            if country:
                team.country = country
            if venue_city:
                team.venue_city = venue_city
            if zone:
                team.timezone = zone
            enriched_teams += 1

    fixtures = (
        await db.execute(
            select(Fixture).options(
                selectinload(Fixture.league),
                selectinload(Fixture.home_team),
            )
        )
    ).scalars()
    updated_fixtures = 0
    by_source: dict[str, int] = {}
    for fixture in fixtures:
        city = fixture_cities.get(fixture.id) or fixture.venue_city
        resolution = resolve_match_day(
            fixture.date,
            venue_city=city,
            league_country=fixture.league.country if fixture.league else None,
            home_team_timezone=(
                fixture.home_team.timezone if fixture.home_team else None
            ),
        )
        fixture.venue_city = city
        fixture.match_day = resolution.match_day
        fixture.match_timezone = resolution.timezone
        fixture.match_day_source = resolution.source
        by_source[resolution.source] = by_source.get(resolution.source, 0) + 1
        updated_fixtures += 1

    await db.commit()
    return {
        "teams_enriched": enriched_teams,
        "fixtures_updated": updated_fixtures,
        "by_source": by_source,
    }
