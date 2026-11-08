"""INX independent Φ fair re-entry — residual refuse until fee-clear fair."""

from __future__ import annotations

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

import desk_inx

CT = ZoneInfo("America/Chicago")


class InxFairReentryTests(unittest.TestCase):
    def test_deep_itm_yes_clears_venue(self):
        now = datetime(2026, 11, 10, 13, 0, tzinfo=CT)
        fair = desk_inx.fair_evaluate(
            {"ticker": "KX", "side": "yes", "ask": 0.85, "strike": 7200},
            venue_edge=0.02,
            spot=7500.0,
            now=now,
        )
        self.assertTrue(fair["ok"])
        self.assertGreaterEqual(float(fair["edge"]), 0.02)
        self.assertGreaterEqual(float(fair["p"]), 0.80)
        self.assertTrue(fair["fee_floors_locked"])

    def test_missing_spot_refuses_residual(self):
        now = datetime(2026, 11, 10, 13, 0, tzinfo=CT)
        fair = desk_inx.fair_evaluate(
            {"ticker": "KX", "side": "yes", "ask": 0.85, "strike": 7200},
            venue_edge=0.02,
            spot=-1.0,
            now=now,
        )
        self.assertFalse(fair["ok"])
        self.assertIn("residual", fair["reason"].lower())

    def test_thin_fair_skips(self):
        now = datetime(2026, 11, 10, 13, 0, tzinfo=CT)
        fair = desk_inx.fair_evaluate(
            {"ticker": "KX", "side": "yes", "ask": 0.90, "strike": 7495},
            venue_edge=0.02,
            spot=7500.0,
            now=now,
        )
        self.assertFalse(fair["ok"])
        self.assertTrue(
            "fair" in fair["reason"].lower() or "edge" in fair["reason"].lower()
            or "z" in fair["reason"].lower()
        )

    def test_no_side_symmetric(self):
        now = datetime(2026, 11, 10, 13, 0, tzinfo=CT)
        # Spot well below strike → NO is deep ITM.
        fair = desk_inx.fair_evaluate(
            {"ticker": "KX", "side": "no", "ask": 0.85, "strike": 7800},
            venue_edge=0.02,
            spot=7500.0,
            now=now,
        )
        self.assertTrue(fair["ok"])
        self.assertGreaterEqual(float(fair["p"]), 0.80)

    def test_pick_by_fair_prefers_value_over_rich_ask(self):
        now = datetime(2026, 11, 10, 13, 0, tzinfo=CT)
        # Highest ask RICH fails fair; VALUE clears — must pick VALUE.
        board = [
            {"ticker": "RICH", "side": "yes", "ask": 0.90, "strike": 7480},
            {"ticker": "VALUE", "side": "yes", "ask": 0.82, "strike": 7200},
        ]
        chosen = desk_inx.pick_by_fair(
            board, venue_edge=0.02, spot=7500.0, now=now,
        )
        self.assertTrue(chosen["ok"])
        self.assertEqual(chosen["pick"]["ticker"], "VALUE")
        self.assertGreaterEqual(int(chosen["n_ok"]), 1)
        self.assertGreaterEqual(float(chosen["fair"]["edge"]), 0.02)

    def test_self_check(self):
        desk_inx.self_check()


if __name__ == "__main__":
    unittest.main()
