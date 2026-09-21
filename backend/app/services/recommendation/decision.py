"""Single recommendation decision engine.

Every direction carries two probabilities: the board's de-vig price and the
trained model's shadow output.  Ranking uses the model only for markets whose
model beat the board on its time holdout; everywhere else the board is the
estimate, which is what keeps the product running while models are unproven.

Expected return is computed for auditing from whichever probability ranks the
candidate.  It is structurally negative under board probabilities (``p ≈ 1/赔率``
means ``EV = 1/超额 − 1``), so it never gates a candidate — see the daily-pick
rules in ``.cursor/rules/project-scope.mdc``.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from app.services.ah_features import (
    ASIAN_HALF_LOSS,
    ASIAN_HALF_WIN,
    ASIAN_LOSS,
    ASIAN_PUSH,
    ASIAN_WIN,
    build_ah_features,
    extract_main_ah_line,
    format_handicap_lean_text,
    settle_asian_total,
    settle_handicap_pick,
)
from app.services.ah_market_structure import side_speaks_for_result
from app.services.ah_predictor import (
    model_status as ah_model_status,
    predict_handicap,
    shadow_cover_probability,
)
from app.services.goal_predictor import (
    distribution_summary,
    model_status as goal_model_status,
    predict_goals,
    score_matrix,
)
from app.services.market_analysis import handicap_direction_signal
from app.services.ml_predictor import (
    model_status as one_x_two_model_status,
    predict_probabilities,
    shadow_probabilities,
)
from app.services.prediction import _odd_float
from app.services.probability_calibration import calibrate_probability

MARKET_1X2 = "1x2"
MARKET_AH = "ah"
MARKET_OU = "ou"
MARKET_BTTS = "btts"

SOURCE_MARKET = "market"
SOURCE_MODEL = "model"

# Board de-vig probability is a two-way price; a side below this is the wrong
# half of a coin flip, not a recommendation.  1X2 keeps the lower floor because
# a three-way board rarely prices any single outcome above one half.
MIN_DAILY_CONFIDENCE = 0.40
MIN_AH_CONFIDENCE = 0.50

_RESULT_KEYS = (ASIAN_WIN, ASIAN_HALF_WIN, ASIAN_PUSH, ASIAN_HALF_LOSS, ASIAN_LOSS)
_DIRECTION_PENALTIES = {
    "aligned_strong": 0.0,
    "aligned_weak": 0.0,
    "unknown": 0.01,
    "reverse_weak": 0.02,
    "reverse_strong": 0.05,
}


@dataclass(frozen=True)
class MarketDirection:
    direction: str | None
    strength: str
    detail: str


@dataclass(frozen=True)
class RecommendationCandidate:
    fixture_id: int
    league_id: int
    match_day: str
    market: str
    direction: str
    lean: str
    line: float | None
    model_source: str | None
    model_version: str | None
    # Board de-vig price for this direction.
    implied_probability: float | None
    # Trained-model output, frozen even when the model is not deployable.
    model_probability: float | None
    probability_source: str
    raw_probability: float | None
    calibrator_version: str | None
    calibrated_probability: float | None
    decimal_odd: float | None
    settlement_distribution: dict[str, float] | None
    expected_return: float | None
    market_direction: str | None
    direction_strength: str
    direction_alignment: str
    direction_penalty: float
    adjusted_ev: float | None
    skip_reason: str | None
    # False when the card cannot put this side into words: the receiving half of
    # a board deeper than one goal wins by "losing by less than the line", which
    # 主胜 / 客胜 cannot express.  Still frozen for audit and calibration.
    tellable: bool = True

    @property
    def minimum_confidence(self) -> float:
        return MIN_AH_CONFIDENCE if self.market == MARKET_AH else MIN_DAILY_CONFIDENCE

    @property
    def ranking_score(self) -> float | None:
        """Calibrated hit probability, less the market-direction penalty.

        Odds deliberately stay out: probabilities here come from the very price
        being bet, so any ``p × 净赔率`` term collapses to ``√(p(1-p))`` and peaks
        at the coin flip.
        """
        if self.calibrated_probability is None:
            return None
        return float(self.calibrated_probability) - float(self.direction_penalty)

    def eligible_for_daily_pick(self) -> bool:
        return (
            self.tellable
            and self.calibrated_probability is not None
            and self.decimal_odd is not None
            and self.direction_alignment != "reverse_strong"
            and float(self.calibrated_probability) >= self.minimum_confidence
        )

    def settlement_json(self) -> str | None:
        if self.settlement_distribution is None:
            return None
        return json.dumps(self.settlement_distribution, ensure_ascii=False, sort_keys=True)


@dataclass(frozen=True)
class MatchDecision:
    fixture_id: int
    match_day: str
    reference: RecommendationCandidate
    candidates: tuple[RecommendationCandidate, ...]


def star_rating(ranking_score: float) -> float:
    """Absolute confidence bands over the calibrated hit probability.

    Bands are fixed, so a thin day cannot manufacture five stars out of its own
    best-of-a-bad-lot.  EV is not an input: under board probabilities it only
    restates the bookmaker's margin.
    """
    if ranking_score >= 0.65:
        return 5.0
    if ranking_score >= 0.60:
        return 4.5
    if ranking_score >= 0.57:
        return 4.0
    if ranking_score >= 0.54:
        return 3.5
    if ranking_score >= 0.51:
        return 3.0
    if ranking_score >= 0.48:
        return 2.5
    if ranking_score >= 0.45:
        return 2.0
    if ranking_score >= 0.42:
        return 1.5
    return 1.0


def settlement_expected_return(
    distribution: dict[str, float],
    decimal_odd: float,
) -> float:
    """Asian settlement EV per unit stake."""
    profit = float(decimal_odd) - 1.0
    return (
        float(distribution.get(ASIAN_WIN, 0.0)) * profit
        + float(distribution.get(ASIAN_HALF_WIN, 0.0)) * profit / 2.0
        - float(distribution.get(ASIAN_HALF_LOSS, 0.0)) / 2.0
        - float(distribution.get(ASIAN_LOSS, 0.0))
    )


def _normalise_distribution(values: dict[str, float]) -> dict[str, float]:
    cleaned = {key: max(0.0, float(values.get(key, 0.0))) for key in _RESULT_KEYS}
    total = sum(cleaned.values())
    if total <= 0:
        return {key: 0.0 for key in _RESULT_KEYS}
    return {key: value / total for key, value in cleaned.items()}


def _conditional_positive(distribution: dict[str, float]) -> float | None:
    positive = distribution[ASIAN_WIN] + distribution[ASIAN_HALF_WIN]
    negative = distribution[ASIAN_HALF_LOSS] + distribution[ASIAN_LOSS]
    at_risk = positive + negative
    return positive / at_risk if at_risk > 0 else None


def _rescale_distribution(
    distribution: dict[str, float],
    positive_probability: float,
) -> dict[str, float]:
    """Preserve push/half-state shape while replacing the positive probability."""
    base = _normalise_distribution(distribution)
    push = base[ASIAN_PUSH]
    at_risk = max(0.0, 1.0 - push)
    positive_mass = at_risk * max(0.0, min(1.0, positive_probability))
    negative_mass = at_risk - positive_mass
    positive_base = base[ASIAN_WIN] + base[ASIAN_HALF_WIN]
    negative_base = base[ASIAN_HALF_LOSS] + base[ASIAN_LOSS]
    win_share = base[ASIAN_WIN] / positive_base if positive_base > 0 else 1.0
    loss_share = base[ASIAN_LOSS] / negative_base if negative_base > 0 else 1.0
    return {
        ASIAN_WIN: positive_mass * win_share,
        ASIAN_HALF_WIN: positive_mass * (1.0 - win_share),
        ASIAN_PUSH: push,
        ASIAN_HALF_LOSS: negative_mass * (1.0 - loss_share),
        ASIAN_LOSS: negative_mass * loss_share,
    }


def _binary_distribution(probability: float) -> dict[str, float]:
    p = max(0.0, min(1.0, float(probability)))
    return {
        ASIAN_WIN: p,
        ASIAN_HALF_WIN: 0.0,
        ASIAN_PUSH: 0.0,
        ASIAN_HALF_LOSS: 0.0,
        ASIAN_LOSS: 1.0 - p,
    }


def _score_distribution(
    matrix: Any,
    *,
    market: str,
    direction: str,
    line: float | None,
) -> dict[str, float] | None:
    if market not in {MARKET_AH, MARKET_OU} or line is None:
        return None
    totals = {key: 0.0 for key in _RESULT_KEYS}
    for home in range(matrix.shape[0]):
        for away in range(matrix.shape[1]):
            probability = float(matrix[home, away])
            if market == MARKET_AH:
                result = settle_handicap_pick(
                    home,
                    away,
                    line,
                    "让胜" if direction == "home" else "让负",
                )
            else:
                result = settle_asian_total(
                    home + away,
                    line,
                    over=direction == "over",
                )
            if result in totals:
                totals[result] += probability
    return _normalise_distribution(totals)


def _fair_pair(first: float, second: float) -> tuple[float, float]:
    a, b = 1.0 / first, 1.0 / second
    total = a + b
    return (a / total, b / total)


def _fair_1x2(market: dict[str, Any]) -> dict[str, float] | None:
    odds = {key: _odd_float(market.get(key)) for key in ("home", "draw", "away")}
    if any(value is None for value in odds.values()):
        return None
    inverse = {key: 1.0 / float(value) for key, value in odds.items()}
    total = sum(inverse.values())
    return {key: value / total for key, value in inverse.items()} if total > 0 else None


def _same_book(first: dict[str, Any], second: dict[str, Any]) -> bool:
    a = str(first.get("bookmaker") or "").strip()
    b = str(second.get("bookmaker") or "").strip()
    return bool(a and b and a == b)


def _stage_market(
    package: dict[str, Any] | None,
    stage: str,
    market: str,
) -> dict[str, Any] | None:
    board = (package or {}).get(stage)
    if not isinstance(board, dict) or board.get("available") is False:
        return None
    value = board.get(market)
    return value if isinstance(value, dict) else None


def _generic_market_direction(
    package: dict[str, Any] | None,
    market: str,
) -> MarketDirection:
    key = {
        MARKET_1X2: "match_winner",
        MARKET_OU: "goals_ou",
        MARKET_BTTS: "both_teams_score",
    }.get(market)
    if key is None:
        return MarketDirection(None, "none", "玩法没有可比盘口方向")
    opening = _stage_market(package, "odds_opening", key)
    current = _stage_market(package, "odds", key)
    if opening is None or current is None or not _same_book(opening, current):
        return MarketDirection(None, "none", "同庄家初盘与即时盘不足")

    if market == MARKET_1X2:
        before, after = _fair_1x2(opening), _fair_1x2(current)
        if before is None or after is None:
            return MarketDirection(None, "none", "1X2 报价不完整")
        changes = {side: after[side] - before[side] for side in ("home", "away")}
    else:
        if market == MARKET_OU:
            try:
                opening_line = float(opening.get("line"))
                current_line = float(current.get("line"))
            except (TypeError, ValueError):
                opening_line = current_line = 0.0
            if abs(current_line - opening_line) >= 0.24:
                direction = "over" if current_line > opening_line else "under"
                return MarketDirection(direction, "strong", "主盘总进球线发生方向移动")
            if abs(current_line - opening_line) > 1e-9:
                direction = "over" if current_line > opening_line else "under"
                return MarketDirection(direction, "weak", "主盘总进球线轻微移动")
        first_before, second_before = _odd_float(opening.get("home")), _odd_float(
            opening.get("away")
        )
        first_after, second_after = _odd_float(current.get("home")), _odd_float(
            current.get("away")
        )
        if None in {first_before, second_before, first_after, second_after}:
            return MarketDirection(None, "none", "两路报价不完整")
        before = _fair_pair(float(first_before), float(second_before))
        after = _fair_pair(float(first_after), float(second_after))
        labels = ("over", "under") if market == MARKET_OU else ("yes", "no")
        changes = {labels[0]: after[0] - before[0], labels[1]: after[1] - before[1]}

    direction, delta = max(changes.items(), key=lambda item: item[1])
    if delta < 0.01:
        return MarketDirection(None, "none", "同档位去水概率变化不足")
    return MarketDirection(
        direction,
        "strong" if delta >= 0.03 else "weak",
        f"同档位去水概率向{direction}移动 {delta:+.1%}",
    )


def _market_direction(
    package: dict[str, Any] | None,
    market: str,
) -> MarketDirection:
    if market != MARKET_AH:
        return _generic_market_direction(package, market)
    signal = handicap_direction_signal(package)
    return MarketDirection(signal.direction, signal.strength, signal.detail)


def _alignment(
    direction: str,
    signal: MarketDirection,
) -> tuple[str, float]:
    if signal.direction is None:
        return "unknown", _DIRECTION_PENALTIES["unknown"]
    if signal.direction == direction:
        key = "aligned_strong" if signal.strength == "strong" else "aligned_weak"
        return key, _DIRECTION_PENALTIES[key]
    key = "reverse_strong" if signal.strength == "strong" else "reverse_weak"
    return key, _DIRECTION_PENALTIES[key]


def _candidate(
    *,
    fixture_id: int,
    league_id: int,
    match_day: str,
    market: str,
    direction: str,
    lean: str,
    line: float | None,
    model_source: str | None,
    model_version: str | None,
    model_probability: float | None,
    model_deployable: bool,
    decimal_odd: float | None,
    implied_probability: float | None,
    raw_distribution: dict[str, float] | None,
    calibration_artifact: dict[str, Any] | None,
    package: dict[str, Any] | None,
    tellable: bool = True,
) -> RecommendationCandidate:
    use_model = model_deployable and model_probability is not None
    source = SOURCE_MODEL if use_model else SOURCE_MARKET
    raw = model_probability if use_model else implied_probability

    calibrated: float | None = None
    calibrator_version: str | None = None
    if raw is not None:
        calibrated, calibrator_version = calibrate_probability(
            calibration_artifact,
            market,
            source,
            direction,
            float(raw),
        )

    # Keep the model's settlement shape (push / half-ball mass) and move only the
    # positive mass onto the ranking probability.
    distribution: dict[str, float] | None = raw_distribution
    ev: float | None = None
    if calibrated is not None and raw_distribution is not None:
        distribution = _rescale_distribution(raw_distribution, calibrated)
        if decimal_odd is not None:
            ev = settlement_expected_return(distribution, decimal_odd)
    elif calibrated is not None and decimal_odd is not None:
        distribution = _binary_distribution(calibrated)
        ev = settlement_expected_return(distribution, decimal_odd)

    reason: str | None = None
    if calibrated is None:
        reason = "probability_unavailable"
    elif decimal_odd is None:
        reason = "odds_missing"
    elif not tellable:
        reason = "deep_board_receiving_side"

    signal = _market_direction(package, market)
    alignment, penalty = _alignment(direction, signal)
    adjusted = ev - penalty if ev is not None else None
    return RecommendationCandidate(
        fixture_id=fixture_id,
        league_id=league_id,
        match_day=match_day,
        market=market,
        direction=direction,
        lean=lean,
        line=line,
        model_source=model_source,
        model_version=model_version,
        implied_probability=implied_probability,
        model_probability=model_probability,
        probability_source=source,
        raw_probability=float(raw) if raw is not None else None,
        calibrator_version=calibrator_version,
        calibrated_probability=calibrated,
        decimal_odd=decimal_odd,
        settlement_distribution=distribution,
        expected_return=ev,
        market_direction=signal.direction,
        direction_strength=signal.strength,
        direction_alignment=alignment,
        direction_penalty=penalty,
        adjusted_ev=adjusted,
        skip_reason=reason,
        tellable=tellable,
    )


def market_order(*, has_ah: bool) -> tuple[str, ...]:
    """有 AH：AH→大小球→双进；无 AH：1X2→大小球→双进."""
    return (
        (MARKET_AH, MARKET_OU, MARKET_BTTS)
        if has_ah
        else (MARKET_1X2, MARKET_OU, MARKET_BTTS)
    )


def select_reference_candidate(
    candidates: list[RecommendationCandidate],
    *,
    has_ah: bool,
) -> RecommendationCandidate | None:
    """Choose one reference with strict market priority.

    Ranking score is compared only between directions inside the same market;
    a later market never outranks an earlier market that has a probability.
    """
    for market in market_order(has_ah=has_ah):
        available = [
            candidate
            for candidate in candidates
            if candidate.market == market
            and candidate.ranking_score is not None
            and candidate.tellable
        ]
        if available:
            return max(
                available,
                key=lambda item: (
                    float(item.ranking_score),
                    float(item.expected_return or 0.0),
                ),
            )
    return None


def build_match_decision(
    *,
    fixture_id: int,
    league_id: int,
    match_day: str,
    odds: dict[str, Any] | None,
    package: dict[str, Any] | None,
    calibration_artifact: dict[str, Any] | None,
) -> MatchDecision:
    """Build all direction candidates and one strict-priority reference."""
    odds = odds if isinstance(odds, dict) else {}
    package = package if isinstance(package, dict) else {}
    candidates: list[RecommendationCandidate] = []

    one_x_two = predict_probabilities(package)
    one_status = one_x_two_model_status()
    base_features = one_x_two.features
    one_shadow = shadow_probabilities(base_features)
    one_deployable = bool(one_status.get("deployable"))
    winner = odds.get("match_winner") if isinstance(odds.get("match_winner"), dict) else {}
    implied_1x2 = _fair_1x2(winner) if winner else None
    for direction, lean in (("home", "主胜"), ("away", "客胜")):
        shadow = (one_shadow or {}).get(direction)
        odd = _odd_float(winner.get(direction)) if winner else None
        candidates.append(
            _candidate(
                fixture_id=fixture_id,
                league_id=league_id,
                match_day=match_day,
                market=MARKET_1X2,
                direction=direction,
                lean=lean,
                line=None,
                model_source=one_x_two.source,
                model_version=str(one_status.get("feature_version") or ""),
                model_probability=float(shadow) if shadow is not None else None,
                model_deployable=one_deployable,
                decimal_odd=odd,
                implied_probability=(implied_1x2 or {}).get(direction),
                raw_distribution=None,
                calibration_artifact=calibration_artifact,
                package=package,
            )
        )

    # Shadow goals: the settlement shape (push / half-ball mass) is needed for
    # every Asian line even while the O/U and BTTS target gates are closed.
    goal_prediction = predict_goals(base_features, odds, ignore_deployable=True)
    goal_status = goal_model_status()
    goal_matrix = score_matrix(goal_prediction) if goal_prediction is not None else None

    line, ah_home_odd, ah_away_odd = extract_main_ah_line(odds)
    ah_features, _, _, _ = build_ah_features(
        {**package, "odds": odds},
        league_id=league_id,
    )
    ah_status = ah_model_status()
    ah_deployable = bool(ah_status.get("deployable"))
    ah_model_prob = shadow_cover_probability(ah_features)
    ah_prediction = predict_handicap(
        odds,
        package=package,
        league_id=league_id,
        features=base_features,
    )
    if line is not None:
        implied_ah = (
            _fair_pair(ah_home_odd, ah_away_odd)
            if ah_home_odd is not None and ah_away_odd is not None
            else (None, None)
        )
        for index, (direction, odd, pick) in enumerate(
            (
                ("home", ah_home_odd, "让胜"),
                ("away", ah_away_odd, "让负"),
            )
        ):
            shadow = (
                float(ah_model_prob)
                if direction == "home" and ah_model_prob is not None
                else 1.0 - float(ah_model_prob)
                if ah_model_prob is not None
                else None
            )
            base_distribution = (
                _score_distribution(
                    goal_matrix,
                    market=MARKET_AH,
                    direction=direction,
                    line=line,
                )
                if goal_matrix is not None
                else None
            )
            candidates.append(
                _candidate(
                    fixture_id=fixture_id,
                    league_id=league_id,
                    match_day=match_day,
                    market=MARKET_AH,
                    direction=direction,
                    lean=format_handicap_lean_text(pick, line),
                    line=line,
                    model_source=ah_prediction.source if ah_prediction else None,
                    model_version=(
                        ah_prediction.model_version
                        if ah_prediction
                        else str(ah_status.get("ah_feature_version") or "")
                    ),
                    model_probability=shadow,
                    model_deployable=ah_deployable,
                    decimal_odd=odd,
                    implied_probability=implied_ah[index],
                    raw_distribution=base_distribution,
                    calibration_artifact=calibration_artifact,
                    package=package,
                    tellable=side_speaks_for_result(float(line), direction),
                )
            )

    ou = odds.get("goals_ou") if isinstance(odds.get("goals_ou"), dict) else None
    try:
        ou_line = float(ou.get("line")) if ou else None
    except (TypeError, ValueError):
        ou_line = None
    if ou is not None and ou_line is not None:
        over_odd, under_odd = _odd_float(ou.get("home")), _odd_float(ou.get("away"))
        implied_ou = (
            _fair_pair(over_odd, under_odd)
            if over_odd is not None and under_odd is not None
            else (None, None)
        )
        ou_deployable = bool(
            goal_prediction is not None and goal_prediction.deploy_ou
        )
        for index, (direction, odd) in enumerate(
            (("over", over_odd), ("under", under_odd))
        ):
            base_distribution = (
                _score_distribution(
                    goal_matrix,
                    market=MARKET_OU,
                    direction=direction,
                    line=ou_line,
                )
                if goal_matrix is not None
                else None
            )
            shadow = (
                _conditional_positive(base_distribution)
                if base_distribution is not None
                else None
            )
            candidates.append(
                _candidate(
                    fixture_id=fixture_id,
                    league_id=league_id,
                    match_day=match_day,
                    market=MARKET_OU,
                    direction=direction,
                    lean=f"{'大' if direction == 'over' else '小'}({ou_line:g})",
                    line=ou_line,
                    model_source=(
                        goal_prediction.source if goal_prediction is not None else None
                    ),
                    model_version=str(goal_status.get("feature_version") or ""),
                    model_probability=shadow,
                    model_deployable=ou_deployable,
                    decimal_odd=odd,
                    implied_probability=implied_ou[index],
                    raw_distribution=base_distribution,
                    calibration_artifact=calibration_artifact,
                    package=package,
                )
            )

    btts = (
        odds.get("both_teams_score")
        if isinstance(odds.get("both_teams_score"), dict)
        else None
    )
    if btts is not None:
        yes_odd, no_odd = _odd_float(btts.get("home")), _odd_float(btts.get("away"))
        implied_btts = (
            _fair_pair(yes_odd, no_odd)
            if yes_odd is not None and no_odd is not None
            else (None, None)
        )
        btts_summary = (
            distribution_summary(goal_prediction)
            if goal_prediction is not None
            else None
        )
        btts_deployable = bool(
            goal_prediction is not None and goal_prediction.deploy_btts
        )
        yes_prob = float(btts_summary["btts_prob"]) if btts_summary is not None else None
        for index, (direction, odd, lean) in enumerate(
            (
                ("yes", yes_odd, "双进:是"),
                ("no", no_odd, "双进:否"),
            )
        ):
            shadow = (
                yes_prob
                if direction == "yes" and yes_prob is not None
                else 1.0 - yes_prob
                if yes_prob is not None
                else None
            )
            candidates.append(
                _candidate(
                    fixture_id=fixture_id,
                    league_id=league_id,
                    match_day=match_day,
                    market=MARKET_BTTS,
                    direction=direction,
                    lean=lean,
                    line=None,
                    model_source=(
                        goal_prediction.source if goal_prediction is not None else None
                    ),
                    model_version=str(goal_status.get("feature_version") or ""),
                    model_probability=shadow,
                    model_deployable=btts_deployable,
                    decimal_odd=odd,
                    implied_probability=implied_btts[index],
                    raw_distribution=(
                        _binary_distribution(shadow) if shadow is not None else None
                    ),
                    calibration_artifact=calibration_artifact,
                    package=package,
                )
            )

    has_ah = line is not None and ah_home_odd is not None and ah_away_odd is not None
    order = market_order(has_ah=has_ah)
    reference = select_reference_candidate(candidates, has_ah=has_ah)

    if reference is None:
        # Neither estimator produced a probability (usually a board with no
        # usable prices).  Keep a deterministic direction for the all-match
        # reference and let the skip reason explain the missing numbers.
        reference = RecommendationCandidate(
            fixture_id=fixture_id,
            league_id=league_id,
            match_day=match_day,
            market=order[0],
            direction="unknown",
            lean="数据不足",
            line=None,
            model_source=None,
            model_version=None,
            implied_probability=None,
            model_probability=None,
            probability_source=SOURCE_MARKET,
            raw_probability=None,
            calibrator_version=None,
            calibrated_probability=None,
            decimal_odd=None,
            settlement_distribution=None,
            expected_return=None,
            market_direction=None,
            direction_strength="none",
            direction_alignment="unknown",
            direction_penalty=0.01,
            adjusted_ev=None,
            skip_reason="odds_and_model_unavailable",
        )
    return MatchDecision(
        fixture_id=fixture_id,
        match_day=match_day,
        reference=reference,
        candidates=tuple(candidates),
    )
