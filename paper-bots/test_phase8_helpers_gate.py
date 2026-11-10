"""Phase 8 helper evidence gate — Gate A, exec lock, skip-regret, advice lift."""
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
import desk_roi_e4


class Phase8HelpersGate(unittest.TestCase):
    def test_gate_passes_on_empty_desk(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = desk_roi_plan.phase8_helpers_gate(tmp, bots=[])
            self.assertTrue(out["pass"], msg=out.get("label"))
            self.assertFalse(out["economic_pass"])
            self.assertTrue(out["paper_only"])
            self.assertTrue(out["observe_only"])
            self.assertFalse(out["auto_promote"])
            self.assertFalse(out["live_orders_enabled"])
            self.assertFalse(out["force_arm"])
            self.assertFalse(out["invent_fills"])
            self.assertFalse(out["places_orders"])
            self.assertEqual(out["phase"], "P8")
            self.assertEqual(out["decision"], "phase8_helpers_gate_pass")
            self.assertEqual(out["helper_gate_a"]["min_n"], 20)
            self.assertFalse(out["helper_gate_a"]["auto_promote"])
            self.assertFalse(out["autonomy"]["may_place_alone_default"])
            self.assertFalse(out["autonomy"]["calendar_scanner_alone"])
            self.assertTrue(out["execution_lock"]["pass"])
            self.assertFalse(out["skip_regret"]["loosen_soft_gates"])
            self.assertTrue(out["advice_lift"]["gate_a_path"])
            self.assertFalse(out["gate_a_pilots"]["staff_arm"])
            self.assertFalse(out["eth_calibration"]["auto_write_phi"])
            self.assertEqual(out["ladder_parlay_shadow"]["ladder_min_p"], 0.80)
            self.assertEqual(out["daily_r"]["sports"], 1.5)
            self.assertEqual(out["daily_r"]["commodity"], 2.0)

    def test_helper_gate_a_and_autonomy_locks(self):
        self.assertEqual(int(desk_roi_plan.HELPER_GATE_A_MIN_N), 20)
        self.assertFalse(desk_roi_plan.LIVE_ORDERS_ENABLED)
        with tempfile.TemporaryDirectory() as tmp:
            alone = desk_roi_plan.helper_may_place_alone(tmp, "calendar_scanner")
            block = desk_roi_plan.helper_autonomy_blocks(tmp, "calendar_scanner")
            self.assertFalse(alone)
            self.assertTrue(isinstance(block, str) and block)
            gate = desk_roi_plan.helper_gate_a(tmp)
            self.assertFalse(gate["auto_promote"])
            self.assertFalse(gate["places_orders"])
            self.assertEqual(gate["min_n"], 20)
            promote = desk_roi_plan.helper_promote_status(tmp)
            self.assertFalse(promote["auto_promote"])
            self.assertFalse(promote["places_orders"])

    def test_insight_exec_lock_and_advice_observe(self):
        lock = desk_roi_e4.insight_helpers_execution_lock(HERE)
        self.assertTrue(lock.get("pass") or lock.get("ok"), msg=lock.get("label"))
        self.assertFalse(lock.get("may_place_alone"))
        self.assertFalse(lock.get("places_orders"))
        self.assertFalse(lock.get("auto_promote"))
        with tempfile.TemporaryDirectory() as tmp:
            advice = desk_roi_e4.helper_advice_lift_board(tmp)
            self.assertTrue(advice.get("gate_a_path"))
            self.assertFalse(advice.get("auto_promote"))
            self.assertFalse(advice.get("places_orders"))
            self.assertFalse(advice.get("staff_arm"))
            pilots = desk_roi_e4.gate_a_pilots_board(tmp)
            self.assertFalse(pilots.get("auto_promote"))
            self.assertFalse(pilots.get("staff_arm"))

    def test_skip_regret_never_loosens(self):
        with tempfile.TemporaryDirectory() as tmp:
            cands = desk_roi_plan.skip_regret_candidates(tmp)
            log = desk_roi_plan.skip_regret_decision_log(tmp)
            self.assertFalse(cands.get("auto_promote"))
            self.assertFalse(log.get("auto_promote"))
            self.assertFalse(log.get("loosen_soft_gates"))
            bad = desk_roi_plan.staff_log_skip_regret_decision(
                tmp, decision="accept", soft="edge_floor",
            )
            self.assertFalse(bad.get("ok"))
            self.assertFalse(bad.get("loosen_soft_gates"))

    def test_daily_r_and_ladder_locks(self):
        self.assertEqual(float(desk_roi_plan.DAILY_R_BUDGET["sports-gap"]), 1.5)
        self.assertEqual(float(desk_roi_plan.DAILY_R_BUDGET["commodity-15m"]), 2.0)
        import desk_phase3
        self.assertAlmostEqual(float(desk_phase3.LADDER_MIN_P), 0.80)
        eth = desk_roi_plan.eth_calibration_report([])
        self.assertFalse(eth.get("auto_write_phi"))

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
            p8 = (summary.get("roi_plan") or {}).get("phase8_helpers")
            self.assertIsInstance(p8, dict)
            self.assertTrue(p8.get("pass"), msg=p8.get("label") if p8 else "missing")
            plan = desk_roi_plan.plan_summary(tmp, bots=bots)
            self.assertIn("phase8_helpers", plan)
            self.assertTrue(plan["phase8_helpers"]["pass"])


if __name__ == "__main__":
    unittest.main()
