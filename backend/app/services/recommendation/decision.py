"""Single recommendation decision engine.

Four market models produce independent probabilities.  Only validated Platt
outputs may enter settlement-aware EV; missing calibration keeps a direction
for the all-match reference but makes the fixture ineligible for daily Top 4.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
from typing import Any

from app.services.ah_features import (
    ASIAN_HALF_LOSS,
    ASIAN_HALF_WIN,
    ASIAN_LOSS,
    ASIAN_PUSH,
    ASIAN_WIN,
    extract_main_ah_line,
    format_handicap_lean_text,
    settle_asian_total,
    settle_handicap_pick,
)
from app.services.ah_predictor import predict_handicap
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
)
from app.services.prediction import _odd_float
from app.services.probability_calibration import calibrate_for_ev

MARKET_1X2 = "1x2"
MARKET_AH = "ah"
MARKET_OU = "ou"
MARKET_BTTS = "btts"

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
    raw_model_probability: float | None
    calibrator_version: str | None
    calibrated_probability: float | None
    implied_probability: float | None
    decimal_odd: float | None
    settlement_distribution: dict[str, float] | None
    expected_return: float | None
    market_direction: str | None
    direction_strength: str
    direction_alignment: str
    direction_penalty: float
    adjusted_ev: float | None
    skip_reason: str | None

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


def star_rating(adjusted_ev: float) -> float:
    """Absolute recommendation-strength bands; never force a daily five-star."""
    if adjusted_ev >= 0.08:
        return 5.0
    if adjusted_ev >= 0.05:
        return 4.5
    if adjusted_ev >= 0.03:
        return 4.0
    if adjusted_ev >= 0.01:
        return 3.5
    if adjusted_ev >= 0.0:
        return 3.0
    if adjusted_ev >= -0.02:
        return 2.5
    if adjusted_ev >= -0.04:
        return 2.0
    if adjusted_ev >= -0.06:
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
    raw_probability: float | None,
    decimal_odd: float | None,
    implied_probability: float | None,
    raw_distribution: dict[str, float] | None,
    calibration_artifact: dict[str, Any] | None,
    package: dict[str, Any] | None,
    skip_reason: str | None = None,
) -> RecommendationCandidate:
    calibrated: float | None = None
    calibrator_version: str | None = None
    # Keep the raw model settlement shape even before a calibrator is ready;
    # EV remains null until a validated Platt output can rescale it.
    distribution: dict[str, float] | None = raw_distribution
    ev: float | None = None
    reason = skip_reason
    if raw_probability is not None:
        calibrated, calibrator_version = calibrate_for_ev(
            calibration_artifact,
            market,
            direction,
            raw_probability,
        )
        if calibrated is None and reason is None:
            reason = "calibrator_unavailable"
    if calibrated is not None and decimal_odd is not None and raw_distribution is not None:
        distribution = _rescale_distribution(raw_distribution, calibrated)
        ev = settlement_expected_return(distribution, decimal_odd)
    elif decimal_odd is None and reason is None:
        reason = "odds_missing"
    elif raw_distribution is None and reason is None:
        reason = "settlement_distribution_unavailable"

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
        raw_model_probability=raw_probability,
        calibrator_version=calibrator_version,
        calibrated_probability=calibrated,
        implied_probability=implied_probability,
        decimal_odd=decimal_odd,
        settlement_distribution=distribution,
        expected_return=ev,
        market_direction=signal.direction,
        direction_strength=signal.strength,
        direction_alignment=alignment,
        direction_penalty=penalty,
        adjusted_ev=adjusted,
        skip_reason=reason if ev is None else None,
    )


def select_reference_candidate(
    candidates: list[RecommendationCandidate],
    *,
    has_ah: bool,
) -> RecommendationCandidate | None:
    """Choose one reference with strict market priority.

    Adjusted EV is compared only between directions inside the same market;
    a later market can never outrank a calculable earlier market.
    """
    order = (MARKET_AH, MARKET_OU, MARKET_BTTS) if has_ah else (
        MARKET_1X2,
        MARKET_OU,
        MARKET_BTTS,
    )
    for market in order:
        available = [
            candidate
            for candidate in candidates
            if candidate.market == market and candidate.adjusted_ev is not None
        ]
        if available:
            return max(
                available,
                key=lambda item: (
                    float(item.adjusted_ev),
                    float(item.calibrated_probability or 0.0),
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
    winner = odds.get("match_winner") if isinstance(odds.get("match_winner"), dict) else {}
    implied_1x2 = _fair_1x2(winner) if winner else None
    for direction, lean in (("home", "主胜"), ("away", "客胜")):
        raw = one_x_two.probs.get(direction) if one_x_two.source == "ml" else None
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
                raw_probability=float(raw) if raw is not None else None,
                decimal_odd=odd,
                implied_probability=(implied_1x2 or {}).get(direction),
                raw_distribution=_binary_distribution(float(raw)) if raw is not None else None,
                calibration_artifact=calibration_artifact,
                package=package,
                skip_reason=None if raw is not None else "model_not_deployable",
            )
        )

    base_features = one_x_two.features
    goal_prediction = predict_goals(base_features, odds)
    goal_status = goal_model_status()
    goal_matrix = score_matrix(goal_prediction) if goal_prediction is not None else None

    line, ah_home_odd, ah_away_odd = extract_main_ah_line(odds)
    ah_prediction = predict_handicap(
        odds,
        package=package,
        league_id=league_id,
        features=base_features,
    )
    ah_model_prob = (
        ah_prediction.model_cover_prob
        if ah_prediction is not None and ah_prediction.source == "ml"
        else None
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
            raw = (
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
            if base_distribution is not None and raw is not None:
                base_distribution = _rescale_distribution(base_distribution, raw)
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
                    model_version=ah_prediction.model_version if ah_prediction else None,
                    raw_probability=raw,
                    decimal_odd=odd,
                    implied_probability=implied_ah[index],
                    raw_distribution=base_distribution,
                    calibration_artifact=calibration_artifact,
                    package=package,
                    skip_reason=(
                        "model_not_deployable"
                        if raw is None
                        else "settlement_distribution_unavailable"
                        if base_distribution is None
                        else None
                    ),
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
        summary = (
            distribution_summary(goal_prediction, total_line=ou_line)
            if goal_prediction is not None and goal_prediction.deploy_ou
            else None
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
                if summary is not None and goal_matrix is not None
                else None
            )
            raw = (
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
                    model_source=goal_prediction.source if summary is not None else None,
                    model_version=str(goal_status.get("feature_version") or ""),
                    raw_probability=raw,
                    decimal_odd=odd,
                    implied_probability=implied_ou[index],
                    raw_distribution=base_distribution,
                    calibration_artifact=calibration_artifact,
                    package=package,
                    skip_reason=None if raw is not None else "model_not_deployable",
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
            if goal_prediction is not None and goal_prediction.deploy_btts
            else None
        )
        yes_prob = float(btts_summary["btts_prob"]) if btts_summary is not None else None
        for index, (direction, odd, lean) in enumerate(
            (
                ("yes", yes_odd, "双进:是"),
                ("no", no_odd, "双进:否"),
            )
        ):
            raw = (
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
                    model_source=goal_prediction.source if yes_prob is not None else None,
                    model_version=str(goal_status.get("feature_version") or ""),
                    raw_probability=raw,
                    decimal_odd=odd,
                    implied_probability=implied_btts[index],
                    raw_distribution=_binary_distribution(raw) if raw is not None else None,
                    calibration_artifact=calibration_artifact,
                    package=package,
                    skip_reason=None if raw is not None else "model_not_deployable",
                )
            )

    has_ah = line is not None and ah_home_odd is not None and ah_away_odd is not None
    order = (MARKET_AH, MARKET_OU, MARKET_BTTS) if has_ah else (
        MARKET_1X2,
        MARKET_OU,
        MARKET_BTTS,
    )
    reference = select_reference_candidate(candidates, has_ah=has_ah)

    # Every fixture still exposes a direction when EV is unavailable.  Strict
    # market order remains intact; the skip reason explains daily ineligibility.
    if reference is None:
        for market in order:
            directional = [
                candidate
                for candidate in candidates
                if candidate.market == market
                and candidate.raw_model_probability is not None
            ]
            if directional:
                reference = max(
                    directional,
                    key=lambda item: float(item.raw_model_probability or 0.0),
                )
                break
    if reference is None:
        # No independent model is deployable.  Preserve a deterministic market
        # direction for the all-match reference, but never compute EV from it.
        fallback_pool = [
            candidate
            for market in order
            for candidate in candidates
            if candidate.market == market and candidate.implied_probability is not None
        ]
        if fallback_pool:
            first_market = next(
                market for market in order if any(c.market == market for c in fallback_pool)
            )
            reference = max(
                (candidate for candidate in fallback_pool if candidate.market == first_market),
                key=lambda item: float(item.implied_probability or 0.0),
            )
            reference = replace(reference, skip_reason="model_not_deployable")
    if reference is None:
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
            raw_model_probability=None,
            calibrator_version=None,
            calibrated_probability=None,
            implied_probability=None,
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
