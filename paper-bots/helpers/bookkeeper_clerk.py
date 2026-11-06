"""
Bookkeeper Clerk insight helper — digests Completions KPI + fee-ledger health (observe-only).

Never paints PnL. Never softens venue floors.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from helpers import HELPER_ONLY, PAPER_ONLY, assert_helper_only

DIGEST_NAME = "bookkeeper_clerk_digest.json"
DESK_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def digest_path(root: str | None = None) -> str:
    return os.path.join(root or DESK_ROOT, "helpers", DIGEST_NAME)


def build_digest(
    completions: dict | None = None,
    fee_ledger: dict | None = None,
    *,
    now: datetime | None = None,
) -> dict:
    assert_helper_only("bookkeeper_clerk")
    assert PAPER_ONLY and HELPER_ONLY
    now = now or datetime.now(timezone.utc)
    completions = completions if isinstance(completions, dict) else {}
    fee_ledger = fee_ledger if isinstance(fee_ledger, dict) else {}
    return {
        "helper": "bookkeeper_clerk",
        "at": now.isoformat(),
        "paper_only": True,
        "may_place_alone": False,
        "floors_locked": True,
        "eligible_completions_today": completions.get("eligible_completions_today"),
        "completions_today": completions.get("completions_today"),
        "eligible_pnl_today": completions.get("eligible_pnl_today"),
        "fee_ledger_n": fee_ledger.get("n") or fee_ledger.get("rows_n"),
        "fee_ledger_complete": fee_ledger.get("complete") if "complete" in fee_ledger else fee_ledger.get("pass"),
        "note": (
            "Observe-only bookkeeper. Taxed Completions + fee ledger completeness — "
            "never invent fills or soften floors."
        ),
    }


def write_digest(
    root: str | None = None,
    *,
    completions: dict | None = None,
    fee_ledger: dict | None = None,
) -> dict:
    digest = build_digest(completions, fee_ledger)
    path = digest_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(digest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)
    return digest


def write_digest_from_desk(root: str | None = None) -> dict:
    completions = fee_ledger = {}
    try:
        import desk_living
        completions = desk_living.completions_summary(root or DESK_ROOT) or {}
    except Exception:
        completions = {}
    try:
        import desk_roi_plan
        fee_ledger = desk_roi_plan.fee_ledger_completeness(root or DESK_ROOT) or {}
    except Exception:
        fee_ledger = {}
    return write_digest(
        root,
        completions=completions if isinstance(completions, dict) else {},
        fee_ledger=fee_ledger if isinstance(fee_ledger, dict) else {},
    )


if __name__ == "__main__":
    print(write_digest(completions={"eligible_completions_today": 2, "completions_today": 3}))
