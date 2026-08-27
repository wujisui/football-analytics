from datetime import datetime, timezone

from app.schemas.response import analysis_to_response
from app.services.analyzer import AnalysisResult
from app.services.market_analysis import build_market_analysis


def _board(
    captured_at: str,
    *,
    role: str,
    ah_line: str,
    ah_home: str,
    ah_away: str,
    ou_line: str,
    ou_home: str,
    ou_away: str,
    home: str,
    draw: str,
    away: str,
    bookmaker: str = "Pinnacle",
) -> dict:
    return {
        "available": True,
        "role": role,
        "captured_at": captured_at,
        "match_winner": {
            "bookmaker": bookmaker,
            "home": home,
            "draw": draw,
            "away": away,
        },
        "asian_handicap": {
            "bookmaker": bookmaker,
            "line": ah_line,
            "home": ah_home,
            "away": ah_away,
            "lines": [
                {"line": "0", "home": "1.82" if role == "opening" else "1.68", "away": "1.99" if role == "opening" else "2.18"},
                {"line": "-0.25", "home": "2.09" if role == "opening" else ah_home, "away": "1.72" if role == "opening" else ah_away},
                {"line": "-0.5", "home": "2.34" if role == "opening" else "2.17", "away": "1.56" if role == "opening" else "1.69"},
            ],
        },
        "goals_ou": {
            "bookmaker": bookmaker,
            "line": ou_line,
            "home": ou_home,
            "away": ou_away,
            "lines": [
                {"line": "3.0", "home": "1.96" if role == "opening" else "1.64", "away": "1.83" if role == "opening" else "2.25"},
                {"line": "3.25", "home": "2.20" if role == "opening" else ou_home, "away": "1.64" if role == "opening" else ou_away},
            ],
        },
    }


def test_four_stage_analysis_uses_real_line_and_probability_movement() -> None:
    opening = _board(
        "2026-08-26T08:00:00+00:00",
        role="opening",
        ah_line="0",
        ah_home="1.82",
        ah_away="1.99",
        ou_line="3.0",
        ou_home="1.96",
        ou_away="1.83",
        home="2.38",
        draw="3.60",
        away="2.59",
    )
    mid = _board(
        "2026-08-27T12:00:00+00:00",
        role="mid",
        ah_line="-0.25",
        ah_home="2.00",
        ah_away="1.82",
        ou_line="3.0",
        ou_home="1.75",
        ou_away="2.10",
        home="2.28",
        draw="3.70",
        away="2.70",
    )
    late = _board(
        "2026-08-27T16:00:00+00:00",
        role="late",
        ah_line="-0.25",
        ah_home="1.96",
        ah_away="1.87",
        ou_line="3.25",
        ou_home="1.90",
        ou_away="1.91",
        home="2.20",
        draw="3.85",
        away="2.78",
    )
    current = _board(
        "2026-08-27T17:00:00+00:00",
        role="current",
        ah_line="-0.25",
        ah_home="1.94",
        ah_away="1.89",
        ou_line="3.25",
        ou_home="1.86",
        ou_away="1.95",
        home="2.18",
        draw="3.91",
        away="2.81",
    )
    result = build_market_analysis(
        {
            "odds_opening": opening,
            "odds_mid": mid,
            "odds_late": late,
            "odds": current,
        },
        probabilities={"home": 0.43, "draw": 0.24, "away": 0.33},
        recommendation="胜/平",
        handicap_lean="让胜(-0.25)",
        goal_lean="大(3.25)",
    )

    text = "\n".join([*result["paragraphs"], *result["bullets"]])
    assert result["available"] is True
    assert result["stage_count"] == 4
    assert "初盘 → 中盘 → 临场 → 即时盘" in text
    assert "初盘 0 → 中盘 -0.25" in text
    assert "向主队方向升盘" in text
    assert "形成主队方向共振" in text
    assert "大小球主盘轨迹：初盘 3 → 临场 3.25" in text
    assert "市场对总进球数的定价上调" in text
    assert "均为负期望" in text


def test_same_capture_is_not_described_as_fake_movement() -> None:
    current = _board(
        "2026-08-27T17:00:00+00:00",
        role="current",
        ah_line="-0.25",
        ah_home="1.94",
        ah_away="1.89",
        ou_line="3.25",
        ou_home="1.86",
        ou_away="1.95",
        home="2.18",
        draw="3.91",
        away="2.81",
    )
    result = build_market_analysis(
        {"odds_opening": {**current, "role": "opening"}, "odds": current},
        probabilities={"home": 0.43, "draw": 0.24, "away": 0.33},
        recommendation="胜/平",
        handicap_lean="让胜(-0.25)",
    )
    text = "\n".join([*result["paragraphs"], *result["bullets"]])
    assert result["stage_count"] == 1
    assert "共 1 个" in text
    assert "相对初盘" not in text


def test_bookmaker_swap_is_reported_but_not_called_a_market_move() -> None:
    opening = _board(
        "2026-08-26T08:00:00+00:00",
        role="opening",
        ah_line="0",
        ah_home="1.82",
        ah_away="1.99",
        ou_line="3.0",
        ou_home="1.96",
        ou_away="1.83",
        home="2.38",
        draw="3.60",
        away="2.59",
        bookmaker="Bet365",
    )
    current = _board(
        "2026-08-27T17:00:00+00:00",
        role="current",
        ah_line="-0.25",
        ah_home="1.94",
        ah_away="1.89",
        ou_line="3.25",
        ou_home="1.86",
        ou_away="1.95",
        home="2.18",
        draw="3.91",
        away="2.81",
    )
    result = build_market_analysis(
        {"odds_opening": opening, "odds": current},
        probabilities={"home": 0.43, "draw": 0.24, "away": 0.33},
        recommendation="胜/平",
        handicap_lean="让胜(-0.25)",
    )
    text = "\n".join(result["paragraphs"])
    assert "向主队方向升盘" not in text
    assert any("庄家不同" in warning for warning in result["warnings"])


def test_detail_analysis_response_includes_backend_explanation() -> None:
    current = _board(
        "2026-08-27T17:00:00+00:00",
        role="current",
        ah_line="-0.25",
        ah_home="1.94",
        ah_away="1.89",
        ou_line="3.25",
        ou_home="1.86",
        ou_away="1.95",
        home="2.18",
        draw="3.91",
        away="2.81",
    )
    analysis = AnalysisResult(
        fixture_id=1623430,
        home_team_name="圣加仑",
        away_team_name="北西兰",
        league_name="欧协联",
        fixture_date=datetime(2026, 8, 27, 18, tzinfo=timezone.utc),
        status="pending",
        home_win_prob=0.43,
        draw_prob=0.24,
        away_win_prob=0.33,
        confidence="中",
        recommendation="胜/平",
        data_source="database",
        analyzed_at=datetime.now(timezone.utc),
        package={"odds": current},
        goal_lean="大(3.25)",
        both_score_lean="双进:是",
        score_hint="比分:2-2/3-1",
        handicap_lean="让胜(-0.25)",
        leans_frozen=True,
    )
    response = analysis_to_response(analysis)
    assert response.market_analysis is not None
    assert response.market_analysis.available is True
    assert response.market_analysis.stage_count == 1
