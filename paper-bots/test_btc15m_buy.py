"""BTC 15-minute writes a crash intent before cash moves. A second side is not a hedge."""
from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest

import desk_profit

ROOT = os.path.dirname(os.path.abspath(__file__))


def _load_btc():
    path = os.path.join(ROOT, "btc15m-signal", "btc15m_signal.py")
    spec = importlib.util.spec_from_file_location("btc15m_buy", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Desk:
    def load_learning(self, root):
        return []

    def learning_skip(self, *args, **kwargs):
        return ""

    def prob_bucket(self, prob):
        return "0.8-0.9"

    def load_settings(self, root):
        return {}

    def venue_min_edge(self, venue, cfg):
        return 0.05

    def stake_dollars_for(self, *args, **kwargs):
        return 20.0, {"base": 20.0, "perf": {"proven_80": False}, "notes": []}

    def contracts_for_stake(self, per, stake):
        return 10

    def correlation_blocks(self, *args, **kwargs):
        return ""


class Btc15mBuy(unittest.TestCase):
    def setUp(self):
        self.btc = _load_btc()
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "buy_intent.json")
        self._old = self.btc.BUY_INTENT
        self.btc.BUY_INTENT = self.path
        self.btc._desk = lambda: _Desk()
        self.btc.save_account = lambda state: None
        self._shadow = self.btc.IS_SHADOW
        self.btc.IS_SHADOW = True

    def tearDown(self):
        self.btc.BUY_INTENT = self._old
        self.btc.IS_SHADOW = self._shadow
        self.tmp.cleanup()

    def test_intent_names_the_exit_and_the_real_ask(self):
        written = self.btc.write_buy_intent(
            fill_id="KXBTC15M-T|1",
            ticker="KXBTC15M-T",
            side="YES",
            contracts=10,
            stake=8.2,
            ask=0.80,
        )
        self.assertEqual(written["exit_rule"], "take-profit +15¢ cap 99¢ / model-flip")
        self.assertEqual(written["ask"], 0.80)
        self.assertTrue(written["paper_only"])
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_btc15m"], 0.05)

    def test_missing_ask_writes_no_file(self):
        with self.assertRaises(ValueError):
            self.btc.write_buy_intent(
                fill_id="KXBTC15M-T|1",
                ticker="KXBTC15M-T",
                side="YES",
                contracts=10,
                stake=8.2,
                ask=None,
            )
        self.assertFalse(os.path.exists(self.path))

    def test_second_side_is_not_a_hedge_and_abandon_invents_nothing(self):
        state = {"cash": 100.0, "open": [], "closed": []}
        msg = self.btc.paper_buy(
            state, "KXBTC15M-T", "YES", 0.80, 0.02, 0.88,
            "2026-11-11T18:00:00Z", True, edge=0.06, series="KXBTC15M",
        )
        self.assertIn("Paper buy", msg)
        self.assertEqual(len(state["open"]), 1)
        self.assertEqual(state["open"][0]["exit_rule"], "take-profit +15¢ cap 99¢ / model-flip")
        self.assertLess(state["cash"], 100.0)
        cash = state["cash"]
        with open(self.path, encoding="utf-8") as handle:
            intent = json.load(handle)
        self.assertEqual(intent["exit_rule"], "take-profit +15¢ cap 99¢ / model-flip")
        self.assertEqual(intent["ask"], 0.80)
        hedge = self.btc.paper_buy(
            state, "KXBTC15M-T", "NO", 0.80, 0.02, 0.88,
            "2026-11-11T18:00:00Z", True, edge=0.06, series="KXBTC15M",
        )
        self.assertEqual(hedge, "second side of the same window is not a hedge")
        self.assertEqual(len(state["open"]), 1)
        self.assertEqual(state["cash"], cash)
        empty = {"cash": 100.0, "open": [], "closed": []}
        self.assertEqual(self.btc.reconcile_buy_intent(empty), "abandoned")
        self.assertEqual(empty["open"], [])
        self.assertEqual(empty["cash"], 100.0)
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_btc15m"], 0.05)


if __name__ == "__main__":
    unittest.main()
