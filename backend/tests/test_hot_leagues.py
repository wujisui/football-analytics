"""Hot-league subset: catalog stays leagues.json; odds sync uses the overlay."""

from app.services.runtime_settings import (
    DEFAULT_HOT_LEAGUE_IDS,
    default_hot_league_ids,
    normalize_hot_league_ids,
)


def test_default_hot_leagues_are_the_agreed_subset() -> None:
    assert DEFAULT_HOT_LEAGUE_IDS == (
        39,
        140,
        78,
        135,
        61,
        2,
        3,
        848,
        169,
        98,
        292,
    )
    selected = default_hot_league_ids()
    assert selected
    assert all(league_id in selected for league_id in DEFAULT_HOT_LEAGUE_IDS)
    # 英冠等次级联赛在目录里，但不在默认热门。
    assert 40 not in selected
    assert 79 not in selected
    assert 62 not in selected


def test_normalize_hot_league_ids_keeps_catalog_order_and_drops_unknown() -> None:
    catalog = {39, 140, 40, 2}
    ordered = normalize_hot_league_ids([140, 39, 39, 999, 40], catalog=catalog)
    # Catalog file order: ... 2, 39, 40, 140 ...
    assert ordered == [39, 40, 140]


def test_normalize_allows_empty_hot_list() -> None:
    assert normalize_hot_league_ids([], catalog={39, 140}) == []
    assert normalize_hot_league_ids(None, catalog={39}) == []
