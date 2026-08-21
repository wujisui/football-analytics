from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.http_cache import set_no_store_headers
from app.core.config import get_settings
from app.core.database import get_db
from app.models.fixture import Fixture
from app.models.league import League
from app.schemas.response import (
    LeagueCatalogItemResponse,
    LeagueCatalogResponse,
    LeagueFilterOptionResponse,
    LeagueFilterOptionsResponse,
    LeaguesListResponse,
    LeagueSummaryResponse,
)
from app.services.competition_scope import allowed_competition_ids
from app.services.league_names import league_name_zh
from app.services.results_capture import prematch_list_clause, results_list_clause
from app.services.runtime_settings import get_hot_league_ids

router = APIRouter(prefix="/leagues", tags=["leagues"])


@router.get("/catalog", response_model=LeagueCatalogResponse)
async def get_league_catalog(
    db: AsyncSession = Depends(get_db),
) -> LeagueCatalogResponse:
    """Configured leagues only. Use ``/leagues/filter-options`` for sidebar filters."""
    settings = get_settings()
    hot_ids, _ = await get_hot_league_ids(db)
    hot = set(hot_ids)
    items: list[LeagueCatalogItemResponse] = []
    for name, league_id in settings.LEAGUE_IDS.items():
        lid = int(league_id)
        items.append(
            LeagueCatalogItemResponse(
                league_id=lid,
                league_name=league_name_zh(
                    name,
                    league_id=lid,
                    country=settings.LEAGUE_COUNTRIES.get(lid),
                    settings=settings,
                ),
                country=settings.LEAGUE_COUNTRIES.get(lid),
                season=settings.configured_season(lid),
                hot=lid in hot,
            )
        )
    return LeagueCatalogResponse(leagues=items)


@router.get("/filter-options", response_model=LeagueFilterOptionsResponse)
async def get_league_filter_options(
    date_str: str | None = Query(
        default=None,
        alias="date",
        description="比赛日 YYYY-MM-DD；prematch 默认当前最早的当地比赛日",
    ),
    scope: str = Query(
        default="prematch",
        description="prematch=未开赛；results=完场日（含进行中/取消；延期仅保留原定开赛未超 1 天）",
    ),
    days: int | None = Query(
        default=None,
        ge=1,
        le=60,
        description="统计连续比赛日数量；prematch 默认 2，results 默认 1",
    ),
    db: AsyncSession = Depends(get_db),
) -> LeagueFilterOptionsResponse:
    """Day league checklist — counts only, no fixture payloads."""
    settings = get_settings()
    scope_key = (scope or "prematch").strip().lower()
    if scope_key not in {"prematch", "results"}:
        raise HTTPException(status_code=400, detail="scope must be prematch or results")
    catalog_ids = set(settings.LEAGUE_IDS.values())
    hot_ids = set((await get_hot_league_ids(db))[0])
    competition_ids = allowed_competition_ids(settings)

    if date_str:
        try:
            day = date.fromisoformat(date_str)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD") from exc
    elif scope_key == "prematch":
        match_day_expr = func.coalesce(Fixture.match_day, func.date(Fixture.date))
        earliest = (
            await db.execute(
                select(func.min(match_day_expr)).where(
                    prematch_list_clause(),
                    *([Fixture.league_id.in_(hot_ids)] if hot_ids else []),
                )
            )
        ).scalar_one_or_none()
        if earliest is None:
            earliest = (
                await db.execute(
                    select(func.min(match_day_expr)).where(prematch_list_clause())
                )
            ).scalar_one_or_none()
        day = date.fromisoformat(earliest) if earliest else date.today()
    else:
        day = date.today()

    window_days = days if days is not None else (2 if scope_key == "prematch" else 1)
    end_day = day + timedelta(days=window_days)

    # Keep schedule-visible even before bookmakers open 1X2 — pruning only
    # applies after a fixture is finished and still has no odds/recommendation.
    # 已开赛（含本地状态还没跟上的 pending）归赛果，不再计入未开赛筛选。
    status_clause = (
        results_list_clause() if scope_key == "results" else prematch_list_clause()
    )

    local_counts: dict[int, int] = {}
    day_expr = (
        func.coalesce(Fixture.match_day, func.date(Fixture.date))
        if scope_key == "prematch"
        else func.date(Fixture.date)
    )
    local_stmt = (
        select(Fixture.league_id, func.count())
        .where(
            day_expr >= day.isoformat(),
            day_expr < end_day.isoformat(),
            status_clause,
            Fixture.league_id.in_(competition_ids),
        )
        .group_by(Fixture.league_id)
    )
    for lid, cnt in (await db.execute(local_stmt)).all():
        local_counts[int(lid)] = int(cnt)

    # A date filter should only contain leagues that actually have local
    # fixtures on that date. Catalog membership controls grouping/defaults,
    # not whether a zero-match option is displayed.
    playing_ids = set(local_counts)

    league_rows: dict[int, League] = {}
    if playing_ids:
        rows = (
            await db.execute(select(League).where(League.id.in_(list(playing_ids))))
        ).scalars().all()
        league_rows = {int(row.id): row for row in rows}

    def _country(league_id: int) -> str | None:
        if league_id in settings.LEAGUE_COUNTRIES:
            return settings.LEAGUE_COUNTRIES[league_id]
        row = league_rows.get(league_id)
        if row and row.country and row.country != "Unknown":
            return row.country
        return None

    def _name(league_id: int) -> str:
        row = league_rows.get(league_id)
        raw = (
            settings.league_display_name(league_id)
            if league_id in catalog_ids
            else (row.name if row else "")
        )
        return league_name_zh(
            raw,
            league_id=league_id,
            country=_country(league_id),
            settings=settings,
        )

    configured: list[LeagueFilterOptionResponse] = []
    extra: list[LeagueFilterOptionResponse] = []
    for league_id in sorted(playing_ids):
        tier = "configured" if league_id in hot_ids else "extra"
        option = LeagueFilterOptionResponse(
            league_id=league_id,
            league_name=_name(league_id),
            country=_country(league_id),
            fixtures_count=local_counts.get(league_id, 0),
            tier=tier,
            # Lists default to primary (configured) leagues only.
            default_checked=tier == "configured",
        )
        (configured if tier == "configured" else extra).append(option)

    return LeagueFilterOptionsResponse(
        date=day.isoformat(),
        configured=configured,
        extra=extra,
    )


@router.get("", response_model=LeaguesListResponse)
async def list_leagues(
    response: Response,
    date_str: str | None = Query(
        default=None,
        alias="date",
        description="基准日期 YYYY-MM-DD，默认今天。不传则按今天统计。",
    ),
    days: int | None = Query(
        default=None,
        ge=1,
        le=60,
        description="从基准日起未来几天（含当天）统计 upcoming 场次，默认 FIXTURES_LOOKAHEAD_DAYS",
    ),
    only_with_fixtures: bool = Query(
        default=True,
        description="仅返回窗口内有赛程的联赛（首页筛选用）；完整目录见 /leagues/catalog",
    ),
    db: AsyncSession = Depends(get_db),
) -> LeaguesListResponse:
    """联赛列表（本地库统计）。

    默认只返回窗口内仍有未开赛（pending/postponed）的联赛。
    完整可配置目录请用 ``GET /leagues/catalog``。
    """
    settings = get_settings()
    if date_str:
        try:
            base_date = date.fromisoformat(date_str)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD") from exc
    else:
        base_date = date.today()

    window_days = days if days is not None else settings.FIXTURES_LOOKAHEAD_DAYS
    end_date = base_date + timedelta(days=window_days - 1)
    start_dt = datetime.combine(base_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())

    leagues: list[LeagueSummaryResponse] = []

    for league_name, league_id in settings.LEAGUE_IDS.items():
        league = await db.get(League, league_id)

        today_stmt = (
            select(func.count())
            .select_from(Fixture)
            .where(
                Fixture.league_id == league_id,
                func.date(Fixture.date) == base_date,
            )
        )
        today_count = (await db.execute(today_stmt)).scalar_one()

        upcoming_stmt = (
            select(func.count())
            .select_from(Fixture)
            .where(
                Fixture.league_id == league_id,
                Fixture.date >= start_dt,
                Fixture.date <= end_dt,
            )
        )
        upcoming_all = (await db.execute(upcoming_stmt)).scalar_one()

        active_stmt = (
            select(func.count())
            .select_from(Fixture)
            .where(
                Fixture.league_id == league_id,
                Fixture.date >= start_dt,
                Fixture.date <= end_dt,
                Fixture.status.in_(["pending", "postponed"]),
            )
        )
        active_count = (await db.execute(active_stmt)).scalar_one()

        if only_with_fixtures and active_count <= 0:
            continue

        country = None
        if league and league.country and league.country != "Unknown":
            country = league.country
        elif league_id in settings.LEAGUE_COUNTRIES:
            country = settings.LEAGUE_COUNTRIES[league_id]

        leagues.append(
            LeagueSummaryResponse(
                league_id=league_id,
                league_name=league_name,
                country=country,
                today_fixtures_count=today_count,
                upcoming_fixtures_count=(
                    active_count if only_with_fixtures else upcoming_all
                ),
            )
        )

    set_no_store_headers(response)
    return LeaguesListResponse(
        date=base_date.isoformat(),
        days=window_days,
        leagues=leagues,
    )
