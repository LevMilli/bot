"""Commodity scan stays on the eight series. A missing book is not a sister price."""
from __future__ import annotations

import datetime as dt
import importlib.util
import os
import unittest

import desk_profit
from helpers import eia_blackout

ROOT = os.path.dirname(os.path.abspath(__file__))


def _load():
    path = os.path.join(ROOT, "commodity-15m-paper", "bot.py")
    spec = importlib.util.spec_from_file_location("commodity_scan", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class CommodityScan(unittest.TestCase):
    def test_eight_series_and_a_missing_book_is_not_the_sister(self):
        bot = _load()
        self.assertEqual(len(bot.SERIES), 8)
        self.assertEqual(
            set(bot.SERIES),
            {
                "KXGOLD15M", "KXWTI15M", "KXSILVER15M", "KXBRENT15M",
                "KXCOPPER15M", "KXPLATINUM15M", "KXPALLADIUM15M", "KXNATGAS15M",
            },
        )
        spot, book, reason = bot.scan_quote(
            "KXWTI15M", 70.0, None,
            sister_spot=80.0, sister_book=(0.02, 12),
        )
        self.assertEqual(reason, "no book")
        self.assertIsNone(book)
        self.assertIsNone(spot)
        kept, kept_book, clear = bot.scan_quote(
            "KXGOLD15M", 2400.0, (0.03, 5),
            sister_spot=70.0, sister_book=(0.02, 12),
        )
        self.assertEqual(clear, "")
        self.assertEqual(kept, 2400.0)
        self.assertEqual(kept_book, (0.03, 5))
        self.assertEqual(
            bot.scan_quote("KXINXU", 1.0, (0.01, 3))[2],
            "not on the commodity clock",
        )
        now = dt.datetime(2026, 11, 11, 16, 0, tzinfo=dt.timezone.utc)
        events = [{"title": "EIA Crude Oil Inventories", "date": now.isoformat()}]
        blocked = eia_blackout.energy_blackout("KXWTI15M", events, now=now)
        clear_metal = eia_blackout.energy_blackout("KXGOLD15M", events, now=now)
        self.assertTrue(blocked["blocked"])
        self.assertFalse(clear_metal["blocked"])
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_commodity15m"], 0.05)


if __name__ == "__main__":
    unittest.main()
