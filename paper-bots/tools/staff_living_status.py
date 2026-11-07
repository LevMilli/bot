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
            "floors", "teller", "expand", "doctor", "l7", "sunday", "ritual-live",
        ),
    )
    parser.add_argument("--root", default=ROOT)
    parser.add_argument(
        "--discord",
        action="store_true",
        help="Paste-ready Discord markdown (gaps/ruin/expand/floors/doctor/l7/ritual-live); never auto-posts.",
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
        print(json.dumps({
            "paper_only": True,
            "fee_floors_locked": True,
            "may_place_alone": False,
            "refreshed_n": (digest or {}).get("refreshed_n") if isinstance(digest, dict) else None,
            "chip": chip,
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
        living = board
        raw: list[str] = []
        fq = living.get("feature_quiet") if isinstance(living.get("feature_quiet"), dict) else {}
        if fq.get("quiet") and fq.get("alert"):
            raw.insert(0, str(fq.get("alert"))[:120])
        timer = living.get("timer_heartbeat") if isinstance(living.get("timer_heartbeat"), dict) else {}
        if timer.get("alive") is False:
            raw.insert(0, str(timer.get("label") or "timer DEAD")[:120])
        swarm = living.get("insight_swarm") if isinstance(living.get("insight_swarm"), dict) else {}
        if swarm.get("pass") is False:
            raw.append(
                f"insight swarm {swarm.get('insight_n')}:{swarm.get('betting_n')} "
                f"(need ≥{swarm.get('min_ratio')}:1)"
            )
        ruin = living.get("ruin_drill_chip") if isinstance(living.get("ruin_drill_chip"), dict) else {}
        if ruin.get("active"):
            raw.insert(0, str(ruin.get("label") or "ruin ACTIVE")[:120])
        elif not ruin.get("practiced_this_month"):
            raw.append("ruin drill: practice soft/hard this Chicago month")
        l7 = desk_living.l7_observe_summary(living)
        if not l7.get("ok"):
            raw.insert(0, str(l7.get("label") or "L7 observe missing")[:120])
        live = desk_living.ritual_live_labels(living)
        live_n = sum(1 for k, v in live.items() if str(k).endswith("_label") and v)
        if live_n < 40:
            raw.insert(0, f"ritual live thin n={live_n} (need ≥40 observe labels)")
        teller = living.get("teller_living") if isinstance(living.get("teller_living"), dict) else {}
        if teller.get("ritual_live_ok") is False:
            raw.append(
                f"teller ritual live thin n={teller.get('ritual_live_n')} (observe)"
            )
        raw.extend([
            "insight swarm ≥3:1 before betting expand",
            "revert last lever if hillclimb kill trips",
            "fee floors locked 0.06/0.05/0.02",
            "make living-ritual-live · staff paste only",
        ])
        print(json.dumps({
            "paper_only": True,
            "fee_floors_locked": True,
            "priority": desk_master.finalize_living_priority(raw),
            "max_n": desk_master.PRIORITY_MAX,
        }, indent=2))
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
