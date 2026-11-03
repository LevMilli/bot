"""Sports hard-stop shadow + latency/fit wiring (positive-ROI next slice)."""
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


class SportsHardStopShadow(unittest.TestCase):
    def test_hit_threshold(self):
        hit = desk_roi_plan.sports_hard_stop_hit(0.80, 0.68, drop=0.12)
        self.assertTrue(hit["hit"])
        self.assertEqual(hit["threshold"], 0.68)
        miss = desk_roi_plan.sports_hard_stop_hit(0.80, 0.69, drop=0.12)
        self.assertFalse(miss["hit"])

    def test_shadow_never_live_by_default(self):
        self.assertFalse(desk_roi_plan.SPORTS_HARD_STOP_LIVE)
        with tempfile.TemporaryDirectory() as tmp:
            rec = desk_roi_plan.record_sports_hard_stop_shadow(
                tmp,
                ticker="KXNBA-T",
                side="home",
                league="NBA",
                entry_price=0.78,
                bid=0.60,
                contracts=20,
                cost=16.0,
            )
            self.assertTrue(rec["recorded"])
            self.assertTrue(rec["shadow_only"])
            summ = desk_roi_plan.sports_hard_stop_shadow_summary(tmp)
            self.assertEqual(summ["n"], 1)
            self.assertFalse(summ["live"])
            self.assertFalse(summ["auto_promote"])
            self.assertEqual(summ["decision"], "reject")  # n < 30

    def test_promote_stays_review_not_auto(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(30):
                desk_roi_plan.record_sports_hard_stop_shadow(
                    tmp,
                    ticker=f"T{i}",
                    entry_price=0.80,
                    bid=0.60,
                    contracts=10,
                    cost=5.0,  # shadow pnl positive-ish at bid 0.60
                )
            summ = desk_roi_plan.sports_hard_stop_shadow_summary(tmp)
            self.assertGreaterEqual(summ["n_with_pnl"], 30)
            # Even when EV looks ok, never auto-promote.
            self.assertFalse(summ["auto_promote"])
            self.assertFalse(summ["code_default_live"])
            self.assertFalse(desk_roi_plan.SPORTS_HARD_STOP_LIVE)
            self.assertIn(summ["decision"], ("review", "reject"))
            self.assertTrue(summ["promote_ready"])
            # Staff arm via file; code constant stays False.
            armed = desk_roi_plan.staff_set_sports_hard_stop_live(
                tmp, True, note="n≥30 shadow EV ok",
            )
            self.assertTrue(armed["ok"])
            self.assertTrue(desk_roi_plan.sports_hard_stop_is_live(tmp))
            self.assertFalse(desk_roi_plan.SPORTS_HARD_STOP_LIVE)
            disarmed = desk_roi_plan.staff_set_sports_hard_stop_live(tmp, False)
            self.assertTrue(disarmed["ok"])
            self.assertFalse(desk_roi_plan.sports_hard_stop_is_live(tmp))

    def test_staff_cannot_arm_before_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.record_sports_hard_stop_shadow(
                tmp, ticker="T0", entry_price=0.80, bid=0.60, contracts=10, cost=5.0,
            )
            denied = desk_roi_plan.staff_set_sports_hard_stop_live(tmp, True)
            self.assertFalse(denied["ok"])
            self.assertFalse(desk_roi_plan.sports_hard_stop_is_live(tmp))


class SportsLatencyFit(unittest.TestCase):
    def test_sports_m4_bar_is_45s(self):
        with tempfile.TemporaryDirectory() as tmp:
            for _ in range(5):
                desk_roi_plan.record_latency(tmp, bot="sports-gap", seconds=30.0)
            lat = desk_roi_plan.latency_p50(tmp, "sports-gap")
            self.assertEqual(lat["bar_s"], 45.0)
            self.assertTrue(lat["pass"])
            row = desk_master.tower_master_row(
                {"id": "sports-gap", "open_risk": 0, "history": [], "gate_a": {}},
                cfg={"max_open_risk": 100, "tower_risk_budgets": {"sports-gap": 0.35}},
                root=tmp,
            )
            self.assertEqual(row["M4_bar_s"], 45.0)
            self.assertTrue(row["passing"]["M4"])

    def test_master_exposes_hard_stop_shadow(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.record_sports_hard_stop_shadow(
                tmp, ticker="T", entry_price=0.8, bid=0.5, contracts=1, cost=1,
            )
            summary = desk_master.master_summary(
                tmp,
                bots=[{"id": "sports-gap", "today": 1, "open_risk": 0, "history": [], "gate_a": {}}],
                cfg={"max_open_risk": 100, "tower_risk_budgets": {"sports-gap": 0.35}},
            )
            plan = summary.get("roi_plan") or {}
            self.assertIn("sports_hard_stop_shadow", plan)
            self.assertFalse(plan["sports_hard_stop_shadow"]["live"])


class FeeFloorsStillLocked(unittest.TestCase):
    def test_floors(self):
        import desk_profit
        parsed, err = desk_profit.parse_venue_min_edge({"kalshi_sports": 0.03})
        self.assertIsNone(parsed)
        self.assertIn("cannot lower", err or "")


if __name__ == "__main__":
    unittest.main()
