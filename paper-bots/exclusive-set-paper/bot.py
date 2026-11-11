#!/usr/bin/env python3
"""Exclusive set — same-venue shadow logger. Buys nothing.

Logs mutually exclusive Kalshi legs of one event. A basket is interesting
only when the sum of (public ask + taker fee) is below $1 by at least the
floor: 0.06 for a sports set, 0.05 for any other Kalshi set. The INX 0.02
floor is not used. KXINXU is not traded.

dutch_book_observe's three example baskets are not read and are not evidence.
Paper only. No stake. No desk risk share. Never LIVE.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DESK_ROOT = os.path.dirname(HERE)
KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
UA = {"User-Agent": "paper-bots-exclusive-set/1.0 (paper-only read)"}

# Game-winner series the sports book already names. A league prefix still
# counts as sports so a same-league exclusive set keeps the 0.06 floor.
SPORTS_SERIES = (
    "KXNFLGAME",
    "KXNCAAFGAME",
    "KXNBAGAME",
    "KXWNBAGAME",
    "KXMLBGAME",
    "KXNHLGAME",
)
SPORTS_PREFIXES = ("KXNFL", "KXNCAAF", "KXNBA", "KXWNBA", "KXMLB", "KXNHL")
SPORTS_FLOOR = 0.06
OTHER_FLOOR = 0.05
INX_FLOOR = 0.02  # locked elsewhere — this tower does not use it

# Labels and ask pairs shipped as constants in dutch_book_observe.
EXAMPLE_LABELS = frozenset({
    "underround_sports",
    "overround_sports",
    "thin_underround",
})
EXAMPLE_PAIRS = frozenset({
    (0.44, 0.44),
    (0.52, 0.52),
    (0.47, 0.47),
})
EXAMPLE_SOURCES = frozenset({"example", "dutch_book_observe"})


def locked_cfg(raw: dict | None = None) -> dict:
    """Paper shadow. Stake stays 0. Floors never fall to the INX number."""
    cfg = dict(raw or {})
    sports = sports_floor()
    other = other_floor()
    cfg["paper_only"] = True
    cfg["live_orders"] = False
    cfg["shadow_only"] = True
    cfg["stake_usd"] = 0.0
    cfg["starter_cash"] = 0.0
    cfg["buys"] = False
    cfg["sports_floor"] = max(sports, _num(cfg.get("sports_floor")) or sports)
    asked_other = _num(cfg.get("other_floor"))
    if asked_other is None:
        asked_other = other
    cfg["other_floor"] = max(other, asked_other)
    if abs(cfg["other_floor"] - INX_FLOOR) < 1e-12:
        cfg["other_floor"] = other
    cfg["venue_min_edge"] = cfg["sports_floor"]
    return cfg


def sports_floor() -> float:
    return _locked_floor("kalshi_sports", SPORTS_FLOOR)


def other_floor() -> float:
    """0.05 for any non-sports Kalshi set. Never the INX 0.02 lock."""
    inx = _locked_floor("kalshi_inx", INX_FLOOR)
    floor = OTHER_FLOOR
    if abs(floor - inx) < 1e-12:
        floor = OTHER_FLOOR
    return floor


def kalshi_fee(ask: float) -> float:
    """ceil(0.07 · p · (1 − p)) dollars per $1 contract."""
    p = float(ask)
    if not (0.0 < p < 1.0) or not math.isfinite(p):
        return 0.0
    raw = 0.07 * p * (1.0 - p)
    return math.ceil(round(raw * 100, 6)) / 100.0


def is_kxinxu(*parts: object) -> bool:
    for part in parts:
        text = str(part or "").strip().upper()
        if not text:
            continue
        if text == "KXINXU" or text.startswith("KXINXU"):
            return True
    return False


def is_sports_series(series: str) -> bool:
    text = str(series or "").strip().upper()
    if not text or is_kxinxu(text):
        return False
    if text in SPORTS_SERIES:
        return True
    return any(text.startswith(prefix) for prefix in SPORTS_PREFIXES)


def floor_for(series: str, cfg: dict | None = None) -> tuple[str, float]:
    cfg = locked_cfg(cfg)
    if is_sports_series(series):
        return "sports", float(cfg["sports_floor"])
    return "other", float(cfg["other_floor"])


def public_ask(market: dict) -> float | None:
    """Yes ask in dollars. Missing stays missing — never invent a complement."""
    for key in ("yes_ask_dollars", "yes_ask", "ask"):
        n = _num(market.get(key))
        if n is None:
            continue
        if n > 1.0 + 1e-12 and n <= 100.0:
            n = n / 100.0
        if 0.0 < n < 1.0:
            return float(n)
    return None


def series_of(market: dict, event: str) -> str:
    for key in ("series_ticker", "series"):
        raw = str(market.get(key) or "").strip().upper()
        if raw:
            return raw
    for raw in (market.get("ticker"), event):
        text = str(raw or "").strip().upper()
        if not text:
            continue
        head = text.split("-", 1)[0]
        if head:
            return head
    return ""


def is_observe_example(event: str, legs: list[dict], label: str, source: str) -> bool:
    """The three dutch_book_observe baskets are examples, not a tape."""
    if str(source or "") in EXAMPLE_SOURCES or str(label or "") in EXAMPLE_LABELS:
        return True
    if str(event or "").strip():
        return False
    asks = tuple(sorted(round(float(leg["ask"]), 2) for leg in legs))
    return len(asks) == 2 and asks in EXAMPLE_PAIRS


def reject_observe_board(board: dict | None) -> dict:
    """Those three baskets stay examples. None of them enter the evidence log."""
    baskets = []
    if isinstance(board, dict):
        baskets = list(board.get("baskets") or [])
    return {
        "accepted": 0,
        "rejected": len(baskets),
        "counts_as_evidence": False,
        "reason": "dutch_book_observe examples are not evidence",
        "paper_only": True,
        "shadow_only": True,
        "buys": 0,
        "stake_usd": 0.0,
        "live_orders": False,
    }


def score_basket(event: str, markets: list[dict], cfg: dict | None = None) -> dict:
    cfg = locked_cfg(cfg)
    event = str(event or "").strip()
    label = ""
    sources = set()
    series = ""
    refused = is_kxinxu(event)
    seen = set()
    parsed = []
    missing = False
    for market in markets or []:
        if not isinstance(market, dict):
            continue
        label = label or str(market.get("label") or "")
        sources.add(str(market.get("source") or "public"))
        ticker = str(market.get("ticker") or market.get("side") or "")
        series = series or series_of(market, event)
        if is_kxinxu(series, ticker, market.get("event_ticker"), market.get("series_ticker")):
            refused = True
        key = ticker or str(market.get("side") or len(parsed))
        if key in seen:
            continue
        seen.add(key)
        ask = public_ask(market)
        if ask is None:
            missing = True
            continue
        fee = kalshi_fee(ask)
        parsed.append({
            "ticker": ticker,
            "side": str(market.get("side") or ticker),
            "ask": round(ask, 4),
            "fee": round(fee, 4),
            "cost": round(ask + fee, 4),
        })
    kind, floor = floor_for(series, cfg)
    if abs(floor - INX_FLOOR) < 1e-12:
        kind, floor = floor_for(series, None)
    source = "example" if sources & EXAMPLE_SOURCES else "public"
    example = is_observe_example(event, parsed, label, source)
    total = round(sum(leg["cost"] for leg in parsed), 4)
    edge = round(1.0 - total, 4) if parsed else None
    row = {
        "event": event,
        "series": series,
        "set": kind,
        "label": label,
        "source": "example" if example else source,
        "floor": floor,
        "legs": parsed,
        "sum_ask_fee": total,
        "edge": edge,
        "action": "skip",
        "interesting": False,
        "example": example,
        "refused": refused,
        "counts_as_evidence": False,
        "buys": 0,
        "stake_usd": 0.0,
        "paper_only": True,
        "shadow_only": True,
        "live_orders": False,
        "graded": False,
        "fill_tax_when_graded": 0.01,
        "reason": "",
    }
    if refused:
        row["reason"] = "KXINXU is not traded"
        return row
    if not event or missing or len(parsed) < 2:
        row["reason"] = "one-sided book — every leg needs a public ask"
        return row
    if example:
        row["reason"] = "example basket is not evidence"
        row["interesting"] = bool(edge is not None and edge + 1e-12 >= floor)
        return row
    if edge is None or edge + 1e-12 < floor:
        if edge is not None and edge < 0:
            row["reason"] = "overround — house edge"
        else:
            shown = f"{edge:.4f}" if edge is not None else "none"
            row["reason"] = f"underround edge {shown} < floor {floor:.2f}"
        return row
    row["interesting"] = True
    row["action"] = "log"
    row["counts_as_evidence"] = True
    row["reason"] = (
        f"{kind} set clears {floor:.2f}: sum {total:.4f} edge {edge:.4f}"
    )
    return row


def score_markets(markets: list | None, cfg: dict | None = None) -> list[dict]:
    cfg = locked_cfg(cfg)
    grouped: dict[str, list] = {}
    loose = 0
    for market in markets or []:
        if not isinstance(market, dict):
            continue
        event = str(market.get("event_ticker") or market.get("event") or "").strip()
        if not event:
            loose += 1
            continue
        grouped.setdefault(event, []).append(market)
    rows = [score_basket(event, legs, cfg) for event, legs in grouped.items()]
    if loose:
        rows.append({
            "event": "",
            "series": "",
            "set": "",
            "action": "skip",
            "interesting": False,
            "example": False,
            "refused": False,
            "counts_as_evidence": False,
            "buys": 0,
            "stake_usd": 0.0,
            "paper_only": True,
            "shadow_only": True,
            "live_orders": False,
            "reason": "no event ticker — one-sided books are skipped",
            "legs": [],
        })
    return rows


def load_book(tower: str) -> tuple[list[dict], list[str]]:
    """Public rows dropped beside the tower. Example files are ignored."""
    path = os.path.join(tower, "exclusive_book.json")
    data = _read_json(path)
    if not isinstance(data, dict):
        return [], []
    if str(data.get("source") or "") in EXAMPLE_SOURCES:
        return [], []
    series = []
    for raw in data.get("series") or []:
        name = str(raw or "").strip().upper()
        if name and not is_kxinxu(name):
            series.append(name)
    markets = []
    for row in data.get("markets") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("source") or "") in EXAMPLE_SOURCES or row.get("example"):
            continue
        if is_kxinxu(row.get("ticker"), row.get("event_ticker"), row.get("series_ticker")):
            continue
        item = dict(row)
        item["source"] = "public"
        markets.append(item)
    return markets, series


def fetch_series(series: str, opener=None) -> list[dict]:
    """One public series page. KXINXU is never requested."""
    name = str(series or "").strip().upper()
    if not name or is_kxinxu(name):
        return []
    url = f"{KALSHI}/markets?series_ticker={name}&status=open&limit=100"
    opener = opener or _default_opener
    try:
        blob = opener(url)
    except Exception:
        return []
    data = _decode(blob)
    rows = data.get("markets") if isinstance(data, dict) else None
    out = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        if is_kxinxu(name, row.get("ticker"), row.get("event_ticker"), row.get("series_ticker")):
            continue
        item = dict(row)
        item["source"] = "public"
        item.setdefault("series_ticker", name)
        out.append(item)
    return out


def fetch_public(opener=None, extra_series: list | None = None) -> list[dict]:
    names = list(SPORTS_SERIES)
    for raw in extra_series or []:
        name = str(raw or "").strip().upper()
        if name and not is_kxinxu(name) and name not in names:
            names.append(name)
    out: list[dict] = []
    for name in names:
        out.extend(fetch_series(name, opener=opener))
    return out


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
        "interesting_n": 0,
        "evidence_n": 0,
    }


def run_once(
    desk_root: str | None = None,
    cfg: dict | None = None,
    markets: list | None = None,
    now: dt.datetime | None = None,
    *,
    fetch: bool | None = None,
    opener=None,
) -> int:
    desk_root = desk_root or DESK_ROOT
    tower = os.path.join(desk_root, "exclusive-set-paper")
    os.makedirs(tower, exist_ok=True)
    cfg = locked_cfg(cfg or _read_json(os.path.join(tower, "config.json")) or {})
    now = now or dt.datetime.now(dt.timezone.utc)
    if markets is None:
        book, extra = load_book(tower)
        rows = list(book)
        if fetch is not False:
            rows.extend(fetch_public(opener=opener, extra_series=extra))
    else:
        rows = list(markets)
    decisions = score_markets(rows, cfg)
    added = _append_evidence(tower, decisions, now)
    state = _read_json(os.path.join(tower, "paper_account.json")) or empty_state()
    if not isinstance(state, dict):
        state = empty_state()
    # The book stays flat. A position on this tower would be a buy.
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
        "interesting_n": sum(1 for row in decisions if row.get("interesting")),
        "evidence_n": _evidence_count(tower),
        "logged_n": len(added),
    })
    _write_json(os.path.join(tower, "paper_account.json"), state)
    _append_research(tower, now, decisions)
    _emit(decisions)
    return 0


def _emit(decisions: list[dict]) -> None:
    logged = [row for row in decisions if row.get("counts_as_evidence")]
    if logged:
        row = logged[0]
        print(
            f"SIGNAL: LOG {row.get('event')} edge {row.get('edge')} "
            f"floor {float(row.get('floor') or 0):.2f}"
        )
        print(f"CARD: logged {row.get('event')} — buys nothing")
    elif not decisions:
        print("SIGNAL: SKIP waiting on a public exclusive set")
        print("CARD: waiting on a public exclusive set")
    else:
        row = decisions[0]
        print("SIGNAL: SKIP " + str(row.get("reason") or "no basket clears the floor"))
        print("CARD: " + str(row.get("reason") or "no basket clears the floor"))
    print("no trade")


def _append_evidence(tower: str, decisions: list[dict], now: dt.datetime) -> list[dict]:
    path = os.path.join(tower, "evidence.jsonl")
    seen = _evidence_events(path)
    added = []
    with open(path, "a", encoding="utf-8") as handle:
        for row in decisions:
            if not row.get("counts_as_evidence"):
                continue
            event = str(row.get("event") or "")
            if not event or event in seen or is_kxinxu(event, row.get("series")):
                continue
            if row.get("example") or str(row.get("source") or "") in EXAMPLE_SOURCES:
                continue
            seen.add(event)
            payload = dict(row)
            payload["at"] = now.isoformat(timespec="seconds")
            handle.write(json.dumps(payload, sort_keys=True) + "\n")
            added.append(payload)
    return added


def _evidence_events(path: str) -> set[str]:
    seen: set[str] = set()
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
                if isinstance(row, dict) and row.get("event"):
                    seen.add(str(row["event"]))
    except OSError:
        return seen
    return seen


def _evidence_count(tower: str) -> int:
    return len(_evidence_events(os.path.join(tower, "evidence.jsonl")))


def _append_research(tower: str, now: dt.datetime, decisions: list[dict]) -> None:
    path = os.path.join(tower, "research.jsonl")
    payload = {
        "at": now.isoformat(timespec="seconds"),
        "paper_only": True,
        "shadow_only": True,
        "live_orders": False,
        "buys": 0,
        "stake_usd": 0.0,
        "decisions": decisions,
    }
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


def _locked_floor(key: str, fallback: float) -> float:
    try:
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        import desk_profit
        live = float(desk_profit.DEFAULT_VENUE_MIN_EDGE[key])
    except Exception:
        live = float(fallback)
    return max(float(fallback), live)


def _num(value):
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(n):
        return None
    return n


def _decode(blob) -> dict:
    if isinstance(blob, dict):
        return blob
    if blob is None:
        return {}
    try:
        if isinstance(blob, bytes):
            blob = blob.decode("utf-8", errors="replace")
        data = json.loads(blob)
    except (TypeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _default_opener(url: str):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=8) as response:
        return response.read()


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


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    tower = os.path.join(DESK_ROOT, "exclusive-set-paper")
    if "--reset" in argv:
        os.makedirs(tower, exist_ok=True)
        _write_json(os.path.join(tower, "paper_account.json"), empty_state())
        print("reset paper account")
        return 0
    return run_once()


if __name__ == "__main__":
    raise SystemExit(main())
