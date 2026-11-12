#!/usr/bin/env python3
"""Gas weekly: shadow paper tower for Kalshi "US gas price this week" (KXAAAGASW).

It reads the AAA national average for regular (today, yesterday and a week ago),
projects it to the settlement date with fading momentum (``gas_model.py``), and
prices every "greater than $X" strike. It buys a side only when the edge after
the Kalshi fee clears the locked economics floor of 0.05.

Paper only. Shadow only. $25 fixed ticket from a $500 sleeve, max 2 open, one per
week. AAA is read at most once an hour (it only updates once a day). Each day's
reading is saved to ``aaa_history.json`` so the model fits its own momentum
after three weeks; until then it buys only within one day of settlement (earlier
strikes are logged for scoring). Exits: model flip at the bid, settle backstop.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DESK_ROOT = os.path.dirname(HERE)
for path in (DESK_ROOT, HERE):
    if path not in sys.path:
        sys.path.insert(0, path)

import kalshi_shadow_tower as engine  # noqa: E402
import gas_model as gm  # noqa: E402

SPEC = {"id": "gas-weekly", "name": "Gas weekly", "floor": 0.05, "max_open": 2, "max_edge": 0.25}
SERIES = "KXAAAGASW"
AAA_CACHE_SEC = 3600
HISTORY_DAYS = 120
LEARN_MAX_DAYS = 1  # until momentum is fitted, buy only on the last day


def _aaa_reading(now: dt.datetime, fetch_html=None) -> dict | None:
    cache = os.path.join(HERE, "aaa_latest.json")
    saved = engine.read_json(cache) or {}
    try:
        fetched = dt.datetime.fromisoformat(str(saved.get("fetched")))
    except ValueError:
        fetched = None
    if fetched is not None and (now - fetched).total_seconds() < AAA_CACHE_SEC and saved.get("reading"):
        return saved["reading"]
    if fetch_html is None:
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        import public_http
        html = public_http.read(gm.AAA_URL, headers=gm.AAA_UA, timeout=20, tries=2).decode("utf-8", "replace")
    else:
        html = fetch_html()
    reading = gm.parse_aaa(html)
    if reading is None:
        return None
    engine.write_json(cache, {"fetched": now.isoformat(timespec="seconds"), "reading": reading})
    _remember(reading)
    return reading


def _remember(reading: dict) -> dict:
    path = os.path.join(HERE, "aaa_history.json")
    history = engine.read_json(path) or {}
    as_of = dt.date.fromisoformat(reading["as_of"])
    history[reading["as_of"]] = reading["current"]
    history.setdefault((as_of - dt.timedelta(days=1)).isoformat(), reading["yesterday"])
    keep = sorted(history)[-HISTORY_DAYS:]
    history = {k: history[k] for k in keep}
    engine.write_json(path, history)
    return history


def quotes_for(markets: list[dict], reading: dict, params: dict) -> list[dict]:
    out = []
    for market in markets:
        if str(market.get("strike_type") or "") != "greater" or market.get("floor_strike") is None:
            continue
        target = gm.event_day(market.get("event_ticker"))
        if target is None:
            continue
        fc = gm.forecast(reading, target, params)
        if fc is None:
            continue
        strike = float(market["floor_strike"])
        p_yes = gm.p_greater(strike, fc)
        how = "fitted" if params.get("fitted") else "default"
        learning = (not params.get("fitted")) and fc["days"] > LEARN_MAX_DAYS
        why = (f"AAA {reading['current']:.4f} as of {reading['as_of']}, {fc['days']}d to "
               f"{target.isoformat()}: mean {fc['mean']:.4f} sd {fc['sd']:.4f} "
               f"(phi {params['phi']} {how}, n {params['n']})")
        for side in engine.sides(market):
            side["fair"] = p_yes if side["side"] == "yes" else 1.0 - p_yes
            side["label"] = f"Gas {target.strftime('%b %d')} > ${strike:.2f}"
            side["why"] = why
            if learning:
                side["log_only"] = True
                side["log_reason"] = (f"learning momentum ({params['n']}/{gm.MIN_HISTORY} days); "
                                      f"buys only within {LEARN_MAX_DAYS}d of settle until fitted")
            out.append(side)
    return out


def model(cfg: dict, now: dt.datetime):
    reading = _aaa_reading(now)
    if reading is None:
        return [], "AAA page did not parse; waiting"
    params = gm.fit(engine.read_json(os.path.join(HERE, "aaa_history.json")) or {})
    markets = engine.kalshi_open_markets(SERIES)
    quotes = quotes_for(markets, reading, params)
    return quotes, "" if quotes else "no open KXAAAGASW strike priced"


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--reset" in argv:
        return engine.reset(SPEC, HERE)
    return engine.run_tower(SPEC, HERE, model)


if __name__ == "__main__":
    raise SystemExit(main())
