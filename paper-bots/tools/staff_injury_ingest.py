#!/usr/bin/env python3
"""
Staff UX — ingest injury/news headlines into injury_wire inbox (observe-only).

Usage (from paper-bots/):
  python3 tools/staff_injury_ingest.py show
  python3 tools/staff_injury_ingest.py add --league NFL --text "WR questionable"
  python3 tools/staff_injury_ingest.py add --text "plain headline"
  python3 tools/staff_injury_ingest.py replace --league NBA --text "star out"
  python3 tools/staff_injury_ingest.py clear
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

from helpers import injury_wire


def main() -> int:
    parser = argparse.ArgumentParser(description="Staff injury wire ingest.")
    parser.add_argument("action", choices=("show", "add", "replace", "clear"))
    parser.add_argument("--root", default=ROOT)
    parser.add_argument("--league", default="")
    parser.add_argument("--text", default="")
    args = parser.parse_args()
    root = args.root

    if args.action == "show":
        inbox = injury_wire.load_inbox(root)
        path = injury_wire.digest_path(root)
        digest = {}
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as handle:
                digest = json.load(handle)
        print(json.dumps({
            "paper_only": True,
            "may_place_alone": False,
            "fee_floors_locked": True,
            "inbox_n": len(inbox) if isinstance(inbox, list) else 0,
            "inbox": inbox if isinstance(inbox, list) else [],
            "digest_n": digest.get("n") if isinstance(digest, dict) else None,
            "note": "Observe-only — never buys; never waives sports floor.",
        }, indent=2, sort_keys=True, default=str))
        return 0

    if args.action == "clear":
        digest = injury_wire.staff_ingest(root, headlines=[], replace=True)
        print(json.dumps(digest, indent=2, sort_keys=True, default=str))
        return 0

    text = str(args.text or "").strip()
    if not text:
        print("error: --text required for add/replace", file=sys.stderr)
        return 2
    headline = {"league": str(args.league or "")[:20], "text": text[:160]}
    replace = args.action == "replace"
    digest = injury_wire.staff_ingest(root, headlines=[headline], replace=replace)
    print(json.dumps({
        "paper_only": True,
        "may_place_alone": False,
        "fee_floors_locked": True,
        "replaced": replace,
        "digest": digest,
    }, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
