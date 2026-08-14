"""Register / login / logout / me — session token lives in an httpOnly cookie."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps_auth import CurrentUserId, session_token_from_request
from app.api.v1.http_cache import set_no_store_headers
from app.core.config import get_settings
from app.core.database import get_db
from app.schemas.response import (
    AuthClaimResponse,
    AuthCredentialsRequest,
    AuthSessionResponse,
    AuthUserResponse,
)
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=token,
        max_age=auth_service.SESSION_DAYS * 24 * 3600,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite=settings.SESSION_COOKIE_SAMESITE,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite=settings.SESSION_COOKIE_SAMESITE,
        path="/",
    )


def _user_response(user) -> AuthUserResponse:
    return AuthUserResponse(
        id=user.id,
        username=user.username,
        is_admin=bool(user.is_admin),
    )


def _session_payload(*, user, claimed: dict[str, int]) -> AuthSessionResponse:
    return AuthSessionResponse(
        user=_user_response(user),
        claimed=AuthClaimResponse(
            favorites=int(claimed.get("favorites", 0)),
            favorites_dup_dropped=int(claimed.get("favorites_dup_dropped", 0)),
            plans=int(claimed.get("plans", 0)),
        ),
    )


@router.post("/register", response_model=AuthSessionResponse)
async def register(
    body: AuthCredentialsRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthSessionResponse:
    set_no_store_headers(response)
    try:
        user = await auth_service.register_user(db, body.username, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    session = await auth_service.create_session(db, user.id)
    claimed = await auth_service.claim_anonymous_private_data(db, user.id)
    await db.commit()
    _set_session_cookie(response, session.token)
    return _session_payload(user=user, claimed=claimed)


@router.post("/login", response_model=AuthSessionResponse)
async def login(
    body: AuthCredentialsRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthSessionResponse:
    set_no_store_headers(response)
    if not (body.username or "").strip() or not body.password:
        raise HTTPException(status_code=400, detail="请输入账号和密码")

    user = await auth_service.authenticate_user(db, body.username, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail="账号或密码错误")

    session = await auth_service.create_session(db, user.id)
    claimed = await auth_service.claim_anonymous_private_data(db, user.id)
    await db.commit()
    _set_session_cookie(response, session.token)
    return _session_payload(user=user, claimed=claimed)


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Revoke the session row and drop the cookie. Idempotent for guests."""
    token = session_token_from_request(request)
    if token:
        await auth_service.revoke_session(db, token)
        await db.commit()
    response = Response(status_code=204)
    set_no_store_headers(response)
    _clear_session_cookie(response)
    return response


@router.get("/me", response_model=AuthUserResponse)
async def me(
    response: Response,
    user_id: CurrentUserId,
    db: AsyncSession = Depends(get_db),
) -> AuthUserResponse:
    set_no_store_headers(response)
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")
    user = await auth_service.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="未登录")
    return _user_response(user)
