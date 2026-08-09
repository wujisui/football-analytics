from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.services.runtime_settings import (
    get_enable_scheduled_full_detail,
    set_enable_scheduled_full_detail,
)
from app.tasks.scheduler import get_task_status, trigger_task

router = APIRouter(prefix="/admin", tags=["admin"])


def verify_admin_key(x_admin_key: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if not settings.ADMIN_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Admin API is not configured. Set ADMIN_API_KEY in .env.",
        )
    if x_admin_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid admin API key.")


class TriggerTaskRequest(BaseModel):
    name: str = Field(
        ...,
        description="任务名称：scheduled_fixtures_sync / clean_old_data / train_model",
    )


class ScheduledFullDetailSetting(BaseModel):
    enabled: bool
    source: str = Field(description="db = 管理员已覆盖；env = 使用环境变量默认值")


class ScheduledFullDetailUpdate(BaseModel):
    enabled: bool


@router.get("/tasks")
async def list_task_status(_: None = Depends(verify_admin_key)) -> dict:
    return get_task_status()


@router.post("/tasks/trigger")
async def trigger_task_endpoint(
    body: TriggerTaskRequest,
    _: None = Depends(verify_admin_key),
) -> dict:
    try:
        await trigger_task(body.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "status": "ok",
        "message": f"Task '{body.name}' triggered successfully.",
        "task_status": get_task_status(),
    }


@router.get(
    "/settings/scheduled-full-detail",
    response_model=ScheduledFullDetailSetting,
)
async def get_scheduled_full_detail_setting(
    _: None = Depends(verify_admin_key),
    db: AsyncSession = Depends(get_db),
) -> ScheduledFullDetailSetting:
    enabled, source = await get_enable_scheduled_full_detail(db)
    return ScheduledFullDetailSetting(enabled=enabled, source=source)


@router.patch(
    "/settings/scheduled-full-detail",
    response_model=ScheduledFullDetailSetting,
)
async def patch_scheduled_full_detail_setting(
    body: ScheduledFullDetailUpdate,
    _: None = Depends(verify_admin_key),
    db: AsyncSession = Depends(get_db),
) -> ScheduledFullDetailSetting:
    enabled = await set_enable_scheduled_full_detail(db, body.enabled)
    return ScheduledFullDetailSetting(enabled=enabled, source="db")
