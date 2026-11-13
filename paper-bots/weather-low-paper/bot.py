#!/usr/bin/env python3
"""Weather low: shadow paper tower for Kalshi daily low temperature brackets (KXLOWT*).

Twin of Weather high for the other end of the day. Prices every low bracket in
24 cities from what the station has already recorded plus the ensemble
forecast for the hours left (``weather_extra.py``). By mid-morning most of the
low is in, so the buy window opens at 10:00 local standard time; earlier
brackets are logged for calibration. Buys a side only when the edge after the
Kalshi fee clears the locked economics floor of 0.05.

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

SPEC = {"id": "weather-low", "name": "Weather low", "floor": 0.05, "max_open": 6, "max_edge": 0.25}
# The low usually lands near dawn. A front can still pull the evening lower; the
# ensemble's remaining hours carry that risk.
LOCK_HOUR_LST = 10


def model(cfg: dict, now: dt.datetime):
    quotes, note = wx.run_cities(HERE, "low", wx.LOW_SERIES, now, LOCK_HOUR_LST)
    if not quotes and not note:
        note = "no open KXLOWT bracket priced"
    return quotes, note


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--reset" in argv:
        return engine.reset(SPEC, HERE)
    return engine.run_tower(SPEC, HERE, model)


if __name__ == "__main__":
    raise SystemExit(main())
