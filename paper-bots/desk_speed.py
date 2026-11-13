"""Speed: how long each tower takes from start to decision. Paper only, read-only.

Measuring never changes what a tower decides. The desk times each check from
the moment the script starts to the moment it prints its decision and exits,
and keeps the last ``KEEP`` times per tower in ``run_speed.json`` next to the
desk's run log. Nothing here is read by any tower.

Targets (plan step 379):
* 15-minute towers: median under 20 seconds.
* Sports towers: median under 45 seconds.
* Everything else: median under 60 seconds (a soft line, shown but not urgent).

The rule from the speed runbook: never trade speed for a lower edge bar. A
slow tower is made faster by reading less or reading smarter, never by
skipping a check that guards the edge.
"""
from __future__ import annotations

import json
import os
import statistics
import threading
import time

FILE = "run_speed.json"
KEEP = 120
FAST_15M = frozenset({"btc15m", "commodity-15m", "more-15m"})
SPORTS = frozenset({"sports-gap", "sports-sharp-lag", "poly-sports-lean", "soccer-tennis-lean", "point-spread",
                    "game-total", "player-props", "period-winner", "esports-match", "champions-league"})
TARGETS = {"15m": 20.0, "sports": 45.0, "other": 60.0}
_LOCK = threading.Lock()


def group_of(bot_id: str, category: str = "") -> str:
    if bot_id in FAST_15M:
        return "15m"
    if bot_id in SPORTS or str(category or "").lower() == "sports":
        return "sports"
    return "other"


def target_for(bot_id: str, category: str = "") -> float:
    return TARGETS[group_of(bot_id, category)]


def path_for(folder: str) -> str:
    return os.path.join(folder, FILE)


def _read(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def record(folder: str, bot_id: str, action: str, seconds: float, ok: bool, at: str = "",
           keep: int = KEEP) -> None:
    """Add one timing. Never raises: timing must never break a run."""
    try:
        sec = round(max(0.0, float(seconds)), 2)
        path = path_for(folder)
        with _LOCK:
            data = _read(path)
            rows = [r for r in data.get(bot_id) or [] if isinstance(r, dict)]
            rows.append({"at": at, "action": str(action or "run"), "sec": sec, "ok": bool(ok)})
            data[bot_id] = rows[-int(keep):]
            os.makedirs(folder, exist_ok=True)
            tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
            with open(tmp, "w", encoding="utf-8") as handle:
                json.dump(data, handle)
            os.replace(tmp, path)
    except Exception:  # noqa: BLE001
        return


class Timer:
    """``with Timer() as t: ...`` then ``t.seconds``. Uses a monotonic clock."""

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.start = None
        self.seconds = 0.0

    def __enter__(self):
        self.start = self.clock()
        return self

    def __exit__(self, *exc):
        self.seconds = self.clock() - self.start
        return False


def _pct(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    i = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
    return ordered[i]


def summary(folder: str, names: dict | None = None, categories: dict | None = None,
            waits: dict | None = None) -> dict:
    """Per tower: median, slowest 10% and last time against its target. Slowest first.

    ``waits`` (optional) maps tower id -> the Kalshi gateway's wait totals for it.
    """
    data = _read(path_for(folder))
    rows = []
    for bot_id, runs in data.items():
        secs = [float(r.get("sec") or 0) for r in runs or [] if isinstance(r, dict) and r.get("action") != "settle"]
        if not secs:
            continue
        target = target_for(bot_id, (categories or {}).get(bot_id, ""))
        median = round(statistics.median(secs), 1)
        p90 = round(_pct(secs, 0.9), 1)
        over = median > target
        name = (names or {}).get(bot_id) or bot_id
        wait = (waits or {}).get(bot_id) or {}
        rows.append({
            "bot": bot_id, "name": name, "group": group_of(bot_id, (categories or {}).get(bot_id, "")),
            "n": len(secs), "median_sec": median, "p90_sec": p90, "last_sec": round(secs[-1], 1),
            "target_sec": target, "over": over,
            "gateway_wait_avg_sec": wait.get("avg"), "gateway_wait_max_sec": wait.get("max"),
            "text": (f"median {median:g}s (target under {target:g}s), slowest 10% {p90:g}s, "
                     f"{len(secs)} checks"
                     + (f", Kalshi wait {float(wait['avg']):.2f}s a read" if wait.get("avg") is not None else "")
                     + (" — over target" if over else "")),
        })
    rows.sort(key=lambda r: (-(r["median_sec"] / r["target_sec"]), r["bot"]))
    slowest = rows[0] if rows else None
    return {
        "paper_only": True,
        "targets": dict(TARGETS),
        "rows": rows,
        "over": [r["bot"] for r in rows if r["over"]],
        "slowest": slowest["bot"] if slowest else None,
        "note": "Time from start to decision for each check. Faster never means a lower edge bar.",
    }


def report_lines(summary_row: dict, top: int = 5) -> list[str]:
    """Plain lines for a weekly or monthly review: slowest towers first."""
    lines = []
    for r in (summary_row.get("rows") or [])[:top]:
        lines.append(f"{r['name']}: {r['text']}")
    if not lines:
        lines.append("No timed checks yet.")
    return lines
