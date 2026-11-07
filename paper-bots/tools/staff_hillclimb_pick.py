#!/usr/bin/env python3
"""
Staff UX helper — list / pack / pick / clear / log one hillclimb lever (paper).

Never auto-writes bot params. Never softens venue floors.
LIVE_ORDERS stay off. auto_apply=False forever.

Usage (from paper-bots/):
  python3 tools/staff_hillclimb_pick.py list
  python3 tools/staff_hillclimb_pick.py status
  python3 tools/staff_hillclimb_pick.py pack
  python3 tools/staff_hillclimb_pick.py journal
  python3 tools/staff_hillclimb_pick.py pick <lever_name> [--who alice] [--note "..."] [--value 0.06]
  python3 tools/staff_hillclimb_pick.py clear [--who alice]
  python3 tools/staff_hillclimb_pick.py log accept|defer --lever <name> [--before ...] [--after ...]
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
    parser.add_argument(
        "action",
        choices=("list", "status", "pack", "journal", "pick", "clear", "log"),
    )
    parser.add_argument("lever", nargs="?", default="")
    parser.add_argument(
        "decision",
        nargs="?",
        default="",
        help="accept|defer when action=log (or pass as lever positional)",
    )
    parser.add_argument("--who", default="")
    parser.add_argument("--note", default="")
    parser.add_argument("--before", default="")
    parser.add_argument("--after", default="")
    parser.add_argument("--lever", dest="lever_flag", default="", help="lever for log action")
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
    if args.action == "pack":
        out = desk_roi_plan.hillclimb_pick_evidence_pack(root)
        print(json.dumps(out, indent=2, sort_keys=True, default=str))
        # Exit 2 when staff must act (needs pick or kill).
        if out.get("needs_staff_pick") or out.get("kill"):
            return 2
        return 0
    if args.action == "journal":
        out = {
            "lever_journal": desk_roi_plan.hillclimb_lever_journal(root),
            "pick_journal": desk_roi_plan.staff_hillclimb_pick_journal(root),
            "auto_apply": False,
            "fee_floors_locked": True,
        }
        print(json.dumps(out, indent=2, sort_keys=True, default=str))
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
    if args.action == "log":
        # Prefer: log accept --lever X ; also allow: log accept VOL_SAFE
        dec = str(args.lever or args.decision or "").strip().lower()
        lever_name = str(args.lever_flag or args.decision or "").strip()
        if dec not in ("accept", "defer"):
            # Maybe positional was decision via lever slot already handled; else fail.
            print("log requires accept|defer", file=sys.stderr)
            return 2
        if lever_name.lower() in ("accept", "defer"):
            lever_name = ""
        # If second positional used as lever: `log accept VOL_SAFE`
        if not lever_name and args.decision and args.decision.lower() not in ("accept", "defer"):
            lever_name = args.decision
        out = desk_roi_plan.staff_log_hillclimb_pick(
            root,
            dec,
            lever=lever_name or args.lever_flag,
            who=args.who,
            note=args.note,
            before=args.before,
            after=args.after,
        )
        print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0 if out.get("ok") else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
