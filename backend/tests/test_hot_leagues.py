"""Database league catalog seed policy."""

from app.services.league_catalog import (
    CATEGORY_BY_LEAGUE_ID,
    CATEGORY_SEEDS,
    DEFAULT_HOT_LEAGUE_IDS,
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
    # 英冠等次级联赛在目录里，但不在默认热门。
    assert 40 not in DEFAULT_HOT_LEAGUE_IDS
    assert 79 not in DEFAULT_HOT_LEAGUE_IDS
    assert 62 not in DEFAULT_HOT_LEAGUE_IDS


def test_seed_categories_include_domestic_cups() -> None:
    assert (8, "各国杯赛") in CATEGORY_SEEDS
    assert CATEGORY_BY_LEAGUE_ID[39] == 1
    assert CATEGORY_BY_LEAGUE_ID[2] == 2
