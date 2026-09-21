"""Daily-pick probability calibration (no official API calls)."""

from datetime import datetime, timedelta, timezone

from app.services.probability_calibration import (
    CALIBRATION_VERSION,
    apply_platt,
    build_calibration_artifact,
    calibrate_for_ev,
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


def test_ev_calibration_never_falls_back_to_raw_probability() -> None:
    artifact = {
        "version": CALIBRATION_VERSION,
        "markets": {
            "ah": {"deployable": False, "a": 1.0, "b": 0.0},
            "ah:home": {"deployable": True, "a": 0.0, "b": 0.0},
        },
    }
    assert calibrate_for_ev(artifact, "ah", "away", 0.7) == (None, None)
    probability, version = calibrate_for_ev(artifact, "ah", "home", 0.7)
    assert probability == 0.5
    assert version == f"{CALIBRATION_VERSION}:ah:home"
