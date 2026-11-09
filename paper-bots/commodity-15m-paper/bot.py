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
    # Prefer-1: Kalshi GET must raise — silent [] false-friends as empty windows
    # when the feed is down (#433/#434 sibling). Call site densifies list_errs.
    data = get_json(f"{KALSHI}/markets?series_ticker={series}&status=open&limit={limit}")
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
    """Spread + depth from a raw Kalshi orderbook payload (or None).

    Live Kalshi returns ``orderbook_fp`` with ``yes_dollars`` / ``no_dollars``
    (BTC ``book_for_side`` already). Legacy ``orderbook.yes/no`` kept as
    fallback. Missing fp must not silent-map thick books to depth 0.
    """
    if not data:
        return None, 0
    if isinstance(data, dict):
        # Prefer fp (current API); fall back to legacy nested / bare book.
        book = data.get("orderbook_fp") or data.get("orderbook") or data
    else:
        book = data
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
        # Depth window must match MAX_SPREAD (0.05). Hardcoding ask−0.02
        # invent-tags depth 0 on thick books with 0.02 < spread ≤ 0.05
        # (#453 leftover / Prefer-1 invent densify).
        if ask is not None and px + 1e-9 >= float(ask) - float(MAX_SPREAD):
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


def prefetch_commodity_books(jobs: list[tuple[str, str, float]]) -> tuple[dict, dict]:
    """Parallel orderbook fetch. jobs = [(ticker, side, ask), ...].

    Returns ({ticker: (spread, depth)}, {ticker: error_str}).
    Prefetch failures must not look like thin depth — callers densify
    ``orderbook failed`` into CARD/brain (BTC/ETH #431 sibling).
    """
    if not jobs:
        return {}, {}
    errs: dict = {}
    try:
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        import desk_more
        tickers = sorted({str(t) for t, _s, _a in jobs if t})
        raw_ok, errs = desk_more.prefetch_map(tickers, _fetch_orderbook_raw, max_workers=8)
    except Exception:
        raw_ok = {}
        for ticker, _side, _ask in jobs:
            key = str(ticker)
            if key in raw_ok or key in errs:
                continue
            try:
                raw_ok[key] = _fetch_orderbook_raw(key)
            except Exception as exc:  # noqa: BLE001
                raw_ok[key] = None
                errs[key] = str(exc)
    out = {}
    for ticker, side, ask in jobs:
        key = str(ticker)
        if key in errs:
            continue  # caller densifies orderbook failed — not depth 0
        out[key] = depth_from_book(raw_ok.get(key), side, ask)
    return out, {str(k): str(v) for k, v in (errs or {}).items()}


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


def listing_bid_for_side(market, side):
    """Held-contract listing bid from a window/market dict (yes_bid / no_bid)."""
    if not isinstance(market, dict):
        return None
    s = str(side or "").upper()
    if s == "YES":
        raw = market.get("yes_bid")
    elif s == "NO":
        raw = market.get("no_bid")
    else:
        return None
    if raw in (None, ""):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def mark_bid_for_held(pos, *, model_side=None, model_bid=None, market=None):
    """Bid that marks the *held* contract — never the complementary model side.

    On side flips `evaluate` quotes the new model side. Selling YES inventory at
    the NO bid (or vice versa) invents PnL / drops honest time-stop densify.
    Prefer same-side model bid, else listing for held. Refuse complementary invent.
    When model_side is omitted (legacy callers), model_bid is treated as held-side.
    """
    held = str((pos or {}).get("side") or "").upper()
    ms = str(model_side or "").upper()
    if model_bid is not None and (not ms or (held and held == ms)):
        try:
            b = float(model_bid)
            if b > 0:
                return b
        except (TypeError, ValueError):
            pass
    if ms and held and held != ms:
        listing = listing_bid_for_side(market, held)
        if listing is not None and float(listing) > 0:
            return float(listing)
        return None
    listing = listing_bid_for_side(market, held)
    if listing is not None and float(listing) > 0:
        return float(listing)
    return None


def manage_model_flips(
    state: dict, side_now, prob_now, bid, fee, delta, ticker=None, market=None,
) -> list[str]:
    """Exit open commodity paper when the live model flips against the held side.

    Sell mark is always the held-side bid (see mark_bid_for_held) — BTC #456 sibling.
    """
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
        if not flip:
            still.append(pos)
            continue
        mark = mark_bid_for_held(
            pos, model_side=side_now, model_bid=bid, market=market,
        )
        if mark is None or float(mark) <= 0:
            still.append(pos)
            continue
        # Fee from held mark — never model-side complementary fee invent.
        mark_fee = kalshi_fee(float(mark))
        pnl = paper_sell(state, pos, mark, mark_fee, reason)
        sold.append(f"{pos.get('ticker')} {reason} pnl {pnl:+.2f}")
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
        # Honest binary settle mark — catchup densify reads exit_price|exit_bid|mark_bid
        # only (never entry companion bid). Losers with exit_price=0 can recover
        # time-stop shadow when settle-retro market bid fields are missing; winners
        # with exit_price=1 stay non-hits (mark PnL > 0 / wipe invent guard).
        pos.update({
            "closed": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "pnl": pnl,
            "payout": round(payout, 2),
            "exit": "settled",
            "exit_price": 1.0 if won else 0.0,
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
    # Frac cushion only when z does not already clear — distance is in Φ(z).
    # Matches BTC #378; avoids double-vetoing fee-clear edges.
    if cushion + 1e-12 < min_cush and z + 1e-12 < float(z_floor):
        reasons.append(f"cushion {cushion:.5f} < {min_cush:.5f}")
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


def _card_sentence(*, buys: int, skip_reasons=None, open_windows: bool = True) -> str:
    """CARD body only. Prefer first evaluate skip over generic no-buy (#396 sibling).

    Prefer-1: skip_reasons (spot / Kalshi list failed|incomplete) must beat
    empty-window invent — feed-down must not false-friend as "No open windows"
    (#433/#434/#435/#439 sibling).
    """
    skips = [str(s).strip() for s in (skip_reasons or []) if str(s).strip()]
    if buys <= 0 and skips:
        return skips[0]
    if not open_windows:
        return "Checked commodity 15m markets. No open windows."
    if buys <= 0:
        return "Checked commodity 15m markets. No paper buy."
    if buys == 1:
        return "Checked commodity 15m markets. Paper buy."
    return f"Checked commodity 15m markets. {buys} paper buys."


def _densify_evaluate_skip(
    *,
    reasons,
    ticker: str = "",
    side: str = "",
    edge=None,
    confidence=None,
    depth=None,
    note: str = "commodity evaluate densify",
) -> None:
    """Mirror btc15m / sports #401: evaluate skips → desk_brain → skip_board.

    CARD + feature-store already densify (#397). Observe only; never LIVE.
    """
    why = [str(r) for r in (reasons or []) if str(r).strip()]
    if not why:
        return
    try:
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        import desk_brain
        desk_brain.record_decision(
            DESK_ROOT,
            bot="commodity-15m",
            action="skip",
            ticker=str(ticker or ""),
            side=str(side or ""),
            edge=edge,
            confidence=confidence,
            depth=depth,
            reasons=why,
            note=str(note or "")[:160],
        )
    except Exception:
        pass


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
    list_errs: list[str] = []
    for series in SERIES:
        spot = spots.get(series)
        if spot is None:
            print(f"  {series}: no spot — skip")
            continue
        try:
            for m in list_open(series, limit=3):
                windows.append((series, spot, m))
        except Exception as exc:
            # Prefer-1: do not collapse Kalshi list-down into empty windows.
            list_errs.append(series)
            print(f"  {series}: Kalshi list failed — {type(exc).__name__}")
    if not windows:
        elapsed = time.perf_counter() - t0
        # Prefer-1/2: feed-down ≠ empty Kalshi windows (#433/#434 sibling).
        # Without this, CARD invents "No open windows" and skip_board stays empty.
        # Partial Yahoo down (some series spot, some not) + empty windows was still
        # inventing clean empty while failed series only printed "no spot — skip".
        empty_skip_reasons: list[str] = []
        empty_note = "no open commodity windows"
        missing_spots = [s for s in SERIES if s not in spots]
        if not spots:
            spot_reason = "spot failed (yahoo)"
            empty_skip_reasons.append(spot_reason)
            empty_note = spot_reason
            _densify_evaluate_skip(
                reasons=[spot_reason],
                note="commodity spot densify",
            )
            print(f"SKIP densify: {spot_reason}")
        elif list_errs:
            # Spots present + list_open raised → Kalshi feed-down invent.
            # Prefer-1 leftover of #435/#439: when SOME spotted series listed OK
            # as [] and SOME raised, "markets failed" invents total Kalshi-down
            # over honest empty siblings. Name incomplete (not total failed).
            spotted = [s for s in SERIES if s in spots]
            listed_ok = [s for s in spotted if s not in list_errs]
            if listed_ok:
                kalshi_reason = (
                    f"markets incomplete (kalshi "
                    f"{len(list_errs)}/{len(spotted)} failed)"
                )
                densify_note = "commodity partial kalshi list densify"
            else:
                kalshi_reason = "markets failed (kalshi)"
                densify_note = "commodity kalshi list densify"
            empty_skip_reasons.append(kalshi_reason)
            empty_note = kalshi_reason
            _densify_evaluate_skip(
                reasons=[kalshi_reason],
                note=densify_note,
            )
            print(f"SKIP densify: {kalshi_reason} ({','.join(list_errs)})")
        elif missing_spots:
            # Prefer-1: partial Yahoo down + empty windows ≠ clean no-open invent
            # (#434 leftover — all-down densified; partial still false-friended).
            # Name incomplete (not total "spot failed") — spotted series may be
            # truly empty Kalshi; still must not invent a complete empty check.
            spot_reason = (
                f"spot incomplete (yahoo "
                f"{len(missing_spots)}/{len(SERIES)} missing)"
            )
            empty_skip_reasons.append(spot_reason)
            empty_note = spot_reason
            _densify_evaluate_skip(
                reasons=[spot_reason],
                note="commodity partial spot densify",
            )
            print(f"SKIP densify: {spot_reason}")
        print(
            "CARD: "
            + _card_sentence(
                buys=0,
                skip_reasons=empty_skip_reasons or None,
                open_windows=False,
            )
        )
        try:
            import desk_roi_plan
            for series in SERIES:
                desk_roi_plan.record_empty_card(
                    DESK_ROOT,
                    bot="commodity-15m",
                    seconds=elapsed,
                    markets_n=0,
                    series=series,
                    note=empty_note,
                )
            if not spots:
                spot_lat_note, eval_lat_note = (
                    "commodity spot failed",
                    "spot failed card",
                )
            elif missing_spots and not list_errs:
                spot_lat_note, eval_lat_note = (
                    "commodity spot incomplete",
                    "spot incomplete card",
                )
            elif list_errs:
                spotted = [s for s in SERIES if s in spots]
                listed_ok = [s for s in spotted if s not in list_errs]
                if listed_ok:
                    spot_lat_note, eval_lat_note = (
                        "commodity kalshi list incomplete",
                        "kalshi list incomplete card",
                    )
                else:
                    spot_lat_note, eval_lat_note = (
                        "commodity kalshi list failed",
                        "kalshi list failed card",
                    )
            else:
                spot_lat_note, eval_lat_note = (
                    "commodity spot (empty)",
                    "empty card",
                )
            desk_roi_plan.record_latency(
                DESK_ROOT, bot="commodity-15m", seconds=spot_secs,
                note=spot_lat_note,
                stage="spot",
            )
            desk_roi_plan.record_latency(
                DESK_ROOT, bot="commodity-15m", seconds=elapsed,
                note=eval_lat_note,
                stage="evaluate",
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
    books, book_errs = prefetch_commodity_books(book_jobs) if book_jobs else ({}, {})
    book_secs = time.perf_counter() - t_book
    print(f"Prefetched {len(books)} commodity orderbook(s) in parallel")
    candidates = []
    buys = 0
    skip_reasons = []  # first evaluate skip → CARD densify (#396 sibling)
    for series, spot, m in windows:
        tick = str(m["ticker"])
        # BTC/ETH densify prefetch book failures into scored reasons → CARD/brain;
        # commodity must not silent-map errs to depth 0 (board-truth lie).
        if tick in book_errs:
            side_ob = "YES" if float(spot) > float(m["target"]) else "NO"
            ask_ob = m["yes_ask"] if side_ob == "YES" else m["no_ask"]
            bid_ob = m["yes_bid"] if side_ob == "YES" else m["no_bid"]
            ob_reason = f"orderbook failed ({book_errs[tick]})"
            print(f"--- {series} {tick} SKIP -> {ob_reason}")
            skip_reasons.append(ob_reason)
            _densify_evaluate_skip(
                reasons=[ob_reason],
                ticker=tick,
                side=side_ob,
                note="commodity orderbook densify",
            )
            # Keep listing bid for time-stop / flip observe; buy path stays off.
            ev = {
                "reasons": [ob_reason],
                "side": side_ob,
                "ask": ask_ob,
                "bid": bid_ob,
                "p": None,
                "z": None,
                "edge": None,
                "depth": 0,
                "ticker": tick,
                "series": series,
                "close_time": m.get("close_time"),
                "target": m.get("target"),
                "spot": spot,
            }
        else:
            ev = evaluate(m, spot, edge_buf, book=books.get(tick))
        print(
            f"  {series} {m['ticker']} spot={spot:.5f} target={m['target']} "
            f"side={ev.get('side')} p={ev.get('p')} reasons={ev.get('reasons')}"
        )
        if ev.get("reasons") and tick not in book_errs:
            skip_reasons.append("; ".join(str(r) for r in (ev.get("reasons") or [])[:3]))
        # Phase 3 densify BEFORE model-flip — near-close underwater flips otherwise
        # leave open[] and never hit mid-open / all-opens time-stop shadow.
        try:
            import desk_roi_plan
            tick = str(m.get("ticker") or "")
            for pos in list(account.get("open") or []):
                if str(pos.get("ticker") or "") != tick:
                    continue
                if pos.get("time_stop_shadowed"):
                    continue
                # Held-side listing bid — never complementary model-side ev["bid"]
                # (BTC #456 sibling). Flip path clears open[] before all-opens densify.
                held = str(pos.get("side") or "").upper()
                bid_ts = listing_bid_for_side(m, held)
                if bid_ts is None and held == str(ev.get("side") or "").upper():
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
                market=m,
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
        # skip_board / hologram densify (#401 sibling) — features alone leave chips blank.
        # Prefetch book_errs already densified above (commodity orderbook densify).
        if ev.get("reasons") and tick not in book_errs:
            _densify_evaluate_skip(
                reasons=list(ev.get("reasons") or []),
                ticker=str(ev.get("ticker") or m.get("ticker") or ""),
                side=str(ev.get("side") or ""),
                edge=ev.get("edge"),
                confidence=ev.get("p"),
                depth=ev.get("depth"),
                note="commodity evaluate densify",
            )
        # Soft z|p near-miss densify on skips (mirror sports/btc). Never LIVE.
        # OB fetch fail is not a soft z|p near-miss — skip invent.
        if ev.get("reasons") and tick not in book_errs:
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
                        # Historical buf for ask catch-up invert (never live guess).
                        "edge_buf": round(float(edge_buf), 4),
                        "ask": ev.get("ask"),
                        "series": m.get("series"),
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
            max_note = f"max buys this check ({max_buys_eff})"
            print(f"  → skip: {max_note}")
            skip_reasons.append(max_note)  # CARD densify parity with BTC
            ev_skip = (row.get("_ev") if isinstance(row, dict) else None) or row or {}
            try:
                import desk_roi_plan
                desk_roi_plan.note_pending_high_edge(
                    DESK_ROOT,
                    bot="commodity-15m",
                    ticker=str(ev_skip.get("ticker") or ""),
                    edge=ev_skip.get("edge"),
                    reason=max_note,
                )
            except Exception:
                pass
            _densify_evaluate_skip(
                reasons=[max_note],
                ticker=str(ev_skip.get("ticker") or ""),
                side=str(ev_skip.get("side") or ""),
                edge=ev_skip.get("edge"),
                confidence=ev_skip.get("p"),
                depth=ev_skip.get("depth"),
                note="commodity max-buys densify",
            )
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
            skip_reasons.append(str(firm_block))  # CARD densify parity with BTC
            try:
                import desk_roi_plan
                desk_roi_plan.record_fit(
                    DESK_ROOT, bot="commodity-15m", outcome="block",
                    ticker=str(ev.get("ticker") or ""), side=str(ev.get("side") or ""),
                    edge=ev.get("edge"), note=firm_block[:160],
                )
            except Exception:
                pass
            _densify_evaluate_skip(
                reasons=[firm_block],
                ticker=str(ev.get("ticker") or ""),
                side=str(ev.get("side") or ""),
                edge=ev.get("edge"),
                confidence=ev.get("p"),
                depth=ev.get("depth"),
                note="commodity firm-queue densify",
            )
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
            skip_reasons.append(str(sticky_block))  # CARD densify parity with BTC
            _densify_evaluate_skip(
                reasons=[sticky_block],
                ticker=str(ev.get("ticker") or ""),
                side=str(ev.get("side") or ""),
                edge=ev.get("edge"),
                confidence=ev.get("p"),
                depth=ev.get("depth"),
                note="commodity sticky densify",
            )
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
            block_note = str(msg)[:160] or "desk/account blocked fill"
            skip_reasons.append(block_note)  # CARD densify parity with BTC
            try:
                import desk_roi_plan
                desk_roi_plan.record_fit(
                    DESK_ROOT, bot="commodity-15m", outcome="block",
                    ticker=str(ev.get("ticker") or ""), side=str(ev.get("side") or ""),
                    edge=ev.get("edge"), note=block_note,
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
            _densify_evaluate_skip(
                reasons=[block_note],
                ticker=str(ev.get("ticker") or ""),
                side=str(ev.get("side") or ""),
                edge=ev.get("edge"),
                confidence=ev.get("p"),
                depth=ev.get("depth"),
                note="commodity desk-block densify",
            )
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
    print("CARD: " + _card_sentence(buys=buys, skip_reasons=skip_reasons))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
