#!/usr/bin/env python3
"""What-if lab building. Research only: it buys nothing and holds no cash.

Grades the rows the towers logged but did not buy, and measures how long
cross-venue gaps last (``whatif_model.py``). Writes ``whatif.json``.
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

import whatif_model as wm  # noqa: E402
import kalshi_shadow_tower as engine  # noqa: E402


def main(argv: list[str] | None = None, *, root: str | None = None, fetch=None,
         now: dt.datetime | None = None) -> int:
    import new_towers

    root = root or DESK_ROOT
    now = now or dt.datetime.now(dt.timezone.utc)
    here = os.path.join(root, os.path.basename(HERE))
    os.makedirs(here, exist_ok=True)
    acct = os.path.join(here, "paper_account.json")
    state = engine.read_json(acct) or {}
    state.update({"cash": 0.0, "open": [], "closed": [], "paper_only": True, "shadow_only": True,
                  "live_orders": False, "stake_usd": 0.0, "research": True})
    towers = [s for s in new_towers.ACTIVE if not s.get("research")]
    prior = engine.read_json(os.path.join(here, "whatif.json")) or {}
    body = wm.run(towers, root, prior, fetch or engine.kalshi_market, now)
    engine.write_json(os.path.join(here, "whatif.json"), body)
    state["checks"] = int(state.get("checks") or 0) + 1
    state["last_check"] = now.isoformat(timespec="seconds")
    engine.write_json(acct, state)
    print("CARD: " + wm.card(body))
    print("no trade")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
