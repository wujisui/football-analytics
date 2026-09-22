"""总进球类玩法的方向口径对比：现行启发式 vs 跟盘口低水侧 vs 恒定基线。只读本地库。

大小球与双进共用一套「取哪一侧」的问题，因此共用一个脚本：加载、计数、训练/留出
分段与打印都只有一份，各玩法只提供「怎么读盘口」「怎么结算」两个小函数。

用法：python scripts/backtest_goal_side.py [起始比赛日]
"""

from __future__ import annotations

import collections
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.prediction import (
    _odd_float,
    _parse_goal_lean,
    _parse_ou_line,
    asian_result_counts_as_hit,
    settle_asian_total,
)

DB = Path(__file__).resolve().parents[1] / "data" / "football.db"
HOLDOUT_SHARE = 0.2


def _ou_case(odds: dict, stored_lean: str, hg: int, ag: int) -> dict | None:
    """大小球：低水侧即市场判大 / 判小；结算按亚洲盘含走水。"""
    board = odds.get("goals_ou")
    if not isinstance(board, dict):
        return None
    over_odd = _odd_float(board.get("home"))
    under_odd = _odd_float(board.get("away"))
    line = _parse_ou_line(board.get("line"))
    if over_odd is None or under_odd is None or line is None:
        return None
    total = hg + ag

    def settle(pick_over: bool, at_line: float) -> bool | None:
        return asian_result_counts_as_hit(
            settle_asian_total(total, at_line, over=pick_over)
        )

    parsed = _parse_goal_lean(stored_lean or "")
    return {
        "stored": (
            settle(parsed[0] == "over", parsed[1]) if parsed is not None else None
        ),
        "stored_positive": None if parsed is None else parsed[0] == "over",
        "market": (
            settle(over_odd < under_odd, line) if over_odd != under_odd else None
        ),
        "market_positive": None if over_odd == under_odd else over_odd < under_odd,
        "always_yes": settle(True, line),
        "always_no": settle(False, line),
    }


def _btts_case(odds: dict, stored_lean: str, hg: int, ag: int) -> dict | None:
    """双进：报价 home=是 / away=否；二元结算，没有走水。"""
    board = odds.get("both_teams_score")
    if not isinstance(board, dict):
        return None
    yes_odd = _odd_float(board.get("home"))
    no_odd = _odd_float(board.get("away"))
    if yes_odd is None or no_odd is None:
        return None
    both_scored = hg > 0 and ag > 0

    lean = (stored_lean or "").strip()
    stored_yes = "是" in lean if ("是" in lean or "否" in lean) else None
    market_yes = None if yes_odd == no_odd else yes_odd < no_odd
    return {
        "stored": None if stored_yes is None else stored_yes is both_scored,
        "stored_positive": stored_yes,
        "market": None if market_yes is None else market_yes is both_scored,
        "market_positive": market_yes,
        "always_yes": both_scored,
        "always_no": not both_scored,
    }


MARKETS = {
    "大小球": {
        "lean_column": "goal_lean",
        "case": _ou_case,
        "labels": {"always_yes": "恒买大", "always_no": "恒买小"},
        "positive": "判大占比",
    },
    "双进": {
        "lean_column": "both_score_lean",
        "case": _btts_case,
        "labels": {"always_yes": "恒买是", "always_no": "恒买否"},
        "positive": "判是占比",
    },
}
STRATEGIES = ("stored", "market", "always_yes", "always_no")


def _report(title: str, cases: list[dict], labels: dict[str, str], positive: str) -> None:
    names = {
        "stored": "现行启发式",
        "market": "跟盘口低水侧",
        "always_yes": labels["always_yes"],
        "always_no": labels["always_no"],
    }
    tally: dict[str, list[int]] = collections.defaultdict(lambda: [0, 0])
    share: dict[str, list[int]] = collections.defaultdict(lambda: [0, 0])
    for case in cases:
        for key in STRATEGIES:
            hit = case.get(key)
            if hit is not None:
                tally[key][1] += 1
                tally[key][0] += int(hit)
        for key in ("stored", "market"):
            flag = case.get(f"{key}_positive")
            if flag is not None:
                share[key][1] += 1
                share[key][0] += int(flag)

    print(f"  {title}（{len(cases)} 场）")
    print(f"    口径                命中            {positive}")
    for key in STRATEGIES:
        hit, total = tally[key]
        if not total:
            continue
        got = share.get(key)
        share_text = f"{got[0] / got[1]:6.1%}" if got and got[1] else "   n/a"
        print(
            f"    {names[key]:<12}  {hit:4d}/{total:4d} = {hit / total:6.1%}"
            f"   {share_text}"
        )


def main() -> None:
    since = sys.argv[1] if len(sys.argv) > 1 else "2026-08-01"
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """
        select f.match_day, f.home_goals hg, f.away_goals ag,
               p.goal_lean, p.both_score_lean, p.odds_json
        from fixtures f join pre_match_data p on p.fixture_id = f.id
        where f.home_goals is not null and f.away_goals is not null
          and f.match_day >= ?
        order by f.match_day, f.id
        """,
        (since,),
    ).fetchall()

    for title, spec in MARKETS.items():
        cases: list[dict] = []
        for row in rows:
            try:
                odds = json.loads(row["odds_json"] or "{}")
            except json.JSONDecodeError:
                continue
            case = spec["case"](odds, row[spec["lean_column"]], row["hg"], row["ag"])
            if case is not None:
                cases.append(case)

        # 时间留出：只看训练段会把噪声当增益，本项目已多次踩过。
        split = int(len(cases) * (1 - HOLDOUT_SHARE))
        print(f"=== {title}方向口径对比（{since} 起） ===")
        _report("全部", cases, spec["labels"], spec["positive"])
        if split and split < len(cases):
            _report("训练段 80%", cases[:split], spec["labels"], spec["positive"])
            _report("留出段 20%", cases[split:], spec["labels"], spec["positive"])
        print()


if __name__ == "__main__":
    main()
