#!/usr/bin/env python3
"""10-year Treasury: shadow paper tower for Kalshi's daily 10Y par yield markets.

Prices today's KXUST10A "above X%" markets from the live ^TNX yield, the
recent daily moves of the official 10-year par yield, and the measured gap
between the two (``ust_model.py``). Buys a side only when the edge after the
Kalshi fee clears the locked econ floor of 0.05.

Paper only. Shadow only. $25 fixed ticket from a $500 sleeve, max 2 open, one
per event. Only on the settlement day, from 9:00 ET until 15 minutes before
the 3:30pm ET strike, and only when the ^TNX quote is under 10 minutes old.
Exits: model flip at the bid, settle backstop.
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

import kalshi_shadow_tower as engine  # noqa: E402
import public_http  # noqa: E402
import ust_model as um  # noqa: E402

SPEC = {"id": "treasury-10y", "name": "10-year Treasury", "floor": 0.05, "max_open": 2, "max_edge": 0.15}
SERIES = "KXUST10A"
CACHE = "ust_daily.json"
CACHE_HOURS = 6
TREASURY = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
            "daily-treasury-rates.csv/{year}/all?type=daily_treasury_yield_curve"
            "&field_tdr_date_value={year}&page&_format=csv")
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/%5ETNX?interval={iv}&range={rng}"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}


def _tnx_closes(body: dict) -> dict:
    try:
        res = body["chart"]["result"][0]
        stamps, closes = res["timestamp"], res["indicators"]["quote"][0]["close"]
    except (KeyError, IndexError, TypeError):
        return {}
    out = {}
    for stamp, close in zip(stamps, closes):
        if close is None:
            continue
        day = dt.datetime.fromtimestamp(int(stamp), dt.timezone.utc).astimezone(um.ET).strftime("%Y-%m-%d")
        out[day] = float(close)
    return out


def _history(now: dt.datetime, read=None) -> dict:
    """Daily sd and basis, refreshed at most every 6 hours."""
    path = os.path.join(HERE, CACHE)
    cache = engine.read_json(path) or {}
    try:
        age = (now - dt.datetime.fromisoformat(cache["at"])).total_seconds() / 3600.0
    except (KeyError, TypeError, ValueError):
        age = None
    if age is not None and age < CACHE_HOURS and cache.get("sd_day"):
        return cache
    read = read or (lambda url: public_http.read(url, headers=UA, timeout=30, tries=2).decode("utf-8"))
    cmt = {}
    for year in (now.year - 1, now.year):
        cmt.update(um.parse_treasury_csv(read(TREASURY.format(year=year))))
    closes = _tnx_closes(json.loads(read(YAHOO.format(iv="1d", rng="6mo"))))
    sd_day = um.daily_sd(cmt)
    gap = um.basis(cmt, closes)
    if sd_day is None or gap is None:
        return {}
    cache = {"at": now.isoformat(timespec="seconds"), "sd_day": round(sd_day, 5),
             "basis_mean": round(gap[0], 5), "basis_sd": round(gap[1], 5),
             "last_official": cmt[max(cmt)], "last_official_day": max(cmt), "paper_only": True}
    try:
        engine.write_json(path, cache)
    except OSError:
        pass
    return cache


def quotes_for(markets: list[dict], level: float, hist: dict, now: dt.datetime) -> list[dict]:
    out = []
    for market in markets:
        day = um.event_day(str(market.get("event_ticker") or ""))
        minutes = um.minutes_left(now, day) if day else None
        if minutes is None or minutes < um.MIN_MINUTES:
            continue
        p_yes = um.fair_yes(market, level, hist["sd_day"], minutes, hist["basis_mean"], hist["basis_sd"])
        if p_yes is None:
            continue
        kind = str(market.get("strike_type"))
        strike = market.get("floor_strike") if kind.startswith("greater") else market.get("cap_strike")
        what = ("above " if kind.startswith("greater") else "below ") + f"{float(strike):.2f}%"
        why = (f"TNX {level:.3f}%, basis {hist['basis_mean']:+.3f}, daily move sd "
               f"{hist['sd_day'] * 100:.1f}bp, {minutes:.0f} min to 3:30pm ET: P {p_yes:.3f}")
        for side in engine.sides(market):
            side["fair"] = p_yes if side["side"] == "yes" else 1.0 - p_yes
            side["label"] = f"10Y {day.strftime('%b %d')} {what}"
            side["why"] = why
            out.append(side)
    return out


def _live_tnx(now: dt.datetime):
    body = engine.public_json(YAHOO.format(iv="1m", rng="1d"), headers=UA)
    try:
        meta = body["chart"]["result"][0]["meta"]
        return float(meta["regularMarketPrice"]), now.timestamp() - int(meta["regularMarketTime"])
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def model(cfg: dict, now: dt.datetime):
    today = now.astimezone(um.ET).date()
    if um.minutes_left(now, today) is None:
        return [], "outside the settlement-day window (9:00-15:30 ET weekdays)"
    tnx = _live_tnx(now)
    if not tnx:
        return [], "10Y yield quote missing"
    if tnx[1] > um.MAX_QUOTE_AGE_SEC:
        return [], f"10Y yield quote {tnx[1] / 60:.0f} min old (bond market closed?)"
    hist = _history(now)
    if not hist:
        return [], "Treasury yield history unavailable; waiting"
    quotes = quotes_for(engine.kalshi_open_markets(SERIES), tnx[0], hist, now)
    return quotes, "" if quotes else "no 10Y market for today in window"


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--reset" in argv:
        return engine.reset(SPEC, HERE)
    return engine.run_tower(SPEC, HERE, model)


if __name__ == "__main__":
    raise SystemExit(main())
