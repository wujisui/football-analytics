from types import SimpleNamespace

from app.services.competition_scope import (
    EXTRA_COMPETITION_IDS,
    allowed_competition_ids,
    competition_is_allowed,
)


def test_catalog_and_verified_extras_are_allowed() -> None:
    settings = SimpleNamespace(LEAGUE_IDS={"英超": 39})

    allowed = allowed_competition_ids(settings)

    assert 39 in allowed
    assert 239 in allowed  # Colombia top division
    assert 102 in allowed  # Emperor Cup
    assert 667 in allowed  # Club friendlies


def test_youth_reserve_and_lower_divisions_are_rejected() -> None:
    settings = SimpleNamespace(LEAGUE_IDS={"英超": 39})

    assert not competition_is_allowed(488, settings)  # U19 Bundesliga
    assert not competition_is_allowed(906, settings)  # Argentina reserves
    assert not competition_is_allowed(63, settings)  # France Ligue 3
    assert not competition_is_allowed(72, settings)  # Brazil Serie B


def test_extra_whitelist_does_not_duplicate_catalog_policy() -> None:
    assert 39 not in EXTRA_COMPETITION_IDS
