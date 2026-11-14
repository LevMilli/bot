"""Practice twins of the three 15-minute towers (ideas B1-B5). Paper only. Shadow only.

Each twin is one row in new_towers.py plus a tiny folder whose bot.py calls
``main(twin_id, folder)``. The twin runs on the shared shadow engine
(kalshi_shadow_tower.py) with its own ledger in its own folder.

Prices come from the original towers' own code, loaded read-only:

* More 15m twins call More 15m's ``model`` (same series, spot, swing math).
* BTC 15m twins call BTC 15m's market list, spot, candles, DVOL, order book and
  ``evaluate_window`` gates (z, cushion, ask band, spread, depth, candles, news).
* Commodity 15m twins call Commodity 15m's index feed, market list, open
  offset, order books and ``evaluate`` gates (z, cushion, ask band, spread,
  depth, EIA blackout).

The originals are never run and never written to. A twin never writes the
originals' paper accounts, learning rows, decision journals, quote caches or
learned open offsets. Its own copies live in ``fifteen-twins-cache/``; the open
offsets start from a read-only copy of the original's file.

Twins of one family share one quote read for ``CACHE_SEC`` seconds, so four BTC
twins cost about one BTC read a minute. Each twin then applies its own rules.

Each twin changes one rule against its control:

* B1 ``more-15m-longshot``: asks under 20c need 0.05 more edge (0.10 total). Control: More 15m.
* B5 ``more-15m-tp15``: adds a take-profit at entry + 15c. Control: More 15m.
* ``btc15m-mirror`` / ``commodity-15m-mirror``: controls with the original gates on this engine.
* B2 ``commodity-15m-cap85``: no buys above an 85c ask. Control: Commodity 15m mirror.
* B3 ``btc15m-5min``: may buy with 5+ minutes left instead of 10+. Control: BTC 15m mirror.
* B4 ``btc15m-tape`` / ``commodity-15m-tape``: Kalshi tape check + fee once per order. Control: mirror.
* B5 ``btc15m-tp10``: take-profit at entry + 10c instead of 15c. Control: BTC 15m mirror.

Shadow rules for all: $25 ticket, $500 sleeve, locked floor 0.05 (never lower), no desk cash.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import kalshi_shadow_tower as engine  # noqa: E402

CACHE_DIR = os.path.join(HERE, "fifteen-twins-cache")
CACHE_SEC = 20.0
CHEAP_ASK = 0.20          # B1: asks under this need more edge
CHEAP_EXTRA_EDGE = 0.05   # B1: on top of the locked 0.05 floor
FLOOR = 0.05              # kalshi_btc15m and kalshi_commodity15m locked floors

BASES = {
    "more": ("more-15m-paper", "bot.py"),
    "btc": ("btc15m-signal", "btc15m_signal.py"),
    "commodity": ("commodity-15m-paper", "bot.py"),
}

# twin id -> settings. ``spec`` is passed to the engine; the rest shapes quotes.
TWINS = {
    "more-15m-longshot": {
        "family": "more", "idea": "B1",
        "spec": {"name": "More 15m long-shot bar", "max_open": 4, "max_edge": 0.20, "group_cap": 2,
                 "tape_check": True, "fee_per_order": True},
        "cheap_extra_edge": CHEAP_EXTRA_EDGE,
    },
    "more-15m-tp15": {
        "family": "more", "idea": "B5",
        "spec": {"name": "More 15m take-profit", "max_open": 4, "max_edge": 0.20, "group_cap": 2,
                 "tape_check": True, "fee_per_order": True, "take_profit": 0.15},
    },
    "btc15m-mirror": {
        "family": "btc", "idea": "control",
        "spec": {"name": "BTC 15m mirror", "max_open": 3, "extra_slots": 0, "take_profit": 0.15},
        "min_minutes": 10.0,
    },
    "btc15m-5min": {
        "family": "btc", "idea": "B3",
        "spec": {"name": "BTC 15m 5-minute rule", "max_open": 3, "extra_slots": 0, "take_profit": 0.15},
        "min_minutes": 5.0,
    },
    "btc15m-tape": {
        "family": "btc", "idea": "B4",
        "spec": {"name": "BTC 15m tape check", "max_open": 3, "extra_slots": 0, "take_profit": 0.15,
                 "tape_check": True, "fee_per_order": True},
        "min_minutes": 10.0,
    },
    "btc15m-tp10": {
        "family": "btc", "idea": "B5",
        "spec": {"name": "BTC 15m take-profit 10c", "max_open": 3, "extra_slots": 0, "take_profit": 0.10},
        "min_minutes": 10.0,
    },
    "commodity-15m-mirror": {
        "family": "commodity", "idea": "control",
        "spec": {"name": "Commodity 15m mirror", "max_open": 2, "extra_slots": 0, "group_cap": 1,
                 "group_cap_why": "one {group} bet open at a time"},
        "min_minutes": 8.0,
    },
    "commodity-15m-cap85": {
        "family": "commodity", "idea": "B2",
        "spec": {"name": "Commodity 15m 85c cap", "max_open": 2, "extra_slots": 0, "group_cap": 1,
                 "group_cap_why": "one {group} bet open at a time"},
        "min_minutes": 8.0, "ask_cap": 0.85,
    },
    "commodity-15m-tape": {
        "family": "commodity", "idea": "B4",
        "spec": {"name": "Commodity 15m tape check", "max_open": 2, "extra_slots": 0, "group_cap": 1,
                 "group_cap_why": "one {group} bet open at a time",
                 "tape_check": True, "fee_per_order": True},
        "min_minutes": 8.0,
    },
}


# ------------------------------------------------------------------ originals, read-only
_LOADED: dict = {}


def load_base(family: str, root: str | None = None):
    """Import an original tower's script under a private name. Its main() is never called.

    File paths it would write (open offsets, quote cache) are pointed at the twin cache.
    """
    root = root or HERE
    key = (family, root)
    if key in _LOADED:
        return _LOADED[key]
    folder, script = BASES[family]
    path = os.path.join(root, folder, script)
    spec = importlib.util.spec_from_file_location(f"_twin_base_{family}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    cache = os.path.join(root, "fifteen-twins-cache", family)
    os.makedirs(cache, exist_ok=True)
    seed = os.path.join(root, folder, "index_basis.json")
    mine = os.path.join(cache, "index_basis.json")
    if os.path.isfile(seed) and not os.path.exists(mine):
        try:
            shutil.copyfile(os.path.realpath(seed), mine)  # read the original, write only our copy
        except OSError:
            pass
    mod.HERE = cache                      # More / Commodity open-offset file lives here now
    if hasattr(mod, "_CACHE"):
        mod._CACHE = os.path.join(cache, "quote_cache.json")   # BTC GET cache
    if hasattr(mod, "ACCOUNT"):
        mod.ACCOUNT = os.path.join(cache, "never_used_account.json")
    if hasattr(mod, "BUY_INTENT"):
        mod.BUY_INTENT = os.path.join(cache, "never_used_buy_intent.json")
    if family == "commodity":
        mod.MIN_MINUTES_LEFT = 0           # the twin applies its own minutes rule
    _LOADED[key] = mod
    return mod


# ------------------------------------------------------------------ shared quote read
def _cache_path(family: str, root: str) -> str:
    return os.path.join(root, "fifteen-twins-cache", f"{family}_rows.json")


def shared_rows(family: str, reader, root: str | None = None, now_ts: float | None = None):
    """(rows, note) from one read shared by every twin of the family for CACHE_SEC seconds."""
    root = root or HERE
    now_ts = time.time() if now_ts is None else now_ts
    path = _cache_path(family, root)
    data = engine.read_json(path)
    if data and isinstance(data.get("rows"), list) and 0 <= now_ts - float(data.get("at") or 0) <= CACHE_SEC:
        return data["rows"], str(data.get("note") or "")
    rows, note = reader()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        engine.write_json(path, {"at": now_ts, "rows": rows, "note": note, "paper_only": True})
    except OSError:
        pass
    return rows, note


# ------------------------------------------------------------------ More 15m
def read_more(root: str | None = None):
    base = load_base("more", root)
    now = dt.datetime.now(dt.timezone.utc)
    quotes, note = base.model({}, now)
    return list(quotes or []), note


def more_quotes(twin: dict, rows: list[dict]) -> list[dict]:
    out = []
    extra = float(twin.get("cheap_extra_edge") or 0.0)
    for row in rows:
        quote = dict(row)
        ask = engine.num(quote.get("ask"))
        if extra > 0 and ask is not None and ask < CHEAP_ASK:
            quote["extra_edge"] = extra
            quote["extra_reason"] = f"ask under {int(CHEAP_ASK * 100)}c"
        out.append(quote)
    return out


# ------------------------------------------------------------------ BTC 15m
def _iso(when) -> str:
    return when.isoformat() if hasattr(when, "isoformat") else str(when or "")


def read_btc(root: str | None = None):
    """One BTC 15m read with BTC 15m's own gates, minus its 10-minute rule (each twin adds its own)."""
    import statistics

    base = load_base("btc", root)
    markets = base.kalshi_markets("KXBTC15M")
    if not markets:
        return [], "no open BTC 15-minute window"
    spots = base.spot_prices()
    if not spots:
        return [], "no BTC spot"
    price = statistics.mean(spots.values())
    coinbase_only = list(spots) == ["coinbase"]
    try:
        closes = [c for _, c in base.candles_1m()]
    except Exception:  # noqa: BLE001 - same as BTC 15m: sigma falls back
        closes = []
    try:
        dvol = base.dvol_latest()
    except Exception:  # noqa: BLE001
        dvol = None
    edge_buf = base.decide_floor(FLOOR)
    rows = []
    for m in markets:
        try:
            ev = base.evaluate_window(m, price, closes, dvol, coinbase_only, edge_buf, min_minutes_left=0)
        except Exception as exc:  # noqa: BLE001 - one window failing skips that window
            ev = {"side": "YES" if price > m["target"] else "NO", "p": None,
                  "reasons": [f"evaluate failed ({type(exc).__name__})"]}
        side = str(ev.get("side") or "YES").lower()
        other = "no" if side == "yes" else "yes"
        p = ev.get("p")
        rows.append({
            "ticker": m["ticker"], "event": m["ticker"], "close": _iso(m["close_time"]),
            "side": side, "fair": None if p is None else round(float(p), 4),
            "ask": ev.get("ask") if ev.get("ask") is not None else m.get(f"{side}_ask"),
            "bid": ev.get("bid") if ev.get("bid") is not None else m.get(f"{side}_bid"),
            "other_ask": m.get(f"{other}_ask"), "other_bid": m.get(f"{other}_bid"),
            "lane": ev.get("lane") or "", "reasons": [str(r) for r in ev.get("reasons") or []],
            "why": (f"BTC {price:,.0f} vs target {float(m['target']):,.0f}, "
                    f"z {float(ev.get('z') or 0):.2f}, p {float(p or 0):.3f}") if p is not None else "",
            "label": f"BTC 15m up by {m['close_time'].strftime('%H:%M')} UTC",
        })
    return rows, ""


# ------------------------------------------------------------------ Commodity 15m
def read_commodity(root: str | None = None):
    """One Commodity 15m read with its own gates, minus its 8-minute rule (each twin adds its own)."""
    base = load_base("commodity", root)
    spots = base.spots_by_series()
    if not spots:
        return [], "no index feed"
    windows, failed = [], []
    for series in base.SERIES:
        spot = spots.get(series)
        if spot is None:
            continue
        try:
            for m in base.list_open(series, limit=3):
                windows.append((series, base.anchored_spot(series, spot, m), m))
        except Exception:  # noqa: BLE001
            failed.append(series)
    jobs = []
    for _series, spot, m in windows:
        side0 = "YES" if float(spot) > float(m["target"]) else "NO"
        ask0 = m["yes_ask"] if side0 == "YES" else m["no_ask"]
        if ask0 is not None:
            jobs.append((str(m["ticker"]), side0, float(ask0)))
    books, book_errs = base.prefetch_commodity_books(jobs) if jobs else ({}, {})
    edge_buf = base.decide_floor(FLOOR)
    rows = []
    for series, spot, m in windows:
        tick = str(m["ticker"])
        side_u = "YES" if float(spot) > float(m["target"]) else "NO"
        if tick in book_errs or tick not in books:
            ev = {"side": side_u, "p": None, "reasons": [f"orderbook failed ({book_errs.get(tick, 'missing')})"]}
        else:
            try:
                ev = base.evaluate(m, spot, edge_buf, book=books[tick])
            except Exception as exc:  # noqa: BLE001
                ev = {"side": side_u, "p": None, "reasons": [f"evaluate failed ({type(exc).__name__})"]}
        side = str(ev.get("side") or side_u).lower()
        other = "no" if side == "yes" else "yes"
        p = ev.get("p")
        label = series.replace("KX", "").replace("15M", "").title()
        rows.append({
            "ticker": tick, "event": tick, "close": _iso(m["close_time"]), "series": series,
            "group": base.series_family(series),
            "side": side, "fair": None if p is None else round(float(p), 4),
            "ask": m.get(f"{side}_ask"), "bid": m.get(f"{side}_bid"),
            "other_ask": m.get(f"{other}_ask"), "other_bid": m.get(f"{other}_bid"),
            "lane": ev.get("lane") or "", "reasons": [str(r) for r in ev.get("reasons") or []],
            "why": (f"{label} {float(spot):.5g} vs target {float(m['target']):.5g}, "
                    f"z {float(ev.get('z') or 0):.2f}, p {float(p or 0):.3f}") if p is not None else "",
            "label": f"{label} 15m up by {m['close_time'].strftime('%H:%M')} UTC",
        })
    note = ("skipped " + ", ".join(failed)) if failed else ""
    return rows, note


# ------------------------------------------------------------------ rows -> engine quotes
def window_quotes(twin: dict, rows: list[dict], now: dt.datetime) -> list[dict]:
    """Both sides of every window. The model side may buy; the other side is only for exits."""
    out = []
    min_minutes = float(twin.get("min_minutes") or 0.0)
    ask_cap = twin.get("ask_cap")
    speed_extra = 0.02
    for row in rows:
        try:
            close = dt.datetime.fromisoformat(str(row.get("close")).replace("Z", "+00:00"))
        except ValueError:
            continue
        minutes = (close - now).total_seconds() / 60.0
        if minutes <= 0:
            continue
        fair = engine.num(row.get("fair"))
        side = str(row.get("side") or "yes")
        reasons = list(row.get("reasons") or [])
        if minutes < min_minutes:
            reasons.append(f"only {minutes:.1f} min left (< {min_minutes:g})")
        ask = engine.num(row.get("ask"))
        if ask_cap is not None and ask is not None and ask > float(ask_cap) + 1e-9:
            reasons.append(f"ask {ask:.2f} over the {int(float(ask_cap) * 100)}c cap")
        base = {"ticker": row["ticker"], "event": row.get("event") or row["ticker"],
                "label": row.get("label") or row["ticker"], "why": row.get("why") or ""}
        if row.get("group"):
            base["group"] = row["group"]
        quote = dict(base, side=side, fair=fair, ask=ask, bid=engine.num(row.get("bid")))
        if row.get("lane") == "speed":
            quote["extra_edge"] = speed_extra
            quote["extra_reason"] = "speed lane"
        if reasons:
            quote["log_only"] = True
            quote["log_reason"] = "; ".join(reasons[:4])
        out.append(quote)
        other = "no" if side == "yes" else "yes"
        out.append(dict(base, side=other, fair=None if fair is None else round(1.0 - fair, 4),
                        ask=engine.num(row.get("other_ask")), bid=engine.num(row.get("other_bid")),
                        log_only=True, log_reason="not the model side",
                        exit_now=f"model now on {side.upper()}" if fair is not None else ""))
    return out


READERS = {"more": read_more, "btc": read_btc, "commodity": read_commodity}


def twin_spec(twin_id: str) -> dict:
    twin = TWINS[twin_id]
    spec = dict(twin["spec"])
    spec["id"] = twin_id
    spec["floor"] = FLOOR
    return spec


def make_model(twin_id: str, root: str | None = None, reader=None):
    twin = TWINS[twin_id]
    family = twin["family"]
    reader = reader or (lambda: READERS[family](root))

    def model(cfg, now):
        rows, note = shared_rows(family, reader, root)
        if family == "more":
            return more_quotes(twin, rows), note
        quotes = window_quotes(twin, rows, now)
        if not quotes and not note:
            note = "no open 15-minute window"
        return quotes, note

    return model


def main(twin_id: str, folder: str, argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    spec = twin_spec(twin_id)
    if "--reset" in argv:
        return engine.reset(spec, folder)
    return engine.run_tower(spec, folder, make_model(twin_id, os.path.dirname(folder)))
