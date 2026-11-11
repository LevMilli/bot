"""Kalshi S&P scan stays inside 12:00–2:00 PM CT and does not buy from a brief."""
from __future__ import annotations

import datetime as dt
import os
import sys
import unittest
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
SP = os.path.join(HERE, "kalshi-sp500-paper")
if HERE not in sys.path:
    sys.path.insert(0, HERE)
if SP not in sys.path:
    sys.path.insert(0, SP)

import desk_profit
import risk_manager

CT = ZoneInfo("America/Chicago")


class KalshiSpScan(unittest.TestCase):
    def test_outside_noon_window_is_clock(self):
        day = dt.date(2026, 11, 11)
        before = dt.datetime(2026, 11, 11, 11, 59, tzinfo=CT)
        open_at = dt.datetime(2026, 11, 11, 12, 0, tzinfo=CT)
        close_at = dt.datetime(2026, 11, 11, 14, 0, tzinfo=CT)
        after = dt.datetime(2026, 11, 11, 14, 1, tzinfo=CT)
        self.assertEqual(risk_manager.noon_window_reason(before, day, "12:00"), "clock")
        self.assertIsNone(risk_manager.noon_window_reason(open_at, day, "12:00"))
        self.assertIsNone(risk_manager.noon_window_reason(close_at, day, "12:00"))
        self.assertEqual(risk_manager.noon_window_reason(after, day, "12:00"), "clock")

    def test_cpi_skip_stays(self):
        reason = risk_manager.news_skip_reason(dt.date(2026, 11, 10))
        self.assertIn("CPI", reason)

    def test_brief_does_not_buy_and_clock_is_written(self):
        with open(os.path.join(SP, "bot.py"), encoding="utf-8") as handle:
            text = handle.read()
        brief = text.split("def step_brief", 1)[1].split("def _sync_kalshi_tape", 1)[0]
        self.assertNotIn("open_position", brief)
        self.assertIn('reason = "clock"', text)

    def test_floor_unchanged(self):
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_inx"], 0.02)


if __name__ == "__main__":
    unittest.main()
