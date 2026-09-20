"""Read the bookmaker main AH board: water gap, dead zone, giving-side median.

Thresholds come from local finished quotes. The dead zone is the 25th percentile
of |home-away water|, clipped so it stays a noise band rather than the typical
gap (the median of all boards is ~0.15 and would empty the daily slate). The
moneyline gate is the median giving-side water, refreshed from the same sample.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import BACKEND_ROOT
from app.services.ah_features import extract_main_ah_line

logger = logging.getLogger(__name__)

MODEL_DIR = BACKEND_ROOT / "data" / "models"
THRESHOLDS_NAME = "ah_market_thresholds.json"

FALLBACK_WATER_DEADZONE = 0.06
FALLBACK_GIVING_ODD_MEDIAN = 1.94
DEADZONE_MIN = 0.04
DEADZONE_MAX = 0.08
MIN_THRESHOLD_SAMPLES = 30
# |盘口| ≥ 1 视为深盘：受让侧赢在「输一球以内」，卡片的胜负方向装不下这层意思。
DEEP_AH_LINE = 1.0
_LINE_EPSILON = 1e-9

_cached: dict[str, Any] | None = None


@dataclass(frozen=True)
class AhBoardStance:
    line: float
    home_odd: float
    away_odd: float
    giving_side: str
    giving_odd: float
    receiving_odd: float
    water_diff: float
    even: bool
    directional: bool
    follow_up: bool
    ah_pick: str
    result_choice: str
    allow_moneyline: bool
    water_deadzone: float
    giving_odd_median: float

    @property
    def lean_token(self) -> str:
        if self.ah_pick == "让胜/负":
            return "cover/no_cover"
        return "cover" if self.ah_pick == "让胜" else "no_cover"

    @property
    def is_deep(self) -> bool:
        return abs(self.line) + _LINE_EPSILON >= DEEP_AH_LINE


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * p
    lo = int(math.floor(rank))
    hi = int(math.ceil(rank))
    if lo == hi:
        return ordered[lo]
    weight = rank - lo
    return ordered[lo] * (1.0 - weight) + ordered[hi] * weight


def _median(values: list[float]) -> float | None:
    return _percentile(values, 0.5)


def giving_side_and_odds(
    line: float, home_odd: float, away_odd: float
) -> tuple[str, float, float]:
    """让球方 is the side giving balls; 平手 uses the cheaper side as that role."""
    if line < -1e-9:
        return "home", home_odd, away_odd
    if line > 1e-9:
        return "away", away_odd, home_odd
    if home_odd <= away_odd:
        return "home", home_odd, away_odd
    return "away", away_odd, home_odd


def thresholds_from_quotes(
    quotes: list[tuple[float, float, float]],
) -> dict[str, Any]:
    """Build dead zone + giving-odd median from ``(line, home_odd, away_odd)``."""
    abs_diffs: list[float] = []
    giving_odds: list[float] = []
    for line, home_odd, away_odd in quotes:
        if home_odd <= 0 or away_odd <= 0:
            continue
        abs_diffs.append(abs(home_odd - away_odd))
        _side, giving_odd, _recv = giving_side_and_odds(line, home_odd, away_odd)
        giving_odds.append(giving_odd)
    n = min(len(abs_diffs), len(giving_odds))
    p25 = _percentile(abs_diffs, 0.25)
    median_giving = _median(giving_odds)
    if n < MIN_THRESHOLD_SAMPLES or p25 is None or median_giving is None:
        deadzone = FALLBACK_WATER_DEADZONE
        giving_median = FALLBACK_GIVING_ODD_MEDIAN
    else:
        deadzone = min(DEADZONE_MAX, max(DEADZONE_MIN, float(p25)))
        giving_median = float(median_giving)
    return {
        "n_samples": n,
        "water_deadzone": deadzone,
        "water_diff_p25": None if p25 is None else round(float(p25), 4),
        "giving_odd_median": giving_median,
        "abs_water_mean": (
            round(sum(abs_diffs) / len(abs_diffs), 4) if abs_diffs else None
        ),
    }


def fallback_thresholds() -> dict[str, Any]:
    return {
        "n_samples": 0,
        "water_deadzone": FALLBACK_WATER_DEADZONE,
        "water_diff_p25": FALLBACK_WATER_DEADZONE,
        "giving_odd_median": FALLBACK_GIVING_ODD_MEDIAN,
        "abs_water_mean": None,
    }


def thresholds_path() -> Path:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    return MODEL_DIR / THRESHOLDS_NAME


def save_thresholds(payload: dict[str, Any]) -> Path:
    path = thresholds_path()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    global _cached
    _cached = dict(payload)
    return path


def load_thresholds() -> dict[str, Any]:
    global _cached
    if _cached is not None:
        return dict(_cached)
    path = MODEL_DIR / THRESHOLDS_NAME
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("water_deadzone"):
                _cached = data
                return dict(data)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to load AH market thresholds: %s", exc)
    payload = fallback_thresholds()
    _cached = payload
    return dict(payload)


def reset_threshold_cache() -> None:
    global _cached
    _cached = None


def classify_ah_board(
    odds: dict[str, Any] | None,
    *,
    thresholds: dict[str, Any] | None = None,
) -> AhBoardStance | None:
    line, home_odd, away_odd = extract_main_ah_line(odds)
    if line is None or home_odd is None or away_odd is None:
        return None
    cfg = thresholds if isinstance(thresholds, dict) else load_thresholds()
    try:
        deadzone = float(cfg.get("water_deadzone") or FALLBACK_WATER_DEADZONE)
    except (TypeError, ValueError):
        deadzone = FALLBACK_WATER_DEADZONE
    try:
        giving_median = float(
            cfg.get("giving_odd_median") or FALLBACK_GIVING_ODD_MEDIAN
        )
    except (TypeError, ValueError):
        giving_median = FALLBACK_GIVING_ODD_MEDIAN
    deadzone = min(DEADZONE_MAX, max(DEADZONE_MIN, deadzone))

    giving_side, giving_odd, receiving_odd = giving_side_and_odds(
        line, home_odd, away_odd
    )
    water_diff = giving_odd - receiving_odd
    # 死区只挡下注（日推），不挡展示：赛前分析拿不准也要给出最可能的一侧，
    # 所以方向恒按较低水位（庄家更不愿意收的那边）走，只有两边完全同水才无向。
    even = abs(water_diff) < deadzone
    directional = water_diff != 0
    follow_up = directional and water_diff < 0
    if not directional:
        # 浅盘同水不再双选；|盘口| ≥ 1 才允许 让胜/负。
        if abs(line) + 1e-9 < 1.0:
            ah_pick = "让胜" if line <= 0 else "让负"
            result_choice = "home" if line <= 0 else "away"
        else:
            ah_pick = "让胜/负"
            result_choice = ""
        allow_moneyline = False
    elif follow_up:
        ah_pick = "让胜" if giving_side == "home" else "让负"
        result_choice = giving_side
        allow_moneyline = (not even) and giving_odd < giving_median
    else:
        ah_pick = "让负" if giving_side == "home" else "让胜"
        result_choice = "away" if giving_side == "home" else "home"
        allow_moneyline = False
    return AhBoardStance(
        line=line,
        home_odd=home_odd,
        away_odd=away_odd,
        giving_side=giving_side,
        giving_odd=giving_odd,
        receiving_odd=receiving_odd,
        water_diff=water_diff,
        even=even,
        directional=directional,
        follow_up=follow_up,
        ah_pick=ah_pick,
        result_choice=result_choice,
        allow_moneyline=allow_moneyline,
        water_deadzone=deadzone,
        giving_odd_median=giving_median,
    )


def bettable_side(stance: AhBoardStance) -> str:
    """The AH side a card can actually put into words.

    浅盘跟水位：两侧都能被对应胜负方向讲清楚，买过半的那一边。深盘一律取让球方：
    受让侧赢在「输一球以内」，而卡片胜负方向只有主胜 / 客胜两格，装不下这层意思，
    曼城 -1.5 买 客+1.5 会被讲成「客胜、比分 1-3」。两侧同价的无向盘保持双选。
    """
    if not stance.directional or not stance.is_deep:
        return stance.result_choice
    return stance.giving_side


def bettable_token(stance: AhBoardStance) -> str:
    """``bettable_side`` as the cover / no_cover token used by the predictor."""
    side = bettable_side(stance)
    if side == "home":
        return "cover"
    if side == "away":
        return "no_cover"
    return stance.lean_token


def recommendation_from_ah_board(
    odds: dict[str, Any] | None,
    *,
    thresholds: dict[str, Any] | None = None,
) -> str | None:
    """Map the main AH board to 主胜 / 客胜.

    None when there is no line, no water gap, **or the board is deep**: 让 1 球以上
    时哪一侧水位低只说明「热门大概率吃不下这个盘」，不说明谁赢球，把它当胜负方向
    会把曼城让 1.5 球读成「客胜」。深盘交回去水 1X2 盘面判断。
    """
    stance = classify_ah_board(odds, thresholds=thresholds)
    if stance is None or not stance.directional or stance.is_deep:
        return None
    return "主胜" if stance.result_choice == "home" else "客胜"


async def refresh_ah_market_thresholds(session: Any) -> dict[str, Any]:
    """Recompute thresholds from finished local quotes. No official API."""
    from sqlalchemy import select

    from app.models.fixture import Fixture
    from app.models.pre_match_data import PreMatchData
    from app.services.results_accuracy import fixture_ready_to_grade

    rows = (
        await session.execute(
            select(Fixture, PreMatchData).join(
                PreMatchData, PreMatchData.fixture_id == Fixture.id
            )
        )
    ).all()
    quotes: list[tuple[float, float, float]] = []
    for fixture, stored in rows:
        if not fixture_ready_to_grade(fixture):
            continue
        try:
            odds = json.loads(stored.odds_json or "")
        except json.JSONDecodeError:
            continue
        line, home_odd, away_odd = extract_main_ah_line(
            odds if isinstance(odds, dict) else None
        )
        if line is None or home_odd is None or away_odd is None:
            continue
        quotes.append((line, home_odd, away_odd))
    payload = thresholds_from_quotes(quotes)
    save_thresholds(payload)
    logger.info(
        "AH market thresholds n=%s deadzone=%.3f giving_median=%.3f",
        payload.get("n_samples"),
        payload.get("water_deadzone"),
        payload.get("giving_odd_median"),
    )
    return payload
