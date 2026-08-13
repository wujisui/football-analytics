"""Unit tests for auto-pick incentive scoring helpers."""

from __future__ import annotations

import unittest

from app.services.auto_pick_incentive import (
    IncentiveParams,
    IncentiveState,
    adjust_pick_score,
    build_soft_weights,
    hit_rate_to_multiplier,
    is_quality_low,
    percentile,
    resolve_soft_weight,
    soft_weight_keys,
    update_ema_value,
    walk_auto_pick_ema,
)


class AutoPickIncentiveTests(unittest.TestCase):
    def test_percentile_p30(self) -> None:
        values = [float(i) for i in range(1, 11)]
        # P30 of 1..10 ≈ 3.7
        self.assertAlmostEqual(percentile(values, 30.0) or 0.0, 3.7, places=5)

    def test_soft_weight_fallback_order(self) -> None:
        self.assertEqual(
            soft_weight_keys(39, "1x2"),
            ("39|1x2", "m:1x2", "l:39", "global"),
        )
        weights = {"m:1x2": 1.1, "global": 1.0}
        self.assertEqual(resolve_soft_weight(weights, league_id=39, market="1x2"), 1.1)
        weights["39|1x2"] = 1.2
        self.assertEqual(resolve_soft_weight(weights, league_id=39, market="1x2"), 1.2)

    def test_build_soft_weights_respects_min_samples(self) -> None:
        params = IncentiveParams(soft_min_samples=20)
        cells = {
            (39, "1x2"): (12, 15),  # below gate
            (40, "ou"): (14, 20),  # at gate
        }
        weights = build_soft_weights(cells, params=params)
        self.assertNotIn("39|1x2", weights)
        self.assertIn("40|ou", weights)
        self.assertIn("global", weights)

    def test_hit_rate_mapping_bounds(self) -> None:
        self.assertEqual(hit_rate_to_multiplier(0.0), 0.75)
        self.assertEqual(hit_rate_to_multiplier(1.0), 1.25)
        self.assertEqual(hit_rate_to_multiplier(0.5), 1.0)

    def test_ema_and_adjust_score(self) -> None:
        params = IncentiveParams(ema_alpha=0.5, ema_clamp=0.5)
        ema_m, ema_l = walk_auto_pick_ema(
            [("1x2", 39, True), ("1x2", 39, True), ("1x2", 39, False)],
            params=params,
        )
        self.assertGreater(ema_m["1x2"], 0.0)
        self.assertGreater(ema_l["39"], 0.0)
        state = IncentiveState(
            params=params,
            ema_market=ema_m,
            ema_league=ema_l,
            soft_weights={"global": 1.0, "39|1x2": 1.1},
            quality_threshold=0.05,
        )
        boosted = adjust_pick_score(0.1, league_id=39, market="1x2", state=state)
        self.assertGreater(boosted, 0.1)
        self.assertTrue(is_quality_low(0.01, 0.05))
        self.assertFalse(is_quality_low(0.2, 0.05))

    def test_ema_update_clamps(self) -> None:
        self.assertEqual(
            update_ema_value(0.4, 1.0, alpha=1.0, clamp=0.5),
            0.5,
        )


if __name__ == "__main__":
    unittest.main()
