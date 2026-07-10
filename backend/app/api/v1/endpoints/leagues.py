from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models.fixture import Fixture
from app.models.league import League
from app.schemas.response import LeaguesListResponse, LeagueSummaryResponse

router = APIRouter(prefix="/leagues", tags=["leagues"])


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
    db: AsyncSession = Depends(get_db),
) -> LeaguesListResponse:
    """联赛列表。

    注意：本接口读本地库，不直接打官方 API。
    - `today_fixtures_count`：基准日当天场次
    - `upcoming_fixtures_count`：基准日起未来 N 天场次（含当天）
    若库中无数据，需先 `python manage.py fetch-leagues` / `fetch-today` / `fetch-upcoming`。
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
        upcoming_count = (await db.execute(upcoming_stmt)).scalar_one()

        country = None
        if league and league.country and league.country != "Unknown":
            country = league.country
        elif league_id in settings.LEAGUE_COUNTRIES:
            country = settings.LEAGUE_COUNTRIES[league_id]

        leagues.append(
            LeagueSummaryResponse(
                league_id=league_id,
                # Prefer configured 中文 display name over DB/API English name.
                league_name=league_name,
                country=country,
                today_fixtures_count=today_count,
                upcoming_fixtures_count=upcoming_count,
            )
        )

    response.headers["Cache-Control"] = "public, max-age=120"
    response.headers["X-Data-Source"] = "database"
    return LeaguesListResponse(
        date=base_date.isoformat(),
        days=window_days,
        leagues=leagues,
    )
