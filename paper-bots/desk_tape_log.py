"""
desk_tape_log.py — short, readable log lines for the 15-minute Kalshi towers.

Two kinds of line, both written to the server log after a BTC 15m or
Commodity 15m paper run:

  tally <bot>: cash $X, open N, bought today B, settled W-L, today $P
  window tape {json}   one line per 15-minute window that just settled

The window line holds the whole market path for that window (Kalshi yes price
and spot when the bot saw it), the settled result, and what the tower did
(bought a side, or the last skip note). Staff read these lines from the log
to chart and review each window afterwards.

Read only. Never places orders and never changes any tower gate.
"""
from __future__ import annotations

import calendar
import json
import os
import threading
import time
from typing import Any

HISTORY_NAME = "kalshi_crypto_history.json"
TAPE_BOTS = {
    "btc15m": ("btc15m-signal", "paper_account.json"),
    "commodity-15m": ("commodity-15m-paper", "paper_account.json"),
}
SERIES_BOT = {
    "KXBTC15M": "btc15m",
    "KXETH15M": "btc15m",
}
# Only settles this recent are logged, so a restart does not repeat old days.
RECENT_SECONDS = 2 * 3600
MAX_PATH_POINTS = 30

_seen: set[str] = set()
_seen_lock = threading.Lock()


def _read(path: str) -> Any:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _f(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _epoch(text: Any) -> float | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S UTC"):
        try:
            return float(calendar.timegm(time.strptime(raw, fmt)))
        except ValueError:
            continue
    return None


def account(root: str, bot_id: str) -> dict:
    folder, name = TAPE_BOTS[bot_id]
    data = _read(os.path.join(root, folder, name))
    return data if isinstance(data, dict) else {}


def tally_line(root: str, bot_id: str) -> str:
    """One plain line: cash, open bets, buys and results since the midnight reload."""
    acct = account(root, bot_id)
    open_rows = [p for p in acct.get("open") or [] if isinstance(p, dict)]
    closed = [p for p in acct.get("closed") or [] if isinstance(p, dict)]
    wins = sum(1 for p in closed if (_f(p.get("pnl")) or 0) > 0)
    losses = sum(1 for p in closed if (_f(p.get("pnl")) or 0) < 0)
    pnl = sum(_f(p.get("pnl")) or 0 for p in closed)
    cash = _f(acct.get("cash"))
    at_risk = sum(_f(p.get("cost")) or 0 for p in open_rows)
    cash_txt = "?" if cash is None else f"${cash:.2f}"
    return (
        f"tally {bot_id}: cash {cash_txt}, open {len(open_rows)} (${at_risk:.2f} at risk), "
        f"bought today {len(open_rows) + len(closed)}, settled {wins}-{losses}, today ${pnl:+.2f}"
    )


def _bot_rows(root: str) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for bot_id in TAPE_BOTS:
        acct = account(root, bot_id)
        for p in list(acct.get("open") or []) + list(acct.get("closed") or []):
            if isinstance(p, dict) and p.get("ticker"):
                out.setdefault(str(p["ticker"]), []).append(p | {"_bot": bot_id})
    return out


def _thin(rows: list[dict], cap: int = MAX_PATH_POINTS) -> list[dict]:
    if len(rows) <= cap:
        return rows
    step = (len(rows) - 1) / float(cap - 1)
    return [rows[round(i * step)] for i in range(cap)]


def window_record(history: dict, settle: dict, bot_rows: dict[str, list[dict]]) -> dict:
    """Whole-market summary for one settled window."""
    ticker = str(settle.get("ticker") or "")
    snaps = [s for s in history.get("snapshots") or [] if isinstance(s, dict) and s.get("ticker") == ticker]
    snaps.sort(key=lambda s: str(s.get("at") or ""))
    yes = [_f(s.get("yes_ask")) for s in snaps]
    yes = [y for y in yes if y is not None]
    spots = [_f(s.get("spot")) for s in snaps]
    spots = [x for x in spots if x is not None]
    target = _f(settle.get("target"))
    if target is None:
        target = next((_f(s.get("target")) for s in snaps if _f(s.get("target")) is not None), None)
    path = [
        {
            "t": str(s.get("at") or "")[11:16],
            "m": _f(s.get("minutes_left")),
            "y": _f(s.get("yes_ask")),
            "s": _f(s.get("spot")),
        }
        for s in _thin(snaps)
    ]
    notes = [str(s.get("note") or "") for s in snaps if s.get("side") and s.get("note")]
    trades = []
    for p in bot_rows.get(ticker) or []:
        trades.append({
            "bot": p.get("_bot"),
            "side": p.get("side"),
            "ask": _f(p.get("ask")),
            "cost": _f(p.get("cost")),
            "pnl": _f(p.get("pnl")),
            "extra": bool(p.get("extra")),
            "why": str(p.get("why") or "")[:80],
        })
    series = str(settle.get("series") or "")
    return {
        "ticker": ticker,
        "series": series,
        "bot": SERIES_BOT.get(series, "commodity-15m"),
        "result": settle.get("result"),
        "target": target,
        "spot_close": _f(settle.get("spot_close")),
        "checks": len(snaps),
        "yes_open": yes[0] if yes else None,
        "yes_low": min(yes) if yes else None,
        "yes_high": max(yes) if yes else None,
        "yes_last": yes[-1] if yes else None,
        "spot_low": min(spots) if spots else None,
        "spot_high": max(spots) if spots else None,
        "traded": trades,
        "last_note": notes[-1][:120] if notes else "",
        "path": path,
    }


def window_lines(root: str, now: float | None = None) -> list[str]:
    """New 'window tape' lines for windows settled in the last two hours."""
    history = _read(os.path.join(root, HISTORY_NAME))
    if not isinstance(history, dict):
        return []
    now = time.time() if now is None else now
    fresh = []
    for row in history.get("settles") or []:
        if not isinstance(row, dict) or not row.get("ticker"):
            continue
        when = _epoch(row.get("at"))
        if when is None or now - when > RECENT_SECONDS:
            continue
        key = f"{row['ticker']}|{row.get('result')}"
        with _seen_lock:
            if key in _seen:
                continue
            _seen.add(key)
        fresh.append(row)
    if not fresh:
        return []
    bot_rows = _bot_rows(root)
    return [
        "window tape " + json.dumps(window_record(history, row, bot_rows), separators=(",", ":"))
        for row in fresh
    ]


def reset_seen() -> None:
    with _seen_lock:
        _seen.clear()
