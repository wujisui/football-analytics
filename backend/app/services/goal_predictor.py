"""Goal-distribution model trained only from pre-match inputs and FT scores."""

from __future__ import annotations

import json
import logging
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from app.core.config import BACKEND_ROOT
from app.services.ah_features import extract_main_ah_line
from app.services.features import FEATURE_VERSION, extract_features
from app.services.prematch_package import package_from_record

logger = logging.getLogger(__name__)

GOAL_FEATURE_VERSION = "goals_v1"
GOAL_MODEL_DIR = BACKEND_ROOT / "data" / "models"
GOAL_META_NAME = "goals_v1_meta.json"
GOAL_WEIGHTS_NAME = "goals_v1_weights.npz"
MIN_GOAL_TRAIN_SAMPLES = 120
MAX_SCORE_GOALS = 8

# Keep the score model compact: 442 rows cannot support the full high-dimensional
# 1X2 vector plus dozens of market interactions without severe overfitting.
GOAL_FEATURE_NAMES = [
    "odds_home",
    "odds_draw",
    "odds_away",
    "ou_line",
    "ou_over_prob",
    "ou_under_prob",
    "has_ou",
    "ah_line",
    "ah_home_prob",
    "ah_away_prob",
    "has_ah",
    "home_wr_5",
    "away_wr_5",
    "home_dr_5",
    "away_dr_5",
    "home_gd_avg_5",
    "away_gd_avg_5",
    "rank_diff",
    "home_advantage",
]


@dataclass(frozen=True)
class GoalPrediction:
    home_lambda: float
    away_lambda: float
    source: str
    deploy_score: bool = True
    deploy_ou: bool = False
    deploy_btts: bool = False
    score_candidates: tuple[tuple[int, int], ...] = ()


def _odd_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _line_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    text = str(value).strip().replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _two_way_market(
    market: dict[str, Any] | None,
) -> tuple[float | None, float | None, float | None]:
    if not isinstance(market, dict):
        return None, None, None
    line = _line_float(market.get("line"))
    first = _odd_float(market.get("home"))
    second = _odd_float(market.get("away"))
    if line is None or first is None or second is None:
        lines = market.get("lines")
        if isinstance(lines, list):
            for item in lines:
                if not isinstance(item, dict):
                    continue
                line = _line_float(item.get("line"))
                first = _odd_float(item.get("home"))
                second = _odd_float(item.get("away"))
                if line is not None and first is not None and second is not None:
                    break
    return line, first, second


def _implied_pair(first: float | None, second: float | None) -> tuple[float, float]:
    if first is None or second is None:
        return 0.5, 0.5
    inv_first, inv_second = 1.0 / first, 1.0 / second
    total = inv_first + inv_second
    if total <= 0:
        return 0.5, 0.5
    return inv_first / total, inv_second / total


def extract_goal_features(
    base_features: dict[str, float],
    odds: dict[str, Any] | None,
) -> dict[str, float]:
    """Compact, point-in-time market vector; never includes our prediction."""
    odds = odds if isinstance(odds, dict) else {}
    ou_line, over_odd, under_odd = _two_way_market(odds.get("goals_ou"))
    over_prob, under_prob = _implied_pair(over_odd, under_odd)
    ah_line, ah_home_odd, ah_away_odd = extract_main_ah_line(odds)
    ah_home_prob, ah_away_prob = _implied_pair(ah_home_odd, ah_away_odd)
    has_ou = float(ou_line is not None and over_odd is not None and under_odd is not None)
    has_ah = float(
        ah_line is not None and ah_home_odd is not None and ah_away_odd is not None
    )
    return {
        "odds_home": float(base_features.get("odds_home", 1 / 3)),
        "odds_draw": float(base_features.get("odds_draw", 1 / 3)),
        "odds_away": float(base_features.get("odds_away", 1 / 3)),
        "ou_line": float(ou_line or 2.5),
        "ou_over_prob": over_prob,
        "ou_under_prob": under_prob,
        "has_ou": has_ou,
        "ah_line": float(ah_line or 0.0),
        "ah_home_prob": ah_home_prob,
        "ah_away_prob": ah_away_prob,
        "has_ah": has_ah,
        "home_wr_5": float(base_features.get("home_wr_5", 1 / 3)),
        "away_wr_5": float(base_features.get("away_wr_5", 1 / 3)),
        "home_dr_5": float(base_features.get("home_dr_5", 1 / 3)),
        "away_dr_5": float(base_features.get("away_dr_5", 1 / 3)),
        "home_gd_avg_5": float(base_features.get("home_gd_avg_5", 0.0)),
        "away_gd_avg_5": float(base_features.get("away_gd_avg_5", 0.0)),
        "rank_diff": float(base_features.get("rank_diff", 0.0)),
        "home_advantage": float(base_features.get("home_advantage", 1.0)),
    }


def goal_feature_vector(features: dict[str, float]) -> list[float]:
    return [float(features.get(name, 0.0)) for name in GOAL_FEATURE_NAMES]


def dumps_goal_features(features: dict[str, float]) -> str:
    return json.dumps(
        {name: float(features.get(name, 0.0)) for name in GOAL_FEATURE_NAMES},
        ensure_ascii=False,
    )


def loads_goal_features(raw: str | None) -> dict[str, float]:
    if not raw:
        return {name: 0.0 for name in GOAL_FEATURE_NAMES}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {name: 0.0 for name in GOAL_FEATURE_NAMES}
    return {name: float(data.get(name, 0.0)) for name in GOAL_FEATURE_NAMES}


async def persist_goal_features(
    session: Any,
    fixture_id: int,
    base_features: dict[str, float],
    odds: dict[str, Any] | None,
) -> None:
    """Attach frozen goal features to the existing match_features row."""
    from sqlalchemy import select

    from app.models.match_feature import MatchFeature

    row = (
        await session.execute(
            select(MatchFeature).where(
                MatchFeature.fixture_id == fixture_id,
                MatchFeature.feature_version == FEATURE_VERSION,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return
    if row.goal_features_json:
        return
    row.goal_features_json = dumps_goal_features(
        extract_goal_features(base_features, odds)
    )
    row.goal_feature_version = GOAL_FEATURE_VERSION


class _PoissonGoalModel:
    """Two regularized Poisson regressions sharing one standardized input."""

    def __init__(self, n_features: int) -> None:
        self.mean = np.zeros(n_features, dtype=np.float64)
        self.scale = np.ones(n_features, dtype=np.float64)
        self.home_w = np.zeros(n_features, dtype=np.float64)
        self.away_w = np.zeros(n_features, dtype=np.float64)
        self.home_b = 0.0
        self.away_b = 0.0

    def _standardize(self, X: np.ndarray) -> np.ndarray:
        return (X - self.mean) / self.scale

    @staticmethod
    def _lambda(Xs: np.ndarray, w: np.ndarray, b: float) -> np.ndarray:
        eta = np.clip(Xs @ w + b, -2.5, 2.5)
        return np.exp(eta)

    def predict(self, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        Xs = self._standardize(X)
        return (
            self._lambda(Xs, self.home_w, self.home_b),
            self._lambda(Xs, self.away_w, self.away_b),
        )

    def fit(
        self,
        X: np.ndarray,
        home_goals: np.ndarray,
        away_goals: np.ndarray,
        *,
        epochs: int = 1200,
        lr: float = 0.012,
        l2: float = 0.035,
    ) -> None:
        self.mean = X.mean(axis=0)
        self.scale = X.std(axis=0)
        self.scale[self.scale < 1e-6] = 1.0
        Xs = self._standardize(X)
        self.home_b = float(math.log(max(float(home_goals.mean()), 0.1)))
        self.away_b = float(math.log(max(float(away_goals.mean()), 0.1)))
        n = max(1, len(X))

        for _ in range(epochs):
            for target, w_name, b_name in (
                (home_goals, "home_w", "home_b"),
                (away_goals, "away_w", "away_b"),
            ):
                w = getattr(self, w_name)
                b = float(getattr(self, b_name))
                lam = self._lambda(Xs, w, b)
                residual = np.clip(lam - target, -6.0, 6.0)
                grad_w = Xs.T @ residual / n + l2 * w
                grad_b = float(residual.mean())
                setattr(self, w_name, w - lr * np.clip(grad_w, -3.0, 3.0))
                setattr(self, b_name, b - lr * max(-3.0, min(3.0, grad_b)))

    def save(self, path: Path) -> None:
        np.savez_compressed(
            path,
            mean=self.mean,
            scale=self.scale,
            home_w=self.home_w,
            away_w=self.away_w,
            home_b=np.asarray(self.home_b),
            away_b=np.asarray(self.away_b),
        )

    @classmethod
    def load(cls, path: Path) -> "_PoissonGoalModel":
        data = np.load(path)
        model = cls(len(data["home_w"]))
        model.mean = data["mean"]
        model.scale = data["scale"]
        model.home_w = data["home_w"]
        model.away_w = data["away_w"]
        model.home_b = float(data["home_b"])
        model.away_b = float(data["away_b"])
        return model


def model_paths() -> tuple[Path, Path]:
    GOAL_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    return GOAL_MODEL_DIR / GOAL_WEIGHTS_NAME, GOAL_MODEL_DIR / GOAL_META_NAME


def load_model() -> tuple[_PoissonGoalModel | None, dict[str, Any]]:
    weights_path, meta_path = model_paths()
    if not weights_path.exists() or not meta_path.exists():
        return None, {}
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("feature_version") != GOAL_FEATURE_VERSION:
            return None, meta
        if not meta.get("deployable", False):
            return None, meta
        return _PoissonGoalModel.load(weights_path), meta
    except Exception as exc:
        logger.warning("Failed to load goal model: %s", exc)
        return None, {}


def predict_goals(
    base_features: dict[str, float] | None,
    odds: dict[str, Any] | None,
) -> GoalPrediction | None:
    if not base_features or float(base_features.get("has_odds", 0.0)) <= 0:
        return None
    model, meta = load_model()
    if model is None:
        return None
    features = extract_goal_features(base_features, odds)
    X = np.asarray([goal_feature_vector(features)], dtype=np.float64)
    home, away = model.predict(X)
    score_lookup = meta.get("score_lookup") or {}
    score_key = _score_group_key(X[0])
    raw_scores = score_lookup.get(score_key) or score_lookup.get("global") or []
    score_candidates = tuple(
        (int(pair[0]), int(pair[1]))
        for pair in raw_scores
        if isinstance(pair, list) and len(pair) == 2
    )
    return GoalPrediction(
        home_lambda=max(0.1, min(6.0, float(home[0]))),
        away_lambda=max(0.1, min(6.0, float(away[0]))),
        source="poisson_ml",
        deploy_score=bool((meta.get("target_gates") or {}).get("score", False)),
        deploy_ou=bool((meta.get("target_gates") or {}).get("ou", False)),
        deploy_btts=bool((meta.get("target_gates") or {}).get("btts", False)),
        score_candidates=score_candidates,
    )


def _poisson_probs(rate: float, max_goals: int) -> np.ndarray:
    probs = np.asarray(
        [math.exp(-rate) * (rate**goals) / math.factorial(goals) for goals in range(max_goals + 1)],
        dtype=np.float64,
    )
    # Put the tiny truncated tail into the last bucket so totals remain normalized.
    probs[-1] += max(0.0, 1.0 - float(probs.sum()))
    return probs


def score_matrix(
    prediction: GoalPrediction,
    max_goals: int = MAX_SCORE_GOALS,
) -> np.ndarray:
    home = _poisson_probs(prediction.home_lambda, max_goals)
    away = _poisson_probs(prediction.away_lambda, max_goals)
    matrix = np.outer(home, away)
    return matrix / matrix.sum()


def distribution_summary(
    prediction: GoalPrediction,
    *,
    total_line: float = 2.5,
    top_scores: int = 2,
) -> dict[str, Any]:
    matrix = score_matrix(prediction)
    home_prob = float(np.tril(matrix, -1).sum())
    draw_prob = float(np.trace(matrix))
    away_prob = float(np.triu(matrix, 1).sum())
    over_prob = sum(
        float(matrix[h, a])
        for h in range(matrix.shape[0])
        for a in range(matrix.shape[1])
        if h + a > total_line
    )
    btts_prob = float(matrix[1:, 1:].sum())
    ranked = sorted(
        (
            (float(matrix[h, a]), h, a)
            for h in range(matrix.shape[0])
            for a in range(matrix.shape[1])
        ),
        reverse=True,
    )
    scores = [(h, a, prob) for prob, h, a in ranked[: max(1, top_scores)]]
    if prediction.score_candidates:
        scores = [
            (h, a, float(matrix[h, a]) if h < matrix.shape[0] and a < matrix.shape[1] else 0.0)
            for h, a in prediction.score_candidates[: max(1, top_scores)]
        ]
    return {
        "home_prob": home_prob,
        "draw_prob": draw_prob,
        "away_prob": away_prob,
        "over_prob": over_prob,
        "under_prob": 1.0 - over_prob,
        "btts_prob": btts_prob,
        "scores": scores,
    }


def _score_group_key(row: np.ndarray) -> str:
    odds = [
        float(row[GOAL_FEATURE_NAMES.index("odds_home")]),
        float(row[GOAL_FEATURE_NAMES.index("odds_draw")]),
        float(row[GOAL_FEATURE_NAMES.index("odds_away")]),
    ]
    outcome = ("home", "draw", "away")[int(np.argmax(odds))]
    ou_side = (
        "over"
        if float(row[GOAL_FEATURE_NAMES.index("ou_over_prob")]) >= 0.5
        else "under"
    )
    return f"{outcome}_{ou_side}"


def _metrics(
    model: _PoissonGoalModel,
    X: np.ndarray,
    home: np.ndarray,
    away: np.ndarray,
) -> dict[str, float]:
    pred_home, pred_away = model.predict(X)
    home_mae = float(np.mean(np.abs(pred_home - home)))
    away_mae = float(np.mean(np.abs(pred_away - away)))
    top1_hits = 0
    top2_hits = 0
    ou_hits = 0
    ou_total = 0
    btts_hits = 0
    result_hits = 0
    ou_index = GOAL_FEATURE_NAMES.index("ou_line")
    for index, (home_rate, away_rate) in enumerate(zip(pred_home, pred_away)):
        actual_home, actual_away = int(home[index]), int(away[index])
        line = float(X[index, ou_index])
        summary = distribution_summary(
            GoalPrediction(float(home_rate), float(away_rate), "eval"),
            total_line=line,
        )
        predicted_scores = [(h, a) for h, a, _ in summary["scores"]]
        top1_hits += int((actual_home, actual_away) == predicted_scores[0])
        top2_hits += int((actual_home, actual_away) in predicted_scores[:2])
        actual_total = actual_home + actual_away
        if abs(actual_total - line) > 1e-9:
            predicted_over = summary["over_prob"] >= 0.5
            ou_hits += int(predicted_over == (actual_total > line))
            ou_total += 1
        predicted_btts = summary["btts_prob"] >= 0.5
        btts_hits += int(predicted_btts == (actual_home > 0 and actual_away > 0))
        predicted_result = max(
            ("home", "draw", "away"),
            key=lambda key: float(summary[f"{key}_prob"]),
        )
        actual_result = (
            "home"
            if actual_home > actual_away
            else "away"
            if actual_home < actual_away
            else "draw"
        )
        result_hits += int(predicted_result == actual_result)
    count = max(1, len(home))
    return {
        "home_mae": home_mae,
        "away_mae": away_mae,
        "total_mae": home_mae + away_mae,
        "top1_score_accuracy": top1_hits / count,
        "top2_score_accuracy": top2_hits / count,
        "ou_accuracy": ou_hits / ou_total if ou_total else float("nan"),
        "btts_accuracy": btts_hits / count,
        "result_accuracy": result_hits / count,
    }


def train_from_rows(
    rows: list[tuple[dict[str, float], int, int]],
) -> dict[str, Any]:
    n = len(rows)
    if n < MIN_GOAL_TRAIN_SAMPLES:
        return {
            "ok": False,
            "reason": f"need>={MIN_GOAL_TRAIN_SAMPLES} samples, got {n}",
            "n_samples": n,
        }
    X = np.asarray([goal_feature_vector(features) for features, _, _ in rows])
    home = np.asarray([min(max(h, 0), MAX_SCORE_GOALS) for _, h, _ in rows], dtype=np.float64)
    away = np.asarray([min(max(a, 0), MAX_SCORE_GOALS) for _, _, a in rows], dtype=np.float64)
    split = max(MIN_GOAL_TRAIN_SAMPLES - 10, int(n * 0.8))
    X_train, X_val = X[:split], X[split:]
    home_train, home_val = home[:split], home[split:]
    away_train, away_val = away[:split], away[split:]

    eval_model = _PoissonGoalModel(X.shape[1])
    eval_model.fit(X_train, home_train, away_train)
    val_metrics = _metrics(eval_model, X_val, home_val, away_val)
    baseline_home = np.full_like(home_val, home_train.mean())
    baseline_away = np.full_like(away_val, away_train.mean())
    baseline_total_mae = float(
        np.mean(np.abs(baseline_home - home_val))
        + np.mean(np.abs(baseline_away - away_val))
    )
    score_counts = Counter(zip(home_train.astype(int), away_train.astype(int)))
    common_scores = [score for score, _ in score_counts.most_common(2)]
    baseline_top1 = float(
        np.mean(
            [
                (int(h), int(a)) == common_scores[0]
                for h, a in zip(home_val, away_val)
            ]
        )
    )
    baseline_top2 = float(
        np.mean(
            [
                (int(h), int(a)) in common_scores
                for h, a in zip(home_val, away_val)
            ]
        )
    )
    grouped_scores: dict[str, Counter[tuple[int, int]]] = {}
    for index, (actual_home, actual_away) in enumerate(
        zip(home_train.astype(int), away_train.astype(int))
    ):
        key = _score_group_key(X_train[index])
        grouped_scores.setdefault(key, Counter())[(actual_home, actual_away)] += 1
    score_lookup: dict[str, list[list[int]]] = {
        key: [[int(h), int(a)] for (h, a), _ in counts.most_common(2)]
        for key, counts in grouped_scores.items()
    }
    score_lookup["global"] = [[int(h), int(a)] for h, a in common_scores]
    lookup_hits = 0
    for index, (actual_home, actual_away) in enumerate(
        zip(home_val.astype(int), away_val.astype(int))
    ):
        candidates = score_lookup.get(_score_group_key(X_val[index])) or score_lookup["global"]
        lookup_hits += int([int(actual_home), int(actual_away)] in candidates)
    lookup_top2_accuracy = lookup_hits / max(1, len(home_val))
    has_ou_index = GOAL_FEATURE_NAMES.index("has_ou")
    over_index = GOAL_FEATURE_NAMES.index("ou_over_prob")
    ou_line_index = GOAL_FEATURE_NAMES.index("ou_line")
    market_ou_hits: list[bool] = []
    for index, (actual_home, actual_away) in enumerate(zip(home_val, away_val)):
        if X_val[index, has_ou_index] <= 0:
            continue
        total = int(actual_home + actual_away)
        line = float(X_val[index, ou_line_index])
        if abs(total - line) < 1e-9:
            continue
        market_ou_hits.append(
            bool(X_val[index, over_index] >= 0.5) == bool(total > line)
        )
    market_ou_accuracy = (
        float(np.mean(market_ou_hits)) if market_ou_hits else 0.5
    )
    train_btts_rate = float(np.mean((home_train > 0) & (away_train > 0)))
    majority_btts = train_btts_rate >= 0.5
    btts_baseline_accuracy = float(
        np.mean(((home_val > 0) & (away_val > 0)) == majority_btts)
    )
    baseline_metrics = {
        "total_mae": baseline_total_mae,
        "top1_score_accuracy": baseline_top1,
        "top2_score_accuracy": baseline_top2,
        "conditional_top2_score_accuracy": lookup_top2_accuracy,
        "ou_market_accuracy": market_ou_accuracy,
        "btts_majority_accuracy": btts_baseline_accuracy,
    }
    score_strategy = (
        "conditional"
        if lookup_top2_accuracy >= val_metrics["top2_score_accuracy"]
        else "poisson"
    )
    best_score_accuracy = max(
        lookup_top2_accuracy, val_metrics["top2_score_accuracy"]
    )
    target_gates = {
        "score": best_score_accuracy > baseline_top2,
        "ou": val_metrics["ou_accuracy"] > market_ou_accuracy,
        "btts": val_metrics["btts_accuracy"] > btts_baseline_accuracy,
    }
    deployable = val_metrics["total_mae"] < baseline_total_mae

    model = _PoissonGoalModel(X.shape[1])
    model.fit(X, home, away, epochs=1500)
    weights_path, meta_path = model_paths()
    model.save(weights_path)
    meta = {
        "feature_version": GOAL_FEATURE_VERSION,
        "feature_names": GOAL_FEATURE_NAMES,
        "n_samples": n,
        "min_train_samples": MIN_GOAL_TRAIN_SAMPLES,
        "val_metrics": val_metrics,
        "baseline_total_mae": baseline_total_mae,
        "baseline_metrics": baseline_metrics,
        "target_gates": target_gates,
        "score_strategy": score_strategy,
        "score_lookup": score_lookup if score_strategy == "conditional" else {},
        "deployable": deployable,
        "trained_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Trained goal model n=%s deployable=%s metrics=%s", n, deployable, val_metrics)
    return {"ok": True, **meta, "weights_path": str(weights_path)}


async def collect_training_rows(
    session: Any,
) -> list[tuple[dict[str, float], int, int]]:
    """Read frozen pre-match packages and FT scores; predictions are never inputs."""
    from sqlalchemy import select

    from app.models.fixture import Fixture
    from app.models.match_feature import MatchFeature
    from app.models.pre_match_data import PreMatchData

    durable = await session.execute(
        select(MatchFeature, Fixture)
        .join(Fixture, Fixture.id == MatchFeature.fixture_id)
        .where(
            MatchFeature.goal_feature_version == GOAL_FEATURE_VERSION,
            MatchFeature.goal_features_json.is_not(None),
            Fixture.status == "finished",
            Fixture.home_goals.is_not(None),
            Fixture.away_goals.is_not(None),
        )
        .order_by(Fixture.date.asc())
    )
    result = await session.execute(
        select(PreMatchData, Fixture)
        .join(Fixture, Fixture.id == PreMatchData.fixture_id)
        .where(
            Fixture.status == "finished",
            Fixture.home_goals.is_not(None),
            Fixture.away_goals.is_not(None),
        )
        .order_by(Fixture.date.asc())
    )
    rows: list[tuple[dict[str, float], int, int]] = []
    seen: set[int] = set()
    for stored_features, fixture in durable.all():
        rows.append(
            (
                loads_goal_features(stored_features.goal_features_json),
                int(fixture.home_goals),
                int(fixture.away_goals),
            )
        )
        seen.add(fixture.id)
        if stored_features.home_goals_label is None:
            stored_features.home_goals_label = int(fixture.home_goals)
            stored_features.away_goals_label = int(fixture.away_goals)

    for stored, fixture in result.all():
        if fixture.id in seen:
            continue
        package = package_from_record(stored)
        base = extract_features(package)
        if float(base.get("has_odds", 0.0)) <= 0:
            continue
        odds = package.get("odds")
        goal_features = extract_goal_features(
            base, odds if isinstance(odds, dict) else None
        )
        rows.append(
            (
                goal_features,
                int(fixture.home_goals),
                int(fixture.away_goals),
            )
        )
        feature_row = (
            await session.execute(
                select(MatchFeature).where(
                    MatchFeature.fixture_id == fixture.id,
                )
            )
        ).scalars().first()
        if feature_row is not None:
            feature_row.goal_features_json = dumps_goal_features(goal_features)
            feature_row.goal_feature_version = GOAL_FEATURE_VERSION
            feature_row.home_goals_label = int(fixture.home_goals)
            feature_row.away_goals_label = int(fixture.away_goals)
    await session.commit()
    return rows


async def train_model_from_db(session: Any) -> dict[str, Any]:
    return train_from_rows(await collect_training_rows(session))


async def maybe_auto_train_model(session: Any | None = None) -> dict[str, Any]:
    from app.core.config import get_settings

    if not get_settings().ML_AUTO_TRAIN:
        return {"ok": False, "skipped": True, "reason": "ML_AUTO_TRAIN=false"}

    async def _run(sess: Any) -> dict[str, Any]:
        rows = await collect_training_rows(sess)
        _, meta = load_model()
        previous = int(meta.get("n_samples", 0)) if meta else 0
        if len(rows) < MIN_GOAL_TRAIN_SAMPLES:
            return {
                "ok": False,
                "skipped": True,
                "reason": "below_threshold",
                "n_samples": len(rows),
            }
        if previous > 0 and len(rows) <= previous:
            return {
                "ok": False,
                "skipped": True,
                "reason": "no_new_labels",
                "n_samples": len(rows),
            }
        return train_from_rows(rows)

    if session is not None:
        return await _run(session)
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as sess:
        return await _run(sess)


def model_status() -> dict[str, Any]:
    _, meta = load_model()
    return {
        "artifact_ready": bool(meta),
        "deployable": bool(meta.get("deployable", False)),
        "trained_n_samples": int(meta.get("n_samples", 0)) if meta else 0,
        "feature_version": GOAL_FEATURE_VERSION,
        "val_metrics": meta.get("val_metrics") if meta else None,
        "baseline_total_mae": meta.get("baseline_total_mae") if meta else None,
        "baseline_metrics": meta.get("baseline_metrics") if meta else None,
        "target_gates": meta.get("target_gates") if meta else None,
        "trained_at": meta.get("trained_at") if meta else None,
    }
