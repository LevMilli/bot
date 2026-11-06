#!/usr/bin/env python3
"""
Staff UX — paper ruin drill set/clear (entries/pause practice).

Never enables live orders. Never softens venue floors.

Usage:
  python3 tools/staff_ruin_drill.py status
  python3 tools/staff_ruin_drill.py set soft|hard|nuclear --who alice [--note "..."]
  python3 tools/staff_ruin_drill.py clear --who alice
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
    parser = argparse.ArgumentParser(description="Staff ruin drill (paper).")
    parser.add_argument("action", choices=("status", "set", "clear"))
    parser.add_argument("level", nargs="?", default="")
    parser.add_argument("--who", default="staff")
    parser.add_argument("--note", default="")
    parser.add_argument("--root", default=ROOT)
    args = parser.parse_args()
    root = args.root

    if args.action == "status":
        print(json.dumps(desk_roi_plan.ruin_drill_status(root), indent=2, sort_keys=True, default=str))
        return 0
    if args.action == "set":
        if args.level not in desk_roi_plan.RUIN_LEVELS:
            print(f"level must be one of {desk_roi_plan.RUIN_LEVELS}", file=sys.stderr)
            return 2
        out = desk_roi_plan.set_ruin_drill(
            root, level=args.level, who=args.who, note=args.note,
        )
        print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0 if out.get("ok") else 1
    if args.action == "clear":
        out = desk_roi_plan.clear_ruin_drill(root, who=args.who, note=args.note)
        print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0 if out.get("ok") else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
