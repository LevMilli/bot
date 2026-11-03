"""
desk_master.py — Trading Masters scoreboard stub (M1–M7).

Paper only. Surfaces dual metrics (volume vs taxed EV) so staff can see whether
throughput upgrades are helping ROI — not a profit guarantee.
"""
from __future__ import annotations

import math
import os
from typing import Any

MASTER_VERSION = 1

# Bars from docs/trading-masters-per-bot-plan.md (Chicago weeks).
MASTER_BARS = {
    "M1_taxed_ev": 0.0,
    "M2_hit_rate": 0.55,
    "M3_fit_buy": 0.40,
    "M5_util_lo": 0.40,
    "M5_util_hi": 0.80,
    "M6_gate_a_n": 20,
}


def _finite(x) -> float | None:
    try:
        n = float(x)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(n):
        return None
    return n


def _taxed_expectancy(history: list, fill_tax: float = 0.01) -> dict:
    rows = [h for h in (history or []) if isinstance(h, dict)]
    pnls = []
    for h in rows:
        p = _finite(h.get("pnl") if h.get("pnl") is not None else h.get("pnl_usd"))
        if p is None:
            continue
        # Crude fill tax: subtract 1¢ * contracts proxy when present, else flat tax once.
        contracts = _finite(h.get("contracts")) or 1.0
        pnls.append(p - float(fill_tax) * max(1.0, contracts))
    n = len(pnls)
    if n <= 0:
        return {"n": 0, "expectancy_taxed": None, "hit_rate": None}
    hits = sum(1 for p in pnls if p > 0)
    return {
        "n": n,
        "expectancy_taxed": round(sum(pnls) / n, 4),
        "hit_rate": round(hits / n, 4),
    }


def tower_master_row(bot: dict, *, fill_tax: float = 0.01, cfg: dict | None = None) -> dict:
    """One tower's master metrics from snapshot bot view."""
    cfg = cfg or {}
    bot_id = str(bot.get("id") or "")
    hist = list(bot.get("history") or [])
    taxed = _taxed_expectancy(hist, fill_tax=fill_tax)
    open_risk = _finite(bot.get("open_risk")) or 0.0
    desk_cap = _finite(cfg.get("max_open_risk")) or 100.0
    shares = cfg.get("tower_risk_budgets") if isinstance(cfg.get("tower_risk_budgets"), dict) else {}
    share = _finite(shares.get(bot_id)) if shares else None
    tower_cap = round(desk_cap * share, 2) if share is not None else None
    util = None
    if tower_cap and tower_cap > 0:
        util = round(min(1.0, open_risk / tower_cap), 4)
    ga = bot.get("gate_a") if isinstance(bot.get("gate_a"), dict) else {}
    m1 = taxed.get("expectancy_taxed")
    m2 = taxed.get("hit_rate")
    n = int(taxed.get("n") or 0)
    ready_bits = {
        "M1": m1 is not None and m1 >= MASTER_BARS["M1_taxed_ev"] and n >= 5,
        "M2": m2 is not None and m2 >= MASTER_BARS["M2_hit_rate"] and n >= 10,
        "M6": bool(ga.get("ready")),
    }
    return {
        "bot": bot_id,
        "paper_only": True,
        "n_settles": n,
        "M1_taxed_ev": m1,
        "M2_hit_rate": m2,
        "M3_fit_buy": None,  # filled when skip/fit journals mature
        "M4_latency_s": None,
        "M5_tower_util": util,
        "M6_gate_a": bool(ga.get("ready")),
        "open_risk": round(open_risk, 2),
        "tower_cap": tower_cap,
        "today": bot.get("today"),
        "passing": ready_bits,
        "note": "M3/M4 stub until fit journals + latency timers land",
    }


def meme_stopbleed_measure(bot: dict | None = None, *, red_lock_usd: float = 8.0) -> dict:
    """Measure memecoin stop-bleed week after ROI-rescue exits (−12% / flip −6% / red −$8).

    Paper only. Does not expand volume. Counts SELL exits from history reasons.
    """
    bot = bot if isinstance(bot, dict) else {}
    hist = [h for h in (bot.get("history") or []) if isinstance(h, dict)]
    sells = []
    for h in hist:
        side = str(h.get("side") or "").upper()
        reason = str(h.get("exit_reason") or h.get("exit") or h.get("reason") or h.get("what") or "")
        # Prefer true SELLs; also accept reason-tagged rows without side.
        if side and side != "SELL" and "SELL" not in str(h.get("what") or "").upper():
            continue
        if not reason and side != "SELL" and "SELL" not in str(h.get("what") or "").upper():
            continue
        sells.append(h if reason else {**h, "exit_reason": str(h.get("what") or "")})
    stop_n = 0
    flip_n = 0
    trail_n = 0
    other_n = 0
    stop_pnl = 0.0
    for h in sells:
        reason = str(h.get("exit_reason") or h.get("exit") or h.get("reason") or h.get("what") or "").lower()
        pnl = _finite(h.get("pnl") if h.get("pnl") is not None else h.get("pnl_usd")) or 0.0
        if "model-flip" in reason or "model flip" in reason:
            flip_n += 1
            stop_pnl += pnl
        elif "stop" in reason and "time_stop" not in reason and "trail" not in reason:
            stop_n += 1
            stop_pnl += pnl
        elif "trail" in reason:
            trail_n += 1
        else:
            other_n += 1
    today = _finite(bot.get("today"))
    red_locked = today is not None and today <= -float(red_lock_usd)
    volume_ok = (stop_n + flip_n) >= 1 or red_locked is False
    # Expand volume only after a clean measure week with no fresh bleed — staff gate.
    expand_volume = False
    if stop_n + flip_n >= 3 and (stop_pnl / max(1, stop_n + flip_n)) > -5 and not red_locked:
        expand_volume = False  # still require explicit staff week pass; never auto-expand
    return {
        "paper_only": True,
        "bot": str(bot.get("id") or "memecoin"),
        "sells_n": len(sells),
        "stop_exits": stop_n,
        "model_flip_exits": flip_n,
        "trail_exits": trail_n,
        "other_exits": other_n,
        "stopbleed_pnl": round(stop_pnl, 2),
        "today": today,
        "red_day_locked": red_locked,
        "red_lock_usd": float(red_lock_usd),
        "policy": {
            "stop_pct": -12,
            "model_flip_momentum_h1_floor": -6,
            "red_day_entry_lock_usd": float(red_lock_usd),
            "max_open_red": 1,
        },
        "expand_volume": expand_volume,
        "volume_ok_to_discuss": volume_ok,
        "note": (
            "Stop-bleed measure only — do not expand memecoin volume until a Chicago "
            "week clears with taxed EV ≥ 0 and red-day lock proven. No profit guarantee."
        ),
    }


def firm_roi_rescue(bots: list | None = None, *, cfg: dict | None = None) -> dict:
    """Overnight ROI rescue flags — which towers should refuse new entries."""
    cfg = cfg or {}
    flags = []
    for bot in bots or []:
        if not isinstance(bot, dict):
            continue
        bot_id = str(bot.get("id") or "")
        today = _finite(bot.get("today"))
        cash = _finite(bot.get("cash"))
        realized = _finite(bot.get("realized"))
        if bot_id == "memecoin" and today is not None and today <= -8:
            flags.append({
                "bot": bot_id,
                "action": "entries_off",
                "why": f"meme red-day lock (today ${today:.2f} ≤ −$8)",
            })
        if bot_id in ("kalshi-sp", "kalshi-sized") and cash is not None and cash <= 460:
            flags.append({
                "bot": bot_id,
                "action": "entries_off",
                "why": f"INX drawdown halt (cash ${cash:.2f} ≤ $460)",
            })
        if bot_id == "sports-gap" and today is not None and today <= -10:
            flags.append({
                "bot": bot_id,
                "action": "accurate_only_cap1",
                "why": f"sports red rescue (today ${today:.2f} ≤ −$10)",
            })
        if realized is not None and realized <= -40 and bot_id.startswith("kalshi"):
            flags.append({
                "bot": bot_id,
                "action": "review",
                "why": f"deep realized ${realized:.2f} — human review before volume",
            })
    return {
        "paper_only": True,
        "n_flags": len(flags),
        "flags": flags[:20],
        "note": (
            "Rescue = stop bleed / starve losers / keep fee floors. "
            "No profit guarantee. Quiet commodity/sized with no edge is OK."
        ),
    }


def master_summary(
    root: str | None = None,
    *,
    bots: list | None = None,
    cfg: dict | None = None,
    fill_tax: float = 0.01,
) -> dict:
    """Desk-level Trading Masters board."""
    _ = root  # reserved for future journal paths
    cfg = cfg or {}
    rows = [tower_master_row(b, fill_tax=fill_tax, cfg=cfg) for b in (bots or []) if isinstance(b, dict)]
    desk_open = round(sum(float(r.get("open_risk") or 0) for r in rows), 2)
    desk_cap = _finite(cfg.get("max_open_risk")) or 100.0
    desk_util = round(desk_open / desk_cap, 4) if desk_cap else None
    m1_ready = sum(1 for r in rows if (r.get("passing") or {}).get("M1"))
    meme = next((b for b in (bots or []) if isinstance(b, dict) and b.get("id") == "memecoin"), None)
    stopbleed = meme_stopbleed_measure(meme)
    rescue = firm_roi_rescue(bots, cfg=cfg)
    return {
        "paper_only": True,
        "version": MASTER_VERSION,
        "bars": dict(MASTER_BARS),
        "desk_open_risk": desk_open,
        "desk_cap": desk_cap,
        "M5_desk_util": desk_util,
        "roi_rescue": rescue,
        "towers_m1_pass": m1_ready,
        "towers": rows,
        "stopbleed": stopbleed,
        "priority": [
            "memecoin stop-bleed before volume",
            "sports tip alarms",
            "feed idle BTC/commodity risk when gates clear",
        ],
        "note": (
            "Trading Masters stub — dual scoreboard for volume vs taxed EV. "
            "No profit guarantee. Fee floors unchanged."
        ),
    }


def self_check() -> None:
    row = tower_master_row(
        {
            "id": "sports-gap",
            "open_risk": 10,
            "history": [{"pnl": 2.0, "contracts": 1}, {"pnl": -1.0, "contracts": 1}] * 6,
            "gate_a": {"ready": False},
        },
        cfg={"max_open_risk": 100, "tower_risk_budgets": {"sports-gap": 0.35}},
    )
    assert row["n_settles"] == 12
    assert row["M1_taxed_ev"] is not None
    assert row["tower_cap"] == 35.0
    summary = master_summary(
        bots=[{"id": "memecoin", "open_risk": 5, "history": [], "gate_a": {}}],
        cfg={"max_open_risk": 100, "tower_risk_budgets": {"memecoin": 0.05}},
    )
    assert summary["version"] == MASTER_VERSION
    assert "towers" in summary
    assert isinstance(summary.get("stopbleed"), dict)
    assert isinstance(summary.get("roi_rescue"), dict)
    bleed = meme_stopbleed_measure(
        {
            "id": "memecoin",
            "today": -22,
            "history": [
                {"side": "SELL", "exit_reason": "stop -19.2% <= -18%", "pnl": -4.5},
                {"side": "SELL", "exit_reason": "model-flip momentum -9.0% <= -8.0%", "pnl": -2.1},
                {"side": "BUY", "reason": "entry", "pnl": None},
            ],
        }
    )
    assert bleed["stop_exits"] == 1
    assert bleed["model_flip_exits"] == 1
    assert bleed["red_day_locked"] is True
    assert bleed["expand_volume"] is False
    rescue = firm_roi_rescue(
        [
            {"id": "memecoin", "today": -10.58, "cash": 7.01},
            {"id": "kalshi-sp", "cash": 444.37, "realized": -55.63},
            {"id": "sports-gap", "today": -16.25},
        ]
    )
    assert rescue["n_flags"] >= 3


if __name__ == "__main__":
    self_check()
    print("desk_master self_check ok")
