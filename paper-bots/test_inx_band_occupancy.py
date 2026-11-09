"""INX band occupancy insight digest (observe-only)."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

import desk_living
from helpers import inx_band_occupancy as occ

CT = ZoneInfo("America/Chicago")


class InxBandOccupancy(unittest.TestCase):
    def test_score_markets_band(self):
        scored = occ.score_markets([
            {"ticker": "A", "yes_ask_dollars": 0.85},
            {"ticker": "B", "yes_ask": 70},  # cents → 0.70 out of band
            {"ticker": "C", "ask": 0.91},
            {"ticker": "D"},  # missing ask
        ])
        self.assertEqual(scored["with_ask"], 3)
        self.assertEqual(scored["in_band_n"], 2)
        self.assertAlmostEqual(scored["occupancy"], 2 / 3, places=4)
        self.assertTrue(scored["occupied"])
        self.assertFalse(scored["thin"])

    def test_feature_history_pre_noon(self):
        rows = [
            {
                "series": "KXINXU",
                "bot": "kalshi-sp",
                "ask": 0.84,
                "at": "2026-11-09T10:15:00-06:00",
                "chicago_day": "2026-11-09",
            },
            {
                "series": "KXINXU",
                "bot": "kalshi-sized",
                "yes_ask_dollars": 0.50,
                "at": "2026-11-09T11:40:00-06:00",
                "chicago_day": "2026-11-09",
            },
            {
                "series": "KXINXU",
                "bot": "kalshi-sp",
                "ask": 0.88,
                "at": "2026-11-09T13:05:00-06:00",
                "chicago_day": "2026-11-09",
            },
            {
                "series": "KXBTC15M",
                "bot": "btc15m",
                "ask": 0.85,
                "at": "2026-11-09T10:00:00-06:00",
            },
        ]
        hist = occ.score_feature_history(
            rows, now=datetime(2026, 11, 9, 14, 0, tzinfo=CT),
        )
        self.assertEqual(hist["with_ask"], 3)
        self.assertEqual(hist["in_band_n"], 2)
        self.assertEqual(hist["pre_noon_with_ask"], 2)
        self.assertEqual(hist["pre_noon_in_band_n"], 1)
        self.assertAlmostEqual(hist["pre_noon_occupancy"], 0.5, places=4)
        digest = occ.build_digest(live={"occupancy": 0.1, "thin": False, "occupied": True}, history=hist)
        self.assertEqual(digest["helper"], "inx_band_occupancy")
        self.assertEqual(digest["pre_noon_occupancy"], 0.5)
        self.assertEqual(digest["occupancy"], 0.5)  # prefer pre-noon
        self.assertFalse(digest["may_place_alone"])
        self.assertTrue(digest["floors_locked"])

    def test_write_chip_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "desk_feature_store.jsonl"), "w", encoding="utf-8") as handle:
                handle.write(json.dumps({
                    "series": "KXINXU",
                    "bot": "kalshi-sp",
                    "ask": 0.86,
                    "at": "2026-11-09T11:00:00-06:00",
                    "chicago_day": "2026-11-09",
                }) + "\n")

            def opener(_url):
                return json.dumps({
                    "markets": [
                        {"ticker": "KXINXU-1", "yes_ask_dollars": 0.83},
                        {"ticker": "KXINXU-2", "yes_ask_dollars": 0.40},
                    ],
                }).encode()

            out = occ.write_digest_from_desk(tmp, opener=opener)
            self.assertEqual(out["live"]["in_band_n"], 1)
            self.assertEqual(out["history"]["pre_noon_in_band_n"], 1)
            chip = desk_living.inx_band_occupancy_chip(tmp)
            self.assertIn("inx band", chip["label"])
            self.assertFalse(chip["may_place_alone"])

    def test_inventory_lists_helper(self):
        self.assertIn("inx_band_occupancy_digest.json", desk_living.INSIGHT_HELPER_DIGESTS)


if __name__ == "__main__":
    unittest.main()
