"""Model lab: score new model ideas on real 15-minute windows before any tower uses them.

Research only. Buys nothing. Every check it reads Coinbase 1-minute candles and
the open Kalshi 15-minute "up or down" markets for BTC, ETH, SOL, XRP and DOGE,
and logs, for each window with 1 to 14 minutes left:

* the fair price the way More 15m does it today (last-hour move, normal tails);
* the same with a 15/60/240-minute blended move (422-423);
* the same with fatter tails (421);
* the same with a time-of-day factor (424);
* log-only inputs: jump guard (426), book imbalance from the top-of-book sizes
  (435-436), tape momentum is not read here to keep reads low, and whether BTC
  is moving the other coins the same way (439-440).

When a window settles it records Kalshi's result and the real move in model
units, then grades each method (Brier score, lower is better), the error by
minutes left (431), the swing multiplier per market with a weekly cap (427-429)
and three exit rules on the logged paths (444-448). Nothing is used by a tower
until it has 50+ settled rows and Levi says yes (455).

Pure logic here; network reads are passed in.
"""
from __future__ import annotations

import datetime as dt
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DESK_ROOT = os.path.dirname(HERE)
if DESK_ROOT not in sys.path:
    sys.path.insert(0, DESK_ROOT)

import shared_models as sm  # noqa: E402

# series -> (label, Coinbase product, sigma floor per minute) - floors copied from More 15m
SERIES = {
    "KXBTC15M": ("BTC", "BTC-USD", 0.0003),
    "KXETH15M": ("ETH", "ETH-USD", 0.0003),
    "KXSOL15M": ("SOL", "SOL-USD", 0.0004),
    "KXXRP15M": ("XRP", "XRP-USD", 0.0004),
    "KXDOGE15M": ("DOGE", "DOGE-USD", 0.0005),
}
METHODS = ("fair_now", "fair_blend", "fair_student", "fair_tod")
MIN_MIN, MAX_MIN = 1.0, 14.0
MAX_PENDING = 2000
MAX_SCORED = 4000
MAX_SETTLE_READS = 20
SETTLE_GRACE_SEC = 120
ENTRY_EDGE = 0.05            # locked BTC / commodity floor; a replay buy needs this much
EXIT_RULES = {
    "flip-only": {},
    "little-left": {"little_left": 0.02},
    "time-decay": {"decay_min": 4.0, "decay_cushion": 0.60},
}
MULT_FILE_KEY = "multipliers"


def _num(v):
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) else None


def _ts(text):
    try:
        return dt.datetime.fromisoformat(str(text).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def kalshi_fee(p):
    p = float(p)
    if not 0 < p < 1:
        return 0.0
    return math.ceil(round(0.07 * p * (1 - p) * 100, 6)) / 100


def closes_from_candles(rows) -> list[tuple]:
    """Coinbase candles [[time, low, high, open, close, vol], ...] -> [(time, close)] oldest first."""
    out = [(int(r[0]), float(r[4])) for r in rows or [] if isinstance(r, (list, tuple)) and len(r) >= 5]
    return sorted(out)


def window_rows(series: str, markets: list[dict], closes: list[tuple], now: dt.datetime,
                lead_ret: float | None, others: dict, mults: dict) -> list[dict]:
    label, _, floor = SERIES[series]
    px = [c for _, c in closes]
    if len(px) < 30:
        return []
    spot = px[-1]
    sig_now = sm.realized_sigma(px, 60)
    sig_blend = sm.blended_sigma(px)
    if sig_now is None:
        return []
    mult = float(mults.get(series, 1.0))
    sig_now = max(floor, mult * sig_now)
    sig_blend = max(floor, mult * (sig_blend or sig_now))
    tod = sm.time_of_day_mult(now)
    jump = sm.jump_guard(px)
    cross = sm.cross_market(lead_ret, {k: v for k, v in others.items() if k != series}) if series == "KXBTC15M" \
        else {"same_way": None, "n": 0}
    out = []
    for m in markets or []:
        close, strike = _ts(m.get("close_time")), _num(m.get("floor_strike"))
        if close is None or not strike:
            continue
        minutes = (close - now.timestamp()) / 60.0
        if not (MIN_MIN <= minutes <= MAX_MIN):
            continue
        t_eff = max(0.25, minutes - 0.67)
        row = {
            "ticker": str(m.get("ticker") or ""), "series": series, "label": label,
            "at": now.isoformat(timespec="seconds"), "close": close, "minutes": round(minutes, 2),
            "spot": spot, "strike": strike, "sigma": round(sig_now, 7), "t_eff": round(t_eff, 3),
            "fair_now": round(sm.fair_up(spot, strike, sig_now, t_eff, clip=(0.01, 0.99)), 4),
            "fair_blend": round(sm.fair_up(spot, strike, sig_blend, t_eff, clip=(0.01, 0.99)), 4),
            "fair_student": round(sm.fair_up(spot, strike, sig_now, t_eff, tails="student",
                                             clip=(0.01, 0.99)), 4),
            "fair_tod": round(sm.fair_up(spot, strike, sig_now * tod, t_eff, clip=(0.01, 0.99)), 4),
            "jump": jump["jump"],
            "imbalance": sm.book_imbalance(
                [(0, _num(m.get("yes_bid_size_fp")) or 0)], [(1, _num(m.get("yes_ask_size_fp")) or 0)], 1),
            "btc_pull": cross.get("same_way"),
            "yes_ask": _num(m.get("yes_ask_dollars")), "no_ask": _num(m.get("no_ask_dollars")),
            "yes_bid": _num(m.get("yes_bid_dollars")), "no_bid": _num(m.get("no_bid_dollars")),
        }
        out.append(row)
    return out


def last_return(closes: list[tuple]) -> float | None:
    if len(closes) < 2 or closes[-2][1] <= 0:
        return None
    return math.log(closes[-1][1] / closes[-2][1])


def price_at(closes: list[tuple], ts: float) -> float | None:
    """Close of the last 1-minute candle that ends at or before ``ts`` (60s-average proxy)."""
    best = None
    for t, c in closes:
        if t + 60 <= ts + 1e-9:
            best = c
    return best


def settle(pending: list[dict], fetch, closes_by: dict, now: dt.datetime, max_reads: int = MAX_SETTLE_READS):
    """Attach Kalshi's result to windows that closed. Returns (still_pending, scored, notes)."""
    keep, done, notes, cache, reads = [], [], [], {}, 0
    for row in pending:
        if row["close"] + SETTLE_GRACE_SEC > now.timestamp():
            keep.append(row)
            continue
        t = row["ticker"]
        if t not in cache:
            if reads >= max_reads:
                keep.append(row)
                continue
            reads += 1
            try:
                cache[t] = str((fetch(t) or {}).get("result") or "").lower()
            except Exception as exc:  # noqa: BLE001
                cache[t] = None
                notes.append(f"{t} result read failed ({type(exc).__name__})")
        result = cache[t]
        if result not in ("yes", "no"):
            if now.timestamp() - row["close"] > 6 * 3600:
                continue                     # never settled in 6 hours: drop, do not guess
            keep.append(row)
            continue
        final = price_at(closes_by.get(row["series"]) or [], row["close"])
        z = None
        if final and row.get("sigma") and row.get("t_eff"):
            z = math.log(final / row["spot"]) / (row["sigma"] * math.sqrt(row["t_eff"]))
        done.append(dict(row, won=result == "yes", z_real=None if z is None else round(z, 4)))
    return keep, done, notes[:10]


def replay_exits(scored: list[dict]) -> dict:
    """Paper replay of three exit rules on logged paths (444-448).

    A replay buy is the first logged row where fair - ask - fee >= 0.05 on a
    side. Later rows of the same window are checked with each rule; a rule that
    sells books bid - fee, otherwise the window settles. P&L per contract.
    """
    by = {}
    for r in scored:
        by.setdefault(r["ticker"], []).append(r)
    out = {name: {"n": 0, "pnl": 0.0, "sold": 0} for name in EXIT_RULES}
    out["hold"] = {"n": 0, "pnl": 0.0, "sold": 0}
    for rows in by.values():
        rows.sort(key=lambda r: r["at"])
        entry = None
        for i, r in enumerate(rows):
            for side in ("yes", "no"):
                ask = r.get(f"{side}_ask")
                if ask is None or not 0 < ask < 1:
                    continue
                fair = sm.side_fair(r["fair_now"], side)
                if fair - ask - kalshi_fee(ask) >= ENTRY_EDGE:
                    entry = (i, side, ask)
                    break
            if entry:
                break
        if not entry:
            continue
        i, side, ask = entry
        won = rows[i]["won"] if side == "yes" else not rows[i]["won"]
        settle_pnl = (1.0 if won else 0.0) - ask - kalshi_fee(ask)
        out["hold"]["n"] += 1
        out["hold"]["pnl"] += settle_pnl
        for name, rule in EXIT_RULES.items():
            pnl = settle_pnl
            for later in rows[i + 1:]:
                bid = later.get(f"{side}_bid")
                d = sm.exit_decision(fair=sm.side_fair(later["fair_now"], side), bid=bid,
                                     fee=kalshi_fee(bid) if bid else 0.0, minutes_left=later["minutes"],
                                     rules=rule)
                if d["sell"]:
                    pnl = bid - kalshi_fee(bid) - ask - kalshi_fee(ask)
                    out[name]["sold"] += 1
                    break
            out[name]["n"] += 1
            out[name]["pnl"] += pnl
    for v in out.values():
        v["pnl"] = round(v["pnl"], 4)
        v["per_trade"] = round(v["pnl"] / v["n"], 4) if v["n"] else None
        v["counts"] = sm.enough_data(v["n"])
    return out


def feature_check(scored: list[dict], key: str, split=0.0) -> dict:
    """Does a log-only feature explain what the model missed? Mean (won - fair) above/below ``split``."""
    hi = [r for r in scored if r.get(key) is not None and r[key] > split]
    lo = [r for r in scored if r.get(key) is not None and r[key] <= split]

    def miss(rows):
        if not rows:
            return None
        return round(sum((1.0 if r["won"] else 0.0) - r["fair_now"] for r in rows) / len(rows), 4)

    return {"above_n": len(hi), "above_miss": miss(hi), "below_n": len(lo), "below_miss": miss(lo),
            "counts": sm.enough_data(min(len(hi), len(lo)))}


def summarize(scored: list[dict], prior_mults: dict, now: dt.datetime, last_refresh: str | None) -> dict:
    methods = {m: sm.compare(scored, "fair_now", m) for m in METHODS[1:]}
    jumpy = [r for r in scored if r.get("jump")]
    calm = [r for r in scored if r.get("jump") is False]
    mults = dict(prior_mults or {})
    measured = {}
    refresh = last_refresh is None or (now - dt.datetime.fromisoformat(last_refresh)).days >= 7
    for series in SERIES:
        zs = [r["z_real"] for r in scored if r["series"] == series and r.get("z_real") is not None]
        val = sm.measured_multiplier(zs)
        measured[series] = {"n": len(zs), "measured": None if val is None else round(val, 3)}
        if refresh:
            mults[series] = sm.next_multiplier(mults.get(series, 1.0), val, len(zs))
    return {
        "methods": methods,
        "error_by_minutes": sm.error_by_minutes([{"minutes": r["minutes"], "fair": r["fair_now"], "won": r["won"]}
                                                 for r in scored]),
        "jump_guard": {"jump_n": len(jumpy), "jump_brier": sm.brier(jumpy, "fair_now"),
                       "calm_n": len(calm), "calm_brier": sm.brier(calm, "fair_now")},
        "imbalance": feature_check(scored, "imbalance"),
        "btc_pull": feature_check(scored, "btc_pull", 0.5),
        "exits": replay_exits(scored),
        "multipliers_measured": measured,
        MULT_FILE_KEY: mults,
        "multipliers_refreshed": now.isoformat(timespec="seconds") if refresh else last_refresh,
    }


def run(prior: dict, now: dt.datetime, *, candles, open_markets, market) -> dict:
    """One check. ``candles(product)``, ``open_markets(series)``, ``market(ticker)``."""
    prior = prior or {}
    notes = []
    closes_by, rets = {}, {}
    for series, (_, product, _) in SERIES.items():
        try:
            closes_by[series] = closes_from_candles(candles(product))
            rets[series] = last_return(closes_by[series])
        except Exception as exc:  # noqa: BLE001 - one market failing does not stop the rest
            notes.append(f"{product} candles failed ({type(exc).__name__})")
    mults = dict(prior.get(MULT_FILE_KEY) or {})
    pending = list(prior.get("pending") or [])
    seen = {(r["ticker"], r["at"][:16]) for r in pending}
    for series in SERIES:
        if series not in closes_by:
            continue
        try:
            markets = open_markets(series)
        except Exception as exc:  # noqa: BLE001
            notes.append(f"{series} markets failed ({type(exc).__name__})")
            continue
        for row in window_rows(series, markets, closes_by[series], now, rets.get("KXBTC15M"), rets, mults):
            if (row["ticker"], row["at"][:16]) not in seen:
                pending.append(row)
    pending, done, more = settle(pending, market, closes_by, now)
    notes += more
    scored = (list(prior.get("scored") or []) + done)[-MAX_SCORED:]
    body = {"at": now.isoformat(timespec="seconds"), "paper_only": True, "research": True,
            "pending": pending[-MAX_PENDING:], "scored": scored, "new_scored": len(done),
            "notes": notes[:10]}
    body.update(summarize(scored, mults, now, prior.get("multipliers_refreshed")))
    return body


def card(body: dict) -> str:
    n = len(body.get("scored") or [])
    parts = [f"{n} settled 15-minute windows scored"]
    for name, row in (body.get("methods") or {}).items():
        parts.append(f"{name.replace('fair_', '')}: {row['verdict']}")
    return "; ".join(parts)
