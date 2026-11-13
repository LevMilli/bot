#!/usr/bin/env python3
"""Market snapshots building. Support only: it buys nothing and holds no cash.

Saves one top-of-book snapshot of every watched Kalshi series
(``snapshot_model.py``). On the desk the recordings live on the /data volume.
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

import snapshot_model as rm  # noqa: E402
import kalshi_shadow_tower as engine  # noqa: E402


def recordings_dir(here: str) -> str:
    """The volume copy when the desk has one (survives deploys), else the tower folder."""
    try:
        import pimp_desk

        durable = pimp_desk.settlement_dir()
    except Exception:  # noqa: BLE001
        durable = None
    if durable:
        return os.path.join(durable, os.path.basename(HERE), "recordings")
    return os.path.join(here, "recordings")


def read_tickers(tickers: list[str]) -> list[dict]:
    """All the given Kalshi markets in one public read (shared gateway)."""
    data = engine.public_json(f"{engine.KALSHI}/markets?tickers={','.join(tickers)}")
    return [m for m in (data or {}).get("markets") or [] if isinstance(m, dict)]


def main(argv: list[str] | None = None, *, here: str | None = None, list_open=None,
         now: dt.datetime | None = None, folder: str | None = None, tickers_read=None) -> int:
    here = here or HERE
    now = now or dt.datetime.now(dt.timezone.utc)
    os.makedirs(here, exist_ok=True)
    folder = folder or recordings_dir(here)
    list_open = list_open or engine.kalshi_open_markets
    acct = os.path.join(here, "paper_account.json")
    state = engine.read_json(acct) or {}
    state.update({"cash": 0.0, "open": [], "closed": [], "paper_only": True, "shadow_only": True,
                  "live_orders": False, "stake_usd": 0.0, "research": True})
    windows = dict(state.get("windows_15m") or {})
    full = rm.full_due(state, now)
    notes: list[str] = []
    markets = 0
    if full:
        snap, notes = rm.snapshot(list_open, now)
        markets = sum(len(v) for v in snap["series"].values())
        if markets:
            rm.save(folder, snap, now)
        state["last_full"] = now.isoformat(timespec="seconds")
    # B19: every minute, the 15-minute windows in their last 14 minutes.
    fast, fast_notes, reads = rm.fast_snapshot(list_open, tickers_read or read_tickers, windows, now)
    fast_n = sum(len(v) for v in fast["series"].values())
    if fast_n:
        rm.save(folder, fast, now)
    notes += fast_notes
    state["windows_15m"] = windows
    state["fast_15m"] = {"at": now.isoformat(timespec="seconds"), "markets": fast_n, "reads": reads,
                         "runs": int((state.get("fast_15m") or {}).get("runs") or 0) + 1}
    gone = rm.prune(folder)
    use = rm.usage(folder)
    state["checks"] = int(state.get("checks") or 0) + 1
    state["last_check"] = now.isoformat(timespec="seconds")
    state["recordings"] = dict(use, folder=folder)
    engine.write_json(acct, state)
    for note in notes[:5]:
        print(f"NOTE: {note}")
    if full:
        line = f"Market snapshots: {markets} markets in {len(snap['series'])} series saved"
    else:
        line = "Market snapshots: full snapshot not due"
    line += (f"; 15m every minute: {fast_n} windows recorded; "
             f"{use['days']} days on file ({use['bytes'] / 1e6:.1f} MB)")
    if gone:
        line += f"; removed {len(gone)} oldest days to stay under {rm.MAX_BYTES // 2**20} MB"
    print("CARD: " + line + ".")
    print("no trade")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
