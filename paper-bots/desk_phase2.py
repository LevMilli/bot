"""
desk_phase2.py — Phase 2 quality track (make more of each *good* trade).

1) Regime-tagged proven_80 (calm+elevated only)
2) Adapt A/B ledger (stake with vs without adapt)
3) Sports gap-decay exit helper
4) Scale-out recycle suggestion
5) Hillclimb week lock helpers

Paper only. Fee floors unchanged. No profit guarantee.
"""
from __future__ import annotations

import json
import math
import os
import time
from typing import Any

PHASE2_NAME = "desk_phase2_state.json"
AB_NAME = "desk_adapt_ab_ledger.json"

# Gap decay: sports edge that existed at tip dies toward Q3/late game.
GAP_DECAY_LIVE_FRAC = 0.55  # keep at most 55% of entry gap once "late"
GAP_DECAY_MINUTES_INTO = 35  # rough "late" for hockey/basketball paper

# Scale-out: free risk when green enough.
SCALE_OUT_GREEN_FRAC = 0.35  # unrealized ≥ 35% of risk → suggest clip 1/3


def phase2_path(root: str | None = None) -> str:
    base = root or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, PHASE2_NAME)


def ab_path(root: str | None = None) -> str:
    base = root or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, AB_NAME)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _finite(x) -> float | None:
    try:
        n = float(x)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(n):
        return None
    return n


def _empty_phase2() -> dict:
    return {
        "paper_only": True,
        "version": 1,
        "gap_decay_exits": [],
        "scale_outs": [],
        "hillclimb_locks": [],
        "last_at": None,
    }


def load_phase2(root: str | None = None) -> dict:
    path = phase2_path(root)
    if not os.path.exists(path):
        return _empty_phase2()
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            return _empty_phase2()
    except (OSError, json.JSONDecodeError):
        return _empty_phase2()
    base = _empty_phase2()
    base.update({k: data.get(k, base[k]) for k in base})
    for key in ("gap_decay_exits", "scale_outs", "hillclimb_locks"):
        if not isinstance(base.get(key), list):
            base[key] = []
    return base


def save_phase2(state: dict, root: str | None = None) -> None:
    path = phase2_path(root)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    state = dict(state)
    state["paper_only"] = True
    for key, lim in (("gap_decay_exits", 300), ("scale_outs", 300), ("hillclimb_locks", 52)):
        rows = list(state.get(key) or [])
        if len(rows) > lim:
            state[key] = rows[-lim:]
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
        handle.write("\n")
    os.replace(tmp, path)


def load_ab(root: str | None = None) -> dict:
    path = ab_path(root)
    if not os.path.exists(path):
        return {"paper_only": True, "version": 1, "rows": [], "last_at": None}
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            return {"paper_only": True, "version": 1, "rows": [], "last_at": None}
    except (OSError, json.JSONDecodeError):
        return {"paper_only": True, "version": 1, "rows": [], "last_at": None}
    if not isinstance(data.get("rows"), list):
        data["rows"] = []
    data["paper_only"] = True
    return data


def save_ab(state: dict, root: str | None = None) -> None:
    path = ab_path(root)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    state = dict(state)
    state["paper_only"] = True
    rows = list(state.get("rows") or [])
    if len(rows) > 4000:
        rows = rows[-4000:]
    state["rows"] = rows
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
        handle.write("\n")
    os.replace(tmp, path)


# --- 1. Regime-tagged proven_80 -------------------------------------------

def history_for_proven(
    history: list | None,
    *,
    allow_regimes: tuple[str, ...] = ("calm", "elevated"),
) -> list:
    """
    Keep settled rows whose entry vol regime is calm/elevated.
    Untagged rows count (legacy fills) so we don't starve proven_80 to zero overnight.
    """
    allow = {str(r).lower() for r in allow_regimes}
    out = []
    for row in history or []:
        if not isinstance(row, dict):
            continue
        if _finite(row.get("pnl")) is None:
            continue
        regime = row.get("vol_regime") or row.get("adapt_regime") or row.get("regime")
        if regime is None or str(regime).lower() in allow or str(regime).lower() in ("", "unknown"):
            out.append(row)
    return out


def proven_80_regime_aware(history: list | None, window_days: int = 20) -> dict:
    """proven_80 using only calm+elevated (plus untagged) settles."""
    import desk_adapt

    filtered = history_for_proven(history)
    perf = desk_adapt.performance_from_history(filtered, window_days=window_days)
    perf["regime_filter"] = ["calm", "elevated", "untagged"]
    perf["n_raw"] = len([r for r in (history or []) if isinstance(r, dict) and _finite(r.get("pnl")) is not None])
    perf["n_filtered"] = int(perf.get("n") or 0)
    return perf


# --- 2. Adapt A/B ledger --------------------------------------------------

def record_adapt_ab(
    root: str | None,
    *,
    bot: str,
    ticker: str = "",
    stake_flat: float,
    stake_adapt: float,
    mult: float = 1.0,
    regime: str = "",
    play_safe: bool = False,
    play_big: bool = False,
    fill_id: str = "",
) -> dict:
    """Every fill stores what stake would have been without adapt."""
    flat = _finite(stake_flat) or 0.0
    adapted = _finite(stake_adapt) or 0.0
    row = {
        "at": _now(),
        "bot": bot,
        "ticker": ticker,
        "stake_flat": round(flat, 2),
        "stake_adapt": round(adapted, 2),
        "delta": round(adapted - flat, 2),
        "mult": round(float(mult or 1.0), 4),
        "regime": str(regime or "")[:32],
        "play_safe": bool(play_safe),
        "play_big": bool(play_big),
        "fill_id": fill_id[:80],
        "pnl": None,  # filled later on settle
    }
    state = load_ab(root)
    state.setdefault("rows", []).append(row)
    state["last_at"] = row["at"]
    save_ab(state, root)
    return row


def attach_ab_pnl(root: str | None, fill_id: str, pnl) -> bool:
    p = _finite(pnl)
    if not fill_id or p is None:
        return False
    state = load_ab(root)
    found = False
    for row in reversed(state.get("rows") or []):
        if row.get("fill_id") == fill_id and row.get("pnl") is None:
            row["pnl"] = round(p, 4)
            # Counterfactual: scale pnl by flat/adapt ratio if adapt sized differently.
            adapt = _finite(row.get("stake_adapt")) or 0.0
            flat = _finite(row.get("stake_flat")) or 0.0
            if adapt > 1e-9:
                row["pnl_flat_cf"] = round(p * (flat / adapt), 4)
            found = True
            break
    if found:
        state["last_at"] = _now()
        save_ab(state, root)
    return found


def adapt_ab_summary(root: str | None = None) -> dict:
    rows = [r for r in (load_ab(root).get("rows") or []) if isinstance(r, dict)]
    settled = [r for r in rows if r.get("pnl") is not None]
    n = len(settled)
    pnl_adapt = sum(float(r["pnl"]) for r in settled) if n else None
    pnl_flat = sum(float(r.get("pnl_flat_cf") if r.get("pnl_flat_cf") is not None else r["pnl"]) for r in settled) if n else None
    delta = None if pnl_adapt is None or pnl_flat is None else round(pnl_adapt - pnl_flat, 4)
    return {
        "paper_only": True,
        "n_fills": len(rows),
        "n_settled": n,
        "pnl_adapt": None if pnl_adapt is None else round(pnl_adapt, 4),
        "pnl_flat_cf": None if pnl_flat is None else round(pnl_flat, 4),
        "adapt_edge_vs_flat": delta,
        "adapt_wins": bool(delta is not None and delta + 1e-12 >= 0),
        "note": "If adapt underperforms flat 2 weeks, shrink play-big before touching entry floors.",
        "recent": rows[-15:],
    }


# --- 3. Sports gap-decay --------------------------------------------------

def sports_gap_decay_exit(
    *,
    gap_at_entry,
    gap_now,
    minutes_since_open=None,
    live: bool = True,
) -> dict:
    """
    Suggest exit when live gap has decayed below GAP_DECAY_LIVE_FRAC of entry
    after the game is well underway.
    """
    ge = _finite(gap_at_entry)
    gn = _finite(gap_now)
    mins = _finite(minutes_since_open)
    out = {
        "exit": False,
        "reason": "",
        "gap_at_entry": ge,
        "gap_now": gn,
        "minutes_since_open": mins,
    }
    if ge is None or gn is None or ge <= 0:
        return out
    if not live:
        return out
    late = mins is None or mins >= GAP_DECAY_MINUTES_INTO
    if late and gn + 1e-12 < ge * GAP_DECAY_LIVE_FRAC:
        out["exit"] = True
        out["reason"] = (
            f"gap-decay: now {gn:.3f} < {GAP_DECAY_LIVE_FRAC:.0%} of entry {ge:.3f}"
        )
    return out


def remember_gap_decay(root: str | None, row: dict) -> None:
    state = load_phase2(root)
    state.setdefault("gap_decay_exits", []).append({**row, "at": _now()})
    state["last_at"] = _now()
    save_phase2(state, root)


# --- 4. Scale-out recycle -------------------------------------------------

def scale_out_suggestion(
    *,
    risk,
    unrealized_pnl,
    clip_frac: float = 1.0 / 3.0,
) -> dict:
    r = _finite(risk) or 0.0
    u = _finite(unrealized_pnl) or 0.0
    if r <= 0:
        return {"scale_out": False, "clip_risk": 0.0, "reason": "no risk"}
    if u + 1e-12 < r * SCALE_OUT_GREEN_FRAC:
        return {
            "scale_out": False,
            "clip_risk": 0.0,
            "reason": f"unrealized {u:.2f} < {SCALE_OUT_GREEN_FRAC:.0%} of risk {r:.2f}",
        }
    clip = round(r * float(clip_frac), 2)
    return {
        "scale_out": True,
        "clip_risk": clip,
        "reason": f"green ≥{SCALE_OUT_GREEN_FRAC:.0%} — clip ~{clip_frac:.0%} (${clip:.2f}) to free risk",
    }


def remember_scale_out(root: str | None, bot: str, ticker: str, plan: dict) -> dict:
    row = {"at": _now(), "bot": bot, "ticker": ticker, **plan}
    state = load_phase2(root)
    state.setdefault("scale_outs", []).append(row)
    state["last_at"] = row["at"]
    save_phase2(state, root)
    return row


# --- 5. Hillclimb week lock -----------------------------------------------

def lock_hillclimb_week(root: str | None, lever: str, note: str = "") -> dict:
    row = {
        "at": _now(),
        "lever": lever,
        "note": (note or "one lever this week — do not thrash")[:160],
    }
    state = load_phase2(root)
    state.setdefault("hillclimb_locks", []).append(row)
    state["last_at"] = row["at"]
    save_phase2(state, root)
    return row


def phase2_summary(root: str | None = None) -> dict:
    st = load_phase2(root)
    return {
        "paper_only": True,
        "version": 1,
        "adapt_ab": adapt_ab_summary(root),
        "gap_decay_exit_count": len(st.get("gap_decay_exits") or []),
        "scale_out_count": len(st.get("scale_outs") or []),
        "hillclimb_locks": list(st.get("hillclimb_locks") or [])[-4:],
        "rules": {
            "proven_regimes": ["calm", "elevated", "untagged"],
            "gap_decay_frac": GAP_DECAY_LIVE_FRAC,
            "gap_decay_minutes": GAP_DECAY_MINUTES_INTO,
            "scale_out_green_frac": SCALE_OUT_GREEN_FRAC,
        },
        "note": "Phase 2 quality — make more of each good trade; fee floors untouched.",
    }


def self_check() -> None:
    tagged = [
        {"pnl": 5, "vol_regime": "calm"},
        {"pnl": 5, "vol_regime": "elevated"},
        {"pnl": -1, "vol_regime": "extreme"},
        {"pnl": 5},  # untagged counts
    ]
    filt = history_for_proven(tagged)
    assert len(filt) == 3
    decay = sports_gap_decay_exit(gap_at_entry=0.10, gap_now=0.04, minutes_since_open=40, live=True)
    assert decay["exit"] is True
    early = sports_gap_decay_exit(gap_at_entry=0.10, gap_now=0.04, minutes_since_open=5, live=True)
    assert early["exit"] is False
    so = scale_out_suggestion(risk=30, unrealized_pnl=12)
    assert so["scale_out"] is True
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        row = record_adapt_ab(
            tmp, bot="btc15m", ticker="T", stake_flat=40, stake_adapt=20, mult=0.5, fill_id="f1",
        )
        assert row["delta"] == -20
        assert attach_ab_pnl(tmp, "f1", 4.0)
        summary = adapt_ab_summary(tmp)
        assert summary["n_settled"] == 1
        # adapt sized half → flat CF doubles pnl
        assert summary["pnl_flat_cf"] == 8.0


if __name__ == "__main__":
    self_check()
    print("desk_phase2 self_check ok")
