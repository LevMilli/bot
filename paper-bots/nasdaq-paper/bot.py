#!/usr/bin/env python3
"""Nasdaq: shadow paper tower for Kalshi end-of-day Nasdaq 100 markets.

Prices KXNASDAQ100U strikes and KXNASDAQ100 ranges for today's 4pm ET close
from the live index (^NDX) and the Nasdaq volatility index (^VXN), see
``nasdaq_model.py``. Buys a side only when the edge after the Kalshi fee clears
the locked index floor of 0.02.

Paper only. Shadow only. $25 fixed ticket from a $500 sleeve, max 2 open, one
per event. Only during regular hours, more than 10 minutes before the close,
and only when the index quote is under 5 minutes old.
Exits: model flip at the bid, settle backstop.
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

import kalshi_shadow_tower as engine  # noqa: E402
import nasdaq_model as nm  # noqa: E402

SPEC = {"id": "nasdaq", "name": "Nasdaq", "floor": 0.02, "max_open": 2, "max_edge": 0.15}
SERIES = ("KXNASDAQ100U", "KXNASDAQ100")
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1m&range=1d"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}


def _close(market: dict):
    try:
        return dt.datetime.fromisoformat(str(market.get("close_time")).replace("Z", "+00:00"))
    except ValueError:
        return None


def quotes_for(markets: list[dict], level: float, vol: float, now: dt.datetime) -> list[dict]:
    out = []
    for market in markets:
        close = _close(market)
        minutes = nm.minutes_left(now, close) if close else None
        if minutes is None or minutes < nm.MIN_MINUTES:
            continue
        p_yes = nm.fair_yes(market, level, vol, minutes)
        if p_yes is None:
            continue
        lo, hi = market.get("floor_strike"), market.get("cap_strike")
        kind = str(market.get("strike_type"))
        if kind == "between":
            what = f"{float(lo):,.0f}-{float(hi):,.0f}"
        elif kind.startswith("greater"):
            what = f"above {float(lo):,.0f}"
        else:
            what = f"below {float(hi):,.0f}"
        why = f"NDX {level:,.2f}, VXN {vol:.1%}, {minutes:.0f} trading min to close: P {p_yes:.3f}"
        for side in engine.sides(market):
            side["fair"] = p_yes if side["side"] == "yes" else 1.0 - p_yes
            side["label"] = f"NDX {close.astimezone(nm.ET).strftime('%b %d')} {what}"
            side["why"] = why
            out.append(side)
    return out


def _yahoo(sym: str, now: dt.datetime):
    got = nm.chart_meta(engine.public_json(YAHOO.format(sym=sym), headers=UA))
    if not got:
        return None
    price, when = got
    return price, now.timestamp() - when


def _why(exc: Exception) -> str:
    code = getattr(exc, "code", None)
    return f"HTTP {code}" if code else type(exc).__name__


def model(cfg: dict, now: dt.datetime):
    close_et = now.astimezone(nm.ET).replace(hour=16, minute=0, second=0, microsecond=0)
    if nm.minutes_left(now, close_et) is None:
        return [], "market closed"
    got = {}
    for name, sym in (("NDX", "%5ENDX"), ("VXN", "%5EVXN")):
        try:
            got[name] = _yahoo(sym, now)
        except Exception as exc:  # noqa: BLE001 - name the source on the card
            return [], f"Yahoo {name} quote {_why(exc)}; waiting"
    ndx, vxn = got["NDX"], got["VXN"]
    if not ndx or not vxn:
        return [], "index quote missing"
    if ndx[1] > nm.MAX_QUOTE_AGE_SEC:
        return [], f"NDX quote {ndx[1] / 60:.0f} min old"
    vol = min(nm.VOL_CAP, max(nm.VOL_FLOOR, vxn[0] / 100.0))
    markets = []
    for series in SERIES:
        try:
            # ~2,800 open strikes across the hourly events: read them all, not just page one
            rows = engine.kalshi_open_markets(series, limit=1000, pages=5)
        except Exception as exc:  # noqa: BLE001
            return [], f"Kalshi {series} list {_why(exc)}; waiting"
        # built and checked for the 4pm close only; the hourly 10am-3pm events stay out
        markets.extend(m for m in rows if str(m.get("event_ticker") or "").endswith("H1600"))
    quotes = quotes_for(markets, ndx[0], vol, now)
    return quotes, "" if quotes else "no Nasdaq market in window"


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--reset" in argv:
        return engine.reset(SPEC, HERE)
    return engine.run_tower(SPEC, HERE, model)


if __name__ == "__main__":
    raise SystemExit(main())
