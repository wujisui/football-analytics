from datetime import datetime, timezone

from app.schemas.response import analysis_to_response
from app.services.analyzer import AnalysisResult
from app.services.market_analysis import (
    build_market_analysis,
    handicap_direction_signal,
)


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
                {"line": "0", "home": "1.82" if role == "initial" else "1.68", "away": "1.99" if role == "initial" else "2.18"},
                {"line": "-0.25", "home": "2.09" if role == "initial" else ah_home, "away": "1.72" if role == "initial" else ah_away},
                {"line": "-0.5", "home": "2.34" if role == "initial" else "2.17", "away": "1.56" if role == "initial" else "1.69"},
            ],
        },
        "goals_ou": {
            "bookmaker": bookmaker,
            "line": ou_line,
            "home": ou_home,
            "away": ou_away,
            "lines": [
                {"line": "3.0", "home": "1.96" if role == "initial" else "1.64", "away": "1.83" if role == "initial" else "2.25"},
                {"line": "3.25", "home": "2.20" if role == "initial" else ou_home, "away": "1.64" if role == "initial" else ou_away},
            ],
        },
    }


def test_four_stage_analysis_uses_real_line_and_probability_movement() -> None:
    opening = _board(
        "2026-08-26T08:00:00+00:00",
        role="initial",
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
    assert "主队要让的球变多了" in text
    assert "方向一致偏向主队" in text
    assert "大小球怎么走的：初盘 3 → 临场 3.25" in text


    assert "大小球盘口比开盘时抬高了" in text
    assert "两边长期算下来都是亏的" in text
    # 白话口径：不要再把术语推给用户。
    assert "去水" not in text
    assert "期望" not in text
    assert "共振" not in text
    assert "庄家" not in text
    # 本来就好懂的词不要再夹注。
    assert "最早开出的报价" not in text
    assert "带减号" not in text
    assert "进球偏" not in text


def test_handicap_direction_signal_marks_unanimous_multi_line_move_strong() -> None:
    opening = _board(
        "2026-08-26T08:00:00+00:00",
        role="initial",
        ah_line="-0.75",
        ah_home="1.90",
        ah_away="1.90",
        ou_line="2.5",
        ou_home="1.90",
        ou_away="1.90",
        home="2.0",
        draw="3.4",
        away="4.0",
    )
    current = _board(
        "2026-08-27T17:00:00+00:00",
        role="current",
        ah_line="-0.5",
        ah_home="2.10",
        ah_away="1.75",
        ou_line="2.5",
        ou_home="1.90",
        ou_away="1.90",
        home="2.0",
        draw="3.4",
        away="4.0",
    )
    opening["asian_handicap"]["lines"] = [
        {"line": str(line), "home": "1.90", "away": "1.90"}
        for line in (-1, -0.75, -0.5, -0.25, 0, 0.25)
    ]
    current["asian_handicap"]["lines"] = [
        {"line": str(line), "home": "2.10", "away": "1.75"}
        for line in (-1, -0.75, -0.5, -0.25, 0, 0.25)
    ]

    signal = handicap_direction_signal(
        {"odds_opening": opening, "odds": current}
    )

    assert signal.direction == "away"
    assert signal.strength == "strong"
    assert signal.line_direction == "away"
    assert signal.common_lines == 6
    assert signal.away_up == 6


def test_handicap_value_is_phrased_as_money_per_hundred() -> None:
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
        {"odds": current},
        probabilities={"home": 0.43, "draw": 0.24, "away": 0.33},
        recommendation="胜/平",
        handicap_lean="让胜(-0.25)",
    )

    text = "\n".join([*result["paragraphs"], *result["bullets"]])
    assert "买主队（让 0.25 球）" in text
    assert "买客队（受让 0.25 球）" in text
    assert "平均每投 100 元" in text
    # 全站沿用「让胜/让负」标签，但解释里必须跟一句白话。
    assert "让胜(-0.25)，也就是买主队（让 0.25 球）" in text
    # 0.25 会半输半赢，说清楚；但不要再用「赢一半、输一半和打平退钱」这种缩写。
    assert "这种盘口可能只赢一半或只亏一半，上面的账已经算上了。" in text


def test_settlement_note_only_appears_when_the_line_can_split_or_refund() -> None:
    def value_bullet(ah_line: str, ah_home: str, ah_away: str) -> str:
        board = _board(
            "2026-08-27T17:00:00+00:00",
            role="current",
            ah_line=ah_line,
            ah_home=ah_home,
            ah_away=ah_away,
            ou_line="3.25",
            ou_home="1.86",
            ou_away="1.95",
            home="2.18",
            draw="3.91",
            away="2.81",
        )
        result = build_market_analysis(
            {"odds": board},
            probabilities={"home": 0.43, "draw": 0.24, "away": 0.33},
        )
        return next(b for b in result["bullets"] if "长期估算" in b)

    assert "只赢一半或只亏一半" in value_bullet("-0.25", "1.94", "1.89")
    assert "踢平会把钱退给你" in value_bullet("0", "1.90", "1.95")
    # 半球盘只有赢或输，不该硬塞一句结算说明。
    half_ball = value_bullet("-0.5", "2.06", "1.84")
    assert "只赢一半" not in half_ball
    assert "退给你" not in half_ball


def test_leans_keep_their_tag_but_gain_a_plain_reading() -> None:
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
        {"odds": current},
        probabilities={"home": 0.43, "draw": 0.24, "away": 0.33},
        recommendation="胜/平",
        handicap_lean="让负(-0.25)",
        goal_lean="小(3.25)",
    )

    text = "\n".join(result["bullets"])
    assert "让负(-0.25)，也就是买客队（受让 0.25 球）" in text
    assert "算法在大小球上的选择：小(3.25)。" in text
    assert "进球偏" not in text


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
        {"odds_opening": {**current, "role": "initial"}, "odds": current},
        probabilities={"home": 0.43, "draw": 0.24, "away": 0.33},
        recommendation="胜/平",
        handicap_lean="让胜(-0.25)",
    )
    text = "\n".join([*result["paragraphs"], *result["bullets"]])
    assert result["stage_count"] == 1
    assert "用到 1 个时间点的盘口" in text
    assert "比开盘时" not in text


def test_bookmaker_swap_is_reported_but_not_called_a_market_move() -> None:
    opening = _board(
        "2026-08-26T08:00:00+00:00",
        role="initial",
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
    assert "主队要让的球变多了" not in text
    assert any("两家不同的博彩公司" in warning for warning in result["warnings"])


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
