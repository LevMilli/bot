#!/usr/bin/env python3
"""Settlement auditor building. Support only: it buys nothing and holds no cash.

Once a day it rechecks every paper trade that was held to settlement against
Kalshi's official result (``audit_model.py``) and writes ``audit.json``.
Kalshi reads go through the shared gateway, at most 40 a run.
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

import audit_model as am  # noqa: E402
import kalshi_shadow_tower as engine  # noqa: E402


def main(argv: list[str] | None = None, *, root: str | None = None, fetch=None,
         now: dt.datetime | None = None) -> int:
    import pimp_desk  # the desk's bot list (folders and state files)

    root = root or DESK_ROOT
    now = now or dt.datetime.now(dt.timezone.utc)
    here = os.path.join(root, os.path.basename(HERE))
    os.makedirs(here, exist_ok=True)
    acct = os.path.join(here, "paper_account.json")
    state = engine.read_json(acct) or {}
    state.update({"cash": 0.0, "open": [], "closed": [], "paper_only": True, "shadow_only": True,
                  "live_orders": False, "stake_usd": 0.0, "research": True})
    prior = engine.read_json(os.path.join(here, "audit.json")) or {}
    body = am.run(am.load_states(root, pimp_desk.BOTS), prior, fetch or engine.kalshi_market, now)
    engine.write_json(os.path.join(here, "audit.json"), body)
    state["checks"] = int(state.get("checks") or 0) + 1
    state["last_check"] = now.isoformat(timespec="seconds")
    state["mismatches"] = len(body["mismatches"])
    engine.write_json(acct, state)
    for note in body.get("notes") or []:
        print(f"NOTE: {note}")
    print("CARD: " + am.card(body))
    print("no trade")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
