"""Shadow tick must be able to record near-miss (not gated by not IS_SHADOW)."""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

import desk_more


ROOT = Path(__file__).resolve().parent
BTC = ROOT / "btc15m-signal" / "btc15m_signal.py"


class ShadowNearMissUngate(unittest.TestCase):
    def test_is_near_miss_zp_only_no_edge_soft(self):
        nm = desk_more.is_near_miss(
            reasons=["ask outside band"],
            z=0.60,
            p=0.90,
            edge=0.049,
            min_edge=0.05,
        )
        self.assertTrue(nm["near_miss"])
        self.assertEqual(nm["soft"], ["z"])
        self.assertNotIn("edge", nm["soft"])

    def test_p_band_with_ask_outside_qualifies(self):
        nm = desk_more.is_near_miss(
            reasons=["p short", "ask outside 0.70-0.92"],
            z=0.78,
            p=0.782,
            edge=0.10,
            min_edge=0.05,
        )
        self.assertTrue(nm["near_miss"])
        self.assertEqual(nm["soft"], ["p"])

    def test_btc_source_records_near_miss_outside_not_is_shadow(self):
        src = BTC.read_text(encoding="utf-8")
        # Near-miss block should not be nested only under `if desk_brain and not IS_SHADOW`.
        self.assertIn("Near-miss shadow densify", src)
        self.assertIn("Near-miss densify under DESK_SHADOW too", src)
        # Sanity: still keep brain under not IS_SHADOW
        self.assertIn("if desk_brain and not IS_SHADOW:", src)


if __name__ == "__main__":
    unittest.main()
