"""用当前代码重放已完场快照，对比库里快照与当前口径的胜平负 / 比分命中率。

基准线是「无脑买去水后 1X2 最热门」，用来区分「算法坏了」与「当天爆冷」——
没有这条线，单看命中率下滑会把爆冷日误判成代码回归。只读本地库，不打官方 API。

用法：python scripts/replay_prediction_leans.py [起始比赛日]
"""

from __future__ import annotations

import collections
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.prediction import (
    derive_prediction_leans,
    implied_probs_from_odds,
    recommendation_outcomes,
)

DB = Path(__file__).resolve().parents[1] / "data" / "football.db"


def outcome(home_goals: int, away_goals: int) -> str:
    if home_goals > away_goals:
        return "home"
    if away_goals > home_goals:
        return "away"
    return "draw"


def score_hits(hint: str, home_goals: int, away_goals: int) -> bool | None:
    hint = (hint or "").strip()
    if not hint.startswith("比分:") or "待分析" in hint:
        return None
    return f"{home_goals}-{away_goals}" in hint.split(":", 1)[1].split("/")


def main() -> None:
    since = sys.argv[1] if len(sys.argv) > 1 else "2026-09-19"
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """
        select f.id, f.match_day, f.home_goals hg, f.away_goals ag,
               p.recommendation rec, p.score_hint, p.odds_json,
               p.home_win_prob, p.draw_prob, p.away_win_prob
        from fixtures f join pre_match_data p on p.fixture_id = f.id
        where f.home_goals is not null and f.away_goals is not null
          and f.match_day >= ?
        """,
        (since,),
    ).fetchall()

    stored = collections.defaultdict(lambda: [0, 0])
    replay = collections.defaultdict(lambda: [0, 0])
    stored_score = collections.defaultdict(lambda: [0, 0])
    replay_score = collections.defaultdict(lambda: [0, 0])
    # 基准线：无脑买去水后 1X2 最热门的一路。用来区分「算法坏了」与「当天爆冷」。
    baseline = collections.defaultdict(lambda: [0, 0])
    flipped: list[tuple] = []

    for row in rows:
        day = row["match_day"]
        actual = outcome(row["hg"], row["ag"])
        try:
            odds = json.loads(row["odds_json"] or "{}")
        except json.JSONDecodeError:
            continue
        probs = {
            "home": float(row["home_win_prob"] or 0),
            "draw": float(row["draw_prob"] or 0),
            "away": float(row["away_win_prob"] or 0),
        }
        if sum(probs.values()) <= 0:
            continue

        implied = implied_probs_from_odds(odds)
        if implied:
            baseline[day][1] += 1
            if max(implied, key=implied.get) == actual:
                baseline[day][0] += 1

        old_outs = recommendation_outcomes(row["rec"] or "")
        if old_outs:
            stored[day][1] += 1
            if actual in old_outs:
                stored[day][0] += 1
        old_score = score_hits(row["score_hint"] or "", row["hg"], row["ag"])
        if old_score is not None:
            stored_score[day][1] += 1
            stored_score[day][0] += int(old_score)

        leans = derive_prediction_leans(probs, odds)
        new_outs = recommendation_outcomes(leans["recommendation"])
        if new_outs:
            replay[day][1] += 1
            if actual in new_outs:
                replay[day][0] += 1
        new_score = score_hits(leans["score_hint"], row["hg"], row["ag"])
        if new_score is not None:
            replay_score[day][1] += 1
            replay_score[day][0] += int(new_score)

        if old_outs and new_outs and old_outs != new_outs:
            flipped.append(
                (
                    row["id"],
                    row["rec"],
                    leans["recommendation"],
                    actual,
                    actual in old_outs,
                    actual in new_outs,
                )
            )

    def show(title: str, old: dict, new: dict) -> None:
        print(f"\n=== {title} ===")
        print("  比赛日        修复前          修复后")
        for day in sorted(set(old) | set(new)):
            oh, ot = old.get(day, [0, 0])
            nh, nt = new.get(day, [0, 0])
            o = f"{oh:3d}/{ot:3d} = {oh / ot:6.1%}" if ot else "     n/a    "
            n = f"{nh:3d}/{nt:3d} = {nh / nt:6.1%}" if nt else "     n/a    "
            print(f"  {day}  {o}   {n}")
        oh = sum(v[0] for v in old.values())
        ot = sum(v[1] for v in old.values())
        nh = sum(v[0] for v in new.values())
        nt = sum(v[1] for v in new.values())
        o = f"{oh:3d}/{ot:3d} = {oh / ot:6.1%}" if ot else "n/a"
        n = f"{nh:3d}/{nt:3d} = {nh / nt:6.1%}" if nt else "n/a"
        print(f"  合计        {o}   {n}")

    show("胜平负", stored, replay)
    show("比分", stored_score, replay_score)

    print("\n=== 基准线：无脑买 1X2 最热门（单选，不含双选） ===")
    for day in sorted(baseline):
        hit, total = baseline[day]
        print(f"  {day}  {hit:3d}/{total:3d} = {hit / total:6.1%}")
    bh = sum(v[0] for v in baseline.values())
    bt = sum(v[1] for v in baseline.values())
    print(f"  合计        {bh:3d}/{bt:3d} = {bh / bt:6.1%}")

    gained = sum(1 for f in flipped if f[5] and not f[4])
    lost = sum(1 for f in flipped if f[4] and not f[5])
    print(f"\n=== 方向发生变化 {len(flipped)} 场：修复后多对 {gained}、多错 {lost} ===")
    for fid, old_rec, new_rec, actual, old_ok, new_ok in flipped:
        print(
            f"  {fid}  {old_rec:>7} {'√' if old_ok else '×'}"
            f"  ->  {new_rec:>7} {'√' if new_ok else '×'}   实际 {actual}"
        )


if __name__ == "__main__":
    main()
