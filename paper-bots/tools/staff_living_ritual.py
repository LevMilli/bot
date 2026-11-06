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
    quiet = payload.get("feature_quiet") if isinstance(payload.get("feature_quiet"), dict) else {}
    age = quiet.get("age_hours") if quiet else None
    age_s = (
        f"{age}h"
        if age is not None
        else str(payload.get("quiet_age") or "n/a")
    )
    lines.append(
        f"• Feature quiet: quiet={quiet.get('quiet') if quiet else None} age={age_s} "
        f"(staff observe — never softens floors)"
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
            flat["feature_quiet"] = quiet if isinstance(quiet, dict) else {}
            flat["quiet_age_h"] = age_h
            flat["quiet_age"] = f"{age_h}h" if age_h is not None else "n/a"
            print(json.dumps(flat, indent=2, sort_keys=True, default=str))
        else:
            quiet = desk_living.feature_store_quiet_alert(root)
            age_h = quiet.get("age_hours") if isinstance(quiet, dict) else None
            quiet_age = f"{age_h}h" if age_h is not None else "n/a"
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
    feature_quiet = desk_living.feature_store_quiet_alert(root)
    quiet_age_h = feature_quiet.get("age_hours") if isinstance(feature_quiet, dict) else None
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
        "feature_quiet": feature_quiet if isinstance(feature_quiet, dict) else {},
        "quiet_age": f"{quiet_age_h}h" if quiet_age_h is not None else "n/a",
        "quiet_age_h": quiet_age_h,
        "note": (
            "Weekly ritual draft — staff reviews gaps/ruin/floors/expand/doctor. "
            "Never invent fills; never soften floors; never enable live."
        ),
    }
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
