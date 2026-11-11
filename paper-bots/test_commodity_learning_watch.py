"""Commodity closes teach learning, and a dropping open mark is watched.

Does not place a paper buy. Does not write the live learning journal.
Fee floor, 2.0R day, confidence ladder, and the time-stop shadow stay put.
"""
import datetime as dt
import inspect
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "commodity-15m-paper"))

import desk_roi_plan  # noqa: E402
from bot import (  # noqa: E402
    CONF_STAKE_HI,
    CONF_STAKE_LO,
    EDGE_BUFFER,
    commodity_learning_block,
    commodity_learning_row,
    confidence_target,
    drop_worth_watching,
    paper_buy,
    paper_sell,
    settle_account,
    main,
    _desk,
)


STAMP = "2026-11-11 00:30:00 UTC"  # 6:30 PM America/Chicago on Nov 10


def _pos(**extra):
    row = {
        "series": "KXGOLD15M",
        "fill_id": "KXGOLD15M|2026-11-11 00:30:00 UTC",
        "fair_at_entry": 0.86,
        "cost": 10.5,
        "side": "YES",
        "ticker": "KXGOLD15M-TEST",
        "ask": 0.74,
    }
    row.update(extra)
    return row


class CommodityLearningWatchTest(unittest.TestCase):
    def test_miss_row_uses_series_and_chicago_hour(self):
        row = commodity_learning_row(_pos(), -10.5, STAMP)
        self.assertEqual(row["result"], "miss")
        self.assertEqual(row["market"], "KXGOLD15M")
        self.assertEqual(row["prob"], 0.86)
        self.assertEqual(row["stake"], 10.5)
        self.assertEqual(row["side"], "YES")
        self.assertEqual(row["hour_ct"], 18)
        self.assertEqual(row["fill_id"], "KXGOLD15M|2026-11-11 00:30:00 UTC")

    def test_hit_and_missing_fields_are_honest(self):
        hit = commodity_learning_row(_pos(fair_at_entry=0.93, cost=15), 4.2, STAMP)
        self.assertEqual(hit["result"], "hit")
        self.assertEqual(hit["stake"], 15)
        self.assertIsNone(commodity_learning_row(_pos(fill_id=""), -1, STAMP))
        self.assertIsNone(commodity_learning_row(_pos(series=""), -1, STAMP))
        self.assertIsNone(commodity_learning_row(_pos(fair_at_entry=None), -1, STAMP))

    def test_eight_cold_misses_block_that_bucket_only(self):
        desk = _desk()
        misses = [
            {
                "result": "miss",
                "market": "KXGOLD15M",
                "bucket": "0.8-0.9",
                "side": "YES",
                "hour_ct": 18,
                "stake": 6,
            }
            for _ in range(8)
        ]
        cold = desk.learning_skip(
            misses, "KXGOLD15M", "0.8-0.9", side="YES", hour_ct=18,
        )
        self.assertIn("Skipping", cold)
        self.assertIn("KXGOLD15M", cold)
        self.assertEqual(
            desk.learning_skip(misses[:7], "KXGOLD15M", "0.8-0.9", side="YES", hour_ct=18),
            "",
        )
        hits = [dict(row, result="hit") for row in misses]
        self.assertEqual(
            desk.learning_skip(hits, "KXGOLD15M", "0.8-0.9", side="YES", hour_ct=18),
            "",
        )
        # A confident bucket and a different series stay open.
        self.assertEqual(
            desk.learning_skip(misses, "KXGOLD15M", "0.9-1.0", side="YES", hour_ct=18),
            "",
        )
        self.assertEqual(
            desk.learning_skip(misses, "KXWTI15M", "0.8-0.9", side="YES", hour_ct=18),
            "",
        )

    def test_drop_watch_uses_the_desk_adverse_bar(self):
        self.assertTrue(drop_worth_watching(0.74, 0.69))
        self.assertFalse(drop_worth_watching(0.74, 0.70))
        self.assertFalse(drop_worth_watching(None, 0.50))
        self.assertEqual(desk_roi_plan.ADVERSE_MARK_DROP, 0.05)

    def test_close_and_buy_paths_call_learning(self):
        self.assertIn("tell_commodity_learning", inspect.getsource(paper_sell))
        self.assertIn("tell_commodity_learning", inspect.getsource(settle_account))
        self.assertIn("commodity settle miss", inspect.getsource(settle_account))
        self.assertIn("commodity_learning_block", inspect.getsource(paper_buy))
        self.assertIn("backfill_commodity_learning", inspect.getsource(main))
        self.assertIn("DROP WATCH", inspect.getsource(main))

    def test_locked_gates_unchanged(self):
        self.assertEqual(EDGE_BUFFER, 0.05)
        self.assertEqual(CONF_STAKE_LO, 6.0)
        self.assertEqual(CONF_STAKE_HI, 15.0)
        self.assertEqual(confidence_target(0.85), 10.5)
        self.assertEqual(desk_roi_plan.DAILY_R_BUDGET["commodity-15m"], 2.0)
        self.assertEqual(desk_roi_plan.DAILY_R_USD, 20)
        self.assertFalse(desk_roi_plan.COMMODITY_TIME_STOP_LIVE)
        # learning_block must not raise when the journal is missing or empty.
        self.assertIsInstance(commodity_learning_block("KXGOLD15M", 0.9, "YES"), str)

    def test_stamp_hour_is_chicago_not_utc(self):
        # 00:30 UTC is 18:30 CT in November, not hour 0.
        row = commodity_learning_row(_pos(), -6, STAMP)
        self.assertNotEqual(row["hour_ct"], 0)
        self.assertEqual(
            row["hour_ct"],
            dt.datetime(2026, 11, 11, 0, 30, tzinfo=dt.timezone.utc)
            .astimezone(dt.timezone(dt.timedelta(hours=-6)))
            .hour,
        )


if __name__ == "__main__":
    unittest.main()
