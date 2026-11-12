"""Fed Watch shadow tower — econ floor + FedWatch lag math. No network."""
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
from desk_roi_e4 import incubation_idea_bank_only


def _bot():
    path = os.path.join(HERE, "fed-watch-paper", "bot.py")
    spec = importlib.util.spec_from_file_location("fed_watch_bot", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class FedWatch(unittest.TestCase):
    def test_floor_locked_to_econ(self):
        bot = _bot()
        cfg = bot.locked_cfg({"venue_min_edge": 0.01})
        self.assertGreaterEqual(cfg["venue_min_edge"], 0.05)
        self.assertEqual(desk_profit.bot_venue_edge("fed-watch"), 0.05)
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_econ"], 0.05)
        self.assertEqual(pimp_desk.DEFAULTS["venue_min_edge"]["kalshi_econ"], 0.05)

    def test_fed_clears_and_thin_skips(self):
        bot = _bot()
        buy = bot.fed_decision({"outcome": "hold", "fedwatch_fair": 0.62, "ask": 0.52})
        self.assertEqual(buy["action"], "buy")
        self.assertGreaterEqual(buy["edge"], 0.05 - 1e-9)
        thin = bot.fed_decision({"outcome": "cut25", "fedwatch_fair": 0.55, "ask": 0.52})
        self.assertEqual(thin["action"], "skip")
        self.assertIn("fed edge", thin["reason"])

    def test_run_buys_clear_waits_without_quotes(self):
        bot = _bot()
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "fed-watch-paper"))
            import io
            from contextlib import redirect_stdout
            buf = io.StringIO()
            with redirect_stdout(buf):
                bot.run_once(desk_root=tmp, quotes=[])
            self.assertIn("waiting on fed quotes", buf.getvalue().lower())
            buf = io.StringIO()
            with redirect_stdout(buf):
                bot.run_once(
                    desk_root=tmp,
                    quotes=[{"outcome": "hold", "fedwatch_fair": 0.62, "ask": 0.52}],
                )
            out = buf.getvalue()
            self.assertIn("BUY hold", out)
            with open(
                os.path.join(tmp, "fed-watch-paper", "paper_account.json"),
                encoding="utf-8",
            ) as handle:
                state = json.load(handle)
            self.assertEqual(len(state["open"]), 1)
            self.assertTrue(state["shadow_only"])
            self.assertTrue(state["idea_bank_only"])
            # 46 whole contracts at 0.52 + 0.02 fee = $24.84.
            self.assertEqual(state["open"][0]["contracts"], 46)
            self.assertAlmostEqual(state["cash"], 475.16, places=2)

    def test_harvest_from_bins_writes_quotes(self):
        bot = _bot()
        with tempfile.TemporaryDirectory() as tmp:
            out = bot.harvest_from_bins(
                tmp,
                [{
                    "outcome": "hold",
                    "meeting": "2026-12",
                    "fedwatch_fair": 0.58,
                    "ask": 0.50,
                    "ticker": "KXFED-HOLD",
                }],
            )
            self.assertTrue(out["ok"])
            self.assertEqual(out["n"], 1)
            path = os.path.join(tmp, "fed-watch-paper", "fedwatch_quotes.json")
            self.assertTrue(os.path.isfile(path))
            thin = bot.quotes_from_bins([{"outcome": "cut", "ask": 0.5}])
            self.assertEqual(thin, [])

    def test_harvest_live_waits_without_bins(self):
        bot = _bot()
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "fed-watch-paper"))
            out = bot.harvest_live(tmp)
            self.assertTrue(out["ok"])
            self.assertEqual(out["n"], 0)
            self.assertIn("waiting", out.get("reason", "").lower())

    def test_desk_registers_shadow_idea_bank(self):
        spec = next(b for b in pimp_desk.BOTS if b["id"] == "fed-watch")
        self.assertTrue(spec.get("shadow_only"))
        self.assertNotIn(
            "fed-watch",
            pimp_desk.DEFAULTS.get("tower_risk_budgets") or {},
        )
        self.assertEqual(pimp_desk.BOT_PLANS["fed-watch"]["exit_quality"], "partial")
        self.assertTrue(incubation_idea_bank_only("KXFED"))
        self.assertTrue(incubation_idea_bank_only("econ"))


if __name__ == "__main__":
    unittest.main()
