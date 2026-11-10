"""E9 doctrine + distance milestone board (#951–954, #981–986)."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_master
import desk_profit
import desk_roi_e9_doctrine as doctrine
import desk_roi_plan


class E9DoctrineDistance(unittest.TestCase):
    def test_combined_board_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            bots = [
                {"id": "btc15m", "today": -80.0, "open_risk": 0, "history": []},
                {"id": "sports-gap", "today": -40.0, "open_risk": 0, "history": []},
            ]
            desk_roi_plan.capture_baseline(tmp, bots=bots, label="W0")
            out = doctrine.doctrine_distance_board(tmp, bots=bots)
        self.assertTrue(out["ok"], msg=out.get("label"))
        self.assertTrue(out["paper_only"])
        self.assertTrue(out["fee_floors_locked"])
        self.assertFalse(out["live_orders_enabled"])
        self.assertFalse(out["tip_chips"])
        self.assertFalse(out["auto_apply"])
        self.assertFalse(out["force_arm"])
        self.assertEqual(out["doctrine_cards"]["n"], 5)
        self.assertEqual(out["distance_milestones"]["n"], 5)

    def test_milestones_earned_only_no_invent(self):
        with tempfile.TemporaryDirectory() as tmp:
            bots = [{"id": "btc15m", "today": -200.0, "history": []}]
            board = doctrine.distance_milestone_board(tmp, bots=bots)
        self.assertTrue(board["celebrate_only_earned"])
        self.assertTrue(board["no_spreadsheet_edits"])
        # −$225 earned; −$150 not yet at −$200.
        by_id = {m["id"]: m for m in board["milestones"]}
        self.assertTrue(by_id["m_neg225"]["earned"])
        self.assertFalse(by_id["m_neg150"]["earned"])
        self.assertFalse(by_id["m_zero"]["earned"])
        for m in board["milestones"]:
            self.assertFalse(m["invented"])
            self.assertEqual(m["celebrate"], m["earned"])

    def test_variance_and_annual_never_soften(self):
        v = doctrine.variance_clause_card()
        self.assertFalse(v["soften_floors_allowed"])
        self.assertTrue(v["fee_floors_locked"])
        a = doctrine.annual_floor_review_card()
        self.assertTrue(a["raise_ok"])
        self.assertTrue(a["lower_forbidden_without_research_staff"])
        floors = desk_profit.venue_floors_locked()
        self.assertTrue(floors["locked"] and floors["all_ok"])

    def test_e9_exit_dual_control_locked(self):
        with tempfile.TemporaryDirectory() as tmp:
            card = doctrine.e9_exit_card(tmp, bots=[])
        self.assertTrue(card["dual_control_locked"])
        self.assertFalse(card["live_orders_enabled"])
        self.assertFalse(card["auto_apply"])
        self.assertTrue(card["ok"])

    def test_masters_wire(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = desk_master.master_summary(
                tmp,
                bots=[{"id": "btc15m", "today": -100.0, "open_risk": 0, "history": [], "gate_a": {}}],
                cfg={"max_open_risk": 100},
            )
            plan = summary.get("roi_plan") or {}
            self.assertIn("doctrine_distance", plan)
            board = plan["doctrine_distance"]
            self.assertTrue(board["ok"])
            self.assertTrue(board["observe_only"])
            self.assertFalse(board["tip_chips"])


if __name__ == "__main__":
    unittest.main()
