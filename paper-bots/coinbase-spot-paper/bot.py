#!/usr/bin/env python3
"""Coinbase spot paper tower — shadow sleeve, public candles, no key.

The desk already trades BTC 15-minute Kalshi contracts. This tower does not
copy that book. It paper-trades Coinbase spot (ETH-USD, SOL-USD) only when a
15-minute move still clears costs:

    round trip = 2 * (US intro taker 0.90% + 0.10% slippage) = 2.00%
    expected capture = 25% of the last completed 15m move
    edge = expected capture - round trip
    buy only if the move is up, z >= 2, and edge >= locked floor 0.05

A normal bar is a few tenths of a percent, so edge is negative and the check
skips. That is the base, not a missed trade. BTC-USD is logged and never
bought. Shorts are refused (spot cash cannot short). Nothing here sends an
order.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import statistics
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DESK_ROOT = os.path.dirname(HERE)

LOCKED_FLOOR = 0.05
LOCKED_HAIRCUT_MAX = 0.25
LOCKED_TAKER_MIN = 0.009  # US Advanced intro taker, 16 Sep 2026 schedule
LOCKED_SLIP_MIN = 0.001
CANDLE_URL = "https://api.exchange.coinbase.com/products/{product}/candles?granularity={granularity}"
UA = {"User-Agent": "coinbase-spot-paper/1.0 (paper-only; no key)"}
KEY_ENV = ("COINBASE_API_KEY", "COINBASE_API_SECRET", "COINBASE_API_SECRET_KEY")


def load_config(path: str | None = None) -> dict:
    path = path or os.path.join(HERE, "config.json")
    with open(path, encoding="utf-8") as handle:
        cfg = json.load(handle)
    if cfg.get("paper_only") is not True or cfg.get("live_orders") is True:
        raise RuntimeError("config must be paper_only with live_orders false")
    return cfg


def locked_cfg(cfg: dict | None = None) -> dict:
    """Raise hurdles. Never soften the floor, the fee, or the capture haircut."""
    raw = dict(cfg or {})
    floor = _num(raw.get("venue_min_edge")) or LOCKED_FLOOR
    try:
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        import desk_profit
        floor = max(floor, float(desk_profit.DEFAULT_VENUE_MIN_EDGE["coinbase_spot"]))
    except Exception:
        floor = max(floor, LOCKED_FLOOR)
    raw["venue_min_edge"] = max(LOCKED_FLOOR, floor)
    raw["capture_haircut"] = min(LOCKED_HAIRCUT_MAX, _num(raw.get("capture_haircut")) or LOCKED_HAIRCUT_MAX)
    raw["taker_fee"] = max(LOCKED_TAKER_MIN, _num(raw.get("taker_fee")) or LOCKED_TAKER_MIN)
    raw["slippage"] = max(LOCKED_SLIP_MIN, _num(raw.get("slippage")) or LOCKED_SLIP_MIN)
    raw["min_z"] = _num(raw.get("min_z")) or 2.0
    raw["stake_usd"] = _num(raw.get("stake_usd")) or 25.0
    raw["max_open"] = int(raw.get("max_open") or 1)
    raw["stop_pct"] = _num(raw.get("stop_pct")) or 0.015
    raw["time_stop_hours"] = _num(raw.get("time_stop_hours")) or 24.0
    raw["starter_cash"] = _num(raw.get("starter_cash")) or 500.0
    raw["learn_min_settles"] = int(raw.get("learn_min_settles") or 8)
    raw["learn_hit_rate"] = _num(raw.get("learn_hit_rate")) or 0.40
    raw["observe_bars"] = int(raw.get("observe_bars") or 16)
    raw["products_trade"] = list(raw.get("products_trade") or ["ETH-USD", "SOL-USD"])
    raw["products_research_only"] = list(raw.get("products_research_only") or ["BTC-USD"])
    raw["paper_only"] = True
    raw["live_orders"] = False
    raw["shadow_only"] = True
    return raw


def research_card(cfg: dict | None = None) -> dict:
    cfg = locked_cfg(cfg)
    trip = round_trip(cfg)
    need = (trip + cfg["venue_min_edge"]) / cfg["capture_haircut"]
    return {
        "paper_only": True,
        "live_orders": False,
        "shadow_only": True,
        "venue": "coinbase_spot",
        "floor": cfg["venue_min_edge"],
        "taker_fee": cfg["taker_fee"],
        "slippage": cfg["slippage"],
        "round_trip": round(trip, 6),
        "capture_haircut": cfg["capture_haircut"],
        "min_z": cfg["min_z"],
        "bar_return_to_clear": round(need, 6),
        "products_trade": cfg["products_trade"],
        "products_research_only": cfg["products_research_only"],
        "stake_usd": cfg["stake_usd"],
        "starter_cash": cfg["starter_cash"],
        "base": (
            "A 15m bar must be about "
            f"{need:.0%} with z>={cfg['min_z']:g} before a long clears fees. "
            "Ordinary bars skip. That is the trading base."
        ),
    }


def round_trip(cfg: dict) -> float:
    return 2.0 * (float(cfg["taker_fee"]) + float(cfg["slippage"]))


def closes_to_returns(closes: list[float]) -> list[float]:
    out = []
    for prev, nxt in zip(closes, closes[1:]):
        if prev <= 0:
            continue
        out.append(nxt / prev - 1.0)
    return out


def horizon_return(closes: list[float], bars: int) -> float | None:
    if bars < 1 or len(closes) <= bars:
        return None
    prev = closes[-1 - bars]
    if prev <= 0:
        return None
    return closes[-1] / prev - 1.0


def evaluate_returns(returns: list[float], cfg: dict, *, product: str = "") -> dict:
    """Fee-aware long decision from completed simple returns. Last bar is the signal."""
    cfg = locked_cfg(cfg)
    trip = round_trip(cfg)
    row = {
        "product": product,
        "action": "skip",
        "reason": "",
        "z": None,
        "ret": None,
        "sigma": None,
        "edge": None,
        "round_trip": trip,
        "floor": cfg["venue_min_edge"],
    }
    if len(returns) < 8:
        row["reason"] = "need 8 bars"
        return row
    prior = [r for r in returns[:-1] if math.isfinite(r)]
    if len(prior) < 7:
        row["reason"] = "need 8 bars"
        return row
    sigma = statistics.pstdev(prior)
    ret = returns[-1]
    row["ret"] = ret
    row["sigma"] = sigma
    if not math.isfinite(ret) or sigma <= 1e-12:
        row["reason"] = "no sigma"
        return row
    z = ret / sigma
    edge = cfg["capture_haircut"] * abs(ret) - trip
    row["z"] = z
    row["edge"] = edge
    if ret <= 0:
        row["reason"] = "spot cash book is long-only"
        return row
    if z + 1e-12 < cfg["min_z"]:
        row["reason"] = f"z {z:.2f} < {cfg['min_z']:g}"
        return row
    if edge + 1e-12 < cfg["venue_min_edge"]:
        row["reason"] = f"edge {edge:.4f} < floor {cfg['venue_min_edge']:.2f}"
        return row
    row["action"] = "buy"
    row["reason"] = "fee-clear long"
    return row


def learning_block(state: dict, product: str, cfg: dict) -> str:
    closed = [
        row for row in (state.get("closed") or [])
        if row.get("ticker") == product and _num(row.get("pnl")) is not None
    ]
    need = int(cfg["learn_min_settles"])
    if len(closed) < need:
        return ""
    hits = sum(1 for row in closed if float(row["pnl"]) > 0)
    rate = hits / len(closed)
    if rate + 1e-12 < float(cfg["learn_hit_rate"]):
        return f"learning skip {product} {hits}/{len(closed)} under {cfg['learn_hit_rate']:.0%}"
    return ""


def btc_yes_open(desk_root: str) -> bool | None:
    """True when the live BTC tower holds YES. None when that file will not read."""
    path = os.path.join(desk_root, "btc15m-signal", "paper_account.json")
    if not os.path.isfile(path):
        return False
    try:
        with open(path, encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    for pos in state.get("open") or []:
        if str(pos.get("side") or "").upper() == "YES":
            return True
    return False


def exit_reason(pos: dict, mark: float, z: float | None, cfg: dict, now: dt.datetime) -> str:
    entry = _num(pos.get("entry_price"))
    if entry is None or entry <= 0 or mark <= 0:
        return ""
    move = mark / entry - 1.0
    if move <= -float(cfg["stop_pct"]) + 1e-12:
        return "stop"
    if move + 1e-12 >= round_trip(cfg) + float(cfg["venue_min_edge"]):
        return "take-profit"
    opened = _parse_time(pos.get("opened"))
    if opened is not None:
        age_h = (now - opened).total_seconds() / 3600.0
        if age_h + 1e-12 >= float(cfg["time_stop_hours"]):
            return "time"
    if z is not None and z <= -float(cfg["min_z"]) + 1e-12:
        return "model-flip"
    return ""


def apply_exit(state: dict, pos: dict, mark: float, reason: str, cfg: dict, now: dt.datetime) -> dict:
    entry = float(pos["entry_price"])
    stake = float(pos.get("cost") or cfg["stake_usd"])
    gross = stake * (mark / entry - 1.0)
    fee = stake * round_trip(cfg)
    pnl = round(gross - fee, 4)
    closed = dict(pos)
    closed.update({
        "exit": reason,
        "exit_price": mark,
        "closed": now.isoformat(timespec="seconds"),
        "pnl": pnl,
        "fee": round(fee, 4),
        "paper_only": True,
    })
    state["open"] = [row for row in state.get("open") or [] if row is not pos]
    state.setdefault("closed", []).append(closed)
    state["cash"] = round(float(state.get("cash") or 0) + stake + pnl, 4)
    return closed


def empty_state(cfg: dict) -> dict:
    return {
        "cash": float(cfg["starter_cash"]),
        "open": [],
        "closed": [],
        "paper_only": True,
        "shadow_only": True,
        "live_orders": False,
        "checks": 0,
    }


def fetch_closes(product: str, granularity: int = 900) -> list[float]:
    url = CANDLE_URL.format(product=product, granularity=int(granularity))
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=8) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    rows = [row for row in payload if isinstance(row, list) and len(row) >= 5]
    rows.sort(key=lambda row: row[0])
    closes = []
    for row in rows:
        px = _num(row[4])
        if px is not None and px > 0:
            closes.append(px)
    return closes


def run_once(
    desk_root: str | None = None,
    cfg: dict | None = None,
    fetch=None,
    now: dt.datetime | None = None,
) -> int:
    desk_root = desk_root or DESK_ROOT
    cfg = locked_cfg(cfg or load_config(os.path.join(desk_root, "coinbase-spot-paper", "config.json")))
    now = now or dt.datetime.now(dt.timezone.utc)
    if any(os.environ.get(name) for name in KEY_ENV):
        print("SIGNAL: SKIP key is set")
        print("CARD: refusing the check because a Coinbase key is set. Public data only.")
        print("no trade")
        return 0
    tower = os.path.join(desk_root, "coinbase-spot-paper")
    os.makedirs(tower, exist_ok=True)
    state = _read_state(os.path.join(tower, "paper_account.json")) or empty_state(cfg)
    state.setdefault("open", [])
    state.setdefault("closed", [])
    state["paper_only"] = True
    state["shadow_only"] = True
    state["live_orders"] = False
    fetch = fetch or (lambda product: fetch_closes(product, int(cfg.get("granularity_sec") or 900)))
    products = list(dict.fromkeys(list(cfg["products_trade"]) + list(cfg["products_research_only"])))
    for pos in state["open"]:
        ticker = str(pos.get("ticker") or "")
        if ticker and ticker not in products:
            products.append(ticker)
    books: dict[str, list[float]] = {}
    errors: dict[str, str] = {}
    for product in products:
        try:
            books[product] = list(fetch(product) or [])
        except Exception as exc:
            errors[product] = exc.__class__.__name__
            books[product] = []
    decisions = {}
    for product, closes in books.items():
        returns = closes_to_returns(closes)
        decision = evaluate_returns(returns, cfg, product=product)
        if product in errors and not closes:
            decision["action"] = "skip"
            decision["reason"] = f"data {errors[product]}"
        decision["observe_return"] = horizon_return(closes, int(cfg["observe_bars"]))
        decisions[product] = decision
    blocked = os.environ.get("DESK_BLOCK_ENTRIES") == "1"
    btc_open = btc_yes_open(desk_root)
    sold = []
    for pos in list(state["open"]):
        product = str(pos.get("ticker") or "")
        closes = books.get(product) or []
        if not closes:
            continue
        decision = decisions.get(product) or {}
        reason = exit_reason(pos, closes[-1], decision.get("z"), cfg, now)
        if reason:
            sold.append(apply_exit(state, pos, closes[-1], reason, cfg, now))
            _record_incubation(desk_root, product, sold[-1].get("pnl"))
    bought = None
    open_n = len(state.get("open") or [])
    gate = ""
    if blocked:
        gate = "desk entry gate"
    elif btc_open is True:
        gate = "btc15m YES open"
    elif btc_open is None:
        gate = "btc book unreadable"
    elif open_n >= int(cfg["max_open"]):
        gate = "max open"
    if gate:
        for product in cfg["products_trade"]:
            decision = decisions.get(product)
            if decision and decision.get("action") == "buy":
                decision["action"] = "skip"
                decision["reason"] = gate
    else:
        for product in cfg["products_trade"]:
            decision = decisions.get(product) or {}
            if decision.get("action") != "buy":
                continue
            learn = learning_block(state, product, cfg)
            if learn:
                decision["action"] = "skip"
                decision["reason"] = learn
                continue
            cash = float(state.get("cash") or 0)
            stake = float(cfg["stake_usd"])
            if cash + 1e-9 < stake:
                decision["action"] = "skip"
                decision["reason"] = "shadow cash below ticket"
                continue
            mark = books[product][-1]
            state["cash"] = round(cash - stake, 4)
            state["open"].append({
                "ticker": product,
                "side": "buy",
                "contracts": 1,
                "cost": stake,
                "entry_price": mark,
                "opened": now.isoformat(timespec="seconds"),
                "edge": decision.get("edge"),
                "z": decision.get("z"),
                "risk_factor": "risk_on_coinbase_spot",
                "paper_only": True,
                "shadow_only": True,
                "exit_plan": {
                    "kind": "stop+take_profit+model_flip+time",
                    "stop_pct": -float(cfg["stop_pct"]),
                    "time_stop_hours": cfg["time_stop_hours"],
                    "fee_floors_locked": True,
                },
            })
            bought = product
            break
    for product in cfg["products_research_only"]:
        decision = decisions.get(product)
        if decision and decision.get("action") == "buy":
            decision["action"] = "skip"
            decision["reason"] = "research only — btc15m owns this factor"
    state["checks"] = int(state.get("checks") or 0) + 1
    state["last_check"] = now.isoformat(timespec="seconds")
    _write_json(os.path.join(tower, "paper_account.json"), state)
    _append_research(tower, now, decisions)
    lines = []
    for product, decision in decisions.items():
        edge = decision.get("edge")
        edge_txt = "n/a" if edge is None else f"{edge:.4f}"
        lines.append(
            f"SIGNAL: {decision['action'].upper()} {product} {decision.get('reason') or ''} edge {edge_txt}"
        )
    if sold:
        lines.append("CARD: " + "; ".join(f"paper sell {row['ticker']} {row['exit']}" for row in sold))
    elif bought:
        lines.append(f"CARD: paper buy {bought}")
    else:
        first = next(iter(decisions.values()), {})
        lines.append("CARD: " + (first.get("reason") or "no fee-clear long"))
    if not bought:
        lines.append("no trade")
    print("\n".join(lines))
    return 0


def _record_incubation(desk_root: str, product: str, pnl) -> None:
    try:
        if desk_root not in sys.path:
            sys.path.insert(0, desk_root)
        import desk_roi_plan
        desk_roi_plan.record_incubation_settle(
            desk_root,
            series=f"COINBASE-{product}",
            bot="coinbase-spot",
            pnl=pnl,
            contracts=1,
            note="shadow spot",
        )
    except Exception:
        return


def _append_research(tower: str, now: dt.datetime, decisions: dict) -> None:
    path = os.path.join(tower, "research.jsonl")
    rows = []
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as handle:
                rows = handle.readlines()[-1999:]
        except OSError:
            rows = []
    for product, decision in decisions.items():
        rows.append(json.dumps({
            "at": now.isoformat(timespec="seconds"),
            "product": product,
            "action": decision.get("action"),
            "reason": decision.get("reason"),
            "z": decision.get("z"),
            "edge": decision.get("edge"),
            "ret": decision.get("ret"),
            "observe_return": decision.get("observe_return"),
            "paper_only": True,
        }) + "\n")
    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.writelines(rows[-2000:])
    except OSError:
        return


def _read_state(path: str) -> dict | None:
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _write_json(path: str, payload: dict) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    os.replace(tmp, path)


def _parse_time(text) -> dt.datetime | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    try:
        parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def _num(value) -> float | None:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(n):
        return None
    return n


def reset_account(desk_root: str | None = None) -> None:
    tower = os.path.join(desk_root or DESK_ROOT, "coinbase-spot-paper")
    for name in ("paper_account.json", "research.jsonl"):
        path = os.path.join(tower, name)
        if os.path.isfile(path):
            os.remove(path)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--reset" in argv:
        reset_account()
        print("reset paper account")
        return 0
    if "--research" in argv:
        print(json.dumps(research_card(), indent=2))
        return 0
    return run_once()


if __name__ == "__main__":
    raise SystemExit(main())
