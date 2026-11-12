#!/usr/bin/env python3
"""Crypto ladder: shadow paper tower for Kalshi daily BTC / ETH strikes (KXBTCD, KXETHD).

Prices every "above $X at 5pm ET" strike from Coinbase spot and Deribit's option
smile (``ladder_model.py``), and buys a side only when the edge after the Kalshi
fee clears the locked BTC floor of 0.05.

Paper only. Shadow only. $25 fixed ticket from a $500 sleeve, max 2 open, one
per event. Skips strikes within 15 minutes of the print or more than 30 hours
out, and skips a coin when Deribit and Coinbase disagree by more than 0.5%.
Exits: model flip at the bid, settle backstop.
"""
from __future__ import annotations

import datetime as dt
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DESK_ROOT = os.path.dirname(HERE)
for path in (DESK_ROOT, HERE):
    if path not in sys.path:
        sys.path.insert(0, path)

import kalshi_shadow_tower as engine  # noqa: E402
import ladder_model as lm  # noqa: E402

SPEC = {"id": "crypto-ladder", "name": "Crypto ladder", "floor": 0.05, "max_open": 2, "max_edge": 0.20}
COINS = {"BTC": "KXBTCD", "ETH": "KXETHD"}
DERIBIT = "https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency={coin}&kind=option"
COINBASE = "https://api.exchange.coinbase.com/products/{coin}-USD/ticker"


def _close(market: dict):
    try:
        return dt.datetime.fromisoformat(str(market.get("close_time")).replace("Z", "+00:00"))
    except ValueError:
        return None


def coin_quotes(coin: str, markets: list[dict], spot: float, smile_map: dict, now: dt.datetime) -> list[dict]:
    out = []
    for market in markets:
        kind = str(market.get("strike_type") or "")
        strike = engine.num(market.get("floor_strike") if kind == "greater" else market.get("cap_strike"))
        close = _close(market)
        if kind not in ("greater", "less") or not strike or close is None:
            continue
        minutes = (close - now).total_seconds() / 60.0
        if minutes < lm.MIN_MINUTES or minutes > lm.MAX_HOURS * 60:
            continue
        under = lm.underlying_near(smile_map, close)
        if not under or abs(under / spot - 1) > lm.MAX_SPOT_GAP:
            continue
        vol = lm.vol_for(smile_map, close, strike, now)
        if not vol:
            continue
        years = minutes * 60.0 / lm.YEAR_SEC
        p_up = lm.p_above(spot, strike, vol, years)
        p_yes = p_up if kind == "greater" else 1.0 - p_up
        word = "above" if kind == "greater" else "below"
        why = (f"{coin} spot {spot:,.2f}, {minutes:.0f} min to 5pm ET, Deribit vol {vol:.0%} at "
               f"{strike:,.0f}: P({word}) {p_yes:.3f}")
        for side in engine.sides(market):
            side["fair"] = p_yes if side["side"] == "yes" else 1.0 - p_yes
            side["label"] = f"{coin} {close.strftime('%b %d')} {word} {strike:,.0f}"
            side["why"] = why
            out.append(side)
    return out


def model(cfg: dict, now: dt.datetime):
    quotes, failed = [], []
    for coin, series in COINS.items():
        try:
            spot = engine.num((engine.public_json(COINBASE.format(coin=coin)) or {}).get("price"))
            if not spot:
                raise ValueError("no spot")
            smile_map = lm.smiles((engine.public_json(DERIBIT.format(coin=coin)) or {}).get("result") or [])
            quotes.extend(coin_quotes(coin, engine.kalshi_open_markets(series), spot, smile_map, now))
        except Exception as exc:  # noqa: BLE001 - one coin's read failing skips that coin
            failed.append(f"{coin} ({type(exc).__name__})")
    note = ("skipped " + ", ".join(failed)) if failed else ""
    if not quotes and not note:
        note = "no open KXBTCD/KXETHD strike in window"
    return quotes, note


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--reset" in argv:
        return engine.reset(SPEC, HERE)
    return engine.run_tower(SPEC, HERE, model)


if __name__ == "__main__":
    raise SystemExit(main())
