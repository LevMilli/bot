"""E9 chaos drill pack (#968–979) — observe-only fail-closed."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_master
import desk_profit
import desk_roi_e9_chaos as chaos
import desk_roi_plan


class E9ChaosDrills(unittest.TestCase):
    def test_pack_passes_all_drills(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = chaos.run_chaos_drill_pack(tmp)
        self.assertTrue(out["ok"], msg=out.get("failed") or out.get("label"))
        self.assertEqual(out["n"], 12)
        self.assertEqual(out["passed_n"], 12)
        self.assertEqual(out["failed"], [])
        self.assertTrue(out["paper_only"])
        self.assertTrue(out["fee_floors_locked"])
        self.assertFalse(out["live_orders_enabled"])
        self.assertFalse(out["auto_apply"])
        self.assertFalse(out["force_arm"])
        ids = [d["id"] for d in out["drills"]]
        self.assertEqual(ids[0], "968_timer_dead")
        self.assertEqual(ids[-1], "979_floors_locked")

    def test_each_drill_individually(self):
        for drill_id, fn in chaos.CHAOS_DRILLS:
            with self.subTest(drill=drill_id):
                row = fn(None)
                self.assertTrue(row["ok"], msg=f"{drill_id}: {row.get('detail')} {row.get('evidence')}")
                self.assertTrue(row["fee_floors_locked"])
                self.assertFalse(row["live_orders_enabled"])

    def test_floors_never_softened(self):
        floors = chaos._floors_ok()
        self.assertTrue(floors["ok"])
        locked = desk_profit.venue_floors_locked()
        self.assertTrue(locked["locked"])
        self.assertTrue(locked["all_ok"])

    def test_commodity_daily_r_budget_locked(self):
        self.assertAlmostEqual(desk_roi_plan.daily_r_budget_for("commodity-15m"), 2.0)

    def test_masters_board_wire(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = desk_master.master_summary(
                tmp,
                bots=[{"id": "btc15m", "open_risk": 0, "history": [], "gate_a": {}}],
                cfg={"max_open_risk": 100},
            )
            plan = summary.get("roi_plan") or {}
            self.assertIn("chaos_drills", plan)
            board = plan["chaos_drills"]
            self.assertTrue(board["ok"])
            self.assertTrue(board["observe_only"])
            self.assertFalse(board["live_orders_enabled"])


if __name__ == "__main__":
    unittest.main()
