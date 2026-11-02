"""
kalshi_history.py — durable quote/history snapshots for desk crypto Kalshi markets.

Series (from staff screenshots):
  KXBTC15M  — BTC 15-minute up/down
  KXETH15M  — ETH 15-minute up/down
  KXBTCD    — BTC price above/below ladder (e.g. 1am EST)

Paper / read-only. Appends snapshots so the desk can wait out volatility and
re-check confidence before a late (≤5m) parlay.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any

HISTORY_NAME = "kalshi_crypto_history.json"
MAX_SNAPSHOTS = 2500
CRYPTO_SERIES = ("KXBTC15M", "KXETH15M", "KXBTCD")


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
