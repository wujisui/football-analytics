import sys

sys.path.insert(0, ".")
from app.services.ah_market_structure import classify_ah_board, recommendation_from_ah_board
from app.services.prediction import derive_prediction_leans, get_recommendation

# 反推截图里的报价：去水后 主21.0 / 平31.9 / 客47.1；
# 让球主+0.5 两侧 EV 为 -2.2% / -2.9% → 约 1.85 / 2.06；大小球 1.75 档 大53.7 / 小46.3。
odds = {
    "available": True,
    "match_winner": {"home": 4.64, "draw": 3.05, "away": 2.07},
    "asian_handicap": {"line": "+0.5", "home": 1.85, "away": 2.06},
    "goals_ou": {"line": "1.75", "home": 1.81, "away": 2.10},
}
probs = {"home": 0.210, "draw": 0.319, "away": 0.471}

stance = classify_ah_board(odds)
print("线:", stance.line, "让球方:", stance.giving_side, "水位差:", round(stance.water_diff, 3))
print("盘口选边:", stance.ah_pick, stance.result_choice, "深盘:", stance.is_deep)
print("board -> 1X2:", recommendation_from_ah_board(odds))
print("get_recommendation:", get_recommendation(probs, odds=odds))

leans = derive_prediction_leans(probs, odds)
for key in ("recommendation", "handicap_lean", "score_hint", "goal_lean", "both_score_lean"):
    print(f"  {key:18s} {leans[key]}")

print()
print("买 主+0.5 的真实命中条件 = 主胜 or 和局 =", round(probs["home"] + probs["draw"], 3))
print("买 客-0.5 的真实命中条件 = 客胜        =", probs["away"])
for name, p, o in (("主+0.5", 0.529, 1.85), ("客-0.5", 0.471, 2.06)):
    print(f"  {name}: p={p:.3f} odds={o} EV/100 = {100 * (p * o - 1):+.1f}")
