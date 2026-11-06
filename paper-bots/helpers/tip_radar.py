"""
Tip Radar insight helper — lists tip-soon sports windows for mains (observe-only).

Never places paper fills. Never softens venue min_edge. Paper / helper-only.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone

from helpers import HELPER_ONLY, PAPER_ONLY, assert_helper_only

DIGEST_NAME = "tip_radar_digest.json"
DESK_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def digest_path(root: str | None = None) -> str:
    base = root or DESK_ROOT
    return os.path.join(base, "helpers", DIGEST_NAME)


def build_digest(games: list | None = None, *, now: datetime | None = None) -> dict:
    """Signal-only tip radar board. `games` optional list of {league,tip_in_min,ticker}."""
    assert_helper_only("tip_radar")
    assert PAPER_ONLY and HELPER_ONLY
    now = now or datetime.now(timezone.utc)
    rows = []
    for g in games or []:
        if not isinstance(g, dict):
            continue
        try:
            tip = float(g.get("tip_in_min"))
        except (TypeError, ValueError):
            continue
        if tip < 0 or tip > 180:
            continue
        rows.append({
            "league": str(g.get("league") or "")[:20],
            "ticker": str(g.get("ticker") or "")[:40],
            "tip_in_min": round(tip, 1),
            "priority": "T-5" if tip <= 5 else ("T-15" if tip <= 15 else "T-180"),
        })
    rows.sort(key=lambda r: float(r["tip_in_min"]))
    return {
        "helper": "tip_radar",
        "at": now.isoformat(),
        "paper_only": True,
        "may_place_alone": False,
        "floors_locked": True,
        "n": len(rows),
        "games": rows[:40],
        "note": "Observe-only tip radar. Never waives sports 0.06 floor.",
    }


def write_digest(root: str | None = None, games: list | None = None) -> dict:
    digest = build_digest(games)
    path = digest_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(digest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)
    return digest


def games_from_quote_cache(
    root: str | None = None,
    *,
    now: datetime | None = None,
    horizon_min: float = 180.0,
) -> list[dict]:
    """Offline tip-soon list from sports-gap quote_cache.json (no network)."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    path = os.path.join(root or DESK_ROOT, "sports-gap-paper", "quote_cache.json")
    games: list[dict] = []
    if not os.path.isfile(path):
        return games
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return games
    if not isinstance(data, dict):
        return games
    for key, payload in data.items():
        if not isinstance(payload, dict):
            continue
        body = payload.get("body")
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
        if not isinstance(body, dict):
            continue
        league = str(payload.get("league") or key or "")[:20]
        for event in body.get("events") or []:
            if not isinstance(event, dict):
                continue
            comps = event.get("competitions") or [{}]
            comp = comps[0] if comps and isinstance(comps[0], dict) else {}
            status = (comp.get("status") or event.get("status") or {})
            stype = status.get("type") if isinstance(status, dict) else {}
            if not isinstance(stype, dict):
                stype = {}
            if str(stype.get("state") or "") != "pre":
                continue
            raw = comp.get("date") or event.get("date")
            if not raw:
                continue
            try:
                when = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            except ValueError:
                continue
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            eta = (when - now).total_seconds() / 60.0
            if eta < 0 or eta > float(horizon_min):
                continue
            games.append({
                "league": league or str(event.get("shortName") or "")[:20],
                "ticker": str(event.get("id") or event.get("uid") or event.get("name") or "")[:40],
                "tip_in_min": round(eta, 1),
                "name": str(event.get("name") or event.get("shortName") or "")[:80],
            })
    games.sort(key=lambda g: float(g.get("tip_in_min") or 0))
    return games[:40]


def write_digest_from_desk(root: str | None = None) -> dict:
    """Prefer live quote_cache tip windows; fall back to prior digest games."""
    games = games_from_quote_cache(root)
    if not games:
        path = digest_path(root)
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as handle:
                    prev = json.load(handle)
                if isinstance(prev, dict):
                    games = list(prev.get("games") or [])
            except (OSError, json.JSONDecodeError, TypeError):
                games = []
    return write_digest(root, games=games)


if __name__ == "__main__":
    out = write_digest(games=[
        {"league": "NBA", "ticker": "DEMO", "tip_in_min": 12},
        {"league": "NFL", "ticker": "DEMO2", "tip_in_min": 4},
    ])
    print("tip_radar", out["n"], out["games"][0]["priority"] if out["games"] else None)
