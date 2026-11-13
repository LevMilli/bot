"""Scorekeeper: grade each bot on its paper record. Suggests only, never acts.

Per closed trade, P&L is after fees and after the desk's fill tax (1 cent a
contract, ``desk_profit.FILL_ADVERSE_TAX``). With at least 50 trades it takes a
95% range for the average trade (mean ± 1.96 · sd / √n):

- promote: even the low end of the range is above $0
- keep:    the average is above $0, but the low end is not
- pause:   the average is $0 or worse, but the high end is still above $0
- retire:  even the high end is below $0 (clearly losing)

Under 50 trades the grade is "too few".

Promotion card (B14). For every practice (shadow) tower in ``new_towers.py`` it
shows the count toward 50 results, the average result after fees, a cautious
low end (the 95% range's low end) and a "ready to review" flag at 50. Ready
only means Levi can now look; promotion still needs his OK. Losses count.
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


def promotion_row(tower_id: str, name: str, pnls: list[float], *, paused: bool = False,
                  min_n: int = MIN_N) -> dict:
    """One line of the 50-result card. pnls: $ per closed trade after fees and fill tax."""
    g = grade(pnls, min_n)
    n = g["n"]
    ready = n >= min_n
    if not ready:
        verdict = "counting"
    elif g["low"] is not None and g["low"] > 0:
        verdict = "looks good"
    elif (g["avg"] or 0) > 0:
        verdict = "mixed"
    else:
        verdict = "not good"
    return {"id": tower_id, "name": name, "n": n, "to_go": max(0, min_n - n), "avg": g["avg"],
            "low": g["low"], "total": g["total"], "ready_to_review": ready, "verdict": verdict,
            "paused": paused, "needs_levi_ok": True}


def promotion(rows: list[dict], now: dt.datetime, min_n: int = MIN_N) -> dict:
    rows = sorted(rows, key=lambda r: (not r["ready_to_review"], -r["n"], r["id"]))
    return {"updated": now.isoformat(timespec="seconds"), "min_n": min_n, "suggest_only": True,
            "after_fees": True, "auto_promote": False, "towers": rows,
            "ready": [r["id"] for r in rows if r["ready_to_review"]]}


def promotion_card(promo: dict) -> str:
    rows = promo.get("towers") or []
    if not rows:
        return "Promotion card: no practice towers yet"
    ready = [r for r in rows if r["ready_to_review"]]
    line = f"Promotion card: {len(ready)} of {len(rows)} practice towers at {promo['min_n']} results"
    if ready:
        bits = [f"{r['id']} {r['verdict']} (avg {r['avg']:+.2f}, low {r['low']:+.2f})" for r in ready[:3]]
        line += "; ready to review (needs Levi's OK): " + ", ".join(bits)
        if len(ready) > 3:
            line += f" and {len(ready) - 3} more"
    waiting = [r for r in rows if not r["ready_to_review"] and r["n"]]
    if waiting:
        line += "; closest: " + ", ".join(f"{r['id']} {r['n']}/{promo['min_n']}" for r in waiting[:2])
    return line
