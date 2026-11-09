"""
Multi-exchange disagree insight helper — BTC spot cross-venue observe.

Compares public Coinbase / Kraken / Bitstamp / Deribit index marks. Never
places fills. Never softens floors. Missing legs stay null — never invent.
"""
from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone

from helpers import HELPER_ONLY, PAPER_ONLY, assert_helper_only

DIGEST_NAME = "multi_ex_disagree_digest.json"
DESK_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = {"User-Agent": "paper-bots-multi-ex/1.0 (paper-only)"}
# Observe alert when max−min / mid exceeds this (bps of spot).
DISAGREE_BPS = 15.0


def digest_path(root: str | None = None) -> str:
    return os.path.join(root or DESK_ROOT, "helpers", DIGEST_NAME)


def _finite(x):
    try:
        n = float(x)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(n) or n <= 0:
        return None
    return n


def _http_json(url: str, *, opener=None):
    import urllib.request

    opener = opener or (
        lambda u: urllib.request.urlopen(
            urllib.request.Request(u, headers=UA), timeout=12,
        ).read()
    )
    try:
        blob = opener(url)
    except Exception:
        return None
    try:
        if isinstance(blob, bytes):
            return json.loads(blob.decode("utf-8", errors="replace"))
        if isinstance(blob, str):
            return json.loads(blob)
        if isinstance(blob, dict):
            return blob
    except json.JSONDecodeError:
        return None
    return None


def fetch_marks(*, opener=None) -> dict[str, float | None]:
    """Public BTC USD marks. Missing venue → None (never invent)."""
    out: dict[str, float | None] = {
        "coinbase": None,
        "kraken": None,
        "bitstamp": None,
        "deribit_index": None,
    }
    cb = _http_json(
        "https://api.exchange.coinbase.com/products/BTC-USD/ticker", opener=opener,
    )
    if isinstance(cb, dict):
        out["coinbase"] = _finite(cb.get("price") or cb.get("ask"))

    kr = _http_json(
        "https://api.kraken.com/0/public/Ticker?pair=XBTUSD", opener=opener,
    )
    if isinstance(kr, dict):
        result = kr.get("result") if isinstance(kr.get("result"), dict) else {}
        row = result.get("XXBTZUSD") or next(iter(result.values()), None)
        if isinstance(row, dict):
            last = row.get("c")
            if isinstance(last, list) and last:
                out["kraken"] = _finite(last[0])

    bs = _http_json("https://www.bitstamp.net/api/v2/ticker/btcusd/", opener=opener)
    if isinstance(bs, dict):
        out["bitstamp"] = _finite(bs.get("last") or bs.get("ask"))

    db = _http_json(
        "https://www.deribit.com/api/v2/public/get_index_price?index_name=btc_usd",
        opener=opener,
    )
    if isinstance(db, dict):
        result = db.get("result") if isinstance(db.get("result"), dict) else {}
        out["deribit_index"] = _finite(result.get("index_price"))

    return out


def disagree_stats(marks: dict | None = None) -> dict:
    """max−min / mid in bps across present marks."""
    vals = []
    for venue, px in (marks or {}).items():
        n = _finite(px)
        if n is None:
            continue
        vals.append((str(venue), n))
    if len(vals) < 2:
        return {
            "n": len(vals),
            "mid": vals[0][1] if vals else None,
            "max_venue": vals[0][0] if vals else None,
            "min_venue": vals[0][0] if vals else None,
            "range_usd": None,
            "range_bps": None,
            "alert": False,
        }
    lo = min(vals, key=lambda r: r[1])
    hi = max(vals, key=lambda r: r[1])
    mid = (lo[1] + hi[1]) / 2.0
    span = hi[1] - lo[1]
    bps = (span / mid) * 10000.0 if mid > 0 else None
    return {
        "n": len(vals),
        "mid": round(mid, 2),
        "max_venue": hi[0],
        "min_venue": lo[0],
        "range_usd": round(span, 2),
        "range_bps": round(bps, 2) if bps is not None else None,
        "alert": bool(bps is not None and bps + 1e-12 >= DISAGREE_BPS),
    }


def build_digest(
    marks: dict | None = None,
    *,
    now: datetime | None = None,
) -> dict:
    assert_helper_only("multi_ex_disagree")
    assert PAPER_ONLY and HELPER_ONLY
    now = now or datetime.now(timezone.utc)
    marks = marks if isinstance(marks, dict) else {}
    clean = {k: _finite(v) for k, v in marks.items()}
    stats = disagree_stats(clean)
    return {
        "helper": "multi_ex_disagree",
        "at": now.isoformat(),
        "paper_only": True,
        "may_place_alone": False,
        "floors_locked": True,
        "marks": {k: (round(v, 2) if v is not None else None) for k, v in clean.items()},
        "present_n": stats["n"],
        "mid": stats["mid"],
        "range_usd": stats["range_usd"],
        "range_bps": stats["range_bps"],
        "max_venue": stats["max_venue"],
        "min_venue": stats["min_venue"],
        "alert": stats["alert"],
        "alert_bps": DISAGREE_BPS,
        "note": (
            f"Observe-only BTC multi-ex disagree (alert ≥{DISAGREE_BPS:g} bps). "
            "Missing venues stay null — never invent. Never LIVE."
        ),
    }


def write_digest_from_desk(root: str | None = None, *, opener=None) -> dict:
    root = root or DESK_ROOT
    digest = build_digest(fetch_marks(opener=opener))
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
