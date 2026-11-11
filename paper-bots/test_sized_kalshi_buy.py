"""Sized Kalshi writes the exit intent before cash and does not buy the open row again."""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
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
    bot_path = os.path.join(ROOT, "kalshi-sized-paper", "bot.py")
    spec = importlib.util.spec_from_file_location("sized_kalshi_buy", bot_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class SizedKalshiBuy(unittest.TestCase):
    def test_intent_names_the_flip_before_cash_and_the_open_row_is_not_bought_again(self):
        bot = _load()
        sim = bot.paper_sim
        tmp = tempfile.TemporaryDirectory()
        old = sim.BUY_INTENT
        sim.BUY_INTENT = os.path.join(tmp.name, "buy_intent.json")
        try:
            state = {"bankroll": 500.0, "open": [], "closed": []}
            seen = {}
            real = sim.write_buy_intent

            def _wrapped(**kwargs):
                seen["bankroll"] = state["bankroll"]
                return real(**kwargs)

            sim.write_buy_intent = _wrapped
            pick = {"ticker": "KXINXU-T", "side": "yes", "ask": 0.84}
            pos = sim.place_paper_buy(
                state, dt.date(2026, 11, 11), "KXINXU", pick, 2, "2026-11-11T12:10:00",
            )
            self.assertIsInstance(pos, dict)
            self.assertEqual(seen["bankroll"], 500.0)
            self.assertLess(state["bankroll"], 500.0)
            self.assertEqual(pos["exit_rule"], "model-flip bid under 50c")
            self.assertEqual(len(state["open"]), 1)
            with open(sim.BUY_INTENT, encoding="utf-8") as handle:
                saved = json.load(handle)
            self.assertEqual(saved["exit_rule"], "model-flip bid under 50c")
            self.assertTrue(saved["paper_only"])
            self.assertEqual(saved["tower"], "kalshi-sized")
            cash = state["bankroll"]
            again = sim.place_paper_buy(
                state, dt.date(2026, 11, 11), "KXINXU", pick, 2, "2026-11-11T12:20:00",
            )
            self.assertEqual(again, "open row already on the book")
            self.assertEqual(state["bankroll"], cash)
            self.assertEqual(len(state["open"]), 1)

            empty = {"bankroll": 500.0, "open": [], "closed": []}
            sim.write_buy_intent = real
            sim.write_buy_intent(
                fill_id="missing", ticker="KXINXU-T", side="yes",
                contracts=1, stake=1.0, ask=0.84,
            )
            self.assertEqual(sim.reconcile_buy_intent(empty), "abandoned")
            self.assertEqual(empty["open"], [])
            with self.assertRaises(ValueError):
                real(
                    fill_id="x", ticker="KXINXU-T", side="yes",
                    contracts=1, stake=1.0, ask=0,
                )
            self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_inx"], 0.02)
            self.assertIn("place_paper_buy", bot.step_scan.__code__.co_names)
            self.assertIn("reconcile_buy_intent", bot.main.__code__.co_names)
        finally:
            sim.BUY_INTENT = old
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
