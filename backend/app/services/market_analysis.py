"""Deterministic detail-page explanation from persisted pre-match odds stages."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.ah_features import (
    format_ah_line,
    handicap_line_from_lean,
    handicap_pick_from_lean,
    outcome_settlement_units,
)
from app.services.prediction import recommendation_outcomes

_STAGES = (
    ("odds_opening", "初盘"),
    ("odds_mid", "中盘"),
    ("odds_late", "临场"),
    ("odds", "即时盘"),
)
_OUTCOMES = ("home", "draw", "away")
_OUTCOME_LABELS = {"home": "主胜", "draw": "平局", "away": "客胜"}


def _odd(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 1.0 else None


def _line(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _signed_pp(value: float) -> str:
    return f"{value * 100:+.1f} 个百分点"


def _captured_at(board: dict[str, Any]) -> datetime | None:
    raw = board.get("scraped_at") or board.get("captured_at")
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _available(board: Any) -> bool:
    return (
        isinstance(board, dict)
        and bool(board.get("available"))
        and board.get("is_live") is not True
        and board.get("valid") is not False
    )


def _stage_boards(package: dict[str, Any] | None) -> list[tuple[str, dict[str, Any]]]:
    """Return chronologically meaningful, capture-time-deduplicated stages."""
    pkg = package if isinstance(package, dict) else {}
    current = pkg.get("odds")
    current_time = _captured_at(current) if _available(current) else None
    candidates: list[tuple[str, dict[str, Any], datetime | None]] = []
    for key, label in _STAGES:
        board = pkg.get(key)
        if not _available(board):
            continue
        captured = _captured_at(board)
        # Legacy stage rows without clocks cannot establish a real sequence.
        if key != "odds" and (captured is None or current_time is None):
            continue
        if key != "odds" and current_time is not None and captured > current_time:
            continue
        candidates.append((label, board, captured))

    # A single refresh can be opening/mid/late/current simultaneously. Keep its
    # latest semantic role so one board is never described as movement.
    by_capture: dict[str, tuple[str, dict[str, Any], datetime | None]] = {}
    no_clock: list[tuple[str, dict[str, Any], datetime | None]] = []
    for item in candidates:
        if item[2] is None:
            no_clock.append(item)
        else:
            by_capture[item[2].isoformat()] = item
    distinct = [*by_capture.values(), *no_clock]
    distinct.sort(
        key=lambda item: (
            item[2] is None,
            item[2] or datetime.max,
            next(index for index, (_, label) in enumerate(_STAGES) if label == item[0]),
        )
    )
    return [(label, board) for label, board, _captured in distinct]


def _market(board: dict[str, Any], key: str) -> dict[str, Any] | None:
    value = board.get(key)
    return value if isinstance(value, dict) else None


def _same_book(first: dict[str, Any], second: dict[str, Any]) -> bool:
    first_book = str(first.get("bookmaker") or "").strip()
    second_book = str(second.get("bookmaker") or "").strip()
    return bool(first_book and second_book and first_book == second_book)


def _fair_two(home: Any, away: Any) -> tuple[float, float] | None:
    home_odd, away_odd = _odd(home), _odd(away)
    if home_odd is None or away_odd is None:
        return None
    home_raw, away_raw = 1.0 / home_odd, 1.0 / away_odd
    total = home_raw + away_raw
    return (home_raw / total, away_raw / total) if total > 0 else None


def _fair_1x2(market: dict[str, Any] | None) -> dict[str, float] | None:
    if not isinstance(market, dict):
        return None
    odds = {outcome: _odd(market.get(outcome)) for outcome in _OUTCOMES}
    if any(value is None for value in odds.values()):
        return None
    inverses = {key: 1.0 / float(value) for key, value in odds.items()}
    total = sum(inverses.values())
    if total <= 0:
        return None
    return {key: value / total for key, value in inverses.items()}


def _line_map(market: dict[str, Any] | None) -> dict[float, tuple[float, float]]:
    if not isinstance(market, dict):
        return {}
    rows = list(market.get("lines") or [])
    if not rows:
        rows = [market]
    mapped: dict[float, tuple[float, float]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        line = _line(row.get("line"))
        home, away = _odd(row.get("home")), _odd(row.get("away"))
        if line is not None and home is not None and away is not None:
            mapped[round(line, 4)] = (home, away)
    return mapped


def _line_path(
    stages: list[tuple[str, dict[str, Any]]],
    market_key: str,
) -> list[tuple[str, float]]:
    current_market = _market(stages[-1][1], market_key) if stages else None
    path: list[tuple[str, float]] = []
    for label, board in stages:
        market = _market(board, market_key)
        if (
            market is None
            or current_market is None
            or (market is not current_market and not _same_book(market, current_market))
        ):
            continue
        line = _line(market.get("line")) if market else None
        if line is not None and (not path or path[-1][1] != line):
            path.append((label, line))
    return path


def _format_line_path(
    path: list[tuple[str, float]],
    *,
    signed: bool = True,
) -> str:
    return " → ".join(
        f"{label} {format_ah_line(line) if signed else f'{line:g}'}"
        for label, line in path
    )


def _common_line_consensus(
    opening: dict[str, Any],
    current: dict[str, Any],
) -> tuple[int, int, int] | None:
    if not _same_book(opening, current):
        return None
    opening_lines, current_lines = _line_map(opening), _line_map(current)
    common = sorted(set(opening_lines) & set(current_lines))
    if not common:
        return None
    home_up = away_up = 0
    for line in common:
        opening_fair = _fair_two(*opening_lines[line])
        current_fair = _fair_two(*current_lines[line])
        if opening_fair is None or current_fair is None:
            continue
        delta = current_fair[0] - opening_fair[0]
        if delta >= 0.015:
            home_up += 1
        elif delta <= -0.015:
            away_up += 1
    return len(common), home_up, away_up


def _ah_expected_return(
    probabilities: dict[str, float],
    line: float,
    pick: str,
    odd: float,
) -> float | None:
    units = outcome_settlement_units(line, pick)
    if units is None:
        return None
    profit = odd - 1.0
    return sum(
        float(probabilities.get(outcome, 0.0))
        * (unit * profit if unit > 0 else unit)
        for outcome, unit in units.items()
    )


def _add_1x2_analysis(
    paragraphs: list[str],
    bullets: list[str],
    warnings: list[str],
    opening_board: dict[str, Any] | None,
    current_board: dict[str, Any],
    recommendation: str,
) -> None:
    current_market = _market(current_board, "match_winner")
    current = _fair_1x2(current_market)
    if current is None:
        return
    top = max(_OUTCOMES, key=current.get)
    paragraphs.append(
        "即时胜平负去水概率为"
        f"主 {_pct(current['home'])} / 平 {_pct(current['draw'])} / 客 {_pct(current['away'])}，"
        f"当前市场定价首先防范{_OUTCOME_LABELS[top]}。"
    )
    outcomes = recommendation_outcomes(recommendation)
    if outcomes:
        relation = "覆盖" if top in outcomes else "未覆盖"
        bullets.append(
            f"胜平负对照：算法「{recommendation}」{relation}市场概率最高的"
            f"「{_OUTCOME_LABELS[top]}」。"
        )

    if opening_board is None:
        return
    opening_market = _market(opening_board, "match_winner")
    opening = _fair_1x2(opening_market)
    if opening is None:
        return
    if not (
        isinstance(opening_market, dict)
        and isinstance(current_market, dict)
        and _same_book(opening_market, current_market)
    ):
        warnings.append("胜平负初盘与即时盘庄家不同，未把两者直接解释为概率走势。")
        return
    deltas = {key: current[key] - opening[key] for key in _OUTCOMES}
    moved = max(_OUTCOMES, key=lambda key: abs(deltas[key]))
    bullets.append(
        f"胜平负变化：{_OUTCOME_LABELS[moved]}去水概率变化"
        f"{_signed_pp(deltas[moved])}（同庄家初盘 → 即时盘）。"
    )


def _add_ah_analysis(
    paragraphs: list[str],
    bullets: list[str],
    warnings: list[str],
    stages: list[tuple[str, dict[str, Any]]],
    opening_board: dict[str, Any] | None,
    current_board: dict[str, Any],
    probabilities: dict[str, float],
    handicap_lean: str,
    handicap_market_note: str,
) -> None:
    current = _market(current_board, "asian_handicap")
    if current is None:
        return
    if any(
        market is not None and not _same_book(market, current)
        for _label, board in stages[:-1]
        if (market := _market(board, "asian_handicap")) is not None
    ):
        warnings.append("让球阶段中存在庄家切换，轨迹只保留与即时盘同庄家的快照。")
    path = _line_path(stages, "asian_handicap")
    if path:
        bullets.append(f"让球主盘轨迹：{_format_line_path(path)}。")
    opening_market = (
        _market(opening_board, "asian_handicap") if opening_board is not None else None
    )
    comparable = opening_market is not None and _same_book(opening_market, current)
    if len(path) >= 2 and comparable:
        delta = path[-1][1] - path[0][1]
        if delta < -1e-9:
            paragraphs.append("让球主盘相对初盘向主队方向升盘，市场定价较早盘更支持主队。")
        elif delta > 1e-9:
            paragraphs.append("让球主盘相对初盘向客队方向退盘，市场定价较早盘更支持客队。")
        else:
            paragraphs.append("让球主盘档位未变，方向判断需结合相同档位的去水概率。")

    if opening_board is not None:
        opening = opening_market
        if opening is not None:
            consensus = _common_line_consensus(opening, current)
            if consensus is None and not _same_book(opening, current):
                warnings.append("让球初盘与即时盘庄家不同，未直接串联同档水位。")
            elif consensus is not None:
                common, home_up, away_up = consensus
                if home_up > away_up and home_up > 0:
                    paragraphs.append(
                        f"同庄家共有 {common} 个让球档可比，其中 {home_up} 档"
                        "主队去水概率明显上升，形成主队方向共振。"
                    )
                elif away_up > home_up and away_up > 0:
                    paragraphs.append(
                        f"同庄家共有 {common} 个让球档可比，其中 {away_up} 档"
                        "客队去水概率明显上升，形成客队方向共振。"
                    )
                else:
                    bullets.append(
                        f"让球同档比较：共有 {common} 档可比，未形成明显单边共振。"
                    )

    if handicap_lean:
        bullets.append(f"算法让球倾向：{handicap_lean}。")
    if handicap_market_note:
        bullets.append(f"倾向说明：{handicap_market_note}。")

    line = _line(current.get("line"))
    home_odd, away_odd = _odd(current.get("home")), _odd(current.get("away"))
    if line is None or home_odd is None or away_odd is None:
        return
    home_ev = _ah_expected_return(probabilities, line, "让胜", home_odd)
    away_ev = _ah_expected_return(probabilities, line, "让负", away_odd)
    if home_ev is None or away_ev is None:
        return
    bullets.append(
        f"让球价值：让胜({format_ah_line(line)}) {_pct(home_ev)}，"
        f"让负({format_ah_line(line)}) {_pct(away_ev)}；已计入赢半、输半与走水返还。"
    )
    if home_ev <= 0 and away_ev <= 0:
        paragraphs.append("按当前概率与报价估算，让球两侧均为负期望：盘口有方向，不等于价格值得下注。")
    elif home_ev > away_ev:
        paragraphs.append("按当前概率与实际报价估算，让胜侧的风险收益优于让负侧。")
    else:
        paragraphs.append("按当前概率与实际报价估算，让负侧的风险收益优于让胜侧。")


def _add_ou_analysis(
    paragraphs: list[str],
    bullets: list[str],
    warnings: list[str],
    stages: list[tuple[str, dict[str, Any]]],
    opening_board: dict[str, Any] | None,
    current_board: dict[str, Any],
    goal_lean: str,
) -> None:
    current = _market(current_board, "goals_ou")
    if current is None:
        return
    if any(
        market is not None and not _same_book(market, current)
        for _label, board in stages[:-1]
        if (market := _market(board, "goals_ou")) is not None
    ):
        warnings.append("大小球阶段中存在庄家切换，轨迹只保留与即时盘同庄家的快照。")
    path = _line_path(stages, "goals_ou")
    if path:
        bullets.append(f"大小球主盘轨迹：{_format_line_path(path, signed=False)}。")
    opening_market = (
        _market(opening_board, "goals_ou") if opening_board is not None else None
    )
    comparable = opening_market is not None and _same_book(opening_market, current)
    if len(path) >= 2 and comparable:
        delta = path[-1][1] - path[0][1]
        if delta > 1e-9:
            paragraphs.append("大小球主盘较初盘升高，市场对总进球数的定价上调。")
        elif delta < -1e-9:
            paragraphs.append("大小球主盘较初盘降低，市场对总进球数的定价下调。")

    if opening_board is not None:
        opening = opening_market
        if opening is not None and not _same_book(opening, current):
            warnings.append("大小球初盘与即时盘庄家不同，未直接串联同档水位。")
        elif opening is not None:
            consensus = _common_line_consensus(opening, current)
            if consensus is not None:
                common, over_up, under_up = consensus
                if over_up > under_up and over_up > 0:
                    bullets.append(
                        f"大小球同档比较：{common} 档可比，{over_up} 档大球去水概率明显上升。"
                    )
                elif under_up > over_up and under_up > 0:
                    bullets.append(
                        f"大小球同档比较：{common} 档可比，{under_up} 档小球去水概率明显上升。"
                    )
    fair = _fair_two(current.get("home"), current.get("away"))
    if fair is not None:
        bullets.append(f"即时大小球去水概率：大 {_pct(fair[0])} / 小 {_pct(fair[1])}。")
    if goal_lean:
        bullets.append(f"算法大小球倾向：{goal_lean}。")


def build_market_analysis(
    package: dict[str, Any] | None,
    *,
    probabilities: dict[str, float] | None = None,
    recommendation: str = "",
    handicap_lean: str = "",
    handicap_market_note: str = "",
    goal_lean: str = "",
) -> dict[str, Any]:
    """Build source-of-truth market explanation for the detail response."""
    stages = _stage_boards(package)
    if not stages:
        return {
            "available": False,
            "title": "盘口解释",
            "paragraphs": ["暂无可用盘口快照，无法形成盘口走势解释。"],
            "bullets": [],
            "warnings": [],
            "stage_count": 0,
        }

    paragraphs: list[str] = []
    bullets: list[str] = []
    warnings: list[str] = []
    current_label, current = stages[-1]
    opening = stages[0][1] if len(stages) > 1 else None
    labels = " → ".join(label for label, _board in stages)
    bullets.append(f"有效盘口阶段：{labels}（按采集时间去重，共 {len(stages)} 个）。")

    _add_1x2_analysis(
        paragraphs,
        bullets,
        warnings,
        opening,
        current,
        recommendation,
    )
    _add_ah_analysis(
        paragraphs,
        bullets,
        warnings,
        stages,
        opening,
        current,
        probabilities or {},
        handicap_lean,
        handicap_market_note,
    )
    _add_ou_analysis(
        paragraphs,
        bullets,
        warnings,
        stages,
        opening,
        current,
        goal_lean,
    )
    if current_label != "即时盘":
        warnings.append("缺少独立即时盘，解释使用当前可用的最近阶段。")
    return {
        "available": True,
        "title": "盘口解释",
        "paragraphs": paragraphs or ["盘口快照可用，但核心玩法数据不足。"],
        "bullets": bullets,
        "warnings": list(dict.fromkeys(warnings)),
        "stage_count": len(stages),
    }
