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
import desk_roi_staff
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
            self.assertTrue(st["evidence_thin"])
            self.assertIn("THIN", st["label"])
            self.assertGreater(st["n_to_promote"], 0)
            self.assertFalse(st["auto_promote"])

    def test_promote_ready_when_ev_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            _seed_labeled(tmp, 30, would_pnl=0.10)
            st = desk_roi_plan.near_miss_promote_status(tmp)
            self.assertEqual(st["labeled_n"], 30)
            self.assertTrue(st["promote_ready"])
            self.assertFalse(st["evidence_thin"])
            self.assertEqual(st["n_to_promote"], 0)
            self.assertIn("ready", st["label"])
            self.assertEqual(st["decision"], "review")
            self.assertGreaterEqual(st["shadow_ev"], 0.0)
            self.assertFalse(st["auto_promote"])
            self.assertFalse(st["live"])

    def test_reject_when_shadow_ev_negative(self):
        with tempfile.TemporaryDirectory() as tmp:
            _seed_labeled(tmp, 30, would_pnl=-0.05)
            st = desk_roi_plan.near_miss_promote_status(tmp)
            self.assertFalse(st["promote_ready"])
            self.assertTrue(st["evidence_thin"])
            self.assertIn("THIN", st["label"])
            self.assertEqual(st["n_to_promote"], 0)  # n bar met; EV still thin
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

    def test_staff_force_arm_z_before_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            armed = desk_roi_plan.staff_promote_near_miss_soft(
                tmp, "z", note="staff gate lifted money-path", force=True,
            )
            self.assertTrue(armed["ok"])
            self.assertEqual(desk_roi_plan.near_miss_soft_live(tmp), "z")
            relax = desk_roi_plan.effective_near_miss_relax(tmp)
            self.assertAlmostEqual(relax["z_relax"], desk_roi_plan.NEAR_MISS_Z_RELAX)
            self.assertEqual(relax["edge_relax"], 0.0)
            self.assertFalse(desk_roi_plan.NEAR_MISS_LIVE)

    def test_soft_p_requires_z_and_m1(self):
        with tempfile.TemporaryDirectory() as tmp:
            # No evidence → soft-p blocked
            denied = desk_roi_plan.staff_promote_near_miss_soft(tmp, "p")
            self.assertFalse(denied["ok"])
            reason0 = (denied.get("reason") or "").lower()
            self.assertTrue(
                "soft-p" in reason0 or "z" in reason0,
                denied.get("reason"),
            )
            # Arm z with force (thin evidence), still no M1 / promote_ready
            desk_roi_plan.staff_promote_near_miss_soft(
                tmp, "z", note="force z", force=True,
            )
            soft_p = desk_roi_plan.near_miss_soft_p_status(tmp, bots=[])
            self.assertTrue(soft_p["z_armed"])
            self.assertFalse(soft_p["soft_p_ready"])
            denied2 = desk_roi_plan.staff_promote_near_miss_soft(tmp, "p")
            self.assertFalse(denied2["ok"])
            # Seed labeled z-band + M1-holding weekly scorecards + z already live
            _seed_labeled(tmp, 30, would_pnl=0.10, soft="z")
            desk_roi_plan.capture_weekly_scorecard(
                tmp,
                bots=[{
                    "id": "btc15m",
                    "history": [{"pnl": 1.0, "contracts": 1} for _ in range(12)],
                    "open_risk": 0,
                }],
                cfg={"max_open_risk": 100},
                label="2026-W44",
            )
            desk_roi_plan.capture_weekly_scorecard(
                tmp,
                bots=[{
                    "id": "btc15m",
                    "history": [{"pnl": 1.0, "contracts": 1} for _ in range(12)],
                    "open_risk": 0,
                }],
                cfg={"max_open_risk": 100},
                label="2026-W45",
            )
            bots = [{
                "id": "btc15m",
                "history": [{"pnl": 1.0, "contracts": 1} for _ in range(12)],
                "open_risk": 0,
            }]
            ready = desk_roi_plan.near_miss_soft_p_status(tmp, bots=bots)
            self.assertTrue(ready["soft_p_ready"], ready)
            # Soft-p second arm still needs its own band OR force — seed p-band too
            _seed_labeled(tmp, 30, would_pnl=0.10, soft="p")
            armed_p = desk_roi_plan.staff_promote_near_miss_soft(
                tmp, "p", note="second arm after z+M1", bots=bots,
            )
            self.assertTrue(armed_p["ok"], armed_p)
            self.assertEqual(desk_roi_plan.near_miss_soft_live(tmp), "p")
            relax = desk_roi_plan.effective_near_miss_relax(tmp)
            self.assertAlmostEqual(relax["p_relax"], desk_roi_plan.NEAR_MISS_P_RELAX)
            self.assertEqual(relax["z_relax"], 0.0)
            self.assertEqual(relax["edge_relax"], 0.0)

    def test_evidence_led_first_arm_soft_p(self):
        """When only soft-p has n≥30 EV≥0, batch arms p — never phantom soft-z."""
        with tempfile.TemporaryDirectory() as tmp:
            _seed_labeled(tmp, 30, would_pnl=0.12, soft="p")
            pref = desk_roi_plan.near_miss_preferred_first_soft(tmp)
            self.assertEqual(pref["preferred"], "p")
            self.assertFalse(pref["z"]["promote_ready"])
            self.assertTrue(pref["p"]["promote_ready"])
            denied_z = desk_roi_plan.staff_promote_near_miss_soft(tmp, "z")
            self.assertFalse(denied_z["ok"])
            armed_p = desk_roi_plan.staff_promote_near_miss_soft(
                tmp, "p", note="evidence-led first arm soft-p",
            )
            self.assertTrue(armed_p["ok"], armed_p)
            self.assertEqual(desk_roi_plan.near_miss_soft_live(tmp), "p")
            relax = desk_roi_plan.effective_near_miss_relax(tmp)
            self.assertAlmostEqual(relax["p_relax"], desk_roi_plan.NEAR_MISS_P_RELAX)
            self.assertEqual(relax["z_relax"], 0.0)

    def test_batch_ready_matches_soft_band(self):
        with tempfile.TemporaryDirectory() as tmp:
            _seed_labeled(tmp, 30, would_pnl=0.15, soft="p")
            out = desk_roi_staff.staff_batch_arm_promotes_ready(tmp, force=False)
            self.assertGreaterEqual(out["armed_n"], 1)
            armed_gates = {a.get("gate") for a in (out.get("armed") or [])}
            self.assertIn("near_miss", armed_gates)
            self.assertEqual(desk_roi_plan.near_miss_soft_live(tmp), "p")

    def test_switch_wrong_soft_z_to_evidence_p(self):
        """Wrongly armed soft-z (no z-band samples) may switch to evidence soft-p."""
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.staff_promote_near_miss_soft(
                tmp, "z", note="phantom z", force=True,
            )
            self.assertEqual(desk_roi_plan.near_miss_soft_live(tmp), "z")
            _seed_labeled(tmp, 30, would_pnl=0.11, soft="p")
            switched = desk_roi_plan.staff_promote_near_miss_soft(
                tmp, "p", note="correct to evidence soft-p",
            )
            self.assertTrue(switched["ok"], switched)
            self.assertEqual(desk_roi_plan.near_miss_soft_live(tmp), "p")


if __name__ == "__main__":
    unittest.main()
