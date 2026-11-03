"""Anti-revenge: same market cool after stop/flip."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_roi_plan


class AntiRevenge(unittest.TestCase):
    def test_blocks_same_ticker(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = desk_roi_plan.record_anti_revenge(
                tmp, bot="sports-gap", ticker="KXNBA-1", reason="hard-stop",
            )
            self.assertTrue(out["cooled"])
            msg = desk_roi_plan.anti_revenge_blocks(tmp, "sports-gap", "KXNBA-1")
            self.assertIn("anti-revenge", msg)
            self.assertIn("KXNBA-1", msg)
            # Other ticker / other bot clear.
            self.assertEqual(
                desk_roi_plan.anti_revenge_blocks(tmp, "sports-gap", "KXNBA-2"), ""
            )
            self.assertEqual(
                desk_roi_plan.anti_revenge_blocks(tmp, "btc15m", "KXNBA-1"), ""
            )

    def test_requires_ticker(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = desk_roi_plan.record_anti_revenge(
                tmp, bot="btc15m", ticker="", reason="model-flip",
            )
            self.assertFalse(out["cooled"])

    def test_fee_floors_untouched(self):
        import desk_profit
        floors = desk_profit.venue_floors_locked()
        self.assertTrue(floors["locked"])
        self.assertTrue(floors["all_ok"])


if __name__ == "__main__":
    unittest.main()
