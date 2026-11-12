"""Polymarket "Fed Decision in <month>?" vs Kalshi KXFEDDECISION.

Both venues list the same five outcomes per FOMC meeting (hike 50+, hike 25,
hold, cut 25, cut 50+). Polymarket's mid is the fair; the Kalshi YES or NO ask
is what the paper sleeve would pay. Public endpoints only, no keys.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DESK_ROOT = os.path.dirname(HERE)

KALSHI_URL = (
    "https://api.elections.kalshi.com/trade-api/v2/markets"
    "?series_ticker=KXFEDDECISION&status=open&limit=200"
)
GAMMA_URL = "https://gamma-api.polymarket.com/events?closed=false&tag_slug=fed&limit=100&offset={offset}"

MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}
MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}
# Kalshi market suffix -> outcome key.
KALSHI_OUTCOME = {"H26": "hike50", "H25": "hike25", "H0": "hold", "C25": "cut25", "C26": "cut50"}
LABEL = {
    "hike50": "Hike 50+", "hike25": "Hike 25", "hold": "Hold",
    "cut25": "Cut 25", "cut50": "Cut 50+",
}


def max_spread() -> float:
    try:
        return float(os.environ.get("FED_PM_MAX_SPREAD") or 0.04)
    except ValueError:
        return 0.04


def kalshi_meeting(event_ticker: str):
    """KXFEDDECISION-26DEC -> (2026, 12)."""
    m = re.search(r"-(\d{2})([A-Z]{3})$", str(event_ticker or ""))
    if not m or m.group(2) not in MONTHS:
        return None
    return (2000 + int(m.group(1)), MONTHS[m.group(2)])


def pm_outcome(title: str):
    """Polymarket groupItemTitle -> outcome key ("25 bps decrease" -> cut25)."""
    t = str(title or "").lower().strip()
    if "no change" in t:
        return "hold"
    m = re.match(r"(\d+)\+?\s*bps\s+(increase|decrease|hike|cut)", t)
    if not m:
        return None
    bps = int(m.group(1))
    up = m.group(2) in ("increase", "hike")
    if bps == 25:
        return "hike25" if up else "cut25"
    if bps >= 50:
        return "hike50" if up else "cut50"
    return None


def pm_meeting(event: dict, market: dict | None = None):
    """Read "after the December 2026 meeting" from the question; fall back to endDate."""
    text = " ".join(
        str(x or "") for x in ((market or {}).get("question"), event.get("title"), event.get("description"))
    )
    m = re.search(r"\b(" + "|".join(MONTH_NAMES) + r")\s+(20\d{2})\b", text, re.I)
    if m:
        return (int(m.group(2)), MONTH_NAMES[m.group(1).lower()])
    end = str(event.get("endDate") or "")
    month = re.search(r"\b(" + "|".join(MONTH_NAMES) + r")\b", str(event.get("title") or ""), re.I)
    if month and len(end) >= 7 and end[:4].isdigit():
        year = int(end[:4])
        mon = MONTH_NAMES[month.group(1).lower()]
        # A December meeting market can end in early January UTC.
        if mon == 12 and end[5:7] == "01":
            year -= 1
        return (year, mon)
    return None


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def pm_fairs(events: list[dict]) -> dict:
    """{(year, month, outcome): {fair, pm_bid, pm_ask, slug}} from Fed decision events."""
    out = {}
    for ev in events or []:
        slug = str(ev.get("slug") or "")
        if not slug.startswith("fed-decision-in-"):
            continue
        for mk in ev.get("markets") or []:
            if mk.get("closed") or mk.get("active") is False:
                continue
            key = pm_outcome(mk.get("groupItemTitle"))
            meeting = pm_meeting(ev, mk)
            if not key or not meeting:
                continue
            bid, ask = _f(mk.get("bestBid")), _f(mk.get("bestAsk"))
            if bid is None or ask is None or not (0 <= bid <= ask <= 1):
                continue
            if ask - bid > max_spread() + 1e-9:
                continue
            fair = (bid + ask) / 2.0
            if not (0.0 < fair < 1.0):
                continue
            out[(meeting[0], meeting[1], key)] = {
                "fair": round(fair, 4), "pm_bid": bid, "pm_ask": ask, "slug": slug,
            }
    return out


def pair_quotes(kalshi: list[dict], events: list[dict]) -> tuple[list[dict], int]:
    """YES and NO quote rows for every Kalshi outcome that Polymarket also prices."""
    fairs = pm_fairs(events)
    quotes, unmatched = [], 0
    for m in kalshi or []:
        ticker = str(m.get("ticker") or "")
        key = KALSHI_OUTCOME.get(ticker.rsplit("-", 1)[-1])
        meeting = kalshi_meeting(m.get("event_ticker"))
        if not key or not meeting:
            continue
        pm = fairs.get((meeting[0], meeting[1], key))
        if not pm:
            unmatched += 1
            continue
        name = f"{meeting[0]}-{meeting[1]:02d} {LABEL[key]}"
        for side, ask_field, fair in (
            ("yes", "yes_ask_dollars", pm["fair"]),
            ("no", "no_ask_dollars", round(1.0 - pm["fair"], 4)),
        ):
            ask = _f(m.get(ask_field))
            if ask is None or not (0.0 < ask < 1.0):
                continue
            quotes.append({
                "outcome": f"{name} {side.upper()}",
                "ticker": ticker,
                "side": side,
                "meeting": f"{meeting[0]}-{meeting[1]:02d}",
                "fair": fair,
                "ask": ask,
                "pm_bid": pm["pm_bid"],
                "pm_ask": pm["pm_ask"],
                "pm_slug": pm["slug"],
                "source": "polymarket",
            })
    return quotes, unmatched


def _read(url: str):
    if DESK_ROOT not in sys.path:
        sys.path.insert(0, DESK_ROOT)
    import public_http
    return json.loads(public_http.read(url, timeout=15).decode("utf-8"))


def kalshi_open() -> list[dict]:
    return list((_read(KALSHI_URL) or {}).get("markets") or [])


def polymarket_events() -> list[dict]:
    out = []
    for page in range(5):
        batch = _read(GAMMA_URL.format(offset=page * 100)) or []
        if not isinstance(batch, list):
            break
        out.extend(batch)
        if len(batch) < 100:
            break
    return out


def live_quotes(kalshi=None, polymarket=None) -> tuple[list[dict], dict]:
    markets = (kalshi or kalshi_open)()
    events = (polymarket or polymarket_events)()
    quotes, unmatched = pair_quotes(markets, events)
    return quotes, {
        "kalshi_n": len(markets),
        "unmatched": unmatched,
        "meetings": sorted({q["meeting"] for q in quotes}),
        "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }
