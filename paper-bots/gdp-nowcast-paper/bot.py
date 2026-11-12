#!/usr/bin/env python3
"""GDP nowcast: shadow paper tower for Kalshi's quarterly GDP markets (KXGDP).

Prices "above X%" on BEA's first (advance) GDP print from the Atlanta Fed's
GDPNow estimate and its measured historical miss (``gdp_model.py``). Buys a
side only when the edge after the Kalshi fee clears the locked econ floor of
0.05; an edge over 0.15 is logged but not bought.

Paper only. Shadow only. $25 fixed ticket from a $500 sleeve, max 2 open, one
per event. Buys only in the last 45 days before the print (logs earlier),
only the quarter GDPNow covers, only when GDPNow is under 10 days
old, and never in the last 2 hours before the release.
Exits: model flip at the bid, settle backstop.
"""
from __future__ import annotations

import datetime as dt
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DESK_ROOT = os.path.dirname(HERE)
for path in (DESK_ROOT, HERE):
    if path not in sys.path:
        sys.path.insert(0, path)

import gdp_model as gm  # noqa: E402
import kalshi_shadow_tower as engine  # noqa: E402
import public_http  # noqa: E402

SPEC = {"id": "gdp-nowcast", "name": "GDP nowcast", "floor": 0.05, "max_open": 2, "max_edge": 0.15}
SERIES = "KXGDP"
CACHE = "gdpnow_cache.json"
CACHE_HOURS = 8
GDPNOW = ("https://www.atlantafed.org/-/media/Project/Atlanta/FRBA/Documents/research-and-data/"
          "data/gdpnow/GDPTrackingModelDataAndForecasts.xlsx")
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}


def parse_workbook(blob: bytes) -> dict:
    import openpyxl  # root requirements; only needed on refresh
    wb = openpyxl.load_workbook(io.BytesIO(blob), read_only=True, data_only=True)
    now = gm.current(list(wb["CurrentQtrEvolution"].iter_rows(values_only=True))[1:])
    table = gm.error_table(list(wb["TrackingArchives"].iter_rows(values_only=True))[1:])
    return {"now": now, "table": table}


def _gdpnow(now: dt.datetime, read=None, parse=parse_workbook) -> dict:
    path = os.path.join(HERE, CACHE)
    cache = engine.read_json(path) or {}
    try:
        age = (now - dt.datetime.fromisoformat(cache["at"])).total_seconds() / 3600.0
    except (KeyError, TypeError, ValueError):
        age = None
    if age is not None and age < CACHE_HOURS and cache.get("now"):
        return cache
    read = read or (lambda url: public_http.read(url, headers=UA, timeout=60, tries=2))
    parsed = parse(read(GDPNOW))
    if not parsed.get("now"):
        return cache if cache.get("now") else {}
    fresh = {"at": now.isoformat(timespec="seconds"), "now": parsed["now"],
             "table": parsed.get("table") or [], "paper_only": True}
    try:
        engine.write_json(path, fresh)
    except OSError:
        pass
    return fresh


def quotes_for(markets: list[dict], cast: dict, now: dt.datetime) -> list[dict]:
    est = cast.get("now") or {}
    try:
        asof = dt.date.fromisoformat(est["asof"])
        value = float(est["value"])
    except (KeyError, TypeError, ValueError):
        return []
    if (now.date() - asof).days > gm.MAX_AGE_DAYS:
        return []
    table = [tuple(x) for x in cast.get("table") or []]
    out = []
    for market in markets:
        release = gm.event_release(str(market.get("event_ticker") or ""))
        if release is None or gm.release_quarter(release) != est.get("quarter"):
            continue
        try:
            close = dt.datetime.fromisoformat(str(market["close_time"]).replace("Z", "+00:00"))
            strike = float(market["floor_strike"])
        except (KeyError, TypeError, ValueError):
            continue
        if not str(market.get("strike_type") or "").startswith("greater"):
            continue
        if (close - now).total_seconds() / 3600.0 < gm.MIN_HOURS_LEFT:
            continue
        days = max(0, (release - now.date()).days)
        sd, bias = gm.error_for(table, days)
        p_yes = gm.p_above(strike, value, sd, bias)
        why = (f"GDPNow {est['quarter']} {value:.2f}% (as of {asof}), typical run-high {bias:+.2f}, usual miss {sd:.2f} "
               f"with {days} days to BEA's first print: P {p_yes:.3f}")
        for side in engine.sides(market):
            side["fair"] = p_yes if side["side"] == "yes" else 1.0 - p_yes
            side["label"] = f"GDP {est['quarter']} above {strike:.1f}%"
            side["why"] = why
            if days > gm.MAX_DAYS_LEFT:
                side["log_only"] = True
                side["log_reason"] = f"{days} days to the print (> {gm.MAX_DAYS_LEFT}); logged, not a buy window"
            out.append(side)
    return out


def model(cfg: dict, now: dt.datetime):
    cast = _gdpnow(now)
    if not cast:
        return [], "GDPNow unavailable; waiting"
    quotes = quotes_for(engine.kalshi_open_markets(SERIES), cast, now)
    return quotes, "" if quotes else "no GDP market matches a fresh GDPNow quarter"


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--reset" in argv:
        return engine.reset(SPEC, HERE)
    return engine.run_tower(SPEC, HERE, model)


if __name__ == "__main__":
    raise SystemExit(main())
