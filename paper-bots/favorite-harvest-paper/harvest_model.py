"""Favorite harvest: price heavy favorites from the calibration lab's table.

The fair value of a side is the low end of the Wilson 95% range of how often
sides at that price band actually won, the same hours before close, in the
same family. No forecast, no outside feed: only what settled markets showed.
"""
from __future__ import annotations

import datetime as dt

MIN_N = 50                 # cell needs this many settled sides before any buy
MIN_PRICE, MAX_PRICE = 0.88, 0.94   # the lab table stops below 0.95
MAX_TABLE_AGE_H = 48
# hours to close -> lab horizon
WINDOWS = ((1, 0.5, 1.5), (3, 2.0, 4.0), (6, 5.0, 7.0))


def horizon_for(hours: float):
    for h, lo, hi in WINDOWS:
        if lo <= hours <= hi:
            return h
    return None


def close_of(market: dict):
    try:
        return dt.datetime.fromisoformat(str(market.get("close_time")).replace("Z", "+00:00"))
    except ValueError:
        return None


def table_age_hours(body: dict, now: dt.datetime):
    try:
        updated = dt.datetime.fromisoformat(str(body.get("updated")))
    except ValueError:
        return None
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=dt.timezone.utc)
    return (now - updated).total_seconds() / 3600.0


def price_side(side: dict, family: str, horizon: int, table: dict, lookup) -> dict | None:
    """Attach fair (Wilson low end) to one side; None if the side is not a favorite."""
    ask = side.get("ask")
    if ask is None or not (MIN_PRICE <= ask <= MAX_PRICE):
        return None
    cell = lookup(family, horizon, ask, table)
    out = dict(side)
    if not cell:
        out.update(fair=ask, log_only=True, log_reason="waiting on calibration (no cell yet)")
        return out
    n = int(cell.get("n") or 0)
    lo = float(cell.get("wilson_lo") or 0.0)
    out["fair"] = lo
    out["why"] = (f"{family} {horizon}h band {cell.get('avg_price', ask):.2f}: won {cell.get('wins')}/{n} "
                  f"({cell.get('win_rate', 0):.0%}), cautious {lo:.3f}")
    if n < MIN_N:
        out.update(log_only=True, log_reason=f"waiting on calibration (n {n} < {MIN_N})")
    return out
