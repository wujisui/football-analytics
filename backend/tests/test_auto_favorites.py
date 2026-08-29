"""Market candidate valuation + within-day quality stars.

排序与每日四场的真源是 `recommendation.pipeline`（见 test_recommendation_pipeline）。
这里只覆盖候选层：哪些玩法根本不该成为候选，以及退还本金后的概率与水位估值。
"""

from datetime import datetime
from types import SimpleNamespace

from app.services.auto_favorites import (
    _market_candidates,
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


def test_double_chance_is_never_a_candidate() -> None:
    odds = {
        "match_winner": {"home": "2.10", "draw": "3.20", "away": "3.40"},
        "asian_handicap": {"home": "1.85", "away": "1.95", "line": "0"},
        "goals_ou": {"home": "1.95", "away": "1.85", "line": "2.5"},
        "both_teams_score": {"home": "1.90", "away": "1.90"},
    }
    candidates = _market_candidates(
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
    assert all("/" not in item.lean for item in candidates)


def test_standalone_handicap_push_is_never_a_candidate() -> None:
    odds = {
        "match_winner": {"home": "1.18", "draw": "7.30", "away": "14.00"},
        "asian_handicap": {"home": "1.90", "away": "1.95", "line": "-2"},
        "goals_ou": {"home": "1.92", "away": "1.92", "line": "3.25"},
        "both_teams_score": {"home": "2.20", "away": "1.65"},
    }
    candidates = _market_candidates(
        _stored(handicap_lean="让平(-2)"),
        odds=odds,
        feature=SimpleNamespace(ah_cover_prob=0.80),
    )
    assert not any(item.market == "ah" for item in candidates)


def test_exact_score_is_never_a_candidate_market() -> None:
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
    candidates = _market_candidates(_stored(score_hint="比分:1-0"), odds=odds)
    assert candidates
    assert {item.market for item in candidates} <= {"1x2", "ah", "ou", "btts"}


def test_plus_half_equivalent_away_pick_shares_the_1x2_probability() -> None:
    """客胜与主队 +0.5 让负是同一事件，不应被 AH 独立概率扭曲。"""
    odds = {
        "match_winner": {"home": "3.80", "draw": "3.40", "away": "2.00"},
        "asian_handicap": {"home": "1.90", "away": "2.08", "line": "+0.5"},
        "goals_ou": {"home": "1.20", "away": "4.50", "line": "2.5"},
        "both_teams_score": {"home": "1.20", "away": "4.50"},
    }
    candidates = _market_candidates(
        _stored(
            recommendation="负",
            handicap_lean="让负(+0.5)",
            home_win_prob=0.16,
            draw_prob=0.20,
            away_win_prob=0.64,
        ),
        odds=odds,
        # Deliberately contradictory AH model: it must not change an equivalent event.
        feature=SimpleNamespace(ah_cover_prob=0.95),
    )
    result_candidates = [
        item for item in candidates if item.event_key == "result:away"
    ]
    assert {item.market for item in result_candidates} == {"1x2", "ah"}
    assert len({item.raw_confidence for item in result_candidates}) == 1
    assert len({item.confidence for item in result_candidates}) == 1
    # 同一事件里 AH 报 2.08、独赢报 2.00，水位差是后续排序唯一的取舍依据。
    handicap = next(item for item in result_candidates if item.market == "ah")
    moneyline = next(item for item in result_candidates if item.market == "1x2")
    assert handicap.decimal_odd > moneyline.decimal_odd


def test_minus_half_no_cover_uses_draw_plus_away_probability() -> None:
    """主队 -0.5 让负包含平局和客胜，应作为更稳的复合事件估值。"""
    odds = {
        "match_winner": {"home": "2.50", "draw": "3.00", "away": "3.00"},
        "asian_handicap": {"home": "2.05", "away": "1.83", "line": "-0.5"},
        "goals_ou": {"home": "1.20", "away": "4.50", "line": "2.5"},
        "both_teams_score": {"home": "1.20", "away": "4.50"},
    }
    candidates = _market_candidates(
        _stored(
            recommendation="负",
            handicap_lean="让负(-0.5)",
            home_win_prob=0.30,
            draw_prob=0.30,
            away_win_prob=0.40,
        ),
        odds=odds,
        feature=SimpleNamespace(ah_cover_prob=0.99),
    )
    handicap = next(item for item in candidates if item.market == "ah")
    assert handicap.raw_confidence == 0.70


def test_quarter_line_prices_the_half_refund_instead_of_a_two_way_bet() -> None:
    """-0.25 让胜 only loses half a stake on a draw, and 平 never fully wins."""
    odds = {
        "match_winner": {"home": "2.50", "draw": "3.00", "away": "3.00"},
        "asian_handicap": {"home": "1.94", "away": "1.89", "line": "-0.25"},
    }
    candidates = _market_candidates(
        _stored(
            recommendation="胜/平",
            handicap_lean="让胜(-0.25)",
            home_win_prob=0.43,
            draw_prob=0.24,
            away_win_prob=0.33,
        ),
        odds=odds,
        feature=SimpleNamespace(ah_cover_prob=0.90),
    )
    handicap = next(item for item in candidates if item.market == "ah")
    # Half the stake rides on the draw, so 12% of it is refunded.
    assert handicap.stake_share == 0.88
    assert handicap.raw_confidence == 0.43 / 0.88
    # The independent AH model claimed a 0.90 cover, which as a plain two-way
    # bet would read as a huge edge; off the 1X2 board it is a losing price.
    assert handicap.raw_confidence < 0.55
    assert handicap.expected_return < 0


def test_level_line_refunds_the_draw_instead_of_counting_it_as_a_loss() -> None:
    odds = {
        "match_winner": {"home": "2.10", "draw": "3.30", "away": "3.60"},
        "asian_handicap": {"home": "1.95", "away": "1.95", "line": "0"},
    }
    candidates = _market_candidates(
        _stored(
            recommendation="胜",
            handicap_lean="让胜(0)",
            home_win_prob=0.45,
            draw_prob=0.28,
            away_win_prob=0.27,
        ),
        odds=odds,
    )
    handicap = next(item for item in candidates if item.market == "ah")
    assert handicap.stake_share == 0.72
    assert handicap.raw_confidence == 0.45 / 0.72


def test_large_model_market_gap_is_conservatively_shrunk() -> None:
    odds = {
        "match_winner": {"home": "3.80", "draw": "3.40", "away": "2.00"},
        "asian_handicap": {"home": "1.90", "away": "2.08", "line": "+0.5"},
    }
    candidates = _market_candidates(
        _stored(
            recommendation="负",
            handicap_lean="让负(+0.5)",
            home_win_prob=0.03,
            draw_prob=0.04,
            away_win_prob=0.93,
        ),
        odds=odds,
    )
    away = next(item for item in candidates if item.market == "1x2")
    assert away.implied_probability < away.confidence < away.raw_confidence


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
