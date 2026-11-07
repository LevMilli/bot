"""Staff raise_Φ accept/defer decision log — never writes Φ / never softens floors."""
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


class RaisePhiDecisionLog(unittest.TestCase):
    def test_rejects_bad_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = desk_roi_plan.staff_log_raise_phi_decision(
                tmp, decision="apply", board="btc",
            )
            self.assertFalse(bad["ok"])
            self.assertFalse(bad["auto_write_phi"])

    def test_log_accept_and_defer(self):
        with tempfile.TemporaryDirectory() as tmp:
            accept = desk_roi_plan.staff_log_raise_phi_decision(
                tmp,
                decision="accept",
                board="btc",
                who="ops",
                note="hi-p miss — raise Φ next week",
                before_hit_rate=0.55,
                after_hit_rate=None,
            )
            self.assertTrue(accept["ok"])
            self.assertEqual(accept["row"]["decision"], "accept")
            self.assertAlmostEqual(accept["row"]["before_hit_rate"], 0.55)
            defer = desk_roi_plan.staff_log_raise_phi_decision(
                tmp,
                decision="defer",
                board="sports",
                who="ops",
                note="n thin",
                before_hit_rate=0.62,
                after_hit_rate=0.62,
            )
            self.assertTrue(defer["ok"])
            summary = desk_roi_plan.raise_phi_decision_log(tmp)
            self.assertEqual(summary["n"], 2)
            self.assertEqual(summary["accepts"], 1)
            self.assertEqual(summary["defers"], 1)
            self.assertFalse(summary["auto_write_phi"])
            self.assertTrue(summary["fee_floors_locked"])

    def test_master_exposes(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.staff_log_raise_phi_decision(
                tmp, decision="defer", board="btc", who="qa",
            )
            summary = desk_master.master_summary(
                tmp,
                bots=[{"id": "btc15m", "open_risk": 0, "history": [], "gate_a": {}}],
                cfg={"max_open_risk": 100},
            )
            plan = summary.get("roi_plan") or {}
            self.assertIn("raise_phi_decisions", plan)
            self.assertEqual(plan["raise_phi_decisions"]["n"], 1)

    def test_fee_floors_untouched(self):
        import desk_profit
        floors = desk_profit.venue_floors_locked()
        self.assertTrue(floors["locked"])
        self.assertTrue(floors["all_ok"])


if __name__ == "__main__":
    unittest.main()
