#!/usr/bin/env python3
"""
Staff UX — compact living upgrade status (never enables live / never softens floors).

Usage (from paper-bots/):
  python3 tools/staff_living_status.py
  python3 tools/staff_living_status.py json
  python3 tools/staff_living_status.py pager
  python3 tools/staff_living_status.py priority
  python3 tools/staff_living_status.py selfcheck
  python3 tools/staff_living_status.py gaps
  python3 tools/staff_living_status.py gaps --discord
  python3 tools/staff_living_status.py inventory
  python3 tools/staff_living_status.py hillclimb
  python3 tools/staff_living_status.py ruin
  python3 tools/staff_living_status.py export
  python3 tools/staff_living_status.py seed
  python3 tools/staff_living_status.py pulse
  python3 tools/staff_living_status.py floors
  python3 tools/staff_living_status.py teller
  python3 tools/staff_living_status.py l7
  python3 tools/staff_living_status.py l7 --discord
  python3 tools/staff_living_status.py sunday
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import desk_living
import desk_master


def _board(root: str) -> dict:
    return desk_living.living_upgrade_board(root) or {}


def _text(board: dict) -> str:
    compact = board.get("compact") if isinstance(board.get("compact"), dict) else {}
    swarm = board.get("insight_swarm") if isinstance(board.get("insight_swarm"), dict) else {}
    quiet = board.get("feature_quiet") if isinstance(board.get("feature_quiet"), dict) else {}
    dual = board.get("dual_control_chip") if isinstance(board.get("dual_control_chip"), dict) else {}
    ruin = board.get("ruin_drill_chip") if isinstance(board.get("ruin_drill_chip"), dict) else {}
    inv = board.get("digest_inventory") if isinstance(board.get("digest_inventory"), dict) else {}
    hill = board.get("hillclimb_chip") if isinstance(board.get("hillclimb_chip"), dict) else {}
    floors = board.get("fee_floors_assert") if isinstance(board.get("fee_floors_assert"), dict) else {}
    teller = board.get("teller_living") if isinstance(board.get("teller_living"), dict) else {}
    expand = board.get("betting_expand_gate") if isinstance(board.get("betting_expand_gate"), dict) else {}
    doctor_age = board.get("doctor_age") if isinstance(board.get("doctor_age"), dict) else {}
    ritual = board.get("ritual_observe") if isinstance(board.get("ritual_observe"), dict) else {}
    compact = board.get("compact") if isinstance(board.get("compact"), dict) else {}
    sunday = board.get("sunday_packet") if isinstance(board.get("sunday_packet"), dict) else {}
    doctor_fresh = ritual.get("doctor_fresh")
    if doctor_fresh is None and compact.get("doctor_fresh") is not None:
        doctor_fresh = compact.get("doctor_fresh")
    if doctor_fresh is None and doctor_age:
        doctor_fresh = not bool(doctor_age.get("stale"))
    live = (
        desk_living.ritual_live_labels(board)
        if hasattr(desk_living, "ritual_live_labels")
        else {}
    )
    sunday_cov = (
        desk_living.sunday_twin_coverage(board)
        if hasattr(desk_living, "sunday_twin_coverage")
        else {}
    )
    prio = (
        desk_living.living_priority_snapshot(board)
        if hasattr(desk_living, "living_priority_snapshot")
        else {}
    )
    hud = (
        desk_living.living_hud_summary(board)
        if hasattr(desk_living, "living_hud_summary")
        else {}
    )
    money = (
        desk_living.living_money_path_tip(board)
        if hasattr(desk_living, "living_money_path_tip")
        else {}
    )
    rails = (
        desk_living.living_guardrails_tip(board)
        if hasattr(desk_living, "living_guardrails_tip")
        else {}
    )
    surfaces = (
        desk_living.living_surface_index(board)
        if hasattr(desk_living, "living_surface_index")
        else {}
    )
    smoke = (
        desk_living.living_staff_smoke(board)
        if hasattr(desk_living, "living_staff_smoke")
        else {}
    )
    paste = (
        desk_living.living_discord_paste_tip(board)
        if hasattr(desk_living, "living_discord_paste_tip")
        else {}
    )
    paper_live = (
        desk_living.living_paper_live_tip(board)
        if hasattr(desk_living, "living_paper_live_tip")
        else {}
    )
    makefile = (
        desk_living.living_makefile_index(board)
        if hasattr(desk_living, "living_makefile_index")
        else {}
    )
    venues = (
        desk_living.living_venues_tip(board)
        if hasattr(desk_living, "living_venues_tip")
        else {}
    )
    chicago = (
        desk_living.living_chicago_tip(board)
        if hasattr(desk_living, "living_chicago_tip")
        else {}
    )
    starve = (
        desk_living.living_starve_tip(board)
        if hasattr(desk_living, "living_starve_tip")
        else {}
    )
    hard_rules = (
        desk_living.living_hard_rules_tip(board)
        if hasattr(desk_living, "living_hard_rules_tip")
        else {}
    )

    swarm_tip = (
        desk_living.living_swarm_tip(board)
        if hasattr(desk_living, "living_swarm_tip")
        else {}
    )
    expand_tip = (
        desk_living.living_expand_tip(board)
        if hasattr(desk_living, "living_expand_tip")
        else {}
    )
    quiet_tip = (
        desk_living.living_quiet_tip(board)
        if hasattr(desk_living, "living_quiet_tip")
        else {}
    )
    timer_tip = (
        desk_living.living_timer_tip(board)
        if hasattr(desk_living, "living_timer_tip")
        else {}
    )
    export_tip = (
        desk_living.living_export_tip(board)
        if hasattr(desk_living, "living_export_tip")
        else {}
    )
    doctor_tip = (
        desk_living.living_doctor_tip(board)
        if hasattr(desk_living, "living_doctor_tip")
        else {}
    )
    inventory_tip = (
        desk_living.living_inventory_tip(board)
        if hasattr(desk_living, "living_inventory_tip")
        else {}
    )
    dual_tip = (
        desk_living.living_dual_tip(board)
        if hasattr(desk_living, "living_dual_tip")
        else {}
    )
    hillclimb_tip = (
        desk_living.living_hillclimb_tip(board)
        if hasattr(desk_living, "living_hillclimb_tip")
        else {}
    )
    ruin_tip = (
        desk_living.living_ruin_tip(board)
        if hasattr(desk_living, "living_ruin_tip")
        else {}
    )
    near_miss_tip = (
        desk_living.living_near_miss_tip(board)
        if hasattr(desk_living, "living_near_miss_tip")
        else {}
    )
    helper_tip = (
        desk_living.living_helper_tip(board)
        if hasattr(desk_living, "living_helper_tip")
        else {}
    )
    hard_stop_tip = (
        desk_living.living_hard_stop_tip(board)
        if hasattr(desk_living, "living_hard_stop_tip")
        else {}
    )
    skip_regret_tip = (
        desk_living.living_skip_regret_tip(board)
        if hasattr(desk_living, "living_skip_regret_tip")
        else {}
    )
    eia_tip = (
        desk_living.living_eia_tip(board)
        if hasattr(desk_living, "living_eia_tip")
        else {}
    )
    injury_tip = (
        desk_living.living_injury_tip(board)
        if hasattr(desk_living, "living_injury_tip")
        else {}
    )
    completions_tip = (
        desk_living.living_completions_tip(board)
        if hasattr(desk_living, "living_completions_tip")
        else {}
    )
    toxic_tip = (
        desk_living.living_toxic_tip(board)
        if hasattr(desk_living, "living_toxic_tip")
        else {}
    )
    calib_tip = (
        desk_living.living_calib_tip(board)
        if hasattr(desk_living, "living_calib_tip")
        else {}
    )
    clv_tip = (
        desk_living.living_clv_tip(board)
        if hasattr(desk_living, "living_clv_tip")
        else {}
    )
    clerk_tip = (
        desk_living.living_clerk_tip(board)
        if hasattr(desk_living, "living_clerk_tip")
        else {}
    )
    bookkeeper_tip = (
        desk_living.living_bookkeeper_tip(board)
        if hasattr(desk_living, "living_bookkeeper_tip")
        else {}
    )
    sunday_bit = str(
        sunday.get("quiet_age_label")
        or compact.get("quiet_age_label")
        or "quiet_age=n/a"
    )
    live_n = sum(
        1 for k, v in live.items() if str(k).endswith("_label") and v
    )
    lines = [
        "Living upgrade status (paper only · floors locked · live=False)",
        f"compact: {compact.get('label') or '—'}",
        (
            f"compact_doctor: {compact.get('doctor_label') or 'doctor=n/a'} · "
            f"{compact.get('ritual_label') or 'ritual=n/a'} · "
            f"doctor_fresh={compact.get('doctor_fresh')}"
        ),
        (
            "quiet+doctor: quiet="
            + ("yes" if quiet.get("quiet") else "no")
            + (
                f" age={quiet.get('age_hours')}h"
                if quiet.get("age_hours") is not None
                else " age=n/a"
            )
            + " · "
            + str(
                compact.get("doctor_label")
                or (
                    "doctor=fresh"
                    if doctor_fresh
                    else "doctor=stale"
                    if doctor_fresh is False
                    else "doctor=n/a"
                )
            )
            + f" · doctor_fresh={doctor_fresh}"
        ),
        (
            f"quiet_age="
            + (
                f"{quiet.get('age_hours')}h"
                if quiet.get("age_hours") is not None
                else str(compact.get("quiet_age") or "n/a")
            )
        ),
        (
            "quiet_age_label: "
            + str(
                compact.get("quiet_age_label")
                or (
                    f"quiet_age={quiet.get('age_hours')}h"
                    if quiet.get("age_hours") is not None
                    else f"quiet_age={compact.get('quiet_age') or 'n/a'}"
                )
            )
        ),
        (
            "quiet_line: "
            + "• Feature quiet: quiet="
            + str(quiet.get("quiet"))
            + " age="
            + (
                f"{quiet.get('age_hours')}h"
                if quiet.get("age_hours") is not None
                else str(compact.get("quiet_age") or "n/a")
            )
            + " (staff observe — never softens floors)"
        ),
        (
            f"swarm: {swarm.get('insight_n')}:{swarm.get('betting_n')} "
            f"pass={swarm.get('pass')}"
        ),
        (
            f"feature quiet: quiet={quiet.get('quiet')} "
            f"age_h={quiet.get('age_hours')} alert={quiet.get('alert') or 'ok'}"
        ),
        f"dual-control: {dual.get('label') or '—'}",
        f"ruin: {ruin.get('label') or '—'}",
        (
            "ruin sunday: "
            + str(ruin.get("label") or "ruin observe")
            + " · sunday quiet "
            + str(
                sunday.get("quiet_age_label")
                or compact.get("quiet_age_label")
                or "quiet_age=n/a"
            )
            + " (observe · never softens floors)"
        ),
        f"hillclimb: {hill.get('label') or '—'}",
        f"digests: {inv.get('label') or '—'}",
        (
            "digest fresh: "
            + str(
                (board.get("digest_freshness") or {}).get("label")
                if isinstance(board.get("digest_freshness"), dict)
                else "digest fresh observe"
            )
        ),
        (
            "journals: "
            + str(
                (board.get("journal_coverage") or {}).get("label")
                if isinstance(board.get("journal_coverage"), dict)
                else "journals observe"
            )
        ),
        (
            "monday pulse: "
            + str(
                (board.get("monday_pulse") or {}).get("label")
                if isinstance(board.get("monday_pulse"), dict)
                else "monday pulse observe"
            )
        ),
        (
            "toxic fills: "
            + str(
                (board.get("toxic_fills") or {}).get("label")
                if isinstance(board.get("toxic_fills"), dict)
                else "toxic fills observe"
            )
        ),
        (
            "adapt A/B: "
            + str(
                (board.get("adapt_ab") or {}).get("label")
                if isinstance(board.get("adapt_ab"), dict)
                else "adapt A/B observe"
            )
        ),
        (
            "raise_Φ SLA: "
            + str(
                (board.get("raise_phi_sla") or {}).get("label")
                if isinstance(board.get("raise_phi_sla"), dict)
                else "raise_Φ SLA observe"
            )
        ),
        (
            "feature coverage: "
            + str(
                (board.get("feature_coverage") or {}).get("label")
                if isinstance(board.get("feature_coverage"), dict)
                else "feature coverage observe"
            )
        ),
        (
            "chip catalog: "
            + str(
                (board.get("chip_catalog") or board.get("board_size") or {}).get("label")
                if isinstance(board.get("chip_catalog") or board.get("board_size"), dict)
                else "chip catalog observe"
            )
        ),
        (
            "phase2 pulse: "
            + str(
                (board.get("phase2_pulse") or {}).get("label")
                if isinstance(board.get("phase2_pulse"), dict)
                else "phase2 pulse observe"
            )
        ),
        (
            "l7 observe: "
            + str(
                (desk_living.l7_observe_summary(board).get("label")
                 if hasattr(desk_living, "l7_observe_summary")
                 else "L7 observe pending")
            )
        ),
        (
            "sunday twins: "
            + str(sunday_cov.get("label") or "sunday twins observe")
        ),
        (
            "timer sunday: "
            + str(live.get("timer_label") or "timer observe")
            + f" · sunday quiet {sunday_bit} (observe · never softens floors)"
        ),
        (
            "ritual live: "
            + str(
                compact.get("ritual_live_sunday_quiet")
                or (
                    f"ritual live n={live_n} · "
                    + str(live.get("digests_label") or "digests observe")
                    + " · "
                    + str(live.get("fills_label") or "fills observe")
                    + f" · sunday quiet {sunday_bit} (observe · never softens floors)"
                )
            )
        ),
        (
            "ritual live sunday: "
            + str(
                compact.get("ritual_live_sunday_quiet")
                or (
                    f"ritual live n={live_n} · "
                    + str(live.get("digests_label") or "digests observe")
                    + " · "
                    + str(live.get("fills_label") or "fills observe")
                    + " · "
                    + str(live.get("timer_label") or "timer observe")
                    + f" · sunday quiet {sunday_bit} (observe · never softens floors)"
                )
            )
        ),
        (
            "sunday twins sunday: "
            + str(sunday_cov.get("label") or "sunday twins observe")
            + f" · sunday quiet {sunday_bit} (observe · never softens floors)"
        ),
        (
            "feature store: "
            + (
                f"n={(board.get('feature_store') or {}).get('n')} "
                f"buys={(board.get('feature_store') or {}).get('buys')} "
                f"skips={(board.get('feature_store') or {}).get('skips')}"
                if isinstance(board.get("feature_store"), dict)
                else "feature store observe"
            )
        ),
        (
            "skip historian: "
            + str(
                (board.get("skip_historian") or {}).get("label")
                if isinstance(board.get("skip_historian"), dict)
                else "skip historian observe"
            )
        ),
        (
            "swarm sunday: "
            + str(
                (board.get("compact") or {}).get("swarm_sunday_quiet")
                if isinstance(board.get("compact"), dict)
                else "swarm observe · sunday quiet"
            )
        ),
        (
            "hill sunday: "
            + str(
                (board.get("compact") or {}).get("hill_sunday_quiet")
                if isinstance(board.get("compact"), dict)
                else "hillclimb observe · sunday quiet"
            )
        ),
        (
            "gaps sunday: "
            + str(
                (board.get("compact") or {}).get("gaps_sunday_quiet")
                if isinstance(board.get("compact"), dict)
                else "gaps observe · sunday quiet"
            )
        ),
        (
            "digests sunday: "
            + str(inv.get("label") or "digests observe")
            + " · sunday quiet "
            + str(
                sunday.get("quiet_age_label")
                or compact.get("quiet_age_label")
                or "quiet_age=n/a"
            )
            + " (observe · never softens floors)"
        ),
        (
            "fills sunday: "
            + (
                f"eligible today {(board.get('completions') or {}).get('eligible_completions_today')}"
                if isinstance(board.get("completions"), dict)
                and (board.get("completions") or {}).get("eligible_completions_today")
                is not None
                else "eligible fills n/a"
            )
            + " · sunday quiet "
            + str(
                sunday.get("quiet_age_label")
                or compact.get("quiet_age_label")
                or "quiet_age=n/a"
            )
            + " (observe · never invents PnL)"
        ),
        (
            "green sunday: "
            + str(
                (board.get("green_day") or {}).get("label")
                if isinstance(board.get("green_day"), dict)
                and (board.get("green_day") or {}).get("label")
                else "green-day observe"
            )
            + " · sunday quiet "
            + str(
                sunday.get("quiet_age_label")
                or compact.get("quiet_age_label")
                or "quiet_age=n/a"
            )
            + " (observe)"
        ),
        (
            "bleed sunday: "
            + str(
                (board.get("bleed") or {}).get("label")
                if isinstance(board.get("bleed"), dict)
                and (board.get("bleed") or {}).get("label")
                else "bleed observe"
            )
            + " · sunday quiet "
            + str(
                sunday.get("quiet_age_label")
                or compact.get("quiet_age_label")
                or "quiet_age=n/a"
            )
            + " (observe · never softens floors)"
        ),
        (
            "CLV sunday: "
            + str(
                (board.get("clv") or board.get("clv_closer") or {}).get("label")
                if isinstance(board.get("clv"), dict) or isinstance(board.get("clv_closer"), dict)
                else "CLV observe"
            )
            + " · sunday quiet "
            + str(
                sunday.get("quiet_age_label")
                or compact.get("quiet_age_label")
                or "quiet_age=n/a"
            )
            + " (observe)"
        ),
        (
            "queue sunday: "
            + str(
                (board.get("firm_queue") or {}).get("label")
                if isinstance(board.get("firm_queue"), dict)
                and (board.get("firm_queue") or {}).get("label")
                else "queue observe"
            )
            + " · sunday quiet "
            + str(
                sunday.get("quiet_age_label")
                or compact.get("quiet_age_label")
                or "quiet_age=n/a"
            )
            + " (observe · never promotes)"
        ),
        (
            "Gate A sunday: "
            + str(
                (board.get("helper_gate_a") or {}).get("label")
                if isinstance(board.get("helper_gate_a"), dict)
                and (board.get("helper_gate_a") or {}).get("label")
                else "Gate A observe"
            )
            + " · sunday quiet "
            + str(
                sunday.get("quiet_age_label")
                or compact.get("quiet_age_label")
                or "quiet_age=n/a"
            )
            + " (observe · never softens floors)"
        ),
        (
            "AI sunday: "
            + str(
                (board.get("living_ai") or {}).get("label")
                if isinstance(board.get("living_ai"), dict)
                and (board.get("living_ai") or {}).get("label")
                else "AI observe"
            )
            + " · sunday quiet "
            + str(
                sunday.get("quiet_age_label")
                or compact.get("quiet_age_label")
                or "quiet_age=n/a"
            )
            + " (observe · never auto-writes Φ)"
        ),
        (
            "tip sunday: "
            + str(
                (board.get("tip_radar") or {}).get("label")
                if isinstance(board.get("tip_radar"), dict)
                and (board.get("tip_radar") or {}).get("label")
                else "tip feed observe"
            )
            + " · sunday quiet "
            + str(
                sunday.get("quiet_age_label")
                or compact.get("quiet_age_label")
                or "quiet_age=n/a"
            )
            + " (observe)"
        ),
        (
            "blackout sunday: "
            + str(
                (board.get("eia_blackout") or {}).get("label")
                if isinstance(board.get("eia_blackout"), dict)
                and (board.get("eia_blackout") or {}).get("label")
                else "blackout observe"
            )
            + " · sunday quiet "
            + str(
                sunday.get("quiet_age_label")
                or compact.get("quiet_age_label")
                or "quiet_age=n/a"
            )
            + " (observe · never softens floors)"
        ),
        (
            "injury sunday: "
            + str(
                (board.get("injury_wire") or {}).get("label")
                if isinstance(board.get("injury_wire"), dict)
                and (board.get("injury_wire") or {}).get("label")
                else "injury observe"
            )
            + " · sunday quiet "
            + str(
                sunday.get("quiet_age_label")
                or compact.get("quiet_age_label")
                or "quiet_age=n/a"
            )
            + " (observe)"
        ),
        (
            "empty sunday: "
            + str(
                (board.get("empty_card") or {}).get("label")
                if isinstance(board.get("empty_card"), dict)
                and (board.get("empty_card") or {}).get("label")
                else "empty CARD observe"
            )
            + " · sunday quiet "
            + str(
                sunday.get("quiet_age_label")
                or compact.get("quiet_age_label")
                or "quiet_age=n/a"
            )
            + " (observe)"
        ),
        (
            "near-miss sunday: "
            + str(
                (board.get("near_miss") or {}).get("label")
                if isinstance(board.get("near_miss"), dict)
                and (board.get("near_miss") or {}).get("label")
                else "near-miss observe"
            )
            + " · sunday quiet "
            + str(
                sunday.get("quiet_age_label")
                or compact.get("quiet_age_label")
                or "quiet_age=n/a"
            )
            + " (observe · never promotes)"
        ),
        (
            "EIA sunday: "
            + str(
                (board.get("eia_scout") or {}).get("label")
                if isinstance(board.get("eia_scout"), dict)
                and (board.get("eia_scout") or {}).get("label")
                else "EIA observe"
            )
            + " · sunday quiet "
            + str(
                sunday.get("quiet_age_label")
                or compact.get("quiet_age_label")
                or "quiet_age=n/a"
            )
            + " (observe)"
        ),
        (
            "calendar sunday: "
            + str(
                (board.get("calendar_scanner") or {}).get("label")
                if isinstance(board.get("calendar_scanner"), dict)
                and (board.get("calendar_scanner") or {}).get("label")
                else "calendar observe"
            )
            + " · sunday quiet "
            + str(
                sunday.get("quiet_age_label")
                or compact.get("quiet_age_label")
                or "quiet_age=n/a"
            )
            + " (observe)"
        ),
        (
            "pager sunday: "
            + str(
                (board.get("feature_quiet_pager") or {}).get("label")
                if isinstance(board.get("feature_quiet_pager"), dict)
                and (board.get("feature_quiet_pager") or {}).get("label")
                else "pager observe"
            )
            + " · sunday quiet "
            + str(
                sunday.get("quiet_age_label")
                or compact.get("quiet_age_label")
                or "quiet_age=n/a"
            )
            + " (observe · never auto-pages)"
        ),
        (
            "books sunday: "
            + str(
                (board.get("bookkeeper") or {}).get("label")
                if isinstance(board.get("bookkeeper"), dict)
                and (board.get("bookkeeper") or {}).get("label")
                else "books observe"
            )
            + " · sunday quiet "
            + str(
                sunday.get("quiet_age_label")
                or compact.get("quiet_age_label")
                or "quiet_age=n/a"
            )
            + " (observe · never invents PnL)"
        ),
        (
            "pulse sunday: "
            + str(
                (board.get("clerk_pulse") or {}).get("label")
                if isinstance(board.get("clerk_pulse"), dict)
                and (board.get("clerk_pulse") or {}).get("label")
                else "pulse observe"
            )
            + " · sunday quiet "
            + str(
                sunday.get("quiet_age_label")
                or compact.get("quiet_age_label")
                or "quiet_age=n/a"
            )
            + " (observe)"
        ),
        (
            "dual sunday: "
            + str(
                (board.get("dual_control") or {}).get("label")
                if isinstance(board.get("dual_control"), dict)
                and (board.get("dual_control") or {}).get("label")
                else "dual observe"
            )
            + " · sunday quiet "
            + str(
                sunday.get("quiet_age_label")
                or compact.get("quiet_age_label")
                or "quiet_age=n/a"
            )
            + " (observe · never softens floors)"
        ),
        (
            "skip-reg sunday: "
            + str(
                (board.get("skip_regret") or {}).get("label")
                if isinstance(board.get("skip_regret"), dict)
                and (board.get("skip_regret") or {}).get("label")
                else "skip-regret observe"
            )
            + " · sunday quiet "
            + str(
                sunday.get("quiet_age_label")
                or compact.get("quiet_age_label")
                or "quiet_age=n/a"
            )
            + " (observe · never softens floors)"
        ),
        (
            "hard-stop sunday: "
            + str(
                (board.get("hard_stop") or {}).get("label")
                if isinstance(board.get("hard_stop"), dict)
                and (board.get("hard_stop") or {}).get("label")
                else "hard-stop observe"
            )
            + " · sunday quiet "
            + str(
                sunday.get("quiet_age_label")
                or compact.get("quiet_age_label")
                or "quiet_age=n/a"
            )
            + " (observe · never promotes)"
        ),
        (
            "distance sunday: "
            + str(
                (board.get("distance_clerk") or {}).get("label")
                if isinstance(board.get("distance_clerk"), dict)
                and (board.get("distance_clerk") or {}).get("label")
                else "distance observe"
            )
            + " · sunday quiet "
            + str(
                sunday.get("quiet_age_label")
                or compact.get("quiet_age_label")
                or "quiet_age=n/a"
            )
            + " (observe)"
        ),
        (
            "quant sunday: "
            + str(
                (board.get("quant_clerk") or {}).get("label")
                if isinstance(board.get("quant_clerk"), dict)
                and (board.get("quant_clerk") or {}).get("label")
                else "quant observe"
            )
            + " · sunday quiet "
            + str(
                sunday.get("quiet_age_label")
                or compact.get("quiet_age_label")
                or "quiet_age=n/a"
            )
            + " (observe)"
        ),
        (
            "report sunday: "
            + str(
                (board.get("reporter") or {}).get("label")
                if isinstance(board.get("reporter"), dict)
                and (board.get("reporter") or {}).get("label")
                else "report observe"
            )
            + " · sunday quiet "
            + str(
                sunday.get("quiet_age_label")
                or compact.get("quiet_age_label")
                or "quiet_age=n/a"
            )
            + " (observe · never auto-posts)"
        ),
        (
            "empty-bee sunday: "
            + str(
                (board.get("empty_card_bee") or {}).get("label")
                if isinstance(board.get("empty_card_bee"), dict)
                and (board.get("empty_card_bee") or {}).get("label")
                else "empty bee observe"
            )
            + " · sunday quiet "
            + str(
                sunday.get("quiet_age_label")
                or compact.get("quiet_age_label")
                or "quiet_age=n/a"
            )
            + " (observe)"
        ),
        (
            "nm-clerk sunday: "
            + str(
                (board.get("near_miss_clerk") or {}).get("label")
                if isinstance(board.get("near_miss_clerk"), dict)
                and (board.get("near_miss_clerk") or {}).get("label")
                else "nm clerk observe"
            )
            + " · sunday quiet "
            + str(
                sunday.get("quiet_age_label")
                or compact.get("quiet_age_label")
                or "quiet_age=n/a"
            )
            + " (observe · never promotes)"
        ),
        (
            "hs-clerk sunday: "
            + str(
                (board.get("hard_stop_clerk") or {}).get("label")
                if isinstance(board.get("hard_stop_clerk"), dict)
                and (board.get("hard_stop_clerk") or {}).get("label")
                else "hs clerk observe"
            )
            + " · sunday quiet "
            + str(
                sunday.get("quiet_age_label")
                or compact.get("quiet_age_label")
                or "quiet_age=n/a"
            )
            + " (observe · never promotes)"
        ),
        (
            "bleed-clerk sunday: "
            + str(
                (board.get("bleed_clerk") or {}).get("label")
                if isinstance(board.get("bleed_clerk"), dict)
                and (board.get("bleed_clerk") or {}).get("label")
                else "bleed clerk observe"
            )
            + " · sunday quiet "
            + str(
                sunday.get("quiet_age_label")
                or compact.get("quiet_age_label")
                or "quiet_age=n/a"
            )
            + " (observe · never softens floors)"
        ),
        (
            "skip-twin sunday: "
            + str(
                (board.get("skip_twin_clerk") or {}).get("label")
                if isinstance(board.get("skip_twin_clerk"), dict)
                and (board.get("skip_twin_clerk") or {}).get("label")
                else "skip-twin observe"
            )
            + " · sunday quiet "
            + str(
                sunday.get("quiet_age_label")
                or compact.get("quiet_age_label")
                or "quiet_age=n/a"
            )
            + " (observe)"
        ),
        (
            "CLV-closer sunday: "
            + str(
                (board.get("clv_closer") or {}).get("label")
                if isinstance(board.get("clv_closer"), dict)
                and (board.get("clv_closer") or {}).get("label")
                else "CLV closer observe"
            )
            + " · sunday quiet "
            + str(
                sunday.get("quiet_age_label")
                or compact.get("quiet_age_label")
                or "quiet_age=n/a"
            )
            + " (observe)"
        ),
        (
            "t-digest sunday: "
            + str(
                (board.get("timer_digest") or {}).get("label")
                if isinstance(board.get("timer_digest"), dict)
                and (board.get("timer_digest") or {}).get("label")
                else "t-digest observe"
            )
            + " · sunday quiet "
            + str(
                sunday.get("quiet_age_label")
                or compact.get("quiet_age_label")
                or "quiet_age=n/a"
            )
            + " (observe)"
        ),
        (
            "skips sunday: "
            + str(
                (board.get("skip_taxonomy") or {}).get("label")
                if isinstance(board.get("skip_taxonomy"), dict)
                and (board.get("skip_taxonomy") or {}).get("label")
                else "skips observe"
            )
            + " · sunday quiet "
            + str(
                sunday.get("quiet_age_label")
                or compact.get("quiet_age_label")
                or "quiet_age=n/a"
            )
            + " (observe)"
        ),
        (
            "adapt sunday: "
            + str(
                (board.get("living_ai") or {}).get("label")
                if isinstance(board.get("living_ai"), dict)
                and (board.get("living_ai") or {}).get("label")
                else "adapt observe"
            )
            + " · sunday quiet "
            + str(
                sunday.get("quiet_age_label")
                or compact.get("quiet_age_label")
                or "quiet_age=n/a"
            )
            + " (observe · never auto-writes Φ)"
        ),
        (
            "teller sunday: "
            + str(
                (board.get("teller_living") or {}).get("label")
                if isinstance(board.get("teller_living"), dict)
                and (board.get("teller_living") or {}).get("label")
                else "teller observe"
            )
            + " · sunday quiet "
            + str(
                sunday.get("quiet_age_label")
                or compact.get("quiet_age_label")
                or "quiet_age=n/a"
            )
            + " (observe · never softens floors)"
        ),
        (
            "quiet sunday: "
            + str(
                (board.get("feature_quiet") or {}).get("label")
                if isinstance(board.get("feature_quiet"), dict)
                and (board.get("feature_quiet") or {}).get("label")
                else "feature quiet observe"
            )
            + " · sunday quiet "
            + str(
                sunday.get("quiet_age_label")
                or compact.get("quiet_age_label")
                or "quiet_age=n/a"
            )
            + " (observe · never softens floors)"
        ),
        (
            "doc-age sunday: "
            + str(
                (board.get("doctor_age") or {}).get("label")
                if isinstance(board.get("doctor_age"), dict)
                and (board.get("doctor_age") or {}).get("label")
                else "doctor age observe"
            )
            + " · sunday quiet "
            + str(
                sunday.get("quiet_age_label")
                or compact.get("quiet_age_label")
                or "quiet_age=n/a"
            )
            + " (observe · never softens floors)"
        ),
        (
            "ritual sunday: "
            + str(
                (board.get("ritual_observe") or {}).get("label")
                if isinstance(board.get("ritual_observe"), dict)
                and (board.get("ritual_observe") or {}).get("label")
                else "ritual observe"
            )
            + " · sunday quiet "
            + str(
                sunday.get("quiet_age_label")
                or compact.get("quiet_age_label")
                or "quiet_age=n/a"
            )
            + " (observe · never auto-posts)"
        ),
        f"floors: {floors.get('label') or '—'}",
        f"teller: {teller.get('memory_line') or '—'}",
        (
            f"ritual_nag={bool(teller.get('ritual_nag'))} "
            f"teller_ritual_ok={teller.get('ritual_ok')} "
            f"teller_ritual_live_n={teller.get('ritual_live_n')}"
        ),
        (
            "teller ritual live: "
            + (
                f"n={teller.get('ritual_live_n')} ok={teller.get('ritual_live_ok')}"
                if teller.get("ritual_live_n") is not None
                else "ritual live observe"
            )
            + f" · sunday quiet {sunday_bit} (observe · never softens floors)"
        ),
        (
            "teller ritual live sunday: "
            + str(
                compact.get("teller_ritual_live_sunday_quiet")
                or (
                    f"teller ritual live n={teller.get('ritual_live_n') if teller.get('ritual_live_n') is not None else live_n} "
                    f"· sunday quiet {sunday_bit} (observe · never softens floors)"
                )
            )
        ),
        (
            "priority: "
            + str(prio.get("label") or "priority observe")
        ),
        (
            "priority sunday: "
            + str(
                compact.get("priority_sunday_quiet")
                or (
                    str(prio.get("label") or "priority observe")
                    + f" · sunday quiet {sunday_bit} (observe · never softens floors)"
                )
            )
        ),
        (
            "hud: "
            + str(hud.get("label") or "hud observe")
        ),
        (
            "hud sunday: "
            + str(
                compact.get("hud_sunday_quiet")
                or (
                    str(hud.get("label") or "hud observe")
                    + f" · sunday quiet {sunday_bit} (observe · never softens floors)"
                )
            )
        ),
        (
            "money-path: "
            + str(money.get("label") or "money-path observe")
        ),
        (
            "money-path sunday: "
            + str(
                compact.get("money_path_sunday_quiet")
                or (
                    str(money.get("label") or "money-path observe")
                    + f" · sunday quiet {sunday_bit} (observe · never invents PnL)"
                )
            )
        ),
        (
            "guardrails: "
            + str(rails.get("label") or "guardrails observe")
        ),
        (
            "guardrails sunday: "
            + str(
                compact.get("guardrails_sunday_quiet")
                or (
                    str(rails.get("label") or "guardrails observe")
                    + f" · sunday quiet {sunday_bit} (observe · never softens floors)"
                )
            )
        ),
        (
            "surfaces: "
            + str(surfaces.get("label") or "surfaces observe")
        ),
        (
            "surfaces sunday: "
            + str(
                compact.get("surfaces_sunday_quiet")
                or (
                    str(surfaces.get("label") or "surfaces observe")
                    + f" · sunday quiet {sunday_bit} (observe · never softens floors)"
                )
            )
        ),
        (
            "smoke: "
            + str(smoke.get("label") or "smoke observe")
        ),
        (
            "smoke sunday: "
            + str(
                compact.get("smoke_sunday_quiet")
                or (
                    str(smoke.get("label") or "smoke observe")
                    + f" · sunday quiet {sunday_bit} (observe · never softens floors)"
                )
            )
        ),
        (
            "paste: "
            + str(paste.get("label") or "paste observe")
        ),
        (
            "paste sunday: "
            + str(
                compact.get("paste_sunday_quiet")
                or (
                    str(paste.get("label") or "paste observe")
                    + f" · sunday quiet {sunday_bit} (observe · never auto-posts)"
                )
            )
        ),
        (
            "paper-live: "
            + str(paper_live.get("label") or "paper-live observe")
        ),
        (
            "paper-live sunday: "
            + str(
                compact.get("paper_live_sunday_quiet")
                or (
                    str(paper_live.get("label") or "paper-live observe")
                    + f" · sunday quiet {sunday_bit} (observe · never enables live)"
                )
            )
        ),
        (
            "makefile: "
            + str(makefile.get("label") or "makefile observe")
        ),
        (
            "makefile sunday: "
            + str(
                compact.get("makefile_sunday_quiet")
                or (
                    str(makefile.get("label") or "makefile observe")
                    + f" · sunday quiet {sunday_bit} (observe · never softens floors)"
                )
            )
        ),
        (
            "venues: "
            + str(venues.get("label") or "venues observe")
        ),
        (
            "venues sunday: "
            + str(
                compact.get("venues_sunday_quiet")
                or (
                    str(venues.get("label") or "venues observe")
                    + f" · sunday quiet {sunday_bit} (observe · never softens floors)"
                )
            )
        ),
        (
            "chicago: "
            + str(chicago.get("label") or "chicago observe")
        ),
        (
            "chicago sunday: "
            + str(
                compact.get("chicago_sunday_quiet")
                or (
                    str(chicago.get("label") or "chicago observe")
                    + f" · sunday quiet {sunday_bit} (observe · never softens floors)"
                )
            )
        ),
        (
            "starve: "
            + str(starve.get("label") or "starve observe")
        ),
        (
            "starve sunday: "
            + str(
                compact.get("starve_sunday_quiet")
                or (
                    str(starve.get("label") or "starve observe")
                    + f" · sunday quiet {sunday_bit} (observe · never softens floors)"
                )
            )
        ),
        (
            "hard-rules: "
            + str(hard_rules.get("label") or "hard-rules observe")
        ),
        (
            "hard-rules sunday: "
            + str(
                compact.get("hard_rules_sunday_quiet")
                or (
                    str(hard_rules.get("label") or "hard-rules observe")
                    + f" · sunday quiet {sunday_bit} (observe · never softens floors)"
                )
            )
        ),

        (
            "swarm: "
            + str(swarm_tip.get("label") or "swarm observe")
        ),
        (
            "swarm sunday: "
            + str(
                compact.get("swarm_tip_sunday_quiet")
                or (
                    str(swarm_tip.get("label") or "swarm observe")
                    + f" · sunday quiet {sunday_bit} (observe · never softens floors)"
                )
            )
        ),
        (
            "expand-tip: "
            + str(expand_tip.get("label") or "expand observe")
        ),
        (
            "expand-tip sunday: "
            + str(
                compact.get("expand_tip_sunday_quiet")
                or (
                    str(expand_tip.get("label") or "expand observe")
                    + f" · sunday quiet {sunday_bit} (observe · never softens floors)"
                )
            )
        ),
        (
            "quiet-tip: "
            + str(quiet_tip.get("label") or "quiet observe")
        ),
        (
            "quiet-tip sunday: "
            + str(
                compact.get("quiet_tip_sunday_quiet")
                or (
                    str(quiet_tip.get("label") or "quiet observe")
                    + f" · sunday quiet {sunday_bit} (observe · never softens floors)"
                )
            )
        ),
        (
            "timer-tip: "
            + str(timer_tip.get("label") or "timer observe")
        ),
        (
            "timer-tip sunday: "
            + str(
                compact.get("timer_tip_sunday_quiet")
                or (
                    str(timer_tip.get("label") or "timer observe")
                    + f" · sunday quiet {sunday_bit} (observe · never softens floors)"
                )
            )
        ),
        (
            "export-tip: "
            + str(export_tip.get("label") or "export observe")
        ),
        (
            "export-tip sunday: "
            + str(
                compact.get("export_tip_sunday_quiet")
                or (
                    str(export_tip.get("label") or "export observe")
                    + f" · sunday quiet {sunday_bit} (observe · never softens floors)"
                )
            )
        ),
        (
            "doctor-tip: "
            + str(doctor_tip.get("label") or "doctor-tip observe")
        ),
        (
            "doctor-tip sunday: "
            + str(
                compact.get("doctor_tip_sunday_quiet")
                or (
                    str(doctor_tip.get("label") or "doctor-tip observe")
                    + f" · sunday quiet {sunday_bit} (observe · never records doctor)"
                )
            )
        ),

        (
            "inventory-tip: "
            + str(inventory_tip.get("label") or "inventory observe")
        ),
        (
            "inventory-tip sunday: "
            + str(
                compact.get("inventory_sunday_quiet")
                or (
                    str(inventory_tip.get("label") or "inventory observe")
                    + f" · sunday quiet {sunday_bit} (observe · never softens floors)"
                )
            )
        ),
        (
            "dual-tip: "
            + str(dual_tip.get("label") or "dual observe")
        ),
        (
            "dual-tip sunday: "
            + str(
                compact.get("dual_tip_sunday_quiet")
                or (
                    str(dual_tip.get("label") or "dual observe")
                    + f" · sunday quiet {sunday_bit} (observe · never enables live)"
                )
            )
        ),
        (
            "hillclimb-tip: "
            + str(hillclimb_tip.get("label") or "hillclimb observe")
        ),
        (
            "hillclimb-tip sunday: "
            + str(
                compact.get("hillclimb_tip_sunday_quiet")
                or (
                    str(hillclimb_tip.get("label") or "hillclimb observe")
                    + f" · sunday quiet {sunday_bit} (observe · never softens floors)"
                )
            )
        ),
        (
            "ruin-tip: "
            + str(ruin_tip.get("label") or "ruin observe")
        ),
        (
            "ruin-tip sunday: "
            + str(
                compact.get("ruin_tip_sunday_quiet")
                or (
                    str(ruin_tip.get("label") or "ruin observe")
                    + f" · sunday quiet {sunday_bit} (observe · never softens floors)"
                )
            )
        ),
        (
            "near-miss-tip: "
            + str(near_miss_tip.get("label") or "near-miss observe")
        ),
        (
            "near-miss-tip sunday: "
            + str(
                compact.get("near_miss_tip_sunday_quiet")
                or (
                    str(near_miss_tip.get("label") or "near-miss observe")
                    + f" · sunday quiet {sunday_bit} (observe · never softens floors)"
                )
            )
        ),
        (
            "helper-tip: "
            + str(helper_tip.get("label") or "helper observe")
        ),
        (
            "helper-tip sunday: "
            + str(
                compact.get("helper_tip_sunday_quiet")
                or (
                    str(helper_tip.get("label") or "helper observe")
                    + f" · sunday quiet {sunday_bit} (observe · never arms)"
                )
            )
        ),
        (
            "hard-stop-tip: "
            + str(hard_stop_tip.get("label") or "hard-stop observe")
        ),
        (
            "hard-stop-tip sunday: "
            + str(
                compact.get("hard_stop_tip_sunday_quiet")
                or (
                    str(hard_stop_tip.get("label") or "hard-stop observe")
                    + f" · sunday quiet {sunday_bit} (observe · never enables live)"
                )
            )
        ),
        (
            "skip-regret-tip: "
            + str(skip_regret_tip.get("label") or "skip-regret observe")
        ),
        (
            "skip-regret-tip sunday: "
            + str(
                compact.get("skip_regret_tip_sunday_quiet")
                or (
                    str(skip_regret_tip.get("label") or "skip-regret observe")
                    + f" · sunday quiet {sunday_bit} (observe · never softens floors)"
                )
            )
        ),
        (
            "eia-tip: "
            + str(eia_tip.get("label") or "eia observe")
        ),
        (
            "eia-tip sunday: "
            + str(
                compact.get("eia_tip_sunday_quiet")
                or (
                    str(eia_tip.get("label") or "eia observe")
                    + f" · sunday quiet {sunday_bit} (observe · never softens floors)"
                )
            )
        ),
        (
            "injury-tip: "
            + str(injury_tip.get("label") or "injury observe")
        ),
        (
            "injury-tip sunday: "
            + str(
                compact.get("injury_tip_sunday_quiet")
                or (
                    str(injury_tip.get("label") or "injury observe")
                    + f" · sunday quiet {sunday_bit} (observe · never softens floors)"
                )
            )
        ),
        (
            "completions-tip: "
            + str(completions_tip.get("label") or "completions observe")
        ),
        (
            "completions-tip sunday: "
            + str(
                compact.get("completions_tip_sunday_quiet")
                or (
                    str(completions_tip.get("label") or "completions observe")
                    + f" · sunday quiet {sunday_bit} (observe · never softens floors)"
                )
            )
        ),
        (
            "toxic-tip: "
            + str(toxic_tip.get("label") or "toxic observe")
        ),
        (
            "toxic-tip sunday: "
            + str(
                compact.get("toxic_tip_sunday_quiet")
                or (
                    str(toxic_tip.get("label") or "toxic observe")
                    + f" · sunday quiet {sunday_bit} (observe · never softens floors)"
                )
            )
        ),
        (
            "calib-tip: "
            + str(calib_tip.get("label") or "calib observe")
        ),
        (
            "calib-tip sunday: "
            + str(
                compact.get("calib_tip_sunday_quiet")
                or (
                    str(calib_tip.get("label") or "calib observe")
                    + f" · sunday quiet {sunday_bit} (observe · never softens floors)"
                )
            )
        ),
        (
            "clv-tip: "
            + str(clv_tip.get("label") or "clv observe")
        ),
        (
            "clv-tip sunday: "
            + str(
                compact.get("clv_tip_sunday_quiet")
                or (
                    str(clv_tip.get("label") or "clv observe")
                    + f" · sunday quiet {sunday_bit} (observe · never softens floors)"
                )
            )
        ),
        (
            "clerk-tip: "
            + str(clerk_tip.get("label") or "clerk observe")
        ),
        (
            "clerk-tip sunday: "
            + str(
                compact.get("clerk_tip_sunday_quiet")
                or (
                    str(clerk_tip.get("label") or "clerk observe")
                    + f" · sunday quiet {sunday_bit} (observe · never softens floors)"
                )
            )
        ),
        (
            "bookkeeper-tip: "
            + str(bookkeeper_tip.get("label") or "bookkeeper observe")
        ),
        (
            "bookkeeper-tip sunday: "
            + str(
                compact.get("bookkeeper_tip_sunday_quiet")
                or (
                    str(bookkeeper_tip.get("label") or "bookkeeper observe")
                    + f" · sunday quiet {sunday_bit} (observe · never softens floors)"
                )
            )
        ),
        (
            f"expand: {expand.get('soft_copy') or expand.get('label') or '—'}"
        ),
        (
            "expand sunday: "
            + (
                "expand=blocked"
                if expand.get("blocked")
                else "expand=ok"
                if expand.get("blocked") is False
                else str(compact.get("expand_label") or "expand=n/a")
            )
            + " · sunday quiet "
            + str(
                sunday.get("quiet_age_label")
                or compact.get("quiet_age_label")
                or "quiet_age=n/a"
            )
            + " (observe · never softens floors)"
        ),
        (
            "floors sunday: "
            + (
                "floors=ok"
                if floors.get("all_ok")
                else "floors=soft"
                if floors.get("all_ok") is False
                else "floors=n/a"
            )
            + " · sunday quiet "
            + str(
                sunday.get("quiet_age_label")
                or compact.get("quiet_age_label")
                or "quiet_age=n/a"
            )
            + " (observe · never softens floors)"
        ),
        f"doctor_age: {doctor_age.get('label') or '—'}",
        (
            f"doctor_fresh={doctor_fresh} "
            f"{compact.get('doctor_label') or ('doctor=fresh' if doctor_fresh else 'doctor=stale' if doctor_fresh is False else 'doctor=n/a')}"
        ),
        (
            "doctor draft: make living-doctor · paste living-ritual-discord "
            "(never auto-posts)"
        ),
        (
            f"ritual_ok={ritual.get('ritual_ok')} exit_ok={ritual.get('exit_ok')} "
            f"floors_ok={ritual.get('floors_ok')} expand_ok={ritual.get('expand_ok')}"
        ),
        f"ritual: {ritual.get('label') or '—'}",
        f"sunday: {sunday.get('label') or '—'}",
        (
            "sunday quiet: "
            + str(
                sunday.get("quiet_age_label")
                or (
                    f"quiet_age={sunday.get('quiet_age')}"
                    if sunday.get("quiet_age")
                    else (
                        compact.get("quiet_age_label")
                        or f"quiet_age={compact.get('quiet_age') or 'n/a'}"
                    )
                )
            )
            + " (observe — never softens floors)"
        ),
        (
            "masters sunday: sunday quiet "
            + str(
                sunday.get("quiet_age_label")
                or compact.get("sunday_quiet_age_label")
                or compact.get("quiet_age_label")
                or "quiet_age=n/a"
            )
            + " (observe)"
        ),
        (
            "masters_sunday_part: "
            + str(
                compact.get("masters_sunday_label")
                or f"masters_sunday={compact.get('quiet_age') or 'n/a'}"
            )
        ),
        (
            f"teller_quiet_nag={bool(teller.get('quiet_nag'))} "
            + str(teller.get("quiet_age_label") or "quiet_age=n/a")
        ),
        f"chicago_today: {board.get('chicago_today')}",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Staff living upgrade status.")
    parser.add_argument(
        "action",
        nargs="?",
        default="text",
        choices=(
            "text", "json", "pager", "priority", "selfcheck",
            "gaps", "inventory", "hillclimb", "ruin", "export", "seed", "pulse",
            "floors", "teller", "expand", "doctor", "l7", "sunday", "ritual-live", "hud",
            "help", "money", "rules", "surfaces", "smoke", "paste", "paper", "makefile",
            "venues", "chicago", "starve", "hard-rules", "swarm", "expand-tip", "quiet-tip", "timer-tip", "export-tip", "doctor-tip", "inventory-tip", "dual-tip", "hillclimb-tip", "ruin-tip", "near-miss-tip", "helper-tip", "hard-stop-tip", "skip-regret-tip", "eia-tip", "injury-tip", "completions-tip", "toxic-tip", "calib-tip", "clv-tip", "clerk-tip", "bookkeeper-tip",
        ),
    )
    parser.add_argument("--root", default=ROOT)
    parser.add_argument(
        "--discord",
        action="store_true",
        help="Paste-ready Discord markdown (gaps/ruin/expand/floors/doctor/l7/ritual-live/hud/money/rules/surfaces/smoke/paste/paper/makefile/venues/chicago/starve/hard-rules/swarm/expand-tip/quiet-tip/timer-tip); never auto-posts.",
    )
    args = parser.parse_args()
    root = args.root
    board = _board(root)

    if args.action == "selfcheck":
        print(json.dumps(desk_living.living_self_check(root), indent=2, sort_keys=True, default=str))
        return 0
    if args.action == "gaps":
        gaps = board.get("dual_control_gaps")
        if not isinstance(gaps, dict):
            gaps = desk_living.dual_control_gaps_page(root)
        if args.discord:
            body = gaps.get("discord") or gaps.get("copy") or ""
            print(body if body else json.dumps(gaps, indent=2, sort_keys=True, default=str))
        elif gaps.get("copy"):
            print(gaps["copy"])
        else:
            print(json.dumps(gaps, indent=2, sort_keys=True, default=str))
        return 2 if gaps.get("page") else 0
    if args.action == "inventory":
        inv = board.get("digest_inventory")
        if not isinstance(inv, dict):
            inv = desk_living.digest_inventory(root)
        print(json.dumps(inv, indent=2, sort_keys=True, default=str))
        return 0
    if args.action == "hillclimb":
        hill = board.get("hillclimb_chip")
        if not isinstance(hill, dict):
            hill = desk_living.hillclimb_chip(root)
        print(json.dumps(hill, indent=2, sort_keys=True, default=str))
        return 0
    if args.action == "ruin":
        ruin = board.get("ruin_drill_page")
        if not isinstance(ruin, dict):
            ruin = desk_living.ruin_drill_page(root)
        if args.discord:
            body = ruin.get("discord") or ruin.get("copy") or ""
            print(body if body else json.dumps(ruin, indent=2, sort_keys=True, default=str))
        elif ruin.get("copy"):
            print(ruin["copy"])
        else:
            print(json.dumps(ruin, indent=2, sort_keys=True, default=str))
        return 0
    if args.action == "export":
        print(json.dumps(desk_living.living_board_export(root), indent=2, sort_keys=True, default=str))
        return 0
    if args.action == "seed":
        print(json.dumps(desk_living.seed_missing_digests(root), indent=2, sort_keys=True, default=str))
        return 0
    if args.action == "pulse":
        from helpers import clerk_pulse
        # Force refresh: clear cadence marker then run.
        marker = os.path.join(root, "helpers", getattr(clerk_pulse, "RUN_MARKER", "clerk_pulse_at.txt"))
        try:
            if os.path.isfile(marker):
                os.remove(marker)
        except OSError:
            pass
        digest = clerk_pulse.refresh_clerks(root)
        chip = desk_living.clerk_pulse_chip(root)
        prio = desk_living.living_priority_snapshot(root=root)
        live = desk_living.ritual_live_labels(root=root)
        live_n = sum(1 for k, v in live.items() if str(k).endswith("_label") and v)
        rails = desk_living.living_guardrails_tip(root=root)
        surfaces = desk_living.living_surface_index(root=root)
        smoke = desk_living.living_staff_smoke(root=root)
        print(json.dumps({
            "paper_only": True,
            "fee_floors_locked": True,
            "may_place_alone": False,
            "refreshed_n": (digest or {}).get("refreshed_n") if isinstance(digest, dict) else None,
            "chip": chip,
            "priority": prio,
            "priority_label": prio.get("label"),
            "ritual_live_n": live_n,
            "ritual_live_ok": live_n >= 40,
            "guardrails_label": rails.get("label"),
            "surfaces_label": surfaces.get("label"),
            "smoke_ok": smoke.get("ok"),
            "smoke_label": smoke.get("label"),
            "note": "Forced clerk pulse refresh — observe digests only.",
        }, indent=2, sort_keys=True, default=str))
        return 0
    if args.action == "floors":
        payload = desk_living.fee_floors_assert(root)
        if args.discord:
            print(payload.get("discord") or payload.get("soft_copy") or payload.get("label") or "—")
        else:
            print(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return 0 if payload.get("all_ok") else 2
    if args.action == "teller":
        print(json.dumps(
            desk_living.teller_living_chip(root, remember=False),
            indent=2, sort_keys=True, default=str,
        ))
        return 0
    if args.action == "expand":
        gate = desk_living.betting_expand_gate(root)
        if args.discord:
            print(
                f"**Betting expand gate** (paper only · never softens floors)\n"
                f"{gate.get('soft_copy') or gate.get('label') or '—'}\n"
                f"_auto_publish=False · live=False_"
            )
        else:
            print(json.dumps(gate, indent=2, sort_keys=True, default=str))
        return 0 if gate.get("allow_betting_expand") else 2
    if args.action == "doctor":
        doc = desk_living.living_doctor(root)
        if args.discord:
            print(doc.get("discord") or doc.get("soft_copy") or doc.get("label") or "—")
        else:
            print(json.dumps(doc, indent=2, sort_keys=True, default=str))
        return 0 if doc.get("ok") else 2
    if args.action == "json":
        compact_j = board.get("compact") if isinstance(board.get("compact"), dict) else {}
        live_j = desk_living.ritual_live_labels(board)
        live_n_j = sum(
            1 for k, v in live_j.items() if str(k).endswith("_label") and v
        )
        prio_j = desk_living.living_priority_snapshot(board)
        hud_j = desk_living.living_hud_summary(board)
        money_j = desk_living.living_money_path_tip(board)
        rails_j = desk_living.living_guardrails_tip(board)
        surfaces_j = desk_living.living_surface_index(board)
        smoke_j = desk_living.living_staff_smoke(board)
        paste_j = desk_living.living_discord_paste_tip(board)
        paper_live_j = desk_living.living_paper_live_tip(board)
        makefile_j = desk_living.living_makefile_index(board)
        venues_j = desk_living.living_venues_tip(board)
        chicago_j = desk_living.living_chicago_tip(board)
        starve_j = desk_living.living_starve_tip(board)
        hard_rules_j = desk_living.living_hard_rules_tip(board)
        swarm_tip_j = desk_living.living_swarm_tip(board)
        expand_tip_j = desk_living.living_expand_tip(board)
        quiet_tip_j = desk_living.living_quiet_tip(board)
        timer_tip_j = desk_living.living_timer_tip(board)
        export_tip_j = desk_living.living_export_tip(board)
        doctor_tip_j = desk_living.living_doctor_tip(board)
        inventory_tip_j = desk_living.living_inventory_tip(board)
        dual_tip_j = desk_living.living_dual_tip(board)
        hillclimb_tip_j = desk_living.living_hillclimb_tip(board)
        ruin_tip_j = desk_living.living_ruin_tip(board)
        near_miss_tip_j = desk_living.living_near_miss_tip(board)
        helper_tip_j = desk_living.living_helper_tip(board)
        hard_stop_tip_j = desk_living.living_hard_stop_tip(board)
        skip_regret_tip_j = desk_living.living_skip_regret_tip(board)
        eia_tip_j = desk_living.living_eia_tip(board)
        injury_tip_j = desk_living.living_injury_tip(board)
        completions_tip_j = desk_living.living_completions_tip(board)
        toxic_tip_j = desk_living.living_toxic_tip(board)
        calib_tip_j = desk_living.living_calib_tip(board)
        clv_tip_j = desk_living.living_clv_tip(board)
        clerk_tip_j = desk_living.living_clerk_tip(board)
        bookkeeper_tip_j = desk_living.living_bookkeeper_tip(board)
        ritual_j = (
            board.get("ritual_observe")
            if isinstance(board.get("ritual_observe"), dict)
            else {}
        )
        doctor_age_j = (
            board.get("doctor_age") if isinstance(board.get("doctor_age"), dict) else {}
        )
        doctor_fresh_j = ritual_j.get("doctor_fresh")
        if doctor_fresh_j is None and doctor_age_j:
            doctor_fresh_j = not bool(doctor_age_j.get("stale"))
        ritual_soft_j = (
            (
                f"**Masters ritual** (paper · floors locked · live=False)\n"
                f"ritual_ok={ritual_j.get('ritual_ok')} "
                f"exit_ok={ritual_j.get('exit_ok')} "
                f"doctor_fresh={ritual_j.get('doctor_fresh')}\n"
                f"{ritual_j.get('label') or 'ritual observe'}\n"
                f"_staff paste only · never auto-posts · never enables live_"
            )
            if ritual_j
            else None
        )
        doctor_soft_j = (
            (
                f"**Living doctor age** (paper · floors locked · live=False)\n"
                f"doctor="
                f"{'fresh' if doctor_fresh_j else 'stale' if doctor_fresh_j is False else 'n/a'} "
                f"doctor_fresh={doctor_fresh_j}\n"
                f"{doctor_age_j.get('label') or 'doctor age'}\n"
                f"ritual draft: make living-ritual-discord\n"
                f"_staff paste only · never auto-posts · never enables live_"
            )
            if ritual_j or doctor_age_j
            else None
        )
        out = {
            "paper_only": True,
            "fee_floors_locked": True,
            "live_orders_enabled": False,
            "compact": board.get("compact"),
            "compact_ritual_ok": compact_j.get("ritual_ok"),
            "compact_ritual_label": compact_j.get("ritual_label"),
            "compact_doctor_fresh": compact_j.get("doctor_fresh"),
            "compact_doctor_label": compact_j.get("doctor_label"),
            "compact_quiet_age": compact_j.get("quiet_age") or (
                f"{(board.get('feature_quiet') or {}).get('age_hours')}h"
                if (board.get("feature_quiet") or {}).get("age_hours") is not None
                else "n/a"
            ),
            "compact_quiet_age_h": compact_j.get("quiet_age_h")
            if compact_j.get("quiet_age_h") is not None
            else (board.get("feature_quiet") or {}).get("age_hours"),
            "compact_quiet_age_label": compact_j.get("quiet_age_label") or (
                f"quiet_age={compact_j.get('quiet_age')}"
                if compact_j.get("quiet_age")
                else (
                    f"quiet_age={(board.get('feature_quiet') or {}).get('age_hours')}h"
                    if (board.get("feature_quiet") or {}).get("age_hours") is not None
                    else "quiet_age=n/a"
                )
            ),
            "quiet_age_h": (board.get("feature_quiet") or {}).get("age_hours"),
            "quiet_age": (
                f"{(board.get('feature_quiet') or {}).get('age_hours')}h"
                if (board.get("feature_quiet") or {}).get("age_hours") is not None
                else "n/a"
            ),
            "quiet_line": (
                "• Feature quiet: quiet="
                + str((board.get("feature_quiet") or {}).get("quiet"))
                + " age="
                + (
                    f"{(board.get('feature_quiet') or {}).get('age_hours')}h"
                    if (board.get("feature_quiet") or {}).get("age_hours") is not None
                    else (
                        str(compact_j.get("quiet_age") or "n/a")
                        if compact_j.get("quiet_age")
                        else "n/a"
                    )
                )
                + " (staff observe — never softens floors)"
            ),
            "quiet_doctor": (
                "quiet="
                + ("yes" if (board.get("feature_quiet") or {}).get("quiet") else "no")
                + (
                    f" age={(board.get('feature_quiet') or {}).get('age_hours')}h"
                    if (board.get("feature_quiet") or {}).get("age_hours") is not None
                    else " age=n/a"
                )
                + " · "
                + str(
                    compact_j.get("doctor_label")
                    or (
                        "doctor=fresh"
                        if doctor_fresh_j
                        else "doctor=stale"
                        if doctor_fresh_j is False
                        else "doctor=n/a"
                    )
                )
                + f" · doctor_fresh={doctor_fresh_j}"
            ),
            "insight_swarm": board.get("insight_swarm"),
            "feature_quiet": board.get("feature_quiet"),
            "feature_quiet_pager": board.get("feature_quiet_pager"),
            "dual_control_chip": board.get("dual_control_chip"),
            "dual_control_gaps": board.get("dual_control_gaps"),
            "hillclimb_chip": board.get("hillclimb_chip"),
            "digest_inventory": board.get("digest_inventory"),
            "ruin_drill_chip": board.get("ruin_drill_chip"),
            "ruin_drill_page": board.get("ruin_drill_page"),
            "fee_floors_assert": board.get("fee_floors_assert"),
            "teller_living": board.get("teller_living"),
            "timer_heartbeat": board.get("timer_heartbeat"),
            "doctor_age": board.get("doctor_age"),
            "doctor_fresh": doctor_fresh_j,
            "ritual_observe": board.get("ritual_observe"),
            "ritual_ok": ritual_j.get("ritual_ok") if ritual_j else None,
            "ritual_exit_ok": ritual_j.get("exit_ok") if ritual_j else None,
            "ritual_soft_copy": ritual_soft_j,
            "doctor_soft_copy": doctor_soft_j,
            "doctor_age_soft_copy": doctor_soft_j,  # alias
            "sunday_packet": board.get("sunday_packet"),
            "sunday_quiet_age": (board.get("sunday_packet") or {}).get("quiet_age")
            if isinstance(board.get("sunday_packet"), dict)
            else None,
            "sunday_quiet_age_label": (
                (board.get("sunday_packet") or {}).get("quiet_age_label")
                if isinstance(board.get("sunday_packet"), dict)
                else None
            ),
            "masters_sunday_quiet": (
                "sunday quiet "
                + str(
                    (board.get("sunday_packet") or {}).get("quiet_age_label")
                    if isinstance(board.get("sunday_packet"), dict)
                    and (board.get("sunday_packet") or {}).get("quiet_age_label")
                    else compact_j.get("sunday_quiet_age_label")
                    or compact_j.get("quiet_age_label")
                    or "quiet_age=n/a"
                )
                + " (observe)"
            ),
            "compact_sunday_quiet_age": compact_j.get("sunday_quiet_age")
            or compact_j.get("quiet_age"),
            "compact_sunday_quiet_age_label": compact_j.get("sunday_quiet_age_label")
            or compact_j.get("quiet_age_label"),
            "compact_masters_sunday_label": compact_j.get("masters_sunday_label")
            or (
                f"masters_sunday={compact_j.get('quiet_age')}"
                if compact_j.get("quiet_age")
                else "masters_sunday=n/a"
            ),
            "compact_masters_sunday_quiet": compact_j.get("masters_sunday_quiet")
            or (
                "sunday quiet "
                + str(
                    compact_j.get("quiet_age_label")
                    or compact_j.get("sunday_quiet_age_label")
                    or "quiet_age=n/a"
                )
                + " (observe)"
            ),
            "compact_expand_sunday_quiet": compact_j.get("expand_sunday_quiet")
            or (
                str(compact_j.get("expand_label") or "expand=n/a")
                + " · sunday quiet "
                + str(compact_j.get("quiet_age_label") or "quiet_age=n/a")
                + " (observe · never softens floors)"
            ),
            "compact_floors_sunday_quiet": compact_j.get("floors_sunday_quiet")
            or (
                "floors=n/a · sunday quiet "
                + str(compact_j.get("quiet_age_label") or "quiet_age=n/a")
                + " (observe · never softens floors)"
            ),
            "compact_ruin_sunday_quiet": compact_j.get("ruin_sunday_quiet")
            or (
                str((board.get("ruin_drill_chip") or {}).get("label") or "ruin observe")
                + " · sunday quiet "
                + str(compact_j.get("quiet_age_label") or "quiet_age=n/a")
                + " (observe · never softens floors)"
            ),
            "digests_sunday_quiet": compact_j.get("digests_sunday_quiet")
            or (
                str((board.get("digest_inventory") or {}).get("label") or "digests observe")
                + " · sunday quiet "
                + str(
                    (board.get("sunday_packet") or {}).get("quiet_age_label")
                    if isinstance(board.get("sunday_packet"), dict)
                    and (board.get("sunday_packet") or {}).get("quiet_age_label")
                    else compact_j.get("quiet_age_label")
                    or "quiet_age=n/a"
                )
                + " (observe · never softens floors)"
            ),
            "fills_sunday_quiet": compact_j.get("fills_sunday_quiet")
            or (
                (
                    f"eligible today {(board.get('completions') or {}).get('eligible_completions_today')}"
                    if isinstance(board.get("completions"), dict)
                    and (board.get("completions") or {}).get("eligible_completions_today")
                    is not None
                    else "eligible fills n/a"
                )
                + " · sunday quiet "
                + str(
                    (board.get("sunday_packet") or {}).get("quiet_age_label")
                    if isinstance(board.get("sunday_packet"), dict)
                    and (board.get("sunday_packet") or {}).get("quiet_age_label")
                    else compact_j.get("quiet_age_label")
                    or "quiet_age=n/a"
                )
                + " (observe · never invents PnL)"
            ),
            "compact_digests_sunday_quiet": compact_j.get("digests_sunday_quiet"),
            "compact_fills_sunday_quiet": compact_j.get("fills_sunday_quiet"),
            "green_sunday_quiet": compact_j.get("green_sunday_quiet")
            or (
                str((board.get("green_day") or {}).get("label") or "green-day observe")
                + " · sunday quiet "
                + str(compact_j.get("quiet_age_label") or "quiet_age=n/a")
                + " (observe)"
            ),
            "bleed_sunday_quiet": compact_j.get("bleed_sunday_quiet")
            or (
                str((board.get("bleed") or {}).get("label") or "bleed observe")
                + " · sunday quiet "
                + str(compact_j.get("quiet_age_label") or "quiet_age=n/a")
                + " (observe · never softens floors)"
            ),
            "clv_sunday_quiet": compact_j.get("clv_sunday_quiet")
            or (
                str(
                    (board.get("clv") or board.get("clv_closer") or {}).get("label")
                    or "CLV observe"
                )
                + " · sunday quiet "
                + str(compact_j.get("quiet_age_label") or "quiet_age=n/a")
                + " (observe)"
            ),
            "timer_sunday_quiet": compact_j.get("timer_sunday_quiet"),
            "calib_sunday_quiet": compact_j.get("calib_sunday_quiet"),
            "compact_green_sunday_quiet": compact_j.get("green_sunday_quiet"),
            "compact_bleed_sunday_quiet": compact_j.get("bleed_sunday_quiet"),
            "compact_clv_sunday_quiet": compact_j.get("clv_sunday_quiet"),
            "compact_timer_sunday_quiet": compact_j.get("timer_sunday_quiet"),
            "compact_calib_sunday_quiet": compact_j.get("calib_sunday_quiet"),
            "queue_sunday_quiet": compact_j.get("queue_sunday_quiet")
            or (
                str((board.get("firm_queue") or {}).get("label") or "queue observe")
                + " · sunday quiet "
                + str(compact_j.get("quiet_age_label") or "quiet_age=n/a")
                + " (observe · never promotes)"
            ),
            "gate_a_sunday_quiet": compact_j.get("gate_a_sunday_quiet")
            or (
                str((board.get("helper_gate_a") or {}).get("label") or "Gate A observe")
                + " · sunday quiet "
                + str(compact_j.get("quiet_age_label") or "quiet_age=n/a")
                + " (observe · never softens floors)"
            ),
            "ai_sunday_quiet": compact_j.get("ai_sunday_quiet")
            or (
                str((board.get("living_ai") or {}).get("label") or "AI observe")
                + " · sunday quiet "
                + str(compact_j.get("quiet_age_label") or "quiet_age=n/a")
                + " (observe · never auto-writes Φ)"
            ),
            "tip_sunday_quiet": compact_j.get("tip_sunday_quiet"),
            "blackout_sunday_quiet": compact_j.get("blackout_sunday_quiet"),
            "injury_sunday_quiet": compact_j.get("injury_sunday_quiet"),
            "compact_queue_sunday_quiet": compact_j.get("queue_sunday_quiet"),
            "compact_gate_a_sunday_quiet": compact_j.get("gate_a_sunday_quiet"),
            "compact_ai_sunday_quiet": compact_j.get("ai_sunday_quiet"),
            "compact_tip_sunday_quiet": compact_j.get("tip_sunday_quiet"),
            "compact_blackout_sunday_quiet": compact_j.get("blackout_sunday_quiet"),
            "compact_injury_sunday_quiet": compact_j.get("injury_sunday_quiet"),
            "empty_sunday_quiet": compact_j.get("empty_sunday_quiet"),
            "near_miss_sunday_quiet": compact_j.get("near_miss_sunday_quiet"),
            "eia_sunday_quiet": compact_j.get("eia_sunday_quiet"),
            "calendar_sunday_quiet": compact_j.get("calendar_sunday_quiet"),
            "pager_sunday_quiet": compact_j.get("pager_sunday_quiet"),
            "books_sunday_quiet": compact_j.get("books_sunday_quiet"),
            "pulse_sunday_quiet": compact_j.get("pulse_sunday_quiet"),
            "dual_sunday_quiet": compact_j.get("dual_sunday_quiet"),
            "compact_empty_sunday_quiet": compact_j.get("empty_sunday_quiet"),
            "compact_near_miss_sunday_quiet": compact_j.get("near_miss_sunday_quiet"),
            "compact_eia_sunday_quiet": compact_j.get("eia_sunday_quiet"),
            "compact_calendar_sunday_quiet": compact_j.get("calendar_sunday_quiet"),
            "compact_pager_sunday_quiet": compact_j.get("pager_sunday_quiet"),
            "compact_books_sunday_quiet": compact_j.get("books_sunday_quiet"),
            "compact_pulse_sunday_quiet": compact_j.get("pulse_sunday_quiet"),
            "compact_dual_sunday_quiet": compact_j.get("dual_sunday_quiet"),
            "skip_reg_sunday_quiet": compact_j.get("skip_reg_sunday_quiet"),
            "compact_skip_reg_sunday_quiet": compact_j.get("skip_reg_sunday_quiet"),
            "hard_stop_sunday_quiet": compact_j.get("hard_stop_sunday_quiet"),
            "compact_hard_stop_sunday_quiet": compact_j.get("hard_stop_sunday_quiet"),
            "distance_sunday_quiet": compact_j.get("distance_sunday_quiet"),
            "compact_distance_sunday_quiet": compact_j.get("distance_sunday_quiet"),
            "quant_sunday_quiet": compact_j.get("quant_sunday_quiet"),
            "compact_quant_sunday_quiet": compact_j.get("quant_sunday_quiet"),
            "report_sunday_quiet": compact_j.get("report_sunday_quiet"),
            "compact_report_sunday_quiet": compact_j.get("report_sunday_quiet"),
            "empty_bee_sunday_quiet": compact_j.get("empty_bee_sunday_quiet"),
            "compact_empty_bee_sunday_quiet": compact_j.get("empty_bee_sunday_quiet"),
            "nm_clerk_sunday_quiet": compact_j.get("nm_clerk_sunday_quiet"),
            "compact_nm_clerk_sunday_quiet": compact_j.get("nm_clerk_sunday_quiet"),
            "hs_clerk_sunday_quiet": compact_j.get("hs_clerk_sunday_quiet"),
            "compact_hs_clerk_sunday_quiet": compact_j.get("hs_clerk_sunday_quiet"),
            "bleed_clerk_sunday_quiet": compact_j.get("bleed_clerk_sunday_quiet"),
            "compact_bleed_clerk_sunday_quiet": compact_j.get("bleed_clerk_sunday_quiet"),
            "skip_twin_sunday_quiet": compact_j.get("skip_twin_sunday_quiet"),
            "compact_skip_twin_sunday_quiet": compact_j.get("skip_twin_sunday_quiet"),
            "clv_closer_sunday_quiet": compact_j.get("clv_closer_sunday_quiet"),
            "compact_clv_closer_sunday_quiet": compact_j.get("clv_closer_sunday_quiet"),
            "tdigest_sunday_quiet": compact_j.get("tdigest_sunday_quiet"),
            "compact_tdigest_sunday_quiet": compact_j.get("tdigest_sunday_quiet"),
            "skips_sunday_quiet": compact_j.get("skips_sunday_quiet"),
            "compact_skips_sunday_quiet": compact_j.get("skips_sunday_quiet"),
            "adapt_sunday_quiet": compact_j.get("adapt_sunday_quiet"),
            "compact_adapt_sunday_quiet": compact_j.get("adapt_sunday_quiet"),
            "teller_sunday_quiet": compact_j.get("teller_sunday_quiet"),
            "compact_teller_sunday_quiet": compact_j.get("teller_sunday_quiet"),
            "quiet_sunday_quiet": compact_j.get("quiet_sunday_quiet"),
            "compact_quiet_sunday_quiet": compact_j.get("quiet_sunday_quiet"),
            "doc_age_sunday_quiet": compact_j.get("doc_age_sunday_quiet"),
            "compact_doc_age_sunday_quiet": compact_j.get("doc_age_sunday_quiet"),
            "ritual_sunday_quiet": compact_j.get("ritual_sunday_quiet"),
            "compact_ritual_sunday_quiet": compact_j.get("ritual_sunday_quiet"),
            "digest_freshness": board.get("digest_freshness"),
            "journal_coverage": board.get("journal_coverage"),
            "monday_pulse": board.get("monday_pulse"),
            "digest_fresh_sunday_quiet": compact_j.get("digest_fresh_sunday_quiet"),
            "journal_sunday_quiet": compact_j.get("journal_sunday_quiet"),
            "monday_sunday_quiet": compact_j.get("monday_sunday_quiet"),
            "compact_digest_fresh_sunday_quiet": compact_j.get("digest_fresh_sunday_quiet"),
            "compact_journal_sunday_quiet": compact_j.get("journal_sunday_quiet"),
            "compact_monday_sunday_quiet": compact_j.get("monday_sunday_quiet"),
            "toxic_fills": board.get("toxic_fills"),
            "adapt_ab": board.get("adapt_ab"),
            "raise_phi_sla": board.get("raise_phi_sla"),
            "toxic_sunday_quiet": compact_j.get("toxic_sunday_quiet"),
            "adapt_ab_sunday_quiet": compact_j.get("adapt_ab_sunday_quiet"),
            "raise_phi_sla_sunday_quiet": compact_j.get("raise_phi_sla_sunday_quiet"),
            "compact_toxic_sunday_quiet": compact_j.get("toxic_sunday_quiet"),
            "compact_adapt_ab_sunday_quiet": compact_j.get("adapt_ab_sunday_quiet"),
            "compact_raise_phi_sla_sunday_quiet": compact_j.get("raise_phi_sla_sunday_quiet"),
            "feature_coverage": board.get("feature_coverage"),
            "chip_catalog": board.get("chip_catalog") or board.get("board_size"),
            "phase2_pulse": board.get("phase2_pulse"),
            "feature_coverage_sunday_quiet": compact_j.get("feature_coverage_sunday_quiet"),
            "chip_catalog_sunday_quiet": compact_j.get("chip_catalog_sunday_quiet"),
            "phase2_pulse_sunday_quiet": compact_j.get("phase2_pulse_sunday_quiet"),
            "compact_feature_coverage_sunday_quiet": compact_j.get("feature_coverage_sunday_quiet"),
            "compact_chip_catalog_sunday_quiet": compact_j.get("chip_catalog_sunday_quiet"),
            "compact_phase2_pulse_sunday_quiet": compact_j.get("phase2_pulse_sunday_quiet"),
            "l7_observe": desk_living.l7_observe_summary(board),
            "l7_observe_label": desk_living.l7_observe_summary(board).get("label"),
            "l7_observe_sunday_quiet": compact_j.get("l7_observe_sunday_quiet"),
            "compact_l7_observe_sunday_quiet": compact_j.get("l7_observe_sunday_quiet"),
            "sunday_twin_coverage": desk_living.sunday_twin_coverage(board),
            "sunday_twin_coverage_label": desk_living.sunday_twin_coverage(board).get("label"),
            "ritual_live_labels": live_j,
            "ritual_live_n": live_n_j,
            "ritual_live_ok": live_n_j >= 40,
            "ritual_live_timer": live_j.get("timer_label"),
            "ritual_live_sunday_quiet": compact_j.get("ritual_live_sunday_quiet"),
            "compact_ritual_live_sunday_quiet": compact_j.get("ritual_live_sunday_quiet"),
            "teller_ritual_live_sunday_quiet": compact_j.get(
                "teller_ritual_live_sunday_quiet"
            ),
            "compact_teller_ritual_live_sunday_quiet": compact_j.get(
                "teller_ritual_live_sunday_quiet"
            ),
            "teller_ritual_live_n": (
                (board.get("teller_living") or {}).get("ritual_live_n")
                if isinstance(board.get("teller_living"), dict)
                else None
            ),
            "priority": prio_j,
            "priority_label": prio_j.get("label"),
            "priority_lines": list(prio_j.get("priority") or []),
            "priority_sunday_quiet": compact_j.get("priority_sunday_quiet"),
            "compact_priority_sunday_quiet": compact_j.get("priority_sunday_quiet"),
            "hud": hud_j,
            "hud_label": hud_j.get("label"),
            "hud_sunday_quiet": compact_j.get("hud_sunday_quiet"),
            "compact_hud_sunday_quiet": compact_j.get("hud_sunday_quiet"),
            "money_path": money_j,
            "money_path_label": money_j.get("label"),
            "money_path_sunday_quiet": compact_j.get("money_path_sunday_quiet"),
            "compact_money_path_sunday_quiet": compact_j.get("money_path_sunday_quiet"),
            "guardrails": rails_j,
            "guardrails_label": rails_j.get("label"),
            "guardrails_sunday_quiet": compact_j.get("guardrails_sunday_quiet"),
            "compact_guardrails_sunday_quiet": compact_j.get("guardrails_sunday_quiet"),
            "surfaces": surfaces_j,
            "surfaces_label": surfaces_j.get("label"),
            "surfaces_sunday_quiet": compact_j.get("surfaces_sunday_quiet"),
            "compact_surfaces_sunday_quiet": compact_j.get("surfaces_sunday_quiet"),
            "smoke": smoke_j,
            "smoke_label": smoke_j.get("label"),
            "smoke_ok": smoke_j.get("ok"),
            "smoke_sunday_quiet": compact_j.get("smoke_sunday_quiet"),
            "compact_smoke_sunday_quiet": compact_j.get("smoke_sunday_quiet"),
            "paste": paste_j,
            "paste_label": paste_j.get("label"),
            "paste_n": paste_j.get("targets_n"),
            "paste_sunday_quiet": compact_j.get("paste_sunday_quiet"),
            "compact_paste_sunday_quiet": compact_j.get("paste_sunday_quiet"),
            "paper_live": paper_live_j,
            "paper_live_label": paper_live_j.get("label"),
            "paper_live_ok": paper_live_j.get("ok"),
            "paper_live_sunday_quiet": compact_j.get("paper_live_sunday_quiet"),
            "compact_paper_live_sunday_quiet": compact_j.get("paper_live_sunday_quiet"),
            "makefile": makefile_j,
            "makefile_label": makefile_j.get("label"),
            "makefile_n": makefile_j.get("targets_n"),
            "makefile_sunday_quiet": compact_j.get("makefile_sunday_quiet"),
            "compact_makefile_sunday_quiet": compact_j.get("makefile_sunday_quiet"),
            "venues": venues_j,
            "venues_label": venues_j.get("label"),
            "venues_ok": venues_j.get("ok"),
            "venues_sunday_quiet": compact_j.get("venues_sunday_quiet"),
            "compact_venues_sunday_quiet": compact_j.get("venues_sunday_quiet"),
            "chicago": chicago_j,
            "chicago_label": chicago_j.get("label"),
            "chicago_sunday_quiet": compact_j.get("chicago_sunday_quiet"),
            "compact_chicago_sunday_quiet": compact_j.get("chicago_sunday_quiet"),
            "starve": starve_j,
            "starve_label": starve_j.get("label"),
            "starve_sunday_quiet": compact_j.get("starve_sunday_quiet"),
            "compact_starve_sunday_quiet": compact_j.get("starve_sunday_quiet"),
            "hard_rules": hard_rules_j,
            "hard_rules_label": hard_rules_j.get("label"),
            "hard_rules_sunday_quiet": compact_j.get("hard_rules_sunday_quiet"),
            "compact_hard_rules_sunday_quiet": compact_j.get("hard_rules_sunday_quiet"),

            "swarm_tip": swarm_tip_j,
            "swarm_tip_label": swarm_tip_j.get("label"),
            "swarm_tip_sunday_quiet": compact_j.get("swarm_tip_sunday_quiet"),
            "compact_swarm_tip_sunday_quiet": compact_j.get("swarm_tip_sunday_quiet"),
            "expand_tip": expand_tip_j,
            "expand_tip_label": expand_tip_j.get("label"),
            "expand_tip_sunday_quiet": compact_j.get("expand_tip_sunday_quiet"),
            "compact_expand_tip_sunday_quiet": compact_j.get("expand_tip_sunday_quiet"),
            "quiet_tip": quiet_tip_j,
            "quiet_tip_label": quiet_tip_j.get("label"),
            "quiet_tip_sunday_quiet": compact_j.get("quiet_tip_sunday_quiet"),
            "compact_quiet_tip_sunday_quiet": compact_j.get("quiet_tip_sunday_quiet"),
            "timer_tip": timer_tip_j,
            "timer_tip_label": timer_tip_j.get("label"),
            "timer_tip_sunday_quiet": compact_j.get("timer_tip_sunday_quiet"),
            "compact_timer_tip_sunday_quiet": compact_j.get("timer_tip_sunday_quiet"),
            "export_tip": export_tip_j,
            "export_tip_label": export_tip_j.get("label"),
            "export_tip_sunday_quiet": compact_j.get("export_tip_sunday_quiet"),
            "compact_export_tip_sunday_quiet": compact_j.get("export_tip_sunday_quiet"),
            "doctor_tip": doctor_tip_j,
            "doctor_tip_label": doctor_tip_j.get("label"),
            "doctor_tip_fresh": doctor_tip_j.get("doctor_fresh"),
            "doctor_tip_sunday_quiet": compact_j.get("doctor_tip_sunday_quiet"),
            "compact_doctor_tip_sunday_quiet": compact_j.get("doctor_tip_sunday_quiet"),
            "inventory_tip": inventory_tip_j,
            "inventory_tip_label": inventory_tip_j.get("label"),
            "inventory_sunday_quiet": compact_j.get("inventory_sunday_quiet"),
            "compact_inventory_sunday_quiet": compact_j.get("inventory_sunday_quiet"),
            "dual_tip": dual_tip_j,
            "dual_tip_label": dual_tip_j.get("label"),
            "dual_tip_sunday_quiet": compact_j.get("dual_tip_sunday_quiet"),
            "compact_dual_tip_sunday_quiet": compact_j.get("dual_tip_sunday_quiet"),
            "hillclimb_tip": hillclimb_tip_j,
            "hillclimb_tip_label": hillclimb_tip_j.get("label"),
            "hillclimb_tip_sunday_quiet": compact_j.get("hillclimb_tip_sunday_quiet"),
            "compact_hillclimb_tip_sunday_quiet": compact_j.get("hillclimb_tip_sunday_quiet"),
            "ruin_tip": ruin_tip_j,
            "ruin_tip_label": ruin_tip_j.get("label"),
            "ruin_tip_sunday_quiet": compact_j.get("ruin_tip_sunday_quiet"),
            "compact_ruin_tip_sunday_quiet": compact_j.get("ruin_tip_sunday_quiet"),
            "near_miss_tip": near_miss_tip_j,
            "near_miss_tip_label": near_miss_tip_j.get("label"),
            "near_miss_tip_sunday_quiet": compact_j.get("near_miss_tip_sunday_quiet"),
            "compact_near_miss_tip_sunday_quiet": compact_j.get("near_miss_tip_sunday_quiet"),
            "helper_tip": helper_tip_j,
            "helper_tip_label": helper_tip_j.get("label"),
            "helper_tip_sunday_quiet": compact_j.get("helper_tip_sunday_quiet"),
            "compact_helper_tip_sunday_quiet": compact_j.get("helper_tip_sunday_quiet"),
            "hard_stop_tip": hard_stop_tip_j,
            "hard_stop_tip_label": hard_stop_tip_j.get("label"),
            "hard_stop_tip_live": hard_stop_tip_j.get("live"),
            "hard_stop_tip_sunday_quiet": compact_j.get("hard_stop_tip_sunday_quiet"),
            "compact_hard_stop_tip_sunday_quiet": compact_j.get("hard_stop_tip_sunday_quiet"),
            "skip_regret_tip": skip_regret_tip_j,
            "skip_regret_tip_label": skip_regret_tip_j.get("label"),
            "skip_regret_tip_sunday_quiet": compact_j.get("skip_regret_tip_sunday_quiet"),
            "compact_skip_regret_tip_sunday_quiet": compact_j.get("skip_regret_tip_sunday_quiet"),
            "eia_tip": eia_tip_j,
            "eia_tip_label": eia_tip_j.get("label"),
            "eia_blocked": eia_tip_j.get("blocked"),
            "eia_tip_sunday_quiet": compact_j.get("eia_tip_sunday_quiet"),
            "compact_eia_tip_sunday_quiet": compact_j.get("eia_tip_sunday_quiet"),
            "injury_tip": injury_tip_j,
            "injury_tip_label": injury_tip_j.get("label"),
            "injury_tip_sunday_quiet": compact_j.get("injury_tip_sunday_quiet"),
            "compact_injury_tip_sunday_quiet": compact_j.get("injury_tip_sunday_quiet"),
            "completions_tip": completions_tip_j,
            "completions_tip_label": completions_tip_j.get("label"),
            "completions_tip_sunday_quiet": compact_j.get("completions_tip_sunday_quiet"),
            "compact_completions_tip_sunday_quiet": compact_j.get("completions_tip_sunday_quiet"),
            "toxic_tip": toxic_tip_j,
            "toxic_tip_label": toxic_tip_j.get("label"),
            "toxic_pass": toxic_tip_j.get("pass"),
            "toxic_tip_sunday_quiet": compact_j.get("toxic_tip_sunday_quiet"),
            "compact_toxic_tip_sunday_quiet": compact_j.get("toxic_tip_sunday_quiet"),
            "calib_tip": calib_tip_j,
            "calib_tip_label": calib_tip_j.get("label"),
            "calib_tip_sunday_quiet": compact_j.get("calib_tip_sunday_quiet"),
            "compact_calib_tip_sunday_quiet": compact_j.get("calib_tip_sunday_quiet"),
            "clv_tip": clv_tip_j,
            "clv_tip_label": clv_tip_j.get("label"),
            "clv_pass": clv_tip_j.get("pass"),
            "clv_tip_sunday_quiet": compact_j.get("clv_tip_sunday_quiet"),
            "compact_clv_tip_sunday_quiet": compact_j.get("clv_tip_sunday_quiet"),
            "clerk_tip": clerk_tip_j,
            "clerk_tip_label": clerk_tip_j.get("label"),
            "clerk_tip_sunday_quiet": compact_j.get("clerk_tip_sunday_quiet"),
            "compact_clerk_tip_sunday_quiet": compact_j.get("clerk_tip_sunday_quiet"),
            "bookkeeper_tip": bookkeeper_tip_j,
            "bookkeeper_tip_label": bookkeeper_tip_j.get("label"),
            "bookkeeper_tip_sunday_quiet": compact_j.get("bookkeeper_tip_sunday_quiet"),
            "compact_bookkeeper_tip_sunday_quiet": compact_j.get("bookkeeper_tip_sunday_quiet"),
            "living_memory_line": (
                (board.get("teller_living") or {}).get("memory_line")
                if isinstance(board.get("teller_living"), dict)
                else None
            ),
            "timer_sunday_quiet": (
                compact_j.get("timer_sunday_quiet")
                or (
                    str(live_j.get("timer_label") or "timer observe")
                    + " · sunday quiet "
                    + str(
                        (board.get("sunday_packet") or {}).get("quiet_age_label")
                        if isinstance(board.get("sunday_packet"), dict)
                        and (board.get("sunday_packet") or {}).get("quiet_age_label")
                        else compact_j.get("quiet_age_label")
                        or "quiet_age=n/a"
                    )
                    + " (observe · never softens floors)"
                )
            ),
            "feature_store": board.get("feature_store"),
            "skip_historian": board.get("skip_historian"),
            "feature_store_sunday_quiet": compact_j.get("feature_store_sunday_quiet"),
            "skip_historian_sunday_quiet": compact_j.get("skip_historian_sunday_quiet"),
            "compact_feature_store_sunday_quiet": compact_j.get("feature_store_sunday_quiet"),
            "compact_skip_historian_sunday_quiet": compact_j.get("skip_historian_sunday_quiet"),
            "ruin_sunday_quiet": (
                str((board.get("ruin_drill_chip") or {}).get("label") or "ruin observe")
                + " · sunday quiet "
                + str(
                    (board.get("sunday_packet") or {}).get("quiet_age_label")
                    if isinstance(board.get("sunday_packet"), dict)
                    and (board.get("sunday_packet") or {}).get("quiet_age_label")
                    else compact_j.get("quiet_age_label")
                    or "quiet_age=n/a"
                )
                + " (observe · never softens floors)"
            ),
            "sunday_quiet_tip": (
                "Sunday quiet tip: "
                + str(
                    (board.get("sunday_packet") or {}).get("quiet_age_label")
                    if isinstance(board.get("sunday_packet"), dict)
                    and (board.get("sunday_packet") or {}).get("quiet_age_label")
                    else compact_j.get("sunday_quiet_age_label")
                    or compact_j.get("quiet_age_label")
                    or "quiet_age=n/a"
                )
                + " · cross-check python3 tools/staff_sunday_packet.py discord "
                "(staff paste · never auto-posts)"
            ),
            "betting_expand_gate": board.get("betting_expand_gate"),
            "expand_sunday_quiet": (
                str(
                    (board.get("betting_expand_gate") or {}).get("label")
                    or (
                        "expand=blocked"
                        if (board.get("betting_expand_gate") or {}).get("blocked")
                        else "expand=ok"
                        if (board.get("betting_expand_gate") or {}).get("blocked") is False
                        else "expand=n/a"
                    )
                )
                + " · sunday quiet "
                + str(
                    (board.get("sunday_packet") or {}).get("quiet_age_label")
                    if isinstance(board.get("sunday_packet"), dict)
                    and (board.get("sunday_packet") or {}).get("quiet_age_label")
                    else compact_j.get("quiet_age_label")
                    or "quiet_age=n/a"
                )
                + " (observe · never softens floors)"
            ),
            "chicago_today": board.get("chicago_today"),
            "chip_catalog": sorted(
                k for k, v in board.items()
                if isinstance(v, dict) and v.get("fee_floors_locked") is True
            ),
        }
        # Flatten every compact *_sunday_quiet twin so new twins never go missing.
        for key, val in compact_j.items():
            if not str(key).endswith("_sunday_quiet"):
                continue
            out.setdefault(key, val)
            out.setdefault(f"compact_{key}", val)
        out["sunday_twins_flat_n"] = sum(
            1
            for k in out
            if str(k).endswith("_sunday_quiet") and not str(k).startswith("compact_")
        )
        print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0
    if args.action == "pager":
        pager = board.get("feature_quiet_pager")
        if not isinstance(pager, dict):
            pager = desk_living.feature_quiet_pager(root)
        if pager.get("page") and pager.get("copy"):
            print(pager["copy"])
        else:
            print(json.dumps({
                "page": False,
                "auto_page": False,
                "fee_floors_locked": True,
                "note": pager.get("note") or "No feature-quiet page.",
            }, indent=2))
        return 0
    if args.action == "priority":
        snap = desk_living.living_priority_snapshot(board)
        if args.discord:
            lines = snap.get("priority") or []
            body = "\n".join(f"• {x}" for x in lines) or "• priority empty"
            print(
                "**Living priority** (paper · floors locked · live=False)\n"
                f"{snap.get('label')}\n"
                f"{body}\n"
                "_staff paste · never auto-posts · never softens floors_"
            )
        else:
            print(json.dumps(snap, indent=2, sort_keys=True, default=str))
        return 0
    if args.action == "sunday":
        cov = desk_living.sunday_twin_coverage(board)
        if args.discord:
            print(
                "**Sunday twin coverage** (paper · floors locked · live=False)\n"
                f"{cov.get('label')}\n"
                f"twins_n={cov.get('twins_n')} fields_n={cov.get('fields_n')}\n"
                "_staff paste · never auto-posts · never softens floors_"
            )
        else:
            print(json.dumps(cov, indent=2, sort_keys=True, default=str))
        return 0 if cov.get("pass") else 2

    if args.action == "ritual-live":
        live = desk_living.ritual_live_labels(board)
        live_n = sum(1 for k, v in live.items() if str(k).endswith("_label") and v)
        compact = board.get("compact") if isinstance(board.get("compact"), dict) else {}
        twin = compact.get("ritual_live_sunday_quiet") or (
            f"ritual live n={live_n} · "
            f"{live.get('digests_label') or 'digests observe'} · "
            f"{live.get('fills_label') or 'fills observe'} · "
            f"{live.get('timer_label') or 'timer observe'} · sunday quiet "
            f"{(board.get('sunday_packet') or {}).get('quiet_age_label') if isinstance(board.get('sunday_packet'), dict) else compact.get('quiet_age_label') or 'quiet_age=n/a'} "
            "(observe · never softens floors)"
        )
        teller = board.get("teller_living") if isinstance(board.get("teller_living"), dict) else {}
        payload = {
            "paper_only": True,
            "fee_floors_locked": True,
            "board_chip": False,
            "ritual_live_n": live_n,
            "ritual_live_ok": live_n >= 40,
            "ritual_live_timer": live.get("timer_label"),
            "ritual_live_sunday_quiet": twin,
            "teller_ritual_live_n": teller.get("ritual_live_n"),
            "teller_ritual_live_ok": teller.get("ritual_live_ok"),
            "teller_memory_line": teller.get("memory_line"),
            "ritual_live_labels": live,
            "note": "Ritual live surface audit — staff paste only; never auto-posts.",
        }
        if args.discord:
            print(
                "**Ritual live** (paper · floors locked · live=False)\n"
                f"{twin}\n"
                f"ritual_live_n={live_n} ok={live_n >= 40} · "
                f"teller_ritual_live_n={teller.get('ritual_live_n')}\n"
                "draft: make living-ritual-discord (staff paste · never auto-posts)\n"
                "_never softens floors · never enables live_"
            )
        else:
            print(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return 0 if live_n >= 40 else 2

    if args.action == "hud":
        hud = desk_living.living_hud_summary(board)
        compact = board.get("compact") if isinstance(board.get("compact"), dict) else {}
        twin = compact.get("hud_sunday_quiet") or (
            f"{hud.get('label') or 'hud observe'} · sunday quiet "
            f"{(board.get('sunday_packet') or {}).get('quiet_age_label') if isinstance(board.get('sunday_packet'), dict) else compact.get('quiet_age_label') or 'quiet_age=n/a'} "
            "(observe · never softens floors)"
        )
        if args.discord:
            print(
                "**Living HUD** (paper · floors locked · live=False)\n"
                f"{twin}\n"
                f"ritual_live_n={hud.get('ritual_live_n')} twins={hud.get('sunday_twins_n')} "
                f"prio_n={hud.get('priority_n')} l7_ok={hud.get('l7_observe_ok')}\n"
                "cmds: make living-hud · living-ritual-live · living-priority "
                "(staff paste · never auto-posts)\n"
                "_never softens floors · never enables live_"
            )
        else:
            out = dict(hud)
            out["hud_sunday_quiet"] = twin
            print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0 if hud.get("ritual_live_ok") and hud.get("l7_observe_ok") else 2

    if args.action == "help":
        print(
            "Living status actions (paper · floors locked · Discord never auto-posts):\n"
            "  text json selfcheck export hud priority ritual-live money rules surfaces smoke paste paper makefile venues chicago starve hard-rules swarm expand-tip quiet-tip timer-tip\n"
            "  floors teller expand doctor l7 sunday pulse gaps inventory\n"
            "  hillclimb ruin seed pager\n"
            "Discord paste: --discord on floors/doctor/l7/sunday/ritual-live/hud/money/rules/surfaces/smoke/paste/paper/makefile/venues/chicago/starve/hard-rules/swarm/expand-tip/quiet-tip/timer-tip/priority\n"
            "Makefile: make living-help"
        )
        return 0

    if args.action == "money":
        tip = desk_living.living_money_path_tip(board)
        compact = board.get("compact") if isinstance(board.get("compact"), dict) else {}
        twin = compact.get("money_path_sunday_quiet") or (
            f"{tip.get('label') or 'money-path observe'} · sunday quiet "
            f"{(board.get('sunday_packet') or {}).get('quiet_age_label') if isinstance(board.get('sunday_packet'), dict) else compact.get('quiet_age_label') or 'quiet_age=n/a'} "
            "(observe · never invents PnL)"
        )
        if args.discord:
            print(
                "**Money-path observe** (paper · floors locked · live=False)\n"
                f"{twin}\n"
                f"fee_ledger_n={tip.get('fee_ledger_n')} complete={tip.get('fee_ledger_complete')} "
                f"floors_ok={tip.get('floors_ok')}\n"
                "_never invents PnL · never softens floors · never auto-posts_"
            )
        else:
            out = dict(tip)
            out["money_path_sunday_quiet"] = twin
            print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0 if tip.get("floors_ok") is not False else 2

    if args.action == "rules":
        tip = desk_living.living_guardrails_tip(board)
        compact = board.get("compact") if isinstance(board.get("compact"), dict) else {}
        twin = compact.get("guardrails_sunday_quiet") or (
            f"{tip.get('label') or 'guardrails observe'} · sunday quiet "
            f"{(board.get('sunday_packet') or {}).get('quiet_age_label') if isinstance(board.get('sunday_packet'), dict) else compact.get('quiet_age_label') or 'quiet_age=n/a'} "
            "(observe · never softens floors)"
        )
        if args.discord:
            floors = tip.get("venue_floors") or {}
            print(
                "**Guardrails observe** (paper · floors locked · live=False)\n"
                f"{twin}\n"
                f"venue floors sports={floors.get('sports')} btc+commodity={floors.get('btc_commodity')} "
                f"inx+dex={floors.get('inx_dex')}\n"
                "_never softens floors · Discord never auto-posts · never enables live_"
            )
        else:
            out = dict(tip)
            out["guardrails_sunday_quiet"] = twin
            print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0 if tip.get("floors_ok") is not False and tip.get("live_orders_enabled") is False else 2

    if args.action == "surfaces":
        tip = desk_living.living_surface_index(board)
        compact = board.get("compact") if isinstance(board.get("compact"), dict) else {}
        twin = compact.get("surfaces_sunday_quiet") or (
            f"{tip.get('label') or 'surfaces observe'} · sunday quiet "
            f"{(board.get('sunday_packet') or {}).get('quiet_age_label') if isinstance(board.get('sunday_packet'), dict) else compact.get('quiet_age_label') or 'quiet_age=n/a'} "
            "(observe · never softens floors)"
        )
        if args.discord:
            print(
                "**Surfaces index** (paper · floors locked · soft-max · live=False)\n"
                f"{twin}\n"
                f"twins_n={tip.get('twins_n')} chips={tip.get('chips_n')}/{tip.get('soft_max')} "
                f"headroom={tip.get('headroom')}\n"
                "_no new board chips · never softens floors · never auto-posts_"
            )
        else:
            out = dict(tip)
            out["surfaces_sunday_quiet"] = twin
            print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0 if not tip.get("over") else 2

    if args.action == "smoke":
        tip = desk_living.living_staff_smoke(board)
        compact = board.get("compact") if isinstance(board.get("compact"), dict) else {}
        twin = compact.get("smoke_sunday_quiet") or (
            f"{tip.get('label') or 'smoke observe'} · sunday quiet "
            f"{(board.get('sunday_packet') or {}).get('quiet_age_label') if isinstance(board.get('sunday_packet'), dict) else compact.get('quiet_age_label') or 'quiet_age=n/a'} "
            "(observe · never softens floors)"
        )
        if args.discord:
            print(
                "**Staff smoke** (paper · floors locked · live=False)\n"
                f"{twin}\n"
                f"ok={tip.get('ok')} floors_ok={tip.get('floors_ok')} "
                f"headroom={tip.get('headroom')} chips={tip.get('chips_n')}/{tip.get('soft_max')}\n"
                "cmds: make living-smoke · living-rules · living-surfaces\n"
                "_never softens floors · never auto-posts · never enables live_"
            )
        else:
            out = dict(tip)
            out["smoke_sunday_quiet"] = twin
            print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0 if tip.get("ok") else 2

    if args.action == "paste":
        tip = desk_living.living_discord_paste_tip(board)
        compact = board.get("compact") if isinstance(board.get("compact"), dict) else {}
        twin = compact.get("paste_sunday_quiet") or (
            f"{tip.get('label') or 'paste observe'} · sunday quiet "
            f"{(board.get('sunday_packet') or {}).get('quiet_age_label') if isinstance(board.get('sunday_packet'), dict) else compact.get('quiet_age_label') or 'quiet_age=n/a'} "
            "(observe · never auto-posts)"
        )
        if args.discord:
            cmds = " · ".join(tip.get("cmds") or [])
            print(
                "**Discord paste index** (paper · floors locked · live=False)\n"
                f"{twin}\n"
                f"targets_n={tip.get('targets_n')} auto_post={tip.get('auto_post')}\n"
                f"cmds: {cmds}\n"
                "_staff paste only · never auto-posts · never softens floors_"
            )
        else:
            out = dict(tip)
            out["paste_sunday_quiet"] = twin
            print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0 if tip.get("auto_post") is False else 2

    if args.action == "paper":
        tip = desk_living.living_paper_live_tip(board)
        compact = board.get("compact") if isinstance(board.get("compact"), dict) else {}
        twin = compact.get("paper_live_sunday_quiet") or (
            f"{tip.get('label') or 'paper-live observe'} · sunday quiet "
            f"{(board.get('sunday_packet') or {}).get('quiet_age_label') if isinstance(board.get('sunday_packet'), dict) else compact.get('quiet_age_label') or 'quiet_age=n/a'} "
            "(observe · never enables live)"
        )
        if args.discord:
            print(
                "**Paper/live assert** (paper · floors locked · live=False)\n"
                f"{twin}\n"
                f"ok={tip.get('ok')} live={tip.get('live_orders_enabled')} "
                f"grok_buys={tip.get('grok_buys')} floors_locked={tip.get('floors_locked')}\n"
                "_never enables live · never softens floors · never auto-posts_"
            )
        else:
            out = dict(tip)
            out["paper_live_sunday_quiet"] = twin
            print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0 if tip.get("ok") else 2

    if args.action == "makefile":
        tip = desk_living.living_makefile_index(board)
        compact = board.get("compact") if isinstance(board.get("compact"), dict) else {}
        twin = compact.get("makefile_sunday_quiet") or (
            f"{tip.get('label') or 'makefile observe'} · sunday quiet "
            f"{(board.get('sunday_packet') or {}).get('quiet_age_label') if isinstance(board.get('sunday_packet'), dict) else compact.get('quiet_age_label') or 'quiet_age=n/a'} "
            "(observe · never softens floors)"
        )
        if args.discord:
            print(
                "**Makefile living index** (paper · floors locked · soft-max · live=False)\n"
                f"{twin}\n"
                f"targets_n={tip.get('targets_n')}\n"
                "cmds: make living-help · living-makefile\n"
                "_observe only · never softens floors · never auto-posts_"
            )
        else:
            out = dict(tip)
            out["makefile_sunday_quiet"] = twin
            print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0 if int(tip.get("targets_n") or 0) > 0 else 2

    if args.action == "venues":
        tip = desk_living.living_venues_tip(board)
        compact = board.get("compact") if isinstance(board.get("compact"), dict) else {}
        twin = compact.get("venues_sunday_quiet") or (
            f"{tip.get('label') or 'venues observe'} · sunday quiet "
            f"{(board.get('sunday_packet') or {}).get('quiet_age_label') if isinstance(board.get('sunday_packet'), dict) else compact.get('quiet_age_label') or 'quiet_age=n/a'} "
            "(observe · never softens floors)"
        )
        if args.discord:
            v = tip.get("venues") or {}
            print(
                "**Venue fee floors** (paper · floors locked · live=False)\n"
                f"{twin}\n"
                f"sports={v.get('sports')} btc+commodity={v.get('btc_commodity')} "
                f"inx+dex={v.get('inx_dex')} ok={tip.get('ok')}\n"
                "_never softens floors · never auto-posts_"
            )
        else:
            out = dict(tip)
            out["venues_sunday_quiet"] = twin
            print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0 if tip.get("ok") else 2

    if args.action == "chicago":
        tip = desk_living.living_chicago_tip(board)
        compact = board.get("compact") if isinstance(board.get("compact"), dict) else {}
        twin = compact.get("chicago_sunday_quiet") or (
            f"{tip.get('label') or 'chicago observe'} · sunday quiet "
            f"{(board.get('sunday_packet') or {}).get('quiet_age_label') if isinstance(board.get('sunday_packet'), dict) else compact.get('quiet_age_label') or 'quiet_age=n/a'} "
            "(observe · never softens floors)"
        )
        if args.discord:
            print(
                "**Chicago day** (paper · floors locked · live=False)\n"
                f"{twin}\n"
                f"chicago_today={tip.get('chicago_today')}\n"
                "_observe only · never softens floors · never auto-posts_"
            )
        else:
            out = dict(tip)
            out["chicago_sunday_quiet"] = twin
            print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0 if tip.get("chicago_today") else 2

    if args.action == "starve":
        tip = desk_living.living_starve_tip(board)
        compact = board.get("compact") if isinstance(board.get("compact"), dict) else {}
        twin = compact.get("starve_sunday_quiet") or (
            f"{tip.get('label') or 'starve observe'} · sunday quiet "
            f"{(board.get('sunday_packet') or {}).get('quiet_age_label') if isinstance(board.get('sunday_packet'), dict) else compact.get('quiet_age_label') or 'quiet_age=n/a'} "
            "(observe · never softens floors)"
        )
        if args.discord:
            print(
                "**Starve rule** (paper · floors locked · live=False)\n"
                f"{twin}\n"
                f"n_min={tip.get('n_min')} factor={tip.get('factor')}\n"
                "_observe only · never rewrites starve · never softens floors_"
            )
        else:
            out = dict(tip)
            out["starve_sunday_quiet"] = twin
            print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0

    if args.action == "hard-rules":
        tip = desk_living.living_hard_rules_tip(board)
        compact = board.get("compact") if isinstance(board.get("compact"), dict) else {}
        twin = compact.get("hard_rules_sunday_quiet") or (
            f"{tip.get('label') or 'hard-rules observe'} · sunday quiet "
            f"{(board.get('sunday_packet') or {}).get('quiet_age_label') if isinstance(board.get('sunday_packet'), dict) else compact.get('quiet_age_label') or 'quiet_age=n/a'} "
            "(observe · never softens floors)"
        )
        if args.discord:
            rules = tip.get("rules") or {}
            print(
                "**Hard rules** (paper · floors locked · live=False)\n"
                f"{twin}\n"
                f"meme_red_lock={rules.get('meme_red_lock_usd')} inx_halt={rules.get('inx_halt_usd')}\n"
                f"kill={rules.get('kill')}\n"
                f"venues={rules.get('venues')}\n"
                "_observe only · never rewrites policy · never softens floors_"
            )
        else:
            out = dict(tip)
            out["hard_rules_sunday_quiet"] = twin
            print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0


    if args.action == "swarm":
        tip = desk_living.living_swarm_tip(board)
        compact = board.get("compact") if isinstance(board.get("compact"), dict) else {}
        twin = compact.get("swarm_tip_sunday_quiet") or (
            f"{tip.get('label') or 'swarm observe'} · sunday quiet "
            f"{(board.get('sunday_packet') or {}).get('quiet_age_label') if isinstance(board.get('sunday_packet'), dict) else compact.get('quiet_age_label') or 'quiet_age=n/a'} "
            "(observe · never softens floors)"
        )
        if args.discord:
            print(
                "**Swarm tip** (paper · floors locked · live=False)\n"
                f"{twin}\n"
                f"insight_n={tip.get('insight_n')} betting_n={tip.get('betting_n')} "
                f"ratio={tip.get('ratio')} pass={tip.get('pass')}\n"
                "_hire ≥3:1 · never softens floors · never auto-posts_"
            )
        else:
            out = dict(tip)
            out["swarm_tip_sunday_quiet"] = twin
            print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0 if tip.get("pass") else 2

    if args.action == "expand-tip":
        tip = desk_living.living_expand_tip(board)
        compact = board.get("compact") if isinstance(board.get("compact"), dict) else {}
        twin = compact.get("expand_tip_sunday_quiet") or (
            f"{tip.get('label') or 'expand observe'} · sunday quiet "
            f"{(board.get('sunday_packet') or {}).get('quiet_age_label') if isinstance(board.get('sunday_packet'), dict) else compact.get('quiet_age_label') or 'quiet_age=n/a'} "
            "(observe · never softens floors)"
        )
        if args.discord:
            print(
                "**Expand tip** (paper · floors locked · live=False)\n"
                f"{twin}\n"
                f"allow={tip.get('allow_betting_expand')} blocked={tip.get('blocked')} "
                f"ratio={tip.get('swarm_ratio')}\n"
                "_paper expand only · never enables live · never softens floors_"
            )
        else:
            out = dict(tip)
            out["expand_tip_sunday_quiet"] = twin
            print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0 if tip.get("blocked") is not True else 2

    if args.action == "quiet-tip":
        tip = desk_living.living_quiet_tip(board)
        compact = board.get("compact") if isinstance(board.get("compact"), dict) else {}
        twin = compact.get("quiet_tip_sunday_quiet") or (
            f"{tip.get('label') or 'quiet observe'} · sunday quiet "
            f"{(board.get('sunday_packet') or {}).get('quiet_age_label') if isinstance(board.get('sunday_packet'), dict) else compact.get('quiet_age_label') or 'quiet_age=n/a'} "
            "(observe · never softens floors)"
        )
        if args.discord:
            print(
                "**Quiet tip** (paper · floors locked · live=False)\n"
                f"{twin}\n"
                f"quiet={tip.get('quiet')} age_h={tip.get('age_hours')} threshold={tip.get('quiet_hours')}\n"
                "_observe only · never softens floors · never auto-posts_"
            )
        else:
            out = dict(tip)
            out["quiet_tip_sunday_quiet"] = twin
            print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0

    if args.action == "timer-tip":
        tip = desk_living.living_timer_tip(board)
        compact = board.get("compact") if isinstance(board.get("compact"), dict) else {}
        twin = compact.get("timer_tip_sunday_quiet") or (
            f"{tip.get('label') or 'timer observe'} · sunday quiet "
            f"{(board.get('sunday_packet') or {}).get('quiet_age_label') if isinstance(board.get('sunday_packet'), dict) else compact.get('quiet_age_label') or 'quiet_age=n/a'} "
            "(observe · never softens floors)"
        )
        if args.discord:
            print(
                "**Timer tip** (paper · floors locked · live=False)\n"
                f"{twin}\n"
                f"alive={tip.get('alive')} age_sec={tip.get('age_sec')}\n"
                "_observe only · never softens floors · never auto-posts_"
            )
        else:
            out = dict(tip)
            out["timer_tip_sunday_quiet"] = twin
            print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0 if tip.get("alive") is not False or tip.get("weekday_alert") is False else 2


    if args.action == "export-tip":
        tip = desk_living.living_export_tip(board)
        compact = board.get("compact") if isinstance(board.get("compact"), dict) else {}
        twin = compact.get("export_tip_sunday_quiet") or (
            f"{tip.get('label') or 'export observe'} · sunday quiet "
            f"{(board.get('sunday_packet') or {}).get('quiet_age_label') if isinstance(board.get('sunday_packet'), dict) else compact.get('quiet_age_label') or 'quiet_age=n/a'} "
            "(observe · never softens floors)"
        )
        if args.discord:
            print(
                "**Export tip** (paper · floors locked · live=False)\n"
                f"{twin}\n"
                f"v={tip.get('export')} twins_n={tip.get('twins_n')} smoke_ok={tip.get('smoke_ok')}\n"
                "cmds: make living-export · living-export-tip\n"
                "_observe only · never softens floors · never auto-posts_"
            )
        else:
            out = dict(tip)
            out["export_tip_sunday_quiet"] = twin
            print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0

    if args.action == "doctor-tip":
        tip = desk_living.living_doctor_tip(board)
        compact = board.get("compact") if isinstance(board.get("compact"), dict) else {}
        twin = compact.get("doctor_tip_sunday_quiet") or (
            f"{tip.get('label') or 'doctor-tip observe'} · sunday quiet "
            f"{(board.get('sunday_packet') or {}).get('quiet_age_label') if isinstance(board.get('sunday_packet'), dict) else compact.get('quiet_age_label') or 'quiet_age=n/a'} "
            "(observe · never records doctor)"
        )
        if args.discord:
            print(
                "**Doctor tip** (paper · floors locked · live=False)\n"
                f"{twin}\n"
                f"fresh={tip.get('doctor_fresh')} stale={tip.get('stale')}\n"
                "cmds: make living-doctor-tip · living-doctor (records)\n"
                "_never records on this tip · never softens floors · never auto-posts_"
            )
        else:
            out = dict(tip)
            out["doctor_tip_sunday_quiet"] = twin
            print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0


    if args.action == "inventory-tip":
        tip = desk_living.living_inventory_tip(board)
        compact = board.get("compact") if isinstance(board.get("compact"), dict) else {}
        twin = compact.get("inventory_sunday_quiet") or (
            f"{tip.get('label') or 'inventory observe'} · sunday quiet "
            f"{(board.get('sunday_packet') or {}).get('quiet_age_label') if isinstance(board.get('sunday_packet'), dict) else compact.get('quiet_age_label') or 'quiet_age=n/a'} "
            "(observe · never softens floors)"
        )
        if args.discord:
            print(
                "**Inventory tip** (paper · floors locked · live=False)\n"
                f"{twin}\n"
                f"present={tip.get('present_n')}/{tip.get('expected_n')} missing={tip.get('missing_n')} pass={tip.get('pass')}\n"
                "_hire clerks first · never softens floors · never auto-posts_"
            )
        else:
            out = dict(tip)
            out["inventory_sunday_quiet"] = twin
            print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0 if tip.get("pass") else 2

    if args.action == "dual-tip":
        tip = desk_living.living_dual_tip(board)
        compact = board.get("compact") if isinstance(board.get("compact"), dict) else {}
        twin = compact.get("dual_tip_sunday_quiet") or (
            f"{tip.get('label') or 'dual observe'} · sunday quiet "
            f"{(board.get('sunday_packet') or {}).get('quiet_age_label') if isinstance(board.get('sunday_packet'), dict) else compact.get('quiet_age_label') or 'quiet_age=n/a'} "
            "(observe · never enables live)"
        )
        if args.discord:
            print(
                "**Dual tip** (paper · floors locked · live=False)\n"
                f"{twin}\n"
                f"signed={tip.get('signed_n')}/{tip.get('items_n')} two_staff={tip.get('two_staff')} arm_ready_paper={tip.get('arm_ready_paper')}\n"
                "_never promotes · never enables live · never softens floors_"
            )
        else:
            out = dict(tip)
            out["dual_tip_sunday_quiet"] = twin
            print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0 if tip.get("live_orders_enabled") is False else 2

    if args.action == "hillclimb-tip":
        tip = desk_living.living_hillclimb_tip(board)
        compact = board.get("compact") if isinstance(board.get("compact"), dict) else {}
        twin = compact.get("hillclimb_tip_sunday_quiet") or (
            f"{tip.get('label') or 'hillclimb observe'} · sunday quiet "
            f"{(board.get('sunday_packet') or {}).get('quiet_age_label') if isinstance(board.get('sunday_packet'), dict) else compact.get('quiet_age_label') or 'quiet_age=n/a'} "
            "(observe · never softens floors)"
        )
        if args.discord:
            print(
                "**Hillclimb tip** (paper · floors locked · live=False)\n"
                f"{twin}\n"
                f"week={tip.get('week')} active={tip.get('active')} kill={tip.get('kill')}\n"
                "_one lever/week · never auto-writes · never softens floors_"
            )
        else:
            out = dict(tip)
            out["hillclimb_tip_sunday_quiet"] = twin
            print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0

    if args.action == "ruin-tip":
        tip = desk_living.living_ruin_tip(board)
        compact = board.get("compact") if isinstance(board.get("compact"), dict) else {}
        twin = compact.get("ruin_tip_sunday_quiet") or (
            f"{tip.get('label') or 'ruin observe'} · sunday quiet "
            f"{(board.get('sunday_packet') or {}).get('quiet_age_label') if isinstance(board.get('sunday_packet'), dict) else compact.get('quiet_age_label') or 'quiet_age=n/a'} "
            "(observe · never softens floors)"
        )
        if args.discord:
            print(
                "**Ruin tip** (paper · floors locked · live=False)\n"
                f"{twin}\n"
                f"active={tip.get('active')} level={tip.get('level')} practiced_month={tip.get('practiced_this_month')}\n"
                "_observe only · never softens floors · never auto-posts_"
            )
        else:
            out = dict(tip)
            out["ruin_tip_sunday_quiet"] = twin
            print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0


    if args.action == "near-miss-tip":
        tip = desk_living.living_near_miss_tip(board)
        compact = board.get("compact") if isinstance(board.get("compact"), dict) else {}
        twin = compact.get("near_miss_tip_sunday_quiet") or (
            f"{tip.get('label') or 'near-miss observe'} · sunday quiet "
            f"{(board.get('sunday_packet') or {}).get('quiet_age_label') if isinstance(board.get('sunday_packet'), dict) else compact.get('quiet_age_label') or 'quiet_age=n/a'} "
            "(observe · never softens floors)"
        )
        if args.discord:
            print(
                "**Near-miss tip** (paper · floors locked · live=False)\n"
                f"{twin}\n"
                f"n={tip.get('n')} labeled={tip.get('labeled_n')} ready={tip.get('promote_ready')} decision={tip.get('decision')}\n"
                "_never auto-promotes · never softens floors · never auto-posts_"
            )
        else:
            out = dict(tip)
            out["near_miss_tip_sunday_quiet"] = twin
            print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0

    if args.action == "helper-tip":
        tip = desk_living.living_helper_tip(board)
        compact = board.get("compact") if isinstance(board.get("compact"), dict) else {}
        twin = compact.get("helper_tip_sunday_quiet") or (
            f"{tip.get('label') or 'helper observe'} · sunday quiet "
            f"{(board.get('sunday_packet') or {}).get('quiet_age_label') if isinstance(board.get('sunday_packet'), dict) else compact.get('quiet_age_label') or 'quiet_age=n/a'} "
            "(observe · never arms)"
        )
        if args.discord:
            print(
                "**Helper tip** (paper · floors locked · live=False)\n"
                f"{twin}\n"
                f"ready={tip.get('ready_n')}/{tip.get('helpers_n')} armed={tip.get('armed_n')} places={tip.get('places_orders')}\n"
                "_never arms · never places · never softens floors_"
            )
        else:
            out = dict(tip)
            out["helper_tip_sunday_quiet"] = twin
            print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0

    if args.action == "hard-stop-tip":
        tip = desk_living.living_hard_stop_tip(board)
        compact = board.get("compact") if isinstance(board.get("compact"), dict) else {}
        twin = compact.get("hard_stop_tip_sunday_quiet") or (
            f"{tip.get('label') or 'hard-stop observe'} · sunday quiet "
            f"{(board.get('sunday_packet') or {}).get('quiet_age_label') if isinstance(board.get('sunday_packet'), dict) else compact.get('quiet_age_label') or 'quiet_age=n/a'} "
            "(observe · never enables live)"
        )
        if args.discord:
            print(
                "**Hard-stop tip** (paper · floors locked · live=False)\n"
                f"{twin}\n"
                f"n={tip.get('n')} ready={tip.get('promote_ready')} live={tip.get('live')}\n"
                "_shadow-only · never enables live · never softens floors_"
            )
        else:
            out = dict(tip)
            out["hard_stop_tip_sunday_quiet"] = twin
            print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0 if tip.get("live") is False else 2

    if args.action == "skip-regret-tip":
        tip = desk_living.living_skip_regret_tip(board)
        compact = board.get("compact") if isinstance(board.get("compact"), dict) else {}
        twin = compact.get("skip_regret_tip_sunday_quiet") or (
            f"{tip.get('label') or 'skip-regret observe'} · sunday quiet "
            f"{(board.get('sunday_packet') or {}).get('quiet_age_label') if isinstance(board.get('sunday_packet'), dict) else compact.get('quiet_age_label') or 'quiet_age=n/a'} "
            "(observe · never softens floors)"
        )
        if args.discord:
            print(
                "**Skip-regret tip** (paper · floors locked · live=False)\n"
                f"{twin}\n"
                f"labeled={tip.get('labeled_n')} decision={tip.get('decision')} loosen={tip.get('loosen_soft_gates')}\n"
                "_never softens floors · never auto-loosens · never auto-posts_"
            )
        else:
            out = dict(tip)
            out["skip_regret_tip_sunday_quiet"] = twin
            print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0


    if args.action == "eia-tip":
        tip = desk_living.living_eia_tip(board)
        compact = board.get("compact") if isinstance(board.get("compact"), dict) else {}
        twin = compact.get("eia_tip_sunday_quiet") or (
            f"{tip.get('label') or 'eia observe'} · sunday quiet "
            f"{(board.get('sunday_packet') or {}).get('quiet_age_label') if isinstance(board.get('sunday_packet'), dict) else compact.get('quiet_age_label') or 'quiet_age=n/a'} "
            "(observe · never softens floors)"
        )
        if args.discord:
            print(
                "**EIA tip** (paper · floors locked · live=False)\n"
                f"{twin}\n"
                f"blocked={tip.get('blocked')} hits={tip.get('hits_n')} window={tip.get('window_min')}m\n"
                "_never softens commodity 0.05 · never enables live · never auto-posts_"
            )
        else:
            out = dict(tip)
            out["eia_tip_sunday_quiet"] = twin
            print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0

    if args.action == "injury-tip":
        tip = desk_living.living_injury_tip(board)
        compact = board.get("compact") if isinstance(board.get("compact"), dict) else {}
        twin = compact.get("injury_tip_sunday_quiet") or (
            f"{tip.get('label') or 'injury observe'} · sunday quiet "
            f"{(board.get('sunday_packet') or {}).get('quiet_age_label') if isinstance(board.get('sunday_packet'), dict) else compact.get('quiet_age_label') or 'quiet_age=n/a'} "
            "(observe · never softens floors)"
        )
        if args.discord:
            print(
                "**Injury tip** (paper · floors locked · live=False)\n"
                f"{twin}\n"
                f"n={tip.get('n')} inbox={tip.get('inbox_n')}\n"
                "_never buys · never waives sports floor · never auto-posts_"
            )
        else:
            out = dict(tip)
            out["injury_tip_sunday_quiet"] = twin
            print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0

    if args.action == "completions-tip":
        tip = desk_living.living_completions_tip(board)
        compact = board.get("compact") if isinstance(board.get("compact"), dict) else {}
        twin = compact.get("completions_tip_sunday_quiet") or (
            f"{tip.get('label') or 'completions observe'} · sunday quiet "
            f"{(board.get('sunday_packet') or {}).get('quiet_age_label') if isinstance(board.get('sunday_packet'), dict) else compact.get('quiet_age_label') or 'quiet_age=n/a'} "
            "(observe · never softens floors)"
        )
        if args.discord:
            print(
                "**Completions tip** (paper · floors locked · live=False)\n"
                f"{twin}\n"
                f"eligible={tip.get('eligible_completions_today')} pnl={tip.get('eligible_pnl_today')} day={tip.get('chicago_day')}\n"
                "_M1 guardrail · never softens floors · never auto-posts_"
            )
        else:
            out = dict(tip)
            out["completions_tip_sunday_quiet"] = twin
            print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0

    if args.action == "toxic-tip":
        tip = desk_living.living_toxic_tip(board)
        compact = board.get("compact") if isinstance(board.get("compact"), dict) else {}
        twin = compact.get("toxic_tip_sunday_quiet") or (
            f"{tip.get('label') or 'toxic observe'} · sunday quiet "
            f"{(board.get('sunday_packet') or {}).get('quiet_age_label') if isinstance(board.get('sunday_packet'), dict) else compact.get('quiet_age_label') or 'quiet_age=n/a'} "
            "(observe · never softens floors)"
        )
        if args.discord:
            print(
                "**Toxic tip** (paper · floors locked · live=False)\n"
                f"{twin}\n"
                f"active={tip.get('active_n')} tracked={tip.get('tracked_n')} pass={tip.get('pass')}\n"
                "_never invents fills · never softens floors · never auto-posts_"
            )
        else:
            out = dict(tip)
            out["toxic_tip_sunday_quiet"] = twin
            print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0 if tip.get("pass") is not False else 2


    if args.action == "calib-tip":
        tip = desk_living.living_calib_tip(board)
        compact = board.get("compact") if isinstance(board.get("compact"), dict) else {}
        twin = compact.get("calib_tip_sunday_quiet") or (
            f"{tip.get('label') or 'calib observe'} · sunday quiet "
            f"{(board.get('sunday_packet') or {}).get('quiet_age_label') if isinstance(board.get('sunday_packet'), dict) else compact.get('quiet_age_label') or 'quiet_age=n/a'} "
            "(observe · never softens floors)"
        )
        if args.discord:
            print(
                "**Calib tip** (paper · floors locked · live=False)\n"
                f"{twin}\n"
                f"tickets={tip.get('tickets_n')} sla_n={tip.get('raise_phi_n')} overdue={tip.get('overdue')} auto_write={tip.get('auto_write_phi')}\n"
                "_never silent Φ write · never softens floors · never auto-posts_"
            )
        else:
            out = dict(tip)
            out["calib_tip_sunday_quiet"] = twin
            print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0

    if args.action == "clv-tip":
        tip = desk_living.living_clv_tip(board)
        compact = board.get("compact") if isinstance(board.get("compact"), dict) else {}
        twin = compact.get("clv_tip_sunday_quiet") or (
            f"{tip.get('label') or 'clv observe'} · sunday quiet "
            f"{(board.get('sunday_packet') or {}).get('quiet_age_label') if isinstance(board.get('sunday_packet'), dict) else compact.get('quiet_age_label') or 'quiet_age=n/a'} "
            "(observe · never softens floors)"
        )
        if args.discord:
            print(
                "**CLV tip** (paper · floors locked · live=False)\n"
                f"{twin}\n"
                f"complete={tip.get('complete')}/{tip.get('n')} rate={tip.get('rate')} pass={tip.get('pass')}\n"
                "_never softens sports 0.06 · never enables live · never auto-posts_"
            )
        else:
            out = dict(tip)
            out["clv_tip_sunday_quiet"] = twin
            print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0 if tip.get("pass") is not False else 2

    if args.action == "clerk-tip":
        tip = desk_living.living_clerk_tip(board)
        compact = board.get("compact") if isinstance(board.get("compact"), dict) else {}
        twin = compact.get("clerk_tip_sunday_quiet") or (
            f"{tip.get('label') or 'clerk observe'} · sunday quiet "
            f"{(board.get('sunday_packet') or {}).get('quiet_age_label') if isinstance(board.get('sunday_packet'), dict) else compact.get('quiet_age_label') or 'quiet_age=n/a'} "
            "(observe · never softens floors)"
        )
        if args.discord:
            print(
                "**Clerk tip** (paper · floors locked · live=False)\n"
                f"{twin}\n"
                f"age={tip.get('age_sec')}s stale={tip.get('stale')} refreshed={tip.get('refreshed_n')}\n"
                "_refreshes digests · never softens floors · never auto-posts_"
            )
        else:
            out = dict(tip)
            out["clerk_tip_sunday_quiet"] = twin
            print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0

    if args.action == "bookkeeper-tip":
        tip = desk_living.living_bookkeeper_tip(board)
        compact = board.get("compact") if isinstance(board.get("compact"), dict) else {}
        twin = compact.get("bookkeeper_tip_sunday_quiet") or (
            f"{tip.get('label') or 'bookkeeper observe'} · sunday quiet "
            f"{(board.get('sunday_packet') or {}).get('quiet_age_label') if isinstance(board.get('sunday_packet'), dict) else compact.get('quiet_age_label') or 'quiet_age=n/a'} "
            "(observe · never softens floors)"
        )
        if args.discord:
            print(
                "**Bookkeeper tip** (paper · floors locked · live=False)\n"
                f"{twin}\n"
                f"fills={tip.get('eligible_completions_today')} pnl={tip.get('eligible_pnl_today')} ledger_complete={tip.get('fee_ledger_complete')}\n"
                "_never invents fills · never softens floors · never auto-posts_"
            )
        else:
            out = dict(tip)
            out["bookkeeper_tip_sunday_quiet"] = twin
            print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0

    if args.action == "l7":
        summary = desk_living.l7_observe_summary(board)
        sunday = board.get("sunday_packet") if isinstance(board.get("sunday_packet"), dict) else {}
        quiet_bit = (
            sunday.get("quiet_age_label")
            or (
                f"quiet_age={sunday.get('quiet_age')}"
                if sunday.get("quiet_age") is not None
                else "quiet_age=n/a"
            )
        )
        label = str(summary.get("label") or "L7 observe pending")
        twin = f"{label} · sunday quiet {quiet_bit} (observe · never softens floors)"
        if args.discord:
            missing = summary.get("missing") or []
            catalog = (
                board.get("chip_catalog")
                if isinstance(board.get("chip_catalog"), dict)
                else board.get("board_size")
            )
            cat_lab = (
                (catalog or {}).get("label")
                if isinstance(catalog, dict)
                else "chip catalog observe"
            )
            print(
                "**L7 observe pulse** (paper · floors locked · live=False)\n"
                f"{twin}\n"
                f"ok={bool(summary.get('ok'))} missing={missing}\n"
                f"catalog={cat_lab}\n"
                "_staff paste · never auto-posts · never softens floors_"
            )
        else:
            print(json.dumps({
                **summary,
                "l7_observe_sunday_quiet": twin,
                "chip_catalog": board.get("chip_catalog") or board.get("board_size"),
            }, indent=2, sort_keys=True, default=str))
        return 0 if summary.get("ok") else 2

    print(_text(board))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
