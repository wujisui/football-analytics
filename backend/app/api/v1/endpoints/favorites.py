from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps_auth import CurrentUserId, RequiredUserId
from app.api.v1.http_cache import set_no_store_headers
from app.core.database import get_db
from app.schemas.response import (
    FavoriteFixtureCreateRequest,
    FavoriteFixtureResponse,
    FavoriteFixturesResponse,
)
from app.services import favorites as favorites_service

router = APIRouter(prefix="/favorites", tags=["favorites"])


@router.get("", response_model=FavoriteFixturesResponse)
async def list_favorites(
    response: Response,
    user_id: CurrentUserId,
    db: AsyncSession = Depends(get_db),
) -> FavoriteFixturesResponse:
    """List favorites for the current session (guest sees shared auto tips only)."""
    set_no_store_headers(response)
    items = await favorites_service.list_favorite_responses(db, user_id=user_id)
    return FavoriteFixturesResponse(total=len(items), favorites=items)


@router.post("", response_model=FavoriteFixtureResponse)
async def create_favorite(
    body: FavoriteFixtureCreateRequest,
    response: Response,
    user_id: RequiredUserId,
    db: AsyncSession = Depends(get_db),
) -> FavoriteFixtureResponse:
    """Add or bump a favorite (idempotent). Guests get 401 — login required."""
    set_no_store_headers(response)
    try:
        return await favorites_service.add_favorite(
            db, body.fixture_id, user_id=user_id
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="比赛不存在，无法收藏") from exc


@router.delete("/{fixture_id}", status_code=204)
async def delete_favorite(
    fixture_id: int,
    response: Response,
    user_id: RequiredUserId,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Remove a favorite. Guests get 401 — login required."""
    set_no_store_headers(response)
    await favorites_service.remove_favorite(db, fixture_id, user_id=user_id)
    return Response(status_code=204)
