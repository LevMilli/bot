"""Risk room: the whole city's open paper bets, grouped by what they ride on.

Display only. It never blocks, sizes or sells anything.

Each open position is mapped to an ``underlying`` (Bitcoin, S&P 500, a weather
city, one sports game...). The room then shows:

- open cost per underlying and its share of all open cost,
- which towers hold each underlying, and on which side,
- ``stacked``: two or more towers holding the same underlying,
- ``same side, same game``: two or more towers on the same side of one game or event,
- ``heavy``: one underlying is 40% or more of all open cost (with 2+ positions).

Unknown tickers fall back to their own series, so nothing is dropped.
"""
from __future__ import annotations

import datetime as dt
import math

HEAVY_SHARE = 0.40

# Order matters: the first prefix that matches the ticker body (after "KX") wins.
_ASSETS = (
    ("BTC", "Bitcoin"), ("ETH", "Ether"), ("SOL", "Solana"), ("XRP", "XRP"), ("DOGE", "Dogecoin"),
    ("BNB", "BNB"), ("HYPE", "Hyperliquid"), ("INX", "S&P 500"), ("SPX", "S&P 500"),
    ("NASDAQ100", "Nasdaq 100"), ("NDX", "Nasdaq 100"), ("TNOTE", "10-year yield"),
    ("TREAS", "10-year yield"), ("AAAGAS", "Gas price"), ("CPI", "CPI"), ("GDP", "GDP"),
    ("FED", "Fed rate"), ("GOLD", "Gold"), ("SILVER", "Silver"), ("WTI", "Crude oil"),
    ("OIL", "Crude oil"), ("NATGAS", "Natural gas"), ("COPPER", "Copper"), ("EURUSD", "EUR/USD"),
    ("USDJPY", "USD/JPY"), ("HIGH", "Weather"),
)
# Towers that are not on Kalshi: what they ride on, and the direction a long means.
_NON_KALSHI = {
    "coinbase-spot": ("Bitcoin", "up"),
    "btc-carry": ("Bitcoin", "flat (hedged)"),
    "qqq-momentum": ("Nasdaq 100", "up"),
}


def num(value):
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) else None


def _event(ticker: str, row: dict) -> str:
    game = str(row.get("game") or "").strip()
    if game:
        return game[:80]
    return ticker.rsplit("-", 1)[0] if "-" in ticker else ticker


def classify(bot_id: str, row: dict, category: str = "") -> tuple[str, str, str]:
    """(underlying, event, side). ``event`` is the single game/event for sports, else ""."""
    if bot_id in _NON_KALSHI:
        name, side = _NON_KALSHI[bot_id]
        return name, "", side
    ticker = str(row.get("ticker") or "").strip().upper()
    side = str(row.get("side") or "").strip().lower() or "not stored"
    if bot_id == "memecoin" or not ticker:
        sym = str(row.get("team") or row.get("ticker") or row.get("symbol") or "unknown").strip()
        return (f"Memecoin {sym}" if bot_id == "memecoin" else sym or "unknown"), "", side
    series = ticker.split("-", 1)[0]
    body = series[2:] if series.startswith("KX") else series
    if "GAME" in body or category == "sports" or bot_id in ("sports-gap", "sports-sharp-lag"):
        event = _event(ticker, row)
        return f"Game {event}", event, (str(row.get("team") or "").strip() or side)
    for prefix, name in _ASSETS:
        if body.startswith(prefix):
            if name == "Weather":
                return f"Weather {body[len(prefix):] or 'city'}", "", side
            return name, "", side
    return series, "", side


def room(open_rows: dict, now: dt.datetime) -> dict:
    """open_rows: {bot_id: (name, category, [open position rows])}."""
    groups: dict = {}
    total = 0.0
    count = 0
    for bot_id, (name, category, rows) in sorted(open_rows.items()):
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            cost = num(row.get("cost")) or 0.0
            under, event, side = classify(bot_id, row, category)
            g = groups.setdefault(under, {"underlying": under, "cost": 0.0, "positions": 0,
                                          "towers": {}, "event": event})
            g["cost"] += cost
            g["positions"] += 1
            t = g["towers"].setdefault(bot_id, {"name": name, "cost": 0.0, "sides": {}})
            t["cost"] += cost
            t["sides"][side] = t["sides"].get(side, 0) + 1
            total += cost
            count += 1
    rows = []
    flags = []
    for g in groups.values():
        g["cost"] = round(g["cost"], 2)
        for t in g["towers"].values():
            t["cost"] = round(t["cost"], 2)
        g["share"] = round(g["cost"] / total, 3) if total > 0 else 0.0
        g["flags"] = []
        if len(g["towers"]) >= 2:
            g["flags"].append("stacked")
            if g["event"]:
                sides = {}
                for tid, t in g["towers"].items():
                    for side in t["sides"]:
                        sides.setdefault(side, set()).add(tid)
                same = sorted(s for s, tids in sides.items() if len(tids) >= 2)
                if same:
                    g["flags"].append("same side, same game")
                    g["same_side"] = same
        if g["share"] >= HEAVY_SHARE and g["positions"] >= 2:
            g["flags"].append("heavy")
        for flag in g["flags"]:
            flags.append({"underlying": g["underlying"], "flag": flag, "cost": g["cost"],
                          "towers": sorted(g["towers"])})
        rows.append(g)
    rows.sort(key=lambda g: (-g["cost"], g["underlying"]))
    return {"updated": now.isoformat(timespec="seconds"), "display_only": True,
            "open_cost": round(total, 2), "positions": count,
            "towers": len({tid for g in rows for tid in g["towers"]}),
            "underlyings": rows, "flags": flags}


def card(body: dict) -> str:
    if not body["positions"]:
        return "No open paper positions in the city right now."
    line = (f"Open paper risk ${body['open_cost']:.2f} in {body['positions']} positions "
            f"across {body['towers']} towers")
    top = body["underlyings"][0]
    line += (f". Biggest: {top['underlying']} ${top['cost']:.2f} ({top['share'] * 100:.0f}%) "
             f"in {len(top['towers'])} tower{'s' if len(top['towers']) != 1 else ''}")
    stacked = [g for g in body["underlyings"] if "stacked" in g["flags"]]
    if stacked:
        line += ". Same bet in 2+ towers: " + "; ".join(
            f"{g['underlying']} ({', '.join(sorted(g['towers']))})" for g in stacked[:4])
    same = [g for g in body["underlyings"] if "same side, same game" in g["flags"]]
    if same:
        line += f". Same side of one game: {len(same)}"
    return line + "."
