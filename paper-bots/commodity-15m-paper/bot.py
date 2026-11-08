#!/usr/bin/env python3
"""
commodity-15m-paper/bot.py — PAPER tower for Kalshi metals/energy 15m markets.

Series priority (#560): liquid first (gold, WTI), then mid liquidity
(silver / brent / copper / platinum), thin last (palladium, natgas).
Same desk adapt gates as BTC (vol-safe / Wilson ≥80% play-big). No live orders.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import statistics
import sys
import time
import urllib.request

KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
UA = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; commodity-15m-paper/1.0; +https://github.com/LevMilli/bot)"
    )
}

# #560 liquid-first SERIES order — evaluate/prefetch spends cycles on gold/WTI
# before thin books (palladium/natgas). Never softens 0.05 floor.
SERIES = (
    "KXGOLD15M",       # liquid metal
    "KXWTI15M",        # liquid energy
    "KXSILVER15M",     # mid
    "KXBRENT15M",      # mid energy
    "KXCOPPER15M",     # mid metal
    "KXPLATINUM15M",   # mid metal
    "KXPALLADIUM15M",  # thin
    "KXNATGAS15M",     # thin / high-σ — last
)

# Yahoo symbols for spot (fail-closed if missing).
YAHOO = {
    "KXPALLADIUM15M": "PA=F",
    "KXNATGAS15M": "NG=F",
    "KXCOPPER15M": "HG=F",
    "KXBRENT15M": "BZ=F",
    "KXWTI15M": "CL=F",
    "KXSILVER15M": "SI=F",
    "KXGOLD15M": "GC=F",
    "KXPLATINUM15M": "PL=F",
}

MIN_MINUTES_LEFT = 8
MIN_MODEL_ACCURATE = 0.80
MIN_MODEL_SPEED = 0.72       # match sports/BTC speed lane; needs SPEED_EDGE_EXTRA
MIN_MODEL_PROB = MIN_MODEL_ACCURATE
SPEED_EDGE_EXTRA = 0.02
MIN_Z = 0.60
MIN_Z_SPEED = 0.55           # speed lane near-miss z when extra edge clears
MAX_BUYS_PER_CHECK = 3
ASK_MIN, ASK_MAX = 0.70, 0.92
MAX_SPREAD = 0.05
MIN_DEPTH = 2
EDGE_BUFFER = 0.05
# Relative cushion floors (fraction of spot) — commodities have different scales.
MIN_CUSHION_FRAC = {
    "KXNATGAS15M": 0.0015,
    "KXCOPPER15M": 0.0008,
    "KXSILVER15M": 0.0010,
    "KXGOLD15M": 0.0006,
    "KXPLATINUM15M": 0.0008,
    "KXPALLADIUM15M": 0.0008,
    "KXBRENT15M": 0.0010,
    "KXWTI15M": 0.0010,
}

# Portfolio corr cap: at most one energy + one metal open at a time.
ENERGY_SERIES = frozenset({"KXNATGAS15M", "KXBRENT15M", "KXWTI15M"})
METAL_SERIES = frozenset({
    "KXGOLD15M", "KXSILVER15M", "KXPLATINUM15M", "KXPALLADIUM15M", "KXCOPPER15M",
})


def series_family(series: str) -> str:
    s = str(series or "")
    if s in ENERGY_SERIES:
        return "energy"
    if s in METAL_SERIES:
        return "metal"
    return "other"


def open_families(state: dict) -> set[str]:
    out = set()
    for pos in state.get("open") or []:
        if not isinstance(pos, dict):
            continue
        fam = series_family(str(pos.get("series") or ""))
        if fam != "other":
            out.add(fam)
    return out

HERE = os.path.dirname(os.path.abspath(__file__))
DESK_ROOT = os.path.dirname(HERE)
ACCOUNT = os.path.join(HERE, "paper_account.json")
PAPER_CASH = 100.0


def _desk():
    if DESK_ROOT not in sys.path:
        sys.path.insert(0, DESK_ROOT)
    import pimp_desk
    return pimp_desk


def get_json(url: str, timeout: int = 20) -> dict:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def load_account() -> dict:
    if os.path.exists(ACCOUNT):
        try:
            with open(ACCOUNT, encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                data.setdefault("cash", PAPER_CASH)
                data.setdefault("open", [])
                data.setdefault("closed", [])
                data["paper_only"] = True
                return data
        except (OSError, json.JSONDecodeError):
            pass
    return {"cash": PAPER_CASH, "open": [], "closed": [], "paper_only": True}


def save_account(state: dict) -> None:
    path = ACCOUNT
    if os.path.islink(path):
        path = os.path.realpath(path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
        handle.write("\n")
    os.replace(tmp, path)


def phi(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def yahoo_spot(symbol: str) -> float | None:
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{symbol}?interval=1m&range=1d"
    )
    try:
        data = get_json(url, timeout=15)
        result = ((data.get("chart") or {}).get("result") or [None])[0]
        if not result:
            return None
        meta = result.get("meta") or {}
        px = meta.get("regularMarketPrice")
        if px is None:
            quotes = ((result.get("indicators") or {}).get("quote") or [{}])[0]
            closes = [c for c in (quotes.get("close") or []) if c is not None]
            px = closes[-1] if closes else None
        return float(px) if px is not None else None
    except Exception:
        return None


def spots_by_series() -> dict[str, float]:
    out = {}
    for series, symbol in YAHOO.items():
        px = yahoo_spot(symbol)
        if px is not None and px > 0:
            out[series] = px
        time.sleep(0.05)
    return out


def list_open(series: str, limit: int = 4) -> list[dict]:
    try:
        data = get_json(f"{KALSHI}/markets?series_ticker={series}&status=open&limit={limit}")
    except Exception:
        return []
    rows = []
    for m in data.get("markets") or []:
        try:
            strike = float(m.get("floor_strike"))
        except (TypeError, ValueError):
            continue
        close = m.get("close_time")
        try:
            when = dt.datetime.fromisoformat(str(close).replace("Z", "+00:00"))
        except Exception:
            continue
        yes_ask = m.get("yes_ask_dollars")
        no_ask = m.get("no_ask_dollars")
        yes_bid = m.get("yes_bid_dollars")
        no_bid = m.get("no_bid_dollars")
        try:
            yes_ask_f = float(yes_ask) if yes_ask not in (None, "") else None
            no_ask_f = float(no_ask) if no_ask not in (None, "") else None
            yes_bid_f = float(yes_bid) if yes_bid not in (None, "") else None
            no_bid_f = float(no_bid) if no_bid not in (None, "") else None
        except (TypeError, ValueError):
            continue
        rows.append({
            "ticker": m.get("ticker"),
            "series": series,
            "target": strike,
            "close_time": when,
            "yes_ask": yes_ask_f,
            "no_ask": no_ask_f,
            "yes_bid": yes_bid_f,
            "no_bid": no_bid_f,
            "title": m.get("title") or series,
        })
    rows.sort(key=lambda r: r["close_time"])
    return rows


def _fetch_orderbook_raw(ticker: str):
    return get_json(f"{KALSHI}/markets/{ticker}/orderbook")


def depth_from_book(data, side: str, ask: float) -> tuple[float | None, int]:
    """Spread + depth from a raw Kalshi orderbook payload (or None)."""
    if not data:
        return None, 0
    book = data.get("orderbook") if isinstance(data, dict) else data
    if not isinstance(book, dict):
        return None, 0
    key = "yes" if side == "YES" else "no"
    levels = book.get(key) or book.get(f"{key}_dollars") or []
    depth = 0
    best_bid = None
    for level in levels:
        try:
            if isinstance(level, (list, tuple)) and len(level) >= 2:
                px, qty = float(level[0]), float(level[1])
            elif isinstance(level, dict):
                px = float(level.get("price") or level.get("price_dollars") or 0)
                qty = float(level.get("quantity") or level.get("count") or 0)
            else:
                continue
        except (TypeError, ValueError):
            continue
        # Kalshi sometimes stores cents.
        if px > 1.5:
            px = px / 100.0
        if best_bid is None or px > best_bid:
            best_bid = px
        if ask is not None and px + 1e-9 >= float(ask) - 0.02:
            depth += int(qty)
    spread = None
    if best_bid is not None and ask is not None:
        spread = max(0.0, float(ask) - float(best_bid))
    return spread, depth


def book_depth(ticker: str, side: str, ask: float) -> tuple[float | None, int]:
    try:
        data = _fetch_orderbook_raw(ticker)
    except Exception:
        return None, 0
    return depth_from_book(data, side, ask)


def prefetch_commodity_books(jobs: list[tuple[str, str, float]]) -> dict:
    """Parallel orderbook fetch. jobs = [(ticker, side, ask), ...].

    Returns {ticker: (spread, depth)}.
    """
    if not jobs:
        return {}
    try:
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        import desk_more
        tickers = sorted({str(t) for t, _s, _a in jobs if t})
        raw_ok, _errs = desk_more.prefetch_map(tickers, _fetch_orderbook_raw, max_workers=8)
    except Exception:
        raw_ok = {}
        for ticker, _side, _ask in jobs:
            if ticker in raw_ok:
                continue
            try:
                raw_ok[ticker] = _fetch_orderbook_raw(str(ticker))
            except Exception:
                raw_ok[ticker] = None
    out = {}
    for ticker, side, ask in jobs:
        out[str(ticker)] = depth_from_book(raw_ok.get(str(ticker)), side, ask)
    return out


def kalshi_fee(price: float) -> float:
    return math.ceil(round(0.07 * float(price) * (1.0 - float(price)) * 100, 6)) / 100


def paper_sell(state: dict, pos: dict, bid: float, fee: float, reason: str) -> float:
    """Flatten one commodity paper position at bid − fee. No live order."""
    contracts = float(pos.get("contracts") or 0)
    per = max(0.0, float(bid) - float(fee or 0))
    proceeds = round(contracts * per, 2)
    pnl = round(proceeds - float(pos.get("cost") or 0), 2)
    state["cash"] = round(float(state.get("cash") or 0) + proceeds, 2)
    closed = dict(pos)
    closed.update({
        "closed": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "exit": reason,
        "exit_price": round(float(bid), 4),
        "payout": proceeds,
        "pnl": pnl,
    })
    state.setdefault("closed", []).append(closed)
    try:
        import desk_roi_plan
        desk_roi_plan.record_incubation_settle(
            DESK_ROOT,
            series=str(pos.get("series") or ""),
            bot="commodity-15m",
            pnl=pnl,
            contracts=pos.get("contracts"),
            note=str(reason or "")[:80],
        )
        desk_roi_plan.record_fee_ledger(
            DESK_ROOT,
            bot="commodity-15m",
            ticker=str(pos.get("ticker") or ""),
            side=str(pos.get("side") or ""),
            price=bid,
            contracts=pos.get("contracts"),
            fee=fee,
            pnl=pnl,
            fill_id=str(pos.get("fill_id") or ""),
            kind="sell",
            note=str(reason or "")[:120],
        )
        desk_roi_plan.record_adverse_fill(
            DESK_ROOT,
            bot="commodity-15m",
            ticker=str(pos.get("ticker") or ""),
            entry_price=(
                pos.get("entry") if pos.get("entry") is not None
                else pos.get("price") if pos.get("price") is not None
                else pos.get("ask")
            ),
            mark_price=bid,
            note=str(reason or "")[:120],
        )
        try:
            import desk_living
            import teller_memory
            desk_living.record_completion(
                DESK_ROOT,
                bot="commodity-15m",
                ticker=str(pos.get("ticker") or ""),
                side=str(pos.get("side") or ""),
                pnl=pnl,
                contracts=pos.get("contracts"),
                fill_id=str(pos.get("fill_id") or ""),
                kind="sell",
                eligible=True,
                note=str(reason or "")[:120],
            )
            teller_memory.remember(
                DESK_ROOT,
                kind="wins" if float(pnl) > 0 else "mistakes",
                text=f"commodity {reason} {pos.get('ticker')} pnl {float(pnl):+.2f}"[:200],
                bot_id="commodity-15m",
            )
        except Exception:
            pass
        helper = str(pos.get("helper_source") or "").strip()
        if helper:
            desk_roi_plan.record_helper_fill(
                DESK_ROOT,
                helper=helper,
                bot="commodity-15m",
                ticker=str(pos.get("ticker") or ""),
                pnl=pnl,
                contracts=pos.get("contracts"),
                fill_id=str(pos.get("fill_id") or ""),
                note=str(reason or "")[:120],
            )
    except Exception:
        pass
    return pnl


def manage_model_flips(state: dict, side_now, prob_now, bid, fee, delta, ticker=None) -> list[str]:
    """Exit open commodity paper when the live model flips against the held side."""
    still = []
    sold = []
    for pos in list(state.get("open") or []):
        if ticker and pos.get("ticker") != ticker:
            still.append(pos)
            continue
        held = str(pos.get("side") or "").upper()
        fair_entry = pos.get("fair_at_entry")
        flip = False
        reason = ""
        if held and side_now and held != str(side_now).upper():
            flip = True
            reason = f"model-flip side {held}→{side_now}"
        else:
            try:
                if DESK_ROOT not in sys.path:
                    sys.path.insert(0, DESK_ROOT)
                import desk_profit
                if desk_profit.model_flip_adverse(held, fair_entry, prob_now, delta):
                    flip = True
                    reason = f"model-flip fair Δ≥{delta:g}"
            except Exception:
                pass
        if flip and bid is not None and float(bid) > 0:
            pnl = paper_sell(state, pos, bid, fee, reason)
            sold.append(f"{pos.get('ticker')} {reason} pnl {pnl:+.2f}")
        else:
            still.append(pos)
    state["open"] = still
    return sold


def settle_account(state: dict) -> None:
    still = []
    now = dt.datetime.now(dt.timezone.utc)
    for pos in list(state.get("open") or []):
        close = str(pos.get("close_time") or "")
        try:
            when = dt.datetime.fromisoformat(close.replace("Z", "+00:00"))
        except ValueError:
            still.append(pos)
            continue
        if when > now:
            still.append(pos)
            continue
        try:
            payload = get_json(f"{KALSHI}/markets/{pos.get('ticker')}")
        except Exception:
            still.append(pos)
            continue
        market = payload.get("market") if isinstance(payload, dict) else None
        if not isinstance(market, dict):
            market = payload if isinstance(payload, dict) else {}
        result = market.get("result")
        if result not in ("yes", "no"):
            still.append(pos)
            continue
        won = (result == "yes" and pos.get("side") == "YES") or (result == "no" and pos.get("side") == "NO")
        payout = float(pos.get("contracts") or 0) * (1.0 if won else 0.0)
        pnl = round(payout - float(pos.get("cost") or 0), 2)
        state["cash"] = round(float(state.get("cash") or 0) + payout, 2)
        pos.update({
            "closed": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "pnl": pnl,
            "payout": round(payout, 2),
            "exit": "settled",
        })
        state.setdefault("closed", []).append(pos)
        try:
            if DESK_ROOT not in sys.path:
                sys.path.insert(0, DESK_ROOT)
            import kalshi_history
            kalshi_history.record_settle(
                DESK_ROOT,
                ticker=str(pos.get("ticker") or ""),
                series=str(pos.get("series") or ""),
                result=str(result),
                side=str(pos.get("side") or ""),
                note="commodity-15m settle",
            )
        except Exception:
            pass
        try:
            if DESK_ROOT not in sys.path:
                sys.path.insert(0, DESK_ROOT)
            import desk_roi_plan
            desk_roi_plan.record_incubation_settle(
                DESK_ROOT,
                series=str(pos.get("series") or ""),
                bot="commodity-15m",
                pnl=pnl,
                contracts=pos.get("contracts"),
                note="settled",
            )
            desk_roi_plan.record_fee_ledger(
                DESK_ROOT,
                bot="commodity-15m",
                ticker=str(pos.get("ticker") or ""),
                side=str(pos.get("side") or ""),
                price=pos.get("ask") or pos.get("entry_price"),
                contracts=pos.get("contracts"),
                fee=0.0,
                pnl=pnl,
                fill_id=str(pos.get("fill_id") or ""),
                kind="settle",
                note="settled",
            )
            # Near-miss would_pnl densify — label soft z|p skips for this ticker.
            try:
                desk_roi_plan.label_near_miss_from_result(
                    DESK_ROOT,
                    ticker=str(pos.get("ticker") or ""),
                    result=str(result),
                    bot="commodity-15m",
                    note="commodity-15m settle label",
                )
            except Exception:
                pass
            # Settle-retro time-stop densify — last minutes missed before close.
            # Evaluate with now≈close (minutes_left≈0). Still NO live sell.
            if not pos.get("time_stop_shadowed"):
                side = str(pos.get("side") or "YES").upper()
                raw = (
                    market.get("yes_bid_dollars") if side == "YES"
                    else market.get("no_bid_dollars")
                )
                if raw in (None, ""):
                    raw = (
                        market.get("yes_bid") if side == "YES"
                        else market.get("no_bid")
                    )
                bid_ts = float(raw) if raw not in (None, "") else None
                if bid_ts is not None and bid_ts > 1.5:
                    bid_ts = bid_ts / 100.0
                # bid=0 is a real finalized-loser quote; only skip missing bids.
                # Still skip inventing time-stops on settle winners (pnl≥0 + bid≤0).
                if bid_ts is not None and bid_ts >= 0:
                    wipe_quote = bid_ts <= 0
                    if wipe_quote and float(pnl) + 1e-12 >= 0.0:
                        pass
                    else:
                        hit = desk_roi_plan.commodity_time_stop_hit(
                            pos.get("close_time"),
                            bid_ts,
                            pos.get("entry") or pos.get("price") or pos.get("ask"),
                            cost=pos.get("cost"),
                            contracts=pos.get("contracts"),
                            now=when,  # close instant → minutes_left≈0
                        )
                        if hit.get("hit"):
                            desk_roi_plan.record_commodity_time_stop_shadow(
                                DESK_ROOT,
                                ticker=str(pos.get("ticker") or ""),
                                side=side,
                                series=str(pos.get("series") or ""),
                                close_time=str(pos.get("close_time") or ""),
                                entry_price=(
                                    pos.get("entry") or pos.get("price") or pos.get("ask")
                                ),
                                bid=bid_ts,
                                contracts=pos.get("contracts"),
                                cost=pos.get("cost"),
                                note="settle-retro shadow time-stop — no live sell",
                                now=when,
                            )
                            pos["time_stop_shadowed"] = True
        except Exception:
            pass
    state["open"] = still


def evaluate(m: dict, spot: float, edge_buf: float, book=None) -> dict:
    target = float(m["target"])
    side = "YES" if spot > target else "NO"
    ask = m["yes_ask"] if side == "YES" else m["no_ask"]
    bid = m["yes_bid"] if side == "YES" else m["no_bid"]
    reasons = []
    if ask is None:
        return {"reasons": ["no ask"], "side": side}
    minutes_left = (m["close_time"] - dt.datetime.now(dt.timezone.utc)).total_seconds() / 60.0
    if minutes_left < MIN_MINUTES_LEFT:
        reasons.append(f"min left {minutes_left:.1f}")
    cushion = abs(spot - target)
    frac = MIN_CUSHION_FRAC.get(m["series"], 0.001)
    min_cush = max(spot * frac, 1e-6)
    # Top25 #9 — metals vs energy playbooks (stricter cushion/z for energy spikes).
    z_floor = MIN_Z
    try:
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        import desk_top25
        playbook = desk_top25.commodity_playbook(m.get("series"))
        min_cush *= float(playbook.get("min_cushion_mult") or 1.0)
        z_floor = float(playbook.get("min_z") or MIN_Z)
    except Exception:
        z_floor = MIN_Z
    # Staff near-miss soft promote may relax z/p — never edge/fee floors.
    z_relax = 0.0
    p_relax = 0.0
    try:
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        import desk_roi_plan
        relax = desk_roi_plan.effective_near_miss_relax(DESK_ROOT)
        z_relax = float(relax.get("z_relax") or 0.0)
        p_relax = float(relax.get("p_relax") or 0.0)
    except Exception:
        z_relax = 0.0
        p_relax = 0.0
    # Conservative σ: ~0.15% of spot * sqrt(minutes_left / 15) for 15m commodities.
    sigma = spot * 0.0015 * math.sqrt(max(minutes_left, 1.0) / 15.0)
    z = cushion / sigma if sigma > 1e-12 else 0.0
    p = phi(z)
    fee = kalshi_fee(ask)
    if book is not None and isinstance(book, (tuple, list)) and len(book) >= 2:
        spread, depth = book[0], int(book[1] or 0)
    else:
        spread, depth = book_depth(str(m["ticker"]), side, ask)
    if cushion + 1e-12 < min_cush:
        reasons.append(f"cushion {cushion:.5f} < {min_cush:.5f}")
    lane = "accurate"
    need_edge = 0.0
    p_acc = max(0.50, float(MIN_MODEL_ACCURATE) - p_relax)
    p_speed = max(0.50, float(MIN_MODEL_SPEED) - p_relax)
    if p + 1e-12 >= p_acc:
        lane = "accurate"
    elif p + 1e-12 >= p_speed:
        lane = "speed"
        need_edge = SPEED_EDGE_EXTRA
        z_floor = min(float(z_floor), MIN_Z_SPEED)
    else:
        reasons.append(f"p {p:.3f} < speed floor {p_speed}")
    z_floor = max(0.40, float(z_floor) - z_relax)
    if z + 1e-12 < z_floor:
        reasons.append(f"z {z:.2f} < {z_floor}")
    if not (ASK_MIN - 1e-12 <= float(ask) <= ASK_MAX + 1e-12):
        reasons.append(f"ask {ask:.3f} outside band")
    if spread is not None and spread > MAX_SPREAD + 1e-12:
        reasons.append(f"spread {spread:.3f}")
    if depth < MIN_DEPTH:
        reasons.append(f"depth {depth} < {MIN_DEPTH}")
    edge = float(p) - float(ask) - float(fee) - float(edge_buf)
    if edge + 1e-12 < need_edge:
        reasons.append(f"edge {edge:.3f} < {need_edge:.3f} ({lane})")
    # E1 #109 — EIA / inventory blackout for energy series only.
    eia_hit = None
    try:
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        from helpers import eia_blackout
        events = eia_blackout.load_calendar_events(DESK_ROOT)
        gate = eia_blackout.energy_blackout(m.get("series"), events)
        if gate.get("blocked"):
            eia_hit = gate
            reasons.append(str(gate.get("reason") or "EIA/inventory blackout"))
    except Exception:
        eia_hit = None
    return {
        "side": side,
        "ask": ask,
        "bid": bid,
        "fee": fee,
        "p": round(p, 4),
        "z": round(z, 4),
        "cushion": round(cushion, 6),
        "sigma": round(sigma, 6),
        "spread": spread,
        "depth": depth,
        "edge": round(edge, 4),
        "lane": lane,
        "min_left": round(minutes_left, 2),
        "reasons": reasons,
        "ticker": m["ticker"],
        "series": m["series"],
        "close_time": m["close_time"],
        "target": target,
        "spot": spot,
        "eia_blackout": eia_hit,
    }


def paper_buy(state: dict, ev: dict) -> str:
    none_msg = "No commodity paper buy."
    if ev.get("reasons"):
        return none_msg + " " + "; ".join(ev["reasons"][:3])
    ticker = ev["ticker"]
    if any(isinstance(p, dict) and p.get("ticker") == ticker for p in state.get("open") or []):
        return none_msg + " already open."
    if os.environ.get("DESK_BLOCK_ENTRIES") == "1":
        return "Desk entry_gate blocked a new paper buy."
    try:
        import desk_roi_plan
        stale = desk_roi_plan.stale_world_blocks(DESK_ROOT, "commodity-15m")
        if stale:
            return stale
        revenge = desk_roi_plan.anti_revenge_blocks(DESK_ROOT, "commodity-15m", ticker)
        if revenge:
            return revenge
    except Exception:
        pass
    fam = series_family(str(ev.get("series") or ""))
    if fam in ("energy", "metal") and fam in open_families(state):
        return (
            f"{none_msg} portfolio corr: already open a {fam} series "
            "(max 1 energy + 1 metal)."
        )
    ask = float(ev["ask"])
    fee = float(ev["fee"] or 0)
    per = ask + fee
    open_risk = sum(float(p.get("cost") or 0) for p in (state.get("open") or []))
    try:
        desk = _desk()
        cfg = desk.load_settings(DESK_ROOT)
        blocked = desk.correlation_blocks(DESK_ROOT, "commodity-15m", ev["side"], ev.get("edge"))
        if blocked:
            return blocked
        stake, plan = desk.stake_dollars_for(
            "commodity-15m",
            ev.get("p"),
            edge=ev.get("edge"),
            cfg=cfg,
            open_risk_used=open_risk,
            ask=ask,
            root=DESK_ROOT,
            vol_kwargs={
                "cushion": ev.get("cushion"),
                "sigma": ev.get("sigma"),
                "spread": ev.get("spread"),
                "minutes_left": ev.get("min_left"),
                "ask": ask,
                "ticker": ticker,
                "spot": ev.get("spot"),
                "recent_range": ev.get("cushion"),
            },
            return_plan=True,
        )
        # WTI↔Brent series haircut when sibling open or closed today.
        try:
            import desk_profit
            today_tag = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
            open_series = [
                str(p.get("series") or "")
                for p in (state.get("open") or [])
                if isinstance(p, dict)
            ]
            closed_today = []
            for p in state.get("closed") or []:
                if not isinstance(p, dict):
                    continue
                if today_tag not in str(p.get("closed") or p.get("at") or ""):
                    continue
                closed_today.append(str(p.get("series") or ""))
            hair = desk_profit.series_corr_haircut(
                ev.get("series"),
                open_series=open_series,
                closed_today_series=closed_today,
            )
            if hair.get("apply") and float(hair.get("mult") or 1) < 1.0 - 1e-12:
                stake = round(float(stake) * float(hair["mult"]), 2)
                plan = dict(plan or {})
                notes = list(plan.get("notes") or [])
                notes.append(str(hair.get("note") or "series corr haircut"))
                plan["notes"] = notes
                plan["series_corr_haircut"] = hair
        except Exception:
            pass
        contracts = desk.contracts_for_stake(per, stake)
    except Exception as exc:
        return f"Desk sizing failed: {type(exc).__name__}"
    if contracts < 1:
        return none_msg
    cost = round(contracts * per, 2)
    cash = float(state.get("cash") or 0)
    if cost > cash + 1e-9 or len(state.get("open") or []) >= 12:
        return none_msg + " cash/open cap."
    state["cash"] = round(cash - cost, 2)
    opened = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    vol = (plan or {}).get("vol") or {}
    perf = (plan or {}).get("perf") or {}
    try:
        import desk_profit
        risk_factor = desk_profit.risk_factor_for("commodity-15m", ev["side"])
    except Exception:
        risk_factor = ""
    state.setdefault("open", []).append({
        "ticker": ticker,
        "series": ev.get("series"),
        "team": ticker,
        "game": f"{ev.get('series')} 15m",
        "side": ev["side"],
        "contracts": contracts,
        "ask": round(ask, 4),
        "fee": round(fee, 4),
        "cost": cost,
        "risk": cost,
        "reward": round(contracts * 1.0 - cost, 2),
        "fair_at_entry": ev.get("p"),
        "gap_at_entry": ev.get("edge"),
        "risk_factor": risk_factor,
        "opened": opened,
        "close_time": ev["close_time"].isoformat(),
        "fill_id": f"{ticker}|{opened}",
        "price_source": KALSHI,
        "price_at": opened,
        "paper_only": True,
        "why": "Paper buy. Commodity 15m cleared desk adapt gates.",
        "cushion": ev.get("cushion"),
        "sigma": ev.get("sigma"),
        "adapt_mult": (plan or {}).get("mult"),
        "adapt_notes": list((plan or {}).get("notes") or [])[:6],
        "play_safe": bool((plan or {}).get("play_safe")),
        "play_big": bool((plan or {}).get("play_big")),
        "vol_regime": vol.get("regime"),
        "vol_score": vol.get("score"),
        "history_n": perf.get("n"),
        "history_hit": perf.get("hit_rate"),
        "history_ci_low": perf.get("hit_ci_low"),
        "fill_tax": 0.01,
    })
    try:
        import desk_roi_plan as _xp
        state["open"][-1]["exit_plan"] = _xp.default_exit_plan("commodity-15m")
    except Exception:
        state["open"][-1]["exit_plan"] = {
            "kind": "model_flip+settle",
            "model_flip": True,
            "settle_backstop": True,
            "fee_floors_locked": True,
        }
    save_account(state)
    return f"Paper buy {ev['side']} {ticker} x{contracts} @ {ask:.2f}."


def main() -> int:
    print("commodity-15m paper check (no live orders)")
    t0 = time.perf_counter()
    if DESK_ROOT not in sys.path:
        sys.path.insert(0, DESK_ROOT)
    try:
        import desk_living
        blocked = desk_living.honor_desk_entry_gate(DESK_ROOT)
        if blocked:
            print(f"Desk entry_gate (CLI honor): {blocked[:160]}")
    except Exception:
        pass
    account = load_account()
    settle_account(account)
    save_account(account)

    try:
        import kalshi_tape
        tape = kalshi_tape.sync_tape_family(DESK_ROOT, "commodity15m")
        print(f"Tape commodity family: +{tape.get('last_added') or 0}")
    except Exception as exc:
        print(f"Tape sync skipped: {type(exc).__name__}")
    try:
        import kalshi_history
        settled = kalshi_history.settle_open_windows(DESK_ROOT, series_list=SERIES, limit=24)
        if settled.get("settled"):
            print(f"History settle harness: {settled['settled']} labels")
        n = kalshi_history.snapshot_open_15m_series(DESK_ROOT, series_list=SERIES, limit_per=2)
        print(f"History snapshots: {n}")
    except Exception as exc:
        print(f"History skipped: {type(exc).__name__}")

    try:
        desk = _desk()
        cfg = desk.load_settings(DESK_ROOT)
        edge_buf = float(desk.venue_min_edge("kalshi_commodity15m", cfg))
        flip_delta = float(cfg.get("model_flip_delta") or 0.06)
        flip_on = bool(cfg.get("model_flip_exits", True))
    except Exception:
        edge_buf = EDGE_BUFFER
        flip_delta = 0.06
        flip_on = True

    t_spot = time.perf_counter()
    spots = spots_by_series()
    spot_secs = time.perf_counter() - t_spot
    print(f"Spots ready: {len(spots)}/{len(SERIES)}  cash=${float(account.get('cash') or 0):.2f}")
    windows = []
    for series in SERIES:
        spot = spots.get(series)
        if spot is None:
            print(f"  {series}: no spot — skip")
            continue
        for m in list_open(series, limit=3):
            windows.append((series, spot, m))
    if not windows:
        elapsed = time.perf_counter() - t0
        print("CARD: Checked commodity 15m markets. No open windows.")
        try:
            import desk_roi_plan
            for series in SERIES:
                desk_roi_plan.record_empty_card(
                    DESK_ROOT,
                    bot="commodity-15m",
                    seconds=elapsed,
                    markets_n=0,
                    series=series,
                    note="no open commodity windows",
                )
            desk_roi_plan.record_latency(
                DESK_ROOT, bot="commodity-15m", seconds=spot_secs,
                note="commodity spot (empty)", stage="spot",
            )
            desk_roi_plan.record_latency(
                DESK_ROOT, bot="commodity-15m", seconds=elapsed,
                note="empty card", stage="evaluate",
            )
        except Exception:
            pass
        print(f"Empty-market CARD in {elapsed:.2f}s (bar 3s)")
        return 0
    # Parallel books for every window's model side (speed).
    book_jobs = []
    for series, spot, m in windows:
        side0 = "YES" if float(spot) > float(m["target"]) else "NO"
        ask0 = m["yes_ask"] if side0 == "YES" else m["no_ask"]
        if ask0 is None:
            continue
        book_jobs.append((str(m["ticker"]), side0, float(ask0)))
    t_book = time.perf_counter()
    books = prefetch_commodity_books(book_jobs)
    book_secs = time.perf_counter() - t_book
    print(f"Prefetched {len(books)} commodity orderbook(s) in parallel")
    candidates = []
    buys = 0
    for series, spot, m in windows:
        ev = evaluate(m, spot, edge_buf, book=books.get(str(m["ticker"])))
        print(
            f"  {series} {m['ticker']} spot={spot:.5f} target={m['target']} "
            f"side={ev.get('side')} p={ev.get('p')} reasons={ev.get('reasons')}"
        )
        # Exits before entries — model-flip when this window's model speaks.
        if (
            flip_on
            and account.get("open")
            and ev.get("side")
            and ev.get("bid") is not None
            and ev.get("p") is not None
        ):
            sold = manage_model_flips(
                account,
                ev["side"],
                ev["p"],
                ev["bid"],
                kalshi_fee(float(ev["bid"])) if ev.get("bid") else 0.0,
                flip_delta,
                ticker=ev.get("ticker"),
            )
            if sold:
                save_account(account)
                for line in sold:
                    print(f"  MODEL-FLIP SELL: {line}")
                try:
                    import desk_roi_plan
                    desk_roi_plan.record_anti_revenge(
                        DESK_ROOT, bot="commodity-15m",
                        ticker=str(ev.get("ticker") or ""), reason="model-flip",
                        note=str(sold[0])[:120],
                    )
                except Exception:
                    pass
        # Phase 3: time-stop shadow (≤3m to close + underwater mark). Live staff-gated.
        try:
            import desk_roi_plan
            tick = str(m.get("ticker") or "")
            for pos in list(account.get("open") or []):
                if str(pos.get("ticker") or "") != tick:
                    continue
                if pos.get("time_stop_shadowed"):
                    continue
                bid_ts = ev.get("bid")
                if bid_ts is None:
                    continue
                hit = desk_roi_plan.commodity_time_stop_hit(
                    pos.get("close_time"),
                    bid_ts,
                    pos.get("entry") or pos.get("price") or pos.get("ask"),
                    cost=pos.get("cost"),
                    contracts=pos.get("contracts"),
                )
                if not hit.get("hit"):
                    continue
                desk_roi_plan.record_commodity_time_stop_shadow(
                    DESK_ROOT,
                    ticker=tick,
                    side=str(pos.get("side") or ""),
                    series=str(pos.get("series") or series or ""),
                    close_time=str(pos.get("close_time") or ""),
                    entry_price=pos.get("entry") or pos.get("price") or pos.get("ask"),
                    bid=bid_ts,
                    contracts=pos.get("contracts"),
                    cost=pos.get("cost"),
                    note="commodity time-stop shadow",
                )
                pos["time_stop_shadowed"] = True
                print(
                    f"  TIME-STOP SHADOW: {tick} left={hit.get('minutes_left')}m "
                    f"mark_pnl={hit.get('mark_pnl')}"
                )
                if desk_roi_plan.commodity_time_stop_is_live(DESK_ROOT) and float(bid_ts) > 0:
                    fee_ts = kalshi_fee(float(bid_ts))
                    pnl_ts = paper_sell(
                        account, pos, bid_ts, fee_ts,
                        f"time-stop left={hit.get('minutes_left')}m mark≤0",
                    )
                    account["open"] = [
                        p for p in (account.get("open") or []) if p is not pos
                    ]
                    save_account(account)
                    print(f"  TIME-STOP SELL: {tick} pnl {pnl_ts:+.2f}")
                    try:
                        desk_roi_plan.record_anti_revenge(
                            DESK_ROOT, bot="commodity-15m",
                            ticker=tick, reason="time-stop",
                            note=f"mark_pnl={hit.get('mark_pnl')}",
                        )
                    except Exception:
                        pass
                else:
                    save_account(account)
        except Exception:
            pass
        try:
            import kalshi_history
            kalshi_history.record_snapshot(
                DESK_ROOT,
                series=series,
                ticker=str(m["ticker"]),
                spot=spot,
                target=m["target"],
                side=ev.get("side"),
                yes_ask=m.get("yes_ask"),
                no_ask=m.get("no_ask"),
                model_p=ev.get("p"),
                minutes_left=ev.get("min_left"),
                regime="skip" if ev.get("reasons") else "confident_early",
                note="; ".join(ev.get("reasons") or [])[:160],
            )
        except Exception:
            pass
        try:
            import desk_living
            desk_living.record_eval_features(
                DESK_ROOT,
                bot="commodity-15m",
                action="skip" if ev.get("reasons") else "fit",
                series=series,
                ticker=str(m.get("ticker") or ""),
                ev=ev,
                reasons=list(ev.get("reasons") or []),
                note="; ".join(ev.get("reasons") or ["fit"])[:160],
            )
        except Exception:
            pass
        # Soft z|p near-miss densify on skips (mirror sports/btc). Never LIVE.
        if ev.get("reasons"):
            try:
                if DESK_ROOT not in sys.path:
                    sys.path.insert(0, DESK_ROOT)
                import desk_more as _nm_com
                nm = _nm_com.is_near_miss(
                    reasons=list(ev.get("reasons") or []),
                    z=ev.get("z"),
                    p=ev.get("p"),
                    edge=ev.get("edge"),
                    min_edge=0.0,
                )
                if nm.get("near_miss"):
                    _nm_com.record_near_miss(DESK_ROOT, {
                        "bot": "commodity-15m",
                        "ticker": ev.get("ticker") or m.get("ticker"),
                        "side": ev.get("side"),
                        "soft": nm.get("soft"),
                        "z": ev.get("z"),
                        "p": ev.get("p"),
                        "edge": ev.get("edge"),
                        "note": f"commodity {nm.get('note')}",
                    })
            except Exception:
                pass
        if not ev.get("reasons"):
            candidates.append({
                "bot": "commodity-15m",
                "ticker": ev.get("ticker"),
                "side": ev.get("side"),
                "edge": ev.get("edge"),
                "confidence": ev.get("p"),
                "depth": ev.get("depth"),
                "stake_est": 25.0,
                "_ev": ev,
            })

    # Densify time-stop shadow across ALL opens (not only current-window ticker).
    # Reuses window bids when present; best-effort market fetch otherwise.
    try:
        import desk_roi_plan
        bid_by_ticker: dict[str, dict] = {}
        for series_w, _spot_w, m_w in windows:
            tick_w = str(m_w.get("ticker") or "")
            if not tick_w:
                continue
            bid_by_ticker[tick_w] = {
                "YES": m_w.get("yes_bid"),
                "NO": m_w.get("no_bid"),
                "series": series_w,
            }
        changed_ts = False
        for pos in list(account.get("open") or []):
            if not isinstance(pos, dict) or pos.get("time_stop_shadowed"):
                continue
            tick = str(pos.get("ticker") or "")
            if not tick:
                continue
            side = str(pos.get("side") or "YES").upper()
            info = bid_by_ticker.get(tick) or {}
            bid_ts = info.get(side)
            if bid_ts is None:
                try:
                    payload = get_json(f"{KALSHI}/markets/{tick}", timeout=12)
                    market = payload.get("market") if isinstance(payload, dict) else None
                    if not isinstance(market, dict):
                        market = payload if isinstance(payload, dict) else {}
                    raw = (
                        market.get("yes_bid_dollars") if side == "YES"
                        else market.get("no_bid_dollars")
                    )
                    if raw in (None, ""):
                        raw = market.get("yes_bid") if side == "YES" else market.get("no_bid")
                    bid_ts = float(raw) if raw not in (None, "") else None
                    if bid_ts is not None and bid_ts > 1.5:
                        bid_ts = bid_ts / 100.0
                except Exception:
                    continue
            if bid_ts is None:
                continue
            hit = desk_roi_plan.commodity_time_stop_hit(
                pos.get("close_time"),
                bid_ts,
                pos.get("entry") or pos.get("price") or pos.get("ask"),
                cost=pos.get("cost"),
                contracts=pos.get("contracts"),
            )
            if not hit.get("hit"):
                continue
            desk_roi_plan.record_commodity_time_stop_shadow(
                DESK_ROOT,
                ticker=tick,
                side=side,
                series=str(pos.get("series") or info.get("series") or ""),
                close_time=str(pos.get("close_time") or ""),
                entry_price=pos.get("entry") or pos.get("price") or pos.get("ask"),
                bid=bid_ts,
                contracts=pos.get("contracts"),
                cost=pos.get("cost"),
                note="commodity time-stop shadow (all-opens densify)",
            )
            pos["time_stop_shadowed"] = True
            changed_ts = True
            print(
                f"  TIME-STOP SHADOW (all-opens): {tick} left={hit.get('minutes_left')}m "
                f"mark_pnl={hit.get('mark_pnl')}"
            )
            if desk_roi_plan.commodity_time_stop_is_live(DESK_ROOT) and float(bid_ts) > 0:
                fee_ts = kalshi_fee(float(bid_ts))
                pnl_ts = paper_sell(
                    account, pos, bid_ts, fee_ts,
                    f"time-stop left={hit.get('minutes_left')}m mark≤0",
                )
                account["open"] = [
                    p for p in (account.get("open") or []) if p is not pos
                ]
                print(f"  TIME-STOP SELL: {tick} pnl {pnl_ts:+.2f}")
                try:
                    desk_roi_plan.record_anti_revenge(
                        DESK_ROOT, bot="commodity-15m",
                        ticker=tick, reason="time-stop",
                        note=f"mark_pnl={hit.get('mark_pnl')}",
                    )
                except Exception:
                    pass
        if changed_ts:
            save_account(account)
    except Exception:
        pass

    # Global rank soft pass — fill best commodity edges first under local loop.
    try:
        import desk_brain
        ranked = desk_brain.rank_desk_queue(candidates)
        desk_brain.remember_queue(DESK_ROOT, ranked, note="commodity-15m local queue")
    except Exception:
        ranked = candidates
    # Cross-tower firm queue: merge commodity fits with sports/btc offers.
    try:
        import desk_roi_plan
        desk_roi_plan.offer_firm_candidates(
            DESK_ROOT,
            [
                {
                    "bot": "commodity-15m",
                    "ticker": r.get("ticker"),
                    "side": r.get("side"),
                    "edge": r.get("edge"),
                    "confidence": r.get("confidence") if r.get("confidence") is not None else r.get("p"),
                    "depth": r.get("depth"),
                    "stake_est": r.get("stake_est") or 25.0,
                }
                for r in ranked
                if r.get("ticker")
            ],
            bot="commodity-15m",
        )
        desk_roi_plan.rebuild_firm_queue(
            DESK_ROOT,
            remaining_risk=desk_roi_plan.remaining_desk_risk(DESK_ROOT),
            note="commodity-15m firm offer",
        )
    except Exception:
        pass
    today_pnl = 0.0
    today_tag = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    for pos in account.get("closed") or []:
        if not isinstance(pos, dict):
            continue
        if today_tag in str(pos.get("closed") or ""):
            try:
                today_pnl += float(pos.get("pnl") or 0)
            except (TypeError, ValueError):
                pass
    try:
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        import desk_more
        import desk_roi_plan
        if today_pnl >= 0:
            top = ranked[0] if ranked else {}
            ev_top = (top.get("_ev") if isinstance(top, dict) else None) or top or {}
            desk_roi_plan.record_selective_attempt(
                DESK_ROOT,
                "commodity-15m",
                edge=ev_top.get("edge"),
                z=ev_top.get("z"),
                depth=ev_top.get("depth"),
                today=today_pnl,
                boosted=True,
                note="selective +1 path considered",
            )
        if desk_roi_plan.selective_kill_active(DESK_ROOT, "commodity-15m"):
            max_buys_eff = int(MAX_BUYS_PER_CHECK)
            print("Selective +1 KILLED (5 green-day EV worsen) — base max_buys only")
        else:
            max_buys_eff = int(
                desk_more.selective_max_buys(
                    "commodity-15m", base=MAX_BUYS_PER_CHECK, today=today_pnl,
                )
            )
    except Exception:
        max_buys_eff = int(MAX_BUYS_PER_CHECK)
    if today_pnl >= 0 and max_buys_eff > MAX_BUYS_PER_CHECK:
        print(
            f"Selective volume: max buys {max_buys_eff} "
            f"(today ${today_pnl:.2f} ≥ 0, fee floors locked)"
        )
    # Daily R budget → settle-only after tower hits target (exits stay on).
    try:
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        import desk_roi_plan
        r_block = desk_roi_plan.daily_r_blocks("commodity-15m", today_pnl)
        if r_block:
            print(f"Settle-only: {r_block}")
            max_buys_eff = 0
    except Exception:
        pass
    for row in ranked:
        if buys >= max_buys_eff:
            print(f"  → skip: max buys this check ({max_buys_eff})")
            ev_skip = (row.get("_ev") if isinstance(row, dict) else None) or row or {}
            try:
                import desk_roi_plan
                desk_roi_plan.note_pending_high_edge(
                    DESK_ROOT,
                    bot="commodity-15m",
                    ticker=str(ev_skip.get("ticker") or ""),
                    edge=ev_skip.get("edge"),
                    reason=f"max buys this check ({max_buys_eff})",
                )
            except Exception:
                pass
            break
        ev = row.get("_ev") or row
        try:
            import desk_roi_plan
            firm_block = desk_roi_plan.firm_queue_blocks(
                DESK_ROOT, "commodity-15m", str(ev.get("ticker") or ""),
            )
        except Exception:
            firm_block = ""
        if firm_block:
            print(f"  → skip: {firm_block}")
            try:
                import desk_roi_plan
                desk_roi_plan.record_fit(
                    DESK_ROOT, bot="commodity-15m", outcome="block",
                    ticker=str(ev.get("ticker") or ""), side=str(ev.get("side") or ""),
                    edge=ev.get("edge"), note=firm_block[:160],
                )
            except Exception:
                pass
            continue
        # E1 #136/#137 — red-day sticky opens exit-first before speculative buys.
        try:
            import desk_more
            sticky_block = desk_more.sticky_entry_blocks(
                "commodity-15m",
                today=today_pnl,
                bots=[{
                    "id": "commodity-15m",
                    "positions": list((account or {}).get("open") or []),
                }],
            )
        except Exception:
            sticky_block = ""
        if sticky_block:
            print(f"  → skip: {sticky_block}")
            continue
        msg = paper_buy(account, ev)
        print(f"  → {msg}")
        if msg.startswith("Paper buy"):
            buys += 1
            try:
                import desk_roi_plan
                desk_roi_plan.record_fit(
                    DESK_ROOT, bot="commodity-15m", outcome="buy",
                    ticker=str(ev.get("ticker") or ""), side=str(ev.get("side") or ""),
                    edge=ev.get("edge"),
                )
                desk_roi_plan.flush_opp_cost_on_buy(
                    DESK_ROOT,
                    bot="commodity-15m",
                    ticker=str(ev.get("ticker") or ""),
                    edge=ev.get("edge"),
                )
            except Exception:
                pass
        else:
            try:
                import desk_roi_plan
                desk_roi_plan.record_fit(
                    DESK_ROOT, bot="commodity-15m", outcome="block",
                    ticker=str(ev.get("ticker") or ""), side=str(ev.get("side") or ""),
                    edge=ev.get("edge"), note=msg[:160],
                )
                why = str(msg or "").lower()
                if any(
                    k in why
                    for k in ("budget", "open risk", "max open", "cash", "risk cap")
                ):
                    desk_roi_plan.note_pending_high_edge(
                        DESK_ROOT,
                        bot="commodity-15m",
                        ticker=str(ev.get("ticker") or ""),
                        edge=ev.get("edge"),
                        reason=str(msg)[:120],
                    )
            except Exception:
                pass
    save_account(account)
    try:
        import desk_roi_plan
        elapsed = time.perf_counter() - t0
        # #504 stage densify: spot / book walls (plus existing evaluate/exit/buy).
        desk_roi_plan.record_latency(
            DESK_ROOT, bot="commodity-15m", seconds=spot_secs,
            note="commodity spot", stage="spot",
        )
        desk_roi_plan.record_latency(
            DESK_ROOT, bot="commodity-15m", seconds=book_secs,
            note=f"commodity book n={len(book_jobs)}", stage="book",
        )
        desk_roi_plan.record_latency(
            DESK_ROOT, bot="commodity-15m", seconds=elapsed,
            note="commodity evaluate", stage="evaluate",
        )
        desk_roi_plan.record_latency(
            DESK_ROOT, bot="commodity-15m", seconds=elapsed,
            note=f"commodity buys={buys}", stage="buy",
        )
        desk_roi_plan.record_latency(
            DESK_ROOT, bot="commodity-15m", seconds=elapsed,
            note="commodity exit/manage", stage="exit",
        )
        desk_roi_plan.record_latency(
            DESK_ROOT, bot="commodity-15m", seconds=elapsed,
            note="commodity check", stage="loop",
        )
    except Exception:
        pass
    print(f"Done. paper buys={buys} open={len(account.get('open') or [])}")
    if buys <= 0:
        print("CARD: Checked commodity 15m markets. No paper buy.")
    elif buys == 1:
        print("CARD: Checked commodity 15m markets. Paper buy.")
    else:
        print(f"CARD: Checked commodity 15m markets. {buys} paper buys.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
