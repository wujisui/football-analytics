from datetime import date, datetime, timedelta, timezone
import asyncio
import logging
import time

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
    ResultFixtureResponse,
    ResultsAccuracyResponse,
    ResultsHistoryResponse,
    ResultsResponse,
    SyncFixturesResponse,
    TodayFixturesResponse,
    analysis_to_response,
)
from app.services.analyzer import (
    DEFAULT_PROB,
    AnalyzerService,
)
from app.services.fetcher import ApiKeyNotConfiguredError, FootballFetcher
from app.services.prediction import (
    OPINION_FACTORS,
    adjust_probabilities_with_factors,
    build_prediction_snapshot,
    derive_prediction_leans,
    get_recommendation,
    implied_probs_from_odds,
    resolve_match_probabilities,
    summarize_accuracy,
)
from app.services.prematch_package import loads_json, rehydrate_odds_markets
from app.services.results_accuracy import (
    build_history_accuracy,
    evaluate_fixture_prediction,
    load_stored_by_fixture_ids,
)

router = APIRouter(prefix="/fixtures", tags=["fixtures"])
logger = logging.getLogger(__name__)

# Protect free-tier quota: force sync cannot spam official API.
_SYNC_COOLDOWN_SECONDS = 90
_last_sync_monotonic: float | None = None
_sync_lock = asyncio.Lock()


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
    raw_probs = {"home": DEFAULT_PROB, "draw": DEFAULT_PROB, "away": DEFAULT_PROB}
    confidence = "低"
    analyzed_at = datetime.now(timezone.utc)

    if stored is not None:
        odds = rehydrate_odds_markets(loads_json(stored.odds_json, {"available": False}))
        if None not in (
            stored.home_win_prob,
            stored.draw_prob,
            stored.away_win_prob,
        ):
            raw_probs = {
                "home": stored.home_win_prob,
                "draw": stored.draw_prob,
                "away": stored.away_win_prob,
            }
            confidence = "中"
        analyzed_at = stored.updated_at
        if analyzed_at.tzinfo is None:
            analyzed_at = analyzed_at.replace(tzinfo=timezone.utc)

    # Local only: if form model never ran, use odds-implied 1X2 when board exists.
    probs = resolve_match_probabilities(
        raw_probs, odds if isinstance(odds, dict) else None
    )
    from app.services.prediction import is_flat_prior

    ready = not is_flat_prior(probs)
    if odds and isinstance(odds, dict) and odds.get("available") and ready:
        confidence = "中" if confidence == "低" else confidence

    leans = derive_prediction_leans(probs, odds if isinstance(odds, dict) else None)

    return AnalysisResponse(
        fixture_id=fixture.id,
        home_team_name=home_name,
        away_team_name=away_name,
        league_name=league_name,
        fixture_date=fixture.date,
        status=fixture.status,
        probabilities=ProbabilitiesResponse(
            available=ready,
            home_win_prob=probs["home"] if ready else None,
            draw_prob=probs["draw"] if ready else None,
            away_win_prob=probs["away"] if ready else None,
        ),
        confidence=confidence,
        recommendation=get_recommendation(probs) if ready else "待分析",
        goal_lean=leans["goal_lean"] if ready else "大小球：待分析",
        both_score_lean=leans["both_score_lean"] if ready else "双方进球：待分析",
        score_hint=leans["score_hint"] if ready else "待分析",
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
                home_goals=fixture.home_goals,
                away_goals=fixture.away_goals,
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


@router.get("/results", response_model=ResultsResponse)
async def get_fixture_results(
    response: Response,
    date_str: str = Query(
        ...,
        alias="date",
        description="查询日期 YYYY-MM-DD（按开赛日）",
    ),
    league_id: int | None = Query(default=None, description="按联赛 ID 过滤"),
    db: AsyncSession = Depends(get_db),
) -> ResultsResponse:
    """按日期查看本地已落库赛果，并对照赛前预测计算命中（只读本地）。"""
    settings = get_settings()
    try:
        base_date = date.fromisoformat(date_str)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD") from exc

    start_dt = datetime.combine(base_date, datetime.min.time())
    end_dt = datetime.combine(base_date, datetime.max.time())

    stmt = (
        select(Fixture)
        .where(
            Fixture.date >= start_dt,
            Fixture.date <= end_dt,
            Fixture.status.in_(["finished", "cancelled", "postponed"]),
        )
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
    stored_by_id = await load_stored_by_fixture_ids(db, [f.id for f in fixtures])

    items: list[ResultFixtureResponse] = []
    accuracy_rows: list[dict] = []
    for fx in fixtures:
        evaluated = evaluate_fixture_prediction(fx, stored_by_id.get(fx.id))
        accuracy_rows.append(
            {
                "has_prediction": evaluated["has_prediction"],
                "evaluable": evaluated["evaluable"],
                "result_hit": evaluated["result_hit"],
                "score_hit": evaluated["score_hit"],
                "ou_hit": evaluated["ou_hit"],
                "btts_hit": evaluated["btts_hit"],
            }
        )
        items.append(
            ResultFixtureResponse(
                fixture_id=fx.id,
                league_id=fx.league_id,
                league_name=_league_name(fx),
                home_team_id=fx.home_team_id,
                away_team_id=fx.away_team_id,
                home_team_name=fx.home_team.name if fx.home_team else "",
                away_team_name=fx.away_team.name if fx.away_team else "",
                fixture_date=fx.date,
                status=fx.status,
                status_short=getattr(fx, "status_short", None),
                home_goals=fx.home_goals,
                away_goals=fx.away_goals,
                et_home_goals=getattr(fx, "et_home_goals", None),
                et_away_goals=getattr(fx, "et_away_goals", None),
                pen_home=getattr(fx, "pen_home", None),
                pen_away=getattr(fx, "pen_away", None),
                has_prediction=evaluated["has_prediction"],
                recommendation=evaluated["recommendation"],
                score_hint=evaluated["score_hint"],
                goal_lean=evaluated["goal_lean"],
                both_score_lean=evaluated["both_score_lean"],
                result_hit=evaluated["result_hit"],
                score_hit=evaluated["score_hit"],
                ou_hit=evaluated["ou_hit"],
                btts_hit=evaluated["btts_hit"],
            )
        )

    summary = summarize_accuracy(accuracy_rows)
    _set_response_headers(response, "database", max_age=60)
    return ResultsResponse(
        date=base_date.isoformat(),
        total=len(items),
        fixtures=items,
        accuracy=ResultsAccuracyResponse.model_validate(summary),
    )


@router.get("/results/history", response_model=ResultsHistoryResponse)
async def get_results_accuracy_history(
    response: Response,
    days: int = Query(default=30, ge=7, le=90, description="统计窗口天数（截至昨天）"),
    league_id: int | None = Query(default=None, description="按联赛 ID 过滤"),
    db: AsyncSession = Depends(get_db),
) -> ResultsHistoryResponse:
    """历史预测准确率汇总 + 按日序列（供折线图）。只读本地库。"""
    settings = get_settings()
    league_ids = (
        [league_id] if league_id is not None else list(settings.LEAGUE_IDS.values())
    )
    payload = await build_history_accuracy(db, days=days, league_ids=league_ids)
    _set_response_headers(response, "database", max_age=120)
    return ResultsHistoryResponse.model_validate(payload)


@router.post("/sync", response_model=SyncFixturesResponse)
async def sync_fixtures(
    days: int | None = Query(
        default=None,
        ge=1,
        le=14,
        description="同步窗口天数；与 date 组合时表示从 date 起共 N 天",
    ),
    date_str: str | None = Query(
        default=None,
        alias="date",
        description="同步起始日 YYYY-MM-DD；默认今天",
    ),
    include_results: bool = Query(
        default=True,
        description="同步时顺带回写近几日已结束比赛比分",
    ),
    include_odds: bool = Query(
        default=True,
        description="按日批量拉取赛前赔率写入本地（首页可直接展示盘口）",
    ),
) -> SyncFixturesResponse:
    """
    强制从官方拉取赛程并写入本地库（绕过 Redis/SQLite 日缓存）。

    首页「刷新」应调用本接口，再读 `/fixtures/today`。
    赔率用 ``/odds?date=`` 按日批量拉取，避免一场一场打接口。
    """
    global _last_sync_monotonic
    settings = get_settings()

    async with _sync_lock:
        now = time.monotonic()
        if _last_sync_monotonic is not None:
            elapsed = now - _last_sync_monotonic
            if elapsed < _SYNC_COOLDOWN_SECONDS:
                retry = int(_SYNC_COOLDOWN_SECONDS - elapsed)
                return SyncFixturesResponse(
                    status="cooldown",
                    fixtures_saved=0,
                    days=days or 1,
                    date=date_str,
                    message=f"同步过于频繁，请 {retry} 秒后再试（保护 API 配额）",
                    retry_after_seconds=retry,
                )

        try:
            if date_str:
                try:
                    start = date.fromisoformat(date_str)
                except ValueError as exc:
                    raise HTTPException(
                        status_code=400, detail="date must be YYYY-MM-DD"
                    ) from exc
            else:
                start = date.today()
            window = days if days is not None else min(settings.FIXTURES_LOOKAHEAD_DAYS, 7)
            window = max(1, min(window, 14))
            day_list = [start + timedelta(days=i) for i in range(window)]

            async with FootballFetcher() as fetcher:
                saved = 0
                for day in day_list:
                    saved += await fetcher.fetch_fixtures_for_date(day, force=True)

                if include_odds:
                    try:
                        # Let rate-limit window cool after fixture day fetches.
                        await asyncio.sleep(3.0)
                        await fetcher.sync_odds_for_dates(day_list)
                    except Exception as exc:
                        logger.warning("include_odds batch failed: %s", exc)

                if include_results:
                    try:
                        await fetcher.capture_finished_results(lookback_days=2)
                    except Exception as exc:
                        logger.warning("include_results capture failed: %s", exc)
        except ApiKeyNotConfiguredError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("sync_fixtures failed: %s", exc, exc_info=True)
            raise HTTPException(status_code=503, detail=f"同步失败：{exc}") from exc

        _last_sync_monotonic = time.monotonic()
        return SyncFixturesResponse(
            status="ok",
            fixtures_saved=saved,
            days=window,
            date=start.isoformat(),
            message="刷新成功",
            retry_after_seconds=_SYNC_COOLDOWN_SECONDS,
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
        home_goals=fixture.home_goals,
        away_goals=fixture.away_goals,
        analysis=analysis_to_response(analysis),
        home_rank=standings.get("home_rank"),
        away_rank=standings.get("away_rank"),
        odds_snippet=odds_snippet,
    )
