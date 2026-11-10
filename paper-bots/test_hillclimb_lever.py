"""Phase 11 hillclimb lever allowlist — one per Chicago week."""
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


class HillclimbLever(unittest.TestCase):
    def test_allowlist_raise_only(self):
        al = desk_roi_plan.hillclimb_allowlist()
        self.assertIn("VOL_SAFE", al["levers"])
        self.assertTrue(al["levers"]["venue_min_edge_btc"]["raise_only"])
        self.assertTrue(al["levers"]["min_cushion_btc"]["raise_only"])
        self.assertTrue(al["fee_floors_locked"])

    def test_pick_and_midweek_thrash_ban(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate = desk_roi_plan.staff_pick_hillclimb_lever(
                tmp, "kelly_fraction", note="test", proposed_value=0.30,
            )
            self.assertFalse(gate["ok"])
            self.assertIn("Sunday packet", gate["reason"])
            desk_roi_plan.staff_mark_sunday_packet_reviewed(tmp, who="test")
            out = desk_roi_plan.staff_pick_hillclimb_lever(
                tmp, "kelly_fraction", note="test", proposed_value=0.30,
            )
            self.assertTrue(out["ok"])
            self.assertEqual(out["active"]["lever"], "kelly_fraction")
            blocked = desk_roi_plan.staff_pick_hillclimb_lever(tmp, "VOL_SAFE")
            self.assertFalse(blocked["ok"])
            self.assertIn("thrash", blocked["reason"])
            # Same lever re-pick ok.
            again = desk_roi_plan.staff_pick_hillclimb_lever(
                tmp, "kelly_fraction", proposed_value=0.28,
            )
            self.assertTrue(again["ok"])

    def test_reject_soften_btc_floor(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.staff_mark_sunday_packet_reviewed(tmp, who="test")
            soft = desk_roi_plan.staff_pick_hillclimb_lever(
                tmp, "venue_min_edge_btc", proposed_value=0.04,
            )
            self.assertFalse(soft["ok"])
            raise_ok = desk_roi_plan.staff_pick_hillclimb_lever(
                tmp, "venue_min_edge_btc", proposed_value=0.06,
            )
            self.assertTrue(raise_ok["ok"])

    def test_reject_unknown_lever(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = desk_roi_plan.staff_pick_hillclimb_lever(tmp, "LOWER_FLOORS")
            self.assertFalse(out["ok"])

    def test_none_and_evidence_templates(self):
        with tempfile.TemporaryDirectory() as tmp:
            none = desk_roi_plan.staff_pick_hillclimb_lever(
                tmp, "NONE", note="observe week",
            )
            self.assertTrue(none["ok"])
            self.assertEqual(none["active"]["lever"], "NONE")
            self.assertTrue(none["active"]["observation_continues"])
            templates = desk_roi_plan.hillclimb_lever_evidence_templates()
            self.assertIn("VOL_SAFE", templates["templates"])
            self.assertIn("NONE", templates["templates"])
            self.assertIn("success_metrics", templates["templates"]["VOL_SAFE"])
            self.assertIn("kill_metrics", templates["templates"]["VOL_SAFE"])
            dry = desk_roi_plan.hillclimb_dry_run_board("VOL_SAFE")
            self.assertTrue(dry["ok"])
            self.assertFalse(dry["dry_run"]["writes_venue_params"])
            pack = desk_roi_plan.hillclimb_pick_evidence_pack(tmp)
            self.assertIn("sunday_review", pack)
            self.assertIn("evidence_templates", pack)

    def test_demote_clears(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.staff_mark_sunday_packet_reviewed(tmp, who="test")
            desk_roi_plan.staff_pick_hillclimb_lever(tmp, "HIT_FOR_BIG")
            dem = desk_roi_plan.staff_demote_hillclimb_lever(tmp, note="sunday")
            self.assertTrue(dem["ok"])
            self.assertIsNone(desk_roi_plan.active_hillclimb_lever(tmp))
            st = desk_roi_plan.hillclimb_lever_status(tmp)
            self.assertIsNone(st["active"])
            self.assertFalse(st["auto_revert"])
            self.assertTrue(st["process_only"])
            self.assertEqual(st["ticket"], "TC-151")
            self.assertTrue(st["needs_staff_pick"])
            self.assertTrue(st["evidence_thin"])
            self.assertIn("THIN", st["label"])

    def test_capture_week_reads_active_lever(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.staff_mark_sunday_packet_reviewed(tmp, who="test")
            desk_roi_plan.staff_pick_hillclimb_lever(tmp, "VOL_SAFE")
            out = desk_roi_plan.capture_hillclimb_week(
                tmp,
                bots=[{"id": "btc15m", "history": [{"pnl": 0.1}]}],
                label="2026-11-03",
            )
            self.assertEqual(out["card"]["lever"], "VOL_SAFE")

    def test_master_exposes(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = desk_master.master_summary(
                tmp,
                bots=[{"id": "btc15m", "open_risk": 0, "history": [], "gate_a": {}}],
                cfg={"max_open_risk": 100},
            )
            plan = summary.get("roi_plan") or {}
            self.assertIn("hillclimb_lever", plan)
            self.assertTrue(plan.get("fee_floors_locked"))

    def test_fee_floors_untouched(self):
        import desk_profit
        floors = desk_profit.venue_floors_locked()
        self.assertTrue(floors["locked"])
        self.assertTrue(floors["all_ok"])

    def test_e9_week_activation_broadcast_discipline(self):
        with tempfile.TemporaryDirectory() as tmp:
            act0 = desk_roi_plan.hillclimb_lever_activation_board(tmp)
            self.assertTrue(act0["ok"])
            self.assertFalse(act0["activated"])
            desk_roi_plan.staff_mark_sunday_packet_reviewed(tmp, who="test")
            desk_roi_plan.staff_pick_hillclimb_lever(tmp, "VOL_SAFE")
            act = desk_roi_plan.hillclimb_lever_activation_board(tmp)
            self.assertTrue(act["activated"])
            self.assertTrue(act["single_entry"])
            self.assertEqual(act["lever"], "VOL_SAFE")
            bc = desk_roi_plan.hillclimb_lever_masters_broadcast(tmp)
            self.assertIn("VOL_SAFE", bc["soft_copy"])
            self.assertFalse(bc["auto_publish"])
            disc = desk_roi_plan.hillclimb_one_lever_discipline(tmp)
            self.assertTrue(disc["ok"])
            self.assertFalse(disc["off_allowlist"])
            daily = desk_roi_plan.hillclimb_lever_daily_check(tmp, bots=[])
            self.assertEqual(daily["lever"], "VOL_SAFE")
            self.assertFalse(daily["auto_revert"])
            win = desk_roi_plan.staff_hillclimb_lock_win(
                tmp, who="test", note="hold", lever="VOL_SAFE",
            )
            self.assertTrue(win["ok"])
            self.assertFalse(win["auto_apply"])
            # Kill postmortem without kill flag needs note override path —
            # force a kill store then postmortem demotes.
            path = desk_roi_plan._path(desk_roi_plan.HILLCLIMB_KILL, tmp)
            desk_roi_plan._save(path, {
                "paper_only": True,
                "weeks": [
                    {"label": "2026-11-01", "m1": 1.0, "m3": 0.2, "fills_n": 5, "lever": "VOL_SAFE"},
                    {"label": "2026-11-08", "m1": 0.5, "m3": 0.4, "fills_n": 8, "lever": "VOL_SAFE"},
                ],
                "status": desk_roi_plan.evaluate_hillclimb_kill([
                    {"label": "2026-11-01", "m1": 1.0, "m3": 0.2, "fills_n": 5},
                    {"label": "2026-11-08", "m1": 0.5, "m3": 0.4, "fills_n": 8},
                ]),
            })
            pm = desk_roi_plan.staff_hillclimb_kill_postmortem(
                tmp, who="test", note="revert after kill",
            )
            self.assertTrue(pm["ok"])
            self.assertEqual(pm["row"]["demoted"], "VOL_SAFE")
            self.assertIsNone(desk_roi_plan.active_hillclimb_lever(tmp))
            board = desk_roi_plan.hillclimb_e9_week_board(tmp)
            self.assertIn("activation", board)
            self.assertIn("broadcast", board)
            self.assertFalse(board["auto_apply"])


if __name__ == "__main__":
    unittest.main()
