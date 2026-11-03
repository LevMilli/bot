"""Sports green_boost gate + green-or-gone Masters flags."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_master
import desk_more
import desk_roi_plan


class SportsGreenBoost(unittest.TestCase):
    def test_default_boost_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            st = desk_roi_plan.sports_green_boost_status(tmp, bots=[])
            self.assertFalse(st["ready"])
            self.assertEqual(st["green_boost"], 0)
            self.assertFalse(st["auto_promote"])
            self.assertEqual(desk_roi_plan.sports_green_boost(tmp), 0)

    def test_ready_when_weeks_hist_clv(self):
        with tempfile.TemporaryDirectory() as tmp:
            hist = [{"pnl": 0.10, "contracts": 1} for _ in range(20)]
            bots = [{"id": "sports-gap", "today": 2.0, "history": hist, "gate_a": {"ready": True}}]
            # Two weekly cards with sports_m1 ≥ 0.
            desk_roi_plan.capture_weekly_scorecard(tmp, bots=bots, label="2026-10-27")
            desk_roi_plan.capture_weekly_scorecard(tmp, bots=bots, label="2026-11-03")
            # CLV beat-close ≥52% with n≥20.
            for i in range(20):
                desk_more.record_sports_clv(
                    tmp,
                    ticker=f"KX-{i}",
                    side="home",
                    fair_entry=0.60,
                    close_fair=0.50 if i < 12 else 0.65,  # 12/20 = 0.60 beat
                    pnl=0.05,
                )
            st = desk_roi_plan.sports_green_boost_status(tmp, bots=bots)
            self.assertTrue(st["hist_ok"])
            self.assertTrue(st["weeks_ok"])
            self.assertTrue(st["clv_ok"])
            self.assertTrue(st["ready"])
            self.assertEqual(st["green_boost"], 1)

    def test_green_or_gone_flags_red_open(self):
        flags = desk_roi_plan.green_or_gone_status([
            {"id": "memecoin", "today": -5.0, "open_risk": 8.0, "gate_a": {"ready": False}},
            {"id": "btc15m", "today": 2.0, "open_risk": 10.0, "gate_a": {"ready": True}},
        ])
        self.assertFalse(flags["pass"])
        self.assertEqual(flags["flagged_n"], 1)
        self.assertEqual(flags["flags"][0]["bot"], "memecoin")

    def test_master_exposes(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = desk_master.master_summary(
                tmp,
                bots=[{"id": "sports-gap", "open_risk": 0, "history": [], "gate_a": {}}],
                cfg={"max_open_risk": 100},
            )
            plan = summary.get("roi_plan") or {}
            self.assertIn("sports_green_boost", plan)
            self.assertIn("green_or_gone", plan)
            self.assertTrue(plan.get("fee_floors_locked"))

    def test_fee_floors_untouched(self):
        import desk_profit
        floors = desk_profit.venue_floors_locked()
        self.assertTrue(floors["locked"])
        self.assertTrue(floors["all_ok"])


if __name__ == "__main__":
    unittest.main()
