"""Daily high temperature model for Kalshi KXHIGH* brackets. Paper only, read-only.

Kalshi settles each market on that city's NWS climate report (the CLI station,
for example CLINYC for Central Park). The day is midnight to midnight local
**standard** time, and the high is a whole °F.

For one city and one day:

1. Observed so far: the max of the station's NWS observations since the day
   began (api.weather.gov, °C converted to °F).
2. Rest of day: the hourly 2 m temperature from every Open-Meteo ensemble
   member (GFS 0.25° plus ECMWF IFS 0.25°, about 80 runs) for the hours still
   ahead in that day.
3. Anchor: when the NWS point forecast has a daytime high for that day, every
   member is shifted so the ensemble median high equals it. Raw ensembles run a
   degree or two off at a given station; the NWS number is the local forecast.
4. Draw the final high per member:
   ``max(observed + |N(0, 0.5)|, member_rest + shift + N(0, σ))``, rounded to a
   whole °F. The ensemble spread already carries most of the uncertainty, so σ
   adds only a little (0.8°F at the day's end, up to 2.0°F a day out). The 0.5°F
   pad reflects that hourly reports can miss a peak between them.
5. A bracket's fair value is the share of draws that land in it.

No draw is made when there is no forecast and no observation; a missing input
skips the market and nothing is invented.
"""
from __future__ import annotations

import datetime as dt
import math
import random
import re
import zlib
from zoneinfo import ZoneInfo

# Kalshi series -> CLI station, the NWS ASOS id, coordinates, and time zone.
CITIES = {
    "KXHIGHNY": {"cli": "CLINYC", "station": "KNYC", "lat": 40.7789, "lon": -73.9692, "tz": "America/New_York", "name": "NYC"},
    "KXHIGHCHI": {"cli": "CLIMDW", "station": "KMDW", "lat": 41.7861, "lon": -87.7522, "tz": "America/Chicago", "name": "Chicago"},
    "KXHIGHMIA": {"cli": "CLIMIA", "station": "KMIA", "lat": 25.7881, "lon": -80.3169, "tz": "America/New_York", "name": "Miami"},
    "KXHIGHAUS": {"cli": "CLIAUS", "station": "KAUS", "lat": 30.1945, "lon": -97.6699, "tz": "America/Chicago", "name": "Austin"},
    "KXHIGHDEN": {"cli": "CLIDEN", "station": "KDEN", "lat": 39.8466, "lon": -104.6562, "tz": "America/Denver", "name": "Denver"},
    "KXHIGHPHIL": {"cli": "CLIPHL", "station": "KPHL", "lat": 39.8733, "lon": -75.2268, "tz": "America/New_York", "name": "Philadelphia"},
    "KXHIGHLAX": {"cli": "CLILAX", "station": "KLAX", "lat": 33.9382, "lon": -118.3866, "tz": "America/Los_Angeles", "name": "Los Angeles"},
}

NWS_UA = {"User-Agent": "paper-bots weather-high (paper-only research)", "Accept": "application/geo+json"}
ENSEMBLE = "https://ensemble-api.open-meteo.com/v1/ensemble"
OBS_PAD_F = 0.5
SIGMA_MIN = 0.8
SIGMA_MAX = 2.0
SIGMA_PER_HOUR = 0.03
DRAWS_PER_MEMBER = 40
_MONTHS = {m: i for i, m in enumerate(
    ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"), 1)}


def c_to_f(c: float) -> float:
    return c * 9.0 / 5.0 + 32.0


def event_day(event_ticker: str):
    """KXHIGHNY-26NOV12 -> date(2026, 11, 12). None if the code does not parse."""
    match = re.search(r"-(\d{2})([A-Z]{3})(\d{2})$", str(event_ticker or ""))
    if not match or match.group(2) not in _MONTHS:
        return None
    try:
        return dt.date(2000 + int(match.group(1)), _MONTHS[match.group(2)], int(match.group(3)))
    except ValueError:
        return None


def climate_window(day: dt.date, tz_name: str) -> tuple[dt.datetime, dt.datetime]:
    """UTC start/end of the climate day: local standard time midnight to midnight."""
    zone = ZoneInfo(tz_name)
    noon = dt.datetime(day.year, day.month, day.day, 12, tzinfo=zone)
    std = noon.utcoffset() - (noon.dst() or dt.timedelta(0))
    start = dt.datetime(day.year, day.month, day.day, tzinfo=dt.timezone(std))
    start = start.astimezone(dt.timezone.utc)
    return start, start + dt.timedelta(days=1)


def bracket(market: dict):
    """(lo, hi) in reported whole °F, inclusive; None for an open side. None if unreadable."""
    kind = str(market.get("strike_type") or "")
    floor = market.get("floor_strike")
    cap = market.get("cap_strike")
    try:
        if kind == "between" and floor is not None and cap is not None:
            return (int(round(float(floor))), int(round(float(cap))))
        if kind == "less" and cap is not None:
            return (None, int(round(float(cap))) - 1)      # "less than 59" = 58 or below
        if kind == "greater" and floor is not None:
            return (int(round(float(floor))) + 1, None)    # "greater than 66" = 67 or above
    except (TypeError, ValueError):
        return None
    return None


def observed_max_f(observations: list[dict], start: dt.datetime, end: dt.datetime):
    """Max °F of NWS observation features inside [start, end). None when none."""
    best = None
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
            value = c_to_f(float(temp))
        except (TypeError, ValueError):
            continue
        best = value if best is None else max(best, value)
    return best


def member_rest_max(hourly: dict, start: dt.datetime, end: dt.datetime, now: dt.datetime) -> list[float]:
    """Per ensemble member: max °F over forecast hours in [max(start, now), end)."""
    times = []
    for text in hourly.get("time") or []:
        try:
            when = dt.datetime.fromisoformat(str(text))
        except ValueError:
            times.append(None)
            continue
        times.append(when if when.tzinfo else when.replace(tzinfo=dt.timezone.utc))
    begin = max(start, now)
    idx = [i for i, when in enumerate(times) if when is not None and begin <= when < end]
    out = []
    for key, values in hourly.items():
        if not key.startswith("temperature_2m") or not isinstance(values, list):
            continue
        pts = [values[i] for i in idx if i < len(values) and values[i] is not None]
        if pts:
            out.append(float(max(pts)))
    return out


def nws_day_high(periods: list[dict], day: dt.date):
    """Daytime high (°F) the NWS forecast gives for ``day``. None if it is not listed."""
    for period in periods or []:
        if not period.get("isDaytime"):
            continue
        try:
            start = dt.datetime.fromisoformat(str(period.get("startTime")))
        except ValueError:
            continue
        if start.date() != day:
            continue
        temp = period.get("temperature")
        unit = str(period.get("temperatureUnit") or "F").upper()
        if isinstance(temp, dict):
            temp = temp.get("value")
        try:
            value = float(temp)
        except (TypeError, ValueError):
            return None
        return c_to_f(value) if unit == "C" else value
    return None


def anchor_shift(full_day_max: list[float], nws_high) -> float:
    """Shift that moves the ensemble median full-day high onto the NWS high (capped ±4°F)."""
    if nws_high is None or not full_day_max:
        return 0.0
    ordered = sorted(full_day_max)
    median = ordered[len(ordered) // 2]
    return max(-4.0, min(4.0, float(nws_high) - median))


def sigma_for(now: dt.datetime, end: dt.datetime) -> float:
    hours = max(0.0, (end - now).total_seconds() / 3600.0)
    return min(SIGMA_MAX, SIGMA_MIN + SIGMA_PER_HOUR * hours)


def draws(obs_max, rest: list[float], sigma: float, seed: str) -> list[int]:
    """Reported whole-°F highs. Empty when there is nothing to draw from."""
    rng = random.Random(zlib.crc32(seed.encode("utf-8")))
    out = []
    if rest:
        for member in rest:
            for _ in range(DRAWS_PER_MEMBER):
                value = member + rng.gauss(0.0, sigma)
                if obs_max is not None:
                    value = max(value, obs_max + abs(rng.gauss(0.0, OBS_PAD_F)))
                out.append(int(math.floor(value + 0.5)))
    elif obs_max is not None:
        for _ in range(DRAWS_PER_MEMBER * 20):
            out.append(int(math.floor(obs_max + abs(rng.gauss(0.0, OBS_PAD_F)) + 0.5)))
    return out


def prob_in(samples: list[int], lo, hi) -> float | None:
    if not samples:
        return None
    hit = sum(1 for s in samples if (lo is None or s >= lo) and (hi is None or s <= hi))
    # Keep a little humility at the edges: never 0 or 1.
    p = (hit + 0.5) / (len(samples) + 1.0)
    return min(0.99, max(0.01, p))
