#!/usr/bin/env python3
"""BTC carry on Coinbase. Paper shadow, laid out like the real wallet.

The real version would be two Coinbase accounts under one login:

* Spot wallet: holds the BTC (bought on BTC-USD) and spare USD.
* Futures account (Coinbase Financial Markets): holds USD margin for one
  short nano BTC perp (BIP, 0.01 BTC per contract).

Long 0.01 BTC spot and short 1 BIP contract cancel out on price. What is
left is the hourly funding. When the funding rate is positive, longs pay
shorts, so this book gets paid. When it is negative, this book pays.

Everything here is pretend money. It reads Coinbase's public market data
only (no key, no account, no order). It moves pretend USD between the two
pretend accounts the way a real sweep would, and it keeps a ledger of every
fee, funding hour, sweep and daily settle so the totals add up.

Locked costs (US retail, checked 2026-11-14):
  spot taker 0.90% each side (Coinbase Advanced US intro tier)
  perp fee 0.05% of notional, at least $0.20, per contract, each side
  liquidation fee 0.80% if the futures account is force-closed
Floor: coinbase_btc_carry 0.02 (2 points a year after the round trip).
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import statistics
import sys
import urllib.error
import urllib.request

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore[assignment]

HERE = os.path.dirname(os.path.abspath(__file__))
DESK_ROOT = os.path.dirname(HERE)

VERSION = 2
VENUE = "coinbase_btc_carry"
VENUE_FLOOR = 0.02  # locked. Annual edge after the round trip must be at least this.

SPOT_PRODUCT = "BTC-USD"
PERP_PRODUCT = "BIP-20DEC30-CDE"
CONTRACT_BTC = 0.01
CONTRACTS = 1

# Locked fees. A config can raise these, never lower them.
SPOT_TAKER = 0.009          # Coinbase Advanced US intro taker 0.90%
PERP_TAKER = 0.0005         # CFM intro futures fee 0.05% per contract per side
PERP_FEE_MIN = 0.20         # minimum per contract per side
LIQ_FEE_RATE = 0.008        # liquidation trades 0.80%

STARTER_CASH = 1500.0
NOTIONAL = STARTER_CASH     # kept for older desk readers that import NOTIONAL

# Margin plan for the futures account, as multiples of Coinbase's overnight
# short margin requirement (read live from the public product feed).
MARGIN_TARGET_X = 2.0       # post this much when opening or topping up
TOPUP_AT_X = 1.5            # below this, sweep USD in from the spot wallet
SWEEP_BACK_AT_X = 3.0       # above this at the daily settle, sweep the extra back

MIN_FUNDING_HOURS = 24      # real hourly rates seen before the first open
TRAILING_HOURS = 168        # 7 days for the entry and exit average
MIN_HOLD_DAYS = 30          # no exit on funding before this
MAX_BASIS = 0.03            # perp and spot more than 3% apart = bad data
HOURS_PER_YEAR = 8760.0
SETTLE_HOUR_ET = 17         # Coinbase posts one net funding payment a day at 5 PM ET
INCUBATION_SERIES = "BTC-CARRY-CB"

API = "https://api.coinbase.com/api/v3/brokerage/market"
UA = {"User-Agent": "btc-carry-paper/2.0 (paper-only; public market data)"}
KEY_ENV = (
    "COINBASE_API_KEY", "COINBASE_API_SECRET", "COINBASE_API_SECRET_KEY",
    "BINANCE_API_KEY", "BINANCE_API_SECRET", "BINANCE_SECRET_KEY",
)

FLAT_CARD = "flat - Coinbase BTC spot long / BIP perp short not open; round trip unpaid"
HOLD_CARD = "holding 0.01 BTC spot / 1 BIP short on Coinbase; paid hourly funding"
HOLD_EXIT = "hold - exits only on a week of negative funding after 30 days"
HOLD_SENTENCE = "hold, not a sell"

# The old Binance archive study (Jan-Oct 2026). Kept as history only.
BTC_2026_GROSS = (
    0.0046, -0.0007, -0.0009, -0.0015, 0.0025,
    0.0022, 0.0058, 0.0061, 0.0044, 0.0041,
)
ETH_2026_GROSS = (
    0.0041, -0.0030, -0.0011, -0.0012, 0.0030,
    0.0007, 0.0035, 0.0047, 0.0042, 0.0028,
)
SOL_2026_GROSS = (
    0.0020, -0.0102, -0.0053, 0.0001, 0.0005,
    -0.0037, 0.0019, 0.0039, 0.0027, 0.0038,
)
OLD_MONTHLY_HAIRCUT = 0.0003
OLD_ROUND_TRIP = 0.0030


# ----------------------------------------------------------------- config

def load_config(path: str | None = None) -> dict:
    path = path or os.path.join(HERE, "config.json")
    with open(path, encoding="utf-8") as handle:
        cfg = json.load(handle)
    if cfg.get("paper_only") is not True or cfg.get("live_orders") is True:
        raise RuntimeError("config must be paper_only with live_orders false")
    return cfg


def _locked_floor() -> float:
    floor = VENUE_FLOOR
    try:
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        import desk_profit
        floor = max(floor, float(desk_profit.DEFAULT_VENUE_MIN_EDGE[VENUE]))
    except Exception:
        floor = VENUE_FLOOR
    return floor


def locked_cfg(cfg: dict | None = None) -> dict:
    """Fees only go up. One contract. Floor never below 0.02."""
    raw = dict(cfg or {})
    raw["spot_taker"] = max(SPOT_TAKER, _num(raw.get("spot_taker")) or 0.0)
    raw["perp_taker"] = max(PERP_TAKER, _num(raw.get("perp_taker")) or 0.0)
    raw["perp_fee_min"] = max(PERP_FEE_MIN, _num(raw.get("perp_fee_min")) or 0.0)
    raw["liq_fee_rate"] = max(LIQ_FEE_RATE, _num(raw.get("liq_fee_rate")) or 0.0)
    raw["contracts"] = CONTRACTS
    raw["contract_btc"] = CONTRACT_BTC
    raw["starter_cash"] = STARTER_CASH
    raw["spot_product"] = SPOT_PRODUCT
    raw["perp_product"] = PERP_PRODUCT
    raw["venue"] = VENUE
    raw["leverage"] = 1
    raw["venue_min_edge"] = max(_locked_floor(), _num(raw.get("venue_min_edge")) or 0.0)
    raw["paper_only"] = True
    raw["live_orders"] = False
    raw["shadow_only"] = True
    return raw


def perp_fee(cfg: dict, price: float, contracts: int = CONTRACTS) -> float:
    """Per contract, per side: 0.05% of notional, at least $0.20."""
    each = max(float(cfg["perp_taker"]) * price * CONTRACT_BTC, float(cfg["perp_fee_min"]))
    return round(each * contracts, 4)


def round_trip_rate(cfg: dict, q: dict) -> float:
    """Open plus close as a share of notional, including both spreads."""
    mid = _mid(q["spot_bid"], q["spot_ask"])
    notional = mid * CONTRACT_BTC * CONTRACTS
    fees = 2 * float(cfg["spot_taker"]) * notional + 2 * perp_fee(cfg, _mid(q["perp_bid"], q["perp_ask"]))
    spreads = ((q["spot_ask"] - q["spot_bid"]) + (q["perp_ask"] - q["perp_bid"])) * CONTRACT_BTC * CONTRACTS
    return (fees + spreads) / notional


# ----------------------------------------------------------------- research cards

def score_months(gross) -> dict:
    rows = [float(g) for g in gross]
    if not rows:
        return {"n": 0, "held_median": None, "held_mean": None, "flip_mean": None,
                "pass": False, "flip_reject": True}
    held = [g - OLD_MONTHLY_HAIRCUT for g in rows]
    flipped = [g - OLD_ROUND_TRIP for g in rows]
    return {
        "n": len(rows),
        "held_median": statistics.median(held),
        "held_mean": sum(held) / len(held),
        "flip_mean": sum(flipped) / len(flipped),
        "pass": statistics.median(held) > 0,
        "flip_reject": sum(flipped) / len(flipped) <= 0,
    }


def twin_research_card() -> dict:
    """The old Binance archive study, kept as history. Nothing here opens cash."""
    btc, eth, sol = (score_months(x) for x in (BTC_2026_GROSS, ETH_2026_GROSS, SOL_2026_GROSS))
    return {
        "paper_only": True,
        "observe_only": True,
        "fee_floors_locked": True,
        "auto_promote": False,
        "live_orders_enabled": False,
        "window": "2026-01..2026-10",
        "source": "retired Binance archive study (Binance does not serve US residents)",
        "btc": {"symbol": "BTC", "role": "live_shadow_sleeve", "venue": VENUE,
                "held_median": btc["held_median"], "flip_mean": btc["flip_mean"],
                "pass": btc["pass"], "second_tower": False},
        "eth": {"symbol": "ETH", "role": "observe_twin_same_factor",
                "held_median": eth["held_median"], "flip_mean": eth["flip_mean"],
                "pass": eth["pass"], "second_tower": False, "opens_desk_cash": False,
                "note": "Coinbase ETP perp would be the US route. Observe only."},
        "sol": {"symbol": "SOL", "role": "reject_mean_red",
                "held_median": sol["held_median"], "flip_mean": sol["flip_mean"],
                "pass": False, "second_tower": False, "opens_desk_cash": False,
                "note": "2026 held mean red after haircut - reject."},
        "note": ("Old Binance study for history. The live sleeve is BTC on Coinbase only. "
                 "ETH is observe-only. SOL is reject. Never LIVE."),
    }


def research_card(cfg: dict | None = None) -> dict:
    cfg = locked_cfg(cfg)
    return {
        "paper_only": True,
        "live_orders": False,
        "shadow_only": True,
        "venue": VENUE,
        "spot_product": SPOT_PRODUCT,
        "perp_product": PERP_PRODUCT,
        "contract_btc": CONTRACT_BTC,
        "contracts": CONTRACTS,
        "starter_cash": STARTER_CASH,
        "spot_taker": cfg["spot_taker"],
        "perp_taker": cfg["perp_taker"],
        "perp_fee_min": cfg["perp_fee_min"],
        "liq_fee_rate": cfg["liq_fee_rate"],
        "floor": cfg["venue_min_edge"],
        "wallet_layout": wallet_layout(),
        "entry_rule": (
            f"Open when the last 7 days of real hourly funding (at least {MIN_FUNDING_HOURS} hours seen), "
            "as a yearly rate, minus the full round trip, plus the entry basis, is at least the 0.02 floor."
        ),
        "exit_rule": (
            f"After {MIN_HOLD_DAYS} days, close if the 7-day funding is below -2% a year. "
            "A forced close happens if the futures account drops below Coinbase's intraday margin."
        ),
        "result": "One result per daily 5 PM ET settle. 50 results before the tower is judged.",
        "flat_card": FLAT_CARD,
        "hold_card": HOLD_CARD,
        "twins": twin_research_card(),
        "auto_promote": False,
    }


def wallet_layout() -> dict:
    """What the real setup would look like. Documentation only; nothing here trades."""
    return {
        "accounts": [
            {"name": "Coinbase spot wallet", "holds": "0.01 BTC per contract plus spare USD",
             "product": SPOT_PRODUCT},
            {"name": "Coinbase Financial Markets futures account", "holds": "USD margin for the short",
             "product": PERP_PRODUCT},
        ],
        "money_moves": [
            "Open: buy BTC on spot, sweep margin USD to futures, sell 1 BIP",
            f"Top-up: futures below {TOPUP_AT_X:g}x overnight margin -> sweep USD in from spot",
            "If spot USD runs out: sell a slice of spot BTC to fund the top-up (hedge drifts)",
            f"Daily 5 PM ET: funding and price change post to futures; above {SWEEP_BACK_AT_X:g}x, sweep the extra back",
            "Close: sell BTC on spot, buy back 1 BIP, sweep futures USD back to spot",
        ],
        "real_money_needs": [
            "A Coinbase account with Coinbase Financial Markets futures approval",
            "One API key: view + trade only, no transfer or withdraw, saved in Railway",
            "A separate real-order piece with its own tests and limits (not built)",
            "50 practice results and Levi's OK",
        ],
    }


# ----------------------------------------------------------------- public data

def fetch_quotes(opener=None, now: dt.datetime | None = None) -> dict:
    """Read Coinbase's public market data. No key. No order."""
    opener = opener or _get_json
    now = _as_utc(now or dt.datetime.now(dt.timezone.utc))
    out: dict = {"at": now.isoformat(timespec="seconds"), "error": ""}
    try:
        spot = opener(f"{API}/product_book?product_id={SPOT_PRODUCT}&limit=5") or {}
        perp_book = opener(f"{API}/product_book?product_id={PERP_PRODUCT}&limit=5") or {}
        perp = opener(f"{API}/products/{PERP_PRODUCT}") or {}
    except Exception as exc:  # noqa: BLE001 - a bad read is a data skip
        out["error"] = exc.__class__.__name__
        return out
    return parse_quotes(spot, perp_book, perp, at=out["at"])


def parse_quotes(spot: dict, perp_book: dict, perp: dict, *, at: str = "") -> dict:
    out: dict = {"at": at, "error": ""}
    sb, sa = _top(spot)
    pb, pa = _top(perp_book)
    details = (perp or {}).get("future_product_details") or {}
    rate = _num(details.get("funding_rate"))
    if rate is None:
        rate = _num((details.get("perpetual_details") or {}).get("funding_rate"))
    ftime = _parse_time(details.get("funding_time") or (details.get("perpetual_details") or {}).get("funding_time"))
    overnight = _num((details.get("overnight_margin_rate") or {}).get("short_margin_rate"))
    intraday = _num((details.get("intraday_margin_rate") or {}).get("short_margin_rate"))
    size = _num(details.get("contract_size"))
    out.update({
        "spot_bid": sb, "spot_ask": sa, "perp_bid": pb, "perp_ask": pa,
        "index": _num(details.get("index_price")),
        "funding_rate": rate,
        "funding_time": ftime.isoformat(timespec="seconds") if ftime else "",
        "short_margin_overnight": overnight,
        "short_margin_intraday": intraday,
        "contract_size": size,
        "trading_disabled": bool((perp or {}).get("trading_disabled")),
    })
    problem = quote_problem(out)
    if problem:
        out["error"] = problem
    return out


def quote_problem(q: dict) -> str:
    for key in ("spot_bid", "spot_ask", "perp_bid", "perp_ask"):
        n = _num(q.get(key))
        if n is None or n <= 0:
            return f"missing {key}"
    if q["spot_ask"] < q["spot_bid"] or q["perp_ask"] < q["perp_bid"]:
        return "crossed book"
    if abs(_mid(q["perp_bid"], q["perp_ask"]) / _mid(q["spot_bid"], q["spot_ask"]) - 1) > MAX_BASIS:
        return "perp and spot too far apart"
    if q.get("contract_size") is not None and abs(float(q["contract_size"]) - CONTRACT_BTC) > 1e-12:
        return "contract size changed"
    for key in ("short_margin_overnight", "short_margin_intraday"):
        n = _num(q.get(key))
        if n is None or not 0 < n < 1:
            return f"missing {key}"
    if q.get("funding_rate") is None or not q.get("funding_time"):
        return "missing funding"
    if abs(float(q["funding_rate"])) > 0.01:
        return "funding rate out of range"
    return ""


def _top(book: dict) -> tuple[float | None, float | None]:
    pb = (book or {}).get("pricebook") or {}
    bids = pb.get("bids") or []
    asks = pb.get("asks") or []
    bid = _num(bids[0].get("price")) if bids and isinstance(bids[0], dict) else None
    ask = _num(asks[0].get("price")) if asks and isinstance(asks[0], dict) else None
    return bid, ask


# ----------------------------------------------------------------- state

def empty_state(cfg: dict | None = None) -> dict:
    return {
        "version": VERSION,
        "venue": VENUE,
        "starter_cash": STARTER_CASH,
        "cash": STARTER_CASH,
        "wallet": {
            "spot_usd": STARTER_CASH, "spot_btc": 0.0, "futures_usd": 0.0,
            "short_contracts": 0, "short_entry": None, "settle_mark": None,
        },
        "funding_seen": [],
        "funding_accrued": 0.0,
        "funding_through": "",
        "est_hours": 0,
        "fees_paid": 0.0,
        "funding_total": 0.0,
        "sweeps": [],
        "events": [],
        "open": [],
        "closed": [],
        "equity_at_settle": STARTER_CASH,
        "last_settle": "",
        "checks": 0,
        "paper_only": True,
        "shadow_only": True,
        "live_orders": False,
    }


def migrate_old_state(state: dict | None, tower: str) -> dict:
    """The Binance book is archived as it was. The Coinbase book starts fresh."""
    if isinstance(state, dict) and state.get("version") == VERSION and state.get("venue") == VENUE:
        return state
    fresh = empty_state()
    if isinstance(state, dict) and state:
        archive = os.path.join(tower, "paper_account.binance-retired.json")
        if not os.path.exists(archive):
            kept = dict(state)
            kept["retired"] = "Moved to Coinbase on 2026-11-14. Binance does not serve US residents."
            _write_json(archive, kept)
        realized = sum(_num(r.get("pnl")) or 0.0 for r in state.get("closed") or [] if isinstance(r, dict))
        fresh["events"].append({
            "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "kind": "moved",
            "note": (f"Binance book archived (cash ${_num(state.get('cash')) or 0:.2f}, "
                     f"marked ${realized:+.2f}). Coinbase book starts at ${STARTER_CASH:,.0f}."),
        })
    return fresh


def equity(state: dict, q: dict) -> float:
    """Spot USD + BTC at the bid + futures USD + unposted funding + open short P&L."""
    w = state["wallet"]
    value = float(w["spot_usd"]) + float(w["spot_btc"]) * float(q["spot_bid"]) + float(w["futures_usd"])
    value += float(state.get("funding_accrued") or 0.0)
    value += short_unrealized(state, q)
    return round(value, 6)


def short_unrealized(state: dict, q: dict) -> float:
    w = state["wallet"]
    n = int(w.get("short_contracts") or 0)
    if not n or w.get("settle_mark") is None:
        return 0.0
    return (float(w["settle_mark"]) - _mid(q["perp_bid"], q["perp_ask"])) * CONTRACT_BTC * n


def futures_equity(state: dict, q: dict) -> float:
    return float(state["wallet"]["futures_usd"]) + float(state.get("funding_accrued") or 0.0) + short_unrealized(state, q)


def margin_need(state: dict, q: dict, kind: str = "overnight") -> float:
    n = int(state["wallet"].get("short_contracts") or 0) or CONTRACTS
    rate = q["short_margin_overnight"] if kind == "overnight" else q["short_margin_intraday"]
    return float(rate) * _mid(q["perp_bid"], q["perp_ask"]) * CONTRACT_BTC * n


def close_value(state: dict, q: dict, cfg: dict) -> float:
    """What the wallet would hold in USD if both legs were closed now at the touch."""
    w = state["wallet"]
    n = int(w.get("short_contracts") or 0)
    spot_sale = float(w["spot_btc"]) * float(q["spot_bid"])
    value = float(w["spot_usd"]) + spot_sale * (1 - float(cfg["spot_taker"])) + float(w["futures_usd"])
    value += float(state.get("funding_accrued") or 0.0)
    if n and w.get("settle_mark") is not None:
        value += (float(w["settle_mark"]) - float(q["perp_ask"])) * CONTRACT_BTC * n
        value -= perp_fee(cfg, float(q["perp_ask"]), n)
    return round(value, 6)


def _sync_cash(state: dict) -> None:
    w = state["wallet"]
    state["cash"] = round(float(w["spot_usd"]) + float(w["futures_usd"]), 4)


def _sweep(state: dict, amount: float, direction: str, now: dt.datetime, why: str) -> None:
    amount = round(max(0.0, amount), 4)
    if amount <= 0:
        return
    w = state["wallet"]
    if direction == "to_futures":
        w["spot_usd"] = round(float(w["spot_usd"]) - amount, 6)
        w["futures_usd"] = round(float(w["futures_usd"]) + amount, 6)
    else:
        w["futures_usd"] = round(float(w["futures_usd"]) - amount, 6)
        w["spot_usd"] = round(float(w["spot_usd"]) + amount, 6)
    state.setdefault("sweeps", []).append({
        "at": now.isoformat(timespec="seconds"), "usd": amount, "direction": direction, "why": why,
    })
    state["sweeps"] = state["sweeps"][-200:]


def _event(state: dict, now: dt.datetime, kind: str, note: str, **extra) -> None:
    row = {"at": now.isoformat(timespec="seconds"), "kind": kind, "note": note}
    row.update(extra)
    state.setdefault("events", []).append(row)
    state["events"] = state["events"][-200:]


# ----------------------------------------------------------------- funding

def record_funding(state: dict, q: dict, now: dt.datetime) -> dict:
    """Log the hourly rate. Credit or charge each hour the short is open, once.

    A missed hour uses the last rate seen and is counted as estimated.
    """
    ftime = _parse_time(q.get("funding_time"))
    rate = _num(q.get("funding_rate"))
    out = {"new_hours": 0, "estimated": 0, "credited": 0.0}
    if ftime is None or rate is None or ftime > now:
        return out
    seen = state.setdefault("funding_seen", [])
    stamp = ftime.isoformat(timespec="seconds")
    last = seen[-1] if seen else None
    if last and str(last.get("time")) >= stamp:
        return out
    # Fill hours between the last one seen and this one.
    filled: list[dict] = []
    if last:
        prev_t = _parse_time(last.get("time"))
        prev_rate = _num(last.get("rate"))
        if prev_t and prev_rate is not None:
            h = prev_t + dt.timedelta(hours=1)
            while h < ftime and len(filled) < 72:
                filled.append({"time": h.isoformat(timespec="seconds"), "rate": prev_rate, "est": True})
                h += dt.timedelta(hours=1)
    filled.append({"time": stamp, "rate": rate, "est": False})
    mark = _mid(q["perp_bid"], q["perp_ask"])
    w = state["wallet"]
    n = int(w.get("short_contracts") or 0)
    pos = (state.get("open") or [None])[0]
    opened = str(pos.get("opened") or "") if isinstance(pos, dict) else ""
    for row in filled:
        row["mark"] = round(mark, 2)
        seen.append(row)
        out["new_hours"] += 1
        if row["est"]:
            out["estimated"] += 1
        if n and opened and row["time"] > opened and row["time"] > str(state.get("funding_through") or ""):
            pay = round(float(row["rate"]) * mark * CONTRACT_BTC * n, 6)  # + = a short gets paid
            state["funding_accrued"] = round(float(state.get("funding_accrued") or 0.0) + pay, 6)
            state["funding_total"] = round(float(state.get("funding_total") or 0.0) + pay, 6)
            state["funding_through"] = row["time"]
            if row["est"]:
                state["est_hours"] = int(state.get("est_hours") or 0) + 1
            if isinstance(pos, dict):
                pos["funding_pnl"] = round(float(pos.get("funding_pnl") or 0.0) + pay, 6)
                pos["funding_hours"] = int(pos.get("funding_hours") or 0) + 1
            out["credited"] = round(out["credited"] + pay, 6)
    state["funding_seen"] = seen[-400:]
    return out


def trailing_funding(state: dict, now: dt.datetime, hours: int = TRAILING_HOURS) -> dict:
    cutoff = (now - dt.timedelta(hours=hours)).isoformat(timespec="seconds")
    rows = [r for r in state.get("funding_seen") or [] if str(r.get("time") or "") > cutoff]
    real = [r for r in rows if not r.get("est")]
    rates = [float(r["rate"]) for r in rows if _num(r.get("rate")) is not None]
    avg = sum(rates) / len(rates) if rates else None
    return {
        "hours": len(rows),
        "real_hours": len(real),
        "avg_hourly": avg,
        "annual": None if avg is None else avg * HOURS_PER_YEAR,
    }


# ----------------------------------------------------------------- decisions

def entry_edge(state: dict, q: dict, cfg: dict, now: dt.datetime) -> dict:
    trail = trailing_funding(state, now)
    out = {"trail": trail, "round_trip": None, "basis": None, "edge": None,
           "floor": cfg["venue_min_edge"], "ok": False, "reason": ""}
    if trail["real_hours"] < MIN_FUNDING_HOURS:
        out["reason"] = f"waiting on funding history ({trail['real_hours']}/{MIN_FUNDING_HOURS} hours)"
        return out
    rt = round_trip_rate(cfg, q)
    basis = q["perp_bid"] / q["spot_ask"] - 1.0  # locked in if the perp drifts back to spot
    edge = float(trail["annual"]) - rt + basis
    out.update({"round_trip": rt, "basis": basis, "edge": edge})
    if edge + 1e-12 < float(cfg["venue_min_edge"]):
        out["reason"] = (f"edge {edge * 100:.2f}%/yr below floor {float(cfg['venue_min_edge']) * 100:.0f}% "
                         f"(funding {float(trail['annual']) * 100:.2f}%/yr, round trip {rt * 100:.2f}%)")
        return out
    out["ok"] = True
    out["reason"] = f"edge {edge * 100:.2f}%/yr clears floor"
    return out


def open_cost(cfg: dict, q: dict) -> dict:
    btc = CONTRACT_BTC * CONTRACTS
    spot_cost = btc * q["spot_ask"]
    spot_fee = spot_cost * float(cfg["spot_taker"])
    pfee = perp_fee(cfg, q["perp_bid"])
    margin = MARGIN_TARGET_X * float(q["short_margin_overnight"]) * _mid(q["perp_bid"], q["perp_ask"]) * btc
    return {
        "btc": btc,
        "spot_cost": round(spot_cost, 4),
        "spot_fee": round(spot_fee, 4),
        "perp_fee": pfee,
        "margin": round(margin, 4),
        "need": round(spot_cost + spot_fee + pfee + margin, 4),
    }


def place_open(state: dict, q: dict, cfg: dict, now: dt.datetime, *, intent_path: str = "", why: str = "") -> dict:
    if state.get("open"):
        return {"bought": False, "reason": "one pair"}
    cost = open_cost(cfg, q)
    w = state["wallet"]
    if float(w["spot_usd"]) + 1e-9 < cost["need"]:
        return {"bought": False, "reason": f"wallet ${w['spot_usd']:.2f} below ${cost['need']:.2f} needed"}
    fill_id = f"btc-carry-cb|{now.isoformat(timespec='seconds')}"
    if intent_path:
        _write_json(intent_path, {
            "tower": "btc-carry", "venue": VENUE, "fill_id": fill_id, "status": "intent",
            "spot_product": SPOT_PRODUCT, "perp_product": PERP_PRODUCT, "contracts": CONTRACTS,
            "need": cost["need"], "paper_only": True,
        })
    equity_before = equity(state, q)
    # 1) Spot wallet buys BTC at the ask, taker fee.
    w["spot_usd"] = round(float(w["spot_usd"]) - cost["spot_cost"] - cost["spot_fee"], 6)
    w["spot_btc"] = round(float(w["spot_btc"]) + cost["btc"], 8)
    # 2) Sweep margin to the futures account.
    _sweep(state, cost["margin"], "to_futures", now, "open margin")
    # 3) Futures account sells 1 BIP at the bid, fee out of futures USD.
    w["futures_usd"] = round(float(w["futures_usd"]) - cost["perp_fee"], 6)
    w["short_contracts"] = CONTRACTS
    w["short_entry"] = q["perp_bid"]
    w["settle_mark"] = q["perp_bid"]
    fees = round(cost["spot_fee"] + cost["perp_fee"], 4)
    state["fees_paid"] = round(float(state.get("fees_paid") or 0.0) + fees, 4)
    state["funding_through"] = _hour_floor(now).isoformat(timespec="seconds")
    if not state.get("last_settle"):
        state["equity_at_settle"] = round(equity_before, 6)
        state["last_settle"] = now.isoformat(timespec="seconds")
    state["open"] = [{
        "ticker": f"{SPOT_PRODUCT} / {PERP_PRODUCT}",
        "team": "BTC carry",
        "side": "long spot / short perp",
        "contracts": CONTRACTS,
        "btc": cost["btc"],
        "cost": round(cost["spot_cost"] + cost["margin"], 4),
        "spot_entry": q["spot_ask"],
        "perp_entry": q["perp_bid"],
        "entry_basis": round(q["perp_bid"] / q["spot_ask"] - 1.0, 6),
        "entry_fees": fees,
        "margin_posted": cost["margin"],
        "funding_pnl": 0.0,
        "funding_hours": 0,
        "opened": now.isoformat(timespec="seconds"),
        "why": why or "funding edge cleared the floor",
        "price_source": "https://api.coinbase.com/api/v3/brokerage/market",
        "price_at": now.isoformat(timespec="seconds"),
        "paper_only": True,
        "shadow_only": True,
        "fill_id": fill_id,
        "exit_name": HOLD_EXIT,
        "exit_plan": _exit_plan(),
    }]
    _sync_cash(state)
    _event(state, now, "open", f"bought {cost['btc']} BTC at {q['spot_ask']:.2f}, sold 1 BIP at {q['perp_bid']:.2f}",
           fees=fees, margin=cost["margin"])
    if intent_path:
        _write_json(intent_path, {"tower": "btc-carry", "fill_id": fill_id, "status": "open", "paper_only": True})
    return {"bought": True, "fill_id": fill_id, "fees": fees, "cost": cost}


def close_pair(state: dict, q: dict, cfg: dict, now: dt.datetime, reason: str, *, forced: bool = False) -> dict:
    """Sell the BTC, buy back the short, sweep everything back to spot."""
    if not state.get("open"):
        return {"closed": False, "reason": "flat"}
    w = state["wallet"]
    n = int(w.get("short_contracts") or 0)
    # Futures account: post funding and the final price change, buy back at the ask.
    exit_price = float(q["perp_ask"])
    w["futures_usd"] = round(float(w["futures_usd"]) + float(state.get("funding_accrued") or 0.0), 6)
    state["funding_accrued"] = 0.0
    if n and w.get("settle_mark") is not None:
        w["futures_usd"] = round(float(w["futures_usd"]) + (float(w["settle_mark"]) - exit_price) * CONTRACT_BTC * n, 6)
    pfee = perp_fee(cfg, exit_price, n)
    if forced:
        pfee = round(max(pfee, float(cfg["liq_fee_rate"]) * exit_price * CONTRACT_BTC * n), 4)
    w["futures_usd"] = round(float(w["futures_usd"]) - pfee, 6)
    # Spot wallet: sell all BTC at the bid, taker fee.
    sale = float(w["spot_btc"]) * float(q["spot_bid"])
    sfee = round(sale * float(cfg["spot_taker"]), 4)
    w["spot_usd"] = round(float(w["spot_usd"]) + sale - sfee, 6)
    w["spot_btc"] = 0.0
    w["short_contracts"] = 0
    w["short_entry"] = None
    w["settle_mark"] = None
    if float(w["futures_usd"]) < 0:
        # A loss past the posted margin is pulled from the spot wallet, like a real deficit.
        _sweep(state, -float(w["futures_usd"]), "to_futures", now, "cover futures deficit")
    _sweep(state, float(w["futures_usd"]), "to_spot", now, "close")
    fees = round(pfee + sfee, 4)
    state["fees_paid"] = round(float(state.get("fees_paid") or 0.0) + fees, 4)
    pos = state["open"][0]
    eq = equity(state, q)
    pnl = round(eq - float(state.get("equity_at_settle") or eq), 4)
    state["closed"].append(_day_row(pos, now, pnl, exit_name="liquidation" if forced else "close",
                                    note=reason, fees=fees))
    state["equity_at_settle"] = eq
    state["last_settle"] = now.isoformat(timespec="seconds")
    state["open"] = []
    _sync_cash(state)
    _event(state, now, "liquidation" if forced else "close", reason, fees=fees, pnl=pnl)
    return {"closed": True, "pnl": pnl, "fees": fees, "forced": forced}


def margin_check(state: dict, q: dict, cfg: dict, now: dt.datetime) -> dict:
    """Keep the futures account funded the way a real sweep would."""
    if not state.get("open"):
        return {"action": "flat"}
    feq = futures_equity(state, q)
    if feq < margin_need(state, q, "intraday"):
        out = close_pair(state, q, cfg, now, "futures account below intraday margin", forced=True)
        return {"action": "liquidated", **out}
    need = margin_need(state, q, "overnight")
    if feq >= TOPUP_AT_X * need:
        return {"action": "ok", "x": round(feq / need, 3)}
    w = state["wallet"]
    short = MARGIN_TARGET_X * need - feq
    from_usd = min(short, max(0.0, float(w["spot_usd"])))
    _sweep(state, from_usd, "to_futures", now, "margin top-up")
    left = round(short - from_usd, 6)
    sold = 0.0
    if left > 0.005 and float(w["spot_btc"]) > 0:
        # Sell just enough BTC (after the taker fee) to cover the rest. The hedge drifts.
        bid = float(q["spot_bid"])
        btc = min(float(w["spot_btc"]), left / (bid * (1 - float(cfg["spot_taker"]))))
        gross = btc * bid
        fee = round(gross * float(cfg["spot_taker"]), 4)
        w["spot_btc"] = round(float(w["spot_btc"]) - btc, 8)
        w["spot_usd"] = round(float(w["spot_usd"]) + gross - fee, 6)
        state["fees_paid"] = round(float(state.get("fees_paid") or 0.0) + fee, 4)
        _sweep(state, gross - fee, "to_futures", now, "margin top-up from BTC sale")
        sold = btc
        _event(state, now, "hedge-drift", f"sold {btc:.8f} BTC to fund margin; spot now below the short", fee=fee)
    _sync_cash(state)
    _event(state, now, "top-up", f"futures at {feq / need:.2f}x overnight margin; moved ${short:.2f}")
    return {"action": "topped_up", "moved": round(short, 4), "btc_sold": sold}


def next_settle_after(stamp: dt.datetime) -> dt.datetime:
    """The next 5 PM New York time after this moment."""
    tz = ZoneInfo("America/New_York") if ZoneInfo else dt.timezone(dt.timedelta(hours=-5))
    local = stamp.astimezone(tz)
    target = local.replace(hour=SETTLE_HOUR_ET, minute=0, second=0, microsecond=0)
    if target <= local:
        target = (local + dt.timedelta(days=1)).replace(hour=SETTLE_HOUR_ET, minute=0, second=0, microsecond=0)
    return target.astimezone(dt.timezone.utc)


def daily_settle(state: dict, q: dict, cfg: dict, now: dt.datetime) -> dict:
    """At 5 PM ET: post funding and the day's price change, write one result."""
    if not state.get("open"):
        return {"settled": False, "reason": "flat"}
    last = _parse_time(state.get("last_settle"))
    if last is None or now < next_settle_after(last):
        return {"settled": False, "reason": "not yet"}
    w = state["wallet"]
    n = int(w.get("short_contracts") or 0)
    mark = _mid(q["perp_bid"], q["perp_ask"])
    variation = (float(w["settle_mark"]) - mark) * CONTRACT_BTC * n if n and w.get("settle_mark") is not None else 0.0
    funding = float(state.get("funding_accrued") or 0.0)
    w["futures_usd"] = round(float(w["futures_usd"]) + funding + variation, 6)
    w["settle_mark"] = mark
    state["funding_accrued"] = 0.0
    need = margin_need(state, q, "overnight")
    if float(w["futures_usd"]) > SWEEP_BACK_AT_X * need:
        _sweep(state, float(w["futures_usd"]) - MARGIN_TARGET_X * need, "to_spot", now, "extra margin back to spot")
    eq = equity(state, q)
    pnl = round(eq - float(state.get("equity_at_settle") or eq), 4)
    pos = state["open"][0]
    state["closed"].append(_day_row(pos, now, pnl, exit_name="day-mark",
                                    note="daily 5 PM ET settle; the hold stays open",
                                    funding=round(funding, 6), variation=round(variation, 6)))
    state["equity_at_settle"] = eq
    state["last_settle"] = now.isoformat(timespec="seconds")
    pos["price_at"] = now.isoformat(timespec="seconds")
    _sync_cash(state)
    return {"settled": True, "pnl": pnl, "funding": funding, "variation": variation}


def exit_check(state: dict, q: dict, cfg: dict, now: dt.datetime) -> dict:
    if not state.get("open"):
        return {"exit": False}
    opened = _parse_time(state["open"][0].get("opened"))
    if opened is None or now - opened < dt.timedelta(days=MIN_HOLD_DAYS):
        return {"exit": False, "reason": "inside the 30-day hold"}
    trail = trailing_funding(state, now)
    if trail["annual"] is None or trail["real_hours"] < MIN_FUNDING_HOURS:
        return {"exit": False, "reason": "not enough funding history"}
    if trail["annual"] < -float(cfg["venue_min_edge"]):
        out = close_pair(state, q, cfg, now, f"7-day funding {trail['annual'] * 100:.2f}%/yr below -2%")
        return {"exit": True, **out}
    return {"exit": False, "reason": "funding fine"}


def _day_row(pos: dict, now: dt.datetime, pnl: float, *, exit_name: str, note: str, **extra) -> dict:
    row = {
        "ticker": pos.get("ticker"),
        "team": "BTC carry",
        "side": "long spot / short perp",
        "exit": exit_name,
        "pnl": pnl,
        "closed": now.isoformat(timespec="seconds"),
        "day": now.date().isoformat(),
        "cost": pos.get("cost"),
        "contracts": pos.get("contracts"),
        "paper_only": True,
        "shadow_only": True,
        "note": note,
    }
    row.update(extra)
    return row


def results(state: dict) -> list[dict]:
    return [r for r in state.get("closed") or [] if isinstance(r, dict)
            and r.get("exit") in ("day-mark", "close", "liquidation")]


def pass_bar(state: dict) -> dict:
    rows = results(state)
    pnls = [float(r["pnl"]) for r in rows if _num(r.get("pnl")) is not None]
    total = round(sum(pnls), 4)
    return {
        "n": len(pnls),
        "needed": 50,
        "total": total,
        "median": statistics.median(pnls) if pnls else None,
        "pass": len(pnls) >= 50 and total > 0 and statistics.median(pnls) > 0,
    }


def _exit_plan() -> dict:
    return {
        "kind": "hold+funding_exit",
        "hold": True,
        "min_hold_days": MIN_HOLD_DAYS,
        "funding_exit": "7-day funding below -2%/yr",
        "forced_close": "futures below intraday margin",
        "staff_close_backstop": True,
        "shadow_only": True,
        "auto_promote": False,
        "fee_floors_locked": True,
        "unlevered": True,
    }


# ----------------------------------------------------------------- cards

def hold_card(state: dict, q: dict, cfg: dict) -> str:
    pos = state["open"][0]
    eq = equity(state, q)
    need = margin_need(state, q, "overnight")
    feq = futures_equity(state, q)
    start = float(state.get("starter_cash") or STARTER_CASH)
    return (
        f"{HOLD_CARD}; since {str(pos.get('opened') or '')[:10]}; "
        f"funding ${float(state.get('funding_total') or 0):+.2f} over {int(pos.get('funding_hours') or 0)}h; "
        f"fees ${float(state.get('fees_paid') or 0):.2f}; "
        f"book ${eq:,.2f} ({eq - start:+.2f}); if closed now ${close_value(state, q, cfg):,.2f}; "
        f"margin {feq / need:.2f}x; results {pass_bar(state)['n']}/50"
    )


def flat_card(state: dict, reason: str) -> str:
    return f"{FLAT_CARD}; {reason}; results {pass_bar(state)['n']}/50"


# ----------------------------------------------------------------- run

def run_once(desk_root: str | None = None, cfg: dict | None = None, fetch=None,
             now: dt.datetime | None = None) -> int:
    desk_root = desk_root or DESK_ROOT
    cfg = locked_cfg(cfg or load_config(os.path.join(desk_root, "btc-carry-paper", "config.json")))
    now = _as_utc(now or dt.datetime.now(dt.timezone.utc))
    if any(os.environ.get(name) for name in KEY_ENV):
        print("SIGNAL: SKIP key is set")
        print("CARD: refusing the check because an exchange key is set. Public data only.")
        print("no trade")
        return 0
    tower = os.path.join(desk_root, "btc-carry-paper")
    os.makedirs(tower, exist_ok=True)
    path = os.path.join(tower, "paper_account.json")
    state = migrate_old_state(_read_state(path), tower)
    try:
        q = (fetch or (lambda: fetch_quotes(now=now)))() or {}
    except Exception as exc:  # noqa: BLE001
        q = {"error": exc.__class__.__name__}
    if not q.get("error"):
        q["error"] = quote_problem(q)
    state["checks"] = int(state.get("checks") or 0) + 1
    state["last_check"] = now.isoformat(timespec="seconds")
    if q.get("error"):
        for pos in state.get("open") or []:
            pos["price_at"] = now.isoformat(timespec="seconds")
        _write_json(path, state)
        _append_research(tower, now, state, q, "data skip")
        print("SIGNAL: SKIP data " + str(q["error"]))
        if state.get("open"):
            print("CARD: " + HOLD_CARD + "; quotes missing this check")
        else:
            print("CARD: " + flat_card(state, "quotes missing: " + str(q["error"])))
            print("no trade")
        return 0
    before = len(results(state))
    record_funding(state, q, now)
    margin_check(state, q, cfg, now)
    daily_settle(state, q, cfg, now)
    exit_check(state, q, cfg, now)
    action = "hold" if state.get("open") else "flat"
    reason = ""
    if not state.get("open"):
        blocked = os.environ.get("DESK_BLOCK_ENTRIES") == "1"
        edge = entry_edge(state, q, cfg, now)
        state["last_edge"] = {k: edge[k] for k in ("edge", "round_trip", "basis", "floor", "reason")}
        state["last_edge"]["funding_annual"] = edge["trail"]["annual"]
        state["last_edge"]["funding_hours"] = edge["trail"]["real_hours"]
        reason = edge["reason"]
        if blocked:
            reason = "desk entry gate"
        elif edge["ok"]:
            placed = place_open(state, q, cfg, now, intent_path=os.path.join(tower, "buy_intent.json"),
                                why=edge["reason"])
            action = "open" if placed.get("bought") else "flat"
            reason = edge["reason"] if placed.get("bought") else placed.get("reason", "")
    for pos in state.get("open") or []:
        pos["price_at"] = now.isoformat(timespec="seconds")
    state["last_action"] = action
    state["pass_bar"] = pass_bar(state)
    state["book_value"] = equity(state, q)
    state["close_value"] = close_value(state, q, cfg)
    _sync_cash(state)
    _record_results(desk_root, state, before)
    _write_json(path, state)
    _append_research(tower, now, state, q, reason)
    if state.get("open"):
        print(f"SIGNAL: {'OPEN' if action == 'open' else 'HOLD'} BTC carry on Coinbase")
        print("CARD: " + hold_card(state, q, cfg))
    else:
        print("SIGNAL: SKIP flat")
        print("CARD: " + flat_card(state, reason))
        print("no trade")
    return 0


def _record_results(desk_root: str, state: dict, before: int) -> None:
    """New daily results count toward the 50. They never promote the tower."""
    fresh = results(state)[before:]
    if not fresh:
        return
    try:
        if desk_root not in sys.path:
            sys.path.insert(0, desk_root)
        import desk_roi_plan
    except Exception:
        return
    for row in fresh:
        try:
            desk_roi_plan.record_incubation_settle(
                desk_root, series=INCUBATION_SERIES, bot="btc-carry", pnl=row.get("pnl"),
                contracts=1, note="shadow daily settle; no auto-promote",
            )
        except Exception:
            return


def _append_research(tower: str, now: dt.datetime, state: dict, q: dict, reason: str) -> None:
    line = json.dumps({
        "at": now.isoformat(timespec="seconds"),
        "action": state.get("last_action"),
        "open": len(state.get("open") or []),
        "cash": state.get("cash"),
        "book": state.get("book_value"),
        "funding_rate": q.get("funding_rate"),
        "funding_time": q.get("funding_time"),
        "spot_bid": q.get("spot_bid"), "spot_ask": q.get("spot_ask"),
        "perp_bid": q.get("perp_bid"), "perp_ask": q.get("perp_ask"),
        "reason": reason,
        "error": q.get("error") or "",
        "paper_only": True,
    }) + "\n"
    try:
        with open(os.path.join(tower, "research.jsonl"), "a", encoding="utf-8") as handle:
            handle.write(line)
    except OSError:
        return


# ----------------------------------------------------------------- helpers

def _get_json(url: str):
    if not url.startswith(API):
        raise ValueError("public market data only")
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        raise


def _mid(a, b) -> float:
    return (float(a) + float(b)) / 2.0


def _hour_floor(t: dt.datetime) -> dt.datetime:
    return t.replace(minute=0, second=0, microsecond=0)


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
    # Follow the desk's volume link so the save is not undone by the next re-link.
    if os.path.islink(path):
        path = os.path.realpath(path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    os.replace(tmp, path)


def _parse_time(value) -> dt.datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _as_utc(parsed)


def _as_utc(value: dt.datetime) -> dt.datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(dt.timezone.utc)


def _num(value) -> float | None:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) else None


def reset_account(desk_root: str | None = None) -> None:
    tower = os.path.join(desk_root or DESK_ROOT, "btc-carry-paper")
    for name in ("paper_account.json", "research.jsonl", "buy_intent.json"):
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
    if "--twins" in argv:
        print(json.dumps(twin_research_card(), indent=2, sort_keys=True))
        return 0
    return run_once()


if __name__ == "__main__":
    raise SystemExit(main())
