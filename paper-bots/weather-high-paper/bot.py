#!/usr/bin/env python3
"""Weather high: shadow paper tower for Kalshi daily high temperature brackets.

Kalshi lists a bracket ladder each day for NYC, Chicago, Miami, Austin, Denver,
Philadelphia and Los Angeles (KXHIGH*). This tower prices every bracket from
what the station has already recorded plus the ensemble forecast for the hours
left (``weather_model.py``). It buys a side only when the edge after the Kalshi
fee clears the locked economics floor of 0.05.

Paper only. Shadow only. $25 fixed ticket from a $500 sleeve, max 7 open, one per
city-day. Buys only after 15:00 local standard time on the day (the afternoon
lock); earlier brackets are logged for calibration. Exits: model flip at the
bid, settle backstop.
This tower also acts as the weather incubator: ``research.jsonl`` keeps every
bracket's fair vs ask for the calibration lab.
"""
from __future__ import annotations

import datetime as dt
import os
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
DESK_ROOT = os.path.dirname(HERE)
for path in (DESK_ROOT, HERE):
    if path not in sys.path:
        sys.path.insert(0, path)

import kalshi_shadow_tower as engine  # noqa: E402
import weather_model as wm  # noqa: E402

SPEC = {"id": "weather-high", "name": "Weather high", "floor": 0.05, "max_open": 7,
        # An edge this large means the model and the market disagree on the
        # inputs, not that the market is that wrong. Log it; do not buy it.
        "max_edge": 0.25}
DAYS_AHEAD = 1  # today and tomorrow (local)
# Buy window: the afternoon lock. Before this local standard hour on the day, or
# for tomorrow, brackets are priced and logged for calibration only. Morning
# Kalshi weather prices already carry the local forecast; the edge is late in
# the day when most of the high is recorded.
LOCK_HOUR_LST = 15


def _observations(station: str, start: dt.datetime) -> list[dict]:
    q = urllib.parse.urlencode({"start": start.strftime("%Y-%m-%dT%H:%M:%SZ")})
    data = engine.public_json(f"https://api.weather.gov/stations/{station}/observations?{q}",
                              headers=wm.NWS_UA, timeout=15)
    return list((data or {}).get("features") or [])


def _nws_periods(city: dict) -> list[dict]:
    point = engine.public_json(f"https://api.weather.gov/points/{city['lat']},{city['lon']}",
                               headers=wm.NWS_UA, timeout=15)
    url = ((point or {}).get("properties") or {}).get("forecast")
    if not url:
        return []
    data = engine.public_json(url, headers=wm.NWS_UA, timeout=15)
    return list(((data or {}).get("properties") or {}).get("periods") or [])


def _ensemble(city: dict) -> dict:
    q = urllib.parse.urlencode({
        "latitude": city["lat"], "longitude": city["lon"], "hourly": "temperature_2m",
        "models": "gfs025,ecmwf_ifs025", "temperature_unit": "fahrenheit",
        "timezone": "GMT", "forecast_days": 3,
    })
    data = engine.public_json(f"{wm.ENSEMBLE}?{q}", timeout=20)
    return (data or {}).get("hourly") or {}


def city_quotes(series: str, city: dict, now: dt.datetime, markets=None, obs=None, hourly=None,
                periods=None) -> list[dict]:
    markets = engine.kalshi_open_markets(series) if markets is None else markets
    by_day: dict = {}
    for market in markets:
        day = wm.event_day(market.get("event_ticker"))
        if day is not None:
            by_day.setdefault(day, []).append(market)
    if not by_day:
        return []
    out = []
    for day in sorted(by_day):
        start, end = wm.climate_window(day, city["tz"])
        if now >= end + dt.timedelta(hours=8):
            continue  # final report is out; the settle check handles it
        if (start - now).total_seconds() > (DAYS_AHEAD + 1) * 86400:
            continue
        if hourly is None:
            hourly = _ensemble(city)
        if obs is None and now > start:
            obs = _observations(city["station"], start)
        obs_max = wm.observed_max_f(obs or [], start, end) if now > start else None
        if periods is None:
            try:
                periods = _nws_periods(city)
            except Exception:  # noqa: BLE001 - no anchor; the raw ensemble still prices
                periods = []
        nws_high = wm.nws_day_high(periods, day)
        shift = wm.anchor_shift(wm.member_rest_max(hourly, start, end, start), nws_high)
        rest = [v + shift for v in wm.member_rest_max(hourly, start, end, now)]
        sigma = wm.sigma_for(now, end)
        for market in by_day[day]:
            rng = wm.bracket(market)
            if rng is None:
                continue
            samples = wm.draws(obs_max, rest, sigma, str(market.get("ticker")))
            p_yes = wm.prob_in(samples, rng[0], rng[1])
            if p_yes is None:
                continue
            seen = "none yet" if obs_max is None else f"{obs_max:.1f}F"
            anchor = "no NWS high" if nws_high is None else f"NWS high {nws_high:.0f}F (shift {shift:+.1f})"
            why = (f"{city['name']} {day.isoformat()} high so far {seen}, {anchor}, "
                   f"{len(rest)} ensemble runs, sigma {sigma:.1f}F")
            label = f"{city['name']} {day.strftime('%b %d')} {_range_text(rng)}"
            hours_in = (now - start).total_seconds() / 3600.0
            locked = hours_in >= LOCK_HOUR_LST
            for side in engine.sides(market):
                side["fair"] = p_yes if side["side"] == "yes" else 1.0 - p_yes
                if not locked:
                    side["log_only"] = True
                    side["log_reason"] = (f"before {LOCK_HOUR_LST}:00 local lock; "
                                          "logged for calibration")
                side["label"] = label
                side["why"] = why
                out.append(side)
    return out


def _range_text(rng) -> str:
    lo, hi = rng
    if lo is None:
        return f"<= {hi}F"
    if hi is None:
        return f">= {lo}F"
    return f"{lo}-{hi}F"


def model(cfg: dict, now: dt.datetime):
    quotes, failed = [], []
    for series, city in wm.CITIES.items():
        try:
            quotes.extend(city_quotes(series, city, now))
        except Exception as exc:  # noqa: BLE001 - one city's read failing skips that city
            failed.append(f"{city['name']} ({type(exc).__name__})")
    note = ("skipped " + ", ".join(failed)) if failed else ""
    if not quotes and not note:
        note = "no open KXHIGH bracket priced"
    return quotes, note


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--reset" in argv:
        return engine.reset(SPEC, HERE)
    return engine.run_tower(SPEC, HERE, model)


if __name__ == "__main__":
    raise SystemExit(main())
