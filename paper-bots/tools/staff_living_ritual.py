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
        f"ritual_ok={payload.get('ok')}",
        "",
    ]
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
            flat = dict(chip)
            flat["ritual_ok"] = chip.get("ritual_ok")
            flat["exit_ok"] = chip.get("exit_ok")
            flat["floors_ok"] = chip.get("floors_ok")
            flat["expand_ok"] = chip.get("expand_ok")
            flat["doctor_fresh"] = chip.get("doctor_fresh")
            print(json.dumps(flat, indent=2, sort_keys=True, default=str))
        else:
            print(chip.get("label") or "ritual observe")
            print(
                f"ritual_ok={chip.get('ritual_ok')} exit_ok={chip.get('exit_ok')} "
                f"floors_ok={chip.get('floors_ok')} expand_ok={chip.get('expand_ok')} "
                f"doctor_fresh={chip.get('doctor_fresh')}"
            )
            print(
                "doctor soft: make living-doctor · draft: make living-ritual-discord "
                "(staff paste · never auto-posts)"
            )
            print(chip.get("note") or "")
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
        for name, row in steps:
            label = row.get("label") or row.get("copy") or name
            if name in ("gaps", "ruin") and row.get("copy"):
                print(f"\n## {name}\n{row.get('copy')}")
            else:
                print(f"- {name}: {label}")
        print(
            f"\nritual_ok={payload['ritual_ok']} exit_ok={payload['exit_ok']} "
            f"floors_ok={payload['floors_ok']} expand_ok={payload['expand_ok']} "
            f"doctor_ok={payload['doctor_ok']}"
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
