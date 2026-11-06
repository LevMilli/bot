#!/usr/bin/env python3
"""
Staff weekly living ritual — gaps, ruin, floors, expand, doctor (never publishes).

Usage (from paper-bots/):
  python3 tools/staff_living_ritual.py
  python3 tools/staff_living_ritual.py --json
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Staff weekly living ritual.")
    parser.add_argument("--root", default=ROOT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = args.root

    steps = [
        ("gaps", desk_living.dual_control_gaps_page(root)),
        ("ruin", desk_living.ruin_drill_page(root)),
        ("floors", desk_living.fee_floors_assert(root)),
        ("expand", desk_living.betting_expand_gate(root)),
        ("doctor", desk_living.living_doctor(root)),
    ]
    payload = {
        "paper_only": True,
        "fee_floors_locked": True,
        "live_orders_enabled": False,
        "auto_publish": False,
        "steps": {name: row for name, row in steps},
        "ok": bool(
            steps[2][1].get("all_ok")
            and not steps[3][1].get("blocked")
            and steps[4][1].get("ok")
        ),
        "note": (
            "Weekly ritual draft — staff reviews gaps/ruin/floors/expand/doctor. "
            "Never invent fills; never soften floors; never enable live."
        ),
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    else:
        print("Living weekly ritual (paper only · floors locked · live=False)")
        for name, row in steps:
            label = row.get("label") or row.get("copy") or name
            if name in ("gaps", "ruin") and row.get("copy"):
                print(f"\n## {name}\n{row.get('copy')}")
            else:
                print(f"- {name}: {label}")
        print(f"\nritual_ok={payload['ok']}")
        print(payload["note"])
    # Fail if floors soft or expand blocked (doctor may still fail on quiet/gaps).
    if not steps[2][1].get("all_ok"):
        return 2
    if steps[3][1].get("blocked"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
