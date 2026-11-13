"""Window history: minute-by-minute recordings of the Kalshi 15-minute markets.

For every 15-minute series a tower trades (BTC and ETH, eight commodities and
the eight More 15m markets) it records, once a minute during the last 14
minutes of each window:

* the top 5 levels of the order book on both sides (YES bids and NO bids;
  a YES offer at A is a NO bid at 1 - A), plus the best bid and ask;
* the window's open price on the settlement source (Kalshi's ``floor_strike``)
  when the window is first seen;
* after the close, the result and the settlement source's final value
  (Kalshi's ``expiration_value``).

Rows go to ``recordings/YYYY-MM-DD.jsonl.gz`` on the /data volume. Days older
than 180 days, or past the size cap, are removed oldest first.

Reads go through the shared Kalshi gateway with the cache turned off for
these URLs, so a recorder read can never hand a tower an older copy of a book
than the tower would have read itself. The recorder sits out a run while the
gateway is backing off, and stops after a fixed read budget and time budget.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DESK_ROOT = os.path.dirname(HERE)
for path in (DESK_ROOT, HERE):
    if path not in sys.path:
        sys.path.insert(0, path)

import desk_data  # noqa: E402

KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
SERIES = (
    # BTC 15m tower
    "KXBTC15M", "KXETH15M",
    # Commodity 15m tower
    "KXGOLD15M", "KXWTI15M", "KXSILVER15M", "KXBRENT15M", "KXCOPPER15M", "KXPLATINUM15M",
    "KXPALLADIUM15M", "KXNATGAS15M",
    # More 15m tower
    "KXSOL15M", "KXXRP15M", "KXDOGE15M", "KXBNB15M", "KXHYPE15M", "KXINX15M", "KXEURUSD15M", "KXUSDJPY15M",
)
LAST_MINUTES = 14.0
DEPTH = 5
READ_BUDGET = 30          # Kalshi reads per run
TIME_BUDGET_SEC = 20.0    # stop reading after this, so the desk timer is never held up
READ_TIMEOUT = 6.0
RESULT_WAIT_SEC = 60      # ask for the result a minute after the close
RESULT_GIVE_UP_SEC = 6 * 3600
MAX_BYTES = 300 * 1024 * 1024


def list_url(series: str) -> str:
    return f"{KALSHI}/markets?series_ticker={series}&status=open&limit=4"


def book_url(ticker: str) -> str:
    return f"{KALSHI}/markets/{ticker}/orderbook?depth={DEPTH}"


def market_url(ticker: str) -> str:
    return f"{KALSHI}/markets/{ticker}"


def gateway_get(url: str):
    """One Kalshi read through the shared door, never from or into the shared cache."""
    import kalshi_gateway

    return json.loads(kalshi_gateway.read(url, timeout=READ_TIMEOUT, ttl=0).decode("utf-8"))


def gateway_busy() -> bool:
    try:
        import kalshi_gateway

        return float(kalshi_gateway.status().get("cooldown_left_s") or 0) > 0
    except Exception:  # noqa: BLE001
        return False


# ------------------------------------------------------------------ parsing
def _close(market: dict):
    return desk_data.parse_at(market.get("close_time"))


def levels(book: dict, key: str, depth: int = DEPTH) -> list[list[float]]:
    """Best ``depth`` bids for one side, best first, as [price, contracts]."""
    rows = book.get(f"{key}_dollars")
    if rows is None:
        rows = book.get(key)
    out = []
    for level in rows or []:
        try:
            if isinstance(level, dict):
                px = float(level.get("price") or level.get("price_dollars") or 0)
                qty = float(level.get("quantity") or level.get("count") or 0)
            else:
                px, qty = float(level[0]), float(level[1])
        except (TypeError, ValueError, IndexError):
            continue
        if px > 1.5:  # older payloads use cents
            px /= 100.0
        if qty > 0 and 0 < px < 1:
            out.append([round(px, 4), round(qty, 2)])
    out.sort(key=lambda r: -r[0])
    return out[:depth]


def book_row(raw: dict, *, at: dt.datetime, series: str, ticker: str, minutes: float) -> dict:
    book = (raw or {}).get("orderbook_fp") or (raw or {}).get("orderbook") or raw or {}
    yes, no = levels(book, "yes"), levels(book, "no")
    yes_bid = yes[0][0] if yes else None
    no_bid = no[0][0] if no else None
    return {
        "kind": "book", "at": at.isoformat(timespec="seconds"), "series": series, "ticker": ticker,
        "min_left": round(minutes, 2),
        "yes_bids": yes, "no_bids": no,
        "yes_bid": yes_bid, "yes_ask": None if no_bid is None else round(1 - no_bid, 4),
        "no_bid": no_bid, "no_ask": None if yes_bid is None else round(1 - yes_bid, 4),
        "depth": round(sum(q for _, q in yes) + sum(q for _, q in no), 2),
    }


def pick_window(markets: list[dict], now: dt.datetime) -> dict | None:
    live = []
    for m in markets or []:
        close = _close(m)
        if close is None or not m.get("ticker"):
            continue
        minutes = (close - now).total_seconds() / 60.0
        if 0 < minutes <= 15.5:
            live.append((close, m))
    if not live:
        return None
    close, m = min(live, key=lambda r: r[0])
    return {"ticker": str(m["ticker"]), "event": str(m.get("event_ticker") or ""),
            "close": close.isoformat(timespec="seconds"), "open_price": desk_data.num(m.get("floor_strike"))}


# ------------------------------------------------------------------ one run
def record(state: dict, now: dt.datetime, get=gateway_get, *, budget: int = READ_BUDGET,
           time_budget: float = TIME_BUDGET_SEC, clock=time.monotonic, series=SERIES) -> tuple[list, list]:
    """One pass. Updates ``state`` in place. Returns (rows, notes)."""
    windows = state.setdefault("windows", {})
    pending = state.setdefault("pending", [])
    rows, notes = [], []
    reads = 0
    start = clock()

    def room() -> bool:
        return reads < budget and clock() - start < time_budget

    for s in series:
        w = windows.get(s)
        if w and desk_data.parse_at(w["close"]) <= now:
            pending.append(dict(w, series=s))
            windows.pop(s, None)
            w = None
        if w is None:
            if not room():
                notes.append(f"{s}: read budget used up")
                continue
            reads += 1
            try:
                w = pick_window((get(list_url(s)) or {}).get("markets") or [], now)
            except Exception as exc:  # noqa: BLE001 - one series failing must not stop the rest
                notes.append(f"{s} list read failed ({type(exc).__name__})")
                continue
            if w is None:
                continue
            windows[s] = w
            rows.append({"kind": "window", "at": now.isoformat(timespec="seconds"), "series": s, **w})
        minutes = (desk_data.parse_at(w["close"]) - now).total_seconds() / 60.0
        if not (0 < minutes <= LAST_MINUTES):
            continue
        if not room():
            notes.append(f"{s}: read budget used up")
            continue
        reads += 1
        try:
            raw = get(book_url(w["ticker"]))
        except Exception as exc:  # noqa: BLE001
            notes.append(f"{s} book read failed ({type(exc).__name__})")
            continue
        rows.append(book_row(raw, at=now, series=s, ticker=w["ticker"], minutes=minutes))
    keep = []
    for p in pending:
        age = (now - desk_data.parse_at(p["close"])).total_seconds()
        if age < RESULT_WAIT_SEC:
            keep.append(p)
            continue
        if age > RESULT_GIVE_UP_SEC:
            notes.append(f"{p['ticker']}: no result after 6 hours; stopped asking")
            continue
        if not room():
            keep.append(p)
            continue
        reads += 1
        try:
            market = (get(market_url(p["ticker"])) or {}).get("market") or {}
        except Exception as exc:  # noqa: BLE001
            notes.append(f"{p['ticker']} result read failed ({type(exc).__name__})")
            keep.append(p)
            continue
        result = str(market.get("result") or "").lower()
        if result not in ("yes", "no"):
            keep.append(p)
            continue
        rows.append({"kind": "result", "at": now.isoformat(timespec="seconds"), "series": p["series"],
                     "ticker": p["ticker"], "close": p["close"], "result": result,
                     "open_price": p.get("open_price") if p.get("open_price") is not None
                     else desk_data.num(market.get("floor_strike")),
                     "settle_value": desk_data.num(market.get("expiration_value"))})
    state["pending"] = keep
    state["reads_last_run"] = reads
    return [desk_data.strip_private(r) for r in rows], notes


# ------------------------------------------------------------------ files
def save(folder: str, rows: list[dict], now: dt.datetime) -> str | None:
    if not rows:
        return None
    return desk_data.write_rows(folder, now.date(), rows)


def prune(folder: str, today: dt.date, max_bytes: int = MAX_BYTES) -> list[str]:
    gone = desk_data.prune_days(folder, today)
    files = desk_data.day_files(folder)
    sizes = {f: os.path.getsize(os.path.join(folder, f)) for f in files}
    total = sum(sizes.values())
    for f in files:
        if total <= max_bytes or f.startswith(today.isoformat()):
            break
        os.remove(os.path.join(folder, f))
        total -= sizes[f]
        gone.append(f)
    return gone


def usage(folder: str) -> dict:
    files = desk_data.day_files(folder)
    return {"days": len(files), "bytes": sum(os.path.getsize(os.path.join(folder, f)) for f in files),
            "first": files[0][:10] if files else None, "last": files[-1][:10] if files else None}


# ------------------------------------------------------------------ tools (263-265)
def rebuild_window(folder: str, ticker: str) -> dict:
    """Everything recorded for one 15-minute window, in time order (step 264)."""
    days = set()
    for f in desk_data.day_files(folder):
        days.add(f[:10])
    rows = []
    for day in sorted(days):
        rows.extend(r for r in desk_data.load_day(folder, day) if r.get("ticker") == ticker)
    rows.sort(key=lambda r: str(r.get("at") or ""))
    books = [r for r in rows if r.get("kind") == "book"]
    head = next((r for r in rows if r.get("kind") == "window"), {})
    result = next((r for r in rows if r.get("kind") == "result"), {})
    quality = desk_data.quality_check([r["at"] for r in books])
    return {"ticker": ticker, "series": desk_data.series_of(ticker), "close": head.get("close") or result.get("close"),
            "open_price": head.get("open_price", result.get("open_price")), "books": books,
            "result": result.get("result"), "settle_value": result.get("settle_value"), "quality": quality}


def window_chart_svg(window: dict, fairs: list[dict] | None = None, trades: list[dict] | None = None,
                     width: int = 640, height: int = 260) -> str:
    """A plain chart of one window: YES mid price, our fair, our trades (step 265)."""
    pad = 36
    books = window.get("books") or []

    def x_of(minutes):
        return pad + (15.0 - float(minutes)) / 15.0 * (width - 2 * pad)

    def y_of(price):
        return height - pad - float(price) * (height - 2 * pad)

    def mid(r):
        if r.get("yes_bid") is not None and r.get("yes_ask") is not None:
            return (r["yes_bid"] + r["yes_ask"]) / 2
        return r.get("yes_bid") if r.get("yes_bid") is not None else r.get("yes_ask")

    close = desk_data.parse_at(window.get("close"))

    def minutes_left(at):
        when = desk_data.parse_at(at)
        return None if (when is None or close is None) else max(0.0, (close - when).total_seconds() / 60.0)

    price_pts = [(x_of(r["min_left"]), y_of(mid(r))) for r in books if mid(r) is not None]
    fair_pts = []
    for f in fairs or []:
        m = minutes_left(f.get("at"))
        p = desk_data.num(f.get("fair"))
        if m is not None and p is not None and m <= 15:
            yes_fair = p if str(f.get("side") or "yes") == "yes" else 1 - p
            fair_pts.append((x_of(m), y_of(yes_fair)))
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
             f'viewBox="0 0 {width} {height}" font-family="sans-serif" font-size="11">',
             f'<rect width="{width}" height="{height}" fill="#0d0a14"/>',
             f'<text x="{pad}" y="18" fill="#f4f1fb">{window.get("ticker", "")} (pretend money)</text>']
    for p in (0.0, 0.5, 1.0):
        parts.append(f'<line x1="{pad}" x2="{width - pad}" y1="{y_of(p):.1f}" y2="{y_of(p):.1f}" stroke="#2a2238"/>')
        parts.append(f'<text x="4" y="{y_of(p) + 4:.1f}" fill="#a59cbc">{p:.2f}</text>')
    for label, minutes in (("15 min left", 15), ("close", 0)):
        parts.append(f'<text x="{x_of(minutes) - 10:.1f}" y="{height - 10}" fill="#a59cbc">{label}</text>')
    if price_pts:
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in sorted(price_pts))
        parts.append(f'<polyline points="{pts}" fill="none" stroke="#a27bff" stroke-width="2"/>')
    if fair_pts:
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in sorted(fair_pts))
        parts.append(f'<polyline points="{pts}" fill="none" stroke="#f0b429" stroke-width="2" '
                     'stroke-dasharray="4 3"/>')
    for t in trades or []:
        m = minutes_left(t.get("opened"))
        ask = desk_data.num(t.get("ask"))
        if m is None or ask is None:
            continue
        yes_px = ask if str(t.get("side") or "yes") == "yes" else 1 - ask
        parts.append(f'<circle cx="{x_of(m):.1f}" cy="{y_of(yes_px):.1f}" r="5" fill="#34d399"/>')
    if window.get("result"):
        parts.append(f'<text x="{width - pad - 90}" y="18" fill="#f4f1fb">result {window["result"].upper()}</text>')
    parts.append(f'<text x="{pad + 160}" y="18" fill="#a27bff">price</text>'
                 f'<text x="{pad + 200}" y="18" fill="#f0b429">our fair</text>'
                 f'<text x="{pad + 255}" y="18" fill="#34d399">our trades</text>')
    parts.append("</svg>")
    return "".join(parts)


# ------------------------------------------------------------------ nightly (276-279, 299-300)
def market_calibration(rows: list[dict]) -> dict:
    """How often the YES side won at each recorded price, split by minutes left and depth.

    Scores the market's own YES mid against the result (15-minute family only,
    kept apart from the daily calibration lab).
    """
    results = {r["ticker"]: r["result"] for r in rows if r.get("kind") == "result"}
    pairs, by_min, by_depth = [], {}, {}
    for r in rows:
        if r.get("kind") != "book" or r.get("ticker") not in results:
            continue
        if r.get("yes_bid") is None or r.get("yes_ask") is None:
            continue
        said = (r["yes_bid"] + r["yes_ask"]) / 2
        won = results[r["ticker"]] == "yes"
        pairs.append((said, won))
        by_min.setdefault(desk_data.minutes_bucket(r.get("min_left")), []).append((said, won))
        by_depth.setdefault(desk_data.volume_bucket(r.get("depth")), []).append((said, won))
    return {"family": "15m", "all": desk_data.calibration(pairs),
            "by_minutes_left": {k: desk_data.calibration(v) for k, v in sorted(by_min.items()) if k},
            "by_depth": {k: desk_data.calibration(v) for k, v in sorted(by_depth.items()) if k}}


def quality_report(rows: list[dict]) -> dict:
    """Missing minutes, duplicate rows and out-of-order times, per window (step 299)."""
    by_ticker: dict[str, list] = {}
    for r in rows:
        if r.get("kind") == "book":
            by_ticker.setdefault(r["ticker"], []).append(r)
    windows, missing, dupes, disorder = 0, 0, 0, 0
    worst = []
    for ticker, books in sorted(by_ticker.items()):
        # A window recorded from its first minute should have about 14 rows.
        times = [b["at"] for b in books]
        q = desk_data.quality_check([t[:16] for t in times], keys=[t[:16] for t in times])
        windows += 1
        missing += q["missing"]
        dupes += q["duplicates"]
        disorder += q["out_of_order"]
        if q["missing"] or q["duplicates"] or q["out_of_order"]:
            worst.append({"ticker": ticker, **{k: q[k] for k in ("missing", "duplicates", "out_of_order")}})
    worst.sort(key=lambda r: -(r["missing"] + r["duplicates"] + r["out_of_order"]))
    return {"windows": windows, "missing_minutes": missing, "duplicates": dupes, "out_of_order": disorder,
            "ok": not (missing or dupes or disorder), "worst": worst[:10]}
