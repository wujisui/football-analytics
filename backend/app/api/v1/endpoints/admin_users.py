"""Staff can list accounts. Role, password and delete stay with the system admin."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps_auth import SystemAdminUser, require_admin
from app.core.database import get_db
from app.schemas.response import AdminUserListResponse, AdminUserRow, UserAccountUpdate
from app.services import auth as auth_service
from app.services.user_roles import ROLE_LABELS

router = APIRouter(prefix="/admin", tags=["admin"])


def _row(user) -> AdminUserRow:
    return AdminUserRow(
        id=user.id,
        username=user.username,
        role=user.role if user.role in ROLE_LABELS else user.role,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


@router.get("/users", response_model=AdminUserListResponse)
async def list_accounts(
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminUserListResponse:
    users = await auth_service.list_users(db)
    return AdminUserListResponse(users=[_row(user) for user in users])


@router.patch("/users/{user_id}", response_model=AdminUserRow)
async def update_account(
    user_id: str,
    body: UserAccountUpdate,
    _: SystemAdminUser,
    db: AsyncSession = Depends(get_db),
) -> AdminUserRow:
    try:
        user = await auth_service.update_user_account(
            db,
            user_id,
            role=body.role,
            password=body.password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    await db.commit()
    return _row(user)


@router.delete("/users/{user_id}", status_code=204)
async def delete_account(
    user_id: str,
    _: SystemAdminUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await auth_service.delete_user_account(db, user_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    await db.commit()
