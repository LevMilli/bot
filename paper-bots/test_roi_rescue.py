"""Overnight ROI rescue: stop bleed, starve losers, keep fee floors."""

import json
import os
import unittest

import desk_master
import desk_more

ROOT = os.path.dirname(os.path.abspath(__file__))


class RoiRescueTests(unittest.TestCase):
    def test_meme_red_lock_fires_at_minus_eight(self):
        shares = desk_more.effective_tower_shares(meme_today=-10.58)
        self.assertAlmostEqual(shares["memecoin"], desk_more.MEME_RED_SHARE)
        self.assertEqual(desk_more.MEME_RED_LOCK_USD, 8.0)
        soft = desk_more.effective_tower_shares(meme_today=-5)
        base = desk_more.DEFAULT_TOWER_BUDGET_SHARE["memecoin"]
        self.assertAlmostEqual(soft["memecoin"], base)

    def test_inx_drawdown_halt(self):
        import importlib.util

        path = os.path.join(ROOT, "kalshi-sp500-paper", "risk_manager.py")
        spec = importlib.util.spec_from_file_location("sp_risk_roi", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        from datetime import date

        day = date(2026, 10, 27)  # non-skip weekday in calendar.json
        ok, why = mod.check_can_trade(day, 444.37, 0, 0)
        self.assertFalse(ok)
        self.assertIn("drawdown", why.lower())
        ok2, _ = mod.check_can_trade(day, 500.0, 0, 0)
        self.assertTrue(ok2)

    def test_inx_configs_rescue_limits(self):
        for folder in ("kalshi-sp500-paper", "kalshi-sized-paper"):
            with open(os.path.join(ROOT, folder, "config.json"), encoding="utf-8") as handle:
                cfg = json.load(handle)
            self.assertEqual(cfg["max_trades_per_day"], 1)
            self.assertEqual(cfg["daily_loss_limit"], 25.0)
            self.assertEqual(cfg["drawdown_halt_bankroll"], 460.0)

    def test_firm_roi_rescue_flags_overnight_board(self):
        rescue = desk_master.firm_roi_rescue(
            [
                {"id": "memecoin", "today": -10.58, "cash": 7.01},
                {"id": "kalshi-sp", "cash": 444.37, "realized": -55.63},
                {"id": "sports-gap", "today": -16.25, "cash": 83.75},
                {"id": "commodity-15m", "today": 0, "cash": 100},
            ]
        )
        bots = {f["bot"] for f in rescue["flags"]}
        self.assertIn("memecoin", bots)
        self.assertIn("kalshi-sp", bots)
        self.assertIn("sports-gap", bots)
        self.assertNotIn("commodity-15m", bots)
        self.assertTrue(rescue["paper_only"])

    def test_meme_policy_on_master_board(self):
        bleed = desk_master.meme_stopbleed_measure({"id": "memecoin", "today": -10.58, "history": []})
        self.assertTrue(bleed["red_day_locked"])
        self.assertEqual(bleed["policy"]["stop_pct"], -12)
        self.assertEqual(bleed["policy"]["red_day_entry_lock_usd"], 8.0)


if __name__ == "__main__":
    unittest.main()
