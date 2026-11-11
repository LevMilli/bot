"""BTC carry watch marks the real premium. A red month stays an open pair."""
from __future__ import annotations

import datetime as dt
import importlib.util
import os
import unittest

import desk_profit

HERE = os.path.dirname(os.path.abspath(__file__))
FEBRUARY = dt.datetime(2026, 2, 15, tzinfo=dt.timezone.utc)
MARCH = dt.datetime(2026, 3, 1, tzinfo=dt.timezone.utc)


def _bot():
    path = os.path.join(HERE, "btc-carry-paper", "bot.py")
    spec = importlib.util.spec_from_file_location("btc_carry_watch", path)
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
        "last_mark": 0.0004,
        "exit_fee_reserved": 0.75,
        "exit_name": "hold — red month is a mark",
        "opened": "2026-02-01T00:00:00+00:00",
        "months": {"2026-02": {"funding": -0.10, "basis": 0.0}},
        "sealed": [],
    }


class BtcCarryWatch(unittest.TestCase):
    def test_the_real_premium_is_the_mark_and_a_red_month_stays_open(self):
        bot = _bot()
        spot = 97000.0
        pos = _pair()
        state = {"cash": 499.25, "open": [pos], "closed": []}
        missed = bot.watch_pair(
            state,
            {"premium": [{"time": "2026-02-08T00:00:00+00:00", "close": spot}], "coinbase": spot},
            FEBRUARY,
        )
        self.assertFalse(missed["sold"])
        self.assertFalse(missed["flat"])
        self.assertEqual(pos["last_mark"], 0.0004)
        self.assertNotEqual(pos["last_mark"], spot)
        self.assertEqual(state["cash"], 499.25)
        self.assertEqual(len(state["open"]), 1)

        marked = bot.watch_pair(
            state,
            {
                "premium": [
                    {"time": "2026-02-01T00:00:00+00:00", "close": 0.0004},
                    {"time": "2026-02-08T00:00:00+00:00", "close": 0.0005},
                    {"time": "2026-02-08T08:00:00+00:00", "close": spot},
                ],
                "coinbase": spot,
            },
            FEBRUARY,
        )
        self.assertEqual(pos["last_mark"], 0.0005)
        self.assertEqual(pos["premium"], 0.0005)
        self.assertFalse(marked["sold"])
        self.assertFalse(marked["month_mark"])
        self.assertEqual(state["closed"], [])

        sealed = bot.watch_pair(
            state,
            {"premium": [{"time": "2026-02-08T00:00:00+00:00", "close": 0.0005}]},
            MARCH,
        )
        self.assertTrue(sealed["month_mark"])
        self.assertEqual(len(state["open"]), 1)
        self.assertEqual(state["open"][0]["ticker"], "BTCUSDT")
        self.assertEqual(pos["exit_fee_reserved"], 0.75)
        self.assertEqual(pos["leverage"], 1)
        self.assertEqual(state["cash"], 499.25)
        self.assertEqual(len(state["closed"]), 1)
        row = state["closed"][0]
        self.assertEqual(row["exit"], "month-mark")
        self.assertEqual(row["month"], "2026-02")
        self.assertLess(row["pnl"], 0)
        self.assertIn("hold stays open", row["note"])

        again = bot.watch_pair(
            state,
            {"premium": [{"time": "2026-02-08T00:00:00+00:00", "close": 0.0005}]},
            MARCH,
        )
        self.assertFalse(again["month_mark"])
        self.assertEqual(len(state["closed"]), 1)
        self.assertEqual(len(state["open"]), 1)
        self.assertFalse(again["sold"])

        flat = {"cash": 500.0, "open": [], "closed": []}
        empty = bot.watch_pair(
            flat,
            {"premium": [{"time": "2026-02-08T00:00:00+00:00", "close": 0.0005}]},
            MARCH,
        )
        self.assertTrue(empty["flat"])
        self.assertFalse(empty["sold"])
        self.assertFalse(empty["month_mark"])
        self.assertEqual(flat["open"], [])
        self.assertEqual(flat["closed"], [])
        self.assertEqual(flat["cash"], 500.0)
        self.assertEqual(flat["watch"], "flat")
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["binance_btc_carry"], 0.02)
        self.assertIn("watch_pair", bot.hold_step.__code__.co_names)
        self.assertNotIn("place_open", bot.watch_pair.__code__.co_names)


if __name__ == "__main__":
    unittest.main()
