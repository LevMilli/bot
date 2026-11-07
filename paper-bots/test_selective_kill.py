"""Selective +1 attempt journal + 5-green-day kill."""
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


class SelectiveKill(unittest.TestCase):
    def test_record_attempt_and_kill_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = desk_roi_plan.record_selective_attempt(
                tmp, "btc15m", edge=0.08, z=1.2, depth=40, today=1.5, boosted=True,
            )
            self.assertTrue(out["recorded"])
            # Seed 10 green days: prior mean 2.0, recent mean 0.5 → kill
            for i, ev in enumerate([2.0] * 5 + [0.5] * 5):
                day = f"2026-10-{i+1:02d}"
                store = desk_roi_plan._load(
                    desk_roi_plan._path("desk_selective_kill.json", tmp)
                    if hasattr(desk_roi_plan, "_path")
                    else os.path.join(tmp, "desk_selective_kill.json"),
                    {"green_days": {}},
                )
                # use e4 module path
                import desk_roi_e4
                path = desk_roi_e4._path(desk_roi_e4.SELECTIVE_KILL_NAME, tmp)
                store = desk_roi_e4._load(path, {"paper_only": True, "green_days": {}, "killed": {}})
                days = list((store.get("green_days") or {}).get("btc15m") or [])
                days.append({"day": day, "taxed_ev": ev, "at": day})
                store.setdefault("green_days", {})["btc15m"] = days
                desk_roi_e4._save(path, store)
            st = desk_roi_plan.selective_kill_status(tmp)
            self.assertTrue(st["by_bot"]["btc15m"]["killed"])
            self.assertTrue(desk_roi_plan.selective_kill_active(tmp, "btc15m"))
            self.assertFalse(desk_roi_plan.selective_kill_active(tmp, "sports-gap"))

    def test_masters_board(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.record_selective_attempt(tmp, "sports-gap", edge=0.1, today=0.2)
            summary = desk_master.master_summary(
                tmp,
                bots=[{"id": "sports-gap", "today": 0.2, "open_risk": 0, "history": [], "gate_a": {}}],
                cfg={"max_open_risk": 100},
            )
            plan = summary.get("roi_plan") or {}
            self.assertIn("selective_kill", plan)
            self.assertTrue(plan.get("fee_floors_locked"))


if __name__ == "__main__":
    unittest.main()
