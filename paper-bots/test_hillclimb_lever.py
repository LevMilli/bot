"""Phase 11 hillclimb lever allowlist — one per Chicago week."""
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


class HillclimbLever(unittest.TestCase):
    def test_allowlist_raise_only(self):
        al = desk_roi_plan.hillclimb_allowlist()
        self.assertIn("VOL_SAFE", al["levers"])
        self.assertTrue(al["levers"]["venue_min_edge_btc"]["raise_only"])
        self.assertTrue(al["levers"]["min_cushion_btc"]["raise_only"])
        self.assertTrue(al["fee_floors_locked"])

    def test_pick_and_midweek_thrash_ban(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = desk_roi_plan.staff_pick_hillclimb_lever(
                tmp, "kelly_fraction", note="test", proposed_value=0.30,
            )
            self.assertTrue(out["ok"])
            self.assertEqual(out["active"]["lever"], "kelly_fraction")
            blocked = desk_roi_plan.staff_pick_hillclimb_lever(tmp, "VOL_SAFE")
            self.assertFalse(blocked["ok"])
            self.assertIn("thrash", blocked["reason"])
            # Same lever re-pick ok.
            again = desk_roi_plan.staff_pick_hillclimb_lever(
                tmp, "kelly_fraction", proposed_value=0.28,
            )
            self.assertTrue(again["ok"])

    def test_reject_soften_btc_floor(self):
        with tempfile.TemporaryDirectory() as tmp:
            soft = desk_roi_plan.staff_pick_hillclimb_lever(
                tmp, "venue_min_edge_btc", proposed_value=0.04,
            )
            self.assertFalse(soft["ok"])
            raise_ok = desk_roi_plan.staff_pick_hillclimb_lever(
                tmp, "venue_min_edge_btc", proposed_value=0.06,
            )
            self.assertTrue(raise_ok["ok"])

    def test_reject_unknown_lever(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = desk_roi_plan.staff_pick_hillclimb_lever(tmp, "LOWER_FLOORS")
            self.assertFalse(out["ok"])

    def test_demote_clears(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.staff_pick_hillclimb_lever(tmp, "HIT_FOR_BIG")
            dem = desk_roi_plan.staff_demote_hillclimb_lever(tmp, note="sunday")
            self.assertTrue(dem["ok"])
            self.assertIsNone(desk_roi_plan.active_hillclimb_lever(tmp))
            st = desk_roi_plan.hillclimb_lever_status(tmp)
            self.assertIsNone(st["active"])
            self.assertFalse(st["auto_revert"])

    def test_capture_week_reads_active_lever(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.staff_pick_hillclimb_lever(tmp, "VOL_SAFE")
            out = desk_roi_plan.capture_hillclimb_week(
                tmp,
                bots=[{"id": "btc15m", "history": [{"pnl": 0.1}]}],
                label="2026-11-03",
            )
            self.assertEqual(out["card"]["lever"], "VOL_SAFE")

    def test_master_exposes(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = desk_master.master_summary(
                tmp,
                bots=[{"id": "btc15m", "open_risk": 0, "history": [], "gate_a": {}}],
                cfg={"max_open_risk": 100},
            )
            plan = summary.get("roi_plan") or {}
            self.assertIn("hillclimb_lever", plan)
            self.assertTrue(plan.get("fee_floors_locked"))

    def test_fee_floors_untouched(self):
        import desk_profit
        floors = desk_profit.venue_floors_locked()
        self.assertTrue(floors["locked"])
        self.assertTrue(floors["all_ok"])


if __name__ == "__main__":
    unittest.main()
