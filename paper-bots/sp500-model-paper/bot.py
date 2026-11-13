#!/usr/bin/env python3
"""S&P model: shadow twin that gives the Kalshi S&P markets a real fair price.

Idea B21. The Kalshi S&P and Sized Kalshi towers refuse the leftover
"1 - price - fee" as edge, so they almost never buy. This twin prices the same
KXINXU strikes (and KXINX ranges) for today's 4pm ET close with the Nasdaq
tower's model, fed with the live S&P 500 (^SPX) and the VIX instead of the
Nasdaq index and VXN (``nasdaq-paper/nasdaq_model.py``, used read-only):

* Fair = lognormal chance from the live index and the VIX over the trading
  minutes left (252 x 390 a year).
* Regular hours only, more than 10 minutes before the close, index quote under
  5 minutes old.
* Edge = fair - ask - Kalshi fee; buy only if edge >= the locked index floor 0.02
  and <= the 0.15 trust cap.
* Rows whose ask sits in the 80-90 cent band the Kalshi S&P tower uses are
  tagged "vault band" so the two can be compared side by side.

Paper only. Shadow only. $25 fixed ticket from a $500 sleeve, max 2 open, one
per event. Exits: model flip at the bid, settle backstop. The two S&P vault
towers are not changed.
"""
from __future__ import annotations

import datetime as dt
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DESK_ROOT = os.path.dirname(HERE)
for path in (DESK_ROOT, HERE, os.path.join(DESK_ROOT, "nasdaq-paper")):
    if path not in sys.path:
        sys.path.insert(0, path)

import kalshi_shadow_tower as engine  # noqa: E402
import nasdaq_model as nm  # noqa: E402 - same index-plus-volatility math

SPEC = {"id": "sp500-model", "name": "S&P model", "floor": 0.02, "max_open": 2, "max_edge": 0.15}
SERIES = ("KXINXU", "KXINX")
VAULT_BAND = (0.80, 0.90)
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1m&range=1d"
CNBC = ("https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol"
        "?symbols=.SPX%7C.VIX&requestMethod=itv&noform=1&partnerId=2&fund=1&exthrs=1&output=json")
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}


def _close(market: dict):
    try:
        return dt.datetime.fromisoformat(str(market.get("close_time")).replace("Z", "+00:00"))
    except ValueError:
        return None


def in_vault_band(ask) -> bool:
    try:
        return VAULT_BAND[0] - 1e-9 <= float(ask) <= VAULT_BAND[1] + 1e-9
    except (TypeError, ValueError):
        return False


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
        why = f"SPX {level:,.2f}, VIX {vol:.1%}, {minutes:.0f} trading min to close: P {p_yes:.3f}"
        for side in engine.sides(market):
            side["fair"] = p_yes if side["side"] == "yes" else 1.0 - p_yes
            side["label"] = f"SPX {close.astimezone(nm.ET).strftime('%b %d')} {what}"
            side["why"] = why + ("; vault band" if in_vault_band(side.get("ask")) else "")
            out.append(side)
    return out


def _cnbc(body: dict, now: dt.datetime) -> dict:
    """{"SPX": (level, age s), "VIX": (level, age s)} from CNBC's quote feed."""
    out = {}
    try:
        rows = body["FormattedQuoteResult"]["FormattedQuote"]
    except (KeyError, TypeError):
        return out
    for row in rows or []:
        name = str(row.get("symbol") or "").lstrip(".")
        try:
            level = float(str(row["last"]).replace(",", ""))
        except (KeyError, TypeError, ValueError):
            continue
        try:
            at = dt.datetime.strptime(str(row.get("last_time")), "%Y-%m-%dT%H:%M:%S.%f%z")
            age = (now - at).total_seconds()
        except ValueError:
            age = float("inf")
        out[name] = (level, age)
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
    try:
        got = _cnbc(engine.public_json(CNBC, headers=UA), now)
    except Exception as exc:  # noqa: BLE001
        got, miss = {}, f"CNBC {_why(exc)}"
    else:
        miss = "CNBC empty"
    for name, sym in (("SPX", "%5EGSPC"), ("VIX", "%5EVIX")):
        if got.get(name) and (name == "VIX" or got[name][1] <= nm.MAX_QUOTE_AGE_SEC):
            continue
        try:
            got[name] = _yahoo(sym, now) or got.get(name)
        except Exception as exc:  # noqa: BLE001
            if not got.get(name):
                return [], f"{name} quote: {miss}, Yahoo {_why(exc)}; waiting"
    spx, vix = got.get("SPX"), got.get("VIX")
    if not spx or not vix:
        return [], "index quote missing"
    if spx[1] > nm.MAX_QUOTE_AGE_SEC:
        return [], f"SPX quote {spx[1] / 60:.0f} min old"
    vol = min(nm.VOL_CAP, max(nm.VOL_FLOOR, vix[0] / 100.0))
    markets = []
    for series in SERIES:
        try:
            rows = engine.kalshi_open_markets(series, limit=1000, pages=3)
        except Exception as exc:  # noqa: BLE001
            return [], f"Kalshi {series} list {_why(exc)}; waiting"
        markets.extend(m for m in rows if str(m.get("event_ticker") or "").endswith("H1600"))
    quotes = quotes_for(markets, spx[0], vol, now)
    return quotes, "" if quotes else "no S&P market in window"


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--reset" in argv:
        return engine.reset(SPEC, HERE)
    return engine.run_tower(SPEC, HERE, model)


if __name__ == "__main__":
    raise SystemExit(main())
