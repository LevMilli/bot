"""Memecoin watch marks a real price. A missing price is not a −12% stop."""
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
    spec = importlib.util.spec_from_file_location("memecoin_watch", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pos(mint="MINT1", entry=1.0, mark=None):
    pos = {
        "mint": mint,
        "symbol": "DOGE",
        "entry_market_price": entry,
        "tokens_left": 10,
    }
    if mark is not None:
        pos["last_mark"] = mark
    return pos


class MemecoinWatch(unittest.TestCase):
    def test_a_real_price_marks_the_first_exit_and_the_hard_exit_without_selling(self):
        bot = _load()
        held = _pos()
        other = _pos("MINT2", entry=2.0, mark=2.0)
        state = {"open": [held, other]}
        notes = bot.watch_opens(state, {"MINT1": 0.94})
        self.assertTrue(held["watch"]["marked"])
        self.assertEqual(held["last_mark"], 0.94)
        self.assertTrue(held["watch"]["first_exit"])
        self.assertFalse(held["watch"]["hard_exit"])
        self.assertFalse(held["watch"]["sold"])
        self.assertEqual(other["last_mark"], 2.0)
        self.assertNotIn("MINT2", "".join(notes) or "MINT1")
        self.assertIn("sold=False", notes[0])

        hard = bot.watch_open(held, 0.88)
        self.assertTrue(hard["hard_exit"])
        self.assertFalse(hard["first_exit"])
        self.assertFalse(hard["sold"])
        self.assertEqual(held["tokens_left"], 10)

        flat = bot.watch_open(_pos(), 0.97)
        self.assertFalse(flat["first_exit"])
        self.assertFalse(flat["hard_exit"])
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["solana_dex"], 0.02)
        src = inspect.getsource(bot.watch_open)
        self.assertNotIn("sell(", src)
        self.assertIn("watch_open", bot.manage.__code__.co_names)

    def test_a_missing_price_is_not_the_hard_exit(self):
        bot = _load()
        pos = _pos(mark=1.05)
        for missing in (None, 0, -1, "nope"):
            watch = bot.watch_open(pos, missing)
            self.assertFalse(watch["marked"])
            self.assertFalse(watch["hard_exit"])
            self.assertFalse(watch["first_exit"])
            self.assertEqual(watch["last_mark"], 1.05)
            self.assertFalse(watch["sold"])
            self.assertEqual(pos["last_mark"], 1.05)
        self.assertFalse(
            hasattr(bot.C, "expand_volume") and bool(getattr(bot.C, "expand_volume"))
        )


if __name__ == "__main__":
    unittest.main()
