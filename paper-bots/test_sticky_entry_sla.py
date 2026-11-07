"""E1 #136/#137 sticky-open SLA — exit priority; red-day entry block."""
from __future__ import annotations

import os
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_more
import desk_roi_plan


class StickyEntrySla(unittest.TestCase):
    def test_blocks_on_red_with_sticky(self):
        bots = [{
            "id": "sports-gap",
            "positions": [{
                "ticker": "OLD",
                "side": "home",
                "opened": "2026-10-01T12:00:00Z",
                "risk": 20,
            }],
        }]
        msg = desk_more.sticky_entry_blocks(
            "sports-gap", today=-3.0, bots=bots, now_epoch=time.time(),
        )
        self.assertTrue(msg)
        self.assertIn("sticky-open", msg)
        # Green day: no block even with sticky
        self.assertEqual(
            desk_more.sticky_entry_blocks(
                "sports-gap", today=1.5, bots=bots, now_epoch=time.time(),
            ),
            "",
        )

    def test_no_block_without_sticky(self):
        bots = [{
            "id": "btc15m",
            "positions": [{
                "ticker": "FRESH",
                "side": "yes",
                "opened": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "risk": 10,
            }],
        }]
        self.assertEqual(
            desk_more.sticky_entry_blocks(
                "btc15m", today=-1.0, bots=bots, now_epoch=time.time(),
            ),
            "",
        )

    def test_sla_status_and_plan(self):
        bots = [{
            "id": "commodity-15m",
            "positions": [{
                "ticker": "OLD",
                "opened": "2026-10-01T12:00:00Z",
                "risk": 5,
            }],
        }]
        st = desk_more.sticky_sla_status(bots, now_epoch=time.time())
        self.assertGreaterEqual(st["sticky_count"], 1)
        self.assertTrue(st["exit_priority"])
        self.assertTrue(st["fee_floors_locked"])
        plan = desk_roi_plan.plan_summary(bots=bots)
        self.assertIn("sticky_sla", plan)
        self.assertTrue(plan["fee_floors_locked"])

    def test_fee_floors(self):
        import desk_profit
        floors = desk_profit.venue_floors_locked()
        self.assertTrue(floors["locked"])
        self.assertAlmostEqual(floors["venues"]["kalshi_sports"]["floor"], 0.06)


if __name__ == "__main__":
    unittest.main()
