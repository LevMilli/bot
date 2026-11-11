"""Wall Street has no buy, no sell, no stake, and no failsafe."""
from __future__ import annotations

import importlib.util
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


def _bot():
    path = os.path.join(HERE, "wall-street-paper", "bot.py")
    spec = importlib.util.spec_from_file_location("wall_street_refuse", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class WallStreetRefuse(unittest.TestCase):
    def test_a_dropping_ticket_is_not_a_button_on_this_floor(self):
        bot = _bot()
        quiet = bot.refuse_floor(None)
        self.assertFalse(quiet["bought"])
        self.assertFalse(quiet["sold"])
        self.assertEqual(quiet["stake"], 0)
        self.assertFalse(quiet["failsafe"])
        self.assertFalse(quiet["button"])
        self.assertIsNone(quiet["holder"])

        dropping = bot.refuse_floor({
            "tower": "commodity-15m",
            "pnl": -278.12,
            "action": "sell",
        })
        self.assertEqual(dropping["holder"], "commodity-15m")
        self.assertEqual(dropping["reason"], "the holding tower's exit")
        self.assertFalse(dropping["sold"])
        self.assertFalse(dropping["bought"])
        self.assertFalse(dropping["failsafe"])
        self.assertFalse(dropping["button"])
        self.assertEqual(dropping["stake"], 0)
        self.assertEqual(bot.HEADCOUNT, 120)
        self.assertIn("refuse_floor", bot.main.__code__.co_names)


if __name__ == "__main__":
    unittest.main()
