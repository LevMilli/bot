"""
Empty-CARD Bee insight helper — nags empty book latency (observe-only).

Never places paper fills. Never softens venue min_edge. Paper / helper-only.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from helpers import HELPER_ONLY, PAPER_ONLY, assert_helper_only

DIGEST_NAME = "empty_card_bee_digest.json"
DESK_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BAR_SEC = 3.0


def digest_path(root: str | None = None) -> str:
    base = root or DESK_ROOT
    return os.path.join(base, "helpers", DIGEST_NAME)


def build_digest(events: list | None = None, *, now: datetime | None = None) -> dict:
    assert_helper_only("empty_card_bee")
    assert PAPER_ONLY and HELPER_ONLY
    now = now or datetime.now(timezone.utc)
    rows = []
    breaches = 0
    for ev in events or []:
        if not isinstance(ev, dict):
            continue
        try:
            sec = float(ev.get("sec") or ev.get("latency_sec") or 0)
        except (TypeError, ValueError):
            continue
        breach = sec + 1e-12 >= BAR_SEC
        if breach:
            breaches += 1
        rows.append({
            "bot": str(ev.get("bot") or "")[:40],
            "series": str(ev.get("series") or "")[:40],
            "sec": round(sec, 3),
            "breach": breach,
        })
    return {
        "helper": "empty_card_bee",
        "at": now.isoformat(),
        "paper_only": True,
        "may_place_alone": False,
        "floors_locked": True,
        "bar_sec": BAR_SEC,
        "n": len(rows),
        "breaches": breaches,
        "events": rows[:40],
        "note": "Observe-only empty CARD bee. Speed without softer floors.",
    }


def write_digest(root: str | None = None, events: list | None = None) -> dict:
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
    events = []
    try:
        import desk_roi_plan
        status = desk_roi_plan.empty_card_status(root or DESK_ROOT) if hasattr(desk_roi_plan, "empty_card_status") else {}
        if isinstance(status, dict):
            for row in status.get("recent") or status.get("events") or []:
                if isinstance(row, dict):
                    events.append(row)
            if not events and status.get("last_sec") is not None:
                events.append({
                    "bot": status.get("bot") or "desk",
                    "series": status.get("series") or "",
                    "sec": status.get("last_sec"),
                })
    except Exception:
        events = []
    return write_digest(root, events)


if __name__ == "__main__":
    print(write_digest(events=[{"bot": "btc15m", "series": "KXBTC15M", "sec": 3.5}]))
