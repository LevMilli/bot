"""Replay lab (the "time machine"): replay a tower's rules on recorded prices.

Paper only. Read only. It never places an order, never writes to a tower's
folder and never changes a tower's rules. Every replay runs in a throwaway
folder and its results are only a report.

Two kinds of replay:

* **Engine towers** (More 15m and the daily ladder towers: Crypto ladder,
  Nasdaq, Weather high and every other row that uses
  ``kalshi_shadow_tower``). Their recorded prices are the ``research.jsonl``
  rows each check writes (fair, ask, bid per side). The replay feeds those rows
  back into the very same ``kalshi_shadow_tower.run_tower`` the live tower
  uses, so the fill rules are the live ones: fee once per order, the Kalshi
  tape check, the trust cap, max open, extra slots, one buy per check, the
  same-direction cap and the model-flip exit.
* **BTC 15m and Commodity 15m.** Their recorded prices are the window
  snapshots in ``kalshi_crypto_history.json`` (side, model chance, yes/no ask,
  minutes left, and the skip note) plus the settled results in the same file.
  Those towers are large single programs that read live feeds, so the replay
  re-checks the rules that can be computed from a snapshot (time left, ask
  band, chance floor, edge after fee) and keeps every other recorded block
  (spread, depth, news, cushion, candles) exactly as the live check saw it.
  Held-side bids come from the other side's ask (yes bid = 1 - no ask).

What-if switches change one rule at a time. Honest numbers: losses always
count, unsettled trades are listed as unsettled and never guessed.

Stats: results are reported on "check" days only (the later part of the
days), with a block-bootstrap lower bound that is made stricter for every
variant tried in the same family (``variants_tried``).
"""
from __future__ import annotations

import contextlib
import datetime as dt
import importlib.util
import io
import json
import math
import os
import random
import sys
import tempfile
from typing import Any, Callable, Iterable

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import kalshi_shadow_tower as engine  # noqa: E402

try:  # Chicago calendar days, same as the vault
    from zoneinfo import ZoneInfo
    CT = ZoneInfo("America/Chicago")
except Exception:  # noqa: BLE001 - fall back to a fixed offset
    CT = dt.timezone(dt.timedelta(hours=-6))

MIN_DAYS = 7               # step 333: at least 7 days before a practice twin
MIN_CHECK_DAYS = 3
CHECK_FRACTION = 0.4       # step 338: the last 40% of days are "check" days
BOOT_SAMPLES = 2000
BASE_ALPHA = 0.05
MANY_VARIANTS = 20         # step 337
REPLAY_GAP_TOLERANCE = 0.02  # dollars per trade (step 324)
RUNS_FILE = "replay_runs.jsonl"

# Reasons the engine itself writes. Any other skip reason on a priced row
# came from the tower's model (log-only rows), so the replay keeps it log-only.
ENGINE_REASONS = (
    "need fair + ask", "fair out of range", "ask ", "edge ", "fair ", "desk entry gate",
    "one new buy per check", "already holding", "same-direction cap", "max open",
    "ticket buys no contract", "shadow cash below ticket", "tape check limit", "Kalshi tape",
)


# ------------------------------------------------------------------ small helpers
def parse_at(text: Any) -> dt.datetime | None:
    try:
        when = dt.datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return when if when.tzinfo else when.replace(tzinfo=dt.timezone.utc)


def ct_day(text: Any) -> str | None:
    when = parse_at(text)
    return None if when is None else when.astimezone(CT).date().isoformat()


def _num(value):
    return engine.num(value)


def load_spec(folder: str) -> dict:
    """SPEC from a tower folder's bot.py (import only; nothing runs)."""
    path = os.path.join(folder, "bot.py")
    name = "replay_spec_" + os.path.basename(os.path.normpath(folder)).replace("-", "_")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return dict(mod.SPEC)


# ------------------------------------------------------------------ recorded data
def read_jsonl(path: str) -> list[dict]:
    out: list[dict] = []
    for p in (path + ".1", path):  # rotated file first, it is older
        try:
            with open(p, encoding="utf-8") as handle:
                for line in handle:
                    try:
                        row = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(row, dict):
                        out.append(row)
        except OSError:
            continue
    return out


def recorded_log_only(decision: dict) -> bool:
    reason = str(decision.get("reason") or "")
    if decision.get("action") == "buy" or not reason:
        return False
    return not reason.startswith(ENGINE_REASONS)


def quote_from_decision(d: dict) -> dict:
    q = {k: d.get(k) for k in ("ticker", "event", "side", "fair", "ask", "bid", "label", "why")}
    if d.get("group"):
        q["group"] = d["group"]
    if recorded_log_only(d):
        q["log_only"] = True
        q["log_reason"] = str(d.get("reason") or "")
    if d.get("tape_volume") is not None:
        q["_tape_volume"] = float(d["tape_volume"])
    return q


def engine_checks(rows: Iterable[dict], days: set[str] | None = None) -> list[dict]:
    """research.jsonl rows -> [{at, quotes}] in time order."""
    out = []
    for row in rows:
        at = parse_at(row.get("at"))
        if at is None:
            continue
        if days is not None and ct_day(row.get("at")) not in days:
            continue
        quotes = [quote_from_decision(d) for d in row.get("decisions") or [] if isinstance(d, dict)]
        gate = any(str((d or {}).get("reason") or "") == "desk entry gate" for d in row.get("decisions") or [])
        out.append({"at": at, "quotes": quotes, "note": str(row.get("note") or ""), "gate_closed": gate})
    out.sort(key=lambda c: c["at"])
    return out


def live_results(account: dict | None) -> dict[str, str]:
    """ticker -> yes/no from the live book's settled trades."""
    out = {}
    for row in (account or {}).get("closed") or []:
        res = str(row.get("result") or "").lower()
        if res in ("yes", "no") and row.get("ticker"):
            out[str(row["ticker"])] = res
    return out


def history_results(history: dict | None) -> dict[str, str]:
    out = {}
    for row in (history or {}).get("settles") or []:
        res = str((row or {}).get("result") or "").lower()
        if res in ("yes", "no") and row.get("ticker"):
            out[str(row["ticker"])] = res
    return out


# ------------------------------------------------------------------ what-if switches
# Engine towers (More 15m and the ladders)
ENGINE_SWITCHES = {
    # step 327: a higher edge bar for asks under ``low_ask_below``
    "low_ask_min_edge": None, "low_ask_below": 0.20,
    # step 328: take profit when the held-side bid reaches ask + this
    "take_profit": None,
    # tape: what to do when a row was never tape-checked live ("fail" is cautious)
    "unknown_tape": "fail",
}
# BTC 15m / Commodity 15m snapshot replay
WINDOW_DEFAULTS = {
    "btc15m": {"min_minutes": 10.0, "ask_min": 0.70, "ask_max": 0.92, "p_accurate": 0.80,
               "p_speed": 0.72, "speed_extra": 0.02, "edge_buf": 0.05, "take_profit": 0.15,
               "tp_cap": 0.99, "high_ask": None, "high_ask_extra": 0.0, "max_buys": 3},
    "commodity-15m": {"min_minutes": 8.0, "ask_min": 0.70, "ask_max": 0.92, "p_accurate": 0.80,
                      "p_speed": 0.72, "speed_extra": 0.02, "edge_buf": 0.05, "take_profit": None,
                      "tp_cap": 0.99, "high_ask": None, "high_ask_extra": 0.0, "max_buys": 3},
}
LOCKED_FLOORS = {"btc15m": 0.05, "commodity-15m": 0.05, "more-15m": 0.05}

# Named ideas from the plan (steps 327-332). Each changes one rule.
IDEAS = {
    "more15m-bar-under-20c": ("more-15m", {"low_ask_min_edge": 0.10}),
    "more15m-tp-10": ("more-15m", {"take_profit": 0.10}),
    "more15m-tp-20": ("more-15m", {"take_profit": 0.20}),
    "more15m-tp-30": ("more-15m", {"take_profit": 0.30}),
    "commodity-cap-85": ("commodity-15m", {"ask_max": 0.85}),
    "commodity-extra-edge-85": ("commodity-15m", {"high_ask": 0.85, "high_ask_extra": 0.03}),
    "btc15m-5min": ("btc15m", {"min_minutes": 5.0}),
    "btc15m-tp-10": ("btc15m", {"take_profit": 0.10}),
    "btc15m-tp-20": ("btc15m", {"take_profit": 0.20}),
}


def window_rules(bot: str, changes: dict | None = None) -> dict:
    rules = dict(WINDOW_DEFAULTS[bot])
    for key, value in (changes or {}).items():
        if key not in rules:
            raise KeyError(f"unknown rule {key!r} for {bot}")
        rules[key] = value
    # A what-if can raise a bar but never take the edge buffer under the locked floor.
    rules["edge_buf"] = max(float(rules["edge_buf"]), LOCKED_FLOORS[bot])
    return rules


def engine_switches(changes: dict | None = None) -> dict:
    sw = dict(ENGINE_SWITCHES)
    for key, value in (changes or {}).items():
        if key not in sw:
            raise KeyError(f"unknown switch {key!r}")
        sw[key] = value
    return sw


# ------------------------------------------------------------------ engine replay
def _tape_for(quotes: list[dict], unknown: str) -> Callable:
    seen = {(q.get("ticker"), q.get("side")): q for q in quotes}

    def tape(ticker: str, _now: dt.datetime) -> list[dict]:
        hits = [q for (t, _s), q in seen.items() if t == ticker]
        rows = []
        for q in hits:
            vol = q.get("_tape_volume")
            if vol is None:
                vol = 1e9 if unknown == "pass" else 0.0
            ask = _num(q.get("ask")) or 0.0
            yes = ask if q.get("side") == "yes" else round(1.0 - ask, 4)
            rows.append({"yes_price_dollars": yes, "count": vol})
        return rows

    return tape


def _apply_low_ask_bar(quotes: list[dict], bar: float | None, below: float) -> list[dict]:
    if bar is None:
        return quotes
    out = []
    for q in quotes:
        ask, fair = _num(q.get("ask")), _num(q.get("fair"))
        if (not q.get("log_only") and ask is not None and fair is not None and 0 < ask < float(below)
                and fair - ask - engine.fee(ask) + 1e-12 < float(bar)):
            q = dict(q, log_only=True, log_reason=f"what-if: ask under {below:.2f} needs edge {bar:g}")
        out.append(q)
    return out


def _take_profits(state: dict, quotes: list[dict], now: dt.datetime, tp: float | None,
                  per_order_fee: bool) -> list[dict]:
    if tp is None:
        return []
    by_key = {(q.get("ticker"), q.get("side")): q for q in quotes}
    keep, sold = [], []
    for pos in state.get("open") or []:
        bid = _num((by_key.get((pos.get("ticker"), pos.get("side"))) or {}).get("bid"))
        ask0 = _num(pos.get("ask")) or 0.0
        if bid is None or not (0 < bid < 1) or bid + 1e-12 < min(0.99, ask0 + float(tp)):
            keep.append(pos)
            continue
        c = int(pos.get("contracts") or 0)
        fee = engine.order_fee(c, bid) if per_order_fee else round(c * engine.fee(bid), 2)
        proceeds = round(c * bid - fee, 2)
        row = dict(pos, exit="what-if take-profit", exit_bid=bid, payout=proceeds,
                   pnl=round(proceeds - float(pos.get("cost") or 0), 2),
                   closed=now.isoformat(timespec="seconds"))
        state["cash"] = round(float(state.get("cash") or 0) + proceeds, 4)
        state.setdefault("closed", []).append(row)
        sold.append(row)
    state["open"] = keep
    return sold


def replay_engine(spec: dict, checks: list[dict], results: dict[str, str], *,
                  changes: dict | None = None, config: dict | None = None) -> dict:
    """Replay recorded checks through the live engine in a throwaway folder."""
    sw = engine_switches(changes)
    per_order_fee = bool(spec.get("fee_per_order"))
    seen: set[str] = set()
    with tempfile.TemporaryDirectory(prefix="replay-") as tower:
        if config:
            engine.write_json(os.path.join(tower, "config.json"), dict(config))
        acct = os.path.join(tower, "paper_account.json")
        old_block = os.environ.pop("DESK_BLOCK_ENTRIES", None)
        try:
            for check in checks:
                now = check["at"]
                quotes = [dict(q) for q in check["quotes"]]
                live_now = {q.get("ticker") for q in quotes}

                def fetch(ticker: str, _live=live_now) -> dict:
                    # A window settles once it has left the open list and a result is known.
                    if ticker in _live or ticker not in results:
                        return {}
                    return {"result": results[ticker]}

                state = engine.read_json(acct)
                if state is not None and sw["take_profit"] is not None:
                    if _take_profits(state, quotes, now, sw["take_profit"], per_order_fee):
                        engine.write_json(acct, state)
                quotes = _apply_low_ask_bar(quotes, sw["low_ask_min_edge"], float(sw["low_ask_below"]))
                seen.update(live_now)
                # The live desk gate was closed on this check: keep it closed in the replay.
                if check.get("gate_closed"):
                    os.environ["DESK_BLOCK_ENTRIES"] = "1"
                else:
                    os.environ.pop("DESK_BLOCK_ENTRIES", None)
                with contextlib.redirect_stdout(io.StringIO()):
                    engine.run_tower(spec, tower, None, now=now, fetch=fetch, quotes=quotes,
                                     tape=_tape_for(quotes, str(sw["unknown_tape"])))
            # End of the recording: settle what has a known result, leave the rest open.
            state = engine.read_json(acct) or engine.empty_state(engine.locked_cfg(spec, config))
            if checks:
                end = checks[-1]["at"] + dt.timedelta(minutes=1)
                engine.settle_open(state, end, fetch=lambda t: {"result": results[t]} if t in results else {})
        finally:
            os.environ.pop("DESK_BLOCK_ENTRIES", None)
            if old_block is not None:
                os.environ["DESK_BLOCK_ENTRIES"] = old_block
    return {"tower": spec.get("id"), "changes": dict(changes or {}), "closed": state.get("closed") or [],
            "open": state.get("open") or [], "cash": state.get("cash"), "checks": len(checks)}


# ------------------------------------------------------------------ BTC 15m / Commodity 15m replay
RULE_TAGS = (
    ("time", r"min left|under 1 minute"),
    ("ask", r"^ask\b.*outside"),
    ("p_floor", r"speed floor"),
    ("edge", r"ask\+fee\+buf"),
)


def _tag(reason: str) -> str:
    """Which re-checked rule a recorded skip reason belongs to; "kept" = replay keeps it as recorded."""
    import re
    text = str(reason or "").strip()
    for tag, pattern in RULE_TAGS:
        if re.search(pattern, text):
            return tag
    return "kept"


def _fee15(p: float) -> float:
    return engine.fee(p)


def window_gates(snap: dict, rules: dict) -> list[str]:
    """Rules the replay re-checks for one snapshot (side already chosen live)."""
    out = []
    left = _num(snap.get("minutes_left"))
    side = str(snap.get("side") or "").upper()
    ask = _num(snap.get("yes_ask") if side == "YES" else snap.get("no_ask"))
    p = _num(snap.get("model_p"))
    if left is None or left < 1.0:
        out.append("under 1 minute")
    elif left < float(rules["min_minutes"]):
        out.append(f"only {left:.1f} min left (< {float(rules['min_minutes']):g})")
    if ask is None or not (float(rules["ask_min"]) <= ask <= float(rules["ask_max"])):
        out.append(f"ask outside {float(rules['ask_min']):.2f}-{float(rules['ask_max']):.2f}")
    if p is None or ask is None:
        out.append("need p + ask")
        return out
    need = ask + _fee15(ask) + float(rules["edge_buf"])
    if rules.get("high_ask") is not None and ask > float(rules["high_ask"]) + 1e-12:
        need += float(rules.get("high_ask_extra") or 0.0)
    if p + 1e-12 >= float(rules["p_accurate"]):
        lane = "accurate"
    elif p + 1e-12 >= float(rules["p_speed"]):
        lane, need = "speed", need + float(rules["speed_extra"])
    else:
        lane = "none"
        out.append(f"p {p:.3f} < speed floor {float(rules['p_speed']):.2f}")
    if p + 1e-12 < need:
        out.append(f"p {p:.3f} < ask+fee+buf ({lane}) = {need:.3f}")
    return out


def kept_blocks(snap: dict) -> list[str]:
    """Recorded blocks the replay cannot re-check (spread, depth, news, cushion, z, candles)."""
    return [r.strip() for r in str(snap.get("note") or "").split(";") if r.strip() and _tag(r) == "kept"]


def replay_windows(bot: str, snaps: list[dict], results: dict[str, str], *, changes: dict | None = None,
                   stake: float = 25.0) -> dict:
    rules = window_rules(bot, changes)
    rows = [s for s in snaps if isinstance(s, dict) and s.get("ticker") and s.get("side")]
    rows.sort(key=lambda s: str(s.get("at") or ""))
    open_pos: dict[str, dict] = {}
    closed: list[dict] = []
    by_check: dict[str, list[dict]] = {}
    for s in rows:
        by_check.setdefault(str(s.get("at"))[:16], []).append(s)
    for at in sorted(by_check):
        buys = 0
        for s in by_check[at]:
            ticker = str(s["ticker"])
            side = str(s["side"]).upper()
            # held side bid = 1 - the other side's ask (one Kalshi book)
            pos = open_pos.get(ticker)
            if pos is not None and rules.get("take_profit") is not None:
                other = _num(s.get("no_ask") if pos["side"] == "YES" else s.get("yes_ask"))
                bid = None if other is None else round(1.0 - other, 4)
                tp = min(float(rules["tp_cap"]), round(pos["ask"] + float(rules["take_profit"]), 2))
                if bid is not None and 0 < bid < 1 and bid + 1e-12 >= tp:
                    proceeds = round(pos["contracts"] * (bid - _fee15(bid)), 2)
                    closed.append(dict(pos, exit="take-profit", exit_bid=bid, payout=proceeds,
                                       pnl=round(proceeds - pos["cost"], 2), closed=s.get("at")))
                    del open_pos[ticker]
                    continue
            if pos is not None or buys >= int(rules["max_buys"]):
                continue
            if window_gates(s, rules) or kept_blocks(s):
                continue
            ask = float(_num(s.get("yes_ask") if side == "YES" else s.get("no_ask")))
            per = ask + _fee15(ask)
            contracts = int(stake // per)
            if contracts < 1:
                continue
            open_pos[ticker] = {"ticker": ticker, "side": side, "ask": ask, "contracts": contracts,
                                "cost": round(contracts * per, 2), "p": _num(s.get("model_p")),
                                "minutes_left": _num(s.get("minutes_left")), "opened": s.get("at")}
            buys += 1
    still_open = []
    for ticker, pos in open_pos.items():
        res = results.get(ticker)
        if res not in ("yes", "no"):
            still_open.append(pos)
            continue
        payout = float(pos["contracts"]) if res == pos["side"].lower() else 0.0
        closed.append(dict(pos, exit="settled", result=res, payout=payout,
                           pnl=round(payout - pos["cost"], 2), closed=pos["opened"]))
    return {"tower": bot, "changes": dict(changes or {}), "rules": rules, "closed": closed,
            "open": still_open, "checks": len(by_check)}


def history_snaps(history: dict | None, bot: str) -> list[dict]:
    want = ("KXBTC15M", "KXETH15M") if bot == "btc15m" else None
    out = []
    for s in (history or {}).get("snapshots") or []:
        series = str((s or {}).get("series") or "")
        if not series.endswith("15M"):
            continue
        if (want and series in want) or (not want and series not in ("KXBTC15M", "KXETH15M")):
            out.append(s)
    return out


# ------------------------------------------------------------------ stats
def daily_pnl(closed: list[dict]) -> dict[str, float]:
    out: dict[str, float] = {}
    for row in closed:
        day = ct_day(row.get("closed") or row.get("opened"))
        if day is None or _num(row.get("pnl")) is None:
            continue
        out[day] = round(out.get(day, 0.0) + float(row["pnl"]), 2)  # losses count
    return dict(sorted(out.items()))


def split_days(days: list[str], check_fraction: float = CHECK_FRACTION) -> tuple[list[str], list[str]]:
    """Earlier days tune, later days check (a fresh test period)."""
    days = sorted(days)
    n_check = max(1, int(math.ceil(len(days) * check_fraction))) if days else 0
    return days[: len(days) - n_check], days[len(days) - n_check:]


def block_bootstrap_low(values: list[float], *, alpha: float = BASE_ALPHA, samples: int = BOOT_SAMPLES,
                        block: int | None = None, seed: int = 7) -> float | None:
    """Cautious lower bound of the mean, resampling runs of days so streaks stay together."""
    n = len(values)
    if n == 0:
        return None
    if n == 1:
        return float(values[0])
    block = max(1, int(block or round(n ** (1.0 / 3.0))))
    rng = random.Random(seed)
    means = []
    for _ in range(int(samples)):
        draw: list[float] = []
        while len(draw) < n:
            start = rng.randrange(n)
            draw.extend(values[(start + i) % n] for i in range(block))
        means.append(sum(draw[:n]) / n)
    means.sort()
    idx = max(0, min(len(means) - 1, int(math.floor(alpha * len(means)))))
    return round(means[idx], 4)


def adjusted_alpha(variants_tried: int, base: float = BASE_ALPHA) -> float:
    """Bonferroni: trying k variants makes each one prove itself at base / k."""
    return base / max(1, int(variants_tried))


def summarize(result: dict, *, variants_tried: int = 1) -> dict:
    daily = daily_pnl(result.get("closed") or [])
    tune, check = split_days(list(daily))
    check_vals = [daily[d] for d in check]
    alpha = adjusted_alpha(variants_tried)
    low = block_bootstrap_low(check_vals, alpha=alpha)
    closed = result.get("closed") or []
    check_set = set(check)
    check_rows = [r for r in closed if ct_day(r.get("closed") or r.get("opened")) in check_set]
    wins = sum(1 for r in check_rows if float(r.get("pnl") or 0) > 0)
    losses = sum(1 for r in check_rows if float(r.get("pnl") or 0) <= 0)
    total = round(sum(check_vals), 2)
    verdict = "worth a practice twin"
    if len(daily) < MIN_DAYS:
        verdict = f"not enough days ({len(daily)} of {MIN_DAYS})"
    elif len(check) < MIN_CHECK_DAYS:
        verdict = f"not enough check days ({len(check)} of {MIN_CHECK_DAYS})"
    elif low is None or low <= 0:
        verdict = "not proven (cautious low end at or below $0 a day)"
    return {
        "days": len(daily), "tune_days": tune, "check_days": check,
        "check_trades": len(check_rows), "check_wins": wins, "check_losses": losses,
        "check_pnl": total, "check_mean_day": round(total / len(check), 2) if check else None,
        "check_low_day": low, "alpha": round(alpha, 5), "variants_tried": int(variants_tried),
        "open_unsettled": len(result.get("open") or []), "verdict": verdict,
        "warning": ("many variants tried: needs a fresh test period before picking the best"
                    if variants_tried >= MANY_VARIANTS else ""),
    }


# ------------------------------------------------------------------ replay vs live
def gap_report(replay_closed: list[dict], live_closed: list[dict]) -> list[dict]:
    """Per Chicago day: live P&L, replay P&L, gap, trade counts (step 325)."""
    live = daily_pnl(live_closed)
    rep = daily_pnl(replay_closed)
    count = lambda rows, d: sum(1 for r in rows if ct_day(r.get("closed") or r.get("opened")) == d)  # noqa: E731
    out = []
    for day in sorted(set(live) | set(rep)):
        lt, rt = count(live_closed, day), count(replay_closed, day)
        gap = round(rep.get(day, 0.0) - live.get(day, 0.0), 2)
        per_trade = round(abs(gap) / max(1, lt, rt), 4)
        out.append({"day": day, "live_pnl": live.get(day, 0.0), "replay_pnl": rep.get(day, 0.0),
                    "gap": gap, "live_trades": lt, "replay_trades": rt, "gap_per_trade": per_trade,
                    "within_tolerance": per_trade <= REPLAY_GAP_TOLERANCE})
    return out


# ------------------------------------------------------------------ run log + report
def store_run(folder: str, run: dict, now: dt.datetime | None = None) -> dict:
    """Append one replay run (settings + summary) to the run log (step 341)."""
    os.makedirs(folder, exist_ok=True)
    row = {"at": (now or dt.datetime.now(dt.timezone.utc)).isoformat(timespec="seconds"),
           "paper_only": True, **run}
    with open(os.path.join(folder, RUNS_FILE), "a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, default=str) + "\n")
    return row


def runs(folder: str) -> list[dict]:
    return read_jsonl(os.path.join(folder, RUNS_FILE))


def variants_tried(folder: str, tower: str) -> int:
    """How many different rule variants were already replayed for this tower (step 336)."""
    keys = {json.dumps(r.get("changes") or {}, sort_keys=True) for r in runs(folder) if r.get("tower") == tower}
    return max(1, len(keys))


def report_text(run: dict) -> str:
    """Plain-words replay report (step 340)."""
    s = run.get("summary") or {}
    change = ", ".join(f"{k} = {v}" for k, v in (run.get("changes") or {}).items()) or "none (today's rules)"
    lines = [
        f"Replay: {run.get('tower')}",
        f"Rule change: {change}",
        f"Days replayed: {s.get('days', 0)}. Tune days: {len(s.get('tune_days') or [])}. "
        f"Check days: {len(s.get('check_days') or [])}.",
        f"On check days only: {s.get('check_trades', 0)} trades, {s.get('check_wins', 0)} won, "
        f"{s.get('check_losses', 0)} lost, total ${float(s.get('check_pnl') or 0):+.2f}.",
        "Cautious low end per day: " + ("n/a" if s.get("check_low_day") is None
                                        else f"${float(s['check_low_day']):+.2f}")
        + f" (variants tried: {s.get('variants_tried', 1)}).",
        f"Still open with no result: {s.get('open_unsettled', 0)} (not guessed).",
        f"Verdict: {s.get('verdict', '')}.",
    ]
    if s.get("warning"):
        lines.append(f"Warning: {s['warning']}.")
    gaps = run.get("gaps") or []
    if gaps:
        bad = [g for g in gaps if not g.get("within_tolerance")]
        lines.append(f"Replay vs live: {len(gaps)} days compared, {len(bad)} outside the tolerance.")
    lines.append("Paper only. A replay suggests; changing a tower stays Levi's call.")
    return "\n".join(lines)


def run_idea(name: str, *, root: str, runs_folder: str | None = None, save: bool = True) -> dict:
    """Replay one named idea against today's rules on the recorded days."""
    tower, changes = IDEAS[name]
    base, alt = replay_tower(tower, root=root), replay_tower(tower, root=root, changes=changes)
    folder = runs_folder or os.path.join(root, "replay-runs")
    out = {}
    for label, res in (("baseline", base), ("idea", alt)):
        tried = variants_tried(folder, tower) if save else 1
        run = {"tower": tower, "idea": name if label == "idea" else "baseline",
               "changes": res["changes"], "summary": summarize(res, variants_tried=tried)}
        if save:
            store_run(folder, run)
        out[label] = run
    return out


def live_account_path(root: str, tower: str) -> str:
    if tower == "btc15m":
        return os.path.join(root, "btc15m-signal", "paper_account.json")
    if tower == "commodity-15m":
        return os.path.join(root, "commodity-15m-paper", "paper_account.json")
    import new_towers
    row = next(r for r in new_towers.ACTIVE if r["id"] == tower)
    return os.path.join(root, row["folder"], "paper_account.json")


def replay_tower(tower: str, *, root: str, changes: dict | None = None) -> dict:
    if tower in ("btc15m", "commodity-15m"):
        history = engine.read_json(os.path.join(root, "kalshi_crypto_history.json")) or {}
        folder = "btc15m-signal" if tower == "btc15m" else "commodity-15m-paper"
        results = {**live_results(engine.read_json(os.path.join(root, folder, "paper_account.json"))),
                   **history_results(history)}
        return replay_windows(tower, history_snaps(history, tower), results, changes=changes)
    import new_towers
    row = next(r for r in new_towers.ACTIVE if r["id"] == tower)
    folder = os.path.join(root, row["folder"])
    spec = load_spec(folder)
    checks = engine_checks(read_jsonl(os.path.join(folder, "research.jsonl")))
    results = live_results(engine.read_json(os.path.join(folder, "paper_account.json")))
    return replay_engine(spec, checks, results, changes=changes,
                         config=engine.read_json(os.path.join(folder, "config.json")))


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Replay lab (paper only, read only)")
    ap.add_argument("what", help="tower id (more-15m, btc15m, commodity-15m, crypto-ladder, ...) or idea name")
    ap.add_argument("--set", action="append", default=[], help="what-if rule, key=value")
    ap.add_argument("--root", default=HERE)
    ap.add_argument("--no-save", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if args.what in IDEAS:
        out = run_idea(args.what, root=args.root, save=not args.no_save)
        print(json.dumps(out, indent=2) if args.json else
              report_text(out["baseline"]) + "\n\n" + report_text(out["idea"]))
        return 0
    changes = {}
    for item in args.set:
        key, _, value = item.partition("=")
        changes[key.strip()] = None if value.strip().lower() == "none" else (
            float(value) if value.replace(".", "", 1).isdigit() else value)
    res = replay_tower(args.what, root=args.root, changes=changes)
    folder = os.path.join(args.root, "replay-runs")
    tried = variants_tried(folder, args.what) if not args.no_save else 1
    run = {"tower": args.what, "changes": changes, "summary": summarize(res, variants_tried=tried)}
    if not changes:
        live = engine.read_json(live_account_path(args.root, args.what)) or {}
        run["gaps"] = gap_report(res["closed"], live.get("closed") or [])
    if not args.no_save:
        store_run(folder, run)
    print(json.dumps(run, indent=2, default=str) if args.json else report_text(run))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
