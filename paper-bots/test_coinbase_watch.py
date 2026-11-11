"""Coinbase watch marks a real price. A flat sleeve stays flat."""
from __future__ import annotations

import importlib.util
import os
import unittest

import desk_profit

HERE = os.path.dirname(os.path.abspath(__file__))


def _bot():
    path = os.path.join(HERE, "coinbase-spot-paper", "bot.py")
    spec = importlib.util.spec_from_file_location("coinbase_watch", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class CoinbaseWatch(unittest.TestCase):
    def test_a_real_price_is_the_mark_and_a_flat_sleeve_stays_flat(self):
        bot = _bot()
        pos = {
            "ticker": "ETH-USD",
            "side": "buy",
            "entry_price": 100.0,
            "cost": 25.0,
            "last_mark": 99.0,
        }
        state = {"cash": 475.0, "open": [pos], "closed": []}
        invented = 100.0 * (1.0 - 0.015)
        missed = bot.watch_sleeve(state, {"ETH-USD": None, "SOL-USD": 20.0})
        self.assertFalse(missed["sold"])
        self.assertFalse(missed["flat"])
        self.assertEqual(pos["last_mark"], 99.0)
        self.assertNotEqual(pos["last_mark"], invented)
        self.assertEqual(state["cash"], 475.0)
        self.assertEqual(len(state["open"]), 1)

        bot.watch_sleeve(state, {"SOL-USD": 20.0})
        self.assertEqual(pos["last_mark"], 99.0)

        marked = bot.watch_sleeve(state, {"ETH-USD": 97.0, "SOL-USD": 20.0})
        self.assertEqual(pos["last_mark"], 97.0)
        self.assertFalse(marked["sold"])
        self.assertEqual(marked["marks"][0]["last_mark"], 97.0)
        self.assertEqual(state["cash"], 475.0)
        self.assertEqual(len(state["open"]), 1)
        for bad in (0, -1, "", "nope"):
            bot.watch_sleeve(state, {"ETH-USD": bad})
            self.assertEqual(pos["last_mark"], 97.0)

        flat = {"cash": 500.0, "open": [], "closed": []}
        wrote = bot.watch_sleeve(flat, {"ETH-USD": invented})
        self.assertTrue(wrote["flat"])
        self.assertFalse(wrote["sold"])
        self.assertEqual(flat["watch"], "flat")
        self.assertEqual(flat["open"], [])
        self.assertEqual(flat["cash"], 500.0)
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["coinbase_spot"], 0.05)
        self.assertIn("watch_sleeve", bot.run_once.__code__.co_names)


if __name__ == "__main__":
    unittest.main()
