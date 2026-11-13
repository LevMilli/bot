#!/usr/bin/env python3
"""Weather cities: shadow paper tower for Kalshi daily highs in 17 more cities (KXHIGHT*).

Twin of Weather high with the same model and the same 15:00 local afternoon
lock, for the cities Weather high does not read: Atlanta, Boston, Dallas,
Washington DC, Newark, Houston, Las Vegas, Minneapolis, New Orleans, Oklahoma
City, Phoenix, San Diego, San Antonio, Louisville, Seattle, San Francisco and
Trenton (``weather_extra.py``). Buys a side only when the edge after the Kalshi
fee clears the locked economics floor of 0.05.

Paper only. Shadow only. $25 fixed ticket from a $500 sleeve, max 6 open, one
per city-day. Exits: model flip at the bid, settle backstop.
"""
from __future__ import annotations

import datetime as dt
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DESK_ROOT = os.path.dirname(HERE)
if DESK_ROOT not in sys.path:
    sys.path.insert(0, DESK_ROOT)

import kalshi_shadow_tower as engine  # noqa: E402
import weather_extra as wx  # noqa: E402

SPEC = {"id": "weather-cities", "name": "Weather cities", "floor": 0.05, "max_open": 6, "max_edge": 0.25}
LOCK_HOUR_LST = 15  # same afternoon lock as Weather high


def model(cfg: dict, now: dt.datetime):
    quotes, note = wx.run_cities(HERE, "high", wx.HIGH_SERIES, now, LOCK_HOUR_LST)
    if not quotes and not note:
        note = "no open KXHIGHT bracket priced"
    return quotes, note


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--reset" in argv:
        return engine.reset(SPEC, HERE)
    return engine.run_tower(SPEC, HERE, model)


if __name__ == "__main__":
    raise SystemExit(main())
