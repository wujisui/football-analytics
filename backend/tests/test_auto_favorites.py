"""Auto-favorite ranking: always fill 4 when enough single-lean fixtures exist."""

from datetime import datetime
from types import SimpleNamespace

from app.services.auto_favorites import (
    rank_auto_pick_candidates,
    score_auto_pick_candidates,
    score_fixture_confidence,
    select_auto_picks_by_match_day,
    within_day_quality_ratings,
)


def _stored(**kwargs):
    base = {
        "recommendation": "胜",
        "score_hint": "比分:1-0",
        "goal_lean": "小(2.5)",
        "both_score_lean": "双进:否",
        "handicap_lean": "让胜(0)",
        "home_win_prob": 0.62,
        "draw_prob": 0.22,
        "away_win_prob": 0.16,
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


def _patch_odds(mod, odds):
    original_package = mod.package_from_record
    original_rehydrate = mod.rehydrate_odds_markets
    mod.package_from_record = lambda _stored: {"odds": odds}
    mod.rehydrate_odds_markets = lambda value: value
    return original_package, original_rehydrate


def test_score_prefers_sharp_single_1x2() -> None:
    odds = {
        "match_winner": {"home": "1.60", "draw": "3.80", "away": "5.50"},
        "asian_handicap": {"home": "1.90", "away": "1.90", "line": "0"},
        "goals_ou": {"home": "2.10", "away": "1.70", "line": "2.5"},
        "both_teams_score": {"home": "2.00", "away": "1.75"},
    }
    score, market, lean = score_fixture_confidence(_stored(), odds=odds)
    assert market == "1x2"
    assert lean == "胜"
    assert score == 0.62 * 1.60 - 1.0


def test_score_uses_validated_calibration_before_expected_return() -> None:
    odds = {
        "match_winner": {"home": "1.60", "draw": "3.80", "away": "5.50"},
        "asian_handicap": {"home": "1.90", "away": "1.90", "line": "0"},
        "goals_ou": {"home": "2.10", "away": "1.70", "line": "2.5"},
        "both_teams_score": {"home": "2.00", "away": "1.75"},
    }
    calibration = {
        "version": "daily-pick-platt-v1",
        # a=0,b=0 maps 1X2 confidence to 0.5; other markets stay raw.
        "markets": {"1x2": {"deployable": True, "a": 0.0, "b": 0.0}},
    }
    score, market, _lean = score_fixture_confidence(
        _stored(),
        odds=odds,
        calibration=calibration,
    )
    assert market != "1x2"
    assert score > 0.5 * 1.60 - 1.0


def test_double_chance_is_rejected() -> None:
    odds = {
        "match_winner": {"home": "2.10", "draw": "3.20", "away": "3.40"},
        "asian_handicap": {"home": "1.85", "away": "1.95", "line": "0"},
        "goals_ou": {"home": "1.95", "away": "1.85", "line": "2.5"},
        "both_teams_score": {"home": "1.90", "away": "1.90"},
    }
    score, market, lean = score_fixture_confidence(
        _stored(
            recommendation="胜/平",
            handicap_lean="让胜/负(0)",
            score_hint="比分:1-0 / 2-1",
            home_win_prob=0.40,
            draw_prob=0.30,
            away_win_prob=0.30,
        ),
        odds=odds,
    )
    assert market in {"ou", "btts", ""}
    assert "胜/平" not in lean
    assert "让胜/负" not in lean


def test_exact_score_is_never_an_auto_pick_market() -> None:
    """比分提示 remains display-only; 9%-type hit rates cannot be a main pick."""
    odds = {
        "match_winner": {"home": "2.10", "draw": "3.20", "away": "3.40"},
        "asian_handicap": {"home": "1.90", "away": "1.90", "line": "0"},
        "goals_ou": {"home": "1.95", "away": "1.85", "line": "2.5"},
        "both_teams_score": {"home": "1.90", "away": "1.90"},
        "bookmakers": [
            {
                "bet": "Exact Score",
                "values": [{"label": "1-0", "odd": "8.00"}],
            }
        ],
    }
    _score, market, _lean = score_fixture_confidence(
        _stored(score_hint="比分:1-0"),
        odds=odds,
    )
    assert market in {"1x2", "ah", "ou", "btts"}
    assert market != "score"


def test_prefers_better_value_market_over_tiny_1x2() -> None:
    """Within a fixture, 1.07 胜 loses to a better-EV AH lean."""
    odds = {
        "match_winner": {"home": "1.07", "draw": "11.0", "away": "26.0"},
        "asian_handicap": {"home": "1.90", "away": "1.90", "line": "-1.5"},
        "goals_ou": {"home": "1.09", "away": "5.50", "line": "2.5"},
        "both_teams_score": {"home": "1.15", "away": "4.80"},
    }
    feature = SimpleNamespace(ah_cover_prob=0.62)
    score, market, lean = score_fixture_confidence(
        _stored(home_win_prob=0.90, handicap_lean="让胜(-1.5)"),
        odds=odds,
        feature=feature,
    )
    assert market == "ah"
    assert "让胜" in lean
    assert score == 0.62 * 1.90 - 1.0
    assert score > 0.90 * 1.07 - 1.0


def test_rank_still_fills_four_when_only_short_odds_exist() -> None:
    short = {
        "match_winner": {"home": "1.07", "draw": "11.0", "away": "26.0"},
        "asian_handicap": {"home": "1.18", "away": "4.50", "line": "-1.5"},
        "goals_ou": {"home": "1.09", "away": "5.50", "line": "2.5"},
        "both_teams_score": {"home": "1.15", "away": "4.80"},
    }

    def row(fid: int, home_p: float, kickoff: str):
        fixture = SimpleNamespace(
            id=fid,
            league_id=39,
            date=datetime.fromisoformat(kickoff),
        )
        stored = _stored(
            recommendation="胜",
            home_win_prob=home_p,
            draw_prob=(1 - home_p) * 0.55,
            away_win_prob=(1 - home_p) * 0.45,
        )
        return fixture, stored, None

    rows = [
        row(1, 0.92, "2026-08-12T12:00:00"),
        row(2, 0.90, "2026-08-12T13:00:00"),
        row(3, 0.88, "2026-08-12T14:00:00"),
        row(4, 0.86, "2026-08-12T15:00:00"),
        row(5, 0.84, "2026-08-12T16:00:00"),
    ]

    import app.services.auto_favorites as mod

    original = _patch_odds(mod, short)
    try:
        picked = rank_auto_pick_candidates(rows, limit=4)
    finally:
        mod.package_from_record, mod.rehydrate_odds_markets = original

    assert len(picked) == 4
    assert [item.fixture_id for item in picked] == [1, 2, 3, 4]


def test_calibration_changes_confidence_without_changing_daily_cap() -> None:
    odds = {
        "match_winner": {"home": "1.70", "draw": "4.00", "away": "6.00"},
        "asian_handicap": {"home": "1.55", "away": "2.40", "line": "-0.5"},
        "goals_ou": {"home": "1.90", "away": "1.90", "line": "2.5"},
        "both_teams_score": {"home": "1.90", "away": "1.90"},
    }
    rows = [
        (
            SimpleNamespace(
                id=fid,
                league_id=39,
                date=datetime.fromisoformat(f"2026-08-12T{11 + fid:02d}:00:00"),
            ),
            _stored(
                home_win_prob=0.70 - fid * 0.02,
                draw_prob=0.20,
                away_win_prob=0.10 + fid * 0.02,
            ),
            None,
        )
        for fid in range(1, 6)
    ]
    calibration = {
        "version": "daily-pick-platt-v1",
        "markets": {"1x2": {"deployable": True, "a": 0.8, "b": -0.15}},
    }

    import app.services.auto_favorites as mod

    original = _patch_odds(mod, odds)
    try:
        picked = rank_auto_pick_candidates(rows, limit=4, calibration=calibration)
    finally:
        mod.package_from_record, mod.rehydrate_odds_markets = original

    assert len(picked) == 4
    assert any(item.confidence != item.raw_confidence for item in picked)


def test_rank_prefers_value_fixture_over_tiny_odds() -> None:
    tiny = {
        "match_winner": {"home": "1.07", "draw": "11.0", "away": "26.0"},
        "asian_handicap": {"home": "1.18", "away": "4.50", "line": "-1.5"},
        "goals_ou": {"home": "1.09", "away": "5.50", "line": "2.5"},
        "both_teams_score": {"home": "1.15", "away": "4.80"},
    }
    value = {
        "match_winner": {"home": "1.80", "draw": "3.60", "away": "4.20"},
        "asian_handicap": {"home": "1.90", "away": "1.90", "line": "0"},
        "goals_ou": {"home": "2.00", "away": "1.80", "line": "2.5"},
        "both_teams_score": {"home": "1.95", "away": "1.85"},
    }

    import app.services.auto_favorites as mod

    def make_row(fid: int, kickoff: str, home_p: float):
        fixture = SimpleNamespace(
            id=fid,
            league_id=39,
            date=datetime.fromisoformat(kickoff),
        )
        stored = _stored(
            recommendation="胜",
            home_win_prob=home_p,
            draw_prob=(1 - home_p) * 0.55,
            away_win_prob=(1 - home_p) * 0.45,
        )
        return fixture, stored, None

    # Odd fixture ids get value odds; even get tiny odds.
    packages = {
        1: tiny,
        2: value,
        3: tiny,
        4: value,
        5: tiny,
        6: value,
        7: tiny,
        8: value,
    }
    rows = [
        make_row(1, "2026-08-12T12:00:00", 0.92),
        make_row(2, "2026-08-12T13:00:00", 0.62),
        make_row(3, "2026-08-12T14:00:00", 0.91),
        make_row(4, "2026-08-12T15:00:00", 0.60),
        make_row(5, "2026-08-12T16:00:00", 0.90),
        make_row(6, "2026-08-12T17:00:00", 0.58),
        make_row(7, "2026-08-12T18:00:00", 0.89),
        make_row(8, "2026-08-12T19:00:00", 0.56),
    ]

    original_package = mod.package_from_record
    original_rehydrate = mod.rehydrate_odds_markets
    mod.package_from_record = lambda stored: {
        "odds": packages[next(f.id for f, s, _ in rows if s is stored)]
    }
    # The lambda above is fragile — use fixture id via side channel.
    mod.package_from_record = lambda stored: {"odds": packages[stored._fid]}
    for fixture, stored, _ in rows:
        stored._fid = fixture.id
    mod.rehydrate_odds_markets = lambda value: value
    try:
        picked = rank_auto_pick_candidates(rows, limit=4)
    finally:
        mod.package_from_record = original_package
        mod.rehydrate_odds_markets = original_rehydrate

    assert [item.fixture_id for item in picked] == [2, 4, 6, 8]
    assert all(item.decimal_odd >= 1.50 for item in picked)


def test_rank_keeps_top_unique_fixtures() -> None:
    odds = {
        "match_winner": {"home": "1.80", "draw": "4.00", "away": "6.00"},
        "asian_handicap": {"home": "1.80", "away": "2.00", "line": "-0.5"},
        "goals_ou": {"home": "2.20", "away": "1.65", "line": "2.5"},
        "both_teams_score": {"home": "2.10", "away": "1.70"},
    }

    def row(fid: int, home_p: float, kickoff: str):
        fixture = SimpleNamespace(
            id=fid,
            league_id=39,
            date=datetime.fromisoformat(kickoff),
        )
        stored = _stored(
            recommendation="胜",
            home_win_prob=home_p,
            draw_prob=(1 - home_p) * 0.55,
            away_win_prob=(1 - home_p) * 0.45,
        )
        return fixture, stored, None

    rows = [
        row(1, 0.70, "2026-08-12T12:00:00"),
        row(2, 0.66, "2026-08-12T13:00:00"),
        row(3, 0.63, "2026-08-12T14:00:00"),
        row(4, 0.61, "2026-08-12T15:00:00"),
        row(5, 0.59, "2026-08-12T16:00:00"),
    ]

    import app.services.auto_favorites as mod

    original = _patch_odds(mod, odds)
    try:
        picked = rank_auto_pick_candidates(rows, limit=4)
    finally:
        mod.package_from_record, mod.rehydrate_odds_markets = original

    assert [item.fixture_id for item in picked] == [1, 2, 3, 4]
    assert all(item.market == "1x2" for item in picked)
    assert all("/" not in item.lean for item in picked)


def test_selects_four_per_match_day_not_four_for_whole_window() -> None:
    odds = {
        "match_winner": {"home": "1.80", "draw": "4.00", "away": "6.00"},
        "asian_handicap": {"home": "1.80", "away": "2.00", "line": "-0.5"},
        "goals_ou": {"home": "2.20", "away": "1.65", "line": "2.5"},
        "both_teams_score": {"home": "2.10", "away": "1.70"},
    }

    def row(fid: int, home_p: float, kickoff: str):
        fixture = SimpleNamespace(
            id=fid,
            league_id=39,
            date=datetime.fromisoformat(kickoff),
        )
        stored = _stored(
            recommendation="胜",
            home_win_prob=home_p,
            draw_prob=(1 - home_p) * 0.55,
            away_win_prob=(1 - home_p) * 0.45,
        )
        return fixture, stored, None

    rows = [
        row(1, 0.70, "2026-08-12T12:00:00"),
        row(2, 0.66, "2026-08-12T13:00:00"),
        row(3, 0.63, "2026-08-12T14:00:00"),
        row(4, 0.61, "2026-08-12T15:00:00"),
        row(5, 0.59, "2026-08-12T16:00:00"),
        row(11, 0.71, "2026-08-13T12:00:00"),
        row(12, 0.67, "2026-08-13T13:00:00"),
        row(13, 0.64, "2026-08-13T14:00:00"),
        row(14, 0.62, "2026-08-13T15:00:00"),
        row(15, 0.60, "2026-08-13T16:00:00"),
    ]

    import app.services.auto_favorites as mod

    original = _patch_odds(mod, odds)
    try:
        scored = score_auto_pick_candidates(rows)
        picked = select_auto_picks_by_match_day(scored, limit_per_day=4)
    finally:
        mod.package_from_record, mod.rehydrate_odds_markets = original

    assert [item.fixture_id for item in picked] == [1, 2, 3, 4, 11, 12, 13, 14]
    assert len(picked) == 8


def test_auto_pick_buckets_use_persisted_local_match_day() -> None:
    odds = {
        "match_winner": {"home": "1.80", "draw": "4.00", "away": "6.00"},
        "asian_handicap": {"home": "1.80", "away": "2.00", "line": "-0.5"},
        "goals_ou": {"home": "2.20", "away": "1.65", "line": "2.5"},
        "both_teams_score": {"home": "2.10", "away": "1.70"},
    }

    def row(fid: int, match_day: str):
        fixture = SimpleNamespace(
            id=fid,
            league_id=11,
            # Both kickoffs share a UTC date; persisted local days differ.
            date=datetime.fromisoformat("2026-08-19T00:30:00"),
            match_day=match_day,
        )
        return fixture, _stored(home_win_prob=0.60 + fid / 100), None

    import app.services.auto_favorites as mod

    original = _patch_odds(mod, odds)
    try:
        scored = score_auto_pick_candidates(
            [row(1, "2026-08-18"), row(2, "2026-08-19")]
        )
        picked = select_auto_picks_by_match_day(scored, limit_per_day=1)
    finally:
        mod.package_from_record, mod.rehydrate_odds_markets = original

    assert [item.fixture_id for item in picked] == [1, 2]
    assert [item.match_day for item in picked] == ["2026-08-18", "2026-08-19"]


def test_within_day_ratings_anchor_best_at_five_per_day() -> None:
    def pick(fid: int, score: float, kickoff: str):
        return SimpleNamespace(
            fixture_id=fid,
            kickoff=datetime.fromisoformat(kickoff),
            match_day=kickoff[:10],
            score=score,
        )

    picks = [
        pick(1, 0.09, "2026-08-12T12:00:00"),
        pick(2, 0.07, "2026-08-12T13:00:00"),
        pick(3, 0.03, "2026-08-12T14:00:00"),
        pick(4, 50.0, "2026-08-13T12:00:00"),  # lone pick next day
    ]
    ratings = within_day_quality_ratings(picks)

    # Each match day anchors its own best at 5 星; lower score tiers lose 0.5.
    assert ratings[1] == 5.0
    assert ratings[2] == 4.5
    assert ratings[3] == 4.0
    # A day's sole pick is that day's best → full stars.
    assert ratings[4] == 5.0


def test_within_day_ratings_equal_scores_all_five() -> None:
    def pick(fid: int, kickoff: str):
        return SimpleNamespace(
            fixture_id=fid,
            kickoff=datetime.fromisoformat(kickoff),
            match_day=kickoff[:10],
            score=-0.03,
        )

    picks = [pick(1, "2026-08-12T12:00:00"), pick(2, "2026-08-12T13:00:00")]
    ratings = within_day_quality_ratings(picks)
    assert ratings == {1: 5.0, 2: 5.0}

