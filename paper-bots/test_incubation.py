"""Incubation lane: new series paper-only until 50 fee-aware settles."""
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


class IncubationLane(unittest.TestCase):
    def test_main_series_skips_tracking(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = desk_roi_plan.record_incubation_settle(
                tmp, series="KXBTC15M", bot="btc15m", pnl=1.0, contracts=1,
            )
            self.assertFalse(out["recorded"])
            self.assertEqual(desk_roi_plan.incubation_status(tmp, "KXBTC15M")["lane"], "main")

    def test_new_series_counts_and_staff_graduate(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(49):
                desk_roi_plan.record_incubation_settle(
                    tmp, series="KXNEON15M", bot="commodity-15m", pnl=0.5, contracts=1,
                )
            st = desk_roi_plan.incubation_status(tmp, "KXNEON15M")
            self.assertEqual(st["lane"], "incubation")
            self.assertFalse(st["promote_ready"])
            denied = desk_roi_plan.staff_graduate_incubation(tmp, "KXNEON15M")
            self.assertFalse(denied["ok"])
            desk_roi_plan.record_incubation_settle(
                tmp, series="KXNEON15M", bot="commodity-15m", pnl=0.5, contracts=1,
            )
            st = desk_roi_plan.incubation_status(tmp, "KXNEON15M")
            self.assertEqual(st["lane"], "ready_to_graduate")
            self.assertIn("staff graduate", desk_roi_plan.incubation_blocks_promote(tmp, "KXNEON15M"))
            armed = desk_roi_plan.staff_graduate_incubation(
                tmp, "KXNEON15M", note="n≥50 ok",
            )
            self.assertTrue(armed["ok"])
            self.assertEqual(
                desk_roi_plan.incubation_status(tmp, "KXNEON15M")["lane"], "graduated",
            )
            self.assertFalse(armed["auto_promote"])

    def test_enroll_main_into_incubation(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = desk_roi_plan.enroll_incubation(tmp, "KXWTI15M", note="re-test")
            self.assertTrue(out["ok"])
            self.assertEqual(out["lane"], "incubation")
            desk_roi_plan.record_incubation_settle(
                tmp, series="KXWTI15M", bot="commodity-15m", pnl=-1.0, contracts=1,
            )
            self.assertEqual(desk_roi_plan.incubation_status(tmp, "KXWTI15M")["n"], 1)

    def test_master_board(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.enroll_incubation(tmp, "KXTEST15M")
            summary = desk_master.master_summary(
                tmp,
                bots=[{"id": "btc15m", "open_risk": 0, "history": [], "gate_a": {}}],
                cfg={"max_open_risk": 100},
            )
            plan = summary.get("roi_plan") or {}
            self.assertIn("incubation", plan)
            self.assertEqual((plan.get("incubation") or {}).get("min_n"), 50)


if __name__ == "__main__":
    unittest.main()
