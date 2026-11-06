"""
Reporter Clerk insight helper — digests weekly scorecard / Sunday packet snapshot (observe-only).

Never auto-publishes. Never softens venue floors.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from helpers import HELPER_ONLY, PAPER_ONLY, assert_helper_only

DIGEST_NAME = "reporter_clerk_digest.json"
DESK_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def digest_path(root: str | None = None) -> str:
    return os.path.join(root or DESK_ROOT, "helpers", DIGEST_NAME)


def build_digest(scorecard: dict | None = None, *, now: datetime | None = None) -> dict:
    assert_helper_only("reporter_clerk")
    assert PAPER_ONLY and HELPER_ONLY
    now = now or datetime.now(timezone.utc)
    s = scorecard if isinstance(scorecard, dict) else {}
    return {
        "helper": "reporter_clerk",
        "at": now.isoformat(),
        "paper_only": True,
        "may_place_alone": False,
        "floors_locked": True,
        "label": s.get("label") or s.get("chicago_week") or s.get("week"),
        "m1": s.get("m1") or s.get("firm_m1") or s.get("taxed_m1"),
        "keys": sorted(list(s.keys()))[:24] if s else [],
        "present": bool(s),
        "auto_publish": False,
        "note": (
            "Observe-only reporter. Sunday living packet mirror — staff publishes; "
            "never paints PnL or softens floors."
        ),
    }


def write_digest(root: str | None = None, scorecard: dict | None = None) -> dict:
    digest = build_digest(scorecard)
    path = digest_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(digest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)
    return digest


def write_digest_from_desk(root: str | None = None) -> dict:
    scorecard = {}
    try:
        import desk_roi_plan
        scorecard = desk_roi_plan.latest_weekly_scorecard(root or DESK_ROOT) or {}
    except Exception:
        scorecard = {}
    digest = write_digest(root, scorecard if isinstance(scorecard, dict) else {})
    # Also refresh Sunday living packet draft (staff publish only).
    try:
        from helpers import sunday_packet
        sunday_packet.write_packet(root)
    except Exception:
        pass
    return digest


if __name__ == "__main__":
    print(write_digest(scorecard={"label": "2026-W45", "m1": -12.5}))
