"""Learning skip v2 + adverse cool-off (positive-ROI Phase 4)."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_roi_plan
import pimp_desk


class LearningSkipV2(unittest.TestCase):
    def test_fine_bucket_skips_when_cold(self):
        rows = [
            {
                "result": "miss", "market": "NBA", "bucket": "0.8-0.9",
                "side": "HOME", "hour_ct": 19, "stake": 20,
            }
            for _ in range(8)
        ]
        msg = pimp_desk.learning_skip(
            rows, "NBA", "0.8-0.9", side="HOME", hour_ct=19,
        )
        self.assertIn("learn v2", msg)

    def test_falls_back_to_coarse(self):
        rows = [
            {"result": "miss", "market": "NBA", "bucket": "0.8-0.9", "stake": 20}
            for _ in range(5)
        ] + [
            {"result": "hit", "market": "NBA", "bucket": "0.8-0.9", "stake": 20}
            for _ in range(3)
        ]
        # 3/8 = 37.5% < 40%
        msg = pimp_desk.learning_skip(rows, "NBA", "0.8-0.9")
        self.assertIn("under 40%", msg)
        self.assertNotIn("learn v2", msg)

    def test_record_learning_stores_side_hour(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Point learning path into tmp by monkeypatching via under — use direct write API.
            # record_learning uses pimp_desk._root; call with rows via load after writing.
            root = tmp
            # Minimal: write via function by temporarily shadowing path
            old = pimp_desk.learning_path
            pimp_desk.learning_path = lambda r=None: os.path.join(tmp, "pimp-learning.json")
            try:
                pimp_desk.record_learning(root, {
                    "result": "hit",
                    "market": "BTC",
                    "prob": 0.85,
                    "stake": 20,
                    "side": "YES",
                    "hour_ct": 14,
                    "fill_id": "t1",
                    "at": "2026-11-03 14:00:00 CT",
                })
                rows = pimp_desk.load_learning(root)
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0].get("side"), "YES")
                self.assertEqual(rows[0].get("hour_ct"), 14)
            finally:
                pimp_desk.learning_path = old


class AdverseCool(unittest.TestCase):
    def test_cool_and_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            shallow = desk_roi_plan.record_adverse_fill(
                tmp, bot="sports-gap", ticker="T", entry_price=0.80, mark_price=0.78,
            )
            self.assertFalse(shallow["cooled"])  # 2¢ < 5¢ threshold
            deep = desk_roi_plan.record_adverse_fill(
                tmp, bot="sports-gap", ticker="T", entry_price=0.80, mark_price=0.70,
            )
            self.assertTrue(deep["cooled"])
            self.assertIn("adverse cool-off", desk_roi_plan.adverse_cool_blocks(tmp, "sports-gap"))


class WeeklyScorecard(unittest.TestCase):
    def test_capture(self):
        with tempfile.TemporaryDirectory() as tmp:
            card = desk_roi_plan.capture_weekly_scorecard(
                tmp,
                bots=[
                    {"id": "btc15m", "today": -2, "gate_a": {"ready": False}},
                    {"id": "sports-gap", "today": 5, "gate_a": {"ready": True}},
                ],
                cfg={"max_open_risk": 100},
            )
            self.assertEqual(card["gate_a_ready_towers"], 1)
            self.assertTrue(card["fee_floors_locked"])


if __name__ == "__main__":
    unittest.main()
