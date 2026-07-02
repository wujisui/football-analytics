from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.database import get_db
from app.models.fixture import Fixture
from app.models.league import League
from app.schemas.response import (
    FixtureResponse,
    LeaguesListResponse,
    LeagueSummaryResponse,
    TodayFixturesResponse,
    analysis_to_response,
)
from app.services.analyzer import AnalyzerService

router = APIRouter(prefix="/fixtures", tags=["fixtures"])


def _set_response_headers(response: Response, data_source: str, max_age: int = 120) -> None:
    response.headers["Cache-Control"] = f"public, max-age={max_age}"
    response.headers["X-Data-Source"] = data_source


@router.get("/today", response_model=TodayFixturesResponse)
async def get_today_fixtures(
    response: Response,
    league_id: int | None = Query(default=None, description="按联赛 ID 过滤"),
    db: AsyncSession = Depends(get_db),
) -> TodayFixturesResponse:
    today = date.today()
    stmt = (
        select(Fixture)
        .where(func.date(Fixture.date) == today)
        .options(
            selectinload(Fixture.home_team),
            selectinload(Fixture.away_team),
            selectinload(Fixture.league),
        )
        .order_by(Fixture.date)
    )
    if league_id is not None:
        stmt = stmt.where(Fixture.league_id == league_id)

    result = await db.execute(stmt)
    fixtures = result.scalars().all()
    analyzer = AnalyzerService(db)

    fixture_responses: list[FixtureResponse] = []
    dominant_source = "database"

    for fixture in fixtures:
        try:
            analysis = await analyzer.analyze_fixture(fixture.id)
            if analysis.data_source == "api":
                dominant_source = "api"
            elif analysis.data_source == "cache" and dominant_source != "api":
                dominant_source = "cache"

            fixture_responses.append(
                FixtureResponse(
                    fixture_id=fixture.id,
                    league_id=fixture.league_id,
                    league_name=fixture.league.name if fixture.league else "",
                    home_team_id=fixture.home_team_id,
                    away_team_id=fixture.away_team_id,
                    home_team_name=fixture.home_team.name if fixture.home_team else "",
                    away_team_name=fixture.away_team.name if fixture.away_team else "",
                    fixture_date=fixture.date,
                    status=fixture.status,
                    analysis=analysis_to_response(analysis),
                )
            )
        except Exception:
            continue

    _set_response_headers(response, dominant_source)
    return TodayFixturesResponse(
        date=today.isoformat(),
        total=len(fixture_responses),
        fixtures=fixture_responses,
    )


@router.get("/{fixture_id}/analysis", response_model=FixtureResponse)
async def get_fixture_analysis(
    fixture_id: int,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> FixtureResponse:
    fixture_stmt = (
        select(Fixture)
        .where(Fixture.id == fixture_id)
        .options(
            selectinload(Fixture.home_team),
            selectinload(Fixture.away_team),
            selectinload(Fixture.league),
        )
    )
    fixture_result = await db.execute(fixture_stmt)
    fixture = fixture_result.scalar_one_or_none()
    if fixture is None:
        raise HTTPException(status_code=404, detail=f"Fixture {fixture_id} not found.")

    analyzer = AnalyzerService(db)
    try:
        analysis = await analyzer.analyze_fixture(fixture_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    _set_response_headers(response, analysis.data_source)
    return FixtureResponse(
        fixture_id=fixture.id,
        league_id=fixture.league_id,
        league_name=fixture.league.name if fixture.league else "",
        home_team_id=fixture.home_team_id,
        away_team_id=fixture.away_team_id,
        home_team_name=fixture.home_team.name if fixture.home_team else "",
        away_team_name=fixture.away_team.name if fixture.away_team else "",
        fixture_date=fixture.date,
        status=fixture.status,
        analysis=analysis_to_response(analysis),
    )
