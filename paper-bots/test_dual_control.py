"""Phase 9 dual-control checklist stub + quarterly re-baseline."""
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


class DualControl(unittest.TestCase):
    def test_live_hard_locked(self):
        self.assertFalse(desk_roi_plan.LIVE_ORDERS_ENABLED)

    def test_incomplete_until_two_staff_and_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            st = desk_roi_plan.dual_control_status(tmp)
            self.assertFalse(st["checklist_complete"])
            self.assertFalse(st["arm_ready_paper"])
            self.assertFalse(st["live_orders_enabled"])
            desk_roi_plan.staff_sign_dual_control(
                tmp, who="alice", role="primary", item_id="gate_a_pilot",
            )
            st = desk_roi_plan.dual_control_status(tmp)
            self.assertEqual(st["signed_n"], 1)
            self.assertFalse(st["arm_ready_paper"])

    def test_arm_ready_paper_still_blocks_live(self):
        with tempfile.TemporaryDirectory() as tmp:
            for iid, _ in desk_roi_plan.DUAL_CONTROL_ITEMS:
                desk_roi_plan.staff_sign_dual_control(
                    tmp, who="alice", role="primary", item_id=iid,
                )
            desk_roi_plan.staff_sign_dual_control(tmp, who="bob", role="secondary")
            st = desk_roi_plan.dual_control_status(tmp)
            self.assertTrue(st["checklist_complete"])
            self.assertTrue(st["two_staff"])
            self.assertTrue(st["arm_ready_paper"])
            self.assertFalse(st["live_orders_enabled"])
            self.assertTrue(st["code_live_lock"])

    def test_same_person_not_two_staff(self):
        with tempfile.TemporaryDirectory() as tmp:
            for iid, _ in desk_roi_plan.DUAL_CONTROL_ITEMS:
                desk_roi_plan.staff_sign_dual_control(
                    tmp, who="solo", role="primary", item_id=iid,
                )
            desk_roi_plan.staff_sign_dual_control(tmp, who="solo", role="secondary")
            st = desk_roi_plan.dual_control_status(tmp)
            self.assertFalse(st["two_staff"])
            self.assertFalse(st["arm_ready_paper"])

    def test_clear_resets(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.staff_sign_dual_control(
                tmp, who="alice", role="primary", item_id="fee_parity",
            )
            desk_roi_plan.staff_clear_dual_control(tmp, who="ops")
            st = desk_roi_plan.dual_control_status(tmp)
            self.assertEqual(st["signed_n"], 0)
            self.assertIsNone(st["primary"])

    def test_quarterly_rebaseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = desk_roi_plan.capture_quarterly_rebaseline(
                tmp,
                bots=[{"id": "btc15m", "today": 2.0, "cash": 100, "gate_a": {"ready": False}}],
                label="W-2026-Q4",
            )
            self.assertTrue(out["quarterly"])
            self.assertEqual(out.get("label"), "W-2026-Q4")
            st = desk_roi_plan.quarterly_rebaseline_status(tmp)
            self.assertTrue(st["has_quarterly"])
            self.assertTrue(st["fee_floors_locked"])

    def test_master_exposes(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = desk_master.master_summary(
                tmp,
                bots=[{"id": "btc15m", "open_risk": 0, "history": [], "gate_a": {}}],
                cfg={"max_open_risk": 100},
            )
            plan = summary.get("roi_plan") or {}
            self.assertIn("dual_control", plan)
            self.assertIn("quarterly_rebaseline", plan)
            self.assertTrue(plan.get("fee_floors_locked"))

    def test_fee_floors_untouched(self):
        import desk_profit
        floors = desk_profit.venue_floors_locked()
        self.assertTrue(floors["locked"])
        self.assertTrue(floors["all_ok"])


if __name__ == "__main__":
    unittest.main()
