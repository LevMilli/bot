"""Near-miss soft-gate staff promote — n≥30 labeled + shadow EV ≥ baseline."""
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
import desk_top25


def _seed_labeled(tmp: str, n: int, would_pnl: float = 0.05, soft: str = "z") -> None:
    for i in range(n):
        desk_more.record_near_miss(
            tmp,
            {
                "bot": "btc15m",
                "ticker": f"KXNM-{i}",
                "side": "YES",
                "soft": [soft],
                "z": 0.58,
                "p": 0.78,
                "edge": 0.06,
                "note": "test",
            },
        )
        desk_roi_plan.label_near_miss_outcome(
            tmp, ticker=f"KXNM-{i}", would_pnl=would_pnl, bot="btc15m",
        )


class NearMissPromote(unittest.TestCase):
    def test_reject_until_labeled_n30(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(10):
                desk_more.record_near_miss(
                    tmp,
                    {"bot": "btc15m", "ticker": f"T{i}", "soft": ["z"], "z": 0.58},
                )
            st = desk_roi_plan.near_miss_promote_status(tmp)
            self.assertEqual(st["decision"], "reject")
            self.assertFalse(st["promote_ready"])
            self.assertFalse(st["auto_promote"])

    def test_promote_ready_when_ev_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            _seed_labeled(tmp, 30, would_pnl=0.10)
            st = desk_roi_plan.near_miss_promote_status(tmp)
            self.assertEqual(st["labeled_n"], 30)
            self.assertTrue(st["promote_ready"])
            self.assertEqual(st["decision"], "review")
            self.assertGreaterEqual(st["shadow_ev"], 0.0)
            self.assertFalse(st["auto_promote"])
            self.assertFalse(st["live"])

    def test_reject_when_shadow_ev_negative(self):
        with tempfile.TemporaryDirectory() as tmp:
            _seed_labeled(tmp, 30, would_pnl=-0.05)
            st = desk_roi_plan.near_miss_promote_status(tmp)
            self.assertFalse(st["promote_ready"])
            self.assertEqual(st["decision"], "reject")

    def test_staff_arm_z_only_when_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            denied = desk_roi_plan.staff_promote_near_miss_soft(tmp, "z")
            self.assertFalse(denied["ok"])
            _seed_labeled(tmp, 30, would_pnl=0.08)
            bad = desk_roi_plan.staff_promote_near_miss_soft(tmp, "edge")
            self.assertFalse(bad["ok"])
            armed = desk_roi_plan.staff_promote_near_miss_soft(
                tmp, "z", note="staff review ok",
            )
            self.assertTrue(armed["ok"])
            self.assertEqual(desk_roi_plan.near_miss_soft_live(tmp), "z")
            relax = desk_roi_plan.effective_near_miss_relax(tmp)
            self.assertAlmostEqual(relax["z_relax"], desk_roi_plan.NEAR_MISS_Z_RELAX)
            self.assertEqual(relax["edge_relax"], 0.0)
            cleared = desk_roi_plan.staff_clear_near_miss_promote(tmp)
            self.assertTrue(cleared["ok"])
            self.assertIsNone(desk_roi_plan.near_miss_soft_live(tmp))

    def test_code_default_never_live(self):
        self.assertFalse(desk_roi_plan.NEAR_MISS_LIVE)

    def test_top25_delegates(self):
        with tempfile.TemporaryDirectory() as tmp:
            _seed_labeled(tmp, 30, would_pnl=0.05)
            row = desk_top25.near_miss_promote_check(tmp)
            self.assertTrue(row["ready_for_review"])
            self.assertFalse(row["auto_promote"])

    def test_master_exposes(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = desk_master.master_summary(
                tmp,
                bots=[{"id": "btc15m", "open_risk": 0, "history": [], "gate_a": {}}],
                cfg={"max_open_risk": 100},
            )
            plan = summary.get("roi_plan") or {}
            self.assertIn("near_miss_promote", plan)
            self.assertTrue(plan.get("fee_floors_locked"))

    def test_fee_floors_untouched(self):
        import desk_profit
        floors = desk_profit.venue_floors_locked()
        self.assertTrue(floors["locked"])
        self.assertTrue(floors["all_ok"])


if __name__ == "__main__":
    unittest.main()
