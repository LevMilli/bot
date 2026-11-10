#!/usr/bin/env python3
"""Wall Street floor. One book. 120 traders. No buys.

The traders are the floor staff. They are not 120 strategies and they do not
send orders. A check always skips.
"""
from __future__ import annotations

import sys

# House count. The city pit draws this many seats. Stay above 100.
HEADCOUNT = 120

# Six desks on one book. Seats sum to HEADCOUNT. None of them buy.
DEPARTMENTS = (
    {
        "id": "quote",
        "name": "Quote",
        "seats": 20,
        "job": "No client flow arrives, so this desk does not quote.",
    },
    {
        "id": "research",
        "name": "Research",
        "seats": 20,
        "job": "Writes the skip in one sentence a person can check.",
    },
    {
        "id": "risk",
        "name": "Risk",
        "seats": 20,
        "job": "Holds the veto. A buy on this floor is a mistake.",
    },
    {
        "id": "ledger",
        "name": "Ledger",
        "seats": 20,
        "job": "Cash stays at 0 and the position list stays empty.",
    },
    {
        "id": "control",
        "name": "Control",
        "seats": 20,
        "job": "Paper only. Keeps a key off this floor.",
    },
    {
        "id": "book",
        "name": "The book",
        "seats": 20,
        "job": "The only book on the floor, and it stays flat.",
    },
)


def evaluate() -> dict:
    seats = sum(int(row["seats"]) for row in DEPARTMENTS)
    if seats != HEADCOUNT:
        raise RuntimeError(f"floor seats {seats} must equal headcount {HEADCOUNT}")
    line = f"{HEADCOUNT} traders on six desks. One book. It does not trade."
    return {
        "action": "skip",
        "reason": line,
        "traders": HEADCOUNT,
        "departments": [dict(row) for row in DEPARTMENTS],
    }


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
