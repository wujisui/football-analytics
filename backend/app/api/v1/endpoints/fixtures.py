from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.database import get_db
from app.models.fixture import Fixture
from app.models.pre_match_data import PreMatchData
from app.schemas.response import (
    AdjustPredictionRequest,
    AnalysisResponse,
    FixtureOddsSnippetResponse,
    FixtureResponse,
    OpinionFactorResponse,
    OpinionFactorsResponse,
    PredictionSnapshotResponse,
    ProbabilitiesResponse,
    TodayFixturesResponse,
    analysis_to_response,
)
from app.services.analyzer import (
    DEFAULT_PROB,
    AnalyzerService,
    get_recommendation,
)
from app.services.prediction import (
    OPINION_FACTORS,
    adjust_probabilities_with_factors,
    build_prediction_snapshot,
    derive_prediction_leans,
)
from app.services.prematch_package import loads_json, rehydrate_odds_markets

router = APIRouter(prefix="/fixtures", tags=["fixtures"])


def _set_response_headers(response: Response, data_source: str, max_age: int = 120) -> None:
    response.headers["Cache-Control"] = f"public, max-age={max_age}"
    response.headers["X-Data-Source"] = data_source


def _league_name(fixture: Fixture) -> str:
    settings = get_settings()
    fallback = fixture.league.name if fixture.league else ""
    return settings.league_display_name(fixture.league_id, fallback)


def _list_analysis_from_fixture(
    fixture: Fixture,
    stored: PreMatchData | None,
) -> AnalysisResponse:
    """Build list-row analysis without Redis/API — pure in-memory from ORM rows."""
    home_name = fixture.home_team.name if fixture.home_team else f"Team {fixture.home_team_id}"
    away_name = fixture.away_team.name if fixture.away_team else f"Team {fixture.away_team_id}"
    league_name = _league_name(fixture)

    odds: dict | None = None
    if stored is not None and None not in (
        stored.home_win_prob,
        stored.draw_prob,
        stored.away_win_prob,
    ):
        probs = {
            "home": stored.home_win_prob,
            "draw": stored.draw_prob,
            "away": stored.away_win_prob,
        }
        confidence = "中"
        analyzed_at = stored.updated_at
        if analyzed_at.tzinfo is None:
            analyzed_at = analyzed_at.replace(tzinfo=timezone.utc)
        odds = rehydrate_odds_markets(loads_json(stored.odds_json, {"available": False}))
    else:
        probs = {"home": DEFAULT_PROB, "draw": DEFAULT_PROB, "away": DEFAULT_PROB}
        confidence = "低"
        analyzed_at = datetime.now(timezone.utc)

    leans = derive_prediction_leans(probs, odds if isinstance(odds, dict) else None)

    return AnalysisResponse(
        fixture_id=fixture.id,
        home_team_name=home_name,
        away_team_name=away_name,
        league_name=league_name,
        fixture_date=fixture.date,
        status=fixture.status,
        probabilities=ProbabilitiesResponse(
            home_win_prob=probs["home"],
            draw_prob=probs["draw"],
            away_win_prob=probs["away"],
        ),
        confidence=confidence,
        recommendation=get_recommendation(probs),
        goal_lean=leans["goal_lean"],
        both_score_lean=leans["both_score_lean"],
        score_hint=leans["score_hint"],
        handicap_lean=leans["handicap_lean"],
        data_source="database",
        analyzed_at=analyzed_at,
        cache_status="miss",
        package=None,
    )


def _list_extras_from_stored(stored: PreMatchData | None) -> tuple[
    int | None,
    int | None,
    FixtureOddsSnippetResponse | None,
]:
    """Ranks + odds snippet for list cards — local JSON only."""
    if stored is None:
        return None, None, None
    standings = loads_json(getattr(stored, "standings_json", None), {}) or {}
    home_rank = standings.get("home_rank")
    away_rank = standings.get("away_rank")
    odds = rehydrate_odds_markets(loads_json(stored.odds_json, {"available": False}))
    snippet = None
    if isinstance(odds, dict) and odds.get("available"):
        snippet = FixtureOddsSnippetResponse(
            available=True,
            match_winner=odds.get("match_winner"),
            asian_handicap=odds.get("asian_handicap"),
            goals_ou=odds.get("goals_ou"),
        )
    return home_rank, away_rank, snippet


@router.get("/today", response_model=TodayFixturesResponse)
async def get_today_fixtures(
    response: Response,
    league_id: int | None = Query(default=None, description="按联赛 ID 过滤"),
    date_str: str | None = Query(
        default=None,
        alias="date",
        description="起始日期 YYYY-MM-DD，默认今天",
    ),
    days: int | None = Query(
        default=None,
        ge=1,
        le=60,
        description="从起始日起未来几天（含当天），默认 1（仅当天）；联赛页可用 7",
    ),
    db: AsyncSession = Depends(get_db),
) -> TodayFixturesResponse:
    """赛程列表（只读本地库，不对每场打官方 API）。"""
    settings = get_settings()
    if date_str:
        try:
            base_date = date.fromisoformat(date_str)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD") from exc
    else:
        base_date = date.today()

    window_days = days if days is not None else 1
    end_date = base_date + timedelta(days=window_days - 1)
    start_dt = datetime.combine(base_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())

    stmt = (
        select(Fixture)
        .where(Fixture.date >= start_dt, Fixture.date <= end_dt)
        .options(
            selectinload(Fixture.home_team),
            selectinload(Fixture.away_team),
            selectinload(Fixture.league),
        )
        .order_by(Fixture.date)
    )
    if league_id is not None:
        stmt = stmt.where(Fixture.league_id == league_id)
    else:
        stmt = stmt.where(Fixture.league_id.in_(list(settings.LEAGUE_IDS.values())))

    result = await db.execute(stmt)
    fixtures = list(result.scalars().all())

    stored_by_id: dict[int, PreMatchData] = {}
    if fixtures:
        pre_stmt = select(PreMatchData).where(
            PreMatchData.fixture_id.in_([f.id for f in fixtures])
        )
        pre_rows = (await db.execute(pre_stmt)).scalars().all()
        stored_by_id = {row.fixture_id: row for row in pre_rows}

    fixture_responses: list[FixtureResponse] = []
    for fixture in fixtures:
        stored = stored_by_id.get(fixture.id)
        home_rank, away_rank, odds_snippet = _list_extras_from_stored(stored)
        fixture_responses.append(
            FixtureResponse(
                fixture_id=fixture.id,
                league_id=fixture.league_id,
                league_name=_league_name(fixture),
                home_team_id=fixture.home_team_id,
                away_team_id=fixture.away_team_id,
                home_team_name=fixture.home_team.name if fixture.home_team else "",
                away_team_name=fixture.away_team.name if fixture.away_team else "",
                fixture_date=fixture.date,
                status=fixture.status,
                analysis=_list_analysis_from_fixture(fixture, stored),
                home_rank=home_rank,
                away_rank=away_rank,
                odds_snippet=odds_snippet,
            )
        )

    _set_response_headers(response, "database")
    return TodayFixturesResponse(
        date=base_date.isoformat(),
        days=window_days,
        total=len(fixture_responses),
        fixtures=fixture_responses,
    )


@router.get("/opinion-factors", response_model=OpinionFactorsResponse)
async def list_opinion_factors() -> OpinionFactorsResponse:
    """Catalog of subjective factors users can toggle (not free-text NLP)."""
    return OpinionFactorsResponse(
        factors=[OpinionFactorResponse.model_validate(f) for f in OPINION_FACTORS]
    )


@router.post("/{fixture_id}/adjust", response_model=PredictionSnapshotResponse)
async def adjust_fixture_prediction(
    fixture_id: int,
    body: AdjustPredictionRequest,
    db: AsyncSession = Depends(get_db),
) -> PredictionSnapshotResponse:
    """Fuse selected opinion tags with stored algorithm probabilities."""
    stored = (
        await db.execute(select(PreMatchData).where(PreMatchData.fixture_id == fixture_id))
    ).scalar_one_or_none()
    if stored is None or None in (
        stored.home_win_prob,
        stored.draw_prob,
        stored.away_win_prob,
    ):
        raise HTTPException(
            status_code=404,
            detail="暂无算法预测，请先打开详情完成分析",
        )

    base = {
        "home": stored.home_win_prob,
        "draw": stored.draw_prob,
        "away": stored.away_win_prob,
    }
    odds = rehydrate_odds_markets(loads_json(stored.odds_json, {"available": False}))
    known = {f["id"] for f in OPINION_FACTORS}
    factors = [f for f in body.factors if f in known]
    adjusted = adjust_probabilities_with_factors(base, factors)
    snap = build_prediction_snapshot(adjusted, odds if isinstance(odds, dict) else None)
    return PredictionSnapshotResponse(**snap, factors=factors)


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
    except Exception as exc:
        # Avoid opaque 500s on first-hit enrichment races; client can retry.
        raise HTTPException(
            status_code=503,
            detail=f"分析暂时失败，请重试：{exc}",
        ) from exc

    _set_response_headers(response, analysis.data_source)
    package = analysis.package if isinstance(analysis.package, dict) else {}
    standings = package.get("standings") or {}
    odds = package.get("odds") or {}
    odds_snippet = None
    if odds.get("available"):
        odds_snippet = FixtureOddsSnippetResponse(
            available=True,
            match_winner=odds.get("match_winner"),
            asian_handicap=odds.get("asian_handicap"),
            goals_ou=odds.get("goals_ou"),
        )
    return FixtureResponse(
        fixture_id=fixture.id,
        league_id=fixture.league_id,
        league_name=_league_name(fixture),
        home_team_id=fixture.home_team_id,
        away_team_id=fixture.away_team_id,
        home_team_name=fixture.home_team.name if fixture.home_team else "",
        away_team_name=fixture.away_team.name if fixture.away_team else "",
        fixture_date=fixture.date,
        status=fixture.status,
        analysis=analysis_to_response(analysis),
        home_rank=standings.get("home_rank"),
        away_rank=standings.get("away_rank"),
        odds_snippet=odds_snippet,
    )
