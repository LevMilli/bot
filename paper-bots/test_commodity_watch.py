"""Commodity watch marks the held-side listing bid. A 5¢ drop is a log, not a sell."""
from __future__ import annotations

import importlib.util
import os
import unittest

import desk_profit

ROOT = os.path.dirname(os.path.abspath(__file__))


def _load():
    path = os.path.join(ROOT, "commodity-15m-paper", "bot.py")
    spec = importlib.util.spec_from_file_location("commodity_watch", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class CommodityWatch(unittest.TestCase):
    def test_brent_and_gold_marks_and_a_missing_bid_stays(self):
        bot = _load()
        brent = {
            "ticker": "KXBRENT15M-T",
            "series": "KXBRENT15M",
            "side": "YES",
            "ask": 0.80,
            "contracts": 3,
            "last_mark": 0.77,
        }
        gold = {
            "ticker": "KXGOLD15M-T",
            "series": "KXGOLD15M",
            "side": "NO",
            "ask": 0.75,
            "contracts": 2,
        }
        state = {"cash": 50.0, "open": [brent, gold], "closed": []}
        notes = bot.watch_opens(state, {
            "KXBRENT15M-T": {"yes_bid": 0.70, "no_bid": 0.28},
            "KXGOLD15M-T": {"yes_bid": 0.20, "no_bid": 0.71},
        })
        self.assertEqual(brent["last_mark"], 0.70)
        self.assertEqual(gold["last_mark"], 0.71)
        self.assertNotEqual(gold["last_mark"], 0.20)
        self.assertEqual(len(state["open"]), 2)
        self.assertEqual(state["cash"], 50.0)
        self.assertEqual(brent["contracts"], 3)
        self.assertTrue(notes)
        self.assertIn("KXBRENT15M-T", notes[0])
        self.assertIn("sold=False", notes[0])
        self.assertFalse(brent["watch"]["sold"])

        kept = bot.watch_open(brent, None)
        self.assertEqual(brent["last_mark"], 0.70)
        self.assertFalse(kept["marked"])
        bot.watch_open(brent, {"no_bid": 0.90})
        self.assertEqual(brent["last_mark"], 0.70)
        for bad in (0, 1, 1.2, "", "nope"):
            bot.watch_open(brent, {"yes_bid": bad})
            self.assertEqual(brent["last_mark"], 0.70)
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_commodity15m"], 0.05)
        self.assertIn("watch_opens", bot.main.__code__.co_names)
        with open(os.path.join(ROOT, "commodity-15m-paper", "bot.py"), encoding="utf-8") as handle:
            self.assertIn("DROP WATCH", handle.read())


if __name__ == "__main__":
    unittest.main()
