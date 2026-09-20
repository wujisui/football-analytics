from app.services.ah_market_structure import (
    FALLBACK_GIVING_ODD_MEDIAN,
    FALLBACK_WATER_DEADZONE,
    classify_ah_board,
    recommendation_from_ah_board,
    thresholds_from_quotes,
)
from app.services.ah_predictor import handicap_bundle_from_markets
from app.services.prediction import derive_prediction_leans, get_recommendation


def _odds(line: str, home: float, away: float) -> dict:
    return {
        "available": True,
        "match_winner": {"home": 3.33, "draw": 3.41, "away": 2.27},
        "asian_handicap": {"line": line, "home": home, "away": away},
        "goals_ou": {"line": 2.5, "home": 1.90, "away": 1.90},
    }


def test_percentile_deadzone_uses_p25_not_median() -> None:
    quotes = [(0.0, 1.90, 1.92)] * 10 + [( -0.5, 1.70, 2.20)] * 30
    payload = thresholds_from_quotes(quotes)
    assert payload["n_samples"] == 40
    assert payload["water_deadzone"] <= 0.08
    assert payload["water_deadzone"] < payload["abs_water_mean"]


def test_near_even_board_still_shows_the_cheaper_side() -> None:
    """死区只挡下注：赛前卡片照样给出最可能的一边，且三件套同向。"""
    odds = _odds("+0.25", 1.94, 1.96)
    stance = classify_ah_board(odds)
    assert stance is not None and stance.even
    rec = get_recommendation({"home": 0.29, "draw": 0.28, "away": 0.43}, odds=odds)
    assert rec == "胜"
    lean, _note = handicap_bundle_from_markets(odds, rec)
    assert lean == "让胜(+0.25)"
    leans = derive_prediction_leans(
        {"home": 0.29, "draw": 0.28, "away": 0.43},
        odds,
    )
    assert leans["recommendation"] == "胜"
    assert leans["handicap_lean"] == "让胜(+0.25)"
    assert "待分析" not in leans["score_hint"]


def test_level_board_follows_cheaper_side() -> None:
    odds = _odds("0", 1.81, 2.07)
    assert recommendation_from_ah_board(odds) == "胜"
    lean, _ = handicap_bundle_from_markets(odds, "胜")
    assert lean == "让胜(0)"


def test_giving_side_high_water_goes_underdog() -> None:
    odds = _odds("-0.5", 2.08, 1.85)
    stance = classify_ah_board(odds)
    assert stance is not None
    assert stance.follow_up is False
    assert stance.ah_pick == "让负"
    assert stance.result_choice == "away"
    assert stance.allow_moneyline is False
    assert get_recommendation({"home": 0.5, "draw": 0.25, "away": 0.25}, odds=odds) == "负"


def test_cheap_giving_side_can_allow_moneyline() -> None:
    odds = _odds("-0.25", 1.80, 2.10)
    stance = classify_ah_board(odds)
    assert stance is not None
    assert stance.follow_up is True
    assert stance.allow_moneyline is True
    assert stance.giving_odd < FALLBACK_GIVING_ODD_MEDIAN
    assert stance.water_deadzone == FALLBACK_WATER_DEADZONE
    assert recommendation_from_ah_board(odds) == "胜"


def test_home_label_does_not_break_deadzone() -> None:
    odds = _odds("-0.25", 1.95, 1.94)
    stance = classify_ah_board(odds)
    assert stance is not None
    assert stance.even
    assert stance.allow_moneyline is False
    assert recommendation_from_ah_board(odds) == "负"


def test_equal_water_has_no_direction_and_falls_back_to_1x2() -> None:
    odds = _odds("0", 1.93, 1.93)
    stance = classify_ah_board(odds)
    assert stance is not None
    assert stance.directional is False
    assert recommendation_from_ah_board(odds) is None
    # 无水位差 → 回到去水 1X2 盘面，仍然给出方向，不出现「观望」。
    assert get_recommendation({"home": 0.33, "draw": 0.33, "away": 0.34}, odds=odds)


def test_missing_1x2_board_falls_back_down_the_market_ladder() -> None:
    odds = {
        "available": True,
        "asian_handicap": {"line": "-0.5", "home": 2.06, "away": 1.85},
        "goals_ou": {"line": 2.5, "home": 1.75, "away": 2.10},
        "both_teams_score": {"home": 1.70, "away": 2.05},
    }
    leans = derive_prediction_leans({"home": 0.4, "draw": 0.3, "away": 0.3}, odds)
    assert leans["recommendation"] == "待分析"
    assert leans["handicap_lean"] == "让负(-0.5)"
    assert leans["goal_lean"] == "大(2.5)"
    assert leans["both_score_lean"] == "双进:是"
