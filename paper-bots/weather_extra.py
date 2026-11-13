"""Shared model for the weather twins: daily lows and more high-temperature cities.

Paper only, read-only. Used by ``weather-low-paper`` (KXLOWT* daily lows) and
``weather-cities-paper`` (KXHIGHT* highs for cities the Weather high tower does
not cover). The Weather high tower itself does not import this file and is not
changed by it.

The math is the Weather high model (``weather-high-paper/weather_model.py``,
loaded read-only by file path) plus a mirror image for lows:

* Observed so far: the station's NWS observations since the climate day began
  (midnight local standard time). Max for highs, min for lows. Hourly reports
  carry tenths of a degree; the 5-minute reports in between carry whole
  degrees C, so they count only as a bound 0.5C toward the safe side.
* Rest of day: every Open-Meteo ensemble member (GFS 0.25 plus ECMWF IFS 0.25)
  for the hours still ahead. Max for highs, min for lows.
* Anchor: the NWS point forecast. Highs use the daytime high for that day; lows
  use the overnight low of the night that ends on that day's morning. Members
  are shifted so their median matches (capped at 4F either way).
* Draw: highs ``max(obs + |N(0, 0.5)|, member + shift + N(0, sigma))``;
  lows ``min(obs - |N(0, 0.5)|, member + shift + N(0, sigma))``, rounded to
  whole F. A bracket's fair value is the share of draws inside it.

Kalshi settles both on the station's daily climate value (CLI code in each
series rule). Every station below was read from the series rules.

Reads are cached in the tower folder: the ensemble and NWS forecast for an hour
(Open-Meteo's free tier is about 10,000 calls a day), the NWS point lookup for a
week. Station observations are read fresh. A missing input skips that city.
"""
from __future__ import annotations

import concurrent.futures
import datetime as dt
import importlib.util
import math
import os
import random
import re
import sys
import threading
import urllib.parse
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import kalshi_shadow_tower as engine  # noqa: E402


def _load_high_model():
    path = os.path.join(HERE, "weather-high-paper", "weather_model.py")
    spec = importlib.util.spec_from_file_location("weather_high_model_readonly", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


wm = _load_high_model()

NY, CHI, DEN, LA, PHX = ("America/New_York", "America/Chicago", "America/Denver",
                         "America/Los_Angeles", "America/Phoenix")


def _c(cli, station, lat, lon, tz, name):
    return {"cli": cli, "station": station, "lat": lat, "lon": lon, "tz": tz, "name": name}


# Station per city (CLI code from the Kalshi rules, ASOS id and coordinates).
STATIONS = {
    "NYC": _c("CLINYC", "KNYC", 40.7789, -73.9692, NY, "NYC"),
    "CHI": _c("CLIMDW", "KMDW", 41.7861, -87.7522, CHI, "Chicago"),
    "MIA": _c("CLIMIA", "KMIA", 25.7881, -80.3169, NY, "Miami"),
    "AUS": _c("CLIAUS", "KAUS", 30.1945, -97.6699, CHI, "Austin"),
    "DEN": _c("CLIDEN", "KDEN", 39.8466, -104.6562, DEN, "Denver"),
    "PHIL": _c("CLIPHL", "KPHL", 39.8733, -75.2268, NY, "Philadelphia"),
    "LAX": _c("CLILAX", "KLAX", 33.9382, -118.3866, LA, "Los Angeles"),
    "ATL": _c("CLIATL", "KATL", 33.6301, -84.4418, NY, "Atlanta"),
    "BOS": _c("CLIBOS", "KBOS", 42.3606, -71.0097, NY, "Boston"),
    "DAL": _c("CLIDFW", "KDFW", 32.8998, -97.0403, CHI, "Dallas"),
    "DC": _c("CLIDCA", "KDCA", 38.8483, -77.0341, NY, "Washington DC"),
    "EWR": _c("CLIEWR", "KEWR", 40.6825, -74.1694, NY, "Newark"),
    "HOU": _c("CLIHOU", "KHOU", 29.6375, -95.2825, CHI, "Houston"),
    "LV": _c("CLILAS", "KLAS", 36.0719, -115.1634, LA, "Las Vegas"),
    "MIN": _c("CLIMSP", "KMSP", 44.8831, -93.2289, CHI, "Minneapolis"),
    "NOLA": _c("CLIMSY", "KMSY", 29.9934, -90.2580, CHI, "New Orleans"),
    "OKC": _c("CLIOKC", "KOKC", 35.3889, -97.6006, CHI, "Oklahoma City"),
    "PHX": _c("CLIPHX", "KPHX", 33.4278, -112.0037, PHX, "Phoenix"),
    "SAN": _c("CLISAN", "KSAN", 32.7336, -117.1831, LA, "San Diego"),
    "SATX": _c("CLISAT", "KSAT", 29.5443, -98.4839, CHI, "San Antonio"),
    "SDF": _c("CLISDF", "KSDF", 38.1811, -85.7392, NY, "Louisville"),
    "SEA": _c("CLISEA", "KSEA", 47.4447, -122.3136, LA, "Seattle"),
    "SFO": _c("CLISFO", "KSFO", 37.6197, -122.3656, LA, "San Francisco"),
    "TTN": _c("CLITTN", "KTTN", 40.2767, -74.8156, NY, "Trenton"),
}

# Highs the Weather high tower does not cover (it keeps NYC, Chicago, Miami,
# Austin, Denver, Philadelphia and LA).
HIGH_SERIES = {f"KXHIGHT{code}": code for code in (
    "ATL", "BOS", "DAL", "DC", "EWR", "HOU", "LV", "MIN", "NOLA", "OKC", "PHX",
    "SAN", "SATX", "SDF", "SEA", "SFO", "TTN")}
# Lows for every city Kalshi lists.
LOW_SERIES = {f"KXLOWT{code}": code for code in (
    "NYC", "CHI", "MIA", "AUS", "DEN", "PHIL", "LAX", "ATL", "BOS", "DAL", "DC", "EWR",
    "HOU", "LV", "MIN", "NOLA", "OKC", "PHX", "SAN", "SATX", "SDF", "SEA", "SFO", "TTN")}

ENSEMBLE_CACHE_SEC = 3600
FORECAST_CACHE_SEC = 3600
POINT_CACHE_SEC = 7 * 86400
DAYS_AHEAD = 1
WORKERS = 6
_CACHE_LOCK = threading.Lock()  # city threads share one cache file


# ------------------------------------------------------------------ pure math (lows)
_TGROUP = re.compile(r"\sT[01]\d{3}[01]\d{3}")
COARSE_HALF_C = 0.5  # 5-minute reports carry whole degrees C: the truth is within 0.5C


def _readings(observations: list[dict], start: dt.datetime, end: dt.datetime):
    """(F, precise) for each NWS observation inside [start, end).

    Hourly METARs carry a tenths-of-a-degree T group and are exact enough. The
    5-minute reports in between carry whole degrees C, so they only bound the
    truth to within 0.5C (0.9F) either way.
    """
    for feat in observations or []:
        props = (feat or {}).get("properties") or {}
        try:
            when = dt.datetime.fromisoformat(str(props.get("timestamp")))
        except ValueError:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=dt.timezone.utc)
        if not (start <= when < end):
            continue
        temp = (props.get("temperature") or {}).get("value")
        if temp is None:
            continue
        try:
            c = float(temp)
        except (TypeError, ValueError):
            continue
        precise = bool(_TGROUP.search(str(props.get("rawMessage") or ""))) or abs(c - round(c)) > 1e-6
        yield c, precise


def observed_extreme_f(observations: list[dict], start: dt.datetime, end: dt.datetime, kind: str):
    """What the station has surely reached so far, in F. None when nothing is in.

    For a low it is the lowest exact reading, or a whole-degree reading plus
    0.5C (the true value was at most that). For a high, the mirror image.
    """
    best = None
    for c, precise in _readings(observations, start, end):
        if kind == "low":
            value = wm.c_to_f(c if precise else c + COARSE_HALF_C)
            best = value if best is None else min(best, value)
        else:
            value = wm.c_to_f(c if precise else c - COARSE_HALF_C)
            best = value if best is None else max(best, value)
    return best


def observed_min_f(observations: list[dict], start: dt.datetime, end: dt.datetime):
    return observed_extreme_f(observations, start, end, "low")


def observed_max_f(observations: list[dict], start: dt.datetime, end: dt.datetime):
    return observed_extreme_f(observations, start, end, "high")


def member_rest_min(hourly: dict, start: dt.datetime, end: dt.datetime, now: dt.datetime) -> list[float]:
    """Per ensemble member: min F over forecast hours in [max(start, now), end)."""
    flipped = {k: ([None if v is None else -float(v) for v in vals] if k.startswith("temperature_2m")
                   and isinstance(vals, list) else vals) for k, vals in (hourly or {}).items()}
    return [-v for v in wm.member_rest_max(flipped, start, end, now)]


def nws_night_low(periods: list[dict], day: dt.date):
    """Overnight low (F) of the NWS night period that ends on ``day``. None if not listed."""
    for period in periods or []:
        if period.get("isDaytime"):
            continue
        try:
            end = dt.datetime.fromisoformat(str(period.get("endTime")))
        except ValueError:
            continue
        if end.date() != day:
            continue
        temp = period.get("temperature")
        unit = str(period.get("temperatureUnit") or "F").upper()
        if isinstance(temp, dict):
            temp = temp.get("value")
        try:
            value = float(temp)
        except (TypeError, ValueError):
            return None
        return wm.c_to_f(value) if unit == "C" else value
    return None


def anchor_shift_low(full_day_min: list[float], nws_low) -> float:
    """Shift that moves the ensemble median full-day low onto the NWS low (capped 4F)."""
    if nws_low is None or not full_day_min:
        return 0.0
    ordered = sorted(full_day_min)
    median = ordered[len(ordered) // 2]
    return max(-4.0, min(4.0, float(nws_low) - median))


def draws_low(obs_min, rest: list[float], sigma: float, seed: str) -> list[int]:
    """Reported whole-F lows. Empty when there is nothing to draw from."""
    rng = random.Random(zlib.crc32(seed.encode("utf-8")))
    out = []
    if rest:
        for member in rest:
            for _ in range(wm.DRAWS_PER_MEMBER):
                value = member + rng.gauss(0.0, sigma)
                if obs_min is not None:
                    value = min(value, obs_min - abs(rng.gauss(0.0, wm.OBS_PAD_F)))
                out.append(int(math.floor(value + 0.5)))
    elif obs_min is not None:
        for _ in range(wm.DRAWS_PER_MEMBER * 20):
            out.append(int(math.floor(obs_min - abs(rng.gauss(0.0, wm.OBS_PAD_F)) + 0.5)))
    return out


def range_text(rng) -> str:
    lo, hi = rng
    if lo is None:
        return f"<= {hi}F"
    if hi is None:
        return f">= {lo}F"
    return f"{lo}-{hi}F"


# ------------------------------------------------------------------ reads (cached)
def _cached(tower: str, name: str, key: str, max_age: float, now: dt.datetime, fetch):
    path = os.path.join(tower, name)
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


def ensemble(tower: str, code: str, city: dict, now: dt.datetime) -> dict:
    def fetch():
        q = urllib.parse.urlencode({
            "latitude": city["lat"], "longitude": city["lon"], "hourly": "temperature_2m",
            "models": "gfs025,ecmwf_ifs025", "temperature_unit": "fahrenheit",
            "timezone": "GMT", "forecast_days": 3,
        })
        return (engine.public_json(f"{wm.ENSEMBLE}?{q}", timeout=20) or {}).get("hourly") or {}
    return _cached(tower, "ensemble_cache.json", code, ENSEMBLE_CACHE_SEC, now, fetch)


def nws_periods(tower: str, code: str, city: dict, now: dt.datetime) -> list[dict]:
    def point():
        data = engine.public_json(f"https://api.weather.gov/points/{city['lat']},{city['lon']}",
                                  headers=wm.NWS_UA, timeout=15)
        return ((data or {}).get("properties") or {}).get("forecast") or ""

    def fetch():
        url = _cached(tower, "nws_points.json", code, POINT_CACHE_SEC, now, point)
        if not url:
            return []
        data = engine.public_json(url, headers=wm.NWS_UA, timeout=15)
        return list(((data or {}).get("properties") or {}).get("periods") or [])
    return _cached(tower, "nws_forecast_cache.json", code, FORECAST_CACHE_SEC, now, fetch)


def observations(station: str, start: dt.datetime) -> list[dict]:
    q = urllib.parse.urlencode({"start": start.strftime("%Y-%m-%dT%H:%M:%SZ")})
    data = engine.public_json(f"https://api.weather.gov/stations/{station}/observations?{q}",
                              headers=wm.NWS_UA, timeout=15)
    return list((data or {}).get("features") or [])


# ------------------------------------------------------------------ quotes
def city_quotes(kind: str, city: dict, now: dt.datetime, markets: list[dict], *, hourly: dict,
                obs=None, periods=None, lock_hour: float, obs_fetch=None) -> list[dict]:
    """Quote rows for one city's open brackets. ``kind`` is "high" or "low"."""
    by_day: dict = {}
    for market in markets or []:
        day = wm.event_day(market.get("event_ticker"))
        if day is not None:
            by_day.setdefault(day, []).append(market)
    out = []
    for day in sorted(by_day):
        start, end = wm.climate_window(day, city["tz"])
        if now >= end + dt.timedelta(hours=8):
            continue  # final report is out; the settle check handles it
        if (start - now).total_seconds() > (DAYS_AHEAD + 1) * 86400:
            continue
        day_obs = obs
        if day_obs is None and now > start and obs_fetch is not None:
            day_obs = obs_fetch(city["station"], start)
        if kind == "high":
            seen = observed_max_f(day_obs or [], start, end) if now > start else None
            nws = wm.nws_day_high(periods or [], day)
            shift = wm.anchor_shift(wm.member_rest_max(hourly, start, end, start), nws)
            rest = [v + shift for v in wm.member_rest_max(hourly, start, end, now)]
        else:
            seen = observed_min_f(day_obs or [], start, end) if now > start else None
            nws = nws_night_low(periods or [], day)
            shift = anchor_shift_low(member_rest_min(hourly, start, end, start), nws)
            rest = [v + shift for v in member_rest_min(hourly, start, end, now)]
        sigma = wm.sigma_for(now, end)
        hours_in = (now - start).total_seconds() / 3600.0
        locked = hours_in >= lock_hour
        for market in by_day[day]:
            rng = wm.bracket(market)
            if rng is None:
                continue
            seed = str(market.get("ticker"))
            samples = (wm.draws(seen, rest, sigma, seed) if kind == "high"
                       else draws_low(seen, rest, sigma, seed))
            p_yes = wm.prob_in(samples, rng[0], rng[1])
            if p_yes is None:
                continue
            seen_txt = "none yet" if seen is None else f"{seen:.1f}F"
            what = "NWS high" if kind == "high" else "NWS night low"
            anchor = f"no {what}" if nws is None else f"{what} {nws:.0f}F (shift {shift:+.1f})"
            why = (f"{city['name']} {day.isoformat()} {kind} so far {seen_txt}, {anchor}, "
                   f"{len(rest)} ensemble runs, sigma {sigma:.1f}F")
            label = f"{city['name']} {day.strftime('%b %d')} {kind} {range_text(rng)}"
            for side in engine.sides(market):
                side["fair"] = p_yes if side["side"] == "yes" else 1.0 - p_yes
                if not locked:
                    side["log_only"] = True
                    side["log_reason"] = f"before {lock_hour:g}:00 local lock; logged for calibration"
                side["label"] = label
                side["why"] = why
                out.append(side)
    return out


def run_cities(tower: str, kind: str, series_map: dict, now: dt.datetime, lock_hour: float,
               *, list_markets=None, get_ensemble=None, get_periods=None, get_obs=None):
    """(quotes, note) across every series. One city failing skips that city."""
    list_markets = list_markets or engine.kalshi_open_markets
    get_ensemble = get_ensemble or (lambda code, city: ensemble(tower, code, city, now))
    get_periods = get_periods or (lambda code, city: nws_periods(tower, code, city, now))
    get_obs = get_obs or observations

    def one(series: str, code: str):
        city = STATIONS[code]
        markets = list_markets(series)
        if not markets:
            return series, [], "dormant"
        hourly = get_ensemble(code, city)
        try:
            periods = get_periods(code, city)
        except Exception:  # noqa: BLE001 - no anchor; the raw ensemble still prices
            periods = []
        rows = city_quotes(kind, city, now, markets, hourly=hourly, periods=periods,
                           lock_hour=lock_hour, obs_fetch=get_obs)
        return series, rows, ""

    quotes, failed, dormant = [], [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(one, s, c): s for s, c in series_map.items()}
        for fut in concurrent.futures.as_completed(futures):
            series = futures[fut]
            try:
                _, rows, flag = fut.result()
            except Exception as exc:  # noqa: BLE001
                failed.append(f"{STATIONS[series_map[series]]['name']} ({type(exc).__name__})")
                continue
            if flag == "dormant":
                dormant.append(series)
            quotes.extend(rows)
    quotes.sort(key=lambda q: (q.get("ticker") or "", q.get("side") or ""))
    parts = []
    if failed:
        parts.append("skipped " + ", ".join(sorted(failed)))
    if dormant:
        parts.append("no open markets: " + ", ".join(sorted(dormant)))
    return quotes, "; ".join(parts)
