"""Coinbase learning keeps a real close under its series key. A flat day writes nothing."""
from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest

import desk_profit
import pimp_desk

HERE = os.path.dirname(os.path.abspath(__file__))


def _bot():
    path = os.path.join(HERE, "coinbase-spot-paper", "bot.py")
    spec = importlib.util.spec_from_file_location("coinbase_learn", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _close(**over):
    row = {
        "ticker": "ETH-USD",
        "side": "buy",
        "fill_id": "ETH-USD|1",
        "exit": "stop",
        "exit_name": "stop −1.5%",
        "exit_price": 98.5,
        "fee": 0.5,
        "cost": 25.0,
        "stake": 25.0,
        "pnl": -0.875,
        "tower": "coinbase-spot",
        "paper_only": True,
    }
    row.update(over)
    return row


class CoinbaseLearn(unittest.TestCase):
    def test_a_close_is_learned_and_a_flat_day_invents_no_settle(self):
        bot = _bot()
        with tempfile.TemporaryDirectory() as tmp:
            flat = {"cash": 500.0, "open": [], "closed": [], "realized": 0.0}
            empty = bot.learn_book(flat, root=tmp)
            self.assertEqual(empty["wrote"], 0)
            self.assertFalse(empty["settle"])
            self.assertFalse(empty["buy"])
            self.assertEqual(flat["open"], [])
            self.assertEqual(flat["cash"], 500.0)
            self.assertFalse(os.path.exists(os.path.join(tmp, "pimp-learning.json")))
            self.assertEqual(pimp_desk.load_learning(tmp), [])

            invented = {
                "cash": 500.0,
                "open": [],
                "closed": [{
                    "ticker": "ETH-USD",
                    "fill_id": "ETH-USD|settle",
                    "exit": "settled",
                    "exit_name": "settled",
                    "pnl": 12.5,
                    "stake": 25.0,
                    "side": "buy",
                }],
            }
            self.assertEqual(bot.learn_book(invented, root=tmp)["wrote"], 0)
            self.assertEqual(pimp_desk.load_learning(tmp), [])
            self.assertFalse(bot.learn_buys("settled"))
            self.assertFalse(bot.learn_buys("fee take-profit"))

            book = {"cash": 499.125, "open": [], "closed": [_close()]}
            first = bot.learn_book(book, root=tmp)
            second = bot.learn_book(book, root=tmp)
            self.assertEqual(first["wrote"], 1)
            self.assertEqual(second["wrote"], 0)
            self.assertFalse(first["settle"])
            self.assertFalse(first["buy"])
            self.assertEqual(book["cash"], 499.125)
            saved = pimp_desk.load_learning(tmp)
            self.assertEqual(len(saved), 1)
            row = saved[0]
            self.assertEqual(row["market"], "COINBASE-ETH-USD")
            self.assertEqual(row["bucket"], "COINBASE-ETH-USD")
            self.assertEqual(row["fill_id"], "ETH-USD|1")
            self.assertEqual(row["reason"], "stop −1.5%")
            self.assertEqual(row["stake"], 25.0)
            self.assertNotIn("result", row)
            self.assertNotEqual(row["reason"], "settled")

            green = _close(
                fill_id="ETH-USD|tp",
                exit="take-profit",
                exit_name="fee take-profit",
                pnl=1.25,
                exit_price=107.0,
            )
            took = bot.learn_book({"cash": 501.25, "open": [], "closed": [green]}, root=tmp)
            self.assertEqual(took["wrote"], 1)
            gained = [
                item for item in pimp_desk.load_learning(tmp)
                if item.get("fill_id") == "ETH-USD|tp"
            ]
            self.assertEqual(len(gained), 1)
            self.assertEqual(gained[0]["reason"], "fee take-profit")
            self.assertNotIn("result", gained[0])

            sol = _close(ticker="SOL-USD", fill_id="SOL-USD|1", exit_name="z≤−2", exit="model-flip")
            bot.learn_book({"cash": 490.0, "open": [], "closed": [sol]}, root=tmp)
            markets = {item["fill_id"]: item["market"] for item in pimp_desk.load_learning(tmp)}
            self.assertEqual(markets["SOL-USD|1"], "COINBASE-SOL-USD")
            self.assertNotEqual(markets["SOL-USD|1"], "COINBASE-ETH-USD")

            bare = _close(fill_id="ETH-USD|nostake")
            del bare["stake"]
            del bare["cost"]
            self.assertEqual(
                bot.learn_book({"cash": 500.0, "open": [], "closed": [bare]}, root=tmp)["wrote"],
                0,
            )
            self.assertFalse(any(
                item.get("fill_id") == "ETH-USD|nostake" for item in pimp_desk.load_learning(tmp)
            ))
            self.assertEqual(bot.floor_stays(0.01), 0.05)
            self.assertEqual(bot.floor_stays(None), 0.05)
            self.assertEqual(bot.floor_stays(0.08), 0.08)
            self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["coinbase_spot"], 0.05)
            self.assertIn("learn_book", bot.run_once.__code__.co_names)
            self.assertIn("learning_row", bot.tell_learning.__code__.co_names)


if __name__ == "__main__":
    unittest.main()
