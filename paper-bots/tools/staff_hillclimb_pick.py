#!/usr/bin/env python3
"""
Staff UX helper — list / pick / clear one hillclimb lever (paper observe path).

Never auto-writes bot params. Never softens venue floors.
LIVE_ORDERS stay off.

Usage (from paper-bots/):
  python3 tools/staff_hillclimb_pick.py list
  python3 tools/staff_hillclimb_pick.py status
  python3 tools/staff_hillclimb_pick.py pick <lever_name> [--who alice] [--note "..."] [--value 0.06]
  python3 tools/staff_hillclimb_pick.py clear [--who alice]
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

import desk_roi_plan


def main() -> int:
    parser = argparse.ArgumentParser(description="Staff hillclimb lever pick (paper).")
    parser.add_argument("action", choices=("list", "status", "pick", "clear"))
    parser.add_argument("lever", nargs="?", default="")
    parser.add_argument("--who", default="")
    parser.add_argument("--note", default="")
    parser.add_argument("--value", default=None, help="optional proposed_value for raise-only levers")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--root", default=ROOT)
    args = parser.parse_args()
    root = args.root

    if args.action == "list":
        print(json.dumps(desk_roi_plan.hillclimb_allowlist(), indent=2, sort_keys=True))
        return 0
    if args.action == "status":
        print(json.dumps(desk_roi_plan.hillclimb_lever_status(root), indent=2, sort_keys=True))
        return 0
    if args.action == "pick":
        if not args.lever:
            print("pick requires <lever_name>", file=sys.stderr)
            return 2
        note = args.note
        if args.who:
            note = (f"who={args.who}; " + note).strip("; ")
        proposed = None
        if args.value is not None and str(args.value) != "":
            try:
                proposed = float(args.value)
            except ValueError:
                print("--value must be a number", file=sys.stderr)
                return 2
        out = desk_roi_plan.staff_pick_hillclimb_lever(
            root,
            args.lever,
            note=note,
            proposed_value=proposed,
            force=bool(args.force),
        )
        print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0 if out.get("ok") else 1
    if args.action == "clear":
        out = desk_roi_plan.staff_clear_hillclimb_lever(
            root, who=args.who, note=args.note,
        )
        print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0 if out.get("ok") else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
