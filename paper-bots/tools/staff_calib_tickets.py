#!/usr/bin/env python3
"""
Staff UX — list raise_phi calibration tickets (never writes Φ / never softens floors).

Usage (from paper-bots/):
  python3 tools/staff_calib_tickets.py
  python3 tools/staff_calib_tickets.py refresh
  python3 tools/staff_calib_tickets.py json
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
from helpers import calib_nag


def main() -> int:
    parser = argparse.ArgumentParser(description="Staff raise_phi calibration tickets.")
    parser.add_argument(
        "action",
        nargs="?",
        default="show",
        choices=("show", "refresh", "json"),
    )
    parser.add_argument("--root", default=ROOT)
    args = parser.parse_args()
    root = args.root

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
    payload = {
        "paper_only": True,
        "fee_floors_locked": True,
        "auto_write_phi": False,
        "tickets_n": digest.get("tickets_n") if isinstance(digest, dict) else chip.get("tickets_n"),
        "tickets": (digest.get("tickets") if isinstance(digest, dict) else None) or chip.get("tickets") or [],
        "boards": (digest.get("boards") if isinstance(digest, dict) else None) or chip.get("boards") or [],
        "living_ai_tickets": ai.get("raise_phi_tickets") if isinstance(ai, dict) else [],
        "note": (
            "raise_phi is a staff dual-control ticket — never silent Φ write, "
            "never softer floors."
        ),
    }
    if args.action == "json" or args.action == "refresh":
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return 0
    print(
        f"calib tickets={payload.get('tickets_n')} "
        f"boards={[t.get('board') for t in (payload.get('tickets') or []) if isinstance(t, dict)]}"
    )
    print(payload.get("note"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
