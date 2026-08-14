from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps_auth import require_admin
from app.core.config import get_settings
from app.core.database import get_db
from app.services.runtime_settings import (
    get_enable_scheduled_full_detail,
    set_enable_scheduled_full_detail,
)
from app.tasks.scheduler import get_task_status, trigger_task

router = APIRouter(prefix="/admin", tags=["admin"])


class TriggerTaskRequest(BaseModel):
    name: str = Field(
        ...,
        description="任务名称：scheduled_fixtures_sync / clean_old_data / train_model / daily_auto_favorites",
    )


class ScheduledFullDetailSetting(BaseModel):
    enabled: bool
    source: str = Field(description="db = 管理员已覆盖；env = 使用环境变量默认值")
    budget: int = Field(
        description="每个定时批次最多预拉的缺包场次数（SCHEDULED_FULL_DETAIL_BUDGET）"
    )


class ScheduledFullDetailUpdate(BaseModel):
    enabled: bool


def _full_detail_payload(enabled: bool, source: str) -> ScheduledFullDetailSetting:
    return ScheduledFullDetailSetting(
        enabled=enabled,
        source=source,
        budget=max(0, int(get_settings().SCHEDULED_FULL_DETAIL_BUDGET)),
    )


@router.get("/tasks")
async def list_task_status(_: None = Depends(require_admin)) -> dict:
    return get_task_status()


@router.post("/tasks/trigger")
async def trigger_task_endpoint(
    body: TriggerTaskRequest,
    _: None = Depends(require_admin),
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
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ScheduledFullDetailSetting:
    enabled, source = await get_enable_scheduled_full_detail(db)
    return _full_detail_payload(enabled, source)


@router.patch(
    "/settings/scheduled-full-detail",
    response_model=ScheduledFullDetailSetting,
)
async def patch_scheduled_full_detail_setting(
    body: ScheduledFullDetailUpdate,
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ScheduledFullDetailSetting:
    enabled = await set_enable_scheduled_full_detail(db, body.enabled)
    return _full_detail_payload(enabled, "db")
