"""US regular gas price model for Kalshi KXAAAGASW. Paper only, read-only.

Kalshi settles "US gas price this week" on the AAA national average for regular
shown on the settlement date (gasprices.aaa.com, updated once a day early morning ET).

Model, in plain terms:

* **Today's move:** a blend of yesterday-to-today and the week's average daily change.
* **Fading momentum:** retail gas moves in runs, but a run slows. Each day ahead
  keeps ``phi`` of the previous day's move (``phi`` = 0.9 until the tower has its
  own history).
* **Spread:** day-to-day noise grows with the square root of days ahead. On top
  of that, a share of the drift itself is uncertain, because nobody knows exactly
  how fast a run fades.
* **Learning:** the tower saves one AAA reading per day in ``aaa_history.json``.
  With 21+ days it fits ``phi`` and the noise from its own history (with bounds),
  and stops guessing.

Fair value for "greater than K" is ``P(price > K)`` under a normal with that mean
and spread. AAA prints four decimals, so ties are ignored.
"""
from __future__ import annotations

import datetime as dt
import math
import re

AAA_URL = "https://gasprices.aaa.com/"
AAA_UA = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "text/html",
}
PHI_DEFAULT = 0.9
NOISE_DEFAULT = 0.008      # $/gal day-to-day noise
DRIFT_UNCERTAINTY = 0.35   # share of the projected drift that is itself uncertain
MIN_HISTORY = 21
_MONTHS = {m: i for i, m in enumerate(
    ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"), 1)}


def parse_aaa(html: str) -> dict | None:
    """{as_of, current, yesterday, week_ago} for regular gas. None if the page changed."""
    text = str(html or "")
    as_of = re.search(r"Price as of\s*(\d{1,2})/(\d{1,2})/(\d{2})", text)

    def row(label: str):
        match = re.search(re.escape(label) + r"\s*</td>\s*<td>\s*\$([0-9]+\.[0-9]+)", text)
        return float(match.group(1)) if match else None

    cur, yday, week = row("Current Avg."), row("Yesterday Avg."), row("Week Ago Avg.")
    if not as_of or None in (cur, yday, week):
        return None
    month, day, year = (int(g) for g in as_of.groups())
    try:
        when = dt.date(2000 + year, month, day)
    except ValueError:
        return None
    if not all(1.0 < v < 10.0 for v in (cur, yday, week)):
        return None
    return {"as_of": when.isoformat(), "current": cur, "yesterday": yday, "week_ago": week}


def event_day(event_ticker: str):
    """KXAAAGASW-26NOV16 -> date(2026, 11, 16)."""
    match = re.search(r"-(\d{2})([A-Z]{3})(\d{2})$", str(event_ticker or ""))
    if not match or match.group(2) not in _MONTHS:
        return None
    try:
        return dt.date(2000 + int(match.group(1)), _MONTHS[match.group(2)], int(match.group(3)))
    except ValueError:
        return None


def fit(history: dict) -> dict:
    """phi and noise from saved daily readings; defaults until MIN_HISTORY days."""
    days = sorted(history or {})
    prices = []
    for prev, cur in zip(days, days[1:]):
        if (dt.date.fromisoformat(cur) - dt.date.fromisoformat(prev)).days == 1:
            prices.append((float(history[prev]), float(history[cur])))
    changes = [b - a for a, b in prices]
    if len(changes) < MIN_HISTORY:
        return {"phi": PHI_DEFAULT, "noise": NOISE_DEFAULT, "n": len(changes), "fitted": False}
    xs, ys = changes[:-1], changes[1:]
    sxx = sum(x * x for x in xs)
    phi = sum(x * y for x, y in zip(xs, ys)) / sxx if sxx > 0 else PHI_DEFAULT
    phi = min(0.98, max(0.3, phi))
    resid = [y - phi * x for x, y in zip(xs, ys)]
    noise = math.sqrt(sum(r * r for r in resid) / max(1, len(resid) - 1))
    noise = min(0.03, max(0.003, noise))
    return {"phi": round(phi, 3), "noise": round(noise, 4), "n": len(changes), "fitted": True}


def forecast(reading: dict, target: dt.date, params: dict) -> dict | None:
    """Mean and sd of the AAA regular average on ``target``. None if it is not ahead."""
    as_of = dt.date.fromisoformat(reading["as_of"])
    days = (target - as_of).days
    if days < 0:
        return None
    cur = float(reading["current"])
    if days == 0:
        return {"mean": cur, "sd": 0.0005, "days": 0, "drift": 0.0}
    d1 = cur - float(reading["yesterday"])
    d7 = (cur - float(reading["week_ago"])) / 7.0
    move = 0.5 * d1 + 0.5 * d7
    phi = float(params["phi"])
    steps = sum(phi ** k for k in range(1, days + 1))
    drift = move * steps
    sd = math.sqrt((float(params["noise"]) * math.sqrt(days)) ** 2 + (DRIFT_UNCERTAINTY * drift) ** 2)
    return {"mean": cur + drift, "sd": max(sd, 0.002), "days": days, "drift": drift}


def p_greater(strike: float, fc: dict) -> float:
    z = (float(fc["mean"]) - float(strike)) / float(fc["sd"])
    p = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
    return min(0.99, max(0.01, p))
