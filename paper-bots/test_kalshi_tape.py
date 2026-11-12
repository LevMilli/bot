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

    def test_family_budgets(self):
        self.assertIn("sports", kalshi_tape.FAMILY_BUDGETS)
        self.assertIn("crypto15m", kalshi_tape.FAMILY_BUDGETS)
        self.assertIn("commodity15m", kalshi_tape.FAMILY_BUDGETS)
        self.assertIn("inx", kalshi_tape.FAMILY_BUDGETS)
        self.assertLessEqual(kalshi_tape.FAMILY_BUDGETS["sports"]["max_markets_per_series"], 25)
        self.assertLessEqual(kalshi_tape.FAMILY_BUDGETS["commodity15m"]["max_markets_per_series"], 15)
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(kalshi_tape, "list_open_markets", return_value=[]), \
                 mock.patch.object(kalshi_tape, "fetch_trades_for_ticker", return_value=[]):
                state = kalshi_tape.sync_tape_family(tmp, "crypto15m")
            self.assertTrue(state.get("paper_only"))

    def test_self_check(self):
        kalshi_tape.self_check()

    def _markets(self, n):
        return [{"ticker": f"KXBTC15M-26NOV02{i:04d}-00", "close_time": f"2099-01-01T00:{i:02d}:00Z"}
                for i in range(n)]

    def test_429_stops_the_tape_instead_of_asking_every_market(self):
        calls = []

        def fake_fetch(ticker, min_ts=None, limit=200):
            calls.append(ticker)
            raise kalshi_tape.RateLimited("429")

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(kalshi_tape, "list_open_markets", return_value=self._markets(10)), \
                 mock.patch.object(kalshi_tape, "fetch_trades_for_ticker", side_effect=fake_fetch):
                state = kalshi_tape.sync_tape(tmp, series=("KXBTC15M",))
        self.assertEqual(len(calls), 1)
        self.assertIn("rate limited", state["last_error"])
        self.assertIn("10 market(s) left", state["last_stopped"])

    def test_time_budget_leaves_the_rest_for_next_check(self):
        now = [0.0]

        def clock():
            return now[0]

        def fake_fetch(ticker, min_ts=None, limit=200):
            now[0] += 4.0
            return []

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(kalshi_tape, "list_open_markets", return_value=self._markets(20)), \
                 mock.patch.object(kalshi_tape, "fetch_trades_for_ticker", side_effect=fake_fetch):
                state = kalshi_tape.sync_tape(tmp, series=("KXBTC15M",), budget_sec=10, clock=clock)
        self.assertIn("tape budget 10s hit", state["last_stopped"])
        self.assertIn("17 market(s) left", state["last_stopped"])

    def test_get_json_does_not_retry_a_429(self):
        import urllib.error
        hits = []

        def boom(req, timeout=None):
            hits.append(1)
            raise urllib.error.HTTPError(req.full_url, 429, "Too Many", {}, None)

        with mock.patch.object(kalshi_tape.urllib.request, "urlopen", side_effect=boom), \
             mock.patch.object(kalshi_tape.time, "sleep") as nap:
            with self.assertRaises(kalshi_tape.RateLimited):
                kalshi_tape._get_json("https://example.invalid/x")
        self.assertEqual(len(hits), 1)
        nap.assert_not_called()

    def test_budget_env_reaches_tower_children(self):
        import pimp_desk
        self.assertIn("KALSHI_TAPE_BUDGET_SEC", pimp_desk._ENV_KEEP)
        with mock.patch.dict(os.environ, {"KALSHI_TAPE_BUDGET_SEC": "12"}):
            self.assertEqual(kalshi_tape.tape_budget_sec(), 12.0)


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
