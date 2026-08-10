"""Regression tests for same-name leagues in different countries."""

from app.services.league_names import league_name_zh


class _Settings:
    league_display_names: dict[int, str] = {}
    LEAGUE_COUNTRIES: dict[int, str] = {}


SETTINGS = _Settings()


def test_championship_uses_id_or_country_instead_of_guessing_england() -> None:
    assert league_name_zh("Championship", league_id=40, settings=SETTINGS) == "英冠"
    assert league_name_zh("Championship", league_id=180, settings=SETTINGS) == "苏冠"
    assert league_name_zh("Championship", country="England", settings=SETTINGS) == "英冠"
    assert league_name_zh("Championship", country="Scotland", settings=SETTINGS) == "苏冠"
    assert league_name_zh("Championship", settings=SETTINGS) == "Championship"


def test_bundesliga_uses_id_or_country_instead_of_guessing_germany() -> None:
    assert league_name_zh("Bundesliga", league_id=78, settings=SETTINGS) == "德甲"
    assert league_name_zh("Bundesliga", league_id=218, settings=SETTINGS) == "奥超"
    assert league_name_zh("Bundesliga", country="Germany", settings=SETTINGS) == "德甲"
    assert league_name_zh("Bundesliga", country="Austria", settings=SETTINGS) == "奥超"
    assert league_name_zh("Bundesliga", settings=SETTINGS) == "Bundesliga"
