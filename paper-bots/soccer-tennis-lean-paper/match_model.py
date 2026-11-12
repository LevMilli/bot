"""Match Polymarket soccer and tennis moneylines to Kalshi game markets. Pure logic, no network.

Polymarket's soccer and tennis books are deep, so its mid-price is a free
outside read on who wins (no Odds API credits). Kalshi lists the same games:

* Soccer: three markets per game, one per team plus "Tie"
  (``KXEPLGAME-26NOV22LFCMUN-LFC``, yes_sub_title "Liverpool"). Polymarket
  has three Yes/No markets: "<Team> FC", "Draw (...)" and the other team.
* Tennis: two markets per match, one per player (full names on both venues).

A game matches when the Kalshi event date is within a day of Polymarket's
start (time zones differ) and every Kalshi team or player name matches
exactly one Polymarket name. Names are compared after dropping accents,
punctuation and club words like "FC"; a few nicknames are mapped in
``ALIASES``. The three soccer mids are scaled to add up to 1.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import unicodedata
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
# league: (Polymarket series id, Kalshi series, kind)
LEAGUES = {
    "EPL": (10188, "KXEPLGAME", "soccer"),
    "La Liga": (10193, "KXLALIGAGAME", "soccer"),
    "UCL": (10204, "KXUCLGAME", "soccer"),
    "Bundesliga": (10194, "KXBUNDESLIGAGAME", "soccer"),
    "Serie A": (10203, "KXSERIEAGAME", "soccer"),
    "Ligue 1": (10195, "KXLIGUE1GAME", "soccer"),
    "MLS": (10189, "KXMLSGAME", "soccer"),
    "ATP": (10365, "KXATPMATCH", "tennis"),
    "WTA": (10366, "KXWTAMATCH", "tennis"),
}
CLUB_WORDS = {"fc", "afc", "cf", "sc", "ac", "as", "ss", "ssc", "us", "rc", "rcd", "cd", "ud", "sd", "ca", "fk", "sk", "09",
              "club", "de", "the", "calcio", "vfb", "vfl", "tsg", "sv", "fsv", "bv", "1", "04", "05",
              "1899", "1846", "1848", "1901", "1907", "1909", "hotspur", "and", "albion", "wanderers"}
ALIASES = {
    "man city": "manchester city", "man united": "manchester united", "man utd": "manchester united",
    "spurs": "tottenham", "wolves": "wolverhampton", "nottm forest": "nottingham forest",
    "psg": "paris saint germain", "paris sg": "paris saint germain", "inter": "internazionale",
    "inter milan": "internazionale", "atletico": "atletico madrid", "bayern": "bayern munchen",
    "bayern munich": "bayern munchen", "leverkusen": "bayer leverkusen", "gladbach": "borussia monchengladbach",
    "dortmund": "borussia dortmund", "athletic": "athletic bilbao", "athletic club": "athletic bilbao",
    "betis": "real betis", "sociedad": "real sociedad", "celta": "celta vigo", "napoli": "napoli",
    "roma": "roma", "lazio": "lazio", "milan": "milan", "marseille": "olympique marseille",
    "lyon": "olympique lyonnais", "olympique lyon": "olympique lyonnais",
    "brighton hove": "brighton", "west ham united": "west ham", "newcastle united": "newcastle",
    "leeds united": "leeds", "santander": "real racing", "deportivo la coruna": "deportivo a coruna",
    "eindhoven": "psv", "slavia prague": "slavia praha", "bodoe glimt": "bodo glimt",
    "m gladbach": "borussia monchengladbach", "stade brest": "stade brestois", "stade brest 29": "stade brestois",
    "saint louis": "st louis city", "los angeles f": "los angeles", "hull city": "hull", "ipswich town": "ipswich", "leicester city": "leicester",
}
MONTHS = {m: i for i, m in enumerate(
    ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"), 1)}
MAX_SPREAD = 0.03
MIN_LIQUIDITY = 5_000.0
MIN_LEAD_MIN = 10
MAX_LEAD_HOURS = 48


def norm(name: str) -> str:
    text = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"[^a-z0-9 ]+", " ", text.replace("&", " and "))
    text = " ".join(t for t in text.split() if t not in CLUB_WORDS)
    return ALIASES.get(text, text)


def same(a: str, b: str) -> bool:
    """Loose name match: equal, or every word of the shorter name starts a word of the longer."""
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    short, long_ = sorted((na.split(), nb.split()), key=len)
    if len(short) == len(long_) and short != long_:
        # same length: allow one-word prefixes like "monchengladbach" vs "m gladbach" only when 1 word
        return len(short) == 1 and (long_[0].startswith(short[0]) or short[0].startswith(long_[0])) \
            and min(len(short[0]), len(long_[0])) >= 4
    return all(any(w.startswith(s) and len(s) >= 3 for w in long_) for s in short)


def surname_match(a: str, b: str) -> bool:
    """Tennis: same last word, and the first initials agree when both have them."""
    wa, wb = norm(a).split(), norm(b).split()
    if not wa or not wb or wa[-1] != wb[-1]:
        return False
    return wa[0][0] == wb[0][0] if len(wa) > 1 and len(wb) > 1 else True


def start_of(event: dict):
    try:
        return dt.datetime.fromisoformat(str(event.get("startTime")).replace("Z", "+00:00"))
    except ValueError:
        return None


def kalshi_day(event_ticker: str):
    m = re.search(r"-(\d{2})([A-Z]{3})(\d{2})", event_ticker or "")
    if not m or m.group(2) not in MONTHS:
        return None
    try:
        return dt.date(2000 + int(m.group(1)), MONTHS[m.group(2)], int(m.group(3)))
    except ValueError:
        return None


def kalshi_games(markets: list[dict]) -> dict:
    """{event ticker: [markets]}."""
    out: dict = {}
    for m in markets or []:
        ev = str(m.get("event_ticker") or "")
        if ev:
            out.setdefault(ev, []).append(m)
    return out


def _mid(market: dict):
    try:
        bid, ask = float(market["bestBid"]), float(market["bestAsk"])
    except (KeyError, TypeError, ValueError):
        return None
    if not 0 < bid <= ask < 1:
        return None
    return (bid + ask) / 2, ask - bid, float(market.get("liquidityNum") or 0)


def poly_lines(kind: str, event: dict):
    """[(name, fair, spread, liquidity)] for the game's moneyline, or None if unusable."""
    lines = [m for m in event.get("markets") or [] if m.get("sportsMarketType") == "moneyline"]
    if kind == "soccer":
        if len(lines) != 3:
            return None
        rows = []
        for m in lines:
            got = _mid(m)
            if got is None:
                return None
            title = str(m.get("groupItemTitle") or "")
            rows.append(("Tie" if title.lower().startswith("draw") else title, *got))
        total = sum(r[1] for r in rows)
        if not 0.9 <= total <= 1.1 or sum(r[0] == "Tie" for r in rows) != 1:
            return None
        return [(n, p / total, s, liq) for n, p, s, liq in rows]
    if len(lines) != 1:
        return None
    try:
        outcomes = json.loads(lines[0].get("outcomes") or "[]")
    except ValueError:
        return None
    got = _mid(lines[0])
    if len(outcomes) != 2 or got is None:
        return None
    p, spread, liq = got
    return [(outcomes[0], p, spread, liq), (outcomes[1], 1.0 - p, spread, liq)]


def _assign(kind: str, kalshi: list[dict], lines: list):
    """{kalshi ticker: (fair, name)} when every Kalshi market maps to exactly one Polymarket line."""
    names = [n for n, *_ in lines]
    test = surname_match if kind == "tennis" else same
    out = {}
    used = set()
    for m in kalshi:
        label = str(m.get("yes_sub_title") or "")
        if kind == "soccer" and label.lower() in ("tie", "draw"):
            hits = [i for i, n in enumerate(names) if n == "Tie"]
        else:
            hits = [i for i, n in enumerate(names) if n != "Tie" and test(label, n)]
        if len(hits) != 1 or hits[0] in used:
            return None
        used.add(hits[0])
        out[m["ticker"]] = (lines[hits[0]][1], names[hits[0]])
    return out if len(used) == len(lines) else None


def pair(league: str, events: list[dict], kalshi_markets: list[dict], now: dt.datetime):
    """([(kalshi market, fair yes, why)], unmatched count) for pre-game matched markets."""
    kind = LEAGUES[league][2]
    games = kalshi_games(kalshi_markets)
    out, unmatched = [], 0
    for event in events or []:
        start = start_of(event)
        if start is None or not re.search(r"\d{4}-\d{2}-\d{2}$", str(event.get("slug") or "")):
            continue                                     # skip props like "-exact-score"
        lead = (start - now).total_seconds() / 60.0
        if lead < MIN_LEAD_MIN or lead > MAX_LEAD_HOURS * 60:
            continue
        lines = poly_lines(kind, event)
        if not lines:
            continue
        _name, _p, spread, liq = lines[0]
        if max(r[2] for r in lines) > MAX_SPREAD or min(r[3] for r in lines) < MIN_LIQUIDITY:
            continue
        found = None
        for ev, kalshi in games.items():
            day = kalshi_day(ev)
            if day is None or abs((day - start.astimezone(ET).date()).days) > 1:
                continue
            got = _assign(kind, kalshi, lines)
            if got:
                found = (kalshi, got)
                break
        if not found:
            unmatched += 1
            continue
        kalshi, got = found
        for m in kalshi:
            fair, name = got[m["ticker"]]
            why = (f"Polymarket {event['slug']} {name} {fair:.3f} (widest spread "
                   f"{max(r[2] for r in lines):.2f}, liquidity ${min(r[3] for r in lines):,.0f}), "
                   f"{lead / 60:.1f}h to start")
            out.append((m, fair, why))
    return out, unmatched
