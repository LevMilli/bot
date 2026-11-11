"""Sized Kalshi watch marks this tower's bid. S&P's bid is not the mark."""
from __future__ import annotations

import importlib.util
import os
import sys
import types
import unittest

import desk_profit

ROOT = os.path.dirname(os.path.abspath(__file__))


def _load():
    if "requests" not in sys.modules:
        stub = types.ModuleType("requests")
        stub.Session = lambda: types.SimpleNamespace(headers={})
        sys.modules["requests"] = stub
    sibling = os.path.join(ROOT, "kalshi-sp500-paper")
    sized = os.path.join(ROOT, "kalshi-sized-paper")
    for path in (sibling, sized):
        if path in sys.path:
            sys.path.remove(path)
        sys.path.insert(0, path)
    bot_path = os.path.join(sized, "bot.py")
    spec = importlib.util.spec_from_file_location("sized_kalshi_watch", bot_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class SizedKalshiWatch(unittest.TestCase):
    def test_own_bid_is_marked_and_the_sibling_bid_is_not(self):
        bot = _load()
        sim = bot.paper_sim
        held = {
            "ticker": "KXINXU-SIZED",
            "side": "yes",
            "tower": "kalshi-sized",
            "last_mark": 0.84,
            "contracts": 2,
        }
        sibling = {
            "ticker": "KXINXU-SP",
            "side": "yes",
            "tower": "kalshi-sp",
            "last_mark": 0.40,
            "contracts": 29,
        }
        state = {"bankroll": 500.0, "open": [held, sibling], "closed": []}
        quotes = {
            "KXINXU-SIZED": {"yes_bid": 0.81, "no_bid": 0.17},
            "KXINXU-SP": {"yes_bid": 0.33, "no_bid": 0.64},
        }
        notes = sim.watch_opens(state, quotes)
        self.assertEqual(held["last_mark"], 0.81)
        self.assertEqual(sibling["last_mark"], 0.40)
        self.assertNotEqual(held["last_mark"], 0.33)
        self.assertEqual(state["bankroll"], 500.0)
        self.assertEqual(len(state["open"]), 2)
        self.assertEqual(held["contracts"], 2)
        self.assertTrue(notes)
        self.assertIn("sold=False", notes[0])
        self.assertFalse(sim.watch_open(held, quotes)["sold"])

        sim.watch_open(held, {"KXINXU-SP": {"yes_bid": 0.22, "no_bid": 0.70}})
        self.assertEqual(held["last_mark"], 0.81)
        sim.watch_open(held, {"KXINXU-SIZED": {"no_bid": 0.10}})
        self.assertEqual(held["last_mark"], 0.81)
        for bad in (None, "", 0, 0.0, 1, 1.2, "nope"):
            result = sim.watch_open(held, {"KXINXU-SIZED": {"yes_bid": bad}})
            self.assertFalse(result["marked"])
            self.assertFalse(result["sold"])
            self.assertEqual(held["last_mark"], 0.81)
            self.assertFalse(sim.bid_under_exit(bad, 0.50))

        under = sim.watch_open(held, {"KXINXU-SIZED": {"yes_bid": 0.49}})
        self.assertEqual(held["last_mark"], 0.49)
        self.assertTrue(under["exit_signal"])
        self.assertFalse(under["sold"])
        self.assertEqual(len(state["open"]), 2)
        self.assertEqual(state["bankroll"], 500.0)
        self.assertFalse(sim.bid_under_exit(0.50, 0.50))
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_inx"], 0.02)
        self.assertIn("watch_open", bot.step_settle.__code__.co_names)
        with open(os.path.join(ROOT, "kalshi-sized-paper", "bot.py"), encoding="utf-8") as handle:
            src = handle.read()
        self.assertLess(src.find("watch_open("), src.find("MODEL-FLIP SELL"))


if __name__ == "__main__":
    unittest.main()
