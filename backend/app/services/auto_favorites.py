"""Auto-favorites: top confident single-lean picks from catalog leagues."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.favorite_fixture import (
    FAVORITE_SOURCE_AUTO,
    FAVORITE_SOURCE_MANUAL,
    FavoriteFixture,
)
from app.models.fixture import Fixture
from app.models.match_feature import MatchFeature
from app.models.pre_match_data import PreMatchData
from app.services.ah_features import handicap_pick_from_lean
from app.services.data_cleanup import record_has_algorithm_recommendation
from app.services.prediction import (
    _odd_float,
    _parse_goal_lean,
    _parse_score_hint,
    is_flat_prior,
    recommendation_outcomes,
    resolve_match_probabilities,
)
from app.services.prematch_package import package_from_record, rehydrate_odds_markets
from app.services.results_capture import prematch_list_clause
from app.services.user_scope import owner_is

logger = logging.getLogger(__name__)

AUTO_PICK_LIMIT = 4
# Soft floor only — always fill up to AUTO_PICK_LIMIT when enough fixtures exist.
MIN_CONFIDENCE = 0.01


@dataclass(frozen=True)
class AutoPickCandidate:
    fixture_id: int
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


def _score_exact(
    stored: PreMatchData,
    odds: dict[str, Any] | None,
) -> tuple[float, str]:
    lean = (stored.score_hint or "").strip()
    scores = _parse_score_hint(lean)
    # Single exact score only; skip multi-score hints like 2-1 / 1-1.
    if len(scores) != 1:
        return 0.0, ""
    target = scores[0]
    if not isinstance(odds, dict):
        return 0.0, ""
    bookmakers = odds.get("bookmakers")
    if not isinstance(bookmakers, list):
        return 0.0, ""
    for book in bookmakers:
        if not isinstance(book, dict):
            continue
        if str(book.get("bet") or "") not in {"Exact Score", "Correct Score"}:
            continue
        values = book.get("values")
        if not isinstance(values, list):
            continue
        for row in values:
            if not isinstance(row, dict):
                continue
            label = str(row.get("label") or "")
            match = re.match(r"^\s*(\d+)\s*[-:]\s*(\d+)\s*$", label)
            if not match:
                continue
            if (int(match.group(1)), int(match.group(2))) != target:
                continue
            odd = _odd_float(row.get("odd"))
            if odd is None or odd <= 1:
                return 0.0, ""
            # Convert long odds into a soft confidence: 1/odd, capped.
            return min(1.0 / odd, 0.45), lean
    return 0.0, ""


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

    if market == "score":
        scores = _parse_score_hint(lean)
        if len(scores) != 1:
            return None
        target = scores[0]
        for book in odds.get("bookmakers") or []:
            if not isinstance(book, dict):
                continue
            if str(book.get("bet") or "") not in {"Exact Score", "Correct Score"}:
                continue
            for row in book.get("values") or []:
                if not isinstance(row, dict):
                    continue
                match = re.match(r"^\s*(\d+)\s*[-:]\s*(\d+)\s*$", str(row.get("label") or ""))
                if match and (int(match.group(1)), int(match.group(2))) == target:
                    return _odd_float(row.get("odd"))
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
        ("score", _score_exact(stored, odds)),
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


def rank_auto_pick_candidates(
    rows: list[tuple[Fixture, PreMatchData, MatchFeature | None]],
    *,
    limit: int = AUTO_PICK_LIMIT,
    min_confidence: float = MIN_CONFIDENCE,
) -> list[AutoPickCandidate]:
    """Rank single-lean picks and always fill up to ``limit`` when possible.

    Odds/EV are used only for relative ordering (prefer better value). Hard
    gates that emptied the slate are intentionally not applied — product needs
    four daily tips whenever enough catalog prematch fixtures exist.
    """
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
        ranked.append(
            AutoPickCandidate(
                fixture_id=fixture.id,
                kickoff=fixture.date,
                score=best.ranking_score,
                market=best.market,
                lean=best.lean,
                confidence=best.confidence,
                decimal_odd=best.decimal_odd,
                expected_return=best.expected_return,
            )
        )
    ranked.sort(key=lambda item: (-item.score, item.kickoff, item.fixture_id))
    return ranked[: max(0, limit)]


async def sync_daily_auto_favorites(
    db: AsyncSession,
    *,
    user_id: str | None = None,
    limit: int = AUTO_PICK_LIMIT,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Replace ``source=auto`` favorites with top single-lean catalog picks.

    Always targets ``limit`` picks (default 4). Odds/EV only reorder candidates;
    empty slate is allowed only when fewer than ``limit`` scorable fixtures exist.
    Manual favorites are never touched.
    """
    settings = get_settings()
    catalog_ids = list(settings.LEAGUE_IDS.values())
    current = now or _utc_now()

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

    candidates = rank_auto_pick_candidates(
        list(by_fixture.values()),
        limit=max(limit * 3, limit),
    )

    manual_ids = {
        int(row[0])
        for row in (
            await db.execute(
                select(FavoriteFixture.fixture_id).where(
                    owner_is(FavoriteFixture.user_id, user_id),
                    FavoriteFixture.source == FAVORITE_SOURCE_MANUAL,
                )
            )
        ).all()
    }

    selected: list[AutoPickCandidate] = []
    for candidate in candidates:
        if candidate.fixture_id in manual_ids:
            continue
        selected.append(candidate)
        if len(selected) >= limit:
            break

    await db.execute(
        delete(FavoriteFixture).where(
            owner_is(FavoriteFixture.user_id, user_id),
            FavoriteFixture.source == FAVORITE_SOURCE_AUTO,
        )
    )

    saved_at = _utc_now()
    for candidate in selected:
        db.add(
            FavoriteFixture(
                fixture_id=candidate.fixture_id,
                user_id=user_id,
                source=FAVORITE_SOURCE_AUTO,
                auto_market=candidate.market,
                auto_lean=candidate.lean,
                saved_at=saved_at,
            )
        )
    await db.commit()

    tz_name = settings.SCHEDULER_TIMEZONE
    try:
        local_day = datetime.now(ZoneInfo(tz_name)).date().isoformat()
    except Exception:
        local_day = saved_at.date().isoformat()

    result = {
        "day": local_day,
        "candidates": len(candidates),
        "selected": [
            {
                "fixture_id": item.fixture_id,
                "score": round(item.score, 4),
                "market": item.market,
                "lean": item.lean,
                "confidence": round(item.confidence, 4),
                "decimal_odd": round(item.decimal_odd, 3),
                "expected_return": round(item.expected_return, 4),
            }
            for item in selected
        ],
        "skipped_manual": sorted(
            {
                item.fixture_id
                for item in candidates[:limit]
                if item.fixture_id in manual_ids
            }
        ),
    }
    logger.info(
        "Auto-favorites day=%s selected=%s candidates=%s",
        local_day,
        len(selected),
        len(candidates),
    )
    return result
