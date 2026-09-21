"""大小球方向口径对比：当前启发式 vs 直接跟盘口 vs 恒大 / 恒小。只读本地库。

用法：python scripts/backtest_ou_side.py [起始比赛日]
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


def settle(total: int, line: float, over: bool) -> bool | None:
    return asian_result_counts_as_hit(settle_asian_total(total, line, over=over))


def main() -> None:
    since = sys.argv[1] if len(sys.argv) > 1 else "2026-08-01"
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """
        select f.match_day, f.home_goals hg, f.away_goals ag,
               p.goal_lean, p.odds_json
        from fixtures f join pre_match_data p on p.fixture_id = f.id
        where f.home_goals is not null and f.away_goals is not null
          and f.match_day >= ?
        """,
        (since,),
    ).fetchall()

    tally: dict[str, list[int]] = collections.defaultdict(lambda: [0, 0])
    over_share: dict[str, list[int]] = collections.defaultdict(lambda: [0, 0])

    for row in rows:
        try:
            odds = json.loads(row["odds_json"] or "{}")
        except json.JSONDecodeError:
            continue
        ou = odds.get("goals_ou")
        if not isinstance(ou, dict):
            continue
        over_odd = _odd_float(ou.get("home"))
        under_odd = _odd_float(ou.get("away"))
        line = _parse_ou_line(ou.get("line"))
        if over_odd is None or under_odd is None or line is None:
            continue
        total = row["hg"] + row["ag"]

        parsed = _parse_goal_lean(row["goal_lean"] or "")
        if parsed is not None:
            side, stored_line = parsed
            hit = settle(total, stored_line, over=side == "over")
            if hit is not None:
                tally["现行启发式"][1] += 1
                tally["现行启发式"][0] += int(hit)
            over_share["现行启发式"][1] += 1
            over_share["现行启发式"][0] += int(side == "over")

        if over_odd != under_odd:
            market_over = over_odd < under_odd
            hit = settle(total, line, over=market_over)
            if hit is not None:
                tally["跟盘口低水侧"][1] += 1
                tally["跟盘口低水侧"][0] += int(hit)
            over_share["跟盘口低水侧"][1] += 1
            over_share["跟盘口低水侧"][0] += int(market_over)

        for name, is_over in (("恒买大", True), ("恒买小", False)):
            hit = settle(total, line, over=is_over)
            if hit is not None:
                tally[name][1] += 1
                tally[name][0] += int(hit)

    print(f"=== 大小球方向口径对比（{since} 起） ===")
    print("  口径                命中            判大占比")
    for name in ("现行启发式", "跟盘口低水侧", "恒买大", "恒买小"):
        hit, total = tally[name]
        share = over_share.get(name)
        share_text = (
            f"{share[0] / share[1]:6.1%}" if share and share[1] else "   n/a"
        )
        if total:
            print(f"  {name:<12}  {hit:4d}/{total:4d} = {hit / total:6.1%}   {share_text}")


if __name__ == "__main__":
    main()
