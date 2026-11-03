"""INX twin gates: anti-double, twin +1¢, pre/post macro (positive-ROI)."""
from __future__ import annotations

import os
import sys
import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_inx
import desk_profit

CT = ZoneInfo("America/Chicago")


class DeskInxGates(unittest.TestCase):
    def test_anti_double(self):
        msg = desk_inx.anti_double_blocks(
            ticker="KXINXU-26NOV03-B9000",
            sp_state={"open": [{"ticker": "KXINXU-26NOV03-B9000"}]},
        )
        self.assertIn("anti-double", msg)
        self.assertEqual(
            desk_inx.anti_double_blocks(
                ticker="OTHER",
                sp_state={"open": [{"ticker": "KXINXU-26NOV03-B9000"}]},
            ),
            "",
        )

    def test_twin_edge_extra_cent(self):
        self.assertIn(
            "twin edge",
            desk_inx.twin_edge_blocks(sized_edge=0.025, venue_edge=0.02, extra=0.01),
        )
        self.assertEqual(
            desk_inx.twin_edge_blocks(sized_edge=0.035, venue_edge=0.02, extra=0.01),
            "",
        )

    def test_post_macro_and_pre_fomc(self):
        skip = {"2026-11-10": ["CPI"], "2026-10-28": ["FOMC"]}
        early = desk_inx.post_macro_blackout(
            datetime(2026, 11, 10, 8, 40, tzinfo=CT), date(2026, 11, 10), skip,
        )
        self.assertTrue(early["blocked"])
        late = desk_inx.post_macro_blackout(
            datetime(2026, 11, 10, 9, 5, tzinfo=CT), date(2026, 11, 10), skip,
        )
        self.assertFalse(late["blocked"])
        pre = desk_inx.pre_fomc_calm_block(
            datetime(2026, 10, 27, 12, 30, tzinfo=CT), date(2026, 10, 27), skip,
        )
        self.assertTrue(pre["blocked"])
        morning = desk_inx.pre_fomc_calm_block(
            datetime(2026, 10, 27, 10, 0, tzinfo=CT), date(2026, 10, 27), skip,
        )
        self.assertFalse(morning["blocked"])

    def test_dual_side_research_helper(self):
        pick = desk_inx.dual_side_pick(
            [
                {"ticker": "HI", "ask": 0.90, "side": "yes"},
                {"ticker": "LO", "ask": 0.81, "side": "yes"},
            ],
            band_lo=0.80,
            band_hi=0.92,
        )
        self.assertEqual(pick["ticker"], "LO")

    def test_fee_floors_untouched(self):
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_inx"], 0.02)
        parsed, err = desk_profit.parse_venue_min_edge({"kalshi_inx": 0.01})
        self.assertIsNone(parsed)
        self.assertIn("cannot lower", err or "")

    def test_module_self_check(self):
        desk_inx.self_check()


if __name__ == "__main__":
    unittest.main()
