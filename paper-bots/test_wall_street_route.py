"""Wall Street routes one tower's question. It does not place the trade."""
from __future__ import annotations

import importlib.util
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


def _bot():
    path = os.path.join(HERE, "wall-street-paper", "bot.py")
    spec = importlib.util.spec_from_file_location("wall_street_route", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class WallStreetRoute(unittest.TestCase):
    def test_one_tower_goes_to_that_tower_and_two_stay_with_the_guide(self):
        bot = _bot()
        one = bot.route_question("why is commodity at −$278.12")
        self.assertEqual(one["to"], "commodity-15m")
        self.assertFalse(one["guide"])
        self.assertFalse(one["bought"])
        self.assertFalse(one["sold"])
        self.assertFalse(one["trade"])

        asked = bot.route_question("buy commodity")
        self.assertEqual(asked["to"], "commodity-15m")
        self.assertFalse(asked["trade"])
        self.assertFalse(asked["bought"])
        self.assertFalse(asked["sold"])

        both = bot.route_question("compare commodity and sports gap")
        self.assertEqual(both["to"], "city guide")
        self.assertTrue(both["guide"])
        self.assertFalse(both["trade"])
        self.assertFalse(both["bought"])
        self.assertFalse(both["sold"])

        empty = bot.route_question("")
        self.assertEqual(empty["to"], "city guide")
        self.assertTrue(empty["guide"])
        self.assertFalse(empty["trade"])
        self.assertEqual(bot.HEADCOUNT, 120)
        self.assertIn("route_question", bot.main.__code__.co_names)


if __name__ == "__main__":
    unittest.main()
