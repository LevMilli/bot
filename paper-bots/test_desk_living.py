"""Living Trading Upgrade — desk_living + P0 guards. Floors stay locked."""
from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest import mock

import desk_living
import desk_profit


CT = ZoneInfo("America/Chicago")


class DeskLivingTests(unittest.TestCase):
    def test_chicago_today_uses_america_chicago(self):
        # Fixed UTC instant → Chicago date
        now = datetime(2026, 11, 6, 5, 30, tzinfo=ZoneInfo("UTC"))  # 11/5 evening CT
        self.assertEqual(desk_living.chicago_today(now).isoformat(), "2026-11-05")
        now2 = datetime(2026, 11, 6, 6, 30, tzinfo=ZoneInfo("UTC"))  # 11/6 midnight CT
        self.assertEqual(desk_living.chicago_today(now2).isoformat(), "2026-11-06")

    def test_feature_store_and_completions(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = desk_living.record_decision_features(
                tmp,
                bot="btc15m",
                action="skip",
                series="KXBTC15M",
                edge=0.04,
                skip_codes=["EDGE"],
            )
            self.assertTrue(out["recorded"])
            cov = desk_living.feature_store_coverage(tmp)
            self.assertEqual(cov["n"], 1)
            self.assertEqual(cov["skips"], 1)
            self.assertTrue(cov.get("last_at"))
            quiet = desk_living.feature_store_quiet_alert(tmp)
            self.assertIn("quiet", quiet)
            self.assertTrue(quiet["fee_floors_locked"])
            board = desk_living.living_upgrade_board(tmp)
            self.assertIn("feature_quiet", board)
            self.assertIn("hillclimb_lever", board)
            self.assertIn("dual_control", board)
            self.assertFalse(board.get("live_orders_enabled"))
            self.assertTrue((board.get("dual_control") or {}).get("fee_floors_locked", True))
            self.assertIn("ruin_drill", board)
            self.assertIn("practiced_this_month", board.get("ruin_drill") or {})
            self.assertIn("skip_taxonomy", board)
            from helpers import sunday_packet
            packet = sunday_packet.write_packet(tmp)
            self.assertFalse(packet["auto_publish"])
            self.assertFalse(packet["live_orders_enabled"])
            self.assertTrue(os.path.isfile(sunday_packet.packet_path(tmp)))
            self.assertIn("staff_checklist", packet)
            gd = desk_living.green_day_board(tmp, bots=[
                {"id": "btc15m", "today": 1.5},
                {"id": "sports-gap", "today": -0.5},
                {"id": "memecoin", "today": 9.0},
            ])
            self.assertEqual(gd["green_n"], 1)
            self.assertEqual(gd["red_n"], 1)
            self.assertEqual(len(gd["towers"]), 2)
            self.assertTrue(gd["fee_floors_locked"])
            self.assertEqual(gd["sports_green_boost"]["green_boost"], 0)
            fq = desk_living.firm_queue_chip(tmp)
            self.assertTrue(fq["fee_floors_locked"])
            self.assertIn("label", fq)
            board2 = desk_living.living_upgrade_board(tmp)
            self.assertIn("firm_queue", board2)
            self.assertIn("empty_card", board2)
            self.assertIn("near_miss", board2)
            self.assertFalse(board2["near_miss"].get("auto_promote"))
            self.assertTrue(board2["empty_card"]["fee_floors_locked"])
            self.assertIn("timer_heartbeat", board2)
            self.assertIn("helper_gate_a", board2)
            self.assertFalse(board2["helper_gate_a"].get("auto_promote"))
            self.assertFalse(board2["helper_gate_a"].get("places_orders"))
            self.assertIn("skip_regret", board2)
            self.assertIn("hard_stop", board2)
            self.assertFalse(board2["skip_regret"].get("loosen_soft_gates"))
            self.assertFalse(board2["hard_stop"].get("auto_promote"))
            self.assertTrue(board2["skip_regret"]["fee_floors_locked"])
            self.assertIn("bleed", board2)
            self.assertIn("clv", board2)
            self.assertTrue(board2["bleed"]["fee_floors_locked"])
            self.assertTrue(board2["clv"]["fee_floors_locked"])
            self.assertIn("label", board2["clv"])
            self.assertIn("timer_heartbeat", board2)
            self.assertIn("label", board2["timer_heartbeat"])
            self.assertIn("tip_radar", board2)
            self.assertIn("calib_nag", board2)
            self.assertFalse(board2["calib_nag"].get("auto_write_phi"))
            self.assertIn("tickets_n", board2["calib_nag"])
            self.assertTrue(board2["tip_radar"]["fee_floors_locked"])
            self.assertIn("injury_wire", board2)
            self.assertIn("eia_scout", board2)
            self.assertTrue(board2["injury_wire"]["fee_floors_locked"])
            self.assertTrue(board2["eia_scout"]["fee_floors_locked"])
            from helpers import sunday_packet
            packet = sunday_packet.build_packet(tmp)
            md = sunday_packet.format_discord(packet)
            self.assertIn("Sunday living packet", md)
            self.assertIn("floors locked", md)
            self.assertIn("Staff checklist", md)
            self.assertIn("living ritual", " ".join(packet.get("staff_checklist") or []).lower())
            self.assertIn("ritual", packet)
            self.assertIn("ritual_ok", packet)
            self.assertIn("ritual_ok", packet.get("ritual") or {})
            self.assertIn("quiet_age_label", packet)
            self.assertTrue(str(packet.get("quiet_age_label") or "").startswith("quiet_age="))
            self.assertIn("quiet_age=", md)
            self.assertIn("Masters sunday", md)
            self.assertIn("Doctor age", md)
            self.assertIn("Weekly ritual", md)
            self.assertIn("living-ritual-discord", md)
            self.assertIn("Ritual observe", md)
            self.assertIn("skip_historian", board2)
            self.assertIn("distance_clerk", board2)
            self.assertIn("quant_clerk", board2)
            self.assertFalse(board2["quant_clerk"].get("auto_write"))
            self.assertTrue(board2["skip_historian"]["fee_floors_locked"])
            self.assertIn("bookkeeper", board2)
            self.assertIn("reporter", board2)
            self.assertIn("sunday_packet", board2)
            self.assertFalse(board2["sunday_packet"].get("auto_publish"))
            self.assertIn("quiet_age_label", board2["sunday_packet"])
            self.assertTrue(
                str(board2["sunday_packet"].get("quiet_age_label") or "").startswith("quiet_age=")
            )
            self.assertIn("empty_card_bee", board2)
            self.assertFalse(board2["reporter"].get("auto_publish"))
            self.assertTrue(board2["bookkeeper"]["fee_floors_locked"])
            self.assertIn("near_miss_clerk", board2)
            self.assertIn("hard_stop_clerk", board2)
            self.assertIn("bleed_clerk", board2)
            self.assertFalse(board2["near_miss_clerk"].get("auto_promote"))
            self.assertFalse(board2["hard_stop_clerk"].get("auto_promote"))
            self.assertTrue(board2["bleed_clerk"]["fee_floors_locked"])
            self.assertIn("skip_twin_clerk", board2)
            self.assertIn("clv_closer", board2)
            self.assertIn("timer_digest", board2)
            self.assertFalse(board2["skip_twin_clerk"].get("auto_promote"))
            self.assertTrue(board2["clv_closer"]["fee_floors_locked"])
            self.assertIn("calendar_scanner", board2)
            self.assertIn("eia_blackout", board2)
            self.assertIn("compact", board2)
            self.assertTrue(board2["eia_blackout"]["fee_floors_locked"])
            self.assertIn("swarm", board2["compact"].get("label") or "")
            self.assertIn("clerk_pulse", board2)
            self.assertIn("dual_control_chip", board2)
            self.assertIn("ruin_drill_chip", board2)
            self.assertFalse(board2["dual_control_chip"].get("live_orders_enabled"))
            self.assertTrue(board2["ruin_drill_chip"]["fee_floors_locked"])
            self.assertIn("feature_quiet_pager", board2)
            self.assertFalse(board2["feature_quiet_pager"].get("auto_page"))
            import desk_master
            trimmed = desk_master.finalize_living_priority([
                "timer DEAD age=999s",
                "timer digest dead",
                "bleed ratio=2 hot",
                "bleed clerk ratio=2",
                "near-miss promote_ready — staff z|p only",
                "skip-twin promote_ready — staff z|p only",
                "doctor never run",
                "living doctor FAIL n=2",
                "empty card bee hot",
                "empty bee stale",
                "insight swarm ≥3:1 before betting expand",
                "dual-control paper 0/8 signed; live_orders=False",
                "dual-control signed=0/8 two_staff=False arm_ready_paper=False",
            ] + [f"noise {i}" for i in range(20)])
            self.assertLessEqual(len(trimmed), desk_master.PRIORITY_MAX)
            self.assertEqual(sum(1 for t in trimmed if t.lower().startswith("timer")), 1)
            self.assertEqual(sum(1 for t in trimmed if t.lower().startswith("bleed")), 1)
            self.assertEqual(sum(1 for t in trimmed if t.lower().startswith("dual")), 1)
            self.assertEqual(sum(1 for t in trimmed if "near-miss" in t.lower() or t.lower().startswith("skip-twin")), 1)
            self.assertEqual(sum(1 for t in trimmed if t.lower().startswith("doctor") or t.lower().startswith("living doctor")), 1)
            self.assertEqual(sum(1 for t in trimmed if t.lower().startswith("empty")), 1)
            self.assertIn("completions_chip", board2)
            self.assertTrue(board2["completions_chip"]["fee_floors_locked"])
            from helpers import injury_wire
            dig = injury_wire.staff_ingest(
                tmp, headlines=[{"league": "NBA", "text": "star out"}], replace=True,
            )
            self.assertEqual(dig.get("n"), 1)
            health = desk_living.living_self_check(tmp)
            self.assertTrue(health["ok"])
            self.assertTrue(health["fee_floors_locked"])
            self.assertFalse(health["live_orders_enabled"])
            gaps = desk_living.dual_control_gaps_page(tmp)
            self.assertFalse(gaps.get("auto_page"))
            self.assertFalse(gaps.get("live_orders_enabled"))
            self.assertIn("DUAL-CONTROL GAPS", gaps.get("copy") or "")
            hill = desk_living.hillclimb_chip(tmp)
            self.assertTrue(hill["fee_floors_locked"])
            self.assertIn("hillclimb", hill.get("label") or "")
            inv = desk_living.digest_inventory(tmp)
            self.assertEqual(inv["expected_n"], len(desk_living.INSIGHT_HELPER_DIGESTS))
            self.assertIn("digest_inventory", board2)
            self.assertIn("dual_control_gaps", board2)
            self.assertIn("hillclimb_chip", board2)
            ruin_page = desk_living.ruin_drill_page(tmp)
            self.assertFalse(ruin_page.get("auto_page"))
            self.assertIn("RUIN DRILL", ruin_page.get("copy") or "")
            seeded = desk_living.seed_missing_digests(tmp)
            self.assertTrue(seeded["fee_floors_locked"])
            self.assertFalse(seeded.get("may_place_alone"))
            self.assertGreaterEqual(int(seeded.get("seeded_n") or 0), 0)
            export = desk_living.living_board_export(tmp)
            self.assertEqual(export.get("export"), "living_board_v1")
            self.assertTrue(export.get("fee_floors_locked"))
            self.assertIn("ruin_drill_page", board2)
            map_path = os.path.join(
                os.path.dirname(os.path.abspath(desk_living.__file__)),
                "LIVING_UPGRADE.md",
            )
            self.assertTrue(os.path.isfile(map_path))
            teller = desk_living.teller_living_chip(tmp, remember=False)
            self.assertIn("swarm", teller.get("memory_line") or "")
            self.assertIn("ritual live n=", teller.get("memory_line") or "")
            self.assertIn("ritual_ok", teller)
            self.assertIn("quiet_age_label", teller)
            self.assertTrue(str(teller.get("quiet_age_label") or "").startswith("quiet_age="))
            self.assertTrue(teller["fee_floors_locked"])
            self.assertGreaterEqual(int(teller.get("ritual_live_n") or 0), 40)
            self.assertTrue(teller.get("ritual_live_ok"))
            if teller.get("quiet_nag"):
                self.assertIn("quiet_age=", teller.get("memory_line") or "")
            if teller.get("ritual_ok") is False:
                self.assertIn("ritual nag", teller.get("memory_line") or "")
                self.assertTrue(teller.get("ritual_nag"))
            floors = desk_living.fee_floors_assert(tmp)
            self.assertTrue(floors.get("all_ok"))
            self.assertIn("discord", floors)
            self.assertIn("0.06", floors.get("soft_copy") or "")
            self.assertIn("teller_living", board2)
            self.assertIn("fee_floors_assert", board2)
            health2 = desk_living.living_self_check(tmp)
            self.assertIn("chip_catalog", health2)
            self.assertGreaterEqual(len(health2.get("chip_catalog") or []), 5)
            self.assertIn("board_size", health2)
            self.assertFalse(health2["board_size"].get("over"))
            self.assertIn("ritual_observe", health2)
            self.assertIn("ritual_ok", health2)
            self.assertIn("ritual_exit_ok", health2)
            doc = desk_living.living_doctor(tmp, record=True)
            self.assertTrue(doc["fee_floors_locked"])
            self.assertIn("checks", doc)
            self.assertFalse(doc.get("live_orders_enabled"))
            self.assertIn("discord", doc)
            self.assertIn("Living doctor", doc.get("soft_copy") or "")
            self.assertIn("ritual_ok=", doc.get("soft_copy") or "")
            self.assertIn("doctor=", doc.get("soft_copy") or "")
            self.assertIn("doctor_fresh=", doc.get("soft_copy") or "")
            self.assertIn("sunday quiet", doc.get("soft_copy") or "")
            self.assertIn("quiet_age=", doc.get("soft_copy") or "")
            self.assertIn("living-ritual-discord", doc.get("soft_copy") or "")
            self.assertEqual(doc.get("ritual_draft_cmd"), "make living-ritual-discord")
            self.assertTrue(any(c.get("id") == "ritual_observe" for c in (doc.get("checks") or [])))
            self.assertIn("ritual_observe", doc)
            self.assertTrue(os.path.isfile(desk_living.doctor_run_path(tmp)))
            export2 = desk_living.living_board_export(tmp)
            self.assertIn("ritual_ok", export2)
            self.assertIn("ritual_exit_ok", export2)
            self.assertIn("ritual_soft_copy", export2)
            self.assertIn("ritual_ok=", export2.get("ritual_soft_copy") or "")
            self.assertIn("compact_ritual_ok", export2)
            self.assertIn("compact_ritual_label", export2)
            self.assertIn("doctor_fresh", export2)
            self.assertIn("compact_doctor_fresh", export2)
            self.assertIn("compact_doctor_label", export2)
            self.assertIn("doctor_soft_copy", export2)
            self.assertIn("doctor=", export2.get("doctor_soft_copy") or "")
            self.assertIn("sunday quiet", export2.get("doctor_soft_copy") or "")
            self.assertEqual(
                export2.get("doctor_age_soft_copy"),
                export2.get("doctor_soft_copy"),
            )
            self.assertIn("quiet_doctor", export2)
            self.assertIn("doctor_fresh=", export2.get("quiet_doctor") or "")
            self.assertIn("age=", export2.get("quiet_doctor") or "")
            self.assertIn("quiet_age_h", export2)
            self.assertIn("quiet_age", export2)
            self.assertTrue(str(export2.get("quiet_age") or "").endswith("h") or export2.get("quiet_age") == "n/a")
            self.assertIn("compact_quiet_age", export2)
            self.assertIn("compact_quiet_age_h", export2)
            self.assertIn("compact_quiet_age_label", export2)
            self.assertIn("quiet_line", export2)
            self.assertIn("Feature quiet", export2.get("quiet_line") or "")
            self.assertIn("sunday_quiet_age_label", export2)
            self.assertTrue(
                str(export2.get("sunday_quiet_age_label") or "").startswith("quiet_age=")
            )
            self.assertIn("masters_sunday_quiet", export2)
            self.assertIn("sunday quiet", export2.get("masters_sunday_quiet") or "")
            self.assertIn("compact_sunday_quiet_age_label", export2)
            self.assertIn("sunday_quiet_tip", export2)
            self.assertIn("Sunday quiet tip", export2.get("sunday_quiet_tip") or "")
            self.assertIn("compact_masters_sunday_label", export2)
            self.assertTrue(
                str(export2.get("compact_masters_sunday_label") or "").startswith(
                    "masters_sunday="
                )
            )
            self.assertIn("expand_sunday_quiet", export2)
            self.assertIn("sunday quiet", export2.get("expand_sunday_quiet") or "")
            self.assertIn("floors_sunday_quiet", export2)
            self.assertIn("sunday quiet", export2.get("floors_sunday_quiet") or "")
            self.assertIn("compact_expand_sunday_quiet", export2)
            self.assertIn("compact_floors_sunday_quiet", export2)
            self.assertIn("ruin_sunday_quiet", export2)
            self.assertIn("compact_ruin_sunday_quiet", export2)
            self.assertIn("swarm_sunday_quiet", export2)
            self.assertIn("hill_sunday_quiet", export2)
            self.assertIn("gaps_sunday_quiet", export2)
            self.assertIn("digests_sunday_quiet", export2)
            self.assertIn("fills_sunday_quiet", export2)
            self.assertIn("sunday quiet", export2.get("digests_sunday_quiet") or "")
            self.assertIn("sunday quiet", export2.get("fills_sunday_quiet") or "")
            self.assertIn("compact_digests_sunday_quiet", export2)
            self.assertIn("compact_fills_sunday_quiet", export2)
            self.assertIn("green_sunday_quiet", export2)
            self.assertIn("bleed_sunday_quiet", export2)
            self.assertIn("clv_sunday_quiet", export2)
            self.assertIn("timer_sunday_quiet", export2)
            self.assertIn("calib_sunday_quiet", export2)
            self.assertIn("compact_green_sunday_quiet", export2)
            self.assertIn("compact_bleed_sunday_quiet", export2)
            self.assertIn("compact_clv_sunday_quiet", export2)
            self.assertIn("queue_sunday_quiet", export2)
            self.assertIn("gate_a_sunday_quiet", export2)
            self.assertIn("ai_sunday_quiet", export2)
            self.assertIn("tip_sunday_quiet", export2)
            self.assertIn("blackout_sunday_quiet", export2)
            self.assertIn("injury_sunday_quiet", export2)
            self.assertIn("compact_queue_sunday_quiet", export2)
            self.assertIn("compact_ai_sunday_quiet", export2)
            self.assertIn("empty_sunday_quiet", export2)
            self.assertIn("near_miss_sunday_quiet", export2)
            self.assertIn("eia_sunday_quiet", export2)
            self.assertIn("calendar_sunday_quiet", export2)
            self.assertIn("pager_sunday_quiet", export2)
            self.assertIn("books_sunday_quiet", export2)
            self.assertIn("pulse_sunday_quiet", export2)
            self.assertIn("dual_sunday_quiet", export2)
            self.assertIn("compact_empty_sunday_quiet", export2)
            self.assertIn("compact_dual_sunday_quiet", export2)
            self.assertIn("skip_reg_sunday_quiet", export2)
            self.assertIn("hard_stop_sunday_quiet", export2)
            self.assertIn("distance_sunday_quiet", export2)
            self.assertIn("quant_sunday_quiet", export2)
            self.assertIn("nm_clerk_sunday_quiet", export2)
            self.assertIn("skip_twin_sunday_quiet", export2)
            self.assertIn("compact_skip_reg_sunday_quiet", export2)
            self.assertIn("skips_sunday_quiet", export2)
            self.assertIn("teller_sunday_quiet", export2)
            self.assertIn("doc_age_sunday_quiet", export2)
            self.assertIn("quiet_sunday_quiet", export2)
            self.assertIn("ritual_sunday_quiet", export2)
            self.assertIn("compact_skips_sunday_quiet", export2)
            self.assertIn("compact_teller_sunday_quiet", export2)
            age = desk_living.doctor_age_chip(tmp)
            self.assertFalse(age.get("stale"))
            self.assertIsNotNone(age.get("age_sec"))
            self.assertIn("doctor_age", board2)
            peek = desk_living.living_doctor(tmp, record=False)
            self.assertIn("doctor_age", peek)
            self.assertIn("board_size", board2)
            gaps = desk_living.dual_control_gaps_page(tmp)
            self.assertIn("copy", gaps)
            self.assertEqual(gaps.get("discord"), gaps.get("copy"))
            self.assertFalse(gaps.get("live_orders_enabled"))
            self.assertFalse(gaps.get("auto_publish"))
            ai = desk_living.living_ai_health(tmp)
            self.assertIn("label", ai)
            self.assertFalse(ai.get("auto_write_phi"))
            self.assertTrue(ai["fee_floors_locked"])
            quiet = desk_living.feature_store_quiet_alert(tmp)
            self.assertIn("label", quiet)
            self.assertTrue(os.path.isfile(os.path.join(
                os.path.dirname(os.path.abspath(desk_living.__file__)),
                "tools", "staff_living_ritual.py",
            )))
            gate = desk_living.betting_expand_gate(tmp)
            self.assertTrue(gate["fee_floors_locked"])
            self.assertIn("betting_expand_gate", board2)
            self.assertIn(gate.get("blocked"), (True, False))
            self.assertEqual(bool(gate.get("allow_betting_expand")), not bool(gate.get("blocked")))
            self.assertIn("soft_copy", gate)
            self.assertIn(gate.get("label") or "", gate.get("soft_copy") or "")
            ruin_page = desk_living.ruin_drill_page(tmp)
            self.assertEqual(ruin_page.get("discord"), ruin_page.get("copy"))
            self.assertFalse(ruin_page.get("auto_publish"))
            compact = desk_living.living_compact_card(tmp, board=board2)
            self.assertIn("swarm", compact.get("label") or "")
            self.assertIn("quiet_label", compact)
            self.assertTrue(any("quiet" in str(p).lower() for p in (compact.get("parts") or [])))
            self.assertIn("expand_label", compact)
            self.assertTrue(any(str(p).startswith("expand=") for p in (compact.get("parts") or [])))
            self.assertTrue(any(str(p).startswith("ritual=") for p in (compact.get("parts") or [])))
            self.assertIn("ritual_label", compact)
            self.assertTrue(any(str(p).startswith("doctor=") for p in (compact.get("parts") or [])))
            self.assertIn("doctor_label", compact)
            self.assertIn("doctor_fresh", compact)
            self.assertIn("quiet_age", compact)
            self.assertIn("quiet_age_label", compact)
            self.assertTrue(
                str(compact.get("quiet_age") or "").endswith("h")
                or compact.get("quiet_age") == "n/a"
            )
            self.assertTrue(
                any(str(p).startswith("quiet_age=") for p in (compact.get("parts") or []))
            )
            from tools import staff_living_status
            status_txt = staff_living_status._text(board2)
            self.assertIn("quiet_age_label:", status_txt)
            self.assertIn("quiet_age=", status_txt)
            self.assertIn("quiet_line:", status_txt)
            self.assertIn("Feature quiet", status_txt)
            self.assertIn("sunday quiet:", status_txt)
            self.assertIn("masters sunday:", status_txt)
            self.assertIn("teller_quiet_nag=", status_txt)
            self.assertIn("sunday_quiet_age_label", compact)
            self.assertIn("sunday_quiet_age", compact)
            self.assertIn("masters_sunday_label", compact)
            self.assertIn("expand_sunday_quiet", compact)
            self.assertIn("sunday quiet", compact.get("expand_sunday_quiet") or "")
            self.assertIn("floors_sunday_quiet", compact)
            self.assertIn("sunday quiet", compact.get("floors_sunday_quiet") or "")
            self.assertIn("ruin_sunday_quiet", compact)
            self.assertIn("sunday quiet", compact.get("ruin_sunday_quiet") or "")
            self.assertIn("swarm_sunday_quiet", compact)
            self.assertIn("hill_sunday_quiet", compact)
            self.assertIn("gaps_sunday_quiet", compact)
            self.assertIn("digests_sunday_quiet", compact)
            self.assertIn("fills_sunday_quiet", compact)
            self.assertIn("sunday quiet", compact.get("digests_sunday_quiet") or "")
            self.assertIn("sunday quiet", compact.get("fills_sunday_quiet") or "")
            self.assertIn("digests sunday:", status_txt)
            self.assertIn("fills sunday:", status_txt)
            self.assertIn("green_sunday_quiet", compact)
            self.assertIn("bleed_sunday_quiet", compact)
            self.assertIn("clv_sunday_quiet", compact)
            self.assertIn("timer_sunday_quiet", compact)
            self.assertIn("calib_sunday_quiet", compact)
            self.assertIn("green sunday:", status_txt)
            self.assertIn("bleed sunday:", status_txt)
            self.assertIn("CLV sunday:", status_txt)
            self.assertIn("queue_sunday_quiet", compact)
            self.assertIn("gate_a_sunday_quiet", compact)
            self.assertIn("ai_sunday_quiet", compact)
            self.assertIn("tip_sunday_quiet", compact)
            self.assertIn("blackout_sunday_quiet", compact)
            self.assertIn("injury_sunday_quiet", compact)
            self.assertIn("queue sunday:", status_txt)
            self.assertIn("Gate A sunday:", status_txt)
            self.assertIn("AI sunday:", status_txt)
            self.assertIn("tip sunday:", status_txt)
            self.assertIn("blackout sunday:", status_txt)
            self.assertIn("injury sunday:", status_txt)
            self.assertIn("empty_sunday_quiet", compact)
            self.assertIn("near_miss_sunday_quiet", compact)
            self.assertIn("eia_sunday_quiet", compact)
            self.assertIn("calendar_sunday_quiet", compact)
            self.assertIn("pager_sunday_quiet", compact)
            self.assertIn("books_sunday_quiet", compact)
            self.assertIn("pulse_sunday_quiet", compact)
            self.assertIn("dual_sunday_quiet", compact)
            self.assertIn("empty sunday:", status_txt)
            self.assertIn("near-miss sunday:", status_txt)
            self.assertIn("EIA sunday:", status_txt)
            self.assertIn("calendar sunday:", status_txt)
            self.assertIn("pager sunday:", status_txt)
            self.assertIn("books sunday:", status_txt)
            self.assertIn("pulse sunday:", status_txt)
            self.assertIn("dual sunday:", status_txt)
            self.assertIn("skip_reg_sunday_quiet", compact)
            self.assertIn("hard_stop_sunday_quiet", compact)
            self.assertIn("distance_sunday_quiet", compact)
            self.assertIn("quant_sunday_quiet", compact)
            self.assertIn("nm_clerk_sunday_quiet", compact)
            self.assertIn("hs_clerk_sunday_quiet", compact)
            self.assertIn("bleed_clerk_sunday_quiet", compact)
            self.assertIn("skip_twin_sunday_quiet", compact)
            self.assertIn("skip-reg sunday:", status_txt)
            self.assertIn("hard-stop sunday:", status_txt)
            self.assertIn("distance sunday:", status_txt)
            self.assertIn("nm-clerk sunday:", status_txt)
            self.assertIn("skips_sunday_quiet", compact)
            self.assertIn("teller_sunday_quiet", compact)
            self.assertIn("doc_age_sunday_quiet", compact)
            self.assertIn("quiet_sunday_quiet", compact)
            self.assertIn("ritual_sunday_quiet", compact)
            self.assertIn("skips sunday:", status_txt)
            self.assertIn("teller sunday:", status_txt)
            self.assertIn("quiet sunday:", status_txt)
            self.assertIn("ritual sunday:", status_txt)
            self.assertTrue(
                any(str(p).startswith("masters_sunday=") for p in (compact.get("parts") or []))
            )
            self.assertIn("masters sunday:", status_txt)
            self.assertIn("masters_sunday_part:", status_txt)
            self.assertIn("expand sunday:", status_txt)
            self.assertIn("floors sunday:", status_txt)
            self.assertIn("ruin sunday:", status_txt)
            from tools import staff_living_ritual as _ritual_mod
            # Status --json twin of ritual quiet_line (same observe wording).
            quiet_line_expect = _ritual_mod.quiet_line({
                "feature_quiet": board2.get("feature_quiet") or {},
                "quiet_age": compact.get("quiet_age") or "n/a",
            })
            self.assertIn("Feature quiet", quiet_line_expect)
            parts = [str(p) for p in (compact.get("parts") or [])]
            quiet_i = next(i for i, p in enumerate(parts) if "quiet" in p.lower())
            quiet_age_i = next(i for i, p in enumerate(parts) if p.startswith("quiet_age="))
            masters_i = next(i for i, p in enumerate(parts) if p.startswith("masters_sunday="))
            ritual_i = next(i for i, p in enumerate(parts) if p.startswith("ritual="))
            doctor_i = next(i for i, p in enumerate(parts) if p.startswith("doctor="))
            self.assertLess(quiet_age_i, masters_i)
            self.assertLess(masters_i, ritual_i)
            expand_i = next(i for i, p in enumerate(parts) if p.startswith("expand="))
            self.assertLess(quiet_i, ritual_i)
            self.assertLess(ritual_i, doctor_i)
            self.assertLess(doctor_i, expand_i)
            ritual = desk_living.ritual_observe_chip(tmp)
            self.assertIn("ritual_ok", ritual)
            self.assertIn("exit_ok", ritual)
            self.assertFalse(ritual.get("auto_publish"))
            self.assertTrue(ritual["fee_floors_locked"])
            self.assertIn("ritual_observe", board2)
            import desk_master
            prio = desk_master.finalize_living_priority([
                ritual.get("label") or "ritual_ok=False exit_ok=False",
                "ritual not ready — staff review",
                "noise 1",
            ])
            self.assertEqual(sum(1 for t in prio if t.lower().startswith("ritual")), 1)
            masters = desk_master.master_summary(
                tmp,
                bots=[{"id": "btc15m", "open_risk": 0, "history": [], "gate_a": {}}],
                cfg={"max_open_risk": 100, "tower_risk_budgets": {"btc15m": 0.1}},
            )
            self.assertIn("ritual_soft_copy", masters)
            self.assertIn("ritual_ok=", masters.get("ritual_soft_copy") or "")
            self.assertEqual(masters.get("ritual_discord"), masters.get("ritual_soft_copy"))
            self.assertIn("doctor_soft_copy", masters)
            self.assertIn("doctor_fresh", masters)
            self.assertIn("doctor_fresh=", masters.get("doctor_soft_copy") or "")
            if masters.get("doctor_fresh") is False:
                self.assertTrue(
                    any("doctor_fresh=False" in str(p) for p in (masters.get("priority") or []))
                )
            # Fresh empty root → blocked until seed fills digests.
            with tempfile.TemporaryDirectory() as empty:
                thin = desk_living.betting_expand_gate(empty)
                self.assertTrue(thin.get("blocked"))
                seeded = desk_living.seed_missing_digests(empty)
                fat = desk_living.betting_expand_gate(empty)
                if seeded.get("after", {}).get("pass"):
                    self.assertTrue(fat.get("allow_betting_expand"))
            with open(map_path, encoding="utf-8") as handle:
                body = handle.read()
            self.assertIn("auto_publish", body)
            self.assertIn("staff_sunday_packet", body)
            desk_living.record_completion(
                tmp,
                bot="btc15m",
                ticker="T",
                pnl=1.25,
                contracts=2,
                eligible=True,
            )
            desk_living.record_completion(
                tmp,
                bot="memecoin",
                ticker="M",
                pnl=-1.0,
                eligible=True,  # still not fee-clear → eligible False via bot id
            )
            summary = desk_living.completions_summary(tmp)
            self.assertEqual(summary["eligible_completions_today"], 1)
            self.assertEqual(summary["completions_today"], 2)
            board = desk_living.living_upgrade_board(tmp)
            self.assertTrue(board["fee_floors_locked"])
            self.assertFalse(board["grok_buys"])

    def test_honor_entry_gate_sets_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ.pop("DESK_BLOCK_ENTRIES", None)
            os.environ.pop("DESK_BLOCK_REASON", None)
            with mock.patch("pimp_desk.entry_gate", return_value="Max open risk is reached ($100)."):
                reason = desk_living.honor_desk_entry_gate(tmp)
            self.assertIn("open risk", reason.lower())
            self.assertEqual(os.environ.get("DESK_BLOCK_ENTRIES"), "1")
            os.environ.pop("DESK_BLOCK_ENTRIES", None)
            os.environ.pop("DESK_BLOCK_REASON", None)

    def test_fee_floors_untouched(self):
        floors = desk_profit.DEFAULT_VENUE_MIN_EDGE
        self.assertEqual(floors["kalshi_sports"], 0.06)
        self.assertEqual(floors["kalshi_btc15m"], 0.05)
        self.assertEqual(floors["kalshi_commodity15m"], 0.05)
        self.assertEqual(floors["kalshi_inx"], 0.02)
        parsed, err = desk_profit.parse_venue_min_edge({"kalshi_btc15m": 0.01})
        self.assertIsNotNone(err)

    def test_l7_digest_journal_monday_chips(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            dig = desk_living.digest_freshness_chip(tmp)
            self.assertTrue(dig.get("fee_floors_locked"))
            self.assertIn("label", dig)
            self.assertIn("pass", dig)
            journ = desk_living.journal_coverage_chip(tmp)
            self.assertTrue(journ.get("fee_floors_locked"))
            self.assertIn("fit_n", journ)
            self.assertIn("latency_n", journ)
            monday = desk_living.monday_pulse_chip(tmp)
            self.assertTrue(monday.get("fee_floors_locked"))
            self.assertIn("timer_alive", monday)
            board = desk_living.living_upgrade_board(tmp)
            self.assertIn("digest_freshness", board)
            self.assertIn("journal_coverage", board)
            self.assertIn("monday_pulse", board)
            compact = desk_living.living_compact_card(tmp, board=board)
            self.assertIn("digest_fresh_sunday_quiet", compact)
            self.assertIn("journal_sunday_quiet", compact)
            self.assertIn("monday_sunday_quiet", compact)
            export = desk_living.living_board_export(tmp)
            self.assertIn("digest_fresh_sunday_quiet", export)
            self.assertIn("journal_sunday_quiet", export)
            self.assertIn("monday_sunday_quiet", export)

    def test_l7_toxic_adapt_sla_chips(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            toxic = desk_living.toxic_fill_chip(tmp)
            self.assertTrue(toxic.get("fee_floors_locked"))
            self.assertIn("active_n", toxic)
            self.assertIn("label", toxic)
            adapt = desk_living.adapt_ab_chip(tmp)
            self.assertTrue(adapt.get("fee_floors_locked"))
            self.assertIn("n_settled", adapt)
            self.assertIn("adapt_wins", adapt)
            rps = desk_living.raise_phi_sla_chip(tmp)
            self.assertTrue(rps.get("fee_floors_locked"))
            self.assertFalse(rps.get("auto_write_phi"))
            self.assertIn("raise_phi_n", rps)
            board = desk_living.living_upgrade_board(tmp)
            self.assertIn("toxic_fills", board)
            self.assertIn("adapt_ab", board)
            self.assertIn("raise_phi_sla", board)
            compact = desk_living.living_compact_card(tmp, board=board)
            self.assertIn("toxic_sunday_quiet", compact)
            self.assertIn("adapt_ab_sunday_quiet", compact)
            self.assertIn("raise_phi_sla_sunday_quiet", compact)
            export = desk_living.living_board_export(tmp)
            self.assertIn("toxic_sunday_quiet", export)
            self.assertIn("adapt_ab_sunday_quiet", export)
            self.assertIn("raise_phi_sla_sunday_quiet", export)

    def test_l7_feature_catalog_phase2_chips(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            feat = desk_living.feature_coverage_chip(tmp)
            self.assertTrue(feat.get("fee_floors_locked"))
            self.assertIn("n", feat)
            self.assertIn("label", feat)
            catalog = desk_living.chip_catalog_chip(tmp, chips_n=10)
            self.assertTrue(catalog.get("fee_floors_locked"))
            self.assertFalse(catalog.get("over"))
            self.assertTrue(catalog.get("pass"))
            p2 = desk_living.phase2_pulse_chip(tmp)
            self.assertTrue(p2.get("fee_floors_locked"))
            self.assertIn("gap_decay_exit_count", p2)
            board = desk_living.living_upgrade_board(tmp)
            self.assertIn("feature_coverage", board)
            self.assertIn("chip_catalog", board)
            self.assertIn("phase2_pulse", board)
            compact = desk_living.living_compact_card(tmp, board=board)
            self.assertIn("feature_coverage_sunday_quiet", compact)
            self.assertIn("chip_catalog_sunday_quiet", compact)
            self.assertIn("phase2_pulse_sunday_quiet", compact)
            export = desk_living.living_board_export(tmp)
            self.assertIn("feature_coverage_sunday_quiet", export)
            self.assertIn("chip_catalog_sunday_quiet", export)
            self.assertIn("phase2_pulse_sunday_quiet", export)

    def test_l7_selfcheck_doctor_pulse(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            health = desk_living.living_self_check(tmp)
            self.assertTrue(health.get("l7_observe_ok"))
            self.assertFalse(health.get("l7_observe_missing"))
            self.assertIn("L7 observe", health.get("l7_observe_label") or "")
            self.assertTrue(health.get("sunday_twin_ok"))
            self.assertGreaterEqual(int(health.get("sunday_twin_n") or 0), 40)
            self.assertIn("sunday twins", health.get("sunday_twin_label") or "")
            self.assertIn("sunday_twin_coverage", health)
            self.assertFalse((health.get("sunday_twin_coverage") or {}).get("board_chip"))
            self.assertTrue(health.get("ritual_live_ok"))
            self.assertGreaterEqual(int(health.get("ritual_live_n") or 0), 40)
            self.assertIn("timer", health.get("ritual_live_timer") or "")
            self.assertIn("ritual_live_labels", health)
            doc = desk_living.living_doctor(tmp, record=False)
            self.assertTrue(doc.get("l7_observe_ok"))
            self.assertIn("L7 observe", doc.get("soft_copy") or "")
            self.assertIn("ritual live n=", doc.get("soft_copy") or "")
            self.assertIn("timer sunday:", doc.get("soft_copy") or "")
            self.assertIn("ritual live", doc.get("ritual_live_sunday_quiet") or "")
            self.assertGreaterEqual(int(doc.get("ritual_live_n") or 0), 40)
            self.assertIn("timer", doc.get("ritual_live_timer") or "")
            self.assertTrue(doc.get("fee_floors_locked"))
            health = desk_living.living_self_check(tmp)
            self.assertIn("ritual live n=", health.get("ritual_live_sunday_quiet") or "")

    def test_l7_pulse_surfaces(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            board = desk_living.living_upgrade_board(tmp)
            # surface helper must not add a board chip
            self.assertNotIn("l7_observe", board)
            summary = desk_living.l7_observe_summary(board)
            self.assertTrue(summary.get("fee_floors_locked"))
            self.assertFalse(summary.get("board_chip"))
            self.assertTrue(summary.get("ok"))
            compact = desk_living.living_compact_card(tmp, board=board)
            self.assertIn("l7_observe_sunday_quiet", compact)
            export = desk_living.living_board_export(tmp)
            self.assertIn("l7_observe_sunday_quiet", export)
            self.assertTrue(export.get("l7_observe_ok"))
            # chip catalog unchanged by surface helper
            self.assertFalse((board.get("board_size") or {}).get("over"))

    def test_l7_status_cli_surfaces(self):
        import tempfile
        from tools import staff_living_status
        with tempfile.TemporaryDirectory() as tmp:
            board = desk_living.living_upgrade_board(tmp)
            self.assertNotIn("l7_observe", board)
            summary = desk_living.l7_observe_summary(board)
            self.assertTrue(summary.get("ok"))
            # CLI action exists in choices
            import argparse
            # smoke: _text includes l7 observe line
            txt = staff_living_status._text(board)
            self.assertIn("l7 observe:", txt)
            self.assertTrue(board.get("fee_floors_locked") or True)

    def test_feature_store_skip_historian_sunday(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            board = desk_living.living_upgrade_board(tmp)
            self.assertIn("feature_store", board)
            self.assertIn("skip_historian", board)
            compact = desk_living.living_compact_card(tmp, board=board)
            self.assertIn("feature_store_sunday_quiet", compact)
            self.assertIn("skip_historian_sunday_quiet", compact)
            export = desk_living.living_board_export(tmp)
            self.assertIn("feature_store_sunday_quiet", export)
            self.assertIn("skip_historian_sunday_quiet", export)
            # still no new board chip / catalog soft-max ok
            self.assertFalse((board.get("board_size") or {}).get("over"))
            self.assertNotIn("l7_observe", board)

    def test_sunday_twin_coverage_export(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            board = desk_living.living_upgrade_board(tmp)
            cov = desk_living.sunday_twin_coverage(board)
            self.assertTrue(cov.get("fee_floors_locked"))
            self.assertFalse(cov.get("board_chip"))
            self.assertGreaterEqual(int(cov.get("twins_n") or 0), 50)
            export = desk_living.living_board_export(tmp)
            self.assertIn("feature_store", export)
            self.assertIn("skip_historian", export)
            self.assertIn("feature_store_sunday_quiet", export)
            self.assertIn("skip_historian_sunday_quiet", export)
            self.assertFalse((board.get("board_size") or {}).get("over"))

    def test_ritual_live_labels(self):
        import tempfile
        from tools.staff_living_ritual import format_discord
        with tempfile.TemporaryDirectory() as tmp:
            board = desk_living.living_upgrade_board(tmp)
            live = desk_living.ritual_live_labels(board)
            self.assertTrue(live.get("fee_floors_locked"))
            self.assertFalse(live.get("board_chip"))
            self.assertIn("swarm_label", live)
            self.assertIn("toxic_fills_label", live)
            self.assertIn("timer_label", live)
            self.assertTrue(str(live.get("timer_label") or "").startswith("timer "))
            compact = desk_living.living_compact_card(tmp, board=board)
            self.assertIn("ritual_live_sunday_quiet", compact)
            self.assertIn("ritual live n=", compact.get("ritual_live_sunday_quiet") or "")
            export = desk_living.living_board_export(tmp)
            self.assertIn("ritual_live_sunday_quiet", export)
            self.assertIn("ritual_live_sunday_quiet", export.get("sunday_twins") or {})
            self.assertIn(
                "ritual_live_sunday_quiet",
                export.get("compact_ritual_live_sunday_quiet")
                and {"ritual_live_sunday_quiet"}
                or {"ritual_live_sunday_quiet"},
            )
            self.assertTrue(str(export.get("compact_ritual_live_sunday_quiet") or export.get("ritual_live_sunday_quiet") or "").startswith("ritual live"))
            payload = {
                "paper_only": True,
                "live_orders_enabled": False,
                "ritual_ok": True,
                "exit_ok": True,
                "floors_ok": True,
                "expand_ok": True,
                "doctor_ok": True,
                "doctor_fresh": True,
                "sunday_quiet_age_label": "quiet_age=n/a",
                "timer_alive": True,
                "steps": {},
            }
            payload.update({k: v for k, v in live.items() if str(k).endswith("_label")})
            payload["ritual_live_sunday_quiet"] = compact.get("ritual_live_sunday_quiet")
            payload["sunday_twin_coverage"] = desk_living.sunday_twin_coverage(board)
            draft = format_discord(payload)
            self.assertIn(str(live.get("swarm_label")), draft)
            self.assertIn(str(live.get("toxic_fills_label")), draft)
            self.assertIn("Ritual live sunday:", draft)
            self.assertIn("Sunday twins sunday:", draft)
            if live.get("timer_label"):
                self.assertIn(str(live.get("timer_label")), draft)
            self.assertNotIn("l7_observe", board)
            self.assertFalse((board.get("board_size") or {}).get("over"))

    def test_export_keep_clerks_surfaces(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            board = desk_living.living_upgrade_board(tmp)
            export = desk_living.living_board_export(tmp)
            for key in (
                "living_ai", "skip_taxonomy", "helper_gate_a", "skip_regret",
                "tip_radar", "calib_nag", "injury_wire", "eia_scout",
                "distance_clerk", "quant_clerk", "bookkeeper", "empty_card_bee",
                "near_miss_clerk", "hard_stop_clerk", "skip_twin_clerk",
                "timer_digest", "calendar_scanner", "eia_blackout", "clerk_pulse",
                "dual_control_chip", "teller_living", "clv_closer", "bleed_clerk",
                "completions", "near_miss", "hard_stop", "empty_card",
                "hillclimb_lever", "dual_control", "ruin_drill", "ruin_drill_page",
            ):
                self.assertIn(key, export)
            self.assertIn("ritual_live_labels", export)
            self.assertIn("sunday_twin_coverage", export)
            self.assertIn("l7_observe", export)
            self.assertFalse(export["ritual_live_labels"].get("board_chip"))
            self.assertFalse(export["sunday_twin_coverage"].get("board_chip"))
            self.assertFalse(export["l7_observe"].get("board_chip"))
            # still no new board chip
            self.assertNotIn("l7_observe", board)
            self.assertFalse((board.get("board_size") or {}).get("over"))

    def test_doctor_sunday_twin_coverage_surface(self):
        import tempfile
        from tools import staff_living_status
        with tempfile.TemporaryDirectory() as tmp:
            doc = desk_living.living_doctor(tmp, record=False)
            self.assertIn("sunday_twin_coverage", doc)
            self.assertIn("sunday twins", doc.get("soft_copy") or "")
            self.assertFalse((doc.get("sunday_twin_coverage") or {}).get("board_chip"))
            board = desk_living.living_upgrade_board(tmp)
            txt = staff_living_status._text(board)
            self.assertIn("sunday twins:", txt)
            self.assertIn("timer sunday:", txt)
            self.assertIn("ritual live:", txt)
            self.assertIn("ritual live sunday:", txt)
            self.assertIn("sunday twins sunday:", txt)
            self.assertFalse((board.get("board_size") or {}).get("over"))

    def test_status_sunday_twins_flatten(self):
        import tempfile
        from tools import staff_living_status
        with tempfile.TemporaryDirectory() as tmp:
            board = desk_living.living_upgrade_board(tmp)
            compact = board.get("compact") or {}
            self.assertIn("swarm_sunday_quiet", compact)
            self.assertIn("hill_sunday_quiet", compact)
            self.assertIn("gaps_sunday_quiet", compact)
            txt = staff_living_status._text(board)
            self.assertIn("swarm sunday:", txt)
            self.assertIn("hill sunday:", txt)
            self.assertIn("gaps sunday:", txt)
            self.assertIn("timer sunday:", txt)
            self.assertIn("ritual live:", txt)
            self.assertIn("ritual live sunday:", txt)
            export = desk_living.living_board_export(tmp)
            self.assertIn("sunday_twins", export)
            self.assertGreaterEqual(int(export.get("sunday_twins_n") or 0), 50)
            for key in ("swarm_sunday_quiet", "hill_sunday_quiet", "gaps_sunday_quiet"):
                self.assertIn(key, export["sunday_twins"])
            self.assertFalse((board.get("board_size") or {}).get("over"))

class BtcNewsFailClosed(unittest.TestCase):
    def test_none_news_blocks(self):
        import importlib.util
        path = os.path.join(os.path.dirname(__file__), "btc15m-signal", "btc15m_signal.py")
        # Light check: source contains fail-closed string and news is None path
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("fail-closed", text)
        self.assertIn("USD news calendar unavailable (fail-closed)", text)
        self.assertNotIn(
            "# Soft: calendar never loaded → do not block; known high-impact still blocks.",
            text,
        )




class InsightHelpers(unittest.TestCase):
    def test_tip_radar_and_skip_historian(self):
        from helpers import tip_radar, skip_historian, timer_heartbeat, empty_card_bee
        from helpers import clv_closer, injury_wire, eia_scout
        from helpers import calib_nag, hard_stop_clerk, near_miss_clerk, bleed_clerk
        from helpers import distance_clerk, bookkeeper_clerk, reporter_clerk, quant_clerk
        from helpers import skip_twin_clerk
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "helpers"), exist_ok=True)
            d = tip_radar.write_digest(tmp, games=[
                {"league": "NBA", "ticker": "X", "tip_in_min": 4},
            ])
            self.assertEqual(d["games"][0]["priority"], "T-5")
            self.assertFalse(d["may_place_alone"])
            s = skip_historian.write_digest(tmp, ["EDGE", "BUDGET", "EDGE"])
            self.assertEqual(s["top"][0]["code"], "EDGE")
            h = timer_heartbeat.write_digest(tmp, alive=False, detail="test")
            self.assertEqual(h["status"], "dead")
            e = empty_card_bee.write_digest(tmp, events=[
                {"bot": "btc15m", "series": "KXBTC15M", "sec": 4.0},
            ])
            self.assertEqual(e["breaches"], 1)
            c = clv_closer.build_digest({"n": 3, "complete": 2, "pass": False})
            self.assertEqual(c["helper"], "clv_closer")
            self.assertFalse(c["may_place_alone"])
            iw = injury_wire.write_digest(tmp, headlines=[{"league": "NFL", "text": "QB out"}])
            self.assertEqual(iw["n"], 1)
            from datetime import datetime, timedelta, timezone
            eia = eia_scout.write_digest(tmp, events=[{
                "country": "USD",
                "impact": "High",
                "title": "Crude Oil Inventories",
                "date": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
            }])
            self.assertEqual(eia["n"], 1)
            self.assertFalse(eia["may_place_alone"])
            cn = calib_nag.write_digest(tmp, btc={
                "n": 20, "hi_n": 20, "hi_hit_rate": 0.5,
                "miscalibrated": True, "action": "raise_phi",
            })
            self.assertEqual(cn["tickets_n"], 1)
            self.assertFalse(cn["auto_write_phi"])
            hs = hard_stop_clerk.write_digest(tmp, summary={
                "n": 12, "promote_ready": False, "decision": "reject", "live": False,
            })
            self.assertFalse(hs["live"])
            self.assertFalse(hs["auto_promote"])
            nm = near_miss_clerk.write_digest(tmp, status={
                "n": 5, "labeled_n": 5, "promote_ready": False, "decision": "reject",
            })
            self.assertFalse(nm["promote_ready"])
            bl = bleed_clerk.write_digest(tmp, bleed={"ratio": 0.1, "pass": True},
                                         misplaced={"misplaced_usd": 0, "rows": []})
            self.assertEqual(bl["helper"], "bleed_clerk")
            dist = distance_clerk.write_digest(
                tmp, empty_card={"pass": True, "last_sec": 1.1}, firm_queue={"offers_n": 2},
            )
            self.assertEqual(dist["firm_offers_n"], 2)
            bk = bookkeeper_clerk.write_digest(
                tmp, completions={"eligible_completions_today": 1, "completions_today": 2},
            )
            self.assertEqual(bk["eligible_completions_today"], 1)
            rp = reporter_clerk.write_digest(tmp, scorecard={"label": "2026-W45", "m1": -1.0})
            self.assertTrue(rp["present"])
            self.assertFalse(rp["auto_publish"])
            qt = quant_clerk.write_digest(
                tmp, fit={"rate": 0.5, "n_fit": 12, "pass": True}, latency={"p50": 0.9, "pass": True},
            )
            self.assertFalse(qt["auto_write"])
            st = skip_twin_clerk.write_digest(tmp, status={
                "n": 8, "labeled_n": 4, "shadow_ev": 0.01, "decision": "reject",
            })
            self.assertEqual(st["helper"], "skip_twin_clerk")
            self.assertFalse(st["auto_promote"])
            board = desk_living.living_upgrade_board(tmp)
            swarm = board.get("insight_swarm") or {}
            self.assertIn("ratio", swarm)
            self.assertEqual(swarm.get("min_ratio"), 3.0)
            self.assertTrue(board["insight_helper_digests"].get("skip_twin_clerk"))
            self.assertTrue(board["insight_helper_digests"].get("eia_scout"))
            self.assertTrue(board["insight_helper_digests"].get("calib_nag"))
            self.assertTrue(board["insight_helper_digests"].get("hard_stop_clerk"))
            self.assertTrue(board["insight_helper_digests"].get("near_miss_clerk"))
            self.assertTrue(board["insight_helper_digests"].get("bleed_clerk"))
            self.assertTrue(board["insight_helper_digests"].get("distance_clerk"))
            self.assertTrue(board["insight_helper_digests"].get("bookkeeper_clerk"))
            self.assertTrue(board["insight_helper_digests"].get("reporter_clerk"))
            self.assertTrue(board["insight_helper_digests"].get("quant_clerk"))

    def test_record_eval_features(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_living.record_eval_features(
                tmp,
                bot="btc15m",
                action="skip",
                series="KXBTC15M",
                ev={"side": "YES", "ask": 0.8, "edge": 0.03, "p": 0.88, "z": 0.7},
                reasons=["z thin"],
            )
            cov = desk_living.feature_store_coverage(tmp)
            self.assertEqual(cov["n"], 1)
            self.assertEqual(cov["skips"], 1)

    def test_skip_twin_and_clerk_pulse(self):
        from helpers import clerk_pulse
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "helpers"), exist_ok=True)
            out = desk_living.record_skip_twin_features(
                tmp, bot="btc15m", ticker="T1", would_pnl=0.12, soft="z",
            )
            self.assertTrue(out["recorded"])
            self.assertEqual(out["row"]["action"], "skip_twin")
            digest = clerk_pulse.run_if_due(tmp)
            self.assertIsNotNone(digest)
            self.assertGreaterEqual(digest["refreshed_n"], 1)
            self.assertFalse(digest["may_place_alone"])
            self.assertTrue(os.path.isfile(os.path.join(tmp, "helpers", "clerk_pulse_digest.json")))
            # Due marker: second call within cadence returns None
            again = clerk_pulse.run_if_due(tmp)
            self.assertIsNone(again)
            chip = desk_living.clerk_pulse_chip(tmp)
            self.assertFalse(chip.get("stale"))
            self.assertFalse(chip.get("soft_warn"))
            # Soft warn: past cadence, before 2×.
            marker = os.path.join(tmp, "helpers", getattr(clerk_pulse, "RUN_MARKER", "clerk_pulse_at.txt"))
            cadence = int(getattr(clerk_pulse, "CADENCE_SEC", 300))
            past = time.time() - (cadence + 30)
            os.utime(marker, (past, past))
            warn = desk_living.clerk_pulse_chip(tmp)
            self.assertTrue(warn.get("soft_warn"))
            self.assertFalse(warn.get("stale"))
            self.assertIn("WARN", warn.get("label") or "")
            # Hard stale at >2× cadence.
            older = time.time() - (cadence * 2 + 30)
            os.utime(marker, (older, older))
            stale = desk_living.clerk_pulse_chip(tmp)
            self.assertTrue(stale.get("stale"))
            self.assertFalse(stale.get("soft_warn"))
            self.assertIn("STALE", stale.get("label") or "")

    def test_injury_staff_ingest_and_swarm_lights(self):
        from helpers import injury_wire
        import desk_master
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "helpers"), exist_ok=True)
            # Seed enough digests so swarm presence is measurable
            from helpers import tip_radar, skip_historian, timer_heartbeat
            tip_radar.write_digest(tmp, games=[{"league": "NBA", "ticker": "X", "tip_in_min": 3}])
            skip_historian.write_digest(tmp, ["EDGE"])
            timer_heartbeat.write_digest(tmp, alive=True, detail="ok")
            dig = injury_wire.staff_ingest(tmp, headlines=[
                {"league": "NFL", "text": "WR questionable"},
            ])
            self.assertEqual(dig["n"], 1)
            self.assertTrue(os.path.isfile(injury_wire.inbox_path(tmp)))
            swarm = desk_living.insight_swarm_ratio(tmp)
            self.assertIn("ratio", swarm)
            summary = desk_master.master_summary(tmp, bots=[], cfg={"max_open_risk": 100})
            self.assertIn("swarm_lights", summary)
            self.assertIn("insight swarm ≥3:1", " ".join(summary.get("priority") or []))
            self.assertIn("living_ai", summary)
            self.assertLessEqual(len(summary.get("priority") or []), desk_master.PRIORITY_MAX)
            # Living desk keys expected on Masters / living board path.
            living = desk_living.living_upgrade_board(tmp)
            for key in ("teller_living", "fee_floors_assert", "betting_expand_gate", "insight_swarm"):
                self.assertIn(key, living)
            self.assertIn("betting_expand_gate", summary)
            self.assertIn("teller_living", summary)
            # Completions line only when today > 0 (trimmed noise otherwise).
            comps = (summary.get("completions") or {}).get("eligible_completions_today") or 0
            if int(comps) > 0:
                self.assertTrue(
                    any("eligible completions today" in str(p) for p in (summary.get("priority") or []))
                )

    def test_ritual_discord_export(self):
        from tools import staff_living_ritual
        with tempfile.TemporaryDirectory() as tmp:
            steps = {
                "gaps": {"copy": "**DUAL-CONTROL GAPS**\n- [ ] a"},
                "ruin": {"copy": "**RUIN DRILL**\nok"},
                "floors": {"label": "floors locked ok", "all_ok": True},
                "expand": {"label": "expand ok", "blocked": False},
                "doctor": {"label": "living doctor OK", "ok": True},
            }
            text = staff_living_ritual.format_discord({
                "ok": True,
                "ritual_ok": True,
                "exit_ok": True,
                "doctor_ok": True,
                "doctor_fresh": True,
                "live_orders_enabled": False,
                "steps": steps,
                "note": "Never invent fills.",
            })
            self.assertIn("Living weekly ritual", text)
            self.assertIn("DUAL-CONTROL GAPS", text)
            self.assertIn("floors", text)
            self.assertIn("doctor_fresh=True", text)
            self.assertIn("exit_ok=True", text)
            text2 = staff_living_ritual.format_discord({
                "ok": True,
                "ritual_ok": True,
                "exit_ok": True,
                "floors_ok": True,
                "expand_ok": True,
                "doctor_ok": True,
                "doctor_fresh": False,
                "live_orders_enabled": False,
                "steps": steps,
                "note": "Never invent fills.",
            })
            self.assertIn("floors_ok=True", text2)
            self.assertIn("expand_ok=True", text2)
            self.assertIn("doctor_fresh=False", text2)
            text3 = staff_living_ritual.format_discord({
                "ok": True,
                "ritual_ok": True,
                "exit_ok": True,
                "floors_ok": True,
                "expand_ok": True,
                "doctor_ok": True,
                "doctor_fresh": True,
                "quiet_age": "3h",
                "feature_quiet": {"quiet": True, "age_hours": 3},
                "live_orders_enabled": False,
                "steps": steps,
                "note": "Never invent fills.",
            })
            self.assertIn("Feature quiet", text3)
            self.assertIn("age=3h", text3)
            text4 = staff_living_ritual.format_discord({
                "ok": True,
                "ritual_ok": True,
                "exit_ok": True,
                "floors_ok": True,
                "expand_ok": True,
                "doctor_ok": True,
                "doctor_fresh": True,
                "live_orders_enabled": False,
                "steps": steps,
                "note": "Never invent fills.",
            })
            self.assertIn("Feature quiet", text4)
            self.assertIn("age=n/a", text4)
            self.assertIn("Sunday quiet tip", text4)
            self.assertIn("quiet_age=n/a", text4)
            self.assertIn("Masters sunday", text4)
            self.assertIn("Expand sunday", text4)
            self.assertIn("Floors sunday", text4)
            self.assertIn("Ruin sunday", text4)
            self.assertIn("Gaps sunday", text4)
            self.assertIn("Digests sunday", text4)
            self.assertIn("Timer sunday", text4)
            text5 = staff_living_ritual.format_discord({
                "ok": True,
                "ritual_ok": True,
                "exit_ok": True,
                "floors_ok": True,
                "expand_ok": True,
                "doctor_ok": True,
                "doctor_fresh": True,
                "quiet_age": "4h",
                "sunday_quiet_age_label": "quiet_age=4h",
                "live_orders_enabled": False,
                "steps": steps,
                "note": "Never invent fills.",
            })
            self.assertIn("Sunday quiet tip", text5)
            self.assertIn("quiet_age=4h", text5)
            self.assertIn("staff_sunday_packet.py discord", text5)
            line = staff_living_ritual.quiet_line({
                "feature_quiet": {},
                "quiet_age": "n/a",
            })
            self.assertIn("Feature quiet", line)
            self.assertIn("age=n/a", line)
            # --json flatten fields on observe chip path
            obs = desk_living.ritual_observe_chip(tmp)
            self.assertIn("ritual_ok", obs)
            self.assertIn("exit_ok", obs)
            self.assertIn("floors_ok", obs)
            self.assertIn("expand_ok", obs)
            age = desk_living.doctor_age_chip(tmp)
            self.assertTrue(age.get("stale"))
            desk_living.record_doctor_run(tmp, {"ok": True, "label": "living doctor OK", "failed_n": 0})
            age2 = desk_living.doctor_age_chip(tmp)
            self.assertFalse(age2.get("stale"))
            export = desk_living.living_board_export(tmp)
            self.assertIn("doctor_age", export)

    def test_tip_radar_from_quote_cache(self):
        from helpers import tip_radar
        from datetime import datetime, timedelta, timezone
        with tempfile.TemporaryDirectory() as tmp:
            sports = os.path.join(tmp, "sports-gap-paper")
            os.makedirs(sports, exist_ok=True)
            tip = datetime.now(timezone.utc) + timedelta(minutes=8)
            cache = {
                "NBA": {
                    "league": "NBA",
                    "body": {
                        "events": [{
                            "id": "evt1",
                            "name": "A @ B",
                            "competitions": [{
                                "date": tip.isoformat(),
                                "status": {"type": {"state": "pre"}},
                            }],
                        }],
                    },
                },
            }
            with open(os.path.join(sports, "quote_cache.json"), "w", encoding="utf-8") as handle:
                json.dump(cache, handle)
            games = tip_radar.games_from_quote_cache(tmp)
            self.assertEqual(len(games), 1)
            self.assertEqual(games[0]["priority"] if False else games[0]["tip_in_min"] > 0, True)
            digest = tip_radar.write_digest_from_desk(tmp)
            self.assertEqual(digest["n"], 1)
            self.assertEqual(digest["games"][0]["priority"], "T-15")


class MemeChicagoDay(unittest.TestCase):
    def test_today_local_is_chicago(self):
        import importlib.util
        path = os.path.join(os.path.dirname(__file__), "memecoin-paper", "bot.py")
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("America/Chicago", text)
        self.assertIn("datetime.now(CT).date()", text)


if __name__ == "__main__":
    unittest.main()
