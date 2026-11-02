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
MIN_MODEL_PROB = 0.80        # margin goal: model Φ(z) must be ≥ 80%
MIN_CUSHION_USD = 40         # BTC cushion floor (was $50 — still fee-aware with venue edge)
MIN_CUSHION_ETH = 2.0        # ETH 15m cushion (KXETH15M)
MIN_Z = 0.65                 # cushion / sigma
MIN_Z_COINBASE_ONLY = 0.80   # stricter if only Coinbase spot worked
ASK_MIN, ASK_MAX = 0.75, 0.90  # only buy high-probability priced contracts
MAX_SPREAD = 0.03
MIN_DEPTH = 5                # contracts offered at or below the ask
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


def _edge_buffer():
    """Venue kalshi_btc15m from desk, or shadow overlay, else local EDGE_BUFFER."""
    shadow = os.environ.get("DESK_SHADOW_VENUE_EDGE")
    if shadow not in (None, ""):
        try:
            return float(shadow)
        except (TypeError, ValueError):
            pass
    try:
        desk = _desk()
        cfg = desk.load_settings(DESK_ROOT)
        return float(desk.venue_min_edge("kalshi_btc15m", cfg))
    except Exception:
        return float(EDGE_BUFFER)


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
        try:
            desk = _desk()
            desk.record_learning(DESK_ROOT, {
                "result": "hit" if pnl > 0 else "miss",
                "market": "BTC",
                "prob": pos.get("fair_at_entry"),
                "stake": pos.get("risk") if pos.get("risk") is not None else pos.get("cost"),
                "fill_id": pos.get("fill_id") or "",
                "at": pos["closed"],
            })
        except Exception:
            pass
    state["open"] = still


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
    })
    state.setdefault("closed", []).append(closed)
    if not IS_SHADOW:
        try:
            desk = _desk()
            desk.record_learning(DESK_ROOT, {
                "result": "hit" if pnl > 0 else "miss",
                "market": "BTC",
                "prob": pos.get("fair_at_entry"),
                "stake": pos.get("risk") if pos.get("risk") is not None else pos.get("cost"),
                "fill_id": pos.get("fill_id") or "",
                "at": closed["closed"],
            })
        except Exception:
            pass
    return pnl


def manage_model_flips(state, side_now, prob_now, bid, fee, delta, ticker=None):
    """Exit open BTC paper when the live model flips against the held side.

    When `ticker` is set, only positions on that market are evaluated (multi-window runs).
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
        if flip and bid is not None and float(bid) > 0:
            pnl = paper_sell(state, pos, bid, fee, reason)
            sold.append(f"{pos.get('ticker')} {reason} pnl {pnl:+.2f}")
        else:
            still.append(pos)
    state["open"] = still
    return sold


def paper_buy(state, ticker, side, ask, fee, prob, close_time, signal_buy, edge=None, vol_kwargs=None):
    """Paper fill only when the signal cleared the edge after fees. No order is sent."""
    none_msg = "Checked all open BTC 15-minute markets. No paper buy."
    if ask is None or not (0.05 <= float(ask) <= 0.95):
        return none_msg
    if any(isinstance(pos, dict) and pos.get("ticker") == ticker for pos in state.get("open") or []):
        return none_msg
    skip = ""
    try:
        desk = _desk()
        skip = desk.learning_skip(desk.load_learning(DESK_ROOT), "BTC", desk.prob_bucket(prob))
    except Exception:
        pass
    if skip:
        return skip
    if os.environ.get("DESK_BLOCK_ENTRIES") == "1" and not IS_SHADOW:
        return "Desk entry_gate blocked a new paper buy. Settles still run."
    if not signal_buy:
        return none_msg
    edge_val = edge
    if edge_val is None and prob is not None and ask is not None:
        edge_val = float(prob) - float(ask) - float(fee or 0)
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
    try:
        desk = _desk()
        cfg = desk.load_settings(DESK_ROOT)
        vk = dict(vol_kwargs or {})
        vk.setdefault("ask", ask)
        vk.setdefault("ticker", ticker)
        stake, adapt_plan = desk.stake_dollars_for(
            "btc15m", prob, edge=edge_val, cfg=cfg, open_risk_used=open_risk, ask=ask,
            root=DESK_ROOT, vol_kwargs=vk, return_plan=True,
        )
        contracts = desk.contracts_for_stake(per, stake)
    except Exception:
        stake = 20.0
        adapt_plan = {}
        contracts = int(stake // per) if per > 0 else 0
    if contracts < 1:
        return none_msg
    cost = round(contracts * per, 2)
    cash = float(state.get("cash") or 0)
    if cost > cash + 1e-9 or len(state.get("open") or []) >= 12:
        return none_msg
    state["cash"] = round(cash - cost, 2)
    reward = round(contracts * 1.0 - cost, 2)
    why = "Paper buy. The BTC 15-minute signal cleared its checks on this window."
    opened = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
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
        "fill_id": f"{ticker}|{opened}",
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
        "vol_regime": vol.get("regime"),
        "vol_score": vol.get("score"),
        "history_n": perf.get("n"),
        "history_hit": perf.get("hit_rate"),
        "history_ci_low": perf.get("hit_ci_low"),
        "fill_tax": 0.01,
    })
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


def get_json(url, headers=None, tries=3):
    hit = _cached(url)
    if hit is not None:
        return hit
    err = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=headers or UA)
            with urllib.request.urlopen(req, timeout=15) as r:
                body = json.load(r)
            _store(url, body)
            return body
        except Exception as e:  # network hiccup -> retry, then mark it failed
            err = e
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
            kalshi_history.record_snapshot(
                root,
                series="KXBTCD",
                ticker=str(m.get("ticker") or ""),
                spot=float(btc_spot),
                target=strike,
                side="YES" if btc_spot >= strike else "NO",
                yes_ask=yes_ask,
                no_ask=no_ask,
                model_p=None,
                minutes_left=min_left,
                regime="ladder_watch",
                note=str(events[0].get("title") or "")[:120],
                extra={"event": event_ticker},
            )
            n += 1
            if n >= 24:
                break
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
    d = get_json("https://nfs.faireconomy.media/ff_calendar_thisweek.json", headers=UA)
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
    cheap = []
    if min_left < time_floor:
        cheap.append(f"only {min_left:.1f} min left (< {time_floor:g})")
    if cushion < cush_floor:
        cheap.append(f"cushion ${cushion:.2f} < ${cush_floor:g}")
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
    zmin = MIN_Z_COINBASE_ONLY if coinbase_only else MIN_Z
    if p < MIN_MODEL_PROB:
        reasons.append(f"p {p:.3f} < safer floor {MIN_MODEL_PROB:.2f}")
    if p < need:
        reasons.append(f"p {p:.3f} < ask+fee+{edge_buf:.2f} = {need:.3f}")
    if z < zmin:
        reasons.append(f"z {z:.2f} < {zmin}")
    if not (ASK_MIN <= ask <= ASK_MAX):
        reasons.append(f"ask {ask:.2f} outside {ASK_MIN:.2f}-{ASK_MAX:.2f}")
    if spread > MAX_SPREAD + 1e-9:
        reasons.append(f"spread {spread:.2f} > {MAX_SPREAD:.2f}")
    if depth < MIN_DEPTH:
        reasons.append(f"only {depth:.0f} contracts at/below ask (< {MIN_DEPTH})")
    if toward is None:
        reasons.append("candle trend unknown")
    elif toward:
        reasons.append("last 5 candles moving toward target")
    if news is None:
        reasons.append("news calendar unavailable")
    elif news:
        reasons.append("USD high-impact news near this block")

    out.update({
        "reasons": reasons,
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
        "cushion": cushion,
        "z": z,
        "need": need,
        "spread": spread,
        "dvol": dvol,
    })
    return out


def main():
    now = dt.datetime.now(dt.timezone.utc)
    account = load_account()
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

    spots = spot_prices()
    if not spots and not eth_markets:
        print("SKIP: no BTC spot and no ETH windows.")
        return _card("Checked all open BTC 15-minute markets. No paper buy.")
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

    if not IS_SHADOW:
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
    books, book_errs = prefetch_books(book_jobs) if book_jobs else ({}, {})

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
    last_sentence = "Checked all open BTC 15-minute markets. No paper buy."

    for ev in ranked:
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

        if flip_on and account.get("open") and ev.get("side") and ev.get("bid") is not None and ev.get("p") is not None:
            sold = manage_model_flips(
                account,
                ev["side"],
                ev["p"],
                ev["bid"],
                fee_per_contract(ev["bid"]) if ev["bid"] else 0,
                flip_delta,
                ticker=ev.get("ticker"),
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
        print(f"  regime: {regime}")
        if kalshi_history is not None and not IS_SHADOW:
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

        # Volatile → hold for ≤5m parlay (even if some gates look soft).
        if regime == "volatile_hold":
            hold_reason = "volatile — holding for ≤5m parlay window"
            if hold_reason not in reasons:
                reasons.append(hold_reason)
            if kalshi_history is not None and not IS_SHADOW and ev.get("side"):
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
            late_reasons = [r for r in (late.get("reasons") or []) if "min left" not in r]
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
                print("  SIGNAL: SKIP -> " + "; ".join(reasons or [regime]))
                skips += 1
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
                    # Phase 1 shadow near-miss: log only (does not eat desk open-risk).
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
                        if nm.get("near_miss"):
                            desk_more.record_near_miss(DESK_ROOT, {
                                "bot": "btc15m",
                                "ticker": ev.get("ticker"),
                                "side": ev.get("side"),
                                "soft": nm.get("soft"),
                                "z": z_val,
                                "p": ev.get("p"),
                                "edge": ev.get("edge"),
                                "note": nm.get("note"),
                            })
                            print(f"  NEAR-MISS shadow logged ({nm.get('note')})")
                    except Exception:
                        pass
                print()
                continue

        # Confident early (≥10m) and clears guidelines → single paper buy now.
        tp = min(round(ev["ask"] + TAKE_PROFIT_ADD, 2), TAKE_PROFIT_CAP)
        print(
            f"  SIGNAL: BUY {ev['side']} on {ev['ticker']} at <= {ev['ask']:.2f} "
            f"(fee {ev['fee']:.2f}). Suggested take-profit {tp:.2f} (fill + 0.15, max 0.99)."
        )
        last_sentence = paper_buy(
            account, ev["ticker"], ev["side"], ev["ask"], ev["fee"], ev["p"],
            ev.get("close_time") or m.get("close_time"), True, edge=ev.get("edge"),
            vol_kwargs={
                "cushion": ev.get("cushion"), "sigma": ev.get("sigma"),
                "spread": ev.get("spread"), "minutes_left": ev.get("min_left"),
                "ask": ev.get("ask"), "ticker": ev.get("ticker"),
            },
        )
        if "Paper buy" in last_sentence and "No paper buy" not in last_sentence:
            buys += 1
            if kalshi_history is not None and not IS_SHADOW:
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
            print(f"  desk/account blocked fill: {last_sentence}")
        print()

    # ---- ETH 15m: history + optional late parlay leg (same fee-aware gates) ----
    eth_spots = eth_spot_prices()
    eth_price = statistics.mean(eth_spots.values()) if eth_spots else None
    if eth_price is not None:
        print(f"\nETH spot avg ${eth_price:,.2f}  open KXETH15M windows: {len(eth_markets)}")
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
        print(f"--- ETH {m['ticker']} regime={regime} p={ev_early.get('p')} cushion={ev_early.get('cushion')}")
        if kalshi_history is not None and not IS_SHADOW:
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
        if regime == "confident_early" and not (ev_early.get("reasons") or []):
            sentence = paper_buy(
                account, m["ticker"], ev_early["side"], ev_early["ask"], ev_early["fee"],
                ev_early["p"], m["close_time"], True, edge=ev_early.get("edge"),
                vol_kwargs={
                    "cushion": ev_early.get("cushion"), "sigma": ev_early.get("sigma"),
                    "spread": ev_early.get("spread"), "minutes_left": ev_early.get("min_left"),
                    "ask": ev_early.get("ask"), "ticker": m["ticker"],
                },
            )
            print(f"  ETH early: {sentence}")
            if "Paper buy" in sentence and "No paper buy" not in sentence:
                buys += 1
                last_sentence = sentence
        elif regime == "parlay_window":
            late = evaluate_window(
                m, eth_price, eth_closes, dvol, False, edge_buf,
                book=eth_books.get(key), min_minutes_left=PARLAY_MIN_MIN, min_cushion=MIN_CUSHION_ETH,
            )
            late_reasons = [r for r in (late.get("reasons") or []) if "min left" not in r]
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
        elif regime == "volatile_hold":
            if kalshi_history is not None and not IS_SHADOW:
                try:
                    kalshi_history.mark_hold(
                        DESK_ROOT, m["ticker"], str(ev_early.get("side") or ""),
                        "ETH volatile — hold for ≤5m parlay", ml,
                    )
                except Exception:
                    pass
            skips += 1
        else:
            skips += 1

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

    print(
        f"Windows scored: BTC {len(markets)} ETH {len(eth_markets)}  "
        f"paper buys: {buys}  parlays: {parlays}  skips/blocks: {skips}"
    )
    print("(Paper only. Nothing was ordered.)")
    if buys:
        return _card(last_sentence if "parlay" in last_sentence.lower() else (
            f"Checked {len(markets)} open BTC 15-minute markets. "
            f"{buys} paper buy{'s' if buys != 1 else ''}."
        ))
    if not markets and eth_markets:
        return _card("Checked ETH/BTC crypto Kalshi markets. No paper buy.")
    return _card(last_sentence if last_sentence else "Checked all open BTC 15-minute markets. No paper buy.")


if __name__ == "__main__":
    sys.exit(main())
