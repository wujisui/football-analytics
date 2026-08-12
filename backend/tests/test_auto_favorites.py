"""Auto-favorite ranking: single-lean catalog recommendations only."""

from datetime import datetime
from types import SimpleNamespace

from app.services.auto_favorites import (
    rank_auto_pick_candidates,
    score_fixture_confidence,
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
    assert score >= 0.58


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
    # Dual 1X2 / AH / multi-score must not win; OU/BTTS may still score.
    assert market in {"ou", "btts", ""}
    assert "胜/平" not in lean
    assert "让胜/负" not in lean
    assert "/" not in lean or market in {"ou", "btts"}


def test_dual_ah_lean_is_rejected_when_other_markets_weak() -> None:
    odds = {
        "match_winner": {"home": "3.40", "draw": "3.20", "away": "2.10"},
        "asian_handicap": {"home": "1.05", "away": "10.0", "line": "0"},
        "goals_ou": {"home": "1.95", "away": "1.85", "line": "2.5"},
        "both_teams_score": {"home": "1.90", "away": "1.90"},
    }
    # Flat-ish 1X2 + dual AH: best remaining single leans are OU/BTTS.
    score, market, lean = score_fixture_confidence(
        _stored(
            recommendation="胜/平",
            handicap_lean="让胜/负(0)",
            score_hint="比分:待分析",
            home_win_prob=0.34,
            draw_prob=0.33,
            away_win_prob=0.33,
        ),
        odds=odds,
    )
    assert market in {"ou", "btts"}
    assert lean in {"小(2.5)", "双进:否"}


def test_rank_keeps_top_unique_fixtures() -> None:
    odds = {
        "match_winner": {"home": "1.55", "draw": "4.00", "away": "6.00"},
        "asian_handicap": {"home": "1.80", "away": "2.00", "line": "-0.5"},
        "goals_ou": {"home": "2.20", "away": "1.65", "line": "2.5"},
        "both_teams_score": {"home": "2.10", "away": "1.70"},
    }

    def row(fid: int, home_p: float, kickoff: str):
        fixture = SimpleNamespace(id=fid, date=datetime.fromisoformat(kickoff))
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

    original_package = mod.package_from_record
    original_rehydrate = mod.rehydrate_odds_markets
    mod.package_from_record = lambda _stored: {"odds": odds}
    mod.rehydrate_odds_markets = lambda value: value
    try:
        picked = rank_auto_pick_candidates(rows, limit=4, min_confidence=0.58)
    finally:
        mod.package_from_record = original_package
        mod.rehydrate_odds_markets = original_rehydrate

    assert [item.fixture_id for item in picked] == [1, 2, 3, 4]
    assert all(item.score >= 0.58 for item in picked)
    assert all(item.market == "1x2" for item in picked)
    assert all("/" not in item.lean for item in picked)
