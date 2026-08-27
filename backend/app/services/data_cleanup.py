"""Physical pruning for finished fixtures that never became analysis-worthy."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

from sqlalchemy import and_, delete, or_, select, union, update
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
from app.services.league_catalog import allowed_league_ids
from app.services.features import has_match_winner_odds
from app.services.prematch_package import loads_json, rehydrate_odds_markets
from app.services.results_capture import (
    POSTPONED_HIDE_AFTER_DAYS,
    RESULTS_BROWSABLE_DAYS,
)

# Statuses whose packages may be slimmed: the match is over as far as we know.
TERMINAL_STATUSES = ("finished", "cancelled", "postponed")
# Pending / live rows still count as prunable candidates because a status that
# never advanced past kickoff means the score was never written back; such rows
# are invisible in【比赛】yet unscoreable in【赛果】. Fixtures before kickoff are
# still protected inside :func:`never_settles` — odds often open late.
PRUNABLE_STATUSES = TERMINAL_STATUSES + ("pending", "live")
DELETE_CHUNK_SIZE = 500

# Display-only sections of a pre-match package; safe to drop once a match is old.
EXPIRED_PACKAGE_COLUMNS = (
    PreMatchData.lineups_json,
    PreMatchData.injuries_json,
    PreMatchData.h2h_json,
    PreMatchData.home_form_json,
    PreMatchData.away_form_json,
    PreMatchData.standings_json,
    PreMatchData.briefing_json,
    PreMatchData.injuries_home,
    PreMatchData.injuries_away,
)


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


def never_settles(fixture: Fixture, *, now: datetime | None = None) -> bool:
    """True when no full-time score can ever grade this fixture.

    Cancelled rows and 「finished」 rows without a score never settle, so 赛果统计
    and ML labels can never use them no matter how complete their pre-match data
    is. Postponed / pending / live rows are spared until their kickoff goes stale:
    until then the product still lists them as an upcoming match, and the score
    may still arrive. Once stale without a score, 官方 will not backfill them.
    """
    if fixture.status == "finished":
        return fixture.home_goals is None or fixture.away_goals is None
    if fixture.status == "cancelled":
        return True
    current = now or datetime.utcnow()
    if fixture.date > current - timedelta(days=POSTPONED_HIDE_AFTER_DAYS):
        return False
    return fixture.home_goals is None or fixture.away_goals is None


def should_prune_fixture(
    fixture: Fixture,
    stored: PreMatchData | None,
    feature: MatchFeature | None,
    *,
    now: datetime | None = None,
) -> bool:
    """Delete rows that 赛果统计 / ML can never score.

    Two cases: the match never settles at all, or it settled without a pre-match
    1X2 board. 缺盘口的场次即使库里冻结过预测也删——没有盘口就没有推断依据，
    这种预测属于无效数据，留着只会污染准确率与训练标签。

    但「完场缺盘口」要等【赛程】日期条选不到那天之后再删：准确率与 ML 本来就只
    收有命中标记的场次，多留几天不影响；立刻删则会让后端漏跑期间的比赛日在赛果
    页永久空白——赛果回填走全球按日接口，只带比分不带盘口，删掉后每次同步都重新
    拉一遍再被删，白耗官方配额。
    """
    if fixture.status not in PRUNABLE_STATUSES:
        return False
    if never_settles(fixture, now=now):
        return True
    if fixture.status != "finished":
        # 未结算且尚未陈旧（含未开赛与刚延期）：盘口可能稍后才开，必须保留。
        return False
    if record_has_prematch_1x2(stored, feature):
        return False
    current = now or datetime.utcnow()
    return fixture.date <= current - timedelta(days=RESULTS_BROWSABLE_DAYS)


async def _delete_ids(
    session: AsyncSession,
    model,
    column,
    ids: set[int] | set[str],
) -> int:
    """Chunked ``DELETE ... IN (...)``; SQLite caps bind params per statement."""
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
    """Delete fixtures 赛果统计 / ML can never score.

    Covers matches that never settle (cancelled, score-less, or stuck at
    postponed / pending / live past a stale kickoff) plus settled ones that never
    got a pre-match 1X2 board. Upcoming fixtures outside the competition whitelist
    are removed immediately; in-scope fixtures before kickoff are never touched.
    Empty ``leagues`` rows (no fixtures left) may be removed after fixture prune.
    """
    now = datetime.utcnow()
    competition_ids = await allowed_league_ids(session)
    rows = (
        await session.execute(
            select(Fixture, PreMatchData, MatchFeature)
            .outerjoin(PreMatchData, PreMatchData.fixture_id == Fixture.id)
            .outerjoin(MatchFeature, MatchFeature.fixture_id == Fixture.id)
            .where(
                or_(
                    Fixture.status.in_(PRUNABLE_STATUSES),
                    and_(
                        Fixture.date > now,
                        Fixture.league_id.not_in(competition_ids),
                    ),
                )
            )
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
            keep_feature is None or _feature_has_1x2(feature)
        ):
            keep_feature = feature
        by_fixture[fixture.id] = (fixture, keep_stored, keep_feature)

    removed_fixture_ids: set[int] = set()
    removed_dates: set[str] = set()
    for fixture_id, (fixture, stored, feature) in by_fixture.items():
        out_of_scope_upcoming = (
            fixture.date > now and fixture.league_id not in competition_ids
        )
        if out_of_scope_upcoming or should_prune_fixture(
            fixture, stored, feature, now=now
        ):
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
    disposable_league_ids = {
        int(lid)
        for (lid,) in (
            await session.execute(
                select(League.id).where(League.is_catalog.is_(False))
            )
        ).all()
    }
    empty_league_ids = disposable_league_ids - remaining_league_ids
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
    snapshots_deleted = await _delete_ids(
        session, ApiSnapshot, ApiSnapshot.cache_key, snapshot_keys
    )

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


async def slim_expired_packages(
    session: AsyncSession,
    *,
    cutoff: datetime,
) -> int:
    """Drop the heavy display sections of packages older than ``cutoff``.

    Prediction, probability and odds columns stay: they are the frozen exam
    赛果统计 grades against. Deleting whole rows used to erase that exam with the
    display JSON, which quietly shrank the historical sample to the retention
    window even though the fixtures were still there.
    """
    fixture_ids = {
        int(fixture_id)
        for (fixture_id,) in (
            await session.execute(
                select(Fixture.id).where(
                    Fixture.date < cutoff,
                    Fixture.status.in_(TERMINAL_STATUSES),
                )
            )
        ).all()
    }
    if not fixture_ids:
        return 0

    slimmed = 0
    ordered = sorted(fixture_ids)
    for start in range(0, len(ordered), DELETE_CHUNK_SIZE):
        chunk = ordered[start : start + DELETE_CHUNK_SIZE]
        result = await session.execute(
            update(PreMatchData)
            .where(
                PreMatchData.fixture_id.in_(chunk),
                or_(*(column.is_not(None) for column in EXPIRED_PACKAGE_COLUMNS)),
            )
            .values({column: None for column in EXPIRED_PACKAGE_COLUMNS})
        )
        slimmed += int(result.rowcount or 0)
    await session.commit()
    return slimmed


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


@dataclass(frozen=True)
class DeleteLeagueReport:
    apply: bool
    league_id: int
    league_name: str
    fixtures: int
    pre_match_data: int
    match_features: int
    auto_pick_snapshots: int
    favorite_fixtures: int
    league_standings: int
    api_snapshots: int
    orphan_teams: int

    def to_dict(self) -> dict:
        return asdict(self)


async def delete_catalog_league(
    session: AsyncSession,
    league_id: int,
    *,
    apply: bool,
) -> DeleteLeagueReport:
    """Preview or delete one unprotected catalog league and all match history."""
    from sqlalchemy import func

    from app.models.auto_pick_snapshot import AutoPickSnapshot
    from app.models.league import LeagueCatalogTombstone
    from app.models.league_standing import LeagueStanding

    league = await session.get(League, int(league_id))
    if league is None or not league.is_catalog:
        raise ValueError("联赛不在可管理目录中")
    if league.is_protected:
        raise PermissionError("系统保护联赛不可删除")

    fixture_rows = (
        await session.execute(
            select(
                Fixture.id,
                Fixture.match_day,
                Fixture.date,
                Fixture.home_team_id,
                Fixture.away_team_id,
            ).where(Fixture.league_id == league.id)
        )
    ).all()
    fixture_ids = {int(row.id) for row in fixture_rows}
    match_days = {
        str(row.match_day or row.date.date().isoformat()) for row in fixture_rows
    }
    candidate_team_ids = {
        int(team_id)
        for row in fixture_rows
        for team_id in (row.home_team_id, row.away_team_id)
    }
    externally_referenced_team_ids: set[int] = set()
    if candidate_team_ids:
        external_refs = union(
            select(Fixture.home_team_id).where(
                Fixture.league_id != league.id,
                Fixture.home_team_id.in_(candidate_team_ids),
            ),
            select(Fixture.away_team_id).where(
                Fixture.league_id != league.id,
                Fixture.away_team_id.in_(candidate_team_ids),
            ),
        )
        externally_referenced_team_ids = {
            int(value)
            for value in (await session.execute(external_refs)).scalars()
        }
    orphan_team_ids = candidate_team_ids - externally_referenced_team_ids
    orphan_preview = len(orphan_team_ids)

    async def _fixture_child_count(model: type) -> int:
        if not fixture_ids:
            return 0
        return int(
            await session.scalar(
                select(func.count())
                .select_from(model)
                .where(model.fixture_id.in_(fixture_ids))
            )
            or 0
        )

    snapshot_keys = {
        key
        for fixture_id in fixture_ids
        for key in (
            analysis_cache_key(fixture_id),
            fixture_score_cache_key(fixture_id),
            odds_cache_key(fixture_id),
            lineups_cache_key(fixture_id),
            injuries_cache_key(fixture_id),
            predictions_cache_key(fixture_id),
        )
    }
    snapshot_keys.update(
        key_builder(day)
        for day in match_days
        for key_builder in (fixtures_cache_key, fixtures_day_leagues_cache_key)
    )
    snapshot_pattern_filters = [
        ApiSnapshot.cache_key.like(f"%league:{league.id}:%"),
    ]
    for team_id in orphan_team_ids:
        snapshot_pattern_filters.extend(
            (
                ApiSnapshot.cache_key.like(f"%team:{team_id}:%"),
                ApiSnapshot.cache_key.like(f"%h2h:{team_id}:%"),
                ApiSnapshot.cache_key.like(f"%h2h:%:{team_id}:%"),
            )
        )
    exact_snapshot_count = 0
    ordered_snapshot_keys = sorted(snapshot_keys)
    for start in range(0, len(ordered_snapshot_keys), DELETE_CHUNK_SIZE):
        chunk = ordered_snapshot_keys[start : start + DELETE_CHUNK_SIZE]
        exact_snapshot_count += int(
            await session.scalar(
                select(func.count())
                .select_from(ApiSnapshot)
                .where(ApiSnapshot.cache_key.in_(chunk))
            )
            or 0
        )
    pattern_snapshot_count = int(
        await session.scalar(
            select(func.count())
            .select_from(ApiSnapshot)
            .where(or_(*snapshot_pattern_filters))
        )
        or 0
    )
    snapshot_count = exact_snapshot_count + pattern_snapshot_count

    report = DeleteLeagueReport(
        apply=apply,
        league_id=int(league.id),
        league_name=league.name,
        fixtures=len(fixture_ids),
        pre_match_data=await _fixture_child_count(PreMatchData),
        match_features=await _fixture_child_count(MatchFeature),
        auto_pick_snapshots=await _fixture_child_count(AutoPickSnapshot),
        favorite_fixtures=await _fixture_child_count(FavoriteFixture),
        league_standings=int(
            await session.scalar(
                select(func.count())
                .select_from(LeagueStanding)
                .where(LeagueStanding.league_id == league.id)
            )
            or 0
        ),
        api_snapshots=snapshot_count,
        orphan_teams=orphan_preview,
    )
    if not apply:
        return report

    await _delete_ids(
        session, ApiSnapshot, ApiSnapshot.cache_key, snapshot_keys
    )
    await session.execute(
        delete(ApiSnapshot).where(or_(*snapshot_pattern_filters))
    )
    await session.execute(delete(League).where(League.id == league_id))
    session.add(LeagueCatalogTombstone(league_id=int(league_id)))
    await session.flush()

    orphan_result = await session.execute(
        delete(Team).where(Team.id.in_(orphan_team_ids))
    )
    orphan_teams = int(orphan_result.rowcount or 0)
    await session.commit()

    cache = get_cache_service()
    await cache.clear_pattern(f"*league:{league_id}:*")
    for team_id in orphan_team_ids:
        await cache.clear_pattern(f"*team:{team_id}:*")
        await cache.clear_pattern(f"*h2h:{team_id}:*")
        await cache.clear_pattern(f"*h2h:*:{team_id}:*")
    for key in snapshot_keys:
        await cache.delete(key)

    return DeleteLeagueReport(**{**report.to_dict(), "orphan_teams": orphan_teams})


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
