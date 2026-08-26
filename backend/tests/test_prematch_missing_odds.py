import asyncio
import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

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


class PrematchMissingOddsTests(unittest.TestCase):
    def test_only_missing_fixture_in_default_prematch_window_is_pulled(self) -> None:
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
                session.add_all((Team(id=1, name="A"), Team(id=2, name="B")))
                await session.flush()
                fixtures = (
                    Fixture(
                        id=48001,
                        league_id=48,
                        home_team_id=1,
                        away_team_id=2,
                        date=now + timedelta(hours=2),
                        match_day=(now + timedelta(hours=2)).date().isoformat(),
                    ),
                    Fixture(
                        id=48002,
                        league_id=48,
                        home_team_id=1,
                        away_team_id=2,
                        date=now + timedelta(days=1, hours=2),
                        match_day=(now + timedelta(days=1)).date().isoformat(),
                    ),
                    Fixture(
                        id=48003,
                        league_id=48,
                        home_team_id=1,
                        away_team_id=2,
                        date=now + timedelta(days=2, hours=2),
                        match_day=(now + timedelta(days=2)).date().isoformat(),
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
                report = await fetcher.sync_missing_odds_for_prematch_list()

                self.assertEqual(report["candidates"], 1)
                self.assertEqual(report["attempted"], 1)
                self.assertEqual(report["updated"], 1)
                fetcher.refresh_odds_for_fixture.assert_awaited_once_with(48001)
            await engine.dispose()

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
