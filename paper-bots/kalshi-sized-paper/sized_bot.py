#!/usr/bin/env python3
"""
PAPER-ONLY Kalshi bot with probability-based stake sizes.

One run reads public BTC quotes and the public Kalshi KXBTCD book, estimates
its own probability that a strike finishes in the money, and may record one
pretend position. It can also settle a position once Kalshi has published a result.

Real orders are not implemented. There is no API key, no wallet, no login,
and no live-trading flag. Every HTTP call in this file is a GET.

Usage:
  python3 sized_bot.py             # one paper check
  python3 sized_bot.py --self-test # offline checks of the stake and risk rules
  python3 sized_bot.py --reset     # delete state.json and paper_trades.md
"""
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, "config.json")))
CT = ZoneInfo(CFG["timezone"])
STATE = os.path.join(HERE, CFG["state_file"])
LOG = os.path.join(HERE, CFG["log_file"])
UA = {"User-Agent": "paper-bot/1.0 (read-only)"}
SETTLED_STATUSES = {"finalized", "determined", "settled", "closed", "inactive"}


def fee_per_contract(price, rate=None):
    """Kalshi taker fee for one contract, rounded up to the cent."""
    rate = CFG["taker_fee_rate"] if rate is None else rate
    return math.ceil(round(rate * price * (1.0 - price) * 100, 6)) / 100.0


def phi(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def model_yes_prob(spot, strike, strike_type, sigma):
    """Zero-drift normal probability that YES wins. Larger sigma pulls this toward 1/2."""
    if spot is None or strike is None or sigma is None or sigma <= 0:
        return None
    z = (float(spot) - float(strike)) / float(sigma)
    kind = strike_type or ""
    if kind in ("greater", "greater_or_equal"):
        return phi(z)
    if kind in ("less", "less_or_equal"):
        return phi(-z)
    return None


def stake_for_prob(p, cfg=None):
    """Dollar budget for a model probability. None when p is below the floor.

    At high_prob the budget is stake_high_min. At 1.0 it is stake_high_max.
    Between min_model_prob and high_prob the budget stays under stake_low_cap,
    starting at stake_low_min.
    """
    cfg = CFG if cfg is None else cfg
    if p is None:
        return None
    p = float(p)
    hi = float(cfg["high_prob"])
    if p + 1e-12 < float(cfg["min_model_prob"]):
        return None
    if p + 1e-12 >= hi:
        span = 1.0 - hi
        t = 0.0 if span <= 1e-12 else max(0.0, min(1.0, (p - hi) / span))
        raw = float(cfg["stake_high_min"]) + t * (float(cfg["stake_high_max"]) - float(cfg["stake_high_min"]))
        raw = min(float(cfg["stake_high_max"]), max(float(cfg["stake_high_min"]), raw))
        return round(raw, 2)
    lo_p = float(cfg["min_model_prob"])
    top = float(cfg["stake_low_cap"]) - 0.01
    floor = float(cfg["stake_low_min"])
    span = hi - lo_p
    t = 0.0 if span <= 1e-12 else max(0.0, min(1.0, (p - lo_p) / span))
    raw = min(top, max(floor, floor + t * (top - floor)))
    return round(raw, 2)


def size_ticket(budget, ask, fee, high, cash, open_risk, cfg=None):
    """Return (contracts, cost) inside the stake band, or (0, 0.0).

    Cost is contracts times (ask + fee). A high-probability ticket has to land
    between stake_high_min and stake_high_max. If whole contracts fall just
    short of the minimum, one extra contract is allowed when that total is
    still at most stake_high_max and still fits cash and open risk.
    A lower-probability ticket stays under stake_low_cap and does not round up.
    """
    cfg = CFG if cfg is None else cfg
    per = float(ask) + float(fee)
    if budget is None or per <= 0 or budget <= 0:
        return 0, 0.0
    room = min(float(cash), float(cfg["max_open_risk"]) - float(open_risk))
    if room <= 0:
        return 0, 0.0
    n = int(min(float(budget), room) / per + 1e-9)
    cost = round(n * per, 2)
    if high:
        lo = float(cfg["stake_high_min"])
        hi_lim = float(cfg["stake_high_max"])
        if cost < lo - 1e-9:
            n2 = n + 1
            cost2 = round(n2 * per, 2)
            if lo - 1e-9 <= cost2 <= hi_lim + 1e-9 and cost2 <= room + 1e-9:
                n, cost = n2, cost2
            else:
                return 0, 0.0
        if n < 1 or cost < lo - 1e-9 or cost > hi_lim + 1e-9 or cost > room + 1e-9:
            return 0, 0.0
        return n, cost
    cap = float(cfg["stake_low_cap"])
    if n < 1 or cost >= cap - 1e-9 or cost > room + 1e-9 or cost > float(budget) + 0.001:
        return 0, 0.0
    return n, cost


def open_risk_of(state):
    return round(sum(float(p["cost"]) for p in state.get("open", [])), 2)


def realized_pnl_on(state, day):
    total = 0.0
    key = str(day)
    for p in state.get("closed", []):
        if p.get("closed_day") == key:
            total += float(p.get("pnl") or 0)
    return round(total, 2)


def entry_block_reason(state, day, news_hits, cfg=None):
    """Why a new paper buy is refused, or None if a buy is still allowed."""
    cfg = CFG if cfg is None else cfg
    if cfg.get("paper_only") is not True:
        return "paper_only is not true"
    if state.get("halted"):
        return "bankroll halt is on (reset the paper account to clear it)"
    if float(state.get("cash", 0)) <= float(cfg["halt_below_bankroll"]) + 1e-9:
        return f"paper cash ${float(state.get('cash', 0)):.2f} is at or below the ${float(cfg['halt_below_bankroll']):.2f} halt"
    if news_hits:
        return "big-news day: " + "; ".join(news_hits)
    realized = realized_pnl_on(state, day)
    if realized <= -float(cfg["daily_loss_stop"]) + 1e-9:
        return f"daily loss stop hit (${realized:.2f}, stop -${float(cfg['daily_loss_stop']):.2f})"
    if len(state.get("open", [])) >= int(cfg["max_open_positions"]):
        return f"max open positions ({int(cfg['max_open_positions'])})"
    risk = open_risk_of(state)
    if risk >= float(cfg["max_open_risk"]) - 1e-9:
        return f"max open risk hit (${risk:.2f} of ${float(cfg['max_open_risk']):.2f})"
    return None


def news_hits_for_day(events, day, tz, country="USD", impacts=("High",)):
    """Titles of matching calendar rows whose local date is `day`."""
    want = set(impacts)
    hits = []
    seen = set()
    for ev in events or []:
        if ev.get("country") != country or ev.get("impact") not in want:
            continue
        try:
            when = datetime.fromisoformat(ev["date"]).astimezone(tz)
        except Exception:
            continue
        if when.date() != day:
            continue
        title = ev.get("title") or "high-impact event"
        if title not in seen:
            seen.add(title)
            hits.append(title)
    return hits


def combine_sigma(spot, minutes, dvol, realized_log_stdev, single_spot, cfg=None):
    """Dollar stdev until settlement. Uses the larger vol input, then a floor."""
    cfg = CFG if cfg is None else cfg
    if spot is None or spot <= 0 or minutes is None or minutes <= 0:
        return None
    parts = []
    if dvol is not None and dvol > 0:
        parts.append(float(spot) * (float(dvol) / 100.0) * math.sqrt(float(minutes) / 525600.0))
    if realized_log_stdev is not None and realized_log_stdev > 0:
        parts.append(float(realized_log_stdev) * float(spot) * math.sqrt(float(minutes)))
    if not parts:
        return None
    sigma = max(parts)
    if single_spot:
        sigma *= float(cfg["thin_spot_sigma_mult"])
    floor = float(spot) * float(cfg["min_sigma_frac_per_sqrt_hour"]) * math.sqrt(float(minutes) / 60.0)
    return max(sigma, floor)


def screen_sides(markets, spot, sigma, cfg=None):
    """Rank YES and NO sides by edge after the fee. Each row is a dict."""
    cfg = CFG if cfg is None else cfg
    rows = []
    for m in markets:
        p_yes = model_yes_prob(spot, m.get("strike"), m.get("strike_type"), sigma)
        if p_yes is None:
            continue
        for side, prob, bid, ask in (
            ("yes", p_yes, m.get("yes_bid"), m.get("yes_ask")),
            ("no", 1.0 - p_yes, m.get("no_bid"), m.get("no_ask")),
        ):
            row = {
                "ticker": m["ticker"], "event_ticker": m.get("event_ticker"),
                "strike": m.get("strike"), "strike_type": m.get("strike_type"),
                "close_time": m.get("close_time"), "side": side, "model_p": prob,
                "bid": bid, "ask": ask, "edge": None, "fee": None, "reason": None,
            }
            if ask is None or bid is None or ask <= 0 or ask >= 1:
                row["reason"] = "no usable ask"
            elif not (float(cfg["min_ask"]) - 1e-9 <= ask <= float(cfg["max_ask"]) + 1e-9):
                row["reason"] = "ask outside bounds"
            elif ask - bid > float(cfg["max_spread"]) + 1e-9:
                row["reason"] = "spread too wide"
            elif prob + 1e-12 < float(cfg["min_model_prob"]):
                row["reason"] = "model probability below floor"
            else:
                fee = fee_per_contract(ask, cfg["taker_fee_rate"])
                edge = prob - ask - fee
                row["fee"] = fee
                row["edge"] = edge
                if edge + 1e-12 < float(cfg["edge_buffer"]):
                    row["reason"] = "edge below buffer"
            rows.append(row)
    rows.sort(key=lambda r: (
        r["edge"] is not None and r["reason"] is None,
        r["edge"] if r["edge"] is not None else -9,
        r["model_p"],
    ), reverse=True)
    return rows


# ---------------- public GET only ----------------
def get_json(url, tries=3, pause=None):
    pause = CFG["request_pause_seconds"] if pause is None else pause
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=20) as resp:
                if pause:
                    time.sleep(pause)
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {}
            last = e
            time.sleep(1.0 + i)
        except Exception as e:
            last = e
            time.sleep(1.0 + i)
    raise RuntimeError(f"GET failed: {url} ({last})")


def dollars(x):
    if x in (None, ""):
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def now_ct():
    return datetime.now(CT)


def stamp(when=None):
    when = now_ct() if when is None else when
    return when.strftime("%Y-%m-%d %H:%M:%S CT")


def fetch_news():
    payload = get_json(CFG["news_url"], pause=0)
    if isinstance(payload, list):
        return payload
    return []


def fetch_spots():
    out = {}
    errors = []
    try:
        out["coinbase"] = float(get_json("https://api.coinbase.com/v2/prices/BTC-USD/spot", pause=0)["data"]["amount"])
    except Exception as e:
        errors.append(f"coinbase: {e}")
    try:
        out["kraken_futures"] = float(get_json(
            "https://futures.kraken.com/derivatives/api/v3/tickers/PF_XBTUSD", pause=0)["ticker"]["last"])
    except Exception as e:
        errors.append(f"kraken: {e}")
    try:
        out["bitstamp"] = float(get_json("https://www.bitstamp.net/api/v2/ticker/btcusd/", pause=0)["last"])
    except Exception as e:
        errors.append(f"bitstamp: {e}")
    return out, errors


def fetch_dvol():
    end = int(time.time() * 1000)
    start = end - 2 * 3600 * 1000
    url = ("https://www.deribit.com/api/v2/public/get_volatility_index_data"
           f"?currency=BTC&resolution=60&start_timestamp={start}&end_timestamp={end}")
    data = get_json(url, pause=0)["result"]["data"]
    return float(data[-1][4])


def fetch_realized_log_stdev():
    rows = get_json("https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=60", pause=0)
    closes = [float(r[4]) for r in sorted(rows, key=lambda r: r[0])]
    last = closes[-61:]
    rets = [math.log(b / a) for a, b in zip(last, last[1:]) if a > 0 and b > 0]
    if len(rets) < 30:
        return None
    mean = sum(rets) / len(rets)
    var = sum((x - mean) ** 2 for x in rets) / (len(rets) - 1)
    return math.sqrt(var)


def fetch_events():
    url = f"{CFG['api_base']}/events?series_ticker={CFG['series_ticker']}&status=open&limit=50"
    return get_json(url).get("events") or []


def choose_event(events, now):
    """Soonest event whose close is inside the configured minute window."""
    best = None
    for ev in events:
        raw = ev.get("strike_date")
        if not raw:
            continue
        try:
            when = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            continue
        minutes = (when - now).total_seconds() / 60.0
        if minutes < float(CFG["min_minutes_left"]) or minutes > float(CFG["max_minutes_left"]):
            continue
        if best is None or minutes < best[0]:
            best = (minutes, ev, when)
    return best


def fetch_markets(event_ticker):
    out, cursor = [], None
    while True:
        url = (f"{CFG['api_base']}/markets?series_ticker={CFG['series_ticker']}"
               f"&event_ticker={event_ticker}&status=open&limit=200")
        if cursor:
            url += "&cursor=" + cursor
        d = get_json(url)
        for m in d.get("markets") or []:
            out.append({
                "ticker": m.get("ticker"),
                "event_ticker": m.get("event_ticker") or event_ticker,
                "strike": dollars(m.get("floor_strike")),
                "strike_type": m.get("strike_type"),
                "yes_bid": dollars(m.get("yes_bid_dollars")),
                "yes_ask": dollars(m.get("yes_ask_dollars")),
                "no_bid": dollars(m.get("no_bid_dollars")),
                "no_ask": dollars(m.get("no_ask_dollars")),
                "close_time": m.get("close_time"),
                "status": m.get("status"),
                "result": m.get("result"),
            })
        cursor = d.get("cursor")
        if not cursor or not d.get("markets"):
            return out


def fetch_market(ticker):
    d = get_json(f"{CFG['api_base']}/markets/{ticker}")
    return d.get("market") or {}


def book_prices(ticker, side):
    """Bid/ask for one side from the public order book. Asks are implied by the other side's bids."""
    ob = get_json(f"{CFG['api_base']}/markets/{ticker}/orderbook").get("orderbook_fp") or {}
    yes = [(float(p), float(q)) for p, q in (ob.get("yes_dollars") or [])]
    no = [(float(p), float(q)) for p, q in (ob.get("no_dollars") or [])]
    own = yes if side == "yes" else no
    other = no if side == "yes" else yes
    if not other:
        return None, None
    ask = round(1.0 - max(p for p, _ in other), 4)
    bid = max((p for p, _ in own), default=None)
    if bid is not None:
        bid = round(bid, 4)
    return bid, ask


# ---------------- state + log ----------------
def fresh_state():
    return {"cash": float(CFG["starting_bankroll"]), "open": [], "closed": [], "runs": 0, "halted": False}


def load_state():
    if os.path.exists(STATE):
        with open(STATE) as f:
            state = json.load(f)
        state.setdefault("open", [])
        state.setdefault("closed", [])
        state.setdefault("halted", False)
        return state
    return fresh_state()


def save_state(state):
    with open(STATE, "w") as f:
        json.dump(state, f, indent=2)


def log_lines(lines):
    new = not os.path.exists(LOG)
    with open(LOG, "a") as f:
        if new:
            f.write("# Paper checks (PAPER ONLY — no real orders)\n")
        for line in lines:
            f.write(line + "\n")


def apply_halt(state):
    if float(state["cash"]) <= float(CFG["halt_below_bankroll"]) + 1e-9:
        state["halted"] = True


def settle_open(state, when):
    """Settle paper positions whose public market result is in. Returns log lines."""
    lines = []
    still = []
    for pos in state["open"]:
        try:
            market = fetch_market(pos["ticker"])
        except Exception as e:
            lines.append(f"- settle {pos['ticker']}: read failed ({e}); left open")
            still.append(pos)
            continue
        result = (market.get("result") or "").lower()
        status = (market.get("status") or "").lower()
        if result not in ("yes", "no") or status not in SETTLED_STATUSES:
            still.append(pos)
            continue
        won = result == pos["side"]
        payout = round(pos["contracts"] * (1.0 if won else 0.0), 2)
        pnl = round(payout - float(pos["cost"]), 2)
        state["cash"] = round(float(state["cash"]) + payout, 2)
        pos.update({
            "closed": stamp(when), "closed_day": str(when.date()), "result": result,
            "payout": payout, "pnl": pnl, "exit": "settled",
        })
        state["closed"].append(pos)
        lines.append(
            f"- **PAPER SETTLE** {pos['contracts']} {pos['side'].upper()} {pos['ticker']}: "
            f"{'WON' if won else 'LOST'} payout ${payout:.2f}, P&L ${pnl:+.2f}"
        )
    state["open"] = still
    apply_halt(state)
    return lines


def candidate_row(row, budget, action):
    edge = "" if row["edge"] is None else f"{row['edge'] * 100:+.1f} pts"
    fee = "" if row["fee"] is None else f"{row['fee']:.2f}"
    ask = "" if row["ask"] is None else f"{row['ask']:.2f}"
    stake = "" if budget is None else f"${budget:.2f}"
    return (f"| {row['ticker']} | {row['side']} | {row['model_p']:.1%} | {ask} | {fee} | "
            f"{edge} | {stake} | {action} |")


def try_fill(state, tradable, spot, sigma, when, lines, summary):
    """Confirm up to three listing candidates on the public order book and record one paper fill."""
    notes = []
    books = 0
    for row in tradable:
        if books >= 3:
            break
        budget = stake_for_prob(row["model_p"])
        high = row["model_p"] + 1e-12 >= float(CFG["high_prob"])
        n0, _cost0 = size_ticket(budget, row["ask"], row["fee"], high, state["cash"], open_risk_of(state))
        if n0 < 1:
            continue
        books += 1
        try:
            bid, ask = book_prices(row["ticker"], row["side"])
        except Exception as e:
            notes.append(f"{row['ticker']} book failed ({e})")
            continue
        if bid is None or ask is None:
            notes.append(f"{row['ticker']} book had no bid/ask")
            continue
        fee = fee_per_contract(ask)
        quote = {
            "ticker": row["ticker"], "event_ticker": row["event_ticker"],
            "strike": row["strike"], "strike_type": row["strike_type"],
            "close_time": row.get("close_time"),
            "yes_bid": bid if row["side"] == "yes" else None,
            "yes_ask": ask if row["side"] == "yes" else None,
            "no_bid": bid if row["side"] == "no" else None,
            "no_ask": ask if row["side"] == "no" else None,
        }
        fresh = [r for r in screen_sides([quote], spot, sigma) if r["side"] == row["side"]]
        if not fresh or fresh[0]["reason"]:
            why = fresh[0]["reason"] if fresh else "re-check failed"
            notes.append(f"{row['ticker']} {why}")
            continue
        n, cost = size_ticket(budget, ask, fee, high, state["cash"], open_risk_of(state))
        if n < 1:
            notes.append(f"{row['ticker']} stake band does not fit refreshed ask {ask:.2f}")
            continue
        filled = dict(row)
        filled["ask"], filled["bid"], filled["fee"] = ask, bid, fee
        open_position(state, filled, n, cost, budget, spot, sigma, when)
        summary["action"] = "PAPER BUY"
        summary["detail"] = f"{n} {row['side']} {row['ticker']} @ {ask:.2f} cost ${cost:.2f}"
        lines.append(
            f"- Action: **PAPER BUY** {n} {row['side'].upper()} {row['ticker']} "
            f"@ {ask:.2f} + fee {fee:.2f} = ${cost:.2f} "
            f"(model {row['model_p']:.1%}, budget ${budget:.2f})"
        )
        return state["open"][-1]
    if notes:
        lines.append("- Order book notes: " + "; ".join(notes))
    return None


def open_position(state, row, contracts, cost, budget, spot, sigma, when):
    state["cash"] = round(float(state["cash"]) - cost, 2)
    state["open"].append({
        "ticker": row["ticker"], "event_ticker": row["event_ticker"], "side": row["side"],
        "strike": row["strike"], "strike_type": row["strike_type"],
        "contracts": contracts, "entry_price": row["ask"], "entry_fee": row["fee"],
        "cost": cost, "model_p": round(row["model_p"], 4), "stake_budget": budget,
        "high_prob_ticket": bool(row["model_p"] + 1e-12 >= float(CFG["high_prob"])),
        "spot_at_entry": None if spot is None else round(spot, 2),
        "sigma_at_entry": None if sigma is None else round(sigma, 2),
        "opened": stamp(when), "opened_day": str(when.date()), "close_time": row.get("close_time"),
    })
    apply_halt(state)


def run():
    if CFG.get("paper_only") is not True:
        sys.exit("Refusing to run: config paper_only must be true. Real orders are not implemented.")
    when = now_ct()
    state = load_state()
    state["runs"] = int(state.get("runs") or 0) + 1
    lines = [f"\n## Check {stamp(when)} (run #{state['runs']})", "",
             "Mode: PAPER ONLY. No order was sent."]
    summary = {"time": stamp(when), "action": "SKIP", "detail": ""}

    lines.extend(settle_open(state, when))
    block = None
    news_hits = []
    try:
        news_hits = news_hits_for_day(
            fetch_news(), when.date(), CT, CFG["news_country"], tuple(CFG["news_impacts"]))
    except Exception as e:
        news_hits = [f"calendar unread ({e})"]
    block = entry_block_reason(state, when.date(), news_hits)
    lines.append("- News: " + ("; ".join(news_hits) if news_hits else "no USD high-impact event today"))

    chosen = None
    try:
        events = fetch_events()
        picked = choose_event(events, datetime.now(timezone.utc))
        if not picked:
            lines.append("- Event: none inside the minute window")
            lines.append("- Action: SKIP (no event in the minute window)")
            summary["detail"] = "no event in window"
        else:
            minutes, ev, close_at = picked
            event_ticker = ev.get("event_ticker")
            lines.append(f"- Event: {event_ticker} closes {close_at.astimezone(CT):%Y-%m-%d %H:%M CT} ({minutes:.0f} min)")
            spots, spot_errors = fetch_spots()
            for err in spot_errors:
                lines.append(f"- Spot source failed: {err}")
            if not spots:
                lines.append("- Spot: unavailable")
                lines.append("- Action: SKIP (no BTC spot quote)")
                summary["detail"] = "no spot"
            else:
                spot = sum(spots.values()) / len(spots)
                lines.append("- Spot: " + ", ".join(f"{k} ${v:,.2f}" for k, v in spots.items())
                             + f" -> avg ${spot:,.2f}")
                dvol = realized = None
                try:
                    dvol = fetch_dvol()
                except Exception as e:
                    lines.append(f"- DVOL failed: {e}")
                try:
                    realized = fetch_realized_log_stdev()
                except Exception as e:
                    lines.append(f"- realized vol failed: {e}")
                sigma = combine_sigma(spot, minutes, dvol, realized, single_spot=(len(spots) == 1))
                if sigma is None:
                    lines.append("- Sigma: unavailable")
                    lines.append("- Action: SKIP (no volatility estimate)")
                    summary["detail"] = "no sigma"
                else:
                    realized_txt = f"{realized:.6f}" if realized is not None else "n/a"
                    dvol_txt = f"{dvol:.2f}" if dvol is not None else "n/a"
                    lines.append(f"- Sigma: ${sigma:,.0f} (DVOL {dvol_txt}, realized log-stdev per minute {realized_txt})")
                    markets = fetch_markets(event_ticker)
                    ranked = screen_sides(markets, spot, sigma)
                    tradable = [r for r in ranked if r["reason"] is None]
                    priced = sorted((r for r in ranked if r["edge"] is not None), key=lambda r: r["edge"], reverse=True)
                    shown = tradable[:5] if tradable else priced[:5]
                    lines += ["",
                              "| ticker | side | model p | ask | fee | edge | stake budget | action |",
                              "|---|---|---|---|---|---|---|---|"]
                    if not shown:
                        lines.append("| - | - | - | - | - | - | - | nothing to show |")
                    preview_block = block
                    for row in shown:
                        row_budget = stake_for_prob(row["model_p"])
                        if row["reason"]:
                            action = row["reason"]
                        elif preview_block:
                            action = "blocked: " + preview_block
                        else:
                            n, cost = size_ticket(row_budget, row["ask"], row["fee"],
                                                 row["model_p"] + 1e-12 >= float(CFG["high_prob"]),
                                                 state["cash"], open_risk_of(state))
                            action = f"fits ${cost:.2f} ({n} contracts)" if n else "stake band does not fit"
                        lines.append(candidate_row(row, row_budget, action))
                    if block:
                        summary["detail"] = block
                        lines.append(f"- Action: SKIP ({block})")
                    elif tradable:
                        chosen = try_fill(state, tradable, spot, sigma, when, lines, summary)
                        if chosen is None:
                            summary["detail"] = "no side survived the order-book re-check and stake band"
                            lines.append("- Action: SKIP (no side survived the order-book re-check and stake band)")
                    else:
                        summary["detail"] = summary["detail"] or "no side cleared every filter"
                        lines.append("- Action: SKIP (no side cleared every filter)")
    except Exception as e:
        summary["detail"] = f"check failed: {e}"
        lines.append(f"- Action: SKIP (check failed: {e})")

    if chosen is None and summary["action"] != "PAPER BUY" and not summary["detail"]:
        summary["detail"] = "no paper buy"
    risk = open_risk_of(state)
    realized_today = realized_pnl_on(state, when.date())
    realized_all = round(sum(float(p.get("pnl") or 0) for p in state["closed"]), 2)
    lines += ["",
              f"Paper cash ${state['cash']:.2f} | open {len(state['open'])} (risk ${risk:.2f}) | "
              f"realized today ${realized_today:+.2f} | realized all ${realized_all:+.2f}",
              f"State file: {STATE}",
              f"Log file: {LOG}"]
    log_lines(lines)
    save_state(state)
    print("\n".join(lines))
    summary.update({"cash": state["cash"], "open_risk": risk, "realized_today": realized_today,
                    "halted": state["halted"]})
    return summary


def self_test():
    cfg = CFG
    assert cfg["paper_only"] is True
    assert cfg["daily_loss_stop"] == 20.0
    assert cfg["max_open_risk"] == 40.0
    assert cfg["max_open_positions"] == 1
    assert cfg["stake_high_min"] == 10.0 and cfg["stake_high_max"] == 30.0
    assert cfg["high_prob"] == 0.80 and cfg["stake_low_cap"] == 10.0
    assert stake_for_prob(0.80) == 10.0
    assert stake_for_prob(0.90) == 20.0
    assert stake_for_prob(1.0) == 30.0
    assert stake_for_prob(0.55) == 2.0
    mid = stake_for_prob(0.675)
    assert mid == 6.0, mid
    just_under = stake_for_prob(0.799)
    assert just_under < 10.0, just_under
    assert stake_for_prob(0.54) is None
    for p in (0.55, 0.62, 0.70, 0.799):
        s = stake_for_prob(p)
        assert s is not None and s < 10.0, (p, s)
    for p in (0.80, 0.85, 0.93, 1.0):
        s = stake_for_prob(p)
        assert 10.0 <= s <= 30.0, (p, s)

    n, cost = size_ticket(10.0, 0.48, 0.02, True, 100, 0)
    assert n == 20 and abs(cost - 10.0) < 1e-9, (n, cost)
    n, cost = size_ticket(10.0, 0.50, 0.02, True, 100, 0)
    assert 10.0 <= cost <= 30.0 and n >= 1, (n, cost)
    n, cost = size_ticket(30.0, 0.40, 0.02, True, 100, 0)
    assert n == 71 and abs(cost - 29.82) < 1e-9, (n, cost)
    demo = [{
        "ticker": "DEMO", "event_ticker": "E", "strike": 100.0, "strike_type": "greater",
        "yes_bid": 0.55, "yes_ask": 0.57, "no_bid": 0.40, "no_ask": 0.43, "close_time": None,
    }]
    quiet = screen_sides(demo, 100, 1)
    assert quiet and all(r["reason"] for r in quiet)
    hot = [r for r in screen_sides(demo, 110, 5) if r["side"] == "yes" and r["reason"] is None]
    assert hot and hot[0]["model_p"] >= 0.80
    budget = stake_for_prob(hot[0]["model_p"])
    assert 10.0 <= budget <= 30.0
    n, cost = size_ticket(budget, hot[0]["ask"], hot[0]["fee"], True, 100, 0)
    assert n >= 1 and 10.0 <= cost <= 30.0, (n, cost)
    mild = [r for r in screen_sides([{
        "ticker": "MILD", "event_ticker": "E", "strike": 100.0, "strike_type": "greater",
        "yes_bid": 0.48, "yes_ask": 0.50, "no_bid": 0.48, "no_ask": 0.50, "close_time": None,
    }], 102, 8) if r["side"] == "yes" and r["reason"] is None]
    assert mild and mild[0]["model_p"] < 0.80
    low_budget = stake_for_prob(mild[0]["model_p"])
    assert low_budget is not None and low_budget < 10.0, low_budget
    n, cost = size_ticket(10.0, 31.0, 0.0, True, 100, 0)
    assert (n, cost) == (0, 0.0)
    n, cost = size_ticket(6.0, 0.48, 0.02, False, 100, 0)
    assert n == 12 and cost < 10, (n, cost)
    n, cost = size_ticket(6.0, 0.48, 0.02, False, 3.0, 0)
    assert cost <= 3.0 + 1e-9 and cost < 10, (n, cost)
    n, cost = size_ticket(20.0, 0.23, 0.02, True, 100, 25)
    assert 10.0 <= cost <= 15.0 + 1e-9, (n, cost)
    n, cost = size_ticket(20.0, 0.23, 0.02, True, 100, 35)
    assert (n, cost) == (0, 0.0)

    assert abs(fee_per_contract(0.50) - 0.02) < 1e-9
    assert abs(fee_per_contract(0.80) - 0.02) < 1e-9
    p_atm = model_yes_prob(100, 100, "greater", 10)
    assert abs(p_atm - 0.5) < 1e-9, p_atm
    assert model_yes_prob(130, 100, "greater", 10) > 0.99
    assert model_yes_prob(70, 100, "greater", 10) < 0.01
    assert model_yes_prob(130, 100, "less", 10) < 0.01
    wide = combine_sigma(100, 60, 80, 0.001, False)
    narrow = combine_sigma(100, 60, 20, 0.0001, False)
    assert wide > narrow > 0

    day = datetime(2026, 10, 30, tzinfo=CT).date()
    events = [
        {"country": "USD", "impact": "High", "date": "2026-10-30T08:30:00-04:00", "title": "CPI"},
        {"country": "USD", "impact": "Low", "date": "2026-10-30T10:00:00-04:00", "title": "Noise"},
        {"country": "EUR", "impact": "High", "date": "2026-10-30T08:30:00-04:00", "title": "Europe"},
        {"country": "USD", "impact": "High", "date": "2026-10-29T08:30:00-04:00", "title": "Yesterday"},
    ]
    hits = news_hits_for_day(events, day, CT)
    assert hits == ["CPI"], hits
    state = fresh_state()
    assert entry_block_reason(state, day, []) is None
    assert "big-news" in entry_block_reason(state, day, ["CPI"])
    state["closed"].append({"closed_day": str(day), "pnl": -20.0})
    assert "daily loss" in entry_block_reason(state, day, [])
    state["closed"].clear()
    state["open"].append({"cost": 10})
    assert "max open positions" in entry_block_reason(state, day, [])
    state["open"].clear()
    state["open"].append({"cost": 40})
    state_many = {"cash": 100, "open": [{"cost": 40}], "closed": [], "halted": False}
    # one position already blocks before the dollar cap is the reason; check the dollar cap with the cap raised
    loose = dict(cfg)
    loose["max_open_positions"] = 5
    assert "max open risk" in entry_block_reason(state_many, day, [], loose)
    state["open"].clear()
    state["cash"] = 80
    assert "halt" in entry_block_reason(state, day, [])
    state["halted"] = True
    state["cash"] = 100
    assert "bankroll halt" in entry_block_reason(state, day, [])
    print("self-test OK")
    print(f"defaults: high stake ${cfg['stake_high_min']:.0f}-${cfg['stake_high_max']:.0f} "
          f"at model p>={cfg['high_prob']:.0%}; low stake under ${cfg['stake_low_cap']:.0f}; "
          f"daily loss stop ${cfg['daily_loss_stop']:.0f}; max open ${cfg['max_open_risk']:.0f}; "
          f"max positions {cfg['max_open_positions']}")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test()
    elif "--reset" in sys.argv:
        for path in (STATE, LOG):
            if os.path.exists(path):
                os.remove(path)
        print(f"Paper state reset to ${CFG['starting_bankroll']:.2f}")
    else:
        run()
