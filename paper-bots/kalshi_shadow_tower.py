"""Shared engine for the new Kalshi shadow towers. Paper only. Shadow only.

Each new tower brings only its model: a function that returns quote rows
``{ticker, event, side, fair, ask, bid, label, why}``. This engine does the rest
the same way for every tower, cloned from the Fed Watch rails:

* **Fee-aware entry:** edge = fair − ask − Kalshi taker fee
  (``ceil(0.07·p·(1−p))`` per contract). It buys only when the edge is at least
  the tower's locked venue floor. The floor can be raised in config, never lowered.
* **Fixed ticket:** $25 in whole contracts from a $500 shadow sleeve. It spends
  no desk cash and takes no tower risk share.
* **Log-only rows:** a quote with ``log_only`` is priced and logged but never
  bought (for example, a weather bracket before the afternoon lock).
* **Trust cap:** a tower may set ``max_edge``. An edge above it is logged
  but not bought; it usually means a bad input, not a free lunch.
* **Limits:** max open positions, one position per event, never both sides of
  one ticker, ask between 5¢ and 95¢ by default, and at most one new buy per check.
* **Exits (partial quality):**
  - Model flip: sell at the bid when bid − fee beats the model's fair by a margin.
  - Settle backstop: $1 per contract when Kalshi's result matches our side.
* **Desk gate:** ``DESK_BLOCK_ENTRIES=1`` stops new buys, but exits still run.
* **Research log:** every check appends fair vs ask rows to ``research.jsonl``
  (rotated at about 4 MB). That log is what the calibration lab scores.

Output follows the desk card format: SETTLE / EXIT / SIGNAL / CARD lines, then
"no trade" when nothing was bought.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
STAKE_USD = 25.0
STARTER_CASH = 500.0
RESEARCH_MAX_BYTES = 4_000_000
RESEARCH_ROWS = 60


# ------------------------------------------------------------------ config + math
def locked_cfg(spec: dict, raw: dict | None = None) -> dict:
    cfg = dict(raw or {})
    lock = float(spec["floor"])
    try:
        floor = float(cfg.get("venue_min_edge") or lock)
    except (TypeError, ValueError):
        floor = lock
    cfg["venue_min_edge"] = max(lock, floor)
    cfg["paper_only"] = True
    cfg["live_orders"] = False
    cfg["shadow_only"] = True
    cfg["stake_usd"] = float(cfg.get("stake_usd") or STAKE_USD)
    cfg["starter_cash"] = float(cfg.get("starter_cash") or STARTER_CASH)
    cfg["max_open"] = int(cfg.get("max_open") or spec.get("max_open") or 1)
    cfg["min_ask"] = max(0.01, float(cfg.get("min_ask") or spec.get("min_ask") or 0.05))
    cfg["max_ask"] = min(0.99, float(cfg.get("max_ask") or spec.get("max_ask") or 0.95))
    cfg["flip_margin"] = float(cfg.get("flip_margin") or 0.02)
    cap = spec.get("max_edge")
    cfg["max_edge"] = None if cap is None else float(cap)
    return cfg


def fee(price: float) -> float:
    """Kalshi taker fee per $1 contract at ``price`` dollars, rounded up to the cent."""
    p = float(price)
    if not (0.0 < p < 1.0) or not math.isfinite(p):
        return 0.0
    return math.ceil(round(0.07 * p * (1.0 - p) * 100, 6)) / 100.0


def num(value):
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) else None


def decide(quote: dict, cfg: dict) -> dict:
    """One fee-aware buy/skip decision for one side of one Kalshi market."""
    fair = num(quote.get("fair"))
    ask = num(quote.get("ask"))
    row = {
        "ticker": str(quote.get("ticker") or ""),
        "event": str(quote.get("event") or ""),
        "side": str(quote.get("side") or "yes").lower(),
        "label": str(quote.get("label") or quote.get("ticker") or ""),
        "fair": None if fair is None else round(fair, 4),
        "ask": ask,
        "bid": num(quote.get("bid")),
        "fee": None,
        "edge": None,
        "floor": cfg["venue_min_edge"],
        "action": "skip",
        "reason": "",
        "why": str(quote.get("why") or ""),
    }
    if fair is None or ask is None:
        row["reason"] = "need fair + ask"
        return row
    if quote.get("log_only"):
        cost = fee(ask) if 0.0 < ask < 1.0 else 0.0
        row["fee"] = round(cost, 4)
        row["edge"] = round(fair - ask - cost, 4)
        row["reason"] = str(quote.get("log_reason") or "logged for calibration; not a buy window")
        return row
    if not (0.0 < fair < 1.0):
        row["reason"] = "fair out of range"
        return row
    if not (cfg["min_ask"] <= ask <= cfg["max_ask"]):
        row["reason"] = f"ask {ask:.2f} outside {cfg['min_ask']:.2f}-{cfg['max_ask']:.2f}"
        return row
    cost = fee(ask)
    edge = fair - ask - cost
    row["fee"] = round(cost, 4)
    row["edge"] = round(edge, 4)
    if edge + 1e-12 < float(cfg["venue_min_edge"]):
        row["reason"] = (f"edge {edge:.3f} < floor {cfg['venue_min_edge']:g} "
                         f"(fair {fair:.3f} ask {ask:.2f} fee {cost:.2f})")
        return row
    if cfg.get("max_edge") is not None and edge > float(cfg["max_edge"]) + 1e-12:
        row["reason"] = (f"edge {edge:.3f} over trust cap {cfg['max_edge']:g}: "
                         "model and market disagree on inputs; logged, not bought")
        return row
    row["action"] = "buy"
    row["reason"] = f"fair {fair:.3f} ask {ask:.2f} fee {cost:.2f} edge {edge:.3f}"
    return row


# ------------------------------------------------------------------ state
def empty_state(cfg: dict) -> dict:
    return {"cash": float(cfg["starter_cash"]), "open": [], "closed": [], "checks": 0,
            "paper_only": True, "shadow_only": True, "live_orders": False}


def read_json(path: str):
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def write_json(path: str, data: dict) -> None:
    """Atomic save. On Railway the desk links paper_account.json to the volume:
    follow the link so the save lands there. Replacing the link itself would let
    the desk's next re-link put the old volume copy back and lose this save."""
    if os.path.islink(path):
        path = os.path.realpath(path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")
    os.replace(tmp, path)


def public_json(url: str, headers: dict | None = None, timeout: float = 12):
    """GET JSON through public_http (Kalshi URLs share the gateway)."""
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    import public_http
    return json.loads(public_http.read(url, headers=headers, timeout=timeout, tries=2).decode("utf-8"))


def kalshi_market(ticker: str) -> dict:
    data = public_json(f"{KALSHI}/markets/{ticker}", timeout=10)
    return (data or {}).get("market") or {}


def kalshi_open_markets(series: str, limit: int = 200) -> list[dict]:
    data = public_json(f"{KALSHI}/markets?series_ticker={series}&status=open&limit={int(limit)}")
    rows = (data or {}).get("markets") or []
    return [row for row in rows if isinstance(row, dict)]


def sides(market: dict) -> list[dict]:
    """YES and NO ask/bid in dollars for one Kalshi market row."""
    out = []
    for side in ("yes", "no"):
        out.append({
            "ticker": str(market.get("ticker") or ""),
            "event": str(market.get("event_ticker") or ""),
            "side": side,
            "ask": num(market.get(f"{side}_ask_dollars")),
            "bid": num(market.get(f"{side}_bid_dollars")),
        })
    return out


def settle_open(state: dict, now: dt.datetime, fetch=None) -> list[dict]:
    fetch = fetch or kalshi_market
    closed, keep = [], []
    for pos in state.get("open") or []:
        try:
            market = fetch(str(pos.get("ticker") or ""))
        except Exception:  # noqa: BLE001 - try again next check
            keep.append(pos)
            continue
        result = str((market or {}).get("result") or "").lower()
        if result not in ("yes", "no"):
            keep.append(pos)
            continue
        contracts = int(pos.get("contracts") or 0)
        payout = float(contracts) if result == pos.get("side") else 0.0
        row = dict(pos, result=result, payout=round(payout, 2),
                   pnl=round(payout - float(pos.get("cost") or 0), 2),
                   closed=now.isoformat(timespec="seconds"), exit="settled")
        state["cash"] = round(float(state.get("cash") or 0) + payout, 4)
        state.setdefault("closed", []).append(row)
        closed.append(row)
    state["open"] = keep
    return closed


def model_flips(state: dict, quotes: list[dict], now: dt.datetime, margin: float) -> list[dict]:
    """Sell a held side at the bid when bid − fee beats the model's fair by ``margin``."""
    by_key = {(q.get("ticker"), q.get("side")): q for q in quotes}
    sold, keep = [], []
    for pos in state.get("open") or []:
        quote = by_key.get((pos.get("ticker"), pos.get("side")))
        fair = num((quote or {}).get("fair"))
        bid = num((quote or {}).get("bid"))
        if fair is None or bid is None or not (0.0 < bid < 1.0):
            keep.append(pos)
            continue
        net = bid - fee(bid)
        if net <= fair + margin:
            keep.append(pos)
            continue
        contracts = int(pos.get("contracts") or 0)
        proceeds = round(contracts * net, 2)
        row = dict(pos, exit="model-flip", exit_bid=bid, exit_fair=round(fair, 4),
                   payout=proceeds, pnl=round(proceeds - float(pos.get("cost") or 0), 2),
                   closed=now.isoformat(timespec="seconds"))
        state["cash"] = round(float(state.get("cash") or 0) + proceeds, 4)
        state.setdefault("closed", []).append(row)
        sold.append(row)
    state["open"] = keep
    return sold


def _append_research(tower: str, now: dt.datetime, decisions: list[dict], note: str) -> None:
    path = os.path.join(tower, "research.jsonl")
    try:
        if os.path.getsize(path) > RESEARCH_MAX_BYTES:
            # On the desk the log is a link to the /data volume: rotate the real file,
            # so the link (and research.jsonl.1's link) keep pointing at the volume.
            real = os.path.realpath(path)
            os.replace(real, os.path.join(os.path.dirname(real), "research.jsonl.1"))
    except OSError:
        pass
    ranked = sorted(decisions, key=lambda d: -(d.get("edge") if d.get("edge") is not None else -9))
    row = {"at": now.isoformat(timespec="seconds"), "paper_only": True, "shadow_only": True,
           "note": note, "n": len(decisions), "decisions": ranked[:RESEARCH_ROWS]}
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


# ------------------------------------------------------------------ one check
def run_tower(spec: dict, tower: str, model, *, now: dt.datetime | None = None,
              fetch=None, quotes: list | None = None) -> int:
    """One check. ``model(cfg, now) -> (quotes, note)``. Returns 0 (a skip is not a failure)."""
    os.makedirs(tower, exist_ok=True)
    cfg = locked_cfg(spec, read_json(os.path.join(tower, "config.json")))
    now = now or dt.datetime.now(dt.timezone.utc)
    acct = os.path.join(tower, "paper_account.json")
    state = read_json(acct) or empty_state(cfg)
    # The desk may seed a bare account ({"paper_only": true}) before the first run.
    for key, value in empty_state(cfg).items():
        state.setdefault(key, value)
    state.setdefault("open", [])
    state.setdefault("closed", [])
    state.update({"paper_only": True, "shadow_only": True, "live_orders": False})
    settled = settle_open(state, now, fetch=fetch)
    note = ""
    if quotes is None:
        try:
            quotes, note = model(cfg, now)
        except Exception as exc:  # noqa: BLE001 - a failed read is a skip, never a guess
            quotes, note = [], f"read failed ({type(exc).__name__}); waiting"
    quotes = list(quotes or [])
    flipped = model_flips(state, quotes, now, cfg["flip_margin"])
    decisions = [decide(q, cfg) for q in quotes]
    held_tickers = {p.get("ticker") for p in state["open"]}
    held_events = {p.get("event") for p in state["open"] if p.get("event")}
    blocked = os.environ.get("DESK_BLOCK_ENTRIES") == "1"
    bought = None
    for d in sorted(decisions, key=lambda d: -(d.get("edge") if d.get("edge") is not None else -9)):
        if d["action"] != "buy":
            continue
        why = ""
        if blocked:
            why = "desk entry gate"
        elif bought is not None:
            why = "one new buy per check"
        elif d["ticker"] in held_tickers:
            why = "already holding this market"
        elif d["event"] and d["event"] in held_events:
            why = "already holding this event"
        elif len(state["open"]) >= cfg["max_open"]:
            why = "max open"
        per = float(d["ask"]) + float(d["fee"] or 0)
        contracts = int(cfg["stake_usd"] // per) if per > 0 else 0
        if not why and contracts < 1:
            why = "ticket buys no contract"
        cost = round(contracts * per, 2)
        if not why and float(state.get("cash") or 0) + 1e-9 < cost:
            why = "shadow cash below ticket"
        if why:
            d["action"], d["reason"] = "skip", why
            continue
        state["cash"] = round(float(state["cash"]) - cost, 4)
        state["open"].append({
            "ticker": d["ticker"], "event": d["event"], "side": d["side"], "label": d["label"],
            "contracts": contracts, "ask": d["ask"], "fee": d["fee"], "cost": cost,
            "fair": d["fair"], "edge": d["edge"], "why": d["why"],
            "opened": now.isoformat(timespec="seconds"),
            "paper_only": True, "shadow_only": True,
            "exit_plan": {"kind": "model-flip+settle", "flip_margin": cfg["flip_margin"]},
        })
        bought = d
    state["checks"] = int(state.get("checks") or 0) + 1
    state["last_check"] = now.isoformat(timespec="seconds")
    write_json(acct, state)
    try:
        _append_research(tower, now, decisions, note)
    except OSError:
        pass
    name = spec["name"]
    for row in settled:
        print(f"SETTLE: {row['label']} {row['side'].upper()} {row['result']} pnl {row['pnl']:+.2f}")
    for row in flipped:
        print(f"EXIT: model-flip {row['label']} {row['side'].upper()} at {row['exit_bid']:.2f} "
              f"pnl {row['pnl']:+.2f}")
    priced = sum(1 for d in decisions if d.get("edge") is not None)
    if bought:
        print(f"SIGNAL: BUY {bought['label']} {bought['side'].upper()} {bought['reason']}")
        print(f"CARD: paper buy {bought['label']} {bought['side'].upper()} at {bought['ask']:.2f} "
              f"({name}, shadow). {bought['why']}".rstrip())
        return 0
    if not decisions:
        text = note or "no market priced this check"
        print(f"SIGNAL: SKIP {text}")
        print(f"CARD: {name}: {text}. Nothing invented.")
        print("no trade")
        return 0
    best = max(decisions, key=lambda d: d.get("edge") if d.get("edge") is not None else -9)
    print(f"SIGNAL: SKIP {best['label']} {best['side'].upper()} {best['reason']}")
    print(f"CARD: {name}: {priced} sides priced, best {best['label']} {best['side'].upper()}: "
          f"{best['reason']}" + (f". {note}" if note else ""))
    print("no trade")
    return 0


def reset(spec: dict, tower: str) -> int:
    cfg = locked_cfg(spec, read_json(os.path.join(tower, "config.json")))
    write_json(os.path.join(tower, "paper_account.json"), empty_state(cfg))
    print("reset paper account")
    return 0
