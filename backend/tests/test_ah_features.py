import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.ah_features import (
    AH_FEATURE_VERSION,
    ASIAN_HALF_LOSS,
    ASIAN_HALF_WIN,
    ASIAN_LOSS,
    ASIAN_PUSH,
    ASIAN_WIN,
    asian_result_counts_as_hit,
    build_ah_features,
    handicap_line_from_lean,
    handicap_pick_from_lean,
    handicap_picks_from_lean,
    adapt_handicap_lean_for_ruleset,
    jc_handicap_line,
    settle_ah_label,
    settle_asian_total,
    settle_handicap_pick,
    settle_handicap_result,
)
from app.services.ah_predictor import (
    HandicapPrediction,
    _BinaryLogReg,
    _structural_pick,
    format_handicap_lean,
    load_trained_model,
)
from app.services.features import extract_features


class AhFeaturesTests(unittest.TestCase):
    def test_settle_ah_label_boundaries(self) -> None:
        self.assertEqual(settle_ah_label(2, 1, -0.5), "cover")
        self.assertEqual(settle_ah_label(1, 1, -0.5), "no_cover")
        self.assertEqual(settle_ah_label(1, 1, 0.0), "push")
        self.assertIsNone(settle_ah_label(None, 1, -0.5))

    def test_format_handicap_lean_includes_side(self) -> None:
        pred = HandicapPrediction(0.62, "cover", "multifactor", -0.25)
        self.assertEqual(format_handicap_lean(pred), "让胜(-0.25)")
        pred_lose = HandicapPrediction(0.4, "no_cover", "multifactor", -0.25)
        self.assertEqual(format_handicap_lean(pred_lose), "让负(-0.25)")
        pred_recv = HandicapPrediction(0.55, "cover", "multifactor", 1.0)
        self.assertEqual(format_handicap_lean(pred_recv), "让胜(+1)")
        pred_level = HandicapPrediction(0.5, "push", "multifactor", 0.0)
        self.assertEqual(format_handicap_lean(pred_level), "让平(0)")
        pred_dual = HandicapPrediction(0.5, "cover/no_cover", "structural", -0.5)
        self.assertEqual(format_handicap_lean(pred_dual), "让胜/负(-0.5)")
        pred_integer_dual = HandicapPrediction(0.5, "no_cover/push", "structural", -1.0)
        self.assertEqual(format_handicap_lean(pred_integer_dual), "让负/平(-1)")

    def test_double_chance_maps_to_handicap_double_pick(self) -> None:
        non_integer = _structural_pick(-0.5, "胜/平")
        self.assertIsNotNone(non_integer)
        self.assertEqual(non_integer.pick, "cover/no_cover")
        self.assertEqual(format_handicap_lean(non_integer), "让胜/负(-0.5)")

        integer = _structural_pick(-1.0, "胜/平")
        self.assertIsNotNone(integer)
        self.assertEqual(integer.pick, "no_cover/push")
        self.assertEqual(format_handicap_lean(integer), "让负/平(-1)")

        mirrored_non_integer = _structural_pick(0.5, "负/平")
        self.assertIsNotNone(mirrored_non_integer)
        self.assertEqual(mirrored_non_integer.pick, "cover/no_cover")

        mirrored_integer = _structural_pick(1.0, "负/平")
        self.assertIsNotNone(mirrored_integer)
        self.assertEqual(mirrored_integer.pick, "cover/push")

    def test_settle_three_way_handicap_result(self) -> None:
        # Jingcai keeps 让平 on integer non-zero lines.
        self.assertEqual(settle_handicap_result(1, 0, -1.0, ruleset="jc"), "让平")
        self.assertEqual(settle_handicap_result(2, 0, -1.0, ruleset="jc"), "让胜")
        self.assertEqual(settle_handicap_result(1, 1, -1.0, ruleset="jc"), "让负")
        self.assertEqual(settle_handicap_result(0, 1, 1.0, ruleset="jc"), "让平")
        self.assertEqual(settle_handicap_result(1, 1, 1.0, ruleset="jc"), "让胜")
        self.assertEqual(settle_handicap_result(0, 2, 1.0, ruleset="jc"), "让负")

    def test_asian_integer_exact_is_a_walk(self) -> None:
        self.assertEqual(settle_handicap_result(2, 1, -1.0), "走水")
        self.assertEqual(settle_handicap_pick(2, 1, -1.0, "让胜"), ASIAN_PUSH)
        self.assertEqual(settle_handicap_pick(2, 1, -1.0, "让负"), ASIAN_PUSH)
        self.assertEqual(settle_handicap_pick(2, 1, -1.0, "让平"), ASIAN_PUSH)
        self.assertEqual(
            settle_handicap_pick(2, 1, -1.0, "让胜", ruleset="jc"),
            ASIAN_LOSS,
        )
        self.assertEqual(
            settle_handicap_pick(1, 0, -1.0, "让平", ruleset="jc"),
            ASIAN_WIN,
        )

    def test_settle_quarter_handicap_split(self) -> None:
        # Home -0.25 at a draw: half stake pushes, half loses.
        self.assertEqual(settle_handicap_pick(3, 3, -0.25, "让胜"), ASIAN_HALF_LOSS)
        self.assertEqual(settle_handicap_pick(3, 3, -0.25, "让负"), ASIAN_HALF_WIN)
        # Home -0.75 winning by one: -0.5 wins and -1 pushes.
        self.assertEqual(settle_handicap_pick(1, 0, -0.75, "让胜"), ASIAN_HALF_WIN)
        self.assertEqual(settle_handicap_pick(1, 0, -0.75, "让负"), ASIAN_HALF_LOSS)
        self.assertEqual(
            settle_handicap_result(3, 3, -0.25),
            "让胜输半 / 让负赢半",
        )

    def test_zero_line_draw_walks_but_other_integer_draw_can_hit(self) -> None:
        for pick in ("让胜", "让平", "让负"):
            self.assertEqual(settle_handicap_pick(2, 2, 0.0, pick), ASIAN_PUSH)
        self.assertEqual(settle_handicap_result(2, 2, 0.0), "走水")
        self.assertEqual(
            settle_handicap_pick(1, 0, -1.0, "让平", ruleset="jc"), ASIAN_WIN
        )
        self.assertEqual(
            settle_handicap_pick(1, 0, -1.0, "让胜", ruleset="jc"), ASIAN_LOSS
        )
        self.assertEqual(settle_handicap_pick(1, 0, -1.0, "让平"), ASIAN_PUSH)

    def test_jc_rounds_line_away_from_zero(self) -> None:
        self.assertEqual(jc_handicap_line(-0.25), -1.0)
        self.assertEqual(jc_handicap_line(-0.5), -1.0)
        self.assertEqual(jc_handicap_line(-0.75), -1.0)
        self.assertEqual(jc_handicap_line(-1.0), -1.0)
        self.assertEqual(jc_handicap_line(-1.25), -2.0)
        self.assertEqual(jc_handicap_line(1.5), 2.0)
        self.assertEqual(jc_handicap_line(0.0), 0.0)

    def test_jc_settles_rounded_line_three_way_without_halves(self) -> None:
        # 主让 0.5 在竞彩按 1 球算：1:0 是让平，不是让胜。
        self.assertEqual(
            settle_handicap_pick(1, 0, -0.5, "让胜", ruleset="jc"), ASIAN_LOSS
        )
        self.assertEqual(
            settle_handicap_pick(1, 0, -0.5, "让平", ruleset="jc"), ASIAN_WIN
        )
        self.assertEqual(settle_handicap_pick(1, 0, -0.5, "让胜"), ASIAN_WIN)
        # 四分盘在竞彩不拆盘，没有赢半 / 输半。
        self.assertEqual(
            settle_handicap_pick(3, 3, -0.25, "让胜", ruleset="jc"), ASIAN_LOSS
        )
        self.assertEqual(settle_handicap_pick(3, 3, -0.25, "让胜"), ASIAN_HALF_LOSS)
        self.assertEqual(settle_handicap_result(1, 0, -0.75, ruleset="jc"), "让平")
        self.assertEqual(settle_handicap_result(2, 0, -0.5, ruleset="jc"), "让胜")
        # 客让 1.25 在竞彩按主队受让 2 球算。
        self.assertEqual(settle_handicap_result(0, 2, 1.25, ruleset="jc"), "让平")
        self.assertEqual(settle_handicap_result(0, 3, 1.25, ruleset="jc"), "让负")

    def test_adapt_lean_shows_rounded_line_for_jc(self) -> None:
        self.assertEqual(
            adapt_handicap_lean_for_ruleset("让胜(-0.5)", ruleset="jc"), "让胜(-1)"
        )
        self.assertEqual(
            adapt_handicap_lean_for_ruleset("让负(+0.25)", ruleset="jc"), "让负(+1)"
        )
        self.assertEqual(
            adapt_handicap_lean_for_ruleset("让胜(-0.5)", ruleset="asian"), "让胜(-0.5)"
        )

    def test_adapt_lean_drops_draw_on_asian_dual_picks(self) -> None:
        self.assertEqual(
            adapt_handicap_lean_for_ruleset("让负/平(-1)", ruleset="asian"),
            "让负(-1)",
        )
        self.assertEqual(
            adapt_handicap_lean_for_ruleset("让负/平(-1)", ruleset="jc"),
            "让负/平(-1)",
        )
        self.assertEqual(
            adapt_handicap_lean_for_ruleset("让平(-1)", ruleset="asian"),
            "让平(-1)",
        )

    def test_settle_quarter_total_split(self) -> None:
        self.assertEqual(settle_asian_total(3, 2.75, over=True), ASIAN_HALF_WIN)
        self.assertEqual(settle_asian_total(3, 2.75, over=False), ASIAN_HALF_LOSS)
        self.assertEqual(settle_asian_total(2, 2.25, over=False), ASIAN_HALF_WIN)
        self.assertEqual(settle_asian_total(2, 2.25, over=True), ASIAN_HALF_LOSS)
        self.assertEqual(settle_asian_total(2, 2.0, over=True), ASIAN_PUSH)

    def test_product_accuracy_counts_partial_results_but_excludes_walks(self) -> None:
        self.assertTrue(asian_result_counts_as_hit(ASIAN_WIN))
        self.assertTrue(asian_result_counts_as_hit(ASIAN_HALF_WIN))
        self.assertTrue(asian_result_counts_as_hit(ASIAN_HALF_LOSS))
        self.assertFalse(asian_result_counts_as_hit(ASIAN_LOSS))
        self.assertIsNone(asian_result_counts_as_hit(ASIAN_PUSH))

    def test_parse_frozen_handicap_lean(self) -> None:
        # Legacy 「让球X」 snapshots must still resolve to the current tokens.
        self.assertEqual(handicap_pick_from_lean("让球胜（-1）"), "让胜")
        self.assertEqual(handicap_pick_from_lean("让负"), "让负")
        self.assertEqual(handicap_pick_from_lean("让负（主让1）"), "让负")
        self.assertIsNone(handicap_pick_from_lean("让胜/负（-0.5）"))
        self.assertEqual(
            handicap_picks_from_lean("让胜/负（-0.5）"),
            {"让胜", "让负"},
        )
        self.assertEqual(
            handicap_picks_from_lean("让球负/平（-1）"),
            {"让负", "让平"},
        )
        self.assertEqual(handicap_line_from_lean("让球胜（-1）"), -1.0)
        self.assertEqual(handicap_line_from_lean("让球负（+1）"), 1.0)
        self.assertEqual(handicap_line_from_lean("让球负（主让1）"), -1.0)
        self.assertEqual(handicap_line_from_lean("让球胜（客让0.5）"), 0.5)
        self.assertEqual(handicap_line_from_lean("让球平（平手）"), 0.0)
        self.assertEqual(handicap_line_from_lean("让球平（0）"), 0.0)
        self.assertIsNone(handicap_line_from_lean("让球平"))

    def test_mx_probs_follow_market(self) -> None:
        package = {
            "odds": {
                "available": True,
                "match_winner": {"home": 2.0, "draw": 3.5, "away": 4.0},
                "asian_handicap": {"line": "-0.5", "home": 1.9, "away": 1.95},
            }
        }
        base = extract_features(package)
        features, _, _, _ = build_ah_features(package, league_id=39)
        ph, _, _ = (
            float(base["odds_home"]),
            float(base["odds_draw"]),
            float(base["odds_away"]),
        )
        total = ph + float(base["odds_draw"]) + float(base["odds_away"])
        market_home = ph / total
        self.assertAlmostEqual(features["mx_home_prob"], market_home, places=5)


class AhModelLoadTests(unittest.TestCase):
    def test_load_rejects_feature_version_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            weights = root / "ah_v1_weights.npz"
            meta = root / "ah_v1_meta.json"
            model = _BinaryLogReg(4)
            model.save(weights)
            meta.write_text(
                json.dumps({"ah_feature_version": "ah_v0", "n_samples": 100}),
                encoding="utf-8",
            )
            with patch("app.services.ah_predictor.model_paths", return_value=(weights, meta)):
                loaded, loaded_meta = load_trained_model()
            self.assertIsNone(loaded)
            self.assertEqual(loaded_meta.get("ah_feature_version"), "ah_v0")

    def test_load_accepts_matching_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            weights = root / "ah_v1_weights.npz"
            meta = root / "ah_v1_meta.json"
            n = 6
            model = _BinaryLogReg(n)
            model.save(weights)
            meta.write_text(
                json.dumps({"ah_feature_version": AH_FEATURE_VERSION, "n_samples": 100}),
                encoding="utf-8",
            )
            with patch("app.services.ah_predictor.model_paths", return_value=(weights, meta)):
                loaded, _ = load_trained_model()
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.w.shape[0], n)


if __name__ == "__main__":
    unittest.main()
