"""Confidence-ranked 1X2 recommendation strategy for the recommendation pipeline.

日推按「模型最有把握」选场，不按正期望选场：当前 1X2 模型跑不赢市场
（`inference_mode=market_baseline`），校准概率等于市场去水概率，期望收益恒等于
负的抽水，正期望在数学上不可能出现。EV 仍然逐场算出来落库供审计，但不参与选优，
等哪天某个玩法真的跑赢市场再把它提回门槛。
"""

from __future__ import annotations

from typing import Any

from app.services.prediction import _odd_float

OUTCOMES = ("home", "draw", "away")
# 平局本身概率低、方差大，即便偶尔算出正 EV 也会拖垮日推整体中奖率，
# 因此日推只在主客两侧里选，平局仍参与 EV 计算供审计与解释使用。
DAILY_PICK_OUTCOMES = ("home", "away")
REASON_TOP_CONFIDENCE = "置信度最高"
REASON_NO_MARKET = "缺少可用赔率，不推荐"


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
    features: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Pick the highest-confidence home/away outcome; EV rides along for audit."""
    resolved_match_id = int(calibration.get("match_id", match_id))
    evs = compute_outcome_evs(calibration, odds)
    probs = _calibrated_probs(calibration)

    if evs is None:
        return {
            "match_id": resolved_match_id,
            "recommended_choice": None,
            "ev": 0.0,
            "confidence": 0.0,
            "reason": REASON_NO_MARKET,
        }

    best_outcome = max(
        DAILY_PICK_OUTCOMES, key=lambda outcome: (probs[outcome], evs[outcome])
    )
    confidence = float(probs[best_outcome])
    if isinstance(features, dict):
        reliability = float(features.get("league_reliability") or 0.0)
        if reliability > 0.0:
            confidence = min(1.0, confidence * (0.75 + 0.25 * reliability))
    return {
        "match_id": resolved_match_id,
        "recommended_choice": best_outcome,
        "ev": float(evs[best_outcome]),
        "confidence": confidence,
        "reason": REASON_TOP_CONFIDENCE,
    }
