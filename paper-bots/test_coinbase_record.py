"""Coinbase records a real close, or a flat line at $0. That zero is not a gain."""
from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest

import desk_brain
import desk_profit

HERE = os.path.dirname(os.path.abspath(__file__))


def _bot():
    path = os.path.join(HERE, "coinbase-spot-paper", "bot.py")
    spec = importlib.util.spec_from_file_location("coinbase_record", path)
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


class CoinbaseRecord(unittest.TestCase):
    def test_a_flat_book_stays_at_zero_and_a_close_keeps_its_pnl(self):
        bot = _bot()
        with tempfile.TemporaryDirectory() as tmp:
            flat = {"cash": 500.0, "open": [], "closed": [], "realized": 12.5}
            first = bot.record_close(flat, claimed=12.5, root=tmp)
            again = bot.record_close(flat, claimed=4.0, root=tmp)
            self.assertTrue(first["flat"])
            self.assertEqual(first["realized"], 0.0)
            self.assertEqual(flat["realized"], 0.0)
            self.assertEqual(flat["record"], "flat")
            self.assertEqual(flat["closed"], [])
            self.assertEqual(flat["cash"], 500.0)
            self.assertEqual(first["line"]["action"], "flat")
            self.assertEqual(first["line"]["bot"], "coinbase-spot")
            self.assertEqual(first["line"]["note"], "flat, realized 0")
            self.assertEqual(first["line"]["realized"], 0.0)
            self.assertNotIn("fill_id", first["line"])
            self.assertNotIn("bid", first["line"])
            self.assertNotIn("hit", first["line"])
            self.assertEqual(again["realized"], 0.0)
            saved = desk_brain.load_journal(tmp)
            flats = [
                row for row in saved["decisions"]
                if row.get("bot") == "coinbase-spot" and row.get("action") == "flat"
            ]
            self.assertEqual(len(flats), 1)
            self.assertEqual(flats[0]["realized"], 0.0)
            self.assertNotIn("hit", flats[0])
            self.assertNotIn("result", flats[0])

            held = {
                "cash": 475.0,
                "open": [{
                    "ticker": "ETH-USD",
                    "side": "buy",
                    "entry_price": 100.0,
                    "last_mark": 110.0,
                    "cost": 25.0,
                }],
                "closed": [],
                "realized": 10.0,
            }
            marked = bot.record_close(held, claimed=10.0, root=tmp)
            self.assertTrue(marked["flat"])
            self.assertEqual(marked["realized"], 0.0)
            self.assertEqual(held["realized"], 0.0)
            self.assertEqual(len(held["open"]), 1)
            self.assertEqual(held["closed"], [])
            self.assertEqual(held["cash"], 475.0)
            self.assertEqual(held["open"][0]["last_mark"], 110.0)

            story = {
                "cash": 500.0,
                "open": [],
                "closed": [{"ticker": "ETH-USD", "pnl": 12.5}],
                "realized": 12.5,
            }
            refused = bot.record_close(story, claimed=12.5, root=tmp)
            self.assertTrue(refused["flat"])
            self.assertEqual(refused["realized"], 0.0)
            self.assertEqual(story["realized"], 0.0)
            self.assertEqual(story["closed"][0]["pnl"], 12.5)
            self.assertNotIn("fill_id", story["closed"][0])
            self.assertFalse(any(row.get("action") == "sell" for row in desk_brain.load_journal(tmp)["decisions"]))

            stopped = _close()
            book = {"cash": 499.125, "open": [], "closed": [stopped], "realized": 9.0}
            wrote = bot.record_close(book, claimed=9.0, root=tmp)
            twice = bot.record_close(book, claimed=9.0, root=tmp)
            self.assertFalse(wrote["flat"])
            self.assertEqual(stopped["pnl"], -0.875)
            self.assertEqual(book["realized"], -0.875)
            self.assertEqual(stopped["cash_after"], 499.125)
            self.assertEqual(stopped["fee"], 0.5)
            self.assertEqual(stopped["exit_price"], 98.5)
            self.assertNotIn("hit", stopped)
            self.assertNotIn("result", stopped)
            row = wrote["closes"][0]
            self.assertEqual(row["bot"], "coinbase-spot")
            self.assertEqual(row["action"], "sell")
            self.assertEqual(row["fill_id"], "ETH-USD|1")
            self.assertEqual(row["bid"], 98.5)
            self.assertEqual(row["stake"], 25.0)
            self.assertEqual(row["fee"], 0.5)
            self.assertEqual(row["exit_name"], "stop −1.5%")
            self.assertEqual(row["cash"], round(499.125, 2))
            self.assertNotIn("hit", row)
            self.assertNotIn("result", row)
            self.assertEqual(twice["closes"][0]["fill_id"], row["fill_id"])
            sales = [
                item for item in desk_brain.load_journal(tmp)["decisions"]
                if item.get("fill_id") == "ETH-USD|1"
            ]
            self.assertEqual(len(sales), 1)

            blank = _close(fill_id="ETH-USD|2", exit_price=None, pnl=1.25, exit="take-profit", exit_name="fee take-profit")
            del blank["exit_price"]
            green = {"cash": 501.25, "open": [], "closed": [blank]}
            took = bot.record_close(green, claimed=50.0, root=tmp)
            self.assertEqual(blank["pnl"], 1.25)
            self.assertEqual(green["realized"], 1.25)
            self.assertNotIn("exit_price", blank)
            self.assertNotIn("bid", took["closes"][0])
            self.assertNotIn("hit", blank)
            self.assertNotIn("hit", took["closes"][0])
            self.assertEqual(took["closes"][0]["exit_name"], "fee take-profit")
            self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["coinbase_spot"], 0.05)
            self.assertIn("record_close", bot.run_once.__code__.co_names)


if __name__ == "__main__":
    unittest.main()
