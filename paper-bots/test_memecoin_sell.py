"""Memecoin failsafe sells the held name at a real mark and does not buy it back."""
from __future__ import annotations

import importlib.util
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
    spec = importlib.util.spec_from_file_location("memecoin_sell", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pos():
    return {
        "mint": "MINT1",
        "symbol": "DOGE",
        "entry_market_price": 1.0,
        "tokens_left": 10,
    }


class MemecoinSell(unittest.TestCase):
    def test_the_held_name_sells_at_the_real_mark_and_records_which_exit(self):
        bot = _load()
        pos = _pos()
        flip = bot.failsafe_sale(pos, 0.94)
        self.assertEqual(flip["exit"], "model-flip −6%")
        self.assertEqual(flip["mark"], 0.94)
        self.assertEqual(flip["mint"], "MINT1")
        self.assertTrue(flip["sold"])
        hard = bot.failsafe_sale(pos, 0.88)
        self.assertEqual(hard["exit"], "stop −12%")
        self.assertEqual(hard["mark"], 0.88)
        self.assertIsNone(bot.failsafe_sale(pos, 0.95))
        self.assertIsNone(bot.failsafe_sale(pos, None))
        self.assertIsNone(bot.failsafe_sale(pos, 0))
        self.assertIsNone(bot.failsafe_sale(pos, 0.90, mint="MINT2"))
        self.assertEqual(pos["tokens_left"], 10)
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["solana_dex"], 0.02)
        self.assertIn("failsafe_sale", bot.manage.__code__.co_names)

    def test_a_sold_name_is_not_bought_back_on_the_same_pass(self):
        bot = _load()
        tmp = tempfile.TemporaryDirectory()
        old = bot.BUY_INTENT
        bot.BUY_INTENT = os.path.join(tmp.name, "buy_intent.json")
        try:
            state = {"cash_usd": 100.0, "open": [], "sold_this_check": ["MINT1"]}
            msg = bot.commit_paper_buy(
                state, mint="MINT1", symbol="DOGE", pair="PAIR",
                price=1.0, liq=100000, ticket=10, conf=0.9, lane="accurate",
            )
            self.assertEqual(msg, "same name already sold this pass")
            self.assertEqual(state["cash_usd"], 100.0)
            self.assertEqual(state["open"], [])
            self.assertFalse(os.path.exists(bot.BUY_INTENT))
            other = bot.commit_paper_buy(
                state, mint="MINT2", symbol="PEPE", pair="PAIR",
                price=1.0, liq=100000, ticket=10, conf=0.9, lane="accurate",
            )
            self.assertIsInstance(other, dict)
            self.assertEqual(other["mint"], "MINT2")
            self.assertEqual(bot.same_mint_block("MINT2", ["MINT1"]), "")
            self.assertFalse(
                hasattr(bot.C, "expand_volume") and bool(getattr(bot.C, "expand_volume"))
            )
        finally:
            bot.BUY_INTENT = old
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
