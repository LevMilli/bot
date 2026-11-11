"""Sized Kalshi learns from the first real settle. Until then the book stays empty."""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import types
import unittest

import desk_profit

ROOT = os.path.dirname(os.path.abspath(__file__))


def _load():
    if "requests" not in sys.modules:
        stub = types.ModuleType("requests")
        stub.Session = lambda: types.SimpleNamespace(headers={})
        sys.modules["requests"] = stub
    sibling = os.path.join(ROOT, "kalshi-sp500-paper")
    sized = os.path.join(ROOT, "kalshi-sized-paper")
    for path in (sibling, sized):
        if path in sys.path:
            sys.path.remove(path)
        sys.path.insert(0, path)
    bot_path = os.path.join(sized, "bot.py")
    spec = importlib.util.spec_from_file_location("sized_kalshi_learn", bot_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class SizedKalshiLearn(unittest.TestCase):
    def test_the_first_settle_is_the_first_row_and_the_floor_stays(self):
        bot = _load()
        fact = bot.header_only_fact("# Learning.md - Sized Kalshi notes\n")
        self.assertFalse(fact["fill"])
        with tempfile.TemporaryDirectory() as tmp:
            flip = {
                "fill_id": "KXINXU-SIZED|flip",
                "ticker": "KXINXU-SIZED",
                "tower": "kalshi-sized",
                "ask": 0.85,
                "risk": 8.61,
                "side": "yes",
                "exit": "model-flip bid under 50c",
            }
            self.assertIsNone(bot.sized_learning_row(flip, 1.25, "model-flip bid under 50c"))
            self.assertEqual(
                bot.tell_sized_learning(flip, 1.25, "model-flip bid under 50c", tmp),
                "empty",
            )
            self.assertEqual(bot._desk().load_learning(tmp), [])

            sibling = {
                "fill_id": "KXINXU-SP|1",
                "tower": "kalshi-sp",
                "result": "yes",
                "ask": 0.85,
                "risk": 8.61,
                "side": "yes",
            }
            self.assertEqual(bot.tell_sized_learning(sibling, 4.0, "settled", tmp), "empty")
            self.assertEqual(bot._desk().load_learning(tmp), [])

            settled = {
                "fill_id": "KXINXU-SIZED|1",
                "ticker": "KXINXU-SIZED",
                "tower": "kalshi-sized",
                "result": "yes",
                "ask": 0.85,
                "risk": 8.61,
                "side": "yes",
            }
            self.assertEqual(bot.tell_sized_learning(settled, 4.09, "settled", tmp), "recorded")
            self.assertEqual(bot.tell_sized_learning(settled, 4.09, "settled", tmp), "duplicate")
            rows = bot._desk().load_learning(tmp)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["market"], "S&P-sized")
            self.assertEqual(rows[0]["reason"], "settled")
            self.assertEqual(rows[0]["result"], "hit")
            self.assertEqual(rows[0]["fill_id"], "KXINXU-SIZED|1")
            lost = dict(settled, fill_id="KXINXU-SIZED|2", result="no")
            self.assertEqual(bot.sized_learning_row(lost, -8.61, "settled")["result"], "miss")
            self.assertNotIn("result", bot.sized_learning_row(flip, 1.25, "model-flip bid under 50c") or {})

        cold_sp = [
            {"market": "S&P", "bucket": "0.8-0.9", "result": "miss", "side": "YES", "hour_ct": 13}
            for _ in range(8)
        ]
        self.assertEqual(bot.learning_skip_sized([], 0.86, "yes", 13), "")
        self.assertEqual(bot.floor_stays(0.01, []), 0.02)
        self.assertEqual(bot.floor_stays(0.01, cold_sp), 0.02)
        self.assertEqual(bot.floor_stays(0.05, cold_sp), 0.05)
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_inx"], 0.02)
        self.assertIn("tell_sized_learning", bot.step_settle.__code__.co_names)


if __name__ == "__main__":
    unittest.main()
