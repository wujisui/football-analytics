"""Join finished fixtures with stored pre-match probs and score accuracy."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.fixture import Fixture
from app.models.pre_match_data import PreMatchData
from app.services.prediction import (
    build_prediction_snapshot,
    evaluate_prediction_vs_score,
    summarize_accuracy,
)
from app.services.prematch_package import loads_json, rehydrate_odds_markets


def evaluate_fixture_prediction(
    fixture: Fixture,
    stored: PreMatchData | None,
) -> dict[str, Any]:
    """Build prediction snapshot + hit flags for one fixture."""
    payload: dict[str, Any] = {
        "has_prediction": False,
        "recommendation": None,
        "score_hint": None,
        "goal_lean": None,
        "both_score_lean": None,
        "score_hit": None,
        "ou_hit": None,
        "btts_hit": None,
        "result_hit": None,
        "evaluable": fixture.home_goals is not None and fixture.away_goals is not None,
    }

    if (
        stored is None
        or None in (stored.home_win_prob, stored.draw_prob, stored.away_win_prob)
    ):
        return payload

    probs = {
        "home": stored.home_win_prob,
        "draw": stored.draw_prob,
        "away": stored.away_win_prob,
    }
    odds = rehydrate_odds_markets(loads_json(stored.odds_json, {"available": False}))
    snap = build_prediction_snapshot(probs, odds if isinstance(odds, dict) else None)

    # Prefer frozen snapshot written at analysis time; fall back to recompute.
    recommendation = getattr(stored, "recommendation", None) or snap["recommendation"]
    score_hint = getattr(stored, "score_hint", None) or snap["score_hint"]
    goal_lean = getattr(stored, "goal_lean", None) or snap["goal_lean"]
    both_score_lean = getattr(stored, "both_score_lean", None) or snap["both_score_lean"]
    has_prediction = recommendation != "待分析" and score_hint != "待分析"

    payload.update(
        {
            "has_prediction": has_prediction,
            "recommendation": recommendation,
            "score_hint": score_hint,
            "goal_lean": goal_lean,
            "both_score_lean": both_score_lean,
        }
    )

    if not has_prediction:
        return payload

    hits = evaluate_prediction_vs_score(
        home_goals=fixture.home_goals,
        away_goals=fixture.away_goals,
        score_hint=score_hint or "",
        goal_lean=goal_lean or "",
        both_score_lean=both_score_lean or "",
        recommendation=recommendation or "",
    )
    payload["result_hit"] = hits["result_hit"]
    payload["score_hit"] = hits["score_hit"]
    payload["ou_hit"] = hits["ou_hit"]
    payload["btts_hit"] = hits["btts_hit"]
    return payload


async def load_stored_by_fixture_ids(
    db: AsyncSession,
    fixture_ids: list[int],
) -> dict[int, PreMatchData]:
    if not fixture_ids:
        return {}
    rows = (
        await db.execute(
            select(PreMatchData).where(PreMatchData.fixture_id.in_(fixture_ids))
        )
    ).scalars().all()
    return {row.fixture_id: row for row in rows}


async def fetch_finished_fixtures(
    db: AsyncSession,
    *,
    start: date,
    end: date,
    league_ids: list[int],
) -> list[Fixture]:
    start_dt = datetime.combine(start, datetime.min.time())
    end_dt = datetime.combine(end, datetime.max.time())
    stmt = (
        select(Fixture)
        .where(
            Fixture.date >= start_dt,
            Fixture.date <= end_dt,
            Fixture.status == "finished",
            Fixture.league_id.in_(league_ids),
            Fixture.home_goals.is_not(None),
            Fixture.away_goals.is_not(None),
        )
        .options(
            selectinload(Fixture.home_team),
            selectinload(Fixture.away_team),
            selectinload(Fixture.league),
        )
        .order_by(Fixture.date)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


def _day_key(fixture_date: datetime) -> str:
    return fixture_date.date().isoformat()


async def build_history_accuracy(
    db: AsyncSession,
    *,
    days: int,
    league_ids: list[int],
    end_day: date | None = None,
) -> dict[str, Any]:
    """
    Overall + per-day accuracy for the last `days` calendar days ending at end_day
    (default: yesterday).
    """
    window = max(1, min(days, 90))
    end = end_day or (date.today() - timedelta(days=1))
    start = end - timedelta(days=window - 1)

    fixtures = await fetch_finished_fixtures(
        db, start=start, end=end, league_ids=league_ids
    )
    stored_by_id = await load_stored_by_fixture_ids(db, [f.id for f in fixtures])

    overall_rows: list[dict[str, Any]] = []
    by_day: dict[str, list[dict[str, Any]]] = {}

    for fx in fixtures:
        evaluated = evaluate_fixture_prediction(fx, stored_by_id.get(fx.id))
        row = {
            "has_prediction": evaluated["has_prediction"],
            "evaluable": evaluated["evaluable"],
            "result_hit": evaluated["result_hit"] if evaluated["has_prediction"] else None,
            "score_hit": evaluated["score_hit"] if evaluated["has_prediction"] else None,
            "ou_hit": evaluated["ou_hit"] if evaluated["has_prediction"] else None,
            "btts_hit": evaluated["btts_hit"] if evaluated["has_prediction"] else None,
        }
        overall_rows.append(row)
        day = _day_key(fx.date)
        by_day.setdefault(day, []).append(row)

    # Chart series: only days that actually have prediction samples.
    # Do not pad empty calendar days back to the lookback window start.
    series: list[dict[str, Any]] = []
    for key in sorted(by_day.keys()):
        day_summary = summarize_accuracy(by_day[key])
        if day_summary["fixtures_with_prediction"] <= 0:
            continue
        series.append(
            {
                "date": key,
                "result_rate": day_summary["result"]["rate"],
                "score_rate": day_summary["score"]["rate"],
                "ou_rate": day_summary["ou"]["rate"],
                "btts_rate": day_summary["btts"]["rate"],
                "result": day_summary["result"],
                "score": day_summary["score"],
                "ou": day_summary["ou"],
                "btts": day_summary["btts"],
                "fixtures_with_prediction": day_summary["fixtures_with_prediction"],
                "fixtures_finished": day_summary["fixtures_finished"],
            }
        )

    overall = summarize_accuracy(overall_rows)
    series_start = series[0]["date"] if series else start.isoformat()
    series_end = series[-1]["date"] if series else end.isoformat()
    return {
        "days": window,
        "start_date": series_start,
        "end_date": series_end,
        "overall": overall,
        "series": series,
    }
