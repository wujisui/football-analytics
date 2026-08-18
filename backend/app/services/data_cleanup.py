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
    fixture_score_cache_key,
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


_PLACEHOLDER_MARKERS = ("待分析", "缺少盘口")


def _is_real_prediction_text(text: str | None) -> bool:
    """True for a frozen lean/recommendation that is not an empty placeholder."""
    value = (text or "").strip()
    if not value:
        return False
    return not any(marker in value for marker in _PLACEHOLDER_MARKERS)


def record_has_algorithm_recommendation(
    stored: PreMatchData | None,
    feature: MatchFeature | None = None,
) -> bool:
    """Whether a real frozen algorithm prediction exists.

    Flat 1/3·1/3·1/3 probabilities and ``待分析`` / ``缺少盘口`` placeholders do
    **not** count. Keep terminal fixtures only when a concrete recommendation or
    lean was frozen (or when ``record_has_prematch_1x2`` already keeps them).
    ``feature`` is accepted for call-site compatibility; probs-only MatchFeature
    rows are not enough without odds.
    """
    _ = feature
    if stored is None:
        return False
    if _is_real_prediction_text(stored.recommendation):
        return True
    return any(
        _is_real_prediction_text(getattr(stored, field, None))
        for field in (
            "score_hint",
            "goal_lean",
            "both_score_lean",
            "handicap_lean",
        )
    )


def should_prune_terminal_fixture(
    fixture: Fixture,
    stored: PreMatchData | None,
    feature: MatchFeature | None,
) -> bool:
    """Delete finished-like rows with neither 1X2 nor a real algorithm prediction."""
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
            fixture_score_cache_key,
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


@dataclass(frozen=True)
class ResetMatchHistoryReport:
    """Counts for wiping match/ML history while keeping accounts & catalog."""

    apply: bool
    fixtures: int
    pre_match_data: int
    match_features: int
    auto_pick_snapshots: int
    favorite_fixtures: int
    league_standings: int
    api_snapshots: int
    incentive_settings_cleared: int
    model_files_removed: int
    cache_cleared: bool
    kept: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


_RESET_MATCH_HISTORY_KEPT = (
    "users",
    "user_sessions",
    "bet_plans",
    "app_settings (except auto_pick_incentive_state)",
    "leagues",
    "teams",
)


async def reset_match_history(
    session: AsyncSession,
    *,
    apply: bool,
    clear_cache: bool = True,
    remove_model_artifacts: bool = True,
) -> ResetMatchHistoryReport:
    """Wipe fixtures / odds / features / picks so ML can restart on new boards.

    Keeps user accounts, sessions, bet plans, admin toggles, and league/team
    catalog rows. Favorites are removed because they FK to fixtures.
    """
    from app.core.config import BACKEND_ROOT
    from app.models.app_setting import AppSetting
    from app.models.auto_pick_snapshot import AutoPickSnapshot
    from app.models.league_standing import LeagueStanding
    from app.services.auto_pick_incentive import KEY_INCENTIVE_STATE

    async def _count(model: type) -> int:
        from sqlalchemy import func

        return int(await session.scalar(select(func.count()).select_from(model)) or 0)

    fixtures = await _count(Fixture)
    pre_match = await _count(PreMatchData)
    features = await _count(MatchFeature)
    auto_picks = await _count(AutoPickSnapshot)
    favorites = await _count(FavoriteFixture)
    standings = await _count(LeagueStanding)
    snapshots = await _count(ApiSnapshot)
    incentive_row = (
        await session.execute(
            select(AppSetting).where(AppSetting.key == KEY_INCENTIVE_STATE)
        )
    ).scalar_one_or_none()
    incentive_count = 1 if incentive_row is not None else 0

    model_dir = BACKEND_ROOT / "data" / "models"
    model_files = (
        [p for p in model_dir.iterdir() if p.is_file()] if model_dir.is_dir() else []
    )

    if not apply:
        return ResetMatchHistoryReport(
            apply=False,
            fixtures=fixtures,
            pre_match_data=pre_match,
            match_features=features,
            auto_pick_snapshots=auto_picks,
            favorite_fixtures=favorites,
            league_standings=standings,
            api_snapshots=snapshots,
            incentive_settings_cleared=incentive_count,
            model_files_removed=len(model_files) if remove_model_artifacts else 0,
            cache_cleared=False,
            kept=_RESET_MATCH_HISTORY_KEPT,
        )

    # Children first for explicit counts; fixtures CASCADE would also work.
    await session.execute(delete(FavoriteFixture))
    await session.execute(delete(AutoPickSnapshot))
    await session.execute(delete(MatchFeature))
    await session.execute(delete(PreMatchData))
    await session.execute(delete(Fixture))
    await session.execute(delete(LeagueStanding))
    await session.execute(delete(ApiSnapshot))
    if incentive_row is not None:
        await session.delete(incentive_row)
    await session.commit()

    removed_models = 0
    if remove_model_artifacts:
        for path in model_files:
            try:
                path.unlink()
                removed_models += 1
            except OSError:
                pass

    cache_cleared = False
    if clear_cache:
        cache = get_cache_service()
        await cache.clear_pattern("api:football:*")
        cache_cleared = True

    return ResetMatchHistoryReport(
        apply=True,
        fixtures=fixtures,
        pre_match_data=pre_match,
        match_features=features,
        auto_pick_snapshots=auto_picks,
        favorite_fixtures=favorites,
        league_standings=standings,
        api_snapshots=snapshots,
        incentive_settings_cleared=incentive_count,
        model_files_removed=removed_models,
        cache_cleared=cache_cleared,
        kept=_RESET_MATCH_HISTORY_KEPT,
    )
