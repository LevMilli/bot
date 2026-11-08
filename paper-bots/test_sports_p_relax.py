"""Sports-gap must honor staff soft-p relax on fair floors (never edge/fee)."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
GAP_DIR = os.path.join(HERE, "sports-gap-paper")
if HERE not in sys.path:
    sys.path.insert(0, HERE)
if GAP_DIR not in sys.path:
    sys.path.insert(0, GAP_DIR)

import desk_more
import desk_roi_plan
import gap_bot


def _seed_soft_p(tmp: str, n: int = 30) -> None:
    for i in range(n):
        desk_more.record_near_miss(
            tmp,
            {
                "bot": "sports-gap",
                "ticker": f"KX-P-{i}",
                "side": "YES",
                "soft": ["p"],
                "p": 0.78,
                "edge": 0.05,
            },
        )
        desk_roi_plan.label_near_miss_outcome(
            tmp, ticker=f"KX-P-{i}", would_pnl=0.10, bot="sports-gap",
        )


class SportsSoftPRelax(unittest.TestCase):
    def test_default_floors_without_arm(self):
        with tempfile.TemporaryDirectory() as tmp:
            floors = gap_bot.fair_lane_floors("NCAAF", tmp)
            self.assertAlmostEqual(floors["p_relax"], 0.0)
            self.assertGreaterEqual(
                floors["accurate_floor"], gap_bot.MIN_FAIR_ACCURATE - 1e-12,
            )
            self.assertGreaterEqual(
                floors["speed_floor"], gap_bot.MIN_FAIR_SPEED - 1e-12,
            )
            self.assertTrue(floors["fee_floors_locked"])

    def test_soft_p_arm_relaxes_fair_floors(self):
        with tempfile.TemporaryDirectory() as tmp:
            baseline = gap_bot.fair_lane_floors("NCAAF", tmp)
            self.assertAlmostEqual(baseline["p_relax"], 0.0)
            _seed_soft_p(tmp)
            armed = desk_roi_plan.staff_promote_near_miss_soft(
                tmp, "p", note="test sports p-relax wire",
            )
            self.assertTrue(armed["ok"], armed)
            floors = gap_bot.fair_lane_floors("NCAAF", tmp)
            self.assertAlmostEqual(floors["p_relax"], desk_roi_plan.NEAR_MISS_P_RELAX)
            self.assertAlmostEqual(
                floors["accurate_floor"],
                baseline["accurate_floor"] - desk_roi_plan.NEAR_MISS_P_RELAX,
                places=6,
            )
            self.assertAlmostEqual(
                floors["speed_floor"],
                baseline["speed_floor"] - desk_roi_plan.NEAR_MISS_P_RELAX,
                places=6,
            )
            # Soft-p never softens fee/edge floors.
            self.assertEqual(gap_bot.MIN_GAP, 0.06)


if __name__ == "__main__":
    unittest.main()
