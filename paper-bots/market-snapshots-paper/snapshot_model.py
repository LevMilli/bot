"""Market snapshots: top-of-book snapshots of the Kalshi series the towers watch.

Every 15 minutes it lists each watched series' open markets (one public read
per series, through the shared gateway) and saves one compact row per market:

    [ticker, yes_bid, yes_ask, yes_bid_size, yes_ask_size, last, volume, open_interest]

Rows go to ``recordings/YYYY-MM-DD.jsonl.gz`` (one gzip member per snapshot,
so a crash loses at most one snapshot). On the desk the folder lives on the
/data volume. When the folder passes ``MAX_BYTES`` the oldest days are
deleted. Only the best bid/ask and their sizes are kept, not the full book.

Faster recordings for the 15-minute markets (B19). The building now wakes
every minute. The full snapshot above still runs only once every 15 minutes.
On the other minutes it records just the open 15-minute windows
(``SERIES_15M``) during the last 14 minutes of each window, with one batched
``/markets?tickers=`` read for all of them. A series is listed again (one read)
only when its known window has closed, so a minute costs about two reads.
Fast rows are saved the same way with ``"fast": true``.
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
import os

SERIES = (
    # weather, gas, crypto daily, indexes
    "KXHIGHNY", "KXHIGHCHI", "KXHIGHMIA", "KXHIGHAUS", "KXHIGHDEN", "KXHIGHPHIL", "KXHIGHLAX",
    "KXAAAGASW", "KXBTCD", "KXETHD", "KXNASDAQ100U", "KXINXU",
    # macro
    "KXUST10A", "KXCPI", "KXCPIYOY", "KXGDP",
    # sports game winners
    "KXNBAGAME", "KXNFLGAME", "KXNHLGAME", "KXEPLGAME", "KXUCLGAME", "KXATPMATCH", "KXWTAMATCH",
)
# B19: the 15-minute windows, recorded every minute for the last 14 minutes of each window.
SERIES_15M = (
    "KXBTC15M", "KXETH15M", "KXSOL15M", "KXXRP15M", "KXDOGE15M", "KXBNB15M", "KXHYPE15M",
    "KXWTI15M", "KXBRENT15M", "KXNATGAS15M", "KXGOLD15M", "KXSILVER15M", "KXCOPPER15M",
    "KXPLATINUM15M", "KXPALLADIUM15M", "KXEURUSD15M", "KXUSDJPY15M", "KXINX15M",
)
FULL_EVERY_SEC = 900       # the original full snapshot keeps its 15-minute pace
FAST_LAST_MIN = 14         # record a window only in its last 14 minutes
MAX_BYTES = 150 * 1024 * 1024
PER_SERIES = 200


def _f(market: dict, key: str):
    try:
        value = float(market.get(key))
    except (TypeError, ValueError):
        return None
    return round(value, 4)


def compact(market: dict) -> list | None:
    ticker = str(market.get("ticker") or "")
    if not ticker:
        return None
    return [ticker, _f(market, "yes_bid_dollars"), _f(market, "yes_ask_dollars"),
            _f(market, "yes_bid_size_fp"), _f(market, "yes_ask_size_fp"),
            _f(market, "last_price_dollars"), _f(market, "volume_fp"), _f(market, "open_interest_fp")]


def snapshot(list_open, now: dt.datetime, series=SERIES) -> tuple[dict, list[str]]:
    """list_open(series, limit) -> markets. Returns (snapshot, notes)."""
    rows, notes = {}, []
    for s in series:
        try:
            markets = list_open(s, PER_SERIES)
        except Exception as exc:  # noqa: BLE001 - one series failing must not stop the rest
            notes.append(f"{s} read failed ({type(exc).__name__})")
            continue
        got = [r for r in (compact(m) for m in markets or []) if r]
        if got:
            rows[s] = got
    return {"at": now.isoformat(timespec="seconds"), "cols": ["ticker", "yes_bid", "yes_ask", "bid_size",
            "ask_size", "last", "volume", "oi"], "series": rows}, notes


def _close(market: dict) -> dt.datetime | None:
    try:
        return dt.datetime.fromisoformat(str(market.get("close_time") or "").replace("Z", "+00:00"))
    except ValueError:
        return None


def full_due(state: dict, now: dt.datetime, every: int = FULL_EVERY_SEC) -> bool:
    """True when the 15-minute full snapshot is due (or has never run). Allows 30s of drift."""
    try:
        last = dt.datetime.fromisoformat(str(state.get("last_full") or ""))
    except ValueError:
        return True
    return (now - last).total_seconds() >= every - 30


def learn_windows(windows: dict, series: str, markets: list[dict], now: dt.datetime) -> None:
    """Remember the open 15m tickers of one series: {series: {ticker: close iso}}."""
    keep = {}
    for m in markets or []:
        close = _close(m)
        if m.get("ticker") and close and close > now:
            keep[str(m["ticker"])] = close.isoformat(timespec="seconds")
    windows[series] = keep


def live_tickers(windows: dict, now: dt.datetime, last_min: int = FAST_LAST_MIN) -> list[str]:
    """Known 15m tickers inside the last ``last_min`` minutes of their window."""
    out = []
    for by_ticker in windows.values():
        for ticker, close_iso in by_ticker.items():
            try:
                close = dt.datetime.fromisoformat(close_iso)
            except ValueError:
                continue
            left = (close - now).total_seconds()
            if 0 < left <= last_min * 60:
                out.append(ticker)
    return sorted(out)


def stale_series(windows: dict, now: dt.datetime, series=SERIES_15M) -> list[str]:
    """Series with no known window still open: they need one listing read."""
    out = []
    for s in series:
        alive = False
        for close_iso in (windows.get(s) or {}).values():
            try:
                alive = alive or dt.datetime.fromisoformat(close_iso) > now
            except ValueError:
                continue
        if not alive:
            out.append(s)
    return out


def fast_snapshot(list_open, read_tickers, windows: dict, now: dt.datetime,
                  series=SERIES_15M) -> tuple[dict, list[str], int]:
    """One minute's 15m recording. Returns (snapshot, notes, reads). ``windows`` is updated in place.

    list_open(series, limit) lists a series; read_tickers(tickers) -> markets reads
    them all at once.
    """
    notes, reads = [], 0
    for s in stale_series(windows, now, series):
        reads += 1
        try:
            learn_windows(windows, s, list_open(s, PER_SERIES), now)
        except Exception as exc:  # noqa: BLE001 - one series failing must not stop the rest
            notes.append(f"{s} read failed ({type(exc).__name__})")
    tickers = live_tickers(windows, now)
    rows: dict = {}
    if tickers:
        reads += 1
        try:
            markets = read_tickers(tickers)
        except Exception as exc:  # noqa: BLE001
            markets = []
            notes.append(f"15m batch read failed ({type(exc).__name__})")
        series_of = {t: s for s, by in windows.items() for t in by}
        for m in markets or []:
            row = compact(m)
            if row and row[0] in series_of:
                rows.setdefault(series_of[row[0]], []).append(row)
    snap = {"at": now.isoformat(timespec="seconds"), "fast": True,
            "cols": ["ticker", "yes_bid", "yes_ask", "bid_size", "ask_size", "last", "volume", "oi"],
            "series": rows}
    return snap, notes, reads


def save(folder: str, snap: dict, now: dt.datetime) -> str:
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, now.date().isoformat() + ".jsonl.gz")
    with gzip.open(path, "ab") as handle:
        handle.write((json.dumps(snap, separators=(",", ":")) + "\n").encode("utf-8"))
    return path


def prune(folder: str, max_bytes: int = MAX_BYTES) -> list[str]:
    """Delete the oldest day files until the folder fits. Today's file is never deleted."""
    files = sorted(f for f in os.listdir(folder) if f.endswith(".jsonl.gz")) if os.path.isdir(folder) else []
    sizes = {f: os.path.getsize(os.path.join(folder, f)) for f in files}
    total, gone = sum(sizes.values()), []
    for f in files[:-1]:
        if total <= max_bytes:
            break
        os.remove(os.path.join(folder, f))
        total -= sizes[f]
        gone.append(f)
    return gone


def read_day(path: str) -> list[dict]:
    out = []
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def usage(folder: str) -> dict:
    files = sorted(f for f in os.listdir(folder) if f.endswith(".jsonl.gz")) if os.path.isdir(folder) else []
    return {"days": len(files), "bytes": sum(os.path.getsize(os.path.join(folder, f)) for f in files),
            "first": files[0][:10] if files else None, "last": files[-1][:10] if files else None}
