#!/usr/bin/env python3
"""Meme price check: research building for the Memecoin tower (idea B15).

Every 15 minutes it reads the Memecoin tower's open positions and the mints it
checked recently (``../memecoin-paper``, read-only), asks DexScreener and
Jupiter for each price, and counts how often a 2% gap (or a missing price)
WOULD have stopped a buy or a sale. Buys nothing; the Memecoin tower is not
changed. The tally in price_check.json is what a later flag would be judged on.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DESK_ROOT = os.path.dirname(HERE)
for path in (DESK_ROOT, HERE):
    if path not in sys.path:
        sys.path.insert(0, path)

import kalshi_shadow_tower as engine  # noqa: E402 - read_json / write_json / public_json
import price_check as pc  # noqa: E402

NAME = "Meme price check"
MEME = os.path.join(DESK_ROOT, "memecoin-paper")
UA = {"User-Agent": "Mozilla/5.0 (paper)"}
KEEP_ROWS = 200


def _why(exc: Exception) -> str:
    code = getattr(exc, "code", None)
    return f"HTTP {code}" if code else type(exc).__name__


def main(argv: list[str] | None = None, *, here: str | None = None, meme: str | None = None,
         dex_get=None, jup_get=None, now: dt.datetime | None = None) -> int:
    here = here or HERE
    meme = meme or MEME
    now = now or dt.datetime.now(dt.timezone.utc)
    os.makedirs(here, exist_ok=True)
    acct = os.path.join(here, "paper_account.json")
    state = engine.read_json(acct) or {}
    state.update({"cash": 0.0, "open": [], "closed": [], "paper_only": True, "shadow_only": True,
                  "live_orders": False, "stake_usd": 0.0, "research": True})
    watch = pc.watch_list(engine.read_json(os.path.join(meme, "positions.json")),
                          os.path.join(meme, "checks.csv"))
    notes, rows = [], []
    if watch:
        ids = ",".join(w["mint"] for w in watch)
        try:
            dex = pc.dex_prices((dex_get or engine.public_json)(pc.DEX.format(mints=ids), headers=UA))
        except Exception as exc:  # noqa: BLE001 - fails closed: every row reads as missing
            dex = {}
            notes.append(f"DexScreener {_why(exc)}")
        try:
            jup = pc.jup_prices((jup_get or engine.public_json)(pc.JUP.format(mints=ids), headers=UA))
        except Exception as exc:  # noqa: BLE001
            jup = {}
            notes.append(f"Jupiter {_why(exc)}")
        rows = pc.compare(watch, dex, jup)
    out_path = os.path.join(here, "price_check.json")
    saved = engine.read_json(out_path) or {}
    tally = dict(saved.get("tally") or {})
    for key in ("checks", "mints", "agree", "gap_over_2pct", "missing", "open_blocked"):
        tally.setdefault(key, 0)
    tally["checks"] += 1
    for row in rows:
        tally["mints"] += 1
        if not row["block"]:
            tally["agree"] += 1
        elif row["gap"] is None:
            tally["missing"] += 1
        else:
            tally["gap_over_2pct"] += 1
        if row["block"] and row["why"] == "open":
            tally["open_blocked"] += 1
    history = list(saved.get("recent_blocks") or [])
    history.extend(dict(r, at=now.isoformat(timespec="seconds")) for r in rows if r["block"])
    engine.write_json(out_path, {"updated": now.isoformat(timespec="seconds"), "max_gap": pc.MAX_GAP,
                                 "tally": tally, "last": rows, "recent_blocks": history[-KEEP_ROWS:],
                                 "paper_only": True})
    state["checks"] = int(state.get("checks") or 0) + 1
    state["last_check"] = now.isoformat(timespec="seconds")
    state["price_check"] = tally
    engine.write_json(acct, state)
    for note in notes:
        print(f"NOTE: {note}")
    blocks = sum(1 for r in rows if r["block"])
    if not watch:
        line = "no memecoin positions or recent checks to compare"
    else:
        line = f"{len(rows)} mints compared, {blocks} would be blocked (gap over 2% or a price missing)"
    seen = tally["mints"]
    if seen:
        line += f"; all time {tally['agree'] / seen:.0%} agree over {seen} reads"
    print(f"CARD: {NAME}: {line}.")
    print("no trade")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
