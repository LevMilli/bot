"""Coinbase failsafe sells an open long at a real mark. A flat book has no sell."""
from __future__ import annotations

import datetime as dt
import importlib.util
import os
import unittest

import desk_profit

HERE = os.path.dirname(os.path.abspath(__file__))
NOW = dt.datetime(2026, 11, 11, 18, 0, tzinfo=dt.timezone.utc)


def _bot():
    path = os.path.join(HERE, "coinbase-spot-paper", "bot.py")
    spec = importlib.util.spec_from_file_location("coinbase_sell", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pos(bot, **over):
    row = {
        "ticker": "ETH-USD",
        "side": "buy",
        "entry_price": 100.0,
        "cost": 25.0,
        "fill_id": "ETH-USD|1",
        "opened": (NOW - dt.timedelta(hours=1)).isoformat(),
        "last_mark": 99.0,
        "paper_only": True,
    }
    row.update(over)
    return row


class CoinbaseSell(unittest.TestCase):
    def test_an_open_long_sells_at_the_real_mark_and_a_flat_book_does_not(self):
        bot = _bot()
        cheap = {
            "taker_fee": 0.001,
            "slippage": 0.001,
            "venue_min_edge": 0.01,
            "stop_pct": 0.001,
            "time_stop_hours": 1.0,
            "min_z": 0.5,
        }
        self.assertGreaterEqual(bot.locked_cfg(cheap)["taker_fee"], bot.LOCKED_TAKER_MIN)
        self.assertGreaterEqual(bot.locked_cfg(cheap)["venue_min_edge"], 0.05)

        pos = _pos(bot)
        state = {"cash": 475.0, "open": [pos], "closed": []}
        invented = 100.0 * (1.0 - 0.015)
        missed = bot.failsafe_sale(
            state, {"ETH-USD": None, "SOL-USD": invented}, z_by_product={"ETH-USD": -3},
            now=NOW, cfg=cheap,
        )
        self.assertFalse(missed["sold"])
        self.assertFalse(missed["flat"])
        self.assertFalse(missed["hit"])
        self.assertEqual(state["open"], [pos])
        self.assertEqual(state["closed"], [])
        self.assertEqual(state["cash"], 475.0)
        self.assertEqual(pos["last_mark"], 99.0)

        for bad in (0, -1, "", "nope", float("nan")):
            held = bot.failsafe_sale(
                state, {"ETH-USD": bad}, z_by_product={"ETH-USD": -3}, now=NOW, cfg=cheap,
            )
            self.assertFalse(held["sold"])
            self.assertEqual(state["cash"], 475.0)
            self.assertEqual(len(state["open"]), 1)

        quiet = bot.failsafe_sale(
            state, {"ETH-USD": 100.0}, z_by_product={"ETH-USD": -1.9}, now=NOW, cfg=cheap,
        )
        self.assertFalse(quiet["sold"])
        self.assertEqual(len(state["open"]), 1)

        above_trip = bot.failsafe_sale(
            state, {"ETH-USD": 103.0}, z_by_product={"ETH-USD": 0}, now=NOW, cfg=cheap,
        )
        self.assertFalse(above_trip["sold"])
        self.assertEqual(pos["entry_price"], 100.0)

        soft = bot.failsafe_sale(
            state, {"ETH-USD": 106.0}, z_by_product={"ETH-USD": 0}, now=NOW, cfg=cheap,
        )
        self.assertFalse(soft["sold"])
        self.assertEqual(state["cash"], 475.0)

        young = _pos(bot, opened=(NOW - dt.timedelta(hours=23)).isoformat())
        waiting = {"cash": 475.0, "open": [young], "closed": []}
        early = bot.failsafe_sale(
            waiting, {"ETH-USD": 100.0}, z_by_product={"ETH-USD": 0}, now=NOW, cfg=cheap,
        )
        self.assertFalse(early["sold"])
        self.assertEqual(len(waiting["open"]), 1)

        stopped = bot.failsafe_sale(
            state, {"ETH-USD": invented, "SOL-USD": 20.0},
            z_by_product={"ETH-USD": 0}, now=NOW, cfg=cheap,
        )
        self.assertTrue(stopped["sold"])
        self.assertFalse(stopped["hit"])
        self.assertEqual(state["open"], [])
        closed = state["closed"][0]
        self.assertEqual(closed["exit"], "stop")
        self.assertEqual(closed["exit_name"], "stop −1.5%")
        self.assertEqual(closed["exit_price"], invented)
        self.assertEqual(closed["fill_id"], "ETH-USD|1")
        self.assertEqual(closed["tower"], "coinbase-spot")
        self.assertEqual(closed["stake"], 25.0)
        self.assertNotIn("hit", closed)
        self.assertNotIn("result", closed)
        self.assertAlmostEqual(closed["fee"], 0.5, places=4)
        self.assertAlmostEqual(state["cash"], 499.125, places=3)
        self.assertEqual(replacement_reason(bot, state), "failsafe sold — no replacement")
        self.assertEqual(state["open"], [])
        self.assertAlmostEqual(state["cash"], 499.125, places=3)

        fresh = {
            "cash": 475.0,
            "open": [_pos(bot)],
            "closed": [],
        }
        flipped = bot.failsafe_sale(
            fresh, {"ETH-USD": 100.0}, z_by_product={"ETH-USD": -2}, now=NOW, cfg=cheap,
        )
        self.assertEqual(flipped["sales"][0]["exit"], "model-flip")
        self.assertEqual(flipped["sales"][0]["exit_name"], "z≤−2")
        self.assertNotIn("hit", flipped["sales"][0])
        self.assertFalse(flipped["hit"])

        aged = {
            "cash": 475.0,
            "open": [_pos(bot, opened=(NOW - dt.timedelta(hours=24)).isoformat())],
            "closed": [],
        }
        timed = bot.failsafe_sale(
            aged, {"ETH-USD": 100.0}, z_by_product={"ETH-USD": 0}, now=NOW, cfg=cheap,
        )
        self.assertEqual(timed["sales"][0]["exit"], "time")
        self.assertEqual(timed["sales"][0]["exit_name"], "24h")

        green = {
            "cash": 475.0,
            "open": [_pos(bot, fill_id="ETH-USD|tp")],
            "closed": [],
        }
        took = bot.failsafe_sale(
            green, {"ETH-USD": 107.0}, z_by_product={"ETH-USD": 3}, now=NOW, cfg=cheap,
        )
        self.assertEqual(took["sales"][0]["exit"], "take-profit")
        self.assertEqual(took["sales"][0]["exit_name"], "fee take-profit")
        self.assertEqual(took["sales"][0]["exit_price"], 107.0)
        self.assertGreater(took["sales"][0]["pnl"], 0)
        self.assertNotIn("hit", took["sales"][0])
        self.assertNotIn("result", took["sales"][0])
        self.assertFalse(took["hit"])
        self.assertAlmostEqual(took["sales"][0]["fee"], 0.5, places=4)

        short = {
            "cash": 475.0,
            "open": [_pos(bot, side="short")],
            "closed": [],
        }
        kept = bot.failsafe_sale(
            short, {"ETH-USD": invented}, z_by_product={"ETH-USD": -3}, now=NOW, cfg=cheap,
        )
        self.assertFalse(kept["sold"])
        self.assertEqual(len(short["open"]), 1)
        self.assertEqual(short["cash"], 475.0)

        flat = {"cash": 500.0, "open": [], "closed": []}
        none = bot.failsafe_sale(
            flat, {"ETH-USD": invented}, z_by_product={"ETH-USD": -3}, now=NOW, cfg=cheap,
        )
        self.assertTrue(none["flat"])
        self.assertFalse(none["sold"])
        self.assertFalse(none["hit"])
        self.assertEqual(flat["open"], [])
        self.assertEqual(flat["closed"], [])
        self.assertEqual(flat["cash"], 500.0)
        self.assertEqual(bot.replacement_block(flat), "")
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["coinbase_spot"], 0.05)
        self.assertIn("failsafe_sale", bot.run_once.__code__.co_names)
        self.assertIn("replacement_block", bot.place_shadow_buy.__code__.co_names)
        self.assertNotIn("apply_exit", bot.watch_sleeve.__code__.co_names)


def replacement_reason(bot, state):
    decision = {
        "action": "buy",
        "flat": False,
        "edge": 0.10,
        "floor": 0.05,
        "product": "ETH-USD",
    }
    refused = bot.place_shadow_buy(
        state, decision, 100.0, btc_yes=False, intent_path="", now="2026-11-11T18:00:00+00:00",
    )
    return refused["reason"]


if __name__ == "__main__":
    unittest.main()
