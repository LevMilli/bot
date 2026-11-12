#!/usr/bin/env python3
"""Scorekeeper building. Support only: it buys nothing and holds no cash.

Grades every desk bot on its paper record (``score_model.py``) and writes
``scorecard.json``. It only suggests promote / keep / pause / retire; it never
changes a bot.
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

import score_model as sm  # noqa: E402
import kalshi_shadow_tower as engine  # noqa: E402


def histories(root: str, now: dt.datetime) -> dict:
    import new_towers
    import pimp_desk

    day = now.astimezone(pimp_desk.CT).date()
    runs = pimp_desk._load_runs(root)
    out = {}
    for spec in pimp_desk.BOTS:
        if spec["id"] in new_towers.RESEARCH:
            continue
        try:
            view = pimp_desk._bot_view(spec, root, runs, day)
        except Exception:  # one bad state file must not stop the card
            continue
        out[spec["id"]] = (spec["name"], view.get("history") or [])
    return out


def extra_split(root: str, fill_tax: float) -> dict:
    """{bot_id: {extra: {n, avg}, normal: {n, avg}}} from engine towers' closed trades.

    Trades opened in an extra slot carry ``extra: true``. P&L here is after fees
    and the same 1-cent-a-contract fill tax the grades use.
    """
    import new_towers

    out = {}
    for tid, row in new_towers.BY_ID.items():
        if tid in new_towers.RESEARCH:
            continue
        state = engine.read_json(os.path.join(root, row["folder"], "paper_account.json")) or {}
        split = {"extra": [], "normal": []}
        for trade in state.get("closed") or []:
            pnl = engine.num(trade.get("pnl"))
            if pnl is None:
                continue
            pnl -= fill_tax * float(trade.get("contracts") or 0)
            split["extra" if trade.get("extra") else "normal"].append(pnl)
        if split["extra"]:
            out[tid] = {k: {"n": len(v), "avg": round(sum(v) / len(v), 4) if v else None}
                        for k, v in split.items()}
    return out


def main(argv: list[str] | None = None, *, root: str | None = None, now: dt.datetime | None = None) -> int:
    import desk_profit

    root = root or DESK_ROOT
    now = now or dt.datetime.now(dt.timezone.utc)
    here = os.path.join(root, os.path.basename(HERE))
    os.makedirs(here, exist_ok=True)
    acct = os.path.join(here, "paper_account.json")
    state = engine.read_json(acct) or {}
    state.update({"cash": 0.0, "open": [], "closed": [], "paper_only": True, "shadow_only": True,
                  "live_orders": False, "stake_usd": 0.0, "research": True})

    def pnls_of(rows):
        return desk_profit._history_pnls(rows, window_days=sm.ALL_TIME_DAYS, now=now,
                                         fill_tax=desk_profit.FILL_ADVERSE_TAX)

    body = sm.run(histories(root, now), now, pnls_of=pnls_of)
    body["extra_slots"] = extra_split(root, desk_profit.FILL_ADVERSE_TAX)
    engine.write_json(os.path.join(here, "scorecard.json"), body)
    state["checks"] = int(state.get("checks") or 0) + 1
    state["last_check"] = now.isoformat(timespec="seconds")
    state["counts"] = body["counts"]
    engine.write_json(acct, state)
    print("CARD: " + sm.card(body))
    print("no trade")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
