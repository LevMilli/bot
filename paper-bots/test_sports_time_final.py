"""Sports Phase 3 time-to-final trim shadow — ≤5m left + underwater mark."""
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


class SportsTimeFinal(unittest.TestCase):
    def test_minutes_remaining_nba_q4(self):
        rem = desk_roi_plan.sports_minutes_remaining(
            {"period": 4, "displayClock": "3:00"}, league="NBA",
        )
        self.assertAlmostEqual(rem, 3.0, places=2)

    def test_minutes_remaining_nfl_q3(self):
        rem = desk_roi_plan.sports_minutes_remaining(
            {"period": 3, "displayClock": "5:00"}, league="NFL",
        )
        # 1Q left (15) + 5 = 20
        self.assertAlmostEqual(rem, 20.0, places=2)

    def test_hit_near_final_underwater(self):
        hit = desk_roi_plan.sports_time_final_hit(
            4.0,
            bid=0.40,
            entry_price=0.55,
            cost=5.5,
            contracts=10,
        )
        self.assertTrue(hit["hit"])
        self.assertTrue(hit["near_final"])
        self.assertTrue(hit["underwater"])
        self.assertTrue(hit["shadow_only"])

    def test_no_hit_when_far_from_final(self):
        hit = desk_roi_plan.sports_time_final_hit(
            12.0,
            bid=0.40,
            entry_price=0.55,
            cost=5.5,
            contracts=10,
        )
        self.assertFalse(hit["hit"])
        self.assertFalse(hit["near_final"])

    def test_no_hit_when_in_profit(self):
        hit = desk_roi_plan.sports_time_final_hit(
            3.0,
            bid=0.70,
            entry_price=0.40,
            cost=4.0,
            contracts=10,
        )
        self.assertFalse(hit["hit"])
        self.assertFalse(hit["underwater"])

    def test_shadow_summary_and_no_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            st = desk_roi_plan.sports_time_final_shadow_summary(tmp)
            self.assertTrue(st["evidence_thin"])
            self.assertFalse(st["promote_ready"])
            self.assertIn("THIN", st["label"])
            denied = desk_roi_plan.staff_set_sports_time_final_live(tmp, True)
            self.assertFalse(denied["ok"])
            for i in range(30):
                desk_roi_plan.record_sports_time_final_shadow(
                    tmp,
                    ticker=f"KX-{i}",
                    side="home",
                    league="NBA",
                    minutes_left=2.0,
                    entry_price=0.60,
                    bid=0.40,
                    contracts=10,
                    cost=6.0,
                )
            st2 = desk_roi_plan.sports_time_final_shadow_summary(tmp)
            self.assertGreaterEqual(st2["n_with_pnl"], 30)
            self.assertFalse(st2["promote_ready"])  # EV < 0
            armed = desk_roi_plan.staff_set_sports_time_final_live(
                tmp, True, force=True, note="test",
            )
            self.assertTrue(armed["ok"])
            self.assertTrue(desk_roi_plan.sports_time_final_is_live(tmp))

    def test_default_exit_plan_includes_tfinal(self):
        plan = desk_roi_plan.default_exit_plan("sports-gap")
        self.assertIn("time_final", plan["kind"])
        self.assertTrue(plan["time_final_shadow"])
        self.assertFalse(plan["time_final_live"])

    def test_master_exposes(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = desk_master.master_summary(
                tmp,
                bots=[{"id": "sports-gap", "open_risk": 0, "history": [], "gate_a": {}}],
                cfg={"max_open_risk": 100},
            )
            plan = summary.get("roi_plan") or {}
            self.assertIn("sports_time_final", plan)
            self.assertTrue(plan.get("fee_floors_locked"))

    def test_fee_floors_untouched(self):
        import desk_profit
        floors = desk_profit.venue_floors_locked()
        self.assertTrue(floors["locked"])
        self.assertAlmostEqual(floors["venues"]["kalshi_sports"]["floor"], 0.06)


if __name__ == "__main__":
    unittest.main()
