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


def fee_need(cfg: dict | None = None) -> float:
    """0.05 on top of the taker round trip. A maker fee does not cheapen it."""
    cfg = locked_cfg(cfg)
    return round_trip(cfg) + float(cfg["venue_min_edge"])


def _replay_returns(rows) -> list[float]:
    out = []
    for row in rows or []:
        if isinstance(row, dict):
            pnl = _num(row.get("pnl"))
            stake = _num(row.get("cost") if row.get("cost") is not None else row.get("stake"))
            if pnl is None or stake is None or stake <= 0:
                continue
            out.append(pnl / stake)
        else:
            n = _num(row)
            if n is not None:
                out.append(n)
    return out


def _window_clears(window) -> bool:
    if len(window) < 20:
        return False
    hits = sum(1 for value in window if value > 0)
    if hits / len(window) + 1e-12 < 0.40:
        return False
    if statistics.median(window) <= 0:
        return False
    return statistics.fmean(window) + 1e-12 >= 0.05


def replay_bar(rows) -> str:
    """Full sample and the latest 20. Empty means the bar is met."""
    vals = _replay_returns(rows)
    if not _window_clears(vals) or not _window_clears(vals[-20:]):
        return "replay bar not met"
    return ""


def decide_stake(stake, adapted) -> float:
    """Adapt does not get a stake to multiply. A missing ticket is zero."""
    base = _num(stake)
    if base is None or base <= 0:
        return 0.0
    if adapted is None:
        return round(base, 2)
    got = _num(adapted)
    if got is None or got < 0:
        return round(base, 2)
    return round(min(got, base), 2)


def decide(signal, replay, cfg=None, adapted=None) -> dict:
    """Flat unless the replay bar and the fee floor both passed.

    BTC stays a log. A failed candle stays a data skip. Adapt cannot raise the stake.
    """
    cfg = locked_cfg(cfg)
    row = dict(signal or {})
    row["floor"] = cfg["venue_min_edge"]
    row["round_trip"] = round_trip(cfg)
    row["need"] = fee_need(cfg)
    row["taker_fee"] = cfg["taker_fee"]
    row["stake"] = 0.0
    row["flat"] = True
    reason = str(row.get("reason") or "")
    if row.get("data_skip") or reason.lower().startswith("data "):
        if row.get("action") == "buy":
            row["action"] = "skip"
        return row
    product = str(row.get("product") or "")
    if product == "BTC-USD" or row.get("action") == "log":
        row["action"] = "log" if row.get("action") == "log" else "flat"
        row["scored_as_buy"] = False
        if "not scored" not in reason and "research only" not in reason:
            row["reason"] = "logged, not scored as a buy"
        return row
    if row.get("action") != "buy":
        return row
    missed = replay_bar(replay)
    if missed:
        row["action"] = "flat"
        row["reason"] = missed
        return row
    edge = _num(row.get("edge"))
    if edge is None or edge + 1e-12 < float(cfg["venue_min_edge"]):
        row["action"] = "flat"
        row["reason"] = "floor on top of the round trip"
        return row
    row["flat"] = False
    row["stake"] = decide_stake(cfg["stake_usd"], adapted)
    row["action"] = "buy"
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


def real_spot(price):
    """A Coinbase price above zero. Missing, zero, and a wipe are not a mark."""
    n = _num(price)
    if n is None or n <= 0:
        return None
    return n


def watch_sleeve(state, prices) -> dict:
    """Mark an open long at its own real price. A flat sleeve stays flat.

    A missing price is not filled in with the −1.5% stop. This does not sell.
    """
    book = state if isinstance(state, dict) else {}
    opens = [row for row in book.get("open") or [] if isinstance(row, dict)]
    quotes = prices if isinstance(prices, dict) else {}
    if not opens:
        book["watch"] = "flat"
        return {"flat": True, "sold": False, "marks": []}
    marks = []
    for pos in opens:
        product = str(pos.get("ticker") or "")
        mark = real_spot(quotes.get(product))
        if mark is None:
            marks.append({"product": product, "marked": False, "sold": False})
            continue
        pos["last_mark"] = mark
        marks.append({"product": product, "marked": True, "sold": False, "last_mark": mark})
    book["watch"] = "marked"
    return {"flat": False, "sold": False, "marks": marks}


EXIT_NAME = {
    "stop": "stop −1.5%",
    "take-profit": "fee take-profit",
    "model-flip": "z≤−2",
    "time": "24h",
}


def replacement_block(state) -> str:
    """A failsafe sale does not open another long on the same check."""
    book = state if isinstance(state, dict) else {}
    sold = book.get("sold_this_check") or []
    if isinstance(sold, (list, tuple)) and any(sold):
        return "failsafe sold — no replacement"
    return ""


def failsafe_sale(state, prices, z_by_product=None, now=None, cfg=None) -> dict:
    """Sell an open long at its own real mark when one of this tower's exits fired.

    The exits are the −1.5% stop, the take-profit after the taker round trip
    plus the 0.05 floor, z ≤ −2, and the 24h stop. A flat book has nothing to
    sell. A missing price is not filled in with the stop. Another product's
    price is not this sale. The taker is not cut to the maker fee. The sale
    is not labeled a hit, and it does not open a replacement.
    """
    book = state if isinstance(state, dict) else {}
    cfg = locked_cfg(cfg)
    cfg["stop_pct"] = 0.015
    cfg["time_stop_hours"] = 24.0
    cfg["min_z"] = 2.0
    if cfg["venue_min_edge"] < 0.05:
        cfg["venue_min_edge"] = 0.05
    if cfg["taker_fee"] < LOCKED_TAKER_MIN:
        cfg["taker_fee"] = LOCKED_TAKER_MIN
    when = now if isinstance(now, dt.datetime) else dt.datetime.now(dt.timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=dt.timezone.utc)
    quotes = prices if isinstance(prices, dict) else {}
    zs = z_by_product if isinstance(z_by_product, dict) else {}
    opens = [row for row in book.get("open") or [] if isinstance(row, dict)]
    if not opens:
        book["sold_this_check"] = []
        return {"flat": True, "sold": False, "hit": False, "sales": []}
    sales = []
    for pos in list(opens):
        side = str(pos.get("side") or "buy").lower()
        if side not in ("buy", "long"):
            continue
        product = str(pos.get("ticker") or "")
        mark = real_spot(quotes.get(product))
        if mark is None:
            continue
        reason = exit_reason(pos, mark, _num(zs.get(product)), cfg, when)
        if not reason:
            continue
        closed = apply_exit(book, pos, mark, reason, cfg, when)
        closed["exit_name"] = EXIT_NAME.get(reason, reason)
        closed["tower"] = "coinbase-spot"
        closed["stake"] = closed.get("cost")
        closed.pop("hit", None)
        closed.pop("result", None)
        sales.append(closed)
    book["sold_this_check"] = [row.get("ticker") for row in sales]
    return {"flat": False, "sold": bool(sales), "hit": False, "sales": sales}


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


def read_closes(closes):
    """Real positive closes. A hole or a wipe stays missing."""
    if not isinstance(closes, (list, tuple)) or not closes:
        return None
    out = []
    for px in closes:
        n = _num(px)
        if n is None or n <= 0:
            return None
        out.append(n)
    return out


def scan_book(product, closes, error=None, cfg=None) -> dict:
    """Read ETH-USD and SOL-USD. Log BTC-USD. Do not score BTC as a buy.

    A failed candle is a data skip. The last close is stored only when it is real.
    """
    cfg = locked_cfg(cfg)
    name = str(product or "")
    row = {
        "product": name,
        "action": "skip",
        "reason": "",
        "last": None,
        "scored_as_buy": False,
        "paper_only": True,
    }
    cleaned = None if error else read_closes(closes)
    if cleaned is None:
        row["reason"] = f"data {error or 'candle'}"
        row["data_skip"] = True
        return row
    row["last"] = cleaned[-1]
    research = {str(item) for item in (cfg.get("products_research_only") or ["BTC-USD"])}
    if name == "BTC-USD" or name in research:
        row["action"] = "log"
        row["reason"] = "research only — logged, not scored as a buy"
        return row
    row["action"] = "read"
    row["reason"] = "candle read"
    row["bars"] = len(cleaned)
    return row


def scan_card(rows) -> str:
    """A failed candle wins the card over a story about edge."""
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        reason = str(row.get("reason") or "").strip()
        if row.get("data_skip") or reason.lower().startswith("data "):
            return reason or "data candle"
    return ""


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


BUY_EXIT = "stop −1.5% / fee take-profit / z≤−2 / 24h"
TICKET_USD = 25.0


def write_buy_intent(path, *, fill_id, product, price, stake=TICKET_USD):
    """The crash intent. A real price and the $25 ticket are required."""
    price_n = _num(price)
    stake_n = _num(stake)
    name = str(product or "").strip()
    if (
        price_n is None
        or price_n <= 0
        or stake_n is None
        or abs(stake_n - TICKET_USD) > 1e-9
        or not name
        or name == "BTC-USD"
        or not str(fill_id or "").strip()
    ):
        raise ValueError("buy intent needs a real price and the $25 ticket")
    payload = {
        "tower": "coinbase-spot",
        "fill_id": str(fill_id).strip(),
        "product": name,
        "stake": TICKET_USD,
        "price": price_n,
        "exit_rule": BUY_EXIT,
        "paper_only": True,
        "status": "intent",
    }
    _write_json(path, payload)
    return payload


def reconcile_buy_intent(state, path) -> str:
    """Match an intent to the book. Never create a position or a price."""
    if not path or not os.path.exists(path):
        return "none"
    try:
        with open(path, encoding="utf-8") as handle:
            intent = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return "none"
    if not isinstance(intent, dict):
        return "none"
    fid = str(intent.get("fill_id") or "")
    book = state if isinstance(state, dict) else {}
    opens = [row for row in book.get("open") or [] if isinstance(row, dict)]
    closed = [row for row in book.get("closed") or [] if isinstance(row, dict)]
    if fid and any(str(row.get("fill_id") or "") == fid for row in opens):
        status = "open"
    elif fid and any(str(row.get("fill_id") or "") == fid for row in closed):
        status = "closed"
    else:
        status = "abandoned"
    intent["status"] = status
    intent["paper_only"] = True
    intent["exit_rule"] = BUY_EXIT
    _write_json(path, intent)
    return status


def place_shadow_buy(state, decision, price, *, btc_yes, intent_path, now) -> dict:
    """Write the exit intent before cash. A refuse buys nothing.

    One $25 ticket. No new long while BTC 15-minute holds YES.
    """
    book = state if isinstance(state, dict) else {}
    cash_before = _num(book.get("cash")) or 0.0

    def refuse(reason):
        return {
            "bought": False,
            "reason": reason,
            "fill": False,
            "paper_only": True,
            "cash": cash_before,
        }

    blocked = replacement_block(book)
    if blocked:
        return refuse(blocked)
    if btc_yes:
        return refuse("btc15m YES open")
    if any(isinstance(row, dict) for row in (book.get("open") or [])):
        return refuse("one $25 ticket")
    if not isinstance(decision, dict) or decision.get("flat") or decision.get("action") != "buy":
        return refuse(str((decision or {}).get("reason") or "replay bar not met"))
    edge = _num(decision.get("edge"))
    floor = _num(decision.get("floor"))
    if floor is None or floor + 1e-12 < 0.05:
        floor = 0.05
    if edge is None or edge + 1e-12 < floor:
        return refuse("floor on top of the round trip")
    product = str(decision.get("product") or "")
    if product == "BTC-USD" or not product:
        return refuse("logged, not a buy")
    px = _num(price)
    if px is None or px <= 0:
        return refuse("missing price")
    if cash_before + 1e-9 < TICKET_USD:
        return refuse("shadow cash below ticket")
    fill_id = f"{product}|{now}"
    try:
        write_buy_intent(
            intent_path, fill_id=fill_id, product=product, price=px, stake=TICKET_USD,
        )
    except (TypeError, ValueError):
        return refuse("buy intent needs a real price and the $25 ticket")
    book["cash"] = round(cash_before - TICKET_USD, 4)
    book.setdefault("open", []).append({
        "ticker": product,
        "side": "buy",
        "contracts": 1,
        "cost": TICKET_USD,
        "entry_price": px,
        "opened": str(now),
        "fill_id": fill_id,
        "edge": edge,
        "z": decision.get("z"),
        "exit_rule": BUY_EXIT,
        "risk_factor": "risk_on_coinbase_spot",
        "paper_only": True,
        "shadow_only": True,
    })
    return {
        "bought": True,
        "fill_id": fill_id,
        "exit_rule": BUY_EXIT,
        "stake": TICKET_USD,
        "cash": book["cash"],
    }


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
    reconcile_buy_intent(state, os.path.join(tower, "buy_intent.json"))
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
    research = {str(item) for item in cfg["products_research_only"]}
    for product, closes in books.items():
        err = errors.get(product)
        if product == "BTC-USD" or product in research or (err and not closes) or read_closes(closes) is None:
            decision = scan_book(product, closes, err or ("candle" if read_closes(closes) is None else None), cfg)
        else:
            decision = evaluate_returns(closes_to_returns(closes), cfg, product=product)
            decision["last"] = closes[-1]
            decision["scored_as_buy"] = decision.get("action") == "buy"
        decision["observe_return"] = horizon_return(closes if isinstance(closes, list) else [], int(cfg["observe_bars"]))
        decisions[product] = decision
    for product in cfg["products_trade"]:
        decision = decisions.get(product)
        if isinstance(decision, dict):
            decisions[product] = decide(decision, state.get("closed") or [], cfg, adapted=None)
    blocked = os.environ.get("DESK_BLOCK_ENTRIES") == "1"
    btc_open = btc_yes_open(desk_root)
    spot_prices = {}
    for product, closes in books.items():
        cleaned = read_closes(closes)
        if cleaned:
            spot_prices[product] = cleaned[-1]
    watch_sleeve(state, spot_prices)
    marks = {}
    for product, closes in books.items():
        if closes:
            mark = real_spot(closes[-1])
            if mark is not None:
                marks[product] = mark
    z_by = {
        product: decision.get("z")
        for product, decision in decisions.items()
        if isinstance(decision, dict)
    }
    failsafe = failsafe_sale(state, marks, z_by_product=z_by, now=now, cfg=cfg)
    sold = list(failsafe.get("sales") or [])
    for row in sold:
        _record_incubation(desk_root, str(row.get("ticker") or ""), row.get("pnl"))
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
            stake = float(decision.get("stake") if decision.get("stake") is not None else cfg["stake_usd"])
            if decision.get("flat") or stake <= 0:
                decision["action"] = "flat"
                decision["reason"] = decision.get("reason") or "replay bar not met"
                continue
            if cash + 1e-9 < TICKET_USD:
                decision["action"] = "skip"
                decision["reason"] = "shadow cash below ticket"
                continue
            mark = (books.get(product) or [None])[-1]
            bought_row = place_shadow_buy(
                state,
                decision,
                mark,
                btc_yes=False,
                intent_path=os.path.join(tower, "buy_intent.json"),
                now=now.isoformat(timespec="seconds"),
            )
            if not bought_row.get("bought"):
                decision["action"] = "flat"
                decision["reason"] = bought_row.get("reason") or "refused"
                continue
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
        lines.append("CARD: " + _card_skip_reason(decisions, cfg))
    if not bought:
        lines.append("no trade")
    print("\n".join(lines))
    return 0


def _card_skip_reason(decisions: dict, cfg: dict | None = None) -> str:
    """CARD must densify feed-down, not false-friend as the first z/edge skip.

    Prefer any ``data *`` reason (candle TimeoutError / fetch fail) over ordinary
    model skips when products_trade puts a quiet bar first (#457 Prefer-1).

    Ordinary z/edge skips also densify the locked fee-bar need so the city card
    is not read as a missed plan trade (#cb-carry tip twin).
    """
    data = scan_card(list((decisions or {}).values()))
    if data:
        return data
    first = next(iter((decisions or {}).values()), {}) if decisions else {}
    if not isinstance(first, dict):
        return "no fee-clear long"
    reason = str(first.get("reason") or "no fee-clear long").strip() or "no fee-clear long"
    low = reason.lower()
    if not (
        low.startswith("z ")
        or low.startswith("edge ")
        or "long-only" in low
        or reason == "no fee-clear long"
    ):
        return reason
    card = research_card(cfg)
    need = float(card["bar_return_to_clear"])
    trip = float(card["round_trip"])
    floor = float(card["floor"])
    edge = first.get("edge")
    edge_bit = ""
    if edge is not None:
        try:
            edge_bit = f"; edge {float(edge):.4f}"
        except (TypeError, ValueError):
            edge_bit = ""
    return (
        f"{reason}{edge_bit}; 15m needs ~{need:.0%} bar to clear "
        f"{trip:.0%} RT+{floor:g} floor (ordinary bars skip)"
    )


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
