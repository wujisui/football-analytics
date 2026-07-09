import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import AsyncSessionLocal
from app.models.fixture import Fixture
from app.models.league import League
from app.models.team import Team
from app.services.api_utils import parse_remaining_requests
from app.services.cache import (
    TTL_FIXTURES_TODAY,
    TTL_HEADTOHEAD,
    TTL_LEAGUES,
    TTL_TEAM_FORM,
    TTL_TEAM_STATISTICS,
    TTL_TEAMS,
    CacheService,
    fixture_cache_key,
    fixture_detail_ttl,
    fixtures_cache_key,
    get_cache_service,
    headtohead_cache_key,
    leagues_cache_key,
    team_form_cache_key,
    team_statistics_cache_key,
    teams_cache_key,
)
from app.services.providers import get_api_provider
from app.services.snapshot_store import SnapshotStore

logger = logging.getLogger(__name__)

RETRY_DELAYS = [1, 3, 5]


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

    async def __aenter__(self) -> "FootballFetcher":
        ensure_api_key_configured(self.settings)
        if self.session is None:
            self.session = AsyncSessionLocal()
        await self.cache.connect()
        self._client = httpx.AsyncClient(
            base_url=self.settings.api_base_url,
            headers=self.settings.football_api_headers(),
            timeout=30.0,
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
        """Local-first: Redis → SQLite snapshot → official API."""
        cached = await self.cache.get(cache_key)
        if cached is not None and "payload" in cached:
            self.cache.record_hit()
            logger.info("Cache hit for %s (cached at %s)", cache_key, cached.get("_cached_at"))
            return cached["payload"]

        if self.settings.LOCAL_FIRST and self.session is not None:
            store = SnapshotStore(self.session)
            db_payload = await store.get_valid(cache_key)
            if db_payload is not None:
                self.cache.record_hit()
                await self.cache.set(cache_key, db_payload, ttl)
                return db_payload

        self.cache.record_miss()
        logger.info("Cache/DB miss for %s — calling official API", cache_key)
        payload = await self._run_with_retry(operation, fetch_callback)
        await self.cache.set(cache_key, payload, ttl)

        if self.session is not None:
            store = SnapshotStore(self.session)
            await store.save(cache_key, payload, ttl)

        return payload

    async def _commit(self) -> None:
        if self.session is not None:
            await self.session.commit()

    async def _upsert_league(
        self,
        league_id: int,
        name: str,
        country: str,
        season: str,
    ) -> League:
        assert self.session is not None
        league = await self.session.get(League, league_id)
        if league is None:
            league = League(id=league_id, name=name, country=country, season=season)
            self.session.add(league)
        else:
            league.name = name
            league.country = country
            league.season = season
        return league

    async def _upsert_team(
        self,
        team_id: int,
        name: str,
        logo_url: str | None = None,
    ) -> Team:
        assert self.session is not None
        team = await self.session.get(Team, team_id)
        if team is None:
            team = Team(id=team_id, name=name, logo_url=logo_url)
            self.session.add(team)
        else:
            team.name = name
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
            )
            self.session.add(fixture)
        else:
            fixture.league_id = league_id
            fixture.home_team_id = home_team_id
            fixture.away_team_id = away_team_id
            fixture.date = fixture_date
            fixture.status = status

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

    async def _get_league_season(self, league_id: int) -> str:
        assert self.session is not None
        league = await self.session.get(League, league_id)
        if league is not None and league.season:
            return league.season
        return str(datetime.now().year)

    async def fetch_leagues(self, league_ids: list[int] | None = None) -> int:
        assert self.session is not None
        league_ids = league_ids or list(self.settings.LEAGUE_IDS.values())
        if not league_ids:
            logger.warning("No league IDs configured for fetch_leagues.")
            return 0

        cache_key = leagues_cache_key(league_ids)
        payload = await self._get_or_fetch(
            cache_key,
            TTL_LEAGUES,
            "fetch_leagues",
            lambda client: self.provider.fetch_leagues_payload(client, league_ids),
        )
        leagues = self.provider.parse_leagues(payload, league_ids)
        saved = 0

        for league in leagues:
            try:
                await self._upsert_league(
                    league["id"],
                    league["name"],
                    league["country"],
                    league["season"],
                )
                saved += 1
            except Exception as exc:
                logger.error("Failed to save league %s: %s", league, exc, exc_info=True)

        await self._commit()
        self.cache.last_data_update = datetime.now()
        logger.info("Saved %s leagues using provider %s.", saved, self.provider.provider_name)
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

    async def fetch_today_fixtures(self) -> int:
        assert self.session is not None
        today = datetime.now().strftime("%Y-%m-%d")
        cache_key = fixtures_cache_key(today)
        payload = await self._get_or_fetch(
            cache_key,
            TTL_FIXTURES_TODAY,
            "fetch_today_fixtures",
            lambda client: self.provider.fetch_fixtures_payload(client, today),
        )
        fixtures = self.provider.parse_fixtures(payload)
        league_ids: set[int] = set()
        saved = 0

        for fixture in fixtures:
            try:
                await self._upsert_league(
                    fixture["league_id"],
                    fixture["league_name"],
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
                    fixture["league_id"],
                    fixture["home_team_id"],
                    fixture["away_team_id"],
                    fixture["date"],
                    fixture["status"],
                )
                league_ids.add(fixture["league_id"])
                saved += 1
            except Exception as exc:
                logger.error("Failed to save fixture %s: %s", fixture, exc, exc_info=True)

        await self._commit()

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

        logger.info("Saved %s fixtures for %s.", saved, today)
        self.cache.last_data_update = datetime.now()
        return saved

    async def fetch_headtohead(
        self,
        home_team_id: int,
        away_team_id: int,
        last: int = 5,
    ) -> dict[str, Any]:
        cache_key = headtohead_cache_key(home_team_id, away_team_id, last)
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

    async def fetch_team_form_payload(self, team_id: int, last: int = 5) -> dict[str, Any]:
        cache_key = team_form_cache_key(team_id, last)
        return await self._get_or_fetch(
            cache_key,
            TTL_TEAM_FORM,
            "fetch_team_form",
            lambda client: self.provider.fetch_team_form_payload(client, team_id, last),
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
