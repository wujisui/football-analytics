"""浅盘让球「信心」口径对比：1X2 推算 vs 让球盘去水。只读本地库。

同一批浅盘（``|让球线| <= 0.5``）、同一个投注侧（``bettable_side``，即低水侧），
只换算概率的来源，比较谁更会排序、谁的闸更有效：

* ``1X2 推算``   —— 现行 ``_ah_side_probability`` 浅盘分支：拿 1X2 去水概率按
  退半 / 走水结算单位加权，得到条件命中率。全程不碰让球水位。
* ``让球盘去水`` —— 直接对主盘两侧报价去水，即现行深盘分支的兜底口径。

用法：python scripts/backtest_ah_confidence.py [起始比赛日]
"""

from __future__ import annotations

import json
import math
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.ah_features import (
    asian_result_counts_as_hit,
    extract_main_ah_line,
    outcome_settlement_units,
    settle_handicap_pick,
)
from app.services.ah_market_structure import bettable_side, classify_ah_board
from app.services.prediction import _odd_float

DB = Path(__file__).resolve().parents[1] / "data" / "football.db"
GATES = (0.50, 0.53, 0.55, 0.58)
SOURCES = ("1X2 推算", "让球盘去水")


def devig_1x2(odds: dict) -> dict[str, float] | None:
    mw = odds.get("match_winner")
    if not isinstance(mw, dict):
        return None
    quotes = {key: _odd_float(mw.get(key)) for key in ("home", "draw", "away")}
    if any(q is None or q <= 1.0 for q in quotes.values()):
        return None
    inv = {key: 1.0 / q for key, q in quotes.items()}
    total = sum(inv.values())
    return {key: value / total for key, value in inv.items()}


def prob_from_1x2(odds: dict, line: float, pick: str) -> float | None:
    """Current shallow branch: 1X2 de-vig weighted by AH settlement units."""
    units = outcome_settlement_units(line, pick)
    probs = devig_1x2(odds)
    if units is None or probs is None:
        return None
    won = sum(probs[k] * u for k, u in units.items() if u > 0)
    lost = sum(probs[k] * -u for k, u in units.items() if u < 0)
    at_risk = won + lost
    return None if at_risk <= 0 else won / at_risk


def prob_from_ah(home_odd: float, away_odd: float, side: str) -> float:
    inv_home, inv_away = 1.0 / home_odd, 1.0 / away_odd
    inv_side = inv_home if side == "home" else inv_away
    return inv_side / (inv_home + inv_away)


def collect(since: str) -> list[dict]:
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """
        select f.match_day, f.home_goals hg, f.away_goals ag, p.odds_json
        from fixtures f join pre_match_data p on p.fixture_id = f.id
        where f.home_goals is not null and f.away_goals is not null
          and f.match_day >= ?
        order by f.match_day
        """,
        (since,),
    ).fetchall()

    samples: list[dict] = []
    for row in rows:
        try:
            odds = json.loads(row["odds_json"] or "{}")
        except json.JSONDecodeError:
            continue
        line, home_odd, away_odd = extract_main_ah_line(odds)
        if line is None or home_odd is None or away_odd is None:
            continue
        # Shallow only: this is exactly the range where the current code
        # abandons the AH board and reconstructs the number from 1X2.
        if abs(line) > 0.5 + 1e-9:
            continue
        stance = classify_ah_board(odds)
        if stance is None or stance.even:
            continue
        side = bettable_side(stance)
        if side not in {"home", "away"}:
            continue
        pick = "让胜" if side == "home" else "让负"
        hit = asian_result_counts_as_hit(
            settle_handicap_pick(row["hg"], row["ag"], line, pick)
        )
        if hit is None:
            continue
        p_1x2 = prob_from_1x2(odds, line, pick)
        if p_1x2 is None:
            continue

        # Same board, the other side: lets us ask whether the water-chosen side
        # is also the side with the higher conditional hit rate.
        other = "away" if side == "home" else "home"
        other_pick = "让胜" if other == "home" else "让负"
        other_hit = asian_result_counts_as_hit(
            settle_handicap_pick(row["hg"], row["ag"], line, other_pick)
        )
        other_p_1x2 = prob_from_1x2(odds, line, other_pick)

        samples.append(
            {
                "match_day": row["match_day"],
                "y": int(hit),
                "1X2 推算": p_1x2,
                "让球盘去水": prob_from_ah(home_odd, away_odd, side),
                "other_y": None if other_hit is None else int(other_hit),
                "other_p_1x2": other_p_1x2,
                "odd": home_odd if side == "home" else away_odd,
            }
        )
    return samples


def score_function_report(samples: list[dict], title: str = "全样本") -> None:
    """``p × (赔率-1) ** 0.5`` peaks at 赔率 = 2.00 — the thinnest board there is.

    On a shallow AH the bet side is the low-water side, so a quote near 2.00 means
    the water gap has almost vanished. If hit rate falls as the quote approaches
    2.00, the ranking score is systematically shopping for the weakest boards.
    """
    print(f"\n=== 按所投一侧赔率分桶 · {title}（水位越平赔率越接近 2.00） ===")
    buckets = [
        ("<=1.80  水位差大", lambda o: o <= 1.80),
        ("1.80~1.90", lambda o: 1.80 < o <= 1.90),
        ("1.90~1.95", lambda o: 1.90 < o <= 1.95),
        (">1.95   贴近平水", lambda o: o > 1.95),
    ]
    for name, test in buckets:
        kept = [s for s in samples if test(s["odd"])]
        if not kept:
            continue
        hit = sum(s["y"] for s in kept)
        avg_score = sum(
            s["1X2 推算"] * max(s["odd"] - 1.0, 0.0) ** 0.5 for s in kept
        ) / len(kept)
        print(
            f"  {name:<18} {hit:3d}/{len(kept):3d} = {hit / len(kept):6.1%}"
            f"   平均打分 {avg_score:.4f}"
        )

    # 规则「压低幂次会压平原始分差」只在跨赔率档比较时成立。同层内（让球对让球）
    # 赔率挤在 1.8~1.95，(赔率-1)**0.5 几乎是常数，压平分差的恰恰是现行幂次。
    # 反馈乘子范围 soft[0.75,1.25] × ema clamp 0.5，基础分跨度必须撑得住。
    print("  基础分跨度（同层内，跨度越小越容易被反馈乘子支配）")
    for label, exponent in (("e=0.5 现行", 0.5), ("e=0   纯概率", 0.0)):
        scores = [
            s["1X2 推算"] * max(s["odd"] - 1.0, 0.0) ** exponent for s in samples
        ]
        lo, hi = min(scores), max(scores)
        print(f"    {label}  [{lo:.4f}, {hi:.4f}]  极差 {hi / lo - 1:6.1%}")

    # Head-to-head: if a day could only keep one of two candidates, does the
    # score function keep the better one?
    ranked_by_score = sorted(
        samples,
        key=lambda s: s["1X2 推算"] * max(s["odd"] - 1.0, 0.0) ** 0.5,
        reverse=True,
    )
    ranked_by_prob = sorted(samples, key=lambda s: s["1X2 推算"], reverse=True)
    for label, ranked in (("按现行打分", ranked_by_score), ("按纯概率", ranked_by_prob)):
        top = ranked[: max(1, len(ranked) // 4)]
        hit = sum(s["y"] for s in top)
        print(f"  取前 25% · {label:<8} {hit:3d}/{len(top):3d} = {hit / len(top):6.1%}")


def side_rule_report(samples: list[dict], title: str) -> None:
    """Does picking the side by 1X2 conditional probability beat the water side?"""
    usable = [
        s
        for s in samples
        if s["other_y"] is not None and s["other_p_1x2"] is not None
    ]
    print(f"\n=== 选侧规则对比 · {title}（n={len(usable)}） ===")
    if not usable:
        return
    water = sum(s["y"] for s in usable)
    print(f"  按水位选侧（现行）      {water:3d}/{len(usable):3d} = {water / len(usable):6.1%}")

    by_prob = sum(
        s["y"] if s["1X2 推算"] >= s["other_p_1x2"] else s["other_y"] for s in usable
    )
    print(f"  按 1X2 条件命中率选侧  {by_prob:3d}/{len(usable):3d} = {by_prob / len(usable):6.1%}")

    flipped = sum(1 for s in usable if s["1X2 推算"] < s["other_p_1x2"])
    print(f"  两条规则选到不同侧：{flipped}/{len(usable)}")


def score_report(samples: list[dict], title: str) -> None:
    n = len(samples)
    print(f"\n=== {title}（n={n}） ===")
    if not n:
        return
    base = sum(s["y"] for s in samples) / n
    print(f"  不设闸的基准命中率：{base:6.1%}")
    print("  口径          Brier    log-loss")
    for src in SOURCES:
        brier = sum((s[src] - s["y"]) ** 2 for s in samples) / n
        ll = -sum(
            math.log(max(min(s[src], 1 - 1e-9), 1e-9) if s["y"] else max(min(1 - s[src], 1 - 1e-9), 1e-9))
            for s in samples
        ) / n
        print(f"  {src:<10}  {brier:.4f}   {ll:.4f}")

    print("  闸    " + "".join(f"{src:>20}" for src in SOURCES))
    for gate in GATES:
        cells = []
        for src in SOURCES:
            kept = [s for s in samples if s[src] >= gate]
            if kept:
                hit = sum(s["y"] for s in kept)
                cells.append(f"{hit:3d}/{len(kept):3d}={hit / len(kept):6.1%}")
            else:
                cells.append("            n/a")
        print(f"  {gate:.2f} " + "".join(f"{c:>20}" for c in cells))


def main() -> None:
    since = sys.argv[1] if len(sys.argv) > 1 else "2026-06-01"
    samples = collect(since)
    if not samples:
        print("没有可用的浅盘样本。")
        return
    score_report(samples, f"全样本（{since} 起）")

    # Time holdout: the last 30% of match days. Last round's 58% optimum was an
    # in-sample artifact, so any gate must be judged out of sample.
    cut = int(len(samples) * 0.7)
    score_report(samples[:cut], "时间留出 · 训练段（前 70%）")
    score_report(samples[cut:], "时间留出 · 留出段（后 30%）")

    side_rule_report(samples, f"全样本（{since} 起）")
    side_rule_report(samples[cut:], "留出段（后 30%）")
    score_function_report(samples, f"全样本（{since} 起）")
    score_function_report(samples[:cut], "训练段（前 70%）")
    score_function_report(samples[cut:], "留出段（后 30%）")

    disagree = [
        s for s in samples if (s["1X2 推算"] >= 0.53) != (s["让球盘去水"] >= 0.53)
    ]
    print(f"\n两种口径在 0.53 闸下取舍不同的场次：{len(disagree)}/{len(samples)}")


if __name__ == "__main__":
    main()
