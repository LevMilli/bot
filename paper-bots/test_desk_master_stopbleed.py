"""Masters stop-bleed + tip alarms + scoreboard stub. No network."""

import importlib.util
import os
import unittest
from datetime import datetime, timedelta, timezone

import desk_master


ROOT = os.path.dirname(os.path.abspath(__file__))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class StopBleedTests(unittest.TestCase):
    def test_meme_exit_and_lock_constants(self):
        cfg = _load("meme_cfg", os.path.join(ROOT, "memecoin-paper", "config.py"))
        self.assertEqual(cfg.EXIT["stop_pct"], -12)
        self.assertEqual(cfg.EXIT["model_flip_momentum_h1_floor"], -6)
        self.assertEqual(cfg.RED_DAY_ENTRY_LOCK_USD, 8)
        self.assertEqual(cfg.MAX_OPEN_RED, 1)
        self.assertTrue(cfg.SPEED_ONLY_IF_TODAY_NONNEG)
        self.assertEqual(cfg.SPEED_MIN_LIQUIDITY_USD, 50000)
        self.assertEqual(cfg.SCORER["momentum_h1_too_hot"], 80)
        self.assertEqual(cfg.SCORER["min_txns_h1"], 100)

    def test_sports_tip_alarm_bands(self):
        gap = _load("gap_bot_alarms", os.path.join(ROOT, "sports-gap-paper", "gap_bot.py"))
        now = datetime.now(timezone.utc)
        g5 = {"date": (now + timedelta(minutes=4)).isoformat().replace("+00:00", "Z"), "state": "pre"}
        g15 = {"date": (now + timedelta(minutes=12)).isoformat().replace("+00:00", "Z"), "state": "pre"}
        g60 = {"date": (now + timedelta(minutes=60)).isoformat().replace("+00:00", "Z"), "state": "pre"}
        self.assertEqual(gap.tip_alarm_band(g5), 5)
        self.assertEqual(gap.tip_alarm_band(g15), 15)
        self.assertIsNone(gap.tip_alarm_band(g60))

    def test_desk_master_self_check(self):
        desk_master.self_check()

    def test_master_summary_on_empty_bots(self):
        s = desk_master.master_summary(bots=[], cfg={"max_open_risk": 100})
        self.assertEqual(s["version"], 1)
        self.assertTrue(s["paper_only"])
        self.assertEqual(s["towers"], [])


if __name__ == "__main__":
    unittest.main()
