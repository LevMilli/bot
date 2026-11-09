"""Phase 2 capital OS: barbell + midday util + zero-buy alerts."""
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


class CapitalOS(unittest.TestCase):
    def test_barbell_meme_cap(self):
        bad = desk_roi_plan.barbell_status(
            [{"id": "memecoin", "open_risk": 20}, {"id": "btc15m", "open_risk": 5}],
            {"max_open_risk": 100},
        )
        self.assertFalse(bad["meme_ok"])
        self.assertFalse(bad["pass"])
        good = desk_roi_plan.barbell_status(
            [
                {"id": "sports-gap", "open_risk": 35},
                {"id": "btc15m", "open_risk": 30},
                {"id": "memecoin", "open_risk": 5},
            ],
            {"max_open_risk": 100},
        )
        self.assertTrue(good["pass"])
        self.assertTrue(good["fee_floors_locked"])

    def test_shares_clamp_meme_even_when_green(self):
        shares = desk_more.effective_tower_shares(
            {"tower_risk_budgets": {
                **desk_more.DEFAULT_TOWER_BUDGET_SHARE,
                "memecoin": 0.25,
            }},
            meme_today=5.0,
        )
        self.assertLessEqual(shares["memecoin"], desk_roi_plan.BARBELL_MEME_MAX + 1e-12)

    def test_midday_edge_starvation_vs_idle(self):
        alert = desk_roi_plan.midday_util_alert(
            0.12, skip_board={"stable_top": [{"code": "EDGE", "n": 9}]},
        )
        self.assertTrue(alert["alert"])
        idle = desk_roi_plan.midday_util_alert(
            0.05, skip_board={"stable_top": [{"code": "NEWS", "n": 4}]},
        )
        self.assertFalse(idle["alert"])
        self.assertTrue(idle["correct_idle"])

    def test_zero_buy_budget_weekday(self):
        with tempfile.TemporaryDirectory() as tmp:
            # No buys + BUDGET dominant → alert on weekday (may be weekend in CI —
            # assert shape either way).
            out = desk_roi_plan.zero_buy_alert(
                tmp,
                skip_board={"stable_top": [{"code": "BUDGET", "n": 6}]},
            )
            self.assertIn("alert", out)
            self.assertTrue(out["budget_heavy"])
            self.assertTrue(out["fee_floors_locked"])
            if not out["is_weekend"]:
                self.assertTrue(out["alert"])

    def test_capital_os_board(self):
        with tempfile.TemporaryDirectory() as tmp:
            st = desk_roi_plan.capital_os_status(
                tmp,
                bots=[{"id": "btc15m", "open_risk": 40}],
                cfg={"max_open_risk": 100},
                desk_util=0.4,
            )
            self.assertIn("barbell", st)
            self.assertIn("midday_util", st)
            self.assertIn("zero_buy", st)
            cap = desk_roi_plan.capture_capital_os(
                tmp,
                bots=[{"id": "btc15m", "open_risk": 40}],
                cfg={"max_open_risk": 100},
                label="2026-11-03",
            )
            self.assertEqual(cap["label"], "2026-11-03")
            self.assertEqual(
                desk_roi_plan.latest_capital_os(tmp)["label"], "2026-11-03",
            )

    def test_master_exposes(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = desk_master.master_summary(
                tmp,
                bots=[{"id": "btc15m", "open_risk": 10, "history": [], "gate_a": {}}],
                cfg={"max_open_risk": 100},
            )
            plan = summary.get("roi_plan") or {}
            self.assertIn("capital_os", plan)
            self.assertTrue(plan.get("fee_floors_locked"))

    def test_master_capital_os_prefers_live_bots_over_stale(self):
        """Same-day stale ok=True must not hide live barbell fail (#485 twin)."""
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.capture_capital_os(
                tmp,
                bots=[{"id": "btc15m", "open_risk": 0}],
                cfg={"max_open_risk": 100},
                label="2026-11-09",
            )
            stale = desk_roi_plan.latest_capital_os(tmp) or {}
            self.assertTrue(stale.get("ok"))
            bots = [
                {"id": "btc-carry", "open_risk": 500.0, "history": [], "gate_a": {}},
                {"id": "btc15m", "open_risk": 0.0, "history": [], "gate_a": {}},
            ]
            summary = desk_master.master_summary(
                tmp, bots=bots, cfg={"max_open_risk": 100},
            )
            cos = ((summary.get("roi_plan") or {}).get("capital_os") or {})
            self.assertFalse(cos.get("ok"))
            self.assertIn("barbell", cos.get("alerts") or [])
            fh = desk_roi_plan.firm_health_observe(
                tmp, bots=bots, cfg={"max_open_risk": 100},
            )
            self.assertFalse((fh.get("capital_os") or {}).get("ok"))

    def test_fee_floors_untouched(self):
        import desk_profit
        floors = desk_profit.venue_floors_locked()
        self.assertTrue(floors["locked"])
        self.assertTrue(floors["all_ok"])


if __name__ == "__main__":
    unittest.main()
