"""QQQ noise-area intraday momentum. Pure functions, no network.

Rule (Zarattini, Aziz & Barbon 2024, "Beat the Market: An Effective Intraday
Momentum Strategy for SPY", applied to QQQ):

- sigma(t): the average absolute move from the open at time-of-day t over the
  previous 14 sessions.
- Upper band = max(open, yesterday's close) × (1 + sigma(t)).
  Lower band = min(open, yesterday's close) × (1 − sigma(t)).
- Checks only at HH:00 and HH:30, from 10:00 to 15:30 New York time.
- Flat: go long when the 5-minute close is above the upper band, short when
  below the lower band. The close must clear the band by at least ``floor`` ×
  the band's width (sigma × price), a small buffer against touches.
- Long exit (trailing stop): close below max(upper band, VWAP). Short exit:
  close above min(lower band, VWAP). After an exit it may enter the other way
  at the same check if that band is broken.
- Always flat at the 16:00 close.

Costs per share per side: $0.0035 commission plus $0.01 slippage (a full
1-cent spread, on purpose a bit pessimistic).
"""
from __future__ import annotations

import datetime as dt
import math
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
OPEN_MIN = 9 * 60 + 30
SESSION_MIN = 390
LOOKBACK = 14
MIN_DAYS = 10
CHECKS = tuple(range(30, 361, 30))   # 10:00 .. 15:30, minutes after the open
COMMISSION = 0.0035
SLIPPAGE = 0.01


def parse_bars(chart: dict) -> list[dict]:
    """Yahoo v8 chart JSON (5m, regular hours) -> [{date, open, bars: {t_end: bar}}] oldest first."""
    res = ((chart or {}).get("chart") or {}).get("result") or []
    if not res:
        return []
    res = res[0]
    quote = ((res.get("indicators") or {}).get("quote") or [{}])[0]
    days: dict = {}
    for i, ts in enumerate(res.get("timestamp") or []):
        try:
            o, h, lo, c, v = (quote[k][i] for k in ("open", "high", "low", "close", "volume"))
        except (KeyError, IndexError, TypeError):
            continue
        if None in (o, h, lo, c) or not all(math.isfinite(x) for x in (o, h, lo, c)):
            continue
        when = dt.datetime.fromtimestamp(int(ts), NY)
        start = when.hour * 60 + when.minute - OPEN_MIN
        if not 0 <= start < SESSION_MIN:
            continue
        day = days.setdefault(when.date().isoformat(), {"date": when.date().isoformat(), "bars": {}})
        day["bars"][start + 5] = {"o": float(o), "h": float(h), "l": float(lo), "c": float(c), "v": float(v or 0)}
    out = []
    for key in sorted(days):
        day = days[key]
        if 5 not in day["bars"]:
            continue                      # no opening bar: cannot anchor the day
        day["open"] = day["bars"][5]["o"]
        day["last"] = max(day["bars"])
        day["close"] = day["bars"][day["last"]]["c"]
        out.append(day)
    return out


def sigma(days: list[dict], index: int, t_end: int, lookback: int = LOOKBACK) -> float | None:
    moves = []
    for day in days[max(0, index - lookback):index]:
        bar = day["bars"].get(t_end)
        if bar:
            moves.append(abs(bar["c"] / day["open"] - 1.0))
    return sum(moves) / len(moves) if len(moves) >= MIN_DAYS else None


def vwap(day: dict, t_end: int) -> float | None:
    num = den = 0.0
    for t, bar in day["bars"].items():
        if t <= t_end and bar["v"] > 0:
            num += (bar["h"] + bar["l"] + bar["c"]) / 3 * bar["v"]
            den += bar["v"]
    return num / den if den else None


def bands(days: list[dict], index: int, t_end: int) -> dict | None:
    if index < 1 or t_end not in days[index]["bars"]:
        return None
    s = sigma(days, index, t_end)
    if s is None:
        return None
    day, prev = days[index], days[index - 1]
    hi, lo = max(day["open"], prev["close"]), min(day["open"], prev["close"])
    return {"t": t_end, "close": day["bars"][t_end]["c"], "sigma": s, "upper": hi * (1 + s),
            "lower": lo * (1 - s), "vwap": vwap(day, t_end)}


def decide(side: str | None, b: dict, floor: float) -> tuple[bool, str | None, str]:
    """(exit_now, new_side, why) at one check. side is None, 'long' or 'short'."""
    c, up, lo, vw = b["close"], b["upper"], b["lower"], b["vwap"] or b["close"]
    exit_now, why = False, ""
    if side == "long":
        stop = max(up, vw)
        if c < stop:
            exit_now, why, side = True, f"close {c:.2f} under stop {stop:.2f}", None
    elif side == "short":
        stop = min(lo, vw)
        if c > stop:
            exit_now, why, side = True, f"close {c:.2f} over stop {stop:.2f}", None
    if side is None:
        need = floor * b["sigma"] * c
        if c > up + need:
            return exit_now, "long", (why + "; " if why else "") + f"close {c:.2f} above upper {up:.2f}"
        if c < lo - need:
            return exit_now, "short", (why + "; " if why else "") + f"close {c:.2f} below lower {lo:.2f}"
        return exit_now, None, why or f"inside the band {lo:.2f}-{up:.2f}"
    return False, side, why or "holding: stop not hit"


def fill(side: str, price: float, opening: bool) -> float:
    """Fill price after slippage. Buying pays up, selling gets less."""
    buying = (side == "long") == opening
    return price + SLIPPAGE if buying else price - SLIPPAGE


def trade_pnl(side: str, shares: float, entry: float, exit_: float) -> float:
    gross = (exit_ - entry) * shares if side == "long" else (entry - exit_) * shares
    return gross - 2 * COMMISSION * shares


def backtest_day(days: list[dict], index: int, floor: float, ticket: float = 25.0) -> list[dict]:
    """All trades for one past session, using only data known at each check."""
    trades, pos = [], None
    for t in CHECKS + (SESSION_MIN,):
        b = bands(days, index, t) if t != SESSION_MIN else None
        if t == SESSION_MIN or (b is None and t == days[index]["last"]):
            if pos:
                px = fill(pos["side"], days[index]["close"], False)
                trades.append(dict(pos, exit=px, why="flat at the close",
                                   pnl=trade_pnl(pos["side"], pos["shares"], pos["entry"], px)))
            break
        if b is None:
            continue
        exit_now, new_side, _ = decide(pos["side"] if pos else None, b, floor)
        if exit_now and pos:
            px = fill(pos["side"], b["close"], False)
            trades.append(dict(pos, exit=px, why="stop",
                               pnl=trade_pnl(pos["side"], pos["shares"], pos["entry"], px)))
            pos = None
        if new_side and pos is None:
            px = fill(new_side, b["close"], True)
            pos = {"side": new_side, "entry": px, "shares": ticket / px, "t": t}
    return trades


def backtest(days: list[dict], floor: float, ticket: float = 25.0) -> dict:
    trades = []
    for i in range(1, len(days)):
        if sigma(days, i, 30) is not None:
            trades.extend(dict(tr, date=days[i]["date"]) for tr in backtest_day(days, i, floor, ticket))
    pnl = [t["pnl"] for t in trades]
    sessions = len({t["date"] for t in trades})
    return {"trades": len(trades), "sessions_traded": sessions,
            "total": round(sum(pnl), 4), "avg": round(sum(pnl) / len(pnl), 5) if pnl else None,
            "hit_rate": round(sum(1 for p in pnl if p > 0) / len(pnl), 3) if pnl else None,
            "return_on_ticket": round(sum(pnl) / ticket, 4) if pnl else None}
