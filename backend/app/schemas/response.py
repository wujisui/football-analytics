from datetime import datetime, timezone
from typing import Any

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
    home_win_prob: float = Field(..., ge=0, le=1, description="主队胜率")
    draw_prob: float = Field(..., ge=0, le=1, description="平局概率")
    away_win_prob: float = Field(..., ge=0, le=1, description="客队胜率")


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
    values: list[dict[str, Any]] = Field(default_factory=list)


class OddsPackageResponse(BaseModel):
    available: bool = False
    match_winner: MatchWinnerOddsResponse | None = None
    asian_handicap: LineOddsResponse | None = None
    goals_ou: LineOddsResponse | None = None
    bookmakers: list[dict[str, Any]] = Field(default_factory=list)


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


class PrematchPackageResponse(BaseModel):
    odds: OddsPackageResponse = Field(default_factory=OddsPackageResponse)
    lineups: LineupsPackageResponse = Field(default_factory=LineupsPackageResponse)
    injuries: InjuriesPackageResponse = Field(default_factory=InjuriesPackageResponse)
    head_to_head: H2HPackageResponse = Field(default_factory=H2HPackageResponse)
    home_form: FormPackageResponse = Field(default_factory=FormPackageResponse)
    away_form: FormPackageResponse = Field(default_factory=FormPackageResponse)
    standings: StandingsSnippetResponse = Field(default_factory=StandingsSnippetResponse)
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
        description="推荐：主胜/平局/客胜，或双选主胜/平等；待分析表示尚无模型输出",
    )
    goal_lean: str = Field(default="", description="大小球倾向（相对主盘）")
    both_score_lean: str = Field(default="", description="双方进球倾向")
    score_hint: str = Field(default="", description="参考比分")
    handicap_lean: str = Field(default="", description="让球倾向（竞彩风格，相对亚盘）")
    data_source: str = Field(..., description="数据来源：cache/api/database")
    analyzed_at: datetime = Field(..., description="分析时间（UTC）")
    cache_status: str = Field(default="miss", description="分析缓存状态：hit/miss")
    package: PrematchPackageResponse | None = Field(
        default=None, description="赛前数据包：赔率/阵容/伤病/交锋/近况"
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


class LeagueSummaryResponse(BaseModel):
    league_id: int = Field(..., description="联赛 ID")
    league_name: str = Field(..., description="联赛名称")
    country: str | None = Field(default=None, description="国家/地区")
    today_fixtures_count: int = Field(..., description="指定日期（默认今天）的比赛数量")
    upcoming_fixtures_count: int = Field(
        default=0, description="从指定日期起未来 N 天（含当天）的比赛数量"
    )


class LeaguesListResponse(BaseModel):
    date: str = Field(..., description="统计基准日期 YYYY-MM-DD")
    days: int = Field(..., description="未来窗口天数（含基准日）")
    leagues: list[LeagueSummaryResponse] = Field(default_factory=list, description="联赛列表")


def analysis_to_response(analysis) -> AnalysisResponse:
    from app.services.prediction import derive_prediction_leans, get_recommendation

    package = None
    odds = None
    if getattr(analysis, "package", None):
        package = PrematchPackageResponse.model_validate(analysis.package)
        if isinstance(analysis.package, dict):
            odds = analysis.package.get("odds")

    probs = {
        "home": analysis.home_win_prob,
        "draw": analysis.draw_prob,
        "away": analysis.away_win_prob,
    }
    leans = derive_prediction_leans(
        probs,
        odds if isinstance(odds, dict) else None,
    )

    return AnalysisResponse(
        fixture_id=analysis.fixture_id,
        home_team_name=analysis.home_team_name,
        away_team_name=analysis.away_team_name,
        league_name=analysis.league_name,
        fixture_date=analysis.fixture_date,
        status=analysis.status,
        probabilities=ProbabilitiesResponse(
            home_win_prob=analysis.home_win_prob,
            draw_prob=analysis.draw_prob,
            away_win_prob=analysis.away_win_prob,
        ),
        confidence=analysis.confidence,
        # Always recompute — do not reuse stale DB recommendation strings.
        recommendation=get_recommendation(probs),
        goal_lean=leans["goal_lean"],
        both_score_lean=leans["both_score_lean"],
        score_hint=leans["score_hint"],
        handicap_lean=leans["handicap_lean"],
        data_source=analysis.data_source,
        analyzed_at=analysis.analyzed_at,
        cache_status=analysis.cache_status,
        package=package,
    )
