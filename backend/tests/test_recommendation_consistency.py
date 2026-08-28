"""日推方向、让球表达与比分候选的自洽闸。"""

from app.services.recommendation.consistency import validate_pick_consistency


def _odds(*, line: str = "-0.25", home: float = 1.83, away: float = 2.09) -> dict:
    return {
        "available": True,
        "match_winner": {"home": 2.1, "draw": 3.6, "away": 3.5},
        "asian_handicap": {"line": line, "home": home, "away": away},
    }


def _probs(home: float = 0.456, draw: float = 0.279, away: float = 0.265) -> dict:
    return {"home": home, "draw": draw, "away": away}


def test_draw_pick_never_enters_the_daily_four() -> None:
    """平局概率低、方差大，不管盘口能不能表达，都不进日推。"""
    for line in ("-0.25", "0", "-0.75"):
        decision = validate_pick_consistency(
            daily_lean="平",
            probs=_probs(),
            goal_lean="大(2.5)",
            both_score_lean="双进:是",
            odds=_odds(line=line),
        )
        assert decision.is_consistent is False
        assert "平局" in decision.conflict_detail


def test_home_pick_keeps_the_home_side_and_a_home_win_score() -> None:
    decision = validate_pick_consistency(
        daily_lean="胜",
        probs=_probs(),
        goal_lean="大(2.5)",
        both_score_lean="双进:是",
        odds=_odds(line="-0.5", home=1.90, away=1.98),
    )
    assert decision.is_consistent is True
    assert decision.handicap_lean == "让胜(-0.5)"
    home_goals, away_goals = (decision.score_hint or "").split(":")[1].split("-")
    assert int(home_goals) > int(away_goals)


def test_level_ball_keeps_a_bettable_side_with_a_push_downside() -> None:
    """让0也是让球盘：主胜配让0胜，赛果打平走水退本，不算输。"""
    decision = validate_pick_consistency(
        daily_lean="胜",
        probs=_probs(),
        goal_lean="大(2.5)",
        both_score_lean="双进:是",
        odds=_odds(line="0", home=1.95, away=1.95),
    )
    assert decision.is_consistent is True
    assert decision.handicap_lean == "让胜(0)"


def test_home_pick_rejected_on_a_board_deeper_than_one_goal() -> None:
    decision = validate_pick_consistency(
        daily_lean="胜",
        probs=_probs(),
        goal_lean="大(2.5)",
        both_score_lean="双进:是",
        odds=_odds(line="-1.5", home=2.00, away=1.88),
    )
    assert decision.is_consistent is False
    assert "主让1球" in decision.conflict_detail


def test_market_water_no_longer_blocks_the_pick_direction() -> None:
    """闸门表达日推方向，不再因盘口偏向另一边而淘汰。"""
    decision = validate_pick_consistency(
        daily_lean="负",
        probs=_probs(),
        goal_lean="小(2.5)",
        both_score_lean="双进:否",
        odds=_odds(line="-0.25", home=1.70, away=2.25),
    )
    assert decision.is_consistent is True
    assert decision.handicap_lean == "让负(-0.25)"


def test_pick_rejected_when_over_under_lean_is_unavailable() -> None:
    decision = validate_pick_consistency(
        daily_lean="胜",
        probs=_probs(),
        goal_lean="大小：待分析",
        both_score_lean="双进:待分析",
        odds=_odds(),
    )
    assert decision.is_consistent is False
    assert "比分" in decision.conflict_detail


def test_board_free_fixture_stays_consistent_without_a_handicap_row() -> None:
    decision = validate_pick_consistency(
        daily_lean="胜",
        probs=_probs(),
        goal_lean="大(2.5)",
        both_score_lean="双进:是",
        odds={"available": True, "match_winner": {"home": 2.1, "draw": 3.6, "away": 3.5}},
    )
    assert decision.is_consistent is True
    assert decision.handicap_lean is None
    assert decision.score_hint
