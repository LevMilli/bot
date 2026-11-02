"""Shared vol / learn / adapt layer."""

import tempfile
import unittest

import desk_adapt


class DeskAdaptTests(unittest.TestCase):
    def test_self_check(self):
        desk_adapt.self_check()

    def test_high_vol_shrinks(self):
        stake, plan = desk_adapt.adapt_stake(
            40.0,
            history=[{"pnl": 3, "closed": "2026-11-01T12:00:00Z"}] * 20,
            vol_kwargs={"cushion": 5, "sigma": 90, "spread": 0.06, "minutes_left": 2, "ask": 0.5},
        )
        self.assertTrue(plan["play_safe"])
        self.assertLess(stake, 40.0)

    def test_proven_80_enlarges_when_calm(self):
        hist = [{"pnl": 4, "closed": "2026-11-01T12:00:00Z"}] * 16
        hist += [{"pnl": -1, "closed": "2026-11-01T13:00:00Z"}] * 2
        stake, plan = desk_adapt.adapt_stake(
            40.0,
            history=hist,
            vol_kwargs={"cushion": 100, "sigma": 40, "spread": 0.01, "minutes_left": 12, "ask": 0.86},
        )
        self.assertTrue(plan["play_big"])
        self.assertGreater(stake, 40.0)

    def test_remember_and_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            vol = desk_adapt.volatility_score(cushion=10, sigma=80, ask=0.5, minutes_left=3)
            _, plan = desk_adapt.adapt_stake(20, history=[], vol_kwargs={"ask": 0.5})
            desk_adapt.remember_vol(tmp, "btc15m", "T1", vol, plan)
            summary = desk_adapt.adapt_summary(tmp)
            self.assertIn("KXPALLADIUM15M", summary["series_15m"])
            self.assertEqual(summary["by_bot"]["btc15m"]["obs"], 1)


if __name__ == "__main__":
    unittest.main()
