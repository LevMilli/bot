#!/usr/bin/env python3
"""Window history building. Support only: it buys nothing and holds no cash.

Once a minute it records the last 14 minutes of every Kalshi 15-minute window
the towers trade: top 5 book levels, the window's open price, and the result
with the settlement value (``recorder.py``). Once a day it writes a short
report: data gaps, 15-minute calibration, and a decision summary.

Tools (read-only, run by hand):
    python3 bot.py --day 2026-11-13 KXSOL15M      one day of one series (count + first rows)
    python3 bot.py --window KXSOL15M-26NOV131815-15
    python3 bot.py --chart KXSOL15M-26NOV131815-15 out.svg
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DESK_ROOT = os.path.dirname(HERE)
for path in (DESK_ROOT, HERE):
    if path not in sys.path:
        sys.path.insert(0, path)

import desk_data  # noqa: E402
import kalshi_shadow_tower as engine  # noqa: E402
import recorder as rec  # noqa: E402

STATE = "history_state.json"


def recordings_dir(here: str) -> str:
    """The volume copy when the desk has one (survives deploys), else the tower folder."""
    try:
        import pimp_desk

        durable = pimp_desk.settlement_dir()
    except Exception:  # noqa: BLE001
        durable = None
    if durable:
        return os.path.join(durable, os.path.basename(HERE), "recordings")
    return os.path.join(here, "recordings")


def shadow_research_files(desk_root: str = DESK_ROOT) -> dict[str, str]:
    """tower id -> research.jsonl for every trading shadow tower that has one."""
    try:
        import new_towers
    except Exception:  # noqa: BLE001
        return {}
    out = {}
    for row in new_towers.ACTIVE:
        if row.get("research"):
            continue
        path = os.path.join(desk_root, row["folder"], "research.jsonl")
        if os.path.exists(path) or os.path.exists(path + ".1"):
            out[row["id"]] = path
    return out


def nightly(folder: str, day: dt.date, research: dict[str, str] | None = None) -> dict:
    """Report for one finished UTC day: gaps, calibration, decision summary."""
    rows = desk_data.load_day(folder, day)
    # Results land a minute or more after the close: include the next day's results too.
    later = [r for r in desk_data.load_day(folder, day + dt.timedelta(days=1)) if r.get("kind") == "result"]
    scored = rows + later
    results = {r["ticker"]: r["result"] for r in scored if r.get("kind") == "result"}
    closes = {r["ticker"]: r["close"] for r in scored if r.get("close")}
    decisions = []
    for tower, path in sorted((research or {}).items()):
        for d in desk_data.read_research(path, tower):
            if not str(d.get("at") or "").startswith(day.isoformat()):
                continue
            close = desk_data.parse_at(closes.get(d["market"]))
            at = desk_data.parse_at(d["at"])
            if close and at:
                d["minutes_left"] = round((close - at).total_seconds() / 60.0, 2)
            decisions.append(d)
    towers = desk_data.tower_calibration(decisions, results)
    report = {
        "day": day.isoformat(), "paper_only": True,
        "quality": rec.quality_report(rows),
        "market_calibration_15m": rec.market_calibration(scored),
        "tower_calibration": towers,
        "calibration_flags": desk_data.flagged_towers(towers),
        "decisions": desk_data.daily_summary(decisions),
        "results": len(results),
    }
    out = os.path.join(os.path.dirname(folder), "reports")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, day.isoformat() + ".json"), "w", encoding="utf-8") as handle:
        json.dump(desk_data.strip_private(report), handle, indent=1)
    desk_data.prune_days(out, day)
    return report


def tools(argv: list[str], folder: str) -> int:
    if argv[0] == "--day" and len(argv) >= 2:
        rows = desk_data.load_day(folder, argv[1], argv[2] if len(argv) > 2 else None)
        print(json.dumps({"rows": len(rows), "first": rows[:3]}, indent=1))
        return 0
    if argv[0] == "--window" and len(argv) >= 2:
        print(json.dumps(rec.rebuild_window(folder, argv[1]), indent=1))
        return 0
    if argv[0] == "--chart" and len(argv) >= 3:
        window = rec.rebuild_window(folder, argv[1])
        fairs = []
        for tower, path in shadow_research_files().items():
            fairs.extend(r for r in desk_data.read_research(path, tower) if r["market"] == argv[1])
        trades = []
        for path in shadow_research_files().values():
            acct = engine.read_json(os.path.join(os.path.dirname(path), "paper_account.json")) or {}
            trades.extend(t for t in (acct.get("open") or []) + (acct.get("closed") or []) if t.get("ticker") == argv[1])
        with open(argv[2], "w", encoding="utf-8") as handle:
            handle.write(rec.window_chart_svg(window, fairs, trades))
        print(f"chart saved to {argv[2]}")
        return 0
    print("usage: bot.py [--day DATE [SERIES] | --window TICKER | --chart TICKER OUT.svg]")
    return 2


def main(argv: list[str] | None = None, *, here: str | None = None, get=None,
         now: dt.datetime | None = None, folder: str | None = None, research: dict | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    here = here or HERE
    folder = folder or recordings_dir(here)
    if argv and argv[0].startswith("--") and argv[0] != "--reset":
        return tools(argv, folder)
    if "--reset" in argv:  # nothing to reset: the building holds no cash and no positions
        print("reset paper account")
        return 0
    now = now or dt.datetime.now(dt.timezone.utc)
    os.makedirs(here, exist_ok=True)
    acct = os.path.join(here, "paper_account.json")
    state = engine.read_json(acct) or {}
    state.update({"cash": 0.0, "open": [], "closed": [], "paper_only": True, "shadow_only": True,
                  "live_orders": False, "stake_usd": 0.0, "research": True})
    rstate = engine.read_json(os.path.join(here, STATE)) or {}
    if get is None and rec.gateway_busy():
        state["checks"] = int(state.get("checks") or 0) + 1
        state["last_check"] = now.isoformat(timespec="seconds")
        engine.write_json(acct, state)
        print("CARD: Window history: the Kalshi door is backing off; sat this minute out so towers go first.")
        print("no trade")
        return 0
    rows, notes = rec.record(rstate, now, get or rec.gateway_get)
    rec.save(folder, rows, now)
    gone = rec.prune(folder, now.date())
    report = None
    yesterday = now.date() - dt.timedelta(days=1)
    if rstate.get("report_day") != yesterday.isoformat() and now.hour >= 1:
        try:
            report = nightly(folder, yesterday, shadow_research_files() if research is None else research)
        except Exception as exc:  # noqa: BLE001 - the report never stops the recording
            notes.append(f"nightly report failed ({type(exc).__name__})")
        rstate["report_day"] = yesterday.isoformat()
    engine.write_json(os.path.join(here, STATE), rstate)
    use = rec.usage(folder)
    state["checks"] = int(state.get("checks") or 0) + 1
    state["last_check"] = now.isoformat(timespec="seconds")
    state["recordings"] = dict(use, folder=folder)
    if report:
        state["last_report"] = {"day": report["day"], "quality_ok": report["quality"]["ok"],
                                "missing_minutes": report["quality"]["missing_minutes"],
                                "results": report["results"], "calibration_flags": report["calibration_flags"]}
    engine.write_json(acct, state)
    for note in notes[:5]:
        print(f"NOTE: {note}")
    books = sum(1 for r in rows if r.get("kind") == "book")
    results = sum(1 for r in rows if r.get("kind") == "result")
    line = (f"Window history: {books} books and {results} results saved "
            f"({rstate.get('reads_last_run', 0)} Kalshi reads); {use['days']} days on file "
            f"({use['bytes'] / 1e6:.1f} MB)")
    if gone:
        line += f"; removed {len(gone)} oldest days"
    if report:
        q = report["quality"]
        line += f". Yesterday: {q['windows']} windows, {q['missing_minutes']} missing minutes"
        if report["calibration_flags"]:
            line += "; calibration flag: " + report["calibration_flags"][0]
    print("CARD: " + line + ".")
    print("no trade")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
