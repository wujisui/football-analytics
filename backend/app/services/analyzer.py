import asyncio
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
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
from app.services.prematch_package import (
    dumps_json,
    loads_json,
    package_from_record,
    parse_injuries_payload,
    parse_lineups_payload,
    parse_standings_for_teams,
    rehydrate_odds_markets,
    summarize_form_payload,
    summarize_h2h_payload,
)
from app.services.ttl_policy import (
    is_finished_status,
    refresh_ttl_seconds,
    should_stop_api_refresh,
)

logger = logging.getLogger(__name__)

HOME_ADVANTAGE = 0.1  # retained for reference; probs now via ml_predictor
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
    package: dict[str, Any] | None = None

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


def get_recommendation(probs: dict[str, float], features: dict[str, float] | None = None) -> str:
    from app.services.prediction import get_recommendation as _rec

    return _rec(probs, features=features)


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
        package: dict[str, Any] | None = None,
        features: dict[str, float] | None = None,
        model_source: str | None = None,
    ) -> None:
        result = await self.session.execute(
            select(PreMatchData).where(PreMatchData.fixture_id == fixture_id)
        )
        record = result.scalar_one_or_none()
        package = package or {}

        lineups = package.get("lineups") or {}
        home_lineup = lineups.get("home") or {}
        away_lineup = lineups.get("away") or {}
        injuries = package.get("injuries") or {}

        fields = {
            "home_win_prob": home_win_prob,
            "draw_prob": draw_prob,
            "away_win_prob": away_win_prob,
            "home_formation": home_lineup.get("formation"),
            "away_formation": away_lineup.get("formation"),
            "injuries_home": dumps_json(injuries.get("home")),
            "injuries_away": dumps_json(injuries.get("away")),
            "lineups_json": dumps_json(package.get("lineups")),
            "injuries_json": dumps_json(package.get("injuries")),
            "h2h_json": dumps_json(package.get("head_to_head")),
            "home_form_json": dumps_json(package.get("home_form")),
            "away_form_json": dumps_json(package.get("away_form")),
            "standings_json": dumps_json(package.get("standings")),
        }
        # Odds come from batch sync only — never wipe a good local board with empty package.
        odds_pkg = package.get("odds") if isinstance(package.get("odds"), dict) else None
        if odds_pkg and odds_pkg.get("available"):
            fields["odds_json"] = dumps_json(odds_pkg)
        elif record is None:
            fields["odds_json"] = dumps_json({"available": False})

        # Freeze recommendation / leans at analysis time for results audit.
        from app.services.prediction import build_prediction_snapshot

        odds_for_snap = rehydrate_odds_markets(
            odds_pkg
            or (
                loads_json(record.odds_json, {"available": False})
                if record and record.odds_json
                else {"available": False}
            )
        )
        snap = build_prediction_snapshot(
            {
                "home": home_win_prob,
                "draw": draw_prob,
                "away": away_win_prob,
            },
            odds_for_snap if isinstance(odds_for_snap, dict) else None,
            features=features,
        )
        fields["recommendation"] = snap.get("recommendation")
        fields["score_hint"] = snap.get("score_hint")
        fields["goal_lean"] = snap.get("goal_lean")
        fields["both_score_lean"] = snap.get("both_score_lean")
        fields["handicap_lean"] = snap.get("handicap_lean")

        if record is None:
            record = PreMatchData(fixture_id=fixture_id, **fields)
            self.session.add(record)
        else:
            for key, value in fields.items():
                if value is not None:
                    setattr(record, key, value)

        if features is not None:
            from app.services.ml_predictor import persist_match_features

            await persist_match_features(
                self.session,
                fixture_id,
                features,
                {
                    "home": home_win_prob,
                    "draw": draw_prob,
                    "away": away_win_prob,
                },
                source=model_source or "multifactor",
            )

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
            package=package_from_record(stored),
        )

    async def _collect_prematch_package(
        self,
        fetcher: FootballFetcher,
        fixture: Fixture,
        ttl: int,
    ) -> dict[str, Any]:
        """Fetch package pieces in parallel (each failure is isolated)."""
        package: dict[str, Any] = {
            "odds": {"available": False},
            "lineups": {"available": False, "home": None, "away": None},
            "injuries": {"available": False, "home": [], "away": []},
            "head_to_head": {"played": 0, "matches": []},
            "home_form": {"played": 0, "matches": []},
            "away_form": {"played": 0, "matches": []},
            "standings": {"available": False},
        }
        league = fixture.league
        season = (
            league.season
            if league and league.season
            else str(datetime.now(timezone.utc).year)
        )
        # Free plan: clamp standings to 2024 when current season is blocked.
        standings_season = season
        if not get_settings().uses_full_history:
            try:
                year = int(str(season)[:4])
                if year > 2024:
                    standings_season = "2024"
            except ValueError:
                standings_season = "2024"

        async def _h2h() -> None:
            payload = await fetcher.fetch_headtohead(
                fixture.home_team_id, fixture.away_team_id, last=20
            )
            package["head_to_head"] = summarize_h2h_payload(
                payload, fixture.home_team_id, limit=20
            )

        async def _home_form() -> None:
            payload = await fetcher.fetch_team_form_payload(fixture.home_team_id, last=20)
            package["home_form"] = summarize_form_payload(
                payload, fixture.home_team_id, limit=20
            )

        async def _away_form() -> None:
            payload = await fetcher.fetch_team_form_payload(fixture.away_team_id, last=20)
            package["away_form"] = summarize_form_payload(
                payload, fixture.away_team_id, limit=20
            )

        async def _odds_from_local() -> None:
            # Odds are batch-synced with fixtures (POST /fixtures/sync).
            # Detail never calls /odds?fixture= — local only.
            result = await self.session.execute(
                select(PreMatchData).where(PreMatchData.fixture_id == fixture.id)
            )
            stored = result.scalar_one_or_none()
            if stored and stored.odds_json:
                package["odds"] = rehydrate_odds_markets(
                    loads_json(stored.odds_json, {"available": False})
                )
            else:
                package["odds"] = {"available": False}

        async def _lineups() -> None:
            package["lineups"] = parse_lineups_payload(
                await fetcher.fetch_lineups(fixture.id, ttl=ttl)
            )

        async def _injuries() -> None:
            package["injuries"] = parse_injuries_payload(
                await fetcher.fetch_injuries(fixture.id, ttl=ttl),
                fixture.home_team_id,
                fixture.away_team_id,
            )

        async def _standings() -> None:
            try:
                payload = await fetcher.fetch_standings(fixture.league_id, standings_season)
                package["standings"] = parse_standings_for_teams(
                    payload,
                    fixture.home_team_id,
                    fixture.away_team_id,
                    league_id=fixture.league_id,
                    league_name=league.name if league else None,
                )
            except Exception:
                # Persist empty+fetched so we do not retry-storm on rate limits.
                package["standings"] = {
                    "available": False,
                    "league_id": fixture.league_id,
                    "league_name": league.name if league else "",
                    "home_rank": None,
                    "away_rank": None,
                    "scope": "competition",
                    "fetched": True,
                }
                raise

        # Run sequentially: shared AsyncSession cannot safely serve concurrent awaits
        # (parallel gather previously caused intermittent 500 on first detail open).
        for label, coro_factory in (
            ("H2H", _h2h),
            ("home_form", _home_form),
            ("away_form", _away_form),
            ("odds_local", _odds_from_local),
            ("standings", _standings),
            ("lineups", _lineups),
            ("injuries", _injuries),
        ):
            try:
                await coro_factory()
            except Exception as exc:
                logger.warning(
                    "%s package fetch failed for %s: %s", label, fixture.id, exc
                )

        return package

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

    async def analyze_fixture_local(self, fixture_id: int) -> AnalysisResult:
        """List-page analysis: Redis/DB only — never call official API.

        Used by /fixtures/today so a league with many matches does not block
        on dozens of form/H2H/stats requests.
        """
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
                package=None,
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

        stored = await self._get_fresh_pre_match(fixture_id, fixture)
        if stored is None:
            # Any stored probs are fine for the list; ignore TTL freshness.
            result = await self.session.execute(
                select(PreMatchData).where(PreMatchData.fixture_id == fixture_id)
            )
            stored = result.scalar_one_or_none()
            if stored is None or None in (
                stored.home_win_prob,
                stored.draw_prob,
                stored.away_win_prob,
            ):
                # Placeholder until detail page runs full analysis.
                probs = {
                    "home": DEFAULT_PROB,
                    "draw": DEFAULT_PROB,
                    "away": DEFAULT_PROB,
                }
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
                    confidence="低",
                    recommendation=get_recommendation(probs),
                    data_source="database",
                    analyzed_at=datetime.now(timezone.utc),
                    cache_status="miss",
                    package=None,
                )

        result = self._result_from_pre_match(
            fixture, home_name, away_name, league_name, stored, confidence="中"
        )
        result.package = None
        return result

    async def analyze_fixture(
        self,
        fixture_id: int,
        *,
        include_package: bool = True,
    ) -> AnalysisResult:
        cache_key = analysis_cache_key(fixture_id)
        cached = await self.cache.get(cache_key)
        if cached is not None and "payload" in cached:
            payload = cached["payload"]
            package = payload.get("package") if include_package else None
            # Detail view needs form/h2h; skip empty packages left by free-plan last= failures.
            package_useful = False
            package_stale = False
            if isinstance(package, dict):
                h2h_pkg = package.get("head_to_head") or {}
                home_form = package.get("home_form") or {}
                away_form = package.get("away_form") or {}
                # Pre-fix / failed summarize / old fetch strategy → refresh once.
                standings = package.get("standings") or {}
                history_tag = get_settings().history_source_tag
                package_stale = (
                    "fetched" not in h2h_pkg
                    or h2h_pkg.get("source") != history_tag
                    or home_form.get("source") != history_tag
                    or away_form.get("source") != history_tag
                    or not standings.get("fetched")
                )
                package_useful = bool(
                    home_form.get("played")
                    or away_form.get("played")
                    or h2h_pkg.get("played")
                    or (package.get("odds") or {}).get("available")
                    or (package.get("lineups") or {}).get("available")
                    or standings.get("available")
                )
            if include_package and (not package_useful or package_stale):
                pass
            else:
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
                    package=package,
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
                # Detail page needs form/h2h; odds-only rows used to short-circuit refresh.
                home_form = loads_json(stored.home_form_json, {}) or {}
                away_form = loads_json(stored.away_form_json, {}) or {}
                h2h = loads_json(stored.h2h_json, {}) or {}
                has_form_or_h2h = bool(
                    home_form.get("played")
                    or away_form.get("played")
                    or h2h.get("played")
                    or (home_form.get("matches") or [])
                    or (away_form.get("matches") or [])
                    or (h2h.get("matches") or [])
                )
                # Old/failed rows or pre-merge fetch strategy → one refresh.
                standings = loads_json(getattr(stored, "standings_json", None), {}) or {}
                history_tag = get_settings().history_source_tag
                package_stale = (
                    "fetched" not in h2h
                    or h2h.get("source") != history_tag
                    or home_form.get("source") != history_tag
                    or away_form.get("source") != history_tag
                    or not standings.get("fetched")
                )
                has_any_package = bool(
                    stored.h2h_json
                    or stored.odds_json
                    or stored.lineups_json
                    or stored.home_form_json
                    or stored.away_form_json
                    or getattr(stored, "standings_json", None)
                )
                if (
                    include_package
                    and (
                        not has_any_package
                        or not has_form_or_h2h
                        or package_stale
                    )
                    and not should_stop_api_refresh(fixture.date, fixture.status)
                ):
                    pass  # fall through to refresh package before kickoff
                else:
                    result = self._result_from_pre_match(
                        fixture, home_name, away_name, league_name, stored, confidence="中"
                    )
                    if not include_package:
                        result.package = None
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
        total_sources = 7
        data_source = "api"
        package: dict[str, Any] = {}

        home_form = TeamFormStats()
        away_form = TeamFormStats()
        refresh_ttl = self._analysis_refresh_ttl(fixture) or TTL_ANALYSIS
        api_budget = max(2.0, float(settings.ANALYSIS_API_BUDGET_SECONDS))

        async def _enrich_from_api() -> None:
            nonlocal package, home_form, away_form, sources_ok, data_source
            async with FootballFetcher(session=self.session, cache=self.cache) as fetcher:
                if include_package:
                    package = await self._collect_prematch_package(
                        fetcher, fixture, ttl=refresh_ttl
                    )
                    if package.get("head_to_head", {}).get("played", 0) > 0:
                        sources_ok += 1
                    if package.get("home_form", {}).get("played", 0) > 0:
                        sources_ok += 1
                        home_form = TeamFormStats(
                            wins=package["home_form"].get("wins", 0),
                            draws=package["home_form"].get("draws", 0),
                            losses=package["home_form"].get("losses", 0),
                        )
                    if package.get("away_form", {}).get("played", 0) > 0:
                        sources_ok += 1
                        away_form = TeamFormStats(
                            wins=package["away_form"].get("wins", 0),
                            draws=package["away_form"].get("draws", 0),
                            losses=package["away_form"].get("losses", 0),
                        )
                    if package.get("odds", {}).get("available"):
                        sources_ok += 1
                    if package.get("lineups", {}).get("available"):
                        sources_ok += 1
                    if package.get("injuries", {}).get("available"):
                        sources_ok += 1
                else:
                    home_form = await self.get_team_form(fetcher, fixture.home_team_id)
                    if home_form.played > 0:
                        sources_ok += 1
                    away_form = await self.get_team_form(fetcher, fixture.away_team_id)
                    if away_form.played > 0:
                        sources_ok += 1
                    try:
                        await fetcher.fetch_headtohead(
                            fixture.home_team_id, fixture.away_team_id
                        )
                        sources_ok += 1
                    except Exception as exc:
                        logger.warning("H2H fetch failed for %s: %s", fixture_id, exc)

                # Stats are optional; skip if little budget remains.
                try:
                    await asyncio.wait_for(
                        asyncio.gather(
                            fetcher.fetch_team_statistics(
                                fixture.home_team_id, fixture.league_id, season
                            ),
                            fetcher.fetch_team_statistics(
                                fixture.away_team_id, fixture.league_id, season
                            ),
                        ),
                        timeout=3.0,
                    )
                    sources_ok += 1
                except Exception as exc:
                    logger.warning("Team statistics fetch failed for %s: %s", fixture_id, exc)

        enrich_task = asyncio.create_task(_enrich_from_api())
        try:
            await asyncio.wait_for(asyncio.shield(enrich_task), timeout=api_budget)
        except asyncio.TimeoutError:
            logger.warning(
                "Analysis API budget (%.1fs) exceeded for fixture %s — returning partial/local",
                api_budget,
                fixture_id,
            )
            # Cancel leftover work, then reset session — CancelledError mid-commit
            # previously left AsyncSession unusable and surfaced as HTTP 500.
            enrich_task.cancel()
            try:
                await enrich_task
            except asyncio.CancelledError:
                pass
            except Exception as cancel_exc:
                logger.warning(
                    "Enrichment cleanup error for fixture %s: %s", fixture_id, cancel_exc
                )
            try:
                await self.session.rollback()
            except Exception:
                logger.exception("Session rollback failed after analysis timeout")

            data_source = "database" if sources_ok == 0 else "api"
            if sources_ok == 0:
                pre_match = await self.session.execute(
                    select(PreMatchData).where(PreMatchData.fixture_id == fixture_id)
                )
                stored = pre_match.scalar_one_or_none()
                if stored and None not in (
                    stored.home_win_prob,
                    stored.draw_prob,
                    stored.away_win_prob,
                ):
                    result = self._result_from_pre_match(
                        fixture, home_name, away_name, league_name, stored, confidence="低"
                    )
                    if include_package and not result.package:
                        result.package = package or None
                    return result
        except Exception as exc:
            logger.error("Analyzer API unavailable for fixture %s: %s", fixture_id, exc)
            if not enrich_task.done():
                enrich_task.cancel()
                try:
                    await enrich_task
                except (asyncio.CancelledError, Exception):
                    pass
            try:
                await self.session.rollback()
            except Exception:
                logger.exception("Session rollback failed after analysis error")

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

        # Ensure form summaries are in package for feature extraction even when
        # only TeamFormStats were populated via legacy get_team_form path.
        # Do not invent a chronological form string from unsorted W/D/L counts —
        # that would fake win/loss streaks.
        if not isinstance(package.get("home_form"), dict) or not package["home_form"].get("played"):
            package["home_form"] = {
                "played": home_form.played,
                "wins": home_form.wins,
                "draws": home_form.draws,
                "losses": home_form.losses,
                "form": "",
            }
        if not isinstance(package.get("away_form"), dict) or not package["away_form"].get("played"):
            package["away_form"] = {
                "played": away_form.played,
                "wins": away_form.wins,
                "draws": away_form.draws,
                "losses": away_form.losses,
                "form": "",
            }

        from app.services.ml_predictor import predict_probabilities

        prediction = predict_probabilities(package)
        probs = normalize_probabilities(prediction.probs)
        completeness = sources_ok / total_sources
        confidence = get_confidence_level(completeness)
        if prediction.source == "ml" and completeness >= 0.5:
            confidence = get_confidence_level(max(completeness, 0.8))

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
            recommendation=get_recommendation(probs, features=prediction.features),
            data_source=data_source if prediction.source == "form_fallback" else (
                f"{data_source}+{prediction.source}"
            ),
            analyzed_at=datetime.now(timezone.utc),
            cache_status="miss",
            package=package if include_package else None,
        )

        await self._save_pre_match_data(
            fixture_id,
            result.home_win_prob,
            result.draw_prob,
            result.away_win_prob,
            package=package if include_package else None,
            features=prediction.features,
            model_source=prediction.source,
        )

        await self.cache.set(cache_key, result.to_dict(), TTL_ANALYSIS)
        return result
