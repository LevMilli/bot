"""
desk_inx.py — Positive-ROI helpers for Kalshi S&P / sized twins (paper only).

- Anti-double: sized refuses same settle-day ticker/side already open on kalshi-sp
- Twin edge: sized needs fair edge ≥ venue + 1¢ (never residual payout)
- Dual-side pick: band candidate ranking only — not venue clearance
- Independent Φ fair vs ^GSPC spot: p − ask − fee must clear kalshi_inx venue floor
- Pre/post macro: block calm before FOMC and first 30m after CPI/JOBS/FOMC prints

Fee floors unchanged. No profit guarantee.
"""
from __future__ import annotations

import json
import math
import urllib.request
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

CT = ZoneInfo("America/Chicago")

TWIN_EDGE_EXTRA = 0.01  # sized must clear venue + 1¢ vs fair edge
POST_PRINT_MINUTES = 30
PRE_FOMC_BLOCK_HOUR = 12  # CT — no new INX entries afternoon before FOMC day
SPX_YAHOO = "^GSPC"
# Afternoon INX: ~0.5% of spot per √hour until 15:00 CT (conservative).
INX_SIGMA_FRAC = 0.005
MIN_FAIR_P = 0.80
MIN_FAIR_Z = 0.60
_UA = {"User-Agent": "desk-inx-paper/1.0"}

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
    """Band-book residual payout proxy: 1 − ask − fee (no model p).

    Not independent edge — always clears venue floors in the 80–92¢ band.
    Callers must not treat this as venue/model clearance (see refuse_residual_as_edge).
    """
    a = _finite(ask)
    if a is None or not (0.0 < a < 1.0):
        return None
    return round(max(0.0, 1.0 - a - taker_fee_one(a, rate)), 4)


def refuse_residual_as_edge() -> str:
    """Hard skip reason: residual payout is not fee-aware model edge."""
    return "no independent fair — residual payout (1−ask−fee) is not edge"


def phi(z: float) -> float:
    return 0.5 * (1.0 + math.erf(float(z) / math.sqrt(2.0)))


def spx_spot() -> float | None:
    """Live S&P spot via Yahoo ^GSPC. Fail-closed → None."""
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{SPX_YAHOO}?interval=1m&range=1d"
    )
    try:
        req = urllib.request.Request(url, headers=_UA)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.load(resp)
        result = ((data.get("chart") or {}).get("result") or [None])[0]
        if not result:
            return None
        meta = result.get("meta") or {}
        px = meta.get("regularMarketPrice")
        if px is None:
            quotes = ((result.get("indicators") or {}).get("quote") or [{}])[0]
            closes = [c for c in (quotes.get("close") or []) if c is not None]
            px = closes[-1] if closes else None
        out = _finite(px)
        return out if out is not None and out > 0 else None
    except Exception:
        return None


def minutes_to_inx_settle(
    now: datetime | None = None,
    *,
    settle_time_ct: str = "15:00",
) -> float:
    now = now or datetime.now(CT)
    if now.tzinfo is None:
        now_ct = now.replace(tzinfo=CT)
    else:
        now_ct = now.astimezone(CT)
    parts = str(settle_time_ct or "15:00").split(":")
    hh = int(parts[0]) if parts else 15
    mm = int(parts[1]) if len(parts) > 1 else 0
    settle = datetime.combine(now_ct.date(), time(hh, mm), CT)
    return max((settle - now_ct).total_seconds() / 60.0, 1.0)


def inx_sigma(spot: float, minutes_left: float) -> float:
    s = float(spot)
    m = max(float(minutes_left), 15.0)
    return max(s * float(INX_SIGMA_FRAC) * math.sqrt(m / 60.0), 1e-6)


def fair_evaluate(
    pick: dict | None,
    *,
    venue_edge: float = 0.02,
    spot: float | None = None,
    now: datetime | None = None,
    settle_time_ct: str = "15:00",
    fee_rate: float = 0.07,
    min_p: float = MIN_FAIR_P,
    min_z: float = MIN_FAIR_Z,
) -> dict:
    """Independent Φ fair for a KXINXU band pick. Never treats residual as edge.

    YES ≈ P(S≥K) = Φ((S−K)/σ). Fee-aware edge = p − ask − fee must clear venue.
    Missing spot → refuse (fail-closed).
    """
    out: dict[str, Any] = {
        "ok": False,
        "paper_only": True,
        "fee_floors_locked": True,
        "reason": "",
        "p": None,
        "edge": None,
        "z": None,
        "spot": None,
        "sigma": None,
        "fee": None,
        "ask": None,
        "strike": None,
        "side": None,
        "minutes_left": None,
    }
    if not isinstance(pick, dict):
        out["reason"] = refuse_residual_as_edge()
        return out
    ask = _finite(pick.get("ask"))
    strike = _finite(pick.get("strike"))
    side = str(pick.get("side") or "").strip().lower()
    out["ask"] = ask
    out["strike"] = strike
    out["side"] = side or None
    if ask is None or not (0.0 < ask < 1.0) or strike is None or side not in ("yes", "no"):
        out["reason"] = "inx fair: pick missing ask/strike/side"
        return out
    px = _finite(spot) if spot is not None else spx_spot()
    if px is None or px <= 0:
        out["reason"] = refuse_residual_as_edge() + " (no ^GSPC spot)"
        return out
    out["spot"] = px
    minutes_left = minutes_to_inx_settle(now, settle_time_ct=settle_time_ct)
    out["minutes_left"] = round(minutes_left, 2)
    sigma = inx_sigma(px, minutes_left)
    out["sigma"] = round(sigma, 4)
    z_yes = (px - strike) / sigma
    p_yes = phi(z_yes)
    p = float(p_yes) if side == "yes" else float(1.0 - p_yes)
    z = abs(z_yes)
    fee = taker_fee_one(ask, fee_rate)
    edge = p - float(ask) - float(fee)
    out.update({
        "p": round(p, 4),
        "z": round(z, 4),
        "fee": fee,
        "edge": round(edge, 4),
    })
    need = float(venue_edge)
    if p + 1e-12 < float(min_p):
        out["reason"] = f"inx fair p {p:.3f} < {float(min_p):.2f}"
        return out
    if z + 1e-12 < float(min_z):
        out["reason"] = f"inx fair z {z:.2f} < {float(min_z):.2f}"
        return out
    if edge + 1e-12 < need:
        out["reason"] = f"inx fair edge {edge:.3f} < venue {need:.3f}"
        return out
    out["ok"] = True
    out["reason"] = ""
    return out


def rank_by_fair(
    candidates: list | None,
    *,
    venue_edge: float = 0.02,
    spot: float | None = None,
    now: datetime | None = None,
    settle_time_ct: str = "15:00",
    fee_rate: float = 0.07,
    min_p: float = MIN_FAIR_P,
    min_z: float = MIN_FAIR_Z,
) -> dict:
    """Rank band candidates by Φ fair edge (desc) among those that clear venue.

    Callers should walk `picks` after order-book re-check — a rich ask can leave
    the band or fail post-OB fair while a fee-clear sibling still fills.
    Missing spot → refuse (residual never clears).
    """
    empty = {
        "ok": False,
        "pick": None,
        "fair": None,
        "picks": [],
        "n_candidates": 0,
        "n_ok": 0,
        "reason": "no band candidates",
        "paper_only": True,
        "fee_floors_locked": True,
        "spot": None,
    }
    cands = [c for c in (candidates or []) if isinstance(c, dict)]
    empty["n_candidates"] = len(cands)
    if not cands:
        return empty
    # One spot fetch for the whole board (or fail-closed once).
    px = _finite(spot) if spot is not None else spx_spot()
    if px is None or px <= 0:
        empty["reason"] = refuse_residual_as_edge() + " (no ^GSPC spot)"
        return empty
    ranked: list[dict] = []
    last_fail = ""
    for c in cands:
        fair = fair_evaluate(
            c,
            venue_edge=venue_edge,
            spot=px,
            now=now,
            settle_time_ct=settle_time_ct,
            fee_rate=fee_rate,
            min_p=min_p,
            min_z=min_z,
        )
        if not fair.get("ok"):
            last_fail = str(fair.get("reason") or "")
            continue
        edge = _finite(fair.get("edge"))
        if edge is None:
            continue
        ranked.append({
            "pick": {**c, "fair_edge": edge, "fair_p": fair.get("p"), "fair_z": fair.get("z")},
            "fair": fair,
            "edge": edge,
        })
    ranked.sort(key=lambda row: float(row["edge"]), reverse=True)
    if not ranked:
        empty["n_ok"] = 0
        empty["spot"] = px
        empty["reason"] = last_fail or "no candidate cleared inx fair venue edge"
        return empty
    top = ranked[0]
    return {
        "ok": True,
        "pick": top["pick"],
        "fair": top["fair"],
        "picks": ranked,
        "n_candidates": len(cands),
        "n_ok": len(ranked),
        "reason": "",
        "paper_only": True,
        "fee_floors_locked": True,
        "spot": px,
    }


def pick_by_fair(
    candidates: list | None,
    *,
    venue_edge: float = 0.02,
    spot: float | None = None,
    now: datetime | None = None,
    settle_time_ct: str = "15:00",
    fee_rate: float = 0.07,
    min_p: float = MIN_FAIR_P,
    min_z: float = MIN_FAIR_Z,
) -> dict:
    """Among band candidates, pick max Φ fair edge that clears venue.

    Highest-ask pick often fails fair while a cheaper ITM side clears — use this
    instead of signal_engine.pick_trade for fee-aware fills. Missing spot → refuse.
    Prefer `rank_by_fair` when the caller retries after order-book confirmation.
    """
    return rank_by_fair(
        candidates,
        venue_edge=venue_edge,
        spot=spot,
        now=now,
        settle_time_ct=settle_time_ct,
        fee_rate=fee_rate,
        min_p=min_p,
        min_z=min_z,
    )


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
    """Sized Φ fair edge must clear venue floor + 1¢ (never residual payout)."""
    e = _finite(sized_edge)
    if e is None:
        return "twin edge: sized fair edge unknown"
    need = float(venue_edge) + float(extra)
    if e + 1e-12 < need:
        return (
            f"twin edge: sized fair {e:.3f} < venue {float(venue_edge):.2f} "
            f"+ {float(extra):.2f} (= {need:.3f})"
        )
    return ""


def inx_learn_corr_reason(
    desk,
    root: str | None,
    *,
    market: str,
    bot_id: str,
    pick: dict,
    edge,
    hour_ct,
) -> str:
    """Learn / correlation skip for one INX pick. Empty = ok.

    Callers must `continue` to the next fair-ranked sibling on a non-empty
    reason — do not day-skip while another fee-clear side/bucket may clear.
    Desk-wide entry_gate stays outside the sibling walk.
    """
    if desk is None or not isinstance(pick, dict):
        return ""
    try:
        skip = desk.learning_skip(
            desk.load_learning(root),
            market,
            desk.prob_bucket(pick.get("ask")),
            side=pick.get("side"),
            hour_ct=hour_ct,
        )
    except Exception:
        skip = ""
    if skip:
        return str(skip)
    try:
        blocked = desk.correlation_blocks(root, bot_id, pick.get("side"), edge)
    except Exception:
        blocked = ""
    return str(blocked or "")


def first_policy_ok_pick(
    ranked: list | None,
    *,
    policy_reason,
) -> dict | None:
    """Walk fair-ranked rows; return first pick where policy_reason(pick, edge) is empty.

    `ranked` items are `{pick, fair, edge}` from `rank_by_fair`. Used by scans and tests
    so learn/corr cold buckets cannot starve a fee-clear sibling.
    """
    for row in ranked or []:
        if not isinstance(row, dict):
            continue
        pick = row.get("pick")
        if not isinstance(pick, dict):
            continue
        edge = _finite(row.get("edge"))
        if edge is None:
            edge = _finite(pick.get("fair_edge"))
        reason = ""
        try:
            reason = str(policy_reason(pick, edge) or "")
        except Exception:
            reason = ""
        if reason:
            continue
        return {**row, "pick": pick, "edge": edge}
    return None


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


def densify_skip(
    root: str | None,
    *,
    bot: str,
    reason: str,
    ticker: str = "",
    side: str = "",
    edge=None,
    confidence=None,
    series: str = "KXINXU",
    note: str = "inx scan skip densify",
    features: bool = True,
) -> None:
    """Mirror fee-clear skip densify into desk_brain / skip_board (+ features).

    Learning.md already gets logger.learn on most INX skips; without this,
    hologram skip_board by_bot stays empty for kalshi-sp / kalshi-sized while
    the run printed a real NO TRADE reason. Observe only — never LIVE / arm.
    """
    why = str(reason or "").strip()
    if not why or not root:
        return
    bot_id = str(bot or "").strip() or "kalshi-sp"
    try:
        import desk_brain
        desk_brain.record_decision(
            root,
            bot=bot_id,
            action="skip",
            ticker=str(ticker or ""),
            side=str(side or ""),
            edge=edge,
            confidence=confidence,
            reasons=[why],
            note=str(note or "")[:160],
        )
    except Exception:
        pass
    if not features:
        return
    try:
        import desk_living
        desk_living.record_eval_features(
            root,
            bot=bot_id,
            action="skip",
            series=str(series or "KXINXU"),
            ticker=str(ticker or ""),
            ev={
                "side": side or None,
                "edge": edge,
                "confidence": confidence,
                "ticker": ticker or None,
            },
            reasons=[why],
            note=why[:160],
        )
    except Exception:
        pass


def self_check() -> None:
    from datetime import date as d

    assert residual_edge(0.85) is not None
    assert "not edge" in refuse_residual_as_edge().lower()
    assert abs(phi(0.0) - 0.5) < 1e-9
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
    # Fair: deep ITM yes clears; missing spot refuses; ATM thin skips.
    now = datetime(2026, 11, 10, 13, 0, tzinfo=CT)
    deep = fair_evaluate(
        {"ticker": "T", "side": "yes", "ask": 0.85, "strike": 7300},
        venue_edge=0.02, spot=7500.0, now=now,
    )
    assert deep["ok"] is True and deep["edge"] is not None and deep["edge"] >= 0.02
    # Missing/invalid spot → refuse (no network in self_check).
    miss = fair_evaluate(
        {"ticker": "T", "side": "yes", "ask": 0.85, "strike": 7300},
        venue_edge=0.02, spot=-1.0, now=now,
    )
    assert miss["ok"] is False and "residual" in (miss.get("reason") or "").lower()
    thin = fair_evaluate(
        {"ticker": "T", "side": "yes", "ask": 0.88, "strike": 7490},
        venue_edge=0.02, spot=7500.0, now=now,
    )
    assert thin["ok"] is False
    # Highest-ask RICH fails fair; VALUE clears — pick_by_fair must choose VALUE.
    board = [
        {"ticker": "RICH", "side": "yes", "ask": 0.90, "strike": 7480},
        {"ticker": "VALUE", "side": "yes", "ask": 0.82, "strike": 7200},
    ]
    chosen = pick_by_fair(board, venue_edge=0.02, spot=7500.0, now=now)
    assert chosen["ok"] is True and chosen["pick"]["ticker"] == "VALUE"
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
