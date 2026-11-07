"""E2 exit-quality observe + selective throughput after M1."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_roi_plan


class ExitQualityObserve(unittest.TestCase):
    def test_sports_exit_kinds(self):
        bots = [{
            "id": "sports-gap",
            "closed": [
                {"league": "NFL", "exit": "gap closed - sold at bid", "pnl": 2.0},
                {"league": "NFL", "exit": "model-flip fair Δ≥0.08", "pnl": -1.0},
                {"league": "NBA", "exit": "scale-out +8¢ fair (full)", "pnl": 1.5},
                {"league": "NBA", "exit": "settled", "pnl": 0.5},
                {"league": "NHL", "exit": "gap-decay exit", "pnl": -0.2},
            ],
            "open": [],
        }]
        board = desk_roi_plan.sports_exit_quality_board(bots, min_n=1)
        self.assertEqual(board["n"], 5)
        keys = {r["key"] for r in board["by_kind"]}
        self.assertIn("gap_close", keys)
        self.assertIn("model_flip", keys)
        self.assertIn("scale_out", keys)
        self.assertIn("settle", keys)
        self.assertIn("gap_decay", keys)

    def test_btc_commodity_exit_kinds(self):
        bots = [
            {
                "id": "btc15m",
                "closed": [
                    {"exit": "take-profit bid", "pnl": 1.2},
                    {"exit": "model-flip", "pnl": -0.4},
                    {"exit": "settled", "pnl": 0.3},
                ],
            },
            {
                "id": "commodity-15m",
                "closed": [
                    {"exit_reason": "model-flip fair", "pnl": 0.8},
                    {"reason": "settled", "pnl": -0.1},
                ],
            },
        ]
        board = desk_roi_plan.fee_clear_exit_quality_board(bots, min_n=1)
        self.assertEqual(board["n"], 5)
        keys = {r["key"] for r in board["by_kind"]}
        self.assertIn("take_profit", keys)
        self.assertIn("model_flip", keys)
        self.assertIn("settle", keys)
        bot_ids = {r["key"] for r in board["by_bot"]}
        self.assertEqual(bot_ids, {"btc15m", "commodity-15m"})

    def test_selective_after_m1(self):
        bots = [
            {
                "id": "btc15m",
                "today": 1.0,
                "history": [{"pnl": 1.0, "contracts": 1} for _ in range(12)],
            },
            {
                "id": "sports-gap",
                "today": -2.0,
                "history": [{"pnl": 0.5, "contracts": 1} for _ in range(12)],
            },
            {"id": "memecoin", "today": 5.0, "history": []},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            sel = desk_roi_plan.selective_throughput_observe(tmp, bots=bots)
            self.assertTrue(sel["m1_holds"])
            self.assertTrue(sel["after_m1"])
            ids = {t["bot"] for t in sel["towers"]}
            self.assertIn("btc15m", ids)
            self.assertNotIn("memecoin", ids)
            btc = next(t for t in sel["towers"] if t["bot"] == "btc15m")
            self.assertTrue(btc["boosted"])
            sports = next(t for t in sel["towers"] if t["bot"] == "sports-gap")
            self.assertFalse(sports["boosted"])  # red day

    def test_combined_observe(self):
        bots = [{
            "id": "sports-gap",
            "open": [{"ticker": "T1", "exit_plan": {"kind": "gap_decay"}}],
            "closed": [{"league": "NFL", "exit": "settled", "pnl": 1.0}],
            "history": [{"pnl": 1.0, "contracts": 1} for _ in range(12)],
            "today": 0.5,
        }]
        with tempfile.TemporaryDirectory() as tmp:
            out = desk_roi_plan.exit_quality_observe(tmp, bots=bots)
            self.assertTrue(out["observe_only"])
            self.assertFalse(out["live_orders_enabled"])
            self.assertTrue(out["fee_floors_locked"])
            self.assertIn("exit_plan_coverage", out)
            self.assertIn("hard_stop_shadow", out)
            self.assertIn("selective_throughput", out)
            plan = desk_roi_plan.plan_summary(tmp, bots=bots)
            self.assertIn("exit_quality", plan)
            self.assertIn("selective_throughput", plan)

    def test_fee_floors(self):
        import desk_profit
        floors = desk_profit.venue_floors_locked()
        self.assertTrue(floors["locked"])
        self.assertAlmostEqual(floors["venues"]["kalshi_sports"]["floor"], 0.06)


if __name__ == "__main__":
    unittest.main()
