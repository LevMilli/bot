#!/usr/bin/env python3
"""More 15m: shadow paper tower for Kalshi 15-minute "up or down" markets the
older towers never read.

Series: SOL, XRP, DOGE, BNB, HYPE (CF Benchmarks 60-second averages), the S&P 500
(KXINX15M, regular hours), EUR/USD and USD/JPY (Pyth). Each window asks whether
the price at the close is at least the price at the open; Kalshi posts that
open price as ``floor_strike``.

Fair = N(ln(spot / open) / (sigma * sqrt(minutes left))), with sigma the
realized 1-minute move over the last hour (x1.25 for fat tails, floored per
asset). Spot: Coinbase mid for the coins (Kraken backup), Hyperliquid's live
oracle for the S&P and FX. For those three the oracle is a different print from
Kalshi's source, so the bot learns the open offset at each fresh window and
only buys once it has seen 3 opens.

Paper only. Shadow only. Locked floor 0.05 (same as BTC 15m), trust cap 0.20,
$25 ticket from a $500 sleeve, max 4 open, one per window, one new buy per check.
Buys only with 3 to 14 minutes left. Exits: model flip at the bid, settle backstop.
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

HERE = os.path.dirname(os.path.abspath(__file__))
DESK_ROOT = os.path.dirname(HERE)
for path in (DESK_ROOT, HERE):
    if path not in sys.path:
        sys.path.insert(0, path)

import kalshi_shadow_tower as engine  # noqa: E402

SPEC = {"id": "more-15m", "name": "More 15m", "floor": 0.05, "max_open": 4, "max_edge": 0.20}

# series -> (label, spot kind, spot symbol, Hyperliquid candle coin, sigma floor per minute)
SERIES = {
    "KXSOL15M": ("SOL", "coin", "SOL", "SOL", 0.0004),
    "KXXRP15M": ("XRP", "coin", "XRP", "XRP", 0.0004),
    "KXDOGE15M": ("DOGE", "coin", "DOGE", "DOGE", 0.0005),
    "KXBNB15M": ("BNB", "coin", "BNB", "BNB", 0.0003),
    "KXHYPE15M": ("HYPE", "coin", "HYPE", "HYPE", 0.0006),
    "KXINX15M": ("S&P 500", "oracle", "xyz:SP500", "xyz:SP500", 0.00008),
    "KXEURUSD15M": ("EUR/USD", "oracle", "xyz:EUR", "xyz:EUR", 0.00004),
    "KXUSDJPY15M": ("USD/JPY", "oracle", "xyz:JPY", "xyz:JPY", 0.00004),
}
LEARN_BASIS = {"KXINX15M", "KXEURUSD15M", "KXUSDJPY15M"}
BASIS_MIN_OPENS = 3
BASIS_LEARN_MIN = 1.5     # learn only within 1.5 minutes of the open
BASIS_WEIGHT = 0.3
BASIS_FILE = "index_basis.json"
SIGMA_MULT = 1.25
MIN_MINUTES, MAX_MINUTES = 3.0, 14.0
HYPERLIQUID = "https://api.hyperliquid.xyz/info"
COINBASE = "https://api.exchange.coinbase.com/products/{sym}-USD/ticker"
KRAKEN = "https://api.kraken.com/0/public/Ticker?pair={sym}USD"
UA = {"User-Agent": "paper-bot/1.0 (more-15m)"}


def phi(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def hl_post(body: dict, timeout: float = 12):
    req = urllib.request.Request(HYPERLIQUID, data=json.dumps(body).encode("utf-8"), method="POST",
                                 headers={**UA, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def hl_oracles() -> dict[str, float]:
    meta, ctxs = hl_post({"type": "metaAndAssetCtxs", "dex": "xyz"})
    out = {}
    for asset, ctx in zip(meta.get("universe") or [], ctxs or []):
        px = engine.num((ctx or {}).get("oraclePx"))
        if px and px > 0:
            out[str(asset.get("name") or "")] = px
    return out


def sigma_per_min(coin: str, floor: float, now: dt.datetime) -> float:
    end = int(now.timestamp() * 1000)
    rows = hl_post({"type": "candleSnapshot",
                    "req": {"coin": coin, "interval": "1m", "startTime": end - 65 * 60000, "endTime": end}})
    closes = [engine.num(r.get("c")) for r in rows or []]
    closes = [c for c in closes if c and c > 0]
    rets = [math.log(b / a) for a, b in zip(closes, closes[1:])]
    if len(rets) < 20:
        raise ValueError("short candle history")
    return max(floor, SIGMA_MULT * statistics.pstdev(rets))


def coin_spot(sym: str) -> float:
    try:
        row = engine.public_json(COINBASE.format(sym=sym), headers=UA) or {}
        bid, ask = engine.num(row.get("bid")), engine.num(row.get("ask"))
        if bid and ask and ask >= bid:
            return (bid + ask) / 2.0
    except Exception:  # noqa: BLE001 - fall through to Kraken
        pass
    data = engine.public_json(KRAKEN.format(sym="XDG" if sym == "DOGE" else sym), headers=UA) or {}
    for row in (data.get("result") or {}).values():
        px = engine.num((row.get("c") or [None])[0])
        if px:
            return px
    raise ValueError("no spot")


def _basis() -> dict:
    data = engine.read_json(os.path.join(HERE, BASIS_FILE))
    return data or {}


def anchor(series: str, spot: float, market: dict, close: dt.datetime, now: dt.datetime) -> tuple[float, bool]:
    """(spot on Kalshi's scale, ready). Coins: unchanged and ready."""
    if series not in LEARN_BASIS:
        return spot, True
    state = _basis()
    row = state.get(series) or {}
    frac = float(row.get("frac") or 0.0)
    age = 15.0 - (close - now).total_seconds() / 60.0
    strike = engine.num(market.get("floor_strike"))
    ticker = str(market.get("ticker") or "")
    if strike and 0.0 <= age <= BASIS_LEARN_MIN and row.get("last") != ticker:
        seen = (strike - spot) / spot
        frac = seen if "frac" not in row else (1 - BASIS_WEIGHT) * frac + BASIS_WEIGHT * seen
        row = {"frac": round(frac, 7), "last": ticker, "n": int(row.get("n") or 0) + 1}
        state[series] = row
        try:
            engine.write_json(os.path.join(HERE, BASIS_FILE), state)
        except OSError:
            pass
    return spot * (1.0 + frac), int(row.get("n") or 0) >= BASIS_MIN_OPENS


def _close(market: dict):
    try:
        return dt.datetime.fromisoformat(str(market.get("close_time")).replace("Z", "+00:00"))
    except ValueError:
        return None


def window_quotes(series: str, markets: list[dict], spot: float, sigma: float, now: dt.datetime) -> list[dict]:
    label = SERIES[series][0]
    out = []
    for market in markets:
        close = _close(market)
        strike = engine.num(market.get("floor_strike"))
        if close is None or not strike:
            continue
        minutes = (close - now).total_seconds() / 60.0
        if minutes <= 0 or minutes > 15.5:
            continue
        level, ready = anchor(series, spot, market, close, now)
        t_eff = max(0.25, minutes - (0.67 if SERIES[series][1] == "coin" else 0.0))  # 60s average at the close
        p_yes = phi(math.log(level / strike) / (sigma * math.sqrt(t_eff)))
        p_yes = min(0.99, max(0.01, p_yes))
        why = (f"{label} {level:,.6g} vs open {strike:,.6g} ({100 * (level / strike - 1):+.3f}%), "
               f"{minutes:.1f} min left, 1-min move {100 * sigma:.3f}%: P(up) {p_yes:.3f}")
        log_reason = ""
        if not ready:
            log_reason = "learning the open offset (needs 3 window opens)"
        elif not (MIN_MINUTES <= minutes <= MAX_MINUTES):
            log_reason = f"{minutes:.1f} min left; buys only with 3-14 min left"
        for side in engine.sides(market):
            side["fair"] = p_yes if side["side"] == "yes" else 1.0 - p_yes
            side["label"] = f"{label} 15m up by {close.strftime('%H:%M')} UTC"
            side["why"] = why
            if log_reason:
                side["log_only"] = True
                side["log_reason"] = log_reason
            out.append(side)
    return out


def model(cfg: dict, now: dt.datetime):
    quotes, failed = [], []
    try:
        oracles = hl_oracles()
    except Exception as exc:  # noqa: BLE001
        oracles, failed = {}, [f"oracle ({type(exc).__name__})"]
    for series, (label, kind, sym, candle, floor) in SERIES.items():
        try:
            markets = engine.kalshi_open_markets(series, limit=3)
            if not markets:
                continue
            spot = coin_spot(sym) if kind == "coin" else oracles.get(sym)
            if not spot:
                raise ValueError("no spot")
            sigma = sigma_per_min(candle, floor, now)
            quotes.extend(window_quotes(series, markets, spot, sigma, now))
        except Exception as exc:  # noqa: BLE001 - one market's read failing skips that market
            failed.append(f"{label} ({type(exc).__name__})")
        time.sleep(0.05)
    note = ("skipped " + ", ".join(failed)) if failed else ""
    if not quotes and not note:
        note = "no open 15-minute window"
    return quotes, note


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--reset" in argv:
        return engine.reset(SPEC, HERE)
    return engine.run_tower(SPEC, HERE, model)


if __name__ == "__main__":
    raise SystemExit(main())
