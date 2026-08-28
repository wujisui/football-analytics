"""League-bucket recommendation calibration (no official API calls)."""

import random
from datetime import datetime, timedelta, timezone

from app.services.recommendation.calibration import (
    CALIBRATION_VERSION,
    _HistoryRow,
    build_calibration_artifact,
    calibrate_implied_probs,
    calibrate_match,
)


def _synthetic_rows(
    *,
    league_id: int,
    count: int,
    home_rate: float,
    draw_rate: float,
) -> list[_HistoryRow]:
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    rows: list[_HistoryRow] = []
    away_rate = max(0.0, 1.0 - home_rate - draw_rate)
    labels = (
        ["home"] * int(count * home_rate)
        + ["draw"] * int(count * draw_rate)
        + ["away"] * (count - int(count * home_rate) - int(count * draw_rate))
    )
    # Spread the outcomes over the timeline: the fitter holds out the most
    # recent 20%, and a chronologically blocked list makes that slice
    # single-class, which no calibrator can beat.
    random.Random(20260828).shuffle(labels)
    for index in range(count):
        label = labels[index % len(labels)]
        rows.append(
            _HistoryRow(
                occurred_at=start + timedelta(hours=index),
                league_id=league_id,
                implied_home=0.50,
                implied_draw=0.26,
                implied_away=0.24,
                label=label,
            )
        )
    return rows


def test_build_artifact_has_global_and_league_buckets() -> None:
    rows = _synthetic_rows(league_id=39, count=120, home_rate=0.45, draw_rate=0.27)
    rows += _synthetic_rows(league_id=140, count=80, home_rate=0.40, draw_rate=0.28)
    artifact = build_calibration_artifact(rows, trained_at=datetime(2026, 8, 1, tzinfo=timezone.utc))
    assert artifact["version"] == CALIBRATION_VERSION
    assert artifact["global"]["n_matches"] == 200
    assert "39" in artifact["leagues"]
    assert "140" in artifact["leagues"]


def test_calibrate_match_returns_required_fields() -> None:
    rows = _synthetic_rows(league_id=39, count=120, home_rate=0.45, draw_rate=0.27)
    artifact = build_calibration_artifact(rows)
    payload = calibrate_match(
        match_id=1001,
        league_id=39,
        odds={
            "available": True,
            "match_winner": {"home": 2.0, "draw": 3.4, "away": 4.0},
        },
        artifact=artifact,
    )
    assert payload is not None
    assert payload["match_id"] == 1001
    assert 0.0 < payload["calibrated_home_prob"] < 1.0
    assert 0.0 < payload["calibrated_draw_prob"] < 1.0
    assert 0.0 < payload["calibrated_away_prob"] < 1.0
    total = (
        payload["calibrated_home_prob"]
        + payload["calibrated_draw_prob"]
        + payload["calibrated_away_prob"]
    )
    assert abs(total - 1.0) < 1e-5
    assert payload["sample_size"] >= 60
    assert 0.0 <= payload["reliability"] <= 1.0
    assert set(payload["calibration_bias"]) == {"home", "draw", "away"}


def test_unknown_league_falls_back_to_global_bucket() -> None:
    rows = _synthetic_rows(league_id=39, count=120, home_rate=0.45, draw_rate=0.27)
    artifact = build_calibration_artifact(rows)
    payload = calibrate_implied_probs(
        match_id=2002,
        league_id=999,
        implied={"home": 0.5, "draw": 0.26, "away": 0.24},
        artifact=artifact,
    )
    assert payload["sample_size"] == 120
    assert payload["reliability"] > 0.0


def test_missing_odds_returns_none() -> None:
    assert calibrate_match(match_id=1, league_id=39, odds=None) is None
