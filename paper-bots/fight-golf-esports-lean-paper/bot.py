#!/usr/bin/env python3
"""UFC, golf & esports lean: shadow paper tower for Kalshi fights, golf winners and esports matches.

Idea B20. Polymarket's mid for the same fight, match or golfer is the fair
price (``fge_model.py``), and a Kalshi side is bought only when Kalshi lags it
by more than the locked sports floor of 0.06 after the fee. An edge over 0.15
is logged, not bought (usually a bad match or late news).

Leagues: UFC, League of Legends, Counter-Strike 2, Valorant, Dota 2, and the
PGA Tour winner market. The parked esports-match shell is left as it is.

Paper only. Shadow only. $25 fixed ticket from a $500 sleeve, max 6 open, one
per event. Exits: model flip at the bid, settle backstop. Cross-venue gaps in
these markets are usually tiny, so expect few trades.
"""
from __future__ import annotations

import datetime as dt
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DESK_ROOT = os.path.dirname(HERE)
for path in (DESK_ROOT, HERE, os.path.join(DESK_ROOT, "soccer-tennis-lean-paper")):
    if path not in sys.path:
        sys.path.insert(0, path)

import kalshi_shadow_tower as engine  # noqa: E402
import fge_model as fm  # noqa: E402

SPEC = {"id": "fight-golf-esports-lean", "name": "UFC, golf & esports lean", "floor": 0.06,
        "max_open": 6, "max_edge": 0.15}
GAMMA = ("https://gamma-api.polymarket.com/events?series_id={sid}&active=true&closed=false"
         "&limit=200&end_date_min={lo}&end_date_max={hi}")


def gamma_url(sid: int, kind: str, now: dt.datetime) -> str:
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    hi = now + dt.timedelta(days=fm.END_WINDOW_DAYS[kind])
    return GAMMA.format(sid=sid, lo=now.strftime(fmt), hi=hi.strftime(fmt))


def quotes_for(league: str, events: list[dict], markets: list[dict], now: dt.datetime):
    kind = fm.LEAGUES[league][2]
    if kind == "golf":
        pairs, unmatched = fm.pair_golf(events, markets, now)
    else:
        pairs, unmatched = fm.pair_two_way(league, events, markets, now)
    out = []
    for market, p_yes, why in pairs:
        who = market.get("yes_sub_title") or market["ticker"].rsplit("-", 1)[1]
        for side in engine.sides(market):
            side["fair"] = p_yes if side["side"] == "yes" else 1.0 - p_yes
            side["label"] = f"{league} {who} {'to win' if side['side'] == 'yes' else 'not to win'}"
            side["why"] = why
            out.append(side)
    return out, unmatched


def model(cfg: dict, now: dt.datetime):
    quotes, notes = [], []
    for league, (sid, series, kind) in fm.LEAGUES.items():
        try:
            events = engine.public_json(gamma_url(sid, kind, now), timeout=30) or []
            if not events:
                continue                            # nothing listed; skip the Kalshi read
            got, unmatched = quotes_for(league, events, engine.kalshi_open_markets(series, limit=1000), now)
            quotes.extend(got)
            if unmatched:
                what = "golfers without a two-sided Polymarket price" if kind == "golf" else "Polymarket-only"
                notes.append(f"{league} {unmatched} {what}")
        except Exception as exc:  # noqa: BLE001 - one league's read failing skips that league
            notes.append(f"{league} skipped ({type(exc).__name__})")
    note = "; ".join(notes)
    if not quotes and not note:
        note = "no matched market"
    return quotes, note


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--reset" in argv:
        return engine.reset(SPEC, HERE)
    return engine.run_tower(SPEC, HERE, model)


if __name__ == "__main__":
    raise SystemExit(main())
