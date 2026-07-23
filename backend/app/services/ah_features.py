"""Asian handicap (让球穿盘) features and label settlement."""

from __future__ import annotations

import json
import math
import re
from typing import Any

from app.services.features import FEATURE_NAMES, extract_features

AH_FEATURE_VERSION = "ah_v1"

TOP5_LEAGUE_IDS = frozenset({39, 140, 78, 135, 61})
ASIA_LEAGUE_IDS = frozenset({169, 98, 292, 253})

# Appended to frozen 1X2 feature vector for AH training / inference.
AH_EXTRA_NAMES: list[str] = [
    "ah_line_norm",
    "ah_home_odd_inv",
    "ah_away_odd_inv",
    "ah_water_diff",
    "ah_implied_cover",
    "ah_line_abs_norm",
    "ah_tier_shallow",
    "ah_tier_medium",
    "ah_tier_deep",
    "ah_is_giving",
    "mx_home_prob",
    "mx_draw_prob",
    "mx_away_prob",
    "mx_vs_ah_gap",
    "league_tier_top5",
    "league_tier_asia",
    "has_ah_market",
]

AH_FEATURE_NAMES: list[str] = [*FEATURE_NAMES, *AH_EXTRA_NAMES]


def dumps_ah_features(features: dict[str, float]) -> str:
    ordered = {name: float(features.get(name, 0.0)) for name in AH_FEATURE_NAMES}
    return json.dumps(ordered, ensure_ascii=False)


def loads_ah_features(raw: str | None) -> dict[str, float]:
    if not raw:
        return {name: 0.0 for name in AH_FEATURE_NAMES}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {name: 0.0 for name in AH_FEATURE_NAMES}
    if not isinstance(data, dict):
        return {name: 0.0 for name in AH_FEATURE_NAMES}
    return {name: float(data.get(name, 0.0)) for name in AH_FEATURE_NAMES}


def ah_feature_vector(features: dict[str, float]) -> list[float]:
    return [float(features.get(name, 0.0)) for name in AH_FEATURE_NAMES]


def _odd_float(value: Any) -> float | None:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def _parse_line_float(line_raw: Any) -> float | None:
    if line_raw is None or line_raw == "":
        return None
    text = str(line_raw).strip().replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def extract_main_ah_line(
    odds: dict[str, Any] | None,
) -> tuple[float | None, float | None, float | None]:
    """Main AH line + home/away decimal odds from parsed odds package."""
    if not isinstance(odds, dict) or not odds.get("available", True):
        return None, None, None
    ah = odds.get("asian_handicap")
    if not isinstance(ah, dict):
        return None, None, None

    line_raw = ah.get("line")
    home_raw = ah.get("home")
    away_raw = ah.get("away")
    lines = ah.get("lines")
    if (line_raw is None or home_raw is None or away_raw is None) and isinstance(lines, list):
        for item in lines:
            if not isinstance(item, dict):
                continue
            line_raw = item.get("line")
            home_raw = item.get("home")
            away_raw = item.get("away")
            if line_raw is not None and home_raw is not None and away_raw is not None:
                break

    line_f = _parse_line_float(line_raw)
    home_f = _odd_float(home_raw)
    away_f = _odd_float(away_raw)
    if line_f is None or home_f is None or away_f is None:
        return None, None, None
    return line_f, home_f, away_f


def _league_tier_flags(league_id: int | None) -> tuple[float, float]:
    if league_id in TOP5_LEAGUE_IDS:
        return 1.0, 0.0
    if league_id in ASIA_LEAGUE_IDS:
        return 0.0, 1.0
    return 0.0, 0.0


def _implied_cover_prob(home_odd: float, away_odd: float) -> float:
    inv_h, inv_a = 1.0 / home_odd, 1.0 / away_odd
    total = inv_h + inv_a
    if total <= 0:
        return 0.5
    return inv_h / total


def _line_tier_flags(line_f: float) -> tuple[float, float, float]:
    al = abs(line_f)
    if al <= 0.75:
        return 1.0, 0.0, 0.0
    if al <= 1.35:
        return 0.0, 1.0, 0.0
    return 0.0, 0.0, 1.0


def settle_ah_label(
    home_goals: int | None,
    away_goals: int | None,
    line_f: float | None,
) -> str | None:
    """Return cover | no_cover | push | None."""
    if home_goals is None or away_goals is None or line_f is None:
        return None
    margin = float(home_goals) + float(line_f) - float(away_goals)
    if abs(margin) < 1e-9:
        return "push"
    return "cover" if margin > 0 else "no_cover"


def build_ah_features(
    package: dict[str, Any] | None,
    probs_1x2: dict[str, float] | None,
    *,
    league_id: int | None = None,
) -> tuple[dict[str, float], float | None, float | None, float | None]:
    """Build full AH feature dict + raw (line, home_odd, away_odd)."""
    package = package or {}
    base = extract_features(package)
    odds = package.get("odds") if isinstance(package.get("odds"), dict) else {}
    line_f, home_f, away_f = extract_main_ah_line(odds)

    probs = probs_1x2 or {}
    ph = float(probs.get("home", 1 / 3))
    pd = float(probs.get("draw", 1 / 3))
    pa = float(probs.get("away", 1 / 3))

    top5, asia = _league_tier_flags(league_id)
    has_ah = 1.0 if line_f is not None and home_f and away_f else 0.0

    if line_f is None or home_f is None or away_f is None:
        extra = {
            "ah_line_norm": 0.0,
            "ah_home_odd_inv": 0.0,
            "ah_away_odd_inv": 0.0,
            "ah_water_diff": 0.0,
            "ah_implied_cover": 0.5,
            "ah_line_abs_norm": 0.0,
            "ah_tier_shallow": 0.0,
            "ah_tier_medium": 0.0,
            "ah_tier_deep": 0.0,
            "ah_is_giving": 0.0,
            "mx_home_prob": ph,
            "mx_draw_prob": pd,
            "mx_away_prob": pa,
            "mx_vs_ah_gap": 0.0,
            "league_tier_top5": top5,
            "league_tier_asia": asia,
            "has_ah_market": 0.0,
        }
        return {**base, **extra}, None, None, None

    implied = _implied_cover_prob(home_f, away_f)
    shallow, medium, deep = _line_tier_flags(line_f)
    line_norm = max(-1.0, min(1.0, line_f / 2.5))
    extra = {
        "ah_line_norm": line_norm,
        "ah_home_odd_inv": 1.0 / home_f,
        "ah_away_odd_inv": 1.0 / away_f,
        "ah_water_diff": home_f - away_f,
        "ah_implied_cover": implied,
        "ah_line_abs_norm": min(1.0, abs(line_f) / 2.5),
        "ah_tier_shallow": shallow,
        "ah_tier_medium": medium,
        "ah_tier_deep": deep,
        "ah_is_giving": 1.0 if line_f < -0.05 else 0.0,
        "mx_home_prob": ph,
        "mx_draw_prob": pd,
        "mx_away_prob": pa,
        "mx_vs_ah_gap": ph - implied,
        "league_tier_top5": top5,
        "league_tier_asia": asia,
        "has_ah_market": has_ah,
    }
    return {**base, **extra}, line_f, home_f, away_f


def format_ah_line(line_f: float) -> str:
    value = float(line_f)
    if value.is_integer():
        text = str(int(value))
    else:
        text = str(value)
    # AH line is always from the home side: positive = home receives,
    # negative = home gives. Show '+' explicitly to remove ambiguity.
    return f"+{text}" if value > 0 else text


def pick_to_lean(pick: str) -> str:
    if pick == "cover":
        return "让球胜"
    if pick == "push":
        return "让球平"
    return "让球负"


def parse_score_hint(score_hint: str | None) -> list[tuple[int, int]]:
    """Extract scores from ``2-1`` or ``0-1 / 1-1`` style hints."""
    text = (score_hint or "").strip()
    if not text or "待分析" in text:
        return []
    found: list[tuple[int, int]] = []
    for match in re.finditer(r"(\d+)\s*[-:]\s*(\d+)", text):
        try:
            found.append((int(match.group(1)), int(match.group(2))))
        except ValueError:
            continue
    return found
