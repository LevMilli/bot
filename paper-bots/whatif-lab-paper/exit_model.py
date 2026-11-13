"""Exit lab (B12): for every closed Kalshi trade, what each exit rule would have made.

Research only. It never sells, buys or changes a tower. For each closed paper
trade with a Kalshi ticker it rebuilds the side's bid from entry to close using
Kalshi's public 1-minute candlesticks (hourly for trades held longer than a
day), then grades these exits on the same trade, per contract, after fees:

- ``actual``:     what the tower really did (its own P&L, losses included)
- ``hold``:       hold to the Kalshi result: $1 if our side won, else $0
- ``plus10``:     sell at the bid the first time it is 10 cents above the entry price
- ``plus15``:     the same at 15 cents
- ``model_flip``: sell the first time bid − fee beats the tower's own logged fair by
                  2 cents (only towers that log fairs in research.jsonl)
- ``time_stop``:  sell at the bid half way between entry and close

A sell is taken at the candle's closing bid less the Kalshi taker fee; if a
rule never fires the trade is held to the result. Every trade counts, winners
and losers alike. A rule is only compared on trades where it could be graded,
and ``actual`` is shown on that same set so the comparison is fair.

Kalshi reads go through the shared gateway: one ``/markets?tickers=`` read per
100 trades for results and close times, and batched candlestick reads (100
tickers or 10,000 candles at most per read). A graded trade is cached in
``exits.json`` and never read again.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import statistics

MIN_N = 50
Z95 = 1.96
LOOKBACK_DAYS = 30
MARKET_READS = 6           # /markets?tickers= reads a run (100 tickers each)
CANDLE_READS = 20          # candlestick reads a run
MAX_TICKERS = 100
MAX_CANDLES = 9000         # Kalshi allows 10,000 per batch; keep a margin
FLIP_MARGIN = 0.02
TARGETS = {"plus10": 0.10, "plus15": 0.15}
RULES = ("actual", "hold", "plus10", "plus15", "model_flip", "time_stop")
NAMES = {"actual": "what it did", "hold": "hold to the end", "plus10": "+10c", "plus15": "+15c",
         "model_flip": "model flip", "time_stop": "time stop"}
KEEP = 20000
RECHECK_HOURS = 6          # an unsettled market is read again after this


# ------------------------------------------------------------------ helpers
def _num(value):
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) else None


def when(text) -> dt.datetime | None:
    """Parse ISO times and the desk's ``YYYY-MM-DD HH:MM:SS UTC`` stamps."""
    if text in (None, ""):
        return None
    s = str(text).strip()
    if s.endswith(" UTC"):
        s = s[:-4].replace(" ", "T") + "+00:00"
    try:
        out = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return out if out.tzinfo else out.replace(tzinfo=dt.timezone.utc)


def fee(price: float) -> float:
    """Kalshi taker fee per contract, rounded up to the cent (same as the engine)."""
    p = float(price)
    if not (0.0 < p < 1.0):
        return 0.0
    return math.ceil(round(0.07 * p * (1.0 - p) * 100, 6)) / 100.0


def trade_of(bot: str, row: dict) -> dict | None:
    """Normalize one closed trade. None when it is not a Kalshi binary trade."""
    ticker = str(row.get("ticker") or "")
    side = str(row.get("side") or "").lower()
    contracts = _num(row.get("contracts"))
    pnl = _num(row.get("pnl"))
    opened = when(row.get("opened") or row.get("opened_at") or row.get("entry_time"))
    if not ticker.startswith("KX") or side not in ("yes", "no") or not contracts or contracts <= 0:
        return None
    if pnl is None or opened is None:
        return None
    cost = _num(row.get("cost"))
    entry = cost / contracts if cost is not None else None
    if entry is None:
        ask = _num(row.get("ask") if row.get("ask") is not None else row.get("entry_price"))
        if ask is None:
            return None
        entry = ask + (_num(row.get("fee")) or fee(ask))
    ask = _num(row.get("ask") if row.get("ask") is not None else row.get("entry_price"))
    closed = when(row.get("closed")) or opened
    return {
        "bot": bot, "ticker": ticker, "side": side, "contracts": contracts,
        "entry": round(entry, 4), "ask": round(ask, 4) if ask is not None else round(entry, 4),
        "pnl": round(pnl, 4), "opened": opened.isoformat(timespec="seconds"),
        "closed": closed.isoformat(timespec="seconds"), "exit": str(row.get("exit") or ""),
        "close_time": str(row.get("close_time") or ""),
        "result": str(row.get("result") or "").lower() if row.get("result") in ("yes", "no") else "",
    }


def key_of(t: dict) -> str:
    return f"{t['bot']}|{t['ticker']}|{t['side']}|{t['opened']}"


def closed_trades(accounts: list[tuple[str, str]], now: dt.datetime, days: int = LOOKBACK_DAYS) -> list[dict]:
    """accounts: [(bot_id, state path)]. Closed Kalshi trades from the last ``days``."""
    cutoff = now - dt.timedelta(days=days)
    out = []
    for bot, path in accounts:
        try:
            with open(path, encoding="utf-8") as handle:
                state = json.load(handle)
        except (OSError, ValueError):
            continue
        if not isinstance(state, dict):
            continue
        for row in state.get("closed") or []:
            if not isinstance(row, dict):
                continue
            t = trade_of(bot, row)
            if t and when(t["closed"]) >= cutoff:
                out.append(t)
    return out


# ------------------------------------------------------------------ price path
def side_bids(candles: list[dict], side: str) -> list[tuple[int, float]]:
    """[(end_ts, our side's bid)] from Kalshi candles. A NO bid is 1 − YES ask."""
    out = []
    for c in candles or []:
        end = int(c.get("end_period_ts") or 0)
        if side == "yes":
            px = _num((c.get("yes_bid") or {}).get("close_dollars"))
        else:
            ask = _num((c.get("yes_ask") or {}).get("close_dollars"))
            px = None if ask is None else round(1.0 - ask, 4)
        if end and px is not None and 0.0 < px < 1.0:
            out.append((end, px))
    out.sort()
    return out


def flip_points(log: list[dict], ticker: str, side: str) -> list[tuple[int, float, float]]:
    """[(ts, bid, fair)] the tower logged for this contract (research.jsonl)."""
    out = []
    for row in log:
        at = when(row.get("at"))
        if at is None:
            continue
        for d in row.get("decisions") or []:
            if d.get("ticker") != ticker or d.get("side") != side:
                continue
            bid, fair = _num(d.get("bid")), _num(d.get("fair"))
            if bid is not None and fair is not None and 0.0 < bid < 1.0:
                out.append((int(at.timestamp()), bid, fair))
    out.sort()
    return out


def grade(t: dict, result: str, close_ts: int, path: list[tuple[int, float]],
          flips: list[tuple[int, float, float]] | None = None) -> dict:
    """Per-contract P&L after fees for each rule on one trade."""
    won = 1.0 if result == t["side"] else 0.0
    entry = t["entry"]
    opened = int(when(t["opened"]).timestamp())
    held = round(won - entry, 4)
    out = {"actual": round(t["pnl"] / t["contracts"], 4), "hold": held}
    after = [(ts, px) for ts, px in path if opened < ts <= close_ts]
    for rule, step in TARGETS.items():
        out[rule] = held
        for _ts, px in after:
            if px >= t["ask"] + step - 1e-9:
                out[rule] = round(px - fee(px) - entry, 4)
                break
    mid = opened + (close_ts - opened) // 2
    stop = [px for ts, px in after if ts <= mid]
    out["time_stop"] = round(stop[-1] - fee(stop[-1]) - entry, 4) if stop and after else None
    if flips:
        out["model_flip"] = held
        for ts, bid, fair in flips:
            if opened < ts <= close_ts and bid - fee(bid) > fair + FLIP_MARGIN:
                out["model_flip"] = round(bid - fee(bid) - entry, 4)
                break
    else:
        out["model_flip"] = None
    return out


# ------------------------------------------------------------------ network
def market_info(tickers: list[str], get) -> dict:
    """{ticker: {result, close_time}} with one /markets?tickers= read."""
    from kalshi_shadow_tower import KALSHI

    data = get(f"{KALSHI}/markets?tickers={','.join(tickers)}") or {}
    out = {}
    for m in data.get("markets") or []:
        if isinstance(m, dict) and m.get("ticker"):
            out[m["ticker"]] = {"result": str(m.get("result") or "").lower(),
                                "close_time": str(m.get("close_time") or "")}
    return out


def candle_groups(todo: list[dict]) -> list[tuple[list[dict], int]]:
    """Group trades into batch reads: ≤100 tickers, ≤MAX_CANDLES candles. Returns [(trades, period)]."""
    groups, cur, period = [], [], 1
    for t in sorted(todo, key=lambda t: t["_open_ts"]):
        span_min = (t["_close_ts"] - t["_open_ts"]) / 60
        p = 1 if span_min <= 24 * 60 else 60
        trial = cur + [t]
        lo = min(x["_open_ts"] for x in trial)
        hi = max(x["_close_ts"] for x in trial)
        tickers = {x["ticker"] for x in trial}
        cp = max(period if cur else 1, p)
        per_ticker = (hi - lo) / 60 / cp + 2
        if cur and (len(tickers) > MAX_TICKERS or per_ticker * len(tickers) > MAX_CANDLES):
            groups.append((cur, period))
            cur, period = [t], p
            continue
        cur, period = trial, cp
    if cur:
        groups.append((cur, period))
    return groups


def candles_for(trades: list[dict], period: int, get) -> dict:
    from kalshi_shadow_tower import KALSHI

    start = min(t["_open_ts"] for t in trades) - 60
    end = max(t["_close_ts"] for t in trades)
    tickers = ",".join(sorted({t["ticker"] for t in trades}))
    data = get(f"{KALSHI}/markets/candlesticks?market_tickers={tickers}"
               f"&start_ts={start}&end_ts={end}&period_interval={period}") or {}
    return {str(m.get("market_ticker") or m.get("ticker")): m.get("candlesticks") or []
            for m in data.get("markets") or []}


# ------------------------------------------------------------------ report
def stats(values: list[float]) -> dict:
    n = len(values)
    out = {"n": n, "avg": None, "low": None, "high": None, "hit_rate": None}
    if not n:
        return out
    avg = sum(values) / n
    out.update(avg=round(avg, 4), hit_rate=round(sum(1 for v in values if v > 0) / n, 3),
               total=round(sum(values), 2))
    if n > 1:
        half = Z95 * statistics.stdev(values) / math.sqrt(n)
        out.update(low=round(avg - half, 4), high=round(avg + half, 4))
    return out


def report(graded: dict, now: dt.datetime, days: int = LOOKBACK_DAYS) -> dict:
    """Per bot and overall: for each rule, $ per trade (per-contract P&L × contracts).

    ``actual_same`` is what the tower really made on exactly the trades that rule
    could be graded on, so the two numbers are always comparable.
    """
    cutoff = now - dt.timedelta(days=days)
    by_bot: dict = {}
    for g in graded.values():
        if not g.get("grades") or (when(g.get("closed")) or now) < cutoff:
            continue
        by_bot.setdefault(g["bot"], []).append(g)
    out = {}
    for bot, rows in sorted(by_bot.items()):
        out[bot] = _rules(rows)
    every = [g for rows in by_bot.values() for g in rows]
    return {"bots": out, "all": _rules(every) if every else {}}


def _rules(rows: list[dict]) -> dict:
    res = {}
    for rule in RULES:
        got = [(g["grades"][rule] * g["contracts"], g["grades"]["actual"] * g["contracts"])
               for g in rows if g["grades"].get(rule) is not None]
        s = stats([v for v, _ in got])
        s["actual_same"] = round(sum(a for _, a in got) / len(got), 4) if got else None
        s["ready"] = s["n"] >= MIN_N
        res[rule] = s
    return res


def best_rule(rules: dict) -> tuple[str, dict] | None:
    """The rule with the best cautious low end, among rules with 50+ graded trades."""
    ready = [(r, s) for r, s in rules.items() if r != "actual" and s.get("n", 0) >= MIN_N and s.get("low") is not None]
    if not ready:
        return None
    return max(ready, key=lambda rs: rs[1]["low"])


# ------------------------------------------------------------------ run
def run(accounts: list[tuple[str, str]], logs: dict, prior: dict, get, now: dt.datetime,
        market_reads: int = MARKET_READS, candle_reads: int = CANDLE_READS) -> dict:
    """accounts: [(bot, state path)]; logs: {bot: research.jsonl rows} for model-flip.

    ``prior`` is the last exits.json; graded trades are reused, never re-read.
    """
    graded = dict(prior.get("graded") or {})
    markets = dict(prior.get("markets") or {})
    trades = closed_trades(accounts, now)
    todo = [t for t in trades if key_of(t) not in graded]
    notes = []
    m_reads = c_reads = 0
    # 1) results and close times, one read per 100 tickers
    need = []
    for t in todo:
        info = markets.get(t["ticker"]) or {}
        if info.get("result") in ("yes", "no") and info.get("close_time"):
            continue
        last = when(info.get("checked"))
        if last and now - last < dt.timedelta(hours=RECHECK_HOURS):
            continue
        if t["ticker"] not in need:
            need.append(t["ticker"])
    for i in range(0, len(need), MAX_TICKERS):
        if m_reads >= market_reads:
            notes.append("market read budget used; the rest waits for the next run")
            break
        m_reads += 1
        batch = need[i:i + MAX_TICKERS]
        try:
            got = market_info(batch, get)
        except Exception as exc:  # noqa: BLE001 - a failed read waits for the next run
            notes.append(f"market read failed ({type(exc).__name__})")
            continue
        for ticker in batch:
            info = dict(got.get(ticker) or {})
            info["checked"] = now.isoformat(timespec="seconds")
            markets[ticker] = info
    # 2) price paths for settled trades
    ready = []
    pending = 0
    for t in todo:
        info = markets.get(t["ticker"]) or {}
        result = t["result"] or info.get("result") or ""
        close = when(info.get("close_time") or t["close_time"])
        if result not in ("yes", "no") or close is None:
            pending += 1
            continue
        t["result"] = result
        t["_open_ts"] = int(when(t["opened"]).timestamp())
        t["_close_ts"] = max(int(close.timestamp()), t["_open_ts"] + 60)
        ready.append(t)
    for group, period in candle_groups(ready):
        if c_reads >= candle_reads:
            notes.append("candle read budget used; the rest waits for the next run")
            break
        c_reads += 1
        try:
            candles = candles_for(group, period, get)
        except Exception as exc:  # noqa: BLE001
            notes.append(f"candle read failed ({type(exc).__name__})")
            continue
        for t in group:
            path = side_bids(candles.get(t["ticker"]) or [], t["side"])
            flips = flip_points(logs.get(t["bot"]) or [], t["ticker"], t["side"])
            row = {k: v for k, v in t.items() if not k.startswith("_")}
            # No price history: hold and actual still grade; the price rules stay empty.
            row["grades"] = grade(t, t["result"], t["_close_ts"], path, flips)
            if not path:
                for rule in ("plus10", "plus15", "time_stop"):
                    row["grades"][rule] = None
            row["path_points"] = len(path)
            graded[key_of(t)] = row
    graded = dict(sorted(graded.items(), key=lambda kv: kv[1].get("closed") or "")[-KEEP:])
    rep = report(graded, now)
    return {"updated": now.isoformat(timespec="seconds"), "paper_only": True, "suggest_only": True,
            "min_n": MIN_N, "lookback_days": LOOKBACK_DAYS, "rules": list(RULES), "names": NAMES,
            "report": rep, "pending": pending,
            "ungraded": sum(1 for t in trades if key_of(t) not in graded),
            "reads": {"markets": m_reads, "candles": c_reads}, "notes": notes,
            "graded": graded, "markets": dict(list(markets.items())[-KEEP:])}


def card(body: dict) -> str:
    rep = body.get("report") or {}
    every = rep.get("all") or {}
    n = (every.get("hold") or {}).get("n", 0)
    line = f"Exit lab: {n} closed Kalshi trades graded"
    if not n:
        return line + (f"; {body.get('pending', 0)} waiting on results." if body.get("pending") else ".")
    bits = []
    for rule in ("actual", "hold", "plus10", "plus15", "model_flip", "time_stop"):
        s = every.get(rule) or {}
        if s.get("n"):
            bits.append(f"{NAMES[rule]} {s['avg']:+.2f}")
    line += " (avg $ per trade: " + ", ".join(bits) + ")"
    best = best_rule(every)
    if best:
        rule, s = best
        line += (f". Best cautious rule: {NAMES[rule]} (n {s['n']}, low end {s['low']:+.2f} vs "
                 f"what it did {s['actual_same']:+.2f})")
    else:
        line += f". No rule has {MIN_N} graded trades yet"
    if body.get("pending"):
        line += f"; {body['pending']} waiting on results"
    return line + ". Suggests only."
