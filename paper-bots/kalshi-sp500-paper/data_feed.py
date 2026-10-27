"""
data_feed.py - READ-ONLY access to Kalshi's PUBLIC market data.

Plain-English summary
---------------------
Kalshi publishes market data (prices, order books, price history) on a public
web API that anyone can read without an account. This file is the ONLY place
the bot talks to Kalshi, and it only ever does HTTP GET (read) requests.

  * No API keys, no login, no wallet.
  * There is deliberately NO function here that can place, change or cancel
    an order. The bot cannot trade real money even by accident.

Key ideas a beginner needs:
  * A "series" is a family of markets, e.g. KXINXU = "S&P 500 above/below".
  * An "event" is one settlement time, e.g. KXINXU-26OCT27H1600 =
    "S&P 500 at 4 PM ET (3 PM CT) on Oct 27, 2026".
  * A "market" is one yes/no contract inside an event, e.g.
    "...-T7674.9999" = "Will the S&P be at/above 7,675?"
  * Prices are in dollars (0.85 = 85 cents). A winning contract pays $1.00.
  * The NO side's ask price = 1 - (YES side's bid). That is how Kalshi's
    single order book works: buying NO at 15c is the same as selling YES at 85c.
  * Kalshi moved older settled markets (settled before the "historical cutoff",
    Aug 27 2026 at time of writing) to separate /historical/... endpoints.
    The helpers below try the normal endpoint first and fall back to the
    historical one automatically.
"""
import json
import time
import urllib.request
import urllib.error
import datetime as dt
from zoneinfo import ZoneInfo

CT = ZoneInfo("America/Chicago")
_CONFIG = json.load(open(__file__.replace("data_feed.py", "config.json")))
BASE = _CONFIG["api_base"]
PAUSE = _CONFIG.get("request_pause_seconds", 0.05)


def get_json(path, retries=5):
    """GET one public API path (e.g. '/markets?...') and return parsed JSON.

    Retries with a growing wait if Kalshi is busy (HTTP 429) or the network
    hiccups. Returns {} (empty) on a 404 "not found" so callers can fall back.
    """
    url = BASE + path
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "paper-bot/1.0 (read-only)"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                time.sleep(PAUSE)            # be polite to the public API
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {}
            last_err = e
            time.sleep(1.5 * (attempt + 1))  # 429 / 5xx: wait and retry
        except Exception as e:               # timeouts, connection resets
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Kalshi API read failed after {retries} tries: {url} ({last_err})")


def dollars(x):
    """Kalshi returns prices as strings like '0.8500'. Convert to float (None if blank)."""
    if x in (None, ""):
        return None
    return float(x)


# ----------------------------------------------------------------- events
def list_events(series_ticker):
    """All events (every settlement time) ever listed for a series, paginated."""
    events, cursor = [], ""
    while True:
        d = get_json(f"/events?series_ticker={series_ticker}&limit=200" + (f"&cursor={cursor}" if cursor else ""))
        events += d.get("events", [])
        cursor = d.get("cursor")
        if not cursor:
            return events


def event_settle_time_ct(event):
    """When an event settles, in Central Time (from its 'strike_date')."""
    return dt.datetime.fromisoformat(event["strike_date"].replace("Z", "+00:00")).astimezone(CT)


def find_event_for(series_ticker, day, settle_hhmm_ct="15:00", events=None):
    """Find the event ticker that settles on `day` at the given CT time, or None.

    We match on the settle time instead of building the ticker by hand, because
    Kalshi's ticker format changed in 2025 (KXINXU-24DEC03 -> KXINXU-25JUN10H1600)
    and on Nov 20 2025 there was a duplicate '...H1600B' event.
    """
    events = events if events is not None else list_events(series_ticker)
    hh, mm = map(int, settle_hhmm_ct.split(":"))
    hits = [e["event_ticker"] for e in events
            if e.get("strike_date")
            and event_settle_time_ct(e).date() == day
            and (event_settle_time_ct(e).hour, event_settle_time_ct(e).minute) == (hh, mm)]
    hits.sort(key=lambda t: (t.endswith("B"), t))   # prefer the normal ticker over a '...B' duplicate
    return hits[0] if hits else None


# ----------------------------------------------------------------- markets
def get_event_markets(event_ticker):
    """All markets (contracts) in one event. Tries live endpoint, then /historical."""
    for base in ("/markets", "/historical/markets"):
        ms, cursor = [], ""
        while True:
            d = get_json(f"{base}?event_ticker={event_ticker}&limit=1000" + (f"&cursor={cursor}" if cursor else ""))
            ms += d.get("markets", [])
            cursor = d.get("cursor")
            if not cursor:
                break
        if ms:
            return ms
    return []


def get_market(ticker):
    """One market's current snapshot (live endpoint, then historical)."""
    for base in ("/markets/", "/historical/markets/"):
        d = get_json(base + ticker)
        if d.get("market"):
            return d["market"]
    return None


def get_orderbook(ticker, depth=10):
    """Current resting orders for one market.

    Kalshi's book lists BIDS only, for both sides:
      'yes_dollars' = people wanting to BUY yes at each price
      'no_dollars'  = people wanting to BUY no at each price
    The best YES ask is therefore 1 - (best NO bid), and vice versa.
    """
    d = get_json(f"/markets/{ticker}/orderbook?depth={depth}")
    ob = d.get("orderbook_fp") or d.get("orderbook") or {}
    yes = [(float(p), float(q)) for p, q in (ob.get("yes_dollars") or [])]
    no = [(float(p), float(q)) for p, q in (ob.get("no_dollars") or [])]
    best_yes_bid = max(yes)[0] if yes else None
    best_no_bid = max(no)[0] if no else None
    return {
        "yes_bids": sorted(yes, reverse=True),
        "no_bids": sorted(no, reverse=True),
        "yes_bid": best_yes_bid,
        "no_bid": best_no_bid,
        "yes_ask": round(1 - best_no_bid, 4) if best_no_bid is not None else None,
        "no_ask": round(1 - best_yes_bid, 4) if best_yes_bid is not None else None,
    }


# ----------------------------------------------------------------- price history
def _norm_candle(c):
    """Live and historical candles use different field names; return one format."""
    def side(name):
        s = c.get(name) or {}
        return dollars(s.get("close_dollars", s.get("close")))
    return {"end_ts": c["end_period_ts"], "yes_bid": side("yes_bid"), "yes_ask": side("yes_ask")}


def get_candles(series_ticker, ticker, start_ts, end_ts, period_minutes=1):
    """Bid/ask history (one row per period in which something changed).

    Each row's yes_bid / yes_ask are the CLOSING quotes of that period, i.e.
    the quote standing at `end_ts`. Minutes where nothing changed have no row,
    so the standing quote at time T is the last row with end_ts <= T.
    """
    d = get_json(f"/series/{series_ticker}/markets/{ticker}/candlesticks"
                 f"?start_ts={start_ts}&end_ts={end_ts}&period_interval={period_minutes}")
    if not d.get("candlesticks"):
        d = get_json(f"/historical/markets/{ticker}/candlesticks"
                     f"?start_ts={start_ts}&end_ts={end_ts}&period_interval={period_minutes}")
    return [_norm_candle(c) for c in d.get("candlesticks", [])]


def get_candles_batch(tickers, start_ts, end_ts, period_minutes=1):
    """Same as get_candles but up to 100 LIVE (post-cutoff) markets in one call.
    Returns {ticker: [candles]}; historical markets are not supported here."""
    out = {}
    for i in range(0, len(tickers), 100):
        chunk = tickers[i:i + 100]
        d = get_json(f"/markets/candlesticks?market_tickers={','.join(chunk)}"
                     f"&start_ts={start_ts}&end_ts={end_ts}&period_interval={period_minutes}")
        for m in d.get("markets", []):
            out[m.get("market_ticker") or m.get("ticker")] = [_norm_candle(c) for c in m.get("candlesticks", [])]
    return out


def quote_at(candles, t_ts):
    """Standing (yes_bid, yes_ask) at unix time t_ts: last candle with end_ts <= t_ts.
    Never looks at anything after t_ts (no lookahead)."""
    best = None
    for c in candles:
        if c["end_ts"] <= t_ts and (best is None or c["end_ts"] > best["end_ts"]):
            best = c
    return (best["yes_bid"], best["yes_ask"], best["end_ts"]) if best else (None, None, None)


def historical_cutoff():
    """Date before which settled markets live under /historical endpoints."""
    return get_json("/historical/cutoff")
