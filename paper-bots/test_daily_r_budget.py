"""Daily R budget → settle-only after tower hits target."""
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


class DailyRBudget(unittest.TestCase):
    def test_sports_1_5r_blocks(self):
        # 1.5R × $20 = $30
        self.assertEqual(desk_roi_plan.daily_r_budget_for("sports-gap"), 1.5)
        self.assertEqual(desk_roi_plan.daily_r_blocks("sports-gap", 29.99), "")
        msg = desk_roi_plan.daily_r_blocks("sports-gap", 30.0)
        self.assertIn("settle-only", msg)
        self.assertIn("sports-gap", msg)

    def test_btc_2r_threshold(self):
        status = desk_roi_plan.daily_r_status("btc15m", 39.0)
        self.assertFalse(status["settle_only"])
        status = desk_roi_plan.daily_r_status("btc15m", 40.0)
        self.assertTrue(status["settle_only"])
        self.assertEqual(status["target_usd"], 40.0)

    def test_board_and_master_wire(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = desk_roi_plan.capture_daily_r_board(
                tmp,
                bots=[
                    {"id": "sports-gap", "today": 32.0},
                    {"id": "commodity-15m", "today": 5.0},
                ],
                label="2026-11-03",
            )
            self.assertEqual(board["settle_only"], ["sports-gap"])
            self.assertTrue(board["fee_floors_locked"])
            summary = desk_master.master_summary(
                tmp,
                bots=[
                    {"id": "sports-gap", "today": 32.0, "open_risk": 0, "history": [], "gate_a": {}},
                    {"id": "btc15m", "today": 5.0, "open_risk": 0, "history": [], "gate_a": {}},
                ],
                cfg={"max_open_risk": 100},
            )
            plan = summary.get("roi_plan") or {}
            self.assertIn("daily_r", plan)
            self.assertIn("sports-gap", (plan.get("daily_r") or {}).get("settle_only") or [])

    def test_firm_health_prefers_live_bots_over_stale_daily_r(self):
        """Stale same-day settle_only=[] must not hide commodity 1.5R settle-only."""
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.capture_daily_r_board(
                tmp,
                bots=[{"id": "commodity-15m", "today": 0.0}],
                label="2026-11-09",
            )
            stale = desk_roi_plan.latest_daily_r_board(tmp) or {}
            self.assertEqual(stale.get("settle_only") or [], [])
            bots = [
                {"id": "commodity-15m", "today": 35.02, "open_risk": 0},
                {"id": "sports-gap", "today": 0.0, "open_risk": 0},
            ]
            out = desk_roi_plan.firm_health_observe(tmp, bots=bots, cfg={"max_open_risk": 100})
            self.assertIn("daily_r_settle", out.get("alerts") or [])
            self.assertIn(
                "commodity-15m",
                ((out.get("daily_r") or {}).get("settle_only") or []),
            )
            self.assertFalse(out.get("ok"))


if __name__ == "__main__":
    unittest.main()
