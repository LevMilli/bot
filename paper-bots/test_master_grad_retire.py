"""Master graduation checklist + meme 20d retirement clock."""
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


def _all_pass_row(bot: str = "sports-gap") -> dict:
    return {
        "bot": bot,
        "passing": {c: True for c in desk_roi_plan.GRADUATION_CODES},
    }


class GraduationChecklist(unittest.TestCase):
    def test_two_weeks_makes_master_not_auto(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.capture_graduation_week(tmp, [_all_pass_row()], label="2026-11-01")
            board = desk_roi_plan.graduation_board(tmp)
            self.assertEqual(board["towers"]["sports-gap"]["status"], "week_1")
            desk_roi_plan.capture_graduation_week(tmp, [_all_pass_row()], label="2026-11-02")
            board = desk_roi_plan.graduation_board(tmp)
            self.assertEqual(board["towers"]["sports-gap"]["status"], "master")
            self.assertTrue(board["towers"]["sports-gap"]["graduated"])
            self.assertFalse(board["towers"]["sports-gap"]["auto_promote"])
            self.assertFalse(board["auto_promote"])

    def test_broken_week_resets_streak(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.capture_graduation_week(tmp, [_all_pass_row()], label="2026-11-01")
            broken = {
                "bot": "sports-gap",
                "passing": {c: (c != "M3") for c in desk_roi_plan.GRADUATION_CODES},
            }
            desk_roi_plan.capture_graduation_week(tmp, [broken], label="2026-11-02")
            board = desk_roi_plan.graduation_board(tmp)
            self.assertEqual(board["towers"]["sports-gap"]["status"], "not_ready")
            self.assertEqual(board["towers"]["sports-gap"]["consecutive_all_pass_weeks"], 0)


class MemeRetirement(unittest.TestCase):
    def test_negative_window_recommends_pause(self):
        clock = desk_roi_plan.meme_retirement_clock(
            {
                "id": "memecoin",
                "history": [{"pnl": -1.5, "contracts": 1} for _ in range(12)],
            }
        )
        self.assertTrue(clock["recommend_pause"])
        self.assertEqual(clock["action"], "pause_entries")
        self.assertFalse(clock["expand_volume"])
        self.assertFalse(clock["retired"])

    def test_thin_sample_keeps_measuring(self):
        clock = desk_roi_plan.meme_retirement_clock(
            {
                "id": "memecoin",
                "history": [{"pnl": -5.0, "contracts": 1} for _ in range(3)],
            }
        )
        self.assertFalse(clock["recommend_pause"])
        self.assertEqual(clock["action"], "keep_measuring")


class MasterWire(unittest.TestCase):
    def test_master_exposes_grad_and_retire(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Seed fit/latency so M3/M4 can eventually pass; graduation still records.
            for _ in range(12):
                desk_roi_plan.record_fit(tmp, bot="btc15m", outcome="fit")
                desk_roi_plan.record_fit(tmp, bot="btc15m", outcome="buy")
                desk_roi_plan.record_latency(tmp, bot="btc15m", seconds=8.0)
            summary = desk_master.master_summary(
                tmp,
                bots=[
                    {
                        "id": "btc15m",
                        "open_risk": 0,
                        "today": 1,
                        "history": [{"pnl": 1.0, "contracts": 1} for _ in range(25)],
                        "gate_a": {"ready": True},
                    },
                    {
                        "id": "memecoin",
                        "open_risk": 5,
                        "today": -9,
                        "history": [{"pnl": -2.0, "contracts": 1} for _ in range(12)],
                        "gate_a": {"ready": False},
                    },
                ],
                cfg={
                    "max_open_risk": 100,
                    "tower_risk_budgets": {"btc15m": 0.35, "memecoin": 0.05},
                },
            )
            self.assertEqual(summary["version"], 3)
            self.assertIsInstance(summary.get("graduation"), dict)
            self.assertIsInstance(summary.get("meme_retirement"), dict)
            self.assertTrue(summary["meme_retirement"]["recommend_pause"])
            self.assertFalse(summary["meme_retirement"]["expand_volume"])
            plan = summary.get("roi_plan") or {}
            self.assertIn("graduation", plan)
            # M5/M7 present on tower rows
            btc = next(t for t in summary["towers"] if t["bot"] == "btc15m")
            self.assertIn("M5", btc["passing"])
            self.assertIn("M7", btc["passing"])
            self.assertTrue(btc["passing"]["M7"])  # Gate B ready with 25 small wins


if __name__ == "__main__":
    unittest.main()
