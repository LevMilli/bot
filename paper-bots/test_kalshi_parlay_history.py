"""Crypto Kalshi history + parlay helpers."""

import os
import tempfile
import unittest

import kalshi_history
import kalshi_parlay


class HistoryParlayTests(unittest.TestCase):
    def test_classify_regime(self):
        early = kalshi_parlay.classify_regime(
            minutes_left=12, model_p=0.92, z=1.0, cushion=80,
            min_cushion=40, min_z=0.65,
        )
        self.assertEqual(early, "confident_early")
        hold = kalshi_parlay.classify_regime(
            minutes_left=12, model_p=0.81, z=0.66, cushion=45,
            min_cushion=40, min_z=0.65,
        )
        self.assertEqual(hold, "volatile_hold")
        late = kalshi_parlay.classify_regime(
            minutes_left=4, model_p=0.9, z=1.0, cushion=80,
            min_cushion=40, min_z=0.65,
        )
        self.assertEqual(late, "parlay_window")

    def test_history_and_parlay_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            kalshi_history.record_snapshot(
                tmp, series="KXBTC15M", ticker="T1", spot=78000, target=78100,
                side="NO", yes_ask=0.2, no_ask=0.82, model_p=0.88,
                minutes_left=12, regime="volatile_hold",
            )
            kalshi_history.mark_hold(tmp, "T1", "NO", "volatile", 12)
            summary = kalshi_history.history_summary(tmp)
            self.assertEqual(summary["snapshot_count"], 1)
            self.assertEqual(len(summary["open_holds"]), 1)
            path = os.path.join(tmp, "paper_parlays.json")
            row = kalshi_parlay.open_paper_parlay(
                path,
                [
                    {"ticker": "BTC1", "side": "NO", "ask": 0.80, "fee": 0.02, "fair": 0.9,
                     "close_time": "2026-11-02T06:00:00+00:00", "series": "KXBTC15M"},
                    {"ticker": "ETH1", "side": "NO", "ask": 0.82, "fee": 0.02, "fair": 0.88,
                     "close_time": "2026-11-02T06:00:00+00:00", "series": "KXETH15M"},
                ],
                stake_dollars=40,
                note="test",
            )
            self.assertIsNotNone(row)
            self.assertEqual(len(row["legs"]), 2)
            self.assertTrue(os.path.exists(path))


if __name__ == "__main__":
    unittest.main()
