"""Memecoin decide: 0.02 floor, −$5 skip, Adapt cannot lift the $10 ceiling."""
from __future__ import annotations

import importlib.util
import inspect
import os
import sys
import types
import unittest

import desk_profit

ROOT = os.path.dirname(os.path.abspath(__file__))


def _load():
    meme = os.path.join(ROOT, "memecoin-paper")
    if meme not in sys.path:
        sys.path.insert(0, meme)
    if "requests" not in sys.modules:
        stub = types.ModuleType("requests")
        stub.Session = lambda: types.SimpleNamespace(headers={})
        sys.modules["requests"] = stub
    path = os.path.join(meme, "bot.py")
    spec = importlib.util.spec_from_file_location("memecoin_decide", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class MemecoinDecide(unittest.TestCase):
    def test_floor_stays_and_a_locked_day_skips_while_exits_stay_awake(self):
        bot = _load()
        self.assertEqual(bot.decide_floor(0.01), 0.02)
        self.assertEqual(bot.decide_floor(0.05), 0.05)
        self.assertEqual(bot.decide_floor("nope"), 0.02)
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["solana_dex"], 0.02)
        self.assertIn("−$5", bot.decide_skip(-5))
        self.assertEqual(bot.decide_skip(-4.99), "")
        self.assertEqual(bot.decide_size(25, 40, -5, 100), 0.0)
        scan = inspect.getsource(bot.scan)
        main = inspect.getsource(bot.main)
        self.assertLess(main.find("manage("), main.find("scan("))
        self.assertLess(scan.find("decide_skip"), scan.find("paper_buy"))

    def test_adapt_cannot_lift_the_red_day_ceiling(self):
        bot = _load()
        # Ladder $25, Adapt $40. A red day stays at $10. A green day stays at $25.
        self.assertEqual(bot.decide_size(25, 40, -1, 100, "accurate"), 10.0)
        self.assertEqual(bot.decide_size(25, 40, 4, 100, "accurate"), 25.0)
        # Adapt may shrink. It cannot put the ladder back above its own number.
        self.assertEqual(bot.decide_size(25, 12, 4, 100, "accurate"), 12.0)
        self.assertEqual(bot.decide_size(25, 8, 4, 100, "accurate"), 0.0)
        self.assertEqual(bot.decide_size(25, 40, -1, 12, "speed"), 10.0)
        self.assertEqual(bot.decide_size(25, 40, 4, 8, "accurate"), 0.0)
        self.assertIn("decide_size", bot.scan.__code__.co_names)
        # #614: scan reaches decide_floor through floor_for_next_mint.
        self.assertIn("floor_for_next_mint", bot.scan.__code__.co_names)
        self.assertIn("decide_floor", bot.floor_for_next_mint.__code__.co_names)
        self.assertFalse(hasattr(bot.C, "expand_volume") and bool(getattr(bot.C, "expand_volume")))


if __name__ == "__main__":
    unittest.main()
