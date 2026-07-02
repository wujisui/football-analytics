from datetime import datetime

from pydantic import BaseModel, Field


class ProbabilitiesResponse(BaseModel):
    home_win_prob: float = Field(..., ge=0, le=1, description="主队胜率")
    draw_prob: float = Field(..., ge=0, le=1, description="平局概率")
    away_win_prob: float = Field(..., ge=0, le=1, description="客队胜率")


class AnalysisResponse(BaseModel):
    fixture_id: int = Field(..., description="比赛 ID")
    home_team_name: str = Field(..., description="主队名称")
    away_team_name: str = Field(..., description="客队名称")
    league_name: str = Field(..., description="联赛名称")
    fixture_date: datetime = Field(..., description="比赛时间")
    status: str = Field(..., description="比赛状态")
    probabilities: ProbabilitiesResponse = Field(..., description="胜平负概率")
    confidence: str = Field(..., description="置信度：高/中/低")
    recommendation: str = Field(..., description="推荐方向：主胜/平局/客胜")
    data_source: str = Field(..., description="数据来源：cache/api/database")
    analyzed_at: datetime = Field(..., description="分析时间")
    cache_status: str = Field(default="miss", description="分析缓存状态：hit/miss")


class FixtureResponse(BaseModel):
    fixture_id: int = Field(..., description="比赛 ID")
    league_id: int = Field(..., description="联赛 ID")
    league_name: str = Field(..., description="联赛名称")
    home_team_id: int = Field(..., description="主队 ID")
    away_team_id: int = Field(..., description="客队 ID")
    home_team_name: str = Field(..., description="主队名称")
    away_team_name: str = Field(..., description="客队名称")
    fixture_date: datetime = Field(..., description="比赛时间")
    status: str = Field(..., description="比赛状态")
    analysis: AnalysisResponse = Field(..., description="赛前分析结果")


class TodayFixturesResponse(BaseModel):
    date: str = Field(..., description="日期 YYYY-MM-DD")
    total: int = Field(..., description="比赛总数")
    fixtures: list[FixtureResponse] = Field(default_factory=list, description="赛程列表")


class LeagueSummaryResponse(BaseModel):
    league_id: int = Field(..., description="联赛 ID")
    league_name: str = Field(..., description="联赛名称")
    country: str | None = Field(default=None, description="国家/地区")
    today_fixtures_count: int = Field(..., description="今日比赛数量")


class LeaguesListResponse(BaseModel):
    leagues: list[LeagueSummaryResponse] = Field(default_factory=list, description="联赛列表")


def analysis_to_response(analysis) -> AnalysisResponse:
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
        recommendation=analysis.recommendation,
        data_source=analysis.data_source,
        analyzed_at=analysis.analyzed_at,
        cache_status=analysis.cache_status,
    )
