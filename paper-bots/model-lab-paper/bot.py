#!/usr/bin/env python3
"""Model lab building. Research only: it buys nothing and holds no cash.

Scores new model ideas (blended swings, fatter tails, time of day, jump guard,
book imbalance, BTC pull, exit rules) on real Kalshi 15-minute windows, using
``model_lab.py`` and the shared math in ``shared_models.py``. Writes
``model_lab.json``. No tower reads it to trade.
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

import model_lab as ml  # noqa: E402
import kalshi_shadow_tower as engine  # noqa: E402

CANDLES = "https://api.exchange.coinbase.com/products/{product}/candles?granularity=60"
UA = {"User-Agent": "paper-bot/1.0 (model-lab)"}


def candles(product: str):
    return engine.public_json(CANDLES.format(product=product), headers=UA) or []


def main(argv: list[str] | None = None, *, root: str | None = None, candles_fetch=None, markets_fetch=None,
         market_fetch=None, now: dt.datetime | None = None) -> int:
    root = root or DESK_ROOT
    now = now or dt.datetime.now(dt.timezone.utc)
    here = os.path.join(root, os.path.basename(HERE))
    os.makedirs(here, exist_ok=True)
    acct = os.path.join(here, "paper_account.json")
    state = engine.read_json(acct) or {}
    state.update({"cash": 0.0, "open": [], "closed": [], "paper_only": True, "shadow_only": True,
                  "live_orders": False, "stake_usd": 0.0, "research": True})
    out_path = os.path.join(here, "model_lab.json")
    body = ml.run(engine.read_json(out_path) or {}, now, candles=candles_fetch or candles,
                  open_markets=markets_fetch or engine.kalshi_open_markets,
                  market=market_fetch or engine.kalshi_market)
    engine.write_json(out_path, body)
    state["checks"] = int(state.get("checks") or 0) + 1
    state["last_check"] = now.isoformat(timespec="seconds")
    state["scored"] = len(body["scored"])
    engine.write_json(acct, state)
    for note in body.get("notes") or []:
        print(f"NOTE: {note}")
    print("CARD: " + ml.card(body))
    print("no trade")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
