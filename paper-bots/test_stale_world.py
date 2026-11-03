"""Clock-skew / stale-world entry skip."""
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


class StaleWorld(unittest.TestCase):
    def test_no_history_allows(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(desk_roi_plan.stale_world_blocks(tmp, "btc15m"), "")

    def test_slow_loop_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.record_latency(tmp, bot="btc15m", seconds=41.0)
            msg = desk_roi_plan.stale_world_blocks(tmp, "btc15m")
            self.assertIn("stale-world", msg)
            self.assertIn("41", msg)
            # Fresh override clears.
            self.assertEqual(
                desk_roi_plan.stale_world_blocks(tmp, "btc15m", loop_seconds=5.0), ""
            )

    def test_sports_bar_higher(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.record_latency(tmp, bot="sports-gap", seconds=50.0)
            self.assertEqual(desk_roi_plan.stale_world_blocks(tmp, "sports-gap"), "")
            desk_roi_plan.record_latency(tmp, bot="sports-gap", seconds=91.0)
            self.assertIn("stale-world", desk_roi_plan.stale_world_blocks(tmp, "sports-gap"))

    def test_clock_skew_and_quote_age(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIn(
                "clock-skew",
                desk_roi_plan.stale_world_blocks(
                    tmp, "commodity-15m", loop_seconds=1.0, clock_skew_sec=31.0,
                ),
            )
            self.assertIn(
                "quote age",
                desk_roi_plan.stale_world_blocks(
                    tmp, "commodity-15m", loop_seconds=1.0, quote_age_sec=40.0,
                ),
            )

    def test_status_board(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.record_latency(tmp, bot="btc15m", seconds=99.0)
            st = desk_roi_plan.stale_world_status(tmp, bots=[{"id": "btc15m"}])
            self.assertIn("btc15m", st["blocked"])
            self.assertTrue(st["fee_floors_locked"])

    def test_master_exposes(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = desk_master.master_summary(
                tmp,
                bots=[{"id": "btc15m", "open_risk": 0, "history": [], "gate_a": {}}],
                cfg={"max_open_risk": 100},
            )
            plan = summary.get("roi_plan") or {}
            self.assertIn("stale_world", plan)
            self.assertTrue(plan.get("fee_floors_locked"))

    def test_fee_floors_untouched(self):
        import desk_profit
        floors = desk_profit.venue_floors_locked()
        self.assertTrue(floors["locked"])
        self.assertTrue(floors["all_ok"])


if __name__ == "__main__":
    unittest.main()
