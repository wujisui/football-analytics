"""Physical pruning for finished fixtures that never became analysis-worthy."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from sqlalchemy import delete, select, union
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_snapshot import ApiSnapshot
from app.models.favorite_fixture import FavoriteFixture
from app.models.fixture import Fixture
from app.models.league import League
from app.models.match_feature import MatchFeature
from app.models.pre_match_data import PreMatchData
from app.models.team import Team
from app.services.cache import (
    analysis_cache_key,
    fixture_cache_key,
    fixtures_cache_key,
    fixtures_day_leagues_cache_key,
    get_cache_service,
    injuries_cache_key,
    lineups_cache_key,
    odds_cache_key,
    predictions_cache_key,
)
from app.services.features import has_match_winner_odds
from app.services.prematch_package import loads_json, rehydrate_odds_markets

# Only terminal fixtures may be pruned. Pending / live always stay — odds may
# open later, and schedule data must not be thrown away before kickoff.
TERMINAL_STATUSES = ("finished", "cancelled", "postponed")
DELETE_CHUNK_SIZE = 500


@dataclass(frozen=True)
class PruneReport:
    apply: bool
    fixtures_without_value: int
    empty_leagues_deleted: int
    league_ids: list[int]
    fixtures_deleted: int
    favorites_deleted: int
    features_deleted: int
    prematch_deleted: int
    snapshots_deleted: int
    orphan_teams_deleted: int

    def to_dict(self) -> dict:
        return asdict(self)


def _stored_has_1x2(stored: PreMatchData | None) -> bool:
    if stored is None:
        return False
    for raw in (stored.odds_json, stored.odds_opening_json):
        odds = rehydrate_odds_markets(loads_json(raw, {"available": False}))
        if has_match_winner_odds(odds):
            return True
    return False


def _feature_has_1x2(feature: MatchFeature | None) -> bool:
    if feature is None:
        return False
    try:
        payload = json.loads(feature.features_json or "{}")
        return float(payload.get("has_odds", 0.0)) > 0
    except (TypeError, ValueError, json.JSONDecodeError):
        return False


def record_has_prematch_1x2(
    stored: PreMatchData | None,
    feature: MatchFeature | None,
) -> bool:
    """Whether a fixture has a usable stored pre-match 1X2 board."""
    return _stored_has_1x2(stored) or _feature_has_1x2(feature)


def record_has_algorithm_recommendation(
    stored: PreMatchData | None,
    feature: MatchFeature | None,
) -> bool:
    """Whether a frozen algorithm recommendation / analysis snapshot exists."""
    if stored is not None:
        recommendation = (stored.recommendation or "").strip()
        if recommendation and recommendation != "待分析":
            return True
        if None not in (stored.home_win_prob, stored.draw_prob, stored.away_win_prob):
            return True
    if feature is not None and None not in (
        feature.home_win_prob,
        feature.draw_prob,
        feature.away_win_prob,
    ):
        return True
    return False


def should_prune_terminal_fixture(
    fixture: Fixture,
    stored: PreMatchData | None,
    feature: MatchFeature | None,
) -> bool:
    """Delete only finished-like rows with neither 1X2 nor algorithm recommendation."""
    if fixture.status not in TERMINAL_STATUSES:
        return False
    if record_has_prematch_1x2(stored, feature):
        return False
    if record_has_algorithm_recommendation(stored, feature):
        return False
    return True


async def _delete_ids(session: AsyncSession, model, column, ids: set[int]) -> int:
    deleted = 0
    ordered = sorted(ids)
    for start in range(0, len(ordered), DELETE_CHUNK_SIZE):
        chunk = ordered[start : start + DELETE_CHUNK_SIZE]
        result = await session.execute(delete(model).where(column.in_(chunk)))
        deleted += int(result.rowcount or 0)
    return deleted


async def prune_low_value_data(
    session: AsyncSession,
    *,
    apply: bool,
) -> PruneReport:
    """Delete terminal fixtures that never got 1X2 odds or an algorithm recommendation.

    Never deletes pending / live fixtures. Never wipes a league's upcoming schedule
    because some finished matches lacked odds — odds often open closer to kickoff.
    Empty ``leagues`` rows (no fixtures left) may be removed after fixture prune.
    """
    rows = (
        await session.execute(
            select(Fixture, PreMatchData, MatchFeature)
            .outerjoin(PreMatchData, PreMatchData.fixture_id == Fixture.id)
            .outerjoin(MatchFeature, MatchFeature.fixture_id == Fixture.id)
            .where(Fixture.status.in_(TERMINAL_STATUSES))
        )
    ).all()

    # MatchFeature can produce multiple rows per fixture; collapse to one decision.
    by_fixture: dict[int, tuple[Fixture, PreMatchData | None, MatchFeature | None]] = {}
    for fixture, stored, feature in rows:
        prev = by_fixture.get(fixture.id)
        if prev is None:
            by_fixture[fixture.id] = (fixture, stored, feature)
            continue
        _, prev_stored, prev_feature = prev
        keep_stored = prev_stored or stored
        keep_feature = prev_feature
        if feature is not None and (
            keep_feature is None
            or record_has_prematch_1x2(None, feature)
            or record_has_algorithm_recommendation(None, feature)
        ):
            keep_feature = feature
        by_fixture[fixture.id] = (fixture, keep_stored, keep_feature)

    removed_fixture_ids: set[int] = set()
    removed_dates: set[str] = set()
    for fixture_id, (fixture, stored, feature) in by_fixture.items():
        if should_prune_terminal_fixture(fixture, stored, feature):
            removed_fixture_ids.add(fixture_id)
            removed_dates.add(fixture.date.date().isoformat())

    if not apply:
        return PruneReport(
            apply=False,
            fixtures_without_value=len(removed_fixture_ids),
            empty_leagues_deleted=0,
            league_ids=[],
            fixtures_deleted=len(removed_fixture_ids),
            favorites_deleted=0,
            features_deleted=0,
            prematch_deleted=0,
            snapshots_deleted=0,
            orphan_teams_deleted=0,
        )

    favorites_deleted = await _delete_ids(
        session, FavoriteFixture, FavoriteFixture.fixture_id, removed_fixture_ids
    )
    features_deleted = await _delete_ids(
        session, MatchFeature, MatchFeature.fixture_id, removed_fixture_ids
    )
    prematch_deleted = await _delete_ids(
        session, PreMatchData, PreMatchData.fixture_id, removed_fixture_ids
    )
    fixtures_deleted = await _delete_ids(
        session, Fixture, Fixture.id, removed_fixture_ids
    )

    # Only remove league rows that now have zero fixtures (pending included).
    empty_league_ids: set[int] = set()
    remaining_league_ids = {
        int(lid)
        for (lid,) in (
            await session.execute(select(Fixture.league_id).distinct())
        ).all()
    }
    all_league_ids = {
        int(lid)
        for (lid,) in (await session.execute(select(League.id))).all()
    }
    empty_league_ids = all_league_ids - remaining_league_ids
    await _delete_ids(session, League, League.id, empty_league_ids)

    fixture_snapshot_keys = {
        key_builder(fixture_id)
        for fixture_id in removed_fixture_ids
        for key_builder in (
            fixture_cache_key,
            analysis_cache_key,
            odds_cache_key,
            lineups_cache_key,
            injuries_cache_key,
            predictions_cache_key,
        )
    }
    day_snapshot_keys = {
        key_builder(day)
        for day in removed_dates
        for key_builder in (fixtures_cache_key, fixtures_day_leagues_cache_key)
    }
    snapshot_keys = fixture_snapshot_keys | day_snapshot_keys
    snapshots_deleted = 0
    if snapshot_keys:
        result = await session.execute(
            delete(ApiSnapshot).where(ApiSnapshot.cache_key.in_(snapshot_keys))
        )
        snapshots_deleted = int(result.rowcount or 0)

    referenced_team_ids = union(
        select(Fixture.home_team_id),
        select(Fixture.away_team_id),
    )
    result = await session.execute(
        delete(Team).where(Team.id.not_in(referenced_team_ids))
    )
    orphan_teams_deleted = int(result.rowcount or 0)
    await session.commit()

    cache = get_cache_service()
    for key in snapshot_keys:
        await cache.delete(key)

    return PruneReport(
        apply=True,
        fixtures_without_value=len(removed_fixture_ids),
        empty_leagues_deleted=len(empty_league_ids),
        league_ids=sorted(empty_league_ids),
        fixtures_deleted=fixtures_deleted,
        favorites_deleted=favorites_deleted,
        features_deleted=features_deleted,
        prematch_deleted=prematch_deleted,
        snapshots_deleted=snapshots_deleted,
        orphan_teams_deleted=orphan_teams_deleted,
    )
