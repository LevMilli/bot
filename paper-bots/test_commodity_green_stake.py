"""Commodity green-sleeve buy-in floor. Fee floor and 2.0R stay put."""
from __future__ import annotations

import importlib.util
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


def _load_commodity():
    path = os.path.join(HERE, "commodity-15m-paper", "bot.py")
    spec = importlib.util.spec_from_file_location("commodity_15m_bot_green_stake", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class CommodityGreenStake(unittest.TestCase):
    def test_lifts_small_ticket_when_sleeve_is_ahead(self):
        cbot = _load_commodity()
        state = {"cash": 135.31, "open": [{"cost": 3.75}]}
        stake, note = cbot.commodity_green_stake(
            3.75,
            state,
            {"vol": {"regime": "elevated"}},
            tower_left=15.0,
        )
        self.assertEqual(stake, 8.0)
        self.assertIn("lifted to $8.00", note)

    def test_keeps_a_larger_desk_stake(self):
        cbot = _load_commodity()
        state = {"cash": 135.0, "open": []}
        stake, note = cbot.commodity_green_stake(
            12.0, state, {"vol": {"regime": "calm"}}, tower_left=15.0,
        )
        self.assertEqual(stake, 12.0)
        self.assertEqual(note, "")

    def test_no_lift_when_sleeve_is_under_the_start(self):
        cbot = _load_commodity()
        state = {"cash": 90.0, "open": []}
        stake, note = cbot.commodity_green_stake(
            3.75, state, {"vol": {"regime": "calm"}}, tower_left=15.0,
        )
        self.assertEqual(stake, 3.75)
        self.assertEqual(note, "")

    def test_no_lift_in_extreme_vol(self):
        cbot = _load_commodity()
        state = {"cash": 135.0, "open": []}
        stake, note = cbot.commodity_green_stake(
            3.75, state, {"vol": {"regime": "extreme"}}, tower_left=15.0,
        )
        self.assertEqual(stake, 3.75)
        self.assertEqual(note, "")

    def test_caps_at_tower_room_and_cash(self):
        cbot = _load_commodity()
        state = {"cash": 135.0, "open": [{"cost": 10.0}]}
        stake, _note = cbot.commodity_green_stake(
            3.75, state, {"vol": {"regime": "high"}}, tower_left=5.0,
        )
        self.assertEqual(stake, 5.0)
        # Cash left is $6, but the open position keeps the sleeve ahead of $100.
        tight = {"cash": 6.0, "open": [{"cost": 100.0}]}
        stake_cash, _note = cbot.commodity_green_stake(
            3.75, tight, {"vol": {"regime": "calm"}}, tower_left=15.0,
        )
        self.assertEqual(stake_cash, 6.0)

    def test_does_not_shrink_a_ticket_the_desk_already_sized(self):
        cbot = _load_commodity()
        state = {"cash": 4.0, "open": [{"cost": 100.0}]}
        stake, note = cbot.commodity_green_stake(
            7.5, state, {"vol": {"regime": "calm"}}, tower_left=15.0,
        )
        self.assertEqual(stake, 7.5)
        self.assertEqual(note, "")

    def test_fee_floor_and_daily_budget_unchanged(self):
        import desk_profit
        import desk_roi_plan
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_commodity15m"], 0.05)
        self.assertEqual(float(desk_roi_plan.DAILY_R_BUDGET["commodity-15m"]), 2.0)
        self.assertEqual(float(desk_roi_plan.DAILY_R_BUDGET["btc15m"]), 2.0)
        self.assertEqual(float(desk_roi_plan.DAILY_R_BUDGET["sports-gap"]), 1.5)


if __name__ == "__main__":
    unittest.main()
