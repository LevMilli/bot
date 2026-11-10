"""
Funding scout insight helper — Deribit BTC perpetual funding observe.

Surfaces current / 8h funding for the carry sleeve. Never opens desk cash.
Never softens floors. Missing marks stay null — never invent.
"""
from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone

from helpers import HELPER_ONLY, PAPER_ONLY, assert_helper_only

DIGEST_NAME = "funding_scout_digest.json"
DESK_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = {"User-Agent": "paper-bots-funding-scout/1.0 (paper-only)"}
# Observe flag when |8h funding| exceeds this (not a floor soften).
HOT_ABS_8H = 0.0003


def digest_path(root: str | None = None) -> str:
    return os.path.join(root or DESK_ROOT, "helpers", DIGEST_NAME)


def _finite(x):
    try:
        n = float(x)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(n):
        return None
    return n


def fetch_funding(*, opener=None) -> dict:
    """Deribit BTC-PERPETUAL funding + mark. Empty on miss — never invent."""
    import urllib.request

    opener = opener or (
        lambda u: urllib.request.urlopen(
            urllib.request.Request(u, headers=UA), timeout=12,
        ).read()
    )
    url = (
        "https://www.deribit.com/api/v2/public/get_book_summary_by_currency"
        "?currency=BTC&kind=future"
    )
    try:
        blob = opener(url)
    except Exception:
        return {}
    try:
        if isinstance(blob, bytes):
            data = json.loads(blob.decode("utf-8", errors="replace"))
        elif isinstance(blob, str):
            data = json.loads(blob)
        elif isinstance(blob, dict):
            data = blob
        else:
            return {}
    except json.JSONDecodeError:
        return {}
    rows = data.get("result") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("instrument_name") or "")
        if "PERPETUAL" not in name:
            continue
        return {
            "instrument": name,
            "mark_price": _finite(row.get("mark_price")),
            "funding_8h": _finite(row.get("funding_8h")),
            "current_funding": _finite(row.get("current_funding")),
            "open_interest": _finite(row.get("open_interest")),
        }
    return {}


def build_digest(
    marks: dict | None = None,
    *,
    now: datetime | None = None,
) -> dict:
    assert_helper_only("funding_scout")
    assert PAPER_ONLY and HELPER_ONLY
    now = now or datetime.now(timezone.utc)
    marks = marks if isinstance(marks, dict) else {}
    f8 = _finite(marks.get("funding_8h"))
    cur = _finite(marks.get("current_funding"))
    hot = bool(f8 is not None and abs(f8) + 1e-15 >= HOT_ABS_8H)
    return {
        "helper": "funding_scout",
        "at": now.isoformat(),
        "paper_only": True,
        "may_place_alone": False,
        "floors_locked": True,
        "opens_desk_cash": False,
        "instrument": str(marks.get("instrument") or "")[:40] or None,
        "mark_price": round(float(marks["mark_price"]), 2) if _finite(marks.get("mark_price")) is not None else None,
        "funding_8h": f8,
        "current_funding": cur,
        "open_interest": _finite(marks.get("open_interest")),
        "hot": hot,
        "hot_abs_8h": HOT_ABS_8H,
        "waiting": f8 is None and cur is None,
        "note": (
            "Observe-only BTC funding scout (Deribit perpetual). "
            "Hot when |funding_8h| is elevated — never invents marks; never LIVE."
        ),
    }


def write_digest_from_desk(root: str | None = None, *, opener=None) -> dict:
    root = root or DESK_ROOT
    digest = build_digest(fetch_funding(opener=opener))
    path = digest_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(digest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)
    return digest


if __name__ == "__main__":
    print(json.dumps(write_digest_from_desk(), indent=2, sort_keys=True))
