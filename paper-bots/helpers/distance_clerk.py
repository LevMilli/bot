"""
Distance Clerk insight helper — digests empty-CARD latency + firm-queue distance (observe-only).

Never places fills. Never softens venue floors. Speed without junk volume.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from helpers import HELPER_ONLY, PAPER_ONLY, assert_helper_only

DIGEST_NAME = "distance_clerk_digest.json"
DESK_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def digest_path(root: str | None = None) -> str:
    return os.path.join(root or DESK_ROOT, "helpers", DIGEST_NAME)


def build_digest(
    empty_card: dict | None = None,
    firm_queue: dict | None = None,
    *,
    now: datetime | None = None,
) -> dict:
    assert_helper_only("distance_clerk")
    assert PAPER_ONLY and HELPER_ONLY
    now = now or datetime.now(timezone.utc)
    empty_card = empty_card if isinstance(empty_card, dict) else {}
    firm_queue = firm_queue if isinstance(firm_queue, dict) else {}
    return {
        "helper": "distance_clerk",
        "at": now.isoformat(),
        "paper_only": True,
        "may_place_alone": False,
        "floors_locked": True,
        "empty_card_pass": empty_card.get("pass"),
        "empty_card_last_sec": empty_card.get("last_sec") or empty_card.get("p50"),
        "firm_offers_n": firm_queue.get("offers_n"),
        "firm_accepted_n": firm_queue.get("accepted_n"),
        "firm_deferred_n": firm_queue.get("deferred_n"),
        "remaining_risk": firm_queue.get("remaining_risk"),
        "note": (
            "Observe-only distance clerk. Empty CARD + firm queue distance — "
            "recycle risk to fee-clear; never soften floors."
        ),
    }


def write_digest(
    root: str | None = None,
    *,
    empty_card: dict | None = None,
    firm_queue: dict | None = None,
) -> dict:
    digest = build_digest(empty_card, firm_queue)
    path = digest_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(digest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)
    return digest


def write_digest_from_desk(root: str | None = None) -> dict:
    empty_card = firm_queue = {}
    try:
        import desk_roi_plan
        base = root or DESK_ROOT
        empty_card = desk_roi_plan.empty_card_status(base) or {}
        firm_queue = desk_roi_plan.firm_queue_status(base) or {}
    except Exception:
        empty_card = firm_queue = {}
    return write_digest(
        root,
        empty_card=empty_card if isinstance(empty_card, dict) else {},
        firm_queue=firm_queue if isinstance(firm_queue, dict) else {},
    )


if __name__ == "__main__":
    print(write_digest(empty_card={"pass": True, "last_sec": 1.2}, firm_queue={"offers_n": 3}))
