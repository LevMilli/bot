"""Freshness inspector: is every building running on time, and how old were the
prices behind each buy? Display only. It never blocks a buy.

Building check (every building, research ones too):

- ``on time``: the last run is inside the expected gap.
- ``late``: a timer building whose last run is older than 3 gaps (at least gap + 30 min).
  Clock-window buildings (Kalshi S&P, Sized Kalshi) are late after 4 days, so a
  weekend is not flagged.
- ``never ran``, ``paused``, ``last run failed`` and ``no timer`` are shown as they are.

Price-age check (trading towers): for each open or closed trade that stored both
the time its price was read (``price_at``) and the buy time (``opened``), the gap
between them. Trades that stored only one time are counted as "not stored", not
guessed. A price read more than 60 seconds before the buy is flagged ``stale``.
"""
from __future__ import annotations

import datetime as dt

STALE_QUOTE_SEC = 60
CLOCK_LATE_SEC = 4 * 86400
LATE_GAPS = 3
LATE_GRACE_SEC = 1800


def parse_when(text):
    text = str(text or "").strip()
    if not text:
        return None
    if text.endswith(" UTC"):
        text = text[:-4].replace(" ", "T") + "+00:00"
    try:
        when = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=dt.timezone.utc)
    return when


def late_after(every_sec) -> float | None:
    if not every_sec:
        return None
    gap = float(every_sec)
    return max(LATE_GAPS * gap, gap + LATE_GRACE_SEC)


def building(bot_id: str, name: str, run: dict | None, every_sec, clock: bool, paused: bool,
             now: dt.datetime, next_run: str = "") -> dict:
    run = run if isinstance(run, dict) else {}
    last = parse_when(run.get("at"))
    age = None if last is None else max(0.0, (now - last).total_seconds())
    limit = late_after(every_sec) if every_sec else (CLOCK_LATE_SEC if clock else None)
    if paused:
        status = "paused"
    elif last is None:
        status = "never ran" if (every_sec or clock) else "no timer"
    elif run.get("ok") is False:
        status = "last run failed"
    elif limit is not None and age > limit:
        status = "late"
    elif limit is None:
        status = "no timer"
    else:
        status = "on time"
    return {"id": bot_id, "name": name, "status": status,
            "last_run": last.isoformat(timespec="seconds") if last else "",
            "age_min": None if age is None else round(age / 60, 1),
            "every_sec": int(every_sec) if every_sec else None, "clock_window": bool(clock),
            "late_after_min": None if limit is None else round(limit / 60, 1),
            "next_run": next_run or ""}


def quote_ages(rows: list[dict]) -> dict:
    ages = []
    missing = 0
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        priced = parse_when(row.get("price_at") or row.get("priced_at"))
        opened = parse_when(row.get("opened") or row.get("entry_time"))
        if priced is None or opened is None:
            missing += 1
            continue
        ages.append(max(0.0, (opened - priced).total_seconds()))
    stale = sum(1 for a in ages if a > STALE_QUOTE_SEC)
    return {"checked": len(ages), "not_stored": missing, "stale": stale,
            "max_sec": round(max(ages), 1) if ages else None,
            "avg_sec": round(sum(ages) / len(ages), 1) if ages else None}


def inspect(buildings: list[dict], trades: dict, now: dt.datetime) -> dict:
    """buildings: rows from ``building``. trades: {bot_id: [raw trade rows]}."""
    counts: dict = {}
    for b in buildings:
        counts[b["status"]] = counts.get(b["status"], 0) + 1
    quotes = {tid: quote_ages(rows) for tid, rows in sorted(trades.items())}
    return {"updated": now.isoformat(timespec="seconds"), "display_only": True,
            "stale_quote_sec": STALE_QUOTE_SEC, "buildings": buildings, "counts": counts,
            "quotes": quotes}


def card(body: dict) -> str:
    total = len(body["buildings"])
    c = body["counts"]
    line = f"{c.get('on time', 0)} of {total} buildings ran on time"
    late = [b for b in body["buildings"] if b["status"] == "late"]
    failed = [b for b in body["buildings"] if b["status"] == "last run failed"]
    if late:
        line += ". Late: " + ", ".join(f"{b['name']} ({b['age_min']:.0f} min)" for b in late[:5])
    if failed:
        line += ". Last run failed: " + ", ".join(b["name"] for b in failed[:5])
    if c.get("never ran"):
        line += f". Never ran: {c['never ran']}"
    q = body["quotes"]
    checked = sum(v["checked"] for v in q.values())
    stale = sum(v["stale"] for v in q.values())
    missing = sum(v["not_stored"] for v in q.values())
    line += f". Price age at buy: {checked} trades checked, {stale} older than {body['stale_quote_sec']}s"
    if missing:
        line += f", {missing} did not store a separate price time"
    return line + "."
