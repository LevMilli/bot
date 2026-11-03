"""Ruin drill UX: soft / hard / nuclear."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_master
import desk_roi_plan
import pimp_desk


class RuinDrill(unittest.TestCase):
    def test_soft_blocks_entries_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = desk_roi_plan.set_ruin_drill(tmp, "soft", who="test", note="drill")
            self.assertTrue(out["ok"])
            self.assertTrue(out["active"])
            self.assertEqual(out["level"], "soft")
            self.assertTrue(out["block_entries"])
            self.assertFalse(out["pause_all_bots"])
            msg = desk_roi_plan.ruin_drill_blocks_entries(tmp)
            self.assertIn("ruin drill soft", msg)
            cleared = desk_roi_plan.clear_ruin_drill(tmp, who="test")
            self.assertFalse(cleared["active"])
            self.assertEqual(desk_roi_plan.ruin_drill_blocks_entries(tmp), "")

    def test_hard_pauses_bots(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(pimp_desk, "set_pause", return_value={"ok": True}) as pause:
                out = desk_roi_plan.set_ruin_drill(tmp, "hard", who="ops")
            self.assertTrue(out["pause_all_bots"])
            pause.assert_called()
            kwargs = pause.call_args.kwargs
            self.assertTrue(kwargs.get("all_bots"))
            self.assertTrue(kwargs.get("on"))

    def test_nuclear_recommends_flatten(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(pimp_desk, "set_pause", return_value={"ok": True}):
                out = desk_roi_plan.set_ruin_drill(tmp, "nuclear", who="ops")
            self.assertTrue(out["flatten_recommended"])
            self.assertIn("flatten", desk_roi_plan.ruin_drill_blocks_entries(tmp))

    def test_entry_gate_honors_drill(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.set_ruin_drill(tmp, "soft", who="test")
            with mock.patch.object(pimp_desk, "snapshot", return_value={"bots": []}):
                with mock.patch.object(pimp_desk, "load_settings", return_value={
                    **pimp_desk.DEFAULTS,
                }):
                    msg = pimp_desk.entry_gate(tmp, bots=[])
            self.assertIn("ruin drill", msg)

    def test_master_exposes_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = desk_master.master_summary(
                tmp,
                bots=[{"id": "btc15m", "open_risk": 0, "history": [], "gate_a": {}}],
                cfg={"max_open_risk": 100},
            )
            plan = summary.get("roi_plan") or {}
            self.assertIn("ruin_drill", plan)
            self.assertFalse((plan.get("ruin_drill") or {}).get("active"))


if __name__ == "__main__":
    unittest.main()
