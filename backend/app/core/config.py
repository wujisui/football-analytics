from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

ApiProvider = Literal["api_football186", "api_football", "live_football_data"]

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def load_local_env() -> None:
    """Load non-secret .env first, then local secrets (secrets override)."""
    load_dotenv(BACKEND_ROOT / ".env", override=False)
    load_dotenv(BACKEND_ROOT / "secrets.local.env", override=True)


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
    HTTP_VERIFY_SSL: bool = True
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/football.db"
    REDIS_URL: str = "redis://localhost:6379"
    LOG_LEVEL: str = "INFO"
    SCHEDULER_TIMEZONE: str = "Asia/Shanghai"
    PRE_MATCH_WINDOW_HOURS: int = 2
    CLEANUP_DAYS: int = 7
    ADMIN_API_KEY: str = ""
    LOG_DIR: str = "logs"
    # Prefer local DB / cache before calling API-Sports (saves quota).
    LOCAL_FIRST: bool = True
    # Optional override for analysis refresh TTL (seconds). Empty/0 = kickoff-based policy.
    ANALYSIS_REFRESH_TTL_SECONDS: int = 0

    LEAGUE_IDS: dict[str, int] = {
        "英超": 39,
        "西甲": 140,
        "德甲": 78,
        "意甲": 135,
        "法甲": 61,
        "欧冠": 2,
        "欧罗巴": 3,
        "亚冠": 10,
        "MLS": 253,
        "Brazil Serie A": 71,
    }

    @property
    def api_host(self) -> str:
        return (self.API_BASE_HOST or self.RAPIDAPI_HOST).strip()

    @property
    def api_base_url(self) -> str:
        return f"https://{self.api_host}"

    @property
    def uses_api_sports_direct(self) -> bool:
        return bool(self.API_SPORTS_KEY.strip())

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
