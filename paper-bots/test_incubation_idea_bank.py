"""Incubation registrar blocks weather/econ/Polymarket from main AUTO."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_roi_plan


class IncubationIdeaBank(unittest.TestCase):
    def test_blocks_auto_prefixes(self):
        self.assertTrue(desk_roi_plan.incubation_idea_bank_only("KXHIGHTEMP-NYC"))
        self.assertTrue(desk_roi_plan.incubation_idea_bank_only("weather"))
        self.assertIn("idea-bank", desk_roi_plan.incubation_blocks_auto("KXGDPNOW"))
        self.assertFalse(desk_roi_plan.incubation_idea_bank_only("KXBTC15M"))
        self.assertEqual(desk_roi_plan.incubation_blocks_auto("KXBTC15M"), "")

    def test_enroll_refuses_main_auto(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = desk_roi_plan.enroll_incubation(tmp, "KXHIGHTEMP", note="weather idea")
            self.assertTrue(out["ok"])
            self.assertTrue(out["idea_bank_only"])
            self.assertTrue(out["refused_main_auto"])
            self.assertEqual(out["lane"], "idea_bank")
            denied = desk_roi_plan.staff_graduate_incubation(tmp, "KXHIGHTEMP")
            self.assertFalse(denied["ok"])
            self.assertIn("idea-bank", denied["reason"])
            self.assertIn("idea-bank", desk_roi_plan.incubation_blocks_promote(tmp, "KXHIGHTEMP"))


if __name__ == "__main__":
    unittest.main()
