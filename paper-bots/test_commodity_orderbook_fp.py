"""Commodity depth_from_book must read Kalshi orderbook_fp (not invent depth 0)."""
from __future__ import annotations

import importlib.util
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


def _load_commodity():
    path = os.path.join(HERE, "commodity-15m-paper", "bot.py")
    spec = importlib.util.spec_from_file_location("commodity_15m_bot_obfp", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class CommodityOrderbookFp(unittest.TestCase):
    def test_orderbook_fp_yes_dollars_near_ask(self):
        cbot = _load_commodity()
        raw = {
            "orderbook_fp": {
                "yes_dollars": [
                    ["0.7800", "10.00"],
                    ["0.7900", "25.50"],
                    ["0.8000", "40.00"],
                ],
                "no_dollars": [
                    ["0.1800", "5.00"],
                ],
            }
        }
        spread, depth = cbot.depth_from_book(raw, "YES", 0.81)
        self.assertIsNotNone(spread)
        # Levels >= ask−MAX_SPREAD (=0.76) → 10 + 25 + 40
        self.assertGreaterEqual(depth, 75)
        self.assertLess(spread, 0.05)

    def test_orderbook_fp_string_qty_does_not_silent_zero(self):
        cbot = _load_commodity()
        raw = {
            "orderbook_fp": {
                "no_dollars": [["0.7200", "96.00"], ["0.7100", "12.25"]],
                "yes_dollars": [["0.2000", "1.00"]],
            }
        }
        spread, depth = cbot.depth_from_book(raw, "NO", 0.73)
        self.assertGreaterEqual(depth, 96)
        self.assertIsNotNone(spread)

    def test_legacy_orderbook_still_works(self):
        cbot = _load_commodity()
        raw = {
            "orderbook": {
                "yes": [[0.48, 5], [0.47, 10]],
                "no": [[0.50, 3]],
            }
        }
        spread, depth = cbot.depth_from_book(raw, "YES", 0.50)
        self.assertIsNotNone(spread)
        self.assertGreaterEqual(depth, 5)

    def test_empty_and_none_stay_depth_zero(self):
        cbot = _load_commodity()
        self.assertEqual(cbot.depth_from_book(None, "YES", 0.5), (None, 0))
        self.assertEqual(
            cbot.depth_from_book({"orderbook_fp": {"yes_dollars": [], "no_dollars": []}}, "YES", 0.8),
            (None, 0),
        )

    def test_fp_preferred_over_empty_legacy(self):
        """If both keys exist, fp wins — legacy empty must not mask thick fp."""
        cbot = _load_commodity()
        raw = {
            "orderbook": {"yes": [], "no": []},
            "orderbook_fp": {
                "yes_dollars": [["0.8400", "100.00"]],
                "no_dollars": [],
            },
        }
        _spread, depth = cbot.depth_from_book(raw, "YES", 0.85)
        self.assertGreaterEqual(depth, 100)

    def test_spread_gap_thick_book_not_invent_depth_zero(self):
        """0.02 < spread ≤ MAX_SPREAD must not densify invent depth 0."""
        cbot = _load_commodity()
        raw = {
            "orderbook_fp": {
                "yes_dollars": [
                    ["0.8000", "100.00"],
                    ["0.8500", "40.00"],
                    ["0.8800", "50.00"],  # best; 3¢ under ask
                ],
                "no_dollars": [],
            }
        }
        ask = 0.91
        spread, depth = cbot.depth_from_book(raw, "YES", ask)
        self.assertIsNotNone(spread)
        self.assertAlmostEqual(float(spread), 0.03, places=4)
        self.assertLessEqual(float(spread), cbot.MAX_SPREAD + 1e-12)
        # Old ask−0.02 window excluded 0.88 → invent 0; MAX_SPREAD includes it.
        self.assertGreaterEqual(depth, 50)


if __name__ == "__main__":
    unittest.main()
