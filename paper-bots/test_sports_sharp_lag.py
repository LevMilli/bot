"""Sports Sharp Lag shadow tower — fee floor + lag math. No network."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_profit
import pimp_desk


def _bot():
    path = os.path.join(HERE, "sports-sharp-lag-paper", "bot.py")
    spec = importlib.util.spec_from_file_location("sports_sharp_lag_bot", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class SportsSharpLag(unittest.TestCase):
    def test_floor_locked_to_sports(self):
        bot = _bot()
        cfg = bot.locked_cfg({"venue_min_edge": 0.01})
        self.assertGreaterEqual(cfg["venue_min_edge"], 0.06)
        self.assertEqual(desk_profit.bot_venue_edge("sports-sharp-lag"), 0.06)
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_sports"], 0.06)

    def test_lag_clears_and_thin_skips(self):
        bot = _bot()
        buy = bot.lag_decision({"game": "A@B", "sharp_fair": 0.62, "ask": 0.52})
        self.assertEqual(buy["action"], "buy")
        self.assertGreaterEqual(buy["edge"], 0.06 - 1e-9)
        thin = bot.lag_decision({"game": "C@D", "sharp_fair": 0.55, "ask": 0.52})
        self.assertEqual(thin["action"], "skip")
        self.assertIn("lag edge", thin["reason"])

    def test_run_buys_clear_lag_waits_without_quotes(self):
        bot = _bot()
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "sports-sharp-lag-paper"))
            import io
            from contextlib import redirect_stdout
            buf = io.StringIO()
            with redirect_stdout(buf):
                bot.run_once(desk_root=tmp, quotes=[])
            self.assertIn("waiting on sharp", buf.getvalue().lower())
            buf = io.StringIO()
            with redirect_stdout(buf):
                bot.run_once(
                    desk_root=tmp,
                    quotes=[{"game": "NYG@PHI", "sharp_fair": 0.62, "ask": 0.52}],
                )
            out = buf.getvalue()
            self.assertIn("BUY NYG@PHI", out)
            state = json.load(open(
                os.path.join(tmp, "sports-sharp-lag-paper", "paper_account.json"),
                encoding="utf-8",
            ))
            self.assertEqual(len(state["open"]), 1)
            self.assertTrue(state["shadow_only"])
            self.assertAlmostEqual(state["cash"], 475.0, places=2)

    def test_desk_registers_shadow(self):
        spec = next(b for b in pimp_desk.BOTS if b["id"] == "sports-sharp-lag")
        self.assertTrue(spec.get("shadow_only"))
        self.assertNotIn(
            "sports-sharp-lag",
            pimp_desk.DEFAULTS.get("tower_risk_budgets") or {},
        )
        self.assertEqual(pimp_desk.BOT_PLANS["sports-sharp-lag"]["exit_quality"], "partial")


if __name__ == "__main__":
    unittest.main()
