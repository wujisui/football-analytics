import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps_auth import AdminUser, require_admin
from app.core.config import get_settings
from app.core.database import get_db
from app.services import auth as auth_service
from app.services.data_cleanup import reset_match_history
from app.services.cache import get_cache_service
from app.services.fixtures_sync import official_sync_busy
from app.services.runtime_settings import (
    default_hot_league_ids,
    get_api_sports_keys_setting,
    get_hot_league_ids,
    get_last_sync_run,
    get_subscription_early_odds,
    get_subscription_enabled,
    set_api_sports_keys_setting,
    set_hot_league_ids,
    set_subscription_early_odds,
    set_subscription_enabled,
)
from app.tasks.scheduler import (
    RESULTS_SYNC_TASK,
    UNSUBSCRIBED_ODDS_HOURS,
    format_clock,
    full_sync_completed_today,
    get_task_status,
    refresh_fixture_sync_jobs,
    subscribed_light_odds_slots,
    trigger_task,
)

router = APIRouter(prefix="/admin", tags=["admin"])


class TriggerTaskRequest(BaseModel):
    name: str = Field(
        ...,
        description=(
            "任务名称：scheduled_fixtures_sync / scheduled_results_sync / "
            "clean_old_data / train_model / daily_auto_favorites"
        ),
    )


class LastSyncRun(BaseModel):
    finished_at: str = Field(description="批次结束时刻（UTC ISO），前端按本地时区展示")
    status: str = Field(description="completed / failed")
    label: str = Field(description="批次类型中文名")
    quota_used: int = Field(description="该批次实际发出的官方请求数")
    api_remaining: int | None = None
    error: str | None = None


class SubscriptionSetting(BaseModel):
    subscribed: bool
    source: str = Field(description="db = 管理员已覆盖；env = 使用环境变量默认值")
    early_odds_enabled: bool
    sync_times: list[str]
    full_sync_completed_today: bool
    api_remaining: int | None = None
    last_sync: LastSyncRun | None = None


class SubscriptionUpdate(BaseModel):
    subscribed: bool


class SubscriptionEarlyOddsUpdate(BaseModel):
    enabled: bool


class ApiSportsKeySetting(BaseModel):
    key_count: int
    masked_keys: str = Field(description="仅末 4 位预览，完整 Key 不回传")


class ApiSportsKeyUpdate(BaseModel):
    password: str = Field(..., min_length=1, description="当前管理员登录密码")
    keys: str = Field(
        default="",
        description="逗号分隔的官方 Key；空字符串表示删除库内覆盖、改回 env",
    )


class HotLeagueItem(BaseModel):
    league_id: int
    league_name: str
    country: str | None = None
    selected: bool


class HotLeaguesSetting(BaseModel):
    league_ids: list[int]
    default_league_ids: list[int] = Field(description="内置默认勾选（五大联赛+欧战+中日韩）")
    source: str = Field(description="db = 管理员已覆盖；env = 内置默认勾选")
    leagues: list[HotLeagueItem] = Field(default_factory=list)


class HotLeaguesUpdate(BaseModel):
    league_ids: list[int] = Field(default_factory=list)


class ResetMatchHistoryRequest(BaseModel):
    password: str = Field(..., min_length=1, description="当前管理员登录密码")
    apply: bool = Field(
        default=False,
        description="false=只预览删除数量；true=真正清空",
    )


class ResetMatchHistoryResponse(BaseModel):
    apply: bool
    fixtures: int
    pre_match_data: int
    match_features: int
    auto_pick_snapshots: int
    favorite_fixtures: int
    league_standings: int
    api_snapshots: int
    incentive_settings_cleared: int
    model_files_removed: int
    cache_cleared: bool
    kept: list[str]


SYNC_MODE_LABELS = {
    "full": "完整批次",
    "odds": "盘口轻刷",
    "fixtures": "当天赛程",
    "results": "赛果回写",
}


def _last_sync_payload(run: dict[str, Any] | None) -> LastSyncRun | None:
    if not run or not run.get("finished_at"):
        return None
    mode = str(run.get("mode") or "")
    return LastSyncRun(
        finished_at=str(run["finished_at"]),
        status=str(run.get("status") or "completed"),
        label=SYNC_MODE_LABELS.get(mode, mode or "同步"),
        quota_used=int(run.get("quota_used") or 0),
        api_remaining=run.get("api_remaining"),
        error=run.get("error"),
    )


async def _subscription_payload(
    subscribed: bool,
    source: str,
) -> SubscriptionSetting:
    early_odds, _ = await get_subscription_early_odds()
    if subscribed:
        times = ["11:00"] + [
            format_clock(hour, minute)
            for hour, minute in subscribed_light_odds_slots(early_odds=early_odds)
        ]
        times = sorted(set(times))
    else:
        times = ["08:05", "11:00"] + [
            format_clock(hour) for hour in UNSUBSCRIBED_ODDS_HOURS
        ]
    last_sync = _last_sync_payload(await get_last_sync_run())
    # Process memory is empty until this deploy calls the official API again,
    # so fall back to the remaining count persisted with the last batch.
    remaining = get_cache_service().last_api_remaining
    if remaining is None and last_sync is not None:
        remaining = last_sync.api_remaining
    return SubscriptionSetting(
        subscribed=subscribed,
        source=source,
        early_odds_enabled=early_odds,
        sync_times=times,
        full_sync_completed_today=await full_sync_completed_today(),
        api_remaining=remaining,
        last_sync=last_sync,
    )


def _reset_history_response(report: Any) -> ResetMatchHistoryResponse:
    payload: dict[str, Any] = report.to_dict()
    payload["kept"] = list(payload.get("kept") or [])
    return ResetMatchHistoryResponse(**payload)


@router.get("/tasks")
async def list_task_status(_: None = Depends(require_admin)) -> dict:
    return get_task_status()


@router.post("/tasks/trigger")
async def trigger_task_endpoint(
    body: TriggerTaskRequest,
    _: None = Depends(require_admin),
) -> dict:
    allowed = {
        "scheduled_fixtures_sync",
        RESULTS_SYNC_TASK,
        "clean_old_data",
        "train_model",
        "daily_auto_favorites",
    }
    if body.name not in allowed:
        raise HTTPException(status_code=400, detail=f"Unknown task: {body.name}")
    if (
        body.name == "scheduled_fixtures_sync"
        and await full_sync_completed_today()
    ):
        raise HTTPException(status_code=409, detail="今日完整批次已完成，无需重复同步")
    if official_sync_busy():
        raise HTTPException(status_code=409, detail="官方同步正在执行，请稍后再试")
    running = (
        get_task_status()
        .get("active_tasks", {})
    )
    if any(
        (running.get(name) or {}).get("status") == "running"
        for name in ("scheduled_fixtures_sync", RESULTS_SYNC_TASK, body.name)
    ):
        raise HTTPException(status_code=409, detail="任务正在执行，请勿重复触发")
    try:
        asyncio.create_task(trigger_task(body.name))
        await asyncio.sleep(0)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "status": "accepted",
        "message": f"Task '{body.name}' started.",
        "task_status": get_task_status(),
    }


@router.get("/settings/subscription", response_model=SubscriptionSetting)
async def get_subscription_setting(
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionSetting:
    subscribed, source = await get_subscription_enabled(db)
    return await _subscription_payload(subscribed, source)


@router.patch("/settings/subscription", response_model=SubscriptionSetting)
async def patch_subscription_setting(
    body: SubscriptionUpdate,
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionSetting:
    subscribed = await set_subscription_enabled(db, body.subscribed)
    await refresh_fixture_sync_jobs()
    return await _subscription_payload(subscribed, "db")


@router.patch("/settings/subscription-early-odds", response_model=SubscriptionSetting)
async def patch_subscription_early_odds_setting(
    body: SubscriptionEarlyOddsUpdate,
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionSetting:
    await set_subscription_early_odds(db, body.enabled)
    subscribed, source = await get_subscription_enabled(db)
    await refresh_fixture_sync_jobs()
    return await _subscription_payload(subscribed, source)


def _hot_leagues_payload(
    league_ids: list[int],
    source: str,
) -> HotLeaguesSetting:
    settings = get_settings()
    selected = set(league_ids)
    items: list[HotLeagueItem] = []
    for name, league_id in settings.LEAGUE_IDS.items():
        lid = int(league_id)
        country = settings.LEAGUE_COUNTRIES.get(lid)
        items.append(
            HotLeagueItem(
                league_id=lid,
                league_name=league_name_zh(
                    name, league_id=lid, country=country, settings=settings
                ),
                country=country,
                selected=lid in selected,
            )
        )
    return HotLeaguesSetting(
        league_ids=league_ids,
        default_league_ids=default_hot_league_ids(),
        source=source,
        leagues=items,
    )


@router.get("/settings/hot-leagues", response_model=HotLeaguesSetting)
async def get_hot_leagues_setting(
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> HotLeaguesSetting:
    league_ids, source = await get_hot_league_ids(db)
    return _hot_leagues_payload(league_ids, source)


@router.patch("/settings/hot-leagues", response_model=HotLeaguesSetting)
async def patch_hot_leagues_setting(
    body: HotLeaguesUpdate,
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> HotLeaguesSetting:
    league_ids = await set_hot_league_ids(db, body.league_ids)
    return _hot_leagues_payload(league_ids, "db")


def _api_sports_key_payload(
    blob: str | None,
) -> ApiSportsKeySetting:
    from app.services.api_key_pool import (
        mask_api_sports_keys_blob,
        parse_api_sports_keys,
    )

    return ApiSportsKeySetting(
        key_count=len(parse_api_sports_keys(blob or "")),
        masked_keys=mask_api_sports_keys_blob(blob),
    )


@router.get("/settings/api-sports-key", response_model=ApiSportsKeySetting)
async def get_api_sports_key_setting(
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ApiSportsKeySetting:
    blob = await get_api_sports_keys_setting(db)
    return _api_sports_key_payload(blob)


@router.put("/settings/api-sports-key", response_model=ApiSportsKeySetting)
async def put_api_sports_key_setting(
    body: ApiSportsKeyUpdate,
    admin: AdminUser,
    db: AsyncSession = Depends(get_db),
) -> ApiSportsKeySetting:
    """Save comma-separated official keys to ``app_settings``.

    Empty ``keys`` removes all configured official keys. Requires the logged-in
    admin password.
    """
    if not auth_service.verify_password(body.password, admin.password_hash):
        raise HTTPException(status_code=403, detail="管理员密码不正确")

    blob = await set_api_sports_keys_setting(db, body.keys)
    return _api_sports_key_payload(blob)


@router.get(
    "/reset-match-history",
    response_model=ResetMatchHistoryResponse,
)
async def preview_reset_match_history(
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ResetMatchHistoryResponse:
    """Preview how many match/ML rows would be wiped (no password, no delete)."""
    report = await reset_match_history(db, apply=False)
    return _reset_history_response(report)


@router.post(
    "/reset-match-history",
    response_model=ResetMatchHistoryResponse,
)
async def post_reset_match_history(
    body: ResetMatchHistoryRequest,
    admin: AdminUser,
    db: AsyncSession = Depends(get_db),
) -> ResetMatchHistoryResponse:
    """Wipe match history after verifying the logged-in admin password.

    Requires a logged-in ``is_admin`` session (Admin Key alone is not enough).
    ``apply=false`` counts only; ``apply=true`` deletes.
    """
    if not auth_service.verify_password(body.password, admin.password_hash):
        raise HTTPException(status_code=403, detail="管理员密码不正确")

    report = await reset_match_history(db, apply=bool(body.apply))
    return _reset_history_response(report)
