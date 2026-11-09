"""Sized Kalshi: twin/anti-double day-skips densify ticker+side+edge (no buys)."""
from __future__ import annotations

import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
BOT = os.path.join(HERE, "kalshi-sized-paper", "bot.py")
CFG = os.path.join(HERE, "kalshi-sized-paper", "config.json")


class KalshiSizedSkipHonesty(unittest.TestCase):
    def test_twin_veto_densify_keeps_ticker_side_edge(self):
        with open(BOT, encoding="utf-8") as handle:
            src = handle.read()
        self.assertIn("anti_double_blocks(", src)
        self.assertIn("twin_edge_blocks(", src)
        self.assertIn("def _remember_veto(", src)
        self.assertIn("last_skip_ticker", src)
        self.assertIn("last_skip_side", src)
        self.assertIn("last_skip_edge", src)
        # Final no-pick densify must pass veto metadata — not bare reason.
        self.assertIn("ticker=last_skip_ticker", src)
        self.assertIn("side=last_skip_side", src)
        self.assertIn("edge=densify_edge", src)
        # No-event skip must learn + densify (skip honesty).
        self.assertIn('logger.learn(f"{day}: no trade - {reason}", "skip")', src)

    def test_config_stays_protective_idle_not_volume(self):
        with open(CFG, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("protective idle twin", text)
        self.assertIn('"max_trades_per_day": 1', text)
        self.assertNotIn("up to 3 sized fills", text)
        self.assertIn('"paper_mode": true', text)


if __name__ == "__main__":
    unittest.main()
