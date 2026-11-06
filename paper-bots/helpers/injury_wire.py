"""
Injury Wire insight helper — placeholder digest for sports news headlines (observe-only).

Never places paper fills. Never softens venue min_edge. Paper / helper-only.
Staff may feed headlines into write_digest; no auto scraping required for v1.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from helpers import HELPER_ONLY, PAPER_ONLY, assert_helper_only

DIGEST_NAME = "injury_wire_digest.json"
DESK_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def digest_path(root: str | None = None) -> str:
    return os.path.join(root or DESK_ROOT, "helpers", DIGEST_NAME)


def build_digest(headlines: list | None = None, *, now: datetime | None = None) -> dict:
    assert_helper_only("injury_wire")
    assert PAPER_ONLY and HELPER_ONLY
    now = now or datetime.now(timezone.utc)
    rows = []
    for h in headlines or []:
        if isinstance(h, dict):
            text = str(h.get("text") or h.get("headline") or "")[:160]
            league = str(h.get("league") or "")[:20]
        else:
            text = str(h or "")[:160]
            league = ""
        if not text:
            continue
        rows.append({"league": league, "text": text})
    return {
        "helper": "injury_wire",
        "at": now.isoformat(),
        "paper_only": True,
        "may_place_alone": False,
        "floors_locked": True,
        "n": len(rows),
        "headlines": rows[:30],
        "note": "Observe-only injury/news wire. Never buys; never waives sports floor.",
    }


def write_digest(root: str | None = None, headlines: list | None = None) -> dict:
    digest = build_digest(headlines)
    path = digest_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(digest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)
    return digest


def write_digest_from_desk(root: str | None = None) -> dict:
    """Preserve last headlines if present; else empty observe digest."""
    path = digest_path(root)
    headlines = []
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as handle:
                prev = json.load(handle)
            if isinstance(prev, dict):
                headlines = list(prev.get("headlines") or [])
        except (OSError, json.JSONDecodeError, TypeError):
            headlines = []
    return write_digest(root, headlines=headlines)


if __name__ == "__main__":
    print(write_digest(headlines=[{"league": "NBA", "text": "Demo: starter questionable (paper digest)"}]))
