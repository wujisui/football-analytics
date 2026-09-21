"""Positive-value recommendation strategy for the daily-pick pipeline.

候选必须先过 ``EV > 0`` 硬门槛；层内再按校准命中概率排序。没有独立市场边际时
宁可不推荐，禁止用“覆盖概率过半”或“负 EV 中亏损较小”补满名额。
"""

from __future__ import annotations

from typing import Any

from app.services.prediction import _odd_float

OUTCOMES = ("home", "draw", "away")
# 平局本身概率低、方差大，即便偶尔算出正 EV 也会拖垮日推整体中奖率，
# 因此日推只在主客两侧里选，平局仍参与 EV 计算供审计与解释使用。
DAILY_PICK_OUTCOMES = ("home", "away")
MIN_DAILY_CONFIDENCE = 0.40
REASON_POSITIVE_VALUE = "正期望价值候选"
REASON_NO_MARKET = "缺少可用赔率，不推荐"
REASON_NO_VALUE = "所有可选方向EV均不大于0，不推荐"


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


def pick_ranking_score(calibrated_prob: float) -> float:
    """层内排序分：就是校准命中概率本身，赔率不参与。

    这里曾经是 ``概率 × 净赔率 ** 0.5``。因为概率全部来自去水市场（``p ≈ 1/赔率``），
    那个式子会约掉成 ``√(p(1-p))``——**极大值落在 p = 0.5**，也就是说它在每一层里
    系统性地挑最接近抛硬币的盘。实测 542 条浅盘让球样本，按所投一侧赔率分桶：

        ≤1.80（水位差大）  69.8% (37/53)   平均分 0.4780
        1.80~1.90          55.9% (246/440) 平均分 0.4846
        1.90~1.95（近平水） 49.0% (24/49)   平均分 0.4879

    命中率单调降，打分单调升，完全反相关；取前 25% 时旧式 55.6%、纯概率 60.0%。

    旧注释担心「压低幂次会压平原始分差、让历史 EMA 更容易反超」，那只在跨赔率档
    比较时成立。``_daily_pick_rank_key`` 先按层排序，层内赔率挤在 1.8~1.95，
    ``(赔率-1) ** 0.5`` 近乎常数：同一批样本里 e=0.5 的基础分极差只有 7.3%，
    e=0 反而有 15.0%。压平分差的恰恰是旧幂次。

    赔率仍逐场算进 ``ev`` 落库供审计与同分决胜，只是不再决定谁进当日四个坑。
    """
    return max(0.0, min(1.0, float(calibrated_prob)))


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
    """Pick the likeliest positive-EV home/away outcome, otherwise abstain."""
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

    eligible = [
        outcome
        for outcome in DAILY_PICK_OUTCOMES
        if probs[outcome] >= MIN_DAILY_CONFIDENCE and evs[outcome] > 0.0
    ]
    if not eligible:
        best_ev = max(evs[outcome] for outcome in DAILY_PICK_OUTCOMES)
        return {
            "match_id": resolved_match_id,
            "recommended_choice": None,
            "ev": float(best_ev),
            "confidence": 0.0,
            "reason": REASON_NO_VALUE,
        }
    # 正 EV 闸之后概率优先，EV 仅作同分决胜。
    best_outcome = max(
        eligible,
        key=lambda outcome: (pick_ranking_score(probs[outcome]), evs[outcome]),
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
        "reason": REASON_POSITIVE_VALUE,
    }
