"""Phase 4 per-league CLV board — beat-close ≥52% once n≥10."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_master
import desk_more
import desk_roi_plan


class ClvLeagues(unittest.TestCase):
    def test_by_league_pass_and_thin(self):
        with tempfile.TemporaryDirectory() as tmp:
            # NFL: 10 rows, 6 beats → 60% pass
            for i in range(10):
                desk_more.record_sports_clv(
                    tmp,
                    ticker=f"NFL-{i}",
                    side="home",
                    fair_entry=0.80 if i < 6 else 0.60,
                    close_fair=0.70,
                    pnl=1.0 if i < 6 else -1.0,
                    league="NFL",
                )
            # NHL: only 3 rows → thin
            for i in range(3):
                desk_more.record_sports_clv(
                    tmp,
                    ticker=f"NHL-{i}",
                    side="home",
                    fair_entry=0.75,
                    close_fair=0.70,
                    pnl=1.0,
                    league="NHL",
                )
            board = desk_more.clv_by_league(tmp)
            by = {r["league"]: r for r in board["leagues"]}
            self.assertIn("NFL", by)
            self.assertFalse(by["NFL"]["thin"])
            self.assertTrue(by["NFL"]["pass"])
            self.assertAlmostEqual(by["NFL"]["beat_close_rate"], 0.6, places=2)
            self.assertTrue(by["NHL"]["thin"])
            self.assertFalse(by["NHL"]["pass"])
            self.assertGreaterEqual(board["pass_n"], 1)
            self.assertFalse(board["board_chip"])

    def test_summary_embeds_by_league(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_more.record_sports_clv(
                tmp, ticker="T", side="home",
                fair_entry=0.8, close_fair=0.7, league="NBA",
            )
            summary = desk_more.clv_summary(tmp)
            self.assertIn("by_league", summary)
            self.assertEqual(summary["n"], 1)

    def test_master_and_calib_observe(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(10):
                desk_more.record_sports_clv(
                    tmp,
                    ticker=f"NBA-{i}",
                    side="home",
                    fair_entry=0.80,
                    close_fair=0.70,
                    league="NBA",
                )
            summary = desk_master.master_summary(
                tmp,
                bots=[{"id": "sports-gap", "open_risk": 0, "history": [], "gate_a": {}}],
                cfg={"max_open_risk": 100},
            )
            plan = summary.get("roi_plan") or {}
            self.assertIn("clv_leagues", plan)
            self.assertTrue(plan.get("fee_floors_locked"))
            obs = desk_roi_plan.calib_clv_observe(tmp, bots=[])
            self.assertIn("clv_leagues", obs)

    def test_fee_floors_untouched(self):
        import desk_profit
        floors = desk_profit.venue_floors_locked()
        self.assertAlmostEqual(floors["venues"]["kalshi_sports"]["floor"], 0.06)


if __name__ == "__main__":
    unittest.main()
