"""只读回放当前统一推荐链路，并对比模型影子轨道。

不调官方 API、不写数据库、不改模型与校准产物。输出两条轨道：

1. ``live``：线上现行口径。概率来自盘口去水（模型未过门禁时），按最低置信度 +
   方向闸过滤，再按 AH → 大小球 → 双进 → 无盘独赢分层取每个比赛日 Top 4。
2. ``model_shadow``：把现有模型产物临时设为可部署并使用恒等 Platt，回答“如果让
   模型直接接管概率，它在训练完成后的比赛上能打多少”。仅供决定模型何时可以上
   线，不是线上成绩。

用法：
    python scripts/backtest_current_recommendation.py
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import AsyncSessionLocal
from app.models.fixture import Fixture
from app.models.pre_match_data import PreMatchData
from app.services import ah_predictor, goal_predictor, ml_predictor
from app.services.ah_features import (
    ASIAN_HALF_LOSS,
    ASIAN_HALF_WIN,
    ASIAN_LOSS,
    ASIAN_PUSH,
    ASIAN_WIN,
    handicap_line_from_lean,
    handicap_picks_from_lean,
    settle_asian_total,
    settle_handicap_pick,
)
from app.services.probability_calibration import (
    CALIBRATION_VERSION,
    PROBABILITY_SOURCES,
    load_calibration_artifact,
)
from app.services.recommendation.pipeline import (
    match_input_from_fixture_row,
    run_pipeline,
)
from app.services.results_accuracy import settle_auto_pick_hit

MARKETS = ("1x2", "ah", "ou", "btts")


def _parse_trained_at(*statuses: dict[str, Any]) -> datetime:
    values = [
        datetime.fromisoformat(str(status["trained_at"])).replace(tzinfo=None)
        for status in statuses
        if status.get("trained_at")
    ]
    return max(values)


def _identity_calibration() -> dict[str, Any]:
    return {
        "version": CALIBRATION_VERSION,
        "markets": {
            f"{market}:{source}": {"deployable": True, "a": 1.0, "b": 0.0}
            for market in MARKETS
            for source in PROBABILITY_SOURCES
        },
    }


def _force_model_deployment() -> None:
    """Patch only this process; production gates and artifacts stay untouched."""
    one_model, one_meta = ml_predictor.load_trained_model()
    ah_model, ah_meta = ah_predictor.load_trained_model()
    goal_model, goal_meta = goal_predictor.load_model(ignore_deployable=True)

    forced_one_meta = {**one_meta, "deployable": True}
    forced_ah_meta = {**ah_meta, "deployable": True}
    forced_goal_meta = {
        **goal_meta,
        "deployable": True,
        "target_gates": {"score": True, "ou": True, "btts": True},
    }
    ml_predictor.load_trained_model = lambda: (one_model, forced_one_meta)
    ml_predictor.model_status = lambda: {"deployable": True, "feature_version": ""}
    ah_predictor.load_trained_model = lambda: (ah_model, forced_ah_meta)
    ah_predictor.model_status = lambda: {"deployable": True, "ah_feature_version": ""}
    goal_predictor.load_model = lambda **_: (goal_model, forced_goal_meta)


async def _load_finished_inputs(since: datetime) -> tuple[list[Any], dict[int, Fixture]]:
    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                select(Fixture, PreMatchData)
                .join(PreMatchData, PreMatchData.fixture_id == Fixture.id)
                .where(
                    Fixture.date >= since,
                    Fixture.home_goals.is_not(None),
                    Fixture.away_goals.is_not(None),
                )
                .order_by(Fixture.date, Fixture.id)
            )
        ).all()
        inputs = [
            match_input_from_fixture_row(fixture, stored)
            for fixture, stored in rows
        ]
        return inputs, {int(fixture.id): fixture for fixture, _ in rows}


def _settlement_code(pick: Any, fixture: Fixture, hit: bool | None) -> str | None:
    lean = pick.market_lean or pick.lean
    if pick.market == "ah":
        picks = handicap_picks_from_lean(lean)
        if len(picks) == 1:
            return settle_handicap_pick(
                int(fixture.home_goals),
                int(fixture.away_goals),
                handicap_line_from_lean(lean),
                next(iter(picks)),
            )
        return None
    if pick.market == "ou" and pick.market_lean:
        return settle_asian_total(
            int(fixture.home_goals) + int(fixture.away_goals),
            float(pick.market_lean.split("(", 1)[1].rstrip(")")),
            over=pick.recommended_choice == "over",
        )
    if hit is not None:
        return ASIAN_WIN if hit else ASIAN_LOSS
    return None


def _score(result: dict[str, Any], fixtures: dict[int, Fixture]) -> dict[str, Any]:
    by_market: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    by_day: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    sources: dict[str, int] = defaultdict(int)
    pushes = 0
    total_return = 0.0
    for pick in result["picks"]:
        fixture = fixtures[pick.fixture_id]
        lean = pick.market_lean or pick.lean
        sources[f"{pick.market}:{pick.probability_source}"] += 1
        hit = settle_auto_pick_hit(
            market=pick.market,
            lean=lean,
            home_goals=fixture.home_goals,
            away_goals=fixture.away_goals,
            handicap_line=(
                handicap_line_from_lean(lean) if pick.market == "ah" else None
            ),
        )
        if hit is None:
            pushes += 1
        else:
            by_market[pick.market][1] += 1
            by_market[pick.market][0] += int(hit)
            by_day[pick.match_day][1] += 1
            by_day[pick.match_day][0] += int(hit)

        profit = float(pick.decimal_odd) - 1.0
        total_return += {
            ASIAN_WIN: profit,
            ASIAN_HALF_WIN: profit / 2.0,
            ASIAN_PUSH: 0.0,
            ASIAN_HALF_LOSS: -0.5,
            ASIAN_LOSS: -1.0,
        }.get(_settlement_code(pick, fixture, hit) or "", 0.0)

    picks = result["picks"]
    hits = sum(value[0] for value in by_market.values())
    total = sum(value[1] for value in by_market.values())
    evs = [float(pick.ev) for pick in picks if pick.ev is not None]
    return {
        "eligible": result["candidate_count"],
        "selected": len(picks),
        "evaluable": total,
        "hits": hits,
        "hit_rate": hits / total if total else None,
        "pushes": pushes,
        "unit_return": round(total_return, 3),
        "roi": total_return / len(picks) if picks else None,
        "average_confidence": (
            sum(float(pick.confidence) for pick in picks) / len(picks)
            if picks
            else None
        ),
        "average_ev": sum(evs) / len(evs) if evs else None,
        "probability_sources": dict(sorted(sources.items())),
        "by_market": {
            market: {
                "hits": value[0],
                "total": value[1],
                "hit_rate": value[0] / value[1] if value[1] else None,
            }
            for market, value in sorted(by_market.items())
        },
        "by_day": {
            day: {
                "hits": value[0],
                "total": value[1],
                "hit_rate": value[0] / value[1] if value[1] else None,
            }
            for day, value in sorted(by_day.items())
        },
    }


async def main() -> None:
    one_status = ml_predictor.model_status()
    ah_status = ah_predictor.model_status()
    goal_status = goal_predictor.model_status()
    since = _parse_trained_at(one_status, ah_status, goal_status)
    inputs, fixtures = await _load_finished_inputs(since)
    gates = {
        "1x2": bool(one_status.get("deployable")),
        "ah": bool(ah_status.get("deployable")),
        "ou": bool((goal_status.get("target_gates") or {}).get("ou")),
        "btts": bool((goal_status.get("target_gates") or {}).get("btts")),
    }

    live = run_pipeline(
        inputs,
        market_artifact=load_calibration_artifact(),
        limit_per_day=4,
    )
    live_score = _score(live, fixtures)

    _force_model_deployment()
    shadow = run_pipeline(
        inputs,
        market_artifact=_identity_calibration(),
        limit_per_day=4,
    )

    print(
        json.dumps(
            {
                "since": since.isoformat(),
                "finished_fixtures": len(inputs),
                "model_gates_passed": gates,
                "live": live_score,
                "model_shadow": _score(shadow, fixtures),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
