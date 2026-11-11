"""Commodity decide: 0.05 floor, series learning, red day before Adapt."""
import inspect
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "commodity-15m-paper"))

import desk_profit  # noqa: E402
from bot import (  # noqa: E402
    decide_floor,
    decide_size,
    paper_buy,
    red_day_second_buy,
    series_learning_skip,
    sister_mult,
)


def _desk():
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    import pimp_desk
    return pimp_desk


class CommodityDecide(unittest.TestCase):
    def test_floor_stays_and_a_lower_bar_is_put_back(self):
        self.assertEqual(decide_floor(0.02), 0.05)
        self.assertEqual(decide_floor(0.08), 0.08)
        self.assertEqual(decide_floor("nope"), 0.05)
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_commodity15m"], 0.05)

    def test_cold_gold_does_not_block_wti(self):
        desk = _desk()
        bucket = desk.prob_bucket(0.85)
        cold = [
            {
                "market": "KXGOLD15M",
                "bucket": bucket,
                "result": "miss",
                "side": "YES",
                "hour_ct": 8,
            }
            for _ in range(8)
        ]
        gold = series_learning_skip(cold, "KXGOLD15M", 0.85, "YES", 8)
        wti = series_learning_skip(cold, "KXWTI15M", 0.85, "YES", 8)
        self.assertIn("KXGOLD15M", gold)
        self.assertEqual(wti, "")
        self.assertEqual(
            series_learning_skip(cold[:2], "KXGOLD15M", 0.85, "YES", 8),
            "",
        )

    def test_red_day_rules_before_adapt_and_brent_is_the_sibling(self):
        self.assertEqual(red_day_second_buy(-10, 0), "")
        self.assertEqual(red_day_second_buy(-10, 1), "one new buy on a red day")
        self.assertEqual(red_day_second_buy(5, 2), "")
        # Quarter size at −$40. Adapt at $40 cannot put the $15 ladder back.
        self.assertEqual(decide_size(15, 40, -40), 3.75)
        self.assertEqual(decide_size(15, 2, -40), 2)
        self.assertEqual(sister_mult("KXWTI15M", ["KXBRENT15M"]), 0.5)
        self.assertEqual(sister_mult("KXWTI15M", ["KXGOLD15M"]), 1.0)
        self.assertEqual(decide_size(15, 40, -40, sister=0.5), 1.88)
        # A green day with no sister leaves Adapt's number alone.
        self.assertEqual(decide_size(15, 12, 4), 12)
        src = inspect.getsource(paper_buy)
        adapt_at = src.find("stake_dollars_for")
        self.assertGreater(src.find("commodity_same_day_skip"), -1)
        self.assertLess(src.find("commodity_same_day_skip"), adapt_at)
        self.assertLess(src.find("red_day_second_buy"), adapt_at)
        self.assertLess(adapt_at, src.find("decide_size"))


if __name__ == "__main__":
    unittest.main()
