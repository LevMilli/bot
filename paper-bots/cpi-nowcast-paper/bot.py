#!/usr/bin/env python3
"""CPI nowcast: shadow paper tower for Kalshi's monthly CPI markets.

Prices KXCPI / KXCPICORE (month-over-month) and KXCPIYOY / KXCPICOREYOY
(year-over-year) "above X%" markets from the Cleveland Fed's daily inflation
nowcast and its measured historical miss (``cpi_model.py``). Buys a side only
when the edge after the Kalshi fee clears the locked econ floor of 0.05; an
edge over 0.15 is logged but not bought.

Paper only. Shadow only. $25 fixed ticket from a $500 sleeve, max 3 open, one
per event. Only for the month the nowcast covers, only when the nowcast is
under 5 days old, and never in the last 2 hours before the release.
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

import cpi_model as cm  # noqa: E402
import kalshi_shadow_tower as engine  # noqa: E402
import public_http  # noqa: E402

SPEC = {"id": "cpi-nowcast", "name": "CPI nowcast", "floor": 0.05, "max_open": 3, "max_edge": 0.15}
CACHE = "nowcast_cache.json"
CACHE_HOURS = 6
CLEVELAND = ("https://www.clevelandfed.org/-/media/files/webcharts/inflationnowcasting/"
             "nowcast_{kind}.json?sc_lang=en")
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}


def _nowcasts(now: dt.datetime, read=None) -> dict:
    """{"month": {...}, "year": {...}} refreshed at most every 6 hours (files are ~8MB)."""
    path = os.path.join(HERE, CACHE)
    cache = engine.read_json(path) or {}
    try:
        age = (now - dt.datetime.fromisoformat(cache["at"])).total_seconds() / 3600.0
    except (KeyError, TypeError, ValueError):
        age = None
    if age is not None and age < CACHE_HOURS and cache.get("month") and cache.get("year"):
        return cache
    read = read or (lambda url: public_http.read(url, headers=UA, timeout=40, tries=2).decode("utf-8"))
    fresh = {"at": now.isoformat(timespec="seconds"), "paper_only": True}
    for kind in ("month", "year"):
        rows = cm.latest_nowcasts(json.loads(read(CLEVELAND.format(kind=kind))))
        # keep only the last few months; the file holds every month since 2013
        fresh[kind] = {k: rows[k] for k in sorted(rows)[-3:]}
    if not fresh["month"] or not fresh["year"]:
        return cache if cache.get("month") else {}
    try:
        engine.write_json(path, fresh)
    except OSError:
        pass
    return fresh


def _close(market: dict) -> dt.datetime | None:
    try:
        return dt.datetime.fromisoformat(str(market["close_time"]).replace("Z", "+00:00"))
    except (KeyError, ValueError):
        return None


def quotes_for(series: str, markets: list[dict], casts: dict, now: dt.datetime) -> list[dict]:
    kind, name, label = cm.SERIES[series]
    out = []
    for market in markets:
        month = cm.event_month(str(market.get("event_ticker") or ""))
        row = (casts.get(kind) or {}).get(month or "")
        close = _close(market)
        if not row or name not in row or close is None:
            continue
        try:
            asof = dt.date.fromisoformat(row["_asof"])
        except (KeyError, ValueError):
            continue
        if (now.date() - asof).days > cm.MAX_NOWCAST_AGE_DAYS:
            continue
        if (close - now).total_seconds() / 3600.0 < cm.MIN_HOURS_LEFT:
            continue
        bdays = cm.business_days(now.date(), close.date())
        sd, bias = cm.error_for(series, bdays)
        p_yes = cm.fair_yes(market, row[name], sd, bias)
        if p_yes is None:
            continue
        strike = float(market["floor_strike"])
        mon = dt.date(int(month[:4]), int(month[5:]), 1).strftime("%b")
        why = (f"Cleveland nowcast {row[name]:.2f}% (as of {asof}), usual miss {sd:.2f} "
               f"with {bdays} business days to release: P {p_yes:.3f}")
        for side in engine.sides(market):
            side["fair"] = p_yes if side["side"] == "yes" else 1.0 - p_yes
            side["label"] = f"{label} {mon} above {strike:.1f}%"
            side["why"] = why
            out.append(side)
    return out


def model(cfg: dict, now: dt.datetime):
    casts = _nowcasts(now)
    if not casts:
        return [], "Cleveland Fed nowcast unavailable; waiting"
    quotes = []
    for series in cm.SERIES:
        quotes += quotes_for(series, engine.kalshi_open_markets(series), casts, now)
    return quotes, "" if quotes else "no CPI market matches a fresh nowcast"


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--reset" in argv:
        return engine.reset(SPEC, HERE)
    return engine.run_tower(SPEC, HERE, model)


if __name__ == "__main__":
    raise SystemExit(main())
