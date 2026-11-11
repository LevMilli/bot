"""BTC carry failsafe confirms the hold. A red month is not a sell."""
from __future__ import annotations

import importlib.util
import os
import unittest

import desk_profit

HERE = os.path.dirname(os.path.abspath(__file__))


def _bot():
    path = os.path.join(HERE, "btc-carry-paper", "bot.py")
    spec = importlib.util.spec_from_file_location("btc_carry_sell", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pair():
    return {
        "ticker": "BTCUSDT",
        "notional": 500.0,
        "leverage": 1,
        "premium": 0.0004,
        "premium_time": "2026-02-01T00:00:00+00:00",
        "exit_fee_reserved": 0.75,
        "exit_name": "hold — red month is a mark",
        "months": {"2026-02": {"funding": -0.10, "basis": 0.0}},
    }


class BtcCarrySell(unittest.TestCase):
    def test_a_red_month_is_not_a_sell_and_a_missing_premium_is_not_a_close(self):
        bot = _bot()
        spot = 97000.0
        pos = _pair()
        state = {"cash": 499.25, "open": [pos], "closed": []}
        held = bot.failsafe_hold(
            state,
            {
                "premium": [
                    {"time": "2026-02-08T00:00:00+00:00", "close": 0.0005},
                    {"time": "2026-02-08T08:00:00+00:00", "close": spot},
                ],
                "coinbase": spot,
            },
            close_reason="red month",
        )
        self.assertFalse(held["sold"])
        self.assertFalse(held["closed"])
        self.assertFalse(held["hit"])
        self.assertTrue(held["hold"])
        self.assertTrue(held["refused_red_month"])
        self.assertEqual(held["sentence"], "hold, not a sell")
        self.assertEqual(held["premium"], 0.0005)
        self.assertEqual(pos["failsafe"], "hold, not a sell")
        self.assertEqual(pos["failsafe_premium"], 0.0005)
        self.assertNotEqual(pos["failsafe_premium"], spot)
        self.assertEqual(len(state["open"]), 1)
        self.assertEqual(state["open"][0]["ticker"], "BTCUSDT")
        self.assertEqual(pos["exit_fee_reserved"], 0.75)
        self.assertEqual(pos["leverage"], 1)
        self.assertEqual(state["cash"], 499.25)
        self.assertEqual(state["closed"], [])

        missed = bot.failsafe_hold(
            state,
            {"premium": [{"time": "2026-02-09T00:00:00+00:00", "close": spot}], "coinbase": spot},
            close_reason="red month",
        )
        self.assertFalse(missed["sold"])
        self.assertFalse(missed["closed"])
        self.assertEqual(missed["reason"], "missing premium is not a close")
        self.assertEqual(missed["premium"], 0.0005)
        self.assertEqual(pos["failsafe_premium"], 0.0005)
        self.assertEqual(len(state["open"]), 1)
        self.assertEqual(state["closed"], [])
        self.assertEqual(state["cash"], 499.25)
        self.assertEqual(pos["failsafe"], "hold, not a sell")

        flat = {"cash": 500.0, "open": [], "closed": []}
        empty = bot.failsafe_hold(
            flat,
            {"premium": [{"time": "2026-02-08T00:00:00+00:00", "close": 0.0005}]},
            close_reason="red month",
        )
        self.assertTrue(empty["hold"])
        self.assertFalse(empty["sold"])
        self.assertFalse(empty["closed"])
        self.assertFalse(empty["hit"])
        self.assertEqual(empty["sentence"], "hold, not a sell")
        self.assertIsNone(empty["premium"])
        self.assertEqual(flat["open"], [])
        self.assertEqual(flat["closed"], [])
        self.assertEqual(flat["cash"], 500.0)
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["binance_btc_carry"], 0.02)
        self.assertIn("failsafe_hold", bot.hold_step.__code__.co_names)
        self.assertNotIn("place_open", bot.failsafe_hold.__code__.co_names)


if __name__ == "__main__":
    unittest.main()
