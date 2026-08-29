"""Risk-adjusted recommendation strategy for the daily-pick pipeline.

候选同时覆盖独赢与亚洲让球盘。排序不再只追命中率，也不直接追逐高赔率，而使用
``命中概率 × 净赔率 ** PAYOUT_EXPONENT``：凹效用保留收益奖励，同时抑制长赔方差。
EV 仍逐场落库供审计并用于同分决胜；当前模型没有稳定市场边际，因此不把正 EV
作为门槛。
"""

from __future__ import annotations

from typing import Any

from app.services.prediction import _odd_float

OUTCOMES = ("home", "draw", "away")
# 概率来自去水后的市场隐含赔率（``market_baseline``），即 ``p ≈ 1 / 赔率``，
# 于是基础分正比于 ``(赔率 - 1) ** e / 赔率``，极大值落在 ``赔率 = 1 / (1 - e)``。
# 保持 e = 0.5 让 2.00 附近仍可入选：降幂次会整体抬高净赔率 < 1 的低赔候选
# （0.52 的立方根比平方根高约 11%，0.93 只高约 1.2%），把各候选原始分压平，
# 历史 EMA 与联赛软权重因此更容易反超，反而挤掉高概率的 1.9 档候选。
# 要偏向命中率就调 ``MIN_DAILY_CONFIDENCE`` 下限，不要压这个幂次。
PAYOUT_EXPONENT = 0.5
# 平局本身概率低、方差大，即便偶尔算出正 EV 也会拖垮日推整体中奖率，
# 因此日推只在主客两侧里选，平局仍参与 EV 计算供审计与解释使用。
DAILY_PICK_OUTCOMES = ("home", "away")
MIN_DAILY_CONFIDENCE = 0.40
REASON_RISK_ADJUSTED_RETURN = "风险调整回报最高"
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


def risk_adjusted_return_score(
    calibrated_prob: float,
    decimal_odd: float,
) -> float:
    """Balance hit probability and payout without blindly chasing long odds.

    ``net payout ** PAYOUT_EXPONENT`` is a concave utility: moving from 1.60 to
    1.95 is rewarded more than moving from 2.60 to 2.95. The exponent also fixes
    where the ranking peaks against market-implied probabilities — see the
    module-level note on ``PAYOUT_EXPONENT``.

    Quarter/level boards need no extra term here: a partial refund already
    raises ``calibrated_prob`` (it is conditional on the stake resolving) and
    already lowers ``decimal_odd``. Scaling by the at-risk share on top of that
    would penalise refund protection a second time and bias the ranking toward
    higher-variance full-stake bets.
    """
    probability = max(0.0, min(1.0, float(calibrated_prob)))
    net_payout = max(0.0, float(decimal_odd) - 1.0)
    return probability * net_payout**PAYOUT_EXPONENT


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
    """Pick the best risk-adjusted home/away outcome; EV rides along for audit."""
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

    prices = _match_winner_odds(odds) or {}
    eligible = [
        outcome
        for outcome in DAILY_PICK_OUTCOMES
        if probs[outcome] >= MIN_DAILY_CONFIDENCE
    ]
    if not eligible:
        eligible = list(DAILY_PICK_OUTCOMES)
    best_outcome = max(
        eligible,
        key=lambda outcome: (
            risk_adjusted_return_score(probs[outcome], prices[outcome]),
            evs[outcome],
            probs[outcome],
        ),
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
        "reason": REASON_RISK_ADJUSTED_RETURN,
    }
