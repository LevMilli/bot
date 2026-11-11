"""Coinbase buy writes the exit intent before the $25 ticket moves."""
from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest

import desk_profit

HERE = os.path.dirname(os.path.abspath(__file__))
EXIT = "stop −1.5% / fee take-profit / z≤−2 / 24h"


def _bot():
    path = os.path.join(HERE, "coinbase-spot-paper", "bot.py")
    spec = importlib.util.spec_from_file_location("coinbase_buy", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class CoinbaseBuy(unittest.TestCase):
    def test_intent_before_cash_and_a_refuse_buys_nothing(self):
        bot = _bot()
        self.assertEqual(bot.BUY_EXIT, EXIT)
        passed = {
            "product": "ETH-USD",
            "action": "buy",
            "flat": False,
            "edge": 0.08,
            "floor": 0.05,
            "z": 3.0,
        }
        with tempfile.TemporaryDirectory() as tmp:
            intent = os.path.join(tmp, "buy_intent.json")
            state = {"cash": 500.0, "open": [], "closed": [], "paper_only": True}
            flat = bot.place_shadow_buy(
                state, {"product": "ETH-USD", "action": "flat", "flat": True, "reason": "replay bar not met"},
                100.0, btc_yes=False, intent_path=intent, now="2026-11-11T18:00:00",
            )
            self.assertFalse(flat["bought"])
            self.assertFalse(flat["fill"])
            self.assertEqual(state["cash"], 500.0)
            self.assertEqual(state["open"], [])
            self.assertFalse(os.path.exists(intent))

            blocked = bot.place_shadow_buy(
                state, passed, 100.0, btc_yes=True, intent_path=intent, now="2026-11-11T18:00:00",
            )
            self.assertEqual(blocked["reason"], "btc15m YES open")
            self.assertEqual(state["cash"], 500.0)
            self.assertFalse(os.path.exists(intent))

            missing = bot.place_shadow_buy(
                state, passed, None, btc_yes=False, intent_path=intent, now="2026-11-11T18:00:00",
            )
            self.assertEqual(missing["reason"], "missing price")
            self.assertEqual(state["open"], [])

            seen = {}
            real = bot.write_buy_intent

            def _wrapped(*args, **kwargs):
                seen["cash"] = state["cash"]
                return real(*args, **kwargs)

            bot.write_buy_intent = _wrapped
            bought = bot.place_shadow_buy(
                state, passed, 101.5, btc_yes=False, intent_path=intent, now="2026-11-11T18:01:00",
            )
            self.assertTrue(bought["bought"])
            self.assertEqual(seen["cash"], 500.0)
            self.assertEqual(state["cash"], 475.0)
            self.assertEqual(bought["stake"], 25.0)
            self.assertEqual(bought["exit_rule"], EXIT)
            self.assertEqual(len(state["open"]), 1)
            self.assertEqual(state["open"][0]["entry_price"], 101.5)
            self.assertEqual(state["open"][0]["exit_rule"], EXIT)
            with open(intent, encoding="utf-8") as handle:
                saved = json.load(handle)
            self.assertEqual(saved["exit_rule"], EXIT)
            self.assertEqual(saved["stake"], 25.0)
            self.assertEqual(saved["price"], 101.5)
            self.assertTrue(saved["paper_only"])
            self.assertEqual(saved["tower"], "coinbase-spot")

            again = bot.place_shadow_buy(
                state, passed, 110.0, btc_yes=False, intent_path=intent, now="2026-11-11T18:02:00",
            )
            self.assertFalse(again["bought"])
            self.assertEqual(again["reason"], "one $25 ticket")
            self.assertEqual(state["cash"], 475.0)
            self.assertEqual(len(state["open"]), 1)
            with open(intent, encoding="utf-8") as handle:
                self.assertEqual(json.load(handle)["fill_id"], bought["fill_id"])

            empty = {"cash": 500.0, "open": [], "closed": []}
            bot.write_buy_intent = real
            real(intent, fill_id="missing", product="SOL-USD", price=20.0, stake=25.0)
            self.assertEqual(bot.reconcile_buy_intent(empty, intent), "abandoned")
            self.assertEqual(empty["open"], [])
            self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["coinbase_spot"], 0.05)
            self.assertIn("place_shadow_buy", bot.run_once.__code__.co_names)
            self.assertIn("reconcile_buy_intent", bot.run_once.__code__.co_names)


if __name__ == "__main__":
    unittest.main()
