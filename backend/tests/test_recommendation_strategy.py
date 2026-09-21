"""Hit-rate-first recommendation strategy (no official API calls)."""

from app.services.recommendation.strategy import (
    REASON_NO_MARKET,
    REASON_LOW_CONFIDENCE,
    REASON_TOP_PROBABILITY,
    decide_match,
    expected_value,
    pick_ranking_score,
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


def test_ranking_never_peaks_at_the_coin_flip() -> None:
    """排序分必须随概率单调上升，不能在 p = 0.5 见顶。

    旧式 ``概率 × 净赔率 ** 0.5`` 在概率来自去水市场（``p ≈ 1/赔率``）时约成
    ``√(p(1-p))``，极大值恰在 p = 0.5，于是每一层都系统性地挑最像抛硬币的盘。
    实测 542 条浅盘让球按所投一侧赔率分桶：≤1.80 命中 69.8%、平均分 0.4780，
    1.90~1.95 命中 49.0%、平均分 0.4879——命中率单调降、打分单调升。
    """
    fair = {odd: pick_ranking_score(1 / odd) for odd in (1.15, 1.50, 2.00, 4.00)}
    assert fair[1.15] == max(fair.values())
    assert fair[1.15] > fair[1.50] > fair[2.00] > fair[4.00]


def test_payout_no_longer_breaks_a_probability_tie() -> None:
    """赔率只进 EV 审计，不得把低概率候选抬到高概率候选之上。"""
    assert pick_ranking_score(0.50) == pick_ranking_score(0.50)
    assert pick_ranking_score(0.50) > pick_ranking_score(0.25)


def test_quarter_ball_refund_is_not_penalised_twice() -> None:
    """同一方向下，退半的 -0.25 应压过全输的独赢。

    主胜 46.1% / 平 27.0% 时，让胜(-0.25) 的条件命中率为 53.3%；独赢胜 46.1%。
    退半的好处已经计入条件命中率，排序分不得再乘 at_risk 罚第二次。
    """
    assert pick_ranking_score(0.5326) > pick_ranking_score(0.4608)


def test_picks_the_most_likely_side() -> None:
    payload = decide_match(
        match_id=1001,
        calibration=_calibration(),
        odds=_odds(),
    )
    assert payload["recommended_choice"] == "home"
    assert payload["reason"] == REASON_TOP_PROBABILITY
    assert abs(payload["confidence"] - 0.55) < 1e-9
    # EV rides along for audit even though it did not drive the choice.
    assert abs(payload["ev"] - 0.10) < 1e-9


def test_negative_ev_still_produces_a_pick() -> None:
    """负 EV 不是拒绝理由：概率由所投盘口去水而来，EV 恒为负抽水。

    ``EV > 0`` 曾短暂作为硬闸，但 ``p = (1/赔率)/超额`` 使 ``EV = 1/超额 − 1``
    恒为负，只有 Platt 截距能把它抬过零；实测只有 ``ou`` 校准器截距够大，日推
    因此塌成全是大小球。EV 只落库审计。
    """
    payload = decide_match(
        match_id=1002,
        calibration=_calibration(home=0.45, draw=0.14, away=0.41),
        odds=_odds(home=2.0, draw=6.0, away=2.3),
    )
    assert payload["recommended_choice"] == "home"
    assert payload["ev"] < 0.0
    assert payload["reason"] == REASON_TOP_PROBABILITY


def test_confidence_below_floor_is_rejected() -> None:
    """主客两侧都低于 40% 时不推荐，这是唯一的置信度门槛。"""
    payload = decide_match(
        match_id=1006,
        calibration=_calibration(home=0.34, draw=0.32, away=0.34),
        odds=_odds(home=2.20, draw=3.40, away=4.50),
    )
    assert payload["recommended_choice"] is None
    assert payload["confidence"] == 0.0
    assert payload["reason"] == REASON_LOW_CONFIDENCE


def test_draw_is_never_picked() -> None:
    """平局概率最高时也不进日推，只在主客两侧里选。"""
    payload = decide_match(
        match_id=1004,
        calibration=_calibration(home=0.30, draw=0.45, away=0.25),
        odds=_odds(),
    )
    assert payload["recommended_choice"] is None
    assert payload["reason"] == REASON_LOW_CONFIDENCE


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
