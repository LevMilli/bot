"""Result splits: cut each tower's closed trades into groups. Suggests only.

For every trading tower it groups the closed paper trades four ways:

- ``market``: the Kalshi series (the ticker up to the first dash), or the coin /
  symbol for towers that are not on Kalshi. This is how the checklists ask for
  "BTC vs ETH", "by metal", "by league", "by city" and "by market".
- ``exit``: why the trade closed (held to the result, take profit, model flip,
  stop...). This answers "held to end vs sold early" and "how often each exit
  rule fired".
- ``hour``: the Central-time hour the trade was bought (S&P scan times, check
  times, time of day). Rows with no buy time are counted, not guessed.
- ``side``: yes / no (or buy / sell).

Every group keeps its losses. Each group shows trades, wins, losses, total,
average, win rate, average win vs average loss and a cautious 95% low end for
the average trade. Flags (suggest only, never acted on):

- ``clearly losing``: 50+ trades and even the high end of the range is below $0.
- ``wins often, loses money``: win rate 70%+ but the total is below $0.
"""
from __future__ import annotations

import datetime as dt
import math
import re

MIN_N = 50
Z95 = 1.96
OFTEN = 0.70
CUTS = ("market", "exit", "hour", "side")
CT = dt.timezone(dt.timedelta(hours=-6))  # fallback only; the bot passes the desk's Central zone

_LEAGUE = {
    "KXNFLGAME": "NFL", "KXNCAAFGAME": "College football", "KXNBAGAME": "NBA",
    "KXWNBAGAME": "WNBA", "KXMLBGAME": "MLB", "KXNHLGAME": "NHL",
    "KXNCAAMBGAME": "College basketball", "KXNCAABGAME": "College basketball",
}


def num(value):
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) else None


def market_of(row: dict) -> str:
    """Series of a Kalshi ticker (``KXBTC15M-26NOV13...`` -> ``KXBTC15M``), else the symbol."""
    ticker = str(row.get("ticker") or "").strip()
    if ticker:
        head = ticker.split("-", 1)[0].upper()
        return _LEAGUE.get(head, head)
    for key in ("symbol", "team", "game"):
        val = str(row.get(key) or "").strip()
        if val:
            return val[:40]
    return "unknown"


_HELD = re.compile(r"settle|result|resolved|expired|held|final", re.I)


def exit_of(row: dict) -> str:
    """Short plain exit bucket. Numbers are dropped so "tp 0.85" and "tp 0.91" group."""
    raw = str(row.get("exit_reason") or row.get("exit") or row.get("status") or "").strip()
    if not raw or raw == "unknown":
        return "not stored"
    low = raw.lower()
    if _HELD.search(low) and not re.search(r"sold|sell|stop|take|flip|trail", low):
        return "held to result"
    low = re.sub(r"[-+]?\$?\d+(\.\d+)?[%¢c]?", " ", low)
    low = re.sub(r"[^a-z ]+", " ", low)
    low = " ".join(low.split())[:40]
    return low or "not stored"


def _when(text):
    text = str(text or "").strip()
    if not text:
        return None
    try:
        when = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if when.tzinfo is None:
        return None  # a bare local time is ambiguous; count it, do not guess
    return when


def hour_of(row: dict, tz=CT) -> str:
    for key in ("priced_at", "opened", "entry_time", "entry_iso"):
        when = _when(row.get(key))
        if when is not None:
            return f"{when.astimezone(tz).hour:02d}:00 CT"
    return "buy time not stored"


def side_of(row: dict) -> str:
    side = str(row.get("side") or "").strip().lower()
    return side or "not stored"


def key_of(cut: str, row: dict, tz=CT) -> str:
    if cut == "market":
        return market_of(row)
    if cut == "exit":
        return exit_of(row)
    if cut == "hour":
        return hour_of(row, tz)
    return side_of(row)


def stats(pnls: list[float]) -> dict:
    n = len(pnls)
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    out = {"n": n, "wins": len(wins), "losses": len(losses), "total": round(sum(pnls), 2),
           "avg": None, "win_rate": None, "avg_win": None, "avg_loss": None, "low": None, "high": None,
           "flags": []}
    if not n:
        return out
    avg = sum(pnls) / n
    out["avg"] = round(avg, 4)
    out["win_rate"] = round(len(wins) / n, 3)
    out["avg_win"] = round(sum(wins) / len(wins), 4) if wins else None
    out["avg_loss"] = round(sum(losses) / len(losses), 4) if losses else None
    if n >= 2:
        sd = math.sqrt(sum((p - avg) ** 2 for p in pnls) / (n - 1))
        half = Z95 * sd / math.sqrt(n)
        out["low"], out["high"] = round(avg - half, 4), round(avg + half, 4)
    if n >= MIN_N and out["high"] is not None and out["high"] < 0:
        out["flags"].append("clearly losing")
    if out["win_rate"] >= OFTEN and out["total"] < 0:
        out["flags"].append("wins often, loses money")
    return out


def split(rows: list[dict], *, pnl_of=None, tz=CT) -> dict:
    """{cut: {group: stats}} plus ``no_result`` (rows whose P&L was not stored)."""
    pnl_of = pnl_of or (lambda r: num(r.get("pnl")))
    groups: dict = {cut: {} for cut in CUTS}
    missing = 0
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        pnl = pnl_of(row)
        if pnl is None:
            missing += 1
            continue
        for cut in CUTS:
            groups[cut].setdefault(key_of(cut, row, tz), []).append(float(pnl))
    out = {cut: {k: stats(v) for k, v in sorted(g.items())} for cut, g in groups.items()}
    out["no_result"] = missing
    return out


def run(histories: dict, now: dt.datetime, *, pnl_of=None, tz=CT) -> dict:
    """histories: {bot_id: (name, closed rows)}."""
    towers = {}
    flags = []
    for bot_id, (name, rows) in sorted(histories.items()):
        body = split(rows, pnl_of=pnl_of, tz=tz)
        n = sum(g["n"] for g in body["side"].values())
        towers[bot_id] = {"name": name, "n": n, "no_result": body.pop("no_result"), "cuts": body}
        for cut, groups in body.items():
            for group, st in groups.items():
                for flag in st["flags"]:
                    flags.append({"tower": bot_id, "cut": cut, "group": group, "flag": flag,
                                  "n": st["n"], "total": st["total"], "win_rate": st["win_rate"]})
    flags.sort(key=lambda f: (f["flag"], f["total"]))
    return {"updated": now.isoformat(timespec="seconds"), "suggest_only": True, "after_fees": True,
            "min_n": MIN_N, "towers": towers, "flags": flags}


def card(body: dict) -> str:
    towers = body["towers"]
    with_trades = sum(1 for t in towers.values() if t["n"])
    trades = sum(t["n"] for t in towers.values())
    line = f"Split {trades} closed trades from {with_trades} towers by market, exit, hour and side"
    losing = [f for f in body["flags"] if f["flag"] == "clearly losing" and f["cut"] == "market"]
    often = [f for f in body["flags"] if f["flag"] == "wins often, loses money" and f["cut"] == "market"]
    if losing:
        line += ". Clearly losing (50+ trades): " + "; ".join(
            f"{f['tower']} {f['group']} {f['total']:+.2f}" for f in losing[:4])
    if often:
        line += ". Wins often but loses money: " + "; ".join(
            f"{f['tower']} {f['group']} {f['win_rate'] * 100:.0f}% won, {f['total']:+.2f}" for f in often[:4])
    missing = sum(t["no_result"] for t in towers.values())
    if missing:
        line += f". {missing} closed trades had no stored result and are listed, not graded"
    return line + "."
