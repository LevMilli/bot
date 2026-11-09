"""
DVOL regime insight helper — Deribit BTC IV band observe (never invent).

Reads live Deribit DVOL when available, else last known feature/fixture
dvol. Classifies low/mid/high observe bands. Never places fills. Floors locked.
"""
from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone

from helpers import HELPER_ONLY, PAPER_ONLY, assert_helper_only

DIGEST_NAME = "dvol_regime_digest.json"
DESK_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Observe bands only — not a fair invent. Typical BTC DVOL mid-40s.
DVOL_LOW = 40.0
DVOL_HIGH = 60.0


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


def classify_regime(dvol) -> str | None:
    n = _finite(dvol)
    if n is None or n <= 0:
        return None
    if n < DVOL_LOW:
        return "low"
    if n > DVOL_HIGH:
        return "high"
    return "mid"


def fetch_dvol(*, opener=None) -> float | None:
    """Public Deribit BTC DVOL close. None on miss — never invent."""
    import time
    import urllib.request

    end = int(time.time() * 1000)
    start = end - 2 * 3600 * 1000
    url = (
        "https://www.deribit.com/api/v2/public/get_volatility_index_data"
        f"?currency=BTC&resolution=60&start_timestamp={start}&end_timestamp={end}"
    )
    opener = opener or (
        lambda u: urllib.request.urlopen(
            urllib.request.Request(u, headers={"User-Agent": "paper-bots-dvol/1.0"}),
            timeout=12,
        ).read()
    )
    try:
        blob = opener(url)
    except Exception:
        return None
    try:
        if isinstance(blob, bytes):
            data = json.loads(blob.decode("utf-8", errors="replace"))
        elif isinstance(blob, str):
            data = json.loads(blob)
        elif isinstance(blob, dict):
            data = blob
        else:
            return None
    except json.JSONDecodeError:
        return None
    rows = ((data.get("result") or {}) if isinstance(data, dict) else {}).get("data")
    if not isinstance(rows, list) or not rows:
        return None
    last = rows[-1]
    if isinstance(last, (list, tuple)) and len(last) >= 5:
        return _finite(last[4])
    if isinstance(last, dict):
        return _finite(last.get("close") or last.get("c"))
    return None


def load_cached_dvol(root: str | None = None) -> float | None:
    """Last dvol from vol-binary fixture or feature store — never invent."""
    root = root or DESK_ROOT
    fixture = os.path.join(root, "desk_btc_vol_binary.json")
    if os.path.isfile(fixture):
        try:
            with open(fixture, encoding="utf-8") as handle:
                blob = json.load(handle)
            rows = blob.get("rows") or blob.get("quotes") or [] if isinstance(blob, dict) else blob
            for row in reversed(rows or []):
                if not isinstance(row, dict):
                    continue
                n = _finite(row.get("dvol") if row.get("dvol") is not None else row.get("sig_dvol"))
                if n is not None and n > 0:
                    return n
        except (OSError, json.JSONDecodeError):
            pass
    store = os.path.join(root, "desk_feature_store.jsonl")
    if not os.path.isfile(store):
        return None
    last = None
    try:
        with open(store, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(row, dict):
                    continue
                n = _finite(row.get("dvol") if row.get("dvol") is not None else row.get("sig_dvol"))
                if n is not None and n > 0:
                    last = n
    except OSError:
        return last
    return last


def build_digest(
    dvol=None,
    *,
    source: str = "",
    now: datetime | None = None,
) -> dict:
    assert_helper_only("dvol_regime")
    assert PAPER_ONLY and HELPER_ONLY
    now = now or datetime.now(timezone.utc)
    n = _finite(dvol)
    regime = classify_regime(n)
    return {
        "helper": "dvol_regime",
        "at": now.isoformat(),
        "paper_only": True,
        "may_place_alone": False,
        "floors_locked": True,
        "dvol": round(float(n), 4) if n is not None else None,
        "regime": regime,
        "bands": {"low_lt": DVOL_LOW, "high_gt": DVOL_HIGH},
        "source": str(source or "")[:40],
        "waiting": n is None,
        "note": (
            "Observe-only BTC DVOL regime (low<40 / mid / high>60). "
            "Missing DVOL stays null — never invent. Never softens 0.05. Never LIVE."
        ),
    }


def write_digest_from_desk(root: str | None = None, *, opener=None) -> dict:
    root = root or DESK_ROOT
    dvol = fetch_dvol(opener=opener)
    source = "deribit" if dvol is not None else ""
    if dvol is None:
        dvol = load_cached_dvol(root)
        source = "cache" if dvol is not None else ""
    digest = build_digest(dvol, source=source)
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
