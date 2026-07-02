from fastapi import APIRouter

from app.api.v1.endpoints import admin, fixtures, health, leagues

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(fixtures.router)
api_router.include_router(leagues.router)
api_router.include_router(admin.router)
