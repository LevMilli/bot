#!/usr/bin/env python3
"""
Staff UX — list raise_phi calibration tickets (never writes Φ / never softens floors).

Usage (from paper-bots/):
  python3 tools/staff_calib_tickets.py
  python3 tools/staff_calib_tickets.py refresh
  python3 tools/staff_calib_tickets.py json
  python3 tools/staff_calib_tickets.py accept --board btc --who ops --note "..."
  python3 tools/staff_calib_tickets.py defer --board btc --who ops --note "..."
  python3 tools/staff_calib_tickets.py decisions
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
import desk_roi_plan
from helpers import calib_nag


def main() -> int:
    parser = argparse.ArgumentParser(description="Staff raise_phi calibration tickets.")
    parser.add_argument(
        "action",
        nargs="?",
        default="show",
        choices=("show", "refresh", "json", "accept", "defer", "decisions"),
    )
    parser.add_argument("--root", default=ROOT)
    parser.add_argument("--board", default="btc", help="btc|sports|commodity")
    parser.add_argument("--who", default="")
    parser.add_argument("--note", default="")
    parser.add_argument("--before-hit-rate", type=float, default=None)
    parser.add_argument("--after-hit-rate", type=float, default=None)
    args = parser.parse_args()
    root = args.root

    if args.action in ("accept", "defer"):
        out = desk_roi_plan.staff_log_raise_phi_decision(
            root,
            decision=args.action,
            board=args.board,
            who=args.who,
            note=args.note,
            before_hit_rate=args.before_hit_rate,
            after_hit_rate=args.after_hit_rate,
        )
        print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0 if out.get("ok") else 2
    if args.action == "decisions":
        print(json.dumps(
            desk_roi_plan.raise_phi_decision_log(root),
            indent=2, sort_keys=True, default=str,
        ))
        return 0

    if args.action == "refresh":
        digest = calib_nag.write_digest_from_desk(root)
    else:
        path = calib_nag.digest_path(root)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as handle:
                digest = json.load(handle)
        else:
            digest = calib_nag.write_digest_from_desk(root)
        if not isinstance(digest, dict):
            digest = {}

    chip = desk_living.calib_nag_chip(root)
    ai = desk_living.living_ai_health(root)
    decisions = desk_roi_plan.raise_phi_decision_log(root)
    payload = {
        "paper_only": True,
        "fee_floors_locked": True,
        "auto_write_phi": False,
        "tickets_n": digest.get("tickets_n") if isinstance(digest, dict) else chip.get("tickets_n"),
        "tickets": (digest.get("tickets") if isinstance(digest, dict) else None) or chip.get("tickets") or [],
        "boards": (digest.get("boards") if isinstance(digest, dict) else None) or chip.get("boards") or [],
        "living_ai_tickets": ai.get("raise_phi_tickets") if isinstance(ai, dict) else [],
        "decisions_n": decisions.get("n"),
        "decisions_latest": decisions.get("latest"),
        "note": (
            "raise_phi is a staff dual-control ticket — never silent Φ write, "
            "never softer floors. Log accept/defer via this CLI."
        ),
    }
    if args.action == "json" or args.action == "refresh":
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return 0
    print(
        f"calib tickets={payload.get('tickets_n')} "
        f"boards={[t.get('board') for t in (payload.get('tickets') or []) if isinstance(t, dict)]} "
        f"decisions={payload.get('decisions_n')}"
    )
    print(payload.get("note"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
