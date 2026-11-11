"""Kalshi S&P failsafe sells its own contract at the bid minus the taker."""
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
import paper_sim
import pimp_desk


class KalshiSpSell(unittest.TestCase):
    def test_sale_is_the_real_bid_minus_the_taker(self):
        pos = {"contracts": 10, "cost": 8.5, "fee": 0.11, "ask": 0.85}
        sale = paper_sim.failsafe_sale(pos, 0.40)
        self.assertEqual(sale["exit"], "model-flip bid under 50c")
        self.assertEqual(sale["exit_price"], 0.40)
        self.assertFalse(sale["opens_new_ticket"])
        self.assertEqual(sale["payout"], round(10 * 0.40 - sale["exit_fee"], 4))
        self.assertGreater(sale["exit_fee"], 0)
        self.assertLess(sale["payout"], 4.0)

    def test_sized_contract_and_missing_bid_are_not_sold(self):
        held = {"contracts": 10, "cost": 8.5, "fee": 0.11}
        self.assertIsNotNone(paper_sim.failsafe_sale(held, 0.40))
        self.assertIsNone(paper_sim.failsafe_sale(dict(held, tower="kalshi-sized"), 0.40))
        self.assertIsNone(paper_sim.failsafe_sale(dict(held, sized=True), 0.40))
        for raw in (None, 0, 0.50, 0.62):
            self.assertIsNone(paper_sim.failsafe_sale(held, raw))
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_inx"], 0.02)

    def test_failsafe_reason_is_not_a_hit(self):
        with tempfile.TemporaryDirectory() as tmp:
            pimp_desk.record_learning(tmp, {
                "reason": "model-flip bid under 50c",
                "market": "S&P",
                "bucket": "0.8-0.9",
                "stake": 8.5,
                "fill_id": "KXINXU-T|1",
                "side": "yes",
            })
            rows = pimp_desk.load_learning(tmp)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["reason"], "model-flip bid under 50c")
            self.assertNotIn("result", rows[0])


if __name__ == "__main__":
    unittest.main()
