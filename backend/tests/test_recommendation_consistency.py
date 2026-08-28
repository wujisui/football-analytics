"""1X2 vs handicap consistency checks."""

from app.services.recommendation.consistency import (
    align_handicap_with_1x2,
    handicap_conflicts_with_1x2,
)


def _odds(*, line: str = "-0.75", home: float = 2.05, away: float = 1.80) -> dict:
    return {
        "available": True,
        "match_winner": {"home": 2.1, "draw": 3.3, "away": 3.5},
        "asian_handicap": {"line": line, "home": home, "away": away},
    }


def test_home_win_conflicts_when_line_below_minus_half() -> None:
    assert handicap_conflicts_with_1x2(
        lean_1x2="胜",
        handicap_lean="让负(-0.75)",
        odds=_odds(line="-0.75"),
    )


def test_home_win_ok_on_minus_half_line() -> None:
    assert not handicap_conflicts_with_1x2(
        lean_1x2="胜",
        handicap_lean="让胜(-0.5)",
        odds=_odds(line="-0.5", home=1.95, away=1.90),
    )


def test_align_handicap_applies_correction_for_home_win() -> None:
    corrected, applied = align_handicap_with_1x2(
        lean_1x2="胜",
        odds=_odds(line="-0.75"),
        league_id=39,
        stored_handicap="让负(-0.75)",
    )
    assert applied is True
    assert corrected.startswith("让")
