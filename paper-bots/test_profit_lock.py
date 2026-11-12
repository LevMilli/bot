"""Profit-lock harvest paper analog: weekly target → 0.5× size safe-mode."""
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


class ProfitLock(unittest.TestCase):
    def test_locks_after_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            day1 = desk_roi_plan.capture_profit_lock(
                tmp,
                bots=[{"id": "sports-gap", "today": 18.0}, {"id": "btc15m", "today": 10.0}],
                label="2026-11-03",
                target_usd=40.0,
            )
            self.assertFalse(day1["safe_mode"])
            self.assertEqual(day1["size_mult"], 1.0)
            day2 = desk_roi_plan.capture_profit_lock(
                tmp,
                bots=[{"id": "sports-gap", "today": 12.0}, {"id": "btc15m", "today": 5.0}],
                label="2026-11-04",
                target_usd=40.0,
            )
            # 28 + 17 = 45 ≥ 40
            self.assertTrue(day2["safe_mode"])
            self.assertEqual(day2["size_mult"], 0.5)
            self.assertEqual(desk_roi_plan.profit_lock_size_mult(tmp), 0.5)
            self.assertEqual(day2["week_pnl"], 45.0)

    def test_same_day_overwrite_not_double_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.capture_profit_lock(
                tmp,
                bots=[{"id": "btc15m", "today": 50.0}],
                label="2026-11-05",
                target_usd=40.0,
            )
            again = desk_roi_plan.capture_profit_lock(
                tmp,
                bots=[{"id": "btc15m", "today": 41.0}],
                label="2026-11-05",
                target_usd=40.0,
            )
            self.assertEqual(again["week_pnl"], 41.0)
            self.assertTrue(again["safe_mode"])

    def test_under_target_stays_full_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            status = desk_roi_plan.capture_profit_lock(
                tmp,
                bots=[{"id": "commodity-15m", "today": 5.0}],
                label="2026-11-06",
                target_usd=40.0,
            )
            self.assertFalse(status["safe_mode"])
            self.assertEqual(desk_roi_plan.profit_lock_size_mult(tmp), 1.0)


class MasterWire(unittest.TestCase):
    def test_master_exposes_profit_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = desk_master.master_summary(
                tmp,
                bots=[
                    {"id": "sports-gap", "today": 30.0, "open_risk": 0, "history": [], "gate_a": {}},
                    {"id": "btc15m", "today": 15.0, "open_risk": 0, "history": [], "gate_a": {}},
                ],
                cfg={"max_open_risk": 100},
            )
            self.assertIsInstance(summary.get("profit_lock"), dict)
            self.assertTrue(summary["profit_lock"]["safe_mode"])
            self.assertEqual(summary["profit_lock"]["size_mult"], 0.5)
            self.assertIn("profit_lock", summary.get("roi_plan") or {})

    def test_master_profit_lock_prefers_live_bots_over_stale(self):
        """Same-day stale week_pnl must not lag live commodity green (#487 twin)."""
        with tempfile.TemporaryDirectory() as tmp:
            morning = [{"id": "commodity-15m", "today": 10.16, "open_risk": 0, "history": [], "gate_a": {}}]
            desk_roi_plan.capture_profit_lock(tmp, bots=morning, label=desk_roi_plan._chicago_day())
            stale = (desk_roi_plan.profit_lock_status(tmp).get("latest") or {})
            self.assertAlmostEqual(float(stale.get("week_pnl") or 0), 10.16, places=2)
            live = [{"id": "commodity-15m", "today": 35.02, "open_risk": 0, "history": [], "gate_a": {}}]
            summary = desk_master.master_summary(
                tmp, bots=live, cfg={"max_open_risk": 100},
            )
            pl = summary.get("profit_lock") or {}
            row = pl.get("latest") if isinstance(pl.get("latest"), dict) else pl
            self.assertAlmostEqual(float(row.get("week_pnl") or 0), 35.02, places=2)


if __name__ == "__main__":
    unittest.main()
