"""Recommendation pipeline orchestration (no official API calls)."""

from datetime import datetime, timezone

from app.services.recommendation.pipeline import (
    DailyRecommendationPick,
    MatchPipelineInput,
    PipelineMatchResult,
    build_features_placeholder,
    process_match,
    run_pipeline,
    select_daily_picks_by_match_day,
)


def _match(fixture_id: int, *, match_day: str = "2026-08-28") -> MatchPipelineInput:
    return MatchPipelineInput(
        fixture_id=fixture_id,
        league_id=39,
        kickoff=datetime(2026, 8, 28, 15, 0, tzinfo=timezone.utc),
        match_day=match_day,
        odds={
            "available": True,
            "match_winner": {"home": 2.0, "draw": 3.4, "away": 4.0},
        },
    )


def _processed(
    fixture_id: int,
    *,
    match_day: str = "2026-08-28",
    choice: str | None = "home",
    ev: float = 0.12,
) -> PipelineMatchResult:
    strategy = {
        "match_id": fixture_id,
        "recommended_choice": choice,
        "ev": ev,
        "confidence": 0.56,
        "reason": "EV最大" if choice else "无正EV，不推荐",
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


def test_features_placeholder_is_empty() -> None:
    assert build_features_placeholder(_match(1)) == {}


def test_process_match_runs_calibration_and_strategy() -> None:
    result = process_match(_match(1), artifact={})
    assert result is not None
    assert result.features == {}
    assert result.calibration is not None
    assert "recommended_choice" in result.strategy


def test_run_pipeline_keeps_top_four_positive_ev_per_day(monkeypatch) -> None:
    processed = [
        _processed(1, ev=0.40),
        _processed(2, ev=0.30),
        _processed(3, ev=0.20),
        _processed(4, ev=0.10),
        _processed(5, ev=0.05),
        _processed(6, choice=None, ev=-0.02),
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
    assert all(item["ev"] > 0 for item in result["selected"])
    assert all(item["lean"] == "胜" for item in result["selected"])
    assert result["selected"][0]["quality_rating"] == 5.0


def test_run_pipeline_does_not_pad_when_fewer_than_four_positive_ev(monkeypatch) -> None:
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
            reason="EV最大",
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
            reason="EV最大",
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
            reason="EV最大",
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
    selected = select_daily_picks_by_match_day(picks, limit_per_day=1)
    assert {pick.fixture_id for pick in selected} == {1, 3}
