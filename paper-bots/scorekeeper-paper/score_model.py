"""Scorekeeper: grade each bot on its paper record. Suggests only, never acts.

Per closed trade, P&L is after fees and after the desk's fill tax (1 cent a
contract, ``desk_profit.FILL_ADVERSE_TAX``). With at least 50 trades it takes a
95% range for the average trade (mean ± 1.96 · sd / √n):

- promote: even the low end of the range is above $0
- keep:    the average is above $0, but the low end is not
- pause:   the average is $0 or worse, but the high end is still above $0
- retire:  even the high end is below $0 (clearly losing)

Under 50 trades the grade is "too few".
"""
from __future__ import annotations

import datetime as dt
import math

MIN_N = 50
Z95 = 1.96
ALL_TIME_DAYS = 36500
ORDER = {"promote": 0, "keep": 1, "pause": 2, "retire": 3, "too few": 4}


def grade(pnls: list[float], min_n: int = MIN_N) -> dict:
    n = len(pnls)
    out = {"n": n, "avg": None, "low": None, "high": None, "total": round(sum(pnls), 2), "grade": "too few"}
    if n == 0:
        return out
    avg = sum(pnls) / n
    out["avg"] = round(avg, 4)
    out["hit_rate"] = round(sum(1 for p in pnls if p > 0) / n, 3)
    if n < 2:
        return out
    sd = math.sqrt(sum((p - avg) ** 2 for p in pnls) / (n - 1))
    half = Z95 * sd / math.sqrt(n)
    out["low"], out["high"] = round(avg - half, 4), round(avg + half, 4)
    if n < min_n:
        return out
    if avg - half > 0:
        out["grade"] = "promote"
    elif avg > 0:
        out["grade"] = "keep"
    elif avg + half > 0:
        out["grade"] = "pause"
    else:
        out["grade"] = "retire"
    return out


def run(histories: dict, now: dt.datetime, *, pnls_of, min_n: int = MIN_N) -> dict:
    """histories: {bot_id: (name, history rows)}. pnls_of(rows) -> taxed pnls."""
    bots = []
    for bot_id, (name, rows) in histories.items():
        row = grade(pnls_of(rows), min_n)
        row.update({"id": bot_id, "name": name})
        bots.append(row)
    bots.sort(key=lambda r: (ORDER[r["grade"]], -(r["avg"] or 0.0), r["id"]))
    counts = {g: sum(1 for r in bots if r["grade"] == g) for g in ORDER}
    return {"updated": now.isoformat(timespec="seconds"), "min_n": min_n, "suggest_only": True,
            "after_fees": True, "bots": bots, "counts": counts}


def card(body: dict) -> str:
    c = body["counts"]
    graded = len(body["bots"]) - c["too few"]
    head = f"{graded} of {len(body['bots'])} bots have {body['min_n']}+ trades"
    parts = [f"{c[g]} {g}" for g in ("promote", "keep", "pause", "retire") if c[g]]
    line = head + (": " + ", ".join(parts) if parts else "")
    extra = body.get("extra_slots") or {}
    if extra:
        n = sum(v["extra"]["n"] for v in extra.values())
        bits = [f"{tid} {v['extra']['avg']:+.2f} vs {v['normal']['avg']:+.2f}" if v["normal"]["avg"] is not None
                else f"{tid} {v['extra']['avg']:+.2f}" for tid, v in sorted(extra.items())]
        line += f". Extra-slot trades closed: {n} (avg $ per trade, extra vs normal: {'; '.join(bits)})"
    return line
