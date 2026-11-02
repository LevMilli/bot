"""
Shared US high-impact calendar cache (ForexFactory this-week JSON).

Mains use last-good so a brief CDN blip does not fail-closed every BTC window.
Refresh at most every REFRESH_SEC. Paper / read-only.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
DESK_ROOT = os.path.dirname(HERE)
CACHE_NAME = "ff_calendar_cache.json"
FF_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
UA = {"User-Agent": "paper-bot/1.0 (calendar-cache read-only)"}
REFRESH_SEC = 15 * 60


def cache_path(root: str | None = None) -> str:
    base = root or DESK_ROOT
    return os.path.join(base, "helpers", CACHE_NAME)


def _empty() -> dict:
    return {
        "paper_only": True,
        "fetched_at": None,
        "source": FF_URL,
        "events": [],
        "last_error": None,
    }


def load_raw(root: str | None = None) -> dict:
    path = cache_path(root)
    if not os.path.exists(path):
        return _empty()
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            return _empty()
    except (OSError, json.JSONDecodeError):
        return _empty()
    base = _empty()
    base.update({k: data.get(k, base[k]) for k in base})
    if not isinstance(base.get("events"), list):
        base["events"] = []
    return base


def save_raw(state: dict, root: str | None = None) -> None:
    path = cache_path(root)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    state = dict(state)
    state["paper_only"] = True
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
        handle.write("\n")
    os.replace(tmp, path)


def _fetch() -> list:
    req = urllib.request.Request(FF_URL, headers=UA)
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if not isinstance(data, list):
        raise ValueError("calendar payload not a list")
    return data


def refresh_if_stale(root: str | None = None, *, force: bool = False) -> dict:
    state = load_raw(root)
    now = time.time()
    fetched = state.get("fetched_at")
    age = None
    try:
        if fetched is not None:
            age = now - float(fetched)
    except (TypeError, ValueError):
        age = None
    if not force and age is not None and age < REFRESH_SEC and state.get("events"):
        return state
    try:
        events = _fetch()
        state = {
            "paper_only": True,
            "fetched_at": now,
            "source": FF_URL,
            "events": events,
            "last_error": None,
        }
        save_raw(state, root)
    except Exception as exc:  # noqa: BLE001
        state["last_error"] = type(exc).__name__
        # Keep last-good events; only stamp error.
        if state.get("events"):
            save_raw(state, root)
        else:
            save_raw(state, root)
    return state


def load_ff_calendar(root: str | None = None) -> list | None:
    """
    Return event list, preferring fresh/last-good cache.
    None only when we have never successfully fetched anything.
    """
    state = refresh_if_stale(root)
    events = state.get("events") or []
    if not events:
        return None
    return list(events)


def self_check() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        # Seed last-good without network.
        save_raw(
            {
                "paper_only": True,
                "fetched_at": time.time(),
                "source": FF_URL,
                "events": [{"country": "USD", "impact": "High", "title": "Test", "date": "2026-11-02T15:00:00-04:00"}],
                "last_error": None,
            },
            tmp,
        )
        # Point cache under tmp/helpers by using root=tmp
        os.makedirs(os.path.join(tmp, "helpers"), exist_ok=True)
        # rewrite into helpers subpath via cache_path
        seeded = load_raw(tmp)
        assert seeded.get("events")
        # load_ff should return events without needing network if fresh
        ev = load_ff_calendar(tmp)
        assert ev is not None and len(ev) == 1


if __name__ == "__main__":
    self_check()
    print("helpers.calendar_cache self_check ok")
