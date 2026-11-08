"""Staff SLA unblock pack — observe / no-force safety locks."""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_living
import desk_roi_plan
import desk_roi_staff


class StaffSlaPack(unittest.TestCase):
    def test_floors_locked_and_live_off(self):
        self.assertFalse(desk_roi_plan.LIVE_ORDERS_ENABLED)
        with tempfile.TemporaryDirectory() as tmp:
            pack = desk_roi_plan.hillclimb_pick_evidence_pack(tmp)
            self.assertTrue(pack["fee_floors_locked"])
            self.assertFalse(pack["auto_pick"])
            self.assertFalse(pack["auto_apply"])
            self.assertFalse(pack["live_orders_enabled"])

            promo = desk_roi_plan.staff_promote_ready_pack(tmp)
            self.assertTrue(promo["fee_floors_locked"])
            self.assertFalse(promo["force_default"])
            self.assertFalse(promo["live_orders_enabled"])
            self.assertFalse(promo["auto_publish"])

            dual = desk_roi_plan.dual_control_observe_board(tmp)
            self.assertFalse(dual["live_orders_enabled"])
            self.assertFalse(dual["LIVE_ORDERS_ENABLED"])
            self.assertFalse(dual["writes_live_enable"])
            self.assertTrue(dual["fee_floors_locked"])

            dash = desk_roi_plan.staff_dashboard(tmp)
            self.assertTrue(dash["floors_locked"])
            self.assertTrue(dash["fee_floors_locked"])
            self.assertFalse(dash["live_orders_enabled"])
            self.assertFalse(dash["LIVE_ORDERS_ENABLED"])
            self.assertFalse(dash["auto_apply"])
            self.assertFalse(dash["auto_pick"])
            self.assertFalse(dash["tip_invent"])
            self.assertFalse(dash["force_default"])

    def test_hillclimb_never_auto_applies(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack = desk_roi_plan.hillclimb_pick_evidence_pack(tmp)
            self.assertFalse(pack["auto_pick"])
            self.assertFalse(pack["auto_apply"])
            self.assertIn("VOL_SAFE", pack["allowlist"])
            self.assertTrue(pack["needs_staff_pick"])
            self.assertIn("needs_staff_pick", pack["label"])

            journal = desk_roi_plan.hillclimb_lever_journal(tmp)
            self.assertFalse(journal["auto_apply"])
            self.assertFalse(journal["auto_pick"])

            logged = desk_roi_plan.staff_log_hillclimb_pick(
                tmp, "defer", lever="VOL_SAFE", note="wait", before="m1=?", after="m1=?",
            )
            self.assertTrue(logged["ok"])
            self.assertFalse(logged["auto_apply"])
            self.assertFalse(logged["auto_pick"])
            j2 = desk_roi_plan.staff_hillclimb_pick_journal(tmp)
            self.assertEqual(j2["defers"], 1)
            self.assertFalse(j2["auto_apply"])

            # Evidence pack never picks a lever for staff.
            before = desk_roi_plan.active_hillclimb_lever(tmp)
            desk_roi_plan.hillclimb_pick_evidence_pack(tmp)
            after = desk_roi_plan.active_hillclimb_lever(tmp)
            self.assertEqual(before, after)

    def test_hillclimb_chip_needs_staff_pick(self):
        with tempfile.TemporaryDirectory() as tmp:
            chip = desk_living.hillclimb_chip(tmp)
            self.assertTrue(chip.get("needs_staff_pick"))
            self.assertIn("needs_staff_pick", chip["label"])
            self.assertFalse(chip.get("auto_pick"))
            self.assertFalse(chip.get("auto_apply"))

    def test_promote_pack_shapes_and_make_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack = desk_roi_plan.staff_promote_ready_pack(tmp)
            gates = {i["gate"] for i in pack["items"]}
            for expected in (
                "near_miss", "hard_stop", "green_boost", "edge08",
                "helper_gate_a", "commodity_time_stop", "sports_time_final",
            ):
                self.assertIn(expected, gates)
            for item in pack["items"]:
                self.assertTrue(item.get("force_forbidden_until_ready"))
                self.assertIn("ready", item)
                self.assertIn("n", item)
                self.assertIn("ev", item)
                if item["gate"] in desk_roi_staff.PROMOTE_READY_MAKE:
                    self.assertEqual(
                        item["make_command"],
                        desk_roi_staff.PROMOTE_READY_MAKE[item["gate"]],
                    )
                    self.assertTrue(
                        str(item["make_command"]).startswith("make living-")
                    )

    def test_batch_ready_force_false_refuses_thin(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = desk_roi_plan.staff_batch_arm_promotes_ready(tmp, force=False)
            self.assertFalse(out["force_default"])
            self.assertFalse(out["force_applied"])
            self.assertTrue(out["fee_floors_locked"])
            self.assertFalse(out["live_orders_enabled"])
            self.assertEqual(out["armed_n"], 0)
            self.assertGreater(out["blocked_n"], 0)
            for b in out["blocked"]:
                self.assertIn("gate", b)
                self.assertFalse(b.get("ok"))

            # force=True still refuses thin in ready-batch; floors stay locked.
            forced = desk_roi_plan.staff_batch_arm_promotes_ready(tmp, force=True)
            self.assertTrue(forced["force"])
            self.assertFalse(forced["force_applied"])
            self.assertEqual(forced["armed_n"], 0)
            self.assertTrue(forced["fee_floors_locked"])
            self.assertIsNotNone(forced.get("override_note"))
            self.assertIn("refuses", (forced.get("override_note") or "").lower())

    def test_dual_observe_never_enables_live(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = desk_roi_plan.dual_control_observe_board(tmp)
            self.assertFalse(board["live_orders_enabled"])
            self.assertFalse(board["writes_live_enable"])
            desk_roi_plan.staff_sign_dual_control(
                tmp, who="alice", role="primary", item_id="gate_a_pilot",
            )
            board2 = desk_roi_plan.dual_control_observe_board(tmp)
            self.assertFalse(board2["live_orders_enabled"])
            self.assertFalse(desk_roi_plan.LIVE_ORDERS_ENABLED)
            ops = desk_roi_plan.ops_observe(tmp)
            dual = ops.get("dual_control") or {}
            self.assertEqual(dual.get("signed_n"), 1)
            self.assertIn("items_n", dual)
            self.assertFalse(dual.get("live_orders_enabled"))

    def test_observation_clock_and_sla(self):
        with tempfile.TemporaryDirectory() as tmp:
            clock = desk_roi_plan.observation_week_clock(tmp)
            self.assertIn("chicago_week", clock)
            self.assertIn("firm_taxed_m1", clock)
            self.assertIn("green_boost", clock)
            self.assertIn("graduation", clock)
            self.assertIn("meme_retirement", clock)
            self.assertIn("cold_harvest", clock)
            self.assertIn("hillclimb", clock)
            self.assertTrue(clock["fee_floors_locked"])
            self.assertFalse(clock["live_orders_enabled"])

            sla = desk_roi_plan.promote_gate_sla(tmp, refresh=True)
            self.assertGreaterEqual(len(sla["gates"]), 1)
            self.assertTrue(sla["fee_floors_locked"])
            self.assertFalse(sla["auto_promote"])
            for g in sla["gates"]:
                self.assertIn("gate", g)
                self.assertIn("ready_age_days", g)
                self.assertIn("thin_age_days", g)

    def test_sla_armed_flags_helper_inx_edge08(self):
        """Staff-armed helper / INX / edge08 must not look ready_but_unarmed."""
        with tempfile.TemporaryDirectory() as tmp:
            # Helper autonomy already staff-armed.
            with open(os.path.join(tmp, "desk_helper_promote.json"), "w", encoding="utf-8") as fh:
                json.dump({
                    "paper_only": True,
                    "helpers": {
                        "line_shopper": {
                            "staff_approved": True,
                            "autonomy": True,
                            "note": "test arm",
                        }
                    },
                }, fh)
            # INX band staff-approved.
            with open(os.path.join(tmp, "desk_inx_band_promote.json"), "w", encoding="utf-8") as fh:
                json.dump({
                    "paper_only": True,
                    "staff_approved": True,
                    "live": True,
                    "band_id": "80_90",
                    "lo": 0.80,
                    "hi": 0.90,
                }, fh)
            # Edge08 promoted into bot params overlay.
            with open(os.path.join(tmp, "pimp-bot-params.json"), "w", encoding="utf-8") as fh:
                json.dump({
                    "btc15m": {
                        "venue_edge": 0.08,
                        "promoted_from_shadow": "edge08",
                    }
                }, fh)
            # Seed distance board rows via SLA refresh (uses promote_distance_observe).
            sla = desk_roi_staff.promote_gate_sla(tmp, refresh=True)
            by_gate = {g["gate"]: g for g in (sla.get("gates") or []) if isinstance(g, dict)}
            for gate in ("helper_gate_a", "inx_band", "edge08"):
                self.assertIn(gate, by_gate, sorted(by_gate))
                self.assertTrue(by_gate[gate].get("armed"), by_gate[gate])
                self.assertFalse(by_gate[gate].get("ready_but_unarmed"), by_gate[gate])

    def test_csv_exports_observe_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            nm = desk_roi_plan.export_near_miss_shadow_csv(tmp)
            self.assertTrue(nm["ok"])
            self.assertTrue(nm["fee_floors_locked"])
            self.assertFalse(nm["auto_promote"])
            e08 = desk_roi_plan.export_edge08_shadow_csv(tmp)
            self.assertTrue(e08["ok"])
            self.assertFalse(e08["auto_promote"])
            gb = desk_roi_plan.export_green_boost_evidence(tmp)
            self.assertTrue(gb["ok"])
            self.assertFalse(gb["auto_promote"])

    def test_makefile_targets_exist(self):
        mk = os.path.join(HERE, "Makefile")
        with open(mk, encoding="utf-8") as handle:
            text = handle.read()
        for target in (
            "living-hillclimb-pick",
            "living-hillclimb-pick-ready",
            "living-staff-promote-ready-pack",
            "living-staff-promote-batch-ready",
            "living-dual-control-status",
            "living-staff-dashboard",
            "living-observation-clock",
            "living-graduation-capture",
        ):
            self.assertRegex(
                text,
                re.compile(rf"(?m)^{re.escape(target)}(?:\s|:)"),
                msg=f"missing Makefile target {target}",
            )
        self.assertIn("living-staff-promote-batch:", text)
        self.assertIn("STAFF FORCE OVERRIDE", text)

    def test_no_tip_invent_in_staff_module(self):
        path = os.path.join(HERE, "desk_roi_staff.py")
        with open(path, encoding="utf-8") as handle:
            src = handle.read()
        self.assertNotRegex(src, r"living_.*_tip\(")
        self.assertNotIn("tip_wrapper", src)


if __name__ == "__main__":
    unittest.main()
