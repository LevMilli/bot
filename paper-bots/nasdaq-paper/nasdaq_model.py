"""Fair value for Kalshi end-of-day Nasdaq 100 markets (KXNASDAQ100U strikes,
KXNASDAQ100 ranges). Paper only.

In plain terms:

* **Level:** the live Nasdaq 100 index (^NDX).
* **Volatility:** the Nasdaq volatility index (^VXN), the options market's 30-day
  expected move, applied to the trading minutes left until the 4pm ET close.
  Variance only builds while the market is open (252 days x 390 minutes a year).
* **Fair:** lognormal chance the close lands above a strike or inside a range.
"""
from __future__ import annotations

import datetime as dt
import math
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
TRADING_MIN_YEAR = 252 * 390
MIN_MINUTES = 10
MAX_QUOTE_AGE_SEC = 300
VOL_FLOOR, VOL_CAP = 0.08, 0.80


def minutes_left(now: dt.datetime, close: dt.datetime) -> float | None:
    """Regular-session minutes from now to close, same ET day only."""
    n, c = now.astimezone(ET), close.astimezone(ET)
    if n.date() != c.date() or n.weekday() >= 5:
        return None
    open_ = n.replace(hour=9, minute=30, second=0, microsecond=0)
    if n < open_ or n >= c:
        return None
    return (c - n).total_seconds() / 60.0


def _cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def p_above(level: float, strike: float, vol: float, minutes: float) -> float:
    sd = vol * math.sqrt(minutes / TRADING_MIN_YEAR)
    return _cdf((math.log(level / strike) - 0.5 * sd * sd) / sd)


def fair_yes(market: dict, level: float, vol: float, minutes: float):
    kind = str(market.get("strike_type") or "")
    lo, hi = market.get("floor_strike"), market.get("cap_strike")
    if kind in ("greater", "greater_or_equal") and lo:
        p = p_above(level, float(lo), vol, minutes)
    elif kind in ("less", "less_or_equal") and hi:
        p = 1.0 - p_above(level, float(hi), vol, minutes)
    elif kind == "between" and lo and hi:
        p = p_above(level, float(lo), vol, minutes) - p_above(level, float(hi), vol, minutes)
    else:
        return None
    return min(0.99, max(0.01, p))


def chart_meta(body: dict):
    """(price, unix time) from a Yahoo chart response, or None."""
    try:
        meta = body["chart"]["result"][0]["meta"]
        return float(meta["regularMarketPrice"]), int(meta["regularMarketTime"])
    except (KeyError, IndexError, TypeError, ValueError):
        return None
