"""Coinbase spot scan reads ETH and SOL, logs BTC, and lets a failed candle win."""
from __future__ import annotations

import importlib.util
import os
import sys
import unittest

import desk_profit

HERE = os.path.dirname(os.path.abspath(__file__))


def _bot():
    path = os.path.join(HERE, "coinbase-spot-paper", "bot.py")
    spec = importlib.util.spec_from_file_location("coinbase_scan", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class CoinbaseScan(unittest.TestCase):
    def test_btc_is_logged_and_a_failed_candle_wins_the_card(self):
        bot = _bot()
        cfg = bot.locked_cfg({})
        self.assertEqual(cfg["products_trade"], ["ETH-USD", "SOL-USD"])
        self.assertIn("BTC-USD", cfg["products_research_only"])
        eth = bot.scan_book("ETH-USD", [100.0, 101.5], cfg=cfg)
        sol = bot.scan_book("SOL-USD", [20.0, 20.4], cfg=cfg)
        self.assertEqual(eth["action"], "read")
        self.assertEqual(eth["last"], 101.5)
        self.assertEqual(sol["last"], 20.4)
        self.assertFalse(eth["scored_as_buy"])
        btc = bot.scan_book("BTC-USD", [100.0, 130.0], cfg=cfg)
        self.assertEqual(btc["action"], "log")
        self.assertFalse(btc["scored_as_buy"])
        self.assertNotIn("edge", btc)
        self.assertEqual(btc["last"], 130.0)
        self.assertIn("not scored as a buy", btc["reason"])
        failed = bot.scan_book("SOL-USD", None, "TimeoutError", cfg=cfg)
        self.assertTrue(failed["data_skip"])
        self.assertIsNone(failed["last"])
        self.assertNotEqual(failed["last"], eth["last"])
        hole = bot.scan_book("ETH-USD", [100.0, None, 102.0], cfg=cfg)
        self.assertTrue(hole["data_skip"])
        self.assertIsNone(hole["last"])
        card = bot.scan_card([
            {"product": "ETH-USD", "action": "buy", "reason": "edge 0.20 clears", "edge": 0.20},
            failed,
            btc,
        ])
        self.assertEqual(card, failed["reason"])
        self.assertTrue(card.lower().startswith("data "))
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["coinbase_spot"], 0.05)
        self.assertIn("scan_book", bot.run_once.__code__.co_names)
        self.assertIn("scan_card", bot._card_skip_reason.__code__.co_names)


if __name__ == "__main__":
    unittest.main()
