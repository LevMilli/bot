#!/usr/bin/env python3
"""Coinbase maker: shadow twin of Coinbase spot that assumes limit orders.

Idea B17. Same ETH-USD / SOL-USD 15-minute signal as the Coinbase spot tower,
priced at the maker fee with fills only when a candle trades through our price
(rules in ``maker_model.py``). Public Coinbase candles only; no key, no orders.

Every check replays the completed bars since the last check: resting orders
fill or expire, the open position checks its exits. A NEW limit order is placed
only from a signal bar that closed in the last 20 minutes (no back-dated
signals). Paper only. Shadow only. $25 ticket, $500 sleeve, one order or
position at a time. Coinbase spot itself is not changed.
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

import kalshi_shadow_tower as engine  # noqa: E402 - read_json / write_json (volume-safe)
import maker_model as mm  # noqa: E402

ID = "coinbase-maker"
NAME = "Coinbase maker"
FLOOR = 0.05
TICKET = 25.0
STARTER = 500.0
FRESH_SEC = 20 * 60
CANDLE_URL = "https://api.exchange.coinbase.com/products/{product}/candles?granularity=900"
UA = {"User-Agent": "Mozilla/5.0 (paper)"}
RESEARCH_MAX_BYTES = 2_000_000


def fetch_candles(product: str):
    return engine.public_json(CANDLE_URL.format(product=product), headers=UA)


def _iso(ts: float) -> str:
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat(timespec="seconds")


def _close(state: dict, pos: dict, reason: str, price: float, maker: bool, bar_t: int) -> dict:
    pnl, fees = mm.pnl(pos["cost"], pos["entry"], price, maker)
    row = dict(pos, exit=reason, exit_price=round(price, 6), maker_exit=maker, fee=fees, pnl=pnl,
               payout=round(pos["cost"] + pnl, 4), closed=_iso(bar_t + mm.BAR_SEC))
    state["cash"] = round(float(state["cash"]) + pos["cost"] + pnl, 4)
    state["closed"].append(row)
    state["open"] = [p for p in state["open"] if p is not pos]
    return row


def step_product(state: dict, product: str, bars: list[dict], now: dt.datetime, *,
                 blocked: bool = False) -> tuple[list[str], dict]:
    """Advance one product through its new completed bars."""
    lines = []
    seen = state.setdefault("seen", {})
    last = int(seen.get(product) or 0)
    closes = [b["close"] for b in bars]
    first_run = last == 0
    new = [i for i, b in enumerate(bars) if b["t"] > last]
    if first_run:
        new = new[-1:]  # first run: only the latest bar, nothing back-filled
    row = {"product": product, "bars": len(bars)}
    for i in new:
        bar = bars[i]
        z = mm.z_of(closes[: i + 1])
        order = next((o for o in state["orders"] if o["product"] == product), None)
        if order and bar["t"] > order["bar_t"]:
            if mm.entry_fills(order["limit"], bar):
                state["orders"].remove(order)
                pos = {"ticker": product, "event": f"{product}-{order['bar_t']}", "product": product,
                       "side": "long", "label": f"{product} long (maker)", "entry": order["limit"],
                       "ask": order["limit"], "contracts": round(TICKET / order["limit"], 8),
                       "cost": TICKET, "take_profit": round(order["limit"] * (1 + mm.take_profit_move(FLOOR)), 6),
                       "why": order["why"], "opened": _iso(bar["t"] + mm.BAR_SEC), "bar_t": bar["t"],
                       "paper_only": True, "shadow_only": True,
                       "exit_plan": {"kind": "maker take-profit / stop -1.5% / z<=-2 / 24h"}}
                state["cash"] = round(float(state["cash"]) - TICKET, 4)
                state["open"].append(pos)
                lines.append(f"BUY: {pos['label']} filled at {pos['entry']:.4f} ({order['why']})")
                continue  # the fill bar does not also run exits
            order["waited"] = int(order.get("waited") or 0) + 1
            if order["waited"] >= mm.EXPIRE_BARS:
                state["orders"].remove(order)
                state.setdefault("expired", 0)
                state["expired"] += 1
                lines.append(f"SKIP: {product} limit {order['limit']:.4f} not filled in {mm.EXPIRE_BARS} bars; cancelled")
        pos = next((p for p in state["open"] if p["product"] == product), None)
        if pos and bar["t"] > pos["bar_t"]:
            age_h = (bar["t"] + mm.BAR_SEC - pos["bar_t"] - mm.BAR_SEC) / 3600.0
            out = mm.exit_on_bar(pos, bar, z, age_h)
            if out:
                done = _close(state, pos, out[0], out[1], out[2], bar["t"])
                lines.append(f"EXIT: {done['label']} {done['exit']} at {done['exit_price']:.4f} pnl {done['pnl']:+.2f}")
    sig = mm.signal(closes, FLOOR)
    row.update(sig)
    row["need"] = round(mm.bar_needed(FLOOR), 4)
    if bars and sig["action"] == "buy":
        fresh = now.timestamp() - (bars[-1]["t"] + mm.BAR_SEC) <= FRESH_SEC
        busy = state["open"] or state["orders"]
        if not fresh:
            row.update(action="skip", reason="signal bar too old; no late orders")
        elif busy:
            row.update(action="skip", reason="one order or position at a time")
        elif blocked:
            row.update(action="skip", reason="desk entry gate")
        elif float(state["cash"]) + 1e-9 < TICKET:
            row.update(action="skip", reason="paper cash below ticket")
        elif bars[-1]["t"] > last or first_run:
            why = f"z {sig['z']:.2f}, move {sig['ret']:.2%}, edge {sig['edge']:.4f} at maker"
            state["orders"].append({"product": product, "limit": bars[-1]["close"], "bar_t": bars[-1]["t"],
                                    "waited": 0, "why": why, "placed": now.isoformat(timespec="seconds")})
            lines.append(f"ORDER: {product} limit buy {bars[-1]['close']:.4f} resting ({why})")
            row["action"] = "order"
    if bars:
        seen[product] = bars[-1]["t"]
    return lines, row


def _log(here: str, now: dt.datetime, rows: list[dict], note: str) -> None:
    path = os.path.join(here, "research.jsonl")
    try:
        if os.path.getsize(path) > RESEARCH_MAX_BYTES:
            real = os.path.realpath(path)
            os.replace(real, os.path.join(os.path.dirname(real), "research.jsonl.1"))
    except OSError:
        pass
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"at": now.isoformat(timespec="seconds"), "paper_only": True,
                                 "note": note, "checks": rows}) + "\n")


def main(argv: list[str] | None = None, *, here: str | None = None, candles: dict | None = None,
         now: dt.datetime | None = None) -> int:
    here = here or HERE
    now = now or dt.datetime.now(dt.timezone.utc)
    os.makedirs(here, exist_ok=True)
    acct = os.path.join(here, "paper_account.json")
    if "--reset" in list(argv or []):
        engine.write_json(acct, {"cash": STARTER, "open": [], "closed": [], "orders": [], "checks": 0})
        print(f"{NAME}: reset to ${STARTER:.0f} paper")
        return 0
    state = engine.read_json(acct) or {}
    for key, value in {"cash": STARTER, "open": [], "closed": [], "orders": [], "checks": 0}.items():
        state.setdefault(key, value)
    state.update({"paper_only": True, "shadow_only": True, "live_orders": False})
    blocked = os.environ.get("DESK_BLOCK_ENTRIES") == "1"
    lines, rows = [], []
    for product in mm.PRODUCTS:
        try:
            raw = candles[product] if candles is not None else fetch_candles(product)
        except Exception as exc:  # noqa: BLE001 - a failed read is a skip, never a guess
            code = getattr(exc, "code", None)
            lines.append(f"SKIP: {product} candles {'HTTP ' + str(code) if code else type(exc).__name__}")
            continue
        bars = mm.parse_candles(raw, now.timestamp())
        got, row = step_product(state, product, bars, now, blocked=blocked)
        lines.extend(got)
        rows.append(row)
    state["checks"] = int(state["checks"]) + 1
    state["last_check"] = now.isoformat(timespec="seconds")
    engine.write_json(acct, state)
    try:
        _log(here, now, rows, "; ".join(lines))
    except OSError:
        pass
    for line in lines:
        print(line)
    bought = [l for l in lines if l.startswith("BUY:")]
    if bought:
        print(f"CARD: paper {bought[-1][5:]} ({NAME}, shadow)")
        return 0
    if state["open"]:
        held = state["open"][0]
        text = f"holding {held['label']} from {held['entry']:.4f}"
    elif state["orders"]:
        o = state["orders"][0]
        text = f"limit buy {o['product']} {o['limit']:.4f} resting"
    else:
        best = max(rows, key=lambda r: r.get("ret") or -1, default=None)
        need = mm.bar_needed(FLOOR)
        text = (f"no fee-clear long at maker (best bar {best['ret']:+.2%}, needs about {need:.0%})"
                if best and best.get("ret") is not None else "waiting for candles")
    print(f"CARD: {NAME}: {text}.")
    print("no trade")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
