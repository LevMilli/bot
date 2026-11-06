"""Commodity calibration report — fair/prob buckets vs hit (parallel to BTC/sports)."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_living
import desk_master
import desk_roi_plan


def _hist(n: int, fair: float, hit: bool) -> list:
    return [
        {"fair_at_entry": fair, "pnl": 0.10 if hit else -0.10, "contracts": 1}
        for _ in range(n)
    ]


class CommodityCalibration(unittest.TestCase):
    def test_empty_observe(self):
        rep = desk_roi_plan.commodity_calibration_report(bots=[])
        self.assertEqual(rep["n"], 0)
        self.assertEqual(rep["action"], "observe")
        self.assertFalse(rep["miscalibrated"])
        self.assertTrue(rep["fee_floors_locked"])

    def test_flags_hi_fair_miscalibration(self):
        hits = _hist(10, 0.82, True) + _hist(10, 0.82, False)
        bots = [{"id": "commodity-15m", "history": hits}]
        rep = desk_roi_plan.commodity_calibration_report(bots)
        self.assertTrue(rep["miscalibrated"])
        self.assertEqual(rep["action"], "raise_phi")
        self.assertEqual(rep["hi_n"], 20)

    def test_capture_master_and_living_ai(self):
        with tempfile.TemporaryDirectory() as tmp:
            bots = [{"id": "commodity-15m", "history": _hist(5, 0.75, True), "open_risk": 0, "gate_a": {}}]
            card = desk_roi_plan.capture_commodity_calibration(tmp, bots=bots, label="2026-11-06")
            self.assertEqual(card["label"], "2026-11-06")
            summary = desk_master.master_summary(tmp, bots=bots, cfg={"max_open_risk": 100})
            plan = summary.get("roi_plan") or {}
            self.assertIn("commodity_calibration", plan)
            ai = desk_living.living_ai_health(tmp, bots=bots)
            self.assertFalse(ai["auto_write_phi"])
            self.assertTrue(ai["fee_floors_locked"])
            self.assertIn("commodity", ai["calib_boards"])

    def test_fee_floors_untouched(self):
        import desk_profit
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_commodity15m"], 0.05)


if __name__ == "__main__":
    unittest.main()
