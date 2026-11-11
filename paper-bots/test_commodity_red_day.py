"""A red Chicago day gets smaller and skips the shape that already lost.

The +$40 profit lock still stops new buys. A loss does not. The 0.05 floor,
the $6-to-$15 ladder, and daily_r_blocks stay put. Exits are not sized here.
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
    RED_DAY_FLOOR,
    commodity_red_day_mult,
    commodity_same_day_skip,
    confidence_target,
    main,
    paper_buy,
    paper_sell,
    settle_account,
)

# 8:09 AM CT on Nov 11.
NOW = dt.datetime(2026, 11, 11, 14, 9, tzinfo=dt.timezone.utc)
TODAY = "2026-11-11 14:00:00 UTC"
# 7:00 PM CT Nov 10. UTC date is already Nov 11. Chicago day is still Nov 10.
LAST_EVENING = "2026-11-11 01:00:00 UTC"


def _close(pnl, prob, stamp, series="KXGOLD15M", side="YES", exit_why="settled"):
    return {
        "series": series,
        "side": side,
        "fair_at_entry": prob,
        "pnl": pnl,
        "closed": stamp,
        "exit": exit_why,
        "fill_id": f"{series}|{stamp}|{pnl}",
    }


class CommodityRedDayAdjustTest(unittest.TestCase):
    def test_size_scales_down_and_floors_at_two_r(self):
        self.assertEqual(commodity_red_day_mult(0), 1.0)
        self.assertEqual(commodity_red_day_mult(12), 1.0)
        self.assertEqual(commodity_red_day_mult(None), 1.0)
        self.assertEqual(commodity_red_day_mult(-20), 0.625)
        self.assertEqual(commodity_red_day_mult(-40), RED_DAY_FLOOR)
        self.assertEqual(commodity_red_day_mult(-68.34), RED_DAY_FLOOR)
        self.assertEqual(RED_DAY_FLOOR, 0.25)

    def test_same_day_miss_skips_that_shape_only(self):
        lost = [_close(-15, 0.86, TODAY, exit_why="model-flip side YES→NO")]
        skip = commodity_same_day_skip(lost, "KXGOLD15M", 0.84, "YES", NOW)
        self.assertIn("KXGOLD15M", skip)
        self.assertIn("0.8-0.9", skip)
        self.assertIn("model-flip", skip)
        # A more confident bucket, another series, and last evening do not block.
        self.assertEqual(commodity_same_day_skip(lost, "KXGOLD15M", 0.93, "YES", NOW), "")
        self.assertEqual(commodity_same_day_skip(lost, "KXWTI15M", 0.86, "YES", NOW), "")
        evening = [_close(-15, 0.86, LAST_EVENING)]
        self.assertEqual(
            commodity_same_day_skip(evening, "KXGOLD15M", 0.86, "YES", NOW), "",
        )
        won = [_close(4, 0.86, TODAY), _close(-1, 0.86, TODAY)]
        self.assertEqual(commodity_same_day_skip(won, "KXGOLD15M", 0.86, "YES", NOW), "")

    def test_buy_path_adjusts_and_exits_stay(self):
        src = inspect.getsource(main)
        self.assertIn("commodity_red_day_mult", src)
        self.assertIn("one new buy", src)
        self.assertIn("daily_r_blocks", src)
        self.assertNotIn("commodity_loss_stop", src)
        self.assertIn("commodity_same_day_skip", inspect.getsource(paper_buy))
        self.assertIn("commodity_red_day_mult", inspect.getsource(paper_buy))
        self.assertNotIn("commodity_red_day_mult", inspect.getsource(paper_sell))
        self.assertNotIn("commodity_red_day_mult", inspect.getsource(settle_account))

    def test_locked_amounts(self):
        self.assertEqual(desk_roi_plan.daily_r_blocks("commodity-15m", -40.0), "")
        self.assertEqual(desk_roi_plan.daily_r_blocks("commodity-15m", -68.34), "")
        self.assertIn("settle-only", desk_roi_plan.daily_r_blocks("commodity-15m", 40.0))
        self.assertEqual(float(desk_roi_plan.DAILY_R_BUDGET["commodity-15m"]), 2.0)
        self.assertEqual(float(desk_roi_plan.DAILY_R_USD), 20.0)
        self.assertEqual(EDGE_BUFFER, 0.05)
        self.assertEqual(CONF_STAKE_LO, 6.0)
        self.assertEqual(CONF_STAKE_HI, 15.0)
        self.assertEqual(confidence_target(0.80), 6.0)
        self.assertEqual(confidence_target(0.90), 15.0)
        self.assertEqual(confidence_target(0.85), 10.5)
        self.assertFalse(desk_roi_plan.COMMODITY_TIME_STOP_LIVE)


if __name__ == "__main__":
    unittest.main()
