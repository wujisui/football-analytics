from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ApiProvider = Literal["api_football186", "api_football", "live_football_data"]

BACKEND_ROOT = Path(__file__).resolve().parents[2]
LEAGUES_CATALOG_PATH = BACKEND_ROOT / "config" / "leagues.json"

logger = logging.getLogger(__name__)


def load_local_env() -> None:
    """Load non-secret .env first, then local secrets (secrets override)."""
    load_dotenv(BACKEND_ROOT / ".env", override=False)
    load_dotenv(BACKEND_ROOT / "secrets.local.env", override=True)


def _parse_league_catalog(raw: list[Any]) -> tuple[dict[str, int], dict[int, str], dict[int, str]]:
    ids: dict[str, int] = {}
    countries: dict[int, str] = {}
    seasons: dict[int, str] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        league_id = item.get("id")
        if not name or league_id is None:
            continue
        lid = int(league_id)
        ids[name] = lid
        country = item.get("country")
        if country:
            countries[lid] = str(country)
        season = item.get("season")
        if season is not None and str(season).strip():
            seasons[lid] = str(season).strip()
    return ids, countries, seasons


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(
            str(BACKEND_ROOT / ".env"),
            str(BACKEND_ROOT / "secrets.local.env"),
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Official API-Sports key (preferred). Keep it in secrets.local.env only.
    API_SPORTS_KEY: str = ""
    # RapidAPI fallback (optional)
    RAPIDAPI_KEY: str = ""
    RAPIDAPI_HOST: str = "v3.football.api-sports.io"
    API_BASE_HOST: str = "v3.football.api-sports.io"

    API_PROVIDER: ApiProvider = "api_football"
    API_ENDPOINT_LEAGUES: str = "/leagues"
    API_ENDPOINT_TEAMS: str = "/teams"
    API_ENDPOINT_FIXTURES: str = "/fixtures"
    API_ENDPOINT_FIXTURE_DETAIL: str = "/fixtures"
    API_ENDPOINT_QUOTA: str = "/status"
    API_ENDPOINT_HEADTOHEAD: str = "/fixtures/headtohead"
    API_ENDPOINT_TEAM_STATISTICS: str = "/teams/statistics"
    API_ENDPOINT_STANDINGS: str = "/standings"
    API_ENDPOINT_ODDS: str = "/odds"
    API_ENDPOINT_LINEUPS: str = "/fixtures/lineups"
    API_ENDPOINT_INJURIES: str = "/injuries"
    API_ENDPOINT_PREDICTIONS: str = "/predictions"
    HTTP_VERIFY_SSL: bool = True
    # Max seconds the analysis endpoint may spend on official API enrichment.
    ANALYSIS_API_BUDGET_SECONDS: float = 12.0
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/football.db"
    REDIS_URL: str = "redis://localhost:6379"
    # When false, skip Redis and use in-memory fakeredis (recommended for local without Redis).
    REDIS_ENABLED: bool = False
    LOG_LEVEL: str = "INFO"
    SCHEDULER_TIMEZONE: str = "Asia/Shanghai"
    CLEANUP_DAYS: int = 7
    ADMIN_API_KEY: str = ""
    LOG_DIR: str = "logs"
    # Session cookie for /auth. httpOnly so page scripts can never read it.
    SESSION_COOKIE_NAME: str = "fa_session"
    # Must be true in production (HTTPS only). See docs/AUTH_VIP_QUOTA.md §4.2.
    SESSION_COOKIE_SECURE: bool = False
    # lax blocks the cookie on cross-site fetch/XHR — baseline CSRF defense.
    SESSION_COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    # Credentialed browser origins. Cookie auth makes a wildcard unsafe.
    CORS_ALLOW_ORIGINS: str = (
        "http://localhost:7800,http://127.0.0.1:7800,"
        "http://localhost:5173,http://127.0.0.1:5173"
    )
    # Prefer local DB / cache before calling API-Sports (saves quota).
    LOCAL_FIRST: bool = True
    # Future / paid scale default (env). Runtime override via Mine admin UI
    # persists in app_settings; scheduled batches read the effective value.
    ENABLE_SCHEDULED_FULL_DETAIL: bool = False
    # Max incomplete catalog prematch fixtures to enrich per scheduled batch
    # when the flag is on. Each fixture may cost several official API calls.
    SCHEDULED_FULL_DETAIL_BUDGET: int = 10
    # History window for H2H / team form / free-plan date+season clamps:
    # - full: paid plan — no artificial 2022–2024 / ±2-day fixture clip
    # - free: API-Sports free tier (default — matches typical local keys)
    API_HISTORY_MODE: Literal["full", "free"] = "free"
    # Optional override for analysis refresh TTL (seconds). Empty/0 = kickoff-based policy.
    ANALYSIS_REFRESH_TTL_SECONDS: int = 0
    # ML: accumulate local labels from now; auto-train & switch when enough samples.
    ML_MIN_TRAIN_SAMPLES: int = 30
    ML_AUTO_TRAIN: bool = True
    ML_AH_MIN_TRAIN_SAMPLES: int = 80
    ML_AH_AUTO_TRAIN: bool = True

    # Optional JSON array override (same shape as config/leagues.json). Highest priority.
    LEAGUES_JSON: str = ""

    # Built-in fallback when no catalog file / LEAGUES_JSON is present.
    # Prefer editing backend/config/leagues.json — left menu + fixture sync both use it.
    LEAGUE_IDS: dict[str, int] = {
        "世界杯": 1,
        "欧洲杯": 4,
        "欧国联": 5,
        "美洲杯": 9,
        "非洲杯": 6,
        "亚洲杯": 7,
        "金杯赛": 22,
        "欧冠": 2,
        "欧罗巴": 3,
        "欧协联": 848,
        "亚冠": 10,
        "亚冠精英": 17,
        "解放者杯": 13,
        "南美杯": 11,
        "世俱杯": 16,
        "英超": 39,
        "英冠": 40,
        "西甲": 140,
        "德甲": 78,
        "德乙": 79,
        "意甲": 135,
        "法甲": 61,
        "法乙": 62,
        "荷甲": 88,
        "荷乙": 89,
        "葡超": 94,
        "苏超": 179,
        "挪超": 103,
        "瑞典超": 113,
        "巴甲": 71,
        "阿甲": 128,
        "美职联": 253,
        "中超": 169,
        "日职联": 98,
        "韩K联": 292,
        "澳超": 188,
        "沙特联": 307,
    }
    LEAGUE_COUNTRIES: dict[int, str] = {
        1: "World",
        4: "World",
        5: "World",
        9: "World",
        6: "World",
        7: "World",
        22: "World",
        2: "World",
        3: "World",
        848: "World",
        10: "World",
        17: "World",
        13: "World",
        11: "World",
        16: "World",
        39: "England",
        40: "England",
        140: "Spain",
        78: "Germany",
        79: "Germany",
        135: "Italy",
        61: "France",
        62: "France",
        88: "Netherlands",
        89: "Netherlands",
        94: "Portugal",
        179: "Scotland",
        103: "Norway",
        113: "Sweden",
        71: "Brazil",
        128: "Argentina",
        253: "USA",
        169: "China",
        98: "Japan",
        292: "South-Korea",
        188: "Australia",
        307: "Saudi-Arabia",
    }
    # Optional per-league season override (catalog ``season`` field / env).
    LEAGUE_SEASONS: dict[int, str] = {}
    # Inclusive forward window including today. Must cover the date-strip future
    # span (HOME_DATE_RADIUS=7 → today..today+7 = 8 days).
    FIXTURES_LOOKAHEAD_DAYS: int = 8

    @model_validator(mode="after")
    def apply_league_catalog(self) -> Settings:
        raw: list[Any] | None = None
        source = ""
        text = (self.LEAGUES_JSON or "").strip()
        if text:
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    raw = parsed
                    source = "LEAGUES_JSON"
            except json.JSONDecodeError as exc:
                logger.warning("LEAGUES_JSON invalid, ignoring: %s", exc)
        if raw is None and LEAGUES_CATALOG_PATH.is_file():
            try:
                parsed = json.loads(LEAGUES_CATALOG_PATH.read_text(encoding="utf-8"))
                if isinstance(parsed, list):
                    raw = parsed
                    source = str(LEAGUES_CATALOG_PATH)
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("Failed to load %s: %s", LEAGUES_CATALOG_PATH, exc)

        if raw is not None:
            ids, countries, seasons = _parse_league_catalog(raw)
            if ids:
                self.LEAGUE_IDS = ids
                merged_countries = dict(self.LEAGUE_COUNTRIES)
                merged_countries.update(countries)
                self.LEAGUE_COUNTRIES = {
                    lid: merged_countries[lid]
                    for lid in ids.values()
                    if lid in merged_countries
                }
                merged_seasons = dict(self.LEAGUE_SEASONS)
                merged_seasons.update(seasons)
                self.LEAGUE_SEASONS = {
                    lid: merged_seasons[lid] for lid in ids.values() if lid in merged_seasons
                }
                logger.info("Loaded %s leagues from %s", len(ids), source)
            else:
                logger.warning(
                    "League catalog %s produced no leagues; keeping defaults", source
                )

        return self

    @property
    def cors_allow_origins(self) -> list[str]:
        """Explicit origin allowlist; credentialed cookie auth forbids "*"."""
        return [
            origin.strip()
            for origin in self.CORS_ALLOW_ORIGINS.split(",")
            if origin.strip()
        ]

    @property
    def api_host(self) -> str:
        return (self.API_BASE_HOST or self.RAPIDAPI_HOST).strip()

    @property
    def api_base_url(self) -> str:
        return f"https://{self.api_host}"

    @property
    def league_display_names(self) -> dict[int, str]:
        """league_id → configured 中文 display name."""
        return {league_id: name for name, league_id in self.LEAGUE_IDS.items()}

    def league_display_name(self, league_id: int, fallback: str = "") -> str:
        return self.league_display_names.get(league_id) or fallback or f"League {league_id}"

    def configured_season(self, league_id: int, fallback: str | None = None) -> str | None:
        """Season hint from catalog; None → caller may use DB / calendar year."""
        if league_id in self.LEAGUE_SEASONS:
            return self.LEAGUE_SEASONS[league_id]
        return fallback

    @property
    def uses_api_sports_direct(self) -> bool:
        return bool(self.API_SPORTS_KEY.strip())

    @property
    def uses_full_history(self) -> bool:
        return self.API_HISTORY_MODE == "full"

    @property
    def history_source_tag(self) -> str:
        """Bump when fetch strategy changes so stale package rows refresh."""
        return "full-history-v1" if self.uses_full_history else "free-2022-2024-v3"

    @property
    def football_api_key(self) -> str:
        return self.API_SPORTS_KEY.strip() or self.RAPIDAPI_KEY.strip()

    def football_api_headers(self) -> dict[str, str]:
        if self.uses_api_sports_direct:
            return {
                "x-apisports-key": self.API_SPORTS_KEY.strip(),
                "Content-Type": "application/json",
            }
        return {
            "X-RapidAPI-Key": self.RAPIDAPI_KEY.strip(),
            "X-RapidAPI-Host": self.api_host,
            "Content-Type": "application/json",
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
