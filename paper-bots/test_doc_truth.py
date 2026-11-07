"""Doc-truth pins — inventory / floors must match live code (no stale 0.04 / TP lies)."""
from __future__ import annotations

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_profit
import pimp_desk


class DocTruth(unittest.TestCase):
    def test_venue_floors_locked(self):
        floors = desk_profit.venue_floors_locked()
        self.assertTrue(floors["locked"])
        v = floors["venues"]
        self.assertAlmostEqual(v["kalshi_sports"]["floor"], 0.06)
        self.assertAlmostEqual(v["kalshi_btc15m"]["floor"], 0.05)
        self.assertAlmostEqual(v["kalshi_commodity15m"]["floor"], 0.05)
        self.assertAlmostEqual(v["kalshi_inx"]["floor"], 0.02)
        self.assertAlmostEqual(v["solana_dex"]["floor"], 0.02)

    def test_desk_min_edge_is_006(self):
        self.assertAlmostEqual(float(pimp_desk.DEFAULTS["min_edge"]), 0.06)

    def test_auto_cadence(self):
        by_id = {}
        for row in pimp_desk.AUTO:
            if "every_sec" in row:
                by_id[row["id"]] = int(row["every_sec"])
        self.assertEqual(by_id.get("sports-gap"), 180)
        self.assertEqual(by_id.get("btc15m"), 60)
        self.assertEqual(by_id.get("commodity-15m"), 90)
        self.assertEqual(by_id.get("memecoin"), 180)

    def test_inventory_no_stale_floor_or_tp_lie(self):
        path = os.path.join(HERE, "BUY_SELL_FAILSAFE_INVENTORY.md")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        # Desk min_edge row must not claim 0.04 anymore.
        self.assertNotRegex(
            text,
            r"\|\s*`min_edge`\s*\|\s*0\.04\s*\|",
        )
        self.assertRegex(text, r"\|\s*`min_edge`\s*\|\s*\*\*0\.06\*\*")
        self.assertNotIn("TP print-only", text)
        self.assertIn("manage_take_profits", text)
        self.assertIn("real sell path", text)
        # Kalshi daily loss is $25 live.
        self.assertRegex(text, r"−\*\*\$25\*\*")

    def test_readme_btc_tp_honest(self):
        path = os.path.join(HERE, "README.md")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        self.assertNotIn("TP print-only", text)
        self.assertIn("real TP", text)
        self.assertIn("manage_take_profits", text)


if __name__ == "__main__":
    unittest.main()
