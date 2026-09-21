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
        (start + timedelta(hours=index), "1x2:market", 0.8, (index % 5) < 3)
        for index in range(100)
    ]
    artifact = build_calibration_artifact(samples, trained_at=start)
    config = artifact["markets"]["1x2:market"]
    assert artifact["version"] == CALIBRATION_VERSION
    assert config["fit_samples"] == 80
    assert config["holdout_samples"] == 20
    assert config["deployable"] is True
    assert config["calibrated_holdout"]["brier"] < config["raw_holdout"]["brier"]


def test_uncalibrated_key_passes_the_raw_probability_through() -> None:
    # A cold start must still rank; calibration improves a probability, it does
    # not license the bet.
    artifact = {
        "version": CALIBRATION_VERSION,
        "markets": {
            "ah:market": {"deployable": False, "a": 1.0, "b": 0.0},
            "ah:market:home": {"deployable": True, "a": 0.0, "b": 0.0},
        },
    }
    assert calibrate_probability(artifact, "ah", "market", "away", 0.7) == (0.7, None)
    probability, version = calibrate_probability(artifact, "ah", "market", "home", 0.7)
    assert probability == 0.5
    assert version == f"{CALIBRATION_VERSION}:ah:market:home"


def test_market_and_model_estimators_never_share_one_calibrator() -> None:
    artifact = {
        "version": CALIBRATION_VERSION,
        "markets": {"ah:model": {"deployable": True, "a": 0.0, "b": 0.0}},
    }
    assert calibrate_probability(artifact, "ah", "market", "home", 0.7) == (0.7, None)
    assert calibrate_probability(artifact, "ah", "model", "home", 0.7)[0] == 0.5
