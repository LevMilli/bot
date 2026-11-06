"""
EIA Scout insight helper — week-ahead energy inventory calendar (observe-only).

Lists upcoming Crude / NatGas inventory prints so commodity mains can plan
around blackouts. Never places fills. Never softens venue min_edge.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

from helpers import HELPER_ONLY, PAPER_ONLY, assert_helper_only
from helpers.eia_blackout import is_inventory_title, load_calendar_events

DIGEST_NAME = "eia_scout_digest.json"
DESK_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCOUT_DAYS = 7


def digest_path(root: str | None = None) -> str:
    return os.path.join(root or DESK_ROOT, "helpers", DIGEST_NAME)


def _parse_when(raw) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        when = raw
    else:
        try:
            when = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when.astimezone(timezone.utc)


def upcoming_inventory(
    events: list | None,
    *,
    now: datetime | None = None,
    days: float = SCOUT_DAYS,
) -> list[dict]:
    """Inventory/EIA titles from now through +days (not the ±45m blackout window)."""
    assert PAPER_ONLY and HELPER_ONLY
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    horizon = now + timedelta(days=float(days))
    rows: list[dict] = []
    for ev in events or []:
        if not isinstance(ev, dict):
            continue
        title = str(ev.get("title") or ev.get("name") or "")
        if not is_inventory_title(title):
            continue
        when = _parse_when(ev.get("date") or ev.get("when"))
        if when is None or when < now or when > horizon:
            continue
        rows.append({
            "title": title[:120],
            "date": when.isoformat(),
            "impact": str(ev.get("impact") or "")[:16],
            "country": str(ev.get("country") or "")[:8],
            "eta_hours": round((when - now).total_seconds() / 3600.0, 1),
        })
    rows.sort(key=lambda r: float(r.get("eta_hours") or 0))
    return rows


def build_digest(
    events: list | None = None,
    *,
    now: datetime | None = None,
    days: float = SCOUT_DAYS,
) -> dict:
    assert_helper_only("eia_scout")
    assert PAPER_ONLY and HELPER_ONLY
    now = now or datetime.now(timezone.utc)
    rows = upcoming_inventory(events, now=now, days=days)
    next_eta = rows[0]["eta_hours"] if rows else None
    return {
        "helper": "eia_scout",
        "at": now.isoformat(),
        "paper_only": True,
        "may_place_alone": False,
        "floors_locked": True,
        "scout_days": float(days),
        "n": len(rows),
        "next_eta_hours": next_eta,
        "events": rows[:20],
        "note": (
            "Observe-only EIA week scout. Commodity blackout remains ±45m via eia_blackout — "
            "never softens 0.05 floor."
        ),
    }


def write_digest(root: str | None = None, events: list | None = None) -> dict:
    if events is None:
        events = load_calendar_events(root)
    digest = build_digest(events)
    path = digest_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(digest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)
    return digest


def write_digest_from_desk(root: str | None = None) -> dict:
    return write_digest(root)


if __name__ == "__main__":
    demo = [
        {
            "country": "USD",
            "impact": "High",
            "title": "Crude Oil Inventories",
            "date": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
        },
        {
            "country": "USD",
            "impact": "High",
            "title": "CPI",
            "date": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        },
    ]
    out = write_digest(events=demo)
    print("eia_scout", out["n"], out.get("next_eta_hours"))
