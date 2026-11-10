"""Phase 11 continuous hillclimb gate — allowlist, raise-only, one-lever discipline."""
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


class Phase11HillclimbGate(unittest.TestCase):
    def test_gate_passes_on_empty_desk(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = desk_roi_plan.phase11_hillclimb_gate(tmp, bots=[])
            self.assertTrue(out["pass"], msg=out.get("label"))
            self.assertFalse(out["economic_pass"])
            self.assertTrue(out["steady_state"])
            self.assertTrue(out["paper_only"])
            self.assertTrue(out["observe_only"])
            self.assertFalse(out["auto_promote"])
            self.assertFalse(out["auto_apply"])
            self.assertFalse(out["auto_revert"])
            self.assertFalse(out["live_orders_enabled"])
            self.assertFalse(out["parallel_levers"])
            self.assertFalse(out["midweek_thrash"])
            self.assertEqual(out["phase"], "P11")
            self.assertEqual(out["decision"], "phase11_hillclimb_gate_pass")
            self.assertEqual(out["idea_review"]["review_days"], 90)
            self.assertEqual(out["daily_r"]["sports"], 1.5)
            self.assertEqual(out["daily_r"]["commodity"], 2.0)
            self.assertIsNone(out["economic"]["exit_gate"])

    def test_allowlist_and_raise_only(self):
        required = {
            "VOL_SAFE",
            "HIT_FOR_BIG",
            "venue_min_edge_btc",
            "min_cushion_btc",
            "kelly_fraction",
        }
        self.assertEqual(set(desk_roi_plan.HILLCLIMB_ALLOWLIST), required)
        self.assertTrue(desk_roi_plan.HILLCLIMB_ALLOWLIST["venue_min_edge_btc"]["raise_only"])
        self.assertTrue(desk_roi_plan.HILLCLIMB_ALLOWLIST["min_cushion_btc"]["raise_only"])
        self.assertEqual(desk_roi_plan.HILLCLIMB_NONE_LEVER, "NONE")
        self.assertEqual(int(desk_roi_plan.IDEA_REVIEW_DAYS), 90)
        self.assertFalse(desk_roi_plan.LIVE_ORDERS_ENABLED)

    def test_midweek_thrash_and_raise_only_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.staff_mark_sunday_packet_reviewed(tmp, who="test")
            first = desk_roi_plan.staff_pick_hillclimb_lever(
                tmp, "VOL_SAFE", note="week experiment",
            )
            self.assertTrue(first.get("ok"), msg=first)
            thrash = desk_roi_plan.staff_pick_hillclimb_lever(
                tmp, "HIT_FOR_BIG", note="thrash",
            )
            self.assertFalse(thrash.get("ok"))
            soft = desk_roi_plan.staff_pick_hillclimb_lever(
                tmp,
                "venue_min_edge_btc",
                proposed_value=0.03,
                force=True,
            )
            self.assertFalse(soft.get("ok"))

    def test_economic_pass_when_active_this_week(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.staff_mark_sunday_packet_reviewed(tmp, who="staff")
            pick = desk_roi_plan.staff_pick_hillclimb_lever(
                tmp, "NONE", note="observe week",
            )
            self.assertTrue(pick.get("ok"), msg=pick)
            out = desk_roi_plan.phase11_hillclimb_gate(tmp, bots=[])
            self.assertTrue(out["pass"], msg=out.get("label"))
            self.assertTrue(out["economic_pass"], msg=out.get("economic"))
            self.assertTrue(out["economic"]["active_this_week"])

    def test_kill_auto_revert_false(self):
        kill = desk_roi_plan.hillclimb_kill_status()
        self.assertFalse(kill.get("auto_revert"))
        disc = desk_roi_plan.hillclimb_one_lever_discipline()
        self.assertTrue(disc.get("pass") or disc.get("ok"))

    def test_masters_and_plan_summary_wire(self):
        bots = [
            {"id": "sports-gap", "today": 1, "open_risk": 5, "history": [], "gate_a": {}},
            {"id": "btc15m", "today": 1, "open_risk": 5, "history": [], "gate_a": {}},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            summary = desk_master.master_summary(
                tmp,
                bots=bots,
                cfg={
                    "max_open_risk": 100,
                    "tower_risk_budgets": {"sports-gap": 0.35, "btc15m": 0.3},
                },
            )
            p11 = (summary.get("roi_plan") or {}).get("phase11_hillclimb")
            self.assertIsInstance(p11, dict)
            self.assertTrue(p11.get("pass"), msg=p11.get("label") if p11 else "missing")
            plan = desk_roi_plan.plan_summary(tmp, bots=bots)
            self.assertIn("phase11_hillclimb", plan)
            self.assertTrue(plan["phase11_hillclimb"]["pass"])


if __name__ == "__main__":
    unittest.main()
