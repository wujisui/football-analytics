import asyncio
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.services.match_day import (
    fixture_match_day,
    fixture_match_day_expr,
    infer_team_timezone,
    resolve_match_day,
    timezone_for_city,
)


def test_city_timezone_uses_offline_geographic_data() -> None:
    assert timezone_for_city("Glasgow", "World") == "Europe/London"
    assert timezone_for_city("Shanghai", "China") == "Asia/Shanghai"
    assert timezone_for_city("Zagreb", "World") == "Europe/Zagreb"


def test_south_american_utc_next_day_stays_on_local_previous_day() -> None:
    resolution = resolve_match_day(
        datetime.fromisoformat("2026-08-19T00:30:00"),
        home_team_timezone="America/Sao_Paulo",
    )
    assert resolution.match_day == "2026-08-18"
    assert resolution.timezone == "America/Sao_Paulo"
    assert resolution.source == "home_team"


def test_fixture_match_day_sql_prefers_persisted_local_day() -> None:
    sql = str(
        select(fixture_match_day_expr()).compile(
            compile_kwargs={"literal_binds": True}
        )
    )
    assert "coalesce(fixtures.match_day, date(fixtures.date))" in sql.lower()


def test_shanghai_and_glasgow_keep_their_own_august_19_match_day() -> None:
    shanghai = resolve_match_day(
        datetime.fromisoformat("2026-08-19T11:35:00"),
        venue_city="Shanghai",
        league_country="China",
    )
    glasgow = resolve_match_day(
        datetime.fromisoformat("2026-08-19T19:00:00"),
        venue_city="Glasgow",
        league_country="World",
    )
    assert shanghai.match_day == "2026-08-19"
    assert glasgow.match_day == "2026-08-19"


def test_favorites_response_buckets_late_kickoff_on_venue_local_day() -> None:
    """MLS 北京时间次日早场仍属场地当天：关注列表与【比赛】必须同一天。"""

    async def _run() -> None:
        from app.core.database import Base
        from app.models.favorite_fixture import FAVORITE_SOURCE_MANUAL, FavoriteFixture
        from app.models.fixture import Fixture
        from app.models.league import League
        from app.models.team import Team
        from app.services import favorites as favorites_service

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        db = async_sessionmaker(engine, expire_on_commit=False)()
        try:
            db.add(League(id=253, name="美职联", country="USA", season="2026"))
            db.add(Team(id=1600, name="洛杉矶银河"))
            db.add(Team(id=1601, name="西雅图海湾人"))
            kickoff = datetime.fromisoformat("2026-08-30T00:30:00")
            day = resolve_match_day(
                kickoff, venue_city="Los Angeles", league_country="USA"
            )
            db.add(
                Fixture(
                    id=9001,
                    league_id=253,
                    home_team_id=1600,
                    away_team_id=1601,
                    date=kickoff,
                    venue_city="Los Angeles",
                    match_timezone=day.timezone,
                    match_day=day.match_day,
                    match_day_source=day.source,
                    status="pending",
                )
            )
            db.add(
                FavoriteFixture(
                    user_id="u-1",
                    fixture_id=9001,
                    source=FAVORITE_SOURCE_MANUAL,
                    saved_at=datetime.now(timezone.utc).replace(tzinfo=None),
                )
            )
            await db.commit()

            items = await favorites_service.list_favorite_responses(db, user_id="u-1")
            assert [item.match_day for item in items] == ["2026-08-29"]
            # UTC kickoff day would have pushed it to the next day.
            assert items[0].fixture_date.date().isoformat() == "2026-08-30"
        finally:
            await db.close()
            await engine.dispose()

    asyncio.run(_run())


def test_fixture_match_day_falls_back_to_utc_kickoff_day() -> None:
    class _Row:
        match_day = None
        date = datetime.fromisoformat("2026-08-30T00:30:00")

    assert fixture_match_day(_Row()) == "2026-08-30"


def test_team_catalog_city_resolves_sao_paulo_timezone() -> None:
    zone, source = infer_team_timezone(
        venue_city="São Paulo, São Paulo",
        country="Brazil",
    )
    assert zone == "America/Sao_Paulo"
    assert source == "team_venue_city"
