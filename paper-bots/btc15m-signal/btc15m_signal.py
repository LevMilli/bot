#!/usr/bin/env python3
"""
btc15m_signal.py - SIGNAL ONLY helper for Kalshi's "BTC price up in next 15 mins?" markets (KXBTC15M).

What it does (one run):
  1. Reads ALL open KXBTC15M markets from Kalshi's free public API (target = floor_strike,
     yes/no bid/ask, close time) and each order book — not only the nearest close.
  2. Syncs the public trade tape for desk-watched Kalshi series (see kalshi_tape.py).
  3. Averages BTC spot from Coinbase, Kraken Futures (PF_XBTUSD) and Bitstamp.
  4. Estimates how far BTC can move before each close (sigma) from Deribit's DVOL and from the
     last 60 one-minute Coinbase candles, and uses the larger one.
  5. For every open window: picks the side BTC is currently on (YES if price > target, else NO),
     turns the cushion into a probability p = Phi(cushion / sigma), and compares p with ask + fee.
  6. Checks the US high-impact news calendar (ForexFactory) and paper-buys EVERY window that
     clears the same guideline gates (confidence, edge, cushion, z, ask band, spread, depth,
     candle direction, news). Desk entry_gate / open-risk / correlation still apply.

What it does NOT do: it places no real orders, needs no login, no API key, and no wallet.
It keeps a paper account and paper-buys only when the signal clears the edge after fees. Not financial advice.

Run:  python3 btc15m_signal.py
"""
import datetime as dt
import json
import math
import os
import statistics
import sys
import time
import urllib.request

KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

# ---- rule settings (edit here) ----
MIN_MINUTES_LEFT = 10        # early singles need ≥10 minutes before close
PARLAY_MAX_MIN = 5.0         # late multi-leg window (staff: wait → parlay by ~5m left)
PARLAY_MIN_MIN = 1.0
EDGE_BUFFER = 0.05           # fallback if desk venue_min_edge missing
MIN_MODEL_ACCURATE = 0.80    # accurate lane
MIN_MODEL_SPEED = 0.72       # speed lane (match sports; needs SPEED_EDGE_EXTRA)
MIN_MODEL_PROB = MIN_MODEL_ACCURATE
SPEED_EDGE_EXTRA = 0.02
MIN_CUSHION_USD = 35         # BTC cushion floor
MIN_CUSHION_ETH = 1.5        # ETH 15m cushion (KXETH15M)
MIN_Z = 0.60                 # cushion / sigma (accurate lane)
MIN_Z_SPEED = 0.55           # speed lane may sit in near-miss z band if edge clears
MIN_Z_COINBASE_ONLY = 0.75   # stricter if only Coinbase spot worked
ASK_MIN, ASK_MAX = 0.70, 0.92  # slightly wider book for more fee-aware fills
MAX_SPREAD = 0.04
MIN_DEPTH = 3                # contracts offered at or below the ask
MAX_BUYS_PER_CHECK = 3       # spend idle desk margin across multiple windows
NEWS_WINDOW_MIN = 30         # USD high-impact event within 30 min of the block -> skip
TAKE_PROFIT_ADD, TAKE_PROFIT_CAP = 0.15, 0.99
DVOL_FAIL_MULT = 1.2         # if DVOL fails: use realized sigma * 1.2
# Track + history (staff screenshots): BTC 15m, ETH 15m, BTC 1am ladder.
CRYPTO_SERIES = ("KXBTC15M", "KXETH15M", "KXBTCD")


HERE = os.path.dirname(os.path.abspath(__file__))
DESK_ROOT = os.path.dirname(HERE)
ACCOUNT = os.environ.get("DESK_SHADOW_ACCOUNT") or os.path.join(HERE, "paper_account.json")
_CACHE = os.path.join(HERE, "quote_cache.json")
PAPER_CASH = 100.0
IS_SHADOW = os.environ.get("DESK_SHADOW") == "1"


FEE_FLOOR = 0.05


def decide_floor(edge_buf):
    """0.05 after the fee. A higher bar stays. A lower number is put back."""
    try:
        n = float(edge_buf)
    except (TypeError, ValueError):
        return FEE_FLOOR
    if n != n or n < FEE_FLOOR:
        return FEE_FLOOR
    return n


def series_for(ticker, series=None):
    """Learning skip is this series, not one blended crypto bucket."""
    text = str(series or "").strip().upper()
    if text:
        return text
    ticker_u = str(ticker or "").upper()
    if ticker_u.startswith("KXETH"):
        return "KXETH15M"
    return "KXBTC15M"


def cleared_stake(base, adapted, *, proved_80):
    """Adapt may shrink a cleared ticket. It does not size up without 80%."""
    try:
        b = float(base)
        a = float(adapted)
    except (TypeError, ValueError):
        return base
    if a > b + 1e-9 and not proved_80:
        return b
    return a


def _edge_buffer():
    """Venue kalshi_btc15m from desk, or shadow overlay, else local EDGE_BUFFER.

    Never below 0.05. A shadow bar above the floor, such as 0.08, stays.
    """
    raw = None
    shadow = os.environ.get("DESK_SHADOW_VENUE_EDGE")
    if shadow not in (None, ""):
        try:
            raw = float(shadow)
        except (TypeError, ValueError):
            raw = None
    if raw is None:
        try:
            desk = _desk()
            cfg = desk.load_settings(DESK_ROOT)
            raw = float(desk.venue_min_edge("kalshi_btc15m", cfg))
        except Exception:
            raw = float(EDGE_BUFFER)
    return decide_floor(raw)


def load_account():
    path = ACCOUNT
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                data.setdefault("cash", PAPER_CASH)
                data.setdefault("open", [])
                data.setdefault("closed", [])
                data["paper_only"] = True
                if IS_SHADOW:
                    data["shadow"] = True
                return data
        except (OSError, json.JSONDecodeError):
            pass
    out = {"cash": PAPER_CASH, "open": [], "closed": [], "paper_only": True}
    if IS_SHADOW:
        out["shadow"] = True
    return out


def save_account(state):
    path = ACCOUNT
    if os.path.islink(path):
        path = os.path.realpath(path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
        handle.write("\n")
    os.replace(tmp, path)


def _desk():
    if DESK_ROOT not in sys.path:
        sys.path.insert(0, DESK_ROOT)
    import pimp_desk
    return pimp_desk


def settle_account(state):
    """Settle a paper BTC position only when Kalshi has published yes or no. Never guess."""
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
        record_close(pos, cash=state["cash"], reason="settled", bid=None, fee=pos.get("fee"))
        try:
            desk = _desk()
            desk.record_learning(DESK_ROOT, settle_learning_row(pos, pnl))
        except Exception:
            pass
        # Near-miss would_pnl densify — label shadow skips for this ticker (observe).
        try:
            import desk_roi_plan
            desk_roi_plan.label_near_miss_from_result(
                DESK_ROOT,
                ticker=str(pos.get("ticker") or ""),
                result=str(result),
                bot="btc15m",
                note="btc15m settle label",
            )
        except Exception:
            pass
        # Fee ledger + helper fill densify under DESK_SHADOW too (observe journals).
        # Living / teller stay main-desk only.
        try:
            import desk_roi_plan
            settle_note = "settled shadow" if IS_SHADOW else "settled"
            desk_roi_plan.record_fee_ledger(
                DESK_ROOT,
                bot="btc15m",
                ticker=str(pos.get("ticker") or ""),
                side=str(pos.get("side") or ""),
                price=pos.get("ask") or pos.get("entry_price"),
                contracts=pos.get("contracts"),
                fee=0.0,
                pnl=pnl,
                fill_id=str(pos.get("fill_id") or ""),
                kind="settle",
                note=settle_note,
            )
            helper = str(pos.get("helper_source") or "").strip()
            if helper:
                desk_roi_plan.record_helper_fill(
                    DESK_ROOT,
                    helper=helper,
                    bot="btc15m",
                    ticker=str(pos.get("ticker") or ""),
                    pnl=pnl,
                    contracts=pos.get("contracts"),
                    fill_id=str(pos.get("fill_id") or ""),
                    note=settle_note,
                )
        except Exception:
            pass
        if not IS_SHADOW:
            try:
                import desk_living
                import teller_memory
                desk_living.record_completion(
                    DESK_ROOT,
                    bot="btc15m",
                    ticker=str(pos.get("ticker") or ""),
                    side=str(pos.get("side") or ""),
                    pnl=pnl,
                    contracts=pos.get("contracts"),
                    fill_id=str(pos.get("fill_id") or ""),
                    kind="settle",
                    eligible=True,
                    note="settled",
                )
                teller_memory.remember(
                    DESK_ROOT,
                    kind="wins" if float(pnl) > 0 else "mistakes",
                    text=f"btc15m settle {pos.get('ticker')} pnl {float(pnl):+.2f}"[:200],
                    bot_id="btc15m",
                )
            except Exception:
                pass
    state["open"] = still


def sell_learning_row(pos, reason):
    """A sell before settle records the reason only. It is not a hit or a miss."""
    return {
        "reason": str(reason or "")[:160],
        "market": series_for(pos.get("ticker"), pos.get("series")),
        "prob": pos.get("fair_at_entry"),
        "stake": pos.get("risk") if pos.get("risk") is not None else pos.get("cost"),
        "fill_id": pos.get("fill_id") or "",
        "side": pos.get("side") or "",
    }


def settle_learning_row(pos, pnl, *, hour_ct=None):
    """One settle row for this series. Hit or miss comes from the real P/L.

    The market is KXBTC15M or KXETH15M, not one blended crypto bucket.
    """
    row = {
        "result": "hit" if float(pnl or 0) > 0 else "miss",
        "reason": "settled",
        "market": series_for(pos.get("ticker"), pos.get("series")),
        "prob": pos.get("fair_at_entry"),
        "stake": pos.get("risk") if pos.get("risk") is not None else pos.get("cost"),
        "fill_id": pos.get("fill_id") or "",
        "side": pos.get("side") or "",
        "at": pos.get("closed") or "",
    }
    if hour_ct is not None:
        row["hour_ct"] = hour_ct
    return row


def last_minute_block(min_left):
    """The last minute does not open a buy to save a position."""
    try:
        left = float(min_left)
    except (TypeError, ValueError):
        return ""
    if left < 1.0:
        return "no new buy in the last minute"
    return ""


def exit_that_fired(reason):
    """Name which exit fired. The two live exits are take-profit and model-flip."""
    text = str(reason or "")
    if "take-profit" in text:
        return "take-profit +15¢ cap 99¢"
    if "model-flip" in text:
        return "model-flip"
    if text.strip() == "settled":
        return "settled"
    return text[:120]


def record_close(pos, *, cash, reason, bid=None, fee=None, root=None):
    """Stamp fill id, bid, fee, and which exit fired. Do not edit P/L.

    A bid is stored only when it is a real held-side quote. A settle does not
    invent one. The same fill and exit are not written twice.
    """
    if not isinstance(pos, dict):
        return None
    pnl_before = pos.get("pnl")
    try:
        pos["cash_after"] = round(float(cash), 4)
    except (TypeError, ValueError):
        pass
    label = exit_that_fired(reason or pos.get("exit") or "")
    if label:
        pos["exit_name"] = label
    if fee is not None:
        try:
            pos["exit_fee"] = round(float(fee), 4)
        except (TypeError, ValueError):
            pass
    if pnl_before is not None:
        pos["pnl"] = pnl_before
    fee_for_journal = pos.get("exit_fee")
    if fee_for_journal is None:
        fee_for_journal = pos.get("fee")
    stored_bid = real_held_bid(bid)
    journal_root = DESK_ROOT if root is None else root
    try:
        if journal_root not in sys.path:
            sys.path.insert(0, journal_root)
        import desk_brain
        return desk_brain.record_decision(
            journal_root,
            bot="btc15m",
            action="settle" if label == "settled" else "sell",
            ticker=str(pos.get("ticker") or ""),
            side=str(pos.get("side") or ""),
            reasons=[label] if label else [],
            note=str(reason or label)[:240],
            fill_id=str(pos.get("fill_id") or ""),
            bid=stored_bid,
            stake=pos.get("risk") if pos.get("risk") is not None else pos.get("cost"),
            exit_name=label,
            fee=fee_for_journal,
            cash=pos.get("cash_after"),
        )
    except Exception:
        return None


def paper_sell(state, pos, bid, fee, reason):
    """Flatten one open BTC paper position at bid − fee. No live order."""
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
        "opens_new_ticket": False,
    })
    state.setdefault("closed", []).append(closed)
    record_close(closed, cash=state["cash"], reason=reason, bid=bid, fee=fee)
    # Fee ledger + helper fill densify under DESK_SHADOW too (observe journals).
    try:
        import desk_roi_plan
        sell_note = str(reason or "")[:120]
        if IS_SHADOW and sell_note:
            sell_note = f"shadow {sell_note}"[:120]
        elif IS_SHADOW:
            sell_note = "shadow sell"
        desk_roi_plan.record_fee_ledger(
            DESK_ROOT,
            bot="btc15m",
            ticker=str(pos.get("ticker") or ""),
            side=str(pos.get("side") or ""),
            price=bid,
            contracts=pos.get("contracts"),
            fee=fee,
            pnl=pnl,
            fill_id=str(pos.get("fill_id") or ""),
            kind="sell",
            note=sell_note,
        )
        helper = str(pos.get("helper_source") or "").strip()
        if helper:
            desk_roi_plan.record_helper_fill(
                DESK_ROOT,
                helper=helper,
                bot="btc15m",
                ticker=str(pos.get("ticker") or ""),
                pnl=pnl,
                contracts=pos.get("contracts"),
                fill_id=str(pos.get("fill_id") or ""),
                note=sell_note,
            )
    except Exception:
        pass
    if not IS_SHADOW:
        try:
            desk = _desk()
            desk.record_learning(DESK_ROOT, sell_learning_row(pos, reason) | {"at": closed["closed"]})
        except Exception:
            pass
        try:
            import desk_roi_plan
            series = str(pos.get("series") or "KXBTC15M")
            desk_roi_plan.record_incubation_settle(
                DESK_ROOT,
                series=series,
                bot="btc15m",
                pnl=pnl,
                contracts=pos.get("contracts"),
                note=str(reason or "")[:80],
            )
            desk_roi_plan.record_adverse_fill(
                DESK_ROOT,
                bot="btc15m",
                ticker=str(pos.get("ticker") or ""),
                entry_price=pos.get("ask") if pos.get("ask") is not None else pos.get("entry_price"),
                mark_price=bid,
                note=str(reason or "")[:120],
            )
            try:
                import desk_living
                import teller_memory
                desk_living.record_completion(
                    DESK_ROOT,
                    bot="btc15m",
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
                    text=f"btc15m {reason} {pos.get('ticker')} pnl {float(pnl):+.2f}"[:200],
                    bot_id="btc15m",
                )
            except Exception:
                pass
        except Exception:
            pass
    return pnl


def listing_bid_for_side(market, side):
    """Listing bid for YES/NO from a kalshi market row. None if missing."""
    if not isinstance(market, dict):
        return None
    s = str(side or "").upper()
    if s == "YES":
        return fnum(market.get("yes_bid"))
    if s == "NO":
        return fnum(market.get("no_bid"))
    return None


def mark_bid_for_held(pos, *, model_side=None, model_bid=None, market=None):
    """Bid that marks the *held* contract — never the complementary model side.

    On side flips `evaluate_window` quotes the new model side. Selling YES inventory
    at the NO bid (or vice versa) invents PnL. Prefer same-side model bid, else
    listing for held, else a live held-side book. Refuse complementary invent.

    When model_side is omitted (legacy callers), model_bid is treated as already
    held-side — keep prior behavior.
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
        ticker = str((pos or {}).get("ticker") or "")
        if ticker and held in ("YES", "NO"):
            try:
                b, _, _ = book_for_side(ticker, held)
                if b is not None and float(b) > 0:
                    return float(b)
            except Exception:
                pass
        return None
    listing = listing_bid_for_side(market, held)
    if listing is not None and float(listing) > 0:
        return float(listing)
    return None


def real_held_bid(bid):
    """A held-side bid strictly inside (0, 1). A wipe or a complement is not a mark."""
    try:
        n = float(bid)
    except (TypeError, ValueError):
        return None
    if n != n or n <= 0 or n >= 1:
        return None
    return n


def watch_open(pos, bid, *, model_side=None, model_p=None, market=None):
    """Mark the open contract at the held-side bid and compare. Does not sell.

    The comparison is the stored take-profit and whether the model still
    matches the held side. A missing bid, a zero, a wipe, or the other
    side's price does not replace a prior mark.
    """
    if not isinstance(pos, dict):
        return None
    held = str(pos.get("side") or "").upper()
    ms = str(model_side or "").upper()
    mark = real_held_bid(mark_bid_for_held(
        pos, model_side=model_side, model_bid=bid, market=market,
    ))
    other = real_held_bid(bid)
    if mark is not None and ms and held and ms != held and other is not None and abs(mark - other) < 1e-12:
        mark = None
    try:
        tp_f = float(pos.get("take_profit")) if pos.get("take_profit") is not None else None
    except (TypeError, ValueError):
        tp_f = None
    if mark is None:
        pos["watch"] = {
            "last_mark": pos.get("last_mark"),
            "take_profit": tp_f,
            "at_take_profit": False,
            "model_side": ms or None,
            "model_matches_held": False,
            "marked": False,
        }
        return pos["watch"]
    pos["last_mark"] = mark
    pos["watch"] = {
        "last_mark": mark,
        "take_profit": tp_f,
        "at_take_profit": bool(tp_f is not None and mark + 1e-12 >= tp_f),
        "model_side": ms or None,
        "model_p": model_p,
        "model_matches_held": bool(ms and held and ms == held),
        "marked": True,
    }
    return pos["watch"]


def manage_model_flips(
    state, side_now, prob_now, bid, fee, delta, ticker=None, market=None,
):
    """Exit open BTC paper when the live model flips against the held side.

    When `ticker` is set, only positions on that market are evaluated (multi-window runs).
    Sell mark is always the held-side bid (see mark_bid_for_held).
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
                desk = _desk()
                import desk_profit
                if desk_profit.model_flip_adverse(held, fair_entry, prob_now, delta):
                    flip = True
                    reason = f"model-flip fair Δ≥{delta:g}"
            except Exception:
                pass
        if not flip:
            still.append(pos)
            continue
        mark = real_held_bid(mark_bid_for_held(
            pos, model_side=side_now, model_bid=bid, market=market,
        ))
        if mark is None:
            still.append(pos)
            continue
        mark_fee = fee_per_contract(mark)
        pnl = paper_sell(state, pos, mark, mark_fee, reason)
        sold.append(f"{pos.get('ticker')} {reason} pnl {pnl:+.2f}")
    state["open"] = still
    return sold


def manage_take_profits(state, bid, fee, ticker=None, market=None, model_side=None):
    """Execute stored take-profit when held-side bid reaches take_profit (paper only).

    Replaces the old advisory-only TP print. Fee floors unchanged.
    Never marks held inventory at the complementary model-side bid.
    """
    still = []
    sold = []
    for pos in list(state.get("open") or []):
        if ticker and pos.get("ticker") != ticker:
            still.append(pos)
            continue
        mark = real_held_bid(mark_bid_for_held(
            pos, model_side=model_side, model_bid=bid, market=market,
        ))
        if mark is None:
            still.append(pos)
            continue
        tp = pos.get("take_profit")
        try:
            tp_f = float(tp) if tp is not None else None
        except (TypeError, ValueError):
            tp_f = None
        if tp_f is None:
            # Backfill legacy opens that only had a printed suggestion.
            try:
                ask0 = float(pos.get("ask") or 0)
                tp_f = min(round(ask0 + TAKE_PROFIT_ADD, 2), TAKE_PROFIT_CAP) if ask0 > 0 else None
            except (TypeError, ValueError):
                tp_f = None
        if tp_f is not None and float(mark) + 1e-12 >= tp_f:
            mark_fee = fee_per_contract(mark)
            reason = f"take-profit +15¢ cap 99¢ bid {float(mark):.2f} ≥ {tp_f:.2f}"
            pnl = paper_sell(state, pos, mark, mark_fee, reason)
            sold.append(f"{pos.get('ticker')} {reason} pnl {pnl:+.2f}")
        else:
            still.append(pos)
    state["open"] = still
    return sold


BUY_EXIT_RULE = "take-profit +15¢ cap 99¢ / model-flip"
BUY_INTENT = os.path.join(HERE, "buy_intent.json")


def _atomic_json(dest, payload):
    tmp = dest + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
        handle.flush()
    os.replace(tmp, dest)


def load_buy_intent():
    if not os.path.exists(BUY_INTENT):
        return None
    try:
        with open(BUY_INTENT, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def write_buy_intent(*, fill_id, ticker, side, contracts, stake, ask):
    """Write the crash intent before cash moves. The ask has to be a real quote."""
    try:
        ask_n = float(ask)
        stake_n = float(stake)
    except (TypeError, ValueError):
        raise ValueError("buy intent needs the real ask and the stake") from None
    if ask_n != ask_n or ask_n <= 0 or stake_n != stake_n or stake_n <= 0:
        raise ValueError("buy intent needs the real ask and the stake")
    payload = {
        "tower": "btc15m",
        "fill_id": str(fill_id),
        "ticker": str(ticker or ""),
        "side": str(side or ""),
        "contracts": int(contracts),
        "stake": round(stake_n, 2),
        "ask": ask_n,
        "exit_rule": BUY_EXIT_RULE,
        "paper_only": True,
        "status": "intent",
    }
    if not payload["fill_id"] or not payload["ticker"]:
        raise ValueError("buy intent needs a fill id and a ticker")
    _atomic_json(BUY_INTENT, payload)
    return payload


def reconcile_buy_intent(state):
    """Match an intent to the saved book. Never create a position or a price."""
    intent = load_buy_intent()
    if not isinstance(intent, dict):
        return "none"
    fid = str(intent.get("fill_id") or "")
    opens = [p for p in (state or {}).get("open") or [] if isinstance(p, dict)]
    closed = [p for p in (state or {}).get("closed") or [] if isinstance(p, dict)]
    if fid and any(str(p.get("fill_id") or "") == fid for p in opens):
        status = "open"
    elif fid and any(str(p.get("fill_id") or "") == fid for p in closed):
        status = "closed"
    else:
        status = "abandoned"
    if intent.get("status") != status or intent.get("paper_only") is not True:
        intent["status"] = status
        intent["paper_only"] = True
        intent["exit_rule"] = BUY_EXIT_RULE
        _atomic_json(BUY_INTENT, intent)
    return status


def second_side_block(state, ticker, side):
    """One paper buy for this window. The other side is not a hedge."""
    want = str(side or "").upper()
    book = list((state or {}).get("open") or []) + list((state or {}).get("closed") or [])
    for pos in book:
        if not isinstance(pos, dict):
            continue
        if str(pos.get("ticker") or "") != str(ticker or ""):
            continue
        held = str(pos.get("side") or "").upper()
        if held and want and held != want:
            return "second side of the same window is not a hedge"
        return "one paper buy for that window"
    return ""


def paper_buy(state, ticker, side, ask, fee, prob, close_time, signal_buy, edge=None, vol_kwargs=None, series=None):
    """Paper fill only when the signal cleared the edge after fees. No order is sent."""
    none_msg = "Checked all open BTC 15-minute markets. No paper buy."
    if ask is None or not (0.05 <= float(ask) <= 0.95):
        return none_msg
    late = last_minute_block((vol_kwargs or {}).get("minutes_left"))
    if late:
        return late
    held = second_side_block(state, ticker, side)
    if held:
        return held
    if not IS_SHADOW:
        try:
            import desk_roi_plan
            cool = desk_roi_plan.adverse_cool_blocks(DESK_ROOT, "btc15m")
            if cool:
                return cool
            stale = desk_roi_plan.stale_world_blocks(DESK_ROOT, "btc15m")
            if stale:
                return stale
            revenge = desk_roi_plan.anti_revenge_blocks(DESK_ROOT, "btc15m", ticker)
            if revenge:
                return revenge
        except Exception:
            pass
    skip = ""
    try:
        desk = _desk()
        hour_ct = None
        try:
            from zoneinfo import ZoneInfo
            hour_ct = dt.datetime.now(ZoneInfo("America/Chicago")).hour
        except Exception:
            hour_ct = None
        series_name = series_for(ticker, series)
        bucket = desk.prob_bucket(prob)
        rows = desk.load_learning(DESK_ROOT)
        skip = desk.learning_skip(
            rows, series_name, bucket, side=side, hour_ct=hour_ct,
        )
        if not skip and series_name == "KXBTC15M":
            # Rows written before the series key still brake this series only.
            skip = desk.learning_skip(
                rows, "BTC", bucket, side=side, hour_ct=hour_ct,
            )
    except Exception:
        pass
    if skip:
        return skip
    if os.environ.get("DESK_BLOCK_ENTRIES") == "1" and not IS_SHADOW:
        # Prefer-1: honor stored DESK_BLOCK_REASON — do not invent bland entry_gate.
        try:
            import desk_living
            return desk_living.desk_block_entries_reason(
                "Desk entry_gate blocked a new paper buy. Settles still run."
            )
        except Exception:
            return "Desk entry_gate blocked a new paper buy. Settles still run."
    if not signal_buy:
        return none_msg
    edge_val = edge
    if edge_val is None and prob is not None and ask is not None:
        edge_val = float(prob) - float(ask) - float(fee or 0)
    floor = decide_floor(_edge_buffer())
    try:
        gap = float(edge_val)
    except (TypeError, ValueError):
        gap = None
    if gap is None or gap + 1e-12 < floor:
        return "near-miss under the floor"
    if not IS_SHADOW:
        try:
            desk = _desk()
            blocked = desk.correlation_blocks(DESK_ROOT, "btc15m", side, edge_val)
            if blocked:
                return blocked
        except Exception:
            pass
    per = float(ask) + float(fee or 0)
    open_risk = sum(
        float(p.get("risk") if p.get("risk") is not None else p.get("cost") or 0)
        for p in (state.get("open") or [])
    )
    vk = dict(vol_kwargs or {})
    vk.setdefault("ask", ask)
    vk.setdefault("ticker", ticker)
    try:
        desk = _desk()
        cfg = desk.load_settings(DESK_ROOT)
        stake, adapt_plan = desk.stake_dollars_for(
            "btc15m", prob, edge=edge_val, cfg=cfg, open_risk_used=open_risk, ask=ask,
            root=DESK_ROOT, vol_kwargs=vk, return_plan=True,
        )
        base = (adapt_plan or {}).get("base")
        proved = bool(((adapt_plan or {}).get("perf") or {}).get("proven_80"))
        capped = cleared_stake(base if base is not None else stake, stake, proved_80=proved)
        if float(capped) + 1e-9 < float(stake):
            adapt_plan = dict(adapt_plan or {})
            notes = list(adapt_plan.get("notes") or [])
            notes.append("adapt size-up needs 80% on this sample")
            adapt_plan["notes"] = notes
            adapt_plan["play_big"] = False
            stake = capped
        contracts = desk.contracts_for_stake(per, stake)
    except Exception:
        stake = 20.0
        adapt_plan = {}
        contracts = int(stake // per) if per > 0 else 0
    if contracts < 1:
        return none_msg
    check = None
    try:
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        import strict_fill
        check = strict_fill.recheck(
            ticker, side, ask, contracts, fee_per=fee_per_contract,
            edge=edge_val, min_edge=floor,
        )
    except ImportError:
        check = None
    if check is not None:
        if not check["ok"]:
            return check["reason"]
        if check["ask"] != float(ask):
            ask = check["ask"]
            fee = fee_per_contract(float(ask))
            per = float(ask) + float(fee or 0)
        contracts = int(check["contracts"])
    cost = round(contracts * per, 2)
    cash = float(state.get("cash") or 0)
    if cost > cash + 1e-9 or len(state.get("open") or []) >= 12:
        return none_msg
    opened = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    fill_id = f"{ticker}|{opened}"
    try:
        write_buy_intent(
            fill_id=fill_id, ticker=ticker, side=side,
            contracts=contracts, stake=cost, ask=ask,
        )
    except (TypeError, ValueError):
        return none_msg
    state["cash"] = round(cash - cost, 2)
    reward = round(contracts * 1.0 - cost, 2)
    why = "Paper buy. The BTC 15-minute signal cleared its checks on this window."
    try:
        import desk_profit
        risk_factor = desk_profit.risk_factor_for("btc15m", side)
    except Exception:
        risk_factor = ""
    vol = (adapt_plan or {}).get("vol") or {}
    perf = (adapt_plan or {}).get("perf") or {}
    state.setdefault("open", []).append({
        "ticker": ticker,
        "team": ticker,
        "game": "BTC 15-minute",
        "side": side,
        "contracts": contracts,
        "ask": round(float(ask), 4),
        "fee": round(float(fee or 0), 4),
        "cost": cost,
        "risk": cost,
        "reward": reward,
        "risk_reward": round(reward / cost, 4) if cost else None,
        "max_payout": round(contracts * 1.0, 2),
        "why": why,
        "fair_at_entry": None if prob is None else round(float(prob), 4),
        "gap_at_entry": None if edge_val is None else round(float(edge_val), 4),
        "risk_factor": risk_factor,
        "opened": opened,
        "close_time": close_time.isoformat() if hasattr(close_time, "isoformat") else str(close_time or ""),
        "fill_id": fill_id,
        "price_source": KALSHI,
        "price_at": opened,
        "paper_only": True,
        "shadow": IS_SHADOW,
        # Prove-it drawer fields (city reads snapshot only).
        "cushion": vk.get("cushion"),
        "sigma": vk.get("sigma"),
        "adapt_mult": (adapt_plan or {}).get("mult"),
        "adapt_notes": list((adapt_plan or {}).get("notes") or [])[:6],
        "play_safe": bool((adapt_plan or {}).get("play_safe")),
        "play_big": bool((adapt_plan or {}).get("play_big")),
        "fill_check": None if check is None else {
            k: check.get(k) for k in
            ("decided_ask", "quoted_ask", "slip", "depth", "capped", "requoted", "note")
        },
        "vol_regime": vol.get("regime"),
        "vol_score": vol.get("score"),
        "history_n": perf.get("n"),
        "history_hit": perf.get("hit_rate"),
        "history_ci_low": perf.get("hit_ci_low"),
        "fill_tax": 0.01,
        # Calendar consulted (loaded) → attribute close to helper for Gate A evidence.
        "helper_source": (
            "calendar_scanner" if vk.get("calendar_loaded") else str(vk.get("helper_source") or "")
        ),
        "take_profit": min(round(float(ask) + TAKE_PROFIT_ADD, 2), TAKE_PROFIT_CAP),
        "exit_rule": BUY_EXIT_RULE,
    })
    try:
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        import desk_roi_plan as _xp
        plan = dict(_xp.default_exit_plan("btc15m"))
        plan["take_profit_add"] = TAKE_PROFIT_ADD
        plan["take_profit_cap"] = TAKE_PROFIT_CAP
        state["open"][-1]["exit_plan"] = plan
    except Exception:
        state["open"][-1]["exit_plan"] = {
            "kind": "take_profit+model_flip+settle",
            "take_profit_add": TAKE_PROFIT_ADD,
            "take_profit_cap": TAKE_PROFIT_CAP,
            "fee_floors_locked": True,
        }
    save_account(state)
    return "Checked all open BTC 15-minute markets. Paper buy."


def _cached(url):
    try:
        with open(_CACHE, encoding="utf-8") as handle:
            data = json.load(handle)
        row = data.get(url) if isinstance(data, dict) else None
        if not isinstance(row, dict) or time.time() - float(row.get("at") or 0) > 60:
            return None
        return row.get("body")
    except Exception:
        return None


def _store(url, body):
    try:
        with open(_CACHE, encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}
    data[url] = {"at": time.time(), "body": body}
    if len(data) > 30:
        data = dict(list(data.items())[-30:])
    tmp = _CACHE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle)
    os.replace(tmp, _CACHE)


def _kalshi_urlopen(req, timeout):
    """Kalshi GETs share one pace / back-off / cache across towers (kalshi_gateway)."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root not in sys.path:
        sys.path.insert(0, root)
    try:
        import kalshi_gateway
    except ImportError:
        return urllib.request.urlopen(req, timeout=timeout)
    return kalshi_gateway.urlopen(req, timeout=timeout)


def _gateway_busy(exc) -> bool:
    return type(exc).__name__ == "GatewayBusy"


def get_json(url, headers=None, tries=3):
    hit = _cached(url)
    if hit is not None:
        return hit
    err = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=headers or UA)
            with _kalshi_urlopen(req, timeout=15) as r:
                body = json.load(r)
            _store(url, body)
            return body
        except Exception as e:  # network hiccup -> retry, then mark it failed
            err = e
            if _gateway_busy(e):
                break  # shared Kalshi door is shut; skip this read now
            time.sleep(1 + i)
    raise RuntimeError("public GET failed")


def phi(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def fee_per_contract(p):
    """Kalshi taker fee for 1 contract at price p (dollars), rounded up to the cent."""
    return math.ceil(round(0.07 * p * (1 - p) * 100, 6)) / 100


def parse_ts(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


# ---------------- data ----------------
def _market_row(m):
    if not m.get("close_time"):
        return None
    return {
        "ticker": m["ticker"],
        "target": fnum(m.get("floor_strike")),
        "yes_bid": fnum(m.get("yes_bid_dollars")), "yes_ask": fnum(m.get("yes_ask_dollars")),
        "no_bid": fnum(m.get("no_bid_dollars")), "no_ask": fnum(m.get("no_ask_dollars")),
        "open_time": parse_ts(m["open_time"]) if m.get("open_time") else None,
        "close_time": parse_ts(m["close_time"]),
    }


def kalshi_markets(series: str = "KXBTC15M"):
    """Every still-open window for a 15m series with a target, nearest close first."""
    now = dt.datetime.now(dt.timezone.utc)
    out = []
    cursor = ""
    while True:
        url = f"{KALSHI}/markets?series_ticker={series}&status=open&limit=200"
        if cursor:
            url += f"&cursor={cursor}"
        d = get_json(url)
        for raw in d.get("markets", []) or []:
            row = _market_row(raw)
            if not row or row["close_time"] <= now or row["target"] is None:
                continue
            row["series"] = series
            out.append(row)
        cursor = d.get("cursor") or ""
        if not cursor or not d.get("markets"):
            break
        if len(out) >= 500:
            break
    out.sort(key=lambda row: row["close_time"])
    return out


def kalshi_market():
    """Nearest open KXBTC15M (compat helper)."""
    ms = kalshi_markets("KXBTC15M")
    return ms[0] if ms else None


def eth_spot_prices():
    out = {}
    try:
        out["coinbase"] = float(get_json("https://api.coinbase.com/v2/prices/ETH-USD/spot")["data"]["amount"])
    except Exception as e:
        print(f"  coinbase ETH spot failed: {e}")
    try:
        out["kraken"] = float(get_json("https://api.kraken.com/0/public/Ticker?pair=ETHUSD")["result"]["XETHZUSD"]["c"][0])
    except Exception as e:
        print(f"  kraken ETH spot failed: {e}")
    return out


def snapshot_btcd_ladder(root, btc_spot: float):
    """History-only: nearest KXBTCD event strikes around spot (staff 1am ladder screen)."""
    try:
        if root not in sys.path:
            sys.path.insert(0, root)
        import kalshi_history
        ev = get_json(f"{KALSHI}/events?series_ticker=KXBTCD&status=open&limit=5")
        events = ev.get("events") or []
        if not events:
            return 0
        # Prefer soonest close / 1am style event first in list.
        event_ticker = events[0].get("event_ticker")
        if not event_ticker:
            return 0
        d = get_json(f"{KALSHI}/markets?event_ticker={event_ticker}&limit=200")
        n = 0
        candidates = []
        for m in d.get("markets") or []:
            try:
                strike = float(m.get("floor_strike"))
            except (TypeError, ValueError):
                continue
            if abs(strike - float(btc_spot)) > 800:
                continue
            yes_ask = fnum(m.get("yes_ask_dollars"))
            no_ask = fnum(m.get("no_ask_dollars"))
            close = parse_ts(m["close_time"]) if m.get("close_time") else None
            min_left = (close - dt.datetime.now(dt.timezone.utc)).total_seconds() / 60 if close else None
            side = "YES" if btc_spot >= strike else "NO"
            ask = yes_ask if side == "YES" else no_ask
            kalshi_history.record_snapshot(
                root,
                series="KXBTCD",
                ticker=str(m.get("ticker") or ""),
                spot=float(btc_spot),
                target=strike,
                side=side,
                yes_ask=yes_ask,
                no_ask=no_ask,
                model_p=None,
                minutes_left=min_left,
                regime="ladder_watch",
                note=str(events[0].get("title") or "")[:120],
                extra={"event": event_ticker},
            )
            # Phase 3: ladder companion candidate (score only — paper buy still via desk gates).
            if ask is not None:
                depth = None
                ticker = str(m.get("ticker") or "")
                # Cheap depth: only for the nearest few strikes (API budget).
                if len(candidates) < 6 and ticker:
                    try:
                        _bid, book_ask, book_depth = book_for_side(ticker, side)
                        if book_ask is not None:
                            ask = book_ask
                        depth = float(book_depth) if book_depth else None
                    except Exception:
                        depth = None
                candidates.append({
                    "ticker": ticker,
                    "spot": float(btc_spot),
                    "strike": strike,
                    "ask": ask,
                    "fee": fee_per_contract(ask),
                    "depth": depth,
                    "model_p": None,  # Φ(z) not attached on daily ladder — shadow rank only
                    "side": side,
                    "series": "KXBTCD",
                })
            n += 1
            if n >= 24:
                break
        if candidates:
            try:
                import desk_phase3
                # Shadow rank when no model_p; ok=True only if a later pass attaches Φ≥80%.
                pick = desk_phase3.pick_ladder_rung(
                    candidates, min_edge=_edge_buffer(), require_ok=False,
                )
                if pick:
                    desk_phase3.remember_ladder_pick(root, pick)
                    tag = "ok" if pick.get("ok") else "shadow"
                    print(
                        f"  KXBTCD ladder companion {tag} {pick.get('ticker')} "
                        f"strike={pick.get('strike')} score={pick.get('score')} (paper score only)"
                    )
            except Exception as exc:
                print(f"  KXBTCD ladder companion score failed: {exc}")
        return n
    except Exception as e:
        print(f"  KXBTCD ladder history failed: {e}")
        return 0


def book_for_side(ticker, side):
    """Kalshi's order book lists BIDS only. A YES offer at price A is a NO bid at 1-A (and vice versa).
    Returns (bid, ask, contracts offered at or below the ask) for `side`, read live from the book."""
    ob = get_json(f"{KALSHI}/markets/{ticker}/orderbook").get("orderbook_fp", {})
    own = [(float(p), float(q)) for p, q in (ob.get("yes_dollars" if side == "YES" else "no_dollars") or [])]
    other = [(float(p), float(q)) for p, q in (ob.get("no_dollars" if side == "YES" else "yes_dollars") or [])]
    if not other:
        return None, None, 0.0
    best_other = max(p for p, _ in other)
    ask = round(1 - best_other, 4)
    bid = max((p for p, _ in own), default=None)
    depth = sum(q for p, q in other if p >= best_other - 1e-9)
    return bid, ask, depth


def prefetch_books(jobs):
    """Parallel orderbook fetches. jobs = [(ticker, side), ...].

    Returns ({(ticker, side): (bid, ask, depth)}, {(ticker, side): error_str}).
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    books, errors = {}, {}
    if not jobs:
        return books, errors

    def _one(pair):
        ticker, side = pair
        try:
            return pair, book_for_side(ticker, side), None
        except Exception as exc:  # noqa: BLE001
            return pair, (None, None, 0.0), str(exc)

    workers = min(8, max(1, len(jobs)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(_one, job) for job in jobs]
        for fut in as_completed(futs):
            pair, result, err = fut.result()
            if err:
                errors[pair] = err
            books[pair] = result
    return books, errors


def spot_prices():
    out = {}
    try:
        out["coinbase"] = float(get_json("https://api.coinbase.com/v2/prices/BTC-USD/spot")["data"]["amount"])
    except Exception as e:
        print(f"  coinbase spot failed: {e}")
    try:
        out["kraken_futures"] = float(get_json(
            "https://futures.kraken.com/derivatives/api/v3/tickers/PF_XBTUSD")["ticker"]["last"])
    except Exception as e:
        print(f"  kraken futures failed: {e}")
    try:
        out["bitstamp"] = float(get_json("https://www.bitstamp.net/api/v2/ticker/btcusd/")["last"])
    except Exception as e:
        print(f"  bitstamp failed: {e}")
    return out


def candles_1m(product: str = "BTC-USD"):
    """Coinbase 1-minute candles, returned oldest -> newest as (time, close)."""
    rows = get_json(f"https://api.exchange.coinbase.com/products/{product}/candles?granularity=60")
    rows = sorted(rows, key=lambda r: r[0])     # [time, low, high, open, close, volume]
    return [(r[0], float(r[4])) for r in rows]


def dvol_latest():
    end = int(time.time() * 1000)
    start = end - 2 * 3600 * 1000
    d = get_json("https://www.deribit.com/api/v2/public/get_volatility_index_data"
                 f"?currency=BTC&resolution=60&start_timestamp={start}&end_timestamp={end}")
    data = d["result"]["data"]
    return float(data[-1][4])                    # [ts, open, high, low, close]


def usd_high_impact_near(block_start, block_end):
    """
    High-impact USD events near the block.
    Prefers helpers.calendar_cache last-good so a CDN blip does not fail-closed
    every window. Returns [] for no hits, None only if calendar never loaded.
    """
    d = None
    try:
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        from helpers.calendar_cache import load_ff_calendar
        d = load_ff_calendar(DESK_ROOT)
    except Exception:
        d = None
    if d is None:
        try:
            d = get_json("https://nfs.faireconomy.media/ff_calendar_thisweek.json", headers=UA)
        except Exception:
            return None
    if not isinstance(d, list):
        return None
    w = dt.timedelta(minutes=NEWS_WINDOW_MIN)
    hits = []
    for ev in d:
        if ev.get("country") != "USD" or ev.get("impact") != "High":
            continue
        try:
            t = dt.datetime.fromisoformat(ev["date"]).astimezone(dt.timezone.utc)
        except Exception:
            continue
        if block_start - w <= t <= block_end + w:
            hits.append(f"{ev.get('title')} at {t:%H:%M} UTC")
    return hits


# ---------------- main ----------------
def _card(sentence):
    print("CARD: " + sentence)
    return 0


def _card_sentence(*, buys, markets_n, eth_markets_n, last_sentence, skip_reasons=None):
    """CARD body only. Prefer first evaluate/ops skip over generic no-buy (#396 sibling)."""
    if buys:
        if last_sentence and "parlay" in str(last_sentence).lower():
            return str(last_sentence)
        return (
            f"Checked {markets_n} open BTC 15-minute markets. "
            f"{buys} paper buy{'s' if buys != 1 else ''}."
        )
    skips = [str(s).strip() for s in (skip_reasons or []) if str(s).strip()]
    if skips:
        return skips[0]
    if not markets_n and eth_markets_n:
        return "Checked ETH/BTC crypto Kalshi markets. No paper buy."
    return (
        last_sentence
        if last_sentence
        else "Checked all open BTC 15-minute markets. No paper buy."
    )


def _densify_skip_brain(
    *,
    reasons,
    ticker: str = "",
    side: str = "",
    edge=None,
    confidence=None,
    depth=None,
    score=None,
    note: str = "",
) -> None:
    """ETH/BTC skip → desk_brain → skip_board. Observe only; never LIVE."""
    if IS_SHADOW:
        return
    why = [str(r) for r in (reasons or []) if str(r).strip()]
    if not why:
        return
    try:
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        import desk_brain
        desk_brain.record_decision(
            DESK_ROOT,
            bot="btc15m",
            action="skip",
            ticker=str(ticker or ""),
            side=str(side or ""),
            edge=edge,
            confidence=confidence,
            depth=depth,
            reasons=why,
            score=score,
            note=str(note or "")[:160],
        )
    except Exception:
        pass


def eth_early_should_buy(regime, reasons=None, *, delay_eth: bool = False) -> bool:
    """
    E1 #106 — ETH early singles under the same confident_early gates as BTC.
    Not parlay-only: clear fee-aware early → single paper buy (unless lead-lag delay).
    """
    if str(regime or "") != "confident_early":
        return False
    if delay_eth:
        return False
    return not bool(reasons or [])


def _sigma_for(price, min_left, closes, dvol):
    """Return (sigma, realized, sig_dvol) for this window's minutes-left."""
    realized = None
    if closes:
        last = closes[-61:]
        rets = [math.log(b / a) for a, b in zip(last, last[1:]) if a > 0]
        if len(rets) >= 10:
            realized = statistics.stdev(rets) * price * math.sqrt(max(min_left, 0))
    sig_dvol = (
        price * dvol / 100 * math.sqrt(max(min_left, 0) / 525600) if dvol else None
    )
    if sig_dvol is not None and realized is not None:
        sigma = max(sig_dvol, realized)
    elif sig_dvol is not None:
        sigma = sig_dvol
    elif realized is not None:
        sigma = realized * DVOL_FAIL_MULT
    else:
        sigma = None
    return sigma, realized, sig_dvol


def scan_drop_reasons(min_left, ask=None, cushion=None, *, series="KXBTC15M", cushion_floor=None):
    """Scan drops for one open window. An empty list can still face later gates.

    Under 1 minute is too late. An ask outside 70–92¢ is out. A cushion under
    $35 on BTC or $1.50 on ETH is out. Ask and cushion are checked only when
    those values are passed. The 0.05 floor is not changed here.
    """
    drops = []
    try:
        left = float(min_left)
    except (TypeError, ValueError):
        left = -1.0
    if left < 1.0:
        drops.append("under 1 minute")
    series_u = str(series or "").upper()
    if cushion_floor is None:
        cush_floor = MIN_CUSHION_ETH if "ETH" in series_u else MIN_CUSHION_USD
    else:
        cush_floor = float(cushion_floor)
    if ask is not None:
        try:
            px = float(ask)
        except (TypeError, ValueError):
            px = None
        if px is None or not (ASK_MIN <= px <= ASK_MAX):
            drops.append(f"ask outside {ASK_MIN:.2f}-{ASK_MAX:.2f}")
    if cushion is not None:
        try:
            gap = float(cushion)
        except (TypeError, ValueError):
            gap = -1.0
        if gap < cush_floor:
            drops.append(f"cushion ${gap:.2f} < ${cush_floor:g}")
    return drops


def late_scan_reasons(reasons):
    """The late re-check drops the early clock line and keeps under 1 minute."""
    return [r for r in (reasons or []) if "min left" not in str(r)]


def evaluate_window(m, price, closes, dvol, coinbase_only, edge_buf, book=None,
                    min_minutes_left=None, min_cushion=None):
    """Apply the same guideline gates to one open 15m crypto window (BTC or ETH).

    Cheap gates first (time / band / cushion) before news and heavy reasons.
    `book` optional (bid, ask, depth) from prefetch_books.
    Returns dict with reasons, side, p, ask, bid, fee, depth, edge, min_left.
    """
    now = dt.datetime.now(dt.timezone.utc)
    min_left = (m["close_time"] - now).total_seconds() / 60
    side = "YES" if price > m["target"] else "NO"
    cushion = abs(price - m["target"])
    time_floor = MIN_MINUTES_LEFT if min_minutes_left is None else float(min_minutes_left)
    cush_floor = MIN_CUSHION_USD if min_cushion is None else float(min_cushion)
    out = {
        "ticker": m["ticker"],
        "series": m.get("series") or "KXBTC15M",
        "min_left": min_left,
        "sigma": None,
        "realized": None,
        "sig_dvol": None,
        "reasons": [],
        "side": side,
        "p": None,
        "ask": None,
        "bid": None,
        "fee": None,
        "depth": 0.0,
        "edge": None,
        "toward": None,
        "news": None,
        "cushion": cushion,
        "confidence": None,
    }
    # Cheap gates first — fail fast before σ / news / book work when possible.
    # Under 1 minute is its own drop. The late re-check strips "min left" and
    # must still keep this one. Cushion under the dollar floor is dropped even
    # when z already clears.
    cheap = []
    series_name = m.get("series") or "KXBTC15M"
    for reason in scan_drop_reasons(min_left, series=series_name):
        cheap.append(reason)
    if min_left >= 1.0 and min_left < time_floor:
        cheap.append(f"only {min_left:.1f} min left (< {time_floor:g})")
    listing_ask = m["yes_ask"] if side == "YES" else m["no_ask"]
    if listing_ask is not None and not (ASK_MIN <= listing_ask <= ASK_MAX):
        # Still allow book to rescue a stale listing; only hard-fail if book also bad later.
        pass

    sigma, realized, sig_dvol = _sigma_for(price, min_left, closes, dvol)
    out["sigma"] = sigma
    out["realized"] = realized
    out["sig_dvol"] = sig_dvol
    if sigma is None:
        out["reasons"] = cheap + ["could not compute sigma"]
        return out

    z = cushion / sigma if sigma > 0 else 0
    p = phi(z)
    ask = listing_ask
    bid = m["yes_bid"] if side == "YES" else m["no_bid"]
    depth = 0.0
    if book is not None:
        b_bid, b_ask, depth = book[0], book[1], book[2]
        if b_ask is not None:
            ask = b_ask
        if b_bid is not None:
            bid = b_bid
    else:
        try:
            b_bid, b_ask, depth = book_for_side(m["ticker"], side)
            if b_ask is not None:
                ask = b_ask
            if b_bid is not None:
                bid = b_bid
        except Exception as e:
            out["reasons"] = cheap + [f"orderbook failed ({e})"]
            return out
    if ask is None or bid is None:
        out["reasons"] = cheap + ["missing bid/ask"]
        return out

    fee = fee_per_contract(ask)
    spread = ask - bid
    need = ask + fee + edge_buf
    toward = None
    if len(closes) >= 6:
        move = closes[-1] - closes[-6]
        toward = (move < 0) if side == "YES" else (move > 0)
    news = None
    try:
        start = m["open_time"] or (m["close_time"] - dt.timedelta(minutes=15))
        news = usd_high_impact_near(start, m["close_time"])
    except Exception:
        news = None

    reasons = list(cheap)
    # Staff near-miss soft promote may relax z/p floors slightly — never edge/fee.
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
    zmin_acc = MIN_Z_COINBASE_ONLY if coinbase_only else MIN_Z
    p_acc = max(0.50, float(MIN_MODEL_ACCURATE) - p_relax)
    p_speed = max(0.50, float(MIN_MODEL_SPEED) - p_relax)
    lane = "accurate"
    need_p = float(need)
    if p + 1e-12 >= p_acc:
        lane = "accurate"
    elif p + 1e-12 >= p_speed:
        lane = "speed"
        need_p = float(need) + SPEED_EDGE_EXTRA
    else:
        reasons.append(f"p {p:.3f} < speed floor {p_speed:.2f}")
    if p < need_p:
        reasons.append(f"p {p:.3f} < ask+fee+buf ({lane}) = {need_p:.3f}")
    # Speed lane: allow near-miss z band only when extra fee-aware edge already clears.
    zmin = zmin_acc if lane == "accurate" else min(zmin_acc, MIN_Z_SPEED)
    zmin = max(0.40, float(zmin) - z_relax)
    if z < zmin:
        reasons.append(f"z {z:.2f} < {zmin}")
    for reason in scan_drop_reasons(
        min_left, ask, cushion,
        series=out.get("series") or series_name,
        cushion_floor=cush_floor,
    ):
        if reason not in reasons:
            reasons.append(reason)
    if not (ASK_MIN <= ask <= ASK_MAX):
        reasons.append(f"ask {ask:.2f} outside {ASK_MIN:.2f}-{ASK_MAX:.2f}")
    if spread > MAX_SPREAD + 1e-9:
        reasons.append(f"spread {spread:.2f} > {MAX_SPREAD:.2f}")
    if depth < MIN_DEPTH:
        reasons.append(f"only {depth:.0f} contracts at/below ask (< {MIN_DEPTH})")
    # Soft: unknown candle trend does not block.
    # Adverse toward-target only blocks when p has not already cleared fee-aware need —
    # otherwise candle double-vetoes fee-clear Φ edges (p/z/edge floors stay locked).
    if toward and p + 1e-12 < float(need_p):
        reasons.append("last 5 candles moving toward target")
    # Living upgrade P0: calendar never loaded → FAIL-CLOSED (block buys).
    # Known high-impact hits still block. Matches desk copy "unavailable = skip BUY".
    if news is None:
        reasons.append("USD news calendar unavailable (fail-closed)")
    elif news:
        reasons.append("USD high-impact news near this block")

    out.update({
        "reasons": reasons,
        "lane": lane,
        "side": side,
        "p": p,
        "confidence": p,
        "ask": ask,
        "bid": bid,
        "fee": fee,
        "depth": depth,
        "edge": float(p) - float(ask) - float(fee),
        "toward": toward,
        "news": news,
        "calendar_loaded": news is not None,
        "news_fail_closed": news is None,
        "news_soft_unavailable": False,
        "candle_soft_unknown": toward is None,
        "cushion": cushion,
        "z": z,
        "need": need,
        "spread": spread,
        "dvol": dvol,
    })
    return out


def main():
    t0 = time.perf_counter()
    now = dt.datetime.now(dt.timezone.utc)
    # Living upgrade: CLI/standalone honors desk entry_gate (exits still run).
    if not IS_SHADOW:
        try:
            if DESK_ROOT not in sys.path:
                sys.path.insert(0, DESK_ROOT)
            import desk_living
            blocked = desk_living.honor_desk_entry_gate(DESK_ROOT)
            if blocked:
                print(f"Desk entry_gate (CLI honor): {blocked[:160]}")
        except Exception:
            pass
    account = load_account()
    reconcile_buy_intent(account)
    if not os.path.exists(ACCOUNT):
        save_account(account)
    try:
        settle_account(account)
        save_account(account)
    except Exception:
        pass
    edge_buf = _edge_buffer()
    flip_delta = 0.08
    flip_on = True
    try:
        desk = _desk()
        cfg = desk.load_settings(DESK_ROOT)
        flip_delta = float(cfg.get("model_flip_delta") or 0.08)
        flip_on = bool(cfg.get("model_flip_exits", True))
    except Exception:
        pass
    tag = "SHADOW " if IS_SHADOW else ""
    print(f"BTC 15-min Kalshi paper check  ({tag}no real orders)  {now:%Y-%m-%d %H:%M:%S} UTC")
    print(f"Price source https://api.elections.kalshi.com/trade-api/v2 at {now:%Y-%m-%dT%H:%M:%SZ}\n")

    markets = kalshi_markets("KXBTC15M")
    eth_markets = kalshi_markets("KXETH15M")
    # Track public tape for crypto series from staff screenshots.
    if not IS_SHADOW:
        try:
            if DESK_ROOT not in sys.path:
                sys.path.insert(0, DESK_ROOT)
            import kalshi_tape
            tickers = [m["ticker"] for m in markets] + [m["ticker"] for m in eth_markets]
            tape = kalshi_tape.sync_tape_family(
                DESK_ROOT, "crypto15m", tickers=tickers,
            )
            print(
                f"Kalshi tape: +{tape.get('last_added') or 0} new prints "
                f"(kept {len(tape.get('trades') or [])}; "
                f"{len(markets)} BTC + {len(eth_markets)} ETH 15m window(s))"
            )
            if tape.get("last_error"):
                print(f"  tape note: {tape['last_error']}")
        except Exception as e:
            print(f"  kalshi tape sync failed: {e}")

    t_spot = time.perf_counter()
    spots = spot_prices()
    spot_secs = time.perf_counter() - t_spot
    if not spots and not eth_markets:
        # Prefer-1/2: all BTC venue spots down + no ETH fallback must not invent a
        # clean "Checked… No paper buy" CARD with empty skip_board (commodity #434
        # sibling). Spot feed-down ≠ fee-aware no-edge after a real check.
        spot_reason = "spot failed"
        print(f"SKIP densify: {spot_reason} (no BTC spot and no ETH windows)")
        _densify_skip_brain(reasons=[spot_reason], note="btc spot densify")
        if not IS_SHADOW:
            try:
                import desk_roi_plan
                desk_roi_plan.record_latency(
                    DESK_ROOT, bot="btc15m", seconds=spot_secs,
                    note="btc15m spot failed", stage="spot",
                )
                desk_roi_plan.record_latency(
                    DESK_ROOT, bot="btc15m", seconds=time.perf_counter() - t0,
                    note="spot failed card", stage="evaluate",
                )
                for series in ("KXBTC15M", "KXETH15M"):
                    desk_roi_plan.record_empty_card(
                        DESK_ROOT,
                        bot="btc15m",
                        seconds=time.perf_counter() - t0,
                        markets_n=len(markets) if series == "KXBTC15M" else 0,
                        series=series,
                        note=spot_reason,
                    )
            except Exception:
                pass
        return _card(spot_reason)
    price = statistics.mean(spots.values()) if spots else None
    if price is not None:
        print("BTC spot: " + ", ".join(f"{k} ${v:,.2f}" for k, v in spots.items()) + f"  -> avg ${price:,.2f}")
    coinbase_only = list(spots) == ["coinbase"] if spots else False

    closes = []
    try:
        closes = [c for _, c in candles_1m()]
    except Exception as e:
        print(f"  candles failed: {e}")
    dvol = None
    try:
        dvol = dvol_latest()
    except Exception as e:
        print(f"  DVOL failed: {e}")

    # History settle + 15m sweep densify under DESK_SHADOW too (label bridge).
    try:
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        import kalshi_history
        try:
            settled = kalshi_history.settle_open_windows(DESK_ROOT, limit=30)
            if settled.get("settled"):
                print(f"History settle harness: labeled {settled['settled']} window(s)")
        except Exception as exc:
            print(f"  history settle harness skipped: {type(exc).__name__}")
        n15 = kalshi_history.snapshot_open_15m_series(DESK_ROOT)
        if n15:
            print(f"15m series history: recorded {n15} open markets (crypto/metals/energy)")
    except Exception as e:
        print(f"  15m history sweep failed: {e}")
    if not IS_SHADOW and price is not None:
        n_ladder = snapshot_btcd_ladder(DESK_ROOT, price)
        if n_ladder:
            print(f"KXBTCD ladder history: recorded {n_ladder} strikes near spot")

    if not markets:
        print("No open KXBTC15M window right now — still tracking ETH/ladder history.")
    else:
        print(f"Open KXBTC15M windows to score: {len(markets)} (early confident single / volatile→5m parlay)\n")

    # Parallel books for every window's model side (speed).
    book_jobs = []
    for m in markets:
        if price is None:
            break
        side0 = "YES" if price > m["target"] else "NO"
        book_jobs.append((m["ticker"], side0))
    t_book = time.perf_counter()
    books, book_errs = prefetch_books(book_jobs) if book_jobs else ({}, {})
    book_secs = time.perf_counter() - t_book

    scored = []
    for m in markets:
        if price is None:
            break
        key = (m["ticker"], "YES" if price > m["target"] else "NO")
        if key in book_errs:
            ev = {
                "ticker": m["ticker"], "side": key[1], "reasons": [f"orderbook failed ({book_errs[key]})"],
                "ask": None, "bid": None, "p": None, "fee": None, "depth": 0, "edge": None,
                "confidence": None, "close_time": m["close_time"], "market": m, "series": "KXBTC15M",
            }
        else:
            ev = evaluate_window(
                m, price, closes, dvol, coinbase_only, edge_buf,
                book=books.get(key),
            )
            ev["close_time"] = m["close_time"]
            ev["market"] = m
        scored.append(ev)

    # Rank fits by opportunity score; spend open-risk on best edges first.
    try:
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        import desk_brain
        ranked = desk_brain.rank_candidates(scored, edge_key="edge", conf_key="confidence", depth_key="depth")
    except Exception:
        desk_brain = None
        ranked = scored

    try:
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        import kalshi_history
        import kalshi_parlay
    except Exception:
        kalshi_history = None
        kalshi_parlay = None

    buys = 0
    skips = 0
    parlays = 0
    parlay_legs = []  # candidates for ≤5m combo
    skip_reasons = []  # first evaluate/ops skip → CARD densify (#396 sibling)
    last_sentence = "Checked all open BTC 15-minute markets. No paper buy."
    # Selective volume: +1 fee-clear buy/check on green Chicago day (min_edge locked).
    today_pnl = 0.0
    today_tag = now.strftime("%Y-%m-%d")
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
            top = next((ev for ev in ranked if not ev.get("reasons")), None) or (
                ranked[0] if ranked else {}
            )
            desk_roi_plan.record_selective_attempt(
                DESK_ROOT,
                "btc15m",
                edge=(top or {}).get("edge"),
                z=(top or {}).get("z"),
                depth=(top or {}).get("depth"),
                today=today_pnl,
                boosted=True,
                note="selective +1 path considered",
            )
        if desk_roi_plan.selective_kill_active(DESK_ROOT, "btc15m"):
            max_buys_eff = int(MAX_BUYS_PER_CHECK)
            print("Selective +1 KILLED (5 green-day EV worsen) — base max_buys only")
        else:
            max_buys_eff = int(
                desk_more.selective_max_buys(
                    "btc15m", base=MAX_BUYS_PER_CHECK, today=today_pnl,
                )
            )
    except Exception:
        max_buys_eff = int(MAX_BUYS_PER_CHECK)
    if today_pnl >= 0 and max_buys_eff > MAX_BUYS_PER_CHECK:
        print(f"Selective volume: max buys {max_buys_eff} (today ${today_pnl:.2f} ≥ 0, fee floors locked)")
    # Buy-loop gate locks (cool / stale / daily-R) — densify CARD+brain and
    # refuse max-buys(0) invent (#522 commodity / #521 sports twin).
    try:
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        import desk_roi_plan

        def _densify_gate_skip(reason: str, *, note: str) -> None:
            skip_reasons.insert(0, str(reason))
            if desk_brain and not IS_SHADOW:
                try:
                    desk_brain.record_decision(
                        DESK_ROOT, bot="btc15m", action="skip",
                        reasons=[str(reason)], note=note,
                    )
                except Exception:
                    pass

        cool = desk_roi_plan.adverse_cool_blocks(DESK_ROOT, "btc15m")
        if cool:
            print(f"Adverse cool: {cool}")
            max_buys_eff = 0
            _densify_gate_skip(cool, note="btc adverse-cool densify")
        stale = desk_roi_plan.stale_world_blocks(DESK_ROOT, "btc15m")
        if stale:
            print(f"Stale-world: {stale}")
            max_buys_eff = 0
            _densify_gate_skip(stale, note="btc stale-world densify")
        # Prefer-1: densify real entry_gate reason (not bland invent) when honor locked.
        if not IS_SHADOW and os.environ.get("DESK_BLOCK_ENTRIES") == "1":
            try:
                import desk_living
                gate_why = desk_living.desk_block_entries_reason(
                    "Desk entry_gate blocked a new paper buy. Settles still run."
                )
            except Exception:
                gate_why = ""
            if gate_why:
                print(f"Entry gate: {gate_why}")
                max_buys_eff = 0
                _densify_gate_skip(gate_why, note="btc entry-gate densify")
        # Daily R budget → settle-only after tower hits target (exits stay on).
        # Insert last so settle-only stays skips[0] over cool/stale/entry.
        r_block = desk_roi_plan.daily_r_blocks("btc15m", today_pnl)
        if r_block:
            print(f"Settle-only: {r_block}")
            max_buys_eff = 0
            _densify_gate_skip(r_block, note="btc daily-r densify")
    except Exception:
        pass

    # Cross-tower firm queue: offer fee-clear BTC fits for desk-wide rank.
    try:
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        import desk_roi_plan
        firm_offers = []
        for ev in ranked:
            if ev.get("reasons"):
                continue
            if ev.get("edge") is None or not ev.get("side"):
                continue
            firm_offers.append({
                "bot": "btc15m",
                "ticker": str(ev.get("ticker") or ""),
                "side": ev.get("side"),
                "edge": ev.get("edge"),
                "confidence": ev.get("confidence") if ev.get("confidence") is not None else ev.get("p"),
                "depth": ev.get("depth"),
                "stake_est": 25.0,
            })
        desk_roi_plan.offer_firm_candidates(DESK_ROOT, firm_offers, bot="btc15m")
        desk_roi_plan.rebuild_firm_queue(
            DESK_ROOT,
            remaining_risk=desk_roi_plan.remaining_desk_risk(DESK_ROOT),
            note="btc15m firm offer",
        )
    except Exception:
        pass

    for ev in ranked:
        if buys >= max_buys_eff:
            skips += 1
            max_note = f"max buys this check ({max_buys_eff})"
            # Prefer-1: gate (settle-only / cool / stale / entry / ruin) zeroed the cap —
            # do not invent capacity skip into brain while CARD names the gate.
            gate_keys = (
                "settle-only", "adverse cool", "stale-world", "clock-skew",
                "entry_gate", "ruin drill", "daily loss",
                "max open risk", "max open positions",
            )
            gate_hits = [
                str(s)
                for s in skip_reasons
                if any(k in str(s).lower() for k in gate_keys)
            ]
            gate_lock = max_buys_eff == 0 and bool(gate_hits)
            if gate_lock:
                gate_why = next(
                    (s for s in gate_hits if "settle-only" in s.lower()),
                    gate_hits[0],
                )
                print(f"--- {ev.get('ticker')}  skip: {gate_why}")
                continue
            skip_reasons.append(max_note)
            print(f"--- {ev.get('ticker')}  skip: {max_note}")
            if not IS_SHADOW:
                try:
                    import desk_roi_plan
                    desk_roi_plan.note_pending_high_edge(
                        DESK_ROOT,
                        bot="btc15m",
                        ticker=str(ev.get("ticker") or ""),
                        edge=ev.get("edge"),
                        reason=max_note,
                    )
                except Exception:
                    pass
            # Mirror sticky/firm densify (#405 sibling) — CARD already has max_note;
            # skip_board needs desk_brain → record_skip_codes.
            if desk_brain and not IS_SHADOW:
                try:
                    desk_brain.record_decision(
                        DESK_ROOT, bot="btc15m", action="skip",
                        ticker=ev.get("ticker") or "", side=ev.get("side") or "",
                        edge=ev.get("edge"), confidence=ev.get("confidence") or ev.get("p"),
                        depth=ev.get("depth"), reasons=[max_note],
                        score=ev.get("_brain_score"),
                    )
                except Exception:
                    pass
            continue
        m = ev.get("market") or {"ticker": ev.get("ticker"), "target": 0, "close_time": ev.get("close_time"),
                                 "yes_bid": None, "yes_ask": None, "no_bid": None, "no_ask": None}
        min_left = ev.get("min_left")
        if min_left is None and ev.get("close_time"):
            min_left = (ev["close_time"] - now).total_seconds() / 60
        close = ev.get("close_time")
        if close is not None:
            print(
                f"--- {ev.get('ticker')}  target ${float(m.get('target') or 0):,.2f}  "
                f"closes {close:%H:%M} UTC"
            )
        else:
            print(f"--- {ev.get('ticker')}")
        if min_left is not None:
            print(f"  ({min_left:.1f} min left) brain_score={ev.get('_brain_score', 'n/a')}")
        if ev.get("sigma") is not None:
            print(
                f"  Sigma used ${ev['sigma']:,.2f}"
                + (f" | realized ${ev['realized']:,.2f}" if ev.get("realized") is not None else "")
            )
        if ev.get("side") and ev.get("ask") is not None and ev.get("p") is not None:
            print(
                f"  Side {ev['side']}: cushion ${ev.get('cushion', 0):,.2f}  z {ev.get('z', 0):.2f}  "
                f"p {ev['p']:.3f}  ask {ev['ask']:.2f}  fee {ev['fee']:.2f}  "
                f"need p >= {ev.get('need', 0):.3f}  spread {ev.get('spread', 0):.2f}  "
                f"(venue edge {edge_buf:.2f})"
            )
            print(f"  Depth offered at or below ask: {ev.get('depth', 0):,.0f} contracts")

        if account.get("open"):
            marked = False
            for pos in account.get("open") or []:
                if not isinstance(pos, dict):
                    continue
                if ev.get("ticker") and pos.get("ticker") != ev.get("ticker"):
                    continue
                before = pos.get("last_mark")
                watch_open(
                    pos, ev.get("bid"), model_side=ev.get("side"),
                    model_p=ev.get("p"), market=m,
                )
                if pos.get("last_mark") != before:
                    marked = True
            if marked and not IS_SHADOW:
                save_account(account)

        if account.get("open") and ev.get("bid") is not None:
            tp_fee = fee_per_contract(ev["bid"]) if ev["bid"] else 0
            tp_sold = manage_take_profits(
                account, ev["bid"], tp_fee, ticker=ev.get("ticker"),
                market=m, model_side=ev.get("side"),
            )
            if tp_sold:
                save_account(account)
                for line in tp_sold:
                    print(f"  TAKE-PROFIT SELL: {line}")
                    if desk_brain and not IS_SHADOW:
                        try:
                            desk_brain.record_decision(
                                DESK_ROOT, bot="btc15m", action="flip",
                                ticker=ev.get("ticker") or "", side=ev.get("side") or "",
                                note=line,
                            )
                        except Exception:
                            pass
                try:
                    import desk_roi_plan
                    desk_roi_plan.record_anti_revenge(
                        DESK_ROOT, bot="btc15m",
                        ticker=str(ev.get("ticker") or ""), reason="take-profit",
                        note=str(tp_sold[0])[:120],
                    )
                except Exception:
                    pass
        if flip_on and account.get("open") and ev.get("side") and ev.get("bid") is not None and ev.get("p") is not None:
            sold = manage_model_flips(
                account,
                ev["side"],
                ev["p"],
                ev["bid"],
                fee_per_contract(ev["bid"]) if ev["bid"] else 0,
                flip_delta,
                ticker=ev.get("ticker"),
                market=m,
            )
            if sold:
                save_account(account)
                for line in sold:
                    print(f"  MODEL-FLIP SELL: {line}")
                    if desk_brain and not IS_SHADOW:
                        try:
                            desk_brain.record_decision(
                                DESK_ROOT, bot="btc15m", action="flip",
                                ticker=ev.get("ticker") or "", side=ev.get("side") or "",
                                note=line,
                            )
                        except Exception:
                            pass
                try:
                    import desk_roi_plan
                    desk_roi_plan.record_anti_revenge(
                        DESK_ROOT, bot="btc15m",
                        ticker=str(ev.get("ticker") or ""), reason="model-flip",
                        note=str(sold[0])[:120],
                    )
                except Exception:
                    pass

        reasons = list(ev.get("reasons") or [])
        ml = float(min_left) if min_left is not None else 0.0
        regime = "unknown"
        if kalshi_parlay is not None:
            regime = kalshi_parlay.classify_regime(
                minutes_left=ml,
                model_p=ev.get("p"),
                z=ev.get("z"),
                cushion=ev.get("cushion"),
                min_cushion=MIN_CUSHION_USD,
                min_z=MIN_Z_COINBASE_ONLY if coinbase_only else MIN_Z,
                min_p=MIN_MODEL_PROB,
                early_min=MIN_MINUTES_LEFT,
                parlay_max=PARLAY_MAX_MIN,
                parlay_min=PARLAY_MIN_MIN,
            )
        # Safety: evaluate already fee-cleared in early window — never re-veto
        # into volatile_hold / ≤5m parlay (#378/#380 parity).
        if (
            regime == "volatile_hold"
            and not reasons
            and ml + 1e-12 >= float(MIN_MINUTES_LEFT)
        ):
            regime = "confident_early"
        print(f"  regime: {regime}")
        # History snapshot densify under DESK_SHADOW (settle→near-miss label bridge).
        if kalshi_history is not None:
            try:
                kalshi_history.record_snapshot(
                    DESK_ROOT,
                    series="KXBTC15M",
                    ticker=str(ev.get("ticker") or ""),
                    spot=price,
                    target=float(m.get("target") or 0) or None,
                    side=ev.get("side"),
                    yes_ask=m.get("yes_ask"),
                    no_ask=m.get("no_ask"),
                    model_p=ev.get("p"),
                    minutes_left=ml,
                    regime=regime,
                    note="; ".join(reasons)[:180],
                )
            except Exception:
                pass

        # Volatile → hold for ≤5m parlay (thin evaluate only).
        if regime == "volatile_hold":
            hold_reason = "volatile — holding for ≤5m parlay window"
            if hold_reason not in reasons:
                reasons.append(hold_reason)
            if kalshi_history is not None and ev.get("side"):
                try:
                    kalshi_history.mark_hold(
                        DESK_ROOT, str(ev.get("ticker") or ""), str(ev.get("side")),
                        hold_reason, ml,
                    )
                except Exception:
                    pass

        # Late window: defer singles into parlay candidate list if fee-aware fit
        # (re-check without the early ≥10m time gate).
        if regime == "parlay_window" and price is not None:
            late = evaluate_window(
                m, price, closes, dvol, coinbase_only, edge_buf,
                book=books.get((m.get("ticker"), ev.get("side") or ("YES" if price > m["target"] else "NO"))),
                min_minutes_left=PARLAY_MIN_MIN,
            )
            late_reasons = late_scan_reasons(late.get("reasons"))
            if not late_reasons and late.get("ask") is not None:
                parlay_legs.append({
                    "ticker": late["ticker"],
                    "side": late["side"],
                    "ask": late["ask"],
                    "fee": late["fee"],
                    "fair": late.get("p"),
                    "close_time": m.get("close_time").isoformat() if hasattr(m.get("close_time"), "isoformat") else str(m.get("close_time") or ""),
                    "series": "KXBTC15M",
                    "edge": late.get("edge"),
                    "confidence": late.get("p"),
                    "depth": late.get("depth"),
                })
                print("  SIGNAL: PARLAY-CANDIDATE (≤5m) — waiting for combo legs")
                reasons = ["deferred to ≤5m parlay candidate"]
            else:
                reasons = late_reasons or reasons

        if reasons or regime in ("volatile_hold", "parlay_window", "too_late"):
            if regime == "confident_early" and not reasons:
                pass  # fall through — should not hit
            else:
                skip_note = "; ".join(reasons or [regime])
                print("  SIGNAL: SKIP -> " + skip_note)
                skips += 1
                skip_reasons.append(skip_note)
                last_sentence = "Checked all open BTC 15-minute markets. No paper buy."
                if desk_brain and not IS_SHADOW:
                    try:
                        desk_brain.record_decision(
                            DESK_ROOT, bot="btc15m", action="skip",
                            ticker=ev.get("ticker") or "", side=ev.get("side") or "",
                            edge=ev.get("edge"), confidence=ev.get("confidence") or ev.get("p"),
                            depth=ev.get("depth"), reasons=reasons or [regime],
                            score=ev.get("_brain_score"),
                        )
                    except Exception:
                        pass
                    try:
                        import desk_living
                        desk_living.record_eval_features(
                            DESK_ROOT, bot="btc15m", action="skip",
                            series=str(ev.get("series") or "KXBTC15M"),
                            ticker=str(ev.get("ticker") or ""),
                            ev=ev,
                            reasons=list(reasons or [regime]),
                            note="; ".join(reasons or [regime])[:160],
                        )
                    except Exception:
                        pass
                # Near-miss shadow densify: also under DESK_SHADOW / living-shadow-tick
                # (brain/living stay non-shadow). Soft z|p only — never edge promote.
                try:
                    import desk_more
                    z_val = None
                    if ev.get("cushion") is not None and ev.get("sigma"):
                        try:
                            z_val = float(ev["cushion"]) / float(ev["sigma"])
                        except (TypeError, ValueError, ZeroDivisionError):
                            z_val = None
                    nm = desk_more.is_near_miss(
                        reasons=reasons or [regime],
                        z=z_val,
                        p=ev.get("p") or ev.get("confidence"),
                        edge=ev.get("edge"),
                        min_edge=float(edge_buf),
                    )
                    soft = [
                        s for s in (nm.get("soft") or [])
                        if s in ("z", "p")
                    ]
                    if nm.get("near_miss") and len(soft) == 1:
                        desk_more.record_near_miss(DESK_ROOT, {
                            "bot": "btc15m",
                            "ticker": ev.get("ticker"),
                            "side": ev.get("side"),
                            "soft": soft,
                            "z": z_val,
                            "p": ev.get("p"),
                            "edge": ev.get("edge"),
                            "ask": ev.get("ask"),
                            "series": "KXBTC15M",
                            "note": nm.get("note"),
                            "is_shadow": bool(IS_SHADOW),
                        })
                        print(f"  NEAR-MISS shadow logged ({nm.get('note')})")
                except Exception:
                    pass
                print()
                continue

        # Confident early (≥10m) and clears guidelines → single paper buy now.
        try:
            if DESK_ROOT not in sys.path:
                sys.path.insert(0, DESK_ROOT)
            import desk_roi_plan
            firm_block = desk_roi_plan.firm_queue_blocks(
                DESK_ROOT, "btc15m", str(ev.get("ticker") or ""),
            )
        except Exception:
            firm_block = ""
        if firm_block:
            print(f"  SIGNAL: SKIP -> {firm_block}")
            skips += 1
            skip_reasons.append(str(firm_block))
            last_sentence = "Checked all open BTC 15-minute markets. No paper buy."
            if desk_brain and not IS_SHADOW:
                try:
                    desk_brain.record_decision(
                        DESK_ROOT, bot="btc15m", action="skip",
                        ticker=ev.get("ticker") or "", side=ev.get("side") or "",
                        edge=ev.get("edge"), confidence=ev.get("confidence") or ev.get("p"),
                        depth=ev.get("depth"), reasons=[firm_block],
                        score=ev.get("_brain_score"),
                    )
                except Exception:
                    pass
            print()
            continue
        # E1 #136/#137 — red-day sticky opens exit-first before speculative buys.
        try:
            if DESK_ROOT not in sys.path:
                sys.path.insert(0, DESK_ROOT)
            import desk_more
            sticky_block = desk_more.sticky_entry_blocks(
                "btc15m",
                today=today_pnl,
                bots=[{"id": "btc15m", "positions": list((account or {}).get("open") or [])}],
            )
        except Exception:
            sticky_block = ""
        if sticky_block:
            print(f"  SIGNAL: SKIP -> {sticky_block}")
            skips += 1
            skip_reasons.append(str(sticky_block))
            last_sentence = "Checked all open BTC 15-minute markets. No paper buy."
            # Mirror firm-queue densify (#403 sibling) — CARD already has sticky;
            # skip_board / holograms need desk_brain → record_skip_codes.
            if desk_brain and not IS_SHADOW:
                try:
                    desk_brain.record_decision(
                        DESK_ROOT, bot="btc15m", action="skip",
                        ticker=ev.get("ticker") or "", side=ev.get("side") or "",
                        edge=ev.get("edge"), confidence=ev.get("confidence") or ev.get("p"),
                        depth=ev.get("depth"), reasons=[sticky_block],
                        score=ev.get("_brain_score"),
                    )
                except Exception:
                    pass
            print()
            continue
        tp = min(round(ev["ask"] + TAKE_PROFIT_ADD, 2), TAKE_PROFIT_CAP)
        print(
            f"  SIGNAL: BUY {ev['side']} on {ev['ticker']} at <= {ev['ask']:.2f} "
            f"(fee {ev['fee']:.2f}). Take-profit {tp:.2f} will paper-sell (fill + 0.15, max 0.99)."
        )
        last_sentence = paper_buy(
            account, ev["ticker"], ev["side"], ev["ask"], ev["fee"], ev["p"],
            ev.get("close_time") or m.get("close_time"), True, edge=ev.get("edge"),
            series=ev.get("series") or "KXBTC15M",
            vol_kwargs={
                "cushion": ev.get("cushion"), "sigma": ev.get("sigma"),
                "spread": ev.get("spread"), "minutes_left": ev.get("min_left"),
                "ask": ev.get("ask"), "ticker": ev.get("ticker"),
                "series": ev.get("series") or "KXBTC15M",
                "calendar_loaded": bool(ev.get("calendar_loaded")),
            },
        )
        if "Paper buy" in last_sentence and "No paper buy" not in last_sentence:
            buys += 1
            if not IS_SHADOW:
                try:
                    import desk_roi_plan
                    import desk_living
                    desk_roi_plan.record_fit(
                        DESK_ROOT, bot="btc15m", outcome="buy",
                        ticker=str(ev.get("ticker") or ""), side=str(ev.get("side") or ""),
                        edge=ev.get("edge"),
                    )
                    desk_living.record_eval_features(
                        DESK_ROOT, bot="btc15m", action="buy",
                        series=str(ev.get("series") or "KXBTC15M"),
                        ticker=str(ev.get("ticker") or ""),
                        ev=ev,
                        note="btc paper buy",
                    )
                    desk_roi_plan.flush_opp_cost_on_buy(
                        DESK_ROOT,
                        bot="btc15m",
                        ticker=str(ev.get("ticker") or ""),
                        edge=ev.get("edge"),
                    )
                except Exception:
                    pass
            if kalshi_history is not None:
                try:
                    kalshi_history.clear_hold(DESK_ROOT, str(ev.get("ticker") or ""))
                except Exception:
                    pass
            if desk_brain and not IS_SHADOW:
                try:
                    note = desk_brain.explain_buy(
                        "btc15m", ev["side"], ev["ticker"], ev.get("edge"),
                        ev.get("confidence") or ev.get("p"), ev.get("depth"),
                    )
                    print(f"  BRAIN: {note}")
                    desk_brain.record_decision(
                        DESK_ROOT, bot="btc15m", action="buy",
                        ticker=ev.get("ticker") or "", side=ev.get("side") or "",
                        edge=ev.get("edge"), confidence=ev.get("confidence") or ev.get("p"),
                        depth=ev.get("depth"), score=ev.get("_brain_score"), note=note,
                    )
                except Exception:
                    pass
        else:
            skips += 1
            block_note = str(last_sentence)[:160] or "desk/account blocked fill"
            skip_reasons.append(block_note)
            print(f"  desk/account blocked fill: {last_sentence}")
            # Mirror sticky/max-buys densify (#407 sibling) — CARD+features already;
            # skip_board needs desk_brain → record_skip_codes.
            if desk_brain and not IS_SHADOW:
                try:
                    desk_brain.record_decision(
                        DESK_ROOT, bot="btc15m", action="skip",
                        ticker=ev.get("ticker") or "", side=ev.get("side") or "",
                        edge=ev.get("edge"), confidence=ev.get("confidence") or ev.get("p"),
                        depth=ev.get("depth"), reasons=[block_note],
                        score=ev.get("_brain_score"),
                    )
                except Exception:
                    pass
            if not IS_SHADOW:
                try:
                    import desk_roi_plan
                    import desk_living
                    desk_roi_plan.record_fit(
                        DESK_ROOT, bot="btc15m", outcome="block",
                        ticker=str(ev.get("ticker") or ""), side=str(ev.get("side") or ""),
                        edge=ev.get("edge"), note=block_note,
                    )
                    desk_living.record_eval_features(
                        DESK_ROOT, bot="btc15m", action="skip",
                        series=str(ev.get("series") or "KXBTC15M"),
                        ticker=str(ev.get("ticker") or ""),
                        ev=ev,
                        reasons=list(ev.get("reasons") or []) + [block_note[:80]],
                        note=block_note,
                    )
                    why = str(last_sentence or "").lower()
                    if any(
                        k in why
                        for k in ("budget", "open risk", "max open", "cash", "risk cap")
                    ):
                        desk_roi_plan.note_pending_high_edge(
                            DESK_ROOT,
                            bot="btc15m",
                            ticker=str(ev.get("ticker") or ""),
                            edge=ev.get("edge"),
                            reason=str(last_sentence)[:120],
                        )
                except Exception:
                    pass
        print()

    # ---- ETH 15m: history + optional late parlay leg (same fee-aware gates) ----
    eth_spots = eth_spot_prices()
    eth_price = statistics.mean(eth_spots.values()) if eth_spots else None
    if eth_price is not None:
        print(f"\nETH spot avg ${eth_price:,.2f}  open KXETH15M windows: {len(eth_markets)}")
    # Prefer-1/2: #436 early densify only fires when `not eth_markets`. Open ETH
    # windows + all ETH spots down must not silent-break into a clean "Checked…
    # No paper buy" CARD (dual BTC/ETH spot-down invent; commodity #434 sibling).
    if eth_markets and eth_price is None:
        eth_spot_reason = "spot failed (eth)"
        print(
            f"SKIP densify: {eth_spot_reason} "
            f"({len(eth_markets)} open ETH window(s), no ETH spot)"
        )
        skip_reasons.append(eth_spot_reason)
        skips += 1
        _densify_skip_brain(
            reasons=[eth_spot_reason],
            note="btc eth spot densify",
        )
        if not IS_SHADOW:
            try:
                import desk_roi_plan
                desk_roi_plan.record_empty_card(
                    DESK_ROOT,
                    bot="btc15m",
                    seconds=time.perf_counter() - t0,
                    markets_n=len(eth_markets),
                    series="KXETH15M",
                    note=eth_spot_reason,
                )
            except Exception:
                pass
    eth_closes = []
    try:
        eth_closes = [c for _, c in candles_1m("ETH-USD")]
    except Exception as e:
        print(f"  ETH candles failed: {e}")
    eth_book_jobs = []
    for m in eth_markets:
        if eth_price is None:
            break
        eth_book_jobs.append((m["ticker"], "YES" if eth_price > m["target"] else "NO"))
    eth_books, eth_errs = prefetch_books(eth_book_jobs) if eth_book_jobs else ({}, {})
    for m in eth_markets:
        if eth_price is None:
            break
        key = (m["ticker"], "YES" if eth_price > m["target"] else "NO")
        if key in eth_errs:
            # BTC densifies prefetch book failures into scored reasons → CARD/brain;
            # ETH must not silent-continue (skip_board / CARD lie).
            eth_ob = f"orderbook failed ({eth_errs[key]})"
            print(f"--- ETH {m['ticker']} SKIP -> {eth_ob}")
            skips += 1
            skip_reasons.append(eth_ob)
            _densify_skip_brain(
                reasons=[eth_ob],
                ticker=str(m.get("ticker") or ""),
                side=str(key[1] or ""),
                note="ETH orderbook densify",
            )
            continue
        ev_early = evaluate_window(
            m, eth_price, eth_closes, dvol, False, edge_buf,
            book=eth_books.get(key), min_cushion=MIN_CUSHION_ETH,
        )
        ml = float(ev_early.get("min_left") or 0)
        regime = "unknown"
        if kalshi_parlay is not None:
            regime = kalshi_parlay.classify_regime(
                minutes_left=ml,
                model_p=ev_early.get("p"),
                z=ev_early.get("z"),
                cushion=ev_early.get("cushion"),
                min_cushion=MIN_CUSHION_ETH,
                min_z=MIN_Z,
                min_p=MIN_MODEL_PROB,
            )
        # Same evaluate→single safety as BTC: don't re-veto fee-clear early ETH.
        if (
            regime == "volatile_hold"
            and not (ev_early.get("reasons") or [])
            and ml + 1e-12 >= float(MIN_MINUTES_LEFT)
        ):
            regime = "confident_early"
        print(f"--- ETH {m['ticker']} regime={regime} p={ev_early.get('p')} cushion={ev_early.get('cushion')}")
        if account.get("open"):
            marked = False
            for pos in account.get("open") or []:
                if not isinstance(pos, dict):
                    continue
                if m.get("ticker") and pos.get("ticker") != m.get("ticker"):
                    continue
                before = pos.get("last_mark")
                watch_open(
                    pos, ev_early.get("bid"), model_side=ev_early.get("side"),
                    model_p=ev_early.get("p"), market=m,
                )
                if pos.get("last_mark") != before:
                    marked = True
            if marked and not IS_SHADOW:
                save_account(account)
        if account.get("open") and ev_early.get("bid") is not None:
            eth_bid = ev_early["bid"]
            eth_tp_fee = fee_per_contract(eth_bid) if eth_bid else 0
            eth_tp_sold = manage_take_profits(
                account, eth_bid, eth_tp_fee, ticker=m.get("ticker"),
                market=m, model_side=ev_early.get("side"),
            )
            if eth_tp_sold:
                save_account(account)
                for line in eth_tp_sold:
                    print(f"  TAKE-PROFIT SELL: {line}")
        if (
            flip_on
            and account.get("open")
            and ev_early.get("side")
            and ev_early.get("bid") is not None
            and ev_early.get("p") is not None
        ):
            eth_flip_sold = manage_model_flips(
                account,
                ev_early["side"],
                ev_early["p"],
                ev_early["bid"],
                fee_per_contract(ev_early["bid"]) if ev_early.get("bid") else 0,
                flip_delta,
                ticker=m.get("ticker"),
                market=m,
            )
            if eth_flip_sold:
                save_account(account)
                for line in eth_flip_sold:
                    print(f"  MODEL-FLIP SELL: {line}")
        if kalshi_history is not None:
            try:
                kalshi_history.record_snapshot(
                    DESK_ROOT, series="KXETH15M", ticker=m["ticker"], spot=eth_price,
                    target=m.get("target"), side=ev_early.get("side"),
                    yes_ask=m.get("yes_ask"), no_ask=m.get("no_ask"),
                    model_p=ev_early.get("p"), minutes_left=ml, regime=regime,
                    note="; ".join(ev_early.get("reasons") or [])[:180],
                )
            except Exception:
                pass
        # Same fee-aware gates as BTC early singles (evaluate_window); not parlay-only.
        delay_eth = False
        btc_move = None
        delay_sec = 45
        if regime == "confident_early" and not (ev_early.get("reasons") or []):
            # Top25 #10 — ETH lead-lag study: if BTC just spiked, delay ETH early buy.
            try:
                if price and closes and len(closes) >= 2:
                    btc_move = abs(float(price) - float(closes[-1])) / max(float(closes[-1]), 1e-9) * 100.0
                if DESK_ROOT not in sys.path:
                    sys.path.insert(0, DESK_ROOT)
                import desk_top25 as _top25
                delay_sec = int(_top25.ETH_LEAD_LAG_DELAY_SEC)
                delay_eth = _top25.should_delay_eth(btc_move)
                _top25.record_eth_lead_lag(
                    DESK_ROOT,
                    btc_move_pct=btc_move,
                    eth_edge=ev_early.get("edge"),
                    delayed=delay_eth,
                    note=m["ticker"],
                )
            except Exception:
                delay_eth = False
        if eth_early_should_buy(regime, ev_early.get("reasons"), delay_eth=delay_eth):
            tp = min(round(float(ev_early["ask"]) + TAKE_PROFIT_ADD, 2), TAKE_PROFIT_CAP)
            print(
                f"  SIGNAL: BUY ETH {ev_early['side']} on {m['ticker']} at <= {ev_early['ask']:.2f} "
                f"(fee {ev_early['fee']:.2f}). Take-profit {tp:.2f} will paper-sell."
            )
            sentence = paper_buy(
                account, m["ticker"], ev_early["side"], ev_early["ask"], ev_early["fee"],
                ev_early["p"], m["close_time"], True, edge=ev_early.get("edge"),
                series="KXETH15M",
                vol_kwargs={
                    "cushion": ev_early.get("cushion"), "sigma": ev_early.get("sigma"),
                    "spread": ev_early.get("spread"), "minutes_left": ev_early.get("min_left"),
                    "ask": ev_early.get("ask"), "ticker": m["ticker"], "series": "KXETH15M",
                    "calendar_loaded": bool(ev_early.get("calendar_loaded")),
                },
            )
            print(f"  ETH early: {sentence}")
            if "Paper buy" in sentence and "No paper buy" not in sentence:
                buys += 1
                last_sentence = sentence
                if kalshi_history is not None:
                    try:
                        kalshi_history.clear_hold(DESK_ROOT, str(m.get("ticker") or ""))
                    except Exception:
                        pass
                if desk_brain and not IS_SHADOW:
                    try:
                        note = desk_brain.explain_buy(
                            "btc15m", ev_early["side"], m["ticker"], ev_early.get("edge"),
                            ev_early.get("p"), ev_early.get("depth"),
                        )
                        print(f"  BRAIN: {note}")
                        desk_brain.record_decision(
                            DESK_ROOT, bot="btc15m", action="buy",
                            ticker=str(m.get("ticker") or ""), side=ev_early.get("side") or "",
                            edge=ev_early.get("edge"), confidence=ev_early.get("p"),
                            depth=ev_early.get("depth"), note=note,
                        )
                    except Exception:
                        pass
                try:
                    if DESK_ROOT not in sys.path:
                        sys.path.insert(0, DESK_ROOT)
                    import desk_top25 as _top25b
                    _top25b.remember_buy(DESK_ROOT)
                    import teller_memory
                    teller_memory.remember(
                        DESK_ROOT, "wins",
                        f"ETH early single {m['ticker']} cleared same gates as BTC.",
                        bot_id="btc15m", source="btc15m_signal",
                    )
                except Exception:
                    pass
            else:
                skips += 1
                eth_block = str(sentence)[:160] or "ETH desk/account blocked fill"
                skip_reasons.append(eth_block)
                print(f"  ETH desk/account blocked fill: {sentence}")
                _densify_skip_brain(
                    reasons=[eth_block],
                    ticker=str(m.get("ticker") or ""),
                    side=str(ev_early.get("side") or ""),
                    edge=ev_early.get("edge"),
                    confidence=ev_early.get("p"),
                    depth=ev_early.get("depth"),
                    note="ETH desk-block densify",
                )
        elif regime == "confident_early" and delay_eth:
            mv = f"{btc_move:.3f}%" if btc_move is not None else "?"
            delay_note = f"ETH early DELAYED ({delay_sec}s study) — BTC move {mv}"
            print(f"  {delay_note} (paper lead-lag)")
            skips += 1
            skip_reasons.append(delay_note)
            _densify_skip_brain(
                reasons=[delay_note],
                ticker=str(m.get("ticker") or ""),
                side=str(ev_early.get("side") or ""),
                edge=ev_early.get("edge"),
                confidence=ev_early.get("p"),
                depth=ev_early.get("depth"),
                note="ETH delay densify",
            )
        elif regime == "confident_early":
            reasons = list(ev_early.get("reasons") or []) or [regime]
            eth_skip = "; ".join(reasons)
            print("  ETH SIGNAL: SKIP -> " + eth_skip)
            skips += 1
            skip_reasons.append(eth_skip)
            _densify_skip_brain(
                reasons=reasons,
                ticker=str(m.get("ticker") or ""),
                side=str(ev_early.get("side") or ""),
                edge=ev_early.get("edge"),
                confidence=ev_early.get("p"),
                depth=ev_early.get("depth"),
                note="ETH evaluate densify",
            )
            # Near-miss densify under DESK_SHADOW too (soft z|p only).
            try:
                import desk_more
                z_val = ev_early.get("z")
                nm = desk_more.is_near_miss(
                    reasons=reasons,
                    z=z_val,
                    p=ev_early.get("p"),
                    edge=ev_early.get("edge"),
                    min_edge=float(edge_buf),
                )
                soft = [
                    s for s in (nm.get("soft") or [])
                    if s in ("z", "p")
                ]
                if nm.get("near_miss") and len(soft) == 1:
                    desk_more.record_near_miss(DESK_ROOT, {
                        "bot": "btc15m",
                        "ticker": m.get("ticker"),
                        "side": ev_early.get("side"),
                        "soft": soft,
                        "z": z_val,
                        "p": ev_early.get("p"),
                        "edge": ev_early.get("edge"),
                        "ask": ev_early.get("ask"),
                        "note": f"ETH {nm.get('note')}",
                        "series": "KXETH15M",
                        "is_shadow": bool(IS_SHADOW),
                    })
                    print(f"  ETH NEAR-MISS shadow logged ({nm.get('note')})")
            except Exception:
                pass
        elif regime == "parlay_window":
            late = evaluate_window(
                m, eth_price, eth_closes, dvol, False, edge_buf,
                book=eth_books.get(key), min_minutes_left=PARLAY_MIN_MIN, min_cushion=MIN_CUSHION_ETH,
            )
            late_reasons = late_scan_reasons(late.get("reasons"))
            if not late_reasons and late.get("ask") is not None:
                parlay_legs.append({
                    "ticker": late["ticker"], "side": late["side"], "ask": late["ask"],
                    "fee": late["fee"], "fair": late.get("p"),
                    "close_time": m["close_time"].isoformat(),
                    "series": "KXETH15M", "edge": late.get("edge"),
                    "confidence": late.get("p"), "depth": late.get("depth"),
                })
                print("  ETH PARLAY-CANDIDATE")
            else:
                skips += 1
                eth_parlay = "; ".join(late_reasons or ["ETH parlay_window skip"])
                skip_reasons.append(eth_parlay)
                _densify_skip_brain(
                    reasons=[eth_parlay],
                    ticker=str(m.get("ticker") or ""),
                    side=str(ev_early.get("side") or late.get("side") or ""),
                    edge=late.get("edge") if isinstance(late, dict) else ev_early.get("edge"),
                    confidence=(
                        late.get("p") if isinstance(late, dict) else None
                    ) or ev_early.get("p"),
                    note="ETH parlay densify",
                )
        elif regime == "volatile_hold":
            if kalshi_history is not None:
                try:
                    kalshi_history.mark_hold(
                        DESK_ROOT, m["ticker"], str(ev_early.get("side") or ""),
                        "ETH volatile — hold for ≤5m parlay", ml,
                    )
                except Exception:
                    pass
            skips += 1
            eth_vol = "ETH volatile — hold for ≤5m parlay"
            skip_reasons.append(eth_vol)
            _densify_skip_brain(
                reasons=[eth_vol],
                ticker=str(m.get("ticker") or ""),
                side=str(ev_early.get("side") or ""),
                edge=ev_early.get("edge"),
                confidence=ev_early.get("p"),
                depth=ev_early.get("depth"),
                note="ETH volatile densify",
            )
        else:
            skips += 1
            eth_else = str(regime or "ETH skip")
            skip_reasons.append(eth_else)
            _densify_skip_brain(
                reasons=[eth_else],
                ticker=str(m.get("ticker") or ""),
                side=str(ev_early.get("side") or ""),
                edge=ev_early.get("edge"),
                confidence=ev_early.get("p"),
                note="ETH regime densify",
            )

    # Open paper parlay when ≥2 fee-aware legs ready in the ≤5m window.
    if (not IS_SHADOW) and kalshi_parlay is not None and len(parlay_legs) >= 2:
        # Prefer one BTC + one ETH leg when available.
        btc_leg = next((x for x in parlay_legs if x.get("series") == "KXBTC15M"), None)
        eth_leg = next((x for x in parlay_legs if x.get("series") == "KXETH15M"), None)
        legs = [btc_leg, eth_leg] if btc_leg and eth_leg else parlay_legs[:2]
        if all(legs) and os.environ.get("DESK_BLOCK_ENTRIES") != "1":
            path = kalshi_parlay.parlay_path(DESK_ROOT, os.path.dirname(ACCOUNT))
            # Stake from desk Kelly-lite on the weaker confidence.
            conf = min(float(legs[0].get("confidence") or 0), float(legs[1].get("confidence") or 0))
            edge = min(float(legs[0].get("edge") or 0), float(legs[1].get("edge") or 0))
            try:
                desk = _desk()
                cfg = desk.load_settings(DESK_ROOT)
                stake = desk.stake_dollars_for(
                    "btc15m", conf, edge=edge, cfg=cfg, open_risk_used=0.0,
                    ask=legs[0]["ask"], root=DESK_ROOT,
                )
            except Exception:
                stake = 20.0
            cash = float(account.get("cash") or 0)
            stake = min(float(stake), cash)
            # Phase 3: joint EV + same-direction crypto corr haircut before open.
            try:
                import desk_phase3
                sim = desk_phase3.simulate_parlay(
                    DESK_ROOT, legs,
                    note="≤5m paper parlay pre-open sim",
                )
                if not desk_phase3.should_open_parlay(sim, min_ev=0.0):
                    print(
                        f"  PARLAY SKIP: joint EV {sim.get('ev')} "
                        f"(corr haircut {sim.get('corr_haircut')}) — fee-aware combo gate"
                    )
                    row = None
                else:
                    row = kalshi_parlay.open_paper_parlay(
                        path, legs, stake_dollars=stake,
                        note=(
                            "≤5m paper parlay after volatile hold "
                            f"(joint_ev={sim.get('ev')})"
                        ),
                    )
            except Exception as exc:
                print(f"  PARLAY Phase3 sim failed ({exc}); opening without joint gate")
                row = kalshi_parlay.open_paper_parlay(
                    path, legs, stake_dollars=stake,
                    note="≤5m paper parlay after volatile hold (BTC+ETH or dual legs)",
                )
            if row:
                # Deduct combined stake from paper cash; attach legs as open positions tagged parlay.
                account["cash"] = round(cash - float(row["stake"]), 2)
                for leg in row["legs"]:
                    account.setdefault("open", []).append({
                        "ticker": leg["ticker"],
                        "team": leg["ticker"],
                        "game": f"parlay {row['parlay_id']}",
                        "side": leg["side"],
                        "contracts": leg["contracts"],
                        "ask": leg["ask"],
                        "fee": leg["fee"],
                        "cost": leg["cost"],
                        "risk": leg["cost"],
                        "reward": round(leg["contracts"] * 1.0 - leg["cost"], 2),
                        "fair_at_entry": leg.get("fair_at_entry"),
                        "opened": row["opened"],
                        "close_time": leg.get("close_time") or "",
                        "fill_id": f"{row['parlay_id']}|{leg['ticker']}",
                        "parlay_id": row["parlay_id"],
                        "paper_only": True,
                        "price_source": KALSHI,
                        "why": "Paper parlay leg. Volatile early → ≤5m combo.",
                    })
                save_account(account)
                parlays += 1
                buys += 1
                last_sentence = (
                    f"Checked crypto Kalshi markets. Paper parlay {row['parlay_id']} "
                    f"({len(row['legs'])} legs, stake ${row['stake']:.2f})."
                )
                print(f"PARLAY OPEN: {last_sentence}")
                for leg in legs:
                    if kalshi_history is not None:
                        try:
                            kalshi_history.clear_hold(DESK_ROOT, leg["ticker"])
                        except Exception:
                            pass

    elapsed = time.perf_counter() - t0
    if not IS_SHADOW:
        try:
            import desk_roi_plan
            # #503 stage densify: spot / book walls (plus existing evaluate/exit/buy).
            desk_roi_plan.record_latency(
                DESK_ROOT, bot="btc15m", seconds=spot_secs,
                note="btc15m spot", stage="spot",
            )
            desk_roi_plan.record_latency(
                DESK_ROOT, bot="btc15m", seconds=book_secs,
                note=f"btc15m book n={len(book_jobs)}", stage="book",
            )
            desk_roi_plan.record_latency(
                DESK_ROOT, bot="btc15m", seconds=elapsed,
                note="btc15m evaluate", stage="evaluate",
            )
            desk_roi_plan.record_latency(
                DESK_ROOT, bot="btc15m", seconds=elapsed,
                note=f"btc15m buys={buys}", stage="buy",
            )
            desk_roi_plan.record_latency(
                DESK_ROOT, bot="btc15m", seconds=elapsed,
                note="btc15m exit/manage", stage="exit",
            )
            desk_roi_plan.record_latency(
                DESK_ROOT, bot="btc15m", seconds=elapsed,
                note="btc15m check", stage="loop",
            )
            if not markets and not eth_markets:
                for series in ("KXBTC15M", "KXETH15M"):
                    desk_roi_plan.record_empty_card(
                        DESK_ROOT,
                        bot="btc15m",
                        seconds=elapsed,
                        markets_n=0,
                        series=series,
                        note="no open BTC/ETH 15m windows",
                    )
        except Exception:
            pass
    print(
        f"Windows scored: BTC {len(markets)} ETH {len(eth_markets)}  "
        f"paper buys: {buys}  parlays: {parlays}  skips/blocks: {skips}"
    )
    print("(Paper only. Nothing was ordered.)")
    return _card(_card_sentence(
        buys=buys,
        markets_n=len(markets),
        eth_markets_n=len(eth_markets),
        last_sentence=last_sentence,
        skip_reasons=skip_reasons,
    ))


if __name__ == "__main__":
    sys.exit(main())
