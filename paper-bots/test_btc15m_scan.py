"""BTC 15-minute scan drops a late window, a band miss, and a thin cushion."""
from __future__ import annotations

import datetime as dt
import importlib.util
import os
import unittest
from unittest import mock

import desk_profit

ROOT = os.path.dirname(os.path.abspath(__file__))


def _load_btc():
    path = os.path.join(ROOT, "btc15m-signal", "btc15m_signal.py")
    spec = importlib.util.spec_from_file_location("btc15m_scan", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Btc15mScan(unittest.TestCase):
    def test_scan_drops_late_band_and_thin_cushion(self):
        btc = _load_btc()
        self.assertEqual(btc.scan_drop_reasons(0.4, 0.80, 40), ["under 1 minute"])
        self.assertEqual(btc.scan_drop_reasons(1.0, 0.80, 35), [])
        self.assertEqual(btc.scan_drop_reasons(3.0, 0.69, 40), ["ask outside 0.70-0.92"])
        self.assertEqual(btc.scan_drop_reasons(3.0, 0.93, 40), ["ask outside 0.70-0.92"])
        self.assertIn("cushion", btc.scan_drop_reasons(4.0, 0.82, 34.99)[0])
        self.assertEqual(btc.scan_drop_reasons(4.0, 0.70, 1.5, series="KXETH15M"), [])
        self.assertIn("cushion", btc.scan_drop_reasons(4.0, 0.80, 1.49, series="KXETH15M")[0])
        kept = btc.late_scan_reasons([
            "under 1 minute",
            "only 0.4 min left (< 1)",
        ])
        self.assertEqual(kept, ["under 1 minute"])
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_btc15m"], 0.05)

    def test_evaluate_keeps_under_one_minute_and_thin_cushion(self):
        btc = _load_btc()
        close = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=24)
        m = {
            "ticker": "KXBTC15M-LATE",
            "series": "KXBTC15M",
            "target": 100000.0,
            "open_time": close - dt.timedelta(minutes=15),
            "close_time": close,
            "yes_ask": 0.82,
            "no_ask": 0.20,
            "yes_bid": 0.80,
            "no_bid": 0.18,
        }
        with mock.patch.object(btc, "_sigma_for", return_value=(20.0, 20.0, None)):
            with mock.patch.object(btc, "usd_high_impact_near", return_value=False):
                late = btc.evaluate_window(
                    m, 100040.0, [100040.0] * 8, None, False, 0.05,
                    book=(0.80, 0.82, 10.0),
                    min_minutes_left=btc.PARLAY_MIN_MIN,
                )
        kept = btc.late_scan_reasons(late.get("reasons"))
        self.assertIn("under 1 minute", kept)
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_btc15m"], 0.05)


if __name__ == "__main__":
    unittest.main()
