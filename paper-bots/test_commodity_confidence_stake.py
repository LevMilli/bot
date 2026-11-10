"""Commodity buy-in scales with model confidence. Gates and haircuts stay."""
from __future__ import annotations

import importlib.util
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


def _load_commodity():
    path = os.path.join(HERE, "commodity-15m-paper", "bot.py")
    spec = importlib.util.spec_from_file_location("commodity_15m_bot_conf_stake", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class CommodityConfidenceStake(unittest.TestCase):
    def test_eighty_is_smaller_than_ninety(self):
        cbot = _load_commodity()
        low, _ = cbot.commodity_confidence_stake(0.80, {"mult": 1.0}, 15.0, 135.0)
        high, _ = cbot.commodity_confidence_stake(0.90, {"mult": 1.0}, 15.0, 135.0)
        self.assertEqual(low, 6.0)
        self.assertEqual(high, 15.0)
        self.assertGreater(high, low)

    def test_midpoint_is_linear(self):
        cbot = _load_commodity()
        stake, note = cbot.commodity_confidence_stake(0.85, {"mult": 1.0}, 15.0, 135.0)
        self.assertEqual(stake, 10.5)
        self.assertIn("90% $15", note)

    def test_above_ninety_stays_at_the_tower_share(self):
        cbot = _load_commodity()
        stake, _ = cbot.commodity_confidence_stake(0.96, {"mult": 1.0}, 15.0, 135.0)
        self.assertEqual(stake, 15.0)

    def test_speed_lane_uses_the_low_buy_in(self):
        cbot = _load_commodity()
        stake, _ = cbot.commodity_confidence_stake(0.74, {"mult": 1.0}, 15.0, 135.0)
        self.assertEqual(stake, 6.0)

    def test_vol_and_brent_haircuts_still_cut_a_ninety(self):
        cbot = _load_commodity()
        plan = {
            "mult": 0.50,
            "profit_lock_mult": 0.50,
            "series_corr_haircut": {"apply": True, "mult": 0.50},
        }
        high, _ = cbot.commodity_confidence_stake(0.90, plan, 15.0, 135.0)
        low, _ = cbot.commodity_confidence_stake(0.80, plan, 15.0, 135.0)
        # 15 * 0.5 * 0.5 * 0.5 = 1.875 → 1.88; 6 * 0.125 = 0.75 → sub-$1 buys nothing
        self.assertEqual(high, 1.88)
        self.assertEqual(low, 0.0)
        self.assertGreater(high, low)

    def test_caps_at_tower_room_and_cash(self):
        cbot = _load_commodity()
        room, _ = cbot.commodity_confidence_stake(0.90, {"mult": 1.0}, 4.0, 135.0)
        cash, _ = cbot.commodity_confidence_stake(0.90, {"mult": 1.0}, 15.0, 3.0)
        self.assertEqual(room, 4.0)
        self.assertEqual(cash, 3.0)

    def test_fee_floor_and_daily_budget_unchanged(self):
        import desk_profit
        import desk_roi_plan
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_commodity15m"], 0.05)
        self.assertEqual(float(desk_roi_plan.DAILY_R_BUDGET["commodity-15m"]), 2.0)


if __name__ == "__main__":
    unittest.main()
