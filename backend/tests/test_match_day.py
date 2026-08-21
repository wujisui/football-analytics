from datetime import datetime

from sqlalchemy import select

from app.services.match_day import (
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


def test_team_catalog_city_resolves_sao_paulo_timezone() -> None:
    zone, source = infer_team_timezone(
        venue_city="São Paulo, São Paulo",
        country="Brazil",
    )
    assert zone == "America/Sao_Paulo"
    assert source == "team_venue_city"
