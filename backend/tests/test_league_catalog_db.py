import asyncio
import unittest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.fixture import Fixture
from app.models.league import League, LeagueCategory, LeagueCatalogTombstone
from app.models.team import Team
from app.services.data_cleanup import delete_catalog_league
from app.services.fetcher import FootballFetcher
from app.services.league_catalog import (
    allowed_league_ids,
    retarget_catalog_league_id,
    seed_league_catalog,
)


def _sqlite_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def _foreign_keys_on(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


class LeagueCatalogDatabaseTests(unittest.TestCase):
    def test_fixture_persist_uses_database_admission_function(self) -> None:
        async def run() -> None:
            session = AsyncMock()
            cache = MagicMock(last_data_update=None)
            fetcher = FootballFetcher(session=session, cache=cache)
            with patch(
                "app.services.fetcher.catalog_allowed_league_ids",
                AsyncMock(return_value={48}),
            ) as allowed:
                saved = await fetcher._persist_fixtures([], fetch_teams=False)
            self.assertEqual(saved, 0)
            allowed.assert_awaited_once_with(session)

        asyncio.run(run())

    def test_seed_protects_existing_catalog(self) -> None:
        async def run() -> None:
            engine = _sqlite_engine()
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as session:
                await seed_league_catalog(session)
                premier_league = await session.get(League, 39)
                self.assertIsNotNone(premier_league)
                assert premier_league is not None
                self.assertTrue(premier_league.is_catalog)
                self.assertTrue(premier_league.is_protected)
                self.assertEqual(premier_league.category_id, 1)
                self.assertIsNotNone(await session.get(LeagueCategory, 8))
            await engine.dispose()

        asyncio.run(run())

    def test_unprotected_league_can_be_deleted_and_readded_later(self) -> None:
        async def run() -> None:
            engine = _sqlite_engine()
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as session:
                session.add(LeagueCategory(id=8, name="各国杯赛", sort_order=80))
                session.add(
                    League(
                        id=48,
                        name="英联杯",
                        country="England",
                        season="2026",
                        category_id=8,
                        is_catalog=True,
                        is_hot=True,
                        is_protected=False,
                    )
                )
                session.add_all((Team(id=1, name="A"), Team(id=2, name="B")))
                await session.flush()
                session.add(
                    Fixture(
                        id=48001,
                        league_id=48,
                        home_team_id=1,
                        away_team_id=2,
                        date=datetime(2026, 8, 26, 12),
                    )
                )
                await session.commit()

                preview = await delete_catalog_league(session, 48, apply=False)
                self.assertEqual(preview.fixtures, 1)
                fake_cache = MagicMock(
                    clear_pattern=AsyncMock(return_value=0),
                    delete=AsyncMock(return_value=None),
                )
                with patch(
                    "app.services.data_cleanup.get_cache_service",
                    return_value=fake_cache,
                ):
                    applied = await delete_catalog_league(session, 48, apply=True)
                self.assertTrue(applied.apply)
                self.assertIsNone(await session.get(League, 48))
                self.assertIsNone(await session.get(Fixture, 48001))
                self.assertIsNotNone(await session.get(LeagueCatalogTombstone, 48))
                self.assertNotIn(48, await allowed_league_ids(session))
            await engine.dispose()

        asyncio.run(run())

    def test_protected_league_delete_is_rejected(self) -> None:
        async def run() -> None:
            engine = _sqlite_engine()
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as session:
                session.add(
                    League(
                        id=39,
                        name="英超",
                        country="England",
                        season="2026",
                        is_catalog=True,
                        is_hot=True,
                        is_protected=True,
                    )
                )
                await session.commit()
                with self.assertRaises(PermissionError):
                    await delete_catalog_league(session, 39, apply=False)
            await engine.dispose()

        asyncio.run(run())

    def test_catalog_league_name_and_country_can_be_updated(self) -> None:
        async def run() -> None:
            from app.api.v1.endpoints.admin import CatalogLeagueUpdate, update_catalog_league

            engine = _sqlite_engine()
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as session:
                session.add(LeagueCategory(id=8, name="各国杯赛", sort_order=80))
                session.add(LeagueCategory(id=1, name="五大联赛", sort_order=10))
                session.add(
                    League(
                        id=48,
                        name="英联杯",
                        country="England",
                        season="2026",
                        category_id=8,
                        is_catalog=True,
                        is_hot=True,
                        is_protected=False,
                    )
                )
                await session.commit()
                await update_catalog_league(
                    48,
                    CatalogLeagueUpdate(
                        league_name="英格兰联赛杯",
                        country="England",
                        category_id=1,
                    ),
                    None,
                    session,
                )
                league = await session.get(League, 48)
                self.assertIsNotNone(league)
                assert league is not None
                self.assertEqual(league.name, "英格兰联赛杯")
                self.assertEqual(league.country, "England")
                self.assertEqual(league.category_id, 1)
            await engine.dispose()

        asyncio.run(run())

    def test_unprotected_league_id_can_be_corrected(self) -> None:
        async def run() -> None:
            engine = _sqlite_engine()
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as session:
                session.add(LeagueCategory(id=8, name="各国杯赛", sort_order=80))
                session.add(
                    League(
                        id=48,
                        name="英联杯",
                        country="England",
                        season="2026",
                        category_id=8,
                        is_catalog=True,
                        is_hot=True,
                        is_protected=False,
                    )
                )
                session.add_all((Team(id=1, name="A"), Team(id=2, name="B")))
                await session.flush()
                session.add(
                    Fixture(
                        id=48001,
                        league_id=48,
                        home_team_id=1,
                        away_team_id=2,
                        date=datetime(2026, 8, 26, 12),
                    )
                )
                await session.commit()
                source = await session.get(League, 48)
                assert source is not None
                moved = await retarget_catalog_league_id(session, source, 46)
                await session.commit()
                self.assertEqual(moved.id, 46)
                self.assertIsNone(await session.get(League, 48))
                self.assertIsNone(await session.get(Fixture, 48001))
                target = await session.get(League, 46)
                self.assertIsNotNone(target)
                assert target is not None
                self.assertTrue(target.is_catalog)
                self.assertEqual(target.name, "英联杯")
                self.assertIsNotNone(await session.get(LeagueCatalogTombstone, 48))
                self.assertNotIn(48, await allowed_league_ids(session))
                self.assertIn(46, await allowed_league_ids(session))
            await engine.dispose()

        asyncio.run(run())

    def test_protected_league_id_cannot_change(self) -> None:
        async def run() -> None:
            engine = _sqlite_engine()
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as session:
                session.add(
                    League(
                        id=39,
                        name="英超",
                        country="England",
                        season="2026",
                        is_catalog=True,
                        is_hot=True,
                        is_protected=True,
                    )
                )
                await session.commit()
                premier = await session.get(League, 39)
                assert premier is not None
                with self.assertRaises(PermissionError):
                    await retarget_catalog_league_id(session, premier, 40)
            await engine.dispose()

        asyncio.run(run())
