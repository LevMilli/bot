"""Weekly cold harvest ledger (paper habit for live)."""
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


class ColdHarvest(unittest.TestCase):
    def test_harvests_green_week(self):
        with tempfile.TemporaryDirectory() as tmp:
            bots = [
                {"id": "sports-gap", "today": 25.0},
                {"id": "btc15m", "today": 25.0},
            ]
            desk_roi_plan.capture_profit_lock(tmp, bots=bots, label="2026-11-03")
            out = desk_roi_plan.capture_cold_harvest(
                tmp, bots=bots, label="2026-11-03", pct=0.40,
            )
            self.assertEqual(out["week_pnl"], 50.0)
            self.assertEqual(out["harvested"], 20.0)
            self.assertEqual(out["cold_total"], 20.0)
            self.assertFalse(out["skipped"])
            self.assertTrue(out["fee_floors_locked"])

    def test_skips_red_week(self):
        with tempfile.TemporaryDirectory() as tmp:
            bots = [{"id": "memecoin", "today": -12.0}]
            desk_roi_plan.capture_profit_lock(tmp, bots=bots, label="2026-11-03")
            out = desk_roi_plan.capture_cold_harvest(
                tmp, bots=bots, label="2026-11-03", pct=0.50,
            )
            self.assertEqual(out["harvested"], 0.0)
            self.assertTrue(out["skipped"])
            self.assertEqual(out["cold_total"], 0.0)

    def test_pct_clamped(self):
        self.assertEqual(desk_roi_plan._clamp_harvest_pct(0.10), 0.30)
        self.assertEqual(desk_roi_plan._clamp_harvest_pct(0.90), 0.50)
        self.assertEqual(desk_roi_plan._clamp_harvest_pct(0.40), 0.40)

    def test_idempotent_week_refresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            bots = [{"id": "btc15m", "today": 100.0}]
            desk_roi_plan.capture_profit_lock(tmp, bots=bots, label="2026-11-03")
            a = desk_roi_plan.capture_cold_harvest(
                tmp, bots=bots, label="2026-11-03", pct=0.30,
            )
            b = desk_roi_plan.capture_cold_harvest(
                tmp, bots=bots, label="2026-11-03", pct=0.30,
            )
            self.assertEqual(a["harvested"], b["harvested"])
            self.assertEqual(b["cold_total"], a["harvested"])  # not doubled

    def test_master_exposes(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = desk_master.master_summary(
                tmp,
                bots=[{
                    "id": "btc15m", "today": 10.0, "open_risk": 0,
                    "history": [], "gate_a": {},
                }],
                cfg={"max_open_risk": 100},
            )
            plan = summary.get("roi_plan") or {}
            self.assertIn("cold_harvest", plan)
            self.assertTrue(plan.get("fee_floors_locked"))

    def test_fee_floors_untouched(self):
        import desk_profit
        floors = desk_profit.venue_floors_locked()
        self.assertTrue(floors["locked"])
        self.assertTrue(floors["all_ok"])


if __name__ == "__main__":
    unittest.main()
