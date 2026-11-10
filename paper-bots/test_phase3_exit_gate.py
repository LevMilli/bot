"""Phase 3 exit-gate certifier — intermediate exits + settle-backstop waivers."""
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


class Phase3ExitGate(unittest.TestCase):
    def test_default_plans_have_intermediate_exits(self):
        for bot in list(desk_roi_plan.FEE_CLEAR) + list(desk_roi_plan.LOSER_IDS):
            plan = desk_roi_plan.default_exit_plan(bot)
            self.assertTrue(
                desk_roi_plan._phase3_has_intermediate_exits(plan),
                msg=f"{bot} should not be bare settle-only: {plan.get('kind')}",
            )
            self.assertIn(bot, desk_roi_plan.PHASE3_SETTLE_BACKSTOP_WAIVERS)

    def test_bare_settle_fails_helper(self):
        bare = {"kind": "settle", "settle_backstop": True}
        self.assertFalse(desk_roi_plan._phase3_has_intermediate_exits(bare))
        self.assertFalse(desk_roi_plan._phase3_has_intermediate_exits(None))
        self.assertFalse(desk_roi_plan._phase3_has_intermediate_exits({}))

    def test_gate_passes_on_empty_desk(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = desk_roi_plan.phase3_exit_gate(tmp, bots=[])
            self.assertTrue(out["pass"], msg=out.get("label"))
            self.assertTrue(out["paper_only"])
            self.assertTrue(out["observe_only"])
            self.assertFalse(out["auto_promote"])
            self.assertFalse(out["live_orders_enabled"])
            self.assertFalse(out["board_chip"])
            self.assertEqual(out["phase"], "P3")
            self.assertTrue(out["btc_tp_honest"])
            self.assertTrue(out["commodity_flip_live"])
            self.assertTrue(out["sports_hard_stop_shadow"])
            self.assertTrue(out["sports_time_final_shadow"])
            self.assertEqual(out["bare_settle_only"], [])
            self.assertEqual(len(out["towers"]), 6)
            self.assertTrue(all(t["pass"] for t in out["towers"]))
            self.assertEqual(out["decision"], "phase3_exit_gate_pass")

    def test_coverage_fail_blocks_gate(self):
        bots = [{
            "id": "btc15m",
            "open": [{"ticker": "T1"}],  # missing exit_plan
        }]
        with tempfile.TemporaryDirectory() as tmp:
            out = desk_roi_plan.phase3_exit_gate(tmp, bots=bots)
            self.assertFalse(out["pass"])
            self.assertFalse(out["exit_plan_coverage"]["pass"])
            self.assertEqual(out["decision"], "phase3_exit_gate_fail")

    def test_coverage_pass_with_stamped_opens(self):
        bots = [{
            "id": "btc15m",
            "open": [{
                "ticker": "T1",
                "exit_plan": desk_roi_plan.default_exit_plan("btc15m"),
            }],
        }]
        with tempfile.TemporaryDirectory() as tmp:
            out = desk_roi_plan.phase3_exit_gate(tmp, bots=bots)
            self.assertTrue(out["pass"], msg=out.get("label"))
            self.assertEqual(out["exit_plan_coverage"]["n_open"], 1)
            self.assertEqual(out["exit_plan_coverage"]["n_with_plan"], 1)

    def test_masters_and_plan_summary_wire(self):
        bots = [
            {"id": "sports-gap", "today": 1, "open_risk": 5, "history": [], "gate_a": {},
             "open": [{"ticker": "S1", "exit_plan": desk_roi_plan.default_exit_plan("sports-gap")}]},
            {"id": "btc15m", "today": 1, "open_risk": 5, "history": [], "gate_a": {},
             "open": [{"ticker": "B1", "exit_plan": desk_roi_plan.default_exit_plan("btc15m")}]},
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
            p3 = (summary.get("roi_plan") or {}).get("phase3_exits")
            self.assertIsInstance(p3, dict)
            self.assertTrue(p3.get("pass"), msg=p3.get("label") if p3 else "missing")
            eq = (summary.get("roi_plan") or {}).get("exit_quality")
            self.assertIsInstance(eq, dict)
            plan = desk_roi_plan.plan_summary(tmp, bots=bots)
            self.assertIn("phase3_exits", plan)
            self.assertTrue(plan["phase3_exits"]["pass"])

    def test_btc_carry_and_coinbase_waivers_listed(self):
        self.assertIn("btc-carry", desk_roi_plan.PHASE3_SETTLE_BACKSTOP_WAIVERS)
        self.assertIn("coinbase-spot", desk_roi_plan.PHASE3_SETTLE_BACKSTOP_WAIVERS)
        self.assertTrue(
            desk_roi_plan._phase3_has_intermediate_exits(
                desk_roi_plan.default_exit_plan("btc-carry")
            )
        )
        self.assertTrue(
            desk_roi_plan._phase3_has_intermediate_exits(
                desk_roi_plan.default_exit_plan("coinbase-spot")
            )
        )


if __name__ == "__main__":
    unittest.main()
