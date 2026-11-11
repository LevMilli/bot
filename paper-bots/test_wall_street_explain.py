"""Wall Street names the tower a number belongs to. It does not spread it."""
from __future__ import annotations

import importlib.util
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


def _bot():
    path = os.path.join(HERE, "wall-street-paper", "bot.py")
    spec = importlib.util.spec_from_file_location("wall_street_explain", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class WallStreetExplain(unittest.TestCase):
    def test_commodity_keeps_its_number(self):
        bot = _bot()
        missing = bot.explain_book(None)
        self.assertEqual(missing["lines"], [])
        self.assertFalse(missing["bought"])
        self.assertFalse(missing["sold"])
        self.assertFalse(missing["spread"])
        self.assertNotIn("278.12", " ".join(missing["lines"]))

        named = bot.explain_book({
            "bots": [
                {"id": "commodity-15m", "realized": -278.12},
                {"id": "sports-gap", "realized": 10.0},
                {"id": "btc-carry"},
            ],
        })
        self.assertEqual(
            named["lines"],
            [
                "commodity's −$278.12 stays commodity's.",
                "sports gap's $10.00 stays sports gap's.",
            ],
        )
        self.assertFalse(any("278.12" in line and "commodity" not in line for line in named["lines"]))
        self.assertNotIn("−$46.35", " ".join(named["lines"]))
        self.assertFalse(named["bought"])
        self.assertFalse(named["sold"])
        self.assertFalse(named["spread"])
        self.assertEqual(bot.HEADCOUNT, 120)
        self.assertIn("explain_book", bot.main.__code__.co_names)
        self.assertNotIn("buy", bot.explain_book.__code__.co_names)


if __name__ == "__main__":
    unittest.main()
