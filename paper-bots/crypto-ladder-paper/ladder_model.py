"""Fair value for Kalshi daily crypto strikes (KXBTCD / KXETHD). Paper only.

Kalshi settles on the 60-second average of the CF Benchmarks index (BRTI / ERTI)
before 5pm ET. The model, in plain terms:

* **Spot:** Coinbase's last trade (close to the CF index, which blends Coinbase
  with other big exchanges). A small basis allowance covers the difference.
* **Volatility:** Deribit's options market. For each strike we read the implied
  vol from the option smile at the Deribit expiries around the Kalshi close and
  blend them by total variance. That captures skew, not just one ATM number.
* **Fair:** lognormal chance spot ends above the strike (Black-Scholes N(d2),
  zero rates).
"""
from __future__ import annotations

import datetime as dt
import math
import re

YEAR_SEC = 365.0 * 86400.0
BASIS = 0.0006          # Coinbase vs CF index, as a share of spot
MIN_MINUTES = 15        # too close to the print: spot noise dominates
MAX_HOURS = 30
MAX_SPOT_GAP = 0.005    # Deribit underlying vs Coinbase spot
_MONTHS = {m: i for i, m in enumerate(
    ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"), 1)}
_INSTR = re.compile(r"^(BTC|ETH)-(\d{1,2})([A-Z]{3})(\d{2})-(\d+)-([CP])$")


def parse_instrument(name: str):
    """BTC-13NOV26-84000-P -> (coin, expiry 08:00Z, strike, 'P')."""
    match = _INSTR.match(str(name or ""))
    if not match or match.group(3) not in _MONTHS:
        return None
    coin, day, mon, yy, strike, cp = match.groups()
    try:
        expiry = dt.datetime(2000 + int(yy), _MONTHS[mon], int(day), 8, tzinfo=dt.timezone.utc)
    except ValueError:
        return None
    return coin, expiry, float(strike), cp


def smiles(summary: list[dict]) -> dict:
    """{expiry: {"underlying": u, "points": [(strike, iv), ...]}} from out-of-the-money options."""
    out: dict = {}
    for row in summary or []:
        parsed = parse_instrument(row.get("instrument_name"))
        iv, under = row.get("mark_iv"), row.get("underlying_price")
        if not parsed or not iv or not under:
            continue
        _, expiry, strike, cp = parsed
        if (cp == "C" and strike < under) or (cp == "P" and strike > under):
            continue
        slot = out.setdefault(expiry, {"underlying": float(under), "points": {}})
        slot["points"][strike] = float(iv) / 100.0
    for slot in out.values():
        slot["points"] = sorted(slot["points"].items())
    return {k: v for k, v in out.items() if len(v["points"]) >= 3}


def iv_at(points: list, strike: float) -> float:
    """Linear in strike, flat beyond the ends."""
    if strike <= points[0][0]:
        return points[0][1]
    if strike >= points[-1][0]:
        return points[-1][1]
    for (k0, v0), (k1, v1) in zip(points, points[1:]):
        if k0 <= strike <= k1:
            return v0 + (v1 - v0) * (strike - k0) / (k1 - k0)
    return points[-1][1]


def vol_for(smile_map: dict, close: dt.datetime, strike: float, now: dt.datetime):
    """Implied vol for this strike at this close, interpolated in total variance."""
    if not smile_map:
        return None
    exps = sorted(e for e in smile_map if e > now)
    if not exps:
        return None
    after = [e for e in exps if e >= close]
    before = [e for e in exps if e < close]
    t_close = (close - now).total_seconds() / YEAR_SEC
    if not after:
        return iv_at(smile_map[before[-1]]["points"], strike)
    e1 = after[0]
    v1 = iv_at(smile_map[e1]["points"], strike)
    if not before:
        return v1
    e0 = before[-1]
    v0 = iv_at(smile_map[e0]["points"], strike)
    t0 = (e0 - now).total_seconds() / YEAR_SEC
    t1 = (e1 - now).total_seconds() / YEAR_SEC
    w = (t_close - t0) / (t1 - t0)
    var = (1 - w) * v0 * v0 * t0 + w * v1 * v1 * t1
    return math.sqrt(max(var, 1e-12) / t_close)


def p_above(spot: float, strike: float, vol: float, years: float) -> float:
    sd = math.sqrt(vol * vol * years + BASIS * BASIS)
    d2 = (math.log(spot / strike) - 0.5 * sd * sd) / sd
    p = 0.5 * (1.0 + math.erf(d2 / math.sqrt(2.0)))
    return min(0.99, max(0.01, p))


def underlying_near(smile_map: dict, close: dt.datetime):
    exps = sorted(smile_map)
    if not exps:
        return None
    best = min(exps, key=lambda e: abs((e - close).total_seconds()))
    return smile_map[best]["underlying"]
