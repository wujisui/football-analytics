"""Risk-adjusted recommendation strategy (no official API calls)."""

from app.services.recommendation import strategy
from app.services.recommendation.strategy import (
    REASON_NO_MARKET,
    REASON_RISK_ADJUSTED_RETURN,
    decide_match,
    expected_value,
    risk_adjusted_return_score,
)


def _calibration(
    *,
    match_id: int = 1001,
    home: float = 0.55,
    draw: float = 0.25,
    away: float = 0.20,
    reliability: float = 0.8,
) -> dict:
    return {
        "match_id": match_id,
        "calibrated_home_prob": home,
        "calibrated_draw_prob": draw,
        "calibrated_away_prob": away,
        "reliability": reliability,
        "sample_size": 120,
        "calibration_bias": {"home": 0.0, "draw": 0.0, "away": 0.0},
    }


def _odds(home: float = 2.0, draw: float = 3.4, away: float = 4.0) -> dict:
    return {
        "available": True,
        "match_winner": {"home": home, "draw": draw, "away": away},
    }


def test_expected_value_formula() -> None:
    assert abs(expected_value(2.0, 0.55) - 0.10) < 1e-9


def test_risk_score_keeps_even_money_reachable() -> None:
    """2.00 附近必须留在可入选范围，不能被幂次人为封顶。

    概率来自去水市场（``p ≈ 1 / 赔率``）时下列候选 EV 全为 0，唯一差别是水位。
    ``e = 0.5`` 的极大值落在 2.00；一旦压低幂次，净赔率 < 1 的低赔候选会被整体
    抬分并压平原始分差，历史权重就能挤掉高概率的 1.9 档候选。命中率偏好不靠压这个
    幂次：让球两侧走 ``pipeline._to_ah_picks`` 的同盘命中率闸，独赢走
    ``MIN_DAILY_CONFIDENCE`` 下限。
    """
    fair = {
        1.15: risk_adjusted_return_score(1 / 1.15, 1.15),
        1.50: risk_adjusted_return_score(1 / 1.50, 1.50),
        2.00: risk_adjusted_return_score(1 / 2.00, 2.00),
        4.00: risk_adjusted_return_score(1 / 4.00, 4.00),
    }
    assert fair[2.00] == max(fair.values())
    assert fair[2.00] > fair[1.50] > fair[1.15]
    assert fair[2.00] > fair[4.00]


def test_low_exponent_would_flatten_the_score_gap_across_odds() -> None:
    """记录压幂次的副作用：原始分差被压平，历史权重更容易反超。

    62% @1.93 与 63% @1.52 两个真实候选，``e = 0.5`` 下原始分相差约 1.31 倍，
    ``e = 1/3`` 下只剩约 1.19 倍。实际历史乘数（约 0.9）足以在后者翻盘，
    这正是 1.93 高概率候选掉出四强的机制。
    """
    high_odds, low_odds = (0.620, 1.93), (0.632, 1.52)
    wide = risk_adjusted_return_score(*high_odds) / risk_adjusted_return_score(*low_odds)

    original = strategy.PAYOUT_EXPONENT
    try:
        strategy.PAYOUT_EXPONENT = 1.0 / 3.0
        narrow = risk_adjusted_return_score(*high_odds) / risk_adjusted_return_score(
            *low_odds
        )
    finally:
        strategy.PAYOUT_EXPONENT = original

    assert wide > narrow > 1.0
    assert wide > 1.30
    assert narrow < 1.20


def test_risk_score_still_rewards_payout_at_equal_probability() -> None:
    assert risk_adjusted_return_score(0.50, 2.2) > risk_adjusted_return_score(0.50, 2.0)
    assert risk_adjusted_return_score(0.50, 2.0) > risk_adjusted_return_score(0.25, 4.0)


def test_quarter_ball_refund_is_not_penalised_twice() -> None:
    """同一方向下，退半的 -0.25 应压过全输的独赢。

    主胜 46.1% / 平 27.0% 时，让胜(-0.25) 的条件命中率为 53.3%、赔率 1.83；
    独赢胜命中率 46.1%、赔率 2.10。前者每单位本金期望更优，综合分必须同向。
    """
    assert risk_adjusted_return_score(0.5326, 1.83) > risk_adjusted_return_score(
        0.4608, 2.10
    )


def test_picks_the_best_risk_adjusted_side() -> None:
    payload = decide_match(
        match_id=1001,
        calibration=_calibration(),
        odds=_odds(),
    )
    assert payload["recommended_choice"] == "home"
    assert payload["reason"] == REASON_RISK_ADJUSTED_RETURN
    assert abs(payload["confidence"] - 0.55) < 1e-9
    # EV rides along for audit even though it did not drive the choice.
    assert abs(payload["ev"] - 0.10) < 1e-9


def test_negative_ev_still_produces_a_payout_aware_pick() -> None:
    """EV 为负仍可入池；较高赔率在风险调整后可以胜过单纯高置信度。"""
    payload = decide_match(
        match_id=1002,
        calibration=_calibration(home=0.45, draw=0.14, away=0.41),
        odds=_odds(home=2.0, draw=6.0, away=2.3),
    )
    assert payload["recommended_choice"] == "away"
    assert payload["ev"] < 0.0
    assert abs(payload["confidence"] - 0.41) < 1e-9


def test_draw_is_never_picked_even_when_most_likely() -> None:
    payload = decide_match(
        match_id=1004,
        calibration=_calibration(home=0.30, draw=0.45, away=0.25),
        odds=_odds(),
    )
    assert payload["recommended_choice"] == "away"
    assert abs(payload["confidence"] - 0.25) < 1e-9


def test_confidence_shrinks_on_low_reliability_leagues() -> None:
    payload = decide_match(
        match_id=1005,
        calibration=_calibration(),
        odds=_odds(),
        features={"league_reliability": 0.4},
    )
    assert abs(payload["confidence"] - 0.55 * (0.75 + 0.25 * 0.4)) < 1e-9


def test_missing_odds_is_not_recommended() -> None:
    payload = decide_match(
        match_id=1003,
        calibration=_calibration(),
        odds=None,
    )
    assert payload["recommended_choice"] is None
    assert payload["reason"] == REASON_NO_MARKET
