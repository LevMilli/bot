"""
Skip Historian insight helper — publishes top skip codes (observe-only).

Never places paper fills. Never softens venue min_edge. Paper / helper-only.
"""
from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone

from helpers import HELPER_ONLY, PAPER_ONLY, assert_helper_only

DIGEST_NAME = "skip_historian_digest.json"
DESK_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def digest_path(root: str | None = None) -> str:
    base = root or DESK_ROOT
    return os.path.join(base, "helpers", DIGEST_NAME)


def build_digest(skip_events: list | None = None, *, now: datetime | None = None) -> dict:
    assert_helper_only("skip_historian")
    assert PAPER_ONLY and HELPER_ONLY
    now = now or datetime.now(timezone.utc)
    counts: Counter[str] = Counter()
    for ev in skip_events or []:
        if isinstance(ev, dict):
            code = str(ev.get("code") or ev.get("stable") or ev.get("skip") or "DATA")
            try:
                n = int(ev.get("n") or 1)
            except (TypeError, ValueError):
                n = 1
            counts[code[:40]] += max(1, min(n, 5000))
        else:
            counts[str(ev or "DATA")[:40]] += 1
    top = [{"code": c, "n": n} for c, n in counts.most_common(20)]
    return {
        "helper": "skip_historian",
        "at": now.isoformat(),
        "paper_only": True,
        "may_place_alone": False,
        "floors_locked": True,
        "n_events": int(sum(counts.values())),
        "top": top,
        "note": "Observe-only skip historian. BUDGET≠EDGE — never soften floors to chase volume.",
    }


def write_digest(root: str | None = None, skip_events: list | None = None) -> dict:
    digest = build_digest(skip_events)
    path = digest_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(digest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)
    return digest


def write_digest_from_desk(root: str | None = None) -> dict:
    """Pull skip board from desk_more if available; else empty digest."""
    events: list = []
    try:
        import desk_more
        board = desk_more.skip_leaderboard(root or DESK_ROOT) if hasattr(desk_more, "skip_leaderboard") else {}
        if isinstance(board, dict):
            for row in board.get("stable_top") or board.get("top") or []:
                if isinstance(row, dict):
                    events.append({
                        "code": row.get("code") or row.get("stable") or "DATA",
                        "n": row.get("n") or 1,
                    })
    except Exception:
        events = []
    return write_digest(root, events)


if __name__ == "__main__":
    d = build_digest(["EDGE", "EDGE", "BUDGET", "NEWS", "WEEKEND"])
    print("skip_historian", d["top"][:3])
