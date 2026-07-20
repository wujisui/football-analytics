import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import AsyncSessionLocal
from app.models.fixture import Fixture
from app.models.league import League
from app.models.team import Team
from app.services.api_utils import parse_remaining_requests
from app.services.team_names import backfill_team_names, team_name_zh
from app.services.cache import (
    TTL_FIXTURES_TODAY,
    TTL_HEADTOHEAD,
    TTL_LEAGUES,
    TTL_STANDINGS,
    TTL_TEAM_FORM,
    TTL_TEAM_STATISTICS,
    TTL_TEAMS,
    CacheService,
    fixture_cache_key,
    fixture_detail_ttl,
    fixtures_cache_key,
    fixtures_day_leagues_cache_key,
    fixtures_league_date_cache_key,
    fixtures_league_range_cache_key,
    get_cache_service,
    headtohead_cache_key,
    injuries_cache_key,
    leagues_cache_key,
    lineups_cache_key,
    odds_cache_key,
    predictions_cache_key,
    standings_cache_key,
    team_form_cache_key,
    team_statistics_cache_key,
    teams_cache_key,
)
from app.services.providers import get_api_provider
from app.services.snapshot_store import SnapshotStore

logger = logging.getLogger(__name__)

# Keep retries short so a single slow/429 endpoint cannot burn the analysis budget.
RETRY_DELAYS = [0.5, 1.5]


def _as_int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _api_payload_errors(payload: dict[str, Any] | None) -> Any:
    if not isinstance(payload, dict):
        return None
    errors = payload.get("errors")
    if errors is None or errors == "" or errors == [] or errors == {}:
        return None
    return errors


def _api_payload_unusable(payload: dict[str, Any] | None) -> bool:
    """True when the upstream body is an error shell (plan/rateLimit/etc.)."""
    return _api_payload_errors(payload) is not None


def _api_payload_plan_or_season_blocked(payload: dict[str, Any] | None) -> bool:
    """Free plans often block ``league+season`` for current WC / domestic seasons."""
    errors = _api_payload_errors(payload)
    if errors is None:
        return False
    text = str(errors).lower()
    return (
        "free plans do not have access" in text
        or "season" in text
        or "plan" in text
    )


class ApiKeyNotConfiguredError(RuntimeError):
    """Raised when no football API key is configured."""


def ensure_api_key_configured(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    key = settings.football_api_key
    placeholders = {
        "",
        "your_api_key_here",
        "your-api-key-here",
        "your_api_sports_key_here",
        "your_rapidapi_key_here",
    }

    if key in placeholders:
        raise ApiKeyNotConfiguredError(
            "Football API key is not configured. "
            "Copy secrets.local.env.example to secrets.local.env, "
            "set API_SPORTS_KEY (recommended) or RAPIDAPI_KEY, then retry."
        )
    return key


class FootballFetcher:
    def __init__(
        self,
        session: AsyncSession | None = None,
        cache: CacheService | None = None,
    ) -> None:
        self.settings = get_settings()
        self.provider = get_api_provider(self.settings)
        self.session = session
        self.cache = cache or get_cache_service()
        self._owns_session = session is None
        self._client: httpx.AsyncClient | None = None
        self.last_remaining_requests: int | None = None
        # AsyncSession is not safe for concurrent awaitables; package gather must serialize DB I/O.
        self._db_lock = asyncio.Lock()

    async def __aenter__(self) -> "FootballFetcher":
        ensure_api_key_configured(self.settings)
        if self.session is None:
            self.session = AsyncSessionLocal()
        await self.cache.connect()
        self._client = httpx.AsyncClient(
            base_url=self.settings.api_base_url,
            headers=self.settings.football_api_headers(),
            timeout=httpx.Timeout(8.0, connect=3.0),
            verify=self.settings.HTTP_VERIFY_SSL,
        )
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._client is not None:
            await self._client.aclose()
        if self._owns_session and self.session is not None:
            await self.session.close()

    async def _run_with_retry(self, operation: str, callback) -> Any:
        if self._client is None:
            raise RuntimeError("FootballFetcher must be used as an async context manager.")

        last_error: Exception | None = None
        attempts = len(RETRY_DELAYS) + 1

        for attempt in range(attempts):
            try:
                result = await callback(self._client)
                if self.provider.last_response is not None:
                    self.last_remaining_requests = parse_remaining_requests(
                        self.provider.last_response
                    )
                    self.cache.last_api_remaining = self.last_remaining_requests
                return result
            except Exception as exc:
                last_error = exc
                if attempt < len(RETRY_DELAYS):
                    delay = RETRY_DELAYS[attempt]
                    logger.warning(
                        "%s failed (attempt %s/%s), retrying in %ss: %s",
                        operation,
                        attempt + 1,
                        attempts,
                        delay,
                        exc,
                    )
                    await asyncio.sleep(delay)

        assert last_error is not None
        logger.error("%s failed after %s attempts: %s", operation, attempts, last_error)
        raise last_error

    async def _get_or_fetch(
        self,
        cache_key: str,
        ttl: int,
        operation: str,
        fetch_callback: Callable[[httpx.AsyncClient], Awaitable[dict[str, Any]]],
    ) -> dict[str, Any]:
        """Local-first: Redis → SQLite snapshot → official API.

        Never cache / re-serve payloads that only contain upstream ``errors``
        (free-plan season blocks, rate limits, etc.) — those must not poison
        later syncs.
        """
        cached = await self.cache.get(cache_key)
        if cached is not None and "payload" in cached:
            cached_payload = cached["payload"]
            if _api_payload_unusable(cached_payload):
                logger.warning(
                    "Dropping unusable cached payload for %s: %s",
                    cache_key,
                    _api_payload_errors(cached_payload),
                )
                await self.cache.delete(cache_key)
            else:
                self.cache.record_hit()
                logger.info(
                    "Cache hit for %s (cached at %s)",
                    cache_key,
                    cached.get("_cached_at"),
                )
                return cached_payload

        if self.settings.LOCAL_FIRST and self.session is not None:
            async with self._db_lock:
                store = SnapshotStore(self.session)
                db_payload = await store.get_valid(cache_key)
            if db_payload is not None:
                if _api_payload_unusable(db_payload):
                    logger.warning(
                        "Ignoring unusable snapshot for %s: %s",
                        cache_key,
                        _api_payload_errors(db_payload),
                    )
                else:
                    self.cache.record_hit()
                    await self.cache.set(cache_key, db_payload, ttl)
                    return db_payload

        self.cache.record_miss()
        logger.info("Cache/DB miss for %s — calling official API", cache_key)
        payload = await self._run_with_retry(operation, fetch_callback)
        if _api_payload_unusable(payload):
            logger.warning(
                "Not caching unusable API payload for %s: %s",
                cache_key,
                _api_payload_errors(payload),
            )
            return payload

        await self.cache.set(cache_key, payload, ttl)

        if self.session is not None:
            async with self._db_lock:
                store = SnapshotStore(self.session)
                await store.save(cache_key, payload, ttl)

        return payload

    async def _commit(self) -> None:
        if self.session is not None:
            async with self._db_lock:
                await self.session.commit()

    async def _upsert_league(
        self,
        league_id: int,
        name: str,
        country: str | None,
        season: str,
    ) -> League:
        assert self.session is not None
        country_value = (country or "").strip() or "Unknown"
        league = await self.session.get(League, league_id)
        if league is None:
            league = League(id=league_id, name=name, country=country_value, season=season)
            self.session.add(league)
        else:
            league.name = name
            # Don't clobber a real country with placeholder when re-seeding.
            if country_value != "Unknown" or not league.country or league.country == "Unknown":
                league.country = country_value
            league.season = season
        return league

    async def _upsert_team(
        self,
        team_id: int,
        name: str,
        logo_url: str | None = None,
    ) -> Team:
        assert self.session is not None
        display_name = team_name_zh(name, team_id) or name
        team = await self.session.get(Team, team_id)
        if team is None:
            team = Team(id=team_id, name=display_name, logo_url=logo_url)
            self.session.add(team)
        else:
            team.name = display_name
            if logo_url is not None:
                team.logo_url = logo_url
        return team

    async def _upsert_fixture(
        self,
        fixture_id: int,
        league_id: int,
        home_team_id: int,
        away_team_id: int,
        fixture_date: datetime,
        status: str,
        home_goals: int | None = None,
        away_goals: int | None = None,
        status_short: str | None = None,
        et_home_goals: int | None = None,
        et_away_goals: int | None = None,
        pen_home: int | None = None,
        pen_away: int | None = None,
    ) -> Fixture:
        assert self.session is not None
        fixture = await self.session.get(Fixture, fixture_id)
        previous_status = fixture.status if fixture is not None else None

        if fixture is None:
            fixture = Fixture(
                id=fixture_id,
                league_id=league_id,
                home_team_id=home_team_id,
                away_team_id=away_team_id,
                date=fixture_date,
                status=status,
                status_short=status_short,
                home_goals=home_goals,
                away_goals=away_goals,
                et_home_goals=et_home_goals,
                et_away_goals=et_away_goals,
                pen_home=pen_home,
                pen_away=pen_away,
            )
            self.session.add(fixture)
        else:
            fixture.league_id = league_id
            fixture.home_team_id = home_team_id
            fixture.away_team_id = away_team_id
            fixture.date = fixture_date
            fixture.status = status
            if status_short is not None:
                fixture.status_short = status_short
            # Score boards: always refresh when parser provided regulation goals.
            if home_goals is not None:
                fixture.home_goals = home_goals
            if away_goals is not None:
                fixture.away_goals = away_goals
            if status_short == "FT":
                fixture.et_home_goals = None
                fixture.et_away_goals = None
                fixture.pen_home = None
                fixture.pen_away = None
            elif status_short in {"AET", "PEN", "ET"}:
                # Overwrite ET/PEN boards on finished knockout results.
                fixture.et_home_goals = et_home_goals
                fixture.et_away_goals = et_away_goals
                fixture.pen_home = pen_home
                fixture.pen_away = pen_away
            else:
                if et_home_goals is not None:
                    fixture.et_home_goals = et_home_goals
                if et_away_goals is not None:
                    fixture.et_away_goals = et_away_goals
                if pen_home is not None:
                    fixture.pen_home = pen_home
                if pen_away is not None:
                    fixture.pen_away = pen_away

        if previous_status is not None and previous_status != status:
            await self.cache.delete(fixture_cache_key(fixture_id))
            today = fixture_date.strftime("%Y-%m-%d")
            await self.cache.delete(fixtures_cache_key(today))
            logger.info(
                "Invalidated cache for fixture %s after status change %s -> %s",
                fixture_id,
                previous_status,
                status,
            )

        return fixture

    async def invalidate_fixtures_day_cache(self, date_str: str) -> None:
        """Drop Redis + SQLite day-list cache so the next fetch hits the official API."""
        cache_key = fixtures_cache_key(date_str)
        await self.cache.delete(cache_key)
        if self.session is not None:
            async with self._db_lock:
                store = SnapshotStore(self.session)
                await store.invalidate(cache_key)

    async def _get_league_season(self, league_id: int) -> str:
        assert self.session is not None
        league = await self.session.get(League, league_id)
        if league is not None and league.season:
            return league.season
        return str(datetime.now().year)

    async def fetch_leagues(self, league_ids: list[int] | None = None) -> int:
        assert self.session is not None
        configured = self.settings.LEAGUE_IDS
        league_ids = league_ids or list(configured.values())
        if not league_ids:
            logger.warning("No league IDs configured for fetch_leagues.")
            return 0

        # Always seed from config so /leagues works even if API is rate-limited.
        id_to_name = {league_id: name for name, league_id in configured.items()}
        countries = self.settings.LEAGUE_COUNTRIES
        season_default = str(datetime.now().year)
        saved = 0
        for league_id in league_ids:
            try:
                season = (
                    self.settings.configured_season(league_id) or season_default
                )
                await self._upsert_league(
                    league_id,
                    id_to_name.get(league_id, f"League {league_id}"),
                    countries.get(league_id),
                    season,
                )
                saved += 1
            except Exception as exc:
                logger.error("Failed to seed league %s: %s", league_id, exc, exc_info=True)
        await self._commit()

        cache_key = leagues_cache_key(league_ids)
        try:
            payload = await self._get_or_fetch(
                cache_key,
                TTL_LEAGUES,
                "fetch_leagues",
                lambda client: self.provider.fetch_leagues_payload(client, league_ids),
            )
            leagues = self.provider.parse_leagues(payload, league_ids)
            for league in leagues:
                try:
                    # Keep configured display name when present; enrich country/season.
                    display_name = id_to_name.get(league["id"], league["name"])
                    await self._upsert_league(
                        league["id"],
                        display_name,
                        league["country"] or countries.get(league["id"]),
                        league["season"],
                    )
                except Exception as exc:
                    logger.error("Failed to save league %s: %s", league, exc, exc_info=True)
            await self._commit()
        except Exception as exc:
            logger.warning(
                "API enrich for leagues failed (seeded %s from config): %s",
                saved,
                exc,
            )

        self.cache.last_data_update = datetime.now()
        logger.info(
            "Saved %s leagues (config seed + optional API enrich via %s).",
            saved,
            self.provider.provider_name,
        )
        return saved

    async def fetch_teams_by_league(self, league_id: int, season: str | None = None) -> int:
        assert self.session is not None
        season = season or await self._get_league_season(league_id)
        cache_key = teams_cache_key(league_id, season)
        payload = await self._get_or_fetch(
            cache_key,
            TTL_TEAMS,
            "fetch_teams_by_league",
            lambda client: self.provider.fetch_teams_payload(client, league_id, season),
        )
        teams = self.provider.parse_teams(payload)
        saved = 0

        for team in teams:
            try:
                await self._upsert_team(team["id"], team["name"], team.get("logo_url"))
                saved += 1
            except Exception as exc:
                logger.error(
                    "Failed to save team for league %s: %s",
                    league_id,
                    exc,
                    exc_info=True,
                )

        await self._commit()
        logger.info("Saved %s teams for league %s (season %s).", saved, league_id, season)
        return saved

    async def _persist_fixtures(
        self,
        fixtures: list[dict[str, Any]],
        *,
        allowed_league_ids: set[int] | None = None,
        fetch_teams: bool = True,
    ) -> int:
        """Upsert parsed fixtures. If allowed_league_ids is set, skip others."""
        assert self.session is not None
        league_ids: set[int] = set()
        saved = 0

        for fixture in fixtures:
            league_id = int(fixture["league_id"])
            if allowed_league_ids is not None and league_id not in allowed_league_ids:
                continue
            try:
                display_name = self.settings.reference_display_name(
                    league_id,
                    str(fixture.get("league_name") or f"League {league_id}"),
                )
                await self._upsert_league(
                    league_id,
                    display_name,
                    fixture["country"],
                    fixture["season"],
                )
                await self._upsert_team(
                    fixture["home_team_id"],
                    fixture["home_team_name"],
                    fixture.get("home_logo"),
                )
                await self._upsert_team(
                    fixture["away_team_id"],
                    fixture["away_team_name"],
                    fixture.get("away_logo"),
                )
                await self._upsert_fixture(
                    fixture["id"],
                    league_id,
                    fixture["home_team_id"],
                    fixture["away_team_id"],
                    fixture["date"],
                    fixture["status"],
                    home_goals=_as_int_or_none(fixture.get("home_goals")),
                    away_goals=_as_int_or_none(fixture.get("away_goals")),
                    status_short=(
                        str(fixture["status_short"]).upper()
                        if fixture.get("status_short") is not None
                        else None
                    ),
                    et_home_goals=_as_int_or_none(fixture.get("et_home_goals")),
                    et_away_goals=_as_int_or_none(fixture.get("et_away_goals")),
                    pen_home=_as_int_or_none(fixture.get("pen_home")),
                    pen_away=_as_int_or_none(fixture.get("pen_away")),
                )
                league_ids.add(league_id)
                saved += 1
            except Exception as exc:
                logger.error("Failed to save fixture %s: %s", fixture, exc, exc_info=True)

        await self._commit()

        if fetch_teams:
            for league_id in league_ids:
                try:
                    await self.fetch_teams_by_league(league_id)
                except Exception as exc:
                    logger.error(
                        "Failed to fetch teams for league %s: %s",
                        league_id,
                        exc,
                        exc_info=True,
                    )

        self.cache.last_data_update = datetime.now()
        return saved

    async def _resolve_league_season(self, league_id: int, hint_date: date | None = None) -> str:
        """Prefer catalog season → DB league.season → calendar year of hint/today."""
        configured = self.settings.configured_season(league_id)
        if configured:
            return configured
        season = await self._get_league_season(league_id)
        if season:
            return season
        return str((hint_date or date.today()).year)

    async def discover_playing_leagues_for_date(
        self,
        day: date | None = None,
        *,
        force: bool = False,
    ) -> dict[str, Any]:
        """One worldwide ``fixtures?date=`` → unique leagues playing that day.

        Cached under ``fixtures_day_leagues_cache_key`` so filter extras cost at
        most ~1 request/day (plus free-plan pagination if any).
        """
        target = day or date.today()
        date_str = target.isoformat()
        summary_key = fixtures_day_leagues_cache_key(date_str)
        if force:
            await self.cache.delete(summary_key)

        cached = await self.cache.get(summary_key)
        if cached is not None and "payload" in cached and not force:
            payload = cached["payload"]
            if isinstance(payload, dict) and payload.get("league_ids") is not None:
                self.cache.record_hit()
                return payload

        if self.settings.LOCAL_FIRST and self.session is not None and not force:
            async with self._db_lock:
                store = SnapshotStore(self.session)
                db_payload = await store.get_valid(summary_key)
            if isinstance(db_payload, dict) and db_payload.get("league_ids") is not None:
                self.cache.record_hit()
                await self.cache.set(summary_key, db_payload, TTL_FIXTURES_TODAY)
                return db_payload

        # Reuse worldwide day fixtures cache when present; else one API call.
        day_key = fixtures_cache_key(date_str)
        if force:
            await self.cache.delete(day_key)
        try:
            raw = await self._get_or_fetch(
                day_key,
                TTL_FIXTURES_TODAY,
                "discover_playing_leagues_for_date",
                lambda client, d=date_str: self.provider.fetch_fixtures_payload(client, d),
            )
        except Exception as exc:
            logger.warning("discover_playing_leagues_for_date %s failed: %s", date_str, exc)
            return {
                "date": date_str,
                "league_ids": [],
                "leagues": {},
                "source": "error",
                "error": str(exc),
            }

        if _api_payload_unusable(raw):
            return {
                "date": date_str,
                "league_ids": [],
                "leagues": {},
                "source": "unavailable",
                "error": str(_api_payload_errors(raw)),
            }

        counts: dict[int, int] = {}
        meta: dict[int, dict[str, Any]] = {}
        for fx in self.provider.parse_fixtures(raw):
            try:
                lid = int(fx["league_id"])
            except (KeyError, TypeError, ValueError):
                continue
            counts[lid] = counts.get(lid, 0) + 1
            if lid not in meta:
                meta[lid] = {
                    "league_id": lid,
                    "league_name": str(fx.get("league_name") or ""),
                    "country": fx.get("country"),
                }

        leagues_out = {
            str(lid): {
                **meta[lid],
                "fixtures_count": counts[lid],
            }
            for lid in counts
        }
        summary: dict[str, Any] = {
            "date": date_str,
            "league_ids": sorted(counts.keys()),
            "leagues": leagues_out,
            "source": "api",
        }
        await self.cache.set(summary_key, summary, TTL_FIXTURES_TODAY)
        if self.session is not None:
            async with self._db_lock:
                store = SnapshotStore(self.session)
                await store.save(summary_key, summary, TTL_FIXTURES_TODAY)
        return summary

    async def _fetch_day_worldwide_filtered(
        self,
        day: date,
        allowed: set[int] | None,
        *,
        force: bool = False,
        fetch_teams: bool = True,
    ) -> int:
        """Worldwide ``date=``; optionally keep only ``allowed`` league IDs."""
        date_str = day.isoformat()
        cache_key = fixtures_cache_key(date_str)
        if force:
            await self.cache.delete(cache_key)
            await self.invalidate_fixtures_day_cache(date_str)
        try:
            payload = await self._get_or_fetch(
                cache_key,
                TTL_FIXTURES_TODAY,
                "fetch_fixtures_worldwide_day",
                lambda client, d=date_str: self.provider.fetch_fixtures_payload(client, d),
            )
            if _api_payload_unusable(payload):
                logger.warning(
                    "Worldwide fixtures date=%s blocked: %s",
                    date_str,
                    _api_payload_errors(payload),
                )
                return 0
            fixtures = self.provider.parse_fixtures(payload)
            saved = await self._persist_fixtures(
                fixtures,
                allowed_league_ids=allowed,
                fetch_teams=fetch_teams,
            )
            logger.info(
                "Worldwide fallback date=%s allowed=%s saved=%s",
                date_str,
                sorted(allowed),
                saved,
            )
            return saved
        except Exception as exc:
            logger.error(
                "Worldwide fixtures date=%s failed: %s",
                date_str,
                exc,
                exc_info=True,
            )
            return 0

    async def fetch_fixtures_for_date(
        self,
        target_date: date | str,
        *,
        force: bool = False,
        league_ids: list[int] | None = None,
    ) -> int:
        """Fetch one calendar day via worldwide ``date=`` (all API leagues by default)."""
        assert self.session is not None
        day = (
            target_date
            if isinstance(target_date, date)
            else date.fromisoformat(str(target_date)[:10])
        )
        allowed: set[int] | None = None
        if league_ids is not None:
            allowed = {int(x) for x in league_ids}
            if not allowed:
                logger.warning("No leagues to fetch for date %s", day.isoformat())
                return 0
        if force:
            await self.invalidate_fixtures_day_cache(day.isoformat())
        saved = await self._fetch_day_worldwide_filtered(
            day,
            allowed,
            force=force,
            fetch_teams=True,
        )
        renamed = await backfill_team_names(self.session)
        logger.info(
            "Saved %s fixtures for %s (force=%s, teams_renamed=%s).",
            saved,
            day.isoformat(),
            force,
            renamed,
        )
        return saved

    async def fetch_today_fixtures(self, *, force: bool = False) -> int:
        return await self.fetch_fixtures_for_date(date.today(), force=force)

    async def fetch_fixtures_window(
        self,
        start: date,
        end: date,
        *,
        force: bool = False,
        league_ids: list[int] | None = None,
    ) -> int:
        """Fetch ``[start, end]`` via worldwide ``date=`` (one call per day).

        When ``league_ids`` is omitted, persist every league returned by the API.
        """
        assert self.session is not None
        if end < start:
            start, end = end, start
        allowed: set[int] | None = None
        if league_ids is not None:
            allowed = {int(x) for x in league_ids}
            if not allowed:
                logger.warning(
                    "No leagues to fetch for window %s..%s",
                    start.isoformat(),
                    end.isoformat(),
                )
                return 0

        total = 0
        cursor = start
        first = True
        while cursor <= end:
            total += await self._fetch_day_worldwide_filtered(
                cursor,
                allowed,
                force=force,
                fetch_teams=first,
            )
            first = False
            cursor += timedelta(days=1)
            if cursor <= end:
                await asyncio.sleep(0.35)

        renamed = await backfill_team_names(self.session)
        logger.info(
            "Saved %s fixtures across %s..%s (force=%s, teams_renamed=%s).",
            total,
            start.isoformat(),
            end.isoformat(),
            force,
            renamed,
        )
        return total

    async def fetch_upcoming_fixtures(
        self,
        days: int | None = None,
        *,
        force: bool = False,
        league_ids: list[int] | None = None,
    ) -> int:
        """Fetch fixtures for today and the next (days-1) days via per-league ranges."""
        window = days if days is not None else self.settings.FIXTURES_LOOKAHEAD_DAYS
        window = max(1, min(window, 60))
        start = date.today()
        end = start + timedelta(days=window - 1)
        return await self.fetch_fixtures_window(
            start, end, force=force, league_ids=league_ids
        )

    async def capture_finished_results(self, lookback_days: int = 3) -> int:
        """
        One-shot result backfill for recently kicked-off fixtures still missing FT scores.

        Fetches by calendar date (not per-fixture live polling). Safe for quota.
        """
        assert self.session is not None
        from sqlalchemy import or_, select

        now = datetime.utcnow()
        # Matches usually finish within ~2h of kickoff; wait a bit before capturing.
        cutoff = now - timedelta(hours=2)
        start = (now - timedelta(days=max(1, lookback_days))).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        result = await self.session.execute(
            select(Fixture).where(
                Fixture.date >= start,
                Fixture.date <= cutoff,
                or_(
                    Fixture.status.in_(["pending", "live"]),
                    Fixture.home_goals.is_(None),
                    Fixture.away_goals.is_(None),
                ),
            )
        )
        fixtures = list(result.scalars().all())
        if not fixtures:
            logger.info("capture_finished_results: nothing to update.")
            return 0

        by_day: dict[date, set[int]] = {}
        for fx in fixtures:
            by_day.setdefault(fx.date.date(), set()).add(fx.league_id)

        total = 0
        for day, league_ids in sorted(by_day.items()):
            try:
                total += await self.fetch_fixtures_for_date(
                    day,
                    force=True,
                    league_ids=sorted(league_ids),
                )
            except Exception as exc:
                logger.error(
                    "capture_finished_results failed for %s: %s",
                    day,
                    exc,
                    exc_info=True,
                )
        logger.info(
            "capture_finished_results updated %s date(s), fixtures_touched≈%s",
            len(by_day),
            total,
        )
        await self._label_match_features_for_finished()
        return total

    async def _label_match_features_for_finished(self) -> int:
        """Stamp outcome labels onto stored match_features after FT scores land."""
        assert self.session is not None
        from sqlalchemy import select

        from app.models.match_feature import MatchFeature
        from app.services.ml_predictor import outcome_label

        result = await self.session.execute(
            select(MatchFeature, Fixture)
            .join(Fixture, Fixture.id == MatchFeature.fixture_id)
            .where(
                Fixture.status == "finished",
                Fixture.home_goals.is_not(None),
                Fixture.away_goals.is_not(None),
                MatchFeature.label.is_(None),
            )
        )
        updated = 0
        for feat, fixture in result.all():
            label = outcome_label(fixture.home_goals, fixture.away_goals)
            if label:
                feat.label = label
                updated += 1
        if updated:
            await self.session.commit()
            logger.info("Labeled %s match_features rows with FT outcomes.", updated)
        return updated

    async def fetch_headtohead(
        self,
        home_team_id: int,
        away_team_id: int,
        last: int = 5,
    ) -> dict[str, Any]:
        cache_key = headtohead_cache_key(
            home_team_id,
            away_team_id,
            last,
            window=self.settings.history_source_tag,
        )
        return await self._get_or_fetch(
            cache_key,
            TTL_HEADTOHEAD,
            "fetch_headtohead",
            lambda client: self.provider.fetch_headtohead_payload(
                client, home_team_id, away_team_id, last
            ),
        )

    async def fetch_team_statistics(
        self,
        team_id: int,
        league_id: int,
        season: str,
    ) -> dict[str, Any]:
        cache_key = team_statistics_cache_key(team_id, league_id, season)
        return await self._get_or_fetch(
            cache_key,
            TTL_TEAM_STATISTICS,
            "fetch_team_statistics",
            lambda client: self.provider.fetch_team_statistics_payload(
                client, team_id, league_id, season
            ),
        )

    async def fetch_standings(self, league_id: int, season: str) -> dict[str, Any]:
        cache_key = standings_cache_key(league_id, season)
        return await self._get_or_fetch(
            cache_key,
            TTL_STANDINGS,
            "fetch_standings",
            lambda client: self.provider.fetch_standings_payload(
                client, league_id, season
            ),
        )

    async def fetch_team_form_payload(self, team_id: int, last: int = 5) -> dict[str, Any]:
        cache_key = team_form_cache_key(
            team_id, last, season=self.settings.history_source_tag
        )
        return await self._get_or_fetch(
            cache_key,
            TTL_TEAM_FORM,
            "fetch_team_form",
            lambda client: self.provider.fetch_team_form_payload(client, team_id, last),
        )

    async def fetch_odds(self, fixture_id: int, ttl: int | None = None) -> dict[str, Any]:
        cache_key = odds_cache_key(fixture_id)
        return await self._get_or_fetch(
            cache_key,
            ttl or TTL_HEADTOHEAD,
            "fetch_odds",
            lambda client: self.provider.fetch_odds_payload(client, fixture_id),
        )

    async def _upsert_odds_and_recompute(
        self,
        fixture_id: int,
        parsed: dict[str, Any],
        raw: dict[str, Any],
        *,
        set_opening: bool = False,
    ) -> None:
        """Write 即时盘; optionally freeze 初盘 once (midday scheduled sync)."""
        from sqlalchemy import select

        from app.models.fixture import Fixture
        from app.models.pre_match_data import PreMatchData
        from app.services.cache import analysis_cache_key
        from app.services.ml_predictor import persist_match_features, predict_probabilities
        from app.services.prediction import build_prediction_snapshot, implied_probs_from_odds
        from app.services.prematch_package import dumps_json, loads_json, rehydrate_odds_markets
        from app.services.ttl_policy import is_prediction_exam_locked

        assert self.session is not None
        captured_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        current_payload = {**parsed, "role": "current", "captured_at": captured_at}
        odds_text = dumps_json(current_payload)
        odds_pkg = rehydrate_odds_markets(parsed)

        async with self._db_lock:
            fixture = await self.session.get(Fixture, fixture_id)
            exam_locked = bool(
                fixture
                and is_prediction_exam_locked(fixture.date, fixture.status)
            )
            row = (
                await self.session.execute(
                    select(PreMatchData).where(PreMatchData.fixture_id == fixture_id)
                )
            ).scalar_one_or_none()

            opening_text: str | None = None
            if set_opening and parsed.get("available"):
                existing_open = (
                    loads_json(getattr(row, "odds_opening_json", None), {})
                    if row is not None
                    else {}
                )
                if not existing_open.get("available"):
                    opening_text = dumps_json(
                        {**parsed, "role": "opening", "captured_at": captured_at}
                    )

            # After kickoff: odds board may still update; prediction exam fields must not.
            if exam_locked:
                if row is None:
                    row = PreMatchData(
                        fixture_id=fixture_id,
                        odds_json=odds_text,
                        odds_opening_json=opening_text,
                    )
                    self.session.add(row)
                else:
                    row.odds_json = odds_text
                    if opening_text is not None:
                        row.odds_opening_json = opening_text
                row.updated_at = datetime.now(timezone.utc)
                await self.session.commit()
                await self.cache.delete(analysis_cache_key(fixture_id))
                await self.cache.set(odds_cache_key(fixture_id), raw, TTL_HEADTOHEAD)
                logger.info(
                    "Odds updated for fixture %s but prediction exam locked — snapshot unchanged",
                    fixture_id,
                )
                return

            package: dict[str, Any] = {
                "odds": odds_pkg,
                "home_form": loads_json(getattr(row, "home_form_json", None), {}) or {},
                "away_form": loads_json(getattr(row, "away_form_json", None), {}) or {},
                "head_to_head": loads_json(getattr(row, "h2h_json", None), {}) or {},
                "standings": loads_json(getattr(row, "standings_json", None), {}) or {},
                "injuries": loads_json(getattr(row, "injuries_json", None), {}) or {},
                "lineups": loads_json(getattr(row, "lineups_json", None), {}) or {},
            }
            pred = predict_probabilities(package)
            probs = pred.probs
            # Brand-new / never-analyzed rows: odds-implied is fine until form package exists.
            if pred.source == "form_fallback":
                implied = implied_probs_from_odds(parsed)
                if implied:
                    probs = implied

            snap = build_prediction_snapshot(probs, odds_pkg, features=pred.features)

            if row is None:
                row = PreMatchData(
                    fixture_id=fixture_id,
                    odds_json=odds_text,
                    odds_opening_json=opening_text,
                    home_win_prob=probs["home"],
                    draw_prob=probs["draw"],
                    away_win_prob=probs["away"],
                    recommendation=snap.get("recommendation"),
                    score_hint=snap.get("score_hint"),
                    goal_lean=snap.get("goal_lean"),
                    both_score_lean=snap.get("both_score_lean"),
                    handicap_lean=snap.get("handicap_lean"),
                )
                self.session.add(row)
            else:
                row.odds_json = odds_text
                if opening_text is not None:
                    row.odds_opening_json = opening_text
                row.home_win_prob = probs["home"]
                row.draw_prob = probs["draw"]
                row.away_win_prob = probs["away"]
                row.recommendation = snap.get("recommendation")
                row.score_hint = snap.get("score_hint")
                row.goal_lean = snap.get("goal_lean")
                row.both_score_lean = snap.get("both_score_lean")
                row.handicap_lean = snap.get("handicap_lean")

            await persist_match_features(
                self.session,
                fixture_id,
                pred.features,
                probs,
                source=pred.source,
            )
            # Ensure TTL freshness sees this write (SQLite onupdate can be flaky).
            row.updated_at = datetime.now(timezone.utc)
            await self.session.commit()

        await self.cache.delete(analysis_cache_key(fixture_id))
        await self.cache.set(odds_cache_key(fixture_id), raw, TTL_HEADTOHEAD)

    async def sync_odds_for_dates(
        self,
        days: list[date],
        *,
        refresh_existing: bool = False,
        budget: int = 40,
        league_ids: list[int] | None = None,
        set_opening: bool = False,
    ) -> int:
        """Sync pre-match odds for tracked pending fixtures in the date window.

        Free-plan constraints (API-Sports):
        - ``/odds?league=&season=`` blocked for current seasons (2025/2026).
        - ``/odds?date=`` only first 3 worldwide pages → misses our leagues.
        - ``/odds?fixture=`` works for open boards.

        Default (scheduler / background): **gap-fill** missing boards only.
        Force sync (``refresh_existing=True``): also re-pull boards that already
        exist so afternoon line moves update local 即时盘 **and** recompute 1X2.
        ``set_opening=True`` (midday job): freeze 初盘 on first available board.
        Missing fixtures are always prioritized within ``budget``.
        """
        from sqlalchemy import select

        from app.models.pre_match_data import PreMatchData
        from app.services.prematch_package import dumps_json, loads_json, parse_odds_payload

        assert self.session is not None
        allowed_filter: set[int] | None = None
        if league_ids is not None:
            allowed_filter = {int(x) for x in league_ids}
            if not allowed_filter:
                return 0
        if not days:
            return 0

        start = datetime.combine(min(days), datetime.min.time())
        end = datetime.combine(max(days), datetime.max.time())
        updated = 0

        filters = [
            Fixture.date >= start,
            Fixture.date <= end,
            Fixture.status == "pending",
        ]
        if allowed_filter is not None:
            filters.append(Fixture.league_id.in_(list(allowed_filter)))

        result = await self.session.execute(select(Fixture).where(*filters))
        fixtures = list(result.scalars().all())
        fixtures.sort(key=lambda fx: fx.date)
        odds_rows = (
            await self.session.execute(
                select(PreMatchData).where(
                    PreMatchData.fixture_id.in_([fx.id for fx in fixtures] or [0])
                )
            )
        ).scalars().all()
        odds_by_fid = {row.fixture_id: row for row in odds_rows}

        missing: list[int] = []
        refreshable: list[int] = []
        for fx in fixtures:
            stored = odds_by_fid.get(fx.id)
            odds = loads_json(getattr(stored, "odds_json", None), {}) or {}
            if not odds.get("available"):
                missing.append(fx.id)
            elif refresh_existing:
                refreshable.append(fx.id)

        queue = missing + (refreshable if refresh_existing else [])
        take = min(len(queue), max(1, budget))

        logger.info(
            "Odds sync: missing=%s refreshable=%s take=%s/%s pending "
            "(refresh_existing=%s set_opening=%s)",
            len(missing),
            len(refreshable),
            take,
            len(fixtures),
            refresh_existing,
            set_opening,
        )

        for index, fixture_id in enumerate(queue[:take]):
            try:
                # Bust Redis odds cache so force refresh never serves a stale board.
                await self.cache.delete(odds_cache_key(fixture_id))
                raw = await self._fetch_odds_with_rate_limit(fixture_id)
                parsed = parse_odds_payload(raw)
                if not parsed.get("available"):
                    logger.info("No official odds yet for fixture %s", fixture_id)
                    await asyncio.sleep(0.45)
                    continue
                await self._upsert_odds_and_recompute(
                    fixture_id, parsed, raw, set_opening=set_opening
                )
                updated += 1
            except Exception as exc:
                logger.warning("Fixture odds %s failed: %s", fixture_id, exc)
            if index + 1 < take:
                # Free-plan friendly pacing; 2s made force-sync feel like 1–2 min.
                await asyncio.sleep(0.55)

        # Midday: promote existing 即时盘 → 初盘 when opening was never frozen
        # (e.g. board first arrived via manual sync).
        if set_opening:
            promoted = 0
            fresh_rows = (
                await self.session.execute(
                    select(PreMatchData).where(
                        PreMatchData.fixture_id.in_([fx.id for fx in fixtures] or [0])
                    )
                )
            ).scalars().all()
            for stored in fresh_rows:
                current = loads_json(getattr(stored, "odds_json", None), {}) or {}
                opening = loads_json(getattr(stored, "odds_opening_json", None), {}) or {}
                if current.get("available") and not opening.get("available"):
                    captured_at = datetime.now(timezone.utc).isoformat().replace(
                        "+00:00", "Z"
                    )
                    stored.odds_opening_json = dumps_json(
                        {**current, "role": "opening", "captured_at": captured_at}
                    )
                    promoted += 1
            if promoted:
                await self.session.commit()
                logger.info("Odds sync: promoted %s current boards to opening", promoted)

        logger.info(
            "Odds sync done: upserted=%s missing=%s refreshed_candidates=%s (window %s..%s)",
            updated,
            len(missing),
            len(refreshable),
            min(days),
            max(days),
        )
        return updated

    async def _fetch_odds_with_rate_limit(self, fixture_id: int) -> dict[str, Any]:
        """Per-fixture odds with longer backoff on 429 (free-plan friendly)."""
        if self._client is None:
            raise RuntimeError("FootballFetcher must be used as an async context manager.")
        delays = (0.0, 8.0, 20.0)
        last_error: Exception | None = None
        for attempt, delay in enumerate(delays):
            if delay:
                await asyncio.sleep(delay)
            try:
                result = await self.provider.fetch_odds_payload(self._client, fixture_id)
                if self.provider.last_response is not None:
                    self.last_remaining_requests = parse_remaining_requests(
                        self.provider.last_response
                    )
                    self.cache.last_api_remaining = self.last_remaining_requests
                return result
            except Exception as exc:
                last_error = exc
                msg = str(exc)
                logger.warning(
                    "fetch_odds fixture=%s attempt %s failed: %s",
                    fixture_id,
                    attempt + 1,
                    exc,
                )
                if "429" not in msg:
                    break
        assert last_error is not None
        raise last_error

    async def fetch_lineups(self, fixture_id: int, ttl: int | None = None) -> dict[str, Any]:
        cache_key = lineups_cache_key(fixture_id)
        return await self._get_or_fetch(
            cache_key,
            ttl or TTL_TEAM_FORM,
            "fetch_lineups",
            lambda client: self.provider.fetch_lineups_payload(client, fixture_id),
        )

    async def fetch_injuries(self, fixture_id: int, ttl: int | None = None) -> dict[str, Any]:
        cache_key = injuries_cache_key(fixture_id)
        return await self._get_or_fetch(
            cache_key,
            ttl or TTL_TEAM_FORM,
            "fetch_injuries",
            lambda client: self.provider.fetch_injuries_payload(client, fixture_id),
        )

    async def fetch_predictions(self, fixture_id: int, ttl: int | None = None) -> dict[str, Any]:
        """Official /predictions (赛前简报); cached like lineups."""
        cache_key = predictions_cache_key(fixture_id)
        return await self._get_or_fetch(
            cache_key,
            ttl or TTL_TEAM_FORM,
            "fetch_predictions",
            lambda client: self.provider.fetch_predictions_payload(client, fixture_id),
        )

    async def fetch_fixture_details(self, fixture_id: int) -> dict[str, Any]:
        fixture_date: datetime | None = None
        status: str | None = None
        if self.session is not None:
            fixture = await self.session.get(Fixture, fixture_id)
            if fixture is not None:
                fixture_date = fixture.date
                status = fixture.status

        cache_key = fixture_cache_key(fixture_id)
        ttl = fixture_detail_ttl(fixture_date, status)
        return await self._get_or_fetch(
            cache_key,
            ttl,
            "fetch_fixture_details",
            lambda client: self.provider.fetch_fixture_detail_payload(client, fixture_id),
        )

    async def check_quota(self) -> int | None:
        await self._run_with_retry(
            "check_quota",
            lambda client: self.provider.fetch_quota_payload(client),
        )
        return self.last_remaining_requests

    async def test_connection(self) -> dict[str, Any]:
        payload = await self._run_with_retry(
            "test_connection",
            lambda client: self.provider.fetch_quota_payload(client),
        )
        return {
            "provider": self.provider.provider_name,
            "auth_mode": "api_sports" if self.settings.uses_api_sports_direct else "rapidapi",
            "host": self.settings.api_host,
            "remaining_requests": self.last_remaining_requests,
            "sample_keys": list(payload.keys()) if isinstance(payload, dict) else [],
            "cache_stats": self.cache.get_stats(),
        }
