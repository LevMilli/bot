"""
EIA / energy-inventory blackout helper.

Reads ForexFactory (or seeded) calendar events and flags NatGas/Oil series
when a crude/natgas inventory print is near. Never places fills.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from helpers import HELPER_ONLY, PAPER_ONLY

# Minutes before/after an inventory print when energy entries are blocked.
EIA_WINDOW_MIN = 45

ENERGY_SERIES = frozenset({"KXNATGAS15M", "KXBRENT15M", "KXWTI15M"})

# Title fragments that mark inventory / EIA-style energy prints.
_TITLE_NEEDLES = (
    "eia",
    "crude oil invent",
    "crude invent",
    "petroleum status",
    "natural gas storage",
    "natgas storage",
    "nat gas storage",
    "gas storage",
    "api crude",
    "oil inventories",
    "weekly petroleum",
)


def is_energy_series(series: str | None) -> bool:
    key = str(series or "").strip().upper()
    if key in ENERGY_SERIES:
        return True
    return any(key.startswith(s) for s in ENERGY_SERIES)


def is_inventory_title(title: str | None) -> bool:
    text = str(title or "").strip().lower()
    if not text:
        return False
    return any(needle in text for needle in _TITLE_NEEDLES)


def _parse_when(raw: Any) -> datetime | None:
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


def inventory_hits(
    events: list | None,
    *,
    now: datetime | None = None,
    window_min: float = EIA_WINDOW_MIN,
) -> list[dict]:
    """Return inventory/EIA events inside ±window_min of now."""
    assert PAPER_ONLY and HELPER_ONLY
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    w = timedelta(minutes=float(window_min))
    hits: list[dict] = []
    for ev in events or []:
        if not isinstance(ev, dict):
            continue
        title = str(ev.get("title") or ev.get("name") or "")
        if not is_inventory_title(title):
            continue
        when = _parse_when(ev.get("date") or ev.get("when"))
        if when is None:
            continue
        if abs(when - now) <= w:
            hits.append(
                {
                    "title": title[:120],
                    "date": when.isoformat(),
                    "impact": str(ev.get("impact") or "")[:16],
                    "country": str(ev.get("country") or "")[:8],
                    "eta_min": round((when - now).total_seconds() / 60.0, 1),
                }
            )
    hits.sort(key=lambda row: abs(float(row.get("eta_min") or 0)))
    return hits


def energy_blackout(
    series: str | None,
    events: list | None,
    *,
    now: datetime | None = None,
    window_min: float = EIA_WINDOW_MIN,
) -> dict:
    """
    Hard gate for energy series near EIA/inventory prints.
    Metals / unknown series always clear.
    """
    assert PAPER_ONLY and HELPER_ONLY
    if not is_energy_series(series):
        return {
            "blocked": False,
            "series": str(series or ""),
            "family": "non-energy",
            "hits": [],
            "reason": "",
        }
    hits = inventory_hits(events, now=now, window_min=window_min)
    if not hits:
        return {
            "blocked": False,
            "series": str(series or ""),
            "family": "energy",
            "hits": [],
            "reason": "",
        }
    top = hits[0]
    reason = (
        f"EIA/inventory blackout: {top.get('title')} "
        f"(eta {top.get('eta_min')}m, ±{int(window_min)}m)"
    )
    return {
        "blocked": True,
        "series": str(series or ""),
        "family": "energy",
        "hits": hits[:5],
        "reason": reason,
        "window_min": float(window_min),
    }


def load_calendar_events(root: str | None = None) -> list:
    """Prefer helpers.calendar_cache last-good; empty list if never loaded."""
    try:
        from helpers.calendar_cache import load_ff_calendar

        events = load_ff_calendar(root)
        if events is None:
            return []
        return list(events)
    except Exception:
        return []


def self_check() -> None:
    now = datetime(2026, 11, 5, 15, 30, tzinfo=timezone.utc)
    events = [
        {
            "country": "USD",
            "impact": "High",
            "title": "Crude Oil Inventories",
            "date": "2026-11-05T15:30:00+00:00",
        },
        {
            "country": "USD",
            "impact": "High",
            "title": "CPI",
            "date": "2026-11-05T15:30:00+00:00",
        },
    ]
    assert is_inventory_title("Natural Gas Storage")
    assert not is_inventory_title("CPI")
    hits = inventory_hits(events, now=now, window_min=45)
    assert len(hits) == 1
    blocked = energy_blackout("KXWTI15M", events, now=now)
    assert blocked["blocked"] is True
    clear = energy_blackout("KXGOLD15M", events, now=now)
    assert clear["blocked"] is False
    far = energy_blackout(
        "KXNATGAS15M",
        events,
        now=datetime(2026, 11, 5, 20, 0, tzinfo=timezone.utc),
    )
    assert far["blocked"] is False


if __name__ == "__main__":
    self_check()
    print("helpers.eia_blackout self_check ok")
