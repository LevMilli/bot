"""
desk_adapt.py — shared study / learn / adapt for every paper bot.

Rules staff asked for:
  • Recognize volatility → play safe when high.
  • Play bigger only when the bot's own record is consistently ≥80% accurate
    (enough settled sample), still fee-aware and open-risk capped.
  • All towers share this layer so they actually learn from results.

Paper only. Does not place live orders.
"""
from __future__ import annotations

import json
import math
import os
import time
from typing import Any

ADAPT_NAME = "desk_adapt_state.json"
MIN_N_FOR_BIG = 12          # need real sample before sizing up
HIT_FOR_BIG = 0.80          # "80% accurate plays"
HIT_FOR_SAFE = 0.50         # under this → shrink even without vol
VOL_SAFE = 0.65             # vol score ≥ this → play safe
VOL_EXTREME = 0.85

# Kalshi 15m series from staff screenshots (crypto + metals + energy).
SERIES_15M = (
    "KXBTC15M",
    "KXETH15M",
    "KXPALLADIUM15M",
    "KXNATGAS15M",
    "KXCOPPER15M",
    "KXBRENT15M",
    "KXWTI15M",
    "KXSILVER15M",
    "KXGOLD15M",
    "KXPLATINUM15M",
)


def adapt_path(root: str | None = None) -> str:
    base = root or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, ADAPT_NAME)


def _empty() -> dict:
    return {
        "paper_only": True,
        "version": 1,
        "by_bot": {},
        "vol_obs": [],
        "last_at": None,
    }


def load_adapt(root: str | None = None) -> dict:
    path = adapt_path(root)
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
    if not isinstance(base.get("by_bot"), dict):
        base["by_bot"] = {}
    if not isinstance(base.get("vol_obs"), list):
        base["vol_obs"] = []
    return base


def save_adapt(state: dict, root: str | None = None) -> None:
    path = adapt_path(root)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    state = dict(state)
    state["paper_only"] = True
    obs = list(state.get("vol_obs") or [])
    if len(obs) > 2000:
        obs = obs[-2000:]
    state["vol_obs"] = obs
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


def volatility_score(
    *,
    cushion=None,
    sigma=None,
    spread=None,
    minutes_left=None,
    ask=None,
    recent_range=None,
    spot=None,
) -> dict:
    """
    0..1 vol score. Higher = more chaotic → play safer.
    Uses cushion/σ, book spread, time left, and optional recent range %.
    """
    parts: list[float] = []
    reasons: list[str] = []
    c = _finite(cushion)
    s = _finite(sigma)
    if c is not None and s is not None and s > 1e-9:
        # z = cushion/sigma; low z ⇒ high vol relative to edge cushion
        z = c / s
        # map z 0.3→1.0 vol, z 1.5→0.0
        v = max(0.0, min(1.0, (1.5 - z) / 1.2))
        parts.append(v)
        if v >= VOL_SAFE:
            reasons.append(f"thin cushion vs σ (z={z:.2f})")
    sp = _finite(spread)
    if sp is not None:
        # spread 1¢ → mild, 5¢+ → extreme
        v = max(0.0, min(1.0, (sp - 0.01) / 0.04))
        parts.append(v)
        if v >= VOL_SAFE:
            reasons.append(f"wide spread {sp:.3f}")
    ml = _finite(minutes_left)
    if ml is not None and ml < 5:
        # late clocks amplify chaos if also near the money
        late = max(0.0, min(1.0, (5.0 - ml) / 5.0))
        parts.append(0.35 + 0.45 * late)
        if ml <= 3:
            reasons.append(f"late clock {ml:.1f}m")
    ask_n = _finite(ask)
    if ask_n is not None and 0.40 <= ask_n <= 0.60:
        parts.append(0.75)
        reasons.append("near-even ask (coin-flip book)")
    rr = _finite(recent_range)
    px = _finite(spot)
    if rr is not None and px is not None and px > 0:
        pct = abs(rr) / px
        v = max(0.0, min(1.0, pct / 0.01))  # 1% move in window → max
        parts.append(v)
        if v >= VOL_SAFE:
            reasons.append(f"sharp recent range {pct*100:.2f}%")
    if not parts:
        score = 0.35  # unknown → mildly cautious
        reasons.append("vol unknown — cautious default")
    else:
        score = sum(parts) / len(parts)
    score = round(max(0.0, min(1.0, score)), 4)
    if score >= VOL_EXTREME:
        regime = "extreme"
    elif score >= VOL_SAFE:
        regime = "high"
    elif score >= 0.40:
        regime = "elevated"
    else:
        regime = "calm"
    return {"score": score, "regime": regime, "reasons": reasons}


def performance_from_history(history: list | None, window_days: int = 20) -> dict:
    """Hit rate + n from closed rows with signed pnl (same spirit as expectancy)."""
    import desk_profit
    exp = desk_profit.bot_expectancy(history or [], window_days=window_days)
    n = int(exp.get("n") or 0)
    hit = exp.get("hit_rate")
    hit_f = float(hit) if hit is not None else None
    proven = bool(n >= MIN_N_FOR_BIG and hit_f is not None and hit_f + 1e-12 >= HIT_FOR_BIG)
    cold = bool(n >= 8 and hit_f is not None and hit_f + 1e-12 < HIT_FOR_SAFE)
    return {
        "n": n,
        "hit_rate": None if hit_f is None else round(hit_f, 4),
        "expectancy": exp.get("expectancy"),
        "proven_80": proven,
        "cold": cold,
        "window_days": window_days,
    }


def size_multiplier(*, vol: dict | None, perf: dict | None) -> dict:
    """
    Combine vol + track record into a stake multiplier.
    High vol → shrink. Proven ≥80% with enough n → enlarge (still capped).
    """
    vol = vol or {}
    perf = perf or {}
    score = float(vol.get("score") or 0.35)
    regime = str(vol.get("regime") or "elevated")
    mult = 1.0
    notes: list[str] = []

    if regime == "extreme" or score >= VOL_EXTREME:
        mult *= 0.25
        notes.append("extreme vol → 0.25× stake")
    elif regime == "high" or score >= VOL_SAFE:
        mult *= 0.50
        notes.append("high vol → 0.50× stake (play safe)")
    elif regime == "elevated":
        mult *= 0.85
        notes.append("elevated vol → 0.85× stake")

    if perf.get("cold"):
        mult *= 0.50
        notes.append(
            f"cold record hit={perf.get('hit_rate')} n={perf.get('n')} → 0.50×"
        )
    elif perf.get("proven_80"):
        # Only size up when not in high/extreme vol.
        if regime in ("calm", "elevated") and score < VOL_SAFE:
            mult *= 1.75
            notes.append(
                f"proven ≥80% (hit={perf.get('hit_rate')} n={perf.get('n')}) → 1.75×"
            )
        else:
            notes.append("proven ≥80% but vol high — no size-up (safe first)")

    mult = round(max(0.15, min(2.0, mult)), 4)
    return {
        "mult": mult,
        "play_safe": score >= VOL_SAFE or bool(perf.get("cold")),
        "play_big": bool(perf.get("proven_80")) and score < VOL_SAFE,
        "notes": notes,
        "vol": vol,
        "perf": perf,
    }


def adapt_stake(
    base_stake: float,
    *,
    history: list | None = None,
    window_days: int = 20,
    vol_kwargs: dict | None = None,
) -> tuple[float, dict]:
    """Apply adapt multipliers to an already-computed Kelly/curve stake."""
    vol = volatility_score(**(vol_kwargs or {}))
    perf = performance_from_history(history, window_days=window_days)
    plan = size_multiplier(vol=vol, perf=perf)
    try:
        base = float(base_stake)
    except (TypeError, ValueError):
        base = 0.0
    out = round(max(0.0, base * float(plan["mult"])), 2)
    if 0 < out < 1.0:
        out = 0.0
    plan["base"] = round(base, 2)
    plan["stake"] = out
    return out, plan


def remember_vol(root: str | None, bot_id: str, ticker: str, vol: dict, plan: dict) -> None:
    state = load_adapt(root)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    state.setdefault("vol_obs", []).append({
        "at": now,
        "bot": bot_id,
        "ticker": ticker,
        "vol": vol,
        "mult": plan.get("mult"),
        "play_safe": plan.get("play_safe"),
        "play_big": plan.get("play_big"),
    })
    bot = state.setdefault("by_bot", {}).setdefault(
        bot_id, {"obs": 0, "safe": 0, "big": 0, "last_at": None},
    )
    bot["obs"] = int(bot.get("obs") or 0) + 1
    if plan.get("play_safe"):
        bot["safe"] = int(bot.get("safe") or 0) + 1
    if plan.get("play_big"):
        bot["big"] = int(bot.get("big") or 0) + 1
    bot["last_at"] = now
    state["last_at"] = now
    save_adapt(state, root)


def adapt_summary(root: str | None = None) -> dict:
    state = load_adapt(root)
    return {
        "paper_only": True,
        "version": state.get("version", 1),
        "series_15m": list(SERIES_15M),
        "by_bot": state.get("by_bot") or {},
        "recent_vol": list(state.get("vol_obs") or [])[-30:],
        "rules": {
            "play_safe_vol": VOL_SAFE,
            "extreme_vol": VOL_EXTREME,
            "big_needs_hit": HIT_FOR_BIG,
            "big_needs_n": MIN_N_FOR_BIG,
        },
    }


def self_check() -> None:
    calm = volatility_score(cushion=120, sigma=50, spread=0.01, minutes_left=12, ask=0.82)
    assert calm["regime"] in ("calm", "elevated")
    hot = volatility_score(cushion=10, sigma=80, spread=0.05, minutes_left=2, ask=0.50)
    assert hot["score"] >= VOL_SAFE
    stake, plan = adapt_stake(
        40.0,
        history=[{"pnl": 5, "closed": "2026-11-01T12:00:00Z"}] * 15
        + [{"pnl": -2, "closed": "2026-11-01T13:00:00Z"}] * 2,
        vol_kwargs={"cushion": 100, "sigma": 40, "spread": 0.01, "minutes_left": 12, "ask": 0.85},
    )
    assert plan["play_big"] is True
    assert stake > 40.0
    safe_stake, safe_plan = adapt_stake(
        40.0,
        history=[{"pnl": 5, "closed": "2026-11-01T12:00:00Z"}] * 15,
        vol_kwargs={"cushion": 5, "sigma": 80, "spread": 0.06, "minutes_left": 2, "ask": 0.5},
    )
    assert safe_plan["play_safe"] is True
    assert safe_stake < 40.0
