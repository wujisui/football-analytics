"""1X2 vs handicap consistency checks."""

from app.services.recommendation.consistency import (
    validate_pick_consistency,
)


def _odds(*, line: str = "-0.75", home: float = 2.05, away: float = 1.80) -> dict:
    return {
        "available": True,
        "match_winner": {"home": 2.1, "draw": 3.3, "away": 3.5},
        "asian_handicap": {"line": line, "home": home, "away": away},
    }


def test_home_or_draw_rejects_minus_three_quarter_board() -> None:
    decision = validate_pick_consistency(
        recommendation="胜/平",
        daily_lean="胜",
        handicap_lean="让负(-0.75)",
        score_hint="比分:1-1",
        odds=_odds(line="-0.75"),
    )
    assert decision.is_consistent is False
    assert decision.conflict_reason == "无法修正，跳过"
    assert "胜/平" in decision.conflict_detail


def test_home_win_keeps_supported_minus_half_direction() -> None:
    decision = validate_pick_consistency(
        recommendation="胜",
        daily_lean="胜",
        handicap_lean="让胜(-0.5)",
        score_hint="比分:1-0/2-0",
        odds=_odds(line="-0.5", home=1.90, away=1.98),
    )
    assert decision.is_consistent is True
    assert decision.handicap_lean == "让胜(-0.5)"
    assert decision.score_hint == "比分:1-0/2-0"
    assert decision.conflict_reason == "原始匹配"


def test_home_or_draw_correction_reuses_only_matching_score() -> None:
    decision = validate_pick_consistency(
        recommendation="胜/平",
        daily_lean="胜",
        handicap_lean="让负(-0.25)",
        score_hint="比分:1-1/1-0",
        odds=_odds(line="-0.25", home=1.88, away=2.02),
    )
    assert decision.is_consistent is True
    assert decision.corrected is True
    assert decision.handicap_lean == "让胜(-0.25)"
    assert decision.score_hint == "比分:1-0"
    assert decision.conflict_reason == "修正后匹配"


def test_correction_rejects_when_market_water_opposes_new_side() -> None:
    decision = validate_pick_consistency(
        recommendation="胜/平",
        daily_lean="胜",
        handicap_lean="让负(-0.25)",
        score_hint="比分:1-0",
        odds=_odds(line="-0.25", home=2.08, away=1.80),
    )
    assert decision.is_consistent is False
    assert "水位不支持" in decision.conflict_detail


def test_correction_never_invents_a_score_candidate() -> None:
    decision = validate_pick_consistency(
        recommendation="胜/平",
        daily_lean="胜",
        handicap_lean="让负(-0.25)",
        score_hint="比分:1-1",
        odds=_odds(line="-0.25", home=1.88, away=2.02),
    )
    assert decision.is_consistent is False
    assert decision.score_hint == "比分:1-1"
    assert "已有比分候选" in decision.conflict_detail
