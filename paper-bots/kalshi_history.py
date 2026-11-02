"""
kalshi_history.py — durable quote/history snapshots for desk crypto Kalshi markets.

Series (from staff screenshots):
  KXBTC15M / KXETH15M / KXBTCD
  KXPALLADIUM15M, KXNATGAS15M, KXCOPPER15M, KXBRENT15M, KXWTI15M, KXSILVER15M
  (+ gold/platinum when listed)

Paper / read-only. Appends snapshots so the desk can wait out volatility and
re-check confidence before a late (≤5m) parlay.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any

HISTORY_NAME = "kalshi_crypto_history.json"
MAX_SNAPSHOTS = 4000
CRYPTO_SERIES = (
    "KXBTC15M",
    "KXETH15M",
    "KXBTCD",
    "KXPALLADIUM15M",
    "KXNATGAS15M",
    "KXCOPPER15M",
    "KXBRENT15M",
    "KXWTI15M",
    "KXSILVER15M",
    "KXGOLD15M",
    "KXPLATINUM15M",
)


def history_path(root: str | None = None) -> str:
    base = root or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, HISTORY_NAME)


def _empty() -> dict:
    return {
        "paper_only": True,
        "series": list(CRYPTO_SERIES),
        "snapshots": [],
        "by_series": {s: {"n": 0, "last_at": None} for s in CRYPTO_SERIES},
        "holds": [],  # volatile windows waiting for ≤5m parlay
    }


def load_history(root: str | None = None) -> dict:
    path = history_path(root)
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
    if not isinstance(base.get("snapshots"), list):
        base["snapshots"] = []
    if not isinstance(base.get("by_series"), dict):
        base["by_series"] = _empty()["by_series"]
    if not isinstance(base.get("holds"), list):
        base["holds"] = []
    for s in CRYPTO_SERIES:
        base["by_series"].setdefault(s, {"n": 0, "last_at": None})
    return base


def save_history(state: dict, root: str | None = None) -> None:
    path = history_path(root)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    snaps = list(state.get("snapshots") or [])
    if len(snaps) > MAX_SNAPSHOTS:
        snaps = snaps[-MAX_SNAPSHOTS:]
    state = dict(state)
    state["snapshots"] = snaps
    state["paper_only"] = True
    holds = list(state.get("holds") or [])
    if len(holds) > 200:
        holds = holds[-200:]
    state["holds"] = holds
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
        handle.write("\n")
    os.replace(tmp, path)


def record_snapshot(
    root: str | None,
    *,
    series: str,
    ticker: str,
    spot: float | None,
    target: float | None,
    side: str | None,
    yes_ask: float | None,
    no_ask: float | None,
    model_p: float | None,
    minutes_left: float | None,
    regime: str,
    note: str = "",
    extra: dict | None = None,
) -> dict:
    """Append one market snapshot. regime: confident | volatile | skip | parlay_ready."""
    state = load_history(root)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    row: dict[str, Any] = {
        "at": now,
        "series": series,
        "ticker": ticker,
        "spot": spot,
        "target": target,
        "side": side,
        "yes_ask": yes_ask,
        "no_ask": no_ask,
        "model_p": None if model_p is None else round(float(model_p), 4),
        "minutes_left": None if minutes_left is None else round(float(minutes_left), 2),
        "regime": regime,
        "note": (note or "")[:200],
    }
    if extra:
        row["extra"] = extra
    state.setdefault("snapshots", []).append(row)
    bucket = state.setdefault("by_series", {}).setdefault(series, {"n": 0, "last_at": None})
    bucket["n"] = int(bucket.get("n") or 0) + 1
    bucket["last_at"] = now
    save_history(state, root)
    return row


def mark_hold(root: str | None, ticker: str, side: str, reason: str, minutes_left: float) -> None:
    state = load_history(root)
    state.setdefault("holds", []).append({
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ticker": ticker,
        "side": side,
        "reason": reason[:200],
        "minutes_left": round(float(minutes_left), 2),
        "status": "waiting_parlay",
    })
    save_history(state, root)


def clear_hold(root: str | None, ticker: str) -> None:
    state = load_history(root)
    holds = []
    for row in state.get("holds") or []:
        if row.get("ticker") == ticker and row.get("status") == "waiting_parlay":
            row = dict(row)
            row["status"] = "cleared"
        holds.append(row)
    state["holds"] = holds
    save_history(state, root)


def snapshots_for(root: str | None, ticker: str, limit: int = 12) -> list[dict]:
    state = load_history(root)
    rows = [r for r in state.get("snapshots") or [] if r.get("ticker") == ticker]
    return rows[-limit:]


def side_consistency(root: str | None, ticker: str, need: int = 3) -> str | None:
    """If last `need` snapshots agree on side, return that side; else None."""
    rows = snapshots_for(root, ticker, limit=need)
    if len(rows) < need:
        return None
    sides = [str(r.get("side") or "").upper() for r in rows[-need:]]
    if sides and all(s == sides[0] and s in ("YES", "NO") for s in sides):
        return sides[0]
    return None


def snapshot_open_15m_series(root: str | None, series_list: tuple | list | None = None, limit_per: int = 3) -> int:
    """Light history pass: quote nearest open markets for commodity/crypto 15m series."""
    import urllib.request

    base = "https://api.elections.kalshi.com/trade-api/v2"
    ua = {"User-Agent": "paper-bot/1.0 (history)"}
    watched = tuple(series_list) if series_list is not None else CRYPTO_SERIES
    n = 0

    def _get(path: str) -> dict:
        req = urllib.request.Request(base + path, headers=ua)
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.load(resp)

    for series in watched:
        if series == "KXBTCD":
            continue  # ladder handled separately
        try:
            d = _get(f"/markets?series_ticker={series}&status=open&limit={max(1, int(limit_per))}")
        except Exception:
            continue
        for m in d.get("markets") or []:
            try:
                strike = float(m.get("floor_strike"))
            except (TypeError, ValueError):
                strike = None
            yes_ask = m.get("yes_ask_dollars")
            no_ask = m.get("no_ask_dollars")
            try:
                yes_ask_f = float(yes_ask) if yes_ask not in (None, "") else None
            except (TypeError, ValueError):
                yes_ask_f = None
            try:
                no_ask_f = float(no_ask) if no_ask not in (None, "") else None
            except (TypeError, ValueError):
                no_ask_f = None
            close = m.get("close_time")
            min_left = None
            if close:
                try:
                    import datetime as dt
                    when = dt.datetime.fromisoformat(str(close).replace("Z", "+00:00"))
                    min_left = (when - dt.datetime.now(dt.timezone.utc)).total_seconds() / 60
                except Exception:
                    min_left = None
            # Crude vol tag from mid-ask: near 50¢ ⇒ volatile coin-flip.
            regime = "ladder_watch"
            if yes_ask_f is not None and 0.40 <= yes_ask_f <= 0.60:
                regime = "volatile_hold"
            elif yes_ask_f is not None and (yes_ask_f >= 0.85 or yes_ask_f <= 0.15):
                regime = "confident_early"
            record_snapshot(
                root,
                series=series,
                ticker=str(m.get("ticker") or ""),
                spot=None,
                target=strike,
                side=None,
                yes_ask=yes_ask_f,
                no_ask=no_ask_f,
                model_p=None,
                minutes_left=min_left,
                regime=regime,
                note=str(m.get("title") or "")[:120],
            )
            n += 1
    return n


def history_summary(root: str | None = None) -> dict:
    state = load_history(root)
    snaps = list(state.get("snapshots") or [])
    holds = [h for h in (state.get("holds") or []) if h.get("status") == "waiting_parlay"]
    return {
        "paper_only": True,
        "tracked_series": list(CRYPTO_SERIES),
        "snapshot_count": len(snaps),
        "by_series": state.get("by_series") or {},
        "open_holds": holds[-20:],
        "recent": snaps[-30:],
    }
