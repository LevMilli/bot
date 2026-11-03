"""BTC calibration report — model-p buckets vs hit rate."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_master
import desk_roi_plan


def _hist(n: int, prob: float, hit: bool) -> list:
    return [
        {"prob": prob, "pnl": 0.10 if hit else -0.10, "contracts": 1}
        for _ in range(n)
    ]


class BtcCalibration(unittest.TestCase):
    def test_empty_observe(self):
        rep = desk_roi_plan.btc_calibration_report(bots=[])
        self.assertEqual(rep["n"], 0)
        self.assertEqual(rep["action"], "observe")
        self.assertFalse(rep["miscalibrated"])

    def test_flags_hi_p_miscalibration(self):
        # 20 trades labeled 0.82, only 10 hits → 50% < 70% floor.
        hits = _hist(10, 0.82, True) + _hist(10, 0.82, False)
        bots = [{"id": "btc15m", "history": hits}]
        rep = desk_roi_plan.btc_calibration_report(bots)
        self.assertTrue(rep["miscalibrated"])
        self.assertEqual(rep["action"], "raise_phi")
        self.assertEqual(rep["hi_n"], 20)
        self.assertAlmostEqual(rep["hi_hit_rate"], 0.5)

    def test_keep_when_calibrated(self):
        hits = _hist(16, 0.85, True) + _hist(4, 0.85, False)  # 80%
        bots = [{"id": "btc15m", "history": hits}]
        rep = desk_roi_plan.btc_calibration_report(bots)
        self.assertFalse(rep["miscalibrated"])
        self.assertEqual(rep["action"], "keep")

    def test_capture_and_master(self):
        with tempfile.TemporaryDirectory() as tmp:
            bots = [{"id": "btc15m", "history": _hist(5, 0.75, True), "open_risk": 0, "gate_a": {}}]
            card = desk_roi_plan.capture_btc_calibration(tmp, bots=bots, label="2026-11-03")
            self.assertEqual(card["label"], "2026-11-03")
            self.assertEqual(desk_roi_plan.latest_btc_calibration(tmp)["label"], "2026-11-03")
            summary = desk_master.master_summary(
                tmp, bots=bots, cfg={"max_open_risk": 100},
            )
            plan = summary.get("roi_plan") or {}
            self.assertIn("btc_calibration", plan)
            self.assertTrue(plan.get("fee_floors_locked"))

    def test_fee_floors_untouched(self):
        import desk_profit
        floors = desk_profit.venue_floors_locked()
        self.assertTrue(floors["locked"])
        self.assertTrue(floors["all_ok"])


if __name__ == "__main__":
    unittest.main()
