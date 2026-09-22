from datetime import datetime, timedelta

import pytest

from app.services.prediction import score_hint_for_consistent_bundle
from app.services.recommendation import pipeline
from app.services.recommendation.decision import (
    MatchDecision,
    RecommendationCandidate,
    build_match_decision,
    select_reference_candidate,
    settlement_expected_return,
)
from app.services.recommendation.pipeline import MatchPipelineInput, run_pipeline

LEANS = {
    ("ah", "home"): "主-0.5",
    ("ah", "away"): "客+0.5",
    ("ou", "over"): "大(2.5)",
    ("ou", "under"): "小(2.5)",
    ("btts", "yes"): "双进:是",
    ("btts", "no"): "双进:否",
    ("1x2", "home"): "主胜",
    ("1x2", "away"): "客胜",
}


def _candidate(
    fixture_id: int,
    *,
    market: str = "ah",
    direction: str = "home",
    probability: float | None = 0.56,
    ev: float | None = -0.03,
    penalty: float = 0.0,
    alignment: str = "aligned_strong",
    source: str = "market",
    odd: float | None = 1.90,
    line: float | None = None,
    lean: str | None = None,
) -> RecommendationCandidate:
    resolved_line = (
        line
        if line is not None
        else -0.5
        if market == "ah"
        else 2.5
        if market == "ou"
        else None
    )
    return RecommendationCandidate(
        fixture_id=fixture_id,
        league_id=39,
        match_day="2026-09-21",
        market=market,
        direction=direction,
        lean=lean or LEANS[(market, direction)],
        line=resolved_line,
        model_source="ml",
        model_version="test-v1",
        implied_probability=probability,
        model_probability=0.61,
        probability_source=source,
        raw_probability=probability,
        calibrator_version=None,
        calibrated_probability=probability,
        decimal_odd=odd,
        settlement_distribution=(
            {
                "win": probability or 0.0,
                "half_win": 0.0,
                "push": 0.0,
                "half_loss": 0.0,
                "loss": 1.0 - (probability or 0.0),
            }
            if probability is not None
            else None
        ),
        expected_return=ev,
        market_direction=direction,
        direction_strength="strong",
        direction_alignment=alignment,
        direction_penalty=penalty,
        adjusted_ev=ev - penalty if ev is not None else None,
        skip_reason=None if probability is not None else "probability_unavailable",
    )


def _match(fixture_id: int, kickoff: datetime) -> MatchPipelineInput:
    return MatchPipelineInput(
        fixture_id=fixture_id,
        league_id=39,
        kickoff=kickoff,
        match_day="2026-09-21",
        odds=None,
        recommendation="主胜",
        handicap_lean="主-0.5",
        score_hint="1-0",
        home_win_prob=0.55,
        away_win_prob=0.25,
    )


def _decisions(monkeypatch: pytest.MonkeyPatch, candidates: dict[int, RecommendationCandidate]) -> None:
    def fake_decision(**kwargs: object) -> MatchDecision:
        fixture_id = int(kwargs["fixture_id"])
        candidate = candidates[fixture_id]
        return MatchDecision(
            fixture_id=fixture_id,
            match_day="2026-09-21",
            reference=candidate,
            candidates=(candidate,),
        )

    monkeypatch.setattr(pipeline, "build_match_decision", fake_decision)


def test_settlement_ev_accounts_for_half_results_and_push() -> None:
    distribution = {
        "win": 0.30,
        "half_win": 0.10,
        "push": 0.20,
        "half_loss": 0.10,
        "loss": 0.30,
    }
    assert settlement_expected_return(distribution, 2.0) == pytest.approx(0.0)


def test_strict_market_order_keeps_ah_even_when_goals_look_stronger() -> None:
    ah = _candidate(1, market="ah", direction="home", probability=0.52)
    ou = _candidate(1, market="ou", direction="over", probability=0.80)
    assert select_reference_candidate([ah, ou], has_ah=True) == ah


def test_direction_penalty_can_demote_a_barely_qualified_ah() -> None:
    ah = _candidate(
        1,
        market="ah",
        direction="home",
        probability=0.511,
        penalty=0.02,
        alignment="reverse_weak",
    )
    ou = _candidate(1, market="ou", direction="under", probability=0.531)
    btts = _candidate(1, market="btts", direction="no", probability=0.571)

    assert ah.ranking_score == pytest.approx(0.491)
    assert ah.eligible_for_daily_pick() is False
    # O/U and BTTS share the fallback tier; the stronger adjusted probability wins.
    assert select_reference_candidate([ah, ou, btts], has_ah=True) == btts


def test_ah_without_a_probability_falls_back_to_ou() -> None:
    ah = _candidate(1, market="ah", direction="home", probability=None)
    ou = _candidate(1, market="ou", direction="under", probability=0.55)
    assert select_reference_candidate([ah, ou], has_ah=True) == ou


def test_board_free_match_keeps_1x2_as_the_last_fallback() -> None:
    moneyline = _candidate(1, market="1x2", direction="home", probability=0.44)
    ou = _candidate(1, market="ou", direction="over", probability=0.70)
    assert select_reference_candidate([moneyline, ou], has_ah=False) == ou


def test_pipeline_falls_from_penalized_ah_to_best_secondary_market(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ah = _candidate(
        1,
        market="ah",
        direction="home",
        probability=0.511,
        penalty=0.02,
        alignment="reverse_weak",
    )
    ou = _candidate(1, market="ou", direction="under", probability=0.531)
    btts = _candidate(1, market="btts", direction="no", probability=0.571)
    reference = select_reference_candidate([ah, ou, btts], has_ah=True)

    monkeypatch.setattr(
        pipeline,
        "build_match_decision",
        lambda **_: MatchDecision(
            fixture_id=1,
            match_day="2026-09-21",
            reference=reference,
            candidates=(ah, ou, btts),
        ),
    )
    result = run_pipeline(
        [_match(1, datetime(2026, 9, 21, 10))],
        market_artifact={"version": "test"},
    )

    assert result["selected_count"] == 1
    assert result["picks"][0].market == "btts"
    assert result["picks"][0].market_lean == "双进:否"


def test_companion_result_row_yields_instead_of_killing_the_best_bet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """西雅图那场：双进:是 去水 60.9% 是全池最高，不能被伴随胜负行毙掉。

    「双进:是 + 小(3)」本身不矛盾（1-1 同时满足），无解只出现在伴随行固定写
    「主胜」时。让伴随行让步到和局并隐藏让球行，那一注才留得住。
    """
    btts = _candidate(1, market="btts", direction="yes", probability=0.609)
    ah = _candidate(1, market="ah", direction="home", probability=0.499, line=-0.5)
    monkeypatch.setattr(
        pipeline,
        "build_match_decision",
        lambda **_: MatchDecision(
            fixture_id=1,
            match_day="2026-09-21",
            reference=btts,
            candidates=(ah, btts),
        ),
    )
    match = MatchPipelineInput(
        fixture_id=1,
        league_id=253,
        kickoff=datetime(2026, 9, 23, 16, 30),
        match_day="2026-09-21",
        odds=None,
        recommendation="主胜",
        handicap_lean="主-0.5",
        score_hint="比分:1-0",
        goal_lean="小(3)",
        both_score_lean="双进:是",
        home_win_prob=0.493,
        draw_prob=0.247,
        away_win_prob=0.259,
    )
    result = run_pipeline([match], market_artifact={"version": "test"})

    assert result["selected_count"] == 1
    pick = result["picks"][0]
    assert pick.market == "btts"
    assert pick.market_lean == "双进:是"
    assert pick.lean == "和局"
    # 平局保证受让方不输盘，伴随让球行指向受让方，不得隐藏。
    assert pick.handicap_lean == "客+0.5"
    for pair in pick.score_hint.removeprefix("比分:").split("/"):
        home, away = (int(value) for value in pair.split("-"))
        assert home == away, "和局伴随行下的比分必须是平局"
        assert home > 0 and away > 0, "双进:是 要求两队都进球"
        assert home + away < 3, "小(3) 要求总进球低于 3"


def test_negative_ev_still_produces_a_pick(monkeypatch: pytest.MonkeyPatch) -> None:
    # Board de-vig probabilities make EV = 1/超额 − 1, always negative.  Gating on
    # it empties the pool instead of finding value.
    _decisions(monkeypatch, {1: _candidate(1, probability=0.57, ev=-0.041)})
    result = run_pipeline(
        [_match(1, datetime(2026, 9, 21, 10))],
        market_artifact={"version": "test"},
    )
    assert result["selected_count"] == 1
    assert result["selected"][0]["ev"] == pytest.approx(-0.041)


def test_quarter_ball_pick_rebuilds_result_and_score_from_selected_side(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Regression: the stored analyzer said 客胜 / 0-1, while the daily bet chose
    # 主+0.25.  All three displayed values must be rebuilt from the bet side.
    candidate = _candidate(
        1,
        market="ah",
        direction="home",
        probability=0.54,
        line=0.25,
        lean="主+0.25",
    )
    _decisions(monkeypatch, {1: candidate})
    match = _match(1, datetime(2026, 9, 21, 10))
    match = MatchPipelineInput(
        **{
            **match.__dict__,
            "recommendation": "客胜",
            "score_hint": "比分:0-1",
            "home_win_prob": 0.28,
            "draw_prob": 0.324,
            "away_win_prob": 0.396,
        }
    )
    result = run_pipeline([match], market_artifact={"version": "test"})
    pick = result["picks"][0]
    assert pick.lean == "主胜"
    assert pick.handicap_lean == "主+0.25"
    assert pick.score_hint == "比分:1-0"


def test_away_quarter_ball_pick_uses_away_result_and_winning_score(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate(
        1,
        market="ah",
        direction="away",
        probability=0.54,
        line=0.25,
        lean="客-0.25",
    )
    _decisions(monkeypatch, {1: candidate})
    result = run_pipeline(
        [_match(1, datetime(2026, 9, 21, 10))],
        market_artifact={"version": "test"},
    )
    pick = result["picks"][0]
    assert pick.lean == "客胜"
    assert pick.handicap_lean == "客-0.25"
    home, away = (int(value) for value in pick.score_hint.removeprefix("比分:").split("-"))
    assert away > home


def test_reference_score_keeps_the_btts_call() -> None:
    # 回归：日推的比分生成器漏了双进对齐，「双进:是」配出 3-0。
    probs = {"home": 0.708, "draw": 0.185, "away": 0.107}
    hint = score_hint_for_consistent_bundle(
        "主胜", None, probs, goal_lean="大(2.75)", both_score_lean="双进:是"
    )
    assert hint is not None
    for pair in hint.removeprefix("比分:").split("/"):
        home, away = (int(value) for value in pair.split("-"))
        assert home > 0 and away > 0
        assert home + away > 2.75


def test_btts_call_never_pairs_with_a_clean_sheet_score() -> None:
    """截图回归：西雅图那场发出「[荐] 双进:是 · 小(3) · 比分 2-0」。

    主胜下双方进球最少 2-1，总进球 3 已经不小于 3，三项条件本就无解；
    一致性闸必须返回 None 让流水线降级，不能挑一项悄悄背叛。
    """
    probs = {"home": 0.493, "draw": 0.247, "away": 0.259}
    assert (
        score_hint_for_consistent_bundle(
            "主胜",
            "主-0.5",
            probs,
            goal_lean="小(3)",
            both_score_lean="双进:是",
        )
        is None
    )
    # 同一块大小球盘换成双进:否，就有解。
    hint = score_hint_for_consistent_bundle(
        "主胜",
        "主-0.5",
        probs,
        goal_lean="小(3)",
        both_score_lean="双进:否",
    )
    assert hint is not None
    for pair in hint.removeprefix("比分:").split("/"):
        home, away = (int(value) for value in pair.split("-"))
        assert home > away
        assert home + away < 3
        assert away == 0


def test_score_never_covers_the_board_the_pick_passed_on() -> None:
    """哥伦甲那场：主 -1.5 去水 48.7% 被降级，比分却给了 3-0。

    降级的理由就是穿盘概率不足五成，参考比分不能反过来演示轻松穿盘。
    """
    probs = {"home": 0.708, "draw": 0.185, "away": 0.107}
    hint = score_hint_for_consistent_bundle(
        "主胜",
        None,
        probs,
        goal_lean="大(2.75)",
        both_score_lean="双进:是",
        declined_handicap_lean="主-1.5",
    )
    assert hint == "比分:2-1"

    # 约束无解时返回 None，交给调用方降级，而不是发布自相矛盾的三件套。
    assert (
        score_hint_for_consistent_bundle(
            "主胜",
            None,
            probs,
            goal_lean="大(2.75)",
            both_score_lean="双进:否",
            declined_handicap_lean="主-1.5",
        )
        is None
    )


def test_deep_board_receiving_side_is_never_sold_as_an_outright_win() -> None:
    # 主队让 2 球：客+2 赢在「输一球以内」，而客胜去水概率只有 8.6%。
    decision = build_match_decision(
        fixture_id=1,
        league_id=39,
        match_day="2026-09-21",
        odds={
            "match_winner": {"home": 1.25, "draw": 6.0, "away": 11.0},
            "asian_handicap": {"line": -2.0, "home": 1.98, "away": 1.79},
            "goals_ou": {"line": 3.25, "home": 2.05, "away": 1.75},
        },
        package={},
        calibration_artifact=None,
    )
    ah = {item.direction: item for item in decision.candidates if item.market == "ah"}
    assert ah["away"].tellable is False
    assert ah["away"].skip_reason == "deep_board_receiving_side"
    assert ah["away"].eligible_for_daily_pick() is False
    # The giving side stays a normal candidate, judged on its own probability.
    assert ah["home"].tellable is True
    assert decision.reference.market != "ah" or decision.reference.direction == "home"


def test_impossible_deep_handicap_falls_back_and_hides_handicap_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ah = _candidate(
        1,
        market="ah",
        direction="home",
        probability=0.56,
        line=-2.0,
        lean="主-2",
    )
    ou = _candidate(
        1,
        market="ou",
        direction="under",
        probability=0.55,
        line=2.0,
        lean="小(2)",
    )

    def fake_decision(**kwargs: object) -> MatchDecision:
        return MatchDecision(
            fixture_id=1,
            match_day="2026-09-21",
            reference=ah,
            candidates=(ah, ou),
        )

    monkeypatch.setattr(pipeline, "build_match_decision", fake_decision)
    match = _match(1, datetime(2026, 9, 21, 10))
    match = MatchPipelineInput(
        **{
            **match.__dict__,
            "goal_lean": "小(2)",
            "both_score_lean": "双进:否",
        }
    )
    result = run_pipeline([match], market_artifact={"version": "test"})
    pick = result["picks"][0]
    assert pick.market == "ou"
    assert pick.handicap_lean is None
    assert pick.lean == "主胜"
    assert pick.score_hint == "比分:1-0"


def test_ranking_uses_probability_not_payout(monkeypatch: pytest.MonkeyPatch) -> None:
    # The coin flip pays more; the confident side must still rank first.
    _decisions(
        monkeypatch,
        {
            1: _candidate(1, probability=0.50, odd=1.98),
            2: _candidate(2, probability=0.62, odd=1.62),
        },
    )
    result = run_pipeline(
        [_match(index, datetime(2026, 9, 21, 10 + index)) for index in (1, 2)],
        market_artifact={"version": "test"},
    )
    assert [pick.fixture_id for pick in result["picks"]] == [2, 1]


def test_lower_layers_only_fill_seats_the_handicap_left_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _decisions(
        monkeypatch,
        {
            1: _candidate(1, market="ou", direction="over", probability=0.70),
            2: _candidate(2, market="btts", direction="yes", probability=0.74),
            3: _candidate(3, market="ah", direction="home", probability=0.51),
            4: _candidate(4, market="1x2", direction="home", probability=0.70),
        },
    )
    result = run_pipeline(
        [_match(index, datetime(2026, 9, 21, 10 + index)) for index in range(1, 5)],
        market_artifact={"version": "test"},
    )
    assert [pick.market for pick in result["picks"]] == ["ah", "btts", "ou", "1x2"]


def test_sub_floor_confidence_and_reverse_direction_are_dropped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _decisions(
        monkeypatch,
        {
            1: _candidate(1, market="ah", probability=0.47),
            2: _candidate(2, market="1x2", probability=0.35),
            3: _candidate(3, market="ah", probability=0.61, alignment="reverse_strong"),
            4: _candidate(4, market="ah", probability=0.55),
        },
    )
    result = run_pipeline(
        [_match(index, datetime(2026, 9, 21, 10 + index)) for index in range(1, 5)],
        market_artifact={"version": "test"},
    )
    assert [pick.fixture_id for pick in result["picks"]] == [4]


def test_days_without_a_board_do_not_alert(monkeypatch: pytest.MonkeyPatch) -> None:
    # Future match days routinely have no prices at all; that is not a shortfall.
    _decisions(
        monkeypatch,
        {index: _candidate(index, probability=None, odd=None) for index in range(1, 9)},
    )
    result = run_pipeline(
        [_match(index, datetime(2026, 9, 21, 10)) for index in range(1, 9)],
        market_artifact={"version": "test"},
    )
    assert result["alerts"] == []


def test_thin_day_recommends_fewer_without_alerting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _decisions(
        monkeypatch,
        {index: _candidate(index, probability=0.30) for index in range(1, 4)},
    )
    result = run_pipeline(
        [_match(index, datetime(2026, 9, 21, 10 + index)) for index in range(1, 4)],
        market_artifact={"version": "test"},
    )
    assert result["selected_count"] == 0
    assert result["alerts"] == []


def test_full_pool_that_cannot_fill_four_seats_alerts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidates = {index: _candidate(index, probability=0.30) for index in range(1, 7)}
    candidates[1] = _candidate(1, probability=0.58)
    _decisions(monkeypatch, candidates)
    result = run_pipeline(
        [_match(index, datetime(2026, 9, 21, 10 + index)) for index in range(1, 7)],
        market_artifact={"version": "test"},
    )
    assert result["alerts"] == [
        {
            "code": "daily_pick_shortfall",
            "match_day": "2026-09-21",
            "selected": 1,
            "expected": 4,
            "matches": 6,
            "eligible": 1,
        }
    ]
