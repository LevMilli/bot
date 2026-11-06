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
        f"hillclimb: {hill.get('label') or '—'}",
        f"digests: {inv.get('label') or '—'}",
        f"floors: {floors.get('label') or '—'}",
        f"teller: {teller.get('memory_line') or '—'}",
        (
            f"ritual_nag={bool(teller.get('ritual_nag'))} "
            f"teller_ritual_ok={teller.get('ritual_ok')}"
        ),
        (
            f"expand: {expand.get('soft_copy') or expand.get('label') or '—'}"
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
            "floors", "teller", "expand", "doctor",
        ),
    )
    parser.add_argument("--root", default=ROOT)
    parser.add_argument(
        "--discord",
        action="store_true",
        help="Paste-ready Discord markdown (gaps/ruin/expand/floors/doctor); never auto-posts.",
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
        print(json.dumps({
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
            "betting_expand_gate": board.get("betting_expand_gate"),
            "chicago_today": board.get("chicago_today"),
            "chip_catalog": sorted(
                k for k, v in board.items()
                if isinstance(v, dict) and v.get("fee_floors_locked") is True
            ),
        }, indent=2, sort_keys=True, default=str))
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
        raw.extend([
            "insight swarm ≥3:1 before betting expand",
            "revert last lever if hillclimb kill trips",
            "fee floors locked 0.06/0.05/0.02",
        ])
        print(json.dumps({
            "paper_only": True,
            "fee_floors_locked": True,
            "priority": desk_master.finalize_living_priority(raw),
            "max_n": desk_master.PRIORITY_MAX,
        }, indent=2))
        return 0
    print(_text(board))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
