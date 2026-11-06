"""
CLV Closer insight helper — digests sports CLV completeness (observe-only).

Never places paper fills. Never softens venue min_edge. Paper / helper-only.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from helpers import HELPER_ONLY, PAPER_ONLY, assert_helper_only

DIGEST_NAME = "clv_closer_digest.json"
DESK_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def digest_path(root: str | None = None) -> str:
    return os.path.join(root or DESK_ROOT, "helpers", DIGEST_NAME)


def build_digest(clv: dict | None = None, *, now: datetime | None = None) -> dict:
    assert_helper_only("clv_closer")
    assert PAPER_ONLY and HELPER_ONLY
    now = now or datetime.now(timezone.utc)
    clv = clv if isinstance(clv, dict) else {}
    return {
        "helper": "clv_closer",
        "at": now.isoformat(),
        "paper_only": True,
        "may_place_alone": False,
        "floors_locked": True,
        "n": clv.get("n"),
        "complete": clv.get("complete"),
        "completeness": clv.get("completeness") if clv.get("completeness") is not None else clv.get("rate"),
        "pass": clv.get("pass"),
        "note": "Observe-only CLV closer. Feeds green_boost evidence — never softens 0.06.",
        "raw": {k: clv.get(k) for k in ("n", "complete", "missing", "pass", "note") if k in clv},
    }


def write_digest_from_desk(root: str | None = None) -> dict:
    clv = {}
    try:
        import desk_roi_plan
        clv = desk_roi_plan.clv_completeness(root or DESK_ROOT) or {}
    except Exception:
        clv = {}
    digest = build_digest(clv)
    path = digest_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(digest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)
    return digest


if __name__ == "__main__":
    print(write_digest_from_desk())
