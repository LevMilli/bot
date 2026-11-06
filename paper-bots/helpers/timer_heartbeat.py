"""
Timer Heartbeat insight helper — pages when desk timer looks dead (observe-only).

Never places paper fills. Never softens venue min_edge. Paper / helper-only.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from helpers import HELPER_ONLY, PAPER_ONLY, assert_helper_only

DIGEST_NAME = "timer_heartbeat_digest.json"
DESK_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def digest_path(root: str | None = None) -> str:
    base = root or DESK_ROOT
    return os.path.join(base, "helpers", DIGEST_NAME)


def build_digest(*, alive: bool | None = None, detail: str = "", now: datetime | None = None) -> dict:
    assert_helper_only("timer_heartbeat")
    assert PAPER_ONLY and HELPER_ONLY
    now = now or datetime.now(timezone.utc)
    status = "unknown" if alive is None else ("alive" if alive else "dead")
    return {
        "helper": "timer_heartbeat",
        "at": now.isoformat(),
        "paper_only": True,
        "may_place_alone": False,
        "floors_locked": True,
        "alive": alive,
        "status": status,
        "detail": str(detail or "")[:200],
        "note": "Life support #1 — dead timer = dead city. Observe-only.",
    }


def write_digest(root: str | None = None, *, alive: bool | None = None, detail: str = "") -> dict:
    digest = build_digest(alive=alive, detail=detail)
    path = digest_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(digest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)
    return digest


def probe_from_snapshot(root: str | None = None) -> dict:
    """Best-effort: read pimp_desk snapshot timer/health if present."""
    alive = None
    detail = ""
    try:
        import pimp_desk
        snap = pimp_desk.snapshot(root or DESK_ROOT)
        timer = snap.get("timer") if isinstance(snap, dict) else None
        health = (snap.get("desk") or {}).get("health") if isinstance(snap, dict) else None
        if isinstance(health, dict) and "alive" in health:
            alive = bool(health.get("alive"))
            detail = str(health.get("note") or health.get("detail") or "")[:200]
        elif isinstance(timer, str):
            alive = "dead" not in timer.lower() and "stopped" not in timer.lower()
            detail = timer[:200]
    except Exception as exc:
        detail = f"probe failed: {type(exc).__name__}"
    return write_digest(root, alive=alive, detail=detail)


if __name__ == "__main__":
    print(write_digest(alive=True, detail="self-check"))
