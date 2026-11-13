"""Build the recorded More 15m day used by the replay tests.

It runs the live engine (kalshi_shadow_tower.run_tower) on made-up but
realistic quotes, a made-up Kalshi tape and made-up results, exactly the way
the live tower runs, and keeps what a live day leaves behind: research.jsonl
and paper_account.json. Paper only. Nothing here reads the network.

    python3 fixtures/replay/make_more15m_day.py [out_folder]
"""
from __future__ import annotations

import contextlib
import datetime as dt
import io
import math
import os
import random
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import kalshi_shadow_tower as engine  # noqa: E402

import replay_lab  # noqa: E402

SPEC = replay_lab.load_spec(os.path.join(ROOT, "more-15m-paper"))  # the live More 15m rules
SERIES = ("KXSOL15M", "KXXRP15M", "KXDOGE15M", "KXEURUSD15M")
COINS = {"KXSOL15M", "KXXRP15M", "KXDOGE15M"}
START = dt.datetime(2026, 11, 12, 15, 0, tzinfo=dt.timezone.utc)
WINDOWS = 6           # 90 minutes of 15-minute windows
SETTLE_LAG_MIN = 1    # Kalshi posts the result about a minute after the close


def _phi(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def world(seed: int = 11):
    """Per check: list of market quotes. Plus the results and the tape."""
    rng = random.Random(seed)
    checks, results, tape = [], {}, {}
    for w in range(WINDOWS):
        open_at = START + dt.timedelta(minutes=15 * w)
        close = open_at + dt.timedelta(minutes=15)
        paths = {}
        for s in SERIES:
            x, path = 0.0, []
            for _ in range(15):
                x += rng.gauss(0, 1)
                path.append(x)
            paths[s] = path
            results[f"{s}-{close:%y%b%d%H%M}".upper()] = "yes" if path[-1] >= 0 else "no"
        for minute in range(15):
            now = open_at + dt.timedelta(minutes=minute, seconds=20)
            left = 15 - minute - 20 / 60
            quotes = []
            for s in SERIES:
                ticker = f"{s}-{close:%y%b%d%H%M}".upper()
                x = paths[s][minute]
                p_yes = min(0.99, max(0.01, _phi(x / math.sqrt(max(0.25, left)))))
                # The market lags the model a bit, so some edges appear.
                mkt = min(0.97, max(0.03, p_yes + rng.gauss(0, 0.08)))
                yes_ask = round(min(0.99, mkt + 0.01), 2)
                yes_bid = round(max(0.01, mkt - 0.01), 2)
                label = f"{s[2:-3]} 15m up by {close:%H:%M} UTC"
                for side in ("yes", "no"):
                    ask = yes_ask if side == "yes" else round(1 - yes_bid, 2)
                    bid = yes_bid if side == "yes" else round(1 - yes_ask, 2)
                    q = {"ticker": ticker, "event": ticker, "side": side, "ask": ask, "bid": bid,
                         "fair": p_yes if side == "yes" else 1 - p_yes, "label": label,
                         "why": f"{s} test path"}
                    if s in COINS:
                        q["group"] = f"coins {'up' if side == 'yes' else 'down'} {close:%H:%M}"
                    if not (3.0 <= left <= 14.0):
                        q["log_only"] = True
                        q["log_reason"] = f"{left:.1f} min left; buys only with 3-14 min left"
                    quotes.append(q)
                    tape[(ticker, side, now.isoformat())] = rng.choice((0, 5, 40, 200, 500))
            checks.append({"at": now, "quotes": quotes, "close": close})
    return checks, results, tape


def build(out: str, seed: int = 11) -> dict:
    checks, results, tape = world(seed)
    closes = {}
    for c in checks:
        for q in c["quotes"]:
            closes[q["ticker"]] = c["close"]
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)
    engine.write_json(os.path.join(out, "config.json"), {
        "paper_only": True, "live_orders": False, "shadow_only": True, "venue_min_edge": 0.05,
        "stake_usd": 25, "starter_cash": 500, "max_open": 4})
    for c in checks:
        now = c["at"]

        def fetch(ticker, _now=now):
            if _now >= closes[ticker] + dt.timedelta(minutes=SETTLE_LAG_MIN):
                return {"result": results[ticker]}
            return {"result": ""}

        def live_tape(ticker, _now, _key=now.isoformat(), _c=c):
            rows = []
            for q in _c["quotes"]:
                if q["ticker"] != ticker:
                    continue
                vol = tape[(ticker, q["side"], _key)]
                yes = q["ask"] if q["side"] == "yes" else round(1 - q["ask"], 4)
                rows.append({"yes_price_dollars": yes, "count": vol})
            return rows

        with contextlib.redirect_stdout(io.StringIO()):
            engine.run_tower(SPEC, out, None, now=now, fetch=fetch, quotes=[dict(q) for q in c["quotes"]],
                             tape=live_tape)
    # Let the last windows settle, as the next live checks would.
    state = engine.read_json(os.path.join(out, "paper_account.json"))
    engine.settle_open(state, checks[-1]["close"] + dt.timedelta(minutes=5),
                       fetch=lambda t: {"result": results[t]})
    engine.write_json(os.path.join(out, "paper_account.json"), state)
    engine.write_json(os.path.join(out, "results.json"), results)
    return state


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "more-15m-day")
    s = build(target)
    print(f"closed {len(s['closed'])}, open {len(s['open'])}, cash {s['cash']}")
