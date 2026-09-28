"""Optional Platt mapping for a probability that is already chosen.

Daily picks pass no artifact, so the raw board probability is what ranks.  A
caller may still inject a keyed calibrator; an unvalidated key passes the raw
value through.  Market and model estimators never share one fit.
"""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from app.core.config import BACKEND_ROOT

logger = logging.getLogger(__name__)

CALIBRATION_VERSION = "recommendation-source-platt-v3"
PROBABILITY_SOURCES = ("market", "model")
CALIBRATION_PATH = BACKEND_ROOT / "data" / "models" / "recommendation_model_calibration.json"
MIN_MARKET_SAMPLES = 80
MIN_HOLDOUT_SAMPLES = 20
HOLDOUT_RATIO = 0.20
EPS = 1e-6


def _clip_probability(value: float) -> float:
    return max(EPS, min(1.0 - EPS, float(value)))


def _logit(value: float) -> float:
    p = _clip_probability(value)
    return math.log(p / (1.0 - p))


def _sigmoid(value: np.ndarray | float) -> np.ndarray | float:
    clipped = np.clip(value, -20.0, 20.0)
    return 1.0 / (1.0 + np.exp(-clipped))


def fit_platt(
    probabilities: list[float],
    outcomes: list[bool],
    *,
    epochs: int = 1200,
    learning_rate: float = 0.03,
    l2: float = 0.02,
) -> tuple[float, float]:
    """Fit monotonic ``sigmoid(a * logit(p) + b)`` with mild identity shrinkage."""
    if len(probabilities) != len(outcomes) or not probabilities:
        return 1.0, 0.0
    x = np.asarray([_logit(p) for p in probabilities], dtype=np.float64)
    y = np.asarray(outcomes, dtype=np.float64)
    a = 1.0
    b = 0.0
    n = max(1, len(y))
    for _ in range(epochs):
        pred = np.asarray(_sigmoid(a * x + b), dtype=np.float64)
        residual = pred - y
        grad_a = float((residual * x).sum() / n + l2 * (a - 1.0))
        grad_b = float(residual.sum() / n + l2 * b)
        a = max(0.0, min(5.0, a - learning_rate * grad_a))
        b = max(-5.0, min(5.0, b - learning_rate * grad_b))
    return float(a), float(b)


def apply_platt(probability: float, a: float, b: float) -> float:
    value = float(_sigmoid(float(a) * _logit(probability) + float(b)))
    return _clip_probability(value)


def _metrics(probabilities: list[float], outcomes: list[bool]) -> dict[str, float]:
    if not probabilities:
        return {"brier": float("nan"), "log_loss": float("nan")}
    p = np.asarray([_clip_probability(v) for v in probabilities], dtype=np.float64)
    y = np.asarray(outcomes, dtype=np.float64)
    return {
        "brier": float(np.mean((p - y) ** 2)),
        "log_loss": float(-np.mean(y * np.log(p) + (1.0 - y) * np.log(1.0 - p))),
    }


def build_calibration_artifact(
    samples: list[tuple[datetime, str, float, bool]],
    *,
    trained_at: datetime | None = None,
) -> dict[str, Any]:
    """Build per-key calibrators with the latest 20% held out chronologically."""
    by_market: dict[str, list[tuple[datetime, float, bool]]] = {}
    for occurred_at, key, probability, outcome in samples:
        parts = key.split(":")
        if len(parts) < 2 or parts[0] not in {"1x2", "ah", "ou", "btts"}:
            continue
        if parts[1] not in PROBABILITY_SOURCES:
            continue
        by_market.setdefault(key, []).append(
            (occurred_at, _clip_probability(probability), bool(outcome))
        )

    markets: dict[str, Any] = {}
    for market, rows in sorted(by_market.items()):
        rows.sort(key=lambda row: row[0])
        n = len(rows)
        if n < MIN_MARKET_SAMPLES:
            markets[market] = {
                "deployable": False,
                "n_samples": n,
                "reason": f"need>={MIN_MARKET_SAMPLES} samples",
            }
            continue
        holdout_n = max(MIN_HOLDOUT_SAMPLES, int(n * HOLDOUT_RATIO))
        fit_rows = rows[:-holdout_n]
        holdout = rows[-holdout_n:]
        fit_p = [row[1] for row in fit_rows]
        fit_y = [row[2] for row in fit_rows]
        test_p = [row[1] for row in holdout]
        test_y = [row[2] for row in holdout]
        a, b = fit_platt(fit_p, fit_y)
        calibrated = [apply_platt(p, a, b) for p in test_p]
        raw_metrics = _metrics(test_p, test_y)
        calibrated_metrics = _metrics(calibrated, test_y)
        deployable = (
            calibrated_metrics["brier"] < raw_metrics["brier"]
            and calibrated_metrics["log_loss"] <= raw_metrics["log_loss"] + 1e-6
        )
        markets[market] = {
            "deployable": deployable,
            "n_samples": n,
            "fit_samples": len(fit_rows),
            "holdout_samples": len(holdout),
            "a": a,
            "b": b,
            "raw_holdout": raw_metrics,
            "calibrated_holdout": calibrated_metrics,
        }

    timestamp = trained_at or datetime.now(timezone.utc)
    return {
        "version": CALIBRATION_VERSION,
        "trained_at": timestamp.isoformat(),
        "trained_day": timestamp.date().isoformat(),
        "n_samples": len(samples),
        "markets": markets,
    }


def calibrate_probability(
    artifact: dict[str, Any] | None,
    market: str,
    source: str,
    direction: str,
    probability: float,
) -> tuple[float, str | None]:
    """Map a raw probability onto observed hit rate for its own estimator.

    Direction-specific calibrators win over the market-wide one.  When neither is
    validated the raw probability passes through untouched and the version is
    ``None`` — calibration improves ranking, it is not a licence to bet.
    """
    if not isinstance(artifact, dict) or artifact.get("version") != CALIBRATION_VERSION:
        return probability, None
    markets = artifact.get("markets") or {}
    for key in (f"{market}:{source}:{direction}", f"{market}:{source}"):
        config = markets.get(key)
        if not isinstance(config, dict) or not config.get("deployable"):
            continue
        try:
            calibrated = apply_platt(
                probability,
                float(config["a"]),
                float(config["b"]),
            )
        except (KeyError, TypeError, ValueError):
            continue
        return calibrated, f"{CALIBRATION_VERSION}:{key}"
    return probability, None


def load_calibration_artifact(path: Path | None = None) -> dict[str, Any]:
    target = path or CALIBRATION_PATH
    if not target.exists():
        return {}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
        return payload if payload.get("version") == CALIBRATION_VERSION else {}
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to load daily-pick calibration: %s", exc)
        return {}


