"""
desk_top25.py — Top-25 shortlist from apex-city-1000-ideas.md

Paper only. Fee floors unchanged. No profit guarantee.
Implements ops/measure/learn hooks the desk can run every timer pass.
"""
from __future__ import annotations

import json
import math
import os
import time
from typing import Any, Iterable

TOP25_NAME = "desk_top25_state.json"
MAKER_TAKER_NAME = "desk_maker_taker_study.json"

# Venue depth needs for depth-adjusted rank (idea #11).
VENUE_DEPTH_NEED = {
    "kalshi_sports": 8.0,
    "kalshi_btc15m": 10.0,
    "kalshi_commodity15m": 6.0,
    "kalshi_inx": 12.0,
    "solana_dex": 1.0,
}

# Commodity playbooks: metals vs energy (idea #9).
METAL_SERIES = {
    "KXPALLADIUM15M",
    "KXCOPPER15M",
    "KXSILVER15M",
    "KXGOLD15M",
    "KXPLATINUM15M",
}
ENERGY_SERIES = {"KXNATGAS15M", "KXBRENT15M", "KXWTI15M"}

PLAYBOOKS = {
    "metal": {
        "min_z": 0.70,
        "min_cushion_mult": 1.10,
        "vol_prior_boost": 0.02,
        "note": "metals: slower mean-revert; slightly stricter z",
    },
    "energy": {
        "min_z": 0.65,
        "min_cushion_mult": 1.25,
        "vol_prior_boost": 0.08,
        "note": "energy: spike-aware; bigger cushion mult + prior",
    },
}

# Sport-split fair floors (idea #15 / E1 #113). NFL stricter on both lanes.
LEAGUE_FAIR_FLOOR = {
    "nhl": 0.80,
    "nba": 0.80,
    "nfl": 0.82,
    "ncaaf": 0.81,
    "mlb": 0.80,
    "default": 0.80,
}
LEAGUE_SPEED_FLOOR = {
    "nfl": 0.74,
    "ncaaf": 0.73,
    "default": 0.72,
}


def league_speed_floor(league: str | None) -> float:
    key = str(league or "").strip().lower()
    return float(LEAGUE_SPEED_FLOOR.get(key, LEAGUE_SPEED_FLOOR["default"]))

# Near-miss promote ladder (idea #16).
NEAR_MISS_PROMOTE_N = 30
NEAR_MISS_PROMOTE_MIN_EV = 0.0

# Zero-buy alert (idea #7).
ZERO_BUY_HOURS = 6.0

# Settle backlog SLA (idea #13).
SETTLE_BACKLOG_SLA = 20

# ETH lead-lag study delay seconds (idea #10).
ETH_LEAD_LAG_DELAY_SEC = 45

# Idea review cadence (idea #25).
IDEA_REVIEW_DAYS = 90

TOP25_INDEX = [
    "skip_regret_shadow",
    "clv_optimize_sports",
    "rebalance_tower_budgets",
    "calibrate_vol_priors",
    "global_rank_minute",
    "timer_watchdog",
    "zero_buy_alert",
    "gate_b_drawdown",
    "commodity_playbooks",
    "eth_lead_lag_study",
    "depth_need_per_venue",
    "hillclimb_recap",
    "sticky_settle_sla",
    "maker_taker_study",
    "sport_split_floors",
    "near_miss_promote",
    "city_vault_board",
    "guest_readonly",
    "desk_health_doctor",
    "pr_template",
    "screenshot_fixtures",
    "chaos_calendar",
    "dual_control_design",
    "fill_tax_education",
    "quarterly_idea_review",
]


def top25_path(root: str | None = None) -> str:
    base = root or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, TOP25_NAME)


def maker_taker_path(root: str | None = None) -> str:
    base = root or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, MAKER_TAKER_NAME)


def _empty() -> dict:
    return {
        "paper_only": True,
        "version": 1,
        "skip_regret": [],
        "budget_rebalance": [],
        "vol_prior_cal": [],
        "global_rank_passes": [],
        "alerts": [],
        "eth_lead_lag": [],
        "hillclimb_recaps": [],
        "near_miss_promotions": [],
        "last_buy_at": None,
        "last_at": None,
        "idea_review_due": None,
    }


def load_top25(root: str | None = None) -> dict:
    path = top25_path(root)
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
    for key in (
        "skip_regret",
        "budget_rebalance",
        "vol_prior_cal",
        "global_rank_passes",
        "alerts",
        "eth_lead_lag",
        "hillclimb_recaps",
        "near_miss_promotions",
    ):
        if not isinstance(base.get(key), list):
            base[key] = []
    return base


def save_top25(state: dict, root: str | None = None) -> None:
    path = top25_path(root)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    state = dict(state)
    state["paper_only"] = True
    for key, lim in (
        ("skip_regret", 500),
        ("budget_rebalance", 100),
        ("vol_prior_cal", 100),
        ("global_rank_passes", 80),
        ("alerts", 200),
        ("eth_lead_lag", 200),
        ("hillclimb_recaps", 52),
        ("near_miss_promotions", 50),
    ):
        rows = list(state.get(key) or [])
        if len(rows) > lim:
            state[key] = rows[-lim:]
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
        handle.write("\n")
    os.replace(tmp, path)


def _finite(x) -> float | None:
    try:
        n = float(x)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(n):
        return None
    return n


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# --- 1. Skip-regret shadow -------------------------------------------------

def record_skip_regret(
    root: str | None,
    *,
    bot: str,
    ticker: str,
    side: str = "",
    soft_gate: str = "",
    edge=None,
    confidence=None,
    would_pnl=None,
    note: str = "",
) -> dict:
    """Log a skipped soft-gate fit and optional counterfactual pnl (shadow twin)."""
    state = load_top25(root)
    row = {
        "at": _now(),
        "bot": bot,
        "ticker": ticker,
        "side": side,
        "soft_gate": soft_gate,
        "edge": _finite(edge),
        "confidence": _finite(confidence),
        "would_pnl": _finite(would_pnl),
        "shadow_only": True,
        "note": (note or "")[:160],
    }
    state.setdefault("skip_regret", []).append(row)
    state["last_at"] = row["at"]
    save_top25(state, root)
    return row


def skip_regret_summary(root: str | None = None) -> dict:
    rows = [r for r in (load_top25(root).get("skip_regret") or []) if isinstance(r, dict)]
    labeled = [r for r in rows if r.get("would_pnl") is not None]
    n = len(labeled)
    wins = sum(1 for r in labeled if float(r["would_pnl"]) > 0)
    avg = round(sum(float(r["would_pnl"]) for r in labeled) / n, 4) if n else None
    # Green twin = average would_pnl ≥ 0 with enough labels
    green = bool(n >= 20 and avg is not None and avg + 1e-12 >= 0)
    return {
        "paper_only": True,
        "n": len(rows),
        "labeled_n": n,
        "win_rate": round(wins / n, 4) if n else None,
        "avg_would_pnl": avg,
        "green_twin": green,
        "loosen_soft_gates": green,  # only then may shadow-loosen (never fee floors)
        "note": "Only loosen non-fee soft gates when green_twin is true.",
        "recent": rows[-12:],
    }


# --- 2. CLV-aware sports score --------------------------------------------

def clv_adjusted_edge(edge, clv, weight: float = 0.35) -> float:
    """Blend fee-aware edge with CLV so sports prefer line-beating entries."""
    e = _finite(edge) or 0.0
    c = _finite(clv)
    if c is None:
        return round(max(0.0, e), 6)
    # Positive CLV boosts; negative haircuts (still floor at 0 for rank)
    return round(max(0.0, e + float(weight) * c), 6)


def sports_rank_score(edge, confidence, clv=None, depth=None, need: float = 8.0) -> float:
    try:
        import desk_more
        adj = clv_adjusted_edge(edge, clv)
        return desk_more.opportunity_score_v2(adj, confidence, depth, need=need)
    except Exception:
        e = max(0.0, (_finite(edge) or 0.0))
        c = max(0.0, min(1.0, (_finite(confidence) or 0.0)))
        return round(e * c, 6)


# --- 3. Auto-rebalance tower budgets --------------------------------------

def rebalance_tower_budgets(
    bot_expectancies: dict[str, float | None],
    *,
    floor_share: float = 0.03,
    root: str | None = None,
    persist: bool = False,
) -> dict[str, float]:
    """
    Soft shares from max(0, taxed EV) with floors so cold towers keep explore budget.
    Does not raise desk max_open_risk. Sums to 1.0. Proposal-only unless persist=True.
    """
    import desk_more

    base = dict(desk_more.DEFAULT_TOWER_BUDGET_SHARE)
    ids = list(base.keys())
    scores = {}
    for bot_id in ids:
        ev = _finite(bot_expectancies.get(bot_id))
        scores[bot_id] = max(0.0, ev if ev is not None else 0.0) + 0.01  # epsilon
    total = sum(scores.values()) or 1.0
    raw = {b: scores[b] / total for b in ids}
    # Blend 70% EV-weight with 30% prior shares; then enforce floors.
    blended = {
        b: 0.70 * raw[b] + 0.30 * float(base[b])
        for b in ids
    }
    for b in ids:
        blended[b] = max(float(floor_share), blended[b])
    s = sum(blended.values()) or 1.0
    out = {b: round(blended[b] / s, 4) for b in ids}
    # Fix float drift on last key.
    keys = list(out.keys())
    out[keys[-1]] = round(1.0 - sum(out[k] for k in keys[:-1]), 4)
    if persist and root is not None:
        state = load_top25(root)
        state.setdefault("budget_rebalance", []).append({"at": _now(), "shares": out})
        state["last_at"] = _now()
        save_top25(state, root)
    return out


# --- 4. Vol prior calibration ---------------------------------------------

def calibrate_vol_priors(
    series_hit_rates: dict[str, float | None],
    *,
    root: str | None = None,
) -> dict[str, float]:
    """
    Propose prior bumps: colder series (lower hit) → higher vol prior (play safer).
    Returns proposals only — does not auto-write desk_more.SERIES_VOL_PRIORS.
    """
    import desk_more

    proposals = {}
    for series, prior in desk_more.SERIES_VOL_PRIORS.items():
        hit = _finite(series_hit_rates.get(series))
        bump = 0.0
        if hit is not None:
            if hit < 0.45:
                bump = 0.06
            elif hit < 0.55:
                bump = 0.03
            elif hit > 0.70:
                bump = -0.02
        proposals[series] = round(max(0.0, min(0.25, float(prior) + bump)), 4)
    state = load_top25(root)
    state.setdefault("vol_prior_cal", []).append({"at": _now(), "proposals": proposals})
    state["last_at"] = _now()
    save_top25(state, root)
    return proposals


# --- 5. Global rank minute ------------------------------------------------

def global_rank_minute(
    candidates: Iterable[dict],
    remaining_risk: float,
    *,
    root: str | None = None,
) -> dict:
    import desk_brain

    rows = [c for c in (candidates or []) if isinstance(c, dict)]
    # Attach venue depth need when missing.
    for row in rows:
        if row.get("depth_need") is None and row.get("venue"):
            row["depth_need"] = VENUE_DEPTH_NEED.get(str(row["venue"]), 10.0)
        need = float(row.get("depth_need") or 10.0)
        try:
            import desk_more
            row["_brain_score"] = desk_more.opportunity_score_v2(
                row.get("edge"), row.get("confidence"), row.get("depth"), need=need,
            )
        except Exception:
            pass
    ranked = desk_brain.rank_desk_queue(rows)
    alloc = desk_brain.allocate_risk(ranked, remaining_risk)
    try:
        desk_brain.remember_queue(root, alloc, note="top25 global rank minute")
    except Exception:
        pass
    state = load_top25(root)
    slim = [
        {
            "bot": r.get("bot"),
            "ticker": r.get("ticker"),
            "score": r.get("_brain_score"),
            "status": r.get("queue_status"),
            "rank": r.get("_queue_rank"),
        }
        for r in alloc[:20]
    ]
    state.setdefault("global_rank_passes", []).append({"at": _now(), "n": len(alloc), "rows": slim})
    state["last_at"] = _now()
    save_top25(state, root)
    return {"paper_only": True, "n": len(alloc), "accepted": sum(1 for r in alloc if r.get("queue_status") == "accepted"), "rows": slim}


# --- 6–7, 13. Watchdog / zero-buy / sticky SLA ----------------------------

def remember_buy(root: str | None = None) -> None:
    state = load_top25(root)
    state["last_buy_at"] = _now()
    state["last_at"] = state["last_buy_at"]
    save_top25(state, root)


def push_alert(
    root: str | None,
    kind: str,
    message: str,
    *,
    severity: str = "warn",
    debounce_sec: float = 3600.0,
) -> dict | None:
    if root is None:
        return None
    state = load_top25(root)
    now = time.time()
    for prev in reversed(list(state.get("alerts") or [])):
        if prev.get("kind") != kind:
            continue
        try:
            text = str(prev.get("at") or "")
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            from datetime import datetime
            age = now - datetime.fromisoformat(text).timestamp()
            if age < float(debounce_sec):
                return None
        except Exception:
            break
        break
    row = {"at": _now(), "kind": kind, "severity": severity, "message": message[:240]}
    state.setdefault("alerts", []).append(row)
    state["last_at"] = row["at"]
    save_top25(state, root)
    return row


def timer_watchdog(health: dict | None, *, root: str | None = None, now_epoch: float | None = None) -> dict:
    """Idea #6 — detect dead timer; suggest restart (does not kill processes itself)."""
    alive = bool((health or {}).get("alive"))
    out = {
        "paper_only": True,
        "alive": alive,
        "action": "ok" if alive else "restart_paper_timer",
        "hint": (
            ""
            if alive
            else "Timer dead — restart Discord paper_timer / pimp_desk.run_scheduled host."
        ),
    }
    if not alive:
        push_alert(root, "timer_watchdog", out["hint"], severity="crit")
    return out


def zero_buy_alert(
    root: str | None,
    *,
    weekday: int | None = None,
    now_epoch: float | None = None,
    hours: float = ZERO_BUY_HOURS,
) -> dict:
    """Idea #7 — weekday silence >6h with skip dump (weekends excluded)."""
    if weekday is not None and int(weekday) >= 5:
        return {"paper_only": True, "alert": False, "reason": "weekend — silence expected"}
    state = load_top25(root)
    last = state.get("last_buy_at")
    now = now_epoch if now_epoch is not None else time.time()
    age_h = None
    if last:
        try:
            text = str(last)
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            from datetime import datetime
            age_h = (now - datetime.fromisoformat(text).timestamp()) / 3600.0
        except Exception:
            age_h = None
    alert = bool(age_h is not None and age_h >= float(hours))
    skip = {}
    try:
        import desk_more
        skip = desk_more.skip_leaderboard(root)
    except Exception:
        skip = {}
    out = {
        "paper_only": True,
        "alert": alert,
        "hours_since_buy": None if age_h is None else round(age_h, 2),
        "threshold_hours": hours,
        "skip_leaderboard": skip,
    }
    if alert:
        top = ", ".join(f"{r['code']}×{r['n']}" for r in (skip.get("top") or [])[:5]) or "no skip codes"
        push_alert(
            root,
            "zero_buy",
            f"No buys in {age_h:.1f}h on a weekday. Top skips: {top}",
            severity="warn",
        )
    return out


def sticky_settle_sla(
    sticky_count: int,
    settle_backlog: int = 0,
    *,
    root: str | None = None,
) -> dict:
    """Idea #13 — page when sticky opens or settle harness backlog exceeds SLA."""
    alerts = []
    if int(sticky_count) > 0:
        msg = f"{sticky_count} sticky open(s) past settle expectation"
        alerts.append(msg)
        push_alert(root, "sticky", msg, severity="warn")
    if int(settle_backlog) >= SETTLE_BACKLOG_SLA:
        msg = f"settle backlog {settle_backlog} ≥ SLA {SETTLE_BACKLOG_SLA}"
        alerts.append(msg)
        push_alert(root, "settle_sla", msg, severity="warn")
    return {
        "paper_only": True,
        "sticky_count": int(sticky_count),
        "settle_backlog": int(settle_backlog),
        "sla": SETTLE_BACKLOG_SLA,
        "alerts": alerts,
    }


# --- 8. Gate B max drawdown -----------------------------------------------

def gate_b(
    history: list | None,
    *,
    max_drawdown: float = 40.0,
    min_n: int = 20,
) -> dict:
    """Gate B: peak-to-trough drawdown on cumulative pnl within bound + enough settles."""
    pnls = []
    for row in history or []:
        if not isinstance(row, dict):
            continue
        p = _finite(row.get("pnl"))
        if p is None:
            continue
        pnls.append(p)
    n = len(pnls)
    if n == 0:
        return {
            "gate": "B",
            "ready": False,
            "n": 0,
            "max_drawdown": None,
            "limit": max_drawdown,
            "paper_only": True,
            "reason": f"need n≥{min_n} and drawdown ≤ ${max_drawdown:.0f}",
        }
    equity = 0.0
    peak = 0.0
    dd = 0.0
    for p in pnls:
        equity += p
        peak = max(peak, equity)
        dd = max(dd, peak - equity)
    ready = bool(n >= int(min_n) and dd <= float(max_drawdown) + 1e-9)
    return {
        "gate": "B",
        "ready": ready,
        "n": n,
        "max_drawdown": round(dd, 2),
        "limit": float(max_drawdown),
        "paper_only": True,
        "reason": (
            f"drawdown ${dd:.2f} ≤ ${max_drawdown:.0f} with n={n}"
            if ready
            else f"need n≥{min_n} and drawdown ≤ ${max_drawdown:.0f} (have n={n}, dd=${dd:.2f})"
        ),
    }


# --- 9. Commodity playbooks -----------------------------------------------

def commodity_playbook(series: str | None) -> dict:
    key = str(series or "").strip().upper()
    for s in METAL_SERIES:
        if key.startswith(s):
            return {"family": "metal", "series": s, **PLAYBOOKS["metal"]}
    for s in ENERGY_SERIES:
        if key.startswith(s):
            return {"family": "energy", "series": s, **PLAYBOOKS["energy"]}
    return {"family": "unknown", "series": key, "min_z": 0.65, "min_cushion_mult": 1.0, "vol_prior_boost": 0.0, "note": "default"}


# --- 10. ETH lead-lag study -----------------------------------------------

def record_eth_lead_lag(
    root: str | None,
    *,
    btc_move_pct,
    eth_edge=None,
    delayed: bool = False,
    note: str = "",
) -> dict:
    state = load_top25(root)
    row = {
        "at": _now(),
        "btc_move_pct": _finite(btc_move_pct),
        "eth_edge": _finite(eth_edge),
        "delay_sec": ETH_LEAD_LAG_DELAY_SEC if delayed else 0,
        "delayed": bool(delayed),
        "note": (note or "")[:160],
        "paper_only": True,
    }
    state.setdefault("eth_lead_lag", []).append(row)
    state["last_at"] = row["at"]
    save_top25(state, root)
    return row


def should_delay_eth(btc_move_pct, threshold_pct: float = 0.15) -> bool:
    m = _finite(btc_move_pct)
    if m is None:
        return False
    return abs(m) >= float(threshold_pct)


# --- 11. Depth need per venue ---------------------------------------------

def depth_need_for(venue: str | None) -> float:
    return float(VENUE_DEPTH_NEED.get(str(venue or ""), 10.0))


# --- 12. Hillclimb recap --------------------------------------------------

def hillclimb_recap(
    root: str | None,
    *,
    lever: str | None,
    taxed_ev_before,
    taxed_ev_after,
    fill_count_before: int = 0,
    fill_count_after: int = 0,
) -> dict:
    """Idea #12 — weekly recap + kill rule signal (EV down 2 weeks while fills up)."""
    before = _finite(taxed_ev_before)
    after = _finite(taxed_ev_after)
    delta = None if before is None or after is None else round(after - before, 4)
    fills_up = int(fill_count_after) > int(fill_count_before)
    ev_down = delta is not None and delta < 0
    state = load_top25(root)
    weeks = list(state.get("hillclimb_recaps") or [])
    kill = False
    if ev_down and fills_up and weeks:
        prev = weeks[-1]
        if prev.get("ev_down") and prev.get("fills_up") and prev.get("lever") == lever:
            kill = True
    row = {
        "at": _now(),
        "lever": lever,
        "taxed_ev_before": before,
        "taxed_ev_after": after,
        "delta": delta,
        "fill_count_before": int(fill_count_before),
        "fill_count_after": int(fill_count_after),
        "fills_up": fills_up,
        "ev_down": bool(ev_down),
        "kill_lever": kill,
        "note": "Revert lever if taxed EV falls 2 consecutive weeks while fills rose.",
    }
    state.setdefault("hillclimb_recaps", []).append(row)
    state["last_at"] = row["at"]
    save_top25(state, root)
    return row


# --- 14. Maker vs taker study ---------------------------------------------

def record_maker_taker(
    root: str | None,
    *,
    style: str,
    ticker: str,
    edge=None,
    fill_price=None,
    note: str = "",
) -> dict:
    style_l = str(style or "").strip().lower()
    if style_l not in ("maker", "taker"):
        style_l = "taker"
    path = maker_taker_path(root)
    state = {"paper_only": True, "version": 1, "rows": []}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as handle:
                loaded = json.load(handle)
            if isinstance(loaded, dict):
                state.update(loaded)
        except (OSError, json.JSONDecodeError):
            pass
    row = {
        "at": _now(),
        "style": style_l,
        "ticker": ticker,
        "edge": _finite(edge),
        "fill_price": _finite(fill_price),
        "note": (note or "")[:120],
    }
    state.setdefault("rows", []).append(row)
    if len(state["rows"]) > 2000:
        state["rows"] = state["rows"][-2000:]
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
        handle.write("\n")
    os.replace(tmp, path)
    return row


def maker_taker_summary(root: str | None = None) -> dict:
    path = maker_taker_path(root)
    rows = []
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
            rows = list((data or {}).get("rows") or [])
        except (OSError, json.JSONDecodeError):
            rows = []
    makers = [r for r in rows if r.get("style") == "maker"]
    takers = [r for r in rows if r.get("style") == "taker"]
    return {
        "paper_only": True,
        "n": len(rows),
        "maker_n": len(makers),
        "taker_n": len(takers),
        "note": "Paper study only — compare resting bids vs taking asks on BTC 15m.",
        "recent": rows[-12:],
    }


# --- 15. Sport-split floors -----------------------------------------------

def league_fair_floor(league: str | None) -> float:
    key = str(league or "").strip().lower()
    return float(LEAGUE_FAIR_FLOOR.get(key, LEAGUE_FAIR_FLOOR["default"]))


# --- 16. Near-miss promote ladder -----------------------------------------

def near_miss_promote_check(root: str | None = None) -> dict:
    try:
        import desk_more
        misses = list((desk_more.load_more(root).get("near_miss") or []))
    except Exception:
        misses = []
    n = len(misses)
    # Without settle labels on near-misses yet, require n≥30 and staff review flag.
    ready = n >= NEAR_MISS_PROMOTE_N
    row = {
        "at": _now(),
        "n": n,
        "need_n": NEAR_MISS_PROMOTE_N,
        "ready_for_review": ready,
        "auto_promote": False,  # never auto-loosen fee floors
        "note": "Promote soft-gate loosen to shadow twin only after staff review.",
    }
    if ready:
        state = load_top25(root)
        state.setdefault("near_miss_promotions", []).append(row)
        state["last_at"] = row["at"]
        save_top25(state, root)
    return row


# --- 19. Doctor / health --------------------------------------------------

def desk_doctor(root: str | None = None, health: dict | None = None) -> dict:
    """Idea #19 — one-shot desk health for CLI / snapshot."""
    checks = []
    def add(name, ok, detail=""):
        checks.append({"name": name, "ok": bool(ok), "detail": detail[:160]})

    add("paper_only", True, "desk stays paper")
    alive = bool((health or {}).get("alive")) if health is not None else None
    if alive is not None:
        add("timer_alive", alive, "paper_timer heartbeat" if alive else "timer dead")
        if health and health.get("weekday_alert"):
            add("weekday_timer_alert", False, str(health.get("alert") or "weekday timer alert"))
        elif health is not None and alive:
            add("weekday_timer_alert", True, "no weekday dead-timer alert")
    # Runtime files present?
    base = root or os.path.dirname(os.path.abspath(__file__))
    for label, name in (
        ("brain_journal", "desk_brain_journal.json"),
        ("adapt_state", "desk_adapt_state.json"),
        ("more_state", "desk_more_state.json"),
    ):
        path = os.path.join(base, name)
        add(label, True, "optional" if not os.path.exists(path) else "present")
    try:
        import desk_more
        board = desk_more.skip_leaderboard(root)
        add("skip_leaderboard", True, f"total={board.get('total')}")
    except Exception as exc:
        add("skip_leaderboard", False, type(exc).__name__)
    try:
        import desk_adapt
        add("adapt_import", True, f"VOL_SAFE={desk_adapt.VOL_SAFE}")
    except Exception as exc:
        add("adapt_import", False, type(exc).__name__)
    # E0 #43/#44 — CARD safety net + Traceback page signal from last runs.
    # Towers that print CARD: today (INX bots still use card_copy parsers).
    _card_bots = {"sports-gap", "btc15m", "commodity-15m", "memecoin"}
    runs_path = os.path.join(base, "pimp-runs.json")
    traceback_bots = []
    missing_card = []
    if os.path.isfile(runs_path):
        try:
            with open(runs_path, encoding="utf-8") as handle:
                runs = json.load(handle)
        except Exception:
            runs = {}
        if isinstance(runs, dict):
            for bot_id, row in runs.items():
                if not isinstance(row, dict):
                    continue
                summary = str(row.get("summary") or "")
                err = str(row.get("error") or "")
                blob = f"{summary}\n{err}"
                if "Traceback" in blob or "UnboundLocalError" in blob:
                    traceback_bots.append(str(bot_id))
                # Towers that print CARD: must leave it on finished ok checks.
                if (
                    str(bot_id) in _card_bots
                    and row.get("ok")
                    and len(summary.strip()) >= 12
                    and "CARD:" not in summary
                    and "card:" not in summary.lower()
                ):
                    missing_card.append(str(bot_id))
    add(
        "no_traceback_in_runs",
        not traceback_bots,
        "clean" if not traceback_bots else f"Traceback in {','.join(traceback_bots[:4])}",
    )
    add(
        "card_line_present",
        not missing_card,
        "CARD ok" if not missing_card else f"missing CARD: {','.join(missing_card[:4])}",
    )
    ok_n = sum(1 for c in checks if c["ok"])
    return {
        "paper_only": True,
        "ok": ok_n == len(checks),
        "passed": ok_n,
        "total": len(checks),
        "checks": checks,
        "hint": "python -m desk_doctor",
    }


# --- 22. Chaos calendar ---------------------------------------------------

def chaos_calendar(year: int | None = None) -> dict:
    """Idea #22 — monthly game-day themes (ops drills, not market chaos)."""
    y = int(year or time.gmtime().tm_year)
    months = [
        (1, "Timer death drill"),
        (2, "Tape stall / family budget drill"),
        (3, "Daily-loss stop trip"),
        (4, "Memecoin rug cascade paper"),
        (5, "Settle harness backlog flood"),
        (6, "Kalshi 5xx circuit breaker"),
        (7, "ESPN empty slate Sunday"),
        (8, "Corrupt JSON recover"),
        (9, "Open-risk full starvation"),
        (10, "Correlation veto loop"),
        (11, "Dual-control dry run"),
        (12, "Backup/restore settlement volume"),
    ]
    return {
        "paper_only": True,
        "year": y,
        "days": [{"month": m, "theme": t} for m, t in months],
        "note": "Tabletop drills — no live orders.",
    }


# --- 25. Quarterly idea review --------------------------------------------

def idea_review_due(root: str | None = None, now_epoch: float | None = None) -> dict:
    now = now_epoch if now_epoch is not None else time.time()
    due = None
    if root is not None:
        state = load_top25(root)
        due = state.get("idea_review_due")
        if not due:
            due_ts = now + IDEA_REVIEW_DAYS * 86400
            due = time.strftime("%Y-%m-%d", time.gmtime(due_ts))
            state["idea_review_due"] = due
            save_top25(state, root)
    if not due:
        due = time.strftime("%Y-%m-%d", time.gmtime(now + IDEA_REVIEW_DAYS * 86400))
    return {
        "paper_only": True,
        "due": due,
        "cadence_days": IDEA_REVIEW_DAYS,
        "note": "Revisit the 1000-idea list; kill half that fight fee-aware gates.",
    }


# --- Snapshot bundle ------------------------------------------------------

def top25_summary(
    root: str | None = None,
    *,
    bots: list | None = None,
    health: dict | None = None,
    cfg: dict | None = None,
) -> dict:
    bots = bots or []
    sticky_n = 0
    try:
        import desk_more
        sticky_n = len(desk_more.sticky_positions(bots))
    except Exception:
        sticky_n = 0

    # Expectancies for budget rebalance proposal (not auto-applied to settings).
    exp_map = {}
    gate_b_rows = []
    for bot in bots:
        if not isinstance(bot, dict) or bot.get("shadow_only"):
            continue
        bid = str(bot.get("id") or "")
        exp_map[bid] = bot.get("expectancy")
        gb = gate_b(bot.get("history") or [])
        gate_b_rows.append({"bot": bid, "ready": gb.get("ready"), "max_drawdown": gb.get("max_drawdown"), "reason": gb.get("reason")})

    proposed_budgets = None
    try:
        # Propose only — staff applies via settings.
        proposed_budgets = rebalance_tower_budgets(exp_map, root=root)
    except Exception:
        proposed_budgets = None

    from datetime import datetime, timezone
    wd = datetime.now(timezone.utc).weekday()
    zba = zero_buy_alert(root, weekday=wd)
    watchdog = timer_watchdog(health, root=root)
    sla = sticky_settle_sla(sticky_n, root=root)
    promote = near_miss_promote_check(root)
    doctor = desk_doctor(root, health=health)

    return {
        "paper_only": True,
        "version": 1,
        "index": list(TOP25_INDEX),
        "skip_regret": skip_regret_summary(root),
        "proposed_tower_budgets": proposed_budgets,
        "depth_need_by_venue": dict(VENUE_DEPTH_NEED),
        "commodity_playbooks": {"metal": PLAYBOOKS["metal"], "energy": PLAYBOOKS["energy"]},
        "league_fair_floors": dict(LEAGUE_FAIR_FLOOR),
        "eth_lead_lag_delay_sec": ETH_LEAD_LAG_DELAY_SEC,
        "gate_b": {
            "paper_only": True,
            "any_ready": any(r.get("ready") for r in gate_b_rows),
            "bots": gate_b_rows,
            "note": "Gate B = max drawdown bound — readiness only, not a live switch.",
        },
        "timer_watchdog": watchdog,
        "zero_buy_alert": zba,
        "sticky_settle_sla": sla,
        "near_miss_promote": promote,
        "maker_taker": maker_taker_summary(root),
        "hillclimb_recent": list((load_top25(root).get("hillclimb_recaps") or []))[-5:],
        "doctor": doctor,
        "chaos_calendar": chaos_calendar(),
        "idea_review": idea_review_due(root),
        "city_vault": {
            "show_skip_board": True,
            "show_budget_bars": True,
            "show_adapt_dial": True,
            "fill_tax_education": True,
            "guest_readonly_query": "?guest=1",
        },
        "dual_control": {
            "required_for": ["raise max_open_risk", "lower min_edge", "flip paper_mode"],
            "status": "design — see docs/dual-control-live-arm.md",
            "armed": False,
        },
        "alerts_recent": list((load_top25(root).get("alerts") or []))[-12:],
        "note": "Top 25 from apex-city-1000-ideas.md — paper-first, no profit guarantee.",
    }


def self_check() -> None:
    assert clv_adjusted_edge(0.06, 0.04) > 0.06
    assert league_fair_floor("nfl") >= league_fair_floor("nhl")
    assert league_fair_floor("nfl") == 0.82
    assert league_speed_floor("nfl") >= league_speed_floor("nhl")
    assert league_speed_floor("nfl") == 0.74
    pb = commodity_playbook("KXNATGAS15M-FOO")
    assert pb["family"] == "energy"
    assert commodity_playbook("KXGOLD15M")["family"] == "metal"
    gb = gate_b([{"pnl": 2}] * 25)
    assert gb["ready"] is True
    gb_bad = gate_b([{"pnl": 5}, {"pnl": -50}] + [{"pnl": 1}] * 20)
    assert gb_bad["max_drawdown"] is not None
    assert depth_need_for("kalshi_btc15m") == 10.0
    assert should_delay_eth(0.2) is True
    assert should_delay_eth(0.01) is False
    cal = chaos_calendar(2026)
    assert len(cal["days"]) == 12
    shares = rebalance_tower_budgets(
        {"sports-gap": 1.0, "btc15m": 0.5, "memecoin": -1.0}, persist=False,
    )
    assert abs(sum(shares.values()) - 1.0) < 1e-6
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        record_skip_regret(tmp, bot="btc15m", ticker="T", soft_gate="z", would_pnl=1.0)
        assert skip_regret_summary(tmp)["labeled_n"] == 1
        record_maker_taker(tmp, style="maker", ticker="T", edge=0.05)
        assert maker_taker_summary(tmp)["maker_n"] == 1
        hillclimb_recap(tmp, lever="VOL_SAFE", taxed_ev_before=0.5, taxed_ev_after=0.4,
                        fill_count_before=10, fill_count_after=20)
        doc = desk_doctor(tmp, health={"alive": True})
        assert doc["passed"] >= 1


if __name__ == "__main__":
    self_check()
    print("desk_top25 self_check ok")
