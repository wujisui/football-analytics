"""1X2 probability model: multi-factor heuristic + optional trained logistic.

Design goals
------------
- While labeled samples are scarce (``source=multifactor``), **odds are a strong
  prior**: bookmakers are not charities; the board aggregates information.
  Match-fixing / one-off shocks exist but are not the base rate for every game.
- Form, H2H, ranks, injuries, and streak / mean-reversion still matter; odds
  should not be the *only* driver, but they must move the output when lines shift.
- When enough labeled ``match_features`` rows exist, fit multinomial logistic
  regression and prefer it; learned weights then replace these hand constants.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from app.core.config import BACKEND_ROOT, get_settings
from app.services.features import (
    FEATURE_NAMES,
    FEATURE_VERSION,
    DEFAULT_PROB,
    extract_features,
    feature_vector,
    loads_features,
    softmax3,
)

logger = logging.getLogger(__name__)

# Default floor; runtime uses Settings.ML_MIN_TRAIN_SAMPLES.
MIN_TRAIN_SAMPLES = 30
MODEL_DIR = BACKEND_ROOT / "data" / "models"
MODEL_META_NAME = "1x2_meta.json"
MODEL_WEIGHTS_NAME = "1x2_weights.npz"

# Multi-factor weights (logits). Odds kept strong while data is thin.
_W_FORM = 1.15
_W_H2H = 0.45
_W_RANK = 0.35
_W_INJURY = 0.25
_W_ODDS = 1.25  # bookmaker board = strong prior until ML is trained
_W_ODDS_THIN_FORM = 0.45  # extra when recent form sample is thin
_W_REVERSION = 1.00
_W_HOME_ADV = 0.22
_W_DRAW_BASE = 0.05


@dataclass
class ProbabilityPrediction:
    probs: dict[str, float]
    source: str  # "ml" | "multifactor" | "form_fallback"
    features: dict[str, float]
    feature_version: str = FEATURE_VERSION


def normalize_probabilities(probs: dict[str, float]) -> dict[str, float]:
    total = sum(max(float(v), 0.0) for v in probs.values())
    if total <= 0:
        return {"home": DEFAULT_PROB, "draw": DEFAULT_PROB, "away": DEFAULT_PROB}
    return {k: max(float(v), 0.0) / total for k, v in probs.items()}


def multifactor_probabilities(features: dict[str, float]) -> dict[str, float]:
    """Explicit multi-factor logits → probabilities (no sklearn required)."""
    f = features
    home_form = 0.55 * f["home_wr_5"] + 0.45 * f["home_wr_10"]
    away_form = 0.55 * f["away_wr_5"] + 0.45 * f["away_wr_10"]
    draw_form = 0.5 * (f["home_dr_5"] + f["away_dr_5"])

    # Goal-diff nudge (scaled down).
    home_form += 0.04 * max(-3.0, min(3.0, f["home_gd_avg_5"]))
    away_form += 0.04 * max(-3.0, min(3.0, f["away_gd_avg_5"]))

    # Thin recent form → lean harder on the market (still not odds-only).
    # wr_* default to 1/3 when empty; treat near-flat both sides as thin signal.
    thin_form = (
        abs(home_form - DEFAULT_PROB) < 0.04
        and abs(away_form - DEFAULT_PROB) < 0.04
    )
    odds_w = _W_ODDS + (_W_ODDS_THIN_FORM if thin_form else 0.0)

    logit_h = (
        _W_FORM * (home_form - away_form)
        + _W_H2H * (f["h2h_home_rate"] - f["h2h_away_rate"]) * (0.4 + 0.6 * f["h2h_played_n"])
        + _W_RANK * f["rank_diff"]
        - _W_INJURY * f["home_injuries_n"]
        + _W_INJURY * f["away_injuries_n"]
        + odds_w * f["has_odds"] * (f["odds_home"] - DEFAULT_PROB)
        + _W_REVERSION * f["home_reversion"]
        - _W_REVERSION * f["away_reversion"]
        + _W_HOME_ADV * f["home_advantage"]
    )
    logit_a = (
        _W_FORM * (away_form - home_form)
        + _W_H2H * (f["h2h_away_rate"] - f["h2h_home_rate"]) * (0.4 + 0.6 * f["h2h_played_n"])
        - _W_RANK * f["rank_diff"]
        - _W_INJURY * f["away_injuries_n"]
        + _W_INJURY * f["home_injuries_n"]
        + odds_w * f["has_odds"] * (f["odds_away"] - DEFAULT_PROB)
        + _W_REVERSION * f["away_reversion"]
        - _W_REVERSION * f["home_reversion"]
    )
    # Draws rise when sides are close, both draw a lot, or both are "due" to stop
    # extreme streaks (champion eventually draws; weak side eventually stops losing).
    closeness = 1.0 - abs(home_form - away_form)
    streak_draw = 0.0
    if f["home_win_streak"] >= 4 or f["away_win_streak"] >= 4:
        streak_draw += 0.08
    if f["home_loss_streak"] >= 4 or f["away_loss_streak"] >= 4:
        streak_draw += 0.06
    logit_d = (
        _W_DRAW_BASE
        + 0.9 * draw_form
        + 0.35 * closeness
        + _W_H2H * f["h2h_draw_rate"] * (0.4 + 0.6 * f["h2h_played_n"])
        + odds_w * f["has_odds"] * (f["odds_draw"] - DEFAULT_PROB) * 0.85
        + streak_draw
        # Mutual reversion → more chaos / draw mass
        + 0.25 * max(0.0, f["home_reversion"]) * max(0.0, f["away_reversion"])
    )

    return normalize_probabilities(softmax3(logit_h, logit_d, logit_a))


class _SoftmaxLogReg:
    """Minimal multinomial logistic regression (no sklearn dependency)."""

    def __init__(self, n_features: int, n_classes: int = 3, seed: int = 42) -> None:
        rng = np.random.default_rng(seed)
        self.W = rng.normal(0, 0.01, size=(n_classes, n_features))
        self.b = np.zeros(n_classes)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        logits = X @ self.W.T + self.b
        logits = logits - logits.max(axis=1, keepdims=True)
        exp = np.exp(logits)
        return exp / exp.sum(axis=1, keepdims=True)

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        *,
        epochs: int = 400,
        lr: float = 0.08,
        l2: float = 0.02,
    ) -> dict[str, float]:
        n = X.shape[0]
        history: dict[str, float] = {}
        for epoch in range(epochs):
            probs = self.predict_proba(X)
            # One-hot
            Y = np.zeros_like(probs)
            Y[np.arange(n), y] = 1.0
            grad_logits = (probs - Y) / n
            grad_W = grad_logits.T @ X + l2 * self.W
            grad_b = grad_logits.sum(axis=0)
            self.W -= lr * grad_W
            self.b -= lr * grad_b
            if epoch == epochs - 1 or epoch % 50 == 0:
                # Cross-entropy
                eps = 1e-9
                ll = -np.mean(np.log(probs[np.arange(n), y] + eps))
                history["log_loss"] = float(ll)
        return history

    def save(self, path: Path) -> None:
        np.savez_compressed(path, W=self.W, b=self.b)

    @classmethod
    def load(cls, path: Path) -> "_SoftmaxLogReg":
        data = np.load(path)
        obj = cls(n_features=data["W"].shape[1], n_classes=data["W"].shape[0])
        obj.W = data["W"]
        obj.b = data["b"]
        return obj


_LABEL_TO_IDX = {"home": 0, "draw": 1, "away": 2}
_IDX_TO_LABEL = {0: "home", 1: "draw", 2: "away"}


def model_paths() -> tuple[Path, Path]:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    return MODEL_DIR / MODEL_WEIGHTS_NAME, MODEL_DIR / MODEL_META_NAME


def load_trained_model() -> tuple[_SoftmaxLogReg | None, dict[str, Any]]:
    weights_path, meta_path = model_paths()
    if not weights_path.exists() or not meta_path.exists():
        return None, {}
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("feature_version") != FEATURE_VERSION:
            logger.warning("Trained model feature_version mismatch; ignoring artifact")
            return None, meta
        model = _SoftmaxLogReg.load(weights_path)
        return model, meta
    except Exception as exc:
        logger.warning("Failed to load trained 1X2 model: %s", exc)
        return None, {}


def min_train_samples() -> int:
    try:
        return max(10, int(get_settings().ML_MIN_TRAIN_SAMPLES))
    except Exception:
        return MIN_TRAIN_SAMPLES


def predict_probabilities(package: dict[str, Any] | None) -> ProbabilityPrediction:
    """Primary inference: trained model when ready, else multi-factor.

    Switch rule: if ``data/models/1x2_*.`` exists and was trained on
    ``>= ML_MIN_TRAIN_SAMPLES`` labeled rows, use ``source=ml``; otherwise
    ``multifactor`` (or flat prior). No manual toggle required.
    """
    features = extract_features(package)
    model, meta = load_trained_model()
    threshold = min_train_samples()
    if model is not None and int(meta.get("n_samples", 0)) >= threshold:
        X = np.asarray([feature_vector(features)], dtype=np.float64)
        proba = model.predict_proba(X)[0]
        probs = normalize_probabilities(
            {"home": float(proba[0]), "draw": float(proba[1]), "away": float(proba[2])}
        )
        return ProbabilityPrediction(probs=probs, source="ml", features=features)

    pkg = package or {}
    home_played = int((pkg.get("home_form") or {}).get("played") or 0) if isinstance(pkg.get("home_form"), dict) else 0
    away_played = int((pkg.get("away_form") or {}).get("played") or 0) if isinstance(pkg.get("away_form"), dict) else 0
    has_form = home_played > 0 or away_played > 0
    usable = (
        has_form
        or features["h2h_played_n"] > 0
        or features["has_odds"] > 0
        or abs(features["rank_diff"]) > 0
    )
    if not usable:
        return ProbabilityPrediction(
            probs={"home": DEFAULT_PROB, "draw": DEFAULT_PROB, "away": DEFAULT_PROB},
            source="form_fallback",
            features=features,
        )

    probs = multifactor_probabilities(features)
    return ProbabilityPrediction(probs=probs, source="multifactor", features=features)


def train_from_rows(
    rows: list[tuple[dict[str, float], str]],
) -> dict[str, Any]:
    """Fit softmax logistic on (features, label) rows and persist artifact."""
    labeled = [(f, y) for f, y in rows if y in _LABEL_TO_IDX]
    n = len(labeled)
    threshold = min_train_samples()
    if n < threshold:
        return {
            "ok": False,
            "reason": f"need>={threshold} labeled samples, got {n}",
            "n_samples": n,
            "min_train_samples": threshold,
        }

    X = np.asarray([feature_vector(f) for f, _ in labeled], dtype=np.float64)
    y = np.asarray([_LABEL_TO_IDX[lab] for _, lab in labeled], dtype=np.int64)

    # Time-ordered holdout: last 20% as eval (caller should pass time-sorted rows).
    split = max(threshold - 5, int(n * 0.8))
    X_train, y_train = X[:split], y[:split]
    X_val, y_val = X[split:], y[split:]

    model = _SoftmaxLogReg(n_features=X.shape[1])
    history = model.fit(X_train, y_train)

    def _metrics(Xm: np.ndarray, ym: np.ndarray) -> dict[str, float]:
        if len(ym) == 0:
            return {"log_loss": float("nan"), "accuracy": float("nan")}
        p = model.predict_proba(Xm)
        eps = 1e-9
        ll = float(-np.mean(np.log(p[np.arange(len(ym)), ym] + eps)))
        acc = float(np.mean(np.argmax(p, axis=1) == ym))
        return {"log_loss": ll, "accuracy": acc}

    train_m = _metrics(X_train, y_train)
    val_m = _metrics(X_val, y_val) if len(y_val) else train_m

    # Refit on all data for deployment.
    model.fit(X, y, epochs=500)
    weights_path, meta_path = model_paths()
    model.save(weights_path)
    meta = {
        "feature_version": FEATURE_VERSION,
        "feature_names": FEATURE_NAMES,
        "n_samples": n,
        "min_train_samples": threshold,
        "train_metrics": train_m,
        "val_metrics": val_m,
        "fit_history": history,
        "classes": ["home", "draw", "away"],
        "trained_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(
        "Trained 1X2 model n=%s val_logloss=%s val_acc=%s → inference will use source=ml",
        n,
        val_m.get("log_loss"),
        val_m.get("accuracy"),
    )
    return {"ok": True, **meta, "weights_path": str(weights_path)}


def outcome_label(home_goals: int | None, away_goals: int | None) -> str | None:
    if home_goals is None or away_goals is None:
        return None
    if home_goals > away_goals:
        return "home"
    if home_goals < away_goals:
        return "away"
    return "draw"


async def persist_match_features(
    session: Any,
    fixture_id: int,
    features: dict[str, float],
    probs: dict[str, float],
    source: str,
    label: str | None = None,
) -> None:
    """Upsert match_features row (does not commit)."""
    from sqlalchemy import select

    from app.models.match_feature import MatchFeature
    from app.services.features import dumps_features

    result = await session.execute(
        select(MatchFeature).where(
            MatchFeature.fixture_id == fixture_id,
            MatchFeature.feature_version == FEATURE_VERSION,
        )
    )
    row = result.scalar_one_or_none()
    payload = {
        "features_json": dumps_features(features),
        "model_source": source,
        "home_win_prob": probs.get("home"),
        "draw_prob": probs.get("draw"),
        "away_win_prob": probs.get("away"),
    }
    if label:
        payload["label"] = label
    if row is None:
        session.add(
            MatchFeature(
                fixture_id=fixture_id,
                feature_version=FEATURE_VERSION,
                **payload,
            )
        )
    else:
        for key, value in payload.items():
            setattr(row, key, value)


async def collect_training_rows(session: Any) -> list[tuple[dict[str, float], str]]:
    """Join finished fixtures with stored features (and backfill from pre_match)."""
    from sqlalchemy import select

    from app.models.fixture import Fixture
    from app.models.match_feature import MatchFeature
    from app.models.pre_match_data import PreMatchData
    from app.services.prematch_package import loads_json, package_from_record

    rows: list[tuple[dict[str, float], str]] = []

    # Prefer durable match_features with labels.
    q = await session.execute(
        select(MatchFeature, Fixture)
        .join(Fixture, Fixture.id == MatchFeature.fixture_id)
        .where(
            MatchFeature.feature_version == FEATURE_VERSION,
            Fixture.status == "finished",
            Fixture.home_goals.is_not(None),
            Fixture.away_goals.is_not(None),
        )
        .order_by(Fixture.date.asc())
    )
    seen: set[int] = set()
    for feat, fixture in q.all():
        label = feat.label or outcome_label(fixture.home_goals, fixture.away_goals)
        if not label:
            continue
        features = loads_features(feat.features_json)
        rows.append((features, label))
        seen.add(fixture.id)

    # Backfill from pre_match_data packages still on disk.
    q2 = await session.execute(
        select(PreMatchData, Fixture)
        .join(Fixture, Fixture.id == PreMatchData.fixture_id)
        .where(
            Fixture.status == "finished",
            Fixture.home_goals.is_not(None),
            Fixture.away_goals.is_not(None),
        )
        .order_by(Fixture.date.asc())
    )
    for stored, fixture in q2.all():
        if fixture.id in seen:
            continue
        package = package_from_record(stored)
        if not package:
            # Minimal package from JSON fields
            package = {
                "home_form": loads_json(stored.home_form_json, {}),
                "away_form": loads_json(stored.away_form_json, {}),
                "head_to_head": loads_json(stored.h2h_json, {}),
                "odds": loads_json(stored.odds_json, {"available": False}),
                "standings": loads_json(stored.standings_json, {}),
                "injuries": loads_json(stored.injuries_json, {}),
            }
        label = outcome_label(fixture.home_goals, fixture.away_goals)
        if not label:
            continue
        features = extract_features(package)
        rows.append((features, label))
        # Persist for next train / cleanup survival
        await persist_match_features(
            session,
            fixture.id,
            features,
            {
                "home": stored.home_win_prob or DEFAULT_PROB,
                "draw": stored.draw_prob or DEFAULT_PROB,
                "away": stored.away_win_prob or DEFAULT_PROB,
            },
            source="backfill",
            label=label,
        )
        seen.add(fixture.id)

    await session.commit()
    return rows


async def train_model_from_db(session: Any) -> dict[str, Any]:
    rows = await collect_training_rows(session)
    return train_from_rows(rows)


async def maybe_auto_train_model(session: Any | None = None) -> dict[str, Any]:
    """Retrain when local labeled rows grew past the threshold / last fit.

    Intended to run after ``capture_finished_results`` labels new FT outcomes.
    Until the threshold is met, returns skipped and inference stays multifactor.
    Once a model is written, ``predict_probabilities`` automatically uses it.
    """
    settings = get_settings()
    if not settings.ML_AUTO_TRAIN:
        return {"ok": False, "skipped": True, "reason": "ML_AUTO_TRAIN=false"}

    async def _run(sess: Any) -> dict[str, Any]:
        rows = await collect_training_rows(sess)
        n = len(rows)
        threshold = min_train_samples()
        _, meta = load_trained_model()
        prev_n = int(meta.get("n_samples", 0)) if meta else 0

        if n < threshold:
            logger.info(
                "ML auto-train skipped: labeled=%s < threshold=%s (keep multifactor)",
                n,
                threshold,
            )
            return {
                "ok": False,
                "skipped": True,
                "reason": "below_threshold",
                "n_samples": n,
                "min_train_samples": threshold,
                "inference": "multifactor",
            }

        if prev_n > 0 and n <= prev_n:
            logger.info(
                "ML auto-train skipped: no new labels (labeled=%s, last_train=%s)",
                n,
                prev_n,
            )
            return {
                "ok": False,
                "skipped": True,
                "reason": "no_new_labels",
                "n_samples": n,
                "last_trained_n": prev_n,
                "inference": "ml",
            }

        result = train_from_rows(rows)
        if result.get("ok"):
            result["inference"] = "ml"
            result["auto"] = True
        return result

    if session is not None:
        return await _run(session)

    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as sess:
        return await _run(sess)


def model_status() -> dict[str, Any]:
    """Snapshot for ops / plan progress (no DB required for artifact side)."""
    threshold = min_train_samples()
    model, meta = load_trained_model()
    ready = model is not None and int(meta.get("n_samples", 0)) >= threshold
    return {
        "inference_mode": "ml" if ready else "multifactor",
        "min_train_samples": threshold,
        "trained_n_samples": int(meta.get("n_samples", 0)) if meta else 0,
        "artifact_ready": ready,
        "feature_version": FEATURE_VERSION,
        "trained_at": meta.get("trained_at") if meta else None,
    }


def label_finished_features(session_sync_note: str = "") -> None:
    """Placeholder for sync helpers; async path uses outcome_label."""
    _ = session_sync_note
