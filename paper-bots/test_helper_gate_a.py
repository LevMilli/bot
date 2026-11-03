"""Helper Gate A: taxed EV before any autonomy story."""
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
import helpers


class HelperGateA(unittest.TestCase):
    def test_default_blocks_autonomy(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(desk_roi_plan.helper_may_place_alone(tmp, "calendar_scanner"))
            self.assertIn(
                "Gate A",
                desk_roi_plan.helper_autonomy_blocks(tmp, "calendar_scanner"),
            )
            self.assertFalse(helpers.may_place_alone(tmp, "calendar_scanner"))

    def test_gate_ready_still_needs_staff(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(desk_roi_plan.HELPER_GATE_A_MIN_N):
                desk_roi_plan.record_helper_fill(
                    tmp, helper="calendar_scanner", bot="btc15m",
                    ticker=f"T-{i}", pnl=0.08, contracts=1, fill_id=f"f-{i}",
                )
            gate = desk_roi_plan.helper_gate_a(tmp, "calendar_scanner")
            self.assertTrue(gate["ready"])
            self.assertFalse(gate["auto_promote"])
            self.assertFalse(gate["places_orders"])
            # Ready but not staff-armed.
            self.assertIn(
                "staff autonomy not armed",
                desk_roi_plan.helper_autonomy_blocks(tmp, "calendar_scanner"),
            )
            armed = desk_roi_plan.staff_set_helper_autonomy(
                tmp, "calendar_scanner", True, note="test arm",
            )
            self.assertTrue(armed["ok"])
            self.assertTrue(desk_roi_plan.helper_may_place_alone(tmp, "calendar_scanner"))
            desk_roi_plan.staff_set_helper_autonomy(tmp, "calendar_scanner", False)
            self.assertFalse(desk_roi_plan.helper_may_place_alone(tmp, "calendar_scanner"))

    def test_staff_cannot_arm_thin_sample(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.record_helper_fill(
                tmp, helper="eia_blackout", bot="commodity-15m",
                ticker="KXWTI", pnl=0.1, contracts=1,
            )
            out = desk_roi_plan.staff_set_helper_autonomy(tmp, "eia_blackout", True)
            self.assertFalse(out["ok"])
            self.assertFalse(out["autonomy"])

    def test_negative_ev_not_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(desk_roi_plan.HELPER_GATE_A_MIN_N):
                desk_roi_plan.record_helper_fill(
                    tmp, helper="bad-helper", bot="btc15m",
                    ticker=f"B-{i}", pnl=-0.05, contracts=1,
                )
            gate = desk_roi_plan.helper_gate_a(tmp, "bad-helper")
            self.assertFalse(gate["ready"])
            self.assertIsNotNone(gate["expectancy_taxed"])
            self.assertLess(gate["expectancy_taxed"], 0)

    def test_master_exposes(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = desk_master.master_summary(
                tmp,
                bots=[{"id": "btc15m", "open_risk": 0, "history": [], "gate_a": {}}],
                cfg={"max_open_risk": 100},
            )
            plan = summary.get("roi_plan") or {}
            self.assertIn("helper_gate_a", plan)
            self.assertTrue(plan.get("fee_floors_locked"))

    def test_fee_floors_untouched(self):
        import desk_profit
        floors = desk_profit.venue_floors_locked()
        self.assertTrue(floors["locked"])
        self.assertTrue(floors["all_ok"])


if __name__ == "__main__":
    unittest.main()
