"""EV-maximizing 1X2 recommendation strategy for the recommendation pipeline."""

from __future__ import annotations

from typing import Any

from app.services.prediction import _odd_float

OUTCOMES = ("home", "draw", "away")
REASON_POSITIVE_EV = "EV最大"
REASON_NO_POSITIVE_EV = "无正EV，不推荐"


def _match_winner_odds(odds: dict[str, Any] | None) -> dict[str, float] | None:
    if not isinstance(odds, dict) or not odds.get("available"):
        return None
    mw = odds.get("match_winner")
    if not isinstance(mw, dict):
        return None
    home = _odd_float(mw.get("home"))
    draw = _odd_float(mw.get("draw"))
    away = _odd_float(mw.get("away"))
    if home is None or draw is None or away is None:
        return None
    return {"home": home, "draw": draw, "away": away}


def _calibrated_probs(calibration: dict[str, Any]) -> dict[str, float]:
    return {
        "home": float(calibration.get("calibrated_home_prob", 0.0)),
        "draw": float(calibration.get("calibrated_draw_prob", 0.0)),
        "away": float(calibration.get("calibrated_away_prob", 0.0)),
    }


def expected_value(decimal_odd: float, calibrated_prob: float) -> float:
    """Net expected return per unit stake: ``odd * prob - 1``."""
    return float(decimal_odd) * float(calibrated_prob) - 1.0


def compute_outcome_evs(
    calibration: dict[str, Any],
    odds: dict[str, Any] | None,
) -> dict[str, float] | None:
    """Return per-outcome EV from calibration output and match-winner odds."""
    prices = _match_winner_odds(odds)
    if prices is None:
        return None
    probs = _calibrated_probs(calibration)
    return {
        outcome: expected_value(prices[outcome], probs[outcome])
        for outcome in OUTCOMES
    }


def decide_match(
    *,
    match_id: int,
    calibration: dict[str, Any],
    odds: dict[str, Any] | None,
) -> dict[str, Any]:
    """Pick the highest positive-EV 1X2 outcome, or skip when none exist."""
    resolved_match_id = int(calibration.get("match_id", match_id))
    evs = compute_outcome_evs(calibration, odds)
    probs = _calibrated_probs(calibration)

    if evs is None:
        return {
            "match_id": resolved_match_id,
            "recommended_choice": None,
            "ev": 0.0,
            "confidence": 0.0,
            "reason": REASON_NO_POSITIVE_EV,
        }

    best_outcome = max(OUTCOMES, key=lambda outcome: (evs[outcome], probs[outcome]))
    best_ev = evs[best_outcome]

    if best_ev <= 0.0:
        return {
            "match_id": resolved_match_id,
            "recommended_choice": None,
            "ev": float(best_ev),
            "confidence": 0.0,
            "reason": REASON_NO_POSITIVE_EV,
        }

    confidence = float(probs[best_outcome])
    return {
        "match_id": resolved_match_id,
        "recommended_choice": best_outcome,
        "ev": float(best_ev),
        "confidence": confidence,
        "reason": REASON_POSITIVE_EV,
    }
