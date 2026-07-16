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
from app.services.team_names import team_name_zh
from app.services.prematch_package import (
    dumps_json,
    loads_json,
    package_from_record,
    parse_injuries_payload,
    parse_lineups_payload,
    parse_odds_payload,
    parse_predictions_payload,
    parse_standings_for_teams,
    rehydrate_odds_markets,
    summarize_form_payload,
    summarize_h2h_payload,
)
from app.services.ttl_policy import (
    PREDICTION_EXAM_FIELDS,
    is_finished_status,
    is_prediction_exam_locked,
    refresh_ttl_seconds,
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
    # Frozen at last pre-kickoff analysis — prefer these over live recompute.
    goal_lean: str | None = None
    both_score_lean: str | None = None
    score_hint: str | None = None
    handicap_lean: str | None = None
    leans_frozen: bool = False

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


def prematch_package_needs_refresh(
    package: dict[str, Any],
    *,
    history_tag: str,
) -> bool:
    """True when detail /analysis should (re)fetch the prematch display package."""
    h2h = package.get("head_to_head") or {}
    home_form = package.get("home_form") or {}
    away_form = package.get("away_form") or {}
    standings = package.get("standings") or {}
    briefing = package.get("briefing") or {}
    odds = package.get("odds") or {}
    lineups = package.get("lineups") or {}

    stale = (
        "fetched" not in h2h
        or h2h.get("source") != history_tag
        or home_form.get("source") != history_tag
        or away_form.get("source") != history_tag
        or not standings.get("fetched")
        or (briefing and not briefing.get("fetched"))
        or (not odds.get("available") and not odds.get("fetched"))
    )
    useful = bool(
        home_form.get("played")
        or away_form.get("played")
        or h2h.get("played")
        or (home_form.get("matches") or [])
        or (away_form.get("matches") or [])
        or (h2h.get("matches") or [])
        or odds.get("available")
        or lineups.get("available")
        or standings.get("available")
    )
    return not useful or stale


def prematch_package_needs_refresh_from_stored(
    stored: PreMatchData,
    *,
    history_tag: str,
) -> bool:
    if not any(
        (
            stored.h2h_json,
            stored.odds_json,
            stored.lineups_json,
            stored.home_form_json,
            stored.away_form_json,
            getattr(stored, "standings_json", None),
            getattr(stored, "briefing_json", None),
        )
    ):
        return True
    package = {
        "head_to_head": loads_json(stored.h2h_json, {}) or {},
        "home_form": loads_json(stored.home_form_json, {}) or {},
        "away_form": loads_json(stored.away_form_json, {}) or {},
        "standings": loads_json(getattr(stored, "standings_json", None), {}) or {},
        "briefing": loads_json(getattr(stored, "briefing_json", None), {}) or {},
        "odds": loads_json(stored.odds_json, {"available": False}) or {},
        "lineups": loads_json(stored.lineups_json, {}) or {},
    }
    return prematch_package_needs_refresh(package, history_tag=history_tag)


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

        fixture = await self.session.get(Fixture, fixture_id)
        exam_locked = bool(
            fixture
            and is_prediction_exam_locked(fixture.date, fixture.status)
        )

        lineups = package.get("lineups") or {}
        home_lineup = lineups.get("home") or {}
        away_lineup = lineups.get("away") or {}
        injuries = package.get("injuries") or {}

        fields: dict[str, Any] = {
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
        briefing_pkg = package.get("briefing") if isinstance(package.get("briefing"), dict) else None
        if briefing_pkg and briefing_pkg.get("fetched"):
            fields["briefing_json"] = dumps_json(briefing_pkg)
        # Never wipe a good local board with an empty package result.
        odds_pkg = package.get("odds") if isinstance(package.get("odds"), dict) else None
        if odds_pkg and odds_pkg.get("available"):
            fields["odds_json"] = dumps_json(odds_pkg)
        elif odds_pkg and odds_pkg.get("fetched"):
            existing = (
                loads_json(record.odds_json, {})
                if record and record.odds_json
                else {}
            )
            if not existing.get("available"):
                fields["odds_json"] = dumps_json(
                    {"available": False, "fetched": True}
                )
        elif record is None:
            fields["odds_json"] = dumps_json({"available": False})

        # Exam lock: after kickoff never write/overwrite prediction snapshot.
        # Pre-kickoff may refresh with the current algorithm.
        if not exam_locked:
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
            fields["home_win_prob"] = home_win_prob
            fields["draw_prob"] = draw_prob
            fields["away_win_prob"] = away_win_prob
            fields["recommendation"] = snap.get("recommendation")
            fields["score_hint"] = snap.get("score_hint")
            fields["goal_lean"] = snap.get("goal_lean")
            fields["both_score_lean"] = snap.get("both_score_lean")
            fields["handicap_lean"] = snap.get("handicap_lean")
        else:
            logger.info(
                "Prediction exam locked for fixture %s — skip overwrite of %s",
                fixture_id,
                ", ".join(PREDICTION_EXAM_FIELDS),
            )

        if record is None:
            record = PreMatchData(fixture_id=fixture_id, **fields)
            self.session.add(record)
        else:
            for key, value in fields.items():
                if value is not None:
                    setattr(record, key, value)

        if features is not None and not exam_locked:
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

        frozen_rec = (getattr(stored, "recommendation", None) or "").strip()
        has_frozen = bool(frozen_rec and frozen_rec != "待分析")
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
            recommendation=frozen_rec if has_frozen else get_recommendation(probs),
            data_source="database",
            analyzed_at=analyzed_at,
            cache_status="miss",
            package=package_from_record(stored),
            goal_lean=getattr(stored, "goal_lean", None),
            both_score_lean=getattr(stored, "both_score_lean", None),
            score_hint=getattr(stored, "score_hint", None),
            handicap_lean=getattr(stored, "handicap_lean", None),
            leans_frozen=has_frozen,
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
            "odds_opening": {"available": False},
            "lineups": {"available": False, "home": None, "away": None},
            "injuries": {"available": False, "home": [], "away": []},
            "head_to_head": {"played": 0, "matches": []},
            "home_form": {"played": 0, "matches": []},
            "away_form": {"played": 0, "matches": []},
            "standings": {"available": False},
            "briefing": {"available": False, "fetched": False},
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

        async def _odds() -> None:
            """Local board first; if missing, pull official /odds?fixture= once.

            Empty official coverage is persisted as fetched=true so detail does
            not retry-storm. Batch sync still refreshes boards for the window.
            """
            result = await self.session.execute(
                select(PreMatchData).where(PreMatchData.fixture_id == fixture.id)
            )
            stored = result.scalar_one_or_none()
            local = (
                rehydrate_odds_markets(
                    loads_json(stored.odds_json, {"available": False})
                )
                if stored and stored.odds_json
                else {"available": False}
            )
            if local.get("available"):
                package["odds"] = local
                return
            if local.get("fetched"):
                package["odds"] = {"available": False, "fetched": True}
                return
            try:
                raw = await fetcher.fetch_odds(fixture.id, ttl=ttl)
                parsed = rehydrate_odds_markets(parse_odds_payload(raw))
                if parsed.get("available"):
                    package["odds"] = parsed
                else:
                    package["odds"] = {"available": False, "fetched": True}
            except Exception:
                package["odds"] = {"available": False, "fetched": True}
                raise

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

        async def _briefing() -> None:
            try:
                package["briefing"] = parse_predictions_payload(
                    await fetcher.fetch_predictions(fixture.id, ttl=ttl)
                )
            except Exception:
                package["briefing"] = {"available": False, "fetched": True}
                raise

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
            ("odds", _odds),
            ("standings", _standings),
            ("lineups", _lineups),
            ("injuries", _injuries),
            ("briefing", _briefing),
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
        home_name = team_name_zh(
            home_team.name if home_team else None, fixture.home_team_id
        ) or f"Team {fixture.home_team_id}"
        away_name = team_name_zh(
            away_team.name if away_team else None, fixture.away_team_id
        ) or f"Team {fixture.away_team_id}"
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
            fixture_date = datetime.fromisoformat(payload["fixture_date"])
            need_refresh = include_package and (
                not isinstance(package, dict)
                or prematch_package_needs_refresh(
                    package,
                    history_tag=get_settings().history_source_tag,
                )
            )
            if not need_refresh:
                return AnalysisResult(
                    fixture_id=payload["fixture_id"],
                    home_team_name=payload["home_team_name"],
                    away_team_name=payload["away_team_name"],
                    league_name=payload["league_name"],
                    fixture_date=fixture_date,
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

        home_name = team_name_zh(
            home_team.name if home_team else None, fixture.home_team_id
        ) or f"Team {fixture.home_team_id}"
        away_name = team_name_zh(
            away_team.name if away_team else None, fixture.away_team_id
        ) or f"Team {fixture.away_team_id}"
        league_name = league.name if league else f"League {fixture.league_id}"
        season = league.season if league and league.season else str(datetime.now().year)

        # Local-first: reuse stored analysis until kickoff-based refresh is due.
        settings = get_settings()
        if settings.LOCAL_FIRST:
            stored = await self._get_fresh_pre_match(fixture_id, fixture)
            if stored is not None:
                history_tag = get_settings().history_source_tag
                if include_package and prematch_package_needs_refresh_from_stored(
                    stored,
                    history_tag=history_tag,
                ):
                    pass  # fall through — same detail path for all match states
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

        exam_locked = is_prediction_exam_locked(fixture.date, fixture.status)
        stored_row = (
            await self.session.execute(
                select(PreMatchData).where(PreMatchData.fixture_id == fixture_id)
            )
        ).scalar_one_or_none()
        has_frozen_probs = bool(
            stored_row
            and None
            not in (
                stored_row.home_win_prob,
                stored_row.draw_prob,
                stored_row.away_win_prob,
            )
        )
        if exam_locked and has_frozen_probs and stored_row is not None:
            await self._save_pre_match_data(
                fixture_id,
                stored_row.home_win_prob,
                stored_row.draw_prob,
                stored_row.away_win_prob,
                package=package if include_package else None,
                features=None,
                model_source=None,
            )
            refreshed = (
                await self.session.execute(
                    select(PreMatchData).where(PreMatchData.fixture_id == fixture_id)
                )
            ).scalar_one_or_none()
            if refreshed is not None:
                result = self._result_from_pre_match(
                    fixture,
                    home_name,
                    away_name,
                    league_name,
                    refreshed,
                    confidence="中",
                )
                if not include_package:
                    result.package = None
                await self.cache.set(cache_key, result.to_dict(), TTL_ANALYSIS)
                return result

        from app.services.ml_predictor import predict_probabilities

        prediction = predict_probabilities(package)
        probs = normalize_probabilities(prediction.probs)
        completeness = sources_ok / total_sources
        confidence = get_confidence_level(completeness)
        if prediction.source == "ml" and completeness >= 0.5:
            confidence = get_confidence_level(max(completeness, 0.8))

        from app.services.prediction import build_prediction_snapshot

        odds_for_snap = None
        if include_package and isinstance(package, dict):
            odds_for_snap = package.get("odds")
        snap = build_prediction_snapshot(
            {
                "home": round(probs["home"], 4),
                "draw": round(probs["draw"], 4),
                "away": round(probs["away"], 4),
            },
            odds_for_snap if isinstance(odds_for_snap, dict) else None,
            features=prediction.features,
        )

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
            recommendation=snap.get("recommendation")
            or get_recommendation(probs, features=prediction.features),
            data_source=data_source if prediction.source == "form_fallback" else (
                f"{data_source}+{prediction.source}"
            ),
            analyzed_at=datetime.now(timezone.utc),
            cache_status="miss",
            package=package if include_package else None,
            goal_lean=snap.get("goal_lean"),
            both_score_lean=snap.get("both_score_lean"),
            score_hint=snap.get("score_hint"),
            handicap_lean=snap.get("handicap_lean"),
            leans_frozen=True,
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
