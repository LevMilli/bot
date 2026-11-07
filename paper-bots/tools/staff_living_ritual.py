#!/usr/bin/env python3
"""
Staff weekly living ritual — gaps, ruin, floors, expand, doctor (never publishes).

Usage (from paper-bots/):
  python3 tools/staff_living_ritual.py
  python3 tools/staff_living_ritual.py --json
  python3 tools/staff_living_ritual.py --discord
  python3 tools/staff_living_ritual.py --observe
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


def quiet_line(payload: dict) -> str:
    """Always-on feature quiet observe line for Discord / --json."""
    quiet = payload.get("feature_quiet") if isinstance(payload.get("feature_quiet"), dict) else {}
    age = quiet.get("age_hours") if quiet else None
    age_s = (
        f"{age}h"
        if age is not None
        else str(payload.get("quiet_age") or "n/a")
    )
    return (
        f"• Feature quiet: quiet={quiet.get('quiet') if quiet else None} age={age_s} "
        f"(staff observe — never softens floors)"
    )


def format_discord(payload: dict) -> str:
    steps = payload.get("steps") if isinstance(payload.get("steps"), dict) else {}
    lines = [
        "**Living weekly ritual** (draft — staff paste only)",
        f"_paper only · floors locked · live={bool(payload.get('live_orders_enabled'))} · auto_publish=False_",
        "",
        f"ritual_ok={payload.get('ritual_ok', payload.get('ok'))} "
        f"exit_ok={payload.get('exit_ok')} "
        f"floors_ok={payload.get('floors_ok')} "
        f"expand_ok={payload.get('expand_ok')} "
        f"doctor_ok={payload.get('doctor_ok')} "
        f"doctor_fresh={payload.get('doctor_fresh')}",
        "",
    ]
    lines.append(quiet_line(payload))
    # Always emit Sunday quiet tip (age=n/a ok) — staff observe only.
    sunday_label = payload.get("sunday_quiet_age_label") or payload.get("quiet_age_label")
    tip_age = sunday_label or f"quiet_age={payload.get('quiet_age') or 'n/a'}"
    lines.append(
        f"• Sunday quiet tip: {tip_age} · cross-check "
        f"`python3 tools/staff_sunday_packet.py discord` "
        f"(staff paste · never auto-posts)"
    )
    lines.append(f"• Masters sunday: sunday quiet {tip_age} (observe · never pages)")
    expand_ok = payload.get("expand_ok")
    expand_bit = (
        "expand=ok"
        if expand_ok
        else "expand=blocked"
        if expand_ok is False
        else "expand=n/a"
    )
    lines.append(
        f"• Expand sunday: {expand_bit} · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    floors_ok = payload.get("floors_ok")
    floors_bit = (
        "floors=ok"
        if floors_ok
        else "floors=soft"
        if floors_ok is False
        else "floors=n/a"
    )
    lines.append(
        f"• Floors sunday: {floors_bit} · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    ruin_label = "ruin observe"
    steps_pre = payload.get("steps") if isinstance(payload.get("steps"), dict) else {}
    ruin_row = steps_pre.get("ruin") if isinstance(steps_pre.get("ruin"), dict) else {}
    if ruin_row.get("label"):
        ruin_label = str(ruin_row.get("label"))
    lines.append(
        f"• Ruin sunday: {ruin_label} · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    gaps_label = "gaps observe"
    gaps_row = steps_pre.get("gaps") if isinstance(steps_pre.get("gaps"), dict) else {}
    if gaps_row.get("label"):
        gaps_label = str(gaps_row.get("label"))
    elif gaps_row.get("copy"):
        gaps_label = "dual-control gaps"
    lines.append(
        f"• Gaps sunday: {gaps_label} · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    lines.append(
        f"• Digests sunday: digests observe · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    lines.append(
        f"• Fills sunday: fills observe · sunday quiet {tip_age} "
        f"(observe · never invents PnL)"
    )
    lines.append(
        f"• Hill sunday: hillclimb none · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    lines.append(
        f"• Swarm sunday: swarm observe · sunday quiet {tip_age} "
        f"(observe)"
    )
    lines.append(
        f"• Green sunday: green-day observe · sunday quiet {tip_age} "
        f"(observe)"
    )
    lines.append(
        f"• Bleed sunday: bleed observe · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    lines.append(
        f"• CLV sunday: CLV observe · sunday quiet {tip_age} "
        f"(observe)"
    )
    timer_alive = payload.get("timer_alive")
    timer_bit = (
        "timer=alive"
        if timer_alive
        else "timer=DEAD"
        if timer_alive is False
        else "timer=n/a"
    )
    lines.append(
        f"• Timer sunday: {timer_bit} · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    lines.append(
        f"• Calib sunday: calib observe · sunday quiet {tip_age} "
        f"(observe · never auto-writes Φ)"
    )
    lines.append(
        f"• Queue sunday: queue observe · sunday quiet {tip_age} "
        f"(observe · never promotes)"
    )
    lines.append(
        f"• Gate A sunday: Gate A observe · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    lines.append(
        f"• AI sunday: AI observe · sunday quiet {tip_age} "
        f"(observe · never auto-writes Φ)"
    )
    lines.append(
        f"• Tip sunday: tip feed observe · sunday quiet {tip_age} "
        f"(observe)"
    )
    lines.append(
        f"• Blackout sunday: blackout observe · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    lines.append(
        f"• Injury sunday: injury observe · sunday quiet {tip_age} "
        f"(observe)"
    )
    lines.append(
        f"• Empty sunday: empty CARD observe · sunday quiet {tip_age} "
        f"(observe)"
    )
    lines.append(
        f"• Near-miss sunday: near-miss observe · sunday quiet {tip_age} "
        f"(observe · never promotes)"
    )
    lines.append(
        f"• EIA sunday: EIA observe · sunday quiet {tip_age} "
        f"(observe)"
    )
    lines.append(
        f"• Calendar sunday: calendar observe · sunday quiet {tip_age} "
        f"(observe)"
    )
    lines.append(
        f"• Pager sunday: pager observe · sunday quiet {tip_age} "
        f"(observe · never auto-pages)"
    )
    lines.append(
        f"• Books sunday: books observe · sunday quiet {tip_age} "
        f"(observe · never invents PnL)"
    )
    lines.append(
        f"• Pulse sunday: pulse observe · sunday quiet {tip_age} "
        f"(observe)"
    )
    lines.append(
        f"• Dual sunday: dual observe · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    lines.append(
        f"• Skip-reg sunday: skip-regret observe · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    lines.append(
        f"• Hard-stop sunday: hard-stop observe · sunday quiet {tip_age} "
        f"(observe · never promotes)"
    )
    lines.append(
        f"• Distance sunday: distance observe · sunday quiet {tip_age} "
        f"(observe)"
    )
    lines.append(
        f"• Quant sunday: quant observe · sunday quiet {tip_age} "
        f"(observe)"
    )
    lines.append(
        f"• Report sunday: report observe · sunday quiet {tip_age} "
        f"(observe · never auto-posts)"
    )
    lines.append(
        f"• Empty-bee sunday: empty bee observe · sunday quiet {tip_age} "
        f"(observe)"
    )
    lines.append(
        f"• NM-clerk sunday: nm clerk observe · sunday quiet {tip_age} "
        f"(observe · never promotes)"
    )
    lines.append(
        f"• HS-clerk sunday: hs clerk observe · sunday quiet {tip_age} "
        f"(observe · never promotes)"
    )
    lines.append(
        f"• Bleed-clerk sunday: bleed clerk observe · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    lines.append(
        f"• Skip-twin sunday: skip-twin observe · sunday quiet {tip_age} "
        f"(observe)"
    )
    lines.append(
        f"• CLV-closer sunday: CLV closer observe · sunday quiet {tip_age} "
        f"(observe)"
    )
    lines.append(
        f"• T-digest sunday: t-digest observe · sunday quiet {tip_age} "
        f"(observe)"
    )
    lines.append(
        f"• Skips sunday: skips observe · sunday quiet {tip_age} "
        f"(observe)"
    )
    lines.append(
        f"• Adapt sunday: adapt observe · sunday quiet {tip_age} "
        f"(observe · never auto-writes Φ)"
    )
    lines.append(
        f"• Teller sunday: teller observe · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    lines.append(
        f"• Quiet sunday: feature quiet observe · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    lines.append(
        f"• Doc-age sunday: doctor age observe · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    lines.append(
        f"• Ritual sunday: ritual observe · sunday quiet {tip_age} "
        f"(observe · never auto-posts)"
    )
    lines.append(
        f"• Digest-fresh sunday: digest fresh observe · sunday quiet {tip_age} "
        f"(observe)"
    )
    lines.append(
        f"• Journals sunday: journals observe · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    lines.append(
        f"• Monday sunday: monday pulse observe · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    lines.append(
        f"• Toxic sunday: toxic fills observe · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    lines.append(
        f"• Adapt-A/B sunday: adapt A/B observe · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    lines.append(
        f"• Raise-Φ-SLA sunday: raise_Φ SLA observe · sunday quiet {tip_age} "
        f"(observe · never auto-writes Φ)"
    )
    lines.append(
        f"• Feature-coverage sunday: feature coverage observe · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    lines.append(
        f"• Chip-catalog sunday: chip catalog observe · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    lines.append(
        f"• Phase2-pulse sunday: phase2 pulse observe · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    lines.append(
        f"• L7-pulse sunday: L7 observe pulse · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    lines.append("")
    for name in ("gaps", "ruin", "floors", "expand", "doctor"):
        row = steps.get(name) if isinstance(steps.get(name), dict) else {}
        if name in ("gaps", "ruin") and row.get("copy"):
            lines.append(row["copy"])
            lines.append("")
        else:
            lines.append(f"• **{name}**: {row.get('label') or '—'}")
    lines.append("")
    lines.append(str(payload.get("note") or "Never invent fills; never soften floors; never enable live."))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Staff weekly living ritual.")
    parser.add_argument("--root", default=ROOT)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--discord", action="store_true")
    parser.add_argument(
        "--observe",
        action="store_true",
        help="Print ritual_observe chip only (never records doctor).",
    )
    args = parser.parse_args()
    root = args.root

    if args.observe:
        chip = desk_living.ritual_observe_chip(root)
        if args.json:
            quiet = desk_living.feature_store_quiet_alert(root)
            age_h = quiet.get("age_hours") if isinstance(quiet, dict) else None
            flat = dict(chip)
            flat["ritual_ok"] = chip.get("ritual_ok")
            flat["exit_ok"] = chip.get("exit_ok")
            flat["floors_ok"] = chip.get("floors_ok")
            flat["expand_ok"] = chip.get("expand_ok")
            flat["doctor_fresh"] = chip.get("doctor_fresh")
            fq = quiet if isinstance(quiet, dict) else {}
            flat["feature_quiet"] = {
                "quiet": fq.get("quiet"),
                "age_hours": fq.get("age_hours"),
                "alert": fq.get("alert"),
            }
            flat["quiet_age_h"] = age_h
            flat["quiet_age"] = f"{age_h}h" if age_h is not None else "n/a"
            flat["quiet_line"] = quiet_line(flat)
            sunday = desk_living.sunday_packet_chip(root)
            flat["sunday_quiet_age"] = (
                sunday.get("quiet_age") if isinstance(sunday, dict) else None
            )
            flat["sunday_quiet_age_label"] = (
                sunday.get("quiet_age_label")
                if isinstance(sunday, dict)
                else None
            ) or f"quiet_age={flat['quiet_age']}"
            flat["sunday_quiet_tip"] = (
                f"Sunday quiet tip: {flat['sunday_quiet_age_label']} · "
                "cross-check python3 tools/staff_sunday_packet.py discord "
                "(staff paste · never auto-posts)"
            )
            flat["masters_sunday_quiet"] = (
                f"sunday quiet {flat['sunday_quiet_age_label']} (observe)"
            )
            expand_bit = (
                "expand=ok"
                if chip.get("expand_ok")
                else "expand=blocked"
                if chip.get("expand_ok") is False
                else "expand=n/a"
            )
            flat["expand_sunday_quiet"] = (
                f"{expand_bit} · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe · never softens floors)"
            )
            floors_bit = (
                "floors=ok"
                if chip.get("floors_ok")
                else "floors=soft"
                if chip.get("floors_ok") is False
                else "floors=n/a"
            )
            flat["floors_sunday_quiet"] = (
                f"{floors_bit} · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe · never softens floors)"
            )
            flat["gaps_sunday_quiet"] = (
                f"gaps observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe · never softens floors)"
            )
            flat["digests_sunday_quiet"] = (
                f"digests observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe · never softens floors)"
            )
            flat["fills_sunday_quiet"] = (
                f"fills observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe · never invents PnL)"
            )
            flat["green_sunday_quiet"] = (
                f"green-day observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe)"
            )
            flat["bleed_sunday_quiet"] = (
                f"bleed observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe · never softens floors)"
            )
            flat["clv_sunday_quiet"] = (
                f"CLV observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe)"
            )
            flat["queue_sunday_quiet"] = (
                f"queue observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe · never promotes)"
            )
            flat["gate_a_sunday_quiet"] = (
                f"Gate A observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe · never softens floors)"
            )
            flat["ai_sunday_quiet"] = (
                f"AI observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe · never auto-writes Φ)"
            )
            flat["tip_sunday_quiet"] = (
                f"tip feed observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe)"
            )
            flat["blackout_sunday_quiet"] = (
                f"blackout observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe · never softens floors)"
            )
            flat["injury_sunday_quiet"] = (
                f"injury observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe)"
            )
            flat["empty_sunday_quiet"] = (
                f"empty CARD observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe)"
            )
            flat["near_miss_sunday_quiet"] = (
                f"near-miss observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe · never promotes)"
            )
            flat["eia_sunday_quiet"] = (
                f"EIA observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe)"
            )
            flat["calendar_sunday_quiet"] = (
                f"calendar observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe)"
            )
            flat["pager_sunday_quiet"] = (
                f"pager observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe · never auto-pages)"
            )
            flat["books_sunday_quiet"] = (
                f"books observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe · never invents PnL)"
            )
            flat["pulse_sunday_quiet"] = (
                f"pulse observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe)"
            )
            flat["dual_sunday_quiet"] = (
                f"dual observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe · never softens floors)"
            )
            flat["skip_reg_sunday_quiet"] = (
                f"skip-regret observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe · never softens floors)"
            )
            flat["hard_stop_sunday_quiet"] = (
                f"hard-stop observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe · never promotes)"
            )
            flat["distance_sunday_quiet"] = (
                f"distance observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe)"
            )
            flat["quant_sunday_quiet"] = (
                f"quant observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe)"
            )
            flat["report_sunday_quiet"] = (
                f"report observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe · never auto-posts)"
            )
            flat["empty_bee_sunday_quiet"] = (
                f"empty bee observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe)"
            )
            flat["nm_clerk_sunday_quiet"] = (
                f"nm clerk observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe · never promotes)"
            )
            flat["hs_clerk_sunday_quiet"] = (
                f"hs clerk observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe · never promotes)"
            )
            flat["bleed_clerk_sunday_quiet"] = (
                f"bleed clerk observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe · never softens floors)"
            )
            flat["skip_twin_sunday_quiet"] = (
                f"skip-twin observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe)"
            )
            flat["clv_closer_sunday_quiet"] = (
                f"CLV closer observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe)"
            )
            flat["tdigest_sunday_quiet"] = (
                f"t-digest observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe)"
            )
            flat["skips_sunday_quiet"] = (
                f"skips observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe)"
            )
            flat["adapt_sunday_quiet"] = (
                f"adapt observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe · never auto-writes Φ)"
            )
            flat["teller_sunday_quiet"] = (
                f"teller observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe · never softens floors)"
            )
            flat["quiet_sunday_quiet"] = (
                f"feature quiet observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe · never softens floors)"
            )
            flat["doc_age_sunday_quiet"] = (
                f"doctor age observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe · never softens floors)"
            )
            flat["ritual_sunday_quiet"] = (
                f"ritual observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe · never auto-posts)"
            )
            flat["digest_fresh_sunday_quiet"] = (
                f"digest fresh observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe)"
            )
            flat["journal_sunday_quiet"] = (
                f"journals observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe · never softens floors)"
            )
            flat["monday_sunday_quiet"] = (
                f"monday pulse observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe · never softens floors)"
            )
            # L7 observe flats (non-sunday)
            dig = desk_living.digest_freshness_chip(root)
            journ = desk_living.journal_coverage_chip(root)
            monday = desk_living.monday_pulse_chip(root)
            flat["digest_freshness"] = dig
            flat["journal_coverage"] = journ
            flat["monday_pulse"] = monday
            flat["toxic_fills"] = desk_living.toxic_fill_chip(root)
            flat["adapt_ab"] = desk_living.adapt_ab_chip(root)
            flat["raise_phi_sla"] = desk_living.raise_phi_sla_chip(root)
            flat["feature_coverage"] = desk_living.feature_coverage_chip(root)
            flat["chip_catalog"] = desk_living.chip_catalog_chip(root)
            flat["phase2_pulse"] = desk_living.phase2_pulse_chip(root)
            _l7 = desk_living.l7_observe_summary(root=root)
            flat["l7_observe_ok"] = _l7.get("ok")
            flat["l7_observe_label"] = _l7.get("label")
            flat["l7_observe_sunday_quiet"] = (
                f"{_l7.get('label') or 'L7 observe pulse'} · sunday quiet "
                f"{flat['sunday_quiet_age_label']} (observe · never softens floors)"
            )
            flat["toxic_sunday_quiet"] = (
                f"toxic fills observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe · never softens floors)"
            )
            flat["adapt_ab_sunday_quiet"] = (
                f"adapt A/B observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe · never softens floors)"
            )
            flat["raise_phi_sla_sunday_quiet"] = (
                f"raise_Φ SLA observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe · never auto-writes Φ)"
            )
            flat["feature_coverage_sunday_quiet"] = (
                f"feature coverage observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe · never softens floors)"
            )
            flat["chip_catalog_sunday_quiet"] = (
                f"chip catalog observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe · never softens floors)"
            )
            flat["phase2_pulse_sunday_quiet"] = (
                f"phase2 pulse observe · sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe · never softens floors)"
            )
            print(json.dumps(flat, indent=2, sort_keys=True, default=str))
        else:
            quiet = desk_living.feature_store_quiet_alert(root)
            age_h = quiet.get("age_hours") if isinstance(quiet, dict) else None
            quiet_age = f"{age_h}h" if age_h is not None else "n/a"
            sunday = desk_living.sunday_packet_chip(root)
            sunday_label = (
                (sunday.get("quiet_age_label") if isinstance(sunday, dict) else None)
                or f"quiet_age={quiet_age}"
            )
            print(chip.get("label") or "ritual observe")
            print(
                f"floors_ok={chip.get('floors_ok')} expand_ok={chip.get('expand_ok')} "
                f"(exit_ok={chip.get('exit_ok')})"
            )
            print(
                f"ritual_ok={chip.get('ritual_ok')} exit_ok={chip.get('exit_ok')} "
                f"floors_ok={chip.get('floors_ok')} expand_ok={chip.get('expand_ok')} "
                f"doctor_fresh={chip.get('doctor_fresh')}"
            )
            print(f"quiet_age={quiet_age}")
            print(
                quiet_line({
                    "feature_quiet": quiet if isinstance(quiet, dict) else {},
                    "quiet_age": quiet_age,
                })
            )
            print(
                f"Sunday quiet tip: {sunday_label} · "
                "cross-check python3 tools/staff_sunday_packet.py discord "
                "(staff paste · never auto-posts)"
            )
            print(f"masters sunday: sunday quiet {sunday_label} (observe)")
            expand_bit = (
                "expand=ok"
                if chip.get("expand_ok")
                else "expand=blocked"
                if chip.get("expand_ok") is False
                else "expand=n/a"
            )
            print(
                f"expand sunday: {expand_bit} · sunday quiet {sunday_label} "
                "(observe · never softens floors)"
            )
            floors_bit = (
                "floors=ok"
                if chip.get("floors_ok")
                else "floors=soft"
                if chip.get("floors_ok") is False
                else "floors=n/a"
            )
            print(
                f"floors sunday: {floors_bit} · sunday quiet {sunday_label} "
                "(observe · never softens floors)"
            )
            print(
                f"ruin sunday: ruin observe · sunday quiet {sunday_label} "
                "(observe · never softens floors)"
            )
            print(
                f"gaps sunday: gaps observe · sunday quiet {sunday_label} "
                "(observe · never softens floors)"
            )
            print(
                f"digests sunday: digests observe · sunday quiet {sunday_label} "
                "(observe · never softens floors)"
            )
            print(
                f"fills sunday: fills observe · sunday quiet {sunday_label} "
                "(observe · never invents PnL)"
            )
            print(
                f"green sunday: green-day observe · sunday quiet {sunday_label} "
                "(observe)"
            )
            print(
                f"bleed sunday: bleed observe · sunday quiet {sunday_label} "
                "(observe · never softens floors)"
            )
            print(
                f"CLV sunday: CLV observe · sunday quiet {sunday_label} "
                "(observe)"
            )
            print(
                f"queue sunday: queue observe · sunday quiet {sunday_label} "
                "(observe · never promotes)"
            )
            print(
                f"Gate A sunday: Gate A observe · sunday quiet {sunday_label} "
                "(observe · never softens floors)"
            )
            print(
                f"AI sunday: AI observe · sunday quiet {sunday_label} "
                "(observe · never auto-writes Φ)"
            )
            print(
                f"tip sunday: tip feed observe · sunday quiet {sunday_label} "
                "(observe)"
            )
            print(
                f"blackout sunday: blackout observe · sunday quiet {sunday_label} "
                "(observe · never softens floors)"
            )
            print(
                f"injury sunday: injury observe · sunday quiet {sunday_label} "
                "(observe)"
            )
            print(
                f"empty sunday: empty CARD observe · sunday quiet {sunday_label} "
                "(observe)"
            )
            print(
                f"near-miss sunday: near-miss observe · sunday quiet {sunday_label} "
                "(observe · never promotes)"
            )
            print(
                f"EIA sunday: EIA observe · sunday quiet {sunday_label} "
                "(observe)"
            )
            print(
                f"calendar sunday: calendar observe · sunday quiet {sunday_label} "
                "(observe)"
            )
            print(
                f"pager sunday: pager observe · sunday quiet {sunday_label} "
                "(observe · never auto-pages)"
            )
            print(
                f"books sunday: books observe · sunday quiet {sunday_label} "
                "(observe · never invents PnL)"
            )
            print(
                f"pulse sunday: pulse observe · sunday quiet {sunday_label} "
                "(observe)"
            )
            print(
                f"dual sunday: dual observe · sunday quiet {sunday_label} "
                "(observe · never softens floors)"
            )
            print(
                f"skip-reg sunday: skip-regret observe · sunday quiet {sunday_label} "
                "(observe · never softens floors)"
            )
            print(
                f"hard-stop sunday: hard-stop observe · sunday quiet {sunday_label} "
                "(observe · never promotes)"
            )
            print(
                f"distance sunday: distance observe · sunday quiet {sunday_label} "
                "(observe)"
            )
            print(
                f"quant sunday: quant observe · sunday quiet {sunday_label} "
                "(observe)"
            )
            print(
                f"report sunday: report observe · sunday quiet {sunday_label} "
                "(observe · never auto-posts)"
            )
            print(
                f"empty-bee sunday: empty bee observe · sunday quiet {sunday_label} "
                "(observe)"
            )
            print(
                f"nm-clerk sunday: nm clerk observe · sunday quiet {sunday_label} "
                "(observe · never promotes)"
            )
            print(
                f"hs-clerk sunday: hs clerk observe · sunday quiet {sunday_label} "
                "(observe · never promotes)"
            )
            print(
                f"bleed-clerk sunday: bleed clerk observe · sunday quiet {sunday_label} "
                "(observe · never softens floors)"
            )
            print(
                f"skip-twin sunday: skip-twin observe · sunday quiet {sunday_label} "
                "(observe)"
            )
            print(
                f"CLV-closer sunday: CLV closer observe · sunday quiet {sunday_label} "
                "(observe)"
            )
            print(
                f"t-digest sunday: t-digest observe · sunday quiet {sunday_label} "
                "(observe)"
            )
            print(
                f"skips sunday: skips observe · sunday quiet {sunday_label} "
                "(observe)"
            )
            print(
                f"adapt sunday: adapt observe · sunday quiet {sunday_label} "
                "(observe · never auto-writes Φ)"
            )
            print(
                f"teller sunday: teller observe · sunday quiet {sunday_label} "
                "(observe · never softens floors)"
            )
            print(
                f"quiet sunday: feature quiet observe · sunday quiet {sunday_label} "
                "(observe · never softens floors)"
            )
            print(
                f"doc-age sunday: doctor age observe · sunday quiet {sunday_label} "
                "(observe · never softens floors)"
            )
            print(
                f"ritual sunday: ritual observe · sunday quiet {sunday_label} "
                "(observe · never auto-posts)"
            )
            dig = desk_living.digest_freshness_chip(root)
            journ = desk_living.journal_coverage_chip(root)
            monday = desk_living.monday_pulse_chip(root)
            print(
                f"digest-fresh sunday: {dig.get('label') or 'digest fresh observe'} · "
                f"sunday quiet {sunday_label} (observe)"
            )
            print(
                f"journals sunday: {journ.get('label') or 'journals observe'} · "
                f"sunday quiet {sunday_label} (observe · never softens floors)"
            )
            print(
                f"monday sunday: {monday.get('label') or 'monday pulse observe'} · "
                f"sunday quiet {sunday_label} (observe · never softens floors)"
            )
            toxic = desk_living.toxic_fill_chip(root)
            adapt_ab = desk_living.adapt_ab_chip(root)
            rps = desk_living.raise_phi_sla_chip(root)
            print(
                f"toxic sunday: {toxic.get('label') or 'toxic fills observe'} · "
                f"sunday quiet {sunday_label} (observe · never softens floors)"
            )
            print(
                f"adapt-A/B sunday: {adapt_ab.get('label') or 'adapt A/B observe'} · "
                f"sunday quiet {sunday_label} (observe · never softens floors)"
            )
            print(
                f"raise-Φ-SLA sunday: {rps.get('label') or 'raise_Φ SLA observe'} · "
                f"sunday quiet {sunday_label} (observe · never auto-writes Φ)"
            )
            feat = desk_living.feature_coverage_chip(root)
            catalog = desk_living.chip_catalog_chip(root)
            p2 = desk_living.phase2_pulse_chip(root)
            print(
                f"feature-coverage sunday: {feat.get('label') or 'feature coverage observe'} · "
                f"sunday quiet {sunday_label} (observe · never softens floors)"
            )
            print(
                f"chip-catalog sunday: {catalog.get('label') or 'chip catalog observe'} · "
                f"sunday quiet {sunday_label} (observe · never softens floors)"
            )
            print(
                f"phase2-pulse sunday: {p2.get('label') or 'phase2 pulse observe'} · "
                f"sunday quiet {sunday_label} (observe · never softens floors)"
            )
            _l7 = desk_living.l7_observe_summary(root=root)
            print(
                f"L7-pulse sunday: {_l7.get('label') or 'L7 observe pulse'} · "
                f"sunday quiet {sunday_label} (observe · never softens floors)"
            )
            print(
                "doctor soft: make living-doctor · draft: make living-ritual-discord "
                "(staff paste · never auto-posts)"
            )
            print(chip.get("note") or "")
            print(f"doctor_fresh={chip.get('doctor_fresh')}")
        return 0 if chip.get("exit_ok") else 2

    steps = [
        ("gaps", desk_living.dual_control_gaps_page(root)),
        ("ruin", desk_living.ruin_drill_page(root)),
        ("floors", desk_living.fee_floors_assert(root)),
        ("expand", desk_living.betting_expand_gate(root)),
        ("doctor", desk_living.living_doctor(root, record=True)),
    ]
    floors_ok = bool(steps[2][1].get("all_ok"))
    expand_ok = not bool(steps[3][1].get("blocked"))
    doctor_ok = bool(steps[4][1].get("ok"))
    exit_ok = floors_ok and expand_ok
    ritual_ok = exit_ok and doctor_ok
    doctor_row = steps[4][1] if len(steps) > 4 else {}
    doctor_fresh = None
    if isinstance(doctor_row, dict):
        ritual_obs = doctor_row.get("ritual_observe")
        if isinstance(ritual_obs, dict) and ritual_obs.get("doctor_fresh") is not None:
            doctor_fresh = bool(ritual_obs.get("doctor_fresh"))
        age = doctor_row.get("doctor_age")
        if doctor_fresh is None and isinstance(age, dict):
            doctor_fresh = not bool(age.get("stale"))
    feature_quiet_raw = desk_living.feature_store_quiet_alert(root)
    fq = feature_quiet_raw if isinstance(feature_quiet_raw, dict) else {}
    feature_quiet = {
        "quiet": fq.get("quiet"),
        "age_hours": fq.get("age_hours"),
        "alert": fq.get("alert"),
    }
    quiet_age_h = feature_quiet.get("age_hours")
    sunday = desk_living.sunday_packet_chip(root)
    sunday_quiet_age_label = None
    if isinstance(sunday, dict) and sunday.get("quiet_age_label"):
        sunday_quiet_age_label = str(sunday.get("quiet_age_label"))
    if not sunday_quiet_age_label:
        sunday_quiet_age_label = (
            f"quiet_age={quiet_age_h}h" if quiet_age_h is not None else "quiet_age=n/a"
        )
    payload = {
        "paper_only": True,
        "fee_floors_locked": True,
        "live_orders_enabled": False,
        "auto_publish": False,
        "steps": {name: row for name, row in steps},
        "ok": ritual_ok,
        "ritual_ok": ritual_ok,
        "exit_ok": exit_ok,
        "floors_ok": floors_ok,
        "expand_ok": expand_ok,
        "doctor_ok": doctor_ok,
        "doctor_fresh": doctor_fresh,
        "feature_quiet": feature_quiet,
        "quiet_age": f"{quiet_age_h}h" if quiet_age_h is not None else "n/a",
        "quiet_age_h": quiet_age_h,
        "quiet_age_label": f"quiet_age={quiet_age_h}h" if quiet_age_h is not None else "quiet_age=n/a",
        "sunday_quiet_age": sunday.get("quiet_age") if isinstance(sunday, dict) else None,
        "sunday_quiet_age_label": sunday_quiet_age_label,
        "note": (
            "Weekly ritual draft — staff reviews gaps/ruin/floors/expand/doctor. "
            "Never invent fills; never soften floors; never enable live."
        ),
    }
    payload["quiet_line"] = quiet_line(payload)
    payload["sunday_quiet_tip"] = (
        f"Sunday quiet tip: {sunday_quiet_age_label} · "
        "cross-check python3 tools/staff_sunday_packet.py discord "
        "(staff paste · never auto-posts)"
    )
    payload["expand_sunday_quiet"] = (
        f"{'expand=ok' if expand_ok else 'expand=blocked' if expand_ok is False else 'expand=n/a'} "
        f"· sunday quiet {sunday_quiet_age_label} "
        "(observe · never softens floors)"
    )
    payload["floors_sunday_quiet"] = (
        f"{'floors=ok' if floors_ok else 'floors=soft' if floors_ok is False else 'floors=n/a'} "
        f"· sunday quiet {sunday_quiet_age_label} "
        "(observe · never softens floors)"
    )
    ruin_step = steps[1][1] if len(steps) > 1 else {}
    payload["ruin_sunday_quiet"] = (
        f"{(ruin_step.get('label') if isinstance(ruin_step, dict) else None) or 'ruin observe'} "
        f"· sunday quiet {sunday_quiet_age_label} "
        "(observe · never softens floors)"
    )
    gaps_step = steps[0][1] if steps else {}
    payload["gaps_sunday_quiet"] = (
        f"{(gaps_step.get('label') if isinstance(gaps_step, dict) else None) or 'gaps observe'} "
        f"· sunday quiet {sunday_quiet_age_label} "
        "(observe · never softens floors)"
    )
    if args.discord:
        print(format_discord(payload))
    elif args.json:
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    else:
        print("Living weekly ritual (paper only · floors locked · live=False)")
        print(
            f"floors_ok={payload['floors_ok']} expand_ok={payload['expand_ok']} "
            f"(exit_ok={payload['exit_ok']})"
        )
        print(payload["quiet_line"])
        print(payload["sunday_quiet_tip"])
        for name, row in steps:
            label = row.get("label") or row.get("copy") or name
            if name in ("gaps", "ruin") and row.get("copy"):
                print(f"\n## {name}\n{row.get('copy')}")
            else:
                print(f"- {name}: {label}")
        print(
            f"\nritual_ok={payload['ritual_ok']} exit_ok={payload['exit_ok']} "
            f"floors_ok={payload['floors_ok']} expand_ok={payload['expand_ok']} "
            f"doctor_ok={payload['doctor_ok']} doctor_fresh={payload.get('doctor_fresh')}"
        )
        print(payload["note"])
    # Fail if floors soft or expand blocked (doctor may still fail on quiet/gaps).
    if not steps[2][1].get("all_ok"):
        return 2
    if steps[3][1].get("blocked"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
