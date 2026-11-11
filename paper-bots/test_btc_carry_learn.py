"""BTC carry learning keeps the month-mark. A close that did not happen is not a settle."""
from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest

import desk_profit
import pimp_desk

HERE = os.path.dirname(os.path.abspath(__file__))


def _bot():
    path = os.path.join(HERE, "btc-carry-paper", "bot.py")
    spec = importlib.util.spec_from_file_location("btc_carry_learn", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _book():
    return {
        "cash": 499.25,
        "open": [{
            "ticker": "BTCUSDT",
            "notional": 500.0,
            "leverage": 1,
            "premium": 0.0005,
            "exit_fee_reserved": 0.75,
            "failsafe": "hold, not a sell",
        }],
        "closed": [{
            "ticker": "BTCUSDT",
            "exit": "month-mark",
            "month": "2026-02",
            "pnl": -0.1,
            "cost": 500.0,
            "result": "hit",
            "note": "mark only; the hold stays open",
        }],
    }


class BtcCarryLearn(unittest.TestCase):
    def test_a_month_mark_is_learned_and_a_missing_close_is_not_a_settle(self):
        bot = _bot()
        with tempfile.TemporaryDirectory() as tmp:
            flat = {"cash": 500.0, "open": [], "closed": []}
            empty = bot.learn_book(flat, root=tmp)
            self.assertEqual(empty["wrote"], 0)
            self.assertFalse(empty["settle"])
            self.assertFalse(empty["buy"])
            self.assertFalse(os.path.exists(os.path.join(tmp, "pimp-learning.json")))
            self.assertEqual(pimp_desk.load_learning(tmp), [])

            invented = {
                "cash": 500.0,
                "open": [],
                "closed": [{
                    "ticker": "BTCUSDT",
                    "exit": "settled",
                    "exit_name": "settled",
                    "month": "2026-02",
                    "pnl": 12.0,
                    "cost": 500.0,
                    "result": "hit",
                }],
            }
            self.assertEqual(bot.learn_book(invented, root=tmp)["wrote"], 0)
            self.assertEqual(pimp_desk.load_learning(tmp), [])
            self.assertFalse(bot.learn_buys("month-mark"))
            self.assertFalse(bot.learn_buys("hold, not a sell"))
            self.assertFalse(bot.learn_buys("settled"))

            state = _book()
            first = bot.learn_book(state, root=tmp)
            second = bot.learn_book(state, root=tmp)
            self.assertEqual(first["wrote"], 1)
            self.assertEqual(second["wrote"], 0)
            self.assertFalse(first["settle"])
            self.assertFalse(first["buy"])
            self.assertEqual(len(state["open"]), 1)
            self.assertEqual(state["open"][0]["exit_fee_reserved"], 0.75)
            self.assertEqual(state["cash"], 499.25)
            rows = pimp_desk.load_learning(tmp)
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["market"], "BTC-CARRY")
            self.assertEqual(row["bucket"], "month-mark")
            self.assertEqual(row["fill_id"], "BTCUSDT|2026-02")
            self.assertEqual(row["reason"], "month-mark; hold, not a sell")
            self.assertEqual(row["stake"], 500.0)
            self.assertEqual(row["side"], "HOLD")
            self.assertNotIn("result", row)
            self.assertNotIn("hit", row)
            self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["binance_btc_carry"], 0.02)
            self.assertIn("learn_book", bot.run_once.__code__.co_names)
            self.assertNotIn("place_open", bot.learn_book.__code__.co_names)


if __name__ == "__main__":
    unittest.main()
