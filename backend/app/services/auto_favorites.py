"""Auto-favorites: history-adjusted single-lean picks from catalog leagues."""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match_feature import MatchFeature
from app.models.pre_match_data import PreMatchData
from app.services.ah_features import (
    handicap_line_from_lean,
    handicap_pick_from_lean,
    outcome_settlement_units,
)
from app.services.prediction import (
    _odd_float,
    _parse_goal_lean,
    is_flat_prior,
    recommendation_outcomes,
    resolve_match_probabilities,
)
from app.services.probability_calibration import calibrate_probability

logger = logging.getLogger(__name__)

AUTO_PICK_LIMIT = 4
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
        by_day.setdefault(pick.match_day, []).append(pick)

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
    match_day: str
    score: float
    market: str
    lean: str
    raw_confidence: float
    confidence: float
    decimal_odd: float
    expected_return: float

@dataclass(frozen=True)
class MarketCandidate:
    market: str
    lean: str
    raw_confidence: float
    confidence: float
    decimal_odd: float
    implied_probability: float
    event_key: str
    # Share of the stake actually at risk; quarter and level boards refund part.
    stake_share: float = 1.0

    @property
    def expected_return(self) -> float:
        """Expected net return per unit stake."""
        return self.stake_share * (self.confidence * self.decimal_odd - 1.0)

    @property
    def ranking_score(self) -> float:
        """Kelly edge balances expected return against losing-stake risk."""
        profit = self.decimal_odd - 1.0
        if profit <= 0:
            return float("-inf")
        # Kelly is meaningful only for positive edges. The product still fills
        # the daily quota when none exist, so rank negative candidates by the
        # smallest expected loss instead of favoring long-shot payout ratios.
        if self.expected_return <= 0:
            return self.expected_return
        return self.expected_return / profit


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


def _handicap_line(lean: str, odds: dict[str, Any] | None) -> float | None:
    handicap = odds.get("asian_handicap") if isinstance(odds, dict) else None
    if isinstance(handicap, dict):
        try:
            return float(handicap.get("line"))
        except (TypeError, ValueError):
            pass
    return handicap_line_from_lean(lean)


def _ah_outcome_units(
    lean: str,
    odds: dict[str, Any] | None,
) -> dict[str, float] | None:
    pick = handicap_pick_from_lean(lean)
    line = _handicap_line(lean, odds)
    if pick is None or line is None:
        return None
    return outcome_settlement_units(line, pick)


def _ah_valuation(
    stored: PreMatchData,
    lean: str,
    odds: dict[str, Any] | None,
) -> tuple[float, float] | None:
    """(win share of the staked money, stake actually at risk) for small lines.

    ±0.25 refunds half the stake on a draw and ±0 refunds all of it, so the
    plain 概率 × 赔率 - 1 of a two-way bet overstates both the risk and the
    payout. Valuing these boards off the 1X2 probabilities also stops the
    handicap model from pricing an event the match-result model already owns.
    """
    units = _ah_outcome_units(lean, odds)
    if units is None:
        return None
    probs = resolve_match_probabilities(
        {
            "home": float(stored.home_win_prob or 0.0),
            "draw": float(stored.draw_prob or 0.0),
            "away": float(stored.away_win_prob or 0.0),
        },
        odds,
    )
    if is_flat_prior(probs):
        return None
    won = sum(float(probs[key]) * unit for key, unit in units.items() if unit > 0)
    lost = sum(float(probs[key]) * -unit for key, unit in units.items() if unit < 0)
    at_risk = won + lost
    if at_risk <= 0:
        return None
    return won / at_risk, at_risk


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
    # Asian handicap has no bettable draw selection: an exact-margin push
    # refunds the stake, so it must never become the daily main pick.
    if single == "让平":
        return 0.0, ""
    valuation = _ah_valuation(stored, lean, odds)
    if valuation is not None:
        return valuation[0], lean
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
    return 0.0, ""


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


def _market_implied_probability(
    market: str,
    lean: str,
    odds: dict[str, Any] | None,
) -> float:
    """Return bookmaker-margin-free probability for the selected outcome."""
    if not isinstance(odds, dict):
        return 0.0
    if market == "1x2":
        outcomes = recommendation_outcomes(lean)
        winner = odds.get("match_winner")
        if not outcomes or len(outcomes) != 1 or not isinstance(winner, dict):
            return 0.0
        prices = {
            key: _odd_float(winner.get(key)) for key in ("home", "draw", "away")
        }
        if any(price is None for price in prices.values()):
            return 0.0
        inverses = {key: 1.0 / float(price) for key, price in prices.items()}
        total = sum(inverses.values())
        return inverses[next(iter(outcomes))] / total if total > 0 else 0.0
    if market == "ah":
        handicap = odds.get("asian_handicap")
        if not isinstance(handicap, dict):
            return 0.0
        home_p, away_p = _implied_two_way(
            _odd_float(handicap.get("home")),
            _odd_float(handicap.get("away")),
        )
        return home_p if handicap_pick_from_lean(lean) == "让胜" else away_p
    if market == "ou":
        total = odds.get("goals_ou")
        parsed = _parse_goal_lean(lean)
        if not isinstance(total, dict) or parsed is None:
            return 0.0
        over_p, under_p = _implied_two_way(
            _odd_float(total.get("home")),
            _odd_float(total.get("away")),
        )
        return over_p if parsed[0] == "over" else under_p
    if market == "btts":
        both = odds.get("both_teams_score")
        if not isinstance(both, dict):
            return 0.0
        yes_p, no_p = _implied_two_way(
            _odd_float(both.get("home")),
            _odd_float(both.get("away")),
        )
        return yes_p if lean.endswith(("：是", ":是", "是")) else no_p
    return 0.0


def _candidate_event_key(
    market: str,
    lean: str,
    odds: dict[str, Any] | None,
) -> str:
    if market == "1x2":
        outcomes = recommendation_outcomes(lean)
        if outcomes and len(outcomes) == 1:
            return f"result:{next(iter(outcomes))}"
    if market == "ah":
        units = _ah_outcome_units(lean, odds)
        # Only a whole-stake board (±0.5) settles as one plain 1X2 event; a
        # quarter or level board keeps its own key because of the refunds.
        if units is not None and all(abs(unit) == 1.0 for unit in units.values()):
            winners = sorted(key for key, unit in units.items() if unit > 0)
            return "result:" + "_".join(winners)
    return f"{market}:{lean}"


def _risk_adjust_candidates(
    candidates: list[MarketCandidate],
) -> list[MarketCandidate]:
    """Share equivalent-event probabilities and shrink optimistic model edges."""
    by_event: dict[str, list[MarketCandidate]] = {}
    for candidate in candidates:
        by_event.setdefault(candidate.event_key, []).append(candidate)

    adjusted: list[MarketCandidate] = []
    for event_candidates in by_event.values():
        one_x_two = next(
            (item for item in event_candidates if item.market == "1x2"),
            None,
        )
        shared_confidence = (
            one_x_two.confidence
            if one_x_two is not None and len(event_candidates) > 1
            else None
        )
        market_anchor = sum(
            item.implied_probability for item in event_candidates
        ) / len(event_candidates)
        for candidate in event_candidates:
            confidence = (
                shared_confidence
                if shared_confidence is not None
                else candidate.confidence
            )
            # Market disagreement is evidence of uncertainty, not free edge.
            # Keep pessimistic estimates; halve only the optimistic gap.
            if market_anchor > 0 and confidence > market_anchor:
                confidence = (confidence + market_anchor) / 2.0
            adjusted.append(replace(candidate, confidence=confidence))
    return adjusted


def _market_candidates(
    stored: PreMatchData,
    *,
    odds: dict[str, Any] | None,
    feature: MatchFeature | None = None,
    calibration: dict[str, Any] | None = None,
) -> list[MarketCandidate]:
    scored = (
        ("1x2", _score_1x2(stored, odds)),
        ("ah", _score_handicap(stored, odds, feature)),
        ("ou", _score_ou(stored, odds)),
        ("btts", _score_btts(stored, odds)),
    )
    candidates: list[MarketCandidate] = []
    for market, (raw_confidence, lean) in scored:
        if not lean:
            continue
        decimal_odd = _market_decimal_odd(market, lean, odds)
        if decimal_odd is None:
            continue
        confidence = calibrate_probability(calibration, market, raw_confidence)
        valuation = _ah_valuation(stored, lean, odds) if market == "ah" else None
        candidates.append(
            MarketCandidate(
                market=market,
                lean=lean,
                raw_confidence=raw_confidence,
                confidence=confidence,
                decimal_odd=decimal_odd,
                implied_probability=_market_implied_probability(market, lean, odds),
                event_key=_candidate_event_key(market, lean, odds),
                stake_share=valuation[1] if valuation is not None else 1.0,
            )
        )
    return _risk_adjust_candidates(candidates)


async def sync_daily_auto_favorites(
    db: AsyncSession,
    *,
    user_id: str | None = None,
    limit: int = AUTO_PICK_LIMIT,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Replace guest-bucket ``source=auto`` tips via the recommendation pipeline."""
    from app.services.recommendation.pipeline import sync_daily_recommendations

    return await sync_daily_recommendations(
        db,
        user_id=user_id,
        limit=limit,
        now=now,
    )
