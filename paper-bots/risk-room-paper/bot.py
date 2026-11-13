#!/usr/bin/env python3
"""Risk room building. Research only: it buys nothing and holds no cash.

Groups every tower's open paper positions by what they ride on
(``risk_model.py``) and writes ``risk_room.json``. Display only: it never
blocks, sizes or sells a trade.
"""
from __future__ import annotations

import datetime as dt
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DESK_ROOT = os.path.dirname(HERE)
for path in (DESK_ROOT, HERE):
    if path not in sys.path:
        sys.path.insert(0, path)

import risk_model as rm  # noqa: E402
import kalshi_shadow_tower as engine  # noqa: E402


def open_positions(root: str, now: dt.datetime) -> dict:
    import new_towers
    import pimp_desk

    day = now.astimezone(pimp_desk.CT).date()
    runs = pimp_desk._load_runs(root)
    out = {}
    for spec in pimp_desk.BOTS:
        if spec["id"] in new_towers.RESEARCH or spec.get("kind") == "floor":
            continue
        try:
            view = pimp_desk._bot_view(spec, root, runs, day)
        except Exception:  # one bad state file must not stop the room
            continue
        rows = view.get("positions") or []
        if rows:
            out[spec["id"]] = (spec["name"], spec.get("category") or spec.get("kind") or "", rows)
    return out


def main(argv: list[str] | None = None, *, root: str | None = None, now: dt.datetime | None = None) -> int:
    root = root or DESK_ROOT
    now = now or dt.datetime.now(dt.timezone.utc)
    here = os.path.join(root, os.path.basename(HERE))
    os.makedirs(here, exist_ok=True)
    acct = os.path.join(here, "paper_account.json")
    state = engine.read_json(acct) or {}
    state.update({"cash": 0.0, "open": [], "closed": [], "paper_only": True, "shadow_only": True,
                  "live_orders": False, "stake_usd": 0.0, "research": True})
    body = rm.room(open_positions(root, now), now)
    engine.write_json(os.path.join(here, "risk_room.json"), body)
    state["checks"] = int(state.get("checks") or 0) + 1
    state["last_check"] = now.isoformat(timespec="seconds")
    state["flags"] = len(body["flags"])
    engine.write_json(acct, state)
    print("CARD: " + rm.card(body))
    print("no trade")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
