"""
desk_phase3.py — Expansion track after Phase 2 quality.

X3 Strike-ladder companion (KXBTCD-style): when spot is mid-ladder, prefer the
deepest ask that still clears model ≥80% + fee-aware edge.
X4 COMBO paper simulator: joint EV with correlation haircut (paper only).

No live orders. Fee floors unchanged. No profit guarantee.
"""
from __future__ import annotations

import json
import math
import os
import time
from typing import Any, Iterable

PHASE3_NAME = "desk_phase3_state.json"

# Correlation haircut for same-direction crypto legs in a parlay.
PARLAY_CORR_HAIRCUT = 0.35  # multiply product-of-marginals by (1 - haircut * shared)

# Ladder: prefer depth, require model floor.
LADDER_MIN_P = 0.80
LADDER_MIN_DEPTH = 5


def phase3_path(root: str | None = None) -> str:
    base = root or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, PHASE3_NAME)


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


def _empty() -> dict:
    return {
        "paper_only": True,
        "version": 1,
        "ladder_picks": [],
        "parlay_sims": [],
        "last_at": None,
    }


def load_phase3(root: str | None = None) -> dict:
    path = phase3_path(root)
    if not os.path.exists(path):
        return _empty()
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            return _empty()
    except (OSError, json.JSONDecodeError):
        return _empty()
    base = _empty()
    base.update({k: data.get(k, base[k]) for k in base})
    for key in ("ladder_picks", "parlay_sims"):
        if not isinstance(base.get(key), list):
            base[key] = []
    return base


def save_phase3(state: dict, root: str | None = None) -> None:
    path = phase3_path(root)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    state = dict(state)
    state["paper_only"] = True
    for key, lim in (("ladder_picks", 400), ("parlay_sims", 400)):
        rows = list(state.get(key) or [])
        if len(rows) > lim:
            state[key] = rows[-lim:]
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
        handle.write("\n")
    os.replace(tmp, path)


def ladder_distance_score(spot, strike) -> float:
    """Lower is closer to the money (mid-ladder sweet spot for deep asks)."""
    s = _finite(spot)
    k = _finite(strike)
    if s is None or k is None or s <= 0:
        return 1e9
    return abs(k - s) / s


def evaluate_ladder_rung(
    *,
    spot,
    strike,
    ask,
    fee=0.0,
    depth=None,
    model_p=None,
    min_edge: float = 0.05,
    min_p: float = LADDER_MIN_P,
    min_depth: float = LADDER_MIN_DEPTH,
) -> dict:
    """Score one ladder strike as a paper candidate."""
    reasons = []
    s = _finite(spot)
    k = _finite(strike)
    a = _finite(ask)
    f = _finite(fee) or 0.0
    d = _finite(depth)
    p = _finite(model_p)
    if s is None or k is None or a is None:
        return {"ok": False, "reasons": ["missing spot/strike/ask"], "score": 0.0}
    # Directional model: YES if spot > strike else NO — caller should pass matching ask/p.
    if p is None:
        # Soft distance prior — not a sole entry reason (still needs ask+edge).
        dist = ladder_distance_score(s, k)
        # Rough: closer ITM → higher p; far OTM → lower. Cap at 0.79 so untagged never auto-clears 80.
        p = max(0.50, min(0.79, 0.79 - dist * 8.0))
        reasons.append("model_p estimated from distance (weak — prefer Φ(z) when available)")
    edge = float(p) - float(a) - float(f)
    if p + 1e-12 < min_p:
        reasons.append(f"p {p:.3f} < {min_p:.2f}")
    if edge + 1e-12 < min_edge:
        reasons.append(f"edge {edge:.3f} < {min_edge:.2f}")
    if d is not None and d + 1e-12 < min_depth:
        reasons.append(f"depth {d:.0f} < {min_depth:.0f}")
    ok = not any(" < " in r for r in reasons if r.startswith(("p ", "edge ", "depth ")))
    # Prefer deeper books at similar edge; mild preference for closer strikes.
    depth_term = 1.0
    if d is not None and d > 0:
        depth_term = 1.0 + min(d, 80.0) / 200.0
    dist = ladder_distance_score(s, k)
    prox = 1.0 / (1.0 + dist * 20.0)
    score = max(0.0, edge) * max(0.0, min(p, 1.0)) * depth_term * (0.7 + 0.3 * prox)
    return {
        "ok": ok and edge >= min_edge and p >= min_p and (d is None or d >= min_depth),
        "reasons": reasons,
        "score": round(score, 6),
        "edge": round(edge, 4),
        "p": round(float(p), 4),
        "ask": a,
        "fee": f,
        "depth": d,
        "strike": k,
        "spot": s,
        "dist": round(dist, 6),
    }


def score_ladder_rungs(rows: Iterable[dict], *, min_edge: float = 0.05) -> list[dict]:
    """Score every ladder row; sorted best-first (score, then depth)."""
    scored = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        ev = evaluate_ladder_rung(
            spot=row.get("spot"),
            strike=row.get("strike") or row.get("target"),
            ask=row.get("ask"),
            fee=row.get("fee") or 0.0,
            depth=row.get("depth"),
            model_p=row.get("model_p") or row.get("p"),
            min_edge=min_edge,
        )
        scored.append({**row, **ev})
    scored.sort(key=lambda r: (-float(r.get("score") or 0), -float(r.get("depth") or 0)))
    return scored


def pick_ladder_rung(
    rows: Iterable[dict],
    *,
    min_edge: float = 0.05,
    require_ok: bool = True,
) -> dict | None:
    """
    Among ladder market rows (each with spot/strike/ask/fee/depth/model_p),
    pick the best rung. require_ok=True (default) keeps fee+80% gates;
    require_ok=False ranks shadow companions when Φ(z) is not yet attached.
    """
    scored = score_ladder_rungs(rows, min_edge=min_edge)
    if not scored:
        return None
    if require_ok:
        ok_rows = [r for r in scored if r.get("ok")]
        return ok_rows[0] if ok_rows else None
    return scored[0]


def remember_ladder_pick(root: str | None, pick: dict) -> dict:
    state = load_phase3(root)
    row = {
        "at": _now(),
        "ticker": pick.get("ticker"),
        "strike": pick.get("strike"),
        "ask": pick.get("ask"),
        "edge": pick.get("edge"),
        "p": pick.get("p"),
        "depth": pick.get("depth"),
        "score": pick.get("score"),
        "ok": bool(pick.get("ok")),
        "shadow_only": not bool(pick.get("ok")),
        "paper_only": True,
    }
    state.setdefault("ladder_picks", []).append(row)
    state["last_at"] = row["at"]
    save_phase3(state, root)
    return row


# --- COMBO / parlay simulator ---------------------------------------------

def parlay_joint_ev(legs: list[dict], *, corr_haircut: float = PARLAY_CORR_HAIRCUT) -> dict:
    """
    Joint EV with correlation haircut for same-direction crypto legs.
    Each leg: fair (p), ask, fee. Stake normalized to $1 for EV units.
    """
    if len(legs) < 2:
        return {"ok": False, "ev": None, "joint_p": None, "reasons": ["need ≥2 legs"]}
    joint_p = 1.0
    cost_sum = 0.0
    combo_cost = 1.0  # product of (ask+fee) ≈ independence-priced combo
    sides = []
    series = []
    reasons = []
    for leg in legs:
        p = _finite(leg.get("fair") if leg.get("fair") is not None else leg.get("p"))
        ask = _finite(leg.get("ask"))
        fee = _finite(leg.get("fee")) or 0.0
        if p is None or ask is None:
            return {"ok": False, "ev": None, "joint_p": None, "reasons": ["leg missing fair/ask"]}
        if p <= 0 or p >= 1:
            reasons.append("fair out of (0,1)")
        unit = max(1e-9, min(0.999999, ask + fee))
        joint_p *= max(1e-9, min(0.999999, p))
        cost_sum += ask + fee
        combo_cost *= unit
        sides.append(str(leg.get("side") or "").upper())
        series.append(str(leg.get("series") or ""))
    # Same-direction crypto → haircut independence assumption.
    shared = 0.0
    crypto = {"KXBTC15M", "KXETH15M", "KXBTCD"}
    if any(s.startswith(tuple(crypto)) or s in crypto for s in series):
        yes_n = sum(1 for s in sides if s in ("YES", "Y", "HOME"))
        no_n = sum(1 for s in sides if s in ("NO", "N", "AWAY"))
        if yes_n >= 2 or no_n >= 2:
            shared = float(corr_haircut)
            reasons.append(f"same-direction crypto haircut {shared:.2f}")
    joint_adj = joint_p * (1.0 - shared)
    # Paper combo unit: ~$1 payout if all win; cost ≈ product of leg (ask+fee).
    # EV_unit = joint_adj - combo_cost. Sum-of-asks kept for desk cash context only.
    ev_unit = joint_adj - combo_cost
    return {
        "ok": True,
        "joint_p_raw": round(joint_p, 6),
        "joint_p": round(joint_adj, 6),
        "cost": round(combo_cost, 4),
        "cost_sum": round(cost_sum, 4),
        "ev": round(ev_unit, 4),
        "corr_haircut": shared,
        "reasons": reasons,
        "n_legs": len(legs),
    }


def simulate_parlay(
    root: str | None,
    legs: list[dict],
    *,
    note: str = "",
) -> dict:
    """Score and persist a paper parlay simulation (does not open a fill)."""
    scored = parlay_joint_ev(legs)
    row = {
        "at": _now(),
        "note": (note or "")[:160],
        "legs": [
            {
                "ticker": l.get("ticker"),
                "side": l.get("side"),
                "ask": l.get("ask"),
                "fair": l.get("fair") or l.get("p"),
                "series": l.get("series"),
            }
            for l in legs
        ],
        **scored,
        "paper_only": True,
        "shadow_only": True,
    }
    state = load_phase3(root)
    state.setdefault("parlay_sims", []).append(row)
    state["last_at"] = row["at"]
    save_phase3(state, root)
    return row


def should_open_parlay(sim: dict, *, min_ev: float = 0.0) -> bool:
    if not sim or not sim.get("ok"):
        return False
    ev = _finite(sim.get("ev"))
    return bool(ev is not None and ev + 1e-12 >= float(min_ev))


def phase3_summary(root: str | None = None) -> dict:
    state = load_phase3(root)
    sims = [r for r in (state.get("parlay_sims") or []) if isinstance(r, dict)]
    picks = [r for r in (state.get("ladder_picks") or []) if isinstance(r, dict)]
    pos_ev = [r for r in sims if _finite(r.get("ev")) is not None and float(r["ev"]) >= 0]
    return {
        "paper_only": True,
        "version": 1,
        "ladder_pick_count": len(picks),
        "parlay_sim_count": len(sims),
        "parlay_positive_ev_n": len(pos_ev),
        "recent_ladder": picks[-8:],
        "recent_parlay_sims": sims[-8:],
        "rules": {
            "ladder_min_p": LADDER_MIN_P,
            "ladder_min_depth": LADDER_MIN_DEPTH,
            "parlay_corr_haircut": PARLAY_CORR_HAIRCUT,
        },
        "note": "Phase 3 expansion — ladder companion + combo sims; paper/shadow only.",
    }


def self_check() -> None:
    # Deep ITM-ish rung with rich depth should beat thin far OTM.
    rows = [
        {"ticker": "A", "spot": 100, "strike": 99, "ask": 0.82, "fee": 0.02, "depth": 40, "model_p": 0.90},
        {"ticker": "B", "spot": 100, "strike": 99, "ask": 0.82, "fee": 0.02, "depth": 3, "model_p": 0.90},
        {"ticker": "C", "spot": 100, "strike": 95, "ask": 0.70, "fee": 0.02, "depth": 50, "model_p": 0.75},
    ]
    pick = pick_ladder_rung(rows, min_edge=0.05)
    assert pick is not None and pick["ticker"] == "A"
    weak = pick_ladder_rung(
        [{"ticker": "W", "spot": 100, "strike": 99, "ask": 0.70, "fee": 0.02, "depth": 20}],
        min_edge=0.05,
        require_ok=False,
    )
    assert weak is not None and weak["ticker"] == "W" and weak.get("ok") is False
    sim = parlay_joint_ev([
        {"fair": 0.85, "ask": 0.80, "fee": 0.02, "side": "YES", "series": "KXBTC15M"},
        {"fair": 0.85, "ask": 0.80, "fee": 0.02, "side": "YES", "series": "KXETH15M"},
    ])
    assert sim["ok"] and sim["corr_haircut"] > 0
    assert sim["joint_p"] < sim["joint_p_raw"]
    assert should_open_parlay(sim, min_ev=0.0) is (float(sim["ev"]) >= 0.0)
    bad = parlay_joint_ev([
        {"fair": 0.55, "ask": 0.80, "fee": 0.02, "side": "YES", "series": "KXBTC15M"},
        {"fair": 0.55, "ask": 0.80, "fee": 0.02, "side": "YES", "series": "KXETH15M"},
    ])
    assert not should_open_parlay(bad, min_ev=0.0)
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        remember_ladder_pick(tmp, pick)
        simulate_parlay(tmp, [
            {"ticker": "t1", "fair": 0.88, "ask": 0.80, "fee": 0.01, "side": "YES", "series": "KXBTC15M"},
            {"ticker": "t2", "fair": 0.88, "ask": 0.80, "fee": 0.01, "side": "NO", "series": "KXETH15M"},
        ], note="unit")
        summary = phase3_summary(tmp)
        assert summary["ladder_pick_count"] == 1
        assert summary["parlay_sim_count"] == 1


if __name__ == "__main__":
    self_check()
    print("desk_phase3 self_check ok")
