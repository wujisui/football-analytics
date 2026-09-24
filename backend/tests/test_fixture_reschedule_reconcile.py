"""官方把比赛挪到别的日子后，本地旧赛程行不能继续冒充未开赛场次。

真源 ``FootballFetcher._mark_fixtures_missing_from_day``：``date=`` 一次返回一整天，
没出现在里面的本地未开赛行就是被改期了。这类行永远等不到盘口——后续同步只会去
官方改到的那个新日期。
"""

import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.fixture import Fixture
from app.models.league import League
from app.models.team import Team
from app.services.fetcher import FootballFetcher


def _sqlite_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def _foreign_keys_on(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def _feed(*fixture_ids: int) -> list[dict]:
    return [{"id": fixture_id} for fixture_id in fixture_ids]


class RescheduleReconcileTests(unittest.TestCase):
    def test_only_missing_unstarted_rows_of_that_day_are_marked(self) -> None:
        async def run() -> None:
            engine = _sqlite_engine()
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as session:
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                day = (now + timedelta(hours=3)).date()
                session.add(
                    League(
                        id=10,
                        name="国际友谊赛",
                        country="World",
                        season=str(now.year),
                        is_catalog=True,
                        is_hot=True,
                        is_protected=False,
                    )
                )
                session.add_all((Team(id=1, name="A"), Team(id=2, name="B")))
                await session.flush()
                session.add_all(
                    (
                        # 仍在官方清单里 → 不动。
                        Fixture(
                            id=101,
                            league_id=10,
                            home_team_id=1,
                            away_team_id=2,
                            date=now + timedelta(hours=3),
                        ),
                        # 官方清单里没了、开赛仍在未来 → 改期。
                        Fixture(
                            id=102,
                            league_id=10,
                            home_team_id=1,
                            away_team_id=2,
                            date=now + timedelta(hours=4),
                        ),
                        # 同一天但已开赛：可能只是当天喂数据漏了，保留待结算。
                        Fixture(
                            id=103,
                            league_id=10,
                            home_team_id=1,
                            away_team_id=2,
                            date=now - timedelta(hours=1),
                        ),
                        # 别的日子的未开赛场次不在本次对账范围内。
                        Fixture(
                            id=104,
                            league_id=10,
                            home_team_id=1,
                            away_team_id=2,
                            date=now + timedelta(days=3),
                        ),
                    )
                )
                await session.commit()

                fetcher = FootballFetcher(session=session, cache=MagicMock())
                marked = await fetcher._mark_fixtures_missing_from_day(day, _feed(101))

                self.assertEqual(marked, 1)
                statuses = {
                    fixture_id: (await session.get(Fixture, fixture_id)).status
                    for fixture_id in (101, 102, 103, 104)
                }
                self.assertEqual(statuses[102], "postponed")
                self.assertEqual(statuses[101], "pending")
                self.assertEqual(statuses[103], "pending")
                self.assertEqual(statuses[104], "pending")
            await engine.dispose()

        asyncio.run(run())

    def test_empty_feed_never_marks_anything(self) -> None:
        """空清单分不清「当天没球」和「官方这次没给全」，一律不动。"""

        async def run() -> None:
            engine = _sqlite_engine()
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as session:
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                day = (now + timedelta(hours=3)).date()
                session.add(
                    League(
                        id=10,
                        name="国际友谊赛",
                        country="World",
                        season=str(now.year),
                        is_catalog=True,
                        is_hot=True,
                        is_protected=False,
                    )
                )
                session.add_all((Team(id=1, name="A"), Team(id=2, name="B")))
                await session.flush()
                session.add(
                    Fixture(
                        id=201,
                        league_id=10,
                        home_team_id=1,
                        away_team_id=2,
                        date=now + timedelta(hours=3),
                    )
                )
                await session.commit()

                fetcher = FootballFetcher(session=session, cache=MagicMock())
                self.assertEqual(
                    await fetcher._mark_fixtures_missing_from_day(day, []), 0
                )
                self.assertEqual((await session.get(Fixture, 201)).status, "pending")
            await engine.dispose()

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
