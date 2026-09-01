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


def test_ah_candidate_can_beat_the_lower_payout_1x2_candidate() -> None:
    result = run_pipeline(
        [_match(1, ah_line="-0.75", ah_cover_prob=0.58)],
        artifact={},
        market_artifact={},
        limit_per_day=4,
    )

    assert result["selected_count"] == 1
    assert result["selected"][0]["market"] == "ah"
    assert result["selected"][0]["lean"] == "让胜(-0.75)"
    assert result["selected"][0]["result_lean"] == "胜"
    assert result["selected"][0]["decimal_odd"] == 1.9


@pytest.mark.parametrize(
    ("choice", "line", "moneyline_odd", "ah_odd", "expected_market", "expected_lean"),
    [
        ("away", "+0.5", 1.99, 2.00, "ah", "让负(+0.5)"),
        ("home", "-0.5", 2.07, 2.08, "ah", "让胜(-0.5)"),
        # 同赔固定取 AH，避免展示随机漂移。
        ("away", "+0.5", 2.00, 2.00, "ah", "让负(+0.5)"),
        # 反向：独赢水位更高时保留独赢，收敛规则不是「一律偏向让球」。
        ("away", "+0.5", 2.12, 2.00, "1x2", "负"),
    ],
)
def test_equivalent_half_ball_keeps_the_higher_quote_despite_market_feedback(
    monkeypatch,
    choice: str,
    line: str,
    moneyline_odd: float,
    ah_odd: float,
    expected_market: str,
    expected_lean: str,
) -> None:
    """Equivalent half-ball bets use the same 1X2 signal; the better quote wins."""
    match = _match(1, ah_line=line)
    assert match.odds is not None
    match.odds["match_winner"][choice] = moneyline_odd
    match.odds["asian_handicap"]["home" if choice == "home" else "away"] = ah_odd
    # 半球盘的对面是「不败」双选：让胜(+0.5) 覆盖主胜+平。想让单选侧真的入选，
    # 该侧概率必须过半，否则模型本来就该去买对面那半个球。
    probabilities = {"home": 0.22, "draw": 0.23, "away": 0.55}
    if choice == "home":
        probabilities = {"home": 0.56, "draw": 0.24, "away": 0.20}
    processed = replace(
        _processed(1, choice=choice, confidence=probabilities[choice]),
        calibration={
            "match_id": 1,
            "calibrated_home_prob": probabilities["home"],
            "calibrated_draw_prob": probabilities["draw"],
            "calibrated_away_prob": probabilities["away"],
            "reliability": 0.7,
            "sample_size": 100,
        },
    )
    monkeypatch.setattr(
        "app.services.recommendation.pipeline.process_match",
        lambda _match, *, artifact=None: processed,
    )
    # This reproduces the observed state: generic 1X2 history is rewarded while
    # AH is penalised. It must not distinguish two bets with identical outcomes.
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
    assert result["selected"][0]["market"] == expected_market
    assert result["selected"][0]["lean"] == expected_lean
    assert result["selected"][0]["decimal_odd"] == (
        ah_odd if expected_market == "ah" else moneyline_odd
    )


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
    assert selected["lean"] == "让胜(-0.5)"
    assert selected["handicap_lean"] == "让胜(-0.5)"


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
    assert result["selected"][0]["lean"].endswith("(-0.25)")


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
    assert all(item["lean"] == "胜" for item in result["selected"])
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


def test_consistency_gate_runs_before_top_four_and_backfills(monkeypatch) -> None:
    processed = [_processed(i, ev=0.50 - i / 100) for i in range(1, 7)]

    def fake_process(match, *, artifact=None):
        del artifact
        return next(item for item in processed if item.fixture_id == match.fixture_id)

    monkeypatch.setattr(
        "app.services.recommendation.pipeline.process_match",
        fake_process,
    )
    # 主胜穿不过主让1.5球，最高分的这场无法表达成让球方向，只能淘汰补位。
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
    assert result["rejected"][0]["conflict_reason"] == "无法自洽，跳过"
    assert all(item["is_consistent"] is True for item in result["selected"])
    assert all(item["handicap_lean"] == "让胜(-0.5)" for item in result["selected"])
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


def test_quiet_day_still_caps_at_the_daily_limit() -> None:
    """清淡日不放宽上限。

    曾按「当日进管线场次 < MIN_MATCHES_FOR_FULL_QUOTA 就取全部候选」处理，等于在
    清淡日取消配额：09-03 只有 5 场有盘口，5 个候选全部入池，超出每日 4 场。
    该常量只决定选不满要不要告警。
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

    selected = select_daily_picks_by_match_day(picks, limit_per_day=4)

    assert [pick.fixture_id for pick in selected] == [1, 2, 3, 4]

    # 候选真的不足 4 场时按实际数量给，不硬塞。
    assert len(select_daily_picks_by_match_day(picks[:2], limit_per_day=4)) == 2
