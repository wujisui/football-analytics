"""Daily-pick probability calibration (no official API calls)."""

from datetime import datetime, timedelta, timezone

from app.services.probability_calibration import (
    CALIBRATION_VERSION,
    apply_platt,
    build_calibration_artifact,
    calibrate_probability,
    fit_platt,
)


def test_platt_corrects_repeatable_overconfidence() -> None:
    # Raw model says 80%, but this time-ordered stream lands around 60%.
    probabilities = [0.8] * 200
    outcomes = [(index % 5) < 3 for index in range(200)]
    a, b = fit_platt(probabilities, outcomes)
    calibrated = apply_platt(0.8, a, b)
    assert 0.56 <= calibrated <= 0.64


def test_artifact_uses_latest_twenty_percent_only_for_validation() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    samples = [
        (start + timedelta(hours=index), "1x2", 0.8, (index % 5) < 3)
        for index in range(100)
    ]
    artifact = build_calibration_artifact(samples, trained_at=start)
    config = artifact["markets"]["1x2"]
    assert artifact["version"] == CALIBRATION_VERSION
    assert config["fit_samples"] == 80
    assert config["holdout_samples"] == 20
    assert config["deployable"] is True
    assert config["calibrated_holdout"]["brier"] < config["raw_holdout"]["brier"]


def test_non_deployable_market_keeps_raw_probability() -> None:
    artifact = {
        "version": CALIBRATION_VERSION,
        "markets": {
            "ou": {"deployable": False, "a": 0.0, "b": 0.0},
            "1x2": {"deployable": True, "a": 0.0, "b": 0.0},
        },
    }
    assert calibrate_probability(artifact, "ou", 0.7) == 0.7
    assert calibrate_probability(artifact, "1x2", 0.7) == 0.5
