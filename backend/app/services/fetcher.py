import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import AsyncSessionLocal
from app.models.fixture import Fixture
from app.models.league import League
from app.models.team import Team
from app.services.api_quota import (
    api_errors_account_blocked,
    api_errors_quota_exhausted,
    clip_fixture_dates_for_plan,
)
from app.services.api_utils import parse_remaining_requests
from app.services.league_catalog import (
    allowed_league_ids as catalog_allowed_league_ids,
    catalog_leagues,
)
from app.services.league_names import league_name_zh
from app.services.match_day import (
    current_prematch_match_day,
    fixture_match_day,
    fixture_match_day_expr,
    infer_team_timezone,
    resolve_match_day,
)
from app.services.results_capture import (
    is_stale_live_row,
    results_capture_cutoff,
    select_stale_pending_fixtures,
    settled_by_full_time,
)
from app.services.team_names import backfill_team_names, team_name_zh
from app.services.cache import (
    TTL_FIXTURE_LIVE_SCORE,
    TTL_FIXTURES_TODAY,
    TTL_HEADTOHEAD,
    TTL_LEAGUES,
    TTL_STANDINGS,
    TTL_TEAM_FORM,
    TTL_TEAM_STATISTICS,
    TTL_TEAMS,
    CacheService,
    fixture_score_cache_key,
    fixtures_cache_key,
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


class ApiAccountBlockedError(RuntimeError):
    """Raised when the official account is suspended / disabled.

    Fail the batch loudly instead of saving nothing: every data endpoint answers
    ``200`` with ``errors.access``, so callers would otherwise report success.
    """


def ensure_api_key_configured(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    from app.services.api_key_pool import official_keys

    keys = official_keys(settings)
    key = keys[0] if keys else ""
    placeholders = {
        "",
        "your_api_key_here",
        "your-api-key-here",
        "your_api_sports_key_here",
    }

    if key in placeholders:
        raise ApiKeyNotConfiguredError(
            "Football API key is not configured. "
            "Set keys in「我的 → 管理员设置 → API-Sports 官方 Key」, "
            "or run `python manage.py set-api-sports-key key1,key2`."
        )
    return key


def _round_robin_fixture_ids(
    fixture_ids: list[int],
    fixtures_by_id: dict[int, Fixture],
    take: int,
) -> list[int]:
    """Fair-share missing odds across leagues so one league isn't starved."""
    from collections import defaultdict, deque

    if take <= 0 or not fixture_ids:
        return []
    buckets: dict[int, deque[int]] = defaultdict(deque)
    for fid in fixture_ids:
        fx = fixtures_by_id.get(fid)
        lid = int(fx.league_id) if fx is not None else 0
        buckets[lid].append(fid)

    out: list[int] = []
    while len(out) < take and buckets:
        empty: list[int] = []
        for lid, queue in list(buckets.items()):
            if not queue:
                empty.append(lid)
                continue
            out.append(queue.popleft())
            if len(out) >= take:
                break
        for lid in empty:
            del buckets[lid]
    return out


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
        # Once the free-tier daily limit is hit, skip further official calls
        # in this fetcher session so the rest of the batch does not burn empty.
        # May clear after a successful API-Sports key failover.
        self.quota_exhausted: bool = False
        # AsyncSession is not safe for concurrent awaitables; package gather must serialize DB I/O.
        self._db_lock = asyncio.Lock()

    def _apply_client_headers(self) -> None:
        if self._client is None:
            return
        for key, value in self.settings.football_api_headers().items():
            self._client.headers[key] = value

    async def _failover_official_key(self, *, reason: str) -> bool:
        """Mark current official key exhausted and switch headers to the next."""
        from app.services.api_key_pool import mark_active_exhausted_and_rotate

        next_key = await mark_active_exhausted_and_rotate(
            self.session,
            self.settings,
            reason=reason,
        )
        if not next_key:
            return False
        self._apply_client_headers()
        self.quota_exhausted = False
        return True

    def _note_upstream_payload(self, payload: dict[str, Any] | None) -> None:
        errors = _api_payload_errors(payload)
        if errors is None:
            return
        if api_errors_account_blocked(errors):
            raise ApiAccountBlockedError(
                f"官方账号被停用，所有数据接口均返回拒绝：{errors}"
            )
        if self.quota_exhausted:
            return
        if api_errors_quota_exhausted(errors):
            self.quota_exhausted = True
            logger.error(
                "Official API daily quota exhausted on active key; "
                "will try failover before further calls: %s",
                errors,
            )

    async def __aenter__(self) -> "FootballFetcher":
        from app.services.api_key_pool import hydrate_key_pool
        from app.services.runtime_settings import hydrate_api_sports_keys

        await hydrate_api_sports_keys(self.session)
        ensure_api_key_configured(self.settings)
        if self.session is None:
            self.session = AsyncSessionLocal()
        await hydrate_key_pool(self.session, self.settings)
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
                    self.cache.note_api_response(self.last_remaining_requests)
                    if (
                        self.last_remaining_requests is not None
                        and self.last_remaining_requests <= 0
                        and self.settings.uses_api_sports_direct
                    ):
                        switched = await self._failover_official_key(
                            reason="remaining=0"
                        )
                        if not switched:
                            self.quota_exhausted = True
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
        *,
        force: bool = False,
    ) -> dict[str, Any]:
        """Local-first: Redis → SQLite snapshot → official API.

        ``force=True`` skips Redis/SQLite and always hits the official API
        (used by result capture / sync so finished scores are not stuck on an
        earlier NS snapshot).

        Never cache / re-serve payloads that only contain upstream ``errors``
        (free-plan season blocks, rate limits, etc.) — those must not poison
        later syncs.
        """
        if self.quota_exhausted:
            if await self._failover_official_key(reason="quota_error"):
                logger.info("Retrying official call after API-Sports key failover")
            else:
                return {
                    "get": operation,
                    "errors": {
                        "requests": (
                            "Official API daily quota already exhausted in this "
                            "sync session; call skipped."
                        )
                    },
                    "results": 0,
                    "response": [],
                }

        if not force:
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
        else:
            await self.cache.delete(cache_key)
            if self.session is not None:
                async with self._db_lock:
                    store = SnapshotStore(self.session)
                    await store.invalidate(cache_key)

        self.cache.record_miss()
        logger.info(
            "%s for %s — calling official API",
            "Forced refresh" if force else "Cache/DB miss",
            cache_key,
        )
        payload = await self._run_with_retry(operation, fetch_callback)
        if _api_payload_unusable(payload):
            self._note_upstream_payload(payload)
            if self.quota_exhausted and await self._failover_official_key(
                reason="quota_error"
            ):
                logger.info(
                    "Re-fetching %s after API-Sports key failover",
                    cache_key,
                )
                payload = await self._run_with_retry(operation, fetch_callback)
            if _api_payload_unusable(payload):
                self._note_upstream_payload(payload)
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
            if not league.is_catalog:
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
        country: str | None = None,
        venue_city: str | None = None,
    ) -> Team:
        assert self.session is not None
        display_name = team_name_zh(name, team_id) or name
        team = await self.session.get(Team, team_id)
        team_timezone, _source = infer_team_timezone(
            venue_city=venue_city,
            country=country,
        )
        if team is None:
            team = Team(
                id=team_id,
                name=display_name,
                logo_url=logo_url,
                country=country or None,
                venue_city=venue_city or None,
                timezone=team_timezone,
            )
            self.session.add(team)
        else:
            team.name = display_name
            if logo_url is not None:
                team.logo_url = logo_url
            if country:
                team.country = country
            if venue_city:
                team.venue_city = venue_city
            if team_timezone:
                team.timezone = team_timezone
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
        venue_city: str | None = None,
        league_country: str | None = None,
    ) -> Fixture:
        assert self.session is not None
        fixture = await self.session.get(Fixture, fixture_id)
        previous_status = fixture.status if fixture is not None else None
        status = settled_by_full_time(
            status=status,
            status_short=status_short,
            fixture_date=fixture_date,
            has_full_time_score=home_goals is not None and away_goals is not None,
        )
        # Detail refresh / day feeds sometimes keep a live long-form status while
        # short is already FT and fulltime goals are present — force finished so
        # list settlement and UI stay aligned.
        if (
            home_goals is not None
            and away_goals is not None
            and (status_short or "").upper() in {"FT", "AET", "PEN"}
        ):
            status = "finished"
        if fixture is not None and is_stale_live_row(previous_status, status):
            # Keep the recorded result; a later good row will update it.
            logger.debug(
                "Ignored stale live row for finished fixture %s (%s)",
                fixture_id,
                status_short,
            )
            return fixture

        home_team = await self.session.get(Team, home_team_id)
        day = resolve_match_day(
            fixture_date,
            venue_city=venue_city,
            league_country=league_country,
            home_team_timezone=home_team.timezone if home_team else None,
        )

        if fixture is None:
            fixture = Fixture(
                id=fixture_id,
                league_id=league_id,
                home_team_id=home_team_id,
                away_team_id=away_team_id,
                date=fixture_date,
                venue_city=venue_city or None,
                match_timezone=day.timezone,
                match_day=day.match_day,
                match_day_source=day.source,
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
            if venue_city:
                fixture.venue_city = venue_city
            fixture.match_timezone = day.timezone
            fixture.match_day = day.match_day
            fixture.match_day_source = day.source
            fixture.status = status
            if status_short is not None:
                fixture.status_short = status_short
            # Score boards: always refresh when parser provided regulation goals.
            if home_goals is not None:
                fixture.home_goals = home_goals
            if away_goals is not None:
                fixture.away_goals = away_goals
            # ET / PEN boards: the parser already nulls them unless settled.
            fixture.et_home_goals = et_home_goals
            fixture.et_away_goals = et_away_goals
            fixture.pen_home = pen_home
            fixture.pen_away = pen_away

        if previous_status is not None and previous_status != status:
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
        catalog = await catalog_leagues(self.session)
        configured = {int(row.id): row for row in catalog}
        requested_ids = league_ids or list(configured)
        league_ids = [int(value) for value in requested_ids if int(value) in configured]
        if not league_ids:
            logger.warning("No league IDs configured for fetch_leagues.")
            return 0

        # Always keep DB catalog rows usable even if the official API is rate-limited.
        id_to_name = {league_id: row.name for league_id, row in configured.items()}
        countries = {league_id: row.country for league_id, row in configured.items()}
        season_default = str(datetime.now().year)
        saved = 0
        for league_id in league_ids:
            try:
                configured_row = configured.get(league_id)
                season = configured_row.season if configured_row else season_default
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

    async def lookup_official_league(self, league_id: int) -> dict[str, Any]:
        """Resolve one official league by id for admin add-confirmation.

        Cache/snapshot first (``TTL_LEAGUES``); a miss spends one
        ``GET /leagues?id=`` request. Does not write the catalog.
        """
        from app.services.api_utils import extract_items, first_value

        target = int(league_id)
        if target < 1:
            raise ValueError("官方联赛 ID 必须为正整数")
        assert self.session is not None
        started = int(self.cache.api_request_count or 0)
        payload = await self._get_or_fetch(
            leagues_cache_key([target]),
            TTL_LEAGUES,
            "lookup_official_league",
            lambda client: self.provider.fetch_leagues_payload(client, [target]),
        )
        if _api_payload_unusable(payload):
            raise RuntimeError("官方联赛查询失败或当日配额已用尽")
        parsed = self.provider.parse_leagues(payload, [target])
        if not parsed:
            raise LookupError("官方没有这个联赛 ID")
        official = parsed[0]
        league_type = ""
        for item in extract_items(payload):
            item_id = first_value(item, [["league", "id"], ["id"], ["league_id"]])
            if item_id is not None and int(item_id) == target:
                league_type = str(
                    first_value(item, [["league", "type"], ["type"]], "") or ""
                )
                break
        suggested = league_name_zh(
            str(official.get("name") or ""),
            league_id=target,
            country=str(official.get("country") or "") or None,
        )
        existing = await self.session.get(League, target)
        return {
            "league_id": target,
            "official_name": str(official.get("name") or ""),
            "country": str(official.get("country") or ""),
            "season": str(official.get("season") or ""),
            "league_type": league_type,
            "suggested_name": suggested,
            "in_catalog": bool(existing is not None and existing.is_catalog),
            "from_cache": int(self.cache.api_request_count or 0) == started,
        }

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
                await self._upsert_team(
                    team["id"],
                    team["name"],
                    team.get("logo_url"),
                    team.get("country"),
                    team.get("venue_city"),
                )
                saved += 1
            except Exception as exc:
                logger.error(
                    "Failed to save team for league %s: %s",
                    league_id,
                    exc,
                    exc_info=True,
                )

        await self._refresh_fixture_match_days(league_id=league_id)
        await self._commit()
        logger.info("Saved %s teams for league %s (season %s).", saved, league_id, season)
        return saved

    async def _refresh_fixture_match_days(self, *, league_id: int) -> int:
        """Re-resolve a league after its team catalog enriched home locations."""

        from sqlalchemy import select

        assert self.session is not None
        league = await self.session.get(League, league_id)
        fixtures = (
            await self.session.execute(
                select(Fixture).where(Fixture.league_id == league_id)
            )
        ).scalars()
        updated = 0
        for fixture in fixtures:
            home = await self.session.get(Team, fixture.home_team_id)
            day = resolve_match_day(
                fixture.date,
                venue_city=fixture.venue_city,
                league_country=league.country if league else None,
                home_team_timezone=home.timezone if home else None,
            )
            if (
                fixture.match_day != day.match_day
                or fixture.match_timezone != day.timezone
                or fixture.match_day_source != day.source
            ):
                fixture.match_day = day.match_day
                fixture.match_timezone = day.timezone
                fixture.match_day_source = day.source
                updated += 1
        return updated

    async def _persist_fixtures(
        self,
        fixtures: list[dict[str, Any]],
        *,
        allowed_league_ids: set[int] | None = None,
        fetch_teams: bool = True,
    ) -> int:
        """Upsert only fixtures admitted by the competition whitelist.

        ``allowed_league_ids`` may further narrow the whitelist for a targeted
        call, but can never expand it.
        """
        assert self.session is not None
        competition_ids = await catalog_allowed_league_ids(self.session)
        effective_ids = (
            competition_ids
            if allowed_league_ids is None
            else competition_ids & {int(value) for value in allowed_league_ids}
        )
        league_ids: set[int] = set()
        saved = 0

        for fixture in fixtures:
            league_id = int(fixture["league_id"])
            if league_id not in effective_ids:
                continue
            try:
                raw_league_name = str(fixture.get("league_name") or f"League {league_id}")
                display_name = league_name_zh(
                    raw_league_name,
                    league_id=league_id,
                    country=fixture.get("country"),
                    settings=self.settings,
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
                    venue_city=fixture.get("venue_city"),
                    league_country=fixture.get("country"),
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
        """Prefer the DB catalog season, then the calendar year."""
        season = await self._get_league_season(league_id)
        if season:
            return season
        return str((hint_date or date.today()).year)

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
        try:
            payload = await self._get_or_fetch(
                cache_key,
                TTL_FIXTURES_TODAY,
                "fetch_fixtures_worldwide_day",
                lambda client, d=date_str: self.provider.fetch_fixtures_payload(client, d),
                force=force,
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
                "all" if allowed is None else sorted(allowed),
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
        Full-day ingest skips per-league team catalog pulls (fixture payload already
        carries names/logos) to avoid burning quota across dozens of leagues.
        """
        assert self.session is not None
        if end < start:
            start, end = end, start
        if not self.settings.uses_full_history:
            clipped = clip_fixture_dates_for_plan(
                [
                    start + timedelta(days=offset)
                    for offset in range((end - start).days + 1)
                ],
                date.today(),
            )
            if not clipped:
                logger.warning(
                    "Free-plan fixtures window %s..%s is outside the allowed "
                    "date range; skipping official fetch",
                    start.isoformat(),
                    end.isoformat(),
                )
                return 0
            if clipped[0] != start or clipped[-1] != end:
                logger.info(
                    "Free-plan fixtures window clipped %s..%s → %s..%s",
                    start.isoformat(),
                    end.isoformat(),
                    clipped[0].isoformat(),
                    clipped[-1].isoformat(),
                )
            start, end = clipped[0], clipped[-1]

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
            if self.quota_exhausted:
                logger.warning(
                    "Stopping fixtures window fetch at %s (quota exhausted)",
                    cursor.isoformat(),
                )
                break
            total += await self._fetch_day_worldwide_filtered(
                cursor,
                allowed,
                force=force,
                # Only pull team catalogs when syncing a curated league subset.
                fetch_teams=first and allowed is not None,
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

    async def capture_finished_results(
        self,
        lookback_days: int = 3,
        *,
        on_days: list[date] | None = None,
        today: date | None = None,
    ) -> int:
        """
        One-shot result backfill for recently kicked-off fixtures still missing FT scores.

        When ``on_days`` is set (scheduled / admin sync), each calendar day is
        force-refreshed via worldwide ``date=`` so yesterday's FT scores land even
        if local rows were never marked stale. Otherwise falls back to scanning
        stale local rows over ``lookback_days``.
        """
        assert self.session is not None
        base_today = today or date.today()

        if on_days:
            day_list = sorted(set(on_days))
            if not self.settings.uses_full_history:
                clipped = clip_fixture_dates_for_plan(day_list, base_today)
                dropped = set(day_list) - set(clipped)
                if dropped:
                    logger.info(
                        "capture_finished_results free-plan skipped dates outside "
                        "window: %s",
                        ",".join(sorted(d.isoformat() for d in dropped)),
                    )
                day_list = clipped
            if not day_list:
                logger.info("capture_finished_results: no result days after clip.")
                return 0

            total = 0
            for day in day_list:
                if self.quota_exhausted:
                    logger.warning(
                        "Stopping result capture at %s (quota exhausted)",
                        day.isoformat(),
                    )
                    break
                try:
                    # Worldwide day fetch (all leagues) — one call settles FT scores.
                    total += await self.fetch_fixtures_for_date(day, force=True)
                except Exception as exc:
                    logger.error(
                        "capture_finished_results failed for %s: %s",
                        day,
                        exc,
                        exc_info=True,
                    )
            logger.info(
                "capture_finished_results refreshed %s date(s), fixtures_touched≈%s",
                len(day_list),
                total,
            )
            await self._label_match_features_for_finished()
            await self._label_ah_for_finished()
            return total

        cutoff = results_capture_cutoff()
        start = (datetime.utcnow() - timedelta(days=max(1, lookback_days))).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        result = await self.session.execute(
            select_stale_pending_fixtures(start=start, cutoff=cutoff)
        )
        fixtures = list(result.scalars().all())
        # Free plan cannot request fixtures outside its date window — drop those
        # days before burning quota on guaranteed plan errors.
        if not self.settings.uses_full_history:
            allowed_days = set(
                clip_fixture_dates_for_plan(
                    sorted({fx.date.date() for fx in fixtures}),
                    base_today,
                )
            )
            dropped = {fx.date.date() for fx in fixtures} - allowed_days
            if dropped:
                logger.info(
                    "capture_finished_results free-plan skipped dates outside "
                    "window: %s",
                    ",".join(sorted(d.isoformat() for d in dropped)),
                )
            fixtures = [fx for fx in fixtures if fx.date.date() in allowed_days]
        if not fixtures:
            logger.info("capture_finished_results: nothing to update.")
            return 0

        by_day: dict[date, set[int]] = {}
        for fx in fixtures:
            by_day.setdefault(fx.date.date(), set()).add(fx.league_id)

        total = 0
        for day, league_ids in sorted(by_day.items()):
            if self.quota_exhausted:
                logger.warning(
                    "Stopping result capture at %s (quota exhausted)",
                    day.isoformat(),
                )
                break
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
        await self._label_ah_for_finished()
        return total

    async def _label_ah_for_finished(self) -> int:
        """Stamp AH cover labels onto match_features after FT scores land."""
        assert self.session is not None
        from app.services.ah_predictor import label_finished_ah

        updated = await label_finished_ah(self.session)
        if updated:
            logger.info("Labeled %s match_features rows with AH outcomes.", updated)
        return updated

    async def _label_match_features_for_finished(self) -> int:
        """Stamp 1X2 and goal labels onto frozen pre-match features."""
        assert self.session is not None
        from sqlalchemy import or_, select

        from app.models.match_feature import MatchFeature
        from app.services.ml_predictor import outcome_label

        result = await self.session.execute(
            select(MatchFeature, Fixture)
            .join(Fixture, Fixture.id == MatchFeature.fixture_id)
            .where(
                Fixture.status == "finished",
                Fixture.home_goals.is_not(None),
                Fixture.away_goals.is_not(None),
                or_(
                    MatchFeature.label.is_(None),
                    MatchFeature.home_goals_label.is_(None),
                    MatchFeature.away_goals_label.is_(None),
                ),
            )
        )
        updated = 0
        for feat, fixture in result.all():
            label = outcome_label(fixture.home_goals, fixture.away_goals)
            if label:
                feat.label = label
                feat.home_goals_label = int(fixture.home_goals)
                feat.away_goals_label = int(fixture.away_goals)
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

    async def refresh_odds_for_fixture(
        self,
        fixture_id: int,
        *,
        restrict_to_current_match_day: bool = True,
    ) -> bool:
        """Pull odds only while the fixture is still a verified prematch."""
        from app.services.league_catalog import allowed_league_ids
        from app.services.prematch_package import parse_odds_payload
        from app.services.odds_snapshot import is_fixture_prematch

        assert self.session is not None
        fixture = await self.session.get(Fixture, fixture_id)
        league = (
            await self.session.get(League, fixture.league_id)
            if fixture is not None
            else None
        )
        if (
            fixture is None
            or league is None
            or not league.is_catalog
            or not is_fixture_prematch(match_start_time=fixture.date)
        ):
            logger.warning(
                "Skip official odds pull outside catalog prematch scope "
                "fixture=%s catalog=%s kickoff=%s",
                fixture_id,
                getattr(league, "is_catalog", None),
                getattr(fixture, "date", None),
            )
            return False
        if restrict_to_current_match_day:
            today = await current_prematch_match_day(
                self.session,
                league_ids=await allowed_league_ids(self.session),
            )
            if not today or fixture_match_day(fixture) != today:
                logger.warning(
                    "Skip official odds pull outside current match day "
                    "fixture=%s match_day=%s current=%s",
                    fixture_id,
                    fixture_match_day(fixture),
                    today,
                )
                return False
        await self.cache.delete(odds_cache_key(fixture_id))
        raw = await self._fetch_odds_with_rate_limit(fixture_id)
        parsed = parse_odds_payload(raw)
        if not parsed.get("available"):
            logger.info("No official odds yet for fixture %s", fixture_id)
            return False
        return await self._upsert_odds_and_recompute(
            fixture_id,
            parsed,
            raw,
        )

    async def _upsert_odds_and_recompute(
        self,
        fixture_id: int,
        parsed: dict[str, Any],
        raw: dict[str, Any],
    ) -> bool:
        """Write 即时盘 and freeze the first available pre-kickoff board as 初盘."""
        from sqlalchemy import select

        from app.models.fixture import Fixture
        from app.models.pre_match_data import PreMatchData
        from app.services.cache import analysis_cache_key
        from app.services.ml_predictor import persist_match_features, predict_probabilities
        from app.services.odds_snapshot import (
            annotate_odds_snapshot,
            is_fixture_prematch,
            normalize_odds_snapshot,
        )
        from app.services.prediction import build_prediction_snapshot, implied_probs_from_odds
        from app.services.prematch_package import (
            SNAPSHOT_LATE,
            SNAPSHOT_MID,
            dumps_json,
            loads_json,
            rehydrate_odds_markets,
            should_write_opening,
            timed_snapshot_json,
        )
        assert self.session is not None
        captured_at = datetime.now(timezone.utc)

        async with self._db_lock:
            fixture = await self.session.get(Fixture, fixture_id)
            if fixture is None or not is_fixture_prematch(
                match_start_time=fixture.date,
                now=captured_at,
            ):
                logger.warning(
                    "Discard odds fetched after prematch boundary fixture=%s "
                    "status=%s scraped_at=%s kickoff=%s",
                    fixture_id,
                    getattr(fixture, "status", None),
                    captured_at,
                    getattr(fixture, "date", None),
                )
                return False
            current_payload = annotate_odds_snapshot(
                parsed,
                scraped_at=captured_at,
                match_start_time=fixture.date,
                role="current",
            )
            captured_at_iso = current_payload["scraped_at"]
            odds_text = dumps_json(current_payload)
            odds_pkg = rehydrate_odds_markets(current_payload)
            row = (
                await self.session.execute(
                    select(PreMatchData).where(PreMatchData.fixture_id == fixture_id)
                )
            ).scalar_one_or_none()

            existing_open = (
                normalize_odds_snapshot(
                    loads_json(getattr(row, "odds_opening_json", None), {}),
                    match_start_time=fixture.date,
                    fixture_id=fixture_id,
                    stage="opening",
                )
                if row is not None
                else {}
            )
            existing_current = (
                normalize_odds_snapshot(
                    loads_json(getattr(row, "odds_json", None), {}),
                    match_start_time=fixture.date,
                    fixture_id=fixture_id,
                    stage="current",
                )
                if row is not None
                else {}
            )
            # Repair a legacy row before replacing its current board: its stored
            # board predates this pull and is therefore the earliest recoverable
            # opening. New rows use this pull directly.
            opening_candidate = parsed
            if (
                not existing_open.get("available")
                and existing_current.get("available")
                and not should_write_opening(
                    existing_current,
                    parsed,
                    locked=False,
                )
            ):
                opening_candidate = existing_current
            opening_text: str | None = None
            if should_write_opening(
                existing_open,
                opening_candidate,
                locked=False,
            ):
                opening_captured_at = (
                    opening_candidate.get("scraped_at")
                    or opening_candidate.get("captured_at")
                    or captured_at_iso
                )
                opening_text = dumps_json(
                    annotate_odds_snapshot(
                        opening_candidate,
                        scraped_at=opening_captured_at,
                        match_start_time=fixture.date,
                        role="opening",
                    )
                )

            kickoff = fixture.date if fixture is not None else None
            existing_mid = (
                normalize_odds_snapshot(
                    loads_json(getattr(row, "odds_mid_json", None), {}),
                    match_start_time=fixture.date,
                    fixture_id=fixture_id,
                    stage="mid",
                )
                if row is not None
                else {}
            )
            existing_late = (
                normalize_odds_snapshot(
                    loads_json(getattr(row, "odds_late_json", None), {}),
                    match_start_time=fixture.date,
                    fixture_id=fixture_id,
                    stage="late",
                )
                if row is not None
                else {}
            )
            mid_text = timed_snapshot_json(
                existing_mid,
                parsed,
                kickoff=kickoff,
                captured_at=captured_at_iso,
                stage=SNAPSHOT_MID["stage"],
                target_hours=SNAPSHOT_MID["target_hours"],
                min_hours=SNAPSHOT_MID["min_hours"],
                max_hours=SNAPSHOT_MID["max_hours"],
                locked=False,
                policy=SNAPSHOT_MID["policy"],
            )
            late_text = timed_snapshot_json(
                existing_late,
                parsed,
                kickoff=kickoff,
                captured_at=captured_at_iso,
                stage=SNAPSHOT_LATE["stage"],
                target_hours=SNAPSHOT_LATE["target_hours"],
                min_hours=SNAPSHOT_LATE["min_hours"],
                max_hours=SNAPSHOT_LATE["max_hours"],
                locked=False,
                policy=SNAPSHOT_LATE["policy"],
            )

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

            snap = build_prediction_snapshot(
                probs,
                odds_pkg,
                features=pred.features,
                league_id=fixture.league_id if fixture else None,
            )

            if row is None:
                row = PreMatchData(
                    fixture_id=fixture_id,
                    odds_json=odds_text,
                    odds_opening_json=opening_text,
                    odds_mid_json=mid_text,
                    odds_late_json=late_text,
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
                if mid_text is not None:
                    row.odds_mid_json = mid_text
                if late_text is not None:
                    row.odds_late_json = late_text
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
            from app.services.ah_predictor import persist_ah_fields
            from app.services.goal_predictor import persist_goal_features

            await persist_goal_features(
                self.session,
                fixture_id,
                pred.features,
                odds_pkg,
            )
            def _stage_pkg(text: str | None, attr: str) -> dict[str, Any]:
                data = loads_json(
                    text if text is not None else getattr(row, attr, None),
                    {"available": False},
                )
                if isinstance(data, dict) and data.get("available"):
                    return rehydrate_odds_markets(data)
                return {"available": False}

            await persist_ah_fields(
                self.session,
                fixture_id,
                {
                    **package,
                    "odds_opening": _stage_pkg(opening_text, "odds_opening_json"),
                    "odds_mid": _stage_pkg(mid_text, "odds_mid_json"),
                    "odds_late": _stage_pkg(late_text, "odds_late_json"),
                },
                league_id=fixture.league_id if fixture else None,
            )
            # Ensure TTL freshness sees this write (SQLite onupdate can be flaky).
            row.updated_at = datetime.now(timezone.utc)
            await self.session.commit()

        await self.cache.delete(analysis_cache_key(fixture_id))
        await self.cache.set(odds_cache_key(fixture_id), raw, TTL_HEADTOHEAD)
        return True

    async def sync_odds_for_dates(
        self,
        days: list[date],
        *,
        refresh_existing: bool = False,
        budget: int = 40,
        league_ids: list[int] | None = None,
    ) -> int:
        """Sync catalog fixtures that are still in 【比赛】 on each local match day.

        Free-plan constraints (API-Sports):
        - ``/odds?league=&season=`` blocked for current seasons (2025/2026).
        - ``/odds?date=`` only first 3 worldwide pages → misses our leagues.
        - ``/odds?fixture=`` works for open boards.

        Default (scheduler / multi-day): gap-fill missing boards within ``budget``.
        Focused sync (single day or explicit ``league_ids``): fill **all** missing
        boards for the selected leagues (round-robin so evening leagues are not
        starved), then optionally refresh existing boards up to ``budget``.
        Every successful first pull freezes 初盘. Existing frozen rows are never
        repaired or rewritten outside a real pre-match refresh.
        """
        from sqlalchemy import select

        from app.models.pre_match_data import PreMatchData
        from app.services.prematch_package import loads_json

        assert self.session is not None
        allowed_filter: set[int] | None = None
        if league_ids is not None:
            allowed_filter = {int(x) for x in league_ids}
            if not allowed_filter:
                return 0
        if not days:
            return 0

        updated = 0

        filters = [
            fixture_match_day_expr().in_([day.isoformat() for day in days]),
            League.is_catalog.is_(True),
            Fixture.date > datetime.now(timezone.utc).replace(tzinfo=None),
        ]
        if allowed_filter is not None:
            filters.append(Fixture.league_id.in_(list(allowed_filter)))

        result = await self.session.execute(
            select(Fixture)
            .join(League, League.id == Fixture.league_id)
            .where(*filters)
        )
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
        fixtures_by_id = {fx.id: fx for fx in fixtures}
        for fx in fixtures:
            stored = odds_by_fid.get(fx.id)
            odds = loads_json(getattr(stored, "odds_json", None), {}) or {}
            if not odds.get("available"):
                missing.append(fx.id)
            elif refresh_existing:
                refreshable.append(fx.id)

        # Free plan blocks /odds?league=&season= for current seasons, so we still
        # pull per fixture. Manual/single-day or league-filtered sync must fill
        # every missing board for the selected leagues — not stop at ``budget``
        # after only the earliest kickoffs (which starved evening leagues like CSL).
        focused = len(days) <= 1 or allowed_filter is not None
        missing_hard_cap = 250
        if focused:
            missing_take = min(len(missing), missing_hard_cap)
        else:
            missing_take = min(len(missing), max(1, budget))
        refresh_take = (
            min(len(refreshable), max(0, budget)) if refresh_existing else 0
        )

        missing_queue = _round_robin_fixture_ids(
            missing, fixtures_by_id, missing_take
        )
        refresh_queue = refreshable[:refresh_take]
        queue = missing_queue + refresh_queue
        take = len(queue)

        logger.info(
            "Odds sync: missing=%s refreshable=%s take_missing=%s "
            "take_refresh=%s/%s pending focused=%s "
            "(refresh_existing=%s)",
            len(missing),
            len(refreshable),
            len(missing_queue),
            len(refresh_queue),
            len(fixtures),
            focused,
            refresh_existing,
        )

        for index, fixture_id in enumerate(queue):
            if self.quota_exhausted:
                logger.warning(
                    "Stopping odds sync after %s/%s (quota exhausted)",
                    index,
                    take,
                )
                break
            try:
                if await self.refresh_odds_for_fixture(
                    fixture_id,
                    restrict_to_current_match_day=False,
                ):
                    updated += 1
            except Exception as exc:
                logger.warning("Fixture odds %s failed: %s", fixture_id, exc)
            if index + 1 < take and not self.quota_exhausted:
                # Free-plan friendly pacing; keep short so toolbar sync follow-up
                # does not feel stuck for a minute on large league selections.
                await asyncio.sleep(0.35)

        logger.info(
            "Odds sync done: upserted=%s missing=%s refreshed_candidates=%s (window %s..%s)",
            updated,
            len(missing),
            len(refreshable),
            min(days),
            max(days),
        )
        return updated

    async def sync_odds_for_prematch_fixtures(
        self,
        fixture_ids: list[int],
    ) -> dict[str, int]:
        """Refresh explicit ids only within today's catalog 【比赛】 scope."""
        from sqlalchemy import select

        from app.services.results_capture import prematch_list_clause

        assert self.session is not None
        from app.services.league_catalog import allowed_league_ids
        from app.services.match_day import current_prematch_match_day

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        today = await current_prematch_match_day(
            self.session,
            now=now,
            league_ids=await allowed_league_ids(self.session),
        )
        requested_ids = sorted(
            {int(fixture_id) for fixture_id in fixture_ids if int(fixture_id) > 0}
        )
        if not requested_ids or not today:
            return {"candidates": 0, "attempted": 0, "updated": 0, "truncated": 0}
        fixtures = list(
            (
                await self.session.execute(
                    select(Fixture)
                    .join(League, League.id == Fixture.league_id)
                    .where(
                        Fixture.id.in_(requested_ids),
                        fixture_match_day_expr() == today,
                        League.is_catalog.is_(True),
                        prematch_list_clause(now),
                    )
                    .order_by(Fixture.date, Fixture.id)
                )
            )
            .scalars()
            .all()
        )
        updated = 0
        attempted = 0
        for index, fixture in enumerate(fixtures):
            if self.quota_exhausted:
                break
            if fixture.date <= datetime.now(timezone.utc).replace(tzinfo=None):
                continue
            fixture_id = int(fixture.id)
            attempted += 1
            try:
                if await self.refresh_odds_for_fixture(
                    fixture_id,
                    restrict_to_current_match_day=False,
                ):
                    updated += 1
            except Exception as exc:
                logger.warning(
                    "Prematch-list batch odds fixture %s failed: %s",
                    fixture_id,
                    exc,
                )
            if index + 1 < len(fixtures) and not self.quota_exhausted:
                await asyncio.sleep(0.35)

        logger.info(
            "Prematch-list batch odds done requested=%s candidates=%s "
            "attempted=%s updated=%s",
            len(requested_ids),
            len(fixtures),
            attempted,
            updated,
        )
        return {
            "candidates": len(fixtures),
            "attempted": attempted,
            "updated": updated,
            "truncated": 0,
        }

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
                    self.cache.note_api_response(self.last_remaining_requests)
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

    async def refresh_fixture_score(self, fixture_id: int, ttl: int | None = None) -> bool:
        """One official detail call → write status / score back to the local DB.

        只由未完场详情点击触发；调用方按开赛多久给 TTL（``score_refresh_ttl``），
        让连续点击复用缓存，不做轮询。
        """
        assert self.session is not None
        payload = await self._get_or_fetch(
            fixture_score_cache_key(fixture_id),
            ttl or TTL_FIXTURE_LIVE_SCORE,
            "refresh_fixture_score",
            lambda client: self.provider.fetch_fixture_detail_payload(client, fixture_id),
        )
        if _api_payload_unusable(payload):
            logger.warning(
                "Live score refresh blocked for fixture %s: %s",
                fixture_id,
                _api_payload_errors(payload),
            )
            return False
        fixtures = self.provider.parse_fixtures(payload)
        saved = await self._persist_fixtures(fixtures, fetch_teams=False)
        return saved > 0

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
            "auth_mode": "api_sports",
            "host": self.settings.api_host,
            "remaining_requests": self.last_remaining_requests,
            "sample_keys": list(payload.keys()) if isinstance(payload, dict) else [],
            "cache_stats": self.cache.get_stats(),
        }
