#!/usr/bin/env python3
"""Result splits building. Research only: it buys nothing and holds no cash.

Cuts every trading tower's closed paper trades by market, exit, hour and side
(``split_model.py``) and writes ``splits.json``. Losses stay in every group. It
only suggests; it never pauses or changes a tower.
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

import split_model as sm  # noqa: E402
import kalshi_shadow_tower as engine  # noqa: E402

ALL_TIME_DAYS = 36500


def histories(root: str, now: dt.datetime) -> dict:
    """{bot_id: (name, closed rows)} through the same views the dashboard uses."""
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
        except Exception:  # one bad state file must not stop the rest
            continue
        out[spec["id"]] = (spec["name"], view.get("history") or [])
    return out


def main(argv: list[str] | None = None, *, root: str | None = None, now: dt.datetime | None = None) -> int:
    import desk_profit
    import pimp_desk

    root = root or DESK_ROOT
    now = now or dt.datetime.now(dt.timezone.utc)
    here = os.path.join(root, os.path.basename(HERE))
    os.makedirs(here, exist_ok=True)
    acct = os.path.join(here, "paper_account.json")
    state = engine.read_json(acct) or {}
    state.update({"cash": 0.0, "open": [], "closed": [], "paper_only": True, "shadow_only": True,
                  "live_orders": False, "stake_usd": 0.0, "research": True})

    def pnl_of(row):
        # Same after-fee, 1-cent-a-contract fill tax the scorekeeper uses. No time window.
        got = desk_profit._history_pnls([row], window_days=ALL_TIME_DAYS, now=now,
                                        fill_tax=desk_profit.FILL_ADVERSE_TAX)
        return got[0] if got else None

    body = sm.run(histories(root, now), now, pnl_of=pnl_of, tz=pimp_desk.CT)
    engine.write_json(os.path.join(here, "splits.json"), body)
    state["checks"] = int(state.get("checks") or 0) + 1
    state["last_check"] = now.isoformat(timespec="seconds")
    state["flags"] = len(body["flags"])
    engine.write_json(acct, state)
    print("CARD: " + sm.card(body))
    print("no trade")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
