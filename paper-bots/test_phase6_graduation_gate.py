"""Phase 6 Master graduation gate — 2w M1–M7, thin_n, meme pause path."""
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


class Phase6GraduationGate(unittest.TestCase):
    def test_gate_passes_on_empty_desk(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = desk_roi_plan.phase6_graduation_gate(tmp, bots=[])
            self.assertTrue(out["pass"], msg=out.get("label"))
            self.assertFalse(out["economic_pass"])  # need ≥3 masters on board
            self.assertTrue(out["paper_only"])
            self.assertTrue(out["observe_only"])
            self.assertFalse(out["auto_promote"])
            self.assertFalse(out["live_orders_enabled"])
            self.assertFalse(out["force_arm"])
            self.assertFalse(out["invent_fills"])
            self.assertEqual(out["phase"], "P6")
            self.assertEqual(out["decision"], "phase6_graduation_gate_pass")
            self.assertEqual(out["graduation"]["weeks_required"], 2)
            self.assertIn("thin_n", out["graduation"]["denial_code_enum"])
            self.assertEqual(out["daily_r"]["commodity"], 2.0)
            self.assertFalse(out["meme"]["expand_volume"])
            self.assertFalse(out["meme"]["auto_retire"])

    def test_graduation_constants(self):
        self.assertEqual(desk_roi_plan.GRADUATION_WEEKS_REQUIRED, 2)
        self.assertEqual(
            tuple(desk_roi_plan.GRADUATION_CODES),
            ("M1", "M2", "M3", "M4", "M5", "M6", "M7"),
        )
        self.assertFalse(desk_roi_plan.LIVE_ORDERS_ENABLED)
        self.assertEqual(desk_roi_plan.MEME_RETIRE_WINDOW_DAYS, 20)

    def test_thin_n_denial_blocks_volume_only(self):
        denials = desk_roi_plan._graduation_denial_for_card(
            {"codes": {c: True for c in desk_roi_plan.GRADUATION_CODES}},
            n_settles=2,
        )
        self.assertIn("thin_n", denials)

    def test_meme_never_auto_retires(self):
        # Negative EV with enough n → recommend pause, never retired=True.
        hist = [{"pnl": -1.0, "contracts": 1} for _ in range(12)]
        clock = desk_roi_plan.meme_retirement_clock(
            {"id": "memecoin", "history": hist},
        )
        self.assertTrue(clock["recommend_pause"])
        self.assertFalse(clock["retired"])
        self.assertFalse(clock["expand_volume"])
        out = desk_roi_plan.phase6_graduation_gate(
            bots=[{"id": "memecoin", "history": hist}],
        )
        self.assertEqual(out["meme"]["status"], "paused")
        self.assertTrue(out["pass"], msg=out.get("label"))

    def test_order_covers_fee_clear_and_losers(self):
        order = set(desk_roi_plan.PHASE6_GRADUATION_ORDER)
        self.assertEqual(
            order,
            set(desk_roi_plan.FEE_CLEAR) | set(desk_roi_plan.LOSER_IDS),
        )

    def test_economic_pass_with_three_masters_and_meme_paused(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Seed two consecutive all-pass weeks for three towers.
            store = {"paper_only": True, "weeks": []}
            towers_pass = {
                bid: {
                    "all": True,
                    "codes": {c: True for c in desk_roi_plan.GRADUATION_CODES},
                }
                for bid in ("sports-gap", "btc15m", "commodity-15m")
            }
            for label in ("2026-11-02", "2026-11-09"):
                store["weeks"].append({"label": label, "towers": towers_pass})
            path = os.path.join(tmp, desk_roi_plan.MASTER_GRAD)
            import json
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(store, handle)
            meme_hist = [{"pnl": -1.0, "contracts": 1} for _ in range(12)]
            bots = [
                {"id": "sports-gap", "history": [{"pnl": 1}] * 10, "gate_a": {}},
                {"id": "btc15m", "history": [{"pnl": 1}] * 10, "gate_a": {}},
                {"id": "commodity-15m", "history": [{"pnl": 1}] * 10, "gate_a": {}},
                {"id": "memecoin", "history": meme_hist, "gate_a": {}},
            ]
            out = desk_roi_plan.phase6_graduation_gate(tmp, bots=bots)
            self.assertTrue(out["pass"], msg=out.get("label"))
            self.assertGreaterEqual(out["graduation"]["masters_n"], 3)
            self.assertEqual(out["meme"]["status"], "paused")
            self.assertTrue(out["economic_pass"], msg=out.get("label"))

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
            p6 = (summary.get("roi_plan") or {}).get("phase6_graduation")
            self.assertIsInstance(p6, dict)
            self.assertTrue(p6.get("pass"), msg=p6.get("label") if p6 else "missing")
            plan = desk_roi_plan.plan_summary(tmp, bots=bots)
            self.assertIn("phase6_graduation", plan)
            self.assertTrue(plan["phase6_graduation"]["pass"])


if __name__ == "__main__":
    unittest.main()
