"""在已结算历史上回测两个待定阈值，不打官方 API、只读本地库。

1. 胜平负「弱热门」条件：市场已有明确热门（差距 >= _SINGLE_PICK_GAP）时仍被判胶着，
   单选与双选各自的命中率差多少。
2. 让球候选范围：只看主盘 vs 收全部浅盘档位，命中率与回报各差多少。

用法：backend/.venv/Scripts/python.exe backend/scripts/backtest_lean_thresholds.py
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.services.ah_features import (  # noqa: E402
    ASIAN_HALF_LOSS,
    ASIAN_HALF_WIN,
    ASIAN_LOSS,
    ASIAN_PUSH,
    ASIAN_WIN,
    extract_main_ah_line,
    iter_ah_quotes,
    outcome_settlement_units,
    settle_handicap_pick,
)
from app.services.prediction import (  # noqa: E402
    _DRAW_INCLUDE_MIN,
    _MARKET_FLAT_SPREAD,
    _SINGLE_PICK_GAP,
    implied_probs_from_odds,
    normalize_probabilities,
)
from app.services.prematch_package import rehydrate_odds_markets  # noqa: E402
from app.services.recommendation.strategy import (  # noqa: E402
    MIN_DAILY_CONFIDENCE,
    risk_adjusted_return_score,
)

DB = ROOT / "data" / "football.db"

# 结算一注的实际收益倍数（相对本金），用于回报统计。
_UNIT_RETURN = {
    ASIAN_WIN: 1.0,
    ASIAN_HALF_WIN: 0.5,
    ASIAN_PUSH: 0.0,
    ASIAN_HALF_LOSS: -0.5,
    ASIAN_LOSS: -1.0,
}


def outcome_of(home_goals: int, away_goals: int) -> str:
    if home_goals > away_goals:
        return "home"
    if home_goals < away_goals:
        return "away"
    return "draw"


def side_probability(
    line: float,
    pick: str,
    probs: dict[str, float],
) -> tuple[float, float] | None:
    """复制 auto_favorites._ah_side_probability 的口径：按 unit 大小加权。"""
    units = outcome_settlement_units(line, pick)
    if units is None:
        return None
    won = sum(probs[k] * u for k, u in units.items() if u > 0)
    lost = sum(probs[k] * -u for k, u in units.items() if u < 0)
    at_risk = won + lost
    if at_risk <= 0:
        return None
    return won / at_risk, at_risk


def load_rows() -> list[dict]:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """
        SELECT f.id, f.date, f.home_goals, f.away_goals,
               p.home_win_prob, p.draw_prob, p.away_win_prob,
               p.recommendation, p.odds_json
        FROM pre_match_data p
        JOIN fixtures f ON f.id = p.fixture_id
        WHERE f.home_goals IS NOT NULL AND f.away_goals IS NOT NULL
          AND p.odds_json IS NOT NULL AND p.odds_json <> ''
        ORDER BY f.date
        """
    ).fetchall()
    con.close()

    out: list[dict] = []
    for r in rows:
        try:
            odds = rehydrate_odds_markets(json.loads(r["odds_json"]))
        except (ValueError, TypeError):
            continue
        market = implied_probs_from_odds(odds)
        if market is None:
            continue
        model = normalize_probabilities(
            {
                "home": float(r["home_win_prob"] or 0.0),
                "draw": float(r["draw_prob"] or 0.0),
                "away": float(r["away_win_prob"] or 0.0),
            }
        )
        out.append(
            {
                "id": r["id"],
                "date": r["date"],
                "hg": int(r["home_goals"]),
                "ag": int(r["away_goals"]),
                "actual": outcome_of(int(r["home_goals"]), int(r["away_goals"])),
                "market": market,
                "model": model,
                "odds": odds,
                "stored_rec": r["recommendation"] or "",
            }
        )
    return out


# ---------------------------------------------------------------- 1X2 阈值


def classify_1x2(row: dict) -> dict | None:
    """还原 get_recommendation 的分支判定，并给出单选替代答案。"""
    market, model = row["market"], row["model"]
    m_rank = sorted(market.items(), key=lambda kv: -kv[1])
    d_rank = sorted(model.items(), key=lambda kv: -kv[1])
    if m_rank[0][0] == "draw":
        return None  # 平局做庄的盘另有分支，不在本次讨论范围

    m_gap = m_rank[0][1] - m_rank[1][1]
    m_spread = m_rank[0][1] - m_rank[2][1]
    d_spread = d_rank[0][1] - d_rank[2][1]
    d_gap = d_rank[0][1] - d_rank[1][1]
    d_draw = model["draw"]
    m_draw = market["draw"]

    weak = (
        d_rank[0][0] in {"home", "away"}
        and model[d_rank[0][0]] < 0.50
        and d_draw >= 0.24
    )
    other_contested = (
        m_spread <= _MARKET_FLAT_SPREAD
        or d_spread <= _MARKET_FLAT_SPREAD
        or (m_draw >= _DRAW_INCLUDE_MIN and m_gap < _SINGLE_PICK_GAP)
    )
    # 只有 weak_* 单独把一个「明确热门」的盘拖进双选时，本次改动才会影响它。
    only_weak_blocks = weak and not other_contested and m_gap >= _SINGLE_PICK_GAP
    if not only_weak_blocks:
        return None

    fav = d_rank[0][0]
    dual = {fav, "draw"} if d_draw >= _DRAW_INCLUDE_MIN - 0.02 else {"home", "away"}
    # 收紧后走「明确热门」分支：模型与市场同向且 d_gap >= 0.08 即单选
    if d_rank[0][0] == m_rank[0][0] and d_gap >= 0.08:
        single = {m_rank[0][0]}
    elif model[m_rank[0][0]] - market[m_rank[0][0]] >= 0.04 and d_gap >= 0.08:
        single = {m_rank[0][0]}
    else:
        return None

    return {"dual": dual, "single": single, "m_gap": m_gap}


def report_1x2(rows: list[dict]) -> None:
    print("=" * 78)
    print("一、胜平负「弱热门」阈值回测")
    print("=" * 78)
    print(
        "范围：仅统计「市场差距 >= "
        f"{_SINGLE_PICK_GAP}（已有明确热门），但被 weak_* 单独拖进双选」的场次。\n"
    )

    total = dual_hit = single_hit = 0
    dual_cover = single_cover = 0.0
    for row in rows:
        verdict = classify_1x2(row)
        if verdict is None:
            continue
        total += 1
        dual_hit += row["actual"] in verdict["dual"]
        single_hit += row["actual"] in verdict["single"]
        # 覆盖度 = 该选项按市场定价本来就该命中的概率，用来剥掉「双选天然更容易中」。
        dual_cover += sum(row["market"][k] for k in verdict["dual"])
        single_cover += sum(row["market"][k] for k in verdict["single"])

    if not total:
        print("没有符合条件的历史场次。")
        return

    d_rate, s_rate = dual_hit / total, single_hit / total
    d_base, s_base = dual_cover / total, single_cover / total
    print(f"受影响场次 {total} 场\n")
    print(f"{'方案':10} {'命中率':>8} {'市场覆盖度':>10} {'超出覆盖度':>10}")
    print(f"{'维持双选':10} {d_rate:8.1%} {d_base:10.1%} {d_rate - d_base:+10.1%}")
    print(f"{'改为单选':10} {s_rate:8.1%} {s_base:10.1%} {s_rate - s_base:+10.1%}")
    print(
        "\n覆盖度是「按市场定价这个选项本来就该中的概率」。双选覆盖两个结果，"
        "命中率天然更高；\n只有『超出覆盖度』那一列才反映判断本身有没有信息量。"
    )


# ---------------------------------------------------------------- 让球档位


def ah_candidates(row: dict, *, shallow_only: bool) -> list[dict]:
    """每块盘先按命中率留下更高的一侧，再交给打分。"""
    probs = row["market"]
    main_line, _, _ = extract_main_ah_line(row["odds"])
    out: list[dict] = []
    for line, home_odd, away_odd in iter_ah_quotes(row["odds"]):
        if not shallow_only and abs(line - (main_line or line)) > 1e-9:
            continue
        sides = []
        for pick, odd in (("让胜", home_odd), ("让负", away_odd)):
            got = side_probability(line, pick, probs)
            if got is None:
                continue
            conf, at_risk = got
            sides.append({"line": line, "pick": pick, "odd": odd,
                          "conf": conf, "at_risk": at_risk})
        if not sides:
            continue
        best = max(s["conf"] for s in sides)
        for s in sides:
            if s["conf"] < best - 1e-9 or s["conf"] < MIN_DAILY_CONFIDENCE:
                continue
            s["score"] = risk_adjusted_return_score(s["conf"], s["odd"])
            out.append(s)
    return out


def _rec_outcomes(row: dict) -> set[str]:
    from app.services.prediction import recommendation_outcomes

    return recommendation_outcomes(row["stored_rec"]) or set()


def _covers(cand: dict, rec_set: set[str]) -> bool:
    """该让球档位在 1X2 结论的每个结果下都不输钱。"""
    if not rec_set:
        return False
    units = outcome_settlement_units(cand["line"], cand["pick"])
    if units is None:
        return False
    return all(units.get(k, -1.0) >= 0 for k in rec_set)


def settle(row: dict, cand: dict) -> float | None:
    res = settle_handicap_pick(row["hg"], row["ag"], cand["line"], cand["pick"])
    if res is None:
        return None
    unit = _UNIT_RETURN[res]
    if unit > 0:
        return unit * (cand["odd"] - 1.0)
    return unit


def report_ah(rows: list[dict]) -> None:
    print()
    print("=" * 78)
    print("二、让球候选范围回测")
    print("=" * 78)
    print("每块盘先留命中率更高的一侧，再按风险调整分选一注。\n")

    def by_score(cands):
        return max(cands, key=lambda c: c["score"])

    def by_hit(cands):
        return max(cands, key=lambda c: c["conf"])

    def by_score_then_1x2(window: float):
        """分数在 window 之内视为并列，优先选能覆盖 1X2 结论的档位。"""

        def make(row):
            rec_set = _rec_outcomes(row)

            def choose(cands):
                best = max(c["score"] for c in cands)
                near = [c for c in cands if c["score"] >= best - window]
                aligned = [c for c in near if _covers(c, rec_set)]
                return max(aligned or near, key=lambda c: c["conf"])

            return choose

        return make

    # 只统计各策略都能出注的场次，避免注数不同导致口径不可比。
    usable = []
    for row in rows:
        main = ah_candidates(row, shallow_only=False)
        allc = ah_candidates(row, shallow_only=True)
        if main and allc:
            usable.append((row, main, allc))
    print(f"各策略均可出注的场次：{len(usable)}\n")

    def evaluate(subset, shallow, chooser) -> tuple[int, float, float, float]:
        n = hits = 0
        rets: list[float] = []
        for row, main, allc in subset:
            pick = chooser(row)(allc if shallow else main)
            ret = settle(row, pick)
            if ret is None:
                continue
            n += 1
            rets.append(ret)
            if ret > 0:
                hits += 1
        if not n:
            return 0, 0.0, 0.0, 0.0
        mean = sum(rets) / n
        var = sum((x - mean) ** 2 for x in rets) / n
        stderr = (var / n) ** 0.5
        return n, hits / n, mean, stderr

    strategies = [
        ("只看主盘 · 按分数（现状）", False, lambda r: by_score),
        ("全浅盘 · 按分数", True, lambda r: by_score),
        ("全浅盘 · 按命中率", True, lambda r: by_hit),
        ("全浅盘 · 分数近则贴 1X2", True, by_score_then_1x2(0.02)),
    ]
    print(f"{'策略':26} {'命中率':>8} {'ROI':>9} {'标准误':>8} {'t':>6}")
    for name, shallow, chooser in strategies:
        n, hit, roi, se = evaluate(usable, shallow, chooser)
        t = roi / se if se else 0.0
        print(f"{name:26} {hit:8.1%} {roi:+9.2%} {se:8.2%} {t:6.2f}")
    print("\nt 值是 ROI 与 0 的距离，|t| < 2 都说明样本量不足以证明有正回报。")

    print(f"\n--- 贴 1X2 的并列窗口敏感性 ---")
    print(f"{'窗口':>8} {'命中率':>8} {'ROI':>9} {'t':>6}")
    for window in (0.005, 0.01, 0.02, 0.03, 0.05, 0.10):
        n, hit, roi, se = evaluate(usable, True, by_score_then_1x2(window))
        print(f"{window:8.3f} {hit:8.1%} {roi:+9.2%} {roi / se if se else 0:6.2f}")

    split = int(len(usable) * 0.7)
    print(f"\n--- 时间切分：前 {split} 场定参 / 后 {len(usable) - split} 场验证 ---")
    print(f"{'策略':26} {'前段 ROI':>10} {'后段命中率':>10} {'后段 ROI':>10} {'后段 t':>8}")
    for name, shallow, chooser in strategies:
        _, _, roi_a, _ = evaluate(usable[:split], shallow, chooser)
        _, hit_b, roi_b, se_b = evaluate(usable[split:], shallow, chooser)
        t_b = roi_b / se_b if se_b else 0.0
        print(f"{name:26} {roi_a:+10.2%} {hit_b:10.1%} {roi_b:+10.2%} {t_b:8.2f}")


def report_current_split() -> None:
    """收紧后未开赛场次的单选/双选构成，用来确认改动落地效果。"""
    from app.services.prediction import get_recommendation

    con = sqlite3.connect(DB)
    rows = con.execute(
        """
        SELECT p.home_win_prob, p.draw_prob, p.away_win_prob, p.odds_json
        FROM pre_match_data p
        JOIN fixtures f ON f.id = p.fixture_id
        WHERE f.date > datetime('now') AND p.odds_json IS NOT NULL
        """
    ).fetchall()
    con.close()

    counts: dict[str, int] = {}
    for hp, dp, ap, odds_text in rows:
        try:
            odds = rehydrate_odds_markets(json.loads(odds_text))
        except (ValueError, TypeError):
            continue
        probs = normalize_probabilities(
            {"home": hp or 0.0, "draw": dp or 0.0, "away": ap or 0.0}
        )
        rec = get_recommendation(probs, odds=odds)
        counts[rec] = counts.get(rec, 0) + 1

    total = sum(counts.values())
    if not total:
        return
    dual = sum(v for k, v in counts.items() if "/" in k)
    print()
    print("=" * 78)
    print("三、当前未开赛场次按现行代码重算的构成")
    print("=" * 78)
    for rec, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {rec:8} {n:4d}")
    print(f"  双选占比 {dual}/{total} = {dual / total:.0%}")


def main() -> None:
    rows = load_rows()
    print(f"已结算且有冻结盘口的场次：{len(rows)}\n")
    report_1x2(rows)
    report_ah(rows)
    report_current_split()


if __name__ == "__main__":
    main()
