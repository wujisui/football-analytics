"""Join finished fixtures with stored pre-match probs and score accuracy."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.auto_pick_snapshot import AutoPickSnapshot
from app.models.fixture import Fixture
from app.models.pre_match_data import PreMatchData
from app.services.ah_features import (
    display_handicap_lean,
    extract_main_ah_line,
    handicap_line_from_lean,
    handicap_picks_from_lean,
    settle_handicap_result,
)
from app.services.prematch_package import package_from_record
from app.services.ttl_policy import is_finished_status
from app.services.prediction import (
    canonical_btts_lean,
    canonical_goal_lean,
    canonical_recommendation,
    canonical_score_hint,
    evaluate_prediction_vs_score,
    recommendation_outcomes,
    summarize_accuracy,
)

# Official short codes that mean regulation (or AET/PEN) is final.
_FINISHED_SHORT = frozenset({"FT", "AET", "PEN"})


def fixture_ready_to_grade(fixture: Fixture) -> bool:
    """True when local score is final enough to settle recommendations.

    Prefer mapped ``status=finished``; also accept FT/AET/PEN short codes when
    detail refresh wrote the board but a stale ``live`` status lingered.
    """
    if fixture.home_goals is None or fixture.away_goals is None:
        return False
    if is_finished_status(fixture.status):
        return True
    short = (getattr(fixture, "status_short", None) or "").strip().upper()
    return short in _FINISHED_SHORT


def settle_auto_pick_hit(
    *,
    market: str,
    lean: str,
    home_goals: int | None,
    away_goals: int | None,
    handicap_line: float | None = None,
) -> bool | None:
    """Grade one frozen daily auto pick against full-time score."""
    if home_goals is None or away_goals is None:
        return None
    market_key = (market or "").strip()
    lean_text = (lean or "").strip()
    if not market_key or not lean_text:
        return None

    if market_key == "1x2":
        outcomes = recommendation_outcomes(lean_text)
        if not outcomes or len(outcomes) != 1:
            return None
        if home_goals > away_goals:
            actual = "home"
        elif home_goals < away_goals:
            actual = "away"
        else:
            actual = "draw"
        return actual in outcomes

    if market_key == "ah":
        picks = handicap_picks_from_lean(lean_text)
        if len(picks) != 1:
            return None
        line = handicap_line if handicap_line is not None else handicap_line_from_lean(lean_text)
        settled = settle_handicap_result(home_goals, away_goals, line)
        if settled is None:
            return None
        return settled in picks

    if market_key == "ou":
        hits = evaluate_prediction_vs_score(
            home_goals=home_goals,
            away_goals=away_goals,
            score_hint="",
            goal_lean=lean_text,
            both_score_lean="",
            recommendation="",
        )
        return hits.get("ou_hit")

    if market_key == "btts":
        hits = evaluate_prediction_vs_score(
            home_goals=home_goals,
            away_goals=away_goals,
            score_hint="",
            goal_lean="",
            both_score_lean=lean_text,
            recommendation="",
        )
        return hits.get("btts_hit")

    return None


def evaluate_fixture_prediction(
    fixture: Fixture,
    stored: PreMatchData | None,
    *,
    auto_pick: Any | None = None,
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
        "auto_pick_hit": None,
        "auto_pick_market": None,
        "auto_pick_lean": None,
        "quality_rating": None,
        # Unsettled rows (feed still live) carry provisional scores — show, never grade.
        "evaluable": fixture_ready_to_grade(fixture),
    }

    def _attach_auto_pick(*, grade: bool) -> None:
        if auto_pick is None:
            return
        payload["auto_pick_market"] = auto_pick.market
        payload["auto_pick_lean"] = auto_pick.lean
        rating = getattr(auto_pick, "quality_rating", None)
        try:
            rating_f = float(rating) if rating is not None else None
        except (TypeError, ValueError):
            rating_f = None
        payload["quality_rating"] = rating_f if rating_f and rating_f > 0 else None
        if not grade:
            return
        ah_line = None
        if auto_pick.market == "ah":
            ah_line = handicap_line_from_lean(auto_pick.lean)
        payload["auto_pick_hit"] = settle_auto_pick_hit(
            market=auto_pick.market,
            lean=auto_pick.lean,
            home_goals=fixture.home_goals,
            away_goals=fixture.away_goals,
            handicap_line=ah_line,
        )

    if (
        stored is None
        or None in (stored.home_win_prob, stored.draw_prob, stored.away_win_prob)
    ):
        _attach_auto_pick(grade=payload["evaluable"])
        return payload

    # Audit uses only the frozen exam snapshot — never recompute with today's algorithm.
    recommendation = (getattr(stored, "recommendation", None) or "").strip()
    score_hint = (getattr(stored, "score_hint", None) or "").strip()
    goal_lean = (getattr(stored, "goal_lean", None) or "").strip()
    both_score_lean = (getattr(stored, "both_score_lean", None) or "").strip()
    handicap_lean = (getattr(stored, "handicap_lean", None) or "").strip()
    if not recommendation or recommendation == "待分析":
        _attach_auto_pick(grade=payload["evaluable"])
        return payload
    if not score_hint or score_hint == "待分析":
        # Older rows may lack score_hint; still count 1X2 / O/U / BTTS if present.
        score_hint = ""

    package = package_from_record(stored)
    odds = package.get("odds") if isinstance(package, dict) else None
    line_f, _, _ = extract_main_ah_line(odds if isinstance(odds, dict) else None)
    if line_f is None:
        line_f = handicap_line_from_lean(handicap_lean)

    payload.update(
        {
            "has_prediction": True,
            "recommendation": canonical_recommendation(recommendation),
            "score_hint": canonical_score_hint(score_hint) or None,
            "goal_lean": canonical_goal_lean(goal_lean) or None,
            "both_score_lean": canonical_btts_lean(both_score_lean) or None,
            "handicap_lean": display_handicap_lean(handicap_lean, line_f),
        }
    )
    if not payload["evaluable"]:
        _attach_auto_pick(grade=False)
        return payload

    handicap_result = settle_handicap_result(
        fixture.home_goals,
        fixture.away_goals,
        line_f,
    )
    predicted_handicaps = handicap_picks_from_lean(handicap_lean)
    payload["handicap_result"] = handicap_result
    if handicap_result is not None and predicted_handicaps:
        payload["handicap_hit"] = handicap_result in predicted_handicaps

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

    if auto_pick is not None:
        payload["auto_pick_market"] = auto_pick.market
        payload["auto_pick_lean"] = auto_pick.lean
        ah_line = line_f
        if auto_pick.market == "ah":
            ah_line = handicap_line_from_lean(auto_pick.lean) or line_f
        payload["auto_pick_hit"] = settle_auto_pick_hit(
            market=auto_pick.market,
            lean=auto_pick.lean,
            home_goals=fixture.home_goals,
            away_goals=fixture.away_goals,
            handicap_line=ah_line,
        )
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


async def load_auto_picks_by_fixture_ids(
    db: AsyncSession,
    fixture_ids: list[int],
) -> dict[int, AutoPickSnapshot]:
    if not fixture_ids:
        return {}
    rows = (
        await db.execute(
            select(AutoPickSnapshot).where(AutoPickSnapshot.fixture_id.in_(fixture_ids))
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
    fixture_ids = [f.id for f in fixtures]
    stored_by_id = await load_stored_by_fixture_ids(db, fixture_ids)
    auto_by_id = await load_auto_picks_by_fixture_ids(db, fixture_ids)

    overall_rows: list[dict[str, Any]] = []
    by_day: dict[str, list[dict[str, Any]]] = {}

    for fx in fixtures:
        evaluated = evaluate_fixture_prediction(
            fx,
            stored_by_id.get(fx.id),
            auto_pick=auto_by_id.get(fx.id),
        )
        row = {
            "has_prediction": evaluated["has_prediction"],
            "evaluable": evaluated["evaluable"],
            "result_hit": evaluated["result_hit"] if evaluated["has_prediction"] else None,
            "auto_pick_hit": evaluated["auto_pick_hit"],
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

    # Chart series: only days that actually have prediction / auto-pick samples.
    # Do not pad empty calendar days back to the lookback window start.
    series: list[dict[str, Any]] = []
    for key in sorted(by_day.keys()):
        day_summary = summarize_accuracy(by_day[key])
        if (
            day_summary["fixtures_with_prediction"] <= 0
            and day_summary["auto_pick"]["total"] <= 0
        ):
            continue
        series.append(
            {
                "date": key,
                "result": day_summary["result"],
                "auto_pick": day_summary["auto_pick"],
                "score": day_summary["score"],
                "ou": day_summary["ou"],
                "btts": day_summary["btts"],
                "handicap": day_summary["handicap"],
                "fixtures_with_prediction": day_summary["fixtures_with_prediction"],
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
