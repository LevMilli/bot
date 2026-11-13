#!/usr/bin/env python3
"""Fed curve: shadow twin of Fed Watch with a second, independent read.

Idea B22. Fed Watch buys Kalshi KXFEDDECISION outcomes when Polymarket's price
says they are cheap. This twin adds the fed funds futures curve (see
``curve_model.py``) and only buys when BOTH agree:

* Fair per side = the lower of the futures-curve chance and the Polymarket mid
  (``fed-watch-paper/fed_feed.py``, read-only). If the two differ by more than
  0.15 the row is logged, not bought.
* No Polymarket price, no futures for that month, a futures quote older than
  4 days, or a meeting past the nearest two -> logged only.
* Edge = fair - Kalshi ask - fee; buy only if >= the locked economics floor 0.05
  and <= the 0.15 trust cap.

Paper only. Shadow only. $25 ticket, $500 sleeve, max 2 open, one per meeting.
Fed Watch itself is not changed.
"""
from __future__ import annotations

import datetime as dt
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DESK_ROOT = os.path.dirname(HERE)
for path in (DESK_ROOT, HERE, os.path.join(DESK_ROOT, "fed-watch-paper")):
    if path not in sys.path:
        sys.path.insert(0, path)

import kalshi_shadow_tower as engine  # noqa: E402
import curve_model as cm  # noqa: E402
import fed_feed  # noqa: E402 - Fed Watch's Polymarket reader, read-only

SPEC = {"id": "fed-curve", "name": "Fed curve", "floor": 0.05, "max_open": 2, "max_edge": 0.15}
MAX_DISAGREE = 0.15
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=5d"
EFFR = "https://markets.newyorkfed.org/api/rates/unsecured/effr/last/1.json"
UA = {"User-Agent": "Mozilla/5.0 (paper)"}


def future_rate(body: dict, now: dt.datetime):
    """(average rate, age seconds) from a Yahoo chart reply, or None."""
    try:
        meta = body["chart"]["result"][0]["meta"]
    except (KeyError, IndexError, TypeError):
        return None
    rate = cm.rate_from_price(meta.get("regularMarketPrice"))
    if rate is None:
        return None
    try:
        age = now.timestamp() - float(meta.get("regularMarketTime"))
    except (TypeError, ValueError):
        age = float("inf")
    return rate, age


def effr_rate(body: dict):
    try:
        return float(body["refRates"][0]["percentRate"])
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def quotes_for(markets: list[dict], curve: dict, pm: dict) -> list[dict]:
    order = sorted(curve)
    out = []
    for market in markets:
        meeting = fed_feed.kalshi_meeting(market.get("event_ticker"))
        key = fed_feed.KALSHI_OUTCOME.get(str(market.get("ticker") or "").rsplit("-", 1)[-1])
        if not meeting or not key:
            continue
        if meeting not in curve:
            continue  # no futures for that month: skip quietly
        before, after = curve[meeting]
        p_curve = cm.odds(before, after)[key]
        pm_row = pm.get((meeting[0], meeting[1], key))
        p_pm = pm_row["fair"] if pm_row else None
        name = f"Fed {dt.date(meeting[0], meeting[1], 1).strftime('%b %Y')} {fed_feed.LABEL[key]}"
        why = f"futures {before:.3f}% -> {after:.3f}%: P {p_curve:.3f}"
        why += f"; Polymarket {p_pm:.3f}" if p_pm is not None else "; no Polymarket price"
        reason = ""
        if p_pm is None:
            reason = "no Polymarket second read"
        elif abs(p_curve - p_pm) > MAX_DISAGREE:
            reason = f"futures and Polymarket differ by {abs(p_curve - p_pm):.2f}"
        elif order.index(meeting) >= cm.BUY_MEETINGS:
            reason = "meeting too far out for the curve"
        for side in engine.sides(market):
            if side["side"] == "yes":
                fair = p_curve if p_pm is None else min(p_curve, p_pm)
            else:
                fair = 1 - p_curve if p_pm is None else min(1 - p_curve, 1 - p_pm)
            side.update(fair=round(fair, 4), label=name, why=why)
            if reason:
                side.update(log_only=True, log_reason=reason)
            out.append(side)
    return out


def _why(exc: Exception) -> str:
    code = getattr(exc, "code", None)
    return f"HTTP {code}" if code else type(exc).__name__


def model(cfg: dict, now: dt.datetime):
    try:
        markets = engine.kalshi_open_markets("KXFEDDECISION", limit=200, pages=2)
    except Exception as exc:  # noqa: BLE001
        return [], f"Kalshi Fed list {_why(exc)}; waiting"
    meetings = cm.meeting_days(markets)
    if not meetings:
        return [], "no open Fed meeting on Kalshi"
    first = (now.year, now.month)
    avgs, ym = {}, first
    # One month past the last meeting helps the late-meeting formula.
    while ym <= cm.next_month(max(meetings)):
        try:
            got = future_rate(engine.public_json(YAHOO.format(sym=cm.zq_symbol(*ym)), headers=UA), now)
        except Exception:  # noqa: BLE001
            got = None
        if not got or got[1] > cm.MAX_FUTURE_AGE_SEC:
            break  # the chain stops at the first missing or stale month
        avgs[ym] = got[0]
        ym = cm.next_month(ym)
    effr = None
    if first in meetings and meetings[first] >= now.day:
        try:
            effr = effr_rate(engine.public_json(EFFR, headers=UA))
        except Exception as exc:  # noqa: BLE001
            return [], f"NY Fed rate {_why(exc)}; waiting"
    curve = cm.chain(avgs, meetings, first, now.day, effr)
    if not curve:
        return [], "fed funds futures missing; waiting"
    try:
        pm = fed_feed.pm_fairs(fed_feed.polymarket_events())
    except Exception:  # noqa: BLE001
        pm = {}
    quotes = quotes_for(markets, curve, pm)
    return quotes, "" if quotes else "no Fed market priced"


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--reset" in argv:
        return engine.reset(SPEC, HERE)
    return engine.run_tower(SPEC, HERE, model)


if __name__ == "__main__":
    raise SystemExit(main())
