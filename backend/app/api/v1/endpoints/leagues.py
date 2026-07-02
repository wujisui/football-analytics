from datetime import date

from fastapi import APIRouter, Depends, Response
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
    db: AsyncSession = Depends(get_db),
) -> LeaguesListResponse:
    settings = get_settings()
    today = date.today()
    leagues: list[LeagueSummaryResponse] = []

    for league_name, league_id in settings.LEAGUE_IDS.items():
        league = await db.get(League, league_id)
        count_stmt = (
            select(func.count())
            .select_from(Fixture)
            .where(
                Fixture.league_id == league_id,
                func.date(Fixture.date) == today,
            )
        )
        count_result = await db.execute(count_stmt)
        today_count = count_result.scalar_one()

        leagues.append(
            LeagueSummaryResponse(
                league_id=league_id,
                league_name=league.name if league else league_name,
                country=league.country if league else None,
                today_fixtures_count=today_count,
            )
        )

    response.headers["Cache-Control"] = "public, max-age=300"
    response.headers["X-Data-Source"] = "database"
    return LeaguesListResponse(leagues=leagues)
