"""Wall Street reads the city book. A missing snapshot is not a P/L."""
from __future__ import annotations

import importlib.util
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


def _bot():
    path = os.path.join(HERE, "wall-street-paper", "bot.py")
    spec = importlib.util.spec_from_file_location("wall_street_read", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class WallStreetRead(unittest.TestCase):
    def test_a_missing_snapshot_is_not_a_pnl(self):
        bot = _bot()
        missing = bot.read_book(None)
        self.assertFalse(missing["read"])
        self.assertIsNone(missing["pnl"])
        self.assertEqual(missing["rows"], [])
        self.assertFalse(missing["bought"])
        self.assertFalse(missing["sold"])
        self.assertEqual(missing["reason"], "snapshot missing")
        self.assertNotEqual(missing["pnl"], 0)
        self.assertNotEqual(missing["pnl"], -278.12)

        empty = bot.read_book({})
        self.assertTrue(empty["read"])
        self.assertIsNone(empty["pnl"])
        self.assertEqual(empty["rows"], [])
        self.assertFalse(empty["bought"])

        book = bot.read_book({
            "bots": [
                {"id": "commodity-15m", "realized": -278.12},
                {"id": "btc-carry"},
            ],
        })
        self.assertTrue(book["read"])
        self.assertIsNone(book["pnl"])
        self.assertEqual(book["rows"][0], {"id": "commodity-15m", "realized": -278.12})
        self.assertIsNone(book["rows"][1]["realized"])
        self.assertFalse(book["bought"])
        self.assertFalse(book["sold"])
        self.assertEqual(bot.HEADCOUNT, 120)
        self.assertIn("read_book", bot.main.__code__.co_names)
        self.assertNotIn("buy", bot.read_book.__code__.co_names)


if __name__ == "__main__":
    unittest.main()
