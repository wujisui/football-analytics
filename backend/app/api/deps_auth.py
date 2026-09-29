"""Resolve the current owner from the httpOnly session cookie.

Missing / invalid cookie → ``None`` (guest). Private writes (收藏 / 方案) must
use ``RequiredUserId`` and return 401. Staff ops accept a logged-in
system/ops admin or the legacy ``X-Admin-Key`` header. Subscription, catalog
delete, backend wipe and user management require the system admin.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models.user import User
from app.services import auth as auth_service
from app.services.user_roles import is_staff_role, is_system_admin_role


def session_token_from_request(request: Request) -> str | None:
    token = request.cookies.get(get_settings().SESSION_COOKIE_NAME) or ""
    return token.strip() or None


async def get_current_user_id(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> str | None:
    """Return authenticated user id, or ``None`` when no valid session."""
    return await auth_service.resolve_user_id_from_token(
        db, session_token_from_request(request)
    )


async def require_current_user_id(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> str:
    """Same as ``get_current_user_id``, but 401 when the caller is a guest."""
    user_id = await auth_service.resolve_user_id_from_token(
        db, session_token_from_request(request)
    )
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    return user_id


CurrentUserId = Annotated[str | None, Depends(get_current_user_id)]
RequiredUserId = Annotated[str, Depends(require_current_user_id)]


def _admin_key_matches(x_admin_key: str | None) -> bool:
    configured = (get_settings().ADMIN_API_KEY or "").strip()
    return bool(configured) and x_admin_key == configured


async def _session_user(request: Request, db: AsyncSession) -> User | None:
    user_id = await auth_service.resolve_user_id_from_token(
        db, session_token_from_request(request)
    )
    if not user_id:
        return None
    return await auth_service.get_user_by_id(db, user_id)


def _reject_admin(user: User | None) -> None:
    if user is None and not (get_settings().ADMIN_API_KEY or "").strip():
        raise HTTPException(
            status_code=503,
            detail="未配置管理员：请用 manage.py set-admin 提升账号，或设置 ADMIN_API_KEY",
        )
    raise HTTPException(status_code=403, detail="需要管理员权限")


async def require_admin(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_admin_key: str | None = Header(default=None),
) -> None:
    """System admin, ops admin, or the legacy X-Admin-Key.

    Cookie path is preferred for the Mine UI. The env key remains for scripts.
    """
    user = await _session_user(request, db)
    if user is not None and is_staff_role(user.role):
        return
    if _admin_key_matches(x_admin_key):
        return
    _reject_admin(user)


async def require_system_admin(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_admin_key: str | None = Header(default=None),
) -> None:
    """System admin or X-Admin-Key. Ops admin is not enough."""
    user = await _session_user(request, db)
    if user is not None and is_system_admin_role(user.role):
        return
    if _admin_key_matches(x_admin_key):
        return
    if user is not None and is_staff_role(user.role):
        raise HTTPException(status_code=403, detail="需要系统管理员权限")
    _reject_admin(user)


async def require_system_admin_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Logged-in system admin only. Admin Key cannot confirm a password."""
    user = await _session_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="请先用系统管理员账号登录")
    if not is_system_admin_role(user.role):
        raise HTTPException(status_code=403, detail="需要系统管理员账号登录")
    return user


SystemAdminUser = Annotated[User, Depends(require_system_admin_user)]
