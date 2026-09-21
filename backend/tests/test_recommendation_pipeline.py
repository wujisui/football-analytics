from datetime import datetime, timedelta

import pytest

from app.services.recommendation import pipeline
from app.services.recommendation.decision import (
    MatchDecision,
    RecommendationCandidate,
    select_reference_candidate,
    settlement_expected_return,
    star_rating,
)
from app.services.recommendation.pipeline import MatchPipelineInput, run_pipeline


def _candidate(
    fixture_id: int,
    *,
    market: str = "ah",
    direction: str = "home",
    ev: float | None = 0.03,
    penalty: float = 0.0,
    probability: float | None = 0.56,
) -> RecommendationCandidate:
    adjusted = ev - penalty if ev is not None else None
    lean = {
        ("ah", "home"): "主-0.5",
        ("ah", "away"): "客+0.5",
        ("ou", "over"): "大(2.5)",
        ("ou", "under"): "小(2.5)",
        ("btts", "yes"): "双进:是",
        ("btts", "no"): "双进:否",
        ("1x2", "home"): "主胜",
        ("1x2", "away"): "客胜",
    }[(market, direction)]
    return RecommendationCandidate(
        fixture_id=fixture_id,
        league_id=39,
        match_day="2026-09-21",
        market=market,
        direction=direction,
        lean=lean,
        line=-0.5 if market == "ah" else 2.5 if market == "ou" else None,
        model_source="ml",
        model_version="test-v1",
        raw_model_probability=probability,
        calibrator_version="platt-v2",
        calibrated_probability=probability,
        implied_probability=0.52,
        decimal_odd=1.90,
        settlement_distribution=(
            {"win": probability or 0.0, "half_win": 0.0, "push": 0.0,
             "half_loss": 0.0, "loss": 1.0 - (probability or 0.0)}
            if probability is not None
            else None
        ),
        expected_return=ev,
        market_direction=direction,
        direction_strength="strong",
        direction_alignment="aligned_strong",
        direction_penalty=penalty,
        adjusted_ev=adjusted,
        skip_reason=None if ev is not None else "calibrator_unavailable",
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


def test_settlement_ev_accounts_for_half_results_and_push() -> None:
    distribution = {
        "win": 0.30,
        "half_win": 0.10,
        "push": 0.20,
        "half_loss": 0.10,
        "loss": 0.30,
    }
    assert settlement_expected_return(distribution, 2.0) == pytest.approx(0.0)


@pytest.mark.parametrize(
    ("ev", "rating"),
    [
        (0.08, 5.0),
        (0.05, 4.5),
        (0.03, 4.0),
        (0.01, 3.5),
        (0.00, 3.0),
        (-0.01, 2.5),
        (-0.03, 2.0),
        (-0.05, 1.5),
        (-0.07, 1.0),
    ],
)
def test_star_rating_uses_absolute_adjusted_ev_bands(ev: float, rating: float) -> None:
    assert star_rating(ev) == rating


def test_strict_market_order_keeps_ah_even_when_ou_has_higher_ev() -> None:
    ah = _candidate(1, market="ah", direction="home", ev=-0.02)
    ou = _candidate(1, market="ou", direction="over", ev=0.20)
    assert select_reference_candidate([ah, ou], has_ah=True) == ah


def test_uncalculable_ah_falls_back_to_ou() -> None:
    ah = _candidate(1, market="ah", direction="home", ev=None, probability=0.57)
    ou = _candidate(1, market="ou", direction="under", ev=0.01)
    assert select_reference_candidate([ah, ou], has_ah=True) == ou


def test_board_free_match_uses_1x2_before_goals() -> None:
    moneyline = _candidate(1, market="1x2", direction="home", ev=-0.04)
    ou = _candidate(1, market="ou", direction="over", ev=0.15)
    assert select_reference_candidate([moneyline, ou], has_ah=False) == moneyline


def test_reverse_penalty_is_subtracted_from_negative_ev() -> None:
    candidate = _candidate(1, ev=-0.02, penalty=0.05)
    assert candidate.adjusted_ev == pytest.approx(-0.07)


def test_pipeline_takes_top_four_by_adjusted_ev(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = datetime(2026, 9, 21, 10)
    evs = {1: -0.02, 2: 0.07, 3: 0.01, 4: 0.03, 5: 0.05}

    def fake_decision(**kwargs: object) -> MatchDecision:
        fixture_id = int(kwargs["fixture_id"])
        candidate = _candidate(fixture_id, ev=evs[fixture_id])
        return MatchDecision(
            fixture_id=fixture_id,
            match_day="2026-09-21",
            reference=candidate,
            candidates=(candidate,),
        )

    monkeypatch.setattr(pipeline, "build_match_decision", fake_decision)
    result = run_pipeline(
        [_match(index, base + timedelta(hours=index)) for index in range(1, 6)],
        market_artifact={"version": "test"},
    )
    assert [pick.fixture_id for pick in result["picks"]] == [2, 5, 4, 3]
    assert result["ratings"] == {2: 4.5, 5: 4.5, 4: 4.0, 3: 3.5}


def test_pipeline_recommends_fewer_when_ev_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_decision(**kwargs: object) -> MatchDecision:
        fixture_id = int(kwargs["fixture_id"])
        candidate = _candidate(fixture_id, ev=None, probability=0.58)
        return MatchDecision(
            fixture_id=fixture_id,
            match_day="2026-09-21",
            reference=candidate,
            candidates=(candidate,),
        )

    monkeypatch.setattr(pipeline, "build_match_decision", fake_decision)
    result = run_pipeline(
        [_match(index, datetime(2026, 9, 21, 10 + index)) for index in range(1, 5)],
        market_artifact={"version": "test"},
    )
    assert result["selected_count"] == 0
    assert result["candidate_count"] == 0
    assert result["alerts"] == [
        {
            "code": "daily_pick_shortfall",
            "match_day": "2026-09-21",
            "selected": 0,
            "expected": 4,
            "matches": 4,
            "ev_computable": 0,
        }
    ]
    assert all(
        reference["skip_reason"] == "calibrator_unavailable"
        for reference in result["references"]
    )
