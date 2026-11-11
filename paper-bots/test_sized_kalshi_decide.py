"""Sized Kalshi decide keeps 0.02 and the fair-edge gate. One fill a day."""
from __future__ import annotations

import importlib.util
import os
import sys
import types
import unittest

import desk_profit

ROOT = os.path.dirname(os.path.abspath(__file__))


def _load():
    if "requests" not in sys.modules:
        stub = types.ModuleType("requests")
        stub.Session = lambda: types.SimpleNamespace(headers={})
        sys.modules["requests"] = stub
    for path in (
        os.path.join(ROOT, "kalshi-sized-paper"),
        os.path.join(ROOT, "kalshi-sp500-paper"),
    ):
        if path not in sys.path:
            sys.path.insert(0, path)
    bot_path = os.path.join(ROOT, "kalshi-sized-paper", "bot.py")
    spec = importlib.util.spec_from_file_location("sized_kalshi_decide", bot_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class SizedKalshiDecide(unittest.TestCase):
    def test_both_gates_stay_and_the_sibling_risk_skips(self):
        bot = _load()
        self.assertEqual(bot.decide_floor(0.01), 0.02)
        self.assertEqual(bot.decide_floor(0.05), 0.05)
        self.assertAlmostEqual(bot.fair_gate_need(0.01, extra=0), 0.03)
        self.assertAlmostEqual(bot.fair_gate_need(0.05), 0.06)
        self.assertIn("twin edge", bot.fair_edge_skip(0.02, 0.02))
        self.assertEqual(bot.fair_edge_skip(0.04, 0.02), "")
        held = {"open": [{"ticker": "KXINXU-T"}]}
        self.assertIn("KXINXU-T", bot.sibling_skip("KXINXU-T", held))
        self.assertEqual(bot.sibling_skip("KXINXU-OTHER", held), "")
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_inx"], 0.02)
        self.assertEqual(bot.CFG["daily_loss_limit"], 25.0)
        self.assertEqual(bot.CFG["max_trades_per_day"], 1)

    def test_learning_uses_this_series_and_adapt_cannot_add_a_second_fill(self):
        bot = _load()
        cold_sized = [
            {
                "market": "S&P-sized",
                "bucket": "0.8-0.9",
                "result": "miss",
                "side": "YES",
                "hour_ct": 13,
            }
            for _ in range(8)
        ]
        cold_sp = [dict(row, market="S&P") for row in cold_sized]
        self.assertIn("S&P-sized", bot.learning_skip_sized(cold_sized, 0.86, "yes", 13))
        self.assertEqual(bot.learning_skip_sized(cold_sp, 0.86, "yes", 13), "")
        self.assertEqual(bot.second_fill_skip(0), "")
        self.assertEqual(bot.second_fill_skip(1), "one fill a day")
        self.assertEqual(bot.decide_size(40, 50, 0), 40)
        self.assertEqual(bot.decide_size(40, 12, 0), 12)
        self.assertEqual(bot.decide_size(40, 50, 1), 0)
        self.assertIn("decide_size", bot.step_scan.__code__.co_names)
        self.assertIn("fair_edge_skip", bot.step_scan.__code__.co_names)
        self.assertIn("learning_skip_sized", bot.step_scan.__code__.co_names)


if __name__ == "__main__":
    unittest.main()
