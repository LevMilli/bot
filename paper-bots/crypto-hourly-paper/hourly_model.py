"""Fair value for Kalshi hourly coin strikes (SOL, XRP, DOGE, BNB). Paper only.

Kalshi settles each "above $X" (KXSOLD, KXXRPD, KXDOGED, KXBNBD) and each range
(KXSOL, KXXRP, KXDOGE, KXBNB) market on the 60-second average of the CF
Benchmarks index before the close. These coins have no deep option market, so
the model is simpler than the BTC/ETH ladder:

* **Spot:** Coinbase's last trade, with a small basis allowance for the CF index.
* **Volatility:** realized, from Coinbase candles. For a close under an hour
  away it uses 5-minute bars (about the last day); for a close four or more
  hours away it uses hourly bars (about the last two weeks), blending in
  between. Each is the larger of the full window and its most recent stretch,
  so a fresh shock is not averaged away, with a floor and a cap.
* **Fair:** lognormal chance spot ends above the strike (N(d2), zero rates).
"""
from __future__ import annotations

import math

YEAR_SEC = 365.0 * 86400.0
BASIS = 0.0008            # Coinbase vs CF index, as a share of spot
MIN_MINUTES = 10          # too close to the print: averaging noise dominates
MAX_HOURS = 30            # next hourly closes and the daily 5pm close; not the weekly
VOL_FLOOR = 0.30          # annualized
VOL_CAP = 3.00
SHORT_MIN, LONG_MIN = 60.0, 240.0


def realized_vol(candles: list, bar_sec: int = 300) -> float | None:
    """Annualized vol from Coinbase candles [[time, low, high, open, close, volume], ...]."""
    rows = sorted((r for r in candles or [] if isinstance(r, (list, tuple)) and len(r) >= 5),
                  key=lambda r: r[0])
    closes = [float(r[4]) for r in rows if r[4] and float(r[4]) > 0]
    if len(closes) < 24:
        return None
    rets = [math.log(b / a) for a, b in zip(closes, closes[1:])]

    def ann(xs):
        if len(xs) < 12:
            return None
        mean = sum(xs) / len(xs)
        var = sum((x - mean) ** 2 for x in xs) / max(1, len(xs) - 1)
        return math.sqrt(var * YEAR_SEC / bar_sec)

    full, recent = ann(rets), ann(rets[-48:])
    best = max(v for v in (full, recent) if v is not None)
    return min(VOL_CAP, max(VOL_FLOOR, best))


def vol_for(minutes: float, short_vol: float | None, long_vol: float | None) -> float | None:
    """5-minute vol for near closes, hourly vol for far ones, linear in between."""
    if short_vol is None and long_vol is None:
        return None
    if short_vol is None:
        return long_vol
    if long_vol is None:
        return short_vol
    w = min(1.0, max(0.0, (float(minutes) - SHORT_MIN) / (LONG_MIN - SHORT_MIN)))
    return (1.0 - w) * short_vol + w * long_vol


def p_above(spot: float, strike: float, vol: float, years: float) -> float:
    sd = math.sqrt(vol * vol * years + BASIS * BASIS)
    d2 = (math.log(spot / strike) - 0.5 * sd * sd) / sd
    p = 0.5 * (1.0 + math.erf(d2 / math.sqrt(2.0)))
    return min(0.99, max(0.01, p))


def p_yes(market: dict, spot: float, vol: float, years: float) -> float | None:
    """YES chance for one Kalshi row: greater, less, or between (floor..cap)."""
    kind = str(market.get("strike_type") or "")
    try:
        lo = None if market.get("floor_strike") is None else float(market["floor_strike"])
        hi = None if market.get("cap_strike") is None else float(market["cap_strike"])
    except (TypeError, ValueError):
        return None
    if kind == "greater" and lo:
        return p_above(spot, lo, vol, years)
    if kind == "less" and hi:
        return 1.0 - p_above(spot, hi, vol, years)
    if kind == "between" and lo and hi and hi > lo:
        p = p_above(spot, lo, vol, years) - p_above(spot, hi, vol, years)
        return min(0.99, max(0.01, p))
    return None
