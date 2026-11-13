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

import exit_model as em  # noqa: E402
import whatif_model as wm  # noqa: E402
import kalshi_shadow_tower as engine  # noqa: E402


def kalshi_trades(ticker: str, min_ts: int, max_ts: int) -> list[dict]:
    """Public Kalshi trades for one market in a time window (shared gateway)."""
    data = engine.public_json(f"{engine.KALSHI}/markets/trades?ticker={ticker}"
                              f"&min_ts={int(min_ts)}&max_ts={int(max_ts)}&limit=1000")
    return [t for t in (data or {}).get("trades") or [] if isinstance(t, dict)]


def accounts(root: str) -> list[tuple[str, str]]:
    """[(bot_id, closed-trade state file)] for every trading tower on the desk (research rows skipped)."""
    import new_towers
    import pimp_desk

    out = []
    for spec in pimp_desk.BOTS:
        if spec["id"] in new_towers.RESEARCH:
            continue
        name = pimp_desk.ACCOUNT_FILES.get(spec["id"]) or spec.get("state") or ""
        if name and spec.get("folder"):
            out.append((spec["id"], os.path.join(root, spec["folder"], name)))
    return out


def exit_lab(root: str, here: str, now: dt.datetime, get=None, accts=None) -> dict:
    """B12: grade each exit rule on every closed Kalshi trade. Writes exits.json. Suggests only."""
    import new_towers

    logs = {s["id"]: wm.read_log(os.path.join(root, s["folder"]))
            for s in new_towers.ACTIVE if not s.get("research")}
    prior = engine.read_json(os.path.join(here, "exits.json")) or {}
    body = em.run(accts if accts is not None else accounts(root), logs, prior,
                  get or engine.public_json, now)
    engine.write_json(os.path.join(here, "exits.json"), body)
    return body


def main(argv: list[str] | None = None, *, root: str | None = None, fetch=None, trades_fetch=None,
         now: dt.datetime | None = None, exit_get=None, exit_accounts=None) -> int:
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
    body = wm.run(towers, root, prior, fetch or engine.kalshi_market, now,
                  trades_fetch=trades_fetch or kalshi_trades)
    engine.write_json(os.path.join(here, "whatif.json"), body)
    try:
        exits = exit_lab(root, here, now, exit_get, exit_accounts)
    except Exception as exc:  # noqa: BLE001 - the exit lab failing must not stop the what-if card
        exits = None
        print(f"NOTE: exit lab skipped ({type(exc).__name__})")
    state["checks"] = int(state.get("checks") or 0) + 1
    state["last_check"] = now.isoformat(timespec="seconds")
    engine.write_json(acct, state)
    print("CARD: " + wm.card(body))
    if exits is not None:
        for note in exits.get("notes") or []:
            print(f"NOTE: exit lab {note}")
        print("EXITS: " + em.card(exits))
    print("no trade")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
