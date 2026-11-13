"""The Discord bot's outside watch on the trading service. Paper only, read-only.

When the trading service runs the timer, nothing inside it can say the timer
died: a dead timer posts nothing. The Discord bot is a separate service, so it
asks the trading service's public ``/healthz`` page once a minute and posts to
the audit channel when:

* the desk timer has missed two passes (last pass more than 150 seconds old),
* the trading service stopped answering (two asks in a row), or
* the two services have run different builds for more than 10 minutes.

Each problem posts once, and one "back to normal" note closes it. The latest
answer is kept in memory so the bot's ``/health.json`` page can show it.
``/healthz`` needs no key and shows no secrets.
"""
from __future__ import annotations

import datetime as dt
import json
import urllib.request

PASS_GAP_S = 60
MISSED_PASSES = 2
DOWN_STREAK = 2
BUILD_SKEW_S = 10 * 60

LAST = {"checked_at": None, "service_ok": None, "last_pass_at": None, "last_pass_age_s": None,
        "service_build": None, "offline": None}


def fetch_health(base_url: str, timeout: float = 8.0) -> dict:
    req = urllib.request.Request(base_url.rstrip("/") + "/healthz", headers={"User-Agent": "pimp-bot-pulse"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def _iso(now: dt.datetime) -> str:
    return now.isoformat(timespec="seconds")


def _parse(text):
    try:
        when = dt.datetime.fromisoformat(str(text))
    except (TypeError, ValueError):
        return None
    return when if when.tzinfo else when.replace(tzinfo=dt.timezone.utc)


def check(base_url: str, state: dict, my_build: dict | None = None, now=None, fetch=fetch_health) -> list:
    """One ask. Updates ``state`` in place and returns new audit notes."""
    now = now or dt.datetime.now(dt.timezone.utc)
    notes = []
    LAST["checked_at"] = _iso(now)
    try:
        body = fetch(base_url) or {}
        ok = bool(body.get("ok"))
    except Exception:  # noqa: BLE001 - a failed ask is what this watch is for
        body, ok = {}, False
    LAST["service_ok"] = ok
    if not ok:
        state["down"] = int(state.get("down") or 0) + 1
        LAST["offline"] = state["down"] >= DOWN_STREAK
        if state["down"] >= DOWN_STREAK and not state.get("down_said"):
            state["down_said"] = True
            notes.append("Desk watch: the trading service is not answering. The city will show the desk as offline.")
        return notes
    if state.get("down_said"):
        notes.append("Desk watch: the trading service is answering again.")
    state["down"] = 0
    state["down_said"] = False
    LAST["offline"] = False
    age = body.get("last_pass_age_s")
    LAST["last_pass_at"] = body.get("last_pass_at")
    LAST["last_pass_age_s"] = age
    if isinstance(age, (int, float)):
        late = age > MISSED_PASSES * PASS_GAP_S + 30
        if late and not state.get("late_said"):
            state["late_said"] = True
            notes.append(f"Desk watch: the desk timer has missed at least {MISSED_PASSES} passes. "
                         f"The last pass finished {int(age // 60)}m {int(age % 60)}s ago.")
        elif not late and state.get("late_said"):
            state["late_said"] = False
            notes.append("Desk watch: the desk timer is running again.")
    theirs = (body.get("build") or {}).get("sha") or ""
    mine = (my_build or {}).get("sha") or ""
    LAST["service_build"] = theirs or None
    if theirs and mine and theirs != mine:
        since = _parse(state.get("skew_since")) or now
        state["skew_since"] = _iso(since)
        if (now - since).total_seconds() > BUILD_SKEW_S and not state.get("skew_said"):
            state["skew_said"] = True
            notes.append(f"Desk watch: the Discord bot runs build {mine} and the trading service runs {theirs}, "
                         "for more than 10 minutes. One deploy may have failed.")
    else:
        if state.get("skew_said"):
            notes.append("Desk watch: both services run the same build again.")
        state.pop("skew_since", None)
        state["skew_said"] = False
    return notes


def snapshot() -> dict:
    """What the bot last heard from the trading service, for ``/health.json``."""
    return dict(LAST)
