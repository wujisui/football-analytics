"""League-bucketed 1X2 odds calibration for the recommendation pipeline.

Input: match-winner decimal odds (or de-vigged implied probabilities).
Output: per-match calibrated probabilities with reliability metadata derived
from historical league-specific bias statistics.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import BACKEND_ROOT
from app.services.prediction import implied_probs_from_odds, normalize_probabilities
from app.services.probability_calibration import apply_platt, fit_platt

logger = logging.getLogger(__name__)

CALIBRATION_VERSION = "league-odds-platt-v1"
CALIBRATION_PATH = BACKEND_ROOT / "data" / "models" / "recommendation_calibration.json"

OUTCOMES = ("home", "draw", "away")
GLOBAL_BUCKET = "global"
MIN_LEAGUE_MATCHES = 60
MIN_OUTCOME_SAMPLES = 40
MIN_HOLDOUT_SAMPLES = 12
HOLDOUT_RATIO = 0.20
REFERENCE_SAMPLES = 150
EPS = 1e-6


@dataclass(frozen=True)
class _HistoryRow:
    occurred_at: datetime
    league_id: int
    implied_home: float
    implied_draw: float
    implied_away: float
    label: str


def _clip_probability(value: float) -> float:
    return max(EPS, min(1.0 - EPS, float(value)))


def _metrics(probabilities: list[float], outcomes: list[bool]) -> dict[str, float]:
    if not probabilities:
        return {"brier": float("nan"), "log_loss": float("nan")}
    import numpy as np

    p = np.asarray([_clip_probability(v) for v in probabilities], dtype=np.float64)
    y = np.asarray(outcomes, dtype=np.float64)
    return {
        "brier": float(np.mean((p - y) ** 2)),
        "log_loss": float(-np.mean(y * np.log(p) + (1.0 - y) * np.log(1.0 - p))),
    }


def _mean_bias(probabilities: list[float], outcomes: list[bool]) -> float:
    if not probabilities:
        return 0.0
    hits = sum(1 for hit in outcomes if hit)
    empirical = hits / len(outcomes)
    predicted = sum(probabilities) / len(probabilities)
    return float(predicted - empirical)


def _fit_outcome_calibrator(
    rows: list[tuple[datetime, float, bool]],
) -> dict[str, Any]:
    rows = sorted(rows, key=lambda row: row[0])
    n = len(rows)
    if n < MIN_OUTCOME_SAMPLES:
        return {
            "deployable": False,
            "n_samples": n,
            "reason": f"need>={MIN_OUTCOME_SAMPLES} samples",
        }

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

    return {
        "deployable": deployable,
        "n_samples": n,
        "fit_samples": len(fit_rows),
        "holdout_samples": len(holdout),
        "a": a,
        "b": b,
        "bias": _mean_bias(fit_p, fit_y),
        "raw_holdout": raw_metrics,
        "calibrated_holdout": calibrated_metrics,
    }


def _build_bucket(rows: list[_HistoryRow]) -> dict[str, Any]:
    outcome_rows: dict[str, list[tuple[datetime, float, bool]]] = {
        outcome: [] for outcome in OUTCOMES
    }
    for row in rows:
        implied = {
            "home": row.implied_home,
            "draw": row.implied_draw,
            "away": row.implied_away,
        }
        for outcome in OUTCOMES:
            outcome_rows[outcome].append(
                (row.occurred_at, implied[outcome], row.label == outcome)
            )

    outcomes: dict[str, Any] = {}
    for outcome in OUTCOMES:
        outcomes[outcome] = _fit_outcome_calibrator(outcome_rows[outcome])

    return {
        "n_matches": len(rows),
        "outcomes": outcomes,
    }


def build_calibration_artifact(
    rows: list[_HistoryRow],
    *,
    trained_at: datetime | None = None,
) -> dict[str, Any]:
    """Fit league buckets plus a global fallback from chronological history."""
    by_league: dict[int, list[_HistoryRow]] = {}
    for row in rows:
        by_league.setdefault(int(row.league_id), []).append(row)

    leagues: dict[str, Any] = {}
    for league_id, league_rows in sorted(by_league.items()):
        if len(league_rows) < MIN_LEAGUE_MATCHES:
            continue
        leagues[str(league_id)] = _build_bucket(league_rows)

    timestamp = trained_at or datetime.now(timezone.utc)
    return {
        "version": CALIBRATION_VERSION,
        "trained_at": timestamp.isoformat(),
        "trained_day": timestamp.date().isoformat(),
        "n_matches": len(rows),
        GLOBAL_BUCKET: _build_bucket(rows),
        "leagues": leagues,
    }


def _resolve_bucket(
    artifact: dict[str, Any] | None,
    league_id: int,
) -> tuple[str, dict[str, Any], int]:
    if not isinstance(artifact, dict) or artifact.get("version") != CALIBRATION_VERSION:
        return "raw", {}, 0

    league_key = str(int(league_id))
    league_bucket = (artifact.get("leagues") or {}).get(league_key)
    if isinstance(league_bucket, dict) and int(league_bucket.get("n_matches") or 0) >= MIN_LEAGUE_MATCHES:
        deployable = any(
            bool((league_bucket.get("outcomes") or {}).get(outcome, {}).get("deployable"))
            for outcome in OUTCOMES
        )
        if deployable:
            return league_key, league_bucket, int(league_bucket.get("n_matches") or 0)

    global_bucket = artifact.get(GLOBAL_BUCKET)
    if isinstance(global_bucket, dict):
        deployable = any(
            bool((global_bucket.get("outcomes") or {}).get(outcome, {}).get("deployable"))
            for outcome in OUTCOMES
        )
        if deployable:
            return GLOBAL_BUCKET, global_bucket, int(global_bucket.get("n_matches") or 0)

    return "raw", {}, int((global_bucket or {}).get("n_matches") or 0)


def _apply_bucket(
    implied: dict[str, float],
    bucket: dict[str, Any],
) -> tuple[dict[str, float], dict[str, float], list[str]]:
    outcomes_cfg = bucket.get("outcomes") or {}
    calibrated: dict[str, float] = {}
    bias: dict[str, float] = {}
    sources: list[str] = []

    for outcome in OUTCOMES:
        cfg = outcomes_cfg.get(outcome) or {}
        raw = _clip_probability(implied[outcome])
        if cfg.get("deployable"):
            value = apply_platt(raw, float(cfg["a"]), float(cfg["b"]))
            sources.append(outcome)
        else:
            value = raw
        calibrated[outcome] = _clip_probability(value)
        bias[outcome] = float(cfg.get("bias") or 0.0)

    return normalize_probabilities(calibrated), bias, sources


def _reliability_score(sample_size: int, bucket: dict[str, Any], used_outcomes: list[str]) -> float:
    if not used_outcomes:
        return 0.0
    outcomes_cfg = bucket.get("outcomes") or {}
    size_factor = min(1.0, sample_size / REFERENCE_SAMPLES)
    quality_scores: list[float] = []
    for outcome in used_outcomes:
        cfg = outcomes_cfg.get(outcome) or {}
        raw_brier = float((cfg.get("raw_holdout") or {}).get("brier") or 0.25)
        cal_brier = float((cfg.get("calibrated_holdout") or {}).get("brier") or raw_brier)
        if raw_brier > EPS:
            improvement = max(0.0, min(1.0, (raw_brier - cal_brier) / raw_brier))
        else:
            improvement = 0.0
        quality_scores.append(0.55 + 0.45 * improvement)
    quality = sum(quality_scores) / len(quality_scores)
    return float(max(0.0, min(1.0, size_factor * quality)))


def calibrate_implied_probs(
    *,
    match_id: int,
    league_id: int,
    implied: dict[str, float],
    artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Calibrate de-vigged 1X2 probabilities for one fixture."""
    base = normalize_probabilities(
        {
            "home": float(implied.get("home", 1 / 3)),
            "draw": float(implied.get("draw", 1 / 3)),
            "away": float(implied.get("away", 1 / 3)),
        }
    )
    bucket_name, bucket, sample_size = _resolve_bucket(artifact, league_id)

    if bucket_name == "raw" or not bucket:
        return {
            "match_id": int(match_id),
            "calibrated_home_prob": base["home"],
            "calibrated_draw_prob": base["draw"],
            "calibrated_away_prob": base["away"],
            "reliability": 0.0,
            "sample_size": sample_size,
            "calibration_bias": {"home": 0.0, "draw": 0.0, "away": 0.0},
        }

    calibrated, bias, used = _apply_bucket(base, bucket)
    reliability = _reliability_score(sample_size, bucket, used or list(OUTCOMES))
    return {
        "match_id": int(match_id),
        "calibrated_home_prob": calibrated["home"],
        "calibrated_draw_prob": calibrated["draw"],
        "calibrated_away_prob": calibrated["away"],
        "reliability": reliability,
        "sample_size": sample_size,
        "calibration_bias": bias,
    }


def calibrate_match(
    *,
    match_id: int,
    league_id: int,
    odds: dict[str, Any] | None,
    artifact: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Calibrate match-winner odds for one fixture."""
    implied = implied_probs_from_odds(odds)
    if implied is None:
        return None
    if artifact is None:
        artifact = load_calibration_artifact()
    return calibrate_implied_probs(
        match_id=match_id,
        league_id=league_id,
        implied=implied,
        artifact=artifact,
    )


def load_calibration_artifact(path: Path | None = None) -> dict[str, Any]:
    target = path or CALIBRATION_PATH
    if not target.exists():
        return {}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
        return payload if payload.get("version") == CALIBRATION_VERSION else {}
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to load recommendation calibration: %s", exc)
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


async def collect_calibration_history(db: Any) -> list[_HistoryRow]:
    """Gather pre-match implied 1X2 odds with settled FT labels."""
    from sqlalchemy import select

    from app.models.fixture import Fixture
    from app.models.match_feature import MatchFeature
    from app.models.pre_match_data import PreMatchData
    from app.services.features import FEATURE_VERSION, extract_features, loads_features
    from app.services.ml_predictor import outcome_label
    from app.services.prematch_package import loads_json, package_from_record

    rows: list[_HistoryRow] = []
    seen: set[int] = set()

    q = await db.execute(
        select(MatchFeature, Fixture)
        .join(Fixture, Fixture.id == MatchFeature.fixture_id)
        .where(
            MatchFeature.feature_version == FEATURE_VERSION,
            Fixture.home_goals.is_not(None),
            Fixture.away_goals.is_not(None),
            Fixture.status.in_(["finished", "ft", "aet", "pen"]),
        )
        .order_by(Fixture.date.asc(), Fixture.id.asc())
    )
    for feat, fixture in q.all():
        label = feat.label or outcome_label(fixture.home_goals, fixture.away_goals)
        if label not in OUTCOMES:
            continue
        features = loads_features(feat.features_json)
        if float(features.get("has_odds") or 0.0) < 0.5:
            continue
        rows.append(
            _HistoryRow(
                occurred_at=fixture.date,
                league_id=int(fixture.league_id),
                implied_home=float(features["odds_home"]),
                implied_draw=float(features["odds_draw"]),
                implied_away=float(features["odds_away"]),
                label=label,
            )
        )
        seen.add(int(fixture.id))

    q2 = await db.execute(
        select(PreMatchData, Fixture)
        .join(Fixture, Fixture.id == PreMatchData.fixture_id)
        .where(
            Fixture.home_goals.is_not(None),
            Fixture.away_goals.is_not(None),
            Fixture.status.in_(["finished", "ft", "aet", "pen"]),
        )
        .order_by(Fixture.date.asc(), Fixture.id.asc())
    )
    for stored, fixture in q2.all():
        if int(fixture.id) in seen:
            continue
        label = outcome_label(fixture.home_goals, fixture.away_goals)
        if label not in OUTCOMES:
            continue
        package = package_from_record(stored)
        if not package:
            package = {
                "home_form": loads_json(stored.home_form_json, {}),
                "away_form": loads_json(stored.away_form_json, {}),
                "head_to_head": loads_json(stored.h2h_json, {}),
                "odds": loads_json(stored.odds_json, {"available": False}),
                "standings": loads_json(stored.standings_json, {}),
                "injuries": loads_json(stored.injuries_json, {}),
            }
        features = extract_features(package)
        if float(features.get("has_odds") or 0.0) < 0.5:
            continue
        rows.append(
            _HistoryRow(
                occurred_at=fixture.date,
                league_id=int(fixture.league_id),
                implied_home=float(features["odds_home"]),
                implied_draw=float(features["odds_draw"]),
                implied_away=float(features["odds_away"]),
                label=label,
            )
        )

    return rows


async def train_from_frozen_history(
    db: Any,
    *,
    now: datetime | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Train once per UTC day from frozen pre-match odds and settled scores."""
    current = now or datetime.now(timezone.utc)
    existing = load_calibration_artifact()
    if not force and existing.get("trained_day") == current.date().isoformat():
        return existing

    history = await collect_calibration_history(db)
    artifact = build_calibration_artifact(history, trained_at=current)
    save_calibration_artifact(artifact)
    logger.info(
        "Recommendation calibration trained matches=%s leagues=%s",
        artifact.get("n_matches"),
        len(artifact.get("leagues") or {}),
    )
    return artifact
