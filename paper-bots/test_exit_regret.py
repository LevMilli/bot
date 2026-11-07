"""E2 exit-regret KPIs — settle losers with shadow; BTC TP giveback; INX flip save."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_master
import desk_roi_plan


class ExitRegret(unittest.TestCase):
    def test_sports_shadow_share_on_settle_losers(self):
        bots = [{
            "id": "sports-gap",
            "closed": [
                {
                    "exit": "settled", "pnl": -5.0,
                    "hard_stop_shadowed": True,
                },
                {
                    "exit": "settled", "pnl": -2.0,
                    "time_final_shadowed": True,
                },
                {"exit": "settled", "pnl": -1.0},  # no shadow
                {"exit": "settled", "pnl": 3.0, "hard_stop_shadowed": True},  # winner
                {"exit": "gap closed - sold at bid", "pnl": -0.5},
            ],
        }]
        out = desk_roi_plan.exit_regret_observe(None, bots=bots)
        self.assertEqual(out["sports_settle_losers"], 3)
        self.assertEqual(out["sports_settle_losers_with_shadow"], 2)
        self.assertAlmostEqual(out["sports_shadow_share"], 2 / 3, places=4)
        self.assertFalse(out["board_chip"])

    def test_btc_tp_giveback(self):
        bots = [{
            "id": "btc15m",
            "closed": [
                {
                    "exit": "settled", "pnl": -4.0,
                    "take_profit": 0.80, "exit_price": 0.0, "contracts": 10,
                    "payout": 0.0,
                },
                {
                    "exit": "take-profit", "pnl": 1.5,
                    "take_profit": 0.80, "exit_price": 0.80,
                },
            ],
        }]
        out = desk_roi_plan.exit_regret_observe(None, bots=bots)
        self.assertEqual(out["btc_settle_n"], 1)
        self.assertEqual(out["btc_tp_giveback_n"], 1)
        self.assertAlmostEqual(out["btc_tp_giveback_avg"], 0.80, places=2)

    def test_inx_flip_save(self):
        bots = [{
            "id": "kalshi-sp",
            "closed": [
                {
                    "exit": "model-flip bid under 50c",
                    "pnl": -2.0, "cost": 10.0,
                },
            ],
        }]
        out = desk_roi_plan.exit_regret_observe(None, bots=bots)
        self.assertEqual(out["inx_flip_n"], 1)
        # save = pnl + cost = 8
        self.assertAlmostEqual(out["inx_flip_save_usd"], 8.0, places=2)

    def test_meme_histogram(self):
        bots = [{
            "id": "memecoin",
            "closed": [
                {"exit": "stop", "pnl": -3.0},
                {"exit": "stop", "pnl": -1.0},
                {"exit": "trail", "pnl": 2.0},
            ],
        }]
        out = desk_roi_plan.exit_regret_observe(None, bots=bots)
        total = sum(int(r["n"]) for r in out["meme_exit_histogram"])
        self.assertEqual(total, 3)
        self.assertTrue(out["meme_exit_histogram"])

    def test_wired_into_exit_quality_and_master(self):
        bots = [{
            "id": "sports-gap",
            "open_risk": 0, "history": [], "gate_a": {},
            "closed": [
                {"exit": "settled", "pnl": -4.0, "hard_stop_shadowed": True},
            ],
        }]
        with tempfile.TemporaryDirectory() as tmp:
            eq = desk_roi_plan.exit_quality_observe(tmp, bots=bots)
            self.assertIn("exit_regret", eq)
            self.assertEqual(eq["exit_regret"]["sports_settle_losers_with_shadow"], 1)
            summary = desk_master.master_summary(
                tmp, bots=bots, cfg={"max_open_risk": 100},
            )
            plan = summary.get("roi_plan") or {}
            self.assertIn("exit_regret", plan)
            self.assertTrue(plan.get("fee_floors_locked"))

    def test_fee_floors_untouched(self):
        import desk_profit
        floors = desk_profit.venue_floors_locked()
        self.assertAlmostEqual(floors["venues"]["kalshi_sports"]["floor"], 0.06)


if __name__ == "__main__":
    unittest.main()
