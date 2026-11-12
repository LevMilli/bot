"""Settlement auditor: recheck closed paper trades against Kalshi's official result.

In plain terms: every paper trade that was held to the end records which way
the market settled ("yes" or "no") and what it paid. Once a day this asks
Kalshi for the real result of each of those markets and flags any trade where

* the recorded result is not Kalshi's result, or
* the payout does not match (our side won but paid $0, or lost but paid out).

Sold trades (model flips, stops) are skipped: they never reached settlement.
Each trade is checked once; a mismatch stays on the list until it is fixed.
Pure logic here; the network read is passed in.
"""
from __future__ import annotations

import datetime as dt
import json
import os

MAX_READS = 40            # Kalshi market reads per run (shared gateway)
PAY_TOL = 0.02


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def trade_key(bot: str, row: dict) -> str:
    when = row.get("closed") or row.get("settled_at") or row.get("day") or ""
    return f"{bot}|{row.get('ticker')}|{row.get('side')}|{when}"


def settled_rows(bot: str, state: dict) -> list[dict]:
    """Closed Kalshi rows held to settlement: ticker KX..., side yes/no, result yes/no."""
    out = []
    for row in (state or {}).get("closed") or []:
        if not isinstance(row, dict):
            continue
        ticker, side = str(row.get("ticker") or ""), str(row.get("side") or "").lower()
        result = str(row.get("result") or "").lower()
        if not ticker.startswith("KX") or side not in ("yes", "no") or result not in ("yes", "no"):
            continue
        if str(row.get("status") or "").lower() == "sold":
            continue
        out.append(row)
    return out


def check(row: dict, official: str) -> str:
    """'' when the row agrees with Kalshi, else a short plain reason."""
    side = str(row.get("side")).lower()
    recorded = str(row.get("result")).lower()
    if official != recorded:
        return f"recorded {recorded}, Kalshi says {official}"
    contracts = _num(row.get("contracts"))
    payout = _num(row.get("payout"))
    if contracts is None or payout is None:
        return ""
    want = contracts if side == official else 0.0
    if abs(payout - want) > PAY_TOL:
        return f"paid ${payout:.2f}, should be ${want:.2f}"
    return ""


def load_states(root: str, specs) -> dict:
    """{bot id: state dict} for every desk bot with a readable JSON state file."""
    out = {}
    for spec in specs:
        folder, name = spec.get("folder"), spec.get("state")
        if not folder or not name or spec.get("research"):
            continue
        path = os.path.join(root, folder, name)
        try:
            with open(path, encoding="utf-8") as fh:
                state = json.load(fh)
        except (OSError, ValueError):
            continue
        if isinstance(state, dict):
            out[str(spec["id"])] = state
    return out


def run(states: dict, prior: dict, fetch, now: dt.datetime, max_reads: int = MAX_READS) -> dict:
    """One audit pass. ``fetch(ticker) -> market dict``. Returns the new audit body."""
    checked = dict((prior or {}).get("checked") or {})
    mismatches = {m["key"]: m for m in (prior or {}).get("mismatches") or [] if isinstance(m, dict) and m.get("key")}
    pending, reads, cache, notes = 0, 0, {}, []
    totals = {}
    for bot, state in sorted(states.items()):
        rows = settled_rows(bot, state)
        totals[bot] = len(rows)
        for row in rows:
            key = trade_key(bot, row)
            if key in checked and key not in mismatches:
                continue
            ticker = str(row["ticker"])
            if ticker not in cache:
                if reads >= max_reads:
                    pending += 1
                    continue
                reads += 1
                try:
                    cache[ticker] = str((fetch(ticker) or {}).get("result") or "").lower()
                except Exception as exc:  # noqa: BLE001 - try again next run
                    cache[ticker] = None
                    notes.append(f"{ticker} read failed ({type(exc).__name__})")
            official = cache[ticker]
            if official not in ("yes", "no"):
                pending += 1
                continue
            problem = check(row, official)
            checked[key] = now.isoformat(timespec="seconds")
            if problem:
                mismatches[key] = {"key": key, "bot": bot, "ticker": ticker, "side": row.get("side"),
                                   "problem": problem, "pnl": row.get("pnl"),
                                   "found": mismatches.get(key, {}).get("found") or now.isoformat(timespec="seconds")}
            else:
                mismatches.pop(key, None)
    # forget checks for trades no longer on any book (account resets), keep the file small
    live = {trade_key(b, r) for b, s in states.items() for r in settled_rows(b, s)}
    checked = {k: v for k, v in checked.items() if k in live}
    mismatches = {k: v for k, v in mismatches.items() if k in live}
    return {"at": now.isoformat(timespec="seconds"), "paper_only": True, "research": True,
            "checked": checked, "mismatches": sorted(mismatches.values(), key=lambda m: m["key"]),
            "pending": pending, "reads": reads, "settled_rows": totals, "notes": notes[:10]}


def card(body: dict) -> str:
    n = len(body.get("checked") or {})
    bad = body.get("mismatches") or []
    head = f"{n} settled trades rechecked against Kalshi"
    if not bad:
        tail = "all match"
    else:
        first = bad[0]
        tail = f"{len(bad)} mismatch{'es' if len(bad) != 1 else ''} (first: {first['bot']} {first['ticker']}: {first['problem']})"
    more = f"; {body.get('pending')} waiting" if body.get("pending") else ""
    return f"{head}: {tail}{more}"
