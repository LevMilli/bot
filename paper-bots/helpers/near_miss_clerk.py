"""
Near-Miss Clerk insight helper — digests soft z|p promote readiness (observe-only).

Never arms soft gates. Never softens edge / fee floors (allowlist is z|p only).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from helpers import HELPER_ONLY, PAPER_ONLY, assert_helper_only

DIGEST_NAME = "near_miss_clerk_digest.json"
DESK_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def digest_path(root: str | None = None) -> str:
    return os.path.join(root or DESK_ROOT, "helpers", DIGEST_NAME)


def build_digest(status: dict | None = None, *, now: datetime | None = None) -> dict:
    assert_helper_only("near_miss_clerk")
    assert PAPER_ONLY and HELPER_ONLY
    now = now or datetime.now(timezone.utc)
    s = status if isinstance(status, dict) else {}
    return {
        "helper": "near_miss_clerk",
        "at": now.isoformat(),
        "paper_only": True,
        "may_place_alone": False,
        "floors_locked": True,
        "n": s.get("n"),
        "labeled_n": s.get("labeled_n"),
        "shadow_ev": s.get("shadow_ev"),
        "promote_ready": bool(s.get("promote_ready")),
        "soft_live": s.get("soft_live"),
        "decision": str(s.get("decision") or "")[:40],
        "auto_promote": False,
        "note": (
            "Observe-only near-miss clerk. Soft allowlist is z|p only — "
            "never edge, never softer fee floors."
        ),
        "raw": {
            k: s.get(k)
            for k in ("n", "labeled_n", "shadow_ev", "baseline_ev", "promote_min_n", "decision", "soft_live")
            if k in s
        },
    }


def write_digest(root: str | None = None, status: dict | None = None) -> dict:
    digest = build_digest(status)
    path = digest_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(digest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)
    return digest


def write_digest_from_desk(root: str | None = None) -> dict:
    status = {}
    try:
        import desk_roi_plan
        status = desk_roi_plan.near_miss_promote_status(root or DESK_ROOT) or {}
    except Exception:
        status = {}
    return write_digest(root, status if isinstance(status, dict) else {})


if __name__ == "__main__":
    print(write_digest(status={"n": 5, "labeled_n": 5, "promote_ready": False, "decision": "reject"}))
