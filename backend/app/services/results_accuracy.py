"""Join finished fixtures with stored pre-match probs and score accuracy."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.fixture import Fixture
from app.models.pre_match_data import PreMatchData
from app.services.ah_features import (
    extract_main_ah_line,
    handicap_line_from_lean,
    handicap_pick_from_lean,
    settle_handicap_result,
)
from app.services.prematch_package import package_from_record
from app.services.prediction import (
    canonical_btts_lean,
    canonical_goal_lean,
    canonical_recommendation,
    canonical_score_hint,
    evaluate_prediction_vs_score,
    summarize_accuracy,
)


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
        "handicap_lean": None,
        "handicap_result": None,
        "handicap_hit": None,
        "score_hit": None,
        "ou_hit": None,
        "btts_hit": None,
        "result_hit": None,
        "single_result_hit": None,
        "evaluable": fixture.home_goals is not None and fixture.away_goals is not None,
    }

    if (
        stored is None
        or None in (stored.home_win_prob, stored.draw_prob, stored.away_win_prob)
    ):
        return payload

    # Audit uses only the frozen exam snapshot — never recompute with today's algorithm.
    recommendation = (getattr(stored, "recommendation", None) or "").strip()
    score_hint = (getattr(stored, "score_hint", None) or "").strip()
    goal_lean = (getattr(stored, "goal_lean", None) or "").strip()
    both_score_lean = (getattr(stored, "both_score_lean", None) or "").strip()
    handicap_lean = (getattr(stored, "handicap_lean", None) or "").strip()
    if not recommendation or recommendation == "待分析":
        return payload
    if not score_hint or score_hint == "待分析":
        # Older rows may lack score_hint; still count 1X2 / O/U / BTTS if present.
        score_hint = ""

    payload.update(
        {
            "has_prediction": True,
            "recommendation": canonical_recommendation(recommendation),
            "score_hint": canonical_score_hint(score_hint) or None,
            "goal_lean": canonical_goal_lean(goal_lean) or None,
            "both_score_lean": canonical_btts_lean(both_score_lean) or None,
            "handicap_lean": handicap_lean or None,
        }
    )

    package = package_from_record(stored)
    odds = package.get("odds") if isinstance(package, dict) else None
    line_f, _, _ = extract_main_ah_line(odds if isinstance(odds, dict) else None)
    if line_f is None:
        line_f = handicap_line_from_lean(handicap_lean)
    handicap_result = settle_handicap_result(
        fixture.home_goals,
        fixture.away_goals,
        line_f,
    )
    predicted_handicap = handicap_pick_from_lean(handicap_lean)
    payload["handicap_result"] = handicap_result
    if handicap_result is not None and predicted_handicap is not None:
        payload["handicap_hit"] = predicted_handicap == handicap_result

    hits = evaluate_prediction_vs_score(
        home_goals=fixture.home_goals,
        away_goals=fixture.away_goals,
        score_hint=score_hint or "",
        goal_lean=goal_lean or "",
        both_score_lean=both_score_lean or "",
        recommendation=recommendation or "",
    )
    payload["result_hit"] = hits["result_hit"]
    if fixture.home_goals is not None and fixture.away_goals is not None:
        predicted = max(
            ("home", "draw", "away"),
            key=lambda key: {
                "home": float(stored.home_win_prob or 0.0),
                "draw": float(stored.draw_prob or 0.0),
                "away": float(stored.away_win_prob or 0.0),
            }[key],
        )
        actual = (
            "home"
            if fixture.home_goals > fixture.away_goals
            else "away"
            if fixture.home_goals < fixture.away_goals
            else "draw"
        )
        payload["single_result_hit"] = predicted == actual
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
    start: date | None,
    end: date,
    league_ids: list[int],
) -> list[Fixture]:
    end_dt = datetime.combine(end, datetime.max.time())
    filters = [
        Fixture.date <= end_dt,
        Fixture.status == "finished",
        Fixture.home_goals.is_not(None),
        Fixture.away_goals.is_not(None),
    ]
    if league_ids:
        filters.append(Fixture.league_id.in_(league_ids))
    if start is not None:
        filters.append(Fixture.date >= datetime.combine(start, datetime.min.time()))
    stmt = (
        select(Fixture)
        .where(*filters)
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
    Overall + per-day accuracy for finished fixtures with scores.

    ``days <= 0`` (default) → **all** local finished fixtures (true historical total).
    ``days > 0`` → optional lookback ending at ``end_day`` (default: today).
    """
    end = end_day or date.today()
    if days and days > 0:
        window = max(1, min(int(days), 3650))
        start: date | None = end - timedelta(days=window - 1)
    else:
        window = 0
        start = None

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
            "single_result_hit": (
                evaluated["single_result_hit"] if evaluated["has_prediction"] else None
            ),
            "score_hit": evaluated["score_hit"] if evaluated["has_prediction"] else None,
            "ou_hit": evaluated["ou_hit"] if evaluated["has_prediction"] else None,
            "btts_hit": evaluated["btts_hit"] if evaluated["has_prediction"] else None,
            "handicap_hit": (
                evaluated["handicap_hit"] if evaluated["has_prediction"] else None
            ),
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
                "handicap_rate": day_summary["handicap"]["rate"],
                "result": day_summary["result"],
                "score": day_summary["score"],
                "ou": day_summary["ou"],
                "btts": day_summary["btts"],
                "handicap": day_summary["handicap"],
                "fixtures_with_prediction": day_summary["fixtures_with_prediction"],
                "fixtures_finished": day_summary["fixtures_finished"],
            }
        )

    overall = summarize_accuracy(overall_rows)
    series_start = series[0]["date"] if series else (start.isoformat() if start else end.isoformat())
    series_end = series[-1]["date"] if series else end.isoformat()
    # Echo requested window; 0 means all-time. For display, also expose sample span.
    span_days = window
    if window == 0 and series:
        try:
            span_days = (
                date.fromisoformat(series_end) - date.fromisoformat(series_start)
            ).days + 1
        except ValueError:
            span_days = 0
    return {
        "days": span_days if window == 0 else window,
        "start_date": series_start,
        "end_date": series_end,
        "overall": overall,
        "series": series,
        "all_time": window == 0,
    }
