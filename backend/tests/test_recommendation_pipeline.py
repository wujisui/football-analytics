"""Recommendation pipeline orchestration (no official API calls)."""

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from app.services.auto_pick_incentive import IncentiveParams, IncentiveState
from app.services.recommendation.features import build_match_features
from app.services.recommendation.pipeline import (
    DailyRecommendationPick,
    MatchPipelineInput,
    PipelineMatchResult,
    log_sync_summary,
    process_match,
    run_pipeline,
    select_daily_picks_by_match_day,
)


def _match(
    fixture_id: int,
    *,
    match_day: str = "2026-08-28",
    goal_lean: str | None = "大(2.5)",
    both_score_lean: str | None = "双进:是",
    ah_line: str | None = None,
    ah_cover_prob: float | None = None,
) -> MatchPipelineInput:
    odds = {
        "available": True,
        "match_winner": {"home": 2.0, "draw": 3.4, "away": 4.0},
    }
    if ah_line is not None:
        odds["asian_handicap"] = {"line": ah_line, "home": 1.90, "away": 1.98}
    return MatchPipelineInput(
        fixture_id=fixture_id,
        league_id=39,
        kickoff=datetime(2026, 8, 28, 15, 0, tzinfo=timezone.utc),
        match_day=match_day,
        odds=odds,
        goal_lean=goal_lean,
        both_score_lean=both_score_lean,
        ah_cover_prob=ah_cover_prob,
        ah_model_line=float(ah_line) if ah_line is not None else None,
    )


def _processed(
    fixture_id: int,
    *,
    match_day: str = "2026-08-28",
    choice: str | None = "home",
    ev: float = 0.12,
    confidence: float = 0.56,
) -> PipelineMatchResult:
    strategy = {
        "match_id": fixture_id,
        "recommended_choice": choice,
        "ev": ev,
        "confidence": confidence,
        "reason": "置信度最高" if choice else "缺少可用赔率，不推荐",
    }
    calibration = {
        "match_id": fixture_id,
        "calibrated_home_prob": 0.56,
        "calibrated_draw_prob": 0.24,
        "calibrated_away_prob": 0.20,
        "reliability": 0.7,
        "sample_size": 100,
        "calibration_bias": {"home": 0.0, "draw": 0.0, "away": 0.0},
    }
    return PipelineMatchResult(
        fixture_id=fixture_id,
        league_id=39,
        kickoff=datetime(2026, 8, 28, 15, 0, tzinfo=timezone.utc),
        match_day=match_day,
        features={},
        calibration=calibration,
        strategy=strategy,
    )


def test_build_match_features_in_process_match() -> None:
    result = process_match(_match(1), artifact={})
    assert result is not None
    assert result.features.get("match_id") == 1
    assert "league_reliability" in result.features
    assert "recommended_choice" in result.strategy


def test_valid_ah_board_never_generates_a_moneyline_candidate() -> None:
    result = run_pipeline(
        [_match(1, ah_line="-0.75", ah_cover_prob=0.58)],
        artifact={},
        market_artifact={},
        limit_per_day=4,
    )

    assert result["selected_count"] == 1
    assert result["selected"][0]["market"] == "ah"
    assert result["selected"][0]["lean"] == "主-0.75"
    assert result["selected"][0]["result_lean"] == "主胜"
    assert result["selected"][0]["decimal_odd"] == 1.9


@pytest.mark.parametrize(
    ("line", "ah_home", "ah_away", "moneyline", "choice", "probs", "expected_lean"),
    [
        (
            "+0.5",
            2.05,
            1.82,
            {"home": 4.0, "draw": 3.4, "away": 1.80},
            "away",
            {"home": 0.22, "draw": 0.23, "away": 0.55},
            "客-0.5",
        ),
        (
            "-0.5",
            1.82,
            2.05,
            {"home": 1.80, "draw": 3.4, "away": 4.0},
            "home",
            {"home": 0.56, "draw": 0.24, "away": 0.20},
            "主-0.5",
        ),
        (
            "+0.5",
            2.05,
            1.82,
            {"home": 4.0, "draw": 3.4, "away": 2.12},
            "away",
            {"home": 0.22, "draw": 0.23, "away": 0.55},
            "客-0.5",
        ),
    ],
)
def test_valid_half_ball_board_always_uses_ah_despite_market_feedback(
    monkeypatch,
    line: str,
    ah_home: float,
    ah_away: float,
    moneyline: dict[str, float],
    choice: str,
    probs: dict[str, float],
    expected_lean: str,
) -> None:
    """A valid AH board cannot fall back to moneyline, even when 1X2 pays more."""
    match = _match(1, ah_line=line)
    assert match.odds is not None
    match.odds["match_winner"] = moneyline
    match.odds["asian_handicap"]["home"] = ah_home
    match.odds["asian_handicap"]["away"] = ah_away
    processed = replace(
        _processed(1, choice=choice, confidence=probs[choice]),
        calibration={
            "match_id": 1,
            "calibrated_home_prob": probs["home"],
            "calibrated_draw_prob": probs["draw"],
            "calibrated_away_prob": probs["away"],
            "reliability": 0.7,
            "sample_size": 100,
        },
    )
    monkeypatch.setattr(
        "app.services.recommendation.pipeline.process_match",
        lambda _match, *, artifact=None: processed,
    )
    state = IncentiveState(
        params=IncentiveParams(),
        ema_market={"1x2": 0.5, "ah": -0.5},
        soft_weights={"global": 1.0},
    )

    result = run_pipeline(
        [match],
        artifact={},
        market_artifact={},
        incentive_state=state,
        limit_per_day=4,
    )

    assert result["selected_count"] == 1
    assert result["selected"][0]["market"] == "ah"
    assert result["selected"][0]["lean"] == expected_lean
    assert result["selected"][0]["decimal_odd"] == (
        ah_away if choice == "away" else ah_home
    )


def test_one_goal_board_uses_market_probability_instead_of_moneyline(
    monkeypatch,
) -> None:
    """复现维拉利尔：主让 1 球没有冻结 AH 模型概率时，仍用主盘去水概率推让球。"""
    match = _match(1, ah_line="-1", ah_cover_prob=None, goal_lean="大(3.25)")
    assert match.odds is not None
    match.odds["match_winner"] = {"home": 1.51, "draw": 4.60, "away": 6.00}
    match.odds["asian_handicap"] = {"line": "-1", "home": 1.83, "away": 2.09}
    match.odds["goals_ou"] = {"line": "3.25", "home": 1.90, "away": 1.96}
    match.odds["both_teams_score"] = {"home": 1.88, "away": 1.98}
    processed = replace(
        _processed(1, choice="home", confidence=0.638),
        calibration={
            "match_id": 1,
            "calibrated_home_prob": 0.638,
            "calibrated_draw_prob": 0.198,
            "calibrated_away_prob": 0.164,
            "reliability": 0.7,
            "sample_size": 100,
        },
    )
    monkeypatch.setattr(
        "app.services.recommendation.pipeline.process_match",
        lambda _match, *, artifact=None: processed,
    )

    result = run_pipeline(
        [match],
        artifact={},
        market_artifact={},
        limit_per_day=4,
    )

    assert result["selected_count"] == 1
    assert result["selected"][0]["market"] == "ah"
    assert result["selected"][0]["lean"] == "主-1"
    assert result["selected"][0]["decimal_odd"] == 1.83
    assert all(item["market"] != "1x2" for item in result["selected"])


def test_weak_deep_ah_falls_back_to_goals_not_moneyline(monkeypatch) -> None:
    """深盘信心不足才降级大小球；线深本身不是降级条件。"""
    match = _match(1, ah_line="-1", ah_cover_prob=0.35, goal_lean="大(3.25)")
    assert match.odds is not None
    match.odds["match_winner"] = {"home": 1.51, "draw": 4.60, "away": 6.00}
    match.odds["asian_handicap"] = {"line": "-1", "home": 1.83, "away": 2.09}
    match.odds["goals_ou"] = {"line": "3.25", "home": 1.90, "away": 1.96}
    processed = replace(
        _processed(1, choice="home", confidence=0.638),
        ah_cover_prob=0.35,
        ah_model_line=-1.0,
        calibration={
            "match_id": 1,
            "calibrated_home_prob": 0.638,
            "calibrated_draw_prob": 0.198,
            "calibrated_away_prob": 0.164,
            "reliability": 0.7,
            "sample_size": 100,
        },
    )
    monkeypatch.setattr(
        "app.services.recommendation.pipeline.process_match",
        lambda _match, *, artifact=None: processed,
    )

    result = run_pipeline(
        [match],
        artifact={},
        market_artifact={},
        limit_per_day=4,
    )

    assert result["selected_count"] == 1
    assert result["selected"][0]["market"] == "ou"
    assert result["selected"][0]["lean"] == "大(3.25)"
    assert all(item["market"] != "1x2" for item in result["selected"])


def test_shallow_board_never_buys_the_lower_probability_side(monkeypatch) -> None:
    """复现布拉加：主胜 51.9% 时不得推对面 48.1% 的高水让负。

    让球盘两侧的条件命中概率之和恒为 1，而基础分 ``p × 净赔率 ** e`` 代入去水
    概率后正比于 ``√(p(1-p))``，关于 0.5 对称。让胜 0.519 与让负 0.481 的概率项
    实测完全相等（各 0.249639），排序只剩抽水差（让胜 -3.0% / 让负 -1.8%），
    没有这道闸就会买进水位更高的低概率侧。
    """
    match = MatchPipelineInput(
        fixture_id=1,
        league_id=94,
        kickoff=datetime(2026, 8, 28, 15, 0, tzinfo=timezone.utc),
        match_day="2026-08-28",
        odds={
            "available": True,
            "match_winner": {"home": 1.85, "draw": 3.60, "away": 4.60},
            "asian_handicap": {"line": "-0.5", "home": 1.869, "away": 2.042},
        },
        goal_lean="小(2.5)",
        both_score_lean="双进:否",
    )
    processed = replace(
        _processed(1, choice="home", confidence=0.519),
        calibration={
            "match_id": 1,
            "calibrated_home_prob": 0.519,
            "calibrated_draw_prob": 0.272,
            "calibrated_away_prob": 0.209,
            "reliability": 0.7,
            "sample_size": 100,
            "calibration_bias": {"home": 0.0, "draw": 0.0, "away": 0.0},
        },
    )
    monkeypatch.setattr(
        "app.services.recommendation.pipeline.process_match",
        lambda _match, *, artifact=None: processed,
    )

    result = run_pipeline(
        [match],
        artifact={},
        market_artifact={},
        limit_per_day=4,
    )

    assert result["selected_count"] == 1
    selected = result["selected"][0]
    assert selected["market"] == "ah"
    assert selected["lean"] == "主-0.5"
    assert selected["handicap_lean"] == "主-0.5"


def test_quarter_ball_refund_survives_adverse_market_feedback() -> None:
    """复现浦和红钻：让胜(-0.25) 的退半兜底不能被玩法历史权重翻掉。

    平局时独赢全输、-0.25 只输一半。退半的好处已计入条件命中率，较低水位的
    代价也已进入基础分；两者必须先完成当场取舍，再应用历史权重做跨场排序。
    """
    match = MatchPipelineInput(
        fixture_id=1,
        league_id=98,
        kickoff=datetime(2026, 8, 29, 10, 0, tzinfo=timezone.utc),
        match_day="2026-08-29",
        odds={
            "available": True,
            "match_winner": {"home": 2.16, "draw": 3.61, "away": 3.39},
            "asian_handicap": {"line": "-0.25", "home": 1.88, "away": 2.03},
        },
        goal_lean="大(2.5)",
        both_score_lean="双进:是",
    )
    state = IncentiveState(
        params=IncentiveParams(),
        ema_market={"1x2": 0.0006, "ah": -0.1747},
        soft_weights={"98|1x2": 1.15, "m:ah": 1.011},
    )

    result = run_pipeline(
        [match],
        artifact={},
        market_artifact={},
        incentive_state=state,
        limit_per_day=4,
    )

    assert result["selected_count"] == 1
    assert result["selected"][0]["market"] == "ah"
    assert result["selected"][0]["lean"] == "主-0.25"


def test_run_pipeline_keeps_top_four_by_confidence_per_day(monkeypatch) -> None:
    """EV 与置信度反向排列，验证选场只看置信度、EV 只是随行审计字段。"""
    processed = [
        _processed(1, confidence=0.62, ev=0.05),
        _processed(2, confidence=0.60, ev=0.10),
        _processed(3, confidence=0.58, ev=0.20),
        _processed(4, confidence=0.56, ev=0.30),
        _processed(5, confidence=0.54, ev=0.40),
        _processed(6, choice=None, ev=0.50),
    ]

    def fake_process(match, *, artifact=None):
        del artifact
        return next(item for item in processed if item.fixture_id == match.fixture_id)

    monkeypatch.setattr(
        "app.services.recommendation.pipeline.process_match",
        fake_process,
    )
    result = run_pipeline([_match(i) for i in range(1, 7)], artifact={}, limit_per_day=4)
    assert result["selected_count"] == 4
    assert [item["fixture_id"] for item in result["selected"]] == [1, 2, 3, 4]
    assert all(item["lean"] == "主胜" for item in result["selected"])
    assert result["selected"][0]["quality_rating"] == 5.0


def test_negative_ev_candidates_still_fill_the_daily_four(monkeypatch) -> None:
    """1X2 模型跑不赢市场时 EV 恒为负；日推不能因此空池。"""
    processed = [
        _processed(i, confidence=0.60 - i / 100, ev=-0.03 - i / 1000)
        for i in range(1, 7)
    ]

    def fake_process(match, *, artifact=None):
        del artifact
        return next(item for item in processed if item.fixture_id == match.fixture_id)

    monkeypatch.setattr(
        "app.services.recommendation.pipeline.process_match",
        fake_process,
    )
    result = run_pipeline([_match(i) for i in range(1, 7)], artifact={}, limit_per_day=4)
    assert result["candidate_count"] == 6
    assert result["selected_count"] == 4
    assert [item["fixture_id"] for item in result["selected"]] == [1, 2, 3, 4]
    assert all(item["ev"] < 0 for item in result["selected"])


def test_run_pipeline_feedback_reorders_without_changing_the_pick_side(
    monkeypatch,
) -> None:
    processed = [
        _processed(1, ev=0.11),
        _processed(2, ev=0.10),
    ]

    def fake_process(match, *, artifact=None):
        del artifact
        return next(item for item in processed if item.fixture_id == match.fixture_id)

    monkeypatch.setattr(
        "app.services.recommendation.pipeline.process_match",
        fake_process,
    )
    state = IncentiveState(
        params=IncentiveParams(),
        ema_market={"1x2": 0.0},
        ema_league={"39": 0.0, "40": 0.3},
        soft_weights={"39|1x2": 0.9, "40|1x2": 1.25},
    )
    processed[1] = PipelineMatchResult(
        fixture_id=2,
        league_id=40,
        kickoff=processed[1].kickoff,
        match_day=processed[1].match_day,
        features={},
        calibration=processed[1].calibration,
        strategy=processed[1].strategy,
    )
    result = run_pipeline(
        [_match(1), _match(2)],
        artifact={},
        incentive_state=state,
        limit_per_day=2,
    )
    assert result["selected_count"] == 2
    assert result["selected"][0]["fixture_id"] == 2
    assert result["selected"][0]["ev"] == 0.10
    assert result["selected"][0]["score"] > result["selected"][1]["score"]


def test_run_pipeline_does_not_pad_when_fewer_candidates_than_quota(
    monkeypatch,
) -> None:
    processed = [
        _processed(10, ev=0.12),
        _processed(11, choice=None, ev=-0.01),
    ]

    def fake_process(match, *, artifact=None):
        del artifact
        return next(item for item in processed if item.fixture_id == match.fixture_id)

    monkeypatch.setattr(
        "app.services.recommendation.pipeline.process_match",
        fake_process,
    )
    result = run_pipeline([_match(10), _match(11)], artifact={}, limit_per_day=4)
    assert result["selected_count"] == 1


def test_ou_then_btts_precede_board_free_moneyline(monkeypatch) -> None:
    """AH 不足时按大小 → 双进补位，无 AH 盘独赢只作最后兜底。"""
    matches = [_match(i) for i in range(1, 5)]
    assert matches[2].odds is not None and matches[3].odds is not None
    matches[2].odds["goals_ou"] = {"line": 2.5, "home": 1.70, "away": 2.18}
    matches[2].odds["both_teams_score"] = {"home": 1.72, "away": 2.12}
    matches[3].odds["both_teams_score"] = {"home": 1.68, "away": 2.20}
    matches[3] = replace(matches[3], goal_lean="大小：待分析")

    processed = [
        _processed(1, choice="home", confidence=0.56),
        _processed(2, choice="home", confidence=0.55),
        _processed(3, choice=None),
        _processed(4, choice=None),
    ]

    def fake_process(match, *, artifact=None):
        del artifact
        return next(item for item in processed if item.fixture_id == match.fixture_id)

    monkeypatch.setattr(
        "app.services.recommendation.pipeline.process_match",
        fake_process,
    )
    result = run_pipeline(
        matches,
        artifact={},
        market_artifact={},
        limit_per_day=4,
    )

    assert [(item["fixture_id"], item["market"]) for item in result["selected"]] == [
        (3, "ou"),
        (4, "btts"),
        (1, "1x2"),
        (2, "1x2"),
    ]
    assert result["selected"][0]["lean"] == "大(2.5)"
    assert result["selected"][1]["lean"] == "双进:是"
    assert result["selected"][0]["quality_rating"] > result["selected"][1]["quality_rating"]
    assert result["selected"][1]["quality_rating"] > result["selected"][2]["quality_rating"]
    ou_home, ou_away = map(
        int, result["selected"][0]["score_hint"].split(":")[1].split("-")
    )
    btts_home, btts_away = map(
        int, result["selected"][1]["score_hint"].split(":")[1].split("-")
    )
    assert ou_home + ou_away > 2.5
    assert btts_home > 0 and btts_away > 0


def test_ou_displaces_board_free_moneyline(monkeypatch) -> None:
    matches = [_match(i) for i in range(1, 6)]
    assert matches[4].odds is not None
    matches[4].odds["goals_ou"] = {"line": 2.5, "home": 1.20, "away": 5.50}
    processed = [
        *[_processed(i, choice="home", confidence=0.60 - i / 100) for i in range(1, 5)],
        _processed(5, choice=None),
    ]

    def fake_process(match, *, artifact=None):
        del artifact
        return next(item for item in processed if item.fixture_id == match.fixture_id)

    monkeypatch.setattr(
        "app.services.recommendation.pipeline.process_match",
        fake_process,
    )
    result = run_pipeline(
        matches,
        artifact={},
        market_artifact={},
        limit_per_day=4,
    )

    assert [item["fixture_id"] for item in result["selected"]] == [5, 1, 2, 3]
    assert [item["market"] for item in result["selected"]] == [
        "ou",
        "1x2",
        "1x2",
        "1x2",
    ]


def test_deep_board_without_ah_probability_is_skipped_and_backfilled(
    monkeypatch,
) -> None:
    processed = [_processed(i, ev=0.50 - i / 100) for i in range(1, 7)]

    def fake_process(match, *, artifact=None):
        del artifact
        return next(item for item in processed if item.fixture_id == match.fixture_id)

    monkeypatch.setattr(
        "app.services.recommendation.pipeline.process_match",
        fake_process,
    )
    # 主让 1.5 仍可凭主盘去水概率进候选；比分穿不过盘时自洽闸淘汰，由后续场次补位。
    matches = [
        _match(1, ah_line="-1.5"),
        *[_match(i, ah_line="-0.5") for i in range(2, 7)],
    ]
    result = run_pipeline(matches, artifact={}, limit_per_day=4)

    assert [item["fixture_id"] for item in result["selected"]] == [2, 3, 4, 5]
    assert result["selected_count"] == 4
    assert result["consistency_rejected_count"] == 1
    assert result["rejected"][0]["fixture_id"] == 1
    assert result["rejected"][0]["is_consistent"] is False
    assert all(item["fixture_id"] != 1 for item in result["selected"])
    assert all(item["is_consistent"] is True for item in result["selected"])
    assert all(item["handicap_lean"] == "主-0.5" for item in result["selected"])
    for item in result["selected"]:
        home_goals, away_goals = item["score_hint"].split(":")[1].split("-")
        assert int(home_goals) > int(away_goals)


def test_select_daily_picks_respects_match_day_buckets() -> None:
    picks = [
        DailyRecommendationPick(
            fixture_id=1,
            league_id=39,
            kickoff=datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc),
            match_day="2026-08-28",
            market="1x2",
            lean="胜",
            recommended_choice="home",
            ev=0.20,
            confidence=0.56,
            reason="置信度最高",
            decimal_odd=2.0,
            raw_confidence=0.50,
            calibrated_home_prob=0.56,
            calibrated_draw_prob=0.24,
            calibrated_away_prob=0.20,
            reliability=0.7,
            sample_size=100,
            score=0.20,
        ),
        DailyRecommendationPick(
            fixture_id=2,
            league_id=39,
            kickoff=datetime(2026, 8, 28, 14, 0, tzinfo=timezone.utc),
            match_day="2026-08-28",
            market="1x2",
            lean="胜",
            recommended_choice="home",
            ev=0.10,
            confidence=0.56,
            reason="置信度最高",
            decimal_odd=2.0,
            raw_confidence=0.50,
            calibrated_home_prob=0.56,
            calibrated_draw_prob=0.24,
            calibrated_away_prob=0.20,
            reliability=0.7,
            sample_size=100,
            score=0.10,
        ),
        DailyRecommendationPick(
            fixture_id=3,
            league_id=39,
            kickoff=datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc),
            match_day="2026-08-29",
            market="1x2",
            lean="胜",
            recommended_choice="home",
            ev=0.30,
            confidence=0.56,
            reason="置信度最高",
            decimal_odd=2.0,
            raw_confidence=0.50,
            calibrated_home_prob=0.56,
            calibrated_draw_prob=0.24,
            calibrated_away_prob=0.20,
            reliability=0.7,
            sample_size=100,
            score=0.30,
        ),
    ]
    selected = select_daily_picks_by_match_day(
        picks,
        limit_per_day=1,
    )
    assert {pick.fixture_id for pick in selected} == {1, 3}


def test_daily_four_follows_pure_score_order_across_markets() -> None:
    base = DailyRecommendationPick(
        fixture_id=1,
        league_id=39,
        kickoff=datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc),
        match_day="2026-08-28",
        market="ah",
        lean="胜",
        market_lean="让胜(-0.5)",
        recommended_choice="home",
        ev=-0.03,
        confidence=0.52,
        reason="风险调整回报最高",
        decimal_odd=1.95,
        raw_confidence=0.52,
        calibrated_home_prob=0.56,
        calibrated_draw_prob=0.24,
        calibrated_away_prob=0.20,
        reliability=0.7,
        sample_size=100,
        score=0.90,
    )
    picks = [
        replace(base, fixture_id=fixture_id, score=0.90 - fixture_id / 100)
        for fixture_id in range(1, 7)
    ]
    picks.extend(
        replace(
            base,
            fixture_id=fixture_id,
            market="1x2",
            market_lean="胜",
            score=0.40 - fixture_id / 100,
        )
        for fixture_id in range(1, 7)
    )

    selected = select_daily_picks_by_match_day(
        picks,
        limit_per_day=4,
    )

    # No per-market quota: a lower-scoring 1X2 candidate must never displace a
    # higher-scoring AH one just to spread the daily four across markets.
    assert len(selected) == 4
    assert all(pick.market == "ah" for pick in selected)
    assert [pick.fixture_id for pick in selected] == [1, 2, 3, 4]


def test_same_fixture_cannot_occupy_two_slots_with_both_markets() -> None:
    base = DailyRecommendationPick(
        fixture_id=1,
        league_id=39,
        kickoff=datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc),
        match_day="2026-08-28",
        market="ah",
        lean="胜",
        market_lean="让胜(-0.25)",
        recommended_choice="home",
        ev=-0.02,
        confidence=0.53,
        reason="风险调整回报最高",
        decimal_odd=1.83,
        raw_confidence=0.53,
        calibrated_home_prob=0.46,
        calibrated_draw_prob=0.27,
        calibrated_away_prob=0.27,
        reliability=0.7,
        sample_size=100,
        score=0.49,
    )
    picks = [
        base,
        replace(base, market="1x2", market_lean="胜", decimal_odd=2.10, score=0.48),
        replace(base, fixture_id=2, score=0.40),
        replace(base, fixture_id=3, score=0.39),
        replace(base, fixture_id=4, score=0.38),
    ]

    selected = select_daily_picks_by_match_day(
        picks,
        limit_per_day=4,
    )

    assert [pick.fixture_id for pick in selected] == [1, 2, 3, 4]
    assert selected[0].market == "ah"


def test_quiet_day_may_pick_fewer_but_never_more_than_four() -> None:
    """池子不足 6 场只是「允许少于 4 场」，不是「可以多于 4 场」。

    曾把这条实现成候选少时 day_limit = len(day_picks)，等于取消上限：
    09-03 只有 5 场进管线，5 个候选就全部入池。
    """
    base = DailyRecommendationPick(
        fixture_id=1,
        league_id=39,
        kickoff=datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc),
        match_day="2026-08-28",
        market="1x2",
        lean="胜",
        recommended_choice="home",
        ev=0.20,
        confidence=0.56,
        reason="置信度最高",
        decimal_odd=2.0,
        raw_confidence=0.50,
        calibrated_home_prob=0.56,
        calibrated_draw_prob=0.24,
        calibrated_away_prob=0.20,
        reliability=0.7,
        sample_size=100,
        score=0.20,
    )
    picks = [
        replace(base, fixture_id=fixture_id, score=0.20 - fixture_id / 100)
        for fixture_id in range(1, 6)
    ]

    # 清淡日的 5 个合格候选同样只能占 4 个坑。
    assert [
        pick.fixture_id
        for pick in select_daily_picks_by_match_day(picks, limit_per_day=4)
    ] == [1, 2, 3, 4]

    # 候选真的不足 4 场时按实际数量给，不硬塞。
    assert len(select_daily_picks_by_match_day(picks[:2], limit_per_day=4)) == 2


def test_short_pool_is_the_only_excuse_for_fewer_than_four(caplog) -> None:
    """池子 ≥ 6 场却选不满 4 场才算异常，池子小于 6 场不告警。

    告警必须按比赛日判断：多日窗口的聚合 selected 通常是 4×有赛日，
    恒大于 4，用聚合数字判断等于告警永不触发。
    """
    with caplog.at_level("WARNING"):
        log_sync_summary(
            total_matches=11,
            candidate_count=9,
            selected_count=7,
            feedback_written=False,
            day="2026-09-03",
            matches_by_day={"2026-09-03": 5, "2026-09-04": 6},
            selected_by_day={"2026-09-03": 4, "2026-09-04": 3},
        )

    alerts = [record.getMessage() for record in caplog.records]
    assert any("match_day=2026-09-04" in message for message in alerts)
    assert not any("match_day=2026-09-03" in message for message in alerts)
