#!/usr/bin/env python3
"""Soccer & tennis lean: shadow paper tower for Kalshi soccer and tennis winners.

Uses Polymarket's moneyline mid for the same game as the fair price (free; no
Odds API credits) and buys a Kalshi side only when Kalshi lags it by more than
the locked sports floor of 0.06 after the fee (``match_model.py``). An edge
over 0.15 means the two venues disagree on something (a lineup, a retirement,
a bad match) and is logged, not bought.

Leagues: EPL, La Liga, Champions League, Bundesliga, Serie A, Ligue 1, MLS,
ATP and WTA. Paper only. Shadow only. $25 fixed ticket from a $500 sleeve,
max 6 open, one per event. Pre-game only: 10 minutes to 48 hours before start.
Exits: model flip at the bid, settle backstop.
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

import kalshi_shadow_tower as engine  # noqa: E402
import match_model as mm  # noqa: E402

SPEC = {"id": "soccer-tennis-lean", "name": "Soccer & tennis lean", "floor": 0.06, "max_open": 6, "max_edge": 0.15}
GAMMA = ("https://gamma-api.polymarket.com/events?series_id={sid}&active=true&closed=false"
         "&limit=200&end_date_min={lo}&end_date_max={hi}")
# Tennis events end days after the match starts (Polymarket closes them late).
END_WINDOW_DAYS = {"soccer": 2, "tennis": 10}


def gamma_url(sid: int, kind: str, now: dt.datetime) -> str:
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    hi = now + dt.timedelta(days=END_WINDOW_DAYS[kind])
    return GAMMA.format(sid=sid, lo=now.strftime(fmt), hi=hi.strftime(fmt))


def quotes_for(league: str, events: list[dict], markets: list[dict], now: dt.datetime):
    out = []
    pairs, unmatched = mm.pair(league, events, markets, now)
    for market, p_yes, why in pairs:
        who = market.get("yes_sub_title") or market["ticker"].rsplit("-", 1)[1]
        what = "draw" if str(who).lower() == "tie" else f"{who} to win"
        for side in engine.sides(market):
            side["fair"] = p_yes if side["side"] == "yes" else 1.0 - p_yes
            side["label"] = f"{league} {what}"
            side["why"] = why
            out.append(side)
    return out, unmatched


def model(cfg: dict, now: dt.datetime):
    quotes, notes = [], []
    for league, (sid, series, kind) in mm.LEAGUES.items():
        try:
            events = engine.public_json(gamma_url(sid, kind, now), timeout=30) or []
            if not any(mm.start_of(e) and mm.start_of(e) > now for e in events):
                continue                            # nothing scheduled; skip the Kalshi read
            got, unmatched = quotes_for(league, events, engine.kalshi_open_markets(series, limit=1000), now)
            quotes.extend(got)
            if unmatched:
                notes.append(f"{league} {unmatched} Polymarket-only")
        except Exception as exc:  # noqa: BLE001 - one league's read failing skips that league
            notes.append(f"{league} skipped ({type(exc).__name__})")
    note = "; ".join(notes)
    if not quotes and not note:
        note = "no matched pre-game market"
    return quotes, note


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--reset" in argv:
        return engine.reset(SPEC, HERE)
    return engine.run_tower(SPEC, HERE, model)


if __name__ == "__main__":
    raise SystemExit(main())
