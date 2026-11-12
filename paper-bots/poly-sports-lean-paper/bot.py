#!/usr/bin/env python3
"""Poly sports lean: shadow paper tower for Kalshi NBA / NFL / NHL game winners.

Uses Polymarket's moneyline mid as the fair price for the same game
(``lean_model.py``) and buys a Kalshi side only when the edge after the Kalshi
fee clears the locked sports floor of 0.06. In practice that means Kalshi has
not caught up with a move Polymarket already made.

Paper only. Shadow only. $25 fixed ticket from a $500 sleeve, max 4 open, one
per game. Pre-game only (5 minutes to 48 hours before start), Polymarket
spread at most 3¢ and liquidity at least $10k.
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
import lean_model as lean  # noqa: E402

SPEC = {"id": "poly-sports-lean", "name": "Poly sports lean", "floor": 0.06, "max_open": 4, "max_edge": 0.15}
GAMMA = "https://gamma-api.polymarket.com/events?series_id={sid}&active=true&closed=false&limit=500"


def quotes_for(league: str, events: list[dict], markets: list[dict], now: dt.datetime):
    out = []
    pairs, unmatched = lean.pair(league, events, markets, now)
    for market, p_yes, why in pairs:
        team = market.get("yes_sub_title") or market["ticker"].rsplit("-", 1)[1]
        for side in engine.sides(market):
            side["fair"] = p_yes if side["side"] == "yes" else 1.0 - p_yes
            side["label"] = f"{league} {team} to win"
            side["why"] = why
            out.append(side)
    return out, unmatched


def model(cfg: dict, now: dt.datetime):
    quotes, notes = [], []
    for league, (sid, series) in lean.LEAGUES.items():
        try:
            events = engine.public_json(GAMMA.format(sid=sid)) or []
            got, unmatched = quotes_for(league, events, engine.kalshi_open_markets(series, limit=1000), now)
            quotes.extend(got)
            if unmatched:
                notes.append(f"{league} {unmatched} unmatched")
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
