"""Kalshi S&P records a close from the bid that was on the book."""
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

import desk_brain
import desk_profit
import paper_sim


class KalshiSpRecord(unittest.TestCase):
    def test_sale_records_bankroll_fee_and_the_bid(self):
        with tempfile.TemporaryDirectory() as tmp:
            pos = {
                "fill_id": "KXINXU-T|1",
                "ticker": "KXINXU-T",
                "side": "yes",
                "cost": 8.5,
                "fee": 0.11,
                "risk": 8.61,
                "exit_price": 0.40,
                "exit_fee": 0.17,
                "pnl": -4.84,
            }
            first = paper_sim.record_close(
                pos, bankroll=495.16, reason="model-flip bid under 50c",
                bid=0.40, root=tmp,
            )
            second = paper_sim.record_close(
                pos, bankroll=495.16, reason="model-flip bid under 50c",
                bid=0.40, root=tmp,
            )
            self.assertEqual(pos["bankroll_after"], 495.16)
            self.assertEqual(pos["pnl"], -4.84)
            self.assertEqual(first["bot"], "kalshi-sp")
            self.assertEqual(first["fill_id"], "KXINXU-T|1")
            self.assertEqual(first["bid"], 0.40)
            self.assertEqual(first["fee"], 0.17)
            self.assertEqual(first["exit_name"], "model-flip bid under 50c")
            self.assertEqual(first["cash"], 495.16)
            journal = desk_brain.load_journal(tmp)
            matches = [
                row for row in journal["decisions"]
                if row.get("fill_id") == "KXINXU-T|1"
            ]
            self.assertEqual(len(matches), 1)
            self.assertEqual(second["fill_id"], first["fill_id"])

    def test_settle_does_not_invent_a_bid(self):
        with tempfile.TemporaryDirectory() as tmp:
            pos = {
                "fill_id": "KXINXU-T|2",
                "ticker": "KXINXU-T",
                "side": "no",
                "fee": 0.11,
                "pnl": -8.61,
            }
            written = paper_sim.record_close(
                pos, bankroll=491.39, reason="settled", bid=None, root=tmp,
            )
            self.assertNotIn("bid", written)
            self.assertNotIn("exit_price", pos)
            self.assertEqual(written["exit_name"], "settled")
            self.assertEqual(written["action"], "settle")
            self.assertEqual(pos["pnl"], -8.61)
            self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_inx"], 0.02)


if __name__ == "__main__":
    unittest.main()
