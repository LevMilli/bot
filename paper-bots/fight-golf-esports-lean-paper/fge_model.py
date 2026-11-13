"""Match Polymarket UFC, golf and esports prices to Kalshi winner markets. Pure logic, no network.

Idea B20. The same lean idea as the soccer & tennis tower: Polymarket's mid is
a free outside read on who wins, and Kalshi lists the same fights and matches.

* UFC fights and esports matches (League of Legends, Counter-Strike 2,
  Valorant, Dota 2): two Kalshi markets per event, one per fighter or team.
  Polymarket has one two-outcome "moneyline" market. A pair is used only when
  the Kalshi event date is within a day of Polymarket's start and both names
  match exactly one Polymarket name. Pre-game only: 10 minutes to 48 hours.
* Golf tournament winner: Kalshi KXPGATOUR has one market per golfer; the
  Polymarket "<tournament> Winner" event has one Yes/No market per golfer. The
  tournament names must match, and each golfer must match exactly one name.
  Golf may run while the tournament is on (it lasts four days).

Name rules come from the soccer & tennis matcher (``match_model``), used read-only.
"""
from __future__ import annotations

import datetime as dt
import json
import re

import match_model as mm

# league: (Polymarket series id, Kalshi series, kind)
LEAGUES = {
    "UFC": (38, "KXUFCFIGHT", "fight"),
    "LoL": (10311, "KXLOLGAME", "esports"),
    "CS2": (10310, "KXCS2GAME", "esports"),
    "Valorant": (10369, "KXVALORANTGAME", "esports"),
    "Dota 2": (10309, "KXDOTA2GAME", "esports"),
    "Golf": (10976, "KXPGATOUR", "golf"),
}
MAX_SPREAD = 0.03
MIN_LIQUIDITY = 5_000.0
MIN_LEAD_MIN = 10
MAX_LEAD_HOURS = 48
END_WINDOW_DAYS = {"fight": 3, "esports": 3, "golf": 6}


def _mid(market: dict):
    try:
        bid, ask = float(market["bestBid"]), float(market["bestAsk"])
    except (KeyError, TypeError, ValueError):
        return None
    if not 0 < bid <= ask < 1:
        return None
    return round((bid + ask) / 2, 4), round(ask - bid, 4), float(market.get("liquidityNum") or 0)


def two_way_line(event: dict):
    """[(name, chance, spread, liquidity)] x2 from the match-winner moneyline, or None."""
    lines = [m for m in event.get("markets") or [] if m.get("sportsMarketType") == "moneyline"]
    if len(lines) != 1:
        return None
    try:
        names = json.loads(lines[0].get("outcomes") or "[]")
    except ValueError:
        return None
    got = _mid(lines[0])
    if len(names) != 2 or got is None:
        return None
    p, wide, liq = got
    return [(names[0], p, wide, liq), (names[1], round(1.0 - p, 4), wide, liq)]


def name_test(kind: str):
    return mm.surname_match if kind in ("fight", "golf") else mm.same


def assign(kind: str, kalshi: list[dict], names: list[str]):
    """{kalshi ticker: index into names} when every Kalshi market maps to exactly one name."""
    test = name_test(kind)
    out, used = {}, set()
    for m in kalshi:
        label = str(m.get("yes_sub_title") or "")
        hits = [i for i, n in enumerate(names) if test(label, n)]
        if len(hits) != 1 or hits[0] in used:
            return None
        used.add(hits[0])
        out[m["ticker"]] = hits[0]
    return out


def pair_two_way(league: str, events: list[dict], kalshi_markets: list[dict], now: dt.datetime):
    """([(kalshi market, fair yes, why)], unmatched count) for pre-game fights and matches."""
    kind = LEAGUES[league][2]
    games = mm.kalshi_games(kalshi_markets)
    out, unmatched = [], 0
    for event in events or []:
        start = mm.start_of(event)
        if start is None:
            continue
        lead = (start - now).total_seconds() / 60.0
        if lead < MIN_LEAD_MIN or lead > MAX_LEAD_HOURS * 60:
            continue
        lines = two_way_line(event)
        if not lines:
            continue
        if lines[0][2] > MAX_SPREAD or lines[0][3] < MIN_LIQUIDITY:
            continue
        names = [n for n, *_ in lines]
        found = None
        for ev, kalshi in games.items():
            day = mm.kalshi_day(ev)
            if day is None or len(kalshi) != 2 or abs((day - start.astimezone(mm.ET).date()).days) > 1:
                continue
            got = assign(kind, kalshi, names)
            if got:
                found = (kalshi, got)
                break
        if not found:
            unmatched += 1
            continue
        kalshi, got = found
        for m in kalshi:
            name, fair, wide, liq = lines[got[m["ticker"]]]
            why = (f"Polymarket {event.get('slug')} {name} {fair:.3f} (spread {wide:.2f}, "
                   f"liquidity ${liq:,.0f}), {lead / 60:.1f}h to start")
            out.append((m, fair, why))
    return out, unmatched


def golf_name(text: str) -> str:
    """'PGA Tour: Austin Championship Winner' -> 'austin championship'."""
    t = re.sub(r"^\s*pga tour\s*:\s*", "", str(text or ""), flags=re.I)
    t = re.sub(r"\s+winner\s*$", "", t, flags=re.I)
    return mm.norm(t)


def kalshi_golf_name(market: dict) -> str:
    title = str(market.get("title") or "")
    return mm.norm(title.split(":", 1)[0]) if ":" in title else ""


def pair_golf(events: list[dict], kalshi_markets: list[dict], now: dt.datetime):
    """([(kalshi market, fair yes, why)], unmatched golfer count) for tournament winners."""
    winners = [e for e in events or [] if str(e.get("slug") or "").endswith("-winner")]
    out, unmatched = [], 0
    for ev, kalshi in mm.kalshi_games(kalshi_markets).items():
        k_name = kalshi_golf_name(kalshi[0])
        hits = [e for e in winners if golf_name(e.get("title")) and golf_name(e.get("title")) in k_name]
        if len(hits) != 1:
            continue
        event = hits[0]
        rows = []
        for pm in event.get("markets") or []:
            if pm.get("closed") or pm.get("active") is False:
                continue
            got = _mid(pm)
            if got is not None:
                rows.append((str(pm.get("groupItemTitle") or ""), *got))
        names = [r[0] for r in rows]
        for m in kalshi:
            label = str(m.get("yes_sub_title") or "")
            idx = [i for i, n in enumerate(names) if mm.surname_match(label, n)]
            if len(idx) != 1:
                unmatched += 1
                continue
            name, fair, wide, liq = rows[idx[0]]
            if wide > MAX_SPREAD or liq < MIN_LIQUIDITY:
                continue
            why = (f"Polymarket {event.get('slug')} {name} {fair:.3f} (spread {wide:.2f}, "
                   f"liquidity ${liq:,.0f})")
            out.append((m, fair, why))
    return out, unmatched
