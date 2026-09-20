"""Deterministic detail-page explanation from persisted pre-match odds stages."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import re

from app.services.ah_features import (
    format_ah_line,
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
_OUTCOME_LABELS = {"home": "主队赢", "draw": "打平", "away": "客队赢"}


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


def _plain_handicap(line: float, *, home_side: bool) -> str:
    """把 -0.25 这种盘口写成「让 0.25 球」，用户不必先懂正负号。"""
    size = abs(line)
    if size < 1e-9:
        return "平手"
    gives = line < 0 if home_side else line > 0
    return f"{'让' if gives else '受让'} {size:g} 球"


def _plain_lean(lean: str, line: float | None) -> str:
    """给「让胜(-0.25)」这类术语补一句白话，术语本身仍按全站口径保留。"""
    pick = handicap_pick_from_lean(lean)
    if line is None or pick not in {"让胜", "让负"}:
        return ""
    if re.search(r"[主客][+-]?(?:\d+(?:\.\d+)?)", lean or ""):
        return ""
    home_side = pick == "让胜"
    team = "主队" if home_side else "客队"
    return f"，也就是买{team}（{_plain_handicap(line, home_side=home_side)}）"


def _settlement_note(line: float) -> str:
    """只有真会出现半输半赢或退钱的盘口才多说一句，0.5 这种直接不提。"""
    units = outcome_settlement_units(line, "让胜") or {}
    values = units.values()
    if any(abs(unit - 0.5) < 1e-9 or abs(unit + 0.5) < 1e-9 for unit in values):
        return "这种盘口可能只赢一半或只亏一半，上面的账已经算上了。"
    if any(abs(unit) < 1e-9 for unit in values):
        return "这种盘口踢平会把钱退给你，上面的账已经算上了。"
    return ""


def _per_hundred(expected_return: float) -> str:
    """把期望收益换成「每投 100 元赚/亏多少」，比百分比直观。"""
    amount = abs(expected_return) * 100
    if amount < 0.05:
        return "长期下来基本打平"
    return f"平均每投 100 元{'赚' if expected_return > 0 else '亏'} {amount:.1f} 元"


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
        "按最新赔率折算（已经扣掉博彩公司的抽成）："
        f"主队赢 {_pct(current['home'])}、打平 {_pct(current['draw'])}、"
        f"客队赢 {_pct(current['away'])}，也就是市场眼下最看好{_OUTCOME_LABELS[top]}。"
    )
    outcomes = recommendation_outcomes(recommendation)
    if outcomes:
        relation = "里面包含了" if top in outcomes else "里面没有"
        bullets.append(
            f"和算法比：算法给的是「{recommendation}」，"
            f"{relation}市场最看好的{_OUTCOME_LABELS[top]}。"
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
        warnings.append(
            "胜平负的初盘和即时盘来自两家不同的博彩公司，价格不能直接比，"
            "所以没有把差异当成行情变化来讲。"
        )
        return
    deltas = {key: current[key] - opening[key] for key in _OUTCOMES}
    moved = max(_OUTCOMES, key=lambda key: abs(deltas[key]))
    bullets.append(
        f"开盘到现在变化最大的是「{_OUTCOME_LABELS[moved]}」："
        f"从 {_pct(opening[moved])} 变成 {_pct(current[moved])}（同一家博彩公司）。"
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
        warnings.append(
            "让球盘中途换过博彩公司，下面只用和最新报价来自同一家的记录。"
        )
    path = _line_path(stages, "asian_handicap")
    if path:
        bullets.append(f"让球盘怎么走的：{_format_line_path(path)}。")
    opening_market = (
        _market(opening_board, "asian_handicap") if opening_board is not None else None
    )
    comparable = opening_market is not None and _same_book(opening_market, current)
    if len(path) >= 2 and comparable:
        delta = path[-1][1] - path[0][1]
        if delta < -1e-9:
            paragraphs.append(
                "和最早的盘口比，主队要让的球变多了，说明市场比开盘时更看好主队。"
            )
        elif delta > 1e-9:
            paragraphs.append(
                "和最早的盘口比，主队要让的球变少了，说明市场比开盘时更看好客队。"
            )
        else:
            paragraphs.append(
                "让球的球数从开盘到现在没变过，看方向得再对比同一档位的赔率。"
            )

    if opening_board is not None:
        opening = opening_market
        if opening is not None:
            consensus = _common_line_consensus(opening, current)
            if consensus is None and not _same_book(opening, current):
                warnings.append(
                    "让球的初盘和即时盘来自两家不同的博彩公司，没有把两边的赔率直接连起来看。"
                )
            elif consensus is not None:
                common, home_up, away_up = consensus
                if home_up > away_up and home_up > 0:
                    paragraphs.append(
                        f"同一家博彩公司有 {common} 个让球档位可以对比，"
                        f"其中 {home_up} 档主队的赢面明显变高，方向一致偏向主队。"
                    )
                elif away_up > home_up and away_up > 0:
                    paragraphs.append(
                        f"同一家博彩公司有 {common} 个让球档位可以对比，"
                        f"其中 {away_up} 档客队的赢面明显变高，方向一致偏向客队。"
                    )
                else:
                    bullets.append(
                        f"{common} 个让球档位可以对比，两边涨跌互现，看不出明显偏向。"
                    )

    line = _line(current.get("line"))
    if handicap_lean:
        bullets.append(
            f"算法在让球上的选择：{handicap_lean}{_plain_lean(handicap_lean, line)}。"
        )
    if handicap_market_note:
        bullets.append(f"为什么这么选：{handicap_market_note}。")

    home_odd, away_odd = _odd(current.get("home")), _odd(current.get("away"))
    if line is None or home_odd is None or away_odd is None:
        return
    home_ev = _ah_expected_return(probabilities, line, "让胜", home_odd)
    away_ev = _ah_expected_return(probabilities, line, "让负", away_odd)
    if home_ev is None or away_ev is None:
        return
    settlement = _settlement_note(line)
    bullets.append(
        "按我们的概率和现在的赔率长期估算："
        f"买主队（{_plain_handicap(line, home_side=True)}）{_per_hundred(home_ev)}，"
        f"买客队（{_plain_handicap(line, home_side=False)}）{_per_hundred(away_ev)}。"
        + (f"{settlement}" if settlement else "")
    )
    if home_ev <= 0 and away_ev <= 0:
        paragraphs.append(
            "两边长期算下来都是亏的：盘口能看出方向，不代表现在这个价格值得买。"
        )
    elif home_ev > away_ev:
        paragraphs.append("同样这么算，买主队这一边比买客队划算。")
    else:
        paragraphs.append("同样这么算，买客队这一边比买主队划算。")


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
        warnings.append(
            "大小球中途换过博彩公司，下面只用和最新报价来自同一家的记录。"
        )
    path = _line_path(stages, "goals_ou")
    if path:
        bullets.append(f"大小球怎么走的：{_format_line_path(path, signed=False)}。")
    opening_market = (
        _market(opening_board, "goals_ou") if opening_board is not None else None
    )
    comparable = opening_market is not None and _same_book(opening_market, current)
    if len(path) >= 2 and comparable:
        delta = path[-1][1] - path[0][1]
        if delta > 1e-9:
            paragraphs.append("大小球盘口比开盘时抬高了。")
        elif delta < -1e-9:
            paragraphs.append("大小球盘口比开盘时降低了。")

    if opening_board is not None:
        opening = opening_market
        if opening is not None and not _same_book(opening, current):
            warnings.append(
                "大小球的初盘和即时盘来自两家不同的博彩公司，没有把两边的赔率直接连起来看。"
            )
        elif opening is not None:
            consensus = _common_line_consensus(opening, current)
            if consensus is not None:
                common, over_up, under_up = consensus
                if over_up > under_up and over_up > 0:
                    bullets.append(
                        f"{common} 个大小球档位可以对比，其中 {over_up} 档买「大」的赢面变高了。"
                    )
                elif under_up > over_up and under_up > 0:
                    bullets.append(
                        f"{common} 个大小球档位可以对比，其中 {under_up} 档买「小」的赢面变高了。"
                    )
    fair = _fair_two(current.get("home"), current.get("away"))
    if fair is not None:
        bullets.append(f"按最新赔率折算：大 {_pct(fair[0])} / 小 {_pct(fair[1])}。")
    if goal_lean:
        bullets.append(f"算法在大小球上的选择：{goal_lean}。")


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
            "paragraphs": ["还没拿到这场的盘口，暂时讲不了赔率怎么变。"],
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
    bullets.append(
        f"下面用到 {len(stages)} 个时间点的盘口：{labels}；同一次抓取只算一次。"
    )

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
        warnings.append("这场还没有单独的最新报价，下面用的是目前能拿到的最近一份盘口。")
    return {
        "available": True,
        "title": "盘口解释",
        "paragraphs": paragraphs
        or ["拿到了盘口，但胜平负、让球、大小球的数据都不全，讲不出结论。"],
        "bullets": bullets,
        "warnings": list(dict.fromkeys(warnings)),
        "stage_count": len(stages),
    }
