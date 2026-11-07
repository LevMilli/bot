"""Desk-wide open-risk headroom — sports must not ignore other towers (E1 #116)."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_roi_plan


class DeskOpenRiskHeadroom(unittest.TestCase):
    def test_other_towers_consume_headroom(self):
        with tempfile.TemporaryDirectory() as tmp:
            bots = [
                {"id": "btc15m", "open_risk": 70.0},
                {"id": "commodity-15m", "open_risk": 20.0},
                {"id": "sports-gap", "open_risk": 5.0},
            ]
            head = desk_roi_plan.desk_open_risk_headroom(
                tmp,
                local_bot="sports-gap",
                local_open_risk=5.0,
                max_open_risk=100.0,
                bots=bots,
            )
            self.assertAlmostEqual(head["other_open_risk"], 90.0)
            self.assertAlmostEqual(head["local_open_risk"], 5.0)
            self.assertAlmostEqual(head["used"], 95.0)
            self.assertAlmostEqual(head["remaining"], 5.0)
            block = desk_roi_plan.desk_open_risk_blocks(
                tmp,
                local_bot="sports-gap",
                local_open_risk=5.0,
                add_cost=10.0,
                max_open_risk=100.0,
                bots=bots,
            )
            self.assertIn("desk max open risk", block)
            ok = desk_roi_plan.desk_open_risk_blocks(
                tmp,
                local_bot="sports-gap",
                local_open_risk=5.0,
                add_cost=4.0,
                max_open_risk=100.0,
                bots=bots,
            )
            self.assertEqual(ok, "")

    def test_local_only_when_no_others(self):
        with tempfile.TemporaryDirectory() as tmp:
            head = desk_roi_plan.desk_open_risk_headroom(
                tmp,
                local_bot="sports-gap",
                local_open_risk=40.0,
                max_open_risk=100.0,
                bots=[{"id": "sports-gap", "open_risk": 99.0}],
            )
            self.assertAlmostEqual(head["other_open_risk"], 0.0)
            self.assertAlmostEqual(head["used"], 40.0)
            self.assertAlmostEqual(head["remaining"], 60.0)

    def test_fee_floors_untouched(self):
        import desk_profit
        floors = desk_profit.venue_floors_locked()
        self.assertTrue(floors["locked"])
        self.assertAlmostEqual(floors["venues"]["kalshi_sports"]["floor"], 0.06)


if __name__ == "__main__":
    unittest.main()
