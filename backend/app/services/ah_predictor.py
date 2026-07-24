"""Asian handicap cover probability: multifactor heuristic + binary logistic ML."""

from __future__ import annotations

import json
import logging
import math
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
    format_ah_line,
    loads_ah_features,
    parse_score_hint,
    pick_to_lean,
    settle_ah_label,
)
from app.services.features import FEATURE_VERSION, dumps_features, extract_features

logger = logging.getLogger(__name__)

MODEL_DIR = BACKEND_ROOT / "data" / "models"
MODEL_WEIGHTS_NAME = "ah_v1_weights.npz"
MODEL_META_NAME = "ah_v1_meta.json"

_LABEL_TO_IDX = {"no_cover": 0, "cover": 1}
TRAIN_LABELS = frozenset(_LABEL_TO_IDX)


@dataclass
class HandicapPrediction:
    cover_prob: float
    pick: str  # cover | no_cover | push
    source: str  # ml | multifactor | structural | score_hint
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


def multifactor_cover_prob(features: dict[str, float]) -> float:
    """Heuristic P(home covers) when ML artifact is not ready."""
    if features.get("has_ah_market", 0) < 0.5:
        return 0.5

    implied = float(features.get("ah_implied_cover", 0.5))
    water_diff = float(features.get("ah_water_diff", 0.0))
    mx_gap = float(features.get("mx_vs_ah_gap", 0.0))
    rank = float(features.get("rank_diff", 0.0))
    form_edge = float(features.get("home_gd_avg_5", 0.0)) - float(
        features.get("away_gd_avg_5", 0.0)
    )

    # Relative water: higher home odd vs away → lower cover prob.
    logit = 2.2 * (implied - 0.5) - 0.65 * water_diff + 1.1 * mx_gap
    logit += 0.35 * rank + 0.25 * form_edge

    shallow = float(features.get("ah_tier_shallow", 0.0))
    if shallow >= 0.5 and water_diff > 0.12:
        logit -= 0.45
    if shallow >= 0.5 and water_diff < -0.12:
        logit += 0.35

    deep = float(features.get("ah_tier_deep", 0.0))
    if deep >= 0.5 and implied < 0.52:
        logit += 0.25

    logit = max(-6.0, min(6.0, logit))
    return float(1.0 / (1.0 + math.exp(-logit)))


def _structural_pick(
    line_f: float,
    recommendation: str,
) -> HandicapPrediction | None:
    rec = (recommendation or "").strip()
    half_giving = -0.85 <= line_f <= -0.4
    half_receiving = 0.4 <= line_f <= 0.85
    home_undivided = rec == "胜/平" or "主队不败" in rec or rec.startswith("主胜/平")
    away_undivided = rec == "负/平" or "客队不败" in rec or rec.startswith("客胜/平")

    if home_undivided and half_giving:
        return HandicapPrediction(0.35, "no_cover", "structural", line_f)
    if home_undivided and half_receiving:
        return HandicapPrediction(0.72, "cover", "structural", line_f)
    if away_undivided and half_receiving:
        return HandicapPrediction(0.68, "cover", "structural", line_f)
    if away_undivided and half_giving:
        return HandicapPrediction(0.32, "no_cover", "structural", line_f)
    if rec in {"负", "客胜"} and half_receiving:
        return HandicapPrediction(0.28, "no_cover", "structural", line_f)
    if rec in {"负", "客胜"} and half_giving:
        return HandicapPrediction(0.25, "no_cover", "structural", line_f)
    if rec in {"平", "平局"} and half_giving:
        return HandicapPrediction(0.30, "no_cover", "structural", line_f)
    if rec in {"平", "平局"} and half_receiving:
        return HandicapPrediction(0.70, "cover", "structural", line_f)
    return None


def _pick_from_score_hint(score_hint: str | None, line_f: float) -> HandicapPrediction | None:
    """Settle main AH line against primary reference score (aligns with score_hint row)."""
    scores = parse_score_hint(score_hint)
    if not scores:
        return None
    home_g, away_g = scores[0]
    label = settle_ah_label(home_g, away_g, line_f)
    if label == "cover":
        return HandicapPrediction(0.68, "cover", "score_hint", line_f)
    if label == "no_cover":
        return HandicapPrediction(0.32, "no_cover", "score_hint", line_f)
    if label == "push":
        return HandicapPrediction(0.5, "push", "score_hint", line_f)
    return None


def _market_water_note(ah_features: dict[str, float], score_pick: str) -> str:
    """Advanced: when odds-implied side differs from score-settled pick."""
    if score_pick not in {"cover", "no_cover"}:
        return ""
    mf = multifactor_cover_prob(ah_features)
    mf_pick = "cover" if mf >= 0.5 else "no_cover"
    if mf_pick == score_pick:
        return ""
    water_diff = float(ah_features.get("ah_water_diff", 0.0))
    if water_diff > 0.05:
        water_side = "客"
    elif water_diff < -0.05:
        water_side = "主"
    else:
        water_side = "均势"
    return (
        f"盘口水位偏{water_side}侧"
        f"（参考比分仍按 {pick_to_lean(score_pick)} 结算）"
    )


def predict_handicap(
    odds: dict[str, Any] | None,
    recommendation: str | None,
    *,
    package: dict[str, Any] | None = None,
    league_id: int | None = None,
    ah_features: dict[str, float] | None = None,
    features: dict[str, float] | None = None,
    score_hint: str | None = None,
) -> HandicapPrediction | None:
    """Predict home cover for main AH line."""
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

    structural = _structural_pick(line_f, recommendation or "")
    if structural:
        return structural

    score_pick = _pick_from_score_hint(score_hint, line_f)
    if score_pick:
        score_pick.market_note = _market_water_note(ah_features, score_pick.pick)
        return score_pick

    model, meta = load_trained_model()
    threshold = min_train_samples()
    n_trained = int(meta.get("n_samples", 0)) if meta else 0
    use_ml = model is not None and n_trained >= threshold

    if use_ml:
        X = np.asarray([ah_feature_vector(ah_features)], dtype=np.float64)
        cover_prob = float(model.predict_proba(X)[0])
        source = "ml"
    else:
        cover_prob = multifactor_cover_prob(ah_features)
        source = "multifactor"

    pick = "cover" if cover_prob >= 0.5 else "no_cover"
    return HandicapPrediction(cover_prob, pick, source, line_f)


def format_handicap_lean(pred: HandicapPrediction) -> str:
    """Product default: pick + main line only (fits list tag)."""
    line_label = format_ah_line(pred.line_f) if pred.line_f is not None else "?"
    return f"{pick_to_lean(pred.pick)}（{line_label}）"


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
        recommendation,
        package=pkg,
        league_id=league_id,
        features=features,
        score_hint=score_hint,
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

    split = max(threshold - 5, int(n * 0.8))
    X_train, y_train = X[:split], y[:split]
    X_val, y_val = X[split:], y[split:]

    model = _BinaryLogReg(n_features=X.shape[1])
    history = model.fit(X_train, y_train)

    def _metrics(Xm: np.ndarray, ym: np.ndarray) -> dict[str, float]:
        if len(ym) == 0:
            return {"log_loss": float("nan"), "accuracy": float("nan")}
        p = model.predict_proba(Xm)
        eps = 1e-9
        ll = float(-np.mean(ym * np.log(p + eps) + (1 - ym) * np.log(1 - p + eps)))
        acc = float(np.mean((p >= 0.5) == (ym >= 0.5)))
        return {"log_loss": ll, "accuracy": acc}

    train_m = _metrics(X_train, y_train)
    val_m = _metrics(X_val, y_val) if len(y_val) else train_m

    model.fit(X, y, epochs=500)
    weights_path, meta_path = model_paths()
    model.save(weights_path)
    meta = {
        "ah_feature_version": AH_FEATURE_VERSION,
        "feature_names": AH_FEATURE_NAMES,
        "n_samples": n,
        "min_train_samples": threshold,
        "train_metrics": train_m,
        "val_metrics": val_m,
        "fit_history": history,
        "classes": ["no_cover", "cover"],
        "trained_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(
        "Trained AH model n=%s val_acc=%s → inference will use source=ml",
        n,
        val_m.get("accuracy"),
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
    pred = predict_handicap(
        (package or {}).get("odds") if isinstance((package or {}).get("odds"), dict) else None,
        None,
        package=package,
        league_id=league_id,
        ah_features=ah_features,
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
    from app.services.prematch_package import loads_json, package_from_record

    rows: list[tuple[dict[str, float], str]] = []
    seen: set[int] = set()

    q = await session.execute(
        select(MatchFeature, Fixture)
        .join(Fixture, Fixture.id == MatchFeature.fixture_id)
        .where(
            MatchFeature.feature_version == FEATURE_VERSION,
            MatchFeature.ah_label.in_(("cover", "no_cover")),
            Fixture.status == "finished",
        )
        .order_by(Fixture.date.asc())
    )
    for feat, _fixture in q.all():
        if not feat.ah_features_json:
            continue
        features = loads_ah_features(feat.ah_features_json)
        if features.get("has_ah_market", 0) < 0.5:
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
            pkg = package_from_record(stored) or {
                "odds": loads_json(stored.odds_json, {"available": False}),
            }
            _, line_f, _, _ = build_ah_features(pkg, league_id=fixture.league_id)
        label = settle_ah_label(fixture.home_goals, fixture.away_goals, line_f)
        if label not in TRAIN_LABELS:
            continue
        if feat.ah_features_json:
            features = loads_ah_features(feat.ah_features_json)
        elif stored:
            pkg = package_from_record(stored) or {
                "odds": loads_json(stored.odds_json, {"available": False}),
            }
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
    from app.services.prematch_package import loads_json, package_from_record

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
        package = package_from_record(stored) or {
            "odds": loads_json(stored.odds_json, {"available": False}),
            "home_form": loads_json(stored.home_form_json, {}),
            "away_form": loads_json(stored.away_form_json, {}),
            "head_to_head": loads_json(stored.h2h_json, {}),
            "standings": loads_json(stored.standings_json, {}),
            "injuries": loads_json(stored.injuries_json, {}),
        }
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
                "inference": "multifactor",
            }

        if prev_n > 0 and n <= prev_n:
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
    threshold = min_train_samples()
    model, meta = load_trained_model()
    n_trained = int(meta.get("n_samples", 0)) if meta else 0
    ready = model is not None and n_trained >= threshold
    return {
        "inference_mode": "ml" if ready else "multifactor",
        "min_train_samples": threshold,
        "trained_n_samples": n_trained,
        "artifact_ready": ready,
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
