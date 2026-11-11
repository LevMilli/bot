"""Sized Kalshi failsafe sells its own contract and does not unlock a second fill."""
from __future__ import annotations

import importlib.util
import inspect
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
    spec = importlib.util.spec_from_file_location("sized_kalshi_sell", bot_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class SizedKalshiSell(unittest.TestCase):
    def test_own_bid_sells_and_the_sibling_stays_open(self):
        bot = _load()
        sim = bot.paper_sim
        day = "2026-11-11"
        held = {
            "ticker": "KXINXU-SIZED",
            "side": "yes",
            "tower": "kalshi-sized",
            "contracts": 10,
            "cost": 8.5,
            "fee": 0.11,
            "ask": 0.85,
            "day": day,
            "fill_id": "KXINXU-SIZED|1",
        }
        sibling = {
            "ticker": "KXINXU-SP",
            "side": "yes",
            "tower": "kalshi-sp",
            "contracts": 29,
            "cost": 24.65,
            "fee": 0.26,
            "ask": 0.85,
            "day": day,
            "fill_id": "KXINXU-SP|1",
        }
        state = {"bankroll": 500.0, "open": [held, sibling], "closed": []}
        self.assertIsNone(sim.failsafe_sale(sibling, 0.40, quote_ticker="KXINXU-SP"))
        self.assertIsNone(sim.failsafe_sale(held, 0.40, quote_ticker="KXINXU-SP"))
        for raw in (None, 0, 0.50, 0.62):
            self.assertIsNone(sim.failsafe_sale(held, raw, quote_ticker="KXINXU-SIZED"))
            self.assertEqual(state["bankroll"], 500.0)
            self.assertEqual(len(state["open"]), 2)

        sale = sim.apply_failsafe(state, held, 0.40, quote_ticker="KXINXU-SIZED")
        self.assertEqual(sale["exit"], "model-flip bid under 50c")
        self.assertEqual(sale["exit_price"], 0.40)
        self.assertFalse(sale["opens_new_ticket"])
        self.assertFalse(sale["unlocks_fill"])
        self.assertGreater(sale["exit_fee"], 0)
        self.assertEqual(sale["payout"], round(10 * 0.40 - sale["exit_fee"], 4))
        self.assertEqual(state["bankroll"], round(500.0 + sale["payout"], 4))
        self.assertLess(sale["pnl"], 0)
        self.assertEqual(state["open"], [sibling])
        self.assertEqual(sibling["contracts"], 29)
        self.assertEqual(held["status"], "sold")
        self.assertNotIn("result", held)
        self.assertEqual(sim.trades_on(state, day), 2)
        self.assertEqual(bot.second_fill_skip(sim.trades_on(state, day)), "one fill a day")
        self.assertEqual(bot.decide_size(40, 40, sim.trades_on(state, day)), 0.0)
        self.assertIsNone(sim.apply_failsafe(state, sibling, 0.40, quote_ticker="KXINXU-SP"))
        self.assertEqual(state["open"], [sibling])

        import pimp_desk
        with tempfile.TemporaryDirectory() as tmp:
            pimp_desk.record_learning(tmp, {
                "reason": sale["exit"],
                "market": "S&P-sized",
                "prob": 0.85,
                "stake": 8.61,
                "fill_id": held["fill_id"],
                "side": "yes",
            })
            rows = pimp_desk.load_learning(tmp)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["reason"], "model-flip bid under 50c")
            self.assertNotIn("result", rows[0])

        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_inx"], 0.02)
        src = inspect.getsource(bot.step_settle)
        failsafe, _, _settle = src.partition("MODEL-FLIP SELL")
        self.assertIn("apply_failsafe", failsafe)
        self.assertNotIn('"result": "hit"', failsafe)


if __name__ == "__main__":
    unittest.main()
