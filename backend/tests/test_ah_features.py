import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.ah_features import (
    AH_FEATURE_VERSION,
    build_ah_features,
    handicap_line_from_lean,
    handicap_pick_from_lean,
    settle_ah_label,
    settle_handicap_result,
)
from app.services.ah_predictor import _BinaryLogReg, load_trained_model
from app.services.features import extract_features


class AhFeaturesTests(unittest.TestCase):
    def test_settle_ah_label_boundaries(self) -> None:
        self.assertEqual(settle_ah_label(2, 1, -0.5), "cover")
        self.assertEqual(settle_ah_label(1, 1, -0.5), "no_cover")
        self.assertEqual(settle_ah_label(1, 1, 0.0), "push")
        self.assertIsNone(settle_ah_label(None, 1, -0.5))

    def test_settle_three_way_handicap_result(self) -> None:
        # Home gives one: 1-0 pushes, 2-0 wins, any level score loses.
        self.assertEqual(settle_handicap_result(1, 0, -1.0), "让球平")
        self.assertEqual(settle_handicap_result(2, 0, -1.0), "让球胜")
        self.assertEqual(settle_handicap_result(1, 1, -1.0), "让球负")
        # Away gives one (home receives +1): 0-1 pushes; 1-1 wins.
        self.assertEqual(settle_handicap_result(0, 1, 1.0), "让球平")
        self.assertEqual(settle_handicap_result(1, 1, 1.0), "让球胜")
        self.assertEqual(settle_handicap_result(0, 2, 1.0), "让球负")

    def test_parse_frozen_handicap_lean(self) -> None:
        self.assertEqual(handicap_pick_from_lean("让球胜（-1）"), "让球胜")
        self.assertEqual(handicap_line_from_lean("让球胜（-1）"), -1.0)
        self.assertEqual(handicap_line_from_lean("让球负（+1）"), 1.0)

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
