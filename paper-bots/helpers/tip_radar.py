"""
Tip Radar insight helper — lists tip-soon sports windows for mains (observe-only).

Never places paper fills. Never softens venue min_edge. Paper / helper-only.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone

from helpers import HELPER_ONLY, PAPER_ONLY, assert_helper_only

DIGEST_NAME = "tip_radar_digest.json"
DESK_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def digest_path(root: str | None = None) -> str:
    base = root or DESK_ROOT
    return os.path.join(base, "helpers", DIGEST_NAME)


def build_digest(games: list | None = None, *, now: datetime | None = None) -> dict:
    """Signal-only tip radar board. `games` optional list of {league,tip_in_min,ticker}."""
    assert_helper_only("tip_radar")
    assert PAPER_ONLY and HELPER_ONLY
    now = now or datetime.now(timezone.utc)
    rows = []
    for g in games or []:
        if not isinstance(g, dict):
            continue
        try:
            tip = float(g.get("tip_in_min"))
        except (TypeError, ValueError):
            continue
        if tip < 0 or tip > 180:
            continue
        rows.append({
            "league": str(g.get("league") or "")[:20],
            "ticker": str(g.get("ticker") or "")[:40],
            "tip_in_min": round(tip, 1),
            "priority": "T-5" if tip <= 5 else ("T-15" if tip <= 15 else "T-180"),
        })
    rows.sort(key=lambda r: float(r["tip_in_min"]))
    return {
        "helper": "tip_radar",
        "at": now.isoformat(),
        "paper_only": True,
        "may_place_alone": False,
        "floors_locked": True,
        "n": len(rows),
        "games": rows[:40],
        "note": "Observe-only tip radar. Never waives sports 0.06 floor.",
    }


def write_digest(root: str | None = None, games: list | None = None) -> dict:
    digest = build_digest(games)
    path = digest_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(digest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)
    return digest


if __name__ == "__main__":
    out = write_digest(games=[
        {"league": "NBA", "ticker": "DEMO", "tip_in_min": 12},
        {"league": "NFL", "ticker": "DEMO2", "tip_in_min": 4},
    ])
    print("tip_radar", out["n"], out["games"][0]["priority"] if out["games"] else None)
