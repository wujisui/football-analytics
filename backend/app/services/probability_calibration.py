"""Time-safe probability calibration for daily auto-pick ranking.

Raw candidate confidence comes from different sources (1X2/AH models and
two-way market probabilities).  A per-market Platt layer maps those values to
observed hit probability before expected return is calculated.
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

CALIBRATION_VERSION = "daily-pick-platt-v1"
CALIBRATION_PATH = BACKEND_ROOT / "data" / "models" / "daily_pick_calibration.json"
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
    """Build per-market calibrators with the latest 20% held out chronologically."""
    by_market: dict[str, list[tuple[datetime, float, bool]]] = {}
    for occurred_at, market, probability, outcome in samples:
        if market not in {"1x2", "ah", "ou", "btts"}:
            continue
        by_market.setdefault(market, []).append(
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
    probability: float,
) -> float:
    """Apply a validated market calibrator; otherwise return the raw probability."""
    raw = _clip_probability(probability)
    if not isinstance(artifact, dict) or artifact.get("version") != CALIBRATION_VERSION:
        return raw
    config = (artifact.get("markets") or {}).get(market)
    if not isinstance(config, dict) or not config.get("deployable"):
        return raw
    try:
        return apply_platt(raw, float(config["a"]), float(config["b"]))
    except (KeyError, TypeError, ValueError):
        return raw


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


def save_calibration_artifact(
    artifact: dict[str, Any],
    path: Path | None = None,
) -> None:
    target = path or CALIBRATION_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


async def train_from_frozen_history(
    db: Any,
    *,
    now: datetime | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Train once per UTC day from frozen predictions and settled local scores."""
    current = now or datetime.now(timezone.utc)
    existing = load_calibration_artifact()
    if not force and existing.get("trained_day") == current.date().isoformat():
        return existing

    # Local imports avoid a module cycle: auto_favorites consumes this artifact.
    from sqlalchemy import select

    from app.models.fixture import Fixture
    from app.models.match_feature import MatchFeature
    from app.models.pre_match_data import PreMatchData
    from app.services.auto_favorites import _market_candidates
    from app.services.prematch_package import package_from_record, rehydrate_odds_markets
    from app.services.results_accuracy import settle_auto_pick_hit

    rows = (
        await db.execute(
            select(Fixture, PreMatchData, MatchFeature)
            .join(PreMatchData, PreMatchData.fixture_id == Fixture.id)
            .outerjoin(MatchFeature, MatchFeature.fixture_id == Fixture.id)
            .where(
                Fixture.home_goals.is_not(None),
                Fixture.away_goals.is_not(None),
                Fixture.status.in_(["finished", "ft", "aet", "pen"]),
            )
            .order_by(Fixture.date, Fixture.id)
        )
    ).all()

    # A fixture can have duplicate feature joins in legacy DBs; keep one.
    by_fixture: dict[int, tuple[Any, Any, Any]] = {}
    for fixture, stored, feature in rows:
        previous = by_fixture.get(int(fixture.id))
        if previous is None or (feature is not None and previous[2] is None):
            by_fixture[int(fixture.id)] = (fixture, stored, feature)

    samples: list[tuple[datetime, str, float, bool]] = []
    for fixture, stored, feature in by_fixture.values():
        package = package_from_record(stored, match_start_time=fixture.date)
        odds_raw = package.get("odds") if isinstance(package, dict) else None
        odds = (
            rehydrate_odds_markets(odds_raw)
            if isinstance(odds_raw, dict)
            else None
        )
        for candidate in _market_candidates(
            stored,
            odds=odds if isinstance(odds, dict) else None,
            feature=feature,
            calibration=None,
        ):
            hit = settle_auto_pick_hit(
                market=candidate.market,
                lean=candidate.lean,
                home_goals=fixture.home_goals,
                away_goals=fixture.away_goals,
            )
            if hit is not None:
                samples.append(
                    (
                        fixture.date,
                        candidate.market,
                        candidate.raw_confidence,
                        hit,
                    )
                )

    artifact = build_calibration_artifact(samples, trained_at=current)
    save_calibration_artifact(artifact)
    logger.info(
        "Daily-pick calibration trained samples=%s markets=%s",
        len(samples),
        {
            key: bool(value.get("deployable"))
            for key, value in (artifact.get("markets") or {}).items()
        },
    )
    return artifact
