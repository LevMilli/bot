"""Fair value for Kalshi's monthly CPI markets from the Cleveland Fed nowcast. Paper only.

In plain terms:

* **Best guess:** the Cleveland Fed publishes a daily "nowcast" of this
  month's CPI (headline and core, month-over-month and year-over-year).
* **How wrong it usually is:** measured from the Cleveland Fed's own charts
  (last ~3 years): how far each day's nowcast landed from the number BLS
  later printed, grouped by how many business days were left before release.
  Early in the month the miss is bigger, so the model is less sure.
* **Safety:** that typical miss is widened by 25% because surprises have fat
  tails.
* **Rounding:** BLS prints one decimal, so "above 0.2%" needs a printed 0.3%
  or more: the true change must be at least 0.25%.
"""
from __future__ import annotations

import datetime as dt
import math
import re

SAFETY = 1.25
MAX_NOWCAST_AGE_DAYS = 5
MIN_HOURS_LEFT = 2.0

# Kalshi series -> (Cleveland file, Cleveland series name, label)
SERIES = {
    "KXCPI": ("month", "CPI Inflation", "CPI MoM"),
    "KXCPICORE": ("month", "Core CPI Inflation", "Core CPI MoM"),
    "KXCPIYOY": ("year", "CPI Inflation", "CPI YoY"),
    "KXCPICOREYOY": ("year", "Core CPI Inflation", "Core CPI YoY"),
}

# Nowcast minus actual at release, last ~36 months, by business days left
# (upper bound of bucket, sd, mean bias). Measured from the Cleveland charts.
ERROR = {
    "KXCPI": [(9, 0.112, -0.002), (14, 0.118, -0.004), (19, 0.136, -0.008), (24, 0.162, -0.009), (99, 0.198, -0.030)],
    "KXCPICORE": [(9, 0.109, 0.016), (14, 0.109, 0.016), (19, 0.109, 0.016), (24, 0.110, 0.017), (99, 0.114, 0.020)],
    "KXCPIYOY": [(9, 0.120, -0.001), (14, 0.125, -0.003), (19, 0.145, -0.004), (24, 0.210, -0.005), (99, 0.236, -0.009)],
    "KXCPICOREYOY": [(9, 0.116, 0.016), (14, 0.116, 0.016), (19, 0.123, 0.021), (24, 0.166, 0.034), (99, 0.194, 0.060)],
}

MONTHS = {m: i for i, m in enumerate(
    ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"), 1)}


def latest_nowcasts(charts: list) -> dict:
    """{"YYYY-MM": {series name: value}} plus "_asof" from a Cleveland nowcast JSON."""
    out = {}
    for chart in charts or []:
        try:
            year, month = str(chart["chart"]["subcaption"]).split("-")
            key = f"{int(year):04d}-{int(month):02d}"
        except (KeyError, TypeError, ValueError):
            continue
        row = {}
        for ds in chart.get("dataset") or []:
            vals = [x.get("value") for x in ds.get("data") or [] if x.get("value") not in ("", None)]
            if vals:
                try:
                    row[str(ds.get("seriesname"))] = float(vals[-1])
                except (TypeError, ValueError):
                    pass
        row["_asof"] = str(chart["chart"].get("_comment") or "")[:10]
        out[key] = row
    return out


def event_month(event_ticker: str) -> str | None:
    """'KXCPI-26NOV' -> '2026-11'."""
    m = re.search(r"-(\d{2})([A-Z]{3})$", event_ticker or "")
    if not m or m.group(2) not in MONTHS:
        return None
    return f"20{m.group(1)}-{MONTHS[m.group(2)]:02d}"


def business_days(start: dt.date, end: dt.date) -> int:
    days, d = 0, start
    while d < end:
        d += dt.timedelta(days=1)
        if d.weekday() < 5:
            days += 1
    return days


def error_for(series: str, bdays: int) -> tuple[float, float]:
    for upper, sd, bias in ERROR[series]:
        if bdays <= upper:
            return sd * SAFETY, bias
    upper, sd, bias = ERROR[series][-1]
    return sd * SAFETY, bias


def _cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def p_above(strike: float, nowcast: float, sd: float, bias: float) -> float:
    """P(printed value > strike) with one-decimal rounding."""
    center = nowcast - bias
    return 1.0 - _cdf((strike + 0.05 - center) / sd)


def fair_yes(market: dict, nowcast: float, sd: float, bias: float) -> float | None:
    if not str(market.get("strike_type") or "").startswith("greater"):
        return None
    try:
        strike = float(market["floor_strike"])
    except (KeyError, TypeError, ValueError):
        return None
    return p_above(strike, nowcast, sd, bias)
