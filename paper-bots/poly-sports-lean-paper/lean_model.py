"""Match Polymarket game moneylines to Kalshi game markets. Pure logic, no network.

Polymarket's sports books are deep and tight on the big US leagues, so its
mid-price is a good outside read on who wins. A game matches when the Eastern
date of the Polymarket start time plus the two team codes from its slug
(``nba-tor-phi-2026-11-12``) equal the Kalshi event code (``26NOV12TORPHI``).
A few codes differ between the two venues and are mapped in ``ALIASES``.
Polymarket's first outcome is the first team in the slug.
"""
from __future__ import annotations

import datetime as dt
import json
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
LEAGUES = {
    "NBA": (10345, "KXNBAGAME"),
    "NFL": (12185, "KXNFLGAME"),
    "NHL": (10346, "KXNHLGAME"),
}
ALIASES = {
    "NFL": {"JAX": "JAC", "LA": "LAR"},
    "NHL": {"MON": "MTL", "LAK": "LA", "LAS": "VGK", "UTAH": "UTA", "CAL": "CGY"},
}
MAX_SPREAD = 0.03
MIN_LIQUIDITY = 10_000.0
MIN_LEAD_MIN = 5
MAX_LEAD_HOURS = 48


def _start(event: dict):
    try:
        return dt.datetime.fromisoformat(str(event.get("startTime")).replace("Z", "+00:00"))
    except ValueError:
        return None


def event_key(league: str, event: dict):
    """(Kalshi event code, [team codes]) for a Polymarket game event, or None."""
    parts = str(event.get("slug") or "").split("-")
    start = _start(event)
    if len(parts) < 6 or start is None or not all(p.isdigit() for p in parts[-3:]):
        return None
    codes = [ALIASES.get(league, {}).get(c.upper(), c.upper()) for c in parts[1:-3]]
    if len(codes) != 2:
        return None
    return start.astimezone(ET).strftime("%y%b%d").upper() + "".join(codes), codes


def moneyline(event: dict):
    """(first team's mid, spread, liquidity) from the event's moneyline market."""
    for market in event.get("markets") or []:
        if market.get("sportsMarketType") != "moneyline":
            continue
        try:
            outcomes = json.loads(market.get("outcomes") or "[]")
            bid, ask = float(market["bestBid"]), float(market["bestAsk"])
        except (TypeError, ValueError, KeyError):
            return None
        if len(outcomes) != 2 or not 0 < bid <= ask < 1:
            return None
        return round((bid + ask) / 2, 4), round(ask - bid, 4), float(market.get("liquidityNum") or 0)
    return None


def kalshi_by_event(markets: list[dict]) -> dict:
    """{event code: {team code: market}} for two-team Kalshi games."""
    out: dict = {}
    for m in markets or []:
        ev, ticker = str(m.get("event_ticker") or ""), str(m.get("ticker") or "")
        if "-" not in ev or "-" not in ticker:
            continue
        out.setdefault(ev.split("-", 1)[1], {})[ticker.rsplit("-", 1)[1]] = m
    return {k: v for k, v in out.items() if len(v) == 2}


def pair(league: str, events: list[dict], kalshi_markets: list[dict], now: dt.datetime):
    """[(kalshi market, fair yes, why)] for every matched pre-game team market."""
    games = kalshi_by_event(kalshi_markets)
    out, unmatched = [], 0
    for event in events or []:
        start = _start(event)
        key = event_key(league, event)
        if start is None or key is None:
            continue
        lead = (start - now).total_seconds() / 60.0
        if lead < MIN_LEAD_MIN or lead > MAX_LEAD_HOURS * 60:
            continue
        code, codes = key
        game = games.get(code)
        if not game or set(game) != set(codes):
            unmatched += 1
            continue
        line = moneyline(event)
        if line is None:
            continue
        mid, spread, liq = line
        if spread > MAX_SPREAD or liq < MIN_LIQUIDITY:
            continue
        for team, p in ((codes[0], mid), (codes[1], 1.0 - mid)):
            why = (f"Polymarket {event['slug']} {team} {p:.3f} (spread {spread:.2f}, "
                   f"liquidity ${liq:,.0f}), {lead / 60:.1f}h to start")
            out.append((game[team], p, why))
    return out, unmatched
