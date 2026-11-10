"""
Line Shopper insight helper — sharp fair vs Kalshi ask + CLV honesty (observe-only).

Reads sports-sharp-lag quotes and the sports CLV league board. Never places
fills. Never softens venue min_edge. Paper / helper-only.
"""
from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone

from helpers import HELPER_ONLY, PAPER_ONLY, assert_helper_only

DIGEST_NAME = "line_shopper_digest.json"
DESK_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCKED_SPORTS_FLOOR = 0.06


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


def _kalshi_fee(ask: float) -> float:
    p = float(ask)
    if not (0.0 < p < 1.0):
        return 0.0
    raw = 0.07 * p * (1.0 - p)
    return math.ceil(round(raw * 100, 6)) / 100.0


def load_sharp_quotes(root: str | None = None) -> list[dict]:
    """Offline sharp_quotes.json — empty means waiting (never invent)."""
    path = os.path.join(root or DESK_ROOT, "sports-sharp-lag-paper", "sharp_quotes.json")
    if not os.path.isfile(path):
        return []
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(data, dict):
        data = data.get("quotes") or data.get("rows") or []
    if not isinstance(data, list):
        return []
    return [r for r in data if isinstance(r, dict)]


def score_quotes(
    quotes: list | None = None,
    *,
    floor: float = LOCKED_SPORTS_FLOOR,
) -> list[dict]:
    """Fee-aware sharp→Kalshi lag rows. Incomplete fair/ask skipped."""
    assert PAPER_ONLY and HELPER_ONLY
    rows = []
    for raw in quotes or []:
        if not isinstance(raw, dict):
            continue
        fair = _finite(
            raw.get("sharp_fair") if raw.get("sharp_fair") is not None else raw.get("fair")
        )
        ask = _finite(raw.get("ask"))
        if fair is None or ask is None:
            continue
        if not (0.0 < fair < 1.0 and 0.0 < ask < 1.0):
            continue
        fee = _kalshi_fee(ask)
        edge = float(fair) - float(ask) - fee
        clear = edge + 1e-12 >= float(floor)
        rows.append({
            "game": str(raw.get("game") or raw.get("ticker") or "")[:80],
            "league": str(raw.get("league") or "")[:16],
            "sharp_fair": round(float(fair), 4),
            "ask": round(float(ask), 4),
            "fee": round(fee, 4),
            "edge": round(edge, 4),
            "clear": clear,
            "floor": float(floor),
        })
    rows.sort(key=lambda r: float(r.get("edge") or -99), reverse=True)
    return rows


def build_digest(
    quotes: list | None = None,
    *,
    clv_leagues: dict | None = None,
    now: datetime | None = None,
    floor: float = LOCKED_SPORTS_FLOOR,
) -> dict:
    assert_helper_only("line_shopper")
    assert PAPER_ONLY and HELPER_ONLY
    now = now or datetime.now(timezone.utc)
    scored = score_quotes(quotes, floor=floor)
    clear_n = sum(1 for r in scored if r.get("clear"))
    best = scored[0] if scored else None
    clv = clv_leagues if isinstance(clv_leagues, dict) else {}
    leagues = [L for L in (clv.get("leagues") or []) if isinstance(L, dict)]
    return {
        "helper": "line_shopper",
        "at": now.isoformat(),
        "paper_only": True,
        "may_place_alone": False,
        "floors_locked": True,
        "floor": float(floor),
        "n": len(scored),
        "clear_n": clear_n,
        "thin_n": max(0, len(scored) - clear_n),
        "best_edge": best.get("edge") if best else None,
        "best_game": best.get("game") if best else None,
        "quotes": scored[:24],
        "clv_pass_n": clv.get("pass_n"),
        "clv_thin_n": clv.get("thin_n"),
        "clv_leagues": leagues[:8],
        "note": (
            "Observe-only line shopper: sharp fair−ask−fee vs sports 0.06, "
            "joined to CLV league honesty. Never softens floors. Never LIVE."
        ),
    }


def write_digest_from_desk(root: str | None = None) -> dict:
    root = root or DESK_ROOT
    quotes = load_sharp_quotes(root)
    clv = {}
    try:
        import desk_more
        clv = desk_more.clv_by_league(root) or {}
    except Exception:
        clv = {}
    digest = build_digest(quotes, clv_leagues=clv)
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
