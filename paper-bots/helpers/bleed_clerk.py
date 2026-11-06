"""
Bleed Clerk insight helper — digests firm bleed + misplaced capital (observe-only).

Never moves risk. Never softens venue floors. Points staff at recycle toward fee-clear.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from helpers import HELPER_ONLY, PAPER_ONLY, assert_helper_only

DIGEST_NAME = "bleed_clerk_digest.json"
DESK_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def digest_path(root: str | None = None) -> str:
    return os.path.join(root or DESK_ROOT, "helpers", DIGEST_NAME)


def build_digest(
    bleed: dict | None = None,
    misplaced: dict | None = None,
    *,
    now: datetime | None = None,
) -> dict:
    assert_helper_only("bleed_clerk")
    assert PAPER_ONLY and HELPER_ONLY
    now = now or datetime.now(timezone.utc)
    bleed = bleed if isinstance(bleed, dict) else {}
    misplaced = misplaced if isinstance(misplaced, dict) else {}
    return {
        "helper": "bleed_clerk",
        "at": now.isoformat(),
        "paper_only": True,
        "may_place_alone": False,
        "floors_locked": True,
        "bleed_ratio": bleed.get("ratio"),
        "bleed_pass": bleed.get("pass"),
        "misplaced_usd": misplaced.get("misplaced_usd"),
        "share_of_cap": misplaced.get("share_of_cap"),
        "misplaced_rows": (misplaced.get("rows") or [])[:12],
        "note": (
            "Observe-only bleed clerk. Recycle open risk on red towers toward fee-clear — "
            "never soften 0.06/0.05/0.02."
        ),
    }


def write_digest(
    root: str | None = None,
    *,
    bleed: dict | None = None,
    misplaced: dict | None = None,
) -> dict:
    digest = build_digest(bleed, misplaced)
    path = digest_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(digest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)
    return digest


def write_digest_from_desk(
    root: str | None = None,
    bots: list | None = None,
    cfg: dict | None = None,
) -> dict:
    bleed = misplaced = {}
    try:
        import desk_roi_plan
        bleed = desk_roi_plan.firm_bleed_ratio(bots) or {}
        misplaced = desk_roi_plan.capital_misplaced(bots, cfg) or {}
    except Exception:
        bleed = misplaced = {}
    return write_digest(
        root,
        bleed=bleed if isinstance(bleed, dict) else {},
        misplaced=misplaced if isinstance(misplaced, dict) else {},
    )


if __name__ == "__main__":
    print(write_digest(bleed={"ratio": 0.2, "pass": True}, misplaced={"misplaced_usd": 12.5, "rows": []}))
