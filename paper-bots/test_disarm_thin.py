"""Disarm thin force-arms — safety rollback; floors locked; LIVE off."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import desk_roi_plan as plan
import desk_roi_staff as staff


class DisarmThinPromotes(unittest.TestCase):
    def test_circular_import_fixed(self):
        # Importing staff then plan APIs must work both directions.
        self.assertTrue(callable(staff.staff_disarm_thin_promotes))
        self.assertTrue(callable(plan.staff_disarm_thin_promotes))
        self.assertTrue(callable(plan.staff_promote_ready_pack))

    def test_disarms_thin_force_armed_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Force-arm thin hard-stop / green_boost / near-miss / inx like prior staff batch.
            hs = plan.staff_set_sports_hard_stop_live(
                tmp, True, note="test force thin", force=True,
            )
            self.assertTrue(hs.get("ok"))
            self.assertTrue(plan.sports_hard_stop_is_live(tmp))

            gb = plan.staff_set_sports_green_boost(
                tmp, True, note="test force thin", force=True,
            )
            self.assertTrue(gb.get("ok"))

            nm = plan.staff_promote_near_miss_soft(
                tmp, "z", note="test force thin", force=True,
            )
            self.assertTrue(nm.get("ok"))

            inx = plan.staff_promote_inx_band(
                tmp, "80_90", note="test force thin", force=True,
            )
            self.assertTrue(inx.get("ok"))

            out = staff.staff_disarm_thin_promotes(
                tmp, note="unit disarm thin",
            )
            self.assertTrue(out.get("ok"))
            self.assertTrue(out.get("fee_floors_locked"))
            self.assertFalse(out.get("live_orders_enabled"))
            self.assertGreaterEqual(int(out.get("cleared_n") or 0), 3)

            self.assertFalse(plan.sports_hard_stop_is_live(tmp))
            gb2 = plan.sports_green_boost_status(tmp)
            self.assertFalse(bool(gb2.get("staff_approved")))
            nm2 = plan.near_miss_promote_status(tmp)
            self.assertFalse(bool(nm2.get("staff_approved")) and bool(nm2.get("live")))


if __name__ == "__main__":
    unittest.main()
