"""BTC carry decides to open once. A red month is not a second leg."""
from __future__ import annotations

import importlib.util
import os
import unittest

import desk_profit

HERE = os.path.dirname(os.path.abspath(__file__))


def _bot():
    path = os.path.join(HERE, "btc-carry-paper", "bot.py")
    spec = importlib.util.spec_from_file_location("btc_carry_decide", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _marks():
    return {
        "symbol": "BTCUSDT",
        "funding": [{"time": "2026-02-01T00:00:00+00:00", "rate": 0.0001}],
        "premium": [{"time": "2026-02-01T00:00:00+00:00", "close": 0.0004}],
    }


class BtcCarryDecide(unittest.TestCase):
    def test_the_hold_rule_opens_once_and_a_red_month_does_not_add_a_leg(self):
        bot = _bot()
        spot = 97000.0
        flat = {"cash": 500.0, "open": [], "closed": []}
        missed = bot.decide_hold(
            flat,
            {"symbol": "BTCUSDT", "funding": [], "premium": [], "coinbase": spot, "error": "no archive rows"},
            floor=0.01,
            paid=4.0,
        )
        self.assertEqual(missed["action"], "flat")
        self.assertTrue(str(missed["reason"]).startswith("data "))
        self.assertEqual(missed["floor"], 0.02)
        self.assertFalse(missed["opened"])
        self.assertFalse(missed["sold"])
        self.assertFalse(missed["second_leg"])
        self.assertEqual(flat["open"], [])
        self.assertEqual(flat["cash"], 500.0)

        opened = bot.decide_hold(flat, _marks(), floor=0.01, paid=4.0)
        self.assertEqual(opened["action"], "open")
        self.assertEqual(opened["reason"], "hold rule, once")
        self.assertEqual(opened["floor"], 0.02)
        self.assertEqual(opened["legs"], 0)
        self.assertFalse(opened["opened"])
        self.assertEqual(flat["open"], [])
        self.assertEqual(flat["cash"], 500.0)

        pair = {
            "ticker": "BTCUSDT",
            "notional": 500.0,
            "leverage": 1,
            "funding_pnl": -0.1,
        }
        held = {"cash": 499.1, "open": [pair], "closed": []}
        red = _marks()
        red["funding"] = [
            {"time": "2026-02-01T00:00:00+00:00", "rate": 0.0001},
            {"time": "2026-02-01T08:00:00+00:00", "rate": -0.0002},
        ]
        again = bot.decide_hold(held, red, floor=0.01, paid=4.0)
        self.assertEqual(again["action"], "hold")
        self.assertEqual(again["reason"], "red month is not a second leg")
        self.assertEqual(again["legs"], 1)
        self.assertFalse(again["second_leg"])
        self.assertFalse(again["opened"])
        self.assertFalse(again["sold"])
        self.assertEqual(again["floor"], 0.02)
        self.assertEqual(len(held["open"]), 1)
        self.assertEqual(held["cash"], 499.1)

        twin = bot.decide_hold(
            flat, {**_marks(), "symbol": "ETHUSDT", "observe_only": True}, paid=4.0,
        )
        self.assertEqual(twin["action"], "flat")
        self.assertEqual(twin["reason"], "observe twin, not a second tower")
        self.assertEqual(twin["floor"], 0.02)

        gated = bot.decide_hold(flat, _marks(), block_entries=True, paid=9.0, floor=0.0)
        self.assertEqual(gated["action"], "flat")
        self.assertEqual(gated["floor"], 0.02)
        self.assertEqual(bot.floor_stays(0.01, paid=4.0), 0.02)
        self.assertEqual(bot.floor_stays(0.05, paid=4.0), 0.05)
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["binance_btc_carry"], 0.02)
        self.assertNotIn("hold_step", bot.decide_hold.__code__.co_names)
        self.assertIn("decide_hold", bot.run_once.__code__.co_names)


if __name__ == "__main__":
    unittest.main()
