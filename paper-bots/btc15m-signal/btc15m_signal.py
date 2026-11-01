#!/usr/bin/env python3
"""
btc15m_signal.py - SIGNAL ONLY helper for Kalshi's "BTC price up in next 15 mins?" markets (KXBTC15M).

What it does (one run):
  1. Reads the open KXBTC15M market from Kalshi's free public API (target = floor_strike,
     yes/no bid/ask, close time) and its order book.
  2. Averages BTC spot from Coinbase, Kraken Futures (PF_XBTUSD) and Bitstamp.
  3. Estimates how far BTC can move before the close (sigma) from Deribit's DVOL and from the
     last 60 one-minute Coinbase candles, and uses the larger one.
  4. Picks the side BTC is currently on (YES if price > target, else NO), turns the cushion into
     a probability p = Phi(cushion / sigma), and compares p with the ask + Kalshi fee.
  5. Checks the US high-impact news calendar (ForexFactory) and prints BUY or SKIP with the reason.

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
MIN_MINUTES_LEFT = 10        # need at least 10 minutes before close
EDGE_BUFFER = 0.05           # p must beat ask + fee by 5 points
MIN_CUSHION_USD = 40         # BTC must be at least $40 away from the target
MIN_Z = 0.5                  # cushion / sigma
MIN_Z_COINBASE_ONLY = 0.6    # stricter if only Coinbase spot worked
ASK_MIN, ASK_MAX = 0.65, 0.85
MAX_SPREAD = 0.03
MIN_DEPTH = 5                # contracts offered at or below the ask
NEWS_WINDOW_MIN = 30         # USD high-impact event within 30 min of the block -> skip
TAKE_PROFIT_ADD, TAKE_PROFIT_CAP = 0.15, 0.99
DVOL_FAIL_MULT = 1.2         # if DVOL fails: use realized sigma * 1.2


HERE = os.path.dirname(os.path.abspath(__file__))
DESK_ROOT = os.path.dirname(HERE)
ACCOUNT = os.path.join(HERE, "paper_account.json")
_CACHE = os.path.join(HERE, "quote_cache.json")
PAPER_CASH = 100.0


def load_account():
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


def save_account(state):
    path = ACCOUNT
    if os.path.islink(path):
        path = os.path.realpath(path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
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


def paper_buy(state, ticker, side, ask, fee, prob, close_time, signal_buy):
    """Paper fill only when the signal cleared the edge after fees. No order is sent."""
    if ask is None or not (0.05 <= float(ask) <= 0.95):
        return "Checked the BTC 15-minute market. No paper buy."
    if any(isinstance(pos, dict) and pos.get("ticker") == ticker for pos in state.get("open") or []):
        return "Checked the BTC 15-minute market. No paper buy."
    skip = ""
    try:
        desk = _desk()
        skip = desk.learning_skip(desk.load_learning(DESK_ROOT), "BTC", desk.prob_bucket(prob))
    except Exception:
        pass
    if skip:
        return skip
    if not signal_buy:
        return "Checked the BTC 15-minute market. No paper buy."
    per = float(ask) + float(fee or 0)
    try:
        desk = _desk()
        cfg = desk.load_settings(DESK_ROOT)
        stake = desk.paper_stake_dollars(prob, cfg)
        contracts = desk.contracts_for_stake(per, stake)
    except Exception:
        stake = 20.0
        contracts = int(stake // per) if per > 0 else 0
    if contracts < 1:
        return "Checked the BTC 15-minute market. No paper buy."
    cost = round(contracts * per, 2)
    cash = float(state.get("cash") or 0)
    if cost > cash + 1e-9 or len(state.get("open") or []) >= 12:
        return "Checked the BTC 15-minute market. No paper buy."
    state["cash"] = round(cash - cost, 2)
    reward = round(contracts * 1.0 - cost, 2)
    why = "Paper buy. The BTC 15-minute signal cleared its checks."
    opened = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
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
        "opened": opened,
        "close_time": close_time.isoformat() if hasattr(close_time, "isoformat") else str(close_time or ""),
        "fill_id": f"{ticker}|{opened}",
        "price_source": KALSHI,
        "price_at": opened,
        "paper_only": True,
    })
    save_account(state)
    return "Checked the BTC 15-minute market. Paper buy."


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
def kalshi_market():
    d = get_json(f"{KALSHI}/markets?series_ticker=KXBTC15M&status=open")
    now = dt.datetime.now(dt.timezone.utc)
    ms = [m for m in d.get("markets", []) if m.get("close_time") and parse_ts(m["close_time"]) > now]
    if not ms:
        return None
    m = min(ms, key=lambda m: parse_ts(m["close_time"]))
    return {
        "ticker": m["ticker"],
        "target": fnum(m.get("floor_strike")),
        "yes_bid": fnum(m.get("yes_bid_dollars")), "yes_ask": fnum(m.get("yes_ask_dollars")),
        "no_bid": fnum(m.get("no_bid_dollars")), "no_ask": fnum(m.get("no_ask_dollars")),
        "open_time": parse_ts(m["open_time"]) if m.get("open_time") else None,
        "close_time": parse_ts(m["close_time"]),
    }


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


def candles_1m():
    """Coinbase 1-minute candles, returned oldest -> newest as (time, close)."""
    rows = get_json("https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=60")
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
    print(f"BTC 15-min Kalshi paper check  (no real orders)  {now:%Y-%m-%d %H:%M:%S} UTC")
    print(f"Price source https://api.elections.kalshi.com/trade-api/v2 at {now:%Y-%m-%dT%H:%M:%SZ}\n")

    m = kalshi_market()
    if not m or m["target"] is None:
        print("SKIP: no open KXBTC15M market with a target right now (between blocks?). Try again in a minute.")
        return _card("Checked the BTC 15-minute market. No paper buy.")
    min_left = (m["close_time"] - now).total_seconds() / 60
    print(f"Market {m['ticker']}  target ${m['target']:,.2f}  closes {m['close_time']:%H:%M} UTC "
          f"({min_left:.1f} min left)")
    print(f"  listing quotes (can lag): YES bid/ask {m['yes_bid']}/{m['yes_ask']}   NO bid/ask {m['no_bid']}/{m['no_ask']}")

    spots = spot_prices()
    if not spots:
        print("SKIP: no BTC spot price available from any source.")
        return _card("Checked the BTC 15-minute market. No paper buy.")
    price = statistics.mean(spots.values())
    print("Spot: " + ", ".join(f"{k} ${v:,.2f}" for k, v in spots.items()) + f"  -> avg ${price:,.2f}")
    coinbase_only = list(spots) == ["coinbase"]

    reasons = []
    # sigma
    realized = None
    closes = []
    try:
        closes = [c for _, c in candles_1m()]
        last = closes[-61:]
        rets = [math.log(b / a) for a, b in zip(last, last[1:])]
        if len(rets) >= 10:
            realized = statistics.stdev(rets) * price * math.sqrt(max(min_left, 0))
    except Exception as e:
        print(f"  candles failed: {e}")
    dvol = None
    try:
        dvol = dvol_latest()
    except Exception as e:
        print(f"  DVOL failed: {e}")
    sig_dvol = price * dvol / 100 * math.sqrt(max(min_left, 0) / 525600) if dvol else None
    if sig_dvol is not None and realized is not None:
        sigma = max(sig_dvol, realized)
    elif sig_dvol is not None:
        sigma = sig_dvol
    elif realized is not None:
        sigma = realized * DVOL_FAIL_MULT
    else:
        print("SKIP: could not compute sigma (no DVOL and no candles).")
        return _card("Checked the BTC 15-minute market. No paper buy.")
    print(f"Sigma: DVOL {dvol if dvol else 'n/a'} -> ${sig_dvol:,.2f}" if sig_dvol else "Sigma: DVOL n/a", end="")
    print(f" | realized ${realized:,.2f}" if realized is not None else " | realized n/a", end="")
    print(f" | used ${sigma:,.2f}")

    side = "YES" if price > m["target"] else "NO"
    cushion = abs(price - m["target"])
    z = cushion / sigma if sigma > 0 else 0
    p = phi(z)
    ask = m["yes_ask"] if side == "YES" else m["no_ask"]
    bid = m["yes_bid"] if side == "YES" else m["no_bid"]
    depth = 0.0
    try:  # the order book is fresher than the market listing; prefer it
        b_bid, b_ask, depth = book_for_side(m["ticker"], side)
        if b_ask is not None:
            ask = b_ask
        if b_bid is not None:
            bid = b_bid
    except Exception as e:
        print(f"  orderbook failed: {e}")
    if ask is None or bid is None:
        print("SKIP: missing bid/ask for the chosen side.")
        return _card("Checked the BTC 15-minute market. No paper buy.")
    fee = fee_per_contract(ask)
    spread = ask - bid
    need = ask + fee + EDGE_BUFFER
    print(f"Side {side}: cushion ${cushion:,.2f}  z {z:.2f}  p {p:.3f}  ask {ask:.2f}  fee {fee:.2f}  "
          f"need p >= {need:.3f}  spread {spread:.2f}  (from order book)")

    print(f"Depth offered at or below ask: {depth:,.0f} contracts")

    # last 5 candles moving toward target?
    toward = None
    if len(closes) >= 6:
        move = closes[-1] - closes[-6]
        toward = (move < 0) if side == "YES" else (move > 0)
        print(f"Last 5 one-minute candles: {move:+,.2f} USD ({'TOWARD' if toward else 'away from'} target)")

    # news — fail closed: unknown calendar must not clear a BUY
    news = None
    try:
        start = m["open_time"] or (m["close_time"] - dt.timedelta(minutes=15))
        news = usd_high_impact_near(start, m["close_time"])
        print("News (USD High, +/-30 min): " + ("; ".join(news) if news else "none"))
    except Exception as e:
        print(f"  news calendar failed ({e}); skipping BUY until calendar loads")

    zmin = MIN_Z_COINBASE_ONLY if coinbase_only else MIN_Z
    if min_left < MIN_MINUTES_LEFT: reasons.append(f"only {min_left:.1f} min left (< {MIN_MINUTES_LEFT})")
    if p < need: reasons.append(f"p {p:.3f} < ask+fee+{EDGE_BUFFER:.2f} = {need:.3f}")
    if cushion < MIN_CUSHION_USD: reasons.append(f"cushion ${cushion:.2f} < ${MIN_CUSHION_USD}")
    if z < zmin: reasons.append(f"z {z:.2f} < {zmin}")
    if not (ASK_MIN <= ask <= ASK_MAX): reasons.append(f"ask {ask:.2f} outside {ASK_MIN:.2f}-{ASK_MAX:.2f}")
    if spread > MAX_SPREAD + 1e-9: reasons.append(f"spread {spread:.2f} > {MAX_SPREAD:.2f}")
    if depth < MIN_DEPTH: reasons.append(f"only {depth:.0f} contracts at/below ask (< {MIN_DEPTH})")
    if toward is None: reasons.append("candle trend unknown")
    elif toward: reasons.append("last 5 candles moving toward target")
    if news is None:
        reasons.append("news calendar unavailable")
    elif news:
        reasons.append("USD high-impact news near this block")

    print()
    signal_buy = not reasons
    if reasons:
        print("SIGNAL: SKIP -> " + "; ".join(reasons))
    else:
        tp = min(round(ask + TAKE_PROFIT_ADD, 2), TAKE_PROFIT_CAP)
        print(f"SIGNAL: BUY {side} on {m['ticker']} at <= {ask:.2f} (fee {fee:.2f}). "
              f"Suggested take-profit {tp:.2f} (fill + 0.15, max 0.99).")
    sentence = paper_buy(account, m["ticker"], side, ask, fee, p, m["close_time"], signal_buy)
    print("(Paper only. Nothing was ordered.)")
    return _card(sentence)


if __name__ == "__main__":
    sys.exit(main())
