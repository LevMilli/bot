#!/usr/bin/env python3
"""Calibration lab building. Research only: it buys nothing and holds no cash.

Refreshes ``calibration.json`` from settled Kalshi markets and the new towers'
logged fair values. See ``../calibration_lab.py`` for the method.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DESK_ROOT = os.path.dirname(HERE)
if DESK_ROOT not in sys.path:
    sys.path.insert(0, DESK_ROOT)

import calibration_lab as lab  # noqa: E402
import kalshi_shadow_tower as engine  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    now = dt.datetime.now(dt.timezone.utc)
    acct = os.path.join(HERE, "paper_account.json")
    state = engine.read_json(acct) or {}
    state.update({"cash": 0.0, "open": [], "closed": [], "paper_only": True, "shadow_only": True,
                  "live_orders": False, "stake_usd": 0.0, "research": True})
    body = lab.run(DESK_ROOT, HERE, now)
    state["checks"] = int(state.get("checks") or 0) + 1
    state["last_check"] = now.isoformat(timespec="seconds")
    engine.write_json(acct, state)
    for note in body.get("notes") or []:
        print(f"NOTE: {note}")
    print("CARD: " + lab.card(body))
    print("no trade")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
