#!/usr/bin/env python3
"""
commodity-15m-paper/bot.py — PAPER tower for Kalshi metals/energy 15m markets.

Series: Palladium, NatGas, Copper, Brent, WTI, Silver, Gold, Platinum.
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

SERIES = (
    "KXPALLADIUM15M",
    "KXNATGAS15M",
    "KXCOPPER15M",
    "KXBRENT15M",
    "KXWTI15M",
    "KXSILVER15M",
    "KXGOLD15M",
    "KXPLATINUM15M",
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


def book_depth(ticker: str, side: str, ask: float) -> tuple[float | None, int]:
    try:
        data = get_json(f"{KALSHI}/markets/{ticker}/orderbook")
    except Exception:
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
        except Exception:
            pass
    state["open"] = still


def evaluate(m: dict, spot: float, edge_buf: float) -> dict:
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
        book = desk_top25.commodity_playbook(m.get("series"))
        min_cush *= float(book.get("min_cushion_mult") or 1.0)
        z_floor = float(book.get("min_z") or MIN_Z)
    except Exception:
        z_floor = MIN_Z
    # Conservative σ: ~0.15% of spot * sqrt(minutes_left / 15) for 15m commodities.
    sigma = spot * 0.0015 * math.sqrt(max(minutes_left, 1.0) / 15.0)
    z = cushion / sigma if sigma > 1e-12 else 0.0
    p = phi(z)
    fee = kalshi_fee(ask)
    spread, depth = book_depth(str(m["ticker"]), side, ask)
    if cushion + 1e-12 < min_cush:
        reasons.append(f"cushion {cushion:.5f} < {min_cush:.5f}")
    lane = "accurate"
    need_edge = 0.0
    if p + 1e-12 >= MIN_MODEL_ACCURATE:
        lane = "accurate"
    elif p + 1e-12 >= MIN_MODEL_SPEED:
        lane = "speed"
        need_edge = SPEED_EDGE_EXTRA
        z_floor = min(float(z_floor), MIN_Z_SPEED)
    else:
        reasons.append(f"p {p:.3f} < speed floor {MIN_MODEL_SPEED}")
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
    save_account(state)
    return f"Paper buy {ev['side']} {ticker} x{contracts} @ {ask:.2f}."


def main() -> int:
    print("commodity-15m paper check (no live orders)")
    t0 = time.perf_counter()
    account = load_account()
    settle_account(account)
    save_account(account)

    if DESK_ROOT not in sys.path:
        sys.path.insert(0, DESK_ROOT)
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

    spots = spots_by_series()
    print(f"Spots ready: {len(spots)}/{len(SERIES)}  cash=${float(account.get('cash') or 0):.2f}")
    candidates = []
    buys = 0
    for series in SERIES:
        spot = spots.get(series)
        if spot is None:
            print(f"  {series}: no spot — skip")
            continue
        for m in list_open(series, limit=3):
            ev = evaluate(m, spot, edge_buf)
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
            except Exception:
                pass
    save_account(account)
    try:
        import desk_roi_plan
        desk_roi_plan.record_latency(
            DESK_ROOT, bot="commodity-15m", seconds=time.perf_counter() - t0,
            note="commodity check",
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
