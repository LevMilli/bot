"""BTC 15-minute learning is one row per fill, keyed by series. The floor stays 0.05."""
from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest

import desk_profit
import pimp_desk

ROOT = os.path.dirname(os.path.abspath(__file__))


def _load_btc():
    path = os.path.join(ROOT, "btc15m-signal", "btc15m_signal.py")
    spec = importlib.util.spec_from_file_location("btc15m_learn", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _misses(market, n=8):
    return [
        {
            "result": "miss",
            "market": market,
            "bucket": "0.8-0.9",
            "side": "YES",
            "hour_ct": 13,
            "stake": 8,
            "fill_id": f"{market}-{i}",
        }
        for i in range(n)
    ]


class Btc15mLearn(unittest.TestCase):
    def test_settle_row_is_the_series_and_one_per_fill(self):
        btc = _load_btc()
        eth = btc.settle_learning_row(
            {
                "ticker": "KXETH15M-T",
                "series": "KXETH15M",
                "side": "YES",
                "fair_at_entry": 0.88,
                "cost": 8.0,
                "fill_id": "KXETH15M-T|1",
                "closed": "2026-11-11 18:00:00 UTC",
            },
            1.5,
            hour_ct=13,
        )
        btc_row = btc.settle_learning_row(
            {
                "ticker": "KXBTC15M-T",
                "side": "NO",
                "fair_at_entry": 0.84,
                "cost": 8.0,
                "fill_id": "KXBTC15M-T|1",
            },
            -2.0,
            hour_ct=13,
        )
        self.assertEqual(eth["market"], "KXETH15M")
        self.assertEqual(eth["result"], "hit")
        self.assertEqual(eth["reason"], "settled")
        self.assertEqual(btc_row["market"], "KXBTC15M")
        self.assertEqual(btc_row["result"], "miss")
        self.assertNotEqual(eth["market"], "BTC")
        with tempfile.TemporaryDirectory() as tmp:
            pimp_desk.record_learning(tmp, eth)
            pimp_desk.record_learning(tmp, dict(eth, result="miss"))
            rows = pimp_desk.load_learning(tmp)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["fill_id"], "KXETH15M-T|1")
            self.assertEqual(rows[0]["result"], "hit")

    def test_a_cold_hour_does_not_cross_series_or_lower_the_floor(self):
        btc = _load_btc()
        eth = _misses("KXETH15M")
        self.assertIn(
            "KXETH15M",
            pimp_desk.learning_skip(eth, "KXETH15M", "0.8-0.9", side="YES", hour_ct=13),
        )
        self.assertEqual(
            pimp_desk.learning_skip(eth, "KXBTC15M", "0.8-0.9", side="YES", hour_ct=13),
            "",
        )
        btc_rows = _misses("KXBTC15M")
        self.assertIn(
            "KXBTC15M",
            pimp_desk.learning_skip(btc_rows, "KXBTC15M", "0.8-0.9", side="YES", hour_ct=13),
        )
        self.assertEqual(
            pimp_desk.learning_skip(btc_rows, "KXETH15M", "0.8-0.9", side="YES", hour_ct=13),
            "",
        )
        thin = _misses("KXBTC15M", n=2)
        self.assertEqual(
            pimp_desk.learning_skip(thin, "KXBTC15M", "0.8-0.9", side="YES", hour_ct=13),
            "",
        )
        self.assertEqual(btc.decide_floor(0.01), 0.05)
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_btc15m"], 0.05)


if __name__ == "__main__":
    unittest.main()
