"""Fair value for Kalshi's quarterly GDP markets from Atlanta Fed GDPNow. Paper only.

In plain terms:

* **Best guess:** the Atlanta Fed's GDPNow estimate of this quarter's real
  GDP growth (annualized), updated after each big data release.
* **How wrong it usually is:** measured from GDPNow's own archive since 2014
  (2020 left out): the root-mean-square miss against BEA's first print,
  grouped by how many days were left before that print. A quarter out the
  miss is about 1.6 points; in the last two weeks it is about 0.9.
* **Early optimism:** far from the print, GDPNow has run high on average
  (about +0.8 points two months out, near zero in the last month). The
  measured average miss for that horizon is taken off the estimate.
* **Rounding:** BEA prints one decimal, so "above 3.0%" needs 3.05% or more.
"""
from __future__ import annotations

import datetime as dt
import math
import re

MAX_AGE_DAYS = 10
MAX_DAYS_LEFT = 45          # further out GDPNow is too rough: log only, never buy
MIN_HOURS_LEFT = 2.0
BUCKET_DAYS = 14
SD_FLOOR = 0.8
MONTHS = {m: i for i, m in enumerate(
    ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"), 1)}
# Fallback if the archive cannot be read: (max days left, rmse, mean miss), measured Nov 2026.
DEFAULT_ERROR = [(13, 0.935, 0.056), (27, 0.896, 0.048), (41, 1.27, 0.254), (55, 1.224, 0.358),
                 (69, 1.471, 0.722), (83, 1.638, 0.82), (9999, 1.776, 0.77)]


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def error_table(archive_rows, gdp_col: int = 27, actual_col: int = 31, days_col: int = 33) -> list:
    """[(max days left, rmse, mean miss)] from GDPNow's TrackingArchives sheet (header row skipped)."""
    buckets = {}
    for row in archive_rows:
        try:
            gdp, actual, days, quarter = row[gdp_col], row[actual_col], row[days_col], row[1]
        except (IndexError, TypeError):
            continue
        if not (_num(gdp) and _num(actual) and _num(days)) or days < 0:
            continue
        if getattr(quarter, "year", None) == 2020:
            continue
        buckets.setdefault(min(int(days) // BUCKET_DAYS, 6), []).append(gdp - actual)
    if len(buckets) < 4:
        return []
    table = []
    for k in sorted(buckets):
        errs = buckets[k]
        rmse = math.sqrt(sum(e * e for e in errs) / len(errs))
        upper = 9999 if k == 6 else (k + 1) * BUCKET_DAYS - 1
        table.append((upper, round(max(SD_FLOOR, rmse), 3), round(sum(errs) / len(errs), 3)))
    return table


def current(evolution_rows) -> dict | None:
    """Latest GDPNow value, its date and quarter label from CurrentQtrEvolution."""
    quarter, last = None, None
    for row in evolution_rows:
        if not row or len(row) < 3:
            continue
        when, note, value = row[0], row[1], row[2]
        m = re.search(r"(\d{2}):Q([1-4])", str(note or ""))
        if m and quarter is None:
            quarter = f"20{m.group(1)}Q{m.group(2)}"
        if isinstance(when, (dt.datetime, dt.date)) and _num(value):
            last = (when, float(value))
    if not quarter or not last:
        return None
    day = last[0].date() if isinstance(last[0], dt.datetime) else last[0]
    return {"quarter": quarter, "value": last[1], "asof": day.isoformat()}


def event_release(event_ticker: str) -> dt.date | None:
    """'KXGDP-27JAN28' -> 2027-01-28."""
    m = re.search(r"-(\d{2})([A-Z]{3})(\d{2})$", event_ticker or "")
    if not m or m.group(2) not in MONTHS:
        return None
    try:
        return dt.date(2000 + int(m.group(1)), MONTHS[m.group(2)], int(m.group(3)))
    except ValueError:
        return None


def release_quarter(release: dt.date) -> str:
    """The quarter whose first print comes out on ``release`` (the last one that ended before it)."""
    q = (release.month - 1) // 3       # 0..3: the quarter we are in
    year = release.year
    if q == 0:
        return f"{year - 1}Q4"
    return f"{year}Q{q}"


def error_for(table: list, days_left: int) -> tuple[float, float]:
    """(sd, mean miss) for this many days before the print."""
    rows = [tuple(r) for r in (table or DEFAULT_ERROR) if len(r) == 3] or DEFAULT_ERROR
    for upper, sd, bias in rows:
        if days_left <= upper:
            return sd, bias
    return rows[-1][1], rows[-1][2]


def _cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def p_above(strike: float, nowcast: float, sd: float, bias: float = 0.0) -> float:
    """P(BEA prints above ``strike``): needs strike + 0.05 or more after rounding."""
    return 1.0 - _cdf((strike + 0.05 - (nowcast - bias)) / sd)
