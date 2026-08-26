import asyncio
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps_auth import AdminUser, require_admin
from app.core.database import get_db
from app.models.league import League, LeagueCategory, LeagueCatalogTombstone
from app.services import auth as auth_service
from app.services.data_cleanup import delete_catalog_league, reset_match_history
from app.services.cache import get_cache_service
from app.services.fixtures_sync import official_sync_busy
from app.services.fetcher import FootballFetcher
from app.services.league_catalog import (
    DEFAULT_HOT_LEAGUE_IDS,
    catalog_leagues,
    league_categories,
    retarget_catalog_league_id,
)
from app.services.runtime_settings import (
    get_api_sports_keys_setting,
    get_last_sync_run,
    get_subscription_early_odds,
    get_subscription_enabled,
    set_api_sports_keys_setting,
    set_hot_league_ids,
    set_subscription_early_odds,
    set_subscription_enabled,
)
from app.tasks.scheduler import (
    PREMATCH_MISSING_ODDS_TASK,
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
            "prematch_missing_odds_sync / clean_old_data / train_model / "
            "daily_auto_favorites"
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
    category_id: int
    selected: bool
    protected: bool


class HotLeagueCategory(BaseModel):
    category_id: int
    category_name: str
    leagues: list[HotLeagueItem] = Field(default_factory=list)


class HotLeaguesSetting(BaseModel):
    league_ids: list[int]
    default_league_ids: list[int] = Field(description="内置默认勾选（五大联赛+欧战+中日韩）")
    source: str = Field(default="db")
    leagues: list[HotLeagueItem] = Field(default_factory=list)
    categories: list[HotLeagueCategory] = Field(default_factory=list)


class HotLeaguesUpdate(BaseModel):
    league_ids: list[int] = Field(default_factory=list)


class LeagueCategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=40)


class CatalogLeagueCreate(BaseModel):
    league_id: int = Field(..., gt=0)
    league_name: str = Field(..., min_length=1, max_length=80)
    country: str = Field(..., min_length=1, max_length=80)
    category_id: int = Field(..., gt=0)
    selected: bool = True


class OfficialLeagueLookup(BaseModel):
    league_id: int
    official_name: str
    country: str
    season: str
    league_type: str = ""
    suggested_name: str
    in_catalog: bool
    from_cache: bool


class CatalogLeagueUpdate(BaseModel):
    league_id: int | None = Field(default=None, gt=0)
    league_name: str | None = Field(default=None, min_length=1, max_length=80)
    country: str | None = Field(default=None, min_length=1, max_length=80)
    category_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def require_one_field(self) -> "CatalogLeagueUpdate":
        if (
            self.league_id is None
            and self.league_name is None
            and self.country is None
            and self.category_id is None
        ):
            raise ValueError("至少修改官方 ID、中文名、国家或分类中的一项")
        return self


class CatalogLeagueDeleteRequest(BaseModel):
    password: str = Field(..., min_length=1)
    apply: bool = True


class CatalogLeagueDeleteReport(BaseModel):
    apply: bool
    league_id: int
    league_name: str
    fixtures: int
    pre_match_data: int
    match_features: int
    auto_pick_snapshots: int
    favorite_fixtures: int
    league_standings: int
    api_snapshots: int
    orphan_teams: int


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
    "prematch_missing_odds": "比赛缺盘补齐",
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
        PREMATCH_MISSING_ODDS_TASK,
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
        for name in (
            "scheduled_fixtures_sync",
            RESULTS_SYNC_TASK,
            PREMATCH_MISSING_ODDS_TASK,
            body.name,
        )
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


async def _hot_leagues_payload(
    db: AsyncSession,
) -> HotLeaguesSetting:
    category_rows = await league_categories(db)
    league_rows = await catalog_leagues(db)
    grouped: dict[int, list[HotLeagueItem]] = {
        int(category.id): [] for category in category_rows
    }
    items: list[HotLeagueItem] = []
    selected_ids: list[int] = []
    for league in league_rows:
        item = HotLeagueItem(
            league_id=int(league.id),
            league_name=league.name,
            country=league.country if league.country != "Unknown" else None,
            category_id=int(league.category_id or 0),
            selected=bool(league.is_hot),
            protected=bool(league.is_protected),
        )
        items.append(item)
        grouped.setdefault(item.category_id, []).append(item)
        if item.selected:
            selected_ids.append(item.league_id)

    categories = [
        HotLeagueCategory(
            category_id=int(category.id),
            category_name=category.name,
            leagues=grouped.get(int(category.id), []),
        )
        for category in category_rows
    ]
    return HotLeaguesSetting(
        league_ids=selected_ids,
        default_league_ids=[
            league_id
            for league_id in DEFAULT_HOT_LEAGUE_IDS
            if any(item.league_id == league_id for item in items)
        ],
        source="db",
        leagues=items,
        categories=categories,
    )


async def _require_category(db: AsyncSession, category_id: int) -> LeagueCategory:
    category = await db.get(LeagueCategory, int(category_id))
    if category is None:
        raise HTTPException(status_code=404, detail="联赛分类不存在")
    return category


def _delete_league_report(report: Any) -> CatalogLeagueDeleteReport:
    return CatalogLeagueDeleteReport(**report.to_dict())


@router.post(
    "/settings/league-categories",
    response_model=HotLeaguesSetting,
)
async def create_league_category(
    body: LeagueCategoryCreate,
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> HotLeaguesSetting:
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="分类名称不能为空")
    exists = await db.scalar(
        select(LeagueCategory.id).where(func.lower(LeagueCategory.name) == name.lower())
    )
    if exists is not None:
        raise HTTPException(status_code=409, detail="分类名称已存在")
    max_sort = int(await db.scalar(select(func.max(LeagueCategory.sort_order))) or 0)
    db.add(LeagueCategory(name=name, sort_order=max_sort + 10))
    await db.commit()
    return await _hot_leagues_payload(db)


@router.delete(
    "/settings/league-categories/{category_id}",
    response_model=HotLeaguesSetting,
)
async def delete_league_category(
    category_id: int,
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> HotLeaguesSetting:
    category = await _require_category(db, category_id)
    child_count = int(
        await db.scalar(
            select(func.count())
            .select_from(League)
            .where(League.is_catalog.is_(True), League.category_id == category.id)
        )
        or 0
    )
    if child_count:
        raise HTTPException(status_code=409, detail="分类下仍有联赛，不能删除")
    await db.delete(category)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="分类下仍有联赛，不能删除") from exc
    return await _hot_leagues_payload(db)


@router.get(
    "/settings/leagues/{league_id}/lookup",
    response_model=OfficialLeagueLookup,
)
async def lookup_catalog_league(
    league_id: int,
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> OfficialLeagueLookup:
    if league_id < 1:
        raise HTTPException(status_code=422, detail="官方联赛 ID 必须为正整数")
    try:
        async with FootballFetcher(session=db) as fetcher:
            payload = await fetcher.lookup_official_league(league_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return OfficialLeagueLookup(**payload)


@router.post(
    "/settings/leagues",
    response_model=HotLeaguesSetting,
)
async def create_catalog_league(
    body: CatalogLeagueCreate,
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> HotLeaguesSetting:
    await _require_category(db, body.category_id)
    league_name = body.league_name.strip()
    country = body.country.strip()
    if not league_name or not country:
        raise HTTPException(status_code=422, detail="中文名和国家不能为空")
    league = await db.get(League, body.league_id)
    if league is not None and league.is_catalog:
        raise HTTPException(status_code=409, detail="该官方联赛 ID 已在目录中")
    if (
        league is not None
        and league.country
        and league.country != "Unknown"
        and league.country.casefold() != country.casefold()
    ):
        raise HTTPException(
            status_code=422,
            detail=f"国家与本地官方记录不一致，应为 {league.country}",
        )
    if league is not None and league.country and league.country != "Unknown":
        country = league.country
    if league is None:
        league = League(
            id=int(body.league_id),
            name=league_name,
            country=country,
            season=str(datetime.now().year),
        )
    else:
        league.name = league_name
        league.country = country
    league.category_id = int(body.category_id)
    league.is_catalog = True
    league.is_hot = body.selected
    league.is_protected = False
    tombstone = await db.get(LeagueCatalogTombstone, body.league_id)
    if tombstone is not None:
        await db.delete(tombstone)
    db.add(league)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="联赛 ID 或数据重复") from exc
    return await _hot_leagues_payload(db)


@router.patch(
    "/settings/leagues/{league_id}",
    response_model=HotLeaguesSetting,
)
async def update_catalog_league(
    league_id: int,
    body: CatalogLeagueUpdate,
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> HotLeaguesSetting:
    league = await db.get(League, int(league_id))
    if league is None or not league.is_catalog:
        raise HTTPException(status_code=404, detail="联赛不在可管理目录中")
    if body.category_id is not None:
        await _require_category(db, body.category_id)
        league.category_id = int(body.category_id)
    if body.league_name is not None:
        league_name = body.league_name.strip()
        if not league_name:
            raise HTTPException(status_code=422, detail="中文名不能为空")
        league.name = league_name
    if body.country is not None:
        country = body.country.strip()
        if not country:
            raise HTTPException(status_code=422, detail="国家不能为空")
        league.country = country
    old_id = int(league.id)
    if body.league_id is not None and int(body.league_id) != old_id:
        if official_sync_busy():
            raise HTTPException(status_code=409, detail="官方同步正在执行，暂不能修改联赛 ID")
        try:
            league = await retarget_catalog_league_id(db, league, int(body.league_id))
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except LookupError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="联赛 ID 或数据重复") from exc
    if int(league.id) != old_id:
        cache = get_cache_service()
        await cache.clear_pattern(f"*league:{old_id}:*")
    return await _hot_leagues_payload(db)


@router.get(
    "/settings/leagues/{league_id}/delete-preview",
    response_model=CatalogLeagueDeleteReport,
)
async def preview_catalog_league_delete(
    league_id: int,
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> CatalogLeagueDeleteReport:
    try:
        report = await delete_catalog_league(db, league_id, apply=False)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _delete_league_report(report)


@router.post(
    "/settings/leagues/{league_id}/delete",
    response_model=CatalogLeagueDeleteReport,
)
async def remove_catalog_league(
    league_id: int,
    body: CatalogLeagueDeleteRequest,
    admin: AdminUser,
    db: AsyncSession = Depends(get_db),
) -> CatalogLeagueDeleteReport:
    if not auth_service.verify_password(body.password, admin.password_hash):
        raise HTTPException(status_code=403, detail="管理员密码不正确")
    if official_sync_busy():
        raise HTTPException(status_code=409, detail="官方同步正在执行，暂不能删除联赛")
    try:
        report = await delete_catalog_league(db, league_id, apply=body.apply)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="联赛历史删除失败，请稍后重试") from exc
    return _delete_league_report(report)


@router.get("/settings/hot-leagues", response_model=HotLeaguesSetting)
async def get_hot_leagues_setting(
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> HotLeaguesSetting:
    return await _hot_leagues_payload(db)


@router.patch("/settings/hot-leagues", response_model=HotLeaguesSetting)
async def patch_hot_leagues_setting(
    body: HotLeaguesUpdate,
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> HotLeaguesSetting:
    await set_hot_league_ids(db, body.league_ids)
    return await _hot_leagues_payload(db)


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
