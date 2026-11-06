"""
Hard-Stop Clerk insight helper — digests sports hard-stop shadow promote readiness (observe-only).

Never arms live hard-stop sells. Never softens venue floors.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from helpers import HELPER_ONLY, PAPER_ONLY, assert_helper_only

DIGEST_NAME = "hard_stop_clerk_digest.json"
DESK_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def digest_path(root: str | None = None) -> str:
    return os.path.join(root or DESK_ROOT, "helpers", DIGEST_NAME)


def build_digest(summary: dict | None = None, *, now: datetime | None = None) -> dict:
    assert_helper_only("hard_stop_clerk")
    assert PAPER_ONLY and HELPER_ONLY
    now = now or datetime.now(timezone.utc)
    s = summary if isinstance(summary, dict) else {}
    return {
        "helper": "hard_stop_clerk",
        "at": now.isoformat(),
        "paper_only": True,
        "may_place_alone": False,
        "floors_locked": True,
        "n": s.get("n"),
        "n_with_pnl": s.get("n_with_pnl"),
        "shadow_expectancy": s.get("shadow_expectancy"),
        "promote_ready": bool(s.get("promote_ready")),
        "live": bool(s.get("live")),
        "staff_approved": bool(s.get("staff_approved")),
        "decision": str(s.get("decision") or "")[:40],
        "auto_promote": False,
        "note": (
            "Observe-only hard-stop clerk. Live sells stay staff-gated; "
            "code default SPORTS_HARD_STOP_LIVE=False."
        ),
        "raw": {
            k: s.get(k)
            for k in ("n", "n_with_pnl", "shadow_expectancy", "promote_min_n", "drop", "decision")
            if k in s
        },
    }


def write_digest(root: str | None = None, summary: dict | None = None) -> dict:
    digest = build_digest(summary)
    path = digest_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(digest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)
    return digest


def write_digest_from_desk(root: str | None = None) -> dict:
    summary = {}
    try:
        import desk_roi_plan
        summary = desk_roi_plan.sports_hard_stop_shadow_summary(root or DESK_ROOT) or {}
    except Exception:
        summary = {}
    return write_digest(root, summary if isinstance(summary, dict) else {})


if __name__ == "__main__":
    print(write_digest(summary={"n": 12, "n_with_pnl": 10, "promote_ready": False, "decision": "reject"}))
