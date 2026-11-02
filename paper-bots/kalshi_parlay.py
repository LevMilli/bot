"""
kalshi_parlay.py — paper multi-leg parlays for late (≤5m) crypto Kalshi entries.

Staff rule (screenshots):
  • Confident early in the 15m window → single paper trade.
  • Too volatile → hold, keep history, then at ~5 minutes left enter a parlay
    (paper COMBO of legs that each still clear fee-aware guidelines).

No live Kalshi combo API calls — paper ledger only.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import uuid
from typing import Any

PARLAY_FILE = "paper_parlays.json"


def parlay_path(root: str | None, account_dir: str | None = None) -> str:
    if account_dir:
        return os.path.join(account_dir, PARLAY_FILE)
    base = root or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "btc15m-signal", PARLAY_FILE)


def load_parlays(path: str) -> dict:
    if not os.path.exists(path):
        return {"paper_only": True, "open": [], "closed": []}
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            return {"paper_only": True, "open": [], "closed": []}
    except (OSError, json.JSONDecodeError):
        return {"paper_only": True, "open": [], "closed": []}
    data.setdefault("paper_only", True)
    data.setdefault("open", [])
    data.setdefault("closed", [])
    return data


def save_parlays(path: str, state: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    state = dict(state)
    state["paper_only"] = True
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
        handle.write("\n")
    os.replace(tmp, path)


def classify_regime(
    *,
    minutes_left: float,
    model_p: float | None,
    z: float | None,
    cushion: float | None,
    min_cushion: float,
    min_z: float,
    min_p: float = 0.80,
    early_min: float = 10.0,
    parlay_max: float = 5.0,
    parlay_min: float = 1.0,
) -> str:
    """
    confident_early | volatile_hold | parlay_window | too_late | unknown
    """
    if minutes_left < parlay_min:
        return "too_late"
    p = float(model_p) if model_p is not None else 0.0
    zz = float(z) if z is not None else 0.0
    c = float(cushion) if cushion is not None else 0.0
    strong = p >= max(min_p, 0.85) and zz >= (min_z + 0.15) and c >= (min_cushion * 1.25)
    ok = p >= min_p and zz >= min_z and c >= min_cushion
    volatile = (not strong) and (c < min_cushion * 1.5 or zz < min_z + 0.2 or p < 0.88)

    if minutes_left >= early_min:
        if strong or (ok and not volatile):
            return "confident_early"
        return "volatile_hold"
    if minutes_left <= parlay_max:
        return "parlay_window"
    # Between 5 and 10 minutes: keep collecting unless rock-solid.
    if strong:
        return "confident_early"
    return "volatile_hold"


def open_paper_parlay(
    path: str,
    legs: list[dict],
    *,
    stake_dollars: float,
    note: str = "",
) -> dict | None:
    """
    Record a paper parlay. Each leg needs ticker, side, ask, fee, fair, close_time.
    Stake is split equally across legs for cash accounting (paper simplification);
    payout rule: all legs must win or parlay loses (Kalshi-style combo intuition).
    """
    if len(legs) < 2:
        return None
    state = load_parlays(path)
    pid = f"parlay-{uuid.uuid4().hex[:10]}"
    opened = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    per = float(stake_dollars) / len(legs)
    cooked = []
    cost = 0.0
    for leg in legs:
        ask = float(leg["ask"])
        fee = float(leg.get("fee") or 0)
        unit = ask + fee
        contracts = int(per // unit) if unit > 0 else 0
        if contracts < 1:
            return None
        leg_cost = round(contracts * unit, 2)
        cost += leg_cost
        cooked.append({
            "ticker": leg["ticker"],
            "side": str(leg["side"]).upper(),
            "ask": ask,
            "fee": fee,
            "contracts": contracts,
            "cost": leg_cost,
            "fair_at_entry": leg.get("fair"),
            "close_time": leg.get("close_time"),
            "series": leg.get("series") or "",
        })
    row = {
        "parlay_id": pid,
        "opened": opened,
        "note": (note or "")[:240],
        "stake": round(cost, 2),
        "legs": cooked,
        "paper_only": True,
        "status": "open",
    }
    state.setdefault("open", []).append(row)
    save_parlays(path, state)
    return row


def parlay_summary(path: str) -> dict:
    state = load_parlays(path)
    return {
        "paper_only": True,
        "open_count": len(state.get("open") or []),
        "closed_count": len(state.get("closed") or []),
        "open": list(state.get("open") or [])[-10:],
        "recent_closed": list(state.get("closed") or [])[-10:],
    }
