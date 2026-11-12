"""Live sharp-book odds for Sports Sharp Lag. Paper only, read-only.

Pulls pre-game moneylines from The Odds API (Pinnacle by default, the sharpest
public book), removes the bookmaker's cut, and pairs each game with its Kalshi
game-winner market. The result is the sharp fair for each team next to the
live Kalshi ask, which is what the tower compares.

Key: set ``ODDS_API_KEY`` (Railway variable). No key, no calls.

Credits: each league fetched is 1 credit. A league is only fetched when Kalshi
has open games for it in the next ``ODDS_LOOKAHEAD_HOURS`` (36). Odds are
cached and refreshed no faster than ``ODDS_REFRESH_MINUTES`` (30), and slower
when needed so the credits left last until the end of the month. Below
``ODDS_API_MIN_LEFT`` (25) credits it stops calling and says so.

Kalshi asks are read fresh on every check (free).
"""
from __future__ import annotations

import calendar
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
DESK_ROOT = os.path.dirname(HERE)
if DESK_ROOT not in sys.path:
    sys.path.insert(0, DESK_ROOT)

import public_http  # noqa: E402

ODDS_API = "https://api.the-odds-api.com/v4/sports/{sport}/odds"
KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
ET = ZoneInfo("America/New_York")
CACHE = "odds_cache.json"

LEAGUES = {
    "NFL": ("americanfootball_nfl", "KXNFLGAME"),
    "NCAAF": ("americanfootball_ncaaf", "KXNCAAFGAME"),
    "NBA": ("basketball_nba", "KXNBAGAME"),
    "WNBA": ("basketball_wnba", "KXWNBAGAME"),
    "MLB": ("baseball_mlb", "KXMLBGAME"),
    "NHL": ("icehockey_nhl", "KXNHLGAME"),
}


def _env_num(name, default):
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return float(default)


def api_key():
    return (os.environ.get("ODDS_API_KEY") or "").strip()


# ------------------------------------------------------------------ pure helpers
def norm(name):
    s = str(name or "").lower().replace(".", "").replace("&", "and").strip()
    if s.endswith(" st"):
        s = s[:-3] + " state"
    return " ".join(s.split())


def team_fits(kalshi_name, full_name):
    """Kalshi says 'Golden State' / 'Kent St.' / 'Los Angeles L'; the book says
    'Golden State Warriors'. A fit is an exact name or a word-boundary prefix."""
    k, f = norm(kalshi_name), norm(full_name)
    if not k or not f:
        return False
    if k == f:
        return True
    if not f.startswith(k):
        return False
    # 'los angeles c' is a one-letter hint for the next word; otherwise the
    # Kalshi name must end on a word boundary ('texas' must not fit 'texas tech').
    rest = f[len(k):]
    if len(k.split()[-1]) == 1:
        return True
    return rest.startswith(" ") and not _is_school_suffix(rest.split()[0])


_SUFFIX = {"tech", "state", "st", "am", "aandm", "christian", "southern", "international"}


def _is_school_suffix(word):
    return word in _SUFFIX


def devig(price_a, price_b):
    """Decimal odds pair -> (p_a, p_b) with the bookmaker's cut removed."""
    try:
        ia, ib = 1.0 / float(price_a), 1.0 / float(price_b)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    total = ia + ib
    if total <= 0:
        return None
    return ia / total, ib / total


def book_fairs(event, bookmaker="pinnacle"):
    """{team name: fair} for one Odds API event from one bookmaker, or None."""
    for book in event.get("bookmakers") or []:
        if str(book.get("key") or "") != bookmaker:
            continue
        for market in book.get("markets") or []:
            if market.get("key") != "h2h":
                continue
            outcomes = [o for o in market.get("outcomes") or [] if o.get("name") != "Draw"]
            if len(outcomes) != 2 or len(market.get("outcomes") or []) != 2:
                return None  # a three-way line is not a two-team winner
            pair = devig(outcomes[0].get("price"), outcomes[1].get("price"))
            if not pair:
                return None
            return {
                outcomes[0]["name"]: round(pair[0], 4),
                outcomes[1]["name"]: round(pair[1], 4),
                "_updated": market.get("last_update") or book.get("last_update"),
            }
    return None


def _ask(market):
    for key in ("yes_ask_dollars", "yes_ask"):
        value = market.get(key)
        if value in (None, ""):
            continue
        try:
            px = float(value)
        except (TypeError, ValueError):
            continue
        if px > 1.0:
            px /= 100.0
        if 0.0 < px < 1.0:
            return round(px, 4)
    return None


def kalshi_events(markets):
    """Group Kalshi game markets into {event_ticker: [m1, m2]}."""
    events = {}
    for m in markets or []:
        if isinstance(m, dict) and m.get("event_ticker") and m.get("ticker"):
            events.setdefault(m["event_ticker"], []).append(m)
    return {ev: ms for ev, ms in events.items() if len(ms) == 2}


def _event_day(event_ticker):
    part = event_ticker.split("-", 1)[1] if "-" in event_ticker else ""
    return part[:7].upper()


def pair_quotes(league, odds_events, kalshi_markets, now, bookmaker="pinnacle"):
    """Sharp fair next to the Kalshi ask for each team of each matched game.

    Pre-game only (a cached line is stale once a game starts). A game is used
    only when exactly one Kalshi event fits both team names on the same day.
    """
    out, unmatched = [], 0
    events = kalshi_events(kalshi_markets)
    for ev in odds_events or []:
        try:
            start = dt.datetime.fromisoformat(str(ev["commence_time"]).replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        if start <= now:
            continue
        fairs = book_fairs(ev, bookmaker)
        if not fairs:
            continue
        home, away = ev.get("home_team"), ev.get("away_team")
        if home not in fairs or away not in fairs:
            continue
        day = start.astimezone(ET).strftime("%y%b%d").upper()
        hits = []
        for ticker, ms in events.items():
            if _event_day(ticker) != day:
                continue
            h = [m for m in ms if team_fits(m.get("yes_sub_title"), home)]
            a = [m for m in ms if team_fits(m.get("yes_sub_title"), away)]
            if len(h) == 1 and len(a) == 1 and h[0] is not a[0]:
                hits.append((h[0], a[0]))
        if len(hits) != 1:
            unmatched += 1
            continue
        hm, am = hits[0]
        game = f"{away} @ {home}"
        for side, team, market in (("home", home, hm), ("away", away, am)):
            ask = _ask(market)
            if ask is None:
                continue
            out.append({
                "game": f"{game} {side.upper()}",
                "team": team,
                "side": side,
                "league": league,
                "ticker": market["ticker"],
                "sharp_fair": fairs[team],
                "ask": ask,
                "source": bookmaker,
                "line_updated": fairs.get("_updated"),
                "commence": ev.get("commence_time"),
            })
    return out, unmatched


def refresh_minutes(remaining, leagues, now):
    """How often odds may refresh so the credits left last the month."""
    floor = max(5.0, _env_num("ODDS_REFRESH_MINUTES", 30))
    if remaining is None or leagues <= 0:
        return floor
    last_day = calendar.monthrange(now.year, now.month)[1]
    end = now.replace(day=last_day, hour=23, minute=59, second=59)
    minutes_left = max(60.0, (end - now).total_seconds() / 60.0)
    usable = max(1.0, float(remaining) - _env_num("ODDS_API_MIN_LEFT", 25))
    return max(floor, minutes_left * leagues / usable)


# ------------------------------------------------------------------ network
def _kalshi_open(series):
    out, cursor = [], ""
    for _page in range(10):
        url = f"{KALSHI}/markets?series_ticker={series}&status=open&limit=1000"
        if cursor:
            url += "&cursor=" + urllib.parse.quote(cursor)
        data = json.loads(public_http.read(url, timeout=10).decode("utf-8"))
        out.extend(data.get("markets") or [])
        cursor = str(data.get("cursor") or "")
        if not cursor or not data.get("markets"):
            break
    return out


def _odds_fetch(sport, key, bookmaker):
    query = urllib.parse.urlencode({
        "apiKey": key, "regions": "eu", "markets": "h2h",
        "oddsFormat": "decimal", "bookmakers": bookmaker,
    })
    req = urllib.request.Request(ODDS_API.format(sport=sport) + "?" + query,
                                 headers={"User-Agent": "paper-bots/1.0 (paper-only read)"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        body = json.loads(resp.read().decode("utf-8"))
        remaining = resp.headers.get("x-requests-remaining")
    try:
        remaining = float(remaining) if remaining is not None else None
    except ValueError:
        remaining = None
    return (body if isinstance(body, list) else []), remaining


def _soon(markets, now, hours):
    limit = now + dt.timedelta(hours=hours)
    for m in markets:
        stamp = m.get("expected_expiration_time") or m.get("close_time")
        try:
            when = dt.datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
        except ValueError:
            continue
        # Game-winner markets expire a few hours after the game starts.
        if now < when <= limit + dt.timedelta(hours=6):
            return True
    return False


def _read(path):
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
    os.replace(tmp, path)


def live_quotes(tower, now=None, *, kalshi=None, odds=None):
    """(quotes, status) for this check. ``kalshi`` / ``odds`` are test seams."""
    now = now or dt.datetime.now(dt.timezone.utc)
    key = api_key()
    if not key:
        return [], {"state": "no_key", "note": "waiting on ODDS_API_KEY (no sharp book wired)"}
    kalshi = kalshi or _kalshi_open
    odds = odds or _odds_fetch
    bookmaker = (os.environ.get("ODDS_API_BOOKMAKER") or "pinnacle").strip() or "pinnacle"
    lookahead = _env_num("ODDS_LOOKAHEAD_HOURS", 36)
    path = os.path.join(tower, CACHE)
    cache = _read(path)
    leagues = cache.setdefault("leagues", {})
    remaining = cache.get("remaining")
    books, active = {}, []
    for league, (_sport, series) in LEAGUES.items():
        try:
            books[league] = kalshi(series)
        except Exception:  # noqa: BLE001
            books[league] = []
        if books[league] and _soon(books[league], now, lookahead):
            active.append(league)
    every = refresh_minutes(remaining, len(active), now)
    fetched, errors, low = 0, [], False
    for league in active:
        sport = LEAGUES[league][0]
        row = leagues.get(league) or {}
        try:
            age = (now - dt.datetime.fromisoformat(row["at"])).total_seconds() / 60.0
        except (KeyError, TypeError, ValueError):
            age = None
        if age is not None and age < every:
            continue
        if remaining is not None and remaining <= _env_num("ODDS_API_MIN_LEFT", 25):
            low = True
            break
        try:
            events, left = odds(sport, key, bookmaker)
        except urllib.error.HTTPError as exc:
            errors.append(f"{league}: HTTP {exc.code}")
            continue
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{league}: {type(exc).__name__}")
            continue
        fetched += 1
        if left is not None:
            remaining = left
        leagues[league] = {"at": now.isoformat(timespec="seconds"), "events": events}
    cache["remaining"] = remaining
    cache["checked"] = now.isoformat(timespec="seconds")
    try:
        _write(path, cache)
    except OSError:
        pass
    quotes, unmatched = [], 0
    for league in active:
        row = leagues.get(league) or {}
        got, miss = pair_quotes(league, row.get("events") or [], books.get(league) or [], now, bookmaker)
        quotes.extend(got)
        unmatched += miss
    status = {
        "state": "low_credits" if low else "ok",
        "leagues": active,
        "fetched": fetched,
        "remaining": remaining,
        "refresh_minutes": round(every, 1),
        "unmatched": unmatched,
        "errors": errors,
        "bookmaker": bookmaker,
    }
    if low:
        status["note"] = f"Odds API credits low ({remaining:g} left); using the last lines only"
    elif errors and not fetched:
        status["note"] = "Odds API read failed: " + "; ".join(errors[:4])
    elif not active:
        status["note"] = "no Kalshi games in the next day and a half"
    return quotes, status
