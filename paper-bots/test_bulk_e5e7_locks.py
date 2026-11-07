"""Bulk E5–E7 lock tests: 451 near-miss edge=0, 452 skip-regret never EDGE,
456 selective never meme/INX, plus insight ratio board smoke."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_living
import desk_master
import desk_more
import desk_roi_e5e7
import desk_roi_plan
import desk_top25


class NearMissEdgeRelaxLock451(unittest.TestCase):
    def test_edge_relax_forever_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            relax = desk_roi_plan.effective_near_miss_relax(tmp)
            self.assertEqual(relax["edge_relax"], 0.0)
            lock = desk_roi_e5e7.near_miss_edge_relax_forever_zero(tmp)
            self.assertTrue(lock["ok"])
            self.assertEqual(lock["edge_relax"], 0.0)
            self.assertTrue(lock["fee_floors_locked"])
            # Soft allowlist never includes edge.
            self.assertNotIn("edge", lock["soft_allow"])


class SkipRegretNeverEdge452(unittest.TestCase):
    def test_candidates_reject_edge_floor(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(4):
                desk_top25.record_skip_regret(
                    tmp, bot="btc15m", ticker=f"Z{i}", soft_gate="z", would_pnl=0.3,
                )
                desk_top25.record_skip_regret(
                    tmp, bot="btc15m", ticker=f"E{i}", soft_gate="edge", would_pnl=1.0,
                )
                desk_top25.record_skip_regret(
                    tmp, bot="btc15m", ticker=f"F{i}", soft_gate="min_edge", would_pnl=0.8,
                )
                desk_top25.record_skip_regret(
                    tmp, bot="sports-gap", ticker=f"N{i}", soft_gate="news", would_pnl=0.2,
                )
            cands = desk_roi_plan.skip_regret_candidates(tmp)
            softs = {c["soft"] for c in cands["candidates"]}
            self.assertIn("z", softs)
            self.assertIn("news", softs)
            self.assertNotIn("edge", softs)
            self.assertNotIn("min_edge", softs)
            lock = desk_roi_e5e7.skip_regret_never_edge_floor(tmp)
            self.assertTrue(lock["ok"])
            self.assertEqual(lock["edge_leaks"], [])
            self.assertTrue(lock["fee_floors_locked"])
            # Fee gates set includes edge forever.
            self.assertIn("edge", desk_roi_plan.SKIP_REGRET_FEE_GATES)


class SelectiveNeverMemeInx456(unittest.TestCase):
    def test_selective_never_expands_losers(self):
        self.assertEqual(
            desk_more.selective_max_buys("memecoin", base=2, today=50.0), 2,
        )
        self.assertEqual(
            desk_more.selective_max_buys("kalshi-sp", base=1, today=50.0), 1,
        )
        self.assertEqual(
            desk_more.selective_max_buys("kalshi-sized", base=1, today=50.0), 1,
        )
        # Fee-clear still may +1 on green.
        self.assertEqual(
            desk_more.selective_max_buys("btc15m", base=3, today=1.0), 4,
        )
        lock = desk_roi_e5e7.selective_never_expands_meme_inx()
        self.assertTrue(lock["ok"])
        self.assertTrue(lock["fee_floors_locked"])
        for row in lock["checks"]:
            if row["bot"] in ("memecoin", "kalshi-sp", "kalshi-sized"):
                self.assertFalse(row["expands"])
                self.assertTrue(row["ok"])


class InsightBettingRatioBoard(unittest.TestCase):
    def test_ratio_board_smoke(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = desk_roi_e5e7.insight_betting_ratio_board(tmp, bots=[])
            self.assertTrue(board["paper_only"])
            self.assertTrue(board["fee_floors_locked"])
            self.assertTrue(board["observe_only"])
            self.assertEqual(board["min_ratio"], desk_living.INSIGHT_BETTING_MIN_RATIO)
            self.assertEqual(board["target_ratio"], 3.0)
            self.assertIn("ratio", board)
            self.assertIn("label", board)
            # Re-export path.
            via = desk_roi_plan.insight_betting_ratio_board(tmp, bots=[])
            self.assertEqual(via["min_ratio"], board["min_ratio"])

    def test_master_wires_e5e7_boards(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = desk_master.master_summary(
                tmp,
                bots=[{"id": "btc15m", "open_risk": 0, "history": [], "gate_a": {}}],
                cfg={"max_open_risk": 100},
            )
            plan = summary.get("roi_plan") or {}
            self.assertIn("insight_betting_ratio", plan)
            self.assertIn("weekly_eligible_fill", plan)
            self.assertIn("edge08_vs_main", plan)
            self.assertIn("fee_clear_cadence", plan)
            ratio = plan["insight_betting_ratio"]
            self.assertIsInstance(ratio, dict)
            self.assertTrue(ratio.get("fee_floors_locked"))


class WeeklyEligibleAndCadenceSmoke(unittest.TestCase):
    def test_weekly_eligible_and_cadence(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_living.record_completion(
                tmp, bot="btc15m", ticker="KXBTC", pnl=0.5, eligible=True,
            )
            desk_living.record_completion(
                tmp, bot="memecoin", ticker="M", pnl=-0.2, eligible=True,
            )
            funnel = desk_roi_e5e7.weekly_eligible_fill_report(tmp, bots=[])
            self.assertGreaterEqual(funnel["all_completions"], 2)
            self.assertEqual(funnel["eligible_completions"], 1)  # meme not fee-clear
            self.assertTrue(funnel["observe_only"])
            cadence = desk_roi_e5e7.fee_clear_cadence_health_board(tmp, bots=[])
            targets = cadence["cadence_targets"]
            self.assertEqual(targets["btc15m"], 60)
            self.assertEqual(targets["commodity-15m"], 90)
            self.assertEqual(targets["sports-gap"], 180)
            edge = desk_roi_e5e7.edge08_vs_main_expectancy_board(tmp, bots=[])
            self.assertEqual(edge["main_venue_edge"], 0.05)
            self.assertEqual(edge["shadow_venue_edge"], 0.08)
            self.assertTrue(edge["observe_only"])


if __name__ == "__main__":
    unittest.main()
