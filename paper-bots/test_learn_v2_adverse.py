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
                label="2026-11-03",
            )
            self.assertEqual(card["gate_a_ready_towers"], 1)
            self.assertTrue(card["fee_floors_locked"])
            latest = desk_roi_plan.latest_weekly_scorecard(tmp)
            self.assertEqual(latest["label"], "2026-11-03")
            # root=None reads package default path (may already have a live card).
            self.assertIsNot(desk_roi_plan.latest_weekly_scorecard(None), latest)

    def test_master_wires_weekly_scorecard(self):
        import desk_master

        with tempfile.TemporaryDirectory() as tmp:
            summary = desk_master.master_summary(
                tmp,
                bots=[
                    {
                        "id": "sports-gap",
                        "label": "Sports",
                        "cash": 500,
                        "today": 2,
                        "open_risk": 10,
                        "gate_a": {"ready": True},
                    }
                ],
                cfg={"max_open_risk": 100},
            )
            plan = summary.get("roi_plan") or {}
            weekly = plan.get("weekly_scorecard")
            self.assertIsInstance(weekly, dict)
            self.assertTrue(weekly.get("fee_floors_locked"))
            self.assertEqual(
                weekly.get("label"),
                desk_roi_plan.latest_weekly_scorecard(tmp)["label"],
            )

    def test_master_weekly_scorecard_prefers_live_bots_over_stale(self):
        """Same-day stale scorecard m1 must not lag live history (#493 twin)."""
        import desk_master

        with tempfile.TemporaryDirectory() as tmp:
            morning = [{
                "id": "commodity-15m",
                "today": 10.16,
                "open_risk": 0,
                "history": [{"pnl": 1.0}] * 4,
                "gate_a": {},
            }]
            desk_roi_plan.capture_weekly_scorecard(
                tmp, bots=morning, cfg={"max_open_risk": 100}, label="2026-11-09",
            )
            stale = desk_roi_plan.latest_weekly_scorecard(tmp) or {}
            self.assertAlmostEqual(float(stale.get("m1") or 0), 0.99, places=2)
            live = [{
                "id": "commodity-15m",
                "today": 35.02,
                "open_risk": 0,
                "history": [{"pnl": 2.0}] * 8,
                "gate_a": {},
            }]
            summary = desk_master.master_summary(
                tmp, bots=live, cfg={"max_open_risk": 100},
            )
            weekly = (summary.get("roi_plan") or {}).get("weekly_scorecard") or {}
            self.assertAlmostEqual(float(weekly.get("m1") or 0), 1.99, places=2)


if __name__ == "__main__":
    unittest.main()
