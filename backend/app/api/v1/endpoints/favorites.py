from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.response import (
    FavoriteFixtureCreateRequest,
    FavoriteFixtureResponse,
    FavoriteFixturesResponse,
)
from app.services import favorites as favorites_service

router = APIRouter(prefix="/favorites", tags=["favorites"])


def _set_no_cache_headers(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Data-Source"] = "database"


@router.get("", response_model=FavoriteFixturesResponse)
async def list_favorites(
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> FavoriteFixturesResponse:
    """List all favorites hydrated from local fixtures + pre_match_data."""
    _set_no_cache_headers(response)
    items = await favorites_service.list_favorite_responses(db)
    return FavoriteFixturesResponse(total=len(items), favorites=items)


@router.post("", response_model=FavoriteFixtureResponse)
async def create_favorite(
    body: FavoriteFixtureCreateRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> FavoriteFixtureResponse:
    """Add or bump a favorite (idempotent)."""
    _set_no_cache_headers(response)
    try:
        return await favorites_service.add_favorite(db, body.fixture_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="比赛不存在，无法收藏") from exc


@router.delete("/{fixture_id}", status_code=204)
async def delete_favorite(
    fixture_id: int,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Remove a favorite. Idempotent when already absent."""
    _set_no_cache_headers(response)
    await favorites_service.remove_favorite(db, fixture_id)
    return Response(status_code=204)
