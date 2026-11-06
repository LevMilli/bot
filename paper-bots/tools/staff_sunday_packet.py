#!/usr/bin/env python3
"""
Staff UX — draft / show Sunday living packet (never auto-publishes).

Usage (from paper-bots/):
  python3 tools/staff_sunday_packet.py draft
  python3 tools/staff_sunday_packet.py show
  python3 tools/staff_sunday_packet.py checklist
  python3 tools/staff_sunday_packet.py discord
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

from helpers import sunday_packet


def _load_or_build(root: str) -> dict:
    path = sunday_packet.packet_path(root)
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as handle:
            packet = json.load(handle)
        if isinstance(packet, dict):
            return packet
    return sunday_packet.write_packet(root)


def main() -> int:
    parser = argparse.ArgumentParser(description="Staff Sunday living packet draft.")
    parser.add_argument("action", choices=("draft", "show", "checklist", "discord"))
    parser.add_argument("--root", default=ROOT)
    args = parser.parse_args()
    root = args.root

    if args.action == "draft":
        packet = sunday_packet.write_packet(root)
        print(json.dumps(packet, indent=2, sort_keys=True, default=str))
        return 0
    if args.action == "show":
        packet = _load_or_build(root)
        print(json.dumps(packet, indent=2, sort_keys=True, default=str))
        return 0
    if args.action == "checklist":
        packet = sunday_packet.build_packet(root)
        print(json.dumps({
            "paper_only": True,
            "auto_publish": False,
            "fee_floors_locked": True,
            "live_orders_enabled": False,
            "staff_checklist": packet.get("staff_checklist") or [],
            "note": packet.get("note"),
        }, indent=2, sort_keys=True))
        return 0
    if args.action == "discord":
        packet = _load_or_build(root)
        print(sunday_packet.format_discord(packet))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
