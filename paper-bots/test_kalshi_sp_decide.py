"""Kalshi S&P Decide: 0.02 floor, learning skip, adapt shrinks $25, BTC veto stays."""
from __future__ import annotations

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SP = os.path.join(HERE, "kalshi-sp500-paper")
if HERE not in sys.path:
    sys.path.insert(0, HERE)
if SP not in sys.path:
    sys.path.insert(0, SP)

import desk_inx
import desk_profit
import risk_manager

CALM = {"cushion": 100, "sigma": 40, "spread": 0.01, "minutes_left": 12, "ask": 0.85}
HOT = {"cushion": 10, "sigma": 80, "spread": 0.05, "minutes_left": 2, "ask": 0.50}


def _strong_history():
    wins = [{"pnl": 5, "closed": "2026-11-01T12:00:00Z"}] * 25
    losses = [{"pnl": -1, "closed": "2026-11-01T13:00:00Z"}] * 3
    return wins + losses


class KalshiSpDecide(unittest.TestCase):
    def test_adapt_shrinks_and_does_not_raise_the_cap(self):
        shrunk, safe = risk_manager.capped_adapt_stake(25.0, history=[], vol_kwargs=HOT)
        self.assertLess(shrunk, 25.0)
        self.assertTrue(safe["capped"])
        raised, big = risk_manager.capped_adapt_stake(
            25.0, history=_strong_history(), vol_kwargs=CALM,
        )
        self.assertEqual(raised, 25.0)
        self.assertTrue(big["play_big"])
        self.assertTrue(any("capped" in note for note in big["notes"]))
        self.assertEqual(risk_manager.CFG["max_trades_per_day"], 1)
        self.assertEqual(risk_manager.CFG["daily_loss_limit"], 25.0)
        self.assertEqual(risk_manager.CFG["max_stake_dollars"], 25.0)

    def test_learning_skip_and_btc_veto_stay(self):
        class Desk:
            def load_learning(self, root):
                return []

            def prob_bucket(self, value):
                return "0.8-0.9"

            def learning_skip(self, rows, market, bucket, side=None, hour_ct=None):
                return f"Skipping {market} in the {bucket} probability bucket."

            def correlation_blocks(self, root, bot_id, side, edge):
                return ""

        reason = desk_inx.inx_learn_corr_reason(
            Desk(), None, market="S&P", bot_id="kalshi-sp",
            pick={"ask": 0.85, "side": "yes"}, edge=0.04, hour_ct=13,
        )
        self.assertIn("S&P", reason)
        self.assertIn("0.8-0.9", reason)
        veto = desk_profit.correlation_veto_reason(
            "kalshi-sp", "yes", 0.03,
            [{"bot": "btc15m", "factor": "risk_on_btc", "edge": 0.05}],
        )
        self.assertIn("correlation veto", veto)
        self.assertIn("btc15m", veto)
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_inx"], 0.02)


if __name__ == "__main__":
    unittest.main()
