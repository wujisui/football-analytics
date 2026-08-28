"""Feature vectors for the recommendation pipeline."""

from __future__ import annotations

from typing import Any

from app.services.features import _injury_count, _rates_from_form
from app.services.ah_features import _implied_cover_prob, extract_main_ah_line

FEATURE_KEYS = (
    "ah_line_shift",
    "league_reliability",
    "ah_implied_cover_home",
    "form_wr5_diff",
    "injury_impact",
)


def _package_block(package: dict[str, Any] | None, key: str) -> dict[str, Any]:
    if not isinstance(package, dict):
        return {}
    block = package.get(key)
    return block if isinstance(block, dict) else {}


def _ah_line_shift(
    current_odds: dict[str, Any] | None,
    opening_odds: dict[str, Any] | None,
) -> float:
    """Opening → current main AH line change (positive = toward home)."""
    open_line, _, _ = extract_main_ah_line(opening_odds)
    current_line, _, _ = extract_main_ah_line(current_odds)
    if open_line is None or current_line is None:
        return 0.0
    return float(current_line - open_line)


def _injury_impact(package: dict[str, Any] | None) -> float:
    injuries = _package_block(package, "injuries")
    home_n = _injury_count(injuries, "home")
    away_n = _injury_count(injuries, "away")
    # Positive when away carries more absences (helps home); capped 0..1.
    delta = (away_n - home_n) / 8.0
    return max(0.0, min(1.0, 0.5 + delta / 2.0))


def build_match_features(
    *,
    match_id: int,
    league_id: int,
    odds: dict[str, Any] | None,
    package: dict[str, Any] | None = None,
    calibration: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build per-fixture feature dict for calibration / strategy."""
    package = package or {}
    opening = package.get("odds_opening")
    opening_odds = opening if isinstance(opening, dict) else None

    home_form = _package_block(package, "home_form")
    away_form = _package_block(package, "away_form")
    home_wr5, _, _ = _rates_from_form(home_form, 5)
    away_wr5, _, _ = _rates_from_form(away_form, 5)

    _, home_odd, away_odd = extract_main_ah_line(odds)
    ah_implied = (
        _implied_cover_prob(home_odd, away_odd)
        if home_odd is not None and away_odd is not None
        else 0.5
    )

    cal = calibration or {}
    vector = {
        "ah_line_shift": _ah_line_shift(odds, opening_odds),
        "league_reliability": float(cal.get("reliability") or 0.0),
        "ah_implied_cover_home": float(ah_implied),
        "form_wr5_diff": float(home_wr5 - away_wr5),
        "injury_impact": _injury_impact(package),
    }
    return {
        "match_id": int(match_id),
        "league_id": int(league_id),
        **vector,
    }


def feature_vector(features: dict[str, Any] | None) -> dict[str, float]:
    """Return only numeric feature keys."""
    data = features or {}
    return {key: float(data.get(key, 0.0)) for key in FEATURE_KEYS}
