"""BTC 15-minute watch marks the held-side bid. The other side is not the mark."""
from __future__ import annotations

import importlib.util
import os
import unittest

import desk_profit

ROOT = os.path.dirname(os.path.abspath(__file__))


def _load_btc():
    path = os.path.join(ROOT, "btc15m-signal", "btc15m_signal.py")
    spec = importlib.util.spec_from_file_location("btc15m_watch", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Btc15mWatch(unittest.TestCase):
    def test_held_bid_is_compared_and_the_complement_is_not_the_mark(self):
        btc = _load_btc()
        pos = {
            "ticker": "KXBTC15M-T",
            "side": "YES",
            "ask": 0.70,
            "take_profit": 0.85,
            "contracts": 10,
            "cost": 7.2,
        }
        market = {"yes_bid": 0.62, "no_bid": 0.80, "yes_ask": 0.64, "no_ask": 0.82}
        same = btc.watch_open(pos, 0.62, model_side="YES", model_p=0.88, market=market)
        self.assertEqual(pos["last_mark"], 0.62)
        self.assertFalse(same["at_take_profit"])
        self.assertTrue(same["model_matches_held"])
        self.assertEqual(len([pos]), 1)

        hit = btc.watch_open(pos, 0.90, model_side="YES", model_p=0.91, market=market)
        self.assertEqual(pos["last_mark"], 0.90)
        self.assertTrue(hit["at_take_profit"])
        self.assertEqual(pos.get("side"), "YES")

        other = {
            "yes_bid": 0.40,
            "no_bid": 0.80,
            "yes_ask": 0.42,
            "no_ask": 0.82,
        }
        flipped = btc.watch_open(pos, 0.80, model_side="NO", model_p=0.70, market=other)
        self.assertEqual(pos["last_mark"], 0.40)
        self.assertFalse(flipped["model_matches_held"])
        self.assertNotEqual(pos["last_mark"], 0.80)
        self.assertFalse(flipped["at_take_profit"])

        btc.book_for_side = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no book"))
        kept = btc.watch_open(pos, None, model_side="NO", model_p=None, market=None)
        self.assertEqual(pos["last_mark"], 0.40)
        self.assertFalse(kept["marked"])
        for bad in (0, 1, 1.2, "", "nope"):
            btc.watch_open(pos, bad, model_side="YES", market={"yes_bid": bad})
            self.assertEqual(pos["last_mark"], 0.40)
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_btc15m"], 0.05)


if __name__ == "__main__":
    unittest.main()
