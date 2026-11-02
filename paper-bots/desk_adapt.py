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
HIT_FOR_BIG = 0.80          # "80% accurate plays" (point estimate floor)
HIT_CI_FLOOR = 0.70         # Wilson lower bound must clear this before play-big
WILSON_Z = 1.96             # ~95% CI
HIT_FOR_SAFE = 0.50         # under this → shrink even without vol
VOL_SAFE = 0.65             # vol score ≥ this → play safe
VOL_EXTREME = 0.85
FALSE_CONF_ASK = 0.90       # rich book ask
FALSE_CONF_Z_MIN = 0.65     # thin cushion/σ below this + rich ask → safe

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


def wilson_lower(hits: int, n: int, z: float = WILSON_Z) -> float | None:
    """Wilson score-interval lower bound for a binomial hit rate."""
    try:
        hits_i = int(hits)
        n_i = int(n)
        z_f = float(z)
    except (TypeError, ValueError):
        return None
    if n_i <= 0 or hits_i < 0 or hits_i > n_i or z_f < 0:
        return None
    phat = hits_i / n_i
    z2 = z_f * z_f
    denom = 1.0 + z2 / n_i
    centre = phat + z2 / (2.0 * n_i)
    radical = (phat * (1.0 - phat) + z2 / (4.0 * n_i)) / n_i
    if radical < 0:
        radical = 0.0
    lower = (centre - z_f * math.sqrt(radical)) / denom
    return round(max(0.0, min(1.0, lower)), 4)


def false_confidence(
    *,
    ask=None,
    cushion=None,
    sigma=None,
    z_min: float = FALSE_CONF_Z_MIN,
    ask_floor: float = FALSE_CONF_ASK,
) -> bool:
    """True when the book looks 'sure' but cushion vs σ is thin (screenshot 99% trap)."""
    ask_n = _finite(ask)
    c = _finite(cushion)
    s = _finite(sigma)
    if ask_n is None or c is None or s is None or s <= 1e-9:
        return False
    if ask_n + 1e-12 < float(ask_floor):
        return False
    z = c / s
    return z < float(z_min)


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
    # False confidence: rich ask (e.g. 98–99¢) with thin cushion/σ → treat as high vol.
    if false_confidence(ask=ask, cushion=cushion, sigma=sigma):
        parts.append(0.90)
        c = _finite(cushion)
        s = _finite(sigma)
        z = (c / s) if (c is not None and s is not None and s > 1e-9) else None
        z_txt = f"{z:.2f}" if z is not None else "?"
        reasons.append(f"false confidence: rich ask {ask_n:.2f} / thin z={z_txt}")
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
    """Hit rate + n from closed rows with signed pnl (same spirit as expectancy).

    proven_80 requires point hit ≥ 80%, n ≥ MIN_N_FOR_BIG, AND Wilson lower ≥ HIT_CI_FLOOR
    so a lucky short streak cannot unlock play-big sizing.
    """
    import desk_profit
    exp = desk_profit.bot_expectancy(history or [], window_days=window_days)
    n = int(exp.get("n") or 0)
    hit = exp.get("hit_rate")
    hit_f = float(hit) if hit is not None else None
    # Reconstruct win count from expectancy hit_rate (same window as n).
    hits = int(round(hit_f * n)) if hit_f is not None and n > 0 else 0
    ci_low = wilson_lower(hits, n) if n > 0 else None
    proven = bool(
        n >= MIN_N_FOR_BIG
        and hit_f is not None
        and hit_f + 1e-12 >= HIT_FOR_BIG
        and ci_low is not None
        and ci_low + 1e-12 >= HIT_CI_FLOOR
    )
    cold = bool(n >= 8 and hit_f is not None and hit_f + 1e-12 < HIT_FOR_SAFE)
    return {
        "n": n,
        "hit_rate": None if hit_f is None else round(hit_f, 4),
        "hit_ci_low": ci_low,
        "hits": hits if n > 0 else 0,
        "expectancy": exp.get("expectancy"),
        "proven_80": proven,
        "cold": cold,
        "window_days": window_days,
    }


def size_multiplier(*, vol: dict | None, perf: dict | None) -> dict:
    """
    Combine vol + track record into a stake multiplier.
    High vol / false confidence → shrink. Proven ≥80% with Wilson CI → enlarge.
    """
    vol = vol or {}
    perf = perf or {}
    score = float(vol.get("score") or 0.35)
    regime = str(vol.get("regime") or "elevated")
    notes: list[str] = []

    fc = any("false confidence" in str(r) for r in (vol.get("reasons") or []))
    if fc and score < VOL_SAFE:
        score = max(score, VOL_SAFE)
        regime = "high"
        notes.append("false confidence → treat as high vol")

    mult = 1.0
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
        if regime in ("calm", "elevated") and score < VOL_SAFE and not fc:
            mult *= 1.75
            notes.append(
                f"proven ≥80% (hit={perf.get('hit_rate')} ci_low={perf.get('hit_ci_low')} "
                f"n={perf.get('n')}) → 1.75×"
            )
        else:
            notes.append("proven ≥80% but vol/false-conf high — no size-up (safe first)")
    elif (
        perf.get("hit_rate") is not None
        and int(perf.get("n") or 0) >= MIN_N_FOR_BIG
        and float(perf.get("hit_rate") or 0) + 1e-12 >= HIT_FOR_BIG
        and (perf.get("hit_ci_low") is None or float(perf.get("hit_ci_low") or 0) < HIT_CI_FLOOR)
    ):
        notes.append(
            f"hit={perf.get('hit_rate')} but Wilson ci_low={perf.get('hit_ci_low')} "
            f"< {HIT_CI_FLOOR} — no size-up"
        )

    mult = round(max(0.15, min(2.0, mult)), 4)
    play_safe = score >= VOL_SAFE or bool(perf.get("cold")) or fc
    play_big = bool(perf.get("proven_80")) and score < VOL_SAFE and not fc
    return {
        "mult": mult,
        "play_safe": play_safe,
        "play_big": play_big,
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
            "big_needs_ci_low": HIT_CI_FLOOR,
            "big_needs_n": MIN_N_FOR_BIG,
            "false_conf_ask": FALSE_CONF_ASK,
            "false_conf_z_min": FALSE_CONF_Z_MIN,
        },
    }


def self_check() -> None:
    calm = volatility_score(cushion=120, sigma=50, spread=0.01, minutes_left=12, ask=0.82)
    assert calm["regime"] in ("calm", "elevated")
    hot = volatility_score(cushion=10, sigma=80, spread=0.05, minutes_left=2, ask=0.50)
    assert hot["score"] >= VOL_SAFE
    # Rich ask + thin cushion must flag false confidence.
    fc = volatility_score(cushion=8, sigma=80, spread=0.01, minutes_left=12, ask=0.98)
    assert any("false confidence" in r for r in fc["reasons"])
    assert false_confidence(ask=0.98, cushion=8, sigma=80) is True
    assert wilson_lower(20, 20) is not None and wilson_lower(20, 20) >= HIT_CI_FLOOR
    # Lucky short streak (≥80% point, weak CI) must NOT play big.
    lucky = [{"pnl": 5, "closed": "2026-11-01T12:00:00Z"}] * 10
    lucky += [{"pnl": -1, "closed": "2026-11-01T13:00:00Z"}] * 2
    lucky_perf = performance_from_history(lucky)
    assert lucky_perf["hit_rate"] is not None and lucky_perf["hit_rate"] >= HIT_FOR_BIG
    assert lucky_perf["proven_80"] is False
    # Strong record with CI clears floor → play big when calm.
    strong = [{"pnl": 5, "closed": "2026-11-01T12:00:00Z"}] * 25
    strong += [{"pnl": -1, "closed": "2026-11-01T13:00:00Z"}] * 3
    stake, plan = adapt_stake(
        40.0,
        history=strong,
        vol_kwargs={"cushion": 100, "sigma": 40, "spread": 0.01, "minutes_left": 12, "ask": 0.85},
    )
    assert plan["play_big"] is True
    assert stake > 40.0
    # Same strong record but false-confidence book → safe, no size-up.
    fc_stake, fc_plan = adapt_stake(
        40.0,
        history=strong,
        vol_kwargs={"cushion": 8, "sigma": 80, "spread": 0.01, "minutes_left": 12, "ask": 0.98},
    )
    assert fc_plan["play_safe"] is True
    assert fc_plan["play_big"] is False
    assert fc_stake < 40.0
    safe_stake, safe_plan = adapt_stake(
        40.0,
        history=[{"pnl": 5, "closed": "2026-11-01T12:00:00Z"}] * 15,
        vol_kwargs={"cushion": 5, "sigma": 80, "spread": 0.06, "minutes_left": 2, "ask": 0.5},
    )
    assert safe_plan["play_safe"] is True
    assert safe_stake < 40.0
