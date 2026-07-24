from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.services.league_names import league_name_zh

router = APIRouter(prefix="/leagues", tags=["leagues"])


@router.get("/catalog", response_model=LeagueCatalogResponse)
async def get_league_catalog() -> LeagueCatalogResponse:
    """Configured leagues only. Use ``/leagues/filter-options`` for sidebar filters."""
    settings = get_settings()
    items: list[LeagueCatalogItemResponse] = []
    for name, league_id in settings.LEAGUE_IDS.items():
        items.append(
            LeagueCatalogItemResponse(
                league_id=league_id,
                league_name=name,
                country=settings.LEAGUE_COUNTRIES.get(league_id),
                season=settings.configured_season(league_id),
            )
        )
    return LeagueCatalogResponse(leagues=items)


@router.get("/filter-options", response_model=LeagueFilterOptionsResponse)
async def get_league_filter_options(
    date_str: str | None = Query(
        default=None,
        alias="date",
        description="日历日 YYYY-MM-DD，默认今天（筛选先按「今天」匹配）",
    ),
    db: AsyncSession = Depends(get_db),
) -> LeagueFilterOptionsResponse:
    """Home filter options from local unfinished fixtures (odds may open later)."""
    settings = get_settings()
    if date_str:
        try:
            day = date.fromisoformat(date_str)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD") from exc
    else:
        day = date.today()

    configured_ids = set(settings.LEAGUE_IDS.values())

    # Keep schedule-visible even before bookmakers open 1X2 — pruning only
    # applies after a fixture is finished and still has no odds/recommendation.
    local_counts: dict[int, int] = {}
    local_stmt = (
        select(Fixture.league_id, func.count())
        .where(
            func.date(Fixture.date) == day,
            Fixture.status.in_(["pending", "live", "postponed"]),
        )
        .group_by(Fixture.league_id)
    )
    for lid, cnt in (await db.execute(local_stmt)).all():
        local_counts[int(lid)] = int(cnt)

    # A date filter should only contain leagues that actually have local
    # fixtures on that date. Catalog membership controls grouping/defaults,
    # not whether a zero-match option is displayed.
    playing_ids = set(local_counts)

    def _country(league_id: int) -> str | None:
        if league_id in settings.LEAGUE_COUNTRIES:
            return settings.LEAGUE_COUNTRIES[league_id]
        return settings.REFERENCE_LEAGUE_COUNTRIES.get(league_id)

    def _name(league_id: int) -> str:
        raw = (
            settings.league_display_name(league_id)
            if league_id in configured_ids
            else settings.reference_display_name(league_id, "")
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
        tier = "configured" if league_id in configured_ids else "extra"
        option = LeagueFilterOptionResponse(
            league_id=league_id,
            league_name=_name(league_id),
            country=_country(league_id),
            fixtures_count=local_counts.get(league_id, 0),
            tier=tier,
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

    默认只返回窗口内仍有未完赛（pending/live/postponed）的联赛。
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
                Fixture.status.in_(["pending", "live", "postponed"]),
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

    response.headers["Cache-Control"] = "public, max-age=120"
    response.headers["X-Data-Source"] = "database"
    return LeaguesListResponse(
        date=base_date.isoformat(),
        days=window_days,
        leagues=leagues,
    )
