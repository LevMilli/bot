"""Monthly rain and snow totals for Kalshi KXRAIN*M and KX*SNOWM. Paper only, no network.

Kalshi settles "total precipitation (or snowfall) at station X in month M is
strictly greater than K inches" on the monthly total in the NWS daily climate
report (CLI) for that station, to the hundredth of an inch (tenth for snow).

Model, in plain terms:

* **Already fallen:** the month-to-date total in the latest complete CLI
  report (read from the Iowa Environmental Mesonet copy). "T" (trace) counts
  as zero. A report written before the day ended does not count as complete.
* **Still to fall:** every Open-Meteo ensemble run (GFS 0.25 and ECMWF IFS 0.25)
  that reaches the end of the month adds up its hourly amounts from the day
  after the last complete report through the last day of the month, in local
  standard time (the climate day).
* **Spread:** ensembles are too sure of themselves about rain amounts, so each
  run is drawn many times with a random scale (about +/-35% for rain, +/-50% for
  snow) plus a small chance of a shower the models missed.
* **No guessing past the forecast:** a run that stops before the month ends is
  dropped. With fewer than 20 runs that reach the end, the city is skipped.

Fair value for "greater than K" is the share of draws whose rounded total is
above K.
"""
from __future__ import annotations

import calendar
import datetime as dt
import math
import random
import re
import zlib

ENSEMBLE = "https://ensemble-api.open-meteo.com/v1/ensemble"
IEM_CLI = "https://mesonet.agron.iastate.edu/json/cli.py"
MIN_MEMBERS = 20
DRAWS_PER_MEMBER = 40
SCALE_SD = {"rain": 0.35, "snow": 0.50}
MISS_CHANCE = 0.3                       # chance a draw gets a small amount the models missed
MISS_PER_DAY = {"rain": 0.01, "snow": 0.03}  # mean inches per day left for that missed amount
DECIMALS = {"rain": 2, "snow": 1}
MAX_REPORT_AGE_DAYS = 3
_MONTHS = {m: i for i, m in enumerate(
    ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"), 1)}


def event_month(event_ticker: str):
    """KXRAINNYCM-26NOV -> (2026, 11). None when it does not parse."""
    match = re.search(r"-(\d{2})([A-Z]{3})$", str(event_ticker or ""))
    if not match or match.group(2) not in _MONTHS:
        return None
    return 2000 + int(match.group(1)), _MONTHS[match.group(2)]


def month_days(year: int, month: int) -> tuple[dt.date, dt.date]:
    return dt.date(year, month, 1), dt.date(year, month, calendar.monthrange(year, month)[1])


def local_std_date(when: dt.datetime, std_offset_h: int) -> dt.date:
    return (when.astimezone(dt.timezone.utc) + dt.timedelta(hours=std_offset_h)).date()


def _num(value):
    """CLI numbers: "T" (trace) is 0, "M" (missing) is None."""
    if value in ("T", "t"):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _product_time(product: str):
    match = re.match(r"(\d{12})-", str(product or ""))
    if not match:
        return None
    return dt.datetime.strptime(match.group(1), "%Y%m%d%H%M").replace(tzinfo=dt.timezone.utc)


def month_to_date(results: list[dict], year: int, month: int, kind: str, std_offset_h: int):
    """(total so far, last complete day) from IEM CLI rows. (0.0, day before the 1st)
    when the month has not started in any complete report yet. None if missing.

    A row counts as complete only if its report was written after that climate
    day ended (midnight local standard time); the afternoon preview does not.
    """
    first, last = month_days(year, month)
    key = "precip_month" if kind == "rain" else "snow_month"
    best = None
    for row in results or []:
        try:
            day = dt.date.fromisoformat(str(row.get("valid")))
        except ValueError:
            continue
        if not (first <= day <= last):
            continue
        written = _product_time(row.get("product"))
        day_end = dt.datetime.combine(day + dt.timedelta(days=1), dt.time(0),
                                      dt.timezone(dt.timedelta(hours=std_offset_h)))
        if written is None or written < day_end:
            continue
        value = _num(row.get(key))
        if value is None:
            continue
        if best is None or day > best[1]:
            best = (value, day)
    if best is None:
        return 0.0, first - dt.timedelta(days=1)
    return best


def daily_sums(hourly: dict, var: str, std_offset_h: int) -> dict:
    """{member key: {"days": {YYYY-MM-DD: inches}, "last": ISO time of last value}}.

    Open-Meteo hourly amounts are for the hour ending at the stamp, so an
    amount stamped exactly at local midnight belongs to the day before.
    """
    stamps = []
    for text in hourly.get("time") or []:
        try:
            when = dt.datetime.fromisoformat(str(text))
        except ValueError:
            stamps.append(None)
            continue
        stamps.append(when if when.tzinfo else when.replace(tzinfo=dt.timezone.utc))
    out = {}
    for key, values in hourly.items():
        if not key.startswith(var) or "probability" in key or not isinstance(values, list):
            continue
        days: dict = {}
        last = None
        for when, value in zip(stamps, values):
            if when is None or value is None:
                continue
            day = local_std_date(when - dt.timedelta(minutes=1), std_offset_h).isoformat()
            days[day] = round(days.get(day, 0.0) + max(0.0, float(value)), 4)
            last = when if last is None or when > last else last
        if days:
            out[key] = {"days": days, "last": last.isoformat()}
    return out


def member_rest(members: dict, start_day: dt.date, end_day: dt.date, std_offset_h: int) -> list[float]:
    """Per run that reaches the end of ``end_day``: inches from ``start_day`` through ``end_day``."""
    need = dt.datetime.combine(end_day + dt.timedelta(days=1), dt.time(0),
                               dt.timezone(dt.timedelta(hours=std_offset_h)))
    out = []
    for row in (members or {}).values():
        try:
            last = dt.datetime.fromisoformat(str(row.get("last")))
        except ValueError:
            continue
        if last < need:
            continue
        total = 0.0
        day = start_day
        while day <= end_day:
            total += float((row.get("days") or {}).get(day.isoformat(), 0.0))
            day += dt.timedelta(days=1)
        out.append(total)
    return out


def draws(so_far: float, rest: list[float], kind: str, days_left: int, seed: str) -> list[float]:
    rng = random.Random(zlib.crc32(seed.encode("utf-8")))
    sd = SCALE_SD[kind]
    miss_mean = MISS_PER_DAY[kind] * max(0, days_left)
    out = []
    for member in rest:
        for _ in range(DRAWS_PER_MEMBER):
            amount = member * math.exp(rng.gauss(0.0, sd) - sd * sd / 2.0)
            if miss_mean > 0 and rng.random() < MISS_CHANCE:
                amount += rng.expovariate(1.0 / miss_mean)
            out.append(round(so_far + amount, DECIMALS[kind]))
    return out


def p_greater(samples: list[float], strike: float):
    if not samples:
        return None
    p = sum(1 for s in samples if s > float(strike) + 1e-9) / len(samples)
    return min(0.99, max(0.01, p))
