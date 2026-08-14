"""Auto-favorites: history-adjusted single-lean picks from catalog leagues."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.auto_pick_snapshot import AutoPickSnapshot
from app.models.favorite_fixture import (
    FAVORITE_SOURCE_AUTO,
    FAVORITE_SOURCE_MANUAL,
    FavoriteFixture,
)
from app.models.fixture import Fixture
from app.models.match_feature import MatchFeature
from app.models.pre_match_data import PreMatchData
from app.services.ah_features import handicap_pick_from_lean
from app.services.auto_pick_incentive import adjust_pick_score, ensure_incentives_for_picks
from app.services.data_cleanup import record_has_algorithm_recommendation
from app.services.prediction import (
    _odd_float,
    _parse_goal_lean,
    is_flat_prior,
    recommendation_outcomes,
    resolve_match_probabilities,
)
from app.services.prematch_package import package_from_record, rehydrate_odds_markets
from app.services.results_capture import prematch_list_clause
from app.services.user_scope import ANON_OWNER_ID

logger = logging.getLogger(__name__)

AUTO_PICK_LIMIT = 4
MIN_CONFIDENCE = 0.01
QUALITY_RATING_MAX = 5.0
QUALITY_RATING_MIN = 0.5


def within_day_quality_ratings(
    picks: list["AutoPickCandidate"],
) -> dict[int, float]:
    """Rate selected picks within each match day by final score rank.

    The highest score anchors 5 星; each lower distinct score tier deducts
    0.5 星. Equal scores receive equal ratings.
    """
    by_day: dict[str, list[AutoPickCandidate]] = {}
    for pick in picks:
        by_day.setdefault(_schedule_day_key(pick.kickoff), []).append(pick)

    ratings: dict[int, float] = {}
    for day_picks in by_day.values():
        distinct_scores = sorted(
            {pick.score for pick in day_picks},
            reverse=True,
        )
        score_tiers = {
            score: index for index, score in enumerate(distinct_scores)
        }
        for pick in day_picks:
            ratings[pick.fixture_id] = max(
                QUALITY_RATING_MIN,
                QUALITY_RATING_MAX - 0.5 * score_tiers[pick.score],
            )
    return ratings


@dataclass(frozen=True)
class AutoPickCandidate:
    fixture_id: int
    league_id: int
    kickoff: datetime
    score: float
    market: str
    lean: str
    confidence: float
    decimal_odd: float
    expected_return: float

@dataclass(frozen=True)
class MarketCandidate:
    market: str
    lean: str
    confidence: float
    decimal_odd: float

    @property
    def expected_return(self) -> float:
        """Expected net return per unit stake."""
        return self.confidence * self.decimal_odd - 1.0

    @property
    def ranking_score(self) -> float:
        """「矮子里拔高个」: prefer better payout edge, never hard-reject short odds."""
        return self.expected_return


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _implied_two_way(first: float | None, second: float | None) -> tuple[float, float]:
    if first is None or second is None:
        return 0.5, 0.5
    inv_first, inv_second = 1.0 / first, 1.0 / second
    total = inv_first + inv_second
    if total <= 0:
        return 0.5, 0.5
    return inv_first / total, inv_second / total


def _score_1x2(stored: PreMatchData, odds: dict[str, Any] | None) -> tuple[float, str]:
    outcomes = recommendation_outcomes(stored.recommendation or "")
    # Auto picks are single-lean only; skip 胜/平、负/平、胜/负.
    if not outcomes or len(outcomes) != 1:
        return 0.0, ""
    probs = resolve_match_probabilities(
        {
            "home": float(stored.home_win_prob or 0.0),
            "draw": float(stored.draw_prob or 0.0),
            "away": float(stored.away_win_prob or 0.0),
        },
        odds,
    )
    if is_flat_prior(probs):
        return 0.0, ""
    outcome = next(iter(outcomes))
    return float(probs[outcome]), (stored.recommendation or "").strip()


def _score_handicap(
    stored: PreMatchData,
    odds: dict[str, Any] | None,
    feature: MatchFeature | None,
) -> tuple[float, str]:
    lean = (stored.handicap_lean or "").strip()
    if not lean or "待分析" in lean or "缺少" in lean:
        return 0.0, ""
    # Reject dual AH leans such as 让胜/负.
    single = handicap_pick_from_lean(lean)
    if single is None:
        return 0.0, ""
    cover = getattr(feature, "ah_cover_prob", None)
    if cover is not None:
        try:
            cover_f = float(cover)
        except (TypeError, ValueError):
            cover_f = None
        if cover_f is not None:
            if single == "让负":
                return max(1.0 - cover_f, 0.0), lean
            if single == "让胜":
                return max(cover_f, 0.0), lean
            # 让平 is rare; treat as max side confidence when model exists.
            return max(cover_f, 1.0 - cover_f), lean
    ah = odds.get("asian_handicap") if isinstance(odds, dict) else None
    if not isinstance(ah, dict):
        return 0.0, ""
    home_p, away_p = _implied_two_way(
        _odd_float(ah.get("home")),
        _odd_float(ah.get("away")),
    )
    if single == "让负":
        return away_p, lean
    if single == "让胜":
        return home_p, lean
    return max(home_p, away_p), lean


def _score_ou(stored: PreMatchData, odds: dict[str, Any] | None) -> tuple[float, str]:
    lean = (stored.goal_lean or "").strip()
    parsed = _parse_goal_lean(lean)
    if parsed is None:
        return 0.0, ""
    side, _line = parsed
    ou = odds.get("goals_ou") if isinstance(odds, dict) else None
    if not isinstance(ou, dict):
        return 0.0, ""
    over_p, under_p = _implied_two_way(
        _odd_float(ou.get("home")),
        _odd_float(ou.get("away")),
    )
    return (over_p if side == "over" else under_p), lean


def _score_btts(stored: PreMatchData, odds: dict[str, Any] | None) -> tuple[float, str]:
    lean = (stored.both_score_lean or "").strip()
    if not lean or "待分析" in lean:
        return 0.0, ""
    market = odds.get("both_teams_score") if isinstance(odds, dict) else None
    if not isinstance(market, dict):
        return 0.0, ""
    yes_p, no_p = _implied_two_way(
        _odd_float(market.get("home")),
        _odd_float(market.get("away")),
    )
    if lean.endswith("：是") or lean.endswith(":是") or lean.endswith("是"):
        return yes_p, lean
    if lean.endswith("：否") or lean.endswith(":否") or lean.endswith("否"):
        return no_p, lean
    return max(yes_p, no_p), lean


def _market_decimal_odd(
    market: str,
    lean: str,
    odds: dict[str, Any] | None,
) -> float | None:
    if not isinstance(odds, dict):
        return None

    if market == "1x2":
        outcomes = recommendation_outcomes(lean)
        if not outcomes or len(outcomes) != 1:
            return None
        key = next(iter(outcomes))
        winner = odds.get("match_winner")
        return _odd_float(winner.get(key)) if isinstance(winner, dict) else None

    if market == "ah":
        pick = handicap_pick_from_lean(lean)
        handicap = odds.get("asian_handicap")
        if not isinstance(handicap, dict):
            return None
        if pick == "让胜":
            return _odd_float(handicap.get("home"))
        if pick == "让负":
            return _odd_float(handicap.get("away"))
        return None

    if market == "ou":
        parsed = _parse_goal_lean(lean)
        total = odds.get("goals_ou")
        if parsed is None or not isinstance(total, dict):
            return None
        side, _line = parsed
        return _odd_float(total.get("home" if side == "over" else "away"))

    if market == "btts":
        both = odds.get("both_teams_score")
        if not isinstance(both, dict):
            return None
        if lean.endswith(("：是", ":是", "是")):
            return _odd_float(both.get("home"))
        if lean.endswith(("：否", ":否", "否")):
            return _odd_float(both.get("away"))
        return None

    return None


def _market_candidates(
    stored: PreMatchData,
    *,
    odds: dict[str, Any] | None,
    feature: MatchFeature | None = None,
) -> list[MarketCandidate]:
    scored = (
        ("1x2", _score_1x2(stored, odds)),
        ("ah", _score_handicap(stored, odds, feature)),
        ("ou", _score_ou(stored, odds)),
        ("btts", _score_btts(stored, odds)),
    )
    candidates: list[MarketCandidate] = []
    for market, (confidence, lean) in scored:
        if not lean:
            continue
        decimal_odd = _market_decimal_odd(market, lean, odds)
        if decimal_odd is None:
            continue
        candidates.append(
            MarketCandidate(
                market=market,
                lean=lean,
                confidence=confidence,
                decimal_odd=decimal_odd,
            )
        )
    return candidates


def _schedule_day_key(kickoff: datetime) -> str:
    """UTC match day — same calendar key as frontend ``toScheduleDayKey``."""
    return kickoff.strftime("%Y-%m-%d")


def _best_market(candidates: list[MarketCandidate]) -> MarketCandidate | None:
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda item: (item.ranking_score, item.confidence, -abs(item.decimal_odd - 2.0)),
    )


def score_fixture_confidence(
    stored: PreMatchData,
    *,
    odds: dict[str, Any] | None,
    feature: MatchFeature | None = None,
) -> tuple[float, str, str]:
    """Return (ranking_score, market, lean) for the best single-lean market."""
    best = _best_market(_market_candidates(stored, odds=odds, feature=feature))
    if best is None:
        return 0.0, "", ""
    return best.ranking_score, best.market, best.lean


def score_auto_pick_candidates(
    rows: list[tuple[Fixture, PreMatchData, MatchFeature | None]],
    *,
    min_confidence: float = MIN_CONFIDENCE,
    incentive_state: Any | None = None,
) -> list[AutoPickCandidate]:
    """Score every scorable single-lean fixture (no day / count cap)."""
    ranked: list[AutoPickCandidate] = []
    for fixture, stored, feature in rows:
        if not record_has_algorithm_recommendation(stored, feature):
            continue
        package = package_from_record(stored)
        odds_raw = package.get("odds") if isinstance(package, dict) else None
        odds = (
            rehydrate_odds_markets(odds_raw)
            if isinstance(odds_raw, dict)
            else None
        )
        best = _best_market(
            [
                item
                for item in _market_candidates(
                    stored,
                    odds=odds if isinstance(odds, dict) else None,
                    feature=feature,
                )
                if item.confidence >= min_confidence
            ]
        )
        if best is None:
            continue
        base_score = best.ranking_score
        if incentive_state is not None:
            final_score = adjust_pick_score(
                base_score,
                league_id=int(fixture.league_id),
                market=best.market,
                state=incentive_state,
            )
        else:
            final_score = base_score
        ranked.append(
            AutoPickCandidate(
                fixture_id=fixture.id,
                league_id=int(fixture.league_id),
                kickoff=fixture.date,
                score=final_score,
                market=best.market,
                lean=best.lean,
                confidence=best.confidence,
                decimal_odd=best.decimal_odd,
                expected_return=best.expected_return,
            )
        )
    ranked.sort(key=lambda item: (-item.score, item.kickoff, item.fixture_id))
    return ranked


def rank_auto_pick_candidates(
    rows: list[tuple[Fixture, PreMatchData, MatchFeature | None]],
    *,
    limit: int = AUTO_PICK_LIMIT,
    min_confidence: float = MIN_CONFIDENCE,
    incentive_state: Any | None = None,
) -> list[AutoPickCandidate]:
    """Rank one pool and keep top ``limit`` (single-day helper / tests)."""
    return score_auto_pick_candidates(
        rows,
        min_confidence=min_confidence,
        incentive_state=incentive_state,
    )[: max(0, limit)]


def select_auto_picks_by_match_day(
    candidates: list[AutoPickCandidate],
    *,
    limit_per_day: int = AUTO_PICK_LIMIT,
    skip_fixture_ids: set[int] | None = None,
) -> list[AutoPickCandidate]:
    """Pick up to ``limit_per_day`` per UTC match day — not one slate for the whole window."""
    skip = skip_fixture_ids or set()
    by_day: dict[str, list[AutoPickCandidate]] = {}
    for candidate in candidates:
        by_day.setdefault(_schedule_day_key(candidate.kickoff), []).append(candidate)

    selected: list[AutoPickCandidate] = []
    for day in sorted(by_day):
        day_picks: list[AutoPickCandidate] = []
        for candidate in by_day[day]:
            if candidate.fixture_id in skip:
                continue
            day_picks.append(candidate)
            if len(day_picks) >= limit_per_day:
                break
        selected.extend(day_picks)
    return selected


async def sync_daily_auto_favorites(
    db: AsyncSession,
    *,
    user_id: str | None = None,
    limit: int = AUTO_PICK_LIMIT,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Replace guest-bucket ``source=auto`` tips with per-match-day picks.

    Daily tips always live in the anonymous owner bucket (``ANON_OWNER_ID``)
    so every session can list them; ``user_id`` is ignored for writes.

    Historical hit feedback adjusts candidate scores without eliminating
    candidates. Each UTC match day gets up to ``limit`` tips (default 4),
    ranked by final score. The day's best pick anchors 5 quality stars and
    lower score tiers deduct 0.5 stars.

    A 7-day window can therefore yield many more than four auto favorites —
    never one global cherry-pick across the week. Manual favorites are never
    touched.
    """
    del user_id  # product-wide tips; kept for call-site compat
    owner = ANON_OWNER_ID
    settings = get_settings()
    catalog_ids = list(settings.LEAGUE_IDS.values())
    current = now or _utc_now()

    # Once per scheduler-local day: refresh EMA + soft weights before ranking.
    incentive_state = await ensure_incentives_for_picks(db, now=current)

    rows = (
        await db.execute(
            select(Fixture, PreMatchData, MatchFeature)
            .join(PreMatchData, PreMatchData.fixture_id == Fixture.id)
            .outerjoin(MatchFeature, MatchFeature.fixture_id == Fixture.id)
            .where(
                Fixture.league_id.in_(catalog_ids),
                prematch_list_clause(current),
            )
            .order_by(Fixture.date, Fixture.id)
        )
    ).all()

    # Collapse possible duplicate MatchFeature joins.
    by_fixture: dict[int, tuple[Fixture, PreMatchData, MatchFeature | None]] = {}
    for fixture, stored, feature in rows:
        prev = by_fixture.get(fixture.id)
        if prev is None or (feature is not None and prev[2] is None):
            by_fixture[fixture.id] = (fixture, stored, feature)

    candidates = score_auto_pick_candidates(
        list(by_fixture.values()),
        incentive_state=incentive_state,
    )

    # Skip fixtures any user already starred manually in the guest bucket
    # (logged-in manuals live on their own rows and do not block shared tips).
    manual_ids = {
        int(row[0])
        for row in (
            await db.execute(
                select(FavoriteFixture.fixture_id).where(
                    FavoriteFixture.user_id == owner,
                    FavoriteFixture.source == FAVORITE_SOURCE_MANUAL,
                )
            )
        ).all()
    }

    selected = select_auto_picks_by_match_day(
        candidates,
        limit_per_day=limit,
        skip_fixture_ids=manual_ids,
    )

    ratings = within_day_quality_ratings(selected)

    await db.execute(
        delete(FavoriteFixture).where(
            FavoriteFixture.user_id == owner,
            FavoriteFixture.source == FAVORITE_SOURCE_AUTO,
        )
    )

    saved_at = _utc_now()
    for candidate in selected:
        db.add(
            FavoriteFixture(
                fixture_id=candidate.fixture_id,
                user_id=owner,
                source=FAVORITE_SOURCE_AUTO,
                auto_market=candidate.market,
                auto_lean=candidate.lean,
                quality_rating=ratings.get(candidate.fixture_id),
                saved_at=saved_at,
            )
        )

    # Persist learning snapshots: only rewrite still-prematch fixtures so
    # kicked-off / finished daily tips remain auditable.
    prematch_ids = set(by_fixture.keys())
    selected_ids = {item.fixture_id for item in selected}
    if prematch_ids - selected_ids:
        await db.execute(
            delete(AutoPickSnapshot).where(
                AutoPickSnapshot.fixture_id.in_(prematch_ids - selected_ids)
            )
        )
    if selected_ids:
        await db.execute(
            delete(AutoPickSnapshot).where(
                AutoPickSnapshot.fixture_id.in_(selected_ids)
            )
        )
    for candidate in selected:
        db.add(
            AutoPickSnapshot(
                fixture_id=candidate.fixture_id,
                match_day=_schedule_day_key(candidate.kickoff),
                market=candidate.market,
                lean=candidate.lean,
                confidence=candidate.confidence,
                decimal_odd=candidate.decimal_odd,
                expected_return=candidate.expected_return,
                score=candidate.score,
                quality_rating=ratings.get(candidate.fixture_id),
                picked_at=saved_at,
            )
        )

    await db.commit()

    tz_name = settings.SCHEDULER_TIMEZONE
    try:
        local_day = datetime.now(ZoneInfo(tz_name)).date().isoformat()
    except Exception:
        local_day = saved_at.date().isoformat()

    by_day_counts: dict[str, int] = {}
    for item in selected:
        key = _schedule_day_key(item.kickoff)
        by_day_counts[key] = by_day_counts.get(key, 0) + 1

    result = {
        "day": local_day,
        "candidates": len(candidates),
        "selected_count": len(selected),
        "by_day": by_day_counts,
        "selected": [
            {
                "fixture_id": item.fixture_id,
                "match_day": _schedule_day_key(item.kickoff),
                "score": round(item.score, 4),
                "market": item.market,
                "lean": item.lean,
                "confidence": round(item.confidence, 4),
                "decimal_odd": round(item.decimal_odd, 3),
                "expected_return": round(item.expected_return, 4),
                "quality_rating": ratings.get(item.fixture_id),
            }
            for item in selected
        ],
        "skipped_manual": sorted(
            {
                item.fixture_id
                for item in candidates
                if item.fixture_id in manual_ids
            }
        ),
    }
    logger.info(
        "Auto-favorites day=%s selected=%s candidates=%s by_day=%s",
        local_day,
        len(selected),
        len(candidates),
        by_day_counts,
    )
    return result
