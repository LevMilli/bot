"""Sized Kalshi scans only inside 12:05–14:55 CT. A header is not a sample fill."""
from __future__ import annotations

import datetime as dt
import importlib.util
import os
import sys
import types
import unittest

import desk_profit

ROOT = os.path.dirname(os.path.abspath(__file__))
DAY = dt.date(2026, 11, 11)


def _load():
    if "requests" not in sys.modules:
        stub = types.ModuleType("requests")
        stub.Session = lambda: types.SimpleNamespace(headers={})
        sys.modules["requests"] = stub
    sized = os.path.join(ROOT, "kalshi-sized-paper")
    sibling = os.path.join(ROOT, "kalshi-sp500-paper")
    for path in (sized, sibling):
        if path not in sys.path:
            sys.path.insert(0, path)
    bot_path = os.path.join(sized, "bot.py")
    spec = importlib.util.spec_from_file_location("sized_kalshi_scan", bot_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class SizedKalshiScan(unittest.TestCase):
    def test_the_window_stays_and_a_header_is_not_a_fill(self):
        bot = _load()
        ct = bot.CT
        noon = dt.datetime(2026, 11, 11, 12, 0, tzinfo=ct)
        open_at = dt.datetime(2026, 11, 11, 12, 5, tzinfo=ct)
        close_at = dt.datetime(2026, 11, 11, 14, 55, tzinfo=ct)
        after = dt.datetime(2026, 11, 11, 14, 56, tzinfo=ct)
        self.assertTrue(bot.outside_scan_window(noon, DAY, "11:00"))
        self.assertIn("12:05", bot.outside_scan_window(noon, DAY, "11:00"))
        self.assertEqual(bot.outside_scan_window(open_at, DAY, "11:00"), "")
        self.assertEqual(bot.outside_scan_window(close_at, DAY, "12:05"), "")
        self.assertTrue(bot.outside_scan_window(after, DAY, "12:05"))
        start, end = bot.scan_window(DAY, "12:30")
        self.assertEqual(start.hour, 12)
        self.assertEqual(start.minute, 30)
        self.assertEqual((end.hour, end.minute), (14, 55))
        fact = bot.header_only_fact("# Learning.md - Sized Kalshi notes\n")
        self.assertEqual(fact["fact"], "header-only learning file")
        self.assertFalse(fact["fill"])
        self.assertIsNone(bot.header_only_fact("# Learning\n\n- a real note\n"))
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_inx"], 0.02)
        with open(os.path.join(ROOT, "kalshi-sized-paper", "bot.py"), encoding="utf-8") as handle:
            src = handle.read()
        self.assertLess(src.find("def outside_scan_window"), src.find("def step_scan"))
        self.assertLess(src.find("outside_scan_window("), src.find("open_position("))

    def test_the_best_refused_edge_needs_a_real_ask(self):
        bot = _load()
        best = bot.remember_refused_edge(None, 0.84, 0.03)
        best = bot.remember_refused_edge(best, 0.90, 0.01)
        self.assertEqual(best, 0.03)
        self.assertEqual(bot.remember_refused_edge(best, None, 0.20), 0.03)
        self.assertEqual(bot.remember_refused_edge(best, 0, 0.20), 0.03)
        self.assertEqual(bot.remember_refused_edge(None, None, None), None)
        self.assertIn("remember_refused_edge", bot.step_scan.__code__.co_names)
        self.assertIn("header_only_fact", bot.step_scan.__code__.co_names)


if __name__ == "__main__":
    unittest.main()
