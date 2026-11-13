#!/usr/bin/env python3
"""Monthly rain and snow: shadow paper tower for Kalshi's monthly total markets.

Rain: KXRAIN<city>M (18 cities). Snow: KX<city>SNOWM (9 cities). Each market asks
whether the month's total at one NWS station is strictly greater than K inches.
Fair value = month-to-date total from the climate report plus every ensemble run
that reaches the end of the month (``precip_model.py``).

Paper only. Shadow only. $25 fixed ticket from a $500 sleeve, max 3 open, one per
city-month. Buys only when 14 or fewer days are left and at least 20 ensemble
runs reach the month's last day; until then a city is noted and skipped (there
is nothing honest to price). Exits: model flip at the bid, settle backstop.
"""
from __future__ import annotations

import datetime as dt
import os
import sys
import threading
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
DESK_ROOT = os.path.dirname(HERE)
for path in (DESK_ROOT, HERE):
    if path not in sys.path:
        sys.path.insert(0, path)

import kalshi_shadow_tower as engine  # noqa: E402
import precip_model as pm  # noqa: E402

SPEC = {"id": "monthly-precip", "name": "Monthly rain and snow", "floor": 0.05, "max_open": 3,
        "max_edge": 0.25}
BUY_MAX_DAYS = 14
ENSEMBLE_CACHE_SEC = 3 * 3600
CLI_CACHE_SEC = 3600
WORKERS = 6
FORECAST_REACH_DAYS = 15  # ECMWF runs reach about 15 days; do not ask for more
UA = {"User-Agent": "paper-bots monthly-precip (read only)"}
_CACHE_LOCK = threading.Lock()


def _s(iem, lat, lon, std, name):
    return {"iem": iem, "lat": lat, "lon": lon, "std": std, "name": name}


# NWS climate-report station per Kalshi rule (CLI code), IEM id, coordinates,
# and the local standard-time offset that defines the climate day.
STATIONS = {
    "NYC": _s("KNYC", 40.7789, -73.9692, -5, "New York (Central Park)"),
    "ABQ": _s("KABQ", 35.0402, -106.6091, -7, "Albuquerque"),
    "ORD": _s("KORD", 41.9786, -87.9048, -6, "Chicago (O'Hare)"),
    "EWR": _s("KEWR", 40.6825, -74.1694, -5, "Newark"),
    "IND": _s("KIND", 39.7173, -86.2944, -5, "Indianapolis"),
    "MSP": _s("KMSP", 44.8831, -93.2289, -6, "Minneapolis"),
    "MSY": _s("KMSY", 29.9934, -90.2580, -6, "New Orleans"),
    "LAX": _s("KLAX", 33.9382, -118.3866, -8, "Los Angeles"),
    "HOU": _s("KHOU", 29.6375, -95.2825, -6, "Houston"),
    "MIA": _s("KMIA", 25.7881, -80.3169, -5, "Miami"),
    "SEA": _s("KSEA", 47.4447, -122.3136, -8, "Seattle"),
    "SFO": _s("KSFO", 37.6197, -122.3656, -8, "San Francisco"),
    "AUS": _s("KAUS", 30.1945, -97.6699, -6, "Austin"),
    "DEN": _s("KDEN", 39.8466, -104.6562, -7, "Denver"),
    "ATL": _s("KATL", 33.6301, -84.4418, -5, "Atlanta"),
    "BOS": _s("KBOS", 42.3606, -71.0097, -5, "Boston"),
    "DCA": _s("KDCA", 38.8483, -77.0341, -5, "Washington DC"),
    "PHL": _s("KPHL", 39.8733, -75.2268, -5, "Philadelphia"),
    "DTW": _s("KDTW", 42.2124, -83.3534, -5, "Detroit"),
}
# Kalshi series -> (station, kind)
SERIES = {
    "KXRAINNYCM": ("NYC", "rain"), "KXRAINABQM": ("ABQ", "rain"), "KXRAINCHIM": ("ORD", "rain"),
    "KXRAINEWRM": ("EWR", "rain"), "KXRAININDM": ("IND", "rain"), "KXRAINMINM": ("MSP", "rain"),
    "KXRAINNOLAM": ("MSY", "rain"), "KXRAINLAXM": ("LAX", "rain"), "KXRAINHOUM": ("HOU", "rain"),
    "KXRAINMIAM": ("MIA", "rain"), "KXRAINSEAM": ("SEA", "rain"), "KXRAINSFOM": ("SFO", "rain"),
    "KXRAINAUSM": ("AUS", "rain"), "KXRAINDENM": ("DEN", "rain"), "KXRAINATLM": ("ATL", "rain"),
    "KXRAINBOSM": ("BOS", "rain"), "KXRAINDCM": ("DCA", "rain"), "KXRAINPHILM": ("PHL", "rain"),
    "KXBOSSNOWM": ("BOS", "snow"), "KXCHISNOWM": ("ORD", "snow"), "KXDENSNOWM": ("DEN", "snow"),
    "KXDETSNOWM": ("DTW", "snow"), "KXSEASNOWM": ("SEA", "snow"), "KXNYCSNOWM": ("NYC", "snow"),
    "KXDCSNOWM": ("DCA", "snow"), "KXPHILSNOWM": ("PHL", "snow"), "KXMSPSNOWM": ("MSP", "snow"),
}


def _cached(name: str, key: str, max_age: float, now: dt.datetime, fetch):
    path = os.path.join(HERE, name)
    saved = engine.read_json(path) or {}
    row = saved.get(key) or {}
    try:
        age = (now - dt.datetime.fromisoformat(str(row.get("at")))).total_seconds()
    except ValueError:
        age = None
    if age is not None and 0 <= age < max_age and row.get("data") is not None:
        return row["data"]
    data = fetch()
    with _CACHE_LOCK:
        # Re-read before writing: other cities in this check save to the same file.
        saved = engine.read_json(path) or {}
        saved[key] = {"at": now.isoformat(timespec="seconds"), "data": data}
        try:
            engine.write_json(path, saved)
        except OSError:
            pass
    return data


def get_cli(code: str, year: int, now: dt.datetime) -> list[dict]:
    st = STATIONS[code]

    def fetch():
        q = urllib.parse.urlencode({"station": st["iem"], "year": year})
        rows = (engine.public_json(f"{pm.IEM_CLI}?{q}", headers=UA, timeout=20) or {}).get("results") or []
        keep = ("valid", "product", "precip_month", "snow_month")
        return [{k: r.get(k) for k in keep} for r in rows[-45:]]
    return _cached("cli_cache.json", f"{code}-{year}", CLI_CACHE_SEC, now, fetch)


def get_members(code: str, kind: str, now: dt.datetime) -> dict:
    st = STATIONS[code]
    var = "precipitation" if kind == "rain" else "snowfall"

    def fetch():
        q = urllib.parse.urlencode({
            "latitude": st["lat"], "longitude": st["lon"], "hourly": var,
            "models": "gfs025,ecmwf_ifs025", "precipitation_unit": "inch",
            "timezone": "GMT", "forecast_days": 16, "past_days": 3,
        })
        hourly = (engine.public_json(f"{pm.ENSEMBLE}?{q}", timeout=30) or {}).get("hourly") or {}
        return pm.daily_sums(hourly, var, st["std"])
    return _cached("ensemble_cache.json", f"{code}-{kind}", ENSEMBLE_CACHE_SEC, now, fetch)


def series_quotes(series: str, markets: list[dict], now: dt.datetime, *, cli=None, members=None):
    """(quotes, note) for one series' open markets."""
    code, kind = SERIES[series]
    st = STATIONS[code]
    by_month: dict = {}
    for market in markets:
        if str(market.get("strike_type") or "") != "greater" or market.get("floor_strike") is None:
            continue
        ym = pm.event_month(market.get("event_ticker"))
        if ym:
            by_month.setdefault(ym, []).append(market)
    if not by_month:
        return [], f"{series}: no greater-than strikes"
    out, notes = [], []
    today = pm.local_std_date(now, st["std"])
    for (year, month), rows in sorted(by_month.items()):
        first, last = pm.month_days(year, month)
        if today > last:
            continue
        results = cli(code, year) if cli else get_cli(code, year, now)
        got = pm.month_to_date(results, year, month, kind, st["std"])
        if got is None:
            notes.append(f"{series} no month-to-date")
            continue
        so_far, through = got
        if today >= first and (today - through).days > pm.MAX_REPORT_AGE_DAYS + 1:
            notes.append(f"{series} climate report is stale (last {through.isoformat()})")
            continue
        start = max(first, through + dt.timedelta(days=1))
        days_left = (last - start).days + 1
        if (last - today).days > FORECAST_REACH_DAYS:
            notes.append(f"{series} forecast does not reach {last.strftime('%b %d')} yet")
            continue
        runs = members(code, kind) if members else get_members(code, kind, now)
        rest = pm.member_rest(runs, start, last, st["std"])
        if len(rest) < pm.MIN_MEMBERS:
            notes.append(f"{series} forecast does not reach {last.strftime('%b %d')} yet "
                         f"({len(rest)} runs do)")
            continue
        samples = pm.draws(so_far, rest, kind, days_left, f"{series}-{year}{month:02d}-{start}")
        rest_sorted = sorted(rest)
        median = rest_sorted[len(rest_sorted) // 2]
        why = (f"{st['name']} {kind} so far {so_far:.2f} in through {through.isoformat()}, "
               f"{days_left} days left, {len(rest)} ensemble runs, median rest {median:.2f} in")
        for market in rows:
            strike = float(market["floor_strike"])
            p_yes = pm.p_greater(samples, strike)
            if p_yes is None:
                continue
            for side in engine.sides(market):
                side["fair"] = p_yes if side["side"] == "yes" else 1.0 - p_yes
                side["label"] = f"{st['name'].split(' (')[0]} {first.strftime('%b')} {kind} > {strike:g} in"
                side["why"] = why
                if days_left > BUY_MAX_DAYS:
                    side["log_only"] = True
                    side["log_reason"] = f"{days_left} days left; buys only within {BUY_MAX_DAYS}"
                out.append(side)
    return out, "; ".join(notes)


def model(cfg: dict, now: dt.datetime, *, list_markets=None, cli=None, members=None):
    list_markets = list_markets or engine.kalshi_open_markets

    def one(series):
        try:
            markets = list_markets(series)
        except Exception as exc:  # noqa: BLE001 - one series failing skips that series
            return [], f"{series} list {type(exc).__name__}"
        if not markets:
            return [], f"no open markets: {series}"
        try:
            return series_quotes(series, markets, now, cli=cli, members=members)
        except Exception as exc:  # noqa: BLE001
            return [], f"{series} {type(exc).__name__}"

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        results = list(pool.map(one, list(SERIES)))
    quotes = [q for qs, _ in results for q in qs]
    notes = [n for _, n in results if n]
    return quotes, "; ".join(notes)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--reset" in argv:
        return engine.reset(SPEC, HERE)
    return engine.run_tower(SPEC, HERE, model)


if __name__ == "__main__":
    raise SystemExit(main())
