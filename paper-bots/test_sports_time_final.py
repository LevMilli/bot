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

    def test_empty_display_clock_is_end_of_slice_not_full_period(self):
        """Empty displayClock must not fall through to period_min (t-final DROP)."""
        self.assertEqual(
            desk_roi_plan._sports_clock_seconds({"period": 4, "displayClock": ""}),
            0.0,
        )
        rem = desk_roi_plan.sports_minutes_remaining(
            {"period": 4, "displayClock": ""}, league="NFL",
        )
        self.assertAlmostEqual(rem, 0.0, places=2)
        hit = desk_roi_plan.sports_time_final_hit(
            rem, bid=0.50, entry_price=0.80, cost=16.0, contracts=20,
        )
        self.assertTrue(hit["near_final"])
        self.assertTrue(hit["hit"])
        # End-of-period type with no clock fields → 0s in slice.
        rem_end = desk_roi_plan.sports_minutes_remaining(
            {
                "period": 4,
                "type": {"name": "STATUS_END_PERIOD", "detail": "End of 4th"},
            },
            league="NFL",
        )
        self.assertAlmostEqual(rem_end, 0.0, places=2)
        # Truly missing clock (no key, no end detail) keeps period_min guess.
        rem_miss = desk_roi_plan.sports_minutes_remaining(
            {"period": 4}, league="NFL",
        )
        self.assertAlmostEqual(rem_miss, 15.0, places=2)

    def test_short_detail_and_string_clock_densify_tfinal(self):
        """Absent displayClock must not period_min-DROP when shortDetail has mm:ss."""
        # Was rem=15 with period_min; shortDetail "2:00 - 4th" → rem=2 → near_final.
        rem = desk_roi_plan.sports_minutes_remaining(
            {"period": 4, "type": {"shortDetail": "2:00 - 4th"}},
            league="NFL",
        )
        self.assertAlmostEqual(rem, 2.0, places=2)
        hit = desk_roi_plan.sports_time_final_hit(
            rem, bid=0.50, entry_price=0.80, cost=16.0, contracts=20,
        )
        self.assertTrue(hit["near_final"])
        self.assertTrue(hit["hit"])
        # String clock seconds (some ESPN payloads stringify).
        self.assertEqual(
            desk_roi_plan._sports_clock_seconds({"period": 4, "clock": "90"}),
            90.0,
        )
        rem_str = desk_roi_plan.sports_minutes_remaining(
            {"period": 4, "clock": "90"}, league="NFL",
        )
        self.assertAlmostEqual(rem_str, 1.5, places=2)

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

    def test_hit_allows_finalized_loser_bid_zero(self):
        # Hit detection accepts bid=0, but settle wipe (rem≤0+bid=0) is not a trim
        # quote — record skips so promote EV is not poisoned by full-hold losers.
        hit = desk_roi_plan.sports_time_final_hit(
            0.0,
            bid=0.0,
            entry_price=0.72,
            cost=19.98,
            contracts=27,
        )
        self.assertTrue(hit["hit"])
        self.assertTrue(hit["near_final"])
        self.assertTrue(hit["underwater"])
        self.assertEqual(hit["bid"], 0.0)
        with tempfile.TemporaryDirectory() as tmp:
            rec = desk_roi_plan.record_sports_time_final_shadow(
                tmp,
                ticker="KX-TF-0",
                minutes_left=0.0,
                entry_price=0.72,
                bid=0.0,
                contracts=27,
                cost=19.98,
            )
            self.assertFalse(rec["recorded"])
            self.assertEqual(rec.get("skipped"), "settle_wipe_not_trim")
            # Mid-game wipe with rem>0 still records.
            mid = desk_roi_plan.record_sports_time_final_shadow(
                tmp,
                ticker="KX-TF-MID0",
                minutes_left=2.0,
                entry_price=0.72,
                bid=0.0,
                contracts=27,
                cost=19.98,
            )
            self.assertTrue(mid["recorded"], mid)

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
