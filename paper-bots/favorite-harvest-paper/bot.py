#!/usr/bin/env python3
"""Favorite harvest: shadow paper tower for heavy Kalshi favorites near close.

Looks at 88–94¢ sides 1, 3 or 6 hours before a scheduled close (weather highs,
gas weekly, BTC/ETH daily, Nasdaq, S&P). Fair is the low end of the Wilson
range from the calibration lab: how often sides at that price actually won.
Buys only when that cautious fair beats ask + Kalshi fee by the 0.05 floor.
Waits (logs only) until a cell has at least 50 settled sides.

Paper only. Shadow only. $25 fixed ticket from a $500 sleeve, max 3 open, one
per event. Exits: model flip at the bid, settle backstop.
"""
from __future__ import annotations

import datetime as dt
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DESK_ROOT = os.path.dirname(HERE)
for path in (DESK_ROOT, HERE):
    if path not in sys.path:
        sys.path.insert(0, path)

import calibration_lab as lab  # noqa: E402
import harvest_model as hm  # noqa: E402
import kalshi_shadow_tower as engine  # noqa: E402

SPEC = {"id": "favorite-harvest", "name": "Favorite harvest", "floor": 0.05, "max_open": 3,
        "max_edge": 0.10, "min_ask": hm.MIN_PRICE, "max_ask": hm.MAX_PRICE}


def quotes_for(markets_by_family: dict, table: dict, now: dt.datetime, lookup=lab.lookup) -> list[dict]:
    out = []
    for family, markets in markets_by_family.items():
        for market in markets:
            close = hm.close_of(market)
            if close is None:
                continue
            hours = (close - now).total_seconds() / 3600.0
            horizon = hm.horizon_for(hours)
            if horizon is None:
                continue
            title = _short(str(market.get("title") or market.get("ticker") or ""))
            for side in engine.sides(market):
                priced = hm.price_side(side, family, horizon, table, lookup)
                if priced is None:
                    continue
                priced["label"] = title   # the card adds YES/NO itself
                priced.setdefault("why", f"{family} {horizon}h, no calibration cell yet")
                out.append(priced)
    return out


def _short(title: str, limit: int = 60) -> str:
    """Drop the trailing "?" and cut at a word boundary, never mid-word or mid-year."""
    title = " ".join(title.split()).rstrip("?")
    if len(title) <= limit:
        return title
    return title[:limit].rsplit(" ", 1)[0].rstrip(",") + "..."


def model(cfg: dict, now: dt.datetime, read=None, fetch=None):
    read = read or (lambda: engine.read_json(os.path.join(lab.LAB_DIR, lab.TABLE)) or {})
    fetch = fetch or engine.kalshi_open_markets
    body = read()
    age = hm.table_age_hours(body, now) if body else None
    if age is None:
        return [], "waiting on calibration (lab has not run yet)"
    if age > hm.MAX_TABLE_AGE_H:
        return [], f"calibration is {age:.0f}h old; waiting for a fresh lab run"
    markets = {}
    for family, members in lab.FAMILIES.items():
        rows = []
        for series in members:
            try:
                rows.extend(fetch(series))
            except Exception:  # noqa: BLE001 - one series failing skips it
                continue
        markets[family] = rows
    quotes = quotes_for(markets, body.get("table") or {}, now)
    return quotes, "" if quotes else "no 88-94c favorite 1/3/6h before close"


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--reset" in argv:
        return engine.reset(SPEC, HERE)
    return engine.run_tower(SPEC, HERE, model)


if __name__ == "__main__":
    raise SystemExit(main())
