#!/usr/bin/env python3
"""Gas monthly: shadow paper tower for Kalshi "US gas price at month end" (KXAAAGASM).

Same model as Gas weekly (``gas-weekly-paper/gas_model.py``, read here without
changing it): the AAA national average for regular, projected to the settlement
date with fading momentum, priced against every "greater than $X" strike.

The month-end bet is further away than the weekly one, so this tower is more
careful:

* It never buys more than 14 days before settlement.
* Until momentum is fitted from 21+ days of saved readings, it buys only within
  3 days of settlement. Everything else is logged for scoring.
* It keeps its own ``aaa_history.json`` and also reads Gas weekly's saved
  history (read only) so it can fit sooner.

Paper only. Shadow only. $25 fixed ticket from a $500 sleeve, max 2 open, one per
month. Exits: model flip at the bid, settle backstop.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DESK_ROOT = os.path.dirname(HERE)
if DESK_ROOT not in sys.path:
    sys.path.insert(0, DESK_ROOT)

import kalshi_shadow_tower as engine  # noqa: E402

WEEKLY_DIR = os.path.join(DESK_ROOT, "gas-weekly-paper")


def _load_gas_model():
    spec = importlib.util.spec_from_file_location("gas_model_monthly_readonly",
                                                  os.path.join(WEEKLY_DIR, "gas_model.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gm = _load_gas_model()

SPEC = {"id": "gas-monthly", "name": "Gas monthly", "floor": 0.05, "max_open": 2, "max_edge": 0.25}
SERIES = "KXAAAGASM"
AAA_CACHE_SEC = 3600
HISTORY_DAYS = 120
LEARN_MAX_DAYS = 3   # until momentum is fitted, buy only in the last 3 days
MAX_DAYS = 14        # never buy further out than this


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


def merged_history() -> dict:
    """Own saved readings plus Gas weekly's (read only). Own readings win on ties."""
    weekly = engine.read_json(os.path.join(WEEKLY_DIR, "aaa_history.json")) or {}
    own = engine.read_json(os.path.join(HERE, "aaa_history.json")) or {}
    out = {}
    for source in (weekly, own):
        if isinstance(source, dict):
            for day, price in source.items():
                try:
                    dt.date.fromisoformat(str(day))
                    out[str(day)] = float(price)
                except (TypeError, ValueError):
                    continue
    return out


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
        why = (f"AAA {reading['current']:.4f} as of {reading['as_of']}, {fc['days']}d to "
               f"{target.isoformat()}: mean {fc['mean']:.4f} sd {fc['sd']:.4f} "
               f"(phi {params['phi']} {how}, n {params['n']})")
        reason = ""
        if fc["days"] > MAX_DAYS:
            reason = f"{fc['days']}d to settle; buys only within {MAX_DAYS}d"
        elif not params.get("fitted") and fc["days"] > LEARN_MAX_DAYS:
            reason = (f"learning momentum ({params['n']}/{gm.MIN_HISTORY} days); "
                      f"buys only within {LEARN_MAX_DAYS}d of settle until fitted")
        for side in engine.sides(market):
            side["fair"] = p_yes if side["side"] == "yes" else 1.0 - p_yes
            side["label"] = f"Gas month end {target.strftime('%b %d')} > ${strike:.2f}"
            side["why"] = why
            if reason:
                side["log_only"] = True
                side["log_reason"] = reason
            out.append(side)
    return out


def model(cfg: dict, now: dt.datetime):
    reading = _aaa_reading(now)
    if reading is None:
        return [], "AAA page did not parse; waiting"
    params = gm.fit(merged_history())
    markets = engine.kalshi_open_markets(SERIES)
    if not markets:
        return [], f"no open markets: {SERIES}"
    quotes = quotes_for(markets, reading, params)
    return quotes, "" if quotes else f"no open {SERIES} strike priced"


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--reset" in argv:
        return engine.reset(SPEC, HERE)
    return engine.run_tower(SPEC, HERE, model)


if __name__ == "__main__":
    raise SystemExit(main())
