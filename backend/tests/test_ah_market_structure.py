from app.services.ah_market_structure import (
    FALLBACK_GIVING_ODD_MEDIAN,
    FALLBACK_WATER_DEADZONE,
    classify_ah_board,
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
    """死区只挡下注：赛前卡片照样给出让球方向，且让球与比分同向。"""
    odds = _odds("+0.25", 1.94, 1.96)
    stance = classify_ah_board(odds)
    assert stance is not None and stance.even
    leans = derive_prediction_leans(
        {"home": 0.29, "draw": 0.28, "away": 0.43},
        odds,
    )
    assert leans["handicap_lean"] == "主+0.25"
    assert "待分析" not in leans["score_hint"]


def test_level_board_follows_cheaper_side() -> None:
    odds = _odds("0", 1.81, 2.07)
    lean, _ = handicap_bundle_from_markets(odds, "主胜")
    assert lean == "主0"


def test_giving_side_high_water_goes_underdog() -> None:
    odds = _odds("-0.5", 2.08, 1.85)
    stance = classify_ah_board(odds)
    assert stance is not None
    assert stance.follow_up is False
    assert stance.ah_pick == "让负"
    assert stance.result_choice == "away"
    assert stance.allow_moneyline is False


def test_cheap_giving_side_can_allow_moneyline() -> None:
    odds = _odds("-0.25", 1.80, 2.10)
    stance = classify_ah_board(odds)
    assert stance is not None
    assert stance.follow_up is True
    assert stance.allow_moneyline is True
    assert stance.giving_odd < FALLBACK_GIVING_ODD_MEDIAN
    assert stance.water_deadzone == FALLBACK_WATER_DEADZONE


def test_home_label_does_not_break_deadzone() -> None:
    odds = _odds("-0.25", 1.95, 1.94)
    stance = classify_ah_board(odds)
    assert stance is not None
    assert stance.even
    assert stance.allow_moneyline is False


def test_ah_board_never_overrides_the_1x2_board() -> None:
    """穿盘方向不是胜负方向：受让方低水包含打平，读成客胜就是买三路最低概率。

    复现 2026-09-20：主让 -0.5、主 2.06 / 客 1.85，1X2 去水后主胜 48% 客胜 21%，
    旧口径据此推「客胜」。当日 63 场里有 17 场这样逆着热门下注，胜平负掉到
    41.3%、比分 0/63；同期跟随热门 55.0% 对逆热门 33.3%。
    """
    odds = _odds("-0.5", 2.06, 1.85)
    odds["match_winner"] = {"home": 2.06, "draw": 3.08, "away": 4.48}
    stance = classify_ah_board(odds)
    assert stance is not None and stance.result_choice == "away"

    # 让球行照旧跟水位买受让方，但胜平负必须回到去水 1X2 盘面。
    assert handicap_bundle_from_markets(odds, "主胜")[0] == "客+0.5"
    assert get_recommendation(
        {"home": 0.47, "draw": 0.31, "away": 0.22}, odds=odds
    ) == "主胜"


def test_deep_board_is_not_a_1x2_direction() -> None:
    """让 1 球以上时受让侧水位低只说明热门吃不下盘口，不说明谁赢球。

    复现曼城让 1.5 打桑德兰：受让侧 1.80 更低，旧口径把它读成「客胜」，卡片变成
    「客胜 · 客+1.5 · 比分 0-4」。深盘应交回去水 1X2 盘面，读出主胜。
    """
    odds = _odds("-1.5", 2.00, 1.80)
    odds["match_winner"] = {"home": 1.22, "draw": 6.80, "away": 13.0}
    stance = classify_ah_board(odds)
    assert stance is not None and stance.directional and stance.is_deep
    assert stance.result_choice == "away"
    assert get_recommendation({"home": 0.78, "draw": 0.13, "away": 0.09}, odds=odds) == (
        "主胜"
    )


def test_deep_board_handicap_takes_the_giving_side() -> None:
    """深盘让球侧取让球方；浅盘仍跟水位，不受影响。"""
    deep = _odds("-1.5", 2.00, 1.80)
    lean, note = handicap_bundle_from_markets(deep, "主胜")
    assert lean == "主-1.5"
    assert "输一球以内" in note

    shallow = _odds("-0.5", 2.08, 1.85)
    assert handicap_bundle_from_markets(shallow, "客胜")[0] == "客+0.5"


def test_reference_score_never_contradicts_the_handicap_row() -> None:
    """比分是推导值，让球是市场读数：打架时让比分让步（2-0 而不是 1-0/0-4）。"""
    odds = _odds("-1.5", 2.00, 1.80)
    odds["match_winner"] = {"home": 1.22, "draw": 6.80, "away": 13.0}
    odds["goals_ou"] = {"line": "3", "home": 2.05, "away": 1.75}
    odds["both_teams_score"] = {"home": 2.10, "away": 1.70}

    leans = derive_prediction_leans({"home": 0.78, "draw": 0.13, "away": 0.09}, odds)

    assert leans["recommendation"] == "主胜"
    assert leans["handicap_lean"] == "主-1.5"
    assert leans["score_hint"] == "比分:2-0"
    assert leans["goal_lean"] == "小(3)"
    assert leans["both_score_lean"] == "双进:否"


def test_missing_1x2_board_falls_back_down_the_market_ladder() -> None:
    odds = {
        "available": True,
        "asian_handicap": {"line": "-0.5", "home": 2.06, "away": 1.85},
        "goals_ou": {"line": 2.5, "home": 1.75, "away": 2.10},
        "both_teams_score": {"home": 1.70, "away": 2.05},
    }
    leans = derive_prediction_leans({"home": 0.4, "draw": 0.3, "away": 0.3}, odds)
    assert leans["recommendation"] == "待分析"
    assert leans["handicap_lean"] == "客+0.5"
    assert leans["goal_lean"] == "大(2.5)"
    assert leans["both_score_lean"] == "双进:是"
