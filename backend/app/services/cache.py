import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.core.config import get_settings
from app.services.ttl_policy import (
    TTL_ANALYSIS_REDIS,
    TTL_FIXTURES_TODAY,
    TTL_LEAGUES,
    TTL_TEAMS,
    fixture_detail_ttl,
    refresh_ttl_seconds,
)

logger = logging.getLogger(__name__)

# Backward-compatible aliases used across the codebase
TTL_ANALYSIS = TTL_ANALYSIS_REDIS
TTL_HEADTOHEAD = 24 * 3600
TTL_TEAM_FORM = 24 * 3600
TTL_TEAM_STATISTICS = 24 * 3600
TTL_STANDINGS = 12 * 3600
TTL_FIXTURE_DETAIL_NEAR = 120
TTL_FIXTURE_DETAIL_FAR = 3600

_cache_service: "CacheService | None" = None


def fixtures_cache_key(date: str) -> str:
    return f"api:football:fixtures:date:{date}"


def fixtures_day_leagues_cache_key(date: str) -> str:
    """Aggregated league IDs playing on a calendar day (from worldwide date=)."""
    return f"api:football:fixtures:day-leagues:{date}"


def fixtures_league_date_cache_key(league_id: int, date: str, season: str) -> str:
    return f"api:football:fixtures:league:{league_id}:season:{season}:date:{date}"


def fixtures_league_range_cache_key(
    league_id: int, season: str, date_from: str, date_to: str
) -> str:
    return (
        f"api:football:fixtures:league:{league_id}:season:{season}"
        f":from:{date_from}:to:{date_to}"
    )


def fixture_cache_key(fixture_id: int) -> str:
    return f"api:football:fixture:{fixture_id}"


def leagues_cache_key(league_ids: list[int]) -> str:
    ids = ",".join(map(str, sorted(league_ids)))
    return f"api:football:leagues:{ids}"


def teams_cache_key(league_id: int, season: str) -> str:
    return f"api:football:teams:league:{league_id}:season:{season}"


def analysis_cache_key(fixture_id: int) -> str:
    return f"analysis:fixture:{fixture_id}"


def headtohead_cache_key(
    home_team_id: int,
    away_team_id: int,
    last: int = 5,
    *,
    window: str = "free",
) -> str:
    # window distinguishes free-plan date-range fetches from legacy last=N keys
    return f"api:football:h2h:{home_team_id}:{away_team_id}:{window}:{last}"


def team_form_cache_key(team_id: int, last: int = 5, *, season: str | int | None = None) -> str:
    # Include season so free-plan season-based fetches don't collide with empty last=N cache
    season_part = str(season) if season is not None else "auto"
    return f"api:football:form:team:{team_id}:season:{season_part}:n:{last}"


def team_statistics_cache_key(team_id: int, league_id: int, season: str) -> str:
    return f"api:football:stats:team:{team_id}:league:{league_id}:season:{season}"


def standings_cache_key(league_id: int, season: str) -> str:
    return f"api:football:standings:league:{league_id}:season:{season}"


def odds_cache_key(fixture_id: int) -> str:
    return f"api:football:odds:fixture:{fixture_id}"


def lineups_cache_key(fixture_id: int) -> str:
    return f"api:football:lineups:fixture:{fixture_id}"


def injuries_cache_key(fixture_id: int) -> str:
    return f"api:football:injuries:fixture:{fixture_id}"


def predictions_cache_key(fixture_id: int) -> str:
    return f"api:football:predictions:fixture:{fixture_id}"


class CacheService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._redis: Any = None
        self.enabled = True
        self.using_fakeredis = False
        self.hits = 0
        self.misses = 0
        self.last_api_remaining: int | None = None
        self.last_data_update: datetime | None = None

    async def _use_fakeredis(self, reason: str) -> None:
        try:
            from fakeredis import aioredis as fakeredis_aioredis

            self._redis = fakeredis_aioredis.FakeRedis(decode_responses=True)
            self.using_fakeredis = True
            logger.info("Using fakeredis in-memory cache (%s).", reason)
        except Exception as fallback_exc:
            logger.error("Cache disabled: %s", fallback_exc)
            self.enabled = False
            self._redis = None

    async def connect(self) -> None:
        if self._redis is not None:
            return

        if not self.settings.REDIS_ENABLED:
            await self._use_fakeredis("REDIS_ENABLED=false")
            return

        try:
            import asyncio

            import redis.asyncio as redis

            client = redis.from_url(
                self.settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=0.3,
                socket_timeout=0.3,
            )
            await asyncio.wait_for(client.ping(), timeout=0.4)
            self._redis = client
            self.using_fakeredis = False
            logger.info("Connected to Redis at %s", self.settings.REDIS_URL)
        except Exception as exc:
            logger.warning(
                "Redis unavailable (%s), falling back to fakeredis in-memory cache.",
                exc,
            )
            await self._use_fakeredis(str(exc))

    async def close(self) -> None:
        if self._redis is not None and hasattr(self._redis, "aclose"):
            await self._redis.aclose()
        self._redis = None

    def record_hit(self) -> None:
        self.hits += 1

    def record_miss(self) -> None:
        self.misses += 1

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return round(self.hits / total, 4)

    async def get(self, key: str) -> dict[str, Any] | None:
        if not self.enabled:
            return None

        await self.connect()
        if self._redis is None:
            return None

        try:
            raw = await self._redis.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception as exc:
            logger.warning("Cache get failed for %s: %s", key, exc)
            return None

    async def set(self, key: str, value: Any, ttl: int = 120) -> None:
        if not self.enabled:
            return

        await self.connect()
        if self._redis is None:
            return

        payload = {
            "payload": value,
            "_cached_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            await self._redis.set(key, json.dumps(payload), ex=max(ttl, 1))
        except Exception as exc:
            logger.warning("Cache set failed for %s: %s", key, exc)

    async def delete(self, key: str) -> None:
        if not self.enabled:
            return

        await self.connect()
        if self._redis is None:
            return

        try:
            await self._redis.delete(key)
        except Exception as exc:
            logger.warning("Cache delete failed for %s: %s", key, exc)

    async def exists(self, key: str) -> bool:
        if not self.enabled:
            return False

        await self.connect()
        if self._redis is None:
            return False

        try:
            return bool(await self._redis.exists(key))
        except Exception as exc:
            logger.warning("Cache exists check failed for %s: %s", key, exc)
            return False

    async def clear_pattern(self, pattern: str) -> int:
        if not self.enabled:
            return 0

        await self.connect()
        if self._redis is None:
            return 0

        deleted = 0
        try:
            async for key in self._redis.scan_iter(match=pattern):
                await self._redis.delete(key)
                deleted += 1
        except Exception as exc:
            logger.warning("Cache clear_pattern failed for %s: %s", pattern, exc)
        return deleted

    def get_stats(self) -> dict[str, Any]:
        return {
            "cache_hits": self.hits,
            "cache_misses": self.misses,
            "cache_hit_rate": self.hit_rate,
            "api_remaining": self.last_api_remaining,
            "last_update": (
                self.last_data_update.isoformat() if self.last_data_update else None
            ),
            "cache_enabled": self.enabled,
            "using_fakeredis": self.using_fakeredis,
        }


def get_cache_service() -> CacheService | None:
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service


__all__ = [
    "TTL_ANALYSIS",
    "TTL_FIXTURES_TODAY",
    "TTL_HEADTOHEAD",
    "TTL_LEAGUES",
    "TTL_TEAM_FORM",
    "TTL_STANDINGS",
    "TTL_TEAM_STATISTICS",
    "TTL_TEAMS",
    "CacheService",
    "analysis_cache_key",
    "fixture_cache_key",
    "fixture_detail_ttl",
    "fixtures_cache_key",
    "fixtures_day_leagues_cache_key",
    "fixtures_league_date_cache_key",
    "fixtures_league_range_cache_key",
    "get_cache_service",
    "headtohead_cache_key",
    "injuries_cache_key",
    "predictions_cache_key",
    "leagues_cache_key",
    "lineups_cache_key",
    "odds_cache_key",
    "refresh_ttl_seconds",
    "standings_cache_key",
    "team_form_cache_key",
    "team_statistics_cache_key",
    "teams_cache_key",
]
