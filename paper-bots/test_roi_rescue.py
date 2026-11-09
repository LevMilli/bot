"""Overnight ROI rescue: stop bleed, starve losers, keep fee floors."""

import json
import os
import unittest

import desk_master
import desk_more

ROOT = os.path.dirname(os.path.abspath(__file__))


class RoiRescueTests(unittest.TestCase):
    def test_meme_red_lock_fires_at_minus_five(self):
        shares = desk_more.effective_tower_shares(meme_today=-10.58)
        self.assertAlmostEqual(shares["memecoin"], desk_more.MEME_RED_SHARE)
        self.assertEqual(desk_more.MEME_RED_LOCK_USD, 5.0)
        soft = desk_more.effective_tower_shares(meme_today=-4)
        base = desk_more.DEFAULT_TOWER_BUDGET_SHARE["memecoin"]
        self.assertAlmostEqual(soft["memecoin"], base)
        locked = desk_more.effective_tower_shares(meme_today=-5)
        self.assertAlmostEqual(locked["memecoin"], desk_more.MEME_RED_SHARE)

    def test_inx_drawdown_halt(self):
        import importlib.util

        path = os.path.join(ROOT, "kalshi-sp500-paper", "risk_manager.py")
        spec = importlib.util.spec_from_file_location("sp_risk_roi", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        from datetime import date

        day = date(2026, 10, 27)  # non-skip weekday in calendar.json
        dd_on = dict(mod.CFG)
        dd_on["staff_clear_drawdown_halt"] = False
        ok, why = mod.check_can_trade(day, 444.37, 0, 0, cfg=dd_on)
        self.assertFalse(ok)
        self.assertIn("drawdown", why.lower())
        ok2, _ = mod.check_can_trade(day, 500.0, 0, 0, cfg=dd_on)
        self.assertTrue(ok2)
        # Staff clear resumes buys under the soft bar; kill switch stays stone.
        dd_clear = dict(mod.CFG)
        dd_clear["staff_clear_drawdown_halt"] = True
        ok3, _ = mod.check_can_trade(day, 444.37, 0, 0, cfg=dd_clear)
        self.assertTrue(ok3)
        ok_kill, why_kill = mod.check_can_trade(day, 399.0, 0, 0, cfg=dd_clear)
        self.assertFalse(ok_kill)
        self.assertIn("kill", why_kill.lower())

    def test_inx_configs_rescue_limits(self):
        for folder in ("kalshi-sp500-paper", "kalshi-sized-paper"):
            with open(os.path.join(ROOT, folder, "config.json"), encoding="utf-8") as handle:
                cfg = json.load(handle)
            self.assertEqual(cfg["max_trades_per_day"], 1)
            self.assertEqual(cfg["daily_loss_limit"], 25.0)
            self.assertEqual(cfg["drawdown_halt_bankroll"], 460.0)
            self.assertEqual(cfg["kill_switch_bankroll"], 400.0)
        with open(os.path.join(ROOT, "kalshi-sp500-paper", "config.json"), encoding="utf-8") as handle:
            sp = json.load(handle)
        self.assertTrue(sp.get("staff_clear_drawdown_halt"))
        with open(os.path.join(ROOT, "kalshi-sized-paper", "config.json"), encoding="utf-8") as handle:
            sized = json.load(handle)
        self.assertTrue(sized.get("staff_clear_drawdown_halt"))

    def test_firm_roi_rescue_flags_overnight_board(self):
        # Force soft-DD still on so board keeps entries_off (ignore live staff clear).
        rescue = desk_master.firm_roi_rescue(
            [
                {"id": "memecoin", "today": -10.58, "cash": 7.01},
                {"id": "kalshi-sp", "cash": 444.37, "realized": -55.63},
                {"id": "sports-gap", "today": -16.25, "cash": 83.75},
                {"id": "commodity-15m", "today": 0, "cash": 100},
            ],
            cfg={"staff_clear_drawdown_halt": False},
        )
        bots = {f["bot"] for f in rescue["flags"]}
        self.assertIn("memecoin", bots)
        self.assertIn("kalshi-sp", bots)
        self.assertIn("sports-gap", bots)
        self.assertNotIn("commodity-15m", bots)
        self.assertTrue(rescue["paper_only"])
        sp = next(f for f in rescue["flags"] if f["bot"] == "kalshi-sp")
        self.assertEqual(sp["action"], "entries_off")

    def test_firm_roi_rescue_honors_staff_clear_soft_dd(self):
        """Staff approval: soft $460 catch-22 cleared; kill/fees/bands stay stone."""
        rescue = desk_master.firm_roi_rescue(
            [
                {"id": "kalshi-sp", "cash": 444.37, "realized": -10.0},
                {"id": "kalshi-sized", "cash": 444.0},
            ],
            cfg={"staff_clear_drawdown_halt": True},
            root=ROOT,
        )
        sp_flags = [f for f in rescue["flags"] if f["bot"] == "kalshi-sp"]
        self.assertTrue(any(f["action"] == "staff_cleared_soft_dd" for f in sp_flags))
        self.assertFalse(any(f["action"] == "entries_off" for f in sp_flags))
        self.assertIn("stone", sp_flags[0]["why"].lower())
        # Shared staff_clear_drawdown_halt also clears the sized twin (risk_manager key).
        sized = next(f for f in rescue["flags"] if f["bot"] == "kalshi-sized")
        self.assertEqual(sized["action"], "staff_cleared_soft_dd")
        # Explicit sized false still keeps the twin entries_off.
        split = desk_master.firm_roi_rescue(
            [
                {"id": "kalshi-sp", "cash": 444.37},
                {"id": "kalshi-sized", "cash": 444.0},
            ],
            cfg={
                "staff_clear_drawdown_halt": True,
                "staff_clear_sized_drawdown_halt": False,
            },
            root=ROOT,
        )
        sized_off = next(f for f in split["flags"] if f["bot"] == "kalshi-sized")
        self.assertEqual(sized_off["action"], "entries_off")
        sp_on = next(f for f in split["flags"] if f["bot"] == "kalshi-sp")
        self.assertEqual(sp_on["action"], "staff_cleared_soft_dd")
    def test_sports_red_rescue_uses_sticky_realized(self):
        # today flat, sticky realized −16.62 → still red-rescue.
        rescue = desk_master.firm_roi_rescue(
            [{"id": "sports-gap", "today": 0.0, "realized": -16.62, "cash": 83.38}]
        )
        sports = [f for f in rescue["flags"] if f["bot"] == "sports-gap"]
        self.assertEqual(len(sports), 1)
        self.assertIn("realized", sports[0]["why"])
        shares = desk_more.effective_tower_shares(
            today_by_bot={"sports-gap": 0.0},
            realized_by_bot={"sports-gap": -16.62},
        )
        self.assertAlmostEqual(shares["sports-gap"], desk_more.SPORTS_RED_SHARE)

    def test_meme_policy_on_master_board(self):
        bleed = desk_master.meme_stopbleed_measure({"id": "memecoin", "today": -10.58, "history": []})
        self.assertTrue(bleed["red_day_locked"])
        self.assertEqual(bleed["policy"]["stop_pct"], -12)
        self.assertEqual(bleed["policy"]["red_day_entry_lock_usd"], 5.0)


if __name__ == "__main__":
    unittest.main()
