from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_serializer


def _utc_iso(value: datetime) -> str:
    """Serialize kickoff/analysis times as UTC ISO-8601 with Z.

    SQLite stores naive datetimes that originate from API-Sports UTC timestamps.
    Emitting Z lets the frontend convert to the viewer's local timezone correctly.
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


class ProbabilitiesResponse(BaseModel):
    available: bool = Field(
        default=True,
        description="是否有有效胜平负概率；无数据时为 false，勿展示 33%/33%/33%",
    )
    home_win_prob: float | None = Field(default=None, ge=0, le=1, description="主队胜率")
    draw_prob: float | None = Field(default=None, ge=0, le=1, description="平局概率")
    away_win_prob: float | None = Field(default=None, ge=0, le=1, description="客队胜率")


class MatchWinnerOddsResponse(BaseModel):
    bookmaker: str | None = None
    home: str | float | None = None
    draw: str | float | None = None
    away: str | float | None = None
    values: list[dict[str, Any]] = Field(default_factory=list)


class LineOddsResponse(BaseModel):
    bookmaker: str | None = None
    bet: str | None = None
    line: str | None = None
    home: str | float | None = None
    away: str | float | None = None
    lines: list[dict[str, Any]] = Field(
        default_factory=list,
        description="多档盘口：[{line, home, away}, ...]，首项为主盘",
    )
    values: list[dict[str, Any]] = Field(default_factory=list)


class OddsPackageResponse(BaseModel):
    available: bool = False
    match_winner: MatchWinnerOddsResponse | None = None
    asian_handicap: LineOddsResponse | None = None
    goals_ou: LineOddsResponse | None = None
    bookmakers: list[dict[str, Any]] = Field(default_factory=list)
    role: str | None = Field(default=None, description="opening|current")
    captured_at: str | None = None


class StandingsSnippetResponse(BaseModel):
    available: bool = False
    league_id: int | None = None
    league_name: str = ""
    group: str | None = None
    home_rank: int | None = None
    away_rank: int | None = None
    scope: str = "competition"
    fetched: bool | None = None


class PlayerLineupResponse(BaseModel):
    id: int | None = None
    name: str = ""
    number: int | str | None = None
    pos: str | None = None
    grid: str | None = None


class TeamLineupResponse(BaseModel):
    team_id: int | None = None
    team_name: str = ""
    formation: str | None = None
    coach: str | None = None
    start_xi: list[PlayerLineupResponse] = Field(default_factory=list)
    substitutes: list[PlayerLineupResponse] = Field(default_factory=list)


class LineupsPackageResponse(BaseModel):
    available: bool = False
    home: TeamLineupResponse | None = None
    away: TeamLineupResponse | None = None


class InjuryItemResponse(BaseModel):
    player_id: int | None = None
    player_name: str = ""
    type: str | None = None
    reason: str | None = None


class InjuriesPackageResponse(BaseModel):
    available: bool = False
    home: list[InjuryItemResponse] = Field(default_factory=list)
    away: list[InjuryItemResponse] = Field(default_factory=list)


class FormMatchResponse(BaseModel):
    fixture_id: int | None = None
    date: str | None = None
    home: str = ""
    away: str = ""
    score: str = ""
    league_id: int | None = None
    league_name: str = ""
    league_country: str = ""
    result: str | None = None
    outcome_for_current_home: str | None = None


class FormPackageResponse(BaseModel):
    team_id: int | None = None
    played: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    form: str = ""
    matches: list[FormMatchResponse] = Field(default_factory=list)


class H2HPackageResponse(BaseModel):
    played: int = 0
    home_wins: int = 0
    draws: int = 0
    away_wins: int = 0
    matches: list[FormMatchResponse] = Field(default_factory=list)
    fetched: bool | None = None


class BriefingWinnerResponse(BaseModel):
    id: int | None = None
    name: str | None = None
    comment: str | None = None


class BriefingPercentResponse(BaseModel):
    home: str | None = None
    draw: str | None = None
    away: str | None = None


class BriefingGoalsResponse(BaseModel):
    home: str | None = None
    away: str | None = None


class BriefingComparisonItemResponse(BaseModel):
    key: str = ""
    label: str = ""
    home: str | None = None
    away: str | None = None


class BriefingPackageResponse(BaseModel):
    """Official API-Sports /predictions (赛前简报); not local ML 我的预测."""

    available: bool = False
    fetched: bool | None = None
    advice: str | None = None
    winner: BriefingWinnerResponse = Field(default_factory=BriefingWinnerResponse)
    win_or_draw: bool | None = None
    under_over: str | None = None
    goals: BriefingGoalsResponse = Field(default_factory=BriefingGoalsResponse)
    percent: BriefingPercentResponse = Field(default_factory=BriefingPercentResponse)
    comparison: list[BriefingComparisonItemResponse] = Field(default_factory=list)


class PrematchPackageResponse(BaseModel):
    odds: OddsPackageResponse = Field(
        default_factory=OddsPackageResponse,
        description="即时盘（最近一次拉取）",
    )
    odds_opening: OddsPackageResponse = Field(
        default_factory=OddsPackageResponse,
        description="初盘（中午定时任务首次落库，冻结）",
    )
    lineups: LineupsPackageResponse = Field(default_factory=LineupsPackageResponse)
    injuries: InjuriesPackageResponse = Field(default_factory=InjuriesPackageResponse)
    head_to_head: H2HPackageResponse = Field(default_factory=H2HPackageResponse)
    home_form: FormPackageResponse = Field(default_factory=FormPackageResponse)
    away_form: FormPackageResponse = Field(default_factory=FormPackageResponse)
    standings: StandingsSnippetResponse = Field(default_factory=StandingsSnippetResponse)
    briefing: BriefingPackageResponse = Field(default_factory=BriefingPackageResponse)
    home_formation: str | None = None
    away_formation: str | None = None


class AnalysisResponse(BaseModel):
    fixture_id: int = Field(..., description="比赛 ID")
    home_team_name: str = Field(..., description="主队名称")
    away_team_name: str = Field(..., description="客队名称")
    league_name: str = Field(..., description="联赛名称")
    fixture_date: datetime = Field(..., description="比赛时间（UTC）")
    status: str = Field(..., description="比赛状态")
    probabilities: ProbabilitiesResponse = Field(..., description="胜平负概率")
    confidence: str = Field(..., description="置信度：高/中/低")
    recommendation: str = Field(
        ...,
        description="推荐：胜/平/负，或双选胜/平、负/平；待分析表示尚无模型输出",
    )
    goal_lean: str = Field(default="", description="大小球倾向（相对主盘）")
    both_score_lean: str = Field(default="", description="双方进球倾向")
    score_hint: str = Field(default="", description="参考比分")
    handicap_lean: str = Field(
        default="",
        description="让球推荐（主盘）：让球胜/让球平/让球负 + 盘口",
    )
    handicap_market_note: str = Field(
        default="",
        description="进阶：盘口水位与参考比分结算不一致时的说明（详情页）",
    )
    data_source: str = Field(..., description="数据来源：cache/api/database")
    analyzed_at: datetime = Field(..., description="分析时间（UTC）")
    cache_status: str = Field(default="miss", description="分析缓存状态：hit/miss")
    package: PrematchPackageResponse | None = Field(
        default=None, description="赛前数据包：赔率/阵容/伤病/交锋/近况/官方简报"
    )

    @field_serializer("fixture_date", "analyzed_at")
    def serialize_analysis_datetimes(self, value: datetime) -> str:
        return _utc_iso(value)


class OpinionFactorResponse(BaseModel):
    id: str
    label: str
    group: str


class OpinionFactorsResponse(BaseModel):
    factors: list[OpinionFactorResponse] = Field(default_factory=list)


class AdjustPredictionRequest(BaseModel):
    factors: list[str] = Field(default_factory=list, description="勾选的主观因素 ID")


class PredictionSnapshotResponse(BaseModel):
    home_win_prob: float
    draw_prob: float
    away_win_prob: float
    recommendation: str
    goal_lean: str = ""
    both_score_lean: str = ""
    score_hint: str = ""
    handicap_lean: str = ""
    factors: list[str] = Field(default_factory=list)


class FixtureOddsSnippetResponse(BaseModel):
    """Compact markets for list cards (from stored odds_json, no live API)."""
    available: bool = False
    match_winner: MatchWinnerOddsResponse | None = None
    asian_handicap: LineOddsResponse | None = None
    goals_ou: LineOddsResponse | None = None


class FixtureResponse(BaseModel):
    fixture_id: int = Field(..., description="比赛 ID")
    league_id: int = Field(..., description="联赛 ID")
    league_name: str = Field(..., description="联赛名称")
    home_team_id: int = Field(..., description="主队 ID")
    away_team_id: int = Field(..., description="客队 ID")
    home_team_name: str = Field(..., description="主队名称")
    away_team_name: str = Field(..., description="客队名称")
    fixture_date: datetime = Field(..., description="比赛时间（UTC）")
    status: str = Field(..., description="比赛状态")
    home_goals: int | None = Field(default=None, description="主队进球（常规时间 90'）")
    away_goals: int | None = Field(default=None, description="客队进球（常规时间 90'）")
    league_country: str | None = Field(default=None, description="联赛所属国家/地区")
    analysis: AnalysisResponse = Field(..., description="赛前分析结果")
    home_rank: int | None = Field(default=None, description="本赛事积分榜排名（主）")
    away_rank: int | None = Field(default=None, description="本赛事积分榜排名（客）")
    odds_snippet: FixtureOddsSnippetResponse | None = Field(
        default=None, description="列表用盘口摘要（本地已存）"
    )

    @field_serializer("fixture_date")
    def serialize_fixture_date(self, value: datetime) -> str:
        return _utc_iso(value)


class TodayFixturesResponse(BaseModel):
    date: str = Field(..., description="起始日期 YYYY-MM-DD")
    days: int = Field(default=1, description="查询窗口天数（含起始日）")
    total: int = Field(..., description="比赛总数")
    fixtures: list[FixtureResponse] = Field(default_factory=list, description="赛程列表")


class ResultFixtureResponse(BaseModel):
    fixture_id: int
    league_id: int
    league_name: str
    league_country: str | None = Field(default=None, description="联赛所属国家/地区")
    home_team_id: int
    away_team_id: int
    home_team_name: str
    away_team_name: str
    fixture_date: datetime
    status: str
    status_short: str | None = Field(
        default=None, description="官方短码 FT/AET/PEN；预测对照用常规时间比分"
    )
    home_goals: int | None = Field(default=None, description="常规时间（90'）主队进球")
    away_goals: int | None = Field(default=None, description="常规时间（90'）客队进球")
    et_home_goals: int | None = Field(default=None, description="加时结束比分（通常含 90'）主")
    et_away_goals: int | None = Field(default=None, description="加时结束比分（通常含 90'）客")
    pen_home: int | None = Field(default=None, description="点球大战主队")
    pen_away: int | None = Field(default=None, description="点球大战客队")
    # Frozen pre-match prediction snapshot + result settlement.
    has_prediction: bool = False
    recommendation: str | None = None
    score_hint: str | None = None
    goal_lean: str | None = None
    both_score_lean: str | None = None
    handicap_lean: str | None = Field(default=None, description="冻结的赛前让球推荐")
    handicap_result: str | None = Field(
        default=None, description="按常规时间比分及赛前盘口结算的让球胜/平/负"
    )
    handicap_hit: bool | None = Field(default=None, description="让球推荐是否命中")
    score_hit: bool | None = None
    ou_hit: bool | None = None
    btts_hit: bool | None = None
    result_hit: bool | None = None
    single_result_hit: bool | None = Field(
        default=None, description="最高概率胜平负单选是否命中"
    )

    @field_serializer("fixture_date")
    def serialize_fixture_date(self, value: datetime) -> str:
        return _utc_iso(value)


class FavoriteFixtureResponse(BaseModel):
    """Hydrated favorite row for the drawer (join fixtures + pre_match_data)."""

    fixture_id: int
    home_team_name: str
    away_team_name: str
    league_id: int
    league_name: str
    league_country: str | None = None
    fixture_date: datetime
    status: str | None = None
    home_goals: int | None = None
    away_goals: int | None = None
    saved_at: datetime
    has_prediction: bool = False
    recommendation: str | None = None
    handicap_lean: str | None = None
    score_hint: str | None = None
    goal_lean: str | None = None
    both_score_lean: str | None = None
    # Finished settlement (same flags as results list); null while not evaluable.
    handicap_result: str | None = None
    handicap_hit: bool | None = None
    score_hit: bool | None = None
    ou_hit: bool | None = None
    btts_hit: bool | None = None
    result_hit: bool | None = None
    single_result_hit: bool | None = None
    probabilities_available: bool = False
    home_win_prob: float | None = None
    draw_prob: float | None = None
    away_win_prob: float | None = None
    odds_snippet: FixtureOddsSnippetResponse | None = None

    @field_serializer("fixture_date", "saved_at")
    def serialize_datetimes(self, value: datetime) -> str:
        return _utc_iso(value)


class FavoriteFixturesResponse(BaseModel):
    total: int
    favorites: list[FavoriteFixtureResponse] = Field(default_factory=list)


class FavoriteFixtureCreateRequest(BaseModel):
    fixture_id: int = Field(..., gt=0, description="比赛 ID")


class AccuracyStatResponse(BaseModel):
    hits: int = 0
    total: int = 0
    rate: float | None = Field(default=None, description="命中率 0–1；无样本时为 null")


class ResultsAccuracyResponse(BaseModel):
    result: AccuracyStatResponse = Field(
        default_factory=AccuracyStatResponse, description="胜平负命中（含双选）"
    )
    single_result: AccuracyStatResponse = Field(
        default_factory=AccuracyStatResponse, description="最高概率胜平负单选命中"
    )
    score: AccuracyStatResponse = Field(default_factory=AccuracyStatResponse, description="比分命中")
    ou: AccuracyStatResponse = Field(default_factory=AccuracyStatResponse, description="大小球命中")
    btts: AccuracyStatResponse = Field(
        default_factory=AccuracyStatResponse, description="双方进球命中"
    )
    handicap: AccuracyStatResponse = Field(
        default_factory=AccuracyStatResponse, description="让球胜平负推荐命中"
    )
    fixtures_with_prediction: int = 0
    fixtures_finished: int = 0


class AccuracyDayPointResponse(BaseModel):
    date: str
    result_rate: float | None = None
    score_rate: float | None = None
    ou_rate: float | None = None
    btts_rate: float | None = None
    handicap_rate: float | None = None
    result: AccuracyStatResponse = Field(default_factory=AccuracyStatResponse)
    score: AccuracyStatResponse = Field(default_factory=AccuracyStatResponse)
    ou: AccuracyStatResponse = Field(default_factory=AccuracyStatResponse)
    btts: AccuracyStatResponse = Field(default_factory=AccuracyStatResponse)
    handicap: AccuracyStatResponse = Field(default_factory=AccuracyStatResponse)
    fixtures_with_prediction: int = 0
    fixtures_finished: int = 0


class ResultsHistoryResponse(BaseModel):
    days: int = Field(description="样本跨度天数；all_time 时为首末日跨度")
    all_time: bool = Field(default=False, description="是否统计全部本地完场样本")
    start_date: str
    end_date: str
    overall: ResultsAccuracyResponse
    series: list[AccuracyDayPointResponse] = Field(default_factory=list)


class ResultsResponse(BaseModel):
    date: str = Field(..., description="查询日期 YYYY-MM-DD")
    total: int = Field(..., description="赛果场次")
    fixtures: list[ResultFixtureResponse] = Field(default_factory=list)
    accuracy: ResultsAccuracyResponse = Field(default_factory=ResultsAccuracyResponse)


class SyncFixturesResponse(BaseModel):
    status: str = Field(..., description="ok")
    fixtures_saved: int = Field(default=0, description="写入/更新的场次数")
    days: int = Field(default=1, description="同步窗口天数")
    date: str | None = Field(default=None, description="单日同步时的日期")
    message: str = Field(default="")


class LeagueCatalogItemResponse(BaseModel):
    league_id: int = Field(..., description="联赛 ID")
    league_name: str = Field(..., description="展示名（中文）")
    country: str | None = Field(default=None, description="国家/地区")
    season: str | None = Field(default=None, description="目录中的赛季提示（可选）")


class LeagueCatalogResponse(BaseModel):
    leagues: list[LeagueCatalogItemResponse] = Field(
        default_factory=list,
        description="config/leagues.json 中可拉取的全部联赛",
    )


class LeagueSummaryResponse(BaseModel):
    league_id: int = Field(..., description="联赛 ID")
    league_name: str = Field(..., description="联赛名称")
    country: str | None = Field(default=None, description="国家/地区")
    today_fixtures_count: int = Field(..., description="指定日期（默认今天）的比赛数量")
    upcoming_fixtures_count: int = Field(
        default=0, description="从指定日期起未来 N 天（含当天）的比赛数量"
    )


class LeagueFilterOptionResponse(BaseModel):
    league_id: int
    league_name: str
    country: str | None = None
    fixtures_count: int = Field(0, description="当日场次（发现或本地）")
    tier: Literal["configured", "extra"] = Field(
        ...,
        description="configured=默认顶级/洲际目录；extra=可选次级/其他目录",
    )
    default_checked: bool = Field(
        ...,
        description="筛选弹层默认勾选",
    )


class LeagueFilterOptionsResponse(BaseModel):
    date: str = Field(..., description="统计日 YYYY-MM-DD（先做「今天」）")
    configured: list[LeagueFilterOptionResponse] = Field(default_factory=list)
    extra: list[LeagueFilterOptionResponse] = Field(default_factory=list)


class LeaguesListResponse(BaseModel):
    date: str = Field(..., description="统计基准日期 YYYY-MM-DD")
    days: int = Field(..., description="未来窗口天数（含基准日）")
    leagues: list[LeagueSummaryResponse] = Field(default_factory=list, description="联赛列表")


def analysis_to_response(analysis) -> AnalysisResponse:
    from app.services.prediction import (
        derive_prediction_leans,
        get_recommendation,
        is_flat_prior,
        resolve_match_probabilities,
    )

    package = None
    odds = None
    if getattr(analysis, "package", None):
        package = PrematchPackageResponse.model_validate(analysis.package)
        if isinstance(analysis.package, dict):
            odds = analysis.package.get("odds")

    raw = {
        "home": analysis.home_win_prob,
        "draw": analysis.draw_prob,
        "away": analysis.away_win_prob,
    }
    probs = resolve_match_probabilities(raw, odds if isinstance(odds, dict) else None)
    ready = not is_flat_prior(probs)

    league_id: int | None = None
    if isinstance(analysis.package, dict):
        standings = analysis.package.get("standings")
        if isinstance(standings, dict):
            raw_lid = standings.get("league_id")
            if raw_lid is not None:
                try:
                    league_id = int(raw_lid)
                except (TypeError, ValueError):
                    league_id = None

    # Prefer snapshot frozen at last pre-kickoff analysis (audit / learning).
    frozen = bool(getattr(analysis, "leans_frozen", False))
    if frozen:
        recommendation = analysis.recommendation or "待分析"
        from app.services.prediction import (
            canonical_btts_lean,
            canonical_goal_lean,
            canonical_recommendation,
            canonical_score_hint,
            resolve_handicap_bundle,
        )

        recommendation = canonical_recommendation(recommendation)
        goal_lean = canonical_goal_lean(
            getattr(analysis, "goal_lean", None) or "大小：待分析"
        )
        both_score_lean = canonical_btts_lean(
            getattr(analysis, "both_score_lean", None) or "双进:待分析"
        )
        score_hint = canonical_score_hint(
            getattr(analysis, "score_hint", None) or "待分析"
        )

        handicap_lean, handicap_market_note = resolve_handicap_bundle(
            odds if isinstance(odds, dict) else None,
            recommendation,
            league_id=league_id,
            stored=getattr(analysis, "handicap_lean", None),
            score_hint=score_hint,
        )
    else:
        leans = derive_prediction_leans(
            probs,
            odds if isinstance(odds, dict) else None,
            league_id=league_id,
        )
        recommendation = get_recommendation(probs) if ready else "待分析"
        goal_lean = leans["goal_lean"] if ready else "大小：待分析"
        both_score_lean = leans["both_score_lean"] if ready else "双进:待分析"
        score_hint = leans["score_hint"] if ready else "比分:待分析"
        handicap_lean = leans["handicap_lean"]
        handicap_market_note = leans.get("handicap_market_note", "")

    return AnalysisResponse(
        fixture_id=analysis.fixture_id,
        home_team_name=analysis.home_team_name,
        away_team_name=analysis.away_team_name,
        league_name=analysis.league_name,
        fixture_date=analysis.fixture_date,
        status=analysis.status,
        probabilities=ProbabilitiesResponse(
            available=ready,
            home_win_prob=probs["home"] if ready else None,
            draw_prob=probs["draw"] if ready else None,
            away_win_prob=probs["away"] if ready else None,
        ),
        confidence=analysis.confidence,
        recommendation=recommendation,
        goal_lean=goal_lean,
        both_score_lean=both_score_lean,
        score_hint=score_hint,
        handicap_lean=handicap_lean,
        handicap_market_note=handicap_market_note or "",
        data_source=analysis.data_source,
        analyzed_at=analysis.analyzed_at,
        cache_status=analysis.cache_status,
        package=package,
    )
