"""Chicago-day loss stop: at or below −2.0R, commodity buys go to zero.

Does not change daily_r_blocks, the 0.05 floor, the confidence ladder, or exits.
"""
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
    commodity_loss_stop,
    confidence_target,
    main,
    paper_sell,
    settle_account,
)


class CommodityLossStopTest(unittest.TestCase):
    def test_at_or_below_minus_40_blocks(self):
        self.assertIn("settle-only", commodity_loss_stop(-40.0))
        self.assertIn("daily loss", commodity_loss_stop(-40.0))
        self.assertIn("settle-only", commodity_loss_stop(-68.34))
        self.assertEqual(commodity_loss_stop(-39.99), "")
        self.assertEqual(commodity_loss_stop(0.0), "")
        self.assertEqual(commodity_loss_stop(40.0), "")
        self.assertEqual(commodity_loss_stop(None), "")

    def test_shared_profit_lock_unchanged(self):
        # Loss still does not trip the shared helper. Profit still does.
        self.assertEqual(desk_roi_plan.daily_r_blocks("commodity-15m", -40.0), "")
        self.assertEqual(desk_roi_plan.daily_r_blocks("commodity-15m", -68.34), "")
        self.assertIn("settle-only", desk_roi_plan.daily_r_blocks("commodity-15m", 40.0))
        self.assertEqual(desk_roi_plan.daily_r_blocks("sports-gap", -40.0), "")

    def test_buy_loop_zeros_max_buys_and_exits_stay(self):
        src = inspect.getsource(main)
        self.assertIn("commodity_loss_stop(today_pnl)", src)
        self.assertIn("max_buys_eff = 0", src)
        self.assertIn("daily_r_blocks", src)
        # Sells and settles are not gated by the loss stop.
        self.assertNotIn("commodity_loss_stop", inspect.getsource(paper_sell))
        self.assertNotIn("commodity_loss_stop", inspect.getsource(settle_account))

    def test_locked_amounts(self):
        self.assertEqual(float(desk_roi_plan.DAILY_R_BUDGET["commodity-15m"]), 2.0)
        self.assertEqual(float(desk_roi_plan.DAILY_R_USD), 20.0)
        self.assertEqual(EDGE_BUFFER, 0.05)
        self.assertEqual(CONF_STAKE_LO, 6.0)
        self.assertEqual(CONF_STAKE_HI, 15.0)
        self.assertEqual(confidence_target(0.85), 10.5)
        self.assertFalse(desk_roi_plan.COMMODITY_TIME_STOP_LIVE)


if __name__ == "__main__":
    unittest.main()
