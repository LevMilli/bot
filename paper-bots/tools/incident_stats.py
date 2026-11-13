#!/usr/bin/env python3
"""Mean time to notice and mean time to fix, from paper-bots/docs/incidents/*.md.

    python3 paper-bots/tools/incident_stats.py

Each note has lines like ``- Started: 2026-11-13 09:00 CT``, ``- Noticed: ...``
and ``- Fixed: ...``. Notes missing a time are listed, not guessed.
"""
from __future__ import annotations

import datetime as dt
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FOLDER = os.path.join(os.path.dirname(HERE), "docs", "incidents")
FIELD = re.compile(r"^-\s*(Started|Noticed|Fixed):\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2})", re.M)


def times(text: str) -> dict:
    return {k.lower(): dt.datetime.strptime(v, "%Y-%m-%d %H:%M") for k, v in FIELD.findall(text)}


def summary(folder: str = FOLDER) -> dict:
    notice, fix, skipped = [], [], []
    for path in sorted(glob.glob(os.path.join(folder, "*.md"))):
        name = os.path.basename(path)
        if name in ("README.md", "TEMPLATE.md"):
            continue
        with open(path, encoding="utf-8") as handle:
            got = times(handle.read())
        if not {"started", "noticed", "fixed"} <= set(got):
            skipped.append(name)
            continue
        notice.append((got["noticed"] - got["started"]).total_seconds() / 60)
        fix.append((got["fixed"] - got["started"]).total_seconds() / 60)
    mean = (lambda xs: round(sum(xs) / len(xs), 1) if xs else None)
    return {"incidents": len(notice), "mean_minutes_to_notice": mean(notice),
            "mean_minutes_to_fix": mean(fix), "missing_times": skipped}


def main() -> int:
    s = summary()
    if not s["incidents"]:
        print("No incident notes with all three times yet.")
    else:
        print(f"{s['incidents']} incidents. Mean time to notice: {s['mean_minutes_to_notice']} minutes. "
              f"Mean time to fix: {s['mean_minutes_to_fix']} minutes.")
    if s["missing_times"]:
        print("Missing a time: " + ", ".join(s["missing_times"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
