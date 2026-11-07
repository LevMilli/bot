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
    def _pl(key: str, fallback: str) -> str:
        val = payload.get(key)
        return str(val) if val else fallback

    lines.append(
        f"• Digests sunday: {_pl('digests_label', 'digests observe')} · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    lines.append(
        f"• Fills sunday: {_pl('fills_label', 'fills observe')} · sunday quiet {tip_age} "
        f"(observe · never invents PnL)"
    )
    lines.append(
        f"• Hill sunday: {_pl('hill_label', 'hillclimb none')} · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    lines.append(
        f"• Swarm sunday: {_pl('swarm_label', 'swarm observe')} · sunday quiet {tip_age} "
        f"(observe)"
    )
    lines.append(
        f"• Green sunday: {_pl('green_label', 'green-day observe')} · sunday quiet {tip_age} "
        f"(observe)"
    )
    lines.append(
        f"• Bleed sunday: {_pl('bleed_label', 'bleed observe')} · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    lines.append(
        f"• CLV sunday: {_pl('clv_label', 'CLV observe')} · sunday quiet {tip_age} "
        f"(observe)"
    )
    timer_alive = payload.get("timer_alive")
    timer_bit = (
        _pl("timer_label", "")
        or (
            "timer=alive"
            if timer_alive
            else "timer=DEAD"
            if timer_alive is False
            else "timer=n/a"
        )
    )
    lines.append(
        f"• Timer sunday: {timer_bit} · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    lines.append(
        f"• Calib sunday: {_pl('calib_label', 'calib observe')} · sunday quiet {tip_age} "
        f"(observe · never auto-writes Φ)"
    )
    lines.append(
        f"• Queue sunday: {_pl('queue_label', 'queue observe')} · sunday quiet {tip_age} "
        f"(observe · never promotes)"
    )
    lines.append(
        f"• Gate A sunday: {_pl('gate_a_label', 'Gate A observe')} · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    lines.append(
        f"• AI sunday: {_pl('ai_label', 'AI observe')} · sunday quiet {tip_age} "
        f"(observe · never auto-writes Φ)"
    )
    lines.append(
        f"• Tip sunday: {_pl('tip_label', 'tip feed observe')} · sunday quiet {tip_age} "
        f"(observe)"
    )
    lines.append(
        f"• Blackout sunday: {_pl('blackout_label', 'blackout observe')} · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    lines.append(
        f"• Injury sunday: {_pl('injury_label', 'injury observe')} · sunday quiet {tip_age} "
        f"(observe)"
    )
    lines.append(
        f"• Empty sunday: {_pl('empty_label', 'empty CARD observe')} · sunday quiet {tip_age} "
        f"(observe)"
    )
    lines.append(
        f"• Near-miss sunday: {_pl('near_miss_label', 'near-miss observe')} · sunday quiet {tip_age} "
        f"(observe · never promotes)"
    )
    lines.append(
        f"• EIA sunday: {_pl('eia_label', 'EIA observe')} · sunday quiet {tip_age} "
        f"(observe)"
    )
    lines.append(
        f"• Calendar sunday: {_pl('calendar_label', 'calendar observe')} · sunday quiet {tip_age} "
        f"(observe)"
    )
    lines.append(
        f"• Pager sunday: {_pl('pager_label', 'pager observe')} · sunday quiet {tip_age} "
        f"(observe · never auto-pages)"
    )
    lines.append(
        f"• Books sunday: {_pl('books_label', 'books observe')} · sunday quiet {tip_age} "
        f"(observe · never invents PnL)"
    )
    lines.append(
        f"• Pulse sunday: {_pl('pulse_label', 'pulse observe')} · sunday quiet {tip_age} "
        f"(observe)"
    )
    lines.append(
        f"• Dual sunday: {_pl('dual_label', 'dual observe')} · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    lines.append(
        f"• Skip-reg sunday: {_pl('skip_reg_label', 'skip-regret observe')} · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    lines.append(
        f"• Hard-stop sunday: {_pl('hard_stop_label', 'hard-stop observe')} · sunday quiet {tip_age} "
        f"(observe · never promotes)"
    )
    lines.append(
        f"• Distance sunday: {_pl('distance_label', 'distance observe')} · sunday quiet {tip_age} "
        f"(observe)"
    )
    lines.append(
        f"• Quant sunday: {_pl('quant_label', 'quant observe')} · sunday quiet {tip_age} "
        f"(observe)"
    )
    lines.append(
        f"• Report sunday: {_pl('report_label', 'report observe')} · sunday quiet {tip_age} "
        f"(observe · never auto-posts)"
    )
    lines.append(
        f"• Empty-bee sunday: {_pl('empty_bee_label', 'empty bee observe')} · sunday quiet {tip_age} "
        f"(observe)"
    )
    lines.append(
        f"• NM-clerk sunday: {_pl('nm_clerk_label', 'nm clerk observe')} · sunday quiet {tip_age} "
        f"(observe · never promotes)"
    )
    lines.append(
        f"• HS-clerk sunday: {_pl('hs_clerk_label', 'hs clerk observe')} · sunday quiet {tip_age} "
        f"(observe · never promotes)"
    )
    lines.append(
        f"• Bleed-clerk sunday: {_pl('bleed_clerk_label', 'bleed clerk observe')} · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    lines.append(
        f"• Skip-twin sunday: {_pl('skip_twin_label', 'skip-twin observe')} · sunday quiet {tip_age} "
        f"(observe)"
    )
    lines.append(
        f"• CLV-closer sunday: {_pl('clv_closer_label', 'CLV closer observe')} · sunday quiet {tip_age} "
        f"(observe)"
    )
    lines.append(
        f"• T-digest sunday: {_pl('tdigest_label', 't-digest observe')} · sunday quiet {tip_age} "
        f"(observe)"
    )
    lines.append(
        f"• Skips sunday: {_pl('skips_label', 'skips observe')} · sunday quiet {tip_age} "
        f"(observe)"
    )
    lines.append(
        f"• Adapt sunday: {_pl('adapt_label', 'adapt observe')} · sunday quiet {tip_age} "
        f"(observe · never auto-writes Φ)"
    )
    lines.append(
        f"• Teller sunday: {_pl('teller_label', 'teller observe')} · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    lines.append(
        f"• Quiet sunday: {_pl('quiet_label', 'feature quiet observe')} · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    lines.append(
        f"• Doc-age sunday: {_pl('doc_age_label', 'doctor age observe')} · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    lines.append(
        f"• Ritual sunday: {_pl('ritual_label', 'ritual observe')} · sunday quiet {tip_age} "
        f"(observe · never auto-posts)"
    )
    lines.append(
        f"• Digest-fresh sunday: {_pl('digest_fresh_label', 'digest fresh observe')} · sunday quiet {tip_age} "
        f"(observe)"
    )
    lines.append(
        f"• Journals sunday: {_pl('journals_label', 'journals observe')} · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    lines.append(
        f"• Monday sunday: {_pl('monday_label', 'monday pulse observe')} · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    lines.append(
        f"• Toxic sunday: {_pl('toxic_fills_label', 'toxic fills observe')} · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    lines.append(
        f"• Adapt-A/B sunday: {_pl('adapt_ab_label', 'adapt A/B observe')} · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    lines.append(
        f"• Raise-Φ-SLA sunday: {_pl('raise_phi_sla_label', 'raise_Φ SLA observe')} · sunday quiet {tip_age} "
        f"(observe · never auto-writes Φ)"
    )
    lines.append(
        f"• Feature-coverage sunday: {_pl('feature_coverage_label', 'feature coverage observe')} · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    lines.append(
        f"• Chip-catalog sunday: {_pl('chip_catalog_label', 'chip catalog observe')} · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    lines.append(
        f"• Phase2-pulse sunday: {_pl('phase2_pulse_label', 'phase2 pulse observe')} · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    lines.append(
        f"• L7-pulse sunday: {_pl('l7_observe_label', 'L7 observe pulse')} · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    lines.append(
        f"• Feature-store sunday: {_pl('feature_store_label', 'feature store observe')} · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    lines.append(
        f"• Skip-historian sunday: {_pl('skip_historian_label', 'skip historian observe')} · sunday quiet {tip_age} "
        f"(observe · never softens floors)"
    )
    ritual_live_twin = payload.get("ritual_live_sunday_quiet")
    if ritual_live_twin:
        lines.append(f"• Ritual live sunday: {ritual_live_twin}")
    else:
        live_n = sum(
            1
            for k, v in payload.items()
            if str(k).endswith("_label") and v and k not in ("label",)
        )
        lines.append(
            f"• Ritual live sunday: ritual live n={live_n} · "
            f"{_pl('digests_label', 'digests observe')} · "
            f"{_pl('fills_label', 'fills observe')} · "
            f"{_pl('timer_label', 'timer observe')} · sunday quiet {tip_age} "
            f"(observe · never softens floors)"
        )
    sunday_cov = payload.get("sunday_twin_coverage")
    if isinstance(sunday_cov, dict) and sunday_cov.get("label"):
        lines.append(
            f"• Sunday twins sunday: {sunday_cov.get('label')} · sunday quiet {tip_age} "
            f"(observe · never softens floors)"
        )
    teller_twin = payload.get("teller_ritual_live_sunday_quiet")
    if teller_twin:
        lines.append(f"• Teller ritual live sunday: {teller_twin}")
    else:
        teller_n = payload.get("teller_ritual_live_n")
        lines.append(
            f"• Teller ritual live sunday: teller ritual live n="
            f"{teller_n if teller_n is not None else 'n/a'} · sunday quiet {tip_age} "
            f"(observe · never softens floors)"
        )
    prio_twin = payload.get("priority_sunday_quiet")
    if prio_twin:
        lines.append(f"• Priority sunday: {prio_twin}")
    else:
        prio_lab = payload.get("priority_label") or "priority observe"
        lines.append(
            f"• Priority sunday: {prio_lab} · sunday quiet {tip_age} "
            f"(observe · never softens floors)"
        )
    hud_twin = payload.get("hud_sunday_quiet")
    if hud_twin:
        lines.append(f"• HUD sunday: {hud_twin}")
    else:
        hud_lab = payload.get("hud_label") or "hud observe"
        lines.append(
            f"• HUD sunday: {hud_lab} · sunday quiet {tip_age} "
            f"(observe · never softens floors)"
        )
    money_twin = payload.get("money_path_sunday_quiet")
    if money_twin:
        lines.append(f"• Money-path sunday: {money_twin}")
    else:
        money_lab = payload.get("money_path_label") or "money-path observe"
        lines.append(
            f"• Money-path sunday: {money_lab} · sunday quiet {tip_age} "
            f"(observe · never invents PnL)"
        )
    rails_twin = payload.get("guardrails_sunday_quiet")
    if rails_twin:
        lines.append(f"• Guardrails sunday: {rails_twin}")
    else:
        rails_lab = payload.get("guardrails_label") or "guardrails observe"
        lines.append(
            f"• Guardrails sunday: {rails_lab} · sunday quiet {tip_age} "
            f"(observe · never softens floors)"
        )
    surfaces_twin = payload.get("surfaces_sunday_quiet")
    if surfaces_twin:
        lines.append(f"• Surfaces sunday: {surfaces_twin}")
    else:
        surfaces_lab = payload.get("surfaces_label") or "surfaces observe"
        lines.append(
            f"• Surfaces sunday: {surfaces_lab} · sunday quiet {tip_age} "
            f"(observe · never softens floors)"
        )
    smoke_twin = payload.get("smoke_sunday_quiet")
    if smoke_twin:
        lines.append(f"• Smoke sunday: {smoke_twin}")
    else:
        smoke_lab = payload.get("smoke_label") or "smoke observe"
        lines.append(
            f"• Smoke sunday: {smoke_lab} · sunday quiet {tip_age} "
            f"(observe · never softens floors)"
        )
    paste_twin = payload.get("paste_sunday_quiet")
    if paste_twin:
        lines.append(f"• Paste sunday: {paste_twin}")
    else:
        paste_lab = payload.get("paste_label") or "paste observe"
        lines.append(
            f"• Paste sunday: {paste_lab} · sunday quiet {tip_age} "
            f"(observe · never auto-posts)"
        )
    paper_twin = payload.get("paper_live_sunday_quiet")
    if paper_twin:
        lines.append(f"• Paper-live sunday: {paper_twin}")
    else:
        paper_lab = payload.get("paper_live_label") or "paper-live observe"
        lines.append(
            f"• Paper-live sunday: {paper_lab} · sunday quiet {tip_age} "
            f"(observe · never enables live)"
        )
    makefile_twin = payload.get("makefile_sunday_quiet")
    if makefile_twin:
        lines.append(f"• Makefile sunday: {makefile_twin}")
    else:
        makefile_lab = payload.get("makefile_label") or "makefile observe"
        lines.append(
            f"• Makefile sunday: {makefile_lab} · sunday quiet {tip_age} "
            f"(observe · never softens floors)"
        )
    venues_twin = payload.get("venues_sunday_quiet")
    if venues_twin:
        lines.append(f"• Venues sunday: {venues_twin}")
    else:
        venues_lab = payload.get("venues_label") or "venues observe"
        lines.append(
            f"• Venues sunday: {venues_lab} · sunday quiet {tip_age} "
            f"(observe · never softens floors)"
        )
    chicago_twin = payload.get("chicago_sunday_quiet")
    if chicago_twin:
        lines.append(f"• Chicago sunday: {chicago_twin}")
    else:
        chicago_lab = payload.get("chicago_label") or "chicago observe"
        lines.append(
            f"• Chicago sunday: {chicago_lab} · sunday quiet {tip_age} "
            f"(observe · never softens floors)"
        )
    starve_twin = payload.get("starve_sunday_quiet")
    if starve_twin:
        lines.append(f"• Starve sunday: {starve_twin}")
    else:
        starve_lab = payload.get("starve_label") or "starve observe"
        lines.append(
            f"• Starve sunday: {starve_lab} · sunday quiet {tip_age} "
            f"(observe · never softens floors)"
        )
    hard_rules_twin = payload.get("hard_rules_sunday_quiet")
    if hard_rules_twin:
        lines.append(f"• Hard-rules sunday: {hard_rules_twin}")
    else:
        hard_rules_lab = payload.get("hard_rules_label") or "hard-rules observe"
        lines.append(
            f"• Hard-rules sunday: {hard_rules_lab} · sunday quiet {tip_age} "
            f"(observe · never softens floors)"
        )
    swarm_tip_twin = payload.get("swarm_tip_sunday_quiet")
    if swarm_tip_twin:
        lines.append(f"• Swarm-tip sunday: {swarm_tip_twin}")
    else:
        swarm_tip_lab = payload.get("swarm_tip_label") or "swarm observe"
        lines.append(
            f"• Swarm-tip sunday: {swarm_tip_lab} · sunday quiet {tip_age} "
            f"(observe · never softens floors)"
        )
    expand_tip_twin = payload.get("expand_tip_sunday_quiet")
    if expand_tip_twin:
        lines.append(f"• Expand-tip sunday: {expand_tip_twin}")
    else:
        expand_tip_lab = payload.get("expand_tip_label") or "expand observe"
        lines.append(
            f"• Expand-tip sunday: {expand_tip_lab} · sunday quiet {tip_age} "
            f"(observe · never softens floors)"
        )
    quiet_tip_twin = payload.get("quiet_tip_sunday_quiet")
    if quiet_tip_twin:
        lines.append(f"• Quiet-tip sunday: {quiet_tip_twin}")
    else:
        quiet_tip_lab = payload.get("quiet_tip_label") or "quiet observe"
        lines.append(
            f"• Quiet-tip sunday: {quiet_tip_lab} · sunday quiet {tip_age} "
            f"(observe · never softens floors)"
        )
    timer_tip_twin = payload.get("timer_tip_sunday_quiet")
    if timer_tip_twin:
        lines.append(f"• Timer-tip sunday: {timer_tip_twin}")
    else:
        timer_tip_lab = payload.get("timer_tip_label") or "timer observe"
        lines.append(
            f"• Timer-tip sunday: {timer_tip_lab} · sunday quiet {tip_age} "
            f"(observe · never softens floors)"
        )
    export_tip_twin = payload.get("export_tip_sunday_quiet")
    if export_tip_twin:
        lines.append(f"• Export-tip sunday: {export_tip_twin}")
    else:
        export_tip_lab = payload.get("export_tip_label") or "export observe"
        lines.append(
            f"• Export-tip sunday: {export_tip_lab} · sunday quiet {tip_age} "
            f"(observe · never softens floors)"
        )
    doctor_tip_twin = payload.get("doctor_tip_sunday_quiet")
    if doctor_tip_twin:
        lines.append(f"• Doctor-tip sunday: {doctor_tip_twin}")
    else:
        doctor_tip_lab = payload.get("doctor_tip_label") or "doctor-tip observe"
        lines.append(
            f"• Doctor-tip sunday: {doctor_tip_lab} · sunday quiet {tip_age} "
            f"(observe · never records doctor)"
        )
    inventory_tip_twin = payload.get("inventory_sunday_quiet") or payload.get("inventory_tip_sunday_quiet")
    if inventory_tip_twin:
        lines.append(f"• Inventory-tip sunday: {inventory_tip_twin}")
    else:
        inventory_tip_lab = payload.get("inventory_tip_label") or "inventory observe"
        lines.append(
            f"• Inventory-tip sunday: {inventory_tip_lab} · sunday quiet {tip_age} "
            f"(observe · never softens floors)"
        )
    dual_tip_twin = payload.get("dual_tip_sunday_quiet")
    if dual_tip_twin:
        lines.append(f"• Dual-tip sunday: {dual_tip_twin}")
    else:
        dual_tip_lab = payload.get("dual_tip_label") or "dual observe"
        lines.append(
            f"• Dual-tip sunday: {dual_tip_lab} · sunday quiet {tip_age} "
            f"(observe · never enables live)"
        )
    hillclimb_tip_twin = payload.get("hillclimb_tip_sunday_quiet")
    if hillclimb_tip_twin:
        lines.append(f"• Hillclimb-tip sunday: {hillclimb_tip_twin}")
    else:
        hillclimb_tip_lab = payload.get("hillclimb_tip_label") or "hillclimb observe"
        lines.append(
            f"• Hillclimb-tip sunday: {hillclimb_tip_lab} · sunday quiet {tip_age} "
            f"(observe · never softens floors)"
        )
    ruin_tip_twin = payload.get("ruin_tip_sunday_quiet")
    if ruin_tip_twin:
        lines.append(f"• Ruin-tip sunday: {ruin_tip_twin}")
    else:
        ruin_tip_lab = payload.get("ruin_tip_label") or "ruin observe"
        lines.append(
            f"• Ruin-tip sunday: {ruin_tip_lab} · sunday quiet {tip_age} "
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
            flat["feature_store"] = desk_living.feature_store_coverage(root)
            flat["skip_historian"] = desk_living.skip_historian_chip(root)
            flat["feature_store_sunday_quiet"] = (
                f"feature store n={flat['feature_store'].get('n')} "
                f"buys={flat['feature_store'].get('buys')} "
                f"skips={flat['feature_store'].get('skips')} · sunday quiet "
                f"{flat['sunday_quiet_age_label']} (observe · never softens floors)"
            )
            flat["skip_historian_sunday_quiet"] = (
                f"{(flat['skip_historian'] or {}).get('label') or 'skip historian observe'} · "
                f"sunday quiet {flat['sunday_quiet_age_label']} "
                "(observe · never softens floors)"
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
            live = desk_living.ritual_live_labels(root=root)
            sunday_cov = desk_living.sunday_twin_coverage(root=root)
            flat["ritual_live_labels"] = live
            flat["sunday_twin_coverage"] = sunday_cov
            flat["sunday_twin_ok"] = bool(sunday_cov.get("pass"))
            flat["sunday_twin_n"] = int(sunday_cov.get("twins_n") or 0)
            flat["sunday_twin_label"] = str(
                sunday_cov.get("label") or "sunday twins observe"
            )
            # Prefer live chip labels on sunday quiet flats when present
            _live_sunday = (
                ("digests_sunday_quiet", "digests_label", "never softens floors"),
                ("fills_sunday_quiet", "fills_label", "never invents PnL"),
                ("swarm_sunday_quiet", "swarm_label", None),
                ("hill_sunday_quiet", "hill_label", "never softens floors"),
                ("green_sunday_quiet", "green_label", None),
                ("bleed_sunday_quiet", "bleed_label", "never softens floors"),
                ("clv_sunday_quiet", "clv_label", None),
                ("timer_sunday_quiet", "timer_label", "never softens floors"),
                ("calib_sunday_quiet", "calib_label", "never auto-writes Φ"),
                ("queue_sunday_quiet", "queue_label", "never promotes"),
                ("gate_a_sunday_quiet", "gate_a_label", "never softens floors"),
                ("ai_sunday_quiet", "ai_label", "never auto-writes Φ"),
                ("tip_sunday_quiet", "tip_label", None),
                ("blackout_sunday_quiet", "blackout_label", "never softens floors"),
                ("injury_sunday_quiet", "injury_label", None),
                ("empty_sunday_quiet", "empty_label", None),
                ("near_miss_sunday_quiet", "near_miss_label", "never promotes"),
                ("eia_sunday_quiet", "eia_label", None),
                ("calendar_sunday_quiet", "calendar_label", None),
                ("pager_sunday_quiet", "pager_label", "never auto-pages"),
                ("books_sunday_quiet", "books_label", "never invents PnL"),
                ("pulse_sunday_quiet", "pulse_label", None),
                ("dual_sunday_quiet", "dual_label", "never softens floors"),
                ("skip_reg_sunday_quiet", "skip_reg_label", "never softens floors"),
                ("hard_stop_sunday_quiet", "hard_stop_label", "never promotes"),
                ("distance_sunday_quiet", "distance_label", None),
                ("quant_sunday_quiet", "quant_label", None),
                ("report_sunday_quiet", "report_label", "never auto-posts"),
                ("empty_bee_sunday_quiet", "empty_bee_label", None),
                ("nm_clerk_sunday_quiet", "nm_clerk_label", "never promotes"),
                ("hs_clerk_sunday_quiet", "hs_clerk_label", "never promotes"),
                ("bleed_clerk_sunday_quiet", "bleed_clerk_label", "never softens floors"),
                ("skip_twin_sunday_quiet", "skip_twin_label", None),
                ("clv_closer_sunday_quiet", "clv_closer_label", None),
                ("tdigest_sunday_quiet", "tdigest_label", None),
                ("skips_sunday_quiet", "skips_label", None),
                ("adapt_sunday_quiet", "adapt_label", "never auto-writes Φ"),
                ("teller_sunday_quiet", "teller_label", "never softens floors"),
                ("quiet_sunday_quiet", "quiet_label", "never softens floors"),
                ("doc_age_sunday_quiet", "doc_age_label", "never softens floors"),
                ("ritual_sunday_quiet", "ritual_label", "never auto-posts"),
                ("digest_fresh_sunday_quiet", "digest_fresh_label", None),
                ("journal_sunday_quiet", "journals_label", "never softens floors"),
                ("monday_sunday_quiet", "monday_label", "never softens floors"),
                ("toxic_sunday_quiet", "toxic_fills_label", "never softens floors"),
                ("adapt_ab_sunday_quiet", "adapt_ab_label", "never softens floors"),
                ("raise_phi_sla_sunday_quiet", "raise_phi_sla_label", "never auto-writes Φ"),
                ("feature_coverage_sunday_quiet", "feature_coverage_label", "never softens floors"),
                ("chip_catalog_sunday_quiet", "chip_catalog_label", "never softens floors"),
                ("phase2_pulse_sunday_quiet", "phase2_pulse_label", "never softens floors"),
                ("l7_observe_sunday_quiet", "l7_observe_label", "never softens floors"),
                ("feature_store_sunday_quiet", "feature_store_label", "never softens floors"),
                ("skip_historian_sunday_quiet", "skip_historian_label", "never softens floors"),
            )
            sq = flat["sunday_quiet_age_label"]
            for flat_key, live_key, note in _live_sunday:
                lab = live.get(live_key)
                if not lab:
                    continue
                suffix = f" (observe · {note})" if note else " (observe)"
                flat[flat_key] = f"{lab} · sunday quiet {sq}{suffix}"
            flat["sunday_twins_sunday_quiet"] = (
                f"{flat['sunday_twin_label']} · sunday quiet {sq} "
                "(observe · never softens floors)"
            )
            live_n_flat = sum(
                1 for k, v in live.items() if str(k).endswith("_label") and v
            )
            flat["ritual_live_sunday_quiet"] = (
                f"ritual live n={live_n_flat} · "
                f"{live.get('digests_label') or 'digests observe'} · "
                f"{live.get('fills_label') or 'fills observe'} · "
                f"{live.get('timer_label') or 'timer observe'} · sunday quiet {sq} "
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
            live = desk_living.ritual_live_labels(root=root)
            sunday_cov = desk_living.sunday_twin_coverage(root=root)
            observe_rows = (
                ("ruin sunday", "ruin_label", "ruin observe", "never softens floors"),
                ("gaps sunday", "gaps_label", "gaps observe", "never softens floors"),
                ("swarm sunday", "swarm_label", "swarm observe", None),
                ("hill sunday", "hill_label", "hillclimb none", "never softens floors"),
                ("digests sunday", "digests_label", "digests observe", "never softens floors"),
                ("fills sunday", "fills_label", "fills observe", "never invents PnL"),
                ("green sunday", "green_label", "green-day observe", None),
                ("bleed sunday", "bleed_label", "bleed observe", "never softens floors"),
                ("CLV sunday", "clv_label", "CLV observe", None),
                ("timer sunday", "timer_label", "timer observe", "never softens floors"),
                ("calib sunday", "calib_label", "calib observe", "never auto-writes Φ"),
                ("queue sunday", "queue_label", "queue observe", "never promotes"),
                ("Gate A sunday", "gate_a_label", "Gate A observe", "never softens floors"),
                ("AI sunday", "ai_label", "AI observe", "never auto-writes Φ"),
                ("tip sunday", "tip_label", "tip feed observe", None),
                ("blackout sunday", "blackout_label", "blackout observe", "never softens floors"),
                ("injury sunday", "injury_label", "injury observe", None),
                ("empty sunday", "empty_label", "empty CARD observe", None),
                ("near-miss sunday", "near_miss_label", "near-miss observe", "never promotes"),
                ("EIA sunday", "eia_label", "EIA observe", None),
                ("calendar sunday", "calendar_label", "calendar observe", None),
                ("pager sunday", "pager_label", "pager observe", "never auto-pages"),
                ("books sunday", "books_label", "books observe", "never invents PnL"),
                ("pulse sunday", "pulse_label", "pulse observe", None),
                ("dual sunday", "dual_label", "dual observe", "never softens floors"),
                ("skip-reg sunday", "skip_reg_label", "skip-regret observe", "never softens floors"),
                ("hard-stop sunday", "hard_stop_label", "hard-stop observe", "never promotes"),
                ("distance sunday", "distance_label", "distance observe", None),
                ("quant sunday", "quant_label", "quant observe", None),
                ("report sunday", "report_label", "report observe", "never auto-posts"),
                ("empty-bee sunday", "empty_bee_label", "empty bee observe", None),
                ("nm-clerk sunday", "nm_clerk_label", "nm clerk observe", "never promotes"),
                ("hs-clerk sunday", "hs_clerk_label", "hs clerk observe", "never promotes"),
                ("bleed-clerk sunday", "bleed_clerk_label", "bleed clerk observe", "never softens floors"),
                ("skip-twin sunday", "skip_twin_label", "skip-twin observe", None),
                ("CLV-closer sunday", "clv_closer_label", "CLV closer observe", None),
                ("t-digest sunday", "tdigest_label", "t-digest observe", None),
                ("skips sunday", "skips_label", "skips observe", None),
                ("adapt sunday", "adapt_label", "adapt observe", "never auto-writes Φ"),
                ("teller sunday", "teller_label", "teller observe", "never softens floors"),
                ("quiet sunday", "quiet_label", "feature quiet observe", "never softens floors"),
                ("doc-age sunday", "doc_age_label", "doctor age observe", "never softens floors"),
                ("ritual sunday", "ritual_label", "ritual observe", "never auto-posts"),
                ("digest-fresh sunday", "digest_fresh_label", "digest fresh observe", None),
                ("journals sunday", "journals_label", "journals observe", "never softens floors"),
                ("monday sunday", "monday_label", "monday pulse observe", "never softens floors"),
                ("toxic sunday", "toxic_fills_label", "toxic fills observe", "never softens floors"),
                ("adapt-A/B sunday", "adapt_ab_label", "adapt A/B observe", "never softens floors"),
                ("raise-Φ-SLA sunday", "raise_phi_sla_label", "raise_Φ SLA observe", "never auto-writes Φ"),
                ("feature-coverage sunday", "feature_coverage_label", "feature coverage observe", "never softens floors"),
                ("chip-catalog sunday", "chip_catalog_label", "chip catalog observe", "never softens floors"),
                ("phase2-pulse sunday", "phase2_pulse_label", "phase2 pulse observe", "never softens floors"),
                ("L7-pulse sunday", "l7_observe_label", "L7 observe pulse", "never softens floors"),
                ("feature-store sunday", "feature_store_label", "feature store observe", "never softens floors"),
                ("skip-historian sunday", "skip_historian_label", "skip historian observe", "never softens floors"),
            )
            # gaps/ruin labels may come from pages rather than ritual_live_labels
            ruin_page = desk_living.ruin_drill_page(root)
            gaps_page = desk_living.dual_control_gaps_page(root)
            if isinstance(ruin_page, dict) and ruin_page.get("label"):
                live["ruin_label"] = str(ruin_page.get("label"))
            if isinstance(gaps_page, dict) and gaps_page.get("label"):
                live["gaps_label"] = str(gaps_page.get("label"))
            for title, key, fallback, note in observe_rows:
                lab = live.get(key) or fallback
                suffix = f" (observe · {note})" if note else " (observe)"
                print(
                    f"{title}: {lab} · sunday quiet {sunday_label}{suffix}"
                )
            print(
                f"sunday twins: {sunday_cov.get('label') or 'sunday twins observe'} · "
                f"sunday quiet {sunday_label} (observe · never softens floors)"
            )
            live_n_obs = sum(
                1 for k, v in live.items() if str(k).endswith("_label") and v
            )
            print(
                f"ritual live sunday: ritual live n={live_n_obs} · "
                f"{live.get('digests_label') or 'digests observe'} · "
                f"{live.get('fills_label') or 'fills observe'} · "
                f"{live.get('timer_label') or 'timer observe'} · "
                f"sunday quiet {sunday_label} (observe · never softens floors)"
            )
            board_obs = desk_living.living_upgrade_board(root)
            teller_obs = (
                board_obs.get("teller_living")
                if isinstance(board_obs.get("teller_living"), dict)
                else {}
            )
            compact_obs = (
                board_obs.get("compact")
                if isinstance(board_obs.get("compact"), dict)
                else {}
            )
            print(
                "teller ritual live sunday: "
                + str(
                    compact_obs.get("teller_ritual_live_sunday_quiet")
                    or (
                        f"teller ritual live n="
                        f"{teller_obs.get('ritual_live_n') if teller_obs.get('ritual_live_n') is not None else live_n_obs} "
                        f"· sunday quiet {sunday_label} (observe · never softens floors)"
                    )
                )
            )
            print(
                "priority sunday: "
                + str(
                    compact_obs.get("priority_sunday_quiet")
                    or (
                        f"{desk_living.living_priority_snapshot(board_obs).get('label') or 'priority observe'} "
                        f"· sunday quiet {sunday_label} (observe · never softens floors)"
                    )
                )
            )
            print(
                "hud sunday: "
                + str(
                    compact_obs.get("hud_sunday_quiet")
                    or (
                        f"{desk_living.living_hud_summary(board_obs).get('label') or 'hud observe'} "
                        f"· sunday quiet {sunday_label} (observe · never softens floors)"
                    )
                )
            )
            print(
                "money-path sunday: "
                + str(
                    compact_obs.get("money_path_sunday_quiet")
                    or (
                        f"{desk_living.living_money_path_tip(board_obs).get('label') or 'money-path observe'} "
                        f"· sunday quiet {sunday_label} (observe · never invents PnL)"
                    )
                )
            )
            print(
                "guardrails sunday: "
                + str(
                    compact_obs.get("guardrails_sunday_quiet")
                    or (
                        f"{desk_living.living_guardrails_tip(board_obs).get('label') or 'guardrails observe'} "
                        f"· sunday quiet {sunday_label} (observe · never softens floors)"
                    )
                )
            )
            print(
                "surfaces sunday: "
                + str(
                    compact_obs.get("surfaces_sunday_quiet")
                    or (
                        f"{desk_living.living_surface_index(board_obs).get('label') or 'surfaces observe'} "
                        f"· sunday quiet {sunday_label} (observe · never softens floors)"
                    )
                )
            )
            print(
                "smoke sunday: "
                + str(
                    compact_obs.get("smoke_sunday_quiet")
                    or (
                        f"{desk_living.living_staff_smoke(board_obs).get('label') or 'smoke observe'} "
                        f"· sunday quiet {sunday_label} (observe · never softens floors)"
                    )
                )
            )
            print(
                "paste sunday: "
                + str(
                    compact_obs.get("paste_sunday_quiet")
                    or (
                        f"{desk_living.living_discord_paste_tip(board_obs).get('label') or 'paste observe'} "
                        f"· sunday quiet {sunday_label} (observe · never auto-posts)"
                    )
                )
            )
            print(
                "paper-live sunday: "
                + str(
                    compact_obs.get("paper_live_sunday_quiet")
                    or (
                        f"{desk_living.living_paper_live_tip(board_obs).get('label') or 'paper-live observe'} "
                        f"· sunday quiet {sunday_label} (observe · never enables live)"
                    )
                )
            )
            print(
                "makefile sunday: "
                + str(
                    compact_obs.get("makefile_sunday_quiet")
                    or (
                        f"{desk_living.living_makefile_index(board_obs).get('label') or 'makefile observe'} "
                        f"· sunday quiet {sunday_label} (observe · never softens floors)"
                    )
                )
            )
            print(
                "venues sunday: "
                + str(
                    compact_obs.get("venues_sunday_quiet")
                    or (
                        f"{desk_living.living_venues_tip(board_obs).get('label') or 'venues observe'} "
                        f"· sunday quiet {sunday_label} (observe · never softens floors)"
                    )
                )
            )
            print(
                "chicago sunday: "
                + str(
                    compact_obs.get("chicago_sunday_quiet")
                    or (
                        f"{desk_living.living_chicago_tip(board_obs).get('label') or 'chicago observe'} "
                        f"· sunday quiet {sunday_label} (observe · never softens floors)"
                    )
                )
            )
            print(
                "starve sunday: "
                + str(
                    compact_obs.get("starve_sunday_quiet")
                    or (
                        f"{desk_living.living_starve_tip(board_obs).get('label') or 'starve observe'} "
                        f"· sunday quiet {sunday_label} (observe · never softens floors)"
                    )
                )
            )
            print(
                "hard-rules sunday: "
                + str(
                    compact_obs.get("hard_rules_sunday_quiet")
                    or (
                        f"{desk_living.living_hard_rules_tip(board_obs).get('label') or 'hard-rules observe'} "
                        f"· sunday quiet {sunday_label} (observe · never softens floors)"
                    )
                )
            )

            print(
                "swarm-tip sunday: "
                + str(
                    compact_obs.get("swarm_tip_sunday_quiet")
                    or (
                        f"{desk_living.living_swarm_tip(board_obs).get('label') or 'swarm observe'} "
                        f"· sunday quiet {sunday_label} (observe · never softens floors)"
                    )
                )
            )
            print(
                "expand-tip sunday: "
                + str(
                    compact_obs.get("expand_tip_sunday_quiet")
                    or (
                        f"{desk_living.living_expand_tip(board_obs).get('label') or 'expand observe'} "
                        f"· sunday quiet {sunday_label} (observe · never softens floors)"
                    )
                )
            )
            print(
                "quiet-tip sunday: "
                + str(
                    compact_obs.get("quiet_tip_sunday_quiet")
                    or (
                        f"{desk_living.living_quiet_tip(board_obs).get('label') or 'quiet observe'} "
                        f"· sunday quiet {sunday_label} (observe · never softens floors)"
                    )
                )
            )
            print(
                "timer-tip sunday: "
                + str(
                    compact_obs.get("timer_tip_sunday_quiet")
                    or (
                        f"{desk_living.living_timer_tip(board_obs).get('label') or 'timer observe'} "
                        f"· sunday quiet {sunday_label} (observe · never softens floors)"
                    )
                )
            )
            print(
                "export-tip sunday: "
                + str(
                    compact_obs.get("export_tip_sunday_quiet")
                    or (
                        f"{desk_living.living_export_tip(board_obs).get('label') or 'export observe'} "
                        f"· sunday quiet {sunday_label} (observe · never softens floors)"
                    )
                )
            )
            print(
                "doctor-tip sunday: "
                + str(
                    compact_obs.get("doctor_tip_sunday_quiet")
                    or (
                        f"{desk_living.living_doctor_tip(board_obs).get('label') or 'doctor-tip observe'} "
                        f"· sunday quiet {sunday_label} (observe · never records doctor)"
                    )
                )
            )
            print(
                "inventory-tip sunday: "
                + str(
                    compact_obs.get("inventory_sunday_quiet")
                    or (
                        f"{desk_living.living_inventory_tip(board_obs).get('label') or 'inventory observe'} "
                        f"· sunday quiet {sunday_label} (observe · never softens floors)"
                    )
                )
            )
            print(
                "dual-tip sunday: "
                + str(
                    compact_obs.get("dual_tip_sunday_quiet")
                    or (
                        f"{desk_living.living_dual_tip(board_obs).get('label') or 'dual observe'} "
                        f"· sunday quiet {sunday_label} (observe · never enables live)"
                    )
                )
            )
            print(
                "hillclimb-tip sunday: "
                + str(
                    compact_obs.get("hillclimb_tip_sunday_quiet")
                    or (
                        f"{desk_living.living_hillclimb_tip(board_obs).get('label') or 'hillclimb observe'} "
                        f"· sunday quiet {sunday_label} (observe · never softens floors)"
                    )
                )
            )
            print(
                "ruin-tip sunday: "
                + str(
                    compact_obs.get("ruin_tip_sunday_quiet")
                    or (
                        f"{desk_living.living_ruin_tip(board_obs).get('label') or 'ruin observe'} "
                        f"· sunday quiet {sunday_label} (observe · never softens floors)"
                    )
                )
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
    # Live labels for ritual Discord sunday lines (surface-only; not board chips).
    board = desk_living.living_upgrade_board(root)
    live = desk_living.ritual_live_labels(board)
    payload.update({k: v for k, v in live.items() if str(k).endswith("_label")})
    timer = board.get("timer_heartbeat") if isinstance(board.get("timer_heartbeat"), dict) else {}
    payload["timer_alive"] = timer.get("alive")
    payload["sunday_twin_coverage"] = desk_living.sunday_twin_coverage(board)
    payload["ritual_live_labels"] = live
    compact = board.get("compact") if isinstance(board.get("compact"), dict) else {}
    payload["ritual_live_sunday_quiet"] = (
        compact.get("ritual_live_sunday_quiet")
        or desk_living.living_compact_card(root, board=board).get("ritual_live_sunday_quiet")
    )
    teller = board.get("teller_living") if isinstance(board.get("teller_living"), dict) else {}
    payload["teller_ritual_live_n"] = teller.get("ritual_live_n")
    payload["teller_ritual_live_ok"] = teller.get("ritual_live_ok")
    payload["teller_ritual_live_sunday_quiet"] = compact.get(
        "teller_ritual_live_sunday_quiet"
    )
    prio = desk_living.living_priority_snapshot(board)
    payload["priority"] = prio
    payload["priority_label"] = prio.get("label")
    payload["priority_lines"] = list(prio.get("priority") or [])
    payload["priority_sunday_quiet"] = compact.get("priority_sunday_quiet") or (
        f"{prio.get('label') or 'priority observe'} · sunday quiet "
        f"{sunday_quiet_age_label} (observe · never softens floors)"
    )
    hud = desk_living.living_hud_summary(board)
    payload["hud"] = hud
    payload["hud_label"] = hud.get("label")
    payload["hud_sunday_quiet"] = compact.get("hud_sunday_quiet") or (
        f"{hud.get('label') or 'hud observe'} · sunday quiet "
        f"{sunday_quiet_age_label} (observe · never softens floors)"
    )
    money = desk_living.living_money_path_tip(board)
    payload["money_path"] = money
    payload["money_path_label"] = money.get("label")
    payload["money_path_sunday_quiet"] = compact.get("money_path_sunday_quiet") or (
        f"{money.get('label') or 'money-path observe'} · sunday quiet "
        f"{sunday_quiet_age_label} (observe · never invents PnL)"
    )
    rails = desk_living.living_guardrails_tip(board)
    payload["guardrails"] = rails
    payload["guardrails_label"] = rails.get("label")
    payload["guardrails_sunday_quiet"] = compact.get("guardrails_sunday_quiet") or (
        f"{rails.get('label') or 'guardrails observe'} · sunday quiet "
        f"{sunday_quiet_age_label} (observe · never softens floors)"
    )
    surfaces = desk_living.living_surface_index(board)
    payload["surfaces"] = surfaces
    payload["surfaces_label"] = surfaces.get("label")
    payload["surfaces_sunday_quiet"] = compact.get("surfaces_sunday_quiet") or (
        f"{surfaces.get('label') or 'surfaces observe'} · sunday quiet "
        f"{sunday_quiet_age_label} (observe · never softens floors)"
    )
    smoke = desk_living.living_staff_smoke(board)
    payload["smoke"] = smoke
    payload["smoke_label"] = smoke.get("label")
    payload["smoke_ok"] = smoke.get("ok")
    payload["smoke_sunday_quiet"] = compact.get("smoke_sunday_quiet") or (
        f"{smoke.get('label') or 'smoke observe'} · sunday quiet "
        f"{sunday_quiet_age_label} (observe · never softens floors)"
    )
    paste = desk_living.living_discord_paste_tip(board)
    payload["paste"] = paste
    payload["paste_label"] = paste.get("label")
    payload["paste_n"] = paste.get("targets_n")
    payload["paste_sunday_quiet"] = compact.get("paste_sunday_quiet") or (
        f"{paste.get('label') or 'paste observe'} · sunday quiet "
        f"{sunday_quiet_age_label} (observe · never auto-posts)"
    )
    paper_live = desk_living.living_paper_live_tip(board)
    payload["paper_live"] = paper_live
    payload["paper_live_label"] = paper_live.get("label")
    payload["paper_live_ok"] = paper_live.get("ok")
    payload["paper_live_sunday_quiet"] = compact.get("paper_live_sunday_quiet") or (
        f"{paper_live.get('label') or 'paper-live observe'} · sunday quiet "
        f"{sunday_quiet_age_label} (observe · never enables live)"
    )
    makefile = desk_living.living_makefile_index(board)
    payload["makefile"] = makefile
    payload["makefile_label"] = makefile.get("label")
    payload["makefile_n"] = makefile.get("targets_n")
    payload["makefile_sunday_quiet"] = compact.get("makefile_sunday_quiet") or (
        f"{makefile.get('label') or 'makefile observe'} · sunday quiet "
        f"{sunday_quiet_age_label} (observe · never softens floors)"
    )
    venues = desk_living.living_venues_tip(board)
    payload["venues"] = venues
    payload["venues_label"] = venues.get("label")
    payload["venues_ok"] = venues.get("ok")
    payload["venues_sunday_quiet"] = compact.get("venues_sunday_quiet") or (
        f"{venues.get('label') or 'venues observe'} · sunday quiet "
        f"{sunday_quiet_age_label} (observe · never softens floors)"
    )
    chicago = desk_living.living_chicago_tip(board)
    payload["chicago"] = chicago
    payload["chicago_label"] = chicago.get("label")
    payload["chicago_sunday_quiet"] = compact.get("chicago_sunday_quiet") or (
        f"{chicago.get('label') or 'chicago observe'} · sunday quiet "
        f"{sunday_quiet_age_label} (observe · never softens floors)"
    )
    starve = desk_living.living_starve_tip(board)
    payload["starve"] = starve
    payload["starve_label"] = starve.get("label")
    payload["starve_sunday_quiet"] = compact.get("starve_sunday_quiet") or (
        f"{starve.get('label') or 'starve observe'} · sunday quiet "
        f"{sunday_quiet_age_label} (observe · never softens floors)"
    )
    hard_rules = desk_living.living_hard_rules_tip(board)
    payload["hard_rules"] = hard_rules
    payload["hard_rules_label"] = hard_rules.get("label")
    payload["hard_rules_sunday_quiet"] = compact.get("hard_rules_sunday_quiet") or (
        f"{hard_rules.get('label') or 'hard-rules observe'} · sunday quiet "
        f"{sunday_quiet_age_label} (observe · never softens floors)"
    )

    swarm_tip = desk_living.living_swarm_tip(board)
    payload["swarm_tip"] = swarm_tip
    payload["swarm_tip_label"] = swarm_tip.get("label")
    payload["swarm_tip_sunday_quiet"] = compact.get("swarm_tip_sunday_quiet") or (
        f"{swarm_tip.get('label') or 'swarm observe'} · sunday quiet "
        f"{sunday_quiet_age_label} (observe · never softens floors)"
    )
    expand_tip = desk_living.living_expand_tip(board)
    payload["expand_tip"] = expand_tip
    payload["expand_tip_label"] = expand_tip.get("label")
    payload["expand_tip_sunday_quiet"] = compact.get("expand_tip_sunday_quiet") or (
        f"{expand_tip.get('label') or 'expand observe'} · sunday quiet "
        f"{sunday_quiet_age_label} (observe · never softens floors)"
    )
    quiet_tip = desk_living.living_quiet_tip(board)
    payload["quiet_tip"] = quiet_tip
    payload["quiet_tip_label"] = quiet_tip.get("label")
    payload["quiet_tip_sunday_quiet"] = compact.get("quiet_tip_sunday_quiet") or (
        f"{quiet_tip.get('label') or 'quiet observe'} · sunday quiet "
        f"{sunday_quiet_age_label} (observe · never softens floors)"
    )
    timer_tip = desk_living.living_timer_tip(board)
    payload["timer_tip"] = timer_tip
    payload["timer_tip_label"] = timer_tip.get("label")
    payload["timer_tip_sunday_quiet"] = compact.get("timer_tip_sunday_quiet") or (
        f"{timer_tip.get('label') or 'timer observe'} · sunday quiet "
        f"{sunday_quiet_age_label} (observe · never softens floors)"
    )
    export_tip = desk_living.living_export_tip(board)
    payload["export_tip"] = export_tip
    payload["export_tip_label"] = export_tip.get("label")
    payload["export_tip_sunday_quiet"] = compact.get("export_tip_sunday_quiet") or (
        f"{export_tip.get('label') or 'export observe'} · sunday quiet "
        f"{sunday_quiet_age_label} (observe · never softens floors)"
    )
    doctor_tip = desk_living.living_doctor_tip(board)
    payload["doctor_tip"] = doctor_tip
    payload["doctor_tip_label"] = doctor_tip.get("label")
    payload["doctor_tip_sunday_quiet"] = compact.get("doctor_tip_sunday_quiet") or (
        f"{doctor_tip.get('label') or 'doctor-tip observe'} · sunday quiet "
        f"{sunday_quiet_age_label} (observe · never records doctor)"
    )
    inventory_tip = desk_living.living_inventory_tip(board)
    payload["inventory_tip"] = inventory_tip
    payload["inventory_tip_label"] = inventory_tip.get("label")
    payload["inventory_sunday_quiet"] = compact.get("inventory_sunday_quiet") or (
        f"{inventory_tip.get('label') or 'inventory observe'} · sunday quiet "
        f"{sunday_quiet_age_label} (observe · never softens floors)"
    )
    dual_tip = desk_living.living_dual_tip(board)
    payload["dual_tip"] = dual_tip
    payload["dual_tip_label"] = dual_tip.get("label")
    payload["dual_tip_sunday_quiet"] = compact.get("dual_tip_sunday_quiet") or (
        f"{dual_tip.get('label') or 'dual observe'} · sunday quiet "
        f"{sunday_quiet_age_label} (observe · never enables live)"
    )
    hillclimb_tip = desk_living.living_hillclimb_tip(board)
    payload["hillclimb_tip"] = hillclimb_tip
    payload["hillclimb_tip_label"] = hillclimb_tip.get("label")
    payload["hillclimb_tip_sunday_quiet"] = compact.get("hillclimb_tip_sunday_quiet") or (
        f"{hillclimb_tip.get('label') or 'hillclimb observe'} · sunday quiet "
        f"{sunday_quiet_age_label} (observe · never softens floors)"
    )
    ruin_tip = desk_living.living_ruin_tip(board)
    payload["ruin_tip"] = ruin_tip
    payload["ruin_tip_label"] = ruin_tip.get("label")
    payload["ruin_tip_sunday_quiet"] = compact.get("ruin_tip_sunday_quiet") or (
        f"{ruin_tip.get('label') or 'ruin observe'} · sunday quiet "
        f"{sunday_quiet_age_label} (observe · never softens floors)"
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
