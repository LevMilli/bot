"""
Helper advice JSON schema v1 validator.

Requires floors_locked (or fee_floors_locked) + ttl > 0.
Rejects any venue_min_edge soften below locked floors.
Helpers never place alone. Paper only.
"""
from __future__ import annotations

from typing import Any

PAPER_ONLY = True
HELPER_ONLY = True
SCHEMA_VERSION = 1

# Locked venue floors — never soften (mirror desk_profit / desk_roi_plan).
LOCKED_VENUE_FLOORS = {
    "kalshi_sports": 0.06,
    "kalshi_btc15m": 0.05,
    "kalshi_commodity15m": 0.05,
    "kalshi_inx": 0.02,
    "solana_dex": 0.02,
    "coinbase_spot": 0.05,
    "binance_btc_carry": 0.02,
    "coinbase_btc_carry": 0.02,
    "kalshi_econ": 0.05,
    "equity_qqq": 0.02,
}

# Aliases helpers may use for venue keys.
_VENUE_ALIASES = {
    "sports": "kalshi_sports",
    "kalshi_sports": "kalshi_sports",
    "btc": "kalshi_btc15m",
    "btc15m": "kalshi_btc15m",
    "kalshi_btc15m": "kalshi_btc15m",
    "commodity": "kalshi_commodity15m",
    "commodity15m": "kalshi_commodity15m",
    "kalshi_commodity15m": "kalshi_commodity15m",
    "inx": "kalshi_inx",
    "kalshi_inx": "kalshi_inx",
    "dex": "solana_dex",
    "solana_dex": "solana_dex",
    "coinbase": "coinbase_spot",
    "coinbase_spot": "coinbase_spot",
    "btc_carry": "coinbase_btc_carry",
    "coinbase_btc_carry": "coinbase_btc_carry",
    "binance_btc_carry": "binance_btc_carry",
    "econ": "kalshi_econ",
    "fed": "kalshi_econ",
    "fedwatch": "kalshi_econ",
    "kalshi_econ": "kalshi_econ",
}


def _finite(x) -> float | None:
    try:
        n = float(x)
    except (TypeError, ValueError):
        return None
    if n != n:  # NaN
        return None
    return n


def _resolve_venue(key: str) -> str | None:
    raw = str(key or "").strip()
    if not raw:
        return None
    if raw in LOCKED_VENUE_FLOORS:
        return raw
    return _VENUE_ALIASES.get(raw) or _VENUE_ALIASES.get(raw.lower())


def _floors_locked_flag(payload: dict) -> bool:
    if payload.get("floors_locked") is True:
        return True
    if payload.get("fee_floors_locked") is True:
        return True
    return False


def _iter_edge_proposals(payload: dict):
    """Yield (venue_key, proposed_edge) from common advice shapes."""
    direct = payload.get("venue_min_edge")
    if isinstance(direct, dict):
        for k, v in direct.items():
            yield str(k), _finite(v)
    elif _finite(direct) is not None and payload.get("venue"):
        yield str(payload.get("venue")), _finite(direct)

    advice = payload.get("advice") if isinstance(payload.get("advice"), dict) else {}
    if isinstance(advice.get("venue_min_edge"), dict):
        for k, v in advice["venue_min_edge"].items():
            yield str(k), _finite(v)
    soften = payload.get("soften_venue_min_edge")
    if isinstance(soften, dict):
        for k, v in soften.items():
            yield str(k), _finite(v)
    edges = payload.get("edges") if isinstance(payload.get("edges"), dict) else {}
    for k, v in edges.items():
        if "edge" in str(k).lower() or str(k) in LOCKED_VENUE_FLOORS or str(k) in _VENUE_ALIASES:
            yield str(k), _finite(v)


def validate_helper_advice(payload: Any) -> tuple[bool, str]:
    """
    Validate helper advice payload.

    Returns (ok, reason). ok=False when:
      - missing floors_locked / fee_floors_locked True
      - ttl missing or ≤ 0
      - any venue_min_edge proposal below locked floor
    """
    if not isinstance(payload, dict):
        return False, "payload must be a dict"
    if not _floors_locked_flag(payload):
        return False, "floors_locked (or fee_floors_locked) must be True"
    ttl = _finite(payload.get("ttl"))
    if ttl is None:
        ttl = _finite(payload.get("ttl_sec"))
    if ttl is None or ttl <= 0:
        return False, "ttl must be > 0"
    for venue_key, edge in _iter_edge_proposals(payload):
        if edge is None:
            continue
        resolved = _resolve_venue(venue_key)
        if not resolved:
            # Unknown venue key with an edge proposal — reject soften attempts.
            if edge is not None:
                return False, f"unknown venue_min_edge key {venue_key!r}"
            continue
        floor = float(LOCKED_VENUE_FLOORS[resolved])
        if edge + 1e-12 < floor:
            return (
                False,
                f"venue_min_edge soften rejected for {resolved}: "
                f"{edge} < locked floor {floor}",
            )
    return True, "ok"
