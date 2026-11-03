"""Skip-regret weekly review card (Phase 8 helper loop)."""
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
import desk_top25


class SkipRegretWeekly(unittest.TestCase):
    def test_thin_sample_rejects(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(5):
                desk_top25.record_skip_regret(
                    tmp, bot="btc15m", ticker=f"T{i}", soft_gate="z", would_pnl=1.0,
                )
            card = desk_roi_plan.skip_regret_weekly_card(tmp, label="2026-11-03")
            self.assertEqual(card["decision"], "reject")
            self.assertFalse(card["auto_promote"])
            self.assertFalse(card["loosen_soft_gates"])
            self.assertTrue(card["fee_floors_locked"])
            self.assertEqual(
                desk_roi_plan.latest_skip_regret_weekly(tmp)["label"], "2026-11-03",
            )

    def test_green_twin_review_not_auto(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(22):
                desk_top25.record_skip_regret(
                    tmp, bot="sports-gap", ticker=f"S{i}", soft_gate="cushion",
                    would_pnl=0.5,
                )
            card = desk_roi_plan.skip_regret_weekly_card(tmp, label="2026-11-04")
            self.assertTrue(card["green_twin"])
            self.assertEqual(card["decision"], "review")
            self.assertFalse(card["auto_promote"])
            self.assertFalse(card["loosen_soft_gates"])


class MasterWire(unittest.TestCase):
    def test_master_exposes_skip_regret_weekly(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_top25.record_skip_regret(
                tmp, bot="btc15m", ticker="X", soft_gate="z", would_pnl=-1.0,
            )
            summary = desk_master.master_summary(
                tmp,
                bots=[{"id": "btc15m", "open_risk": 0, "history": [], "gate_a": {}}],
                cfg={"max_open_risk": 100},
            )
            plan = summary.get("roi_plan") or {}
            card = plan.get("skip_regret_weekly")
            self.assertIsInstance(card, dict)
            self.assertTrue(card.get("fee_floors_locked"))
            self.assertFalse(card.get("auto_promote"))


if __name__ == "__main__":
    unittest.main()
