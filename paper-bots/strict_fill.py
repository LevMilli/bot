"""Stricter paper fills for the Kalshi bots. Paper only, no order is ever sent.

Before, a paper buy filled at the ask the bot saw when it decided, for as many
contracts as it wanted. Real orders do worse: the price moves in the seconds
before the order lands, and the book only has so many contracts at that price.

So, right before a paper buy, the bot calls ``recheck``:

1. Wait a few seconds (``PAPER_REQUOTE_SECONDS``, default 3).
2. Read the order book again.
3. Fill at the WORSE of the two asks (never the better one).
4. Only take part of what the book shows at that price
   (``PAPER_DEPTH_SHARE``, default half), so one paper order never
   pretends to buy the whole book.
5. Skip the buy if the price ran away (more than ``PAPER_MAX_SLIP``,
   default 3 cents) or the edge after fees is gone at the new price.

If the book can't be read again, the fill is assumed 1 cent worse with no
size limit, rather than trusting the old price.

``PAPER_STRICT_FILL=0`` turns the whole check off (tests use this so they do
not touch the network).
"""
from __future__ import annotations

import json
import math
import os
import time
import urllib.request

KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
FALLBACK_SLIP = 0.01


def kalshi_fee(p):
    """Kalshi taker fee for one contract at price p, rounded up to the cent."""
    return math.ceil(round(0.07 * float(p) * (1 - float(p)) * 100, 6)) / 100


def _env_float(name, default):
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return float(default)


def enabled():
    return os.environ.get("PAPER_STRICT_FILL", "1").strip() != "0"


def _levels(book, key):
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
        out.append((px, qty))
    return out


def book_quote(data, side):
    """(ask, offers) for ``side`` from a raw Kalshi orderbook payload.

    Kalshi lists bids only: a YES offer at A is a NO bid at 1-A. ``offers`` is
    a list of (ask_price, contracts) sorted cheapest first.
    """
    if not isinstance(data, dict):
        return None, []
    book = data.get("orderbook_fp") or data.get("orderbook") or data
    if not isinstance(book, dict):
        return None, []
    other = "no" if str(side).upper() == "YES" else "yes"
    offers = sorted((round(1 - px, 4), qty) for px, qty in _levels(book, other) if qty > 0)
    if not offers:
        return None, []
    return offers[0][0], offers


def _fetch(ticker):
    import public_http
    body = public_http.read(f"{KALSHI}/markets/{ticker}/orderbook", timeout=10, tries=3)
    return json.loads(body.decode())


def recheck(ticker, side, ask, contracts, *, fee_per=None, edge=None, min_edge=0.0,
            fetch=None, wait=None, force=False):
    """Re-quote right before a paper buy. Returns a dict.

    ``ok`` False means skip the buy (``reason`` says why). Otherwise use
    ``ask`` and ``contracts`` from the result instead of the originals.
    ``fee_per(price)`` is the bot's per-contract fee; ``edge`` is the edge
    after fees at the original ask, re-checked at the new price.
    """
    decided = float(ask)
    want = int(contracts)
    out = {
        "ok": True, "ask": decided, "contracts": want, "reason": "",
        "decided_ask": round(decided, 4), "quoted_ask": None, "slip": 0.0,
        "depth": None, "capped": False, "requoted": False, "note": "",
    }
    if not force and not enabled():
        out["note"] = "strict fill off"
        return out
    delay = _env_float("PAPER_REQUOTE_SECONDS", 3) if wait is None else float(wait)
    if delay > 0:
        time.sleep(delay)
    quoted, offers = None, []
    try:
        quoted, offers = book_quote((fetch or _fetch)(ticker), side)
    except Exception:  # noqa: BLE001 - any read failure falls back to a worse price
        quoted, offers = None, []
    if quoted is None:
        fill = round(decided + FALLBACK_SLIP, 4)
        out["note"] = "book not re-read; assumed 1¢ worse"
    else:
        out["requoted"] = True
        out["quoted_ask"] = round(quoted, 4)
        fill = round(max(decided, quoted), 4)
    slip = round(fill - decided, 4)
    out["ask"], out["slip"] = fill, slip
    max_slip = _env_float("PAPER_MAX_SLIP", 0.03)
    if slip > max_slip + 1e-9:
        out.update(ok=False, contracts=0,
                   reason=f"price ran away before the fill ({decided:.2f} → {fill:.2f})")
        return out
    if fill >= 0.99:
        out.update(ok=False, contracts=0, reason="no room left at the re-checked price")
        return out
    if edge is not None:
        try:
            fee_move = 0.0
            if fee_per is not None:
                fee_move = float(fee_per(fill)) - float(fee_per(decided))
            left = float(edge) - slip - fee_move
        except (TypeError, ValueError):
            left = None
        if left is not None and left + 1e-12 < float(min_edge or 0):
            out.update(ok=False, contracts=0,
                       reason=f"edge gone at the re-checked price ({decided:.2f} → {fill:.2f})")
            return out
    if offers:
        depth = sum(qty for px, qty in offers if px <= fill + 1e-9)
        out["depth"] = round(depth, 2)
        share = min(1.0, max(0.0, _env_float("PAPER_DEPTH_SHARE", 0.5)))
        room = int(math.floor(depth * share + 1e-9))
        if room < 1:
            out.update(ok=False, contracts=0, reason="book too thin at the re-checked price")
            return out
        if room < want:
            out["contracts"], out["capped"] = room, True
    parts = []
    if slip > 0:
        parts.append(f"filled {slip * 100:.0f}¢ worse than decided")
    if out["capped"]:
        parts.append(f"size cut to {out['contracts']} of {want} (book depth)")
    if parts:
        out["note"] = "; ".join(p for p in [out["note"]] + parts if p)
    elif not out["note"]:
        out["note"] = "price held on re-check"
    return out


def stamp(pos, check):
    """Keep what the re-check did on the paper row (for the city / audits)."""
    if isinstance(pos, dict) and isinstance(check, dict):
        pos["fill_check"] = {
            k: check.get(k) for k in
            ("decided_ask", "quoted_ask", "slip", "depth", "capped", "requoted", "note")
        }
    return pos


def spot_recheck(price, quote, *, side="buy", max_slip=None, fallback=None, wait=None, force=False):
    """Re-quote a coin price right before a paper buy or sell.

    ``quote()`` returns the live price (ask for a buy, bid for a sell) or None.
    Buys fill at the higher of the two prices, sells at the lower. A buy whose
    price rose more than ``max_slip`` (a fraction, e.g. 0.05 = 5%) is skipped.
    Sells are never skipped (an exit must still happen), just filled worse.
    If the live price can't be read, ``fallback`` (default 1%) worse is used.
    """
    decided = float(price)
    buying = str(side).lower() != "sell"
    out = {"ok": True, "price": decided, "decided": decided, "quoted": None,
           "slip_pct": 0.0, "requoted": False, "reason": "", "note": ""}
    if not force and not enabled():
        out["note"] = "strict fill off"
        return out
    delay = _env_float("PAPER_REQUOTE_SECONDS", 3) if wait is None else float(wait)
    if delay > 0:
        time.sleep(delay)
    try:
        live = quote()
        live = float(live) if live is not None else None
        if live is not None and not (live > 0):
            live = None
    except Exception:  # noqa: BLE001
        live = None
    worse = _env_float("PAPER_SPOT_FALLBACK_SLIP", 0.01) if fallback is None else float(fallback)
    if live is None:
        fill = decided * (1 + worse) if buying else decided * (1 - worse)
        out["note"] = f"price not re-read; assumed {worse * 100:.1f}% worse"
    else:
        out["requoted"], out["quoted"] = True, live
        fill = max(decided, live) if buying else min(decided, live)
    slip = (fill / decided - 1.0) if buying else (1.0 - fill / decided)
    out["price"], out["slip_pct"] = fill, round(slip * 100, 4)
    limit = _env_float("PAPER_SPOT_MAX_SLIP", 0.05) if max_slip is None else float(max_slip)
    if buying and slip > limit + 1e-12:
        out.update(ok=False, reason=f"price ran away before the fill (+{slip * 100:.2f}%)")
        return out
    if slip > 0 and not out["note"]:
        out["note"] = f"filled {slip * 100:.2f}% worse than decided"
    elif not out["note"]:
        out["note"] = "price held on re-check"
    return out
