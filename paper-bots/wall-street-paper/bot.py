#!/usr/bin/env python3
"""Wall Street floor. One book. 120 traders. No buys.

The traders are the floor staff. They are not 120 strategies and they do not
send orders. A check always skips.
"""
from __future__ import annotations

import json
import math
import os
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


def _num(value):
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(n):
        return None
    return n


def read_book(snapshot=None) -> dict:
    """Read the city book the towers already wrote.

    A missing snapshot has no P/L. A number that is not already on the book
    is not filled in. This does not trade.
    """
    if not isinstance(snapshot, dict):
        return {
            "read": False,
            "pnl": None,
            "rows": [],
            "bought": False,
            "sold": False,
            "reason": "snapshot missing",
        }
    rows = []
    for bot in snapshot.get("bots") or []:
        if not isinstance(bot, dict):
            continue
        name = str(bot.get("id") or "").strip()
        if not name:
            continue
        realized = _num(bot.get("realized")) if "realized" in bot else None
        rows.append({"id": name, "realized": realized})
    desk = snapshot.get("desk") if isinstance(snapshot.get("desk"), dict) else {}
    if "realized" in desk:
        city = _num(desk.get("realized"))
    elif "pnl" in snapshot:
        city = _num(snapshot.get("pnl"))
    else:
        city = None
    return {
        "read": True,
        "pnl": city,
        "rows": rows,
        "bought": False,
        "sold": False,
        "reason": "city book",
    }


def _plain(bot: dict) -> str:
    ident = str(bot.get("id") or "").strip()
    if ident == "commodity-15m":
        return "commodity"
    name = str(bot.get("name") or "").strip()
    if name:
        return name
    return ident.replace("-", " ")


def _money(amount: float) -> str:
    if amount < 0:
        return f"−${abs(amount):.2f}"
    return f"${amount:.2f}"


def explain_book(snapshot=None) -> dict:
    """Say which tower a number belongs to.

    Commodity's number stays commodity's. It is not spread across the city.
    A missing number is not invented. This does not trade.
    """
    if not isinstance(snapshot, dict):
        return {"lines": [], "bought": False, "sold": False, "spread": False, "reason": "snapshot missing"}
    lines = []
    for bot in snapshot.get("bots") or []:
        if not isinstance(bot, dict) or "realized" not in bot:
            continue
        amount = _num(bot.get("realized"))
        who = _plain(bot)
        if amount is None or not who:
            continue
        lines.append(f"{who}'s {_money(amount)} stays {who}'s.")
    return {"lines": lines, "bought": False, "sold": False, "spread": False, "reason": "named"}


def _load_snapshot(path: str):
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


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
    snap = _load_snapshot(os.path.join(os.path.dirname(os.path.abspath(__file__)), "city_book.json"))
    read_book(snap)
    explain_book(snap)
    print("SIGNAL: SKIP " + row["reason"])
    print("CARD: " + row["reason"])
    print("no trade")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
