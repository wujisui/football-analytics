"""1X2 daily-pick vs handicap-row consistency checks."""

from __future__ import annotations

import logging
from typing import Any

from app.services.ah_features import extract_main_ah_line, handicap_pick_from_lean
from app.services.ah_predictor import _loses_outright_on_recommendation
from app.services.prediction import resolve_handicap_bundle

logger = logging.getLogger(__name__)

HOME_WIN = frozenset({"胜", "主胜"})
AWAY_WIN = frozenset({"负", "客胜"})


def _line_within_1x2_bounds(lean_1x2: str, line_f: float | None) -> bool:
    if line_f is None:
        return True
    if lean_1x2 in HOME_WIN:
        return line_f >= -0.5 - 1e-9
    if lean_1x2 in AWAY_WIN:
        return line_f <= 0.5 + 1e-9
    return True


def handicap_conflicts_with_1x2(
    *,
    lean_1x2: str,
    handicap_lean: str | None,
    odds: dict[str, Any] | None,
) -> bool:
    """True when stored/computed handicap lean fights the 1X2 recommendation."""
    text = (handicap_lean or "").strip()
    if not text or "待分析" in text or "缺少" in text:
        return False
    line_f, _, _ = extract_main_ah_line(odds)
    if line_f is None:
        return False
    if not _line_within_1x2_bounds(lean_1x2, line_f):
        return True
    pick = handicap_pick_from_lean(text)
    if not pick:
        return False
    return _loses_outright_on_recommendation(line_f, pick, lean_1x2)


def align_handicap_with_1x2(
    *,
    lean_1x2: str,
    odds: dict[str, Any] | None,
    league_id: int,
    stored_handicap: str | None = None,
    features: dict[str, float] | None = None,
) -> tuple[str, bool]:
    """Return corrected handicap lean; bool = whether a correction was applied."""
    conflict = handicap_conflicts_with_1x2(
        lean_1x2=lean_1x2,
        handicap_lean=stored_handicap,
        odds=odds,
    )
    if not conflict and (stored_handicap or "").strip():
        return (stored_handicap or "").strip(), False

    corrected, _note = resolve_handicap_bundle(
        odds,
        lean_1x2,
        league_id=league_id,
        features=features,
        stored=stored_handicap,
        prefer_stored=False,
    )
    applied = conflict or (stored_handicap or "").strip() != (corrected or "").strip()
    return corrected, applied


def align_handicap_batch(
    picks: list[Any],
    *,
    odds_by_fixture: dict[int, dict[str, Any] | None],
    stored_handicap_by_fixture: dict[int, str | None],
    features_by_fixture: dict[int, dict[str, Any] | None],
) -> tuple[dict[int, str], int]:
    """Return corrected handicap lean per fixture_id and conflict count."""
    corrected_by_fixture: dict[int, str] = {}
    conflicts = 0
    for pick in picks:
        fixture_id = int(pick.fixture_id)
        features = features_by_fixture.get(fixture_id)
        feature_vec = None
        if isinstance(features, dict):
            feature_vec = {
                key: float(features[key])
                for key in (
                    "ah_line_shift",
                    "league_reliability",
                    "ah_implied_cover_home",
                    "form_wr5_diff",
                    "injury_impact",
                )
                if key in features
            }
        corrected, applied = align_handicap_with_1x2(
            lean_1x2=str(pick.lean),
            odds=odds_by_fixture.get(fixture_id),
            league_id=int(pick.league_id),
            stored_handicap=stored_handicap_by_fixture.get(fixture_id),
            features=feature_vec,
        )
        if applied:
            conflicts += 1
            logger.info(
                "Handicap aligned fixture=%s 1x2=%s -> %s",
                fixture_id,
                pick.lean,
                corrected,
            )
        corrected_by_fixture[fixture_id] = corrected
    return corrected_by_fixture, conflicts
