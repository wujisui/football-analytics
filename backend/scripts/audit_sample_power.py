"""样本清单 + 日推 AH 门槛的时间留出验证。只读本地库，不打官方 API。

回答「数据够不够」：够不够取决于问的是哪个问题。识别口径错误（穿盘方向当胜负）
几乎不需要样本，调一个 3 个百分点的阈值需要上千条**同轨**样本。

用法：python scripts/audit_sample_power.py
"""

from __future__ import annotations

import math
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.ah_features import handicap_line_from_lean
from app.services.results_accuracy import settle_auto_pick_hit

DB = Path(__file__).resolve().parents[1] / "data" / "football.db"
CANDIDATE_GATES = [0.50, 0.51, 0.52, 0.53, 0.54, 0.55, 0.56, 0.58]


def grade(row: sqlite3.Row) -> bool | None:
    line = handicap_line_from_lean(row["lean"]) if row["market"] == "ah" else None
    return settle_auto_pick_hit(
        market=row["market"],
        lean=row["lean"],
        home_goals=row["hg"],
        away_goals=row["ag"],
        handicap_line=line,
    )


def wilson(hits: int, total: int) -> tuple[float, float]:
    """95% Wilson interval — honest about small n in a way ±1.96·SE is not."""
    if total <= 0:
        return (0.0, 1.0)
    z = 1.959964
    p = hits / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def required_n(baseline: float, lift: float) -> int:
    """Per-arm n to detect ``lift`` over ``baseline`` at 80% power, α=0.05."""
    p1, p2 = baseline, baseline + lift
    pbar = (p1 + p2) / 2
    numerator = (
        1.959964 * math.sqrt(2 * pbar * (1 - pbar))
        + 0.8416 * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))
    ) ** 2
    return math.ceil(numerator / (lift * lift))


def report_inventory(con: sqlite3.Connection) -> None:
    print("=== 样本清单：三条轨道各自多少可结算样本 ===")
    analyzer = con.execute(
        """
        select count(*) from fixtures f join pre_match_data p on p.fixture_id = f.id
        where f.status = 'finished' and f.home_goals is not null
        """
    ).fetchone()[0]
    print(f"  分析器预测（pre_match_data，完场）      {analyzer:5d}")

    rows = con.execute(
        """
        select s.market, s.lean, s.confidence, s.match_day,
               f.home_goals hg, f.away_goals ag
        from auto_pick_snapshots s join fixtures f on f.id = s.fixture_id
        where f.status = 'finished' and f.home_goals is not null
        """
    ).fetchall()
    settled = [r for r in rows if grade(r) is not None]
    print(f"  日推快照（auto_pick_snapshots，可结算） {len(settled):5d}")
    for market in ("ah", "1x2", "ou", "btts"):
        subset = [r for r in settled if r["market"] == market]
        print(f"    └─ {market:<4}                              {len(subset):5d}")
    print()
    print("  注意：分析器那 1000+ 条不能用来调日推门槛——日推只推 4 场/轮，")
    print("  绝大多数完场比赛从未进过推荐池，两条轨道的样本量差一个数量级。")


def report_power() -> None:
    print("\n=== 要把一个阈值调出统计显著，需要多少样本 ===")
    print("  （单臂 n，80% 检验力，α=0.05，基线 54%）")
    for lift in (0.10, 0.05, 0.03, 0.02):
        print(f"    提升 {lift:.0%} 个百分点 → 每臂需要 {required_n(0.54, lift):6d} 条")
    print("\n  我们 AH 轨道总共 188 条。只够识别 10 个百分点以上的差异，")
    print("  而阈值调参的真实效应通常是 2~3 个百分点。")


def report_holdout(con: sqlite3.Connection) -> None:
    rows = con.execute(
        """
        select s.market, s.lean, s.confidence, s.match_day,
               f.home_goals hg, f.away_goals ag
        from auto_pick_snapshots s join fixtures f on f.id = s.fixture_id
        where f.status = 'finished' and f.home_goals is not null
          and s.market = 'ah' and s.confidence is not null
        order by s.match_day, s.fixture_id
        """
    ).fetchall()
    graded = [(r, grade(r)) for r in rows]
    graded = [(r, h) for r, h in graded if h is not None]
    if not graded:
        print("\n无可结算 AH 样本")
        return

    split = len(graded) * 2 // 3
    train, test = graded[:split], graded[split:]
    print(
        f"\n=== 53% 门槛的时间留出验证（前 {len(train)} 条调参 / "
        f"后 {len(test)} 条检验）==="
    )
    print(f"  训练段 {train[0][0]['match_day']} ~ {train[-1][0]['match_day']}")
    print(f"  留出段 {test[0][0]['match_day']} ~ {test[-1][0]['match_day']}")

    def rate(sample, gate):
        kept = [h for r, h in sample if float(r["confidence"]) >= gate]
        if not kept:
            return None, 0
        return sum(kept) / len(kept), len(kept)

    print("\n  门槛    训练段命中(样本)      留出段命中(样本)")
    best_gate, best_rate = None, -1.0
    for gate in CANDIDATE_GATES:
        tr, tr_n = rate(train, gate)
        te, te_n = rate(test, gate)
        tr_s = f"{tr:.1%} ({tr_n:3d})" if tr is not None else "   n/a    "
        te_s = f"{te:.1%} ({te_n:3d})" if te is not None else "   n/a    "
        mark = ""
        if tr is not None and tr_n >= 30 and tr > best_rate:
            best_gate, best_rate = gate, tr
        print(f"  {gate:.0%}     {tr_s:<18}  {te_s}")

    base_te, base_n = rate(test, 0.0)
    print(f"\n  留出段不设门槛（旧口径 40%）: {base_te:.1%} ({base_n})")
    gate_te, gate_n = rate(test, 0.53)
    print(f"  留出段用 53% 门槛:            {gate_te:.1%} ({gate_n})")
    lo, hi = wilson(round(gate_te * gate_n), gate_n)
    print(f"  53% 留出段 95% 置信区间:      [{lo:.1%}, {hi:.1%}]")
    if best_gate is not None:
        print(f"\n  仅看训练段，最优门槛会选到 {best_gate:.0%}（{best_rate:.1%}）")
        chosen_te, chosen_n = rate(test, best_gate)
        if chosen_te is not None:
            print(f"  该门槛在留出段: {chosen_te:.1%} ({chosen_n}) —— 这才是它的真实表现")


def main() -> None:
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    report_inventory(con)
    report_power()
    report_holdout(con)


if __name__ == "__main__":
    main()
