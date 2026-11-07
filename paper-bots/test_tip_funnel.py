"""Tip-window fill funnels per league."""
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


class TipFunnel(unittest.TestCase):
    def test_stages_and_board(self):
        with tempfile.TemporaryDirectory() as tmp:
            for stage in (
                "games_seen", "fee_clear", "sized", "bought", "block_budget", "block_edge",
            ):
                out = desk_roi_plan.record_tip_funnel(tmp, "NFL", stage)
                self.assertTrue(out["recorded"], stage)
            bad = desk_roi_plan.record_tip_funnel(tmp, "NCAAB", "games_seen")
            self.assertFalse(bad["recorded"])
            board = desk_roi_plan.tip_funnel_board(tmp)
            nfl = next(r for r in board["leagues"] if r["league"] == "NFL")
            self.assertEqual(nfl["games_seen"], 1)
            self.assertEqual(nfl["bought"], 1)
            self.assertEqual(nfl["block_budget"], 1)
            self.assertIsNotNone(nfl["budget_share"])

    def test_masters(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.record_tip_funnel(tmp, "NBA", "games_seen")
            plan = (desk_master.master_summary(
                tmp, bots=[{"id": "sports-gap", "open_risk": 0, "history": [], "gate_a": {}}],
                cfg={"max_open_risk": 100},
            ).get("roi_plan") or {})
            self.assertIn("tip_funnel", plan)


if __name__ == "__main__":
    unittest.main()
