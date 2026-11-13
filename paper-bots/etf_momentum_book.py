"""Shared paper book for the SPY and IWM momentum towers (twins of QQQ momentum).

Same rules as ``qqq-momentum-paper`` (its ``qqq_model.py`` is read here without
changing it): a noise-area band around the open, checks at HH:00 and HH:30, a
band/VWAP trailing stop, and flat by the 16:00 close. Only the symbol differs.
Shadow paper shares only; no broker is connected.

This is a copy of the QQQ book with the symbol made a setting, so QQQ itself is
untouched. The three move together on most days, so they are close to one bet.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import os
import sys
import time

DESK_ROOT = os.path.dirname(os.path.abspath(__file__))
if DESK_ROOT not in sys.path:
    sys.path.insert(0, DESK_ROOT)

import kalshi_shadow_tower as engine  # noqa: E402 - read_json / write_json (volume-safe)


def _load_qqq_model():
    spec = importlib.util.spec_from_file_location(
        "qqq_model_etf_readonly", os.path.join(DESK_ROOT, "qqq-momentum-paper", "qqq_model.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


qm = _load_qqq_model()

FLOOR = 0.02            # locked equity_qqq floor: clear the band by 2% of its width
TICKET = 25.0
STARTER = 500.0
FRESH_MIN = 10
CACHE_SEC = 240
RESEARCH_MAX_BYTES = 2_000_000
SYMBOLS = ("SPY", "IWM")


def bars_url(symbol: str) -> str:
    return (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            "?interval=5m&range=30d&includePrePost=false")


def fetch_chart(here: str, symbol: str) -> dict:
    cache = os.path.join(here, "bars_cache.json")
    saved = engine.read_json(cache) or {}
    if saved.get("chart") and saved.get("symbol") == symbol and time.time() - float(saved.get("at") or 0) < CACHE_SEC:
        return saved["chart"]
    import public_http

    raw = public_http.read(bars_url(symbol), headers={"User-Agent": f"Mozilla/5.0 (paper-bot {symbol} read-only)"},
                           timeout=20, tries=2)
    chart = json.loads(raw.decode("utf-8"))
    meta = ((chart.get("chart") or {}).get("result") or [{}])[0].get("meta") or {}
    if meta.get("symbol") and str(meta["symbol"]).upper() != symbol:
        raise ValueError(f"asked for {symbol}, got {meta.get('symbol')}")
    engine.write_json(cache, {"at": time.time(), "symbol": symbol, "chart": chart})
    return chart


def _close(state: dict, pos: dict, price: float, why: str, now: dt.datetime) -> dict:
    px = qm.fill(pos["side"], price, False)
    pnl = round(qm.trade_pnl(pos["side"], pos["contracts"], pos["entry"], px), 4)
    row = dict(pos, exit=why, exit_price=round(px, 4), pnl=pnl, payout=round(pos["cost"] + pnl, 4),
               closed=now.isoformat(timespec="seconds"))
    state["cash"] = round(float(state["cash"]) + pos["cost"] + pnl, 4)
    state["closed"].append(row)
    state["open"] = [p for p in state["open"] if p is not pos]
    return row


def _open(state: dict, side: str, price: float, why: str, now: dt.datetime, day: str, symbol: str = "QQQ") -> dict | None:
    if float(state["cash"]) + 1e-9 < TICKET:
        return None
    px = qm.fill(side, price, True)
    pos = {"ticker": symbol, "event": f"{symbol}-{day}", "side": side, "label": f"{symbol} {side}",
           "game": f"{symbol} intraday", "contracts": round(TICKET / px, 6), "entry": round(px, 4),
           "ask": round(px, 4), "cost": TICKET, "why": why, "opened": now.isoformat(timespec="seconds"),
           "day": day, "paper_only": True, "shadow_only": True,
           "exit_plan": {"kind": "band/VWAP trailing stop, flat by 16:00"}}
    state["cash"] = round(float(state["cash"]) - TICKET, 4)
    state["open"].append(pos)
    return pos


def check(state: dict, days: list[dict], now: dt.datetime, *, blocked: bool = False, symbol: str = "QQQ") -> tuple[list[str], list[dict]]:
    """Advance the paper book to ``now``. Returns (event lines, research rows)."""
    lines, rows = [], []
    et = now.astimezone(qm.NY)
    today = et.date().isoformat()
    by_date = {d["date"]: i for i, d in enumerate(days)}
    # A position left from an earlier session closes at that session's close.
    for pos in list(state["open"]):
        if pos.get("day") != today and pos.get("day") in by_date:
            row = _close(state, pos, days[by_date[pos["day"]]]["close"], "flat at the close (late)", now)
            lines.append(f"EXIT: {row['label']} flat at the close pnl {row['pnl']:+.2f}")
    if today not in by_date:
        return lines + [f"SKIP: no {symbol} session today yet (closed, weekend or holiday)"], rows
    i = by_date[today]
    day = days[i]
    now_min = et.hour * 60 + et.minute - qm.OPEN_MIN
    done = state.setdefault("done", {}).setdefault(today, [])
    for t in qm.CHECKS:
        if t in done or now_min < t or t not in day["bars"]:
            continue
        done.append(t)
        b = qm.bands(days, i, t)
        stamp = (dt.datetime.combine(et.date(), dt.time(9, 30), qm.NY) + dt.timedelta(minutes=t)).strftime("%H:%M")
        if b is None:
            rows.append({"t": stamp, "action": "skip", "reason": "need 10 past sessions for the band"})
            continue
        row = {"t": stamp, "close": round(b["close"], 2), "upper": round(b["upper"], 2),
               "lower": round(b["lower"], 2), "vwap": round(b["vwap"] or 0, 2), "sigma": round(b["sigma"], 5)}
        if now_min - t > FRESH_MIN:
            rows.append(dict(row, action="missed", reason=f"bar closed {now_min - t} min ago; no late fills"))
            continue
        pos = state["open"][0] if state["open"] else None
        exit_now, new_side, why = qm.decide(pos["side"] if pos else None, b, FLOOR)
        row.update(action="hold" if pos else "flat", reason=why)
        if exit_now and pos:
            out = _close(state, pos, b["close"], "stop", now)
            lines.append(f"EXIT: {out['label']} stop at {out['exit_price']:.2f} pnl {out['pnl']:+.2f}")
            row["action"], pos = "exit", None
        if new_side and pos is None:
            if blocked:
                row["action"], row["reason"] = "skip", "desk entry gate; " + why
            else:
                got = _open(state, new_side, b["close"], why, now, today, symbol)
                if got:
                    lines.append(f"BUY: {got['label']} at {got['entry']:.2f} ({why})")
                    row["action"] = "enter " + new_side
                else:
                    row["action"], row["reason"] = "skip", "paper cash below ticket"
        rows.append(row)
    session_over = now_min >= qm.SESSION_MIN or (day["last"] < qm.SESSION_MIN and now_min >= day["last"] + 15)
    if session_over:
        for pos in list(state["open"]):
            row = _close(state, pos, day["close"], "flat at the close", now)
            lines.append(f"EXIT: {row['label']} flat at the close {row['exit_price']:.2f} pnl {row['pnl']:+.2f}")
    state["done"] = {k: v for k, v in state["done"].items() if k >= (et.date() - dt.timedelta(days=7)).isoformat()}
    return lines, rows


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


def main(symbol: str, tower_id: str, name: str, here: str, argv: list[str] | None = None, *,
         chart: dict | None = None, now: dt.datetime | None = None) -> int:
    if symbol not in SYMBOLS:
        raise ValueError(f"unknown symbol {symbol}")
    now = now or dt.datetime.now(dt.timezone.utc)
    os.makedirs(here, exist_ok=True)
    acct = os.path.join(here, "paper_account.json")
    state = engine.read_json(acct) or {}
    for key, value in {"cash": STARTER, "open": [], "closed": [], "checks": 0}.items():
        state.setdefault(key, value)
    state.update({"paper_only": True, "shadow_only": True, "live_orders": False})
    try:
        days = qm.parse_bars(chart if chart is not None else fetch_chart(here, symbol))
    except Exception as exc:  # noqa: BLE001 - a failed read is a skip, never a guess
        days = []
        print(f"NOTE: {symbol} bars read failed ({type(exc).__name__}); waiting")
    blocked = os.environ.get("DESK_BLOCK_ENTRIES") == "1"
    lines, rows = (check(state, days, now, blocked=blocked, symbol=symbol) if days
                   else ([f"SKIP: no {symbol} bars"], []))
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
    last = rows[-1] if rows else None
    if bought:
        print(f"CARD: paper {bought[-1][5:]} ({name}, shadow)")
        return 0
    held = state["open"][0] if state["open"] else None
    if held:
        text = f"holding {held['label']} from {held['entry']:.2f}"
    elif last:
        text = f"{last['t']} check: {last.get('reason') or last['action']}"
    else:
        text = (lines[-1].split(": ", 1)[-1] if lines else "waiting for the next half-hour check")
    print(f"CARD: {name}: {text}.")
    print("no trade")
    return 0
