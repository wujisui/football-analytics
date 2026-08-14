"""Daily auto-pick incentives: EMA rewards + prediction-package soft weights.

Pick layer (每日推荐): market-primary EMA + league offset.
Model soft layer (预测包): hit-rate multipliers with league×market fallback.
Persisted in ``app_settings``; refreshed at most once per scheduler-local day.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.app_setting import AppSetting
from app.models.auto_pick_snapshot import AutoPickSnapshot
from app.models.fixture import Fixture
from app.models.pre_match_data import PreMatchData
from app.services.results_accuracy import evaluate_fixture_prediction, load_auto_picks_by_fixture_ids
from app.services.runtime_settings import get_setting_row
from app.services.ttl_policy import is_finished_status

logger = logging.getLogger(__name__)

KEY_INCENTIVE_STATE = "auto_pick_incentive_state"

# Medium-strength EMA defaults (tunable via persisted state overrides).
DEFAULT_EMA_ALPHA = 0.12
DEFAULT_EMA_MARKET_WEIGHT = 1.0
DEFAULT_EMA_LEAGUE_WEIGHT = 0.35
DEFAULT_EMA_CLAMP = 0.5
DEFAULT_SOFT_MIN_SAMPLES = 20
DEFAULT_SOFT_MULT_MIN = 0.75
DEFAULT_SOFT_MULT_MAX = 1.25

MARKETS = ("1x2", "ah", "ou", "btts")


@dataclass(frozen=True)
class IncentiveParams:
    ema_alpha: float = DEFAULT_EMA_ALPHA
    ema_market_weight: float = DEFAULT_EMA_MARKET_WEIGHT
    ema_league_weight: float = DEFAULT_EMA_LEAGUE_WEIGHT
    ema_clamp: float = DEFAULT_EMA_CLAMP
    soft_min_samples: int = DEFAULT_SOFT_MIN_SAMPLES
    soft_mult_min: float = DEFAULT_SOFT_MULT_MIN
    soft_mult_max: float = DEFAULT_SOFT_MULT_MAX


@dataclass
class IncentiveState:
    updated_day: str | None = None
    params: IncentiveParams = None  # type: ignore[assignment]
    ema_market: dict[str, float] | None = None
    ema_league: dict[str, float] | None = None
    soft_weights: dict[str, float] | None = None
    # P10…P90 of historical pick scores; ladder behind the 0.5–5 星 rating.
    quality_deciles: list[float] | None = None

    def __post_init__(self) -> None:
        if self.params is None:
            self.params = IncentiveParams()
        if self.ema_market is None:
            self.ema_market = {}
        if self.ema_league is None:
            self.ema_league = {}
        if self.soft_weights is None:
            self.soft_weights = {"global": 1.0}


def _local_day(now: datetime | None = None) -> str:
    settings = get_settings()
    tz_name = settings.SCHEDULER_TIMEZONE
    current = now or datetime.utcnow()
    try:
        if current.tzinfo is None:
            aware = current.replace(tzinfo=ZoneInfo("UTC"))
        else:
            aware = current
        return aware.astimezone(ZoneInfo(tz_name)).date().isoformat()
    except Exception:
        return current.date().isoformat()


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def percentile(sorted_values: list[float], p: float) -> float | None:
    """Inclusive linear percentile; ``p`` in 0–100."""
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    rank = (len(sorted_values) - 1) * (p / 100.0)
    lo = int(math.floor(rank))
    hi = int(math.ceil(rank))
    if lo == hi:
        return float(sorted_values[lo])
    weight = rank - lo
    return float(sorted_values[lo] * (1.0 - weight) + sorted_values[hi] * weight)


def hit_rate_to_multiplier(
    rate: float | None,
    *,
    mult_min: float = DEFAULT_SOFT_MULT_MIN,
    mult_max: float = DEFAULT_SOFT_MULT_MAX,
) -> float:
    """Map hit rate in [0,1] → soft multiplier; missing rate → 1.0."""
    if rate is None:
        return 1.0
    return mult_min + (mult_max - mult_min) * _clamp(float(rate), 0.0, 1.0)


def soft_weight_keys(league_id: int, market: str) -> tuple[str, str, str, str]:
    """Fallback order: league×market → market → league → global."""
    return (
        f"{league_id}|{market}",
        f"m:{market}",
        f"l:{league_id}",
        "global",
    )


def resolve_soft_weight(
    soft_weights: dict[str, float],
    *,
    league_id: int,
    market: str,
) -> float:
    for key in soft_weight_keys(league_id, market):
        if key in soft_weights:
            return float(soft_weights[key])
    return 1.0


def ema_adjustment(
    *,
    market: str,
    league_id: int,
    ema_market: dict[str, float],
    ema_league: dict[str, float],
    params: IncentiveParams,
) -> float:
    """玩法为主 + 联赛偏移为辅 → multiplicative factor around 1.0."""
    m = _clamp(float(ema_market.get(market, 0.0)), -params.ema_clamp, params.ema_clamp)
    league_key = str(int(league_id))
    league = _clamp(
        float(ema_league.get(league_key, 0.0)),
        -params.ema_clamp,
        params.ema_clamp,
    )
    delta = params.ema_market_weight * m + params.ema_league_weight * league
    return max(0.35, 1.0 + delta)


def adjust_pick_score(
    base_score: float,
    *,
    league_id: int,
    market: str,
    state: IncentiveState,
) -> float:
    soft = resolve_soft_weight(
        state.soft_weights or {},
        league_id=league_id,
        market=market,
    )
    ema = ema_adjustment(
        market=market,
        league_id=league_id,
        ema_market=state.ema_market or {},
        ema_league=state.ema_league or {},
        params=state.params,
    )
    return float(base_score) * soft * ema


QUALITY_DECILE_POINTS = (10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0)
QUALITY_RATING_STEP = 0.5


def build_quality_deciles(scores: list[float]) -> list[float]:
    """P10…P90 ladder of historical pick scores (empty when no history)."""
    ordered = sorted(scores)
    if not ordered:
        return []
    return [
        value
        for point in QUALITY_DECILE_POINTS
        if (value := percentile(ordered, point)) is not None
    ]


def quality_rating(score: float, deciles: list[float] | None) -> float | None:
    """Rank ``score`` against the decile ladder → 0.5–5 星 in half-star steps.

    Returns ``None`` while history is too thin to rank against.
    """
    if not deciles:
        return None
    beaten = sum(1 for edge in deciles if float(score) >= float(edge))
    return round((beaten + 1) * QUALITY_RATING_STEP, 1)


def params_from_dict(raw: dict[str, Any] | None) -> IncentiveParams:
    data = raw or {}
    return IncentiveParams(
        ema_alpha=float(data.get("ema_alpha", DEFAULT_EMA_ALPHA)),
        ema_market_weight=float(
            data.get("ema_market_weight", DEFAULT_EMA_MARKET_WEIGHT)
        ),
        ema_league_weight=float(
            data.get("ema_league_weight", DEFAULT_EMA_LEAGUE_WEIGHT)
        ),
        ema_clamp=float(data.get("ema_clamp", DEFAULT_EMA_CLAMP)),
        soft_min_samples=int(data.get("soft_min_samples", DEFAULT_SOFT_MIN_SAMPLES)),
        soft_mult_min=float(data.get("soft_mult_min", DEFAULT_SOFT_MULT_MIN)),
        soft_mult_max=float(data.get("soft_mult_max", DEFAULT_SOFT_MULT_MAX)),
    )


def state_from_dict(raw: dict[str, Any] | None) -> IncentiveState:
    data = raw or {}
    return IncentiveState(
        updated_day=data.get("updated_day"),
        params=params_from_dict(data.get("params") if isinstance(data.get("params"), dict) else data),
        ema_market={str(k): float(v) for k, v in (data.get("ema_market") or {}).items()},
        ema_league={str(k): float(v) for k, v in (data.get("ema_league") or {}).items()},
        soft_weights={
            str(k): float(v) for k, v in (data.get("soft_weights") or {"global": 1.0}).items()
        },
        quality_deciles=[
            float(value) for value in (data.get("quality_deciles") or [])
        ],
    )


def state_to_dict(state: IncentiveState) -> dict[str, Any]:
    p = state.params
    return {
        "updated_day": state.updated_day,
        "params": {
            "ema_alpha": p.ema_alpha,
            "ema_market_weight": p.ema_market_weight,
            "ema_league_weight": p.ema_league_weight,
            "ema_clamp": p.ema_clamp,
            "soft_min_samples": p.soft_min_samples,
            "soft_mult_min": p.soft_mult_min,
            "soft_mult_max": p.soft_mult_max,
        },
        "ema_market": dict(state.ema_market or {}),
        "ema_league": dict(state.ema_league or {}),
        "soft_weights": dict(state.soft_weights or {"global": 1.0}),
        "quality_deciles": list(state.quality_deciles or []),
    }


def update_ema_value(
    previous: float,
    signal: float,
    *,
    alpha: float,
    clamp: float,
) -> float:
    nxt = (1.0 - alpha) * previous + alpha * signal
    return _clamp(nxt, -clamp, clamp)


def walk_auto_pick_ema(
    settled: list[tuple[str, int, bool]],
    *,
    params: IncentiveParams,
) -> tuple[dict[str, float], dict[str, float]]:
    """Chronological EMA over ``(market, league_id, hit)`` auto-pick settlements."""
    ema_market: dict[str, float] = {}
    ema_league: dict[str, float] = {}
    for market, league_id, hit in settled:
        signal = 1.0 if hit else -1.0
        ema_market[market] = update_ema_value(
            ema_market.get(market, 0.0),
            signal,
            alpha=params.ema_alpha,
            clamp=params.ema_clamp,
        )
        league_key = str(int(league_id))
        # League offset learns slower so market stays primary.
        ema_league[league_key] = update_ema_value(
            ema_league.get(league_key, 0.0),
            signal,
            alpha=params.ema_alpha * 0.75,
            clamp=params.ema_clamp,
        )
    return ema_market, ema_league


def _rate(hits: int, total: int) -> float | None:
    if total <= 0:
        return None
    return hits / total


def build_soft_weights(
    cells: dict[tuple[int, str], tuple[int, int]],
    *,
    params: IncentiveParams,
) -> dict[str, float]:
    """Build persisted multipliers with sample gate + fallback rates."""
    market_hits: dict[str, list[int]] = {m: [0, 0] for m in MARKETS}
    league_hits: dict[int, list[int]] = {}
    global_hits = [0, 0]

    for (league_id, market), (hits, total) in cells.items():
        if market not in market_hits:
            continue
        market_hits[market][0] += hits
        market_hits[market][1] += total
        bucket = league_hits.setdefault(league_id, [0, 0])
        bucket[0] += hits
        bucket[1] += total
        global_hits[0] += hits
        global_hits[1] += total

    weights: dict[str, float] = {
        "global": hit_rate_to_multiplier(
            _rate(global_hits[0], global_hits[1]),
            mult_min=params.soft_mult_min,
            mult_max=params.soft_mult_max,
        )
    }
    for market, (hits, total) in market_hits.items():
        if total >= params.soft_min_samples:
            weights[f"m:{market}"] = hit_rate_to_multiplier(
                _rate(hits, total),
                mult_min=params.soft_mult_min,
                mult_max=params.soft_mult_max,
            )
    for league_id, (hits, total) in league_hits.items():
        if total >= params.soft_min_samples:
            weights[f"l:{league_id}"] = hit_rate_to_multiplier(
                _rate(hits, total),
                mult_min=params.soft_mult_min,
                mult_max=params.soft_mult_max,
            )
    for (league_id, market), (hits, total) in cells.items():
        if total >= params.soft_min_samples:
            weights[f"{league_id}|{market}"] = hit_rate_to_multiplier(
                _rate(hits, total),
                mult_min=params.soft_mult_min,
                mult_max=params.soft_mult_max,
            )
    return weights


async def load_incentive_state(db: AsyncSession) -> IncentiveState:
    row = await get_setting_row(db, KEY_INCENTIVE_STATE)
    if row is None or not (row.value or "").strip():
        return IncentiveState()
    try:
        raw = json.loads(row.value)
    except json.JSONDecodeError:
        logger.warning("Invalid %s JSON; resetting incentive state", KEY_INCENTIVE_STATE)
        return IncentiveState()
    if not isinstance(raw, dict):
        return IncentiveState()
    return state_from_dict(raw)


async def save_incentive_state(db: AsyncSession, state: IncentiveState) -> None:
    payload = json.dumps(state_to_dict(state), ensure_ascii=False, sort_keys=True)
    row = await get_setting_row(db, KEY_INCENTIVE_STATE)
    if row is None:
        db.add(AppSetting(key=KEY_INCENTIVE_STATE, value=payload))
    else:
        row.value = payload
    await db.flush()


async def _load_finished_prediction_rows(
    db: AsyncSession,
) -> list[tuple[Fixture, PreMatchData]]:
    stmt = (
        select(Fixture, PreMatchData)
        .join(PreMatchData, PreMatchData.fixture_id == Fixture.id)
        .where(
            Fixture.home_goals.is_not(None),
            Fixture.away_goals.is_not(None),
        )
        .order_by(Fixture.date, Fixture.id)
    )
    rows = (await db.execute(stmt)).all()
    out: list[tuple[Fixture, PreMatchData]] = []
    for fixture, stored in rows:
        if not is_finished_status(fixture.status):
            continue
        out.append((fixture, stored))
    return out


def _package_market_hits(evaluated: dict[str, Any]) -> dict[str, bool | None]:
    return {
        "1x2": evaluated.get("result_hit"),
        "ah": evaluated.get("handicap_hit"),
        "ou": evaluated.get("ou_hit"),
        "btts": evaluated.get("btts_hit"),
    }


async def refresh_incentive_state(
    db: AsyncSession,
    *,
    now: datetime | None = None,
    force: bool = False,
) -> IncentiveState:
    """Recompute EMA + soft weights once per scheduler-local day.

    A same-day state without the quality ladder is stale (older format), so it
    is refreshed anyway instead of leaving every pick unrated.
    """
    state = await load_incentive_state(db)
    today = _local_day(now)
    if not force and state.updated_day == today and state.quality_deciles:
        return state

    params = state.params
    # Preserve tunable overrides from prior params blob.
    prior = state_to_dict(state).get("params") or {}
    params = params_from_dict(prior)

    finished = await _load_finished_prediction_rows(db)
    fixture_ids = [fx.id for fx, _ in finished]
    auto_by_id = await load_auto_picks_by_fixture_ids(db, fixture_ids)

    auto_settled: list[tuple[str, int, bool]] = []
    package_cells: dict[tuple[int, str], list[int]] = {}

    for fixture, stored in finished:
        evaluated = evaluate_fixture_prediction(
            fixture,
            stored,
            auto_pick=auto_by_id.get(fixture.id),
        )
        if not evaluated.get("evaluable"):
            continue
        auto_hit = evaluated.get("auto_pick_hit")
        auto_market = evaluated.get("auto_pick_market")
        if auto_hit is not None and auto_market:
            auto_settled.append((str(auto_market), int(fixture.league_id), bool(auto_hit)))

        if not evaluated.get("has_prediction"):
            continue
        for market, hit in _package_market_hits(evaluated).items():
            if hit is None:
                continue
            key = (int(fixture.league_id), market)
            bucket = package_cells.setdefault(key, [0, 0])
            bucket[1] += 1
            if hit:
                bucket[0] += 1

    ema_market, ema_league = walk_auto_pick_ema(auto_settled, params=params)
    soft_weights = build_soft_weights(
        {k: (v[0], v[1]) for k, v in package_cells.items()},
        params=params,
    )

    # Quality ladder: deciles of historical auto-pick composite scores.
    snap_rows = (
        await db.execute(
            select(AutoPickSnapshot.score, AutoPickSnapshot.expected_return).order_by(
                AutoPickSnapshot.picked_at, AutoPickSnapshot.id
            )
        )
    ).all()
    hist_scores: list[float] = []
    for score, expected_return in snap_rows:
        value = score if score is not None else expected_return
        if value is None:
            continue
        hist_scores.append(float(value))
    deciles = build_quality_deciles(hist_scores)

    state = IncentiveState(
        updated_day=today,
        params=params,
        ema_market=ema_market,
        ema_league=ema_league,
        soft_weights=soft_weights,
        quality_deciles=deciles,
    )
    await save_incentive_state(db, state)
    logger.info(
        "Auto-pick incentives refreshed day=%s auto_settled=%s soft_keys=%s "
        "quality_deciles=%s",
        today,
        len(auto_settled),
        len(soft_weights),
        [round(value, 4) for value in deciles],
    )
    return state


async def ensure_incentives_for_picks(
    db: AsyncSession,
    *,
    now: datetime | None = None,
) -> IncentiveState:
    """Load persisted incentives; refresh once if local day not yet updated."""
    return await refresh_incentive_state(db, now=now, force=False)
