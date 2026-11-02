"""
kalshi_tape.py — track public Kalshi trades for desk-watched series.

PAPER / READ-ONLY. Polls GET /markets/trades (and open markets per series).
Does not place orders. Used so the desk can see exchange activity, not only
our own paper fills.

Allowlist = series the towers already trade. Full-exchange ingest is out of scope.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Iterable

KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
UA = {"User-Agent": "paper-bot/1.0 (kalshi-tape read-only)"}

# Series the desk cares about (BTC + INX + sports-gap leagues).
WATCH_SERIES = (
    "KXBTC15M",
    "KXINXU",
    "KXNFLGAME",
    "KXNCAAFGAME",
    "KXNBAGAME",
    "KXWNBAGAME",
    "KXMLBGAME",
    "KXNHLGAME",
)

TAPE_NAME = "kalshi_tape.json"
MAX_TRADES_KEPT = 4000
MAX_RECENT = 40


def tape_path(root: str | None = None) -> str:
    base = root or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, TAPE_NAME)


def _empty() -> dict:
    return {
        "paper_only": True,
        "series": list(WATCH_SERIES),
        "by_series": {s: {"count": 0, "last_ts": None, "last_trade_id": None} for s in WATCH_SERIES},
        "trades": [],
        "seen_ids": [],
        "last_sync_at": None,
        "last_error": None,
        "open_markets": {},
    }


def load_tape(root: str | None = None) -> dict:
    path = tape_path(root)
    if not os.path.exists(path):
        return _empty()
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            return _empty()
    except (OSError, json.JSONDecodeError):
        return _empty()
    base = _empty()
    base.update({k: data.get(k, base[k]) for k in base})
    if not isinstance(base.get("by_series"), dict):
        base["by_series"] = _empty()["by_series"]
    for s in WATCH_SERIES:
        base["by_series"].setdefault(s, {"count": 0, "last_ts": None, "last_trade_id": None})
    if not isinstance(base.get("trades"), list):
        base["trades"] = []
    if not isinstance(base.get("seen_ids"), list):
        base["seen_ids"] = []
    if not isinstance(base.get("open_markets"), dict):
        base["open_markets"] = {}
    return base


def save_tape(state: dict, root: str | None = None) -> None:
    path = tape_path(root)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    payload = dict(state)
    payload["paper_only"] = True
    # Cap memory: keep recent trades + a sliding seen_id window.
    trades = list(payload.get("trades") or [])
    if len(trades) > MAX_TRADES_KEPT:
        trades = trades[-MAX_TRADES_KEPT:]
    payload["trades"] = trades
    seen = list(payload.get("seen_ids") or [])
    if len(seen) > MAX_TRADES_KEPT * 2:
        seen = seen[-(MAX_TRADES_KEPT * 2):]
    payload["seen_ids"] = seen
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    os.replace(tmp, path)


def _get_json(url: str, tries: int = 3) -> dict:
    err = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=25) as resp:
                return json.load(resp)
        except Exception as exc:  # noqa: BLE001 — network; caller records last_error
            err = exc
            time.sleep(0.4 * (attempt + 1))
    kind = type(err).__name__ if err else "failed"
    raise RuntimeError(f"Kalshi tape GET failed ({kind})")


def series_of_ticker(ticker: str) -> str | None:
    t = str(ticker or "")
    for s in WATCH_SERIES:
        if t == s or t.startswith(s + "-"):
            return s
    return None


def list_open_markets(series: str, limit: int = 200) -> list[dict]:
    """All open markets for one series (paginated)."""
    out: list[dict] = []
    cursor = ""
    while True:
        url = f"{KALSHI}/markets?series_ticker={series}&status=open&limit={min(limit, 200)}"
        if cursor:
            url += f"&cursor={cursor}"
        d = _get_json(url)
        batch = d.get("markets") or []
        out.extend(batch)
        cursor = d.get("cursor") or ""
        if not cursor or not batch:
            break
        if len(out) >= 1000:
            break
    return out


def fetch_trades_for_ticker(ticker: str, min_ts: int | None = None, limit: int = 200) -> list[dict]:
    url = f"{KALSHI}/markets/trades?ticker={ticker}&limit={min(max(limit, 1), 1000)}"
    if min_ts:
        url += f"&min_ts={int(min_ts)}"
    d = _get_json(url)
    rows = d.get("trades") or []
    return rows if isinstance(rows, list) else []


def _norm_trade(row: dict) -> dict | None:
    if not isinstance(row, dict):
        return None
    tid = row.get("trade_id") or row.get("id")
    ticker = row.get("ticker")
    if not tid or not ticker:
        return None
    series = series_of_ticker(str(ticker))
    if not series:
        return None
    try:
        count = float(row.get("count_fp") or row.get("count") or 0)
    except (TypeError, ValueError):
        count = 0.0
    try:
        yes_px = float(row.get("yes_price_dollars") or row.get("yes_price") or 0)
    except (TypeError, ValueError):
        yes_px = None
    return {
        "trade_id": str(tid),
        "ticker": str(ticker),
        "series": series,
        "created_time": row.get("created_time"),
        "count": count,
        "yes_price": yes_px,
        "taker_side": row.get("taker_side") or row.get("taker_outcome_side"),
        "is_block_trade": bool(row.get("is_block_trade")),
    }


def sync_tape(
    root: str | None = None,
    series: Iterable[str] | None = None,
    tickers: Iterable[str] | None = None,
    per_ticker_limit: int = 100,
) -> dict:
    """
    Pull new public trades for watched open markets (and any extra tickers).
    Idempotent on trade_id. Returns updated tape state (also saved).
    """
    state = load_tape(root)
    watched = tuple(series) if series is not None else WATCH_SERIES
    seen = set(state.get("seen_ids") or [])
    added = 0
    open_markets: dict[str, list[str]] = dict(state.get("open_markets") or {})
    errors: list[str] = []

    want_tickers: set[str] = set(str(t) for t in (tickers or []) if t)
    for s in watched:
        try:
            markets = list_open_markets(s)
            open_markets[s] = [m.get("ticker") for m in markets if m.get("ticker")]
            for m in markets:
                if m.get("ticker"):
                    want_tickers.add(str(m["ticker"]))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{s} markets: {type(exc).__name__}")

    for ticker in sorted(want_tickers):
        ser = series_of_ticker(ticker)
        if not ser or ser not in watched:
            continue
        min_ts = None
        # If we have a last wall time for this series, nudge min_ts back 2 minutes
        # so we do not miss borderline prints; seen_ids dedupe.
        last = (state.get("by_series") or {}).get(ser, {}).get("last_ts")
        if last:
            try:
                # created_time is ISO; convert roughly via fromisoformat if present on a trade
                pass
            except Exception:
                min_ts = None
        try:
            rows = fetch_trades_for_ticker(ticker, min_ts=min_ts, limit=per_ticker_limit)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{ticker} trades: {type(exc).__name__}")
            continue
        for raw in rows:
            norm = _norm_trade(raw)
            if not norm or norm["trade_id"] in seen:
                continue
            seen.add(norm["trade_id"])
            state.setdefault("trades", []).append(norm)
            bucket = state.setdefault("by_series", {}).setdefault(
                ser, {"count": 0, "last_ts": None, "last_trade_id": None}
            )
            bucket["count"] = int(bucket.get("count") or 0) + 1
            bucket["last_ts"] = norm.get("created_time") or bucket.get("last_ts")
            bucket["last_trade_id"] = norm["trade_id"]
            added += 1

    state["seen_ids"] = list(seen)
    state["open_markets"] = open_markets
    state["last_sync_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    state["last_error"] = "; ".join(errors) if errors else None
    state["last_added"] = added
    save_tape(state, root)
    return state


def tape_summary(root: str | None = None) -> dict:
    """Compact view for desk snapshot / city monitors."""
    state = load_tape(root)
    trades = list(state.get("trades") or [])
    by = state.get("by_series") or {}
    open_markets = state.get("open_markets") or {}
    return {
        "paper_only": True,
        "tracked_series": list(WATCH_SERIES),
        "trade_count": len(trades),
        "last_sync_at": state.get("last_sync_at"),
        "last_error": state.get("last_error"),
        "last_added": state.get("last_added"),
        "by_series": {
            s: {
                "count": int((by.get(s) or {}).get("count") or 0),
                "last_ts": (by.get(s) or {}).get("last_ts"),
                "open_markets": len(open_markets.get(s) or []),
            }
            for s in WATCH_SERIES
        },
        "recent": trades[-MAX_RECENT:],
    }


def self_check() -> None:
    assert series_of_ticker("KXBTC15M-26NOV020000-00") == "KXBTC15M"
    assert series_of_ticker("KXINXU-26OCT27H1600-T7674.9999") == "KXINXU"
    assert series_of_ticker("OTHER-1") is None
    n = _norm_trade({
        "trade_id": "abc",
        "ticker": "KXBTC15M-26NOV020000-00",
        "count_fp": "3.5",
        "yes_price_dollars": "0.16",
        "created_time": "2026-11-02T00:00:00Z",
        "taker_side": "yes",
    })
    assert n and n["series"] == "KXBTC15M" and n["count"] == 3.5


if __name__ == "__main__":
    self_check()
    print("kalshi_tape self_check ok")
