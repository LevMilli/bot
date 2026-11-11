"""Kalshi S&P learning is one row per fill. A thin noon bucket does not lower 0.02."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SP = os.path.join(HERE, "kalshi-sp500-paper")
if HERE not in sys.path:
    sys.path.insert(0, HERE)
if SP not in sys.path:
    sys.path.insert(0, SP)

import desk_profit
import pimp_desk
import risk_manager


class KalshiSpLearn(unittest.TestCase):
    def test_one_row_per_fill(self):
        with tempfile.TemporaryDirectory() as tmp:
            row = {
                "result": "hit",
                "reason": "settled",
                "market": "S&P",
                "bucket": "0.8-0.9",
                "stake": 8.5,
                "fill_id": "KXINXU-T|1",
                "side": "yes",
            }
            pimp_desk.record_learning(tmp, row)
            pimp_desk.record_learning(tmp, dict(row, result="miss"))
            rows = pimp_desk.load_learning(tmp)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["fill_id"], "KXINXU-T|1")
            self.assertEqual(rows[0]["result"], "hit")

    def test_thin_noon_bucket_does_not_lower_the_floor(self):
        self.assertEqual(risk_manager.noon_edge(0.01, sample_n=2), 0.02)
        self.assertEqual(risk_manager.noon_edge(0.02, sample_n=0), 0.02)
        self.assertEqual(risk_manager.noon_edge(0.05, sample_n=1), 0.05)
        thin = [
            {"result": "miss", "market": "S&P", "bucket": "0.8-0.9", "stake": 8}
            for _ in range(2)
        ]
        self.assertEqual(
            pimp_desk.learning_skip(thin, "S&P", "0.8-0.9", side="yes", hour_ct=13),
            "",
        )
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_inx"], 0.02)
        self.assertEqual(risk_manager.INX_FLOOR, 0.02)


if __name__ == "__main__":
    unittest.main()
