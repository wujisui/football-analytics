"""Unit tests for auto-pick incentive scoring helpers."""

from __future__ import annotations

import unittest

from app.services.auto_pick_incentive import (
    IncentiveParams,
    IncentiveState,
    adjust_pick_score,
    build_quality_deciles,
    build_soft_weights,
    hit_rate_to_multiplier,
    percentile,
    quality_rating,
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
        # alpha 需明显小于 0.5，否则最后一场负会盖掉前两场胜。
        params = IncentiveParams(ema_alpha=0.2, ema_clamp=0.5)
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
        )
        boosted = adjust_pick_score(0.1, league_id=39, market="1x2", state=state)
        self.assertGreater(boosted, 0.1)

    def test_quality_rating_maps_deciles_to_half_stars(self) -> None:
        deciles = build_quality_deciles([float(i) for i in range(1, 101)])
        self.assertEqual(len(deciles), 9)
        # Below every decile → weakest half star; above all → full 5 星.
        self.assertEqual(quality_rating(0.0, deciles), 0.5)
        self.assertEqual(quality_rating(1000.0, deciles), 5.0)
        # Mid-distribution lands mid-ladder and stays monotonic.
        self.assertEqual(quality_rating(50.0, deciles), 2.5)
        self.assertGreater(
            quality_rating(80.0, deciles) or 0.0,
            quality_rating(20.0, deciles) or 0.0,
        )

    def test_quality_rating_without_history(self) -> None:
        self.assertEqual(build_quality_deciles([]), [])
        self.assertIsNone(quality_rating(0.5, []))

    def test_ema_update_clamps(self) -> None:
        self.assertEqual(
            update_ema_value(0.4, 1.0, alpha=1.0, clamp=0.5),
            0.5,
        )


if __name__ == "__main__":
    unittest.main()
