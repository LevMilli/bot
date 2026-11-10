"""Phase 7 firm portfolio gate — correlation, daily R, profit-lock, incubation."""
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
import desk_roi_plan


class Phase7PortfolioGate(unittest.TestCase):
    def test_gate_passes_on_empty_desk(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = desk_roi_plan.phase7_portfolio_gate(tmp, bots=[])
            self.assertTrue(out["pass"], msg=out.get("label"))
            self.assertFalse(out["economic_pass"])
            self.assertTrue(out["paper_only"])
            self.assertTrue(out["observe_only"])
            self.assertFalse(out["auto_promote"])
            self.assertFalse(out["live_orders_enabled"])
            self.assertFalse(out["force_arm"])
            self.assertFalse(out["invent_fills"])
            self.assertEqual(out["phase"], "P7")
            self.assertEqual(out["decision"], "phase7_portfolio_gate_pass")
            self.assertTrue(out["correlation"]["btc_inx_veto"])
            self.assertTrue(out["correlation"]["meme_isolated"])
            self.assertEqual(out["daily_r"]["commodity"], 2.0)
            self.assertEqual(out["profit_lock"]["target_usd"], 40.0)
            self.assertEqual(out["profit_lock"]["size_mult_safe"], 0.5)
            self.assertEqual(out["incubation"]["min_n"], 50)
            self.assertTrue(out["meme_retirement"]["path_tested"])
            self.assertFalse(out["meme_retirement"]["auto_retire"])

    def test_correlation_locks(self):
        corr = desk_profit.correlation_matrix([])
        self.assertTrue(corr["btc_inx_veto"])
        self.assertTrue(corr["meme_isolated"])
        self.assertEqual(float(desk_profit.SERIES_HAIRCUT_MULT), 0.5)
        self.assertIn(("KXWTI15M", "KXBRENT15M"), desk_profit.SERIES_HAIRCUT_PAIRS)

    def test_daily_r_and_barbell_constants(self):
        self.assertEqual(float(desk_roi_plan.DAILY_R_BUDGET["sports-gap"]), 1.5)
        self.assertEqual(float(desk_roi_plan.DAILY_R_BUDGET["btc15m"]), 2.0)
        self.assertEqual(float(desk_roi_plan.DAILY_R_BUDGET["commodity-15m"]), 2.0)
        self.assertEqual(float(desk_roi_plan.BARBELL_MEME_MAX), 0.15)
        self.assertEqual(float(desk_roi_plan.BARBELL_FEE_CLEAR_MIN), 0.70)

    def test_profit_lock_and_incubation_locks(self):
        self.assertEqual(float(desk_roi_plan.PROFIT_LOCK_TARGET_USD), 40.0)
        self.assertEqual(float(desk_roi_plan.PROFIT_LOCK_SIZE_MULT), 0.5)
        self.assertGreaterEqual(int(desk_roi_plan.INCUBATION_MIN_N), 50)
        self.assertFalse(desk_roi_plan.LIVE_ORDERS_ENABLED)

    def test_meme_retirement_path_tested(self):
        hist = [{"pnl": -1.0, "contracts": 1} for _ in range(12)]
        clock = desk_roi_plan.meme_retirement_clock({"id": "memecoin", "history": hist})
        self.assertTrue(clock["recommend_pause"])
        self.assertFalse(clock["retired"])
        self.assertFalse(clock["expand_volume"])

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
            p7 = (summary.get("roi_plan") or {}).get("phase7_portfolio")
            self.assertIsInstance(p7, dict)
            self.assertTrue(p7.get("pass"), msg=p7.get("label") if p7 else "missing")
            plan = desk_roi_plan.plan_summary(tmp, bots=bots)
            self.assertIn("phase7_portfolio", plan)
            self.assertTrue(plan["phase7_portfolio"]["pass"])


if __name__ == "__main__":
    unittest.main()
