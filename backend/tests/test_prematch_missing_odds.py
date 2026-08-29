import asyncio
import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, call
from zoneinfo import ZoneInfo

from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.fixture import Fixture
from app.models.league import League
from app.models.pre_match_data import PreMatchData
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


def _odds_json() -> str:
    return json.dumps(
        {
            "available": True,
            "match_winner": {"home": 2.0, "draw": 3.1, "away": 3.8},
        }
    )


class PrematchBatchOddsTests(unittest.TestCase):
    def test_only_explicit_today_catalog_fixtures_are_refreshed(self) -> None:
        async def run() -> None:
            engine = _sqlite_engine()
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as session:
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                session.add(
                    League(
                        id=48,
                        name="日本天皇杯",
                        country="Japan",
                        season=str(now.year),
                        is_catalog=True,
                        is_hot=True,
                        is_protected=False,
                    )
                )
                session.add(
                    League(
                        id=49,
                        name="非热门杯赛",
                        country="Japan",
                        season=str(now.year),
                        is_catalog=True,
                        is_hot=False,
                        is_protected=False,
                    )
                )
                session.add_all((Team(id=1, name="A"), Team(id=2, name="B")))
                await session.flush()
                local_today = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
                fixtures = (
                    Fixture(
                        id=48001,
                        league_id=48,
                        home_team_id=1,
                        away_team_id=2,
                        date=now + timedelta(hours=2),
                        match_day=local_today,
                    ),
                    Fixture(
                        id=48002,
                        league_id=48,
                        home_team_id=1,
                        away_team_id=2,
                        date=now + timedelta(hours=3),
                        match_day=local_today,
                    ),
                    Fixture(
                        id=48003,
                        league_id=48,
                        home_team_id=1,
                        away_team_id=2,
                        date=now + timedelta(days=2, hours=2),
                        match_day=(
                            datetime.now(ZoneInfo("Asia/Shanghai")).date()
                            + timedelta(days=1)
                        ).isoformat(),
                    ),
                    Fixture(
                        id=49001,
                        league_id=49,
                        home_team_id=1,
                        away_team_id=2,
                        date=now + timedelta(hours=4),
                        match_day=local_today,
                    ),
                )
                session.add_all(fixtures)
                session.add(PreMatchData(fixture_id=48002, odds_json=_odds_json()))
                await session.commit()

                async def fake_refresh(fixture_id: int) -> bool:
                    row = await session.scalar(
                        select(PreMatchData).where(
                            PreMatchData.fixture_id == fixture_id
                        )
                    )
                    if row is None:
                        session.add(
                            PreMatchData(
                                fixture_id=fixture_id,
                                odds_json=_odds_json(),
                            )
                        )
                    else:
                        row.odds_json = _odds_json()
                    await session.commit()
                    return True

                fetcher = FootballFetcher(session=session, cache=MagicMock())
                fetcher.refresh_odds_for_fixture = AsyncMock(
                    side_effect=fake_refresh
                )
                report = await fetcher.sync_odds_for_prematch_fixtures(
                    [48001, 48002, 48003, 49001]
                )

                self.assertEqual(report["candidates"], 3)
                self.assertEqual(report["attempted"], 3)
                self.assertEqual(report["updated"], 3)
                self.assertEqual(
                    fetcher.refresh_odds_for_fixture.await_args_list,
                    [call(48001), call(48002), call(49001)],
                )
            await engine.dispose()

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
