import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.ml_predictor import train_from_rows


class MlPredictorTests(unittest.TestCase):
    def _synthetic_rows(self, n: int) -> list[tuple[dict[str, float], str]]:
        rows: list[tuple[dict[str, float], str]] = []
        labels = ("home", "draw", "away")
        for i in range(n):
            bias = (i % 3) * 0.05
            features = {
                "has_odds": 1.0,
                "odds_home": 0.45 + bias,
                "odds_draw": 0.28,
                "odds_away": 0.27 - bias,
                "home_wr_5": 0.4 + bias,
                "away_wr_5": 0.3,
                "home_gd_avg_5": 0.2,
                "away_gd_avg_5": -0.1,
                "rank_diff": 0.1,
                "home_advantage": 1.0,
            }
            rows.append((features, labels[i % 3]))
        return rows

    def test_train_below_threshold_skips(self) -> None:
        result = train_from_rows(self._synthetic_rows(25))
        self.assertFalse(result.get("ok"))

    def test_train_meets_threshold_writes_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            weights = root / "1x2_weights.npz"
            meta = root / "1x2_meta.json"
            with patch(
                "app.services.ml_predictor.model_paths",
                return_value=(weights, meta),
            ):
                result = train_from_rows(self._synthetic_rows(40))
            self.assertTrue(result.get("ok"))
            val = result.get("val_metrics") or {}
            self.assertIn("log_loss", val)
            self.assertIn("accuracy", val)
            self.assertIn("deployable", result)
            self.assertIsInstance(result.get("market_val_metrics"), dict)
            self.assertTrue(weights.exists())
            self.assertTrue(meta.exists())
            saved = json.loads(meta.read_text(encoding="utf-8"))
            self.assertIn("deployable", saved)


if __name__ == "__main__":
    unittest.main()
