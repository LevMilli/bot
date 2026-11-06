#!/usr/bin/env python3
"""
Staff UX — dual-control paper checklist (never enables live orders).

Usage (from paper-bots/):
  python3 tools/staff_dual_control.py status
  python3 tools/staff_dual_control.py items
  python3 tools/staff_dual_control.py sign --who alice --role primary [--item gate_a_pilot]
  python3 tools/staff_dual_control.py clear --who alice
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
    parser = argparse.ArgumentParser(description="Staff dual-control paper checklist.")
    parser.add_argument("action", choices=("status", "items", "sign", "clear"))
    parser.add_argument("--who", default="")
    parser.add_argument("--role", default="primary", choices=("primary", "secondary"))
    parser.add_argument("--item", default="", help="checklist item id")
    parser.add_argument("--note", default="")
    parser.add_argument("--root", default=ROOT)
    args = parser.parse_args()
    root = args.root

    if args.action == "status":
        print(json.dumps(desk_roi_plan.dual_control_status(root), indent=2, sort_keys=True, default=str))
        return 0
    if args.action == "items":
        items = [{"id": i, "label": lab} for i, lab in desk_roi_plan.DUAL_CONTROL_ITEMS]
        print(json.dumps({
            "paper_only": True,
            "live_orders_enabled": False,
            "fee_floors_locked": True,
            "items": items,
        }, indent=2, sort_keys=True))
        return 0
    if args.action == "sign":
        if not args.who:
            print("sign requires --who", file=sys.stderr)
            return 2
        out = desk_roi_plan.staff_sign_dual_control(
            root,
            who=args.who,
            role=args.role,
            item_id=args.item or None,
            note=args.note,
        )
        print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0 if out.get("ok") else 1
    if args.action == "clear":
        out = desk_roi_plan.staff_clear_dual_control(root, who=args.who, note=args.note)
        print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0 if out.get("ok") else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
