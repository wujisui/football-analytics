from app.services.competition_scope import EXTRA_COMPETITION_IDS


def test_verified_extras_are_allowed() -> None:
    assert 239 in EXTRA_COMPETITION_IDS  # Colombia top division
    assert 102 in EXTRA_COMPETITION_IDS  # Emperor Cup
    assert 667 in EXTRA_COMPETITION_IDS  # Club friendlies


def test_youth_reserve_and_lower_divisions_are_rejected() -> None:
    assert 488 not in EXTRA_COMPETITION_IDS  # U19 Bundesliga
    assert 906 not in EXTRA_COMPETITION_IDS  # Argentina reserves
    assert 63 not in EXTRA_COMPETITION_IDS  # France Ligue 3
    assert 72 not in EXTRA_COMPETITION_IDS  # Brazil Serie B


def test_extra_whitelist_does_not_duplicate_catalog_policy() -> None:
    assert 39 not in EXTRA_COMPETITION_IDS
