#!/usr/bin/env python3
"""Shared engine for the seven paper shadows that buy nothing.

Each tower reads its series from the public API. A game-winner ticker, a
15-minute series, or a spot symbol is not that series. A listed series logs
the open book and still buys nothing. A series the public API does not list
is named on the card, and that check skips. No ticker, fill, or fair price
is invented. Stake stays 0. Live orders stay off.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import re
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))

# Files that already name series. The shadow folders are not a source of tickers.
SCAN_FILES = (
    "sports-gap-paper/gap_bot.py",
    "commodity-15m-paper/bot.py",
    "btc15m-signal/btc15m_signal.py",
    "desk_roi_plan.py",
)

SPORTS_FLOOR = 0.06
BINARY_FLOOR = 0.05
MENTIONS_CLEAR = 0.05
INX_FLOOR = 0.02

KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
KALSHI_SEARCH = "https://api.elections.kalshi.com/v1/search/series"
POLY_EVENTS = "https://gamma-api.polymarket.com/events"
UA = {"User-Agent": "paper-bots-shadow/1.0 (paper-only read)", "Accept": "application/json"}
CARD_LIMIT = 200

# Series titles read from the public API on 2026-11-11. Game-winner, 15-minute,
# and one-touch tickers are intentionally not in these lists.
SPREAD_SERIES = (
    "KXNFLSPREAD", "KXNCAAFSPREAD", "KXNBASPREAD",
    "KXWNBASPREAD", "KXMLBSPREAD", "KXNHLSPREAD",
)
TOTAL_SERIES = (
    "KXNFLTOTAL", "KXNCAAFTOTAL", "KXNBATOTAL",
    "KXWNBATOTAL", "KXMLBTOTAL", "KXNHLTOTAL",
)
PROP_SERIES = (
    "KXNFLPASSYDS", "KXNFLRSHYDS", "KXNFLRECYDS", "KXNFLREC", "KXNFLTD",
    "KXNBAPTS", "KXNBAREB", "KXNBAAST", "KXNBA3PT",
    "KXNHLGOAL", "KXNHLPTS",
    "KXMLBHIT", "KXMLBHR", "KXMLBKS",
    "KXWNBAPTS", "KXWNBAREB", "KXWNBA3PT", "KXWNBAAST",
)
PERIOD_SERIES = (
    "KXNFL1H", "KXNCAAF1H", "KXNBA1H", "KXWNBA1H", "KXMLBF5", "KXNHL1P",
)
UCL_SERIES = ("KXUCLGAME",)
ESPORTS_SERIES = ("KXLOLGAME", "KXCS2GAME", "KXVALORANTGAME", "KXDOTA2GAME")
MENTION_SERIES = ("mention-markets",)

_TICKER = re.compile(r"\bKX[A-Z0-9]{3,}\b")
_QUOTED = re.compile(r"""['"]([^'"]+)['"]""")
_FLOAT = re.compile(r"[-+]?(?:\d+\.\d+|\d+)(?:[eE][-+]?\d+)?")


TOWERS = (
    {
        "id": "point-spread",
        "name": "Point spread",
        "folder": "point-spread-paper",
        "venue": "kalshi_sports",
        "floor": SPORTS_FLOOR,
        "series_attrs": ("SPREAD_SERIES", "POINT_SPREAD_SERIES"),
        "public_series": SPREAD_SERIES,
        "book": "kalshi",
        "reject_attrs": ("SPORTS",),
        "spread_cap_attr": "MAX_SPREAD",
        "rule": (
            "Point spread on the six leagues. The game-winner series are a different settle. "
            "Clears the sports floor 0.06 after the taker once a series exists. Spread cap is the game-winner cap when that cap is already in the repo."
        ),
        "floor_line": "Sports floor 0.06 cannot be lowered",
    },
    {
        "id": "game-total",
        "name": "Game total",
        "folder": "game-total-paper",
        "venue": "kalshi_sports",
        "floor": SPORTS_FLOOR,
        "series_attrs": ("TOTAL_SERIES", "GAME_TOTAL_SERIES"),
        "public_series": TOTAL_SERIES,
        "book": "kalshi",
        "reject_attrs": ("SPORTS",),
        "spread_cap_attr": "MAX_SPREAD",
        "rule": (
            "Game total on the six leagues. A total settles on the combined score. "
            "The game-winner series do not. Clears the sports floor 0.06 once a series exists."
        ),
        "floor_line": "Sports floor 0.06 cannot be lowered",
    },
    {
        "id": "player-props",
        "name": "Player props",
        "folder": "player-props-paper",
        "venue": "kalshi_sports",
        "floor": SPORTS_FLOOR,
        "series_attrs": ("PROP_SERIES", "PLAYER_PROP_SERIES"),
        "public_series": PROP_SERIES,
        "book": "kalshi",
        "public_gap": "No college-football player-prop series turned up on the public API.",
        "reject_attrs": ("SPORTS",),
        "spread_cap_attr": "MAX_SPREAD",
        "rule": (
            "A player stat contract on the six leagues. Props are a different settle from the game winner. "
            "Clears the sports floor 0.06 once a series exists. Buying the favorite is not a fill."
        ),
        "floor_line": "Sports floor 0.06 cannot be lowered",
    },
    {
        "id": "period-winner",
        "name": "Period winner",
        "folder": "period-winner-paper",
        "venue": "kalshi_sports",
        "floor": SPORTS_FLOOR,
        "series_attrs": ("PERIOD_SERIES", "FIRST_HALF_SERIES"),
        "public_series": PERIOD_SERIES,
        "book": "kalshi",
        "reject_attrs": ("SPORTS",),
        "rule": (
            "First-half or period winner, not the full game. "
            "A full-game win probability is not this fair. Clears the sports floor 0.06 once a series exists."
        ),
        "floor_line": "Sports floor 0.06 cannot be lowered",
    },
    {
        "id": "champions-league",
        "name": "Champions League",
        "folder": "champions-league-paper",
        "venue": "kalshi_sports",
        "floor": SPORTS_FLOOR,
        "series_attrs": ("UCL_SERIES", "CHAMPIONS_LEAGUE_SERIES"),
        "public_series": UCL_SERIES,
        "book": "kalshi",
        "reject_attrs": ("SPORTS",),
        "rule": (
            "UEFA Champions League game winner. It is not a league in the six-sport book. "
            "Clears the sports floor 0.06 once a series exists. Buying the favorite is not a fill."
        ),
        "floor_line": "Sports floor 0.06 cannot be lowered",
    },
    {
        "id": "polymarket-mentions",
        "name": "Polymarket mentions",
        "folder": "polymarket-mentions-paper",
        "venue": "kalshi_econ",
        "floor": MENTIONS_CLEAR,
        "series_attrs": ("MENTION_MARKETS", "MENTION_SERIES"),
        "public_series": MENTION_SERIES,
        "book": "polymarket",
        "quoted_series": True,
        "taker_attr": "POLYMARKET_TAKER_RATE",
        "taker_key": "mentions",
        "rule": (
            "Mention contracts on Polymarket only. No mentions key was added under the locked floors. "
            "The taker coefficient is the mentions rate already in the repo. "
            "A logged edge would still have to clear 0.05. This tower does not buy a phrase."
        ),
        "floor_line": "No mentions floor was added under 0.05. INX and DEX stay at 0.02",
    },
    {
        "id": "esports-match",
        "name": "Esports match",
        "folder": "esports-match-paper",
        "venue": "kalshi_sports",
        "floor": SPORTS_FLOOR,
        "series_attrs": ("ESPORTS_SERIES", "ESPORTS_MATCH_SERIES"),
        "public_series": ESPORTS_SERIES,
        "book": "kalshi",
        "reject_attrs": ("SPORTS",),
        "rule": (
            "Match winner in a titled esports league. It is not in the six-sport book. "
            "Clears the sports floor 0.06 once a series exists. Buying the favorite is not a fill."
        ),
        "floor_line": "Sports floor 0.06 cannot be lowered",
    },
)

BY_ID = {row["id"]: row for row in TOWERS}


def spec_for(tower_id: str) -> dict:
    row = BY_ID.get(tower_id)
    if row is None:
        raise KeyError(tower_id)
    return row


def locked_floor(spec: dict) -> float:
    """Locked venue floor. A config file cannot pull it down."""
    fallback = float(spec["floor"])
    key = str(spec["venue"])
    try:
        if HERE not in sys.path:
            sys.path.insert(0, HERE)
        import desk_profit
        live = float(desk_profit.DEFAULT_VENUE_MIN_EDGE[key])
    except Exception:
        live = fallback
    floor = max(fallback, live)
    if abs(floor - INX_FLOOR) < 1e-12 and fallback > INX_FLOOR:
        floor = fallback
    return floor


def locked_cfg(spec: dict, raw: dict | None = None) -> dict:
    cfg = dict(raw or {})
    floor = locked_floor(spec)
    cfg["paper_only"] = True
    cfg["live_orders"] = False
    cfg["shadow_only"] = True
    cfg["stake_usd"] = 0.0
    cfg["starter_cash"] = 0.0
    cfg["buys"] = False
    asked = _num(cfg.get("venue_min_edge"))
    if asked is None:
        asked = floor
    cfg["venue_min_edge"] = max(floor, asked)
    if abs(cfg["venue_min_edge"] - INX_FLOOR) < 1e-12 and floor > INX_FLOOR:
        cfg["venue_min_edge"] = floor
    return cfg


def series_plan(spec: dict, found: dict[str, str]) -> dict:
    """Which names this check may read. An assigned name replaces the public list."""
    rejected = _rejected(spec, found)
    assigned = any(name in found for name in (spec.get("series_attrs") or ()))
    if assigned:
        names = [name for name in _series_tokens(spec, found) if name not in rejected]
        return {"mode": "assigned", "names": names, "rejected": rejected}
    names = [name for name in (spec.get("public_series") or ()) if name not in rejected]
    if names:
        return {"mode": "public", "names": names, "rejected": rejected}
    if spec.get("discover"):
        return {"mode": "discover", "names": [], "rejected": rejected}
    return {"mode": "absent", "names": [], "rejected": rejected}


def evaluate(
    tower_id: str,
    desk_root: str | None = None,
    registry: dict | None = None,
    book: dict | None = None,
) -> dict:
    """One log row. Buys nothing. A missing series is a skip, not a sample."""
    spec = spec_for(tower_id)
    desk_root = desk_root or HERE
    cfg = locked_cfg(spec)
    found = _scan(desk_root)
    if registry:
        _apply_registry(found, registry)
    plan = series_plan(spec, found)
    rejected = plan["rejected"]
    commission = _commission(spec, found)
    deferred = _deferred(spec, found)
    front = _front_symbols(spec, found)
    taker = _taker_rate(spec, found)
    cap = _spread_cap(spec, found)
    view = _apply_book(spec, plan, book)
    series = view["series"]
    reason = view["reason"]
    if series and spec.get("commission_attrs") and commission is None:
        reason = _fit([reason, "No public commission is on file for this series."])
    row = {
        "tower": spec["id"],
        "action": "skip",
        "reason": reason,
        "ticker_missing": view["ticker_missing"],
        "series": series,
        "rejected_series": sorted(rejected),
        "book": view["quotes"],
        "book_n": len(view["quotes"]),
        "book_empty": view["book_empty"],
        "empty_series": view["empty"],
        "sample": view["sample"],
        "commission": commission,
        "deferred_month": deferred,
        "front_symbols": front,
        "taker_rate": taker,
        "spread_cap": cap,
        "floor": cfg["venue_min_edge"],
        "floor_key": spec["venue"],
        "binary_floor_not_a_fee": bool(spec.get("binary_floor_not_a_fee")),
        "inherits_15m_ladder": False,
        "sells": 0,
        "buys_favorite": False,
        "fair": None,
        "fill": None,
        "implied": None,
        "realized": None,
        "edge": None,
        "buys": 0,
        "stake_usd": 0.0,
        "paper_only": True,
        "shadow_only": True,
        "live_orders": False,
        "counts_as_evidence": False,
        "graded": False,
        "fill_tax_when_graded": 0.01,
    }
    if spec.get("logs_gap"):
        row["gap"] = None
    return row


def _apply_book(spec: dict, plan: dict, book: dict | None) -> dict:
    """Turn a public read into the card line. Never invents a quote."""
    names = list(plan["names"])
    rejected = set(plan["rejected"])
    quotes: list[dict] = []
    empty: list[str] = []
    missing: list[str] = []
    unread: list[str] = []
    discovered = False
    if isinstance(book, dict):
        discovered = bool(book.get("discovered"))
        missing = [name for name in (book.get("missing") or []) if name not in rejected]
        unread = [str(name) for name in (book.get("unread") or []) if str(name)]
        if book.get("error"):
            unread = unread or ["*"]
        if plan["mode"] == "discover":
            names = [name for name in (book.get("series") or []) if name not in rejected]
        elif plan["mode"] != "assigned":
            names = [name for name in names if name not in set(missing)]
        wanted = set(names)
        for quote in book.get("quotes") or []:
            if not isinstance(quote, dict):
                continue
            series = str(quote.get("series") or "")
            if wanted and series not in wanted:
                continue
            if series in rejected:
                continue
            quotes.append(quote)
        empty = [name for name in (book.get("empty") or []) if name in wanted]
    sample = _sample_quote(quotes)
    sample_text = str(sample.get("ticker") or "") if sample else ""
    saw_book = isinstance(book, dict) and not unread
    if unread and not quotes:
        reason = "The public book could not be read. This check skips."
        return _view(names, quotes, empty, not names, False, reason, sample_text)
    if not names:
        if plan["mode"] == "assigned":
            reason = "The assigned series is not this contract. This check skips."
        else:
            reason = str(spec.get("absent") or "The public API does not list a series for this. This check skips.")
        return _view([], [], empty, True, False, reason, "")
    if quotes:
        reason = _live_card(spec, quotes, empty)
        return _view(names, quotes, empty, False, False, reason, sample_text)
    if saw_book:
        reason = _empty_card(spec, names)
        return _view(names, [], empty, False, True, reason, "")
    reason = _listed_card(names)
    return _view(names, [], empty, False, False, reason, "")


def _view(series, quotes, empty, missing, book_empty, reason, sample) -> dict:
    return {
        "series": list(series),
        "quotes": list(quotes),
        "empty": list(empty),
        "ticker_missing": bool(missing),
        "book_empty": bool(book_empty),
        "reason": reason,
        "sample": sample,
    }


def _live_card(spec: dict, quotes: list[dict], empty: list[str]) -> str:
    sample = _sample_quote(quotes)
    if not sample:
        return _empty_card(spec, [])
    bits = ["Logged", str(sample.get("series") or ""), str(sample.get("ticker") or "")]
    if sample.get("bid") is not None:
        bits.append(f"bid {_money(sample['bid'])}")
    if sample.get("ask") is not None:
        bits.append(f"ask {_money(sample['ask'])}")
    open_names = []
    seen = set()
    for quote in quotes:
        name = str(quote.get("series") or "")
        if name and name not in seen:
            seen.add(name)
            open_names.append(name)
    sentences = [
        " ".join(bit for bit in bits if bit).strip() + ".",
        f"{len(open_names)} open series, {len(empty)} empty.",
        "No fill.",
    ]
    gap = str(spec.get("public_gap") or "").strip()
    if gap:
        sentences.append(gap)
    return _fit(sentences)


def _empty_card(spec: dict, names: list[str]) -> str:
    if spec.get("book") == "polymarket":
        return "Polymarket mention-markets has no open market. This check skips."
    shown = _join_names(names, 4)
    sentences = [f"Listed {shown}.", "The open book is empty.", "No fill."]
    gap = str(spec.get("public_gap") or "").strip()
    if gap:
        sentences.append(gap)
    return _fit(sentences)


def _listed_card(names: list[str]) -> str:
    return _fit([
        f"Listed {_join_names(names, 6)}.",
        "No public book on this check.",
        "No fill.",
    ])


def _join_names(names: list[str], cap: int) -> str:
    clean = [str(name) for name in names if name]
    if len(clean) <= cap:
        return ", ".join(clean)
    extra = len(clean) - cap
    return ", ".join(clean[:cap]) + f" and {extra} more"


def _sample_quote(quotes: list[dict]) -> dict | None:
    two = [row for row in quotes if row.get("bid") is not None and row.get("ask") is not None]
    if two:
        return two[0]
    return quotes[0] if quotes else None


def _money(value) -> str:
    text = f"{float(value):.4f}".rstrip("0").rstrip(".")
    if "." not in text:
        return text + ".00"
    if len(text.split(".", 1)[1]) < 2:
        return text + "0"
    return text


def _fit(sentences: list[str], limit: int = CARD_LIMIT) -> str:
    kept = []
    for sentence in sentences:
        sentence = " ".join(str(sentence).split())
        if not sentence:
            continue
        trial = " ".join(kept + [sentence])
        if len(trial) <= limit:
            kept.append(sentence)
    if kept:
        return " ".join(kept)
    return " ".join(str(sentences[0]).split())[:limit]


def load_public_book(spec: dict, found: dict[str, str], opener=None) -> dict:
    """Read the public book for this tower. A failed read is not a ticker."""
    plan = series_plan(spec, found)
    rejected = set(plan["rejected"])
    names = list(plan["names"])
    discovered = False
    if plan["mode"] == "discover":
        discovered = True
        try:
            names = _discover_series(spec, rejected, opener)
        except Exception:
            return {
                "series": [], "quotes": [], "empty": [], "missing": [],
                "unread": ["*"], "discovered": True, "error": True,
            }
    if spec.get("book") == "polymarket" and plan["mode"] != "assigned":
        try:
            book = _polymarket_book(names or list(MENTION_SERIES), opener)
        except Exception:
            return {
                "series": list(names), "quotes": [], "empty": [], "missing": [],
                "unread": ["*"], "discovered": False, "error": True,
            }
        book["discovered"] = False
        return book
    quotes: list[dict] = []
    empty: list[str] = []
    missing: list[str] = []
    unread: list[str] = []
    confirmed: list[str] = []
    for name in names:
        if name in rejected:
            continue
        try:
            rows = _kalshi_markets(name, opener)
        except Exception as exc:
            if _is_missing(exc):
                missing.append(name)
            else:
                unread.append(name)
            continue
        got = _quotes_from_markets(name, rows)
        if got:
            quotes.extend(got)
            confirmed.append(name)
            continue
        try:
            exists = _series_exists(name, opener)
        except Exception as exc:
            if _is_missing(exc):
                missing.append(name)
            else:
                unread.append(name)
            continue
        if exists:
            empty.append(name)
            confirmed.append(name)
        else:
            missing.append(name)
    if plan["mode"] == "discover":
        series = confirmed
    else:
        series = [name for name in names if name not in set(missing)]
    return {
        "series": series,
        "quotes": quotes,
        "empty": empty,
        "missing": missing,
        "unread": unread,
        "discovered": discovered,
        "error": False,
    }


def _discover_series(spec: dict, rejected: set[str], opener) -> list[str]:
    found: list[str] = []
    seen = set()
    for query in (spec.get("discover") or {}).get("queries") or ():
        url = KALSHI_SEARCH + "?" + urllib.parse.urlencode({"query": query, "page_size": 20})
        data = _decode_body(_fetch(url, opener))
        rows = data.get("current_page") if isinstance(data, dict) else None
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            ticker = str(row.get("series_ticker") or "").strip().upper()
            title = str(row.get("series_title") or "")
            if not ticker or ticker in seen or ticker in rejected:
                continue
            if not _discover_ok(spec, ticker, title):
                continue
            seen.add(ticker)
            found.append(ticker)
    return found


def _discover_ok(spec: dict, ticker: str, title: str) -> bool:
    mode = str((spec.get("discover") or {}).get("mode") or "")
    text = f"{ticker} {title}".lower()
    if ticker in ("KXBTC15M", "KXETH15M", "KXBTCD"):
        return False
    if "15m" in ticker.lower() or "15-minute" in text or "15 minute" in text:
        return False
    if mode == "calendar":
        return ("calendar" in text) and any(word in text for word in ("wti", "gold", "crude"))
    if mode == "btc-option":
        if "one touch" in text or "one-touch" in text:
            return False
        return ("option" in text) and any(word in text for word in ("bitcoin", "btc"))
    return False


def _polymarket_book(names: list[str], opener) -> dict:
    tag = names[0] if names else "mention-markets"
    url = POLY_EVENTS + "?" + urllib.parse.urlencode({
        "closed": "false",
        "limit": 20,
        "tag_slug": tag,
    })
    data = _decode_body(_fetch(url, opener))
    events = data if isinstance(data, list) else []
    quotes = []
    for event in events:
        if not isinstance(event, dict) or event.get("closed") is True:
            continue
        for market in event.get("markets") or []:
            if not isinstance(market, dict) or market.get("closed") is True:
                continue
            slug = str(market.get("slug") or "").strip()
            bid = _px(market.get("bestBid"))
            ask = _px(market.get("bestAsk"))
            if not slug or (bid is None and ask is None):
                continue
            quotes.append({"series": tag, "ticker": slug, "bid": bid, "ask": ask})
            if len(quotes) >= 12:
                break
        if len(quotes) >= 12:
            break
    if quotes:
        return {"series": [tag], "quotes": quotes, "empty": [], "missing": [], "unread": [], "error": False}
    return {"series": [tag], "quotes": [], "empty": [tag], "missing": [], "unread": [], "error": False}


def _kalshi_markets(series: str, opener) -> list:
    url = f"{KALSHI}/markets?series_ticker={urllib.parse.quote(series)}&status=open&limit=20"
    data = _decode_body(_fetch(url, opener))
    if isinstance(data, dict) and _error_missing(data):
        return []
    rows = data.get("markets") if isinstance(data, dict) else None
    return list(rows or [])


def _quotes_from_markets(series: str, rows: list) -> list[dict]:
    out = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").strip()
        if not ticker:
            continue
        bid = _px(row.get("yes_bid_dollars"))
        if bid is None:
            bid = _px(row.get("yes_bid"))
        ask = _px(row.get("yes_ask_dollars"))
        if ask is None:
            ask = _px(row.get("yes_ask"))
        if bid is None and ask is None:
            continue
        out.append({"series": series, "ticker": ticker, "bid": bid, "ask": ask})
        if len(out) >= 8:
            break
    return out


def _series_exists(series: str, opener) -> bool:
    url = f"{KALSHI}/series/{urllib.parse.quote(series)}"
    try:
        data = _decode_body(_fetch(url, opener))
    except Exception as exc:
        if _is_missing(exc):
            return False
        raise
    if not isinstance(data, dict) or _error_missing(data):
        return False
    body = data.get("series") if isinstance(data.get("series"), dict) else data
    ticker = str((body or {}).get("ticker") or "").upper()
    return ticker == series.upper() or bool((body or {}).get("title"))


def _px(value):
    number = _num(value)
    if number is None:
        return None
    if number > 1.0 and number <= 100.0:
        number = number / 100.0
    if number <= 0.0 or number >= 1.0:
        return None
    return round(number, 4)


def _fetch(url: str, opener):
    opener = opener or _default_opener
    return opener(url)


def _default_opener(url: str):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=8) as response:
        return response.read()


def _decode_body(blob):
    if isinstance(blob, (dict, list)):
        return blob
    if blob is None:
        return {}
    try:
        if isinstance(blob, bytes):
            blob = blob.decode("utf-8", errors="replace")
        data = json.loads(blob)
    except (TypeError, json.JSONDecodeError):
        return {}
    if isinstance(data, (dict, list)):
        return data
    return {}


def _error_missing(data: dict) -> bool:
    err = data.get("error")
    if isinstance(err, dict):
        code = str(err.get("code") or err.get("message") or "").lower()
        return "not_found" in code or "not found" in code or code == "404"
    return False


def _is_missing(exc: BaseException) -> bool:
    code = getattr(exc, "code", None)
    if code == 404:
        return True
    text = str(exc).lower()
    return "404" in text or "not_found" in text or "not found" in text


def empty_state() -> dict:
    return {
        "cash": 0.0,
        "open": [],
        "closed": [],
        "paper_only": True,
        "shadow_only": True,
        "live_orders": False,
        "stake_usd": 0.0,
        "buys": 0,
        "checks": 0,
        "evidence_n": 0,
    }


def run_once(
    tower_id: str,
    desk_root: str | None = None,
    now: dt.datetime | None = None,
    registry: dict | None = None,
    cfg: dict | None = None,
    *,
    fetch: bool = True,
    opener=None,
    book: dict | None = None,
) -> int:
    spec = spec_for(tower_id)
    desk_root = desk_root or HERE
    tower = os.path.join(desk_root, spec["folder"])
    os.makedirs(tower, exist_ok=True)
    locked_cfg(spec, cfg if cfg is not None else _read_json(os.path.join(tower, "config.json")))
    now = now or dt.datetime.now(dt.timezone.utc)
    if book is None and fetch:
        found = _scan(desk_root)
        if registry:
            _apply_registry(found, registry)
        book = load_public_book(spec, found, opener)
    decision = evaluate(tower_id, desk_root=desk_root, registry=registry, book=book)
    added = _append_evidence(tower, decision, now)
    state = _read_json(os.path.join(tower, "paper_account.json")) or empty_state()
    if not isinstance(state, dict):
        state = empty_state()
    state.update({
        "cash": 0.0,
        "open": [],
        "closed": [],
        "paper_only": True,
        "shadow_only": True,
        "live_orders": False,
        "stake_usd": 0.0,
        "buys": 0,
        "checks": int(state.get("checks") or 0) + 1,
        "last_check": now.isoformat(timespec="seconds"),
        "evidence_n": 0,
        "logged_n": len(added),
        "ticker_missing": bool(decision.get("ticker_missing")),
        "series": list(decision.get("series") or []),
        "reason": decision.get("reason") or "",
        "sample": decision.get("sample") or "",
        "book_n": int(decision.get("book_n") or 0),
        "fair": None,
        "fill": None,
    })
    _write_json(os.path.join(tower, "paper_account.json"), state)
    _append_research(tower, now, decision)
    _emit(decision)
    return 0


def _emit(decision: dict) -> None:
    reason = str(decision.get("reason") or "The public book could not be read. This check skips.")
    print("SIGNAL: SKIP " + reason)
    print("CARD: " + reason)
    print("no trade")


def _append_evidence(tower: str, decision: dict, now: dt.datetime) -> list[dict]:
    """One standing skip line. A missing ticker is not evidence and is not repeated."""
    path = os.path.join(tower, "evidence.jsonl")
    key = _standing_key(decision)
    if key in _evidence_keys(path):
        return []
    payload = dict(decision)
    payload["at"] = now.isoformat(timespec="seconds")
    payload["counts_as_evidence"] = False
    payload["buys"] = 0
    payload["stake_usd"] = 0.0
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
    return [payload]


def _standing_key(row: dict) -> tuple:
    if row.get("ticker_missing"):
        status = "missing"
    elif row.get("book"):
        status = "live"
    elif row.get("book_empty"):
        status = "empty"
    else:
        status = "listed"
    return (status, tuple(row.get("series") or []))


def _evidence_keys(path: str) -> set[tuple]:
    seen: set[tuple] = set()
    if not os.path.isfile(path):
        return seen
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(row, dict):
                    continue
                seen.add(_standing_key(row))
    except OSError:
        return seen
    return seen


def _append_research(tower: str, now: dt.datetime, decision: dict) -> None:
    path = os.path.join(tower, "research.jsonl")
    payload = {
        "at": now.isoformat(timespec="seconds"),
        "paper_only": True,
        "shadow_only": True,
        "live_orders": False,
        "buys": 0,
        "stake_usd": 0.0,
        "fair": None,
        "fill": None,
        "decision": decision,
    }
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _scan(desk_root: str) -> dict[str, str]:
    found: dict[str, str] = {}
    names = set()
    for spec in TOWERS:
        names.update(spec.get("series_attrs") or ())
        names.update(spec.get("reject_attrs") or ())
        names.update(spec.get("commission_attrs") or ())
        names.update(spec.get("deferred_attrs") or ())
        if spec.get("spread_cap_attr"):
            names.add(spec["spread_cap_attr"])
        if spec.get("taker_attr"):
            names.add(spec["taker_attr"])
    names.add("YAHOO")
    for rel in SCAN_FILES:
        text = _read_text(os.path.join(desk_root, rel))
        if not text:
            continue
        for name in names:
            if name in found:
                continue
            body = _assignment_body(text, name)
            if body is not None:
                found[name] = body
    return found


def _apply_registry(found: dict[str, str], registry: dict) -> None:
    """Test hook. Does not write a ticker into the repo."""
    for name, value in (registry.get("assignments") or {}).items():
        if isinstance(value, (list, tuple)):
            inner = ", ".join(repr(str(item)) for item in value)
            found[str(name)] = "(" + inner + ")"
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            found[str(name)] = str(value)
        elif isinstance(value, str):
            found[str(name)] = value


def _series_tokens(spec: dict, found: dict[str, str]) -> list[str]:
    out: list[str] = []
    quoted = bool(spec.get("quoted_series"))
    for name in spec.get("series_attrs") or ():
        body = found.get(name)
        if not body:
            continue
        out.extend(_tokens(body, quoted=quoted))
    deduped = []
    seen = set()
    for name in out:
        if name in seen:
            continue
        seen.add(name)
        deduped.append(name)
    return deduped


def _rejected(spec: dict, found: dict[str, str]) -> set[str]:
    out: set[str] = set()
    for name in spec.get("reject_attrs") or ():
        body = found.get(name)
        if not body:
            continue
        out.update(_tokens(body, quoted=False))
    return out


def _commission(spec: dict, found: dict[str, str]):
    for name in spec.get("commission_attrs") or ():
        body = found.get(name)
        if body is None:
            continue
        match = _FLOAT.search(body)
        if not match:
            continue
        number = _num(match.group(0))
        if number is not None:
            return number
    return None


def _deferred(spec: dict, found: dict[str, str]) -> list[str]:
    out: list[str] = []
    for name in spec.get("deferred_attrs") or ():
        body = found.get(name)
        if not body:
            continue
        out.extend(_tokens(body, quoted=True))
    return out


def _front_symbols(spec: dict, found: dict[str, str]) -> list[str]:
    wanted = tuple(spec.get("front_symbols") or ())
    if not wanted:
        return []
    body = found.get("YAHOO") or ""
    present = []
    for symbol in wanted:
        if symbol in body:
            present.append(symbol)
    return present


def _taker_rate(spec: dict, found: dict[str, str]):
    attr = spec.get("taker_attr")
    key = spec.get("taker_key")
    if not attr or not key:
        return None
    body = found.get(attr) or ""
    match = re.search(r"""['"]%s['"]\s*:\s*([0-9.]+)""" % re.escape(str(key)), body)
    if not match:
        return None
    return _num(match.group(1))


def _spread_cap(spec: dict, found: dict[str, str]):
    name = spec.get("spread_cap_attr")
    if not name:
        return None
    body = found.get(name)
    if body is None:
        return None
    match = _FLOAT.search(body)
    if not match:
        return None
    return _num(match.group(0))


def _tokens(body: str, *, quoted: bool) -> list[str]:
    if quoted:
        raw = _QUOTED.findall(body)
    else:
        raw = _TICKER.findall(body)
    out = []
    for item in raw:
        text = str(item or "").strip()
        if not text or text in out:
            continue
        out.append(text)
    return out


def _assignment_body(text: str, name: str) -> str | None:
    pattern = re.compile(r"(?m)^%s\s*=" % re.escape(name))
    match = pattern.search(text)
    if match is None:
        return None
    rest = text[match.end():].lstrip()
    if not rest:
        return None
    opener = rest[0]
    if opener not in "([{":
        return rest.splitlines()[0].strip()
    closer = {"(": ")", "[": "]", "{": "}"}[opener]
    depth = 0
    quote = ""
    escape = False
    for index, ch in enumerate(rest):
        if quote:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == quote:
                quote = ""
            continue
        if ch in ("'", '"'):
            quote = ch
            continue
        if ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return rest[: index + 1]
    return None


def _num(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _read_text(path: str) -> str:
    if not os.path.isfile(path):
        return ""
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except OSError:
        return ""


def _read_json(path: str):
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    return data


def _write_json(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")


def main(tower_id: str, argv: list[str] | None = None) -> int:
    spec = spec_for(tower_id)
    argv = list(sys.argv[1:] if argv is None else argv)
    tower = os.path.join(HERE, spec["folder"])
    if "--reset" in argv:
        os.makedirs(tower, exist_ok=True)
        _write_json(os.path.join(tower, "paper_account.json"), empty_state())
        print("reset paper account")
        return 0
    return run_once(tower_id)
