"""Commodity failsafe sells a model-flip at the listing bid. A drop watch does not sell."""
from __future__ import annotations

import importlib.util
import os
import unittest

import desk_profit
import desk_roi_plan

ROOT = os.path.dirname(os.path.abspath(__file__))


def _load():
    path = os.path.join(ROOT, "commodity-15m-paper", "bot.py")
    spec = importlib.util.spec_from_file_location("commodity_sell", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class CommoditySell(unittest.TestCase):
    def test_flip_sells_at_the_listing_and_the_watch_does_not(self):
        bot = _load()
        pos = {
            "ticker": "KXBRENT15M-T",
            "series": "KXBRENT15M",
            "side": "YES",
            "ask": 0.80,
            "contracts": 4,
            "cost": 3.24,
        }
        market = {"yes_bid": 0.35, "no_bid": 0.62}
        self.assertIsNone(bot.failsafe_sale(
            pos, flip=False, market=market, today_pnl=-66.90, watch_fired=True,
        ))
        self.assertIsNone(bot.failsafe_sale(
            pos, flip=True, market={"no_bid": 0.90}, today_pnl=-66.90,
        ))
        self.assertIsNone(bot.failsafe_sale(
            pos, flip=True, market={"yes_bid": 0}, today_pnl=-66.90,
        ))
        self.assertEqual(bot.failsafe_sale(
            pos, flip=True, market=market, today_pnl=-66.90,
        ), 0.35)
        self.assertEqual(
            bot.same_series_block("KXBRENT15M", {"KXBRENT15M"}),
            "same series already sold this check",
        )
        self.assertEqual(bot.same_series_block("KXGOLD15M", {"KXBRENT15M"}), "")
        self.assertFalse(desk_roi_plan.COMMODITY_TIME_STOP_LIVE)
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_commodity15m"], 0.05)
        self.assertNotIn("paper_sell", bot.watch_open.__code__.co_names)
        self.assertIn("failsafe_sale", bot.manage_model_flips.__code__.co_names)
        self.assertIn("same_series_block", bot.paper_buy.__code__.co_names)


if __name__ == "__main__":
    unittest.main()
