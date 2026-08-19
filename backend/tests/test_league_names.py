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


def test_bare_cup_stays_country_scoped() -> None:
    assert league_name_zh("Cup", league_id=199, settings=SETTINGS) == "希腊杯"
    assert league_name_zh("Cup", league_id=237, settings=SETTINGS) == "俄罗斯杯"
    assert league_name_zh("Cup", country="Kazakhstan", settings=SETTINGS) == "哈萨克杯"
    assert league_name_zh("Cup", country="Slovakia", settings=SETTINGS) == "斯洛伐克杯"
    assert league_name_zh("Cup", settings=SETTINGS) == "Cup"


def test_premier_league_does_not_default_to_england() -> None:
    assert league_name_zh("Premier League", league_id=116, settings=SETTINGS) == "白俄超"
    assert league_name_zh("Premier League", league_id=342, settings=SETTINGS) == "亚美尼亚超"
    assert (
        league_name_zh("Premier League", country="Armenia", settings=SETTINGS)
        == "亚美尼亚超"
    )


def test_kings_cup_is_not_bound_to_saudi_arabia_by_name() -> None:
    # Thailand runs a King's Cup as well, so the bare name must stay untranslated.
    assert league_name_zh("King's Cup", league_id=504, settings=SETTINGS) == "沙特国王杯"
    assert (
        league_name_zh("King's Cup", country="Saudi-Arabia", settings=SETTINGS)
        == "沙特国王杯"
    )
    assert league_name_zh("King's Cup", settings=SETTINGS) == "King's Cup"
