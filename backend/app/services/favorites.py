"""Single-tenant favorite fixtures CRUD + list hydration from local DB."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.favorite_fixture import FavoriteFixture
from app.models.fixture import Fixture
from app.models.pre_match_data import PreMatchData
from app.schemas.response import FavoriteFixtureResponse


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _to_favorite_response(
    fav: FavoriteFixture,
    fixture: Fixture,
    stored: PreMatchData | None,
) -> FavoriteFixtureResponse:
    # Import list mappers lazily to avoid circular imports at module load.
    from app.api.v1.endpoints.fixtures import (
        _league_country,
        _league_name,
        _list_analysis_from_fixture,
        _list_extras_from_stored,
        _team_display_name,
    )

    analysis = _list_analysis_from_fixture(fixture, stored)
    _, _, odds_snippet = _list_extras_from_stored(stored)
    probs = analysis.probabilities
    ready = bool(probs.available)
    rec = (analysis.recommendation or "").strip()
    has_prediction = ready or (bool(rec) and rec != "待分析")

    return FavoriteFixtureResponse(
        fixture_id=fixture.id,
        home_team_name=_team_display_name(
            fixture.home_team.name if fixture.home_team else None,
            fixture.home_team_id,
        ),
        away_team_name=_team_display_name(
            fixture.away_team.name if fixture.away_team else None,
            fixture.away_team_id,
        ),
        league_id=fixture.league_id,
        league_name=_league_name(fixture),
        league_country=_league_country(fixture),
        fixture_date=fixture.date,
        status=fixture.status,
        home_goals=fixture.home_goals,
        away_goals=fixture.away_goals,
        saved_at=fav.saved_at,
        has_prediction=has_prediction,
        recommendation=analysis.recommendation if has_prediction else None,
        handicap_lean=analysis.handicap_lean or None,
        score_hint=analysis.score_hint if has_prediction else None,
        goal_lean=analysis.goal_lean if has_prediction else None,
        both_score_lean=analysis.both_score_lean if has_prediction else None,
        probabilities_available=ready,
        home_win_prob=probs.home_win_prob if ready else None,
        draw_prob=probs.draw_prob if ready else None,
        away_win_prob=probs.away_win_prob if ready else None,
        odds_snippet=odds_snippet,
    )


async def _load_fixtures_map(
    db: AsyncSession,
    fixture_ids: list[int],
) -> dict[int, Fixture]:
    if not fixture_ids:
        return {}
    stmt = (
        select(Fixture)
        .where(Fixture.id.in_(fixture_ids))
        .options(
            selectinload(Fixture.home_team),
            selectinload(Fixture.away_team),
            selectinload(Fixture.league),
        )
    )
    rows = (await db.execute(stmt)).scalars().all()
    return {row.id: row for row in rows}


async def _load_prematch_map(
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


async def list_favorite_responses(db: AsyncSession) -> list[FavoriteFixtureResponse]:
    fav_rows = (
        await db.execute(
            select(FavoriteFixture).order_by(FavoriteFixture.saved_at.desc())
        )
    ).scalars().all()
    if not fav_rows:
        return []

    ids = [row.fixture_id for row in fav_rows]
    fixtures = await _load_fixtures_map(db, ids)
    stored = await _load_prematch_map(db, ids)

    out: list[FavoriteFixtureResponse] = []
    for fav in fav_rows:
        fixture = fixtures.get(fav.fixture_id)
        if fixture is None:
            continue
        out.append(_to_favorite_response(fav, fixture, stored.get(fav.fixture_id)))
    return out


async def get_favorite_response(
    db: AsyncSession,
    fixture_id: int,
) -> FavoriteFixtureResponse | None:
    fav = await db.get(FavoriteFixture, fixture_id)
    if fav is None:
        return None
    fixtures = await _load_fixtures_map(db, [fixture_id])
    fixture = fixtures.get(fixture_id)
    if fixture is None:
        return None
    stored = await _load_prematch_map(db, [fixture_id])
    return _to_favorite_response(fav, fixture, stored.get(fixture_id))


async def add_favorite(db: AsyncSession, fixture_id: int) -> FavoriteFixtureResponse:
    fixture = await db.get(Fixture, fixture_id)
    if fixture is None:
        raise LookupError(f"fixture {fixture_id} not found")

    fav = await db.get(FavoriteFixture, fixture_id)
    now = _utc_now()
    if fav is None:
        fav = FavoriteFixture(fixture_id=fixture_id, saved_at=now)
        db.add(fav)
    else:
        fav.saved_at = now
    await db.commit()

    response = await get_favorite_response(db, fixture_id)
    if response is None:
        raise RuntimeError(f"favorite {fixture_id} missing after commit")
    return response


async def remove_favorite(db: AsyncSession, fixture_id: int) -> bool:
    fav = await db.get(FavoriteFixture, fixture_id)
    if fav is None:
        return False
    await db.delete(fav)
    await db.commit()
    return True
