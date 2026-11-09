"""Hillclimb kill detector: M3↑ with M1↓ for 2 Chicago weeks → revert flag."""
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


class HillclimbKill(unittest.TestCase):
    def test_kill_when_m3_up_m1_down(self):
        with tempfile.TemporaryDirectory() as tmp:
            bots_good = [{"id": "btc15m", "history": [{"pnl": 3.0, "contracts": 1}] * 8}]
            # Week 1: fits mostly blocked → low M3.
            for _ in range(6):
                desk_roi_plan.record_fit(tmp, bot="btc15m", outcome="fit")
                desk_roi_plan.record_fit(tmp, bot="btc15m", outcome="block")
            desk_roi_plan.capture_hillclimb_week(
                tmp, bots=bots_good, label="2026-11-01", lever="HIT_FOR_BIG",
            )
            bots_worse = [{"id": "btc15m", "history": [{"pnl": 0.2, "contracts": 1}] * 8}]
            # Week 2: more buys → M3↑ while M1↓.
            for _ in range(12):
                desk_roi_plan.record_fit(tmp, bot="btc15m", outcome="fit")
                desk_roi_plan.record_fit(tmp, bot="btc15m", outcome="buy")
            out = desk_roi_plan.capture_hillclimb_week(
                tmp, bots=bots_worse, label="2026-11-08", lever="HIT_FOR_BIG",
            )
            self.assertTrue(out["status"]["kill"])
            self.assertEqual(out["status"]["action"], "revert_lever")
            self.assertFalse(out["status"]["auto_revert"])
            status = desk_roi_plan.hillclimb_kill_status(tmp)
            self.assertTrue(status["kill"])
            self.assertEqual(status["status"]["lever"], "HIT_FOR_BIG")

    def test_no_kill_when_m1_improves(self):
        with tempfile.TemporaryDirectory() as tmp:
            bots_a = [{"id": "sports-gap", "history": [{"pnl": 0.5, "contracts": 1}] * 6}]
            desk_roi_plan.record_fit(tmp, bot="sports-gap", outcome="buy")
            desk_roi_plan.capture_hillclimb_week(tmp, bots=bots_a, label="2026-11-01")
            bots_b = [{"id": "sports-gap", "history": [{"pnl": 1.5, "contracts": 1}] * 6}]
            for _ in range(4):
                desk_roi_plan.record_fit(tmp, bot="sports-gap", outcome="buy")
            out = desk_roi_plan.capture_hillclimb_week(tmp, bots=bots_b, label="2026-11-08")
            self.assertFalse(out["status"]["kill"])
            self.assertEqual(out["status"]["action"], "keep")

    def test_observe_until_two_weeks(self):
        with tempfile.TemporaryDirectory() as tmp:
            bots = [{"id": "btc15m", "history": [{"pnl": 1.0, "contracts": 1}] * 5}]
            out = desk_roi_plan.capture_hillclimb_week(tmp, bots=bots, label="2026-11-01")
            self.assertFalse(out["status"]["kill"])
            self.assertEqual(out["status"]["action"], "observe")


class MasterWire(unittest.TestCase):
    def test_master_exposes_hillclimb(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = desk_master.master_summary(
                tmp,
                bots=[{"id": "btc15m", "open_risk": 0, "history": [{"pnl": 1.0}] * 5, "gate_a": {}}],
                cfg={"max_open_risk": 100},
            )
            self.assertIsInstance(summary.get("hillclimb_kill"), dict)
            plan = summary.get("roi_plan") or {}
            self.assertIn("hillclimb_kill", plan)
            self.assertFalse(summary["hillclimb_kill"].get("auto_revert", True))

    def test_master_hillclimb_prefers_live_bots_over_stale(self):
        """Same-day stale hillclimb card must not lag live M1 (#488 twin)."""
        with tempfile.TemporaryDirectory() as tmp:
            morning = [{"id": "btc15m", "open_risk": 0, "history": [{"pnl": 1.0}] * 5, "gate_a": {}}]
            desk_roi_plan.capture_hillclimb_week(tmp, bots=morning, label="2026-11-09")
            stale = (desk_roi_plan.hillclimb_kill_status(tmp).get("latest") or {})
            self.assertAlmostEqual(float(stale.get("m1") or 0), 0.99, places=2)
            live = [{"id": "btc15m", "open_risk": 0, "history": [{"pnl": 2.0}] * 8, "gate_a": {}}]
            summary = desk_master.master_summary(
                tmp, bots=live, cfg={"max_open_risk": 100},
            )
            hc = summary.get("hillclimb_kill") or {}
            row = hc.get("latest") if isinstance(hc.get("latest"), dict) else hc
            self.assertAlmostEqual(float(row.get("m1") or 0), 1.99, places=2)


if __name__ == "__main__":
    unittest.main()
