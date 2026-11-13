"""Fed curve: pure math that turns 30-day fed funds futures into meeting odds.

The free CME FedWatch page has no public feed, so this rebuilds the same idea
from the futures themselves (Yahoo ``ZQ<month><yy>.CBT``, price -> average
rate for that month = 100 - price) and the meeting days Kalshi lists.

Chain, month by month (the CME method):
* A month with no meeting: the rate at the start and end of the month is the
  month's average.
* A month with a meeting on day d of N (the new rate starts the next day):
  end = (average x N - start x d) / (N - d). If the next month has no meeting,
  its average is used as the end instead (steadier when d is late).
* The first month uses today's NY Fed effective rate as its start when the
  meeting is still ahead in that month.

Expected move = end - start. It is split between the two nearest 25bp steps
(1.08 steps -> 92% "hike 25", 8% "hike 50+"). Later meetings stack the error
of every earlier one, so only the nearest ``BUY_MEETINGS`` meetings may buy.
"""
from __future__ import annotations

import calendar
import datetime as dt
import math

CODES = "FGHJKMNQUVXZ"
STEP = 0.25
CLIP = (0.01, 0.99)
BUY_MEETINGS = 2
MAX_FUTURE_AGE_SEC = 4 * 86400  # covers a weekend
OUTCOMES = ("cut50", "cut25", "hold", "hike25", "hike50")


def zq_symbol(year: int, month: int) -> str:
    return f"ZQ{CODES[month - 1]}{year % 100:02d}.CBT"


def next_month(ym: tuple[int, int]) -> tuple[int, int]:
    y, m = ym
    return (y + 1, 1) if m == 12 else (y, m + 1)


def rate_from_price(price) -> float | None:
    try:
        p = float(price)
    except (TypeError, ValueError):
        return None
    if not (90.0 < p <= 100.0):
        return None
    return 100.0 - p


def meeting_days(markets: list[dict]) -> dict:
    """{(year, month): decision day} from Kalshi KXFEDDECISION close times (2pm ET)."""
    out = {}
    for m in markets or []:
        raw = str(m.get("close_time") or "")
        try:
            at = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            continue
        out[(at.year, at.month)] = at.day
    return out


def chain(avgs: dict, meetings: dict, first: tuple[int, int], today_day: int,
          effr_now: float | None = None) -> dict:
    """{(year, month): (rate before, rate after)} for each meeting the futures cover."""
    out = {}
    if not meetings or first not in avgs:
        return out
    last = max(meetings)
    ym = first
    if first in meetings and meetings[first] >= today_day:
        if effr_now is None:
            return out
        start = float(effr_now)
    elif first in meetings:
        # This month's meeting is behind us; the month's average is the new level.
        start = avgs[first]
        ym = next_month(first)
    else:
        start = avgs[first]
    while ym <= last:
        if ym not in avgs:
            break
        n = calendar.monthrange(*ym)[1]
        if ym in meetings and (ym != first or meetings[ym] >= today_day):
            d = meetings[ym]
            nxt = next_month(ym)
            if nxt not in meetings and nxt in avgs:
                end = avgs[nxt]
            elif n - d > 0:
                end = (avgs[ym] * n - start * d) / (n - d)
            else:
                break
            out[ym] = (start, end)
            start = end
        else:
            start = avgs[ym]
        ym = next_month(ym)
    return out


def odds(before: float, after: float) -> dict:
    """Split the expected move across the two nearest 25bp steps."""
    steps = (after - before) / STEP
    lo = math.floor(steps)
    frac = steps - lo
    p = {k: 0.0 for k in OUTCOMES}

    def bucket(k: int) -> str:
        if k <= -2:
            return "cut50"
        if k >= 2:
            return "hike50"
        return {-1: "cut25", 0: "hold", 1: "hike25"}[k]

    p[bucket(lo)] += 1.0 - frac
    p[bucket(lo + 1)] += frac
    return {k: round(min(CLIP[1], max(CLIP[0], v)), 4) for k, v in p.items()}
