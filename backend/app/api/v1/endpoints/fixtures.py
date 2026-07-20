from datetime import date, datetime, timedelta, timezone
import asyncio
import logging

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
from app.services.league_names import league_name_zh
from app.services.team_names import team_name_zh

router = APIRouter(prefix="/fixtures", tags=["fixtures"])
logger = logging.getLogger(__name__)

_sync_lock = asyncio.Lock()
_odds_followup_lock = asyncio.Lock()


async def _sync_odds_and_results_followup(
    day_list: list[date],
    selected: list[int] | None,
    *,
    include_odds: bool,
    include_results: bool,
    odds_refresh_existing: bool = True,
    odds_budget: int = 40,
) -> None:
    """Run after fixtures are saved — keeps odds aligned with the same sync request."""
    if _odds_followup_lock.locked():
        logger.info("Odds/results follow-up already running; skip duplicate")
        return
    async with _odds_followup_lock:
        try:
            async with FootballFetcher() as fetcher:
                if include_odds:
                    try:
                        await fetcher.sync_odds_for_dates(
                            day_list,
                            refresh_existing=odds_refresh_existing,
                            league_ids=selected,
                            budget=odds_budget,
                        )
                    except Exception as exc:
                        logger.warning("include_odds batch failed: %s", exc)
                if include_results:
                    try:
                        await fetcher.capture_finished_results(lookback_days=2)
                    except Exception as exc:
                        logger.warning("include_results capture failed: %s", exc)
        except Exception as exc:
            logger.warning("sync follow-up failed: %s", exc, exc_info=True)


def _set_response_headers(response: Response, data_source: str, max_age: int = 120) -> None:
    response.headers["Cache-Control"] = f"public, max-age={max_age}"
    response.headers["X-Data-Source"] = data_source


def _set_no_cache_headers(response: Response, data_source: str) -> None:
    """Mutable list/detail payloads must not be cached by the browser."""
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Data-Source"] = data_source


def _league_name(fixture: Fixture) -> str:
    settings = get_settings()
    fallback = fixture.league.name if fixture.league else ""
    return league_name_zh(
        fallback,
        league_id=fixture.league_id,
        country=_league_country(fixture),
        settings=settings,
    )


def _league_country(fixture: Fixture) -> str | None:
    settings = get_settings()
    if fixture.league_id in settings.LEAGUE_COUNTRIES:
        return settings.LEAGUE_COUNTRIES[fixture.league_id]
    if fixture.league_id in settings.REFERENCE_LEAGUE_COUNTRIES:
        return settings.REFERENCE_LEAGUE_COUNTRIES[fixture.league_id]
    if fixture.league and fixture.league.country and fixture.league.country != "Unknown":
        return fixture.league.country
    return None


def _team_display_name(name: str | None, team_id: int, fallback: str = "") -> str:
    """Chinese when mapped; covers rows still stored in English before next sync."""
    return team_name_zh(name, team_id) or fallback or (name or f"Team {team_id}")


def _list_analysis_from_fixture(
    fixture: Fixture,
    stored: PreMatchData | None,
) -> AnalysisResponse:
    """Build list-row analysis without Redis/API — pure in-memory from ORM rows."""
    home_name = _team_display_name(
        fixture.home_team.name if fixture.home_team else None,
        fixture.home_team_id,
    )
    away_name = _team_display_name(
        fixture.away_team.name if fixture.away_team else None,
        fixture.away_team_id,
    )
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

    # Prefer frozen pre-kickoff snapshot so algorithm changes do not rewrite history.
    frozen_rec = (getattr(stored, "recommendation", None) or "").strip() if stored else ""
    if stored and frozen_rec and frozen_rec != "待分析":
        recommendation = frozen_rec
        goal_lean = getattr(stored, "goal_lean", None) or "大小球：待分析"
        both_score_lean = getattr(stored, "both_score_lean", None) or "双方进球：待分析"
        score_hint = getattr(stored, "score_hint", None) or "待分析"
        handicap_lean = getattr(stored, "handicap_lean", None) or "缺少盘口数据分析"
    else:
        leans = derive_prediction_leans(probs, odds if isinstance(odds, dict) else None)
        recommendation = get_recommendation(probs) if ready else "待分析"
        goal_lean = leans["goal_lean"] if ready else "大小球：待分析"
        both_score_lean = leans["both_score_lean"] if ready else "双方进球：待分析"
        score_hint = leans["score_hint"] if ready else "待分析"
        handicap_lean = leans["handicap_lean"]

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
        recommendation=recommendation,
        goal_lean=goal_lean,
        both_score_lean=both_score_lean,
        score_hint=score_hint,
        handicap_lean=handicap_lean,
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
    league_id: int | None = Query(default=None, description="按单个联赛 ID 过滤"),
    league_ids: list[int] | None = Query(
        default=None,
        description="按多个联赛 ID 过滤（首页勾选）；与 league_id 同时传时取交集",
    ),
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

    if league_ids is not None:
        allowed = {int(x) for x in league_ids}
        if not allowed:
            raise HTTPException(status_code=400, detail="league_ids 不能为空")
    else:
        allowed = None

    stmt = (
        select(Fixture)
        .where(
            Fixture.date >= start_dt,
            Fixture.date <= end_dt,
        )
        .options(
            selectinload(Fixture.home_team),
            selectinload(Fixture.away_team),
            selectinload(Fixture.league),
        )
        .order_by(Fixture.date)
    )
    if allowed is not None:
        stmt = stmt.where(Fixture.league_id.in_(list(allowed)))
    if league_id is not None:
        if allowed is not None and league_id not in allowed:
            stmt = stmt.where(Fixture.league_id.in_([-1]))
        else:
            stmt = stmt.where(Fixture.league_id == league_id)

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
                league_country=_league_country(fixture),
                home_team_id=fixture.home_team_id,
                away_team_id=fixture.away_team_id,
                home_team_name=_team_display_name(
                    fixture.home_team.name if fixture.home_team else None,
                    fixture.home_team_id,
                ),
                away_team_name=_team_display_name(
                    fixture.away_team.name if fixture.away_team else None,
                    fixture.away_team_id,
                ),
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

    _set_no_cache_headers(response, "database")
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
    # Optional league filter only when client passes league_id.
    if league_id is not None:
        stmt = stmt.where(Fixture.league_id == league_id)

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
                league_country=_league_country(fx),
                home_team_id=fx.home_team_id,
                away_team_id=fx.away_team_id,
                home_team_name=_team_display_name(
                    fx.home_team.name if fx.home_team else None,
                    fx.home_team_id,
                ),
                away_team_name=_team_display_name(
                    fx.away_team.name if fx.away_team else None,
                    fx.away_team_id,
                ),
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
    days: int = Query(
        default=0,
        ge=0,
        le=3650,
        description="0=全部本地已完场样本（历史总）；>0 为可选近 N 日窗口",
    ),
    end_date_str: str | None = Query(
        default=None,
        alias="end_date",
        description="序列截止日 YYYY-MM-DD；默认今天，且不晚于今天",
    ),
    league_id: int | None = Query(default=None, description="按联赛 ID 过滤"),
    db: AsyncSession = Depends(get_db),
) -> ResultsHistoryResponse:
    """历史预测准确率汇总 + 按日序列（供折线图）。只读本地库。"""
    if league_id is not None:
        league_ids: list[int] = [league_id]
    else:
        league_ids = []
    today = date.today()
    end_day = today
    if end_date_str:
        try:
            parsed = date.fromisoformat(end_date_str)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="end_date 格式应为 YYYY-MM-DD") from exc
        if parsed > today:
            raise HTTPException(status_code=422, detail="end_date 不能晚于今天")
        end_day = parsed
    payload = await build_history_accuracy(
        db, days=days, league_ids=league_ids, end_day=end_day
    )
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
        description="拉取赛前赔率：缺盘补全；强制刷新时覆盖已有盘口并重算胜平负",
    ),
    odds_refresh_existing: bool = Query(
        default=True,
        description="False 时仅补缺失盘口（联赛筛选入库更快）；True 时强制刷新已有盘",
    ),
    odds_budget: int = Query(
        default=100,
        ge=1,
        le=200,
        description="单次同步最多拉取多少场 fixture 盘口",
    ),
    league_ids: list[int] | None = Query(
        default=None,
        description="仅同步勾选的联赛 ID；默认当日 API 返回的全部联赛",
    ),
) -> SyncFixturesResponse:
    """
    强制从官方拉取赛程并写入本地库（绕过 Redis/SQLite 日缓存）。

    选中日本地无数据时由前端自动调用；再读 `/fixtures/today`。
    赛程与盘口在同一请求内顺序完成（非后台补拉）。
    """
    settings = get_settings()

    async with _sync_lock:
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

            selected = league_ids
            if selected is not None and not selected:
                raise HTTPException(status_code=400, detail="league_ids 不能为空")

            async with FootballFetcher() as fetcher:
                saved = await fetcher.fetch_fixtures_window(
                    day_list[0],
                    day_list[-1],
                    force=True,
                    league_ids=selected,
                )
        except ApiKeyNotConfiguredError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("sync_fixtures failed: %s", exc, exc_info=True)
            raise HTTPException(status_code=503, detail=f"同步失败：{exc}") from exc

        if include_odds or include_results:
            await _sync_odds_and_results_followup(
                day_list,
                selected,
                include_odds=include_odds,
                include_results=include_results,
                odds_refresh_existing=odds_refresh_existing,
                odds_budget=odds_budget,
            )
        msg = "赛程已刷新"
        if include_odds:
            msg += "，盘口已同步" if odds_refresh_existing else "，缺失盘口已补全"
        return SyncFixturesResponse(
            status="ok",
            fixtures_saved=saved,
            days=window,
            date=start.isoformat(),
            message=msg,
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

    _set_no_cache_headers(response, analysis.data_source)
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
        league_country=_league_country(fixture),
        home_team_id=fixture.home_team_id,
        away_team_id=fixture.away_team_id,
        home_team_name=_team_display_name(
            fixture.home_team.name if fixture.home_team else None,
            fixture.home_team_id,
        ),
        away_team_name=_team_display_name(
            fixture.away_team.name if fixture.away_team else None,
            fixture.away_team_id,
        ),
        fixture_date=fixture.date,
        status=fixture.status,
        home_goals=fixture.home_goals,
        away_goals=fixture.away_goals,
        analysis=analysis_to_response(analysis),
        home_rank=standings.get("home_rank"),
        away_rank=standings.get("away_rank"),
        odds_snippet=odds_snippet,
    )
