#!/usr/bin/env python3
"""Desk doctor CLI — idea #19 from Top 25. Paper only."""
from __future__ import annotations

import json
import os
import sys


def main(argv: list[str] | None = None) -> int:
    argv = list(argv or sys.argv[1:])
    root = os.path.dirname(os.path.abspath(__file__))
    if argv and not argv[0].startswith("-"):
        root = argv[0]
    health = None
    try:
        import pimp_desk
        health = pimp_desk.timer_health(root)
    except Exception as exc:
        health = {"alive": False, "error": type(exc).__name__}
    import desk_top25
    report = desk_top25.desk_doctor(root, health=health)
    report["health"] = health
    print(json.dumps(report, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
