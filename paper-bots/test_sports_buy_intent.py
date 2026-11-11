"""Sports gap writes a crash intent before cash moves. It does not invent a fill."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
GAP_DIR = os.path.join(HERE, "sports-gap-paper")
if GAP_DIR not in sys.path:
    sys.path.insert(0, GAP_DIR)

import gap_bot


class SportsBuyIntent(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "buy_intent.json")
        self._old = gap_bot.BUY_INTENT
        gap_bot.BUY_INTENT = self.path

    def tearDown(self):
        gap_bot.BUY_INTENT = self._old
        self.tmp.cleanup()

    def test_intent_uses_the_real_ask_and_does_not_buy(self):
        payload = gap_bot.write_buy_intent(
            fill_id="TICK|2026-11-11 10:00:00 CT",
            ticker="TICK",
            side="home",
            contracts=2,
            stake=12.5,
            ask=0.62,
        )
        self.assertEqual(payload["tower"], "sports-gap")
        self.assertEqual(payload["exit_rule"], "sports-gap live exit")
        self.assertTrue(payload["paper_only"])
        self.assertEqual(payload["status"], "intent")
        self.assertEqual(payload["ask"], 0.62)
        state = {"cash": 100.0, "open": [], "closed": [], "paper_only": True}
        self.assertEqual(gap_bot.reconcile_buy_intent(state), "abandoned")
        self.assertEqual(state["open"], [])
        self.assertEqual(state["cash"], 100.0)
        with open(self.path, encoding="utf-8") as handle:
            saved = json.loads(handle.read())
        self.assertEqual(saved["status"], "abandoned")
        self.assertNotIn("entry_price", saved)

    def test_saved_fill_is_resumed_not_duplicated(self):
        gap_bot.write_buy_intent(
            fill_id="TICK|1",
            ticker="TICK",
            side="away",
            contracts=1,
            stake=8.0,
            ask=0.55,
        )
        state = {
            "cash": 92.0,
            "open": [{"fill_id": "TICK|1", "ticker": "TICK", "ask": 0.55}],
            "closed": [],
        }
        self.assertEqual(gap_bot.reconcile_buy_intent(state), "open")
        self.assertEqual(len(state["open"]), 1)
        self.assertEqual(state["cash"], 92.0)

    def test_missing_ask_is_not_invented(self):
        with self.assertRaises(ValueError):
            gap_bot.write_buy_intent(
                fill_id="TICK|1",
                ticker="TICK",
                side="home",
                contracts=1,
                stake=8.0,
                ask=None,
            )
        self.assertFalse(os.path.exists(self.path))

    def test_fee_floor_unchanged(self):
        self.assertEqual(gap_bot.MIN_GAP, 0.06)


if __name__ == "__main__":
    unittest.main()
