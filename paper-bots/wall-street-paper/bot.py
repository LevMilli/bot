#!/usr/bin/env python3
"""Wall Street floor. One book. 120 traders. No buys.

The traders are the floor staff. They are not 120 strategies and they do not
send orders. A check always skips.
"""
from __future__ import annotations

import sys

# House count. The city pit draws this many seats. Stay above 100.
HEADCOUNT = 120


def evaluate() -> dict:
    line = f"{HEADCOUNT} traders on the floor. One book. It does not trade."
    return {"action": "skip", "reason": line, "traders": HEADCOUNT}


def main() -> int:
    if "--reset" in sys.argv:
        print("reset paper account")
        return 0
    row = evaluate()
    print("SIGNAL: SKIP " + row["reason"])
    print("CARD: " + row["reason"])
    print("no trade")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
