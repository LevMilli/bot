"""Fair value for Kalshi's daily 10-year Treasury markets (KXUST10A). Paper only.

Kalshi settles each "above X%" market on the Treasury Department's official
10-year par yield for that day (two decimals, struck near 3:30pm ET).

In plain terms:

* **Level now:** the live 10-year yield from Cboe's ^TNX index.
* **How far it can still move:** the typical daily change of the official
  10-year yield over the last 60 trading days, scaled to the minutes left
  until 3:30pm ET (most of the day's move happens 9:00-15:30).
* **Basis:** ^TNX and the official par yield differ by about a basis point.
  The model measures that gap from history and adds it as extra noise.
* **Rounding:** the official yield has two decimals, so "above 5.18" needs a
  printed 5.19 or more: the true yield must be at least 5.185.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import math
import statistics
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
SESSION_MIN = 390.0          # 9:00 -> 15:30 ET
STRIKE_HOUR, STRIKE_MIN = 15, 30
OPEN_HOUR = 9
MIN_MINUTES = 15
MAX_QUOTE_AGE_SEC = 600
DAILY_SD_FLOOR, DAILY_SD_CAP = 0.03, 0.20   # percent points (3-20 bp a day)
BASIS_SD_FLOOR = 0.008
HISTORY_DAYS = 60


def parse_treasury_csv(text: str) -> dict:
    """{YYYY-MM-DD: 10y par yield} from the Treasury daily yield-curve CSV."""
    out = {}
    for row in csv.DictReader(io.StringIO(text)):
        try:
            month, day, year = str(row.get("Date") or "").split("/")
            out[f"{year}-{month}-{day}"] = float(row["10 Yr"])
        except (ValueError, KeyError, TypeError):
            continue
    return out


def daily_sd(cmt: dict) -> float | None:
    days = sorted(cmt)[-(HISTORY_DAYS + 1):]
    moves = [cmt[b] - cmt[a] for a, b in zip(days, days[1:])]
    if len(moves) < 20:
        return None
    return min(DAILY_SD_CAP, max(DAILY_SD_FLOOR, statistics.pstdev(moves)))


def basis(cmt: dict, tnx_closes: dict) -> tuple[float, float] | None:
    """(mean, sd) of official par yield minus ^TNX close on the same day."""
    gaps = [cmt[d] - tnx_closes[d] for d in sorted(set(cmt) & set(tnx_closes))][-HISTORY_DAYS:]
    if len(gaps) < 20:
        return None
    return statistics.mean(gaps), max(BASIS_SD_FLOOR, statistics.pstdev(gaps))


def strike_time(day: dt.date) -> dt.datetime:
    return dt.datetime(day.year, day.month, day.day, STRIKE_HOUR, STRIKE_MIN, tzinfo=ET)


def minutes_left(now: dt.datetime, day: dt.date) -> float | None:
    """Session minutes from now to 3:30pm ET on ``day``; only on that day, 9:00 onward."""
    n = now.astimezone(ET)
    if n.date() != day or n.weekday() >= 5 or n.hour < OPEN_HOUR:
        return None
    left = (strike_time(day) - n).total_seconds() / 60.0
    return left if left > 0 else None


def _cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def p_above(level: float, strike: float, sd_day: float, minutes: float, basis_mean: float, basis_sd: float) -> float:
    """Chance the printed two-decimal yield is strictly above ``strike``."""
    move_sd = sd_day * math.sqrt(min(1.0, max(0.0, minutes) / SESSION_MIN))
    sd = math.sqrt(move_sd ** 2 + basis_sd ** 2)
    center = level + basis_mean
    return _cdf((center - (strike + 0.005)) / sd)


def fair_yes(market: dict, level: float, sd_day: float, minutes: float, basis_mean: float, basis_sd: float):
    kind = str(market.get("strike_type") or "")
    lo, hi = market.get("floor_strike"), market.get("cap_strike")
    if kind in ("greater", "greater_or_equal") and lo is not None:
        p = p_above(level, float(lo), sd_day, minutes, basis_mean, basis_sd)
    elif kind in ("less", "less_or_equal") and hi is not None:
        p = 1.0 - p_above(level, float(hi) - 0.01, sd_day, minutes, basis_mean, basis_sd)
    else:
        return None
    return min(0.99, max(0.01, p))


def event_day(event_ticker: str) -> dt.date | None:
    """KXUST10A-26NOV13 -> 2026-11-13."""
    try:
        return dt.datetime.strptime(event_ticker.rsplit("-", 1)[1], "%y%b%d").date()
    except (IndexError, ValueError):
        return None
