"""Memecoin buy writes the exit intent before cash and does not average a falling name."""
from __future__ import annotations

import importlib.util
import inspect
import json
import os
import sys
import tempfile
import types
import unittest

import desk_profit

ROOT = os.path.dirname(os.path.abspath(__file__))


def _load():
    meme = os.path.join(ROOT, "memecoin-paper")
    if meme not in sys.path:
        sys.path.insert(0, meme)
    if "requests" not in sys.modules:
        stub = types.ModuleType("requests")
        stub.Session = lambda: types.SimpleNamespace(headers={})
        sys.modules["requests"] = stub
    path = os.path.join(meme, "bot.py")
    spec = importlib.util.spec_from_file_location("memecoin_buy", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class MemecoinBuy(unittest.TestCase):
    def setUp(self):
        self.bot = _load()
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "buy_intent.json")
        self._old = self.bot.BUY_INTENT
        self.bot.BUY_INTENT = self.path

    def tearDown(self):
        self.bot.BUY_INTENT = self._old
        self.tmp.cleanup()

    def test_intent_names_the_flip_and_the_stop_before_cash_moves(self):
        bot = self.bot
        state = {"cash_usd": 100.0, "open": []}
        seen = {}
        real = bot.write_buy_intent

        def _wrapped(**kwargs):
            seen["cash"] = state["cash_usd"]
            return real(**kwargs)

        bot.write_buy_intent = _wrapped
        pos = bot.commit_paper_buy(
            state, mint="MINT1", symbol="DOGE", pair="PAIR",
            price=1.0, liq=100000, ticket=10, conf=0.9, lane="accurate",
        )
        self.assertIsInstance(pos, dict)
        self.assertEqual(seen["cash"], 100.0)
        self.assertLess(state["cash_usd"], 100.0)
        self.assertEqual(pos["exit_rule"], "model-flip −6% then stop −12%")
        self.assertEqual(len(state["open"]), 1)
        with open(self.path, encoding="utf-8") as handle:
            saved = json.load(handle)
        self.assertEqual(saved["exit_rule"], "model-flip −6% then stop −12%")
        self.assertTrue(saved["paper_only"])
        self.assertEqual(saved["mint"], "MINT1")
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["solana_dex"], 0.02)
        src = inspect.getsource(bot.commit_paper_buy)
        self.assertLess(src.find("write_buy_intent"), src.find('st["cash_usd"]'))
        with self.assertRaises(ValueError):
            real(fill_id="x", mint="MINT1", symbol="DOGE", stake=10, price=0)

    def test_a_falling_open_name_is_not_averaged_and_an_abandoned_intent_adds_nothing(self):
        bot = self.bot
        state = {
            "cash_usd": 100.0,
            "open": [{
                "mint": "MINT1",
                "entry_market_price": 1.0,
                "tokens": 10,
                "fill_id": "old",
            }],
        }
        msg = bot.commit_paper_buy(
            state, mint="MINT1", symbol="DOGE", pair="PAIR",
            price=0.9, liq=100000, ticket=10, conf=0.9, lane="accurate",
        )
        self.assertEqual(msg, "do not average down a name that is open and falling")
        self.assertEqual(state["cash_usd"], 100.0)
        self.assertEqual(state["open"][0]["tokens"], 10)
        self.assertEqual(len(state["open"]), 1)
        self.assertFalse(os.path.exists(self.path))

        flat = bot.commit_paper_buy(
            state, mint="MINT1", symbol="DOGE", pair="PAIR",
            price=1.1, liq=100000, ticket=10, conf=0.9, lane="accurate",
        )
        self.assertEqual(flat, "already open")
        self.assertEqual(state["cash_usd"], 100.0)

        bot.write_buy_intent(
            fill_id="missing", mint="MINT2", symbol="PEPE", stake=10, price=1.0,
        )
        empty = {"cash_usd": 100.0, "open": []}
        self.assertEqual(bot.reconcile_buy_intent(empty), "abandoned")
        self.assertEqual(empty["open"], [])
        with open(self.path, encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)["status"], "abandoned")
        self.assertFalse(
            hasattr(bot.C, "expand_volume") and bool(getattr(bot.C, "expand_volume"))
        )


if __name__ == "__main__":
    unittest.main()
