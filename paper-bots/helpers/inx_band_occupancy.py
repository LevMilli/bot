"""
INX band occupancy insight helper — pre-noon 80–92¢ existence rate.

Measures how often KXINXU markets show a YES/NO ask inside the live desk
band (default 0.80–0.92). Observe-only. Never places fills. Never softens
kalshi_inx 0.02. Missing marks stay null — never invent.
"""
from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from helpers import HELPER_ONLY, PAPER_ONLY, assert_helper_only

DIGEST_NAME = "inx_band_occupancy_digest.json"
DESK_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CT = ZoneInfo("America/Chicago")
SERIES = "KXINXU"
# Desk-facing observe band (matches sized/sp blurb). Never a floor change.
DEFAULT_LO = 0.80
DEFAULT_HI = 0.92
# Pre-noon = before 12:00 CT (warm + morning scan window).
PRE_NOON_HOUR = 12
KALSHI_PUBLIC = "https://api.elections.kalshi.com/trade-api/v2"
UA = {"User-Agent": "paper-bots-inx-band-occupancy/1.0 (paper-only)"}


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


def _ask_dollars(row: dict) -> float | None:
    """Prefer yes_ask_dollars; accept yes_ask / ask in dollars or cents."""
    for key in ("yes_ask_dollars", "no_ask_dollars", "ask", "yes_ask", "no_ask"):
        raw = row.get(key)
        if raw is None:
            continue
        n = _finite(raw)
        if n is None:
            continue
        if n > 1.0 + 1e-9:
            n = n / 100.0
        if 0.0 < n < 1.0:
            return float(n)
    return None


def _parse_at(raw) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        when = raw
    else:
        try:
            when = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when.astimezone(CT)


def in_band(ask: float | None, *, lo: float = DEFAULT_LO, hi: float = DEFAULT_HI) -> bool:
    a = _finite(ask)
    if a is None:
        return False
    return float(lo) - 1e-12 <= float(a) <= float(hi) + 1e-12


def score_markets(
    markets: list | None,
    *,
    lo: float = DEFAULT_LO,
    hi: float = DEFAULT_HI,
) -> dict:
    """Live/snapshot occupancy from Kalshi market rows. Empty → thin."""
    assert PAPER_ONLY and HELPER_ONLY
    rows = [r for r in (markets or []) if isinstance(r, dict)]
    with_ask = 0
    in_band_n = 0
    samples: list[dict] = []
    for row in rows:
        ask = _ask_dollars(row)
        if ask is None:
            continue
        with_ask += 1
        hit = in_band(ask, lo=lo, hi=hi)
        if hit:
            in_band_n += 1
        if len(samples) < 12:
            samples.append({
                "ticker": str(row.get("ticker") or "")[:48],
                "ask": round(ask, 4),
                "in_band": hit,
            })
    rate = (in_band_n / with_ask) if with_ask else None
    return {
        "markets_n": len(rows),
        "with_ask": with_ask,
        "in_band_n": in_band_n,
        "occupancy": round(rate, 4) if rate is not None else None,
        "lo": float(lo),
        "hi": float(hi),
        "samples": samples,
        "thin": with_ask < 3,
        "occupied": bool(in_band_n > 0),
    }


def score_feature_history(
    rows: list | None,
    *,
    lo: float = DEFAULT_LO,
    hi: float = DEFAULT_HI,
    now: datetime | None = None,
) -> dict:
    """Historical occupancy from feature-store / eval rows with asks.

    Pre-noon rate uses America/Chicago hour < 12. Missing asks skipped
    (never invent).
    """
    assert PAPER_ONLY and HELPER_ONLY
    now = now or datetime.now(CT)
    if now.tzinfo is None:
        now = now.replace(tzinfo=CT)
    else:
        now = now.astimezone(CT)

    total_ask = 0
    total_in = 0
    pre_ask = 0
    pre_in = 0
    days: dict[str, dict] = {}
    for raw in rows or []:
        if not isinstance(raw, dict):
            continue
        series = str(raw.get("series") or raw.get("family") or "").upper()
        bot = str(raw.get("bot") or "").lower()
        if not (
            series.startswith(SERIES)
            or "inx" in bot
            or bot in ("kalshi-sp", "kalshi-sized", "kalshi_sp", "kalshi_sized")
        ):
            continue
        ask = _ask_dollars(raw)
        if ask is None:
            continue
        when = _parse_at(raw.get("at") or raw.get("ts"))
        day = str(raw.get("chicago_day") or (when.date().isoformat() if when else ""))
        hit = in_band(ask, lo=lo, hi=hi)
        total_ask += 1
        if hit:
            total_in += 1
        pre = bool(when is not None and when.hour < PRE_NOON_HOUR)
        if pre:
            pre_ask += 1
            if hit:
                pre_in += 1
        if day:
            bucket = days.setdefault(day, {"with_ask": 0, "in_band_n": 0, "pre_noon_in": 0})
            bucket["with_ask"] += 1
            if hit:
                bucket["in_band_n"] += 1
            if pre and hit:
                bucket["pre_noon_in"] += 1

    occ = (total_in / total_ask) if total_ask else None
    pre_occ = (pre_in / pre_ask) if pre_ask else None
    days_occupied = sum(1 for d in days.values() if int(d.get("in_band_n") or 0) > 0)
    return {
        "with_ask": total_ask,
        "in_band_n": total_in,
        "occupancy": round(occ, 4) if occ is not None else None,
        "pre_noon_with_ask": pre_ask,
        "pre_noon_in_band_n": pre_in,
        "pre_noon_occupancy": round(pre_occ, 4) if pre_occ is not None else None,
        "days_n": len(days),
        "days_occupied": days_occupied,
        "lo": float(lo),
        "hi": float(hi),
        "thin": total_ask < 5,
        "occupied": bool(total_in > 0),
    }


def load_feature_asks(root: str | None = None, *, limit_lines: int = 12000) -> list[dict]:
    path = os.path.join(root or DESK_ROOT, "desk_feature_store.jsonl")
    out: list[dict] = []
    if not os.path.isfile(path):
        return out
    try:
        with open(path, encoding="utf-8") as handle:
            for i, line in enumerate(handle):
                if i >= int(limit_lines):
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict):
                    out.append(row)
    except OSError:
        return []
    return out


def fetch_open_markets(*, opener=None, limit: int = 200) -> list[dict]:
    """Public Kalshi open KXINXU markets. Empty on miss — never invent."""
    import urllib.request

    opener = opener or (
        lambda u: _kalshi_gateway().urlopen(
            urllib.request.Request(u, headers=UA), timeout=12,
        ).read()
    )
    url = f"{KALSHI_PUBLIC}/markets?series_ticker={SERIES}&status=open&limit={int(limit)}"
    try:
        blob = opener(url)
    except Exception:
        return []
    try:
        if isinstance(blob, bytes):
            data = json.loads(blob.decode("utf-8", errors="replace"))
        elif isinstance(blob, str):
            data = json.loads(blob)
        elif isinstance(blob, dict):
            data = blob
        else:
            return []
    except json.JSONDecodeError:
        return []
    rows = data.get("markets") if isinstance(data, dict) else None
    return [r for r in (rows or []) if isinstance(r, dict)]


def build_digest(
    *,
    live: dict | None = None,
    history: dict | None = None,
    now: datetime | None = None,
) -> dict:
    assert_helper_only("inx_band_occupancy")
    assert PAPER_ONLY and HELPER_ONLY
    now = now or datetime.now(timezone.utc)
    live = live if isinstance(live, dict) else {}
    history = history if isinstance(history, dict) else {}
    pre = history.get("pre_noon_occupancy")
    live_occ = live.get("occupancy")
    # Prefer pre-noon history rate; fall back to live snapshot occupancy.
    headline = pre if pre is not None else live_occ
    occupied = bool(live.get("occupied") or history.get("occupied"))
    return {
        "helper": "inx_band_occupancy",
        "at": now.isoformat(),
        "paper_only": True,
        "may_place_alone": False,
        "floors_locked": True,
        "series": SERIES,
        "band": [DEFAULT_LO, DEFAULT_HI],
        "live": live,
        "history": history,
        "pre_noon_occupancy": pre,
        "live_occupancy": live_occ,
        "occupancy": headline,
        "occupied": occupied,
        "thin": bool(live.get("thin", True) and history.get("thin", True)),
        "note": (
            "Observe-only INX 80–92¢ band occupancy (live snapshot + feature history). "
            "Never softens kalshi_inx 0.02. Never LIVE."
        ),
    }


def write_digest_from_desk(root: str | None = None, *, opener=None) -> dict:
    root = root or DESK_ROOT
    live = score_markets(fetch_open_markets(opener=opener))
    history = score_feature_history(load_feature_asks(root))
    digest = build_digest(live=live, history=history)
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


def _kalshi_gateway():
    """Shared Kalshi pace / back-off / cache (paper-bots/kalshi_gateway.py)."""
    import os
    import sys

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root not in sys.path:
        sys.path.insert(0, root)
    import kalshi_gateway

    return kalshi_gateway
