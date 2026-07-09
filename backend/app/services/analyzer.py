from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models.fixture import Fixture
from app.models.league import League
from app.models.pre_match_data import PreMatchData
from app.models.team import Team
from app.services.api_utils import extract_items, first_value
from app.services.cache import TTL_ANALYSIS, analysis_cache_key, get_cache_service
from app.services.fetcher import FootballFetcher
from app.services.ttl_policy import (
    is_finished_status,
    refresh_ttl_seconds,
    should_stop_api_refresh,
)

logger = logging.getLogger(__name__)

HOME_ADVANTAGE = 0.1
AWAY_DISADVANTAGE = 0.05
DEFAULT_PROB = 1 / 3


@dataclass
class TeamFormStats:
    wins: int = 0
    draws: int = 0
    losses: int = 0

    @property
    def played(self) -> int:
        return self.wins + self.draws + self.losses

    @property
    def win_rate(self) -> float:
        return self.wins / self.played if self.played else DEFAULT_PROB

    @property
    def draw_rate(self) -> float:
        return self.draws / self.played if self.played else DEFAULT_PROB


@dataclass
class AnalysisResult:
    fixture_id: int
    home_team_name: str
    away_team_name: str
    league_name: str
    fixture_date: datetime
    status: str
    home_win_prob: float
    draw_prob: float
    away_win_prob: float
    confidence: str
    recommendation: str
    data_source: str
    analyzed_at: datetime
    cache_status: str = "miss"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["fixture_date"] = self.fixture_date.isoformat()
        data["analyzed_at"] = self.analyzed_at.isoformat()
        return data


def normalize_probabilities(probs: dict[str, float]) -> dict[str, float]:
    total = sum(max(value, 0.0) for value in probs.values())
    if total <= 0:
        return {"home": DEFAULT_PROB, "draw": DEFAULT_PROB, "away": DEFAULT_PROB}
    return {key: max(value, 0.0) / total for key, value in probs.items()}


def get_confidence_level(data_completeness: float) -> str:
    if data_completeness >= 0.8:
        return "高"
    if data_completeness >= 0.5:
        return "中"
    return "低"


def get_recommendation(probs: dict[str, float]) -> str:
    mapping = {"home": "主胜", "draw": "平局", "away": "客胜"}
    best = max(probs, key=probs.get)
    return mapping[best]


def parse_team_form(payload: dict[str, Any], team_id: int) -> TeamFormStats:
    stats = TeamFormStats()
    finished_statuses = {"FT", "AET", "PEN"}

    for item in extract_items(payload):
        status = first_value(item, [["fixture", "status", "short"], ["status", "short"], ["status"]])
        if status and str(status).upper() not in finished_statuses:
            continue

        home_id = first_value(item, [["teams", "home", "id"], ["homeTeam", "id"]])
        away_id = first_value(item, [["teams", "away", "id"], ["awayTeam", "id"]])
        home_goals = first_value(item, [["goals", "home"], ["score", "home"]])
        away_goals = first_value(item, [["goals", "away"], ["score", "away"]])

        if None in (home_id, away_id, home_goals, away_goals):
            continue

        home_goals = int(home_goals)
        away_goals = int(away_goals)

        if int(home_id) == team_id:
            if home_goals > away_goals:
                stats.wins += 1
            elif home_goals == away_goals:
                stats.draws += 1
            else:
                stats.losses += 1
        elif int(away_id) == team_id:
            if away_goals > home_goals:
                stats.wins += 1
            elif away_goals == home_goals:
                stats.draws += 1
            else:
                stats.losses += 1

    return stats


class AnalyzerService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.cache = get_cache_service()

    async def _load_fixture(self, fixture_id: int) -> Fixture | None:
        stmt = (
            select(Fixture)
            .where(Fixture.id == fixture_id)
            .options(
                selectinload(Fixture.home_team),
                selectinload(Fixture.away_team),
                selectinload(Fixture.league),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_team_form(self, fetcher: FootballFetcher, team_id: int, limit: int = 5) -> TeamFormStats:
        try:
            payload = await fetcher.fetch_team_form_payload(team_id, last=limit)
            return parse_team_form(payload, team_id)
        except Exception as exc:
            logger.warning("Failed to fetch form for team %s: %s", team_id, exc)
            return TeamFormStats()

    async def _save_pre_match_data(
        self,
        fixture_id: int,
        home_win_prob: float,
        draw_prob: float,
        away_win_prob: float,
    ) -> None:
        result = await self.session.execute(
            select(PreMatchData).where(PreMatchData.fixture_id == fixture_id)
        )
        record = result.scalar_one_or_none()

        if record is None:
            record = PreMatchData(
                fixture_id=fixture_id,
                home_win_prob=home_win_prob,
                draw_prob=draw_prob,
                away_win_prob=away_win_prob,
            )
            self.session.add(record)
        else:
            record.home_win_prob = home_win_prob
            record.draw_prob = draw_prob
            record.away_win_prob = away_win_prob

        await self.session.commit()

    def _result_from_pre_match(
        self,
        fixture: Fixture,
        home_name: str,
        away_name: str,
        league_name: str,
        stored: PreMatchData,
        confidence: str = "中",
    ) -> AnalysisResult:
        probs = {
            "home": stored.home_win_prob or DEFAULT_PROB,
            "draw": stored.draw_prob or DEFAULT_PROB,
            "away": stored.away_win_prob or DEFAULT_PROB,
        }
        analyzed_at = stored.updated_at
        if analyzed_at.tzinfo is None:
            analyzed_at = analyzed_at.replace(tzinfo=timezone.utc)

        return AnalysisResult(
            fixture_id=fixture.id,
            home_team_name=home_name,
            away_team_name=away_name,
            league_name=league_name,
            fixture_date=fixture.date,
            status=fixture.status,
            home_win_prob=probs["home"],
            draw_prob=probs["draw"],
            away_win_prob=probs["away"],
            confidence=confidence,
            recommendation=get_recommendation(probs),
            data_source="database",
            analyzed_at=analyzed_at,
            cache_status="miss",
        )

    def _analysis_refresh_ttl(self, fixture: Fixture) -> int | None:
        """How long stored analysis stays fresh before re-calling API-Sports.

        Finished matches: never refresh for prediction.
        Otherwise: kickoff-relative policy (far/mid/matchday/near).
        """
        settings = get_settings()
        if settings.ANALYSIS_REFRESH_TTL_SECONDS > 0:
            if is_finished_status(fixture.status):
                return None
            return settings.ANALYSIS_REFRESH_TTL_SECONDS
        return refresh_ttl_seconds(
            fixture.date,
            status=fixture.status,
            kind="analysis",
        )

    async def _get_fresh_pre_match(
        self,
        fixture_id: int,
        fixture: Fixture,
    ) -> PreMatchData | None:
        result = await self.session.execute(
            select(PreMatchData).where(PreMatchData.fixture_id == fixture_id)
        )
        stored = result.scalar_one_or_none()
        if stored is None:
            return None
        if None in (stored.home_win_prob, stored.draw_prob, stored.away_win_prob):
            return None

        # Kickoff passed / finished: freeze — never re-hit API for this fixture.
        if should_stop_api_refresh(fixture.date, fixture.status):
            return stored

        ttl = self._analysis_refresh_ttl(fixture)
        if ttl is None:
            return stored

        updated = stored.updated_at
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - updated
        if age <= timedelta(seconds=ttl):
            return stored
        logger.info(
            "Stored analysis for fixture %s is stale (age=%ss, refresh_ttl=%ss)",
            fixture_id,
            int(age.total_seconds()),
            ttl,
        )
        return None

    async def analyze_fixture(self, fixture_id: int) -> AnalysisResult:
        cache_key = analysis_cache_key(fixture_id)
        cached = await self.cache.get(cache_key)
        if cached is not None and "payload" in cached:
            payload = cached["payload"]
            return AnalysisResult(
                fixture_id=payload["fixture_id"],
                home_team_name=payload["home_team_name"],
                away_team_name=payload["away_team_name"],
                league_name=payload["league_name"],
                fixture_date=datetime.fromisoformat(payload["fixture_date"]),
                status=payload["status"],
                home_win_prob=payload["home_win_prob"],
                draw_prob=payload["draw_prob"],
                away_win_prob=payload["away_win_prob"],
                confidence=payload["confidence"],
                recommendation=payload["recommendation"],
                data_source="cache",
                analyzed_at=datetime.fromisoformat(payload["analyzed_at"]),
                cache_status="hit",
            )

        fixture = await self._load_fixture(fixture_id)
        if fixture is None:
            raise ValueError(f"Fixture {fixture_id} not found in database.")

        home_team = fixture.home_team or await self.session.get(Team, fixture.home_team_id)
        away_team = fixture.away_team or await self.session.get(Team, fixture.away_team_id)
        league = fixture.league or await self.session.get(League, fixture.league_id)

        home_name = home_team.name if home_team else f"Team {fixture.home_team_id}"
        away_name = away_team.name if away_team else f"Team {fixture.away_team_id}"
        league_name = league.name if league else f"League {fixture.league_id}"
        season = league.season if league and league.season else str(datetime.now().year)

        # Local-first: reuse stored analysis until kickoff-based refresh is due.
        settings = get_settings()
        if settings.LOCAL_FIRST:
            stored = await self._get_fresh_pre_match(fixture_id, fixture)
            if stored is not None:
                result = self._result_from_pre_match(
                    fixture, home_name, away_name, league_name, stored, confidence="中"
                )
                await self.cache.set(cache_key, result.to_dict(), TTL_ANALYSIS)
                logger.info(
                    "Analysis served from pre_match_data for fixture %s (status=%s)",
                    fixture_id,
                    fixture.status,
                )
                return result

        # After kickoff: if we somehow have no stored analysis, still do not call API.
        if should_stop_api_refresh(fixture.date, fixture.status):
            pre_match = await self.session.execute(
                select(PreMatchData).where(PreMatchData.fixture_id == fixture_id)
            )
            stored = pre_match.scalar_one_or_none()
            if stored and None not in (
                stored.home_win_prob,
                stored.draw_prob,
                stored.away_win_prob,
            ):
                return self._result_from_pre_match(
                    fixture, home_name, away_name, league_name, stored, confidence="低"
                )
            raise ValueError(
                f"Fixture {fixture_id} has kicked off/finished and has no local analysis. "
                "Prepare data before kickoff next time."
            )

        sources_ok = 0
        total_sources = 4
        data_source = "api"

        home_form = TeamFormStats()
        away_form = TeamFormStats()

        try:
            async with FootballFetcher(session=self.session, cache=self.cache) as fetcher:
                try:
                    await fetcher.fetch_headtohead(
                        fixture.home_team_id,
                        fixture.away_team_id,
                    )
                    sources_ok += 1
                except Exception as exc:
                    logger.warning("Head-to-head fetch failed for %s: %s", fixture_id, exc)

                home_form = await self.get_team_form(fetcher, fixture.home_team_id)
                if home_form.played > 0:
                    sources_ok += 1

                away_form = await self.get_team_form(fetcher, fixture.away_team_id)
                if away_form.played > 0:
                    sources_ok += 1

                try:
                    await fetcher.fetch_team_statistics(
                        fixture.home_team_id,
                        fixture.league_id,
                        season,
                    )
                    await fetcher.fetch_team_statistics(
                        fixture.away_team_id,
                        fixture.league_id,
                        season,
                    )
                    sources_ok += 1
                except Exception as exc:
                    logger.warning("Team statistics fetch failed for %s: %s", fixture_id, exc)
        except Exception as exc:
            logger.error("Analyzer API unavailable for fixture %s: %s", fixture_id, exc)
            data_source = "database"
            sources_ok = 0

            pre_match = await self.session.execute(
                select(PreMatchData).where(PreMatchData.fixture_id == fixture_id)
            )
            stored = pre_match.scalar_one_or_none()
            if stored and None not in (
                stored.home_win_prob,
                stored.draw_prob,
                stored.away_win_prob,
            ):
                return self._result_from_pre_match(
                    fixture, home_name, away_name, league_name, stored, confidence="低"
                )

        raw_probs = {
            "home": home_form.win_rate + HOME_ADVANTAGE,
            "draw": (home_form.draw_rate + away_form.draw_rate) / 2,
            "away": max(away_form.win_rate - AWAY_DISADVANTAGE, 0.0),
        }
        probs = normalize_probabilities(raw_probs)
        completeness = sources_ok / total_sources
        confidence = get_confidence_level(completeness)

        result = AnalysisResult(
            fixture_id=fixture_id,
            home_team_name=home_name,
            away_team_name=away_name,
            league_name=league_name,
            fixture_date=fixture.date,
            status=fixture.status,
            home_win_prob=round(probs["home"], 4),
            draw_prob=round(probs["draw"], 4),
            away_win_prob=round(probs["away"], 4),
            confidence=confidence,
            recommendation=get_recommendation(probs),
            data_source=data_source,
            analyzed_at=datetime.now(timezone.utc),
            cache_status="miss",
        )

        await self._save_pre_match_data(
            fixture_id,
            result.home_win_prob,
            result.draw_prob,
            result.away_win_prob,
        )

        await self.cache.set(cache_key, result.to_dict(), TTL_ANALYSIS)
        return result
