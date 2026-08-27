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


def test_league_one_scotland_is_not_england() -> None:
    assert league_name_zh("League One", league_id=41, country="England", settings=SETTINGS) == "英甲"
    assert league_name_zh("League One", league_id=183, country="Scotland", settings=SETTINGS) == "苏甲"
    assert league_name_zh("League Two", league_id=184, country="Scotland", settings=SETTINGS) == "苏乙"


def test_primera_division_is_country_scoped() -> None:
    assert league_name_zh("Primera División", league_id=265, country="Chile", settings=SETTINGS) == "智利甲"
    assert league_name_zh("Primera División", league_id=268, country="Uruguay", settings=SETTINGS) == "乌拉甲"
    assert league_name_zh("Primera División", league_id=299, country="Venezuela", settings=SETTINGS) == "委内甲"
    assert league_name_zh("Primera División", settings=SETTINGS) == "Primera División"


def test_championship_northern_ireland_is_not_england() -> None:
    assert (
        league_name_zh(
            "Championship", league_id=407, country="Northern-Ireland", settings=SETTINGS
        )
        == "北爱冠"
    )


def test_super_liga_serbia_is_not_slovakia() -> None:
    assert league_name_zh("Super Liga", league_id=286, country="Serbia", settings=SETTINGS) == "塞超"
    assert (
        league_name_zh("Super Liga", league_id=332, country="Slovakia", settings=SETTINGS)
        == "斯洛伐克超"
    )


def test_liga_nacional_honduras_is_not_guatemala() -> None:
    assert (
        league_name_zh("Liga Nacional", league_id=234, country="Honduras", settings=SETTINGS)
        == "洪都拉斯甲"
    )
    assert (
        league_name_zh("Liga Nacional", league_id=339, country="Guatemala", settings=SETTINGS)
        == "危地马拉甲"
    )


def test_kings_cup_is_not_bound_to_saudi_arabia_by_name() -> None:
    # Thailand runs a King's Cup as well, so the bare name must stay untranslated.
    assert league_name_zh("King's Cup", league_id=504, settings=SETTINGS) == "沙特国王杯"
    assert (
        league_name_zh("King's Cup", country="Saudi-Arabia", settings=SETTINGS)
        == "沙特国王杯"
    )
    assert league_name_zh("King's Cup", settings=SETTINGS) == "King's Cup"
