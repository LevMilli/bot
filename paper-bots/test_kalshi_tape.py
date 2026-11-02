"""Kalshi public tape tracker — no network in unit tests."""

import json
import os
import tempfile
import unittest
from unittest import mock

import kalshi_tape


class KalshiTapeTests(unittest.TestCase):
    def test_series_of_ticker(self):
        self.assertEqual(kalshi_tape.series_of_ticker("KXBTC15M-26NOV020000-00"), "KXBTC15M")
        self.assertEqual(kalshi_tape.series_of_ticker("KXINXU-26OCT27H1600-T1"), "KXINXU")
        self.assertIsNone(kalshi_tape.series_of_ticker("NOPE-1"))

    def test_norm_and_dedupe_sync(self):
        with tempfile.TemporaryDirectory() as tmp:
            markets = [{"ticker": "KXBTC15M-26NOV020000-00", "close_time": "2099-01-01T00:00:00Z"}]
            trades = [
                {
                    "trade_id": "t1",
                    "ticker": "KXBTC15M-26NOV020000-00",
                    "count_fp": "2.0",
                    "yes_price_dollars": "0.40",
                    "created_time": "2026-11-02T00:00:01Z",
                    "taker_side": "yes",
                },
                {
                    "trade_id": "t1",  # duplicate
                    "ticker": "KXBTC15M-26NOV020000-00",
                    "count_fp": "2.0",
                    "yes_price_dollars": "0.40",
                    "created_time": "2026-11-02T00:00:01Z",
                    "taker_side": "yes",
                },
                {
                    "trade_id": "t2",
                    "ticker": "KXBTC15M-26NOV020000-00",
                    "count_fp": "1.5",
                    "yes_price_dollars": "0.41",
                    "created_time": "2026-11-02T00:00:02Z",
                    "taker_side": "no",
                },
            ]

            def fake_list(series):
                return markets if series == "KXBTC15M" else []

            def fake_fetch(ticker, min_ts=None, limit=200):
                return trades if ticker.startswith("KXBTC15M") else []

            with mock.patch.object(kalshi_tape, "list_open_markets", side_effect=fake_list), \
                 mock.patch.object(kalshi_tape, "fetch_trades_for_ticker", side_effect=fake_fetch):
                state = kalshi_tape.sync_tape(tmp, series=("KXBTC15M",))
            self.assertEqual(state["last_added"], 2)
            self.assertEqual(len(state["trades"]), 2)
            # Second sync adds nothing.
            with mock.patch.object(kalshi_tape, "list_open_markets", side_effect=fake_list), \
                 mock.patch.object(kalshi_tape, "fetch_trades_for_ticker", side_effect=fake_fetch):
                state2 = kalshi_tape.sync_tape(tmp, series=("KXBTC15M",))
            self.assertEqual(state2["last_added"], 0)
            self.assertEqual(len(state2["trades"]), 2)
            summary = kalshi_tape.tape_summary(tmp)
            self.assertEqual(summary["trade_count"], 2)
            self.assertEqual(summary["by_series"]["KXBTC15M"]["count"], 2)
            self.assertTrue(os.path.exists(os.path.join(tmp, "kalshi_tape.json")))

    def test_soonest_markets_cap(self):
        rows = [
            {"ticker": "A", "close_time": "2099-01-03T00:00:00Z"},
            {"ticker": "B", "close_time": "2099-01-01T00:00:00Z"},
            {"ticker": "C", "close_time": "2099-01-02T00:00:00Z"},
        ]
        kept = kalshi_tape._soonest_markets(rows, 2)
        self.assertEqual([m["ticker"] for m in kept], ["B", "C"])

    def test_self_check(self):
        kalshi_tape.self_check()


class BtcMultiWindowTests(unittest.TestCase):
    def test_evaluate_window_respects_guidelines(self):
        import importlib.util
        path = os.path.join(os.path.dirname(__file__), "btc15m-signal", "btc15m_signal.py")
        spec = importlib.util.spec_from_file_location("btc15m_signal", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        import datetime as dt
        close = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=12)
        m = {
            "ticker": "KXBTC15M-TEST",
            "target": 100.0,
            "yes_bid": 0.80, "yes_ask": 0.82,
            "no_bid": 0.18, "no_ask": 0.20,
            "open_time": close - dt.timedelta(minutes=15),
            "close_time": close,
        }
        # Price far above target → YES; but force book to return thin depth → SKIP.
        with mock.patch.object(mod, "book_for_side", return_value=(0.80, 0.82, 1.0)), \
             mock.patch.object(mod, "usd_high_impact_near", return_value=[]):
            ev = mod.evaluate_window(
                m, price=200.0, closes=[100 + i for i in range(10)],
                dvol=50.0, coinbase_only=False, edge_buf=0.05,
            )
        self.assertTrue(any("contracts" in r for r in ev["reasons"]))


if __name__ == "__main__":
    unittest.main()
