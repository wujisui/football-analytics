from datetime import date, datetime, timedelta, timezone
import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps_auth import require_admin
from app.api.v1.http_cache import set_no_store_headers
from app.core.config import get_settings
from app.core.database import get_db
from app.models.fixture import Fixture
from app.models.pre_match_data import PreMatchData
from app.schemas.response import (
    AdjustPredictionRequest,
    AnalysisResponse,
    FixtureOddsSnippetResponse,
    FixtureResponse,
    FixtureScoreResponse,
    FixtureScoresResponse,
    OpinionFactorResponse,
    OpinionFactorsResponse,
    PredictionSnapshotResponse,
    ProbabilitiesResponse,
    ResultFixtureResponse,
    ResultsHistoryResponse,
    ResultsResponse,
    TodayFixturesResponse,
    analysis_to_response,
)
from app.services.analyzer import (
    DEFAULT_PROB,
    AnalyzerService,
)
from app.services.calendar_tz import utc_today
from app.services.fixtures_sync import official_sync_busy
from app.services.league_catalog import allowed_league_ids
from app.services.fetcher import FootballFetcher
from app.services.match_day import (
    current_prematch_match_day,
    fixture_match_day,
    fixture_match_day_expr,
)
from app.services.prediction import (
    OPINION_FACTORS,
    adjust_probabilities_with_factors,
    build_prediction_snapshot,
    derive_prediction_leans,
    implied_probs_from_odds,
    resolve_match_probabilities,
)
from app.services.prematch_package import loads_json, rehydrate_odds_markets
from app.services.results_accuracy import (
    build_history_accuracy,
    evaluate_fixture_prediction,
    load_auto_picks_by_fixture_ids,
    load_stored_by_fixture_ids,
)
from app.services.results_capture import (
    prematch_list_clause,
    results_list_clause,
    results_list_score,
    score_refresh_ttl,
)
from app.services.runtime_settings import (
    get_client_data_revision,
    touch_client_data_revision,
)
from app.services.league_names import league_name_zh
from app.services.league_standings import (
    fixture_standing_key,
    load_standings_maps,
    snippet_from_ranks,
)
from app.services.team_names import team_name_zh

router = APIRouter(prefix="/fixtures", tags=["fixtures"])
logger = logging.getLogger(__name__)


def _odds_refresh_allowed(
    fixture: Fixture,
    *,
    today_match_day: str | None,
) -> bool:
    """One boundary for UI and API: catalog 【比赛】 on the list's 今天."""
    return bool(
        today_match_day
        and fixture.league
        and fixture.league.is_catalog
        and fixture_match_day(fixture) == today_match_day
        and fixture.date > datetime.now(timezone.utc).replace(tzinfo=None)
    )


@router.get("/data-revision")
async def client_data_revision(
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Lightweight local token; checking it never calls the official API."""
    set_no_store_headers(response)
    return {"revision": await get_client_data_revision(db)}


@router.post("/{fixture_id}/odds/refresh")
async def refresh_fixture_odds(
    fixture_id: int,
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Admin-only pull: first board freezes opening; later pulls update current."""
    if official_sync_busy():
        raise HTTPException(
            status_code=409,
            detail="后台官方同步正在执行，本次盘口未更新，请稍后再试",
        )
    fixture = (
        await db.execute(
            select(Fixture)
            .where(Fixture.id == fixture_id)
            .options(selectinload(Fixture.league))
        )
    ).scalar_one_or_none()
    if fixture is None:
        raise HTTPException(status_code=404, detail="比赛不存在")
    today_match_day = await current_prematch_match_day(
        db,
        league_ids=await allowed_league_ids(db),
    )
    if not _odds_refresh_allowed(fixture, today_match_day=today_match_day):
        raise HTTPException(
            status_code=409,
            detail="仅当前比赛日仍在【比赛】中的目录联赛允许更新盘口",
        )
    async with FootballFetcher(session=db) as fetcher:
        updated = await fetcher.refresh_odds_for_fixture(fixture_id)
        remaining = fetcher.last_remaining_requests
    if updated:
        await touch_client_data_revision(db)
    return {
        "fixture_id": fixture_id,
        "updated": updated,
        "api_remaining": remaining,
    }


def _league_name(fixture: Fixture) -> str:
    if fixture.league and fixture.league.is_catalog:
        return fixture.league.name
    settings = get_settings()
    fallback = fixture.league.name if fixture.league else ""
    return league_name_zh(
        fallback,
        league_id=fixture.league_id,
        country=_league_country(fixture),
        settings=settings,
    )


def _league_country(fixture: Fixture) -> str | None:
    if fixture.league and fixture.league.country and fixture.league.country != "Unknown":
        return fixture.league.country
    settings = get_settings()
    if fixture.league_id in settings.LEAGUE_COUNTRIES:
        return settings.LEAGUE_COUNTRIES[fixture.league_id]
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
        from app.services.odds_snapshot import normalize_odds_snapshot

        odds = rehydrate_odds_markets(
            normalize_odds_snapshot(
                loads_json(stored.odds_json, {"available": False}),
                match_start_time=fixture.date,
                fixture_id=fixture.id,
                stage="current",
            )
        )
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
    from app.services.prediction import has_1x2_market

    # 无赛前 1X2 盘口 → 概率不可用（与 prediction 闸门一致，不展示无依据数字）。
    ready = has_1x2_market(odds if isinstance(odds, dict) else None)
    if ready:
        confidence = "中" if confidence == "低" else confidence

    # Prefer frozen pre-kickoff snapshot so algorithm changes do not rewrite history.
    frozen_rec = (getattr(stored, "recommendation", None) or "").strip() if stored else ""
    if stored and frozen_rec and frozen_rec != "待分析":
        recommendation = frozen_rec
        from app.services.prediction import (
            canonical_btts_lean,
            canonical_goal_lean,
            canonical_recommendation,
            canonical_score_hint,
            resolve_handicap_bundle,
        )

        recommendation = canonical_recommendation(recommendation)
        goal_lean = canonical_goal_lean(
            getattr(stored, "goal_lean", None) or "大小：待分析"
        )
        both_score_lean = canonical_btts_lean(
            getattr(stored, "both_score_lean", None) or "双进:待分析"
        )
        score_hint = canonical_score_hint(
            getattr(stored, "score_hint", None) or "待分析"
        )

        handicap_lean, handicap_market_note = resolve_handicap_bundle(
            odds if isinstance(odds, dict) else None,
            recommendation,
            league_id=fixture.league_id,
            stored=getattr(stored, "handicap_lean", None),
            score_hint=score_hint,
            prefer_stored=True,
        )
    else:
        leans = derive_prediction_leans(
            probs,
            odds if isinstance(odds, dict) else None,
            league_id=fixture.league_id,
        )
        recommendation = leans["recommendation"]
        goal_lean = leans["goal_lean"]
        both_score_lean = leans["both_score_lean"]
        score_hint = leans["score_hint"]
        handicap_lean = leans["handicap_lean"]
        handicap_market_note = leans.get("handicap_market_note", "")

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
        handicap_market_note=handicap_market_note or "",
        data_source="database",
        analyzed_at=analyzed_at,
        cache_status="miss",
        package=None,
    )


def _odds_snippet_from_package(
    odds: dict[str, Any] | None,
) -> FixtureOddsSnippetResponse | None:
    """Single builder for list-card odds摘要.

    详情与列表都走这里：``captured_at`` 是前端区分初盘 / 即时盘的唯一依据，详情
    曾另建一份不带该字段的摘要，回列表合并时会把时间戳抹成空、两份盘口并成一份。
    """
    if not isinstance(odds, dict) or not odds.get("available"):
        return None
    return FixtureOddsSnippetResponse(
        available=True,
        match_winner=odds.get("match_winner"),
        asian_handicap=odds.get("asian_handicap"),
        goals_ou=odds.get("goals_ou"),
        both_teams_score=odds.get("both_teams_score"),
        captured_at=odds.get("captured_at"),
        scraped_at=odds.get("scraped_at") or odds.get("captured_at"),
        match_start_time=odds.get("match_start_time"),
        is_live=bool(odds.get("is_live")),
        valid=odds.get("valid") is not False,
    )


def _odds_snippet_from_stored(
    stored: PreMatchData | None,
    fixture: Fixture,
    *,
    opening: bool = False,
) -> FixtureOddsSnippetResponse | None:
    if stored is None:
        return None
    from app.services.odds_snapshot import normalize_odds_snapshot

    raw = stored.odds_opening_json if opening else stored.odds_json
    return _odds_snippet_from_package(
        rehydrate_odds_markets(
            normalize_odds_snapshot(
                loads_json(raw, {"available": False}),
                match_start_time=fixture.date,
                fixture_id=fixture.id,
                stage="opening" if opening else "current",
            )
        )
    )


def _ranks_from_maps(
    fixture: Fixture,
    standings_maps: dict[tuple[int, str], dict],
    stored: PreMatchData | None,
) -> tuple[int | None, int | None]:
    """Prefer shared league standings; fall back to per-fixture standings_json."""
    key = fixture_standing_key(fixture)
    if key is not None and key in standings_maps:
        snippet = snippet_from_ranks(
            standings_maps[key],
            fixture.home_team_id,
            fixture.away_team_id,
            league_id=fixture.league_id,
            league_name=fixture.league.name if fixture.league else None,
        )
        return snippet.get("home_rank"), snippet.get("away_rank")
    if stored is None:
        return None, None
    standings = loads_json(getattr(stored, "standings_json", None), {}) or {}
    return standings.get("home_rank"), standings.get("away_rank")


@router.get("/today", response_model=TodayFixturesResponse)
async def get_today_fixtures(
    response: Response,
    scope: Literal["schedule", "prematch"] = Query(
        default="schedule",
        description="schedule=指定日期全部赛程；prematch=仅服务器当前时刻尚未开赛",
    ),
    league_id: int | None = Query(default=None, description="按单个联赛 ID 过滤"),
    league_ids: list[int] | None = Query(
        default=None,
        description="按多个联赛 ID 过滤（首页勾选）；与 league_id 同时传时取交集",
    ),
    date_str: str | None = Query(
        default=None,
        alias="date",
        description="起始当地比赛日 YYYY-MM-DD；默认当前尚未开赛场次中最早的比赛日",
    ),
    days: int | None = Query(
        default=None,
        ge=1,
        le=60,
        description="从起始当地比赛日起连续几天（含当天），默认 1",
    ),
    db: AsyncSession = Depends(get_db),
) -> TodayFixturesResponse:
    """按后端已定稿的场地当地比赛日查询（只读本地库）。"""
    match_day_expr = fixture_match_day_expr()
    competition_ids = await allowed_league_ids(db)

    if league_ids is not None:
        allowed = {int(x) for x in league_ids}
        if not allowed:
            raise HTTPException(status_code=400, detail="league_ids 不能为空")
    else:
        allowed = None

    if date_str:
        try:
            base_date = date.fromisoformat(date_str)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD") from exc
    else:
        base_stmt = select(func.min(match_day_expr)).where(
            Fixture.league_id.in_(competition_ids)
        )
        if scope == "prematch":
            base_stmt = base_stmt.where(prematch_list_clause())
        if allowed is not None:
            base_stmt = base_stmt.where(Fixture.league_id.in_(list(allowed)))
        if league_id is not None:
            if allowed is not None and league_id not in allowed:
                base_stmt = base_stmt.where(Fixture.league_id.in_([-1]))
            else:
                base_stmt = base_stmt.where(Fixture.league_id == league_id)
        earliest = (await db.execute(base_stmt)).scalar_one_or_none()
        base_date = date.fromisoformat(earliest) if earliest else utc_today()

    window_days = days if days is not None else 1
    end_date = base_date + timedelta(days=window_days - 1)
    end_exclusive = end_date + timedelta(days=1)

    stmt = (
        select(Fixture)
        .where(
            match_day_expr >= base_date.isoformat(),
            match_day_expr < end_exclusive.isoformat(),
            Fixture.league_id.in_(competition_ids),
        )
        .options(
            selectinload(Fixture.home_team),
            selectinload(Fixture.away_team),
            selectinload(Fixture.league),
        )
        .order_by(Fixture.date)
    )
    if scope == "prematch":
        stmt = stmt.where(prematch_list_clause())
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

    standings_keys = {
        key
        for fixture in fixtures
        if (key := fixture_standing_key(fixture)) is not None
    }
    standings_maps = await load_standings_maps(db, standings_keys)

    today_match_day = await current_prematch_match_day(
        db,
        league_ids=competition_ids,
    )
    fixture_responses: list[FixtureResponse] = []
    for fixture in fixtures:
        stored = stored_by_id.get(fixture.id)
        home_rank, away_rank = _ranks_from_maps(fixture, standings_maps, stored)
        odds_snippet = _odds_snippet_from_stored(stored, fixture)
        odds_opening_snippet = _odds_snippet_from_stored(
            stored, fixture, opening=True
        )
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
                match_day=fixture_match_day(fixture),
                match_timezone=fixture.match_timezone or "UTC",
                match_day_source=fixture.match_day_source or "utc",
                match_day_offset=(
                    date.fromisoformat(fixture_match_day(fixture)) - base_date
                ).days,
                odds_refresh_allowed=_odds_refresh_allowed(
                    fixture, today_match_day=today_match_day
                ),
                status=fixture.status,
                home_goals=fixture.home_goals,
                away_goals=fixture.away_goals,
                analysis=_list_analysis_from_fixture(fixture, stored),
                home_rank=home_rank,
                away_rank=away_rank,
                odds_snippet=odds_snippet,
                odds_opening_snippet=odds_opening_snippet,
            )
        )

    set_no_store_headers(response)
    return TodayFixturesResponse(
        date=base_date.isoformat(),
        days=window_days,
        total=len(fixture_responses),
        fixtures=fixture_responses,
    )


@router.get("/scores", response_model=FixtureScoresResponse)
async def get_fixture_scores(
    response: Response,
    ids: list[int] = Query(
        ...,
        description="比赛 ID 列表（计算器保存方案结算用）",
    ),
    db: AsyncSession = Depends(get_db),
) -> FixtureScoresResponse:
    """Batch local scores for saved calculator plans — no official API calls."""
    unique = []
    seen: set[int] = set()
    for raw in ids:
        fid = int(raw)
        if fid in seen:
            continue
        seen.add(fid)
        unique.append(fid)
        if len(unique) >= 200:
            break
    if not unique:
        set_no_store_headers(response)
        return FixtureScoresResponse(total=0, fixtures=[])

    result = await db.execute(select(Fixture).where(Fixture.id.in_(unique)))
    rows = list(result.scalars().all())
    by_id = {fx.id: fx for fx in rows}
    items: list[FixtureScoreResponse] = []
    for fid in unique:
        fx = by_id.get(fid)
        if fx is None:
            continue
        items.append(
            FixtureScoreResponse(
                fixture_id=fx.id,
                status=fx.status or "",
                fixture_date=fx.date.isoformat() if fx.date else "",
                home_goals=fx.home_goals,
                away_goals=fx.away_goals,
            )
        )
    set_no_store_headers(response)
    return FixtureScoresResponse(total=len(items), fixtures=items)


@router.get("/results", response_model=ResultsResponse)
async def get_fixture_results(
    response: Response,
    date_str: str = Query(
        ...,
        alias="date",
        description="起始比赛日 YYYY-MM-DD（场地当地比赛日）",
    ),
    days: int = Query(
        default=1,
        ge=1,
        le=366,
        description="从 date 起共 N 个比赛日（含起始日）；默认 1=单日",
    ),
    league_id: int | None = Query(default=None, description="按单个联赛 ID 过滤"),
    league_ids: list[int] | None = Query(
        default=None,
        description="按多个联赛 ID 过滤；与 league_id 同时传时取交集",
    ),
    handicap_ruleset: Literal["asian", "jc"] = Query(
        default="asian",
        description="asian=亚洲盘整数盘走水；jc=竞彩让胜/让平/让负",
    ),
    db: AsyncSession = Depends(get_db),
) -> ResultsResponse:
    """按日期（或连续多日）查看本地已落库赛果，并对照赛前预测计算命中（只读本地）。"""
    try:
        base_date = date.fromisoformat(date_str)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD") from exc

    today = utc_today()
    end_date = min(base_date + timedelta(days=days - 1), today)
    if end_date < base_date:
        end_date = base_date

    match_day_expr = fixture_match_day_expr()
    end_exclusive = end_date + timedelta(days=1)

    if league_ids is not None:
        allowed = {int(x) for x in league_ids}
        if not allowed:
            raise HTTPException(status_code=400, detail="league_ids 不能为空")
    else:
        allowed = None

    stmt = (
        select(Fixture)
        .where(
            match_day_expr >= base_date.isoformat(),
            match_day_expr < end_exclusive.isoformat(),
            results_list_clause(),
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
    fixture_ids = [f.id for f in fixtures]
    stored_by_id = await load_stored_by_fixture_ids(db, fixture_ids)
    auto_by_id = await load_auto_picks_by_fixture_ids(db, fixture_ids)
    standings_keys = {
        key
        for fixture in fixtures
        if (key := fixture_standing_key(fixture)) is not None
    }
    standings_maps = await load_standings_maps(db, standings_keys)

    items: list[ResultFixtureResponse] = []
    for fx in fixtures:
        evaluated = evaluate_fixture_prediction(
            fx,
            stored_by_id.get(fx.id),
            auto_pick=auto_by_id.get(fx.id),
            handicap_ruleset=handicap_ruleset,
        )
        home_rank, away_rank = _ranks_from_maps(fx, standings_maps, stored_by_id.get(fx.id))
        home_goals, away_goals = results_list_score(
            fx.status,
            fx.home_goals,
            fx.away_goals,
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
                match_day=fixture_match_day(fx),
                status=fx.status,
                status_short=getattr(fx, "status_short", None),
                home_goals=home_goals,
                away_goals=away_goals,
                et_home_goals=getattr(fx, "et_home_goals", None),
                et_away_goals=getattr(fx, "et_away_goals", None),
                pen_home=getattr(fx, "pen_home", None),
                pen_away=getattr(fx, "pen_away", None),
                has_prediction=evaluated["has_prediction"],
                recommendation=evaluated["recommendation"],
                score_hint=evaluated["score_hint"],
                goal_lean=evaluated["goal_lean"],
                both_score_lean=evaluated["both_score_lean"],
                handicap_lean=evaluated["handicap_lean"],
                handicap_result=evaluated["handicap_result"],
                handicap_hit=evaluated["handicap_hit"],
                result_hit=evaluated["result_hit"],
                auto_pick_hit=evaluated["auto_pick_hit"],
                auto_pick_market=evaluated["auto_pick_market"],
                auto_pick_lean=evaluated["auto_pick_lean"],
                quality_rating=evaluated.get("quality_rating"),
                score_hit=evaluated["score_hit"],
                ou_hit=evaluated["ou_hit"],
                btts_hit=evaluated["btts_hit"],
                home_rank=home_rank,
                away_rank=away_rank,
            )
        )

    set_no_store_headers(response)
    return ResultsResponse(
        date=base_date.isoformat(),
        total=len(items),
        fixtures=items,
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
    handicap_ruleset: Literal["asian", "jc"] = Query(
        default="asian",
        description="asian=亚洲盘整数盘走水；jc=竞彩让胜/让平/让负",
    ),
    db: AsyncSession = Depends(get_db),
) -> ResultsHistoryResponse:
    """历史预测准确率汇总 + 按日序列（供折线图）。只读本地库。"""
    if league_id is not None:
        league_ids: list[int] = [league_id]
    else:
        league_ids = []
    today = utc_today()
    end_day = today
    if end_date_str:
        try:
            parsed = date.fromisoformat(end_date_str)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="end_date 格式应为 YYYY-MM-DD") from exc
        # Client may send local calendar "today" which can be ahead of UTC
        # match-day; clamp instead of 422 so all-history charts stay available.
        end_day = min(parsed, today)
    payload = await build_history_accuracy(
        db,
        days=days,
        league_ids=league_ids,
        end_day=end_day,
        handicap_ruleset=handicap_ruleset,
    )
    set_no_store_headers(response)
    return ResultsHistoryResponse.model_validate(payload)


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
    fixture = await db.get(Fixture, fixture_id)
    from app.services.odds_snapshot import normalize_odds_snapshot

    odds = rehydrate_odds_markets(
        normalize_odds_snapshot(
            loads_json(stored.odds_json, {"available": False}),
            match_start_time=fixture.date if fixture else None,
            fixture_id=fixture_id,
            stage="current",
        )
    )
    known = {f["id"] for f in OPINION_FACTORS}
    factors = [f for f in body.factors if f in known]
    adjusted = adjust_probabilities_with_factors(base, factors)
    snap = build_prediction_snapshot(
        adjusted,
        odds if isinstance(odds, dict) else None,
        league_id=fixture.league_id if fixture else None,
    )
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

    # 已开赛未完场：这一次点击补拉官方比分（预测快照仍冻结）。
    score_ttl = score_refresh_ttl(fixture.status, fixture.date)
    if score_ttl is not None:
        try:
            async with FootballFetcher(session=db) as fetcher:
                refreshed = await fetcher.refresh_fixture_score(fixture.id, ttl=score_ttl)
            if refreshed:
                await db.refresh(fixture)
        except Exception as exc:
            # 比分补拉失败不应挡住已经落库的赛前详情。
            logger.warning(
                "Live score refresh failed for fixture %s: %s",
                fixture.id,
                exc,
            )

    analyzer = AnalyzerService(db)
    try:
        # On-demand: local-first, then official enrich for missing package pieces.
        analysis = await analyzer.analyze_fixture(fixture_id, include_package=True)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"分析暂时失败，请重试：{exc}",
        ) from exc

    set_no_store_headers(response, analysis.data_source)
    package = analysis.package if isinstance(analysis.package, dict) else {}
    standings = package.get("standings") or {}
    odds_snippet = _odds_snippet_from_package(package.get("odds"))
    odds_opening_snippet = _odds_snippet_from_package(package.get("odds_opening"))
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
        match_day=fixture_match_day(fixture),
        match_timezone=fixture.match_timezone or "UTC",
        match_day_source=fixture.match_day_source or "utc",
        odds_refresh_allowed=_odds_refresh_allowed(
            fixture,
            today_match_day=await current_prematch_match_day(
                db,
                league_ids=await allowed_league_ids(db),
            ),
        ),
        status=fixture.status,
        home_goals=fixture.home_goals,
        away_goals=fixture.away_goals,
        analysis=analysis_to_response(analysis),
        home_rank=standings.get("home_rank"),
        away_rank=standings.get("away_rank"),
        odds_snippet=odds_snippet,
        odds_opening_snippet=odds_opening_snippet,
    )
