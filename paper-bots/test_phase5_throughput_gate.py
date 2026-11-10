"""Phase 5 selective throughput gate — green-only +1, boost/NM locks, 2.0R."""
from __future__ import annotations

import json
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


class Phase5ThroughputGate(unittest.TestCase):
    def test_gate_passes_on_empty_desk(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = desk_roi_plan.phase5_throughput_gate(tmp, bots=[])
            self.assertTrue(out["pass"], msg=out.get("label"))
            self.assertTrue(out["paper_only"])
            self.assertTrue(out["observe_only"])
            self.assertFalse(out["auto_promote"])
            self.assertFalse(out["live_orders_enabled"])
            self.assertFalse(out["force_arm"])
            self.assertFalse(out["invent_fills"])
            self.assertEqual(out["phase"], "P5")
            self.assertEqual(out["decision"], "phase5_throughput_gate_pass")
            self.assertTrue(out["selective"]["pass"])
            self.assertEqual(out["sports_green_boost"]["green_boost"], 0)
            self.assertFalse(out["near_miss"]["code_live"])
            self.assertEqual(out["daily_r"]["commodity"], 2.0)
            self.assertEqual(out["empty_card"]["bar_sec"], 3.0)

    def test_selective_red_day_never_boosts(self):
        self.assertEqual(
            desk_more.selective_max_buys("btc15m", base=3, today=-2.0, green_boost=1),
            3,
        )
        self.assertEqual(
            desk_more.selective_max_buys("commodity-15m", base=3, today=1.0, green_boost=1),
            4,
        )
        self.assertEqual(
            desk_more.selective_max_buys("memecoin", base=3, today=9.0, green_boost=1),
            3,
        )

    def test_commodity_daily_r_locked_2(self):
        self.assertEqual(float(desk_roi_plan.DAILY_R_BUDGET["commodity-15m"]), 2.0)
        self.assertEqual(float(desk_roi_plan.DAILY_R_BUDGET["sports-gap"]), 1.5)
        self.assertEqual(float(desk_roi_plan.DAILY_R_BUDGET["btc15m"]), 2.0)

    def test_near_miss_locks(self):
        self.assertFalse(desk_roi_plan.NEAR_MISS_LIVE)
        self.assertGreaterEqual(int(desk_roi_plan.NEAR_MISS_PROMOTE_N), 30)
        self.assertEqual(float(desk_roi_plan.EMPTY_CARD_BAR_SEC), 3.0)

    def test_force_thin_near_miss_fails_without_artifact_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, desk_roi_plan.NEAR_MISS_PROMOTE_NAME)
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({
                    "paper_only": True,
                    "staff_approved": True,
                    "live": True,
                    "soft": "p",
                    "auto_promote": False,
                    "shadow_n": 5,  # thin — force-arm without evidence
                    "shadow_ev": -0.1,
                }, handle)
            out = desk_roi_plan.phase5_throughput_gate(tmp, bots=[])
            self.assertFalse(out["pass"], msg=out.get("label"))
            self.assertTrue(out["near_miss"]["force_armed_thin"])
            self.assertEqual(out["decision"], "phase5_throughput_gate_fail")

    def test_evidence_led_artifact_arm_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, desk_roi_plan.NEAR_MISS_PROMOTE_NAME)
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({
                    "paper_only": True,
                    "staff_approved": True,
                    "live": True,
                    "soft": "p",
                    "auto_promote": False,
                    "shadow_n": 35,
                    "shadow_ev": 1.2,
                }, handle)
            out = desk_roi_plan.phase5_throughput_gate(tmp, bots=[])
            self.assertTrue(out["pass"], msg=out.get("label"))
            self.assertTrue(out["near_miss"]["artifact_evidence_ok"])
            self.assertFalse(out["near_miss"]["force_armed_thin"])

    def test_masters_and_plan_summary_wire(self):
        bots = [
            {"id": "sports-gap", "today": 1, "open_risk": 5, "history": [], "gate_a": {}},
            {"id": "btc15m", "today": 1, "open_risk": 5, "history": [], "gate_a": {}},
            {"id": "commodity-15m", "today": -1, "open_risk": 5, "history": [], "gate_a": {}},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            summary = desk_master.master_summary(
                tmp,
                bots=bots,
                cfg={
                    "max_open_risk": 100,
                    "tower_risk_budgets": {
                        "sports-gap": 0.35, "btc15m": 0.3, "commodity-15m": 0.2,
                    },
                },
            )
            p5 = (summary.get("roi_plan") or {}).get("phase5_throughput")
            self.assertIsInstance(p5, dict)
            self.assertTrue(p5.get("pass"), msg=p5.get("label") if p5 else "missing")
            sel = (summary.get("roi_plan") or {}).get("selective_throughput")
            self.assertIsInstance(sel, dict)
            self.assertIs(sel.get("auto_promote"), False)
            plan = desk_roi_plan.plan_summary(tmp, bots=bots)
            self.assertIn("phase5_throughput", plan)
            self.assertTrue(plan["phase5_throughput"]["pass"])


if __name__ == "__main__":
    unittest.main()
