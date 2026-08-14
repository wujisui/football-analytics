"""Resolve the current owner from the httpOnly session cookie.

Missing / invalid cookie → ``None`` (guest bucket). The token is never exposed
to page scripts. Admin ops accept either a logged-in ``is_admin`` user or the
legacy ``X-Admin-Key`` header. See ``docs/AUTH_VIP_QUOTA.md`` §4.2 / §4.4.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.services import auth as auth_service


def session_token_from_request(request: Request) -> str | None:
    token = request.cookies.get(get_settings().SESSION_COOKIE_NAME) or ""
    return token.strip() or None


async def get_current_user_id(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> str | None:
    """Return authenticated user id, or ``None`` for the guest owner bucket."""
    return await auth_service.resolve_user_id_from_token(
        db, session_token_from_request(request)
    )


CurrentUserId = Annotated[str | None, Depends(get_current_user_id)]


async def require_admin(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_admin_key: str | None = Header(default=None),
) -> None:
    """Allow admin routes when the session user is admin, or via X-Admin-Key.

    Cookie path is preferred for the Mine UI. The env key remains for scripts /
    curl so ops are not blocked if no admin user exists yet.
    """
    user_id = await auth_service.resolve_user_id_from_token(
        db, session_token_from_request(request)
    )
    if user_id:
        user = await auth_service.get_user_by_id(db, user_id)
        if user is not None and bool(user.is_admin):
            return

    settings = get_settings()
    configured = (settings.ADMIN_API_KEY or "").strip()
    if configured and x_admin_key == configured:
        return

    if not configured and not user_id:
        raise HTTPException(
            status_code=503,
            detail="未配置管理员：请用 manage.py set-admin 提升账号，或设置 ADMIN_API_KEY",
        )
    raise HTTPException(status_code=403, detail="需要管理员权限")
