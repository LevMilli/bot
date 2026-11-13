#!/usr/bin/env python3
"""Freshness inspector building. Research only: it buys nothing and holds no cash.

Checks that every building ran on time and how old each buy's price was
(``fresh_model.py``), and writes ``freshness.json``. Display only: it never
blocks a buy or restarts a tower. No network reads.
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

import fresh_model as fm  # noqa: E402
import kalshi_shadow_tower as engine  # noqa: E402


def gather(root: str, now: dt.datetime) -> tuple[list, dict]:
    import new_towers
    import pimp_desk

    runs = pimp_desk._load_runs(root)
    me = os.path.basename(HERE).replace("-paper", "")
    rows, trades = [], {}
    for spec in pimp_desk.BOTS:
        bot_id = spec["id"]
        slots = [s for s in pimp_desk.AUTO if s["id"] == bot_id]
        every = min((int(s["every_sec"]) for s in slots if "every_sec" in s), default=None)
        clock = any("at_ct" in s for s in slots)
        try:
            paused = pimp_desk.bot_paused(root, bot_id)
            nxt = pimp_desk._next_for(bot_id, root, now)
        except Exception:  # noqa: BLE001
            paused, nxt = False, ""
        run = runs.get(bot_id)
        if bot_id == me and not run:
            run = {"at": now.isoformat(timespec="seconds"), "ok": True}  # this run
        rows.append(fm.building(bot_id, spec["name"], run, every, clock, paused, now, nxt))
        if bot_id in new_towers.RESEARCH or spec.get("kind") == "floor" or not spec.get("state"):
            continue
        state = engine.read_json(os.path.join(root, spec["folder"], spec["state"])) or {}
        raw = [r for key in ("open", "closed") for r in (state.get(key) or []) if isinstance(r, dict)]
        if raw:
            trades[bot_id] = raw
    return rows, trades


def main(argv: list[str] | None = None, *, root: str | None = None, now: dt.datetime | None = None) -> int:
    root = root or DESK_ROOT
    now = now or dt.datetime.now(dt.timezone.utc)
    here = os.path.join(root, os.path.basename(HERE))
    os.makedirs(here, exist_ok=True)
    acct = os.path.join(here, "paper_account.json")
    state = engine.read_json(acct) or {}
    state.update({"cash": 0.0, "open": [], "closed": [], "paper_only": True, "shadow_only": True,
                  "live_orders": False, "stake_usd": 0.0, "research": True})
    rows, trades = gather(root, now)
    body = fm.inspect(rows, trades, now)
    engine.write_json(os.path.join(here, "freshness.json"), body)
    state["checks"] = int(state.get("checks") or 0) + 1
    state["last_check"] = now.isoformat(timespec="seconds")
    state["counts"] = body["counts"]
    engine.write_json(acct, state)
    print("CARD: " + fm.card(body))
    print("no trade")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
