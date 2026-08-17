import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api.v1.router import api_router
from app.core.config import get_settings, load_local_env
from app.core.logging import setup_logging
from app.tasks import shutdown_scheduler, start_scheduler

load_local_env()

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.LOG_LEVEL, settings.LOG_DIR)
    logger.info("Application startup")
    # Ensure SQLite schema (e.g. new pre_match_data columns) before serving traffic.
    from app.core.database import init_db
    from app.services.cache import get_cache_service
    from app.tasks.scheduler import refresh_fixture_sync_jobs

    await init_db()
    # Warm cache once so the first API request does not pay Redis connect latency.
    await get_cache_service().connect()
    start_scheduler()
    # Re-apply free-quota cron from app_settings (env default until admin overrides).
    await refresh_fixture_sync_jobs()
    yield
    shutdown_scheduler()
    await get_cache_service().close()
    logger.info("Application shutdown")


app = FastAPI(
    title="Football Analytics API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    # Explicit allowlist: the session cookie is credentialed, so a wildcard
    # would let any page call the API as the logged-in user.
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/api/v1/health")
