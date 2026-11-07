"""INX band promote: research artifact + staff gate; never auto-change live."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_roi_plan


def _hist_leader_70_80(n: int = 25):
    # Asks in 70–80 with strong wins → research leader 70_80.
    rows = []
    for i in range(n):
        rows.append({"ask": 0.75, "pnl": 2.0, "contracts": 1})
    # Live 80–90 thinner/worse
    for i in range(5):
        rows.append({"ask": 0.85, "pnl": -1.0, "contracts": 1})
    return rows


class InxBandPromote(unittest.TestCase):
    def test_default_band_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            live = desk_roi_plan.inx_live_band(tmp)
            self.assertEqual(live["id"], "80_90")
            self.assertFalse(live["staff_approved"])
            self.assertFalse(live["live_changed"])
            status = desk_roi_plan.inx_band_promote_status(tmp)
            self.assertFalse(status["promote_ready"])
            self.assertFalse(status["auto_promote"])

    def test_staff_promote_after_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            rep = desk_roi_plan.run_inx_band_research(tmp, history=_hist_leader_70_80())
            self.assertEqual(rep["leader"], "70_80")
            self.assertFalse(rep["live_changed"])
            status = desk_roi_plan.inx_band_promote_status(tmp)
            self.assertTrue(status["promote_ready"])
            denied = desk_roi_plan.staff_promote_inx_band(tmp, "90_95")
            self.assertFalse(denied["ok"])
            armed = desk_roi_plan.staff_promote_inx_band(
                tmp, "70_80", note="research week locked",
            )
            self.assertTrue(armed["ok"])
            live = desk_roi_plan.inx_live_band(tmp)
            self.assertEqual(live["id"], "70_80")
            self.assertTrue(live["staff_approved"])
            self.assertAlmostEqual(live["lo"], 0.70)
            self.assertAlmostEqual(live["hi"], 0.80)
            eff = desk_roi_plan.effective_inx_ask_band(
                tmp, {"band_min_ask": 0.80, "band_max_ask": 0.92},
            )
            self.assertEqual(eff["source"], "staff_promote")
            self.assertAlmostEqual(eff["lo"], 0.70)
            cleared = desk_roi_plan.staff_clear_inx_band_promote(tmp)
            self.assertTrue(cleared["ok"])
            self.assertFalse(desk_roi_plan.inx_live_band(tmp)["staff_approved"])

    def test_effective_falls_back_to_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            eff = desk_roi_plan.effective_inx_ask_band(
                tmp, {"band_min_ask": 0.80, "band_max_ask": 0.92},
            )
            self.assertEqual(eff["source"], "config")
            self.assertAlmostEqual(eff["hi"], 0.92)

    def test_staff_force_lock_default_band(self):
        with tempfile.TemporaryDirectory() as tmp:
            denied = desk_roi_plan.staff_promote_inx_band(tmp, "80_90")
            self.assertFalse(denied["ok"])
            armed = desk_roi_plan.staff_promote_inx_band(
                tmp, "80_90", note="staff lock default", force=True,
            )
            self.assertTrue(armed["ok"])
            live = desk_roi_plan.inx_live_band(tmp)
            self.assertEqual(live["id"], "80_90")
            self.assertTrue(live["staff_approved"])
            self.assertFalse(live["live_changed"])

    def test_history_from_bots_and_no_force_leader(self):
        with tempfile.TemporaryDirectory() as tmp:
            bots = [{
                "id": "kalshi-sp",
                "history": (
                    [{"ask": 0.75, "pnl": 2.0, "contracts": 1} for _ in range(25)]
                    + [{"ask": 0.85, "pnl": -1.0, "contracts": 1} for _ in range(5)]
                ),
            }]
            hist = desk_roi_plan.inx_history_from_bots(bots)
            self.assertEqual(len(hist), 30)
            rep = desk_roi_plan.run_inx_band_research(tmp, bots=bots)
            self.assertEqual(rep["leader"], "70_80")
            self.assertEqual(rep["history_n"], 30)
            self.assertFalse(rep["auto_promote"])
            status = desk_roi_plan.inx_band_promote_status(tmp)
            self.assertTrue(status["promote_ready"])
            armed = desk_roi_plan.staff_promote_inx_leader(tmp, note="no-force leader")
            self.assertTrue(armed["ok"])
            self.assertEqual(desk_roi_plan.inx_live_band(tmp)["id"], "70_80")
            # Empty research → leader promote fails (no force).
            with tempfile.TemporaryDirectory() as tmp2:
                thin = desk_roi_plan.staff_promote_inx_leader(tmp2)
                self.assertFalse(thin["ok"])
                self.assertFalse(thin.get("force", False))


if __name__ == "__main__":
    unittest.main()
