"""
desk_inx.py — Positive-ROI helpers for Kalshi S&P / sized twins (paper only).

- Anti-double: sized refuses same settle-day ticker/side already open on kalshi-sp
- Twin edge: sized needs residual edge ≥ S&P twin venue edge + 1¢
- Dual-side pick: prefer max (1 − ask − fee) capital efficiency inside the band
- Pre/post macro: block calm before FOMC and first 30m after CPI/JOBS/FOMC prints

Fee floors unchanged. No profit guarantee.
"""
from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

CT = ZoneInfo("America/Chicago")

TWIN_EDGE_EXTRA = 0.01  # sized must clear venue + 1¢ vs residual edge proxy
POST_PRINT_MINUTES = 30
PRE_FOMC_BLOCK_HOUR = 12  # CT — no new INX entries afternoon before FOMC day

# Typical release clocks (CT). Used for post-print 30m when day is tradeable.
MACRO_RELEASE_CT = {
    "CPI": time(8, 30),
    "JOBS": time(8, 30),
    "GDP": time(7, 30),
    "PCE": time(7, 30),
    "FOMC": time(13, 0),  # statement ~1pm CT on decision days
}

MACRO_KEYS = frozenset(MACRO_RELEASE_CT)


def _finite(x) -> float | None:
    try:
        n = float(x)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(n):
        return None
    return n


def taker_fee_one(ask: float, rate: float = 0.07) -> float:
    raw = rate * float(ask) * (1.0 - float(ask))
    return math.ceil(raw * 100 - 1e-12) / 100.0


def residual_edge(ask, *, rate: float = 0.07) -> float | None:
    """Band-book residual edge proxy: 1 − ask − fee (no model p)."""
    a = _finite(ask)
    if a is None or not (0.0 < a < 1.0):
        return None
    return round(max(0.0, 1.0 - a - taker_fee_one(a, rate)), 4)


def dual_side_pick(candidates: list, *, band_lo: float, band_hi: float) -> dict | None:
    """
    Among candidates in ask band, pick max residual edge / ask (capital efficiency).
    Does not soften venue floors — caller still enforces kalshi_inx min_edge.
    """
    best = None
    best_score = None
    for c in candidates or []:
        if not isinstance(c, dict):
            continue
        ask = _finite(c.get("ask"))
        if ask is None or not (band_lo - 1e-12 <= ask <= band_hi + 1e-12):
            continue
        edge = residual_edge(ask)
        if edge is None:
            continue
        score = edge / ask if ask > 1e-12 else 0.0
        if best_score is None or score > best_score + 1e-12:
            best_score = score
            best = {**c, "residual_edge": edge, "efficiency": round(score, 6)}
    return best


def sibling_open_tickers(sp_state: dict | None) -> set[str]:
    """Tickers currently open on the kalshi-sp paper book."""
    out = set()
    if not isinstance(sp_state, dict):
        return out
    for pos in sp_state.get("open") or []:
        if not isinstance(pos, dict):
            continue
        t = str(pos.get("ticker") or "").strip()
        if t:
            out.add(t)
    return out


def anti_double_blocks(
    *,
    ticker: str,
    sp_state: dict | None,
) -> str:
    """Sized must not stack the same KXINXU ticker already open on S&P twin."""
    t = str(ticker or "").strip()
    if not t:
        return ""
    open_t = sibling_open_tickers(sp_state)
    if t in open_t:
        return (
            f"anti-double: kalshi-sp already holds {t} — sized skips same settle ticker"
        )
    return ""


def twin_edge_blocks(
    *,
    sized_edge,
    venue_edge: float = 0.02,
    extra: float = TWIN_EDGE_EXTRA,
) -> str:
    """Sized residual edge must clear venue floor + 1¢."""
    e = _finite(sized_edge)
    if e is None:
        return "twin edge: sized residual edge unknown"
    need = float(venue_edge) + float(extra)
    if e + 1e-12 < need:
        return (
            f"twin edge: sized residual {e:.3f} < venue {float(venue_edge):.2f} "
            f"+ {float(extra):.2f} (= {need:.3f})"
        )
    return ""


def _reasons_for_day(skip_days: dict, day: date) -> list[str]:
    raw = skip_days.get(str(day)) if isinstance(skip_days, dict) else None
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw]
    return [str(raw)]


def macro_keys_on(skip_days: dict, day: date) -> list[str]:
    reasons = _reasons_for_day(skip_days, day)
    hit = []
    blob = "+".join(reasons).upper()
    for key in MACRO_KEYS:
        if key in blob:
            hit.append(key)
    return hit


def post_macro_blackout(
    now: datetime,
    day: date,
    skip_days: dict | None,
) -> dict:
    """
    Block until release + 30m on CPI/JOBS/FOMC/GDP/PCE days.
    Works with full-day calendar skips (redundant) and with future partial opens.
    """
    skip_days = skip_days or {}
    keys = macro_keys_on(skip_days, day)
    if not keys:
        return {"blocked": False, "keys": [], "reason": ""}
    # Normalize now to CT
    if now.tzinfo is None:
        now_ct = now.replace(tzinfo=CT)
    else:
        now_ct = now.astimezone(CT)
    clear_at = None
    for key in keys:
        release = MACRO_RELEASE_CT.get(key)
        if release is None:
            continue
        moment = datetime.combine(day, release, CT) + timedelta(minutes=POST_PRINT_MINUTES)
        if clear_at is None or moment > clear_at:
            clear_at = moment
    if clear_at is None:
        return {"blocked": False, "keys": keys, "reason": ""}
    if now_ct < clear_at:
        return {
            "blocked": True,
            "keys": keys,
            "clear_at": clear_at.isoformat(),
            "reason": (
                f"post-macro blackout ({'+'.join(keys)}): wait until "
                f"{clear_at:%H:%M} CT (+{POST_PRINT_MINUTES}m after print)"
            ),
        }
    return {"blocked": False, "keys": keys, "clear_at": clear_at.isoformat(), "reason": ""}


def pre_fomc_calm_block(
    now: datetime,
    day: date,
    skip_days: dict | None,
) -> dict:
    """Afternoon before an FOMC day: skip new INX entries (calm-before-spike)."""
    skip_days = skip_days or {}
    tomorrow = day + timedelta(days=1)
    if "FOMC" not in macro_keys_on(skip_days, tomorrow):
        return {"blocked": False, "reason": ""}
    if now.tzinfo is None:
        now_ct = now.replace(tzinfo=CT)
    else:
        now_ct = now.astimezone(CT)
    if now_ct.hour >= PRE_FOMC_BLOCK_HOUR:
        return {
            "blocked": True,
            "reason": (
                f"pre-FOMC calm: FOMC on {tomorrow} — no new INX entries after "
                f"{PRE_FOMC_BLOCK_HOUR:02d}:00 CT"
            ),
        }
    return {"blocked": False, "reason": ""}


def inx_entry_blocks(
    *,
    now: datetime,
    day: date,
    skip_days: dict | None,
) -> str:
    """Combined INX time gates (post-print + pre-FOMC). Empty = ok."""
    post = post_macro_blackout(now, day, skip_days)
    if post.get("blocked"):
        return str(post.get("reason") or "post-macro blackout")
    pre = pre_fomc_calm_block(now, day, skip_days)
    if pre.get("blocked"):
        return str(pre.get("reason") or "pre-FOMC calm")
    return ""


def self_check() -> None:
    from datetime import date as d

    assert residual_edge(0.85) is not None
    cands = [
        {"ticker": "A", "ask": 0.90, "side": "yes"},
        {"ticker": "B", "ask": 0.82, "side": "yes"},
    ]
    pick = dual_side_pick(cands, band_lo=0.80, band_hi=0.92)
    assert pick and pick["ticker"] == "B"  # more residual edge / ask
    assert anti_double_blocks(ticker="T1", sp_state={"open": [{"ticker": "T1"}]})
    assert not anti_double_blocks(ticker="T2", sp_state={"open": [{"ticker": "T1"}]})
    assert twin_edge_blocks(sized_edge=0.02, venue_edge=0.02, extra=0.01)
    assert not twin_edge_blocks(sized_edge=0.04, venue_edge=0.02, extra=0.01)
    skip = {"2026-11-10": ["CPI"], "2026-10-28": ["FOMC"]}
    # CPI day 08:00 CT — still in blackout
    blocked = post_macro_blackout(
        datetime(2026, 11, 10, 8, 0, tzinfo=CT), d(2026, 11, 10), skip,
    )
    assert blocked["blocked"] is True
    clear = post_macro_blackout(
        datetime(2026, 11, 10, 9, 5, tzinfo=CT), d(2026, 11, 10), skip,
    )
    assert clear["blocked"] is False
    # Day before FOMC afternoon
    pre = pre_fomc_calm_block(
        datetime(2026, 10, 27, 13, 0, tzinfo=CT), d(2026, 10, 27), skip,
    )
    assert pre["blocked"] is True


if __name__ == "__main__":
    self_check()
    print("desk_inx self_check ok")
