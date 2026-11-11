"""Kalshi S&P writes a crash intent before cash moves. It does not invent a fill."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SP = os.path.join(HERE, "kalshi-sp500-paper")
if HERE not in sys.path:
    sys.path.insert(0, HERE)
if SP not in sys.path:
    sys.path.insert(0, SP)

import desk_profit
import paper_sim


class KalshiSpBuyIntent(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "buy_intent.json")
        self._old = paper_sim.BUY_INTENT
        paper_sim.BUY_INTENT = self.path

    def tearDown(self):
        paper_sim.BUY_INTENT = self._old
        self.tmp.cleanup()

    def test_intent_uses_the_exit_name_and_the_real_ask(self):
        written = paper_sim.write_buy_intent(
            fill_id="KXINXU-T|2026-11-11T12:05:00",
            ticker="KXINXU-T",
            side="yes",
            contracts=10,
            stake=8.7,
            ask=0.85,
        )
        self.assertEqual(written["exit_rule"], "model-flip bid under 50c")
        self.assertEqual(written["ask"], 0.85)
        self.assertTrue(written["paper_only"])
        self.assertEqual(paper_sim.BUY_EXIT_RULE, "model-flip bid under 50c")

    def test_missing_ask_is_not_invented(self):
        with self.assertRaises(ValueError):
            paper_sim.write_buy_intent(
                fill_id="KXINXU-T|1", ticker="KXINXU-T", side="yes",
                contracts=1, stake=1, ask=None,
            )
        self.assertFalse(os.path.exists(self.path))

    def test_abandoned_intent_does_not_create_a_position(self):
        paper_sim.write_buy_intent(
            fill_id="missing|1", ticker="KXINXU-T", side="yes",
            contracts=1, stake=1, ask=0.85,
        )
        state = {"bankroll": 500.0, "open": [], "closed": []}
        status = paper_sim.reconcile_buy_intent(state)
        self.assertEqual(status, "abandoned")
        self.assertEqual(state["open"], [])
        self.assertEqual(state["closed"], [])
        self.assertEqual(state["bankroll"], 500.0)

    def test_saved_fill_is_resumed_not_duplicated(self):
        paper_sim.write_buy_intent(
            fill_id="KXINXU-T|1", ticker="KXINXU-T", side="yes",
            contracts=10, stake=8.7, ask=0.85,
        )
        state = {
            "bankroll": 491.3,
            "open": [{"fill_id": "KXINXU-T|1", "ticker": "KXINXU-T"}],
            "closed": [],
        }
        status = paper_sim.reconcile_buy_intent(state)
        self.assertEqual(status, "open")
        self.assertEqual(len(state["open"]), 1)
        self.assertEqual(state["bankroll"], 491.3)

    def test_second_candidate_same_day_is_a_skip(self):
        self.assertEqual(
            paper_sim.second_fill_block(1, 1),
            "second candidate the same Chicago day is a skip",
        )
        self.assertEqual(paper_sim.second_fill_block(0, 1), "")
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_inx"], 0.02)


if __name__ == "__main__":
    unittest.main()
