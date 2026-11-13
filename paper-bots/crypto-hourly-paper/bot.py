#!/usr/bin/env python3
"""Crypto hourly: shadow paper tower for Kalshi hourly SOL, XRP, DOGE and BNB markets.

Twin of the crypto ladder for the coins Deribit has no option smile for. Prices
every "above $X" strike and every range from Coinbase spot and realized
volatility (``hourly_model.py``), and buys a side only when the edge after the
Kalshi fee clears the locked BTC floor of 0.05.

Paper only. Shadow only. $25 fixed ticket from a $500 sleeve, max 3 open, one
per event. Coins move together: at most 2 open bets the same direction per
close hour. Skips anything within 10 minutes of the print or more than 30 hours
out. Exits: model flip at the bid, settle backstop.
"""
from __future__ import annotations

import datetime as dt
import os
import sys
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
DESK_ROOT = os.path.dirname(HERE)
for path in (DESK_ROOT, HERE):
    if path not in sys.path:
        sys.path.insert(0, path)

import kalshi_shadow_tower as engine  # noqa: E402
import hourly_model as hm  # noqa: E402

SPEC = {"id": "crypto-hourly", "name": "Crypto hourly", "floor": 0.05, "max_open": 3,
        "max_edge": 0.20, "group_cap": 2}
# coin -> (above/below series, range series)
COINS = {
    "SOL": ("KXSOLD", "KXSOL"),
    "XRP": ("KXXRPD", "KXXRP"),
    "DOGE": ("KXDOGED", "KXDOGE"),
    "BNB": ("KXBNBD", "KXBNB"),
}
COINBASE = "https://api.exchange.coinbase.com/products/{coin}-USD/ticker"
CANDLES = "https://api.exchange.coinbase.com/products/{coin}-USD/candles?granularity={bar}"
_ET = ZoneInfo("America/New_York")


def _close(market: dict):
    try:
        return dt.datetime.fromisoformat(str(market.get("close_time")).replace("Z", "+00:00"))
    except ValueError:
        return None


def _money(x: float) -> str:
    return f"{x:,.4f}" if x < 1 else f"{x:,.2f}"


def coin_quotes(coin: str, markets: list[dict], spot: float, vols: tuple, now: dt.datetime) -> list[dict]:
    out = []
    for market in markets:
        close = _close(market)
        if close is None:
            continue
        minutes = (close - now).total_seconds() / 60.0
        if minutes < hm.MIN_MINUTES or minutes > hm.MAX_HOURS * 60:
            continue
        vol = hm.vol_for(minutes, *vols)
        if not vol:
            continue
        years = minutes * 60.0 / hm.YEAR_SEC
        p = hm.p_yes(market, spot, vol, years)
        if p is None:
            continue
        kind = str(market.get("strike_type"))
        lo, hi = market.get("floor_strike"), market.get("cap_strike")
        if kind == "greater":
            what, yes_up = f"above {_money(float(lo))}", True
        elif kind == "less":
            what, yes_up = f"below {_money(float(hi))}", False
        else:
            what, yes_up = f"{_money(float(lo))}-{_money(float(hi))}", None
        hour = close.astimezone(_ET).strftime("%-I%p").lower()
        why = (f"{coin} spot {_money(spot)}, {minutes:.0f} min to the {hour} ET close, "
               f"realized vol {vol:.0%}: P(yes) {p:.3f}")
        for side in engine.sides(market):
            side["fair"] = p if side["side"] == "yes" else 1.0 - p
            side["label"] = f"{coin} {close.astimezone(_ET).strftime('%b %d')} {hour} ET {what}"
            side["why"] = why
            if yes_up is not None:
                # Same close hour, same direction: the coins move together.
                up = yes_up if side["side"] == "yes" else not yes_up
                side["group"] = f"{close.isoformat()} {'up' if up else 'down'}"
            out.append(side)
    return out


def model(cfg: dict, now: dt.datetime):
    quotes, failed, dormant = [], [], []
    for coin, series_pair in COINS.items():
        try:
            spot = engine.num((engine.public_json(COINBASE.format(coin=coin)) or {}).get("price"))
            if not spot:
                raise ValueError("no spot")
            vols = (hm.realized_vol(engine.public_json(CANDLES.format(coin=coin, bar=300)) or [], 300),
                    hm.realized_vol(engine.public_json(CANDLES.format(coin=coin, bar=3600)) or [], 3600))
            if not any(vols):
                raise ValueError("short candle history")
            markets = []
            for series in series_pair:
                rows = engine.kalshi_open_markets(series, pages=2)
                if not rows:
                    dormant.append(series)
                markets.extend(rows)
            quotes.extend(coin_quotes(coin, markets, spot, vols, now))
        except Exception as exc:  # noqa: BLE001 - one coin's read failing skips that coin
            failed.append(f"{coin} ({type(exc).__name__})")
    parts = []
    if failed:
        parts.append("skipped " + ", ".join(failed))
    if dormant:
        parts.append("no open markets: " + ", ".join(dormant))
    note = "; ".join(parts)
    if not quotes and not note:
        note = "no open hourly coin strike in window"
    return quotes, note


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--reset" in argv:
        return engine.reset(SPEC, HERE)
    return engine.run_tower(SPEC, HERE, model)


if __name__ == "__main__":
    raise SystemExit(main())
