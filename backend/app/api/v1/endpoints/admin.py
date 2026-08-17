import asyncio

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps_auth import require_admin
from app.core.config import get_settings
from app.core.database import get_db
from app.services.runtime_settings import (
    get_enable_free_quota,
    get_enable_scheduled_full_detail,
    set_enable_free_quota,
    set_enable_scheduled_full_detail,
)
from app.tasks.scheduler import (
    free_quota_catch_up_due,
    get_task_status,
    refresh_fixture_sync_jobs,
    run_scheduled_fixtures_sync,
    trigger_task,
)

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


class FreeQuotaSetting(BaseModel):
    enabled: bool
    source: str = Field(description="db = 管理员已覆盖；env = 使用环境变量默认值")
    sync_hours: list[int] = Field(
        description="当前生效的定时同步整点（SCHEDULER_TIMEZONE）"
    )
    catch_up_started: bool = Field(
        default=False,
        description="本次开启且已过今日 11:00 时，是否已后台补跑一次同步",
    )


class FreeQuotaUpdate(BaseModel):
    enabled: bool


def _full_detail_payload(enabled: bool, source: str) -> ScheduledFullDetailSetting:
    return ScheduledFullDetailSetting(
        enabled=enabled,
        source=source,
        budget=max(0, int(get_settings().SCHEDULED_FULL_DETAIL_BUDGET)),
    )


def _free_quota_payload(
    enabled: bool,
    source: str,
    *,
    catch_up_started: bool = False,
) -> FreeQuotaSetting:
    hours = [11] if enabled else [0, 6, 11, 16, 19, 22]
    return FreeQuotaSetting(
        enabled=enabled,
        source=source,
        sync_hours=hours,
        catch_up_started=catch_up_started,
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


@router.get("/settings/free-quota", response_model=FreeQuotaSetting)
async def get_free_quota_setting(
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> FreeQuotaSetting:
    enabled, source = await get_enable_free_quota(db)
    return _free_quota_payload(enabled, source)


@router.patch("/settings/free-quota", response_model=FreeQuotaSetting)
async def patch_free_quota_setting(
    body: FreeQuotaUpdate,
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> FreeQuotaSetting:
    previous, _ = await get_enable_free_quota(db)
    enabled = await set_enable_free_quota(db, body.enabled)
    await refresh_fixture_sync_jobs()

    catch_up_started = False
    # Newly enabled after today's 11:00 slot → run one sync now; skip 16/19/22.
    if enabled and not previous and free_quota_catch_up_due():
        catch_up_started = True
        asyncio.create_task(run_scheduled_fixtures_sync())

    return _free_quota_payload(enabled, "db", catch_up_started=catch_up_started)
