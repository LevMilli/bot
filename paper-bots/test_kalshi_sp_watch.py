"""Kalshi S&P watch marks a real bid. A missing bid is not under 50 cents."""
from __future__ import annotations

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SP = os.path.join(HERE, "kalshi-sp500-paper")
if HERE not in sys.path:
    sys.path.insert(0, HERE)
if SP not in sys.path:
    sys.path.insert(0, SP)

import desk_profit
import paper_sim


class KalshiSpWatch(unittest.TestCase):
    def test_real_bid_is_marked_and_under_50_is_the_signal(self):
        pos = {"ticker": "KXINXU-T", "side": "yes"}
        self.assertEqual(paper_sim.mark_open(pos, 0.62), 0.62)
        self.assertEqual(pos["last_mark"], 0.62)
        self.assertFalse(paper_sim.bid_under_exit(0.62, 0.50))
        self.assertEqual(paper_sim.mark_open(pos, 0.49), 0.49)
        self.assertTrue(paper_sim.bid_under_exit(0.49, 0.50))
        self.assertFalse(paper_sim.bid_under_exit(0.50, 0.50))

    def test_missing_bid_is_not_under_50(self):
        pos = {"ticker": "KXINXU-T"}
        for raw in (None, "", 0, 0.0, 1, 1.2, "nope"):
            self.assertIsNone(paper_sim.mark_open(pos, raw))
            self.assertNotIn("last_mark", pos)
            self.assertFalse(paper_sim.bid_under_exit(raw, 0.50))
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_inx"], 0.02)


if __name__ == "__main__":
    unittest.main()
