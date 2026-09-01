"""Asian handicap probability: market baseline + validated binary logistic correction."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import numpy as np

from app.core.config import BACKEND_ROOT, get_settings
from app.services.ah_features import (
    AH_FEATURE_VERSION,
    AH_FEATURE_NAMES,
    ah_feature_vector,
    build_ah_features,
    dumps_ah_features,
    extract_main_ah_line,
    format_handicap_lean_text,
    loads_ah_features,
    pick_to_lean,
    settle_ah_label,
)
from app.services.features import FEATURE_VERSION, dumps_features, extract_features

logger = logging.getLogger(__name__)

MODEL_DIR = BACKEND_ROOT / "data" / "models"
MODEL_WEIGHTS_NAME = "ah_v3_weights.npz"
MODEL_META_NAME = "ah_v3_meta.json"

_LABEL_TO_IDX = {"no_cover": 0, "cover": 1}
TRAIN_LABELS = frozenset(_LABEL_TO_IDX)
MIN_HOLDOUT_SAMPLES = 20
MODEL_MARKET_BLEND = 0.5


@dataclass
class HandicapPrediction:
    cover_prob: float
    pick: str  # cover | no_cover | push | slash-separated dual pick
    source: str  # market_implied | ml
    line_f: float | None = None
    market_note: str = ""


class _BinaryLogReg:
    def __init__(self, n_features: int, seed: int = 42) -> None:
        rng = np.random.default_rng(seed)
        self.w = rng.normal(0, 0.01, size=n_features)
        self.b = 0.0

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        z = X @ self.w + self.b
        z = np.clip(z, -20, 20)
        return 1.0 / (1.0 + np.exp(-z))

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        *,
        epochs: int = 500,
        lr: float = 0.06,
        l2: float = 0.02,
    ) -> dict[str, float]:
        n = X.shape[0]
        history: dict[str, float] = {}
        for epoch in range(epochs):
            p = self.predict_proba(X)
            grad_z = (p - y) / n
            grad_w = X.T @ grad_z + l2 * self.w
            grad_b = float(grad_z.sum())
            self.w -= lr * grad_w
            self.b -= lr * grad_b
            if epoch == epochs - 1 or epoch % 50 == 0:
                eps = 1e-9
                ll = -float(np.mean(y * np.log(p + eps) + (1 - y) * np.log(1 - p + eps)))
                acc = float(np.mean((p >= 0.5) == (y >= 0.5)))
                history["log_loss"] = ll
                history["accuracy"] = acc
        return history

    def save(self, path: Any) -> None:
        np.savez_compressed(path, w=self.w, b=np.asarray([self.b]))

    @classmethod
    def load(cls, path: Any) -> "_BinaryLogReg":
        data = np.load(path)
        obj = cls(n_features=len(data["w"]))
        obj.w = data["w"]
        obj.b = float(data["b"][0])
        return obj


def min_train_samples() -> int:
    return int(get_settings().ML_AH_MIN_TRAIN_SAMPLES)


def model_paths() -> tuple[Any, Any]:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    return MODEL_DIR / MODEL_WEIGHTS_NAME, MODEL_DIR / MODEL_META_NAME


def load_trained_model() -> tuple[_BinaryLogReg | None, dict[str, Any]]:
    weights_path, meta_path = model_paths()
    if not weights_path.exists() or not meta_path.exists():
        return None, {}
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("ah_feature_version") != AH_FEATURE_VERSION:
            logger.warning("Trained AH model ah_feature_version mismatch; ignoring artifact")
            return None, meta
        model = _BinaryLogReg.load(weights_path)
        return model, meta
    except Exception as exc:
        logger.warning("Failed to load AH model: %s", exc)
        return None, {}


def _artifact_is_deployable(
    model: _BinaryLogReg | None,
    meta: dict[str, Any],
) -> bool:
    return (
        model is not None
        and int(meta.get("n_samples", 0)) >= min_train_samples()
        and bool(meta.get("deployable", False))
    )


def _beats_market_baseline(
    model_metrics: dict[str, float],
    market_metrics: dict[str, float],
) -> bool:
    """Require the time-holdout model to improve both probability metrics."""
    return (
        float(model_metrics["log_loss"]) < float(market_metrics["log_loss"])
        and float(model_metrics["brier"]) < float(market_metrics["brier"])
    )


def _structural_pick(
    odds: dict[str, Any] | None,
) -> HandicapPrediction | None:
    """Choose the main AH side with the higher de-vig implied probability.

    The handicap analyzer describes its own two-way market. It must not copy a
    1X2 direction or let a reference score override the quoted AH board.
    """
    line_f, home_odd, away_odd = extract_main_ah_line(odds)
    if line_f is None or home_odd is None or away_odd is None:
        return None
    home_inv, away_inv = 1.0 / home_odd, 1.0 / away_odd
    total = home_inv + away_inv
    if total <= 0:
        return None
    cover_prob = home_inv / total
    away_prob = away_inv / total
    if abs(cover_prob - away_prob) <= 1e-9:
        pick = "cover/no_cover"
        note = (
            f"主盘去水概率让胜 {cover_prob:.1%}、让负 {away_prob:.1%}，"
            "两侧持平"
        )
    else:
        pick = "cover" if cover_prob > away_prob else "no_cover"
        note = (
            f"主盘去水概率让胜 {cover_prob:.1%}、让负 {away_prob:.1%}，"
            f"取{pick_to_lean(pick)}"
        )
    return HandicapPrediction(cover_prob, pick, "market_implied", line_f, note)


def _model_prediction(
    ah_features: dict[str, float],
    line_f: float,
) -> HandicapPrediction:
    """Use a validated model as a conservative correction to market probability."""
    market_prob = max(
        0.0, min(1.0, float(ah_features.get("ah_implied_cover", 0.5)))
    )
    model, meta = load_trained_model()
    if not _artifact_is_deployable(model, meta):
        pick = (
            "cover/no_cover"
            if abs(market_prob - 0.5) <= 1e-9
            else ("cover" if market_prob > 0.5 else "no_cover")
        )
        return HandicapPrediction(market_prob, pick, "market_implied", line_f)

    X = np.asarray([ah_feature_vector(ah_features)], dtype=np.float64)
    model_prob = max(0.0, min(1.0, float(model.predict_proba(X)[0])))
    cover_prob = market_prob + MODEL_MARKET_BLEND * (model_prob - market_prob)
    if abs(cover_prob - 0.5) <= 1e-9:
        pick = "cover/no_cover"
    else:
        pick = "cover" if cover_prob > 0.5 else "no_cover"
    note = (
        f"主盘去水概率让胜 {market_prob:.1%}、让负 {1.0 - market_prob:.1%}；"
        f"合格模型估计让胜 {model_prob:.1%}，保守修正为 {cover_prob:.1%}，"
        f"取{pick_to_lean(pick)}"
    )
    return HandicapPrediction(cover_prob, pick, "ml", line_f, note)


def predict_handicap(
    odds: dict[str, Any] | None,
    *,
    package: dict[str, Any] | None = None,
    league_id: int | None = None,
    ah_features: dict[str, float] | None = None,
    features: dict[str, float] | None = None,
) -> HandicapPrediction | None:
    """Read the main AH direction, allowing only a validated model to correct it."""
    pkg = package or {}
    if odds and isinstance(odds, dict):
        pkg = {**pkg, "odds": odds}

    if ah_features is None:
        ah_features, line_f, _, _ = build_ah_features(pkg, league_id=league_id)
    else:
        line_f, _, _ = extract_main_ah_line(pkg.get("odds") if isinstance(pkg.get("odds"), dict) else odds)

    if features:
        from app.services.features import FEATURE_NAMES

        for name in FEATURE_NAMES:
            if name in features:
                ah_features[name] = float(features[name])

    if line_f is None or ah_features.get("has_ah_market", 0) < 0.5:
        return None

    model_pick = _model_prediction(ah_features, line_f)
    if model_pick.source == "ml":
        return model_pick
    return _structural_pick(odds) or model_pick


def format_handicap_lean(pred: HandicapPrediction) -> str:
    """Product lean with signed line: 让负(-1) / 让胜(+0.5) / 让平(0)."""
    return format_handicap_lean_text(pick_to_lean(pred.pick), pred.line_f)


def handicap_bundle_from_markets(
    odds: dict[str, Any] | None,
    recommendation: str | None = None,
    *,
    package: dict[str, Any] | None = None,
    league_id: int | None = None,
    features: dict[str, float] | None = None,
    score_hint: str | None = None,
) -> tuple[str, str]:
    """Return (handicap_lean, handicap_market_note) for product + detail."""
    del recommendation, score_hint
    if not isinstance(odds, dict) or not odds.get("available", True):
        ah = (odds or {}).get("asian_handicap") if isinstance(odds, dict) else None
        if not isinstance(ah, dict):
            return "缺少盘口数据分析", ""

    pkg = dict(package or {})
    if odds:
        pkg["odds"] = odds

    ah = odds.get("asian_handicap") if isinstance(odds, dict) else None
    if not isinstance(ah, dict):
        return "缺少盘口数据分析", ""

    line_f, home_f, away_f = extract_main_ah_line(odds if isinstance(odds, dict) else None)
    if line_f is None or home_f is None or away_f is None:
        return "缺少盘口数据分析", ""

    pred = predict_handicap(
        odds,
        package=pkg,
        league_id=league_id,
        features=features,
    )
    if not pred:
        return "缺少盘口数据分析", ""
    return format_handicap_lean(pred), (pred.market_note or "").strip()


def train_from_rows(rows: list[tuple[dict[str, float], str]]) -> dict[str, Any]:
    labeled = [(f, y) for f, y in rows if y in TRAIN_LABELS]
    n = len(labeled)
    threshold = min_train_samples()
    if n < threshold:
        return {
            "ok": False,
            "reason": f"need>={threshold} ah labeled samples, got {n}",
            "n_samples": n,
            "min_train_samples": threshold,
        }

    X = np.asarray([ah_feature_vector(f) for f, _ in labeled], dtype=np.float64)
    y = np.asarray([_LABEL_TO_IDX[lab] for _, lab in labeled], dtype=np.float64)

    holdout_n = max(MIN_HOLDOUT_SAMPLES, int(n * 0.2))
    split = n - min(holdout_n, n - 1)
    X_train, y_train = X[:split], y[:split]
    X_val, y_val = X[split:], y[split:]

    model = _BinaryLogReg(n_features=X.shape[1])
    history = model.fit(X_train, y_train)

    def _metrics(Xm: np.ndarray, ym: np.ndarray) -> dict[str, float]:
        if len(ym) == 0:
            return {
                "log_loss": float("nan"),
                "brier": float("nan"),
                "accuracy": float("nan"),
            }
        p = model.predict_proba(Xm)
        eps = 1e-9
        ll = float(-np.mean(ym * np.log(p + eps) + (1 - ym) * np.log(1 - p + eps)))
        brier = float(np.mean((p - ym) ** 2))
        acc = float(np.mean((p >= 0.5) == (ym >= 0.5)))
        return {"log_loss": ll, "brier": brier, "accuracy": acc}

    train_m = _metrics(X_train, y_train)
    val_m = _metrics(X_val, y_val)
    implied_index = AH_FEATURE_NAMES.index("ah_implied_cover")

    def _market_metrics(Xm: np.ndarray, ym: np.ndarray) -> dict[str, float]:
        p = np.clip(Xm[:, implied_index], 1e-9, 1.0 - 1e-9)
        return {
            "log_loss": float(
                -np.mean(ym * np.log(p) + (1.0 - ym) * np.log(1.0 - p))
            ),
            "brier": float(np.mean((p - ym) ** 2)),
            "accuracy": float(np.mean((p >= 0.5) == (ym >= 0.5))),
        }

    market_val_m = _market_metrics(X_val, y_val)
    deployable = _beats_market_baseline(val_m, market_val_m)

    # Refit a fresh estimator on all rows after evaluation. Reusing the holdout
    # estimator would train early rows twice and make the saved artifact depend
    # on the validation pass.
    final_model = _BinaryLogReg(n_features=X.shape[1])
    final_model.fit(X, y, epochs=500)
    weights_path, meta_path = model_paths()
    final_model.save(weights_path)
    meta = {
        "ah_feature_version": AH_FEATURE_VERSION,
        "feature_names": AH_FEATURE_NAMES,
        "n_samples": n,
        "min_train_samples": threshold,
        "fit_samples": len(X_train),
        "holdout_samples": len(X_val),
        "train_metrics": train_m,
        "val_metrics": val_m,
        "market_val_metrics": market_val_m,
        "deployable": deployable,
        "fit_history": history,
        "classes": ["no_cover", "cover"],
        "trained_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(
        "Trained AH model n=%s val_logloss=%s market_logloss=%s deployable=%s",
        n,
        val_m.get("log_loss"),
        market_val_m.get("log_loss"),
        deployable,
    )
    return {"ok": True, **meta, "weights_path": str(weights_path)}


async def persist_ah_fields(
    session: Any,
    fixture_id: int,
    package: dict[str, Any] | None,
    *,
    league_id: int | None = None,
    label: str | None = None,
    force: bool = False,
) -> None:
    from sqlalchemy import select

    from app.models.match_feature import MatchFeature

    ah_features, line_f, home_f, away_f = build_ah_features(
        package, league_id=league_id
    )
    # Persist the same validated, market-shrunk estimate used by the analyzer.
    # Deep-board daily picks consume this frozen probability.
    pred = (
        _model_prediction(ah_features, line_f)
        if line_f is not None and ah_features.get("has_ah_market", 0) >= 0.5
        else None
    )

    result = await session.execute(
        select(MatchFeature).where(
            MatchFeature.fixture_id == fixture_id,
            MatchFeature.feature_version == FEATURE_VERSION,
        )
    )
    row = result.scalar_one_or_none()
    payload = {
        "ah_feature_version": AH_FEATURE_VERSION,
        "ah_features_json": dumps_ah_features(ah_features),
        "ah_line": line_f,
        "ah_home_odd": home_f,
        "ah_away_odd": away_f,
        "ah_cover_prob": pred.cover_prob if pred else None,
        "ah_model_source": pred.source if pred else None,
    }
    if label:
        payload["ah_label"] = label

    frozen_ah_keys = frozenset(
        {
            "ah_feature_version",
            "ah_features_json",
            "ah_line",
            "ah_home_odd",
            "ah_away_odd",
        }
    )
    if row is None:
        base = extract_features(package or {})
        session.add(
            MatchFeature(
                fixture_id=fixture_id,
                feature_version=FEATURE_VERSION,
                features_json=dumps_features(base),
                **payload,
            )
        )
    else:
        if not force and row.ah_features_json:
            payload = {k: v for k, v in payload.items() if k not in frozen_ah_keys}
        for key, value in payload.items():
            setattr(row, key, value)


async def collect_training_rows(session: Any) -> list[tuple[dict[str, float], str]]:
    from sqlalchemy import select

    from app.models.fixture import Fixture
    from app.models.match_feature import MatchFeature
    from app.models.pre_match_data import PreMatchData
    from app.services.prematch_package import package_from_record

    rows: list[tuple[dict[str, float], str]] = []
    seen: set[int] = set()

    q = await session.execute(
        select(MatchFeature, Fixture, PreMatchData)
        .join(Fixture, Fixture.id == MatchFeature.fixture_id)
        .outerjoin(PreMatchData, PreMatchData.fixture_id == Fixture.id)
        .where(
            MatchFeature.feature_version == FEATURE_VERSION,
            MatchFeature.ah_label.in_(("cover", "no_cover")),
            Fixture.status == "finished",
        )
        .order_by(Fixture.date.asc())
    )
    for feat, fixture, stored in q.all():
        features = None
        if (
            feat.ah_feature_version == AH_FEATURE_VERSION
            and feat.ah_features_json
        ):
            features = loads_ah_features(feat.ah_features_json)
        elif stored:
            pkg = package_from_record(stored, match_start_time=fixture.date)
            features, _, _, _ = build_ah_features(
                pkg, league_id=fixture.league_id
            )
        if not features or features.get("has_ah_market", 0) < 0.5:
            continue
        label = feat.ah_label
        if label not in TRAIN_LABELS:
            continue
        rows.append((features, label))
        seen.add(feat.fixture_id)

    q2 = await session.execute(
        select(MatchFeature, Fixture, PreMatchData)
        .join(Fixture, Fixture.id == MatchFeature.fixture_id)
        .outerjoin(PreMatchData, PreMatchData.fixture_id == Fixture.id)
        .where(
            MatchFeature.feature_version == FEATURE_VERSION,
            Fixture.status == "finished",
            Fixture.home_goals.is_not(None),
            Fixture.away_goals.is_not(None),
        )
        .order_by(Fixture.date.asc())
    )
    for feat, fixture, stored in q2.all():
        if fixture.id in seen:
            continue
        line_f = feat.ah_line
        if line_f is None and stored:
            pkg = package_from_record(stored, match_start_time=fixture.date)
            _, line_f, _, _ = build_ah_features(pkg, league_id=fixture.league_id)
        label = settle_ah_label(fixture.home_goals, fixture.away_goals, line_f)
        if label not in TRAIN_LABELS:
            continue
        if feat.ah_features_json:
            features = loads_ah_features(feat.ah_features_json)
        elif stored:
            pkg = package_from_record(stored, match_start_time=fixture.date)
            features, _, _, _ = build_ah_features(
                pkg, league_id=fixture.league_id
            )
        else:
            continue
        if features.get("has_ah_market", 0) < 0.5:
            continue
        rows.append((features, label))
        feat.ah_label = label
        seen.add(fixture.id)

    await session.commit()
    return rows


async def backfill_ah_features(session: Any) -> int:
    from sqlalchemy import select

    from app.models.fixture import Fixture
    from app.models.match_feature import MatchFeature
    from app.models.pre_match_data import PreMatchData
    from app.services.prematch_package import package_from_record

    q = await session.execute(
        select(MatchFeature, Fixture, PreMatchData)
        .join(Fixture, Fixture.id == MatchFeature.fixture_id)
        .outerjoin(PreMatchData, PreMatchData.fixture_id == Fixture.id)
        .where(MatchFeature.feature_version == FEATURE_VERSION)
        .order_by(Fixture.date.asc())
    )
    updated = 0
    for feat, fixture, stored in q.all():
        if not stored:
            continue
        package = package_from_record(stored, match_start_time=fixture.date)
        label = None
        if fixture.status == "finished" and fixture.home_goals is not None:
            ah_features, line_f, _, _ = build_ah_features(
                package, league_id=fixture.league_id
            )
            settled = settle_ah_label(fixture.home_goals, fixture.away_goals, line_f)
            if settled in TRAIN_LABELS:
                label = settled
        else:
            ah_features, _, _, _ = build_ah_features(
                package, league_id=fixture.league_id
            )

        await persist_ah_fields(
            session,
            fixture.id,
            package,
            league_id=fixture.league_id,
            label=label,
            force=True,
        )
        updated += 1

    await session.commit()
    return updated


async def train_model_from_db(session: Any) -> dict[str, Any]:
    rows = await collect_training_rows(session)
    return train_from_rows(rows)


async def maybe_auto_train_model(session: Any | None = None) -> dict[str, Any]:
    settings = get_settings()
    if not settings.ML_AH_AUTO_TRAIN:
        return {"ok": False, "skipped": True, "reason": "ML_AH_AUTO_TRAIN=false"}

    async def _run(sess: Any) -> dict[str, Any]:
        rows = await collect_training_rows(sess)
        n = len(rows)
        threshold = min_train_samples()
        _, meta = load_trained_model()
        prev_n = int(meta.get("n_samples", 0)) if meta else 0

        if n < threshold:
            return {
                "ok": False,
                "skipped": True,
                "reason": "below_threshold",
                "n_samples": n,
                "min_train_samples": threshold,
                "inference": "market_implied",
            }

        if prev_n > 0 and n <= prev_n:
            deployable = bool(meta.get("deployable", False))
            return {
                "ok": False,
                "skipped": True,
                "reason": "no_new_labels",
                "n_samples": n,
                "last_trained_n": prev_n,
                "inference": "ml" if deployable else "market_implied",
            }

        result = train_from_rows(rows)
        if result.get("ok"):
            result["inference"] = (
                "ml" if result.get("deployable") else "market_implied"
            )
            result["auto"] = True
        return result

    if session is not None:
        return await _run(session)

    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as sess:
        return await _run(sess)


def model_status() -> dict[str, Any]:
    threshold = min_train_samples()
    model, meta = load_trained_model()
    n_trained = int(meta.get("n_samples", 0)) if meta else 0
    ready = model is not None and n_trained >= threshold
    deployable = ready and bool(meta.get("deployable", False))
    return {
        "inference_mode": "ml" if deployable else "market_implied",
        "min_train_samples": threshold,
        "trained_n_samples": n_trained,
        "artifact_ready": ready,
        "deployable": deployable,
        "val_metrics": meta.get("val_metrics") if meta else None,
        "market_val_metrics": meta.get("market_val_metrics") if meta else None,
        "ah_feature_version": AH_FEATURE_VERSION,
        "trained_at": meta.get("trained_at") if meta else None,
    }


async def label_finished_ah(session: Any) -> int:
    from sqlalchemy import select

    from app.models.fixture import Fixture
    from app.models.match_feature import MatchFeature

    result = await session.execute(
        select(MatchFeature, Fixture)
        .join(Fixture, Fixture.id == MatchFeature.fixture_id)
        .where(
            Fixture.status == "finished",
            Fixture.home_goals.is_not(None),
            Fixture.away_goals.is_not(None),
            MatchFeature.feature_version == FEATURE_VERSION,
            MatchFeature.ah_line.is_not(None),
            MatchFeature.ah_label.is_(None),
        )
    )
    updated = 0
    for feat, fixture in result.all():
        label = settle_ah_label(fixture.home_goals, fixture.away_goals, feat.ah_line)
        if label:
            feat.ah_label = label
            updated += 1
    if updated:
        await session.commit()
    return updated
