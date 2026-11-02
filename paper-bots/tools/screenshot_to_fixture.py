#!/usr/bin/env python3
"""
Screenshot → fixture pipeline (Top25 #21).

Staff drop Kalshi screen notes as JSON lines; this normalizes them into
desk_adapt SCREEN_FIXTURES-compatible vol_kwargs vectors for CI.

Usage:
  python3 tools/screenshot_to_fixture.py fixtures/raw_screens.jsonl
Paper only. Does not place orders.
"""
from __future__ import annotations

import json
import sys


def normalize(row: dict) -> dict:
    name = str(row.get("name") or row.get("series") or "screen").strip().lower().replace(" ", "_")
    vol = {
        "cushion": row.get("cushion"),
        "sigma": row.get("sigma"),
        "spread": row.get("spread"),
        "minutes_left": row.get("minutes_left") or row.get("min_left"),
        "ask": row.get("ask"),
        "recent_range": row.get("recent_range"),
        "spot": row.get("spot"),
    }
    return {
        "name": name,
        "vol_kwargs": {k: v for k, v in vol.items() if v is not None},
        "expect_safe": bool(row.get("expect_safe", True)),
        "expect_big": bool(row.get("expect_big", False)),
        "expect_false_conf": bool(row.get("expect_false_conf", False)),
        "source": row.get("source") or "staff_screenshot",
    }


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: screenshot_to_fixture.py <raw.jsonl>", file=sys.stderr)
        return 2
    out = []
    with open(argv[1], encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            out.append(normalize(json.loads(line)))
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
