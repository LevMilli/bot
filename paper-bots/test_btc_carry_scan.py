"""BTC carry scan reads the public prints. A Coinbase price does not fill a hole."""
from __future__ import annotations

import importlib.util
import os
import unittest

import desk_profit

HERE = os.path.dirname(os.path.abspath(__file__))


def _bot():
    path = os.path.join(HERE, "btc-carry-paper", "bot.py")
    spec = importlib.util.spec_from_file_location("btc_carry_scan", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class BtcCarryScan(unittest.TestCase):
    def test_a_missing_archive_stays_missing_and_a_spot_price_does_not_fill_it(self):
        bot = _bot()
        spot = 97000.0
        missed = bot.scan_marks(
            {"funding": [], "premium": [], "error": "no archive rows", "coinbase": spot},
            coinbase_price=spot,
        )
        self.assertTrue(missed["data_skip"])
        self.assertEqual(missed["reason"], "data no archive rows")
        self.assertEqual(missed["funding"], [])
        self.assertEqual(missed["premium"], [])
        self.assertFalse(missed["opened"])
        self.assertFalse(missed["sold"])
        self.assertFalse(missed["borrowed_spot"])

        stuffed = bot.scan_marks(
            {
                "funding": [{"time": "2026-02-01T00:00:00+00:00", "rate": spot}],
                "premium": [{"time": "2026-02-01T00:00:00+00:00", "close": spot}],
            },
            coinbase_price=spot,
        )
        self.assertTrue(stuffed["data_skip"])
        self.assertEqual(stuffed["funding"], [])
        self.assertEqual(stuffed["premium"], [])
        self.assertNotEqual(stuffed["premium"], [{"close": spot}])

        half = bot.scan_marks(
            {
                "funding": [{"time": "2026-02-01T00:00:00+00:00", "rate": 0.0001}],
                "premium": [],
                "coinbase": spot,
            },
            coinbase_price=spot,
        )
        self.assertTrue(half["data_skip"])
        self.assertEqual(half["reason"], "data premium archive missing")
        self.assertEqual(half["premium"], [])
        self.assertEqual(half["funding"][0]["rate"], 0.0001)
        self.assertFalse(half["opened"])

        real = bot.scan_marks(
            {
                "funding": [{"time": "2026-02-01T00:00:00+00:00", "rate": 0.0001}],
                "premium": [{"time": "2026-02-01T00:00:00+00:00", "close": 0.0004}],
                "coinbase": spot,
            },
            coinbase_price=spot,
        )
        self.assertFalse(real["data_skip"])
        self.assertEqual(real["reason"], "funding and premium read")
        self.assertEqual(real["funding"][0]["rate"], 0.0001)
        self.assertEqual(real["premium"][0]["close"], 0.0004)
        self.assertNotEqual(real["premium"][0]["close"], spot)
        self.assertFalse(real["opened"])
        self.assertFalse(real["sold"])

        keyed = bot.scan_marks(
            {
                "funding": [{"time": "2026-02-01T00:00:00+00:00", "rate": 0.0001}],
                "premium": [{"time": "2026-02-01T00:00:00+00:00", "close": 0.0004}],
            },
            key_set=True,
        )
        self.assertTrue(keyed["data_skip"])
        self.assertEqual(keyed["funding"], [])
        self.assertEqual(keyed["premium"], [])
        self.assertNotIn("not-a-real-key", keyed["reason"])

        urls = [url for _kind, url in bot.archive_urls(bot._parse_time("2026-10-15T00:00:00+00:00"))]
        self.assertTrue(all("data.binance.vision" in url for url in urls))
        self.assertFalse(any("api.exchange.coinbase.com" in url or "fapi.binance.com" in url for url in urls))
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["binance_btc_carry"], 0.02)
        self.assertNotIn("_urlopen", bot.scan_marks.__code__.co_names)
        self.assertNotIn("hold_step", bot.scan_marks.__code__.co_names)
        self.assertIn("scan_marks", bot.run_once.__code__.co_names)


if __name__ == "__main__":
    unittest.main()
