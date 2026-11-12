"""Tower health watchdog. Paper only, read-only.

Every timer pass the desk records each tower's last run in ``pimp-runs.json``.
Nobody was watching those rows, so a tower could time out or fail for hours
without a word in Discord. ``check(root)`` reads them once per pass and returns
short audit notes for three problems:

* **Timed out:** the run was stopped at its time limit ("Stopped after Ns").
* **Failing:** two finished checks in a row did not end cleanly.
* **Stalled:** no finished check for much longer than its timer gap
  (4x the gap, at least 30 minutes), while the desk timer itself is alive.
  The stall clock starts when the watchdog starts watching (and restarts after
  the timer was down 10+ minutes), so a redeploy does not flag every tower.

Each problem posts once. The note does not repeat every pass; when the tower
finishes a clean check again, one "healthy again" note closes it out. State
lives in ``pimp-watchdog.json`` next to the other desk files.
"""
from __future__ import annotations

import datetime as dt
import json
import os

STATE_FILE = "pimp-watchdog.json"
FAIL_STREAK = 2
STALE_MULT = 4
STALE_MIN_SEC = 30 * 60
RESTART_GAP_SEC = 10 * 60


def _when(text: str):
    text = str(text or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S UTC",):
        try:
            return dt.datetime.strptime(text, fmt).replace(tzinfo=dt.timezone.utc)
        except ValueError:
            pass
    try:
        when = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=dt.timezone.utc)


def _load(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(path: str, data: dict) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")
    os.replace(tmp, path)


def _last_line(summary: str) -> str:
    lines = [ln.strip() for ln in str(summary or "").splitlines() if ln.strip()]
    if not lines:
        return "no output"
    line = lines[-1]
    return line if len(line) <= 140 else line[:137] + "..."


def _gaps(desk, root: str, now: dt.datetime) -> dict:
    """Timer gap in seconds for each tower on an every-N-seconds timer."""
    gaps = {}
    for slot in getattr(desk, "AUTO", ()):
        if "every_sec" not in slot:
            continue
        gap = float(slot["every_sec"])
        try:
            if slot["id"] == "sports-gap":
                gap = desk._sports_auto_gap_sec(root, gap, now=now)
            elif slot["id"] == "memecoin":
                gap = desk._meme_auto_gap_sec(root, gap)
            elif slot["id"] == "commodity-15m":
                gap = desk._commodity_auto_gap_sec(root, gap)
        except Exception:  # noqa: BLE001 - fall back to the base gap
            pass
        gaps[slot["id"]] = max(gaps.get(slot["id"], 0.0), float(gap))
    return gaps


def check(desk, root: str, now: dt.datetime | None = None, timer_alive: bool = True) -> list[str]:
    """Return new watchdog notes (maybe empty). Saves what it has already said."""
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=dt.timezone.utc)
    runs = desk._load_runs(root) or {}
    names = {b["id"]: b.get("name") or b["id"] for b in getattr(desk, "BOTS", ())}
    gaps = _gaps(desk, root, now)
    path = os.path.join(root, STATE_FILE)
    state = _load(path)
    meta = state.get("_meta") if isinstance(state.get("_meta"), dict) else {}
    last = _when(meta.get("last_check"))
    since = _when(meta.get("since"))
    if since is None or last is None or (now - last).total_seconds() > RESTART_GAP_SEC:
        since = now  # fresh start or the timer was down: give towers a full gap first
    state["_meta"] = {"since": since.isoformat(timespec="seconds"), "last_check": now.isoformat(timespec="seconds")}
    notes = []
    for bot_id, gap in sorted(gaps.items()):
        if bot_id not in names:
            continue
        try:
            if desk.bot_paused(root, bot_id):
                continue
        except Exception:  # noqa: BLE001
            pass
        name = names[bot_id]
        row = runs.get(bot_id) if isinstance(runs.get(bot_id), dict) else None
        mine = state.get(bot_id) if isinstance(state.get(bot_id), dict) else {}
        said = set(mine.get("said") or [])
        if row:
            at = str(row.get("at") or "")
            if at and at != mine.get("seen"):
                mine["seen"] = at
                summary = str(row.get("summary") or "")
                timed_out = summary.startswith("Stopped after")
                if row.get("ok"):
                    if said:
                        notes.append(f"Watchdog: {name} is healthy again. Its last check finished cleanly.")
                    said = set()
                    mine["fails"] = 0
                else:
                    mine["fails"] = int(mine.get("fails") or 0) + 1
                    if timed_out and "timeout" not in said:
                        first = summary.splitlines()[0]
                        notes.append(f"Watchdog: {name} hit its time limit ({first.lower().rstrip('.')}). "
                                     "The timer tries again next turn.")
                        said.add("timeout")
                    elif (not timed_out and mine["fails"] >= FAIL_STREAK and "failing" not in said):
                        notes.append(f"Watchdog: {name} failed {mine['fails']} checks in a row. "
                                     f"Last line: {_last_line(summary)}")
                        said.add("failing")
        when = _when(row.get("at")) if row else None
        limit = max(STALE_MULT * gap, STALE_MIN_SEC)
        watched = (now - since).total_seconds()
        if timer_alive and when is not None and (now - when).total_seconds() > limit and watched > limit:
            if "stalled" not in said:
                mins = int((now - when).total_seconds() // 60)
                notes.append(f"Watchdog: {name} has not finished a check in {mins}m "
                             f"(its timer runs about every {int(gap // 60) or 1}m).")
                said.add("stalled")
        elif "stalled" in said and when is not None:
            said.discard("stalled")
        mine["said"] = sorted(said)
        state[bot_id] = mine
    _save(path, state)
    return notes
