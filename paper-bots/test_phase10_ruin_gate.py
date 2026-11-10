"""Phase 10 ruin drills & harvest gate — soft/hard/nuclear, cold, anti-revenge."""
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


class Phase10RuinGate(unittest.TestCase):
    def test_gate_passes_on_empty_desk(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = desk_roi_plan.phase10_ruin_gate(tmp, bots=[])
            self.assertTrue(out["pass"], msg=out.get("label"))
            self.assertFalse(out["economic_pass"])
            self.assertTrue(out["paper_only"])
            self.assertTrue(out["observe_only"])
            self.assertFalse(out["auto_promote"])
            self.assertFalse(out["live_orders_enabled"])
            self.assertFalse(out["force_arm"])
            self.assertFalse(out["invent_fills"])
            self.assertFalse(out["one_more_trade_override"])
            self.assertEqual(out["phase"], "P10")
            self.assertEqual(out["decision"], "phase10_ruin_gate_pass")
            self.assertEqual(out["ruin_drill"]["levels"], ["soft", "hard", "nuclear"])
            self.assertTrue(out["ruin_drill"]["block_probe_ok"])
            self.assertEqual(out["cold_harvest"]["pct_band"], [0.30, 0.50])
            self.assertEqual(out["cold_harvest"]["default_pct"], 0.40)
            self.assertEqual(out["anti_revenge"]["minutes"], 30)
            self.assertEqual(out["stale_world"]["clock_skew_max_s"], 30.0)
            self.assertEqual(out["fee_ledger"]["bar"], 0.80)
            self.assertEqual(out["daily_r"]["sports"], 1.5)
            self.assertEqual(out["daily_r"]["commodity"], 2.0)

    def test_gate_probe_does_not_mutate_caller_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            before = desk_roi_plan.ruin_drill_status(tmp)
            self.assertFalse(before.get("active"))
            self.assertEqual(int(before.get("history_n") or 0), 0)
            out = desk_roi_plan.phase10_ruin_gate(tmp, bots=[])
            self.assertTrue(out["pass"], msg=out.get("label"))
            after = desk_roi_plan.ruin_drill_status(tmp)
            self.assertFalse(after.get("active"))
            self.assertEqual(int(after.get("history_n") or 0), 0)
            self.assertFalse(after.get("practiced_this_month"))

    def test_ruin_levels_and_blocks(self):
        self.assertEqual(tuple(desk_roi_plan.RUIN_LEVELS), ("soft", "hard", "nuclear"))
        self.assertFalse(desk_roi_plan.LIVE_ORDERS_ENABLED)
        with tempfile.TemporaryDirectory() as tmp:
            armed = desk_roi_plan.set_ruin_drill(tmp, "soft", who="test")
            self.assertTrue(armed.get("ok"))
            msg = desk_roi_plan.ruin_drill_blocks_entries(tmp)
            self.assertIn("ruin drill", msg)
            cleared = desk_roi_plan.clear_ruin_drill(tmp, who="test")
            self.assertTrue(cleared.get("ok"))
            self.assertEqual(desk_roi_plan.ruin_drill_blocks_entries(tmp), "")

    def test_cold_harvest_band_and_anti_revenge(self):
        self.assertAlmostEqual(float(desk_roi_plan.COLD_HARVEST_PCT_MIN), 0.30)
        self.assertAlmostEqual(float(desk_roi_plan.COLD_HARVEST_PCT_MAX), 0.50)
        self.assertAlmostEqual(float(desk_roi_plan.COLD_HARVEST_PCT_DEFAULT), 0.40)
        self.assertEqual(int(desk_roi_plan.ANTI_REVENGE_MINUTES), 30)
        with tempfile.TemporaryDirectory() as tmp:
            cold = desk_roi_plan.cold_harvest_status(tmp)
            self.assertEqual(cold["pct_band"], [0.30, 0.50])
            anti = desk_roi_plan.anti_revenge_status(tmp)
            self.assertEqual(anti["minutes"], 30)

    def test_stale_world_and_fee_ledger_locks(self):
        self.assertAlmostEqual(float(desk_roi_plan.CLOCK_SKEW_MAX_SEC), 30.0)
        self.assertAlmostEqual(float(desk_roi_plan.STALE_LOOP_DEFAULT), 40.0)
        self.assertEqual(float(desk_roi_plan.DAILY_R_BUDGET["sports-gap"]), 1.5)
        self.assertEqual(float(desk_roi_plan.DAILY_R_BUDGET["commodity-15m"]), 2.0)
        with tempfile.TemporaryDirectory() as tmp:
            over = desk_roi_plan.stale_world_blocks(tmp, "btc15m", loop_seconds=99)
            under = desk_roi_plan.stale_world_blocks(tmp, "btc15m", loop_seconds=5)
            self.assertTrue(over)
            self.assertFalse(under)
            fee = desk_roi_plan.fee_ledger_completeness(tmp, bots=[])
            self.assertTrue(fee.get("pass"))
            self.assertEqual(fee.get("bar"), 0.80)

    def test_economic_pass_when_practiced(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.set_ruin_drill(tmp, "hard", who="staff", note="monthly drill")
            desk_roi_plan.clear_ruin_drill(tmp, who="staff", note="cleared")
            out = desk_roi_plan.phase10_ruin_gate(tmp, bots=[])
            self.assertTrue(out["pass"], msg=out.get("label"))
            self.assertTrue(out["economic_pass"], msg=out.get("economic"))
            self.assertTrue(out["economic"]["disaster_passed"])
            self.assertTrue(out["economic"]["harvest_visible"])

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
            p10 = (summary.get("roi_plan") or {}).get("phase10_ruin")
            self.assertIsInstance(p10, dict)
            self.assertTrue(p10.get("pass"), msg=p10.get("label") if p10 else "missing")
            plan = desk_roi_plan.plan_summary(tmp, bots=bots)
            self.assertIn("phase10_ruin", plan)
            self.assertTrue(plan["phase10_ruin"]["pass"])


if __name__ == "__main__":
    unittest.main()
