from typing import Any

from fastapi import APIRouter

from app.services.cache import get_cache_service

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, Any]:
    cache = get_cache_service()
    stats = cache.get_stats()
    return {
        "status": "ok",
        "message": "Football Analytics API is running",
        "cache_hits": stats["cache_hits"],
        "cache_misses": stats["cache_misses"],
        "cache_hit_rate": stats["cache_hit_rate"],
        "api_remaining": stats["api_remaining"],
        "last_update": stats["last_update"],
    }
