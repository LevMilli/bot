#!/usr/bin/env python3
"""Fill-realism lab building. Research only: it buys nothing and holds no cash.

Checks every tower's pretend fills against what really traded on Kalshi (and
the next candle for Coinbase spot and QQQ), using ``lab_model.py``. Writes
``fill_realism.json``. It never changes how any tower buys or sells.
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

import lab_model as lm  # noqa: E402
import kalshi_shadow_tower as engine  # noqa: E402

COINBASE_CANDLES = "https://api.exchange.coinbase.com/products/{product}/candles?granularity=60&start={start}&end={end}"
YAHOO_1M = "https://query1.finance.yahoo.com/v8/finance/chart/QQQ?interval=1m&period1={start}&period2={end}"
UA = {"User-Agent": "paper-bot/1.0 (fill-realism-lab)"}


def kalshi_trades(ticker: str, min_ts: int, max_ts: int) -> list[dict]:
    """Public Kalshi trades for one market in a time window (shared gateway)."""
    data = engine.public_json(f"{engine.KALSHI}/markets/trades?ticker={ticker}"
                              f"&min_ts={int(min_ts)}&max_ts={int(max_ts)}&limit=1000")
    return [t for t in (data or {}).get("trades") or [] if isinstance(t, dict)]


def next_open(bot: str, ticker: str, opened: float):
    """Open of the first 1-minute bar that starts after ``opened``."""
    start, end = int(opened), int(opened) + 600
    if bot == "coinbase-spot":
        iso = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).isoformat()  # noqa: E731
        rows = engine.public_json(COINBASE_CANDLES.format(product=ticker, start=iso(start), end=iso(end)),
                                  headers=UA) or []
        bars = sorted((r[0], r[3]) for r in rows if isinstance(r, list) and len(r) >= 5 and r[0] > opened)
        return bars[0][1] if bars else None
    if bot == "qqq-momentum":
        data = engine.public_json(YAHOO_1M.format(start=start, end=end), headers=UA) or {}
        res = ((data.get("chart") or {}).get("result") or [{}])[0] or {}
        stamps = res.get("timestamp") or []
        opens = (((res.get("indicators") or {}).get("quote") or [{}])[0] or {}).get("open") or []
        for ts, px in zip(stamps, opens):
            if ts > opened and px:
                return px
        return None
    return None


def load_states(root: str, specs, research) -> dict:
    out = {}
    for spec in specs:
        folder, name = spec.get("folder"), spec.get("state")
        if not folder or not name or spec.get("research") or spec.get("id") in research:
            continue
        try:
            with open(os.path.join(root, folder, name), encoding="utf-8") as fh:
                state = json.load(fh)
        except (OSError, ValueError):
            continue
        if isinstance(state, dict):
            out[str(spec["id"])] = state
    return out


def main(argv: list[str] | None = None, *, root: str | None = None, trades_fetch=None, candle_fetch=None,
         now: dt.datetime | None = None, specs=None) -> int:
    import new_towers

    if specs is None:
        import pimp_desk
        specs = pimp_desk.BOTS
    root = root or DESK_ROOT
    now = now or dt.datetime.now(dt.timezone.utc)
    here = os.path.join(root, os.path.basename(HERE))
    os.makedirs(here, exist_ok=True)
    acct = os.path.join(here, "paper_account.json")
    state = engine.read_json(acct) or {}
    state.update({"cash": 0.0, "open": [], "closed": [], "paper_only": True, "shadow_only": True,
                  "live_orders": False, "stake_usd": 0.0, "research": True})
    out_path = os.path.join(here, "fill_realism.json")
    prior = engine.read_json(out_path) or {}
    shadow = [s for s in new_towers.ACTIVE if not s.get("research")]
    body = lm.run(load_states(root, specs, new_towers.RESEARCH), prior, trades_fetch or kalshi_trades, now,
                  root=root, shadow_towers=shadow, candle_fetch=candle_fetch or next_open)
    engine.write_json(out_path, body)
    state["checks"] = int(state.get("checks") or 0) + 1
    state["last_check"] = now.isoformat(timespec="seconds")
    state["flagged_beats_tape"] = body["flagged_beats_tape"]
    engine.write_json(acct, state)
    for note in body.get("notes") or []:
        print(f"NOTE: {note}")
    print("CARD: " + lm.card(body))
    print("no trade")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
