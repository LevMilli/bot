"""
desk_master.py — Trading Masters scoreboard (M1–M7).

Paper only. Surfaces dual metrics (volume vs taxed EV) so staff can see whether
throughput upgrades are helping ROI — not a profit guarantee.

M3/M4 read desk_roi_plan fit + latency journals (no longer stubs).
"""
from __future__ import annotations

import math
import os
from typing import Any

MASTER_VERSION = 3

# Bars from docs/trading-masters-per-bot-plan.md (Chicago weeks).
MASTER_BARS = {
    "M1_taxed_ev": 0.0,
    "M2_hit_rate": 0.55,
    "M3_fit_buy": 0.40,
    "M4_latency_15m_s": 20.0,
    "M4_latency_sports_s": 45.0,
    "M5_util_lo": 0.40,
    "M5_util_hi": 0.80,
    "M6_gate_a_n": 20,
    "M7_gate_b_dd": 40.0,
    "M7_gate_b_n": 20,
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


def tower_master_row(
    bot: dict,
    *,
    fill_tax: float = 0.01,
    cfg: dict | None = None,
    root: str | None = None,
) -> dict:
    """One tower's master metrics from snapshot bot view + ROI plan journals."""
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
    m3 = None
    m3_n = 0
    m4 = None
    m4_n = 0
    try:
        import desk_roi_plan
        fb = desk_roi_plan.fit_buy_rate(root, bot_id)
        m3 = fb.get("rate")
        m3_n = int(fb.get("n_fit") or 0)
        lat = desk_roi_plan.latency_p50(root, bot_id)
        m4 = lat.get("p50_s")
        m4_n = int(lat.get("n") or 0)
    except Exception:
        pass
    m4_bar = (
        MASTER_BARS["M4_latency_sports_s"]
        if bot_id == "sports-gap"
        else MASTER_BARS["M4_latency_15m_s"]
    )
    # M5: tower util in band when measured; idle with no open risk counts as calm pass.
    m5_pass = False
    if util is not None:
        m5_pass = MASTER_BARS["M5_util_lo"] <= util <= MASTER_BARS["M5_util_hi"]
    elif open_risk <= 0:
        m5_pass = True
    # M7: Gate B twin ($40 DD / n≥20) via desk_top25 when available.
    m7 = None
    m7_pass = False
    try:
        import desk_top25
        m7 = desk_top25.gate_b(
            hist,
            max_drawdown=MASTER_BARS["M7_gate_b_dd"],
            min_n=int(MASTER_BARS["M7_gate_b_n"]),
        )
        m7_pass = bool(m7.get("ready"))
    except Exception:
        m7 = None
        m7_pass = False
    ready_bits = {
        "M1": m1 is not None and m1 >= MASTER_BARS["M1_taxed_ev"] and n >= 5,
        "M2": m2 is not None and m2 >= MASTER_BARS["M2_hit_rate"] and n >= 10,
        "M3": m3 is not None and m3_n >= 10 and m3 >= MASTER_BARS["M3_fit_buy"],
        "M4": m4 is not None and m4_n >= 5 and m4 <= m4_bar,
        "M5": m5_pass,
        "M6": bool(ga.get("ready")),
        "M7": m7_pass,
    }
    return {
        "bot": bot_id,
        "paper_only": True,
        "n_settles": n,
        "M1_taxed_ev": m1,
        "M2_hit_rate": m2,
        "M3_fit_buy": m3,
        "M3_n_fit": m3_n,
        "M4_latency_s": m4,
        "M4_n": m4_n,
        "M4_bar_s": m4_bar,
        "M5_tower_util": util,
        "M6_gate_a": bool(ga.get("ready")),
        "M7_gate_b": m7,
        "open_risk": round(open_risk, 2),
        "tower_cap": tower_cap,
        "today": bot.get("today"),
        "passing": ready_bits,
        "all_codes": all(ready_bits.values()),
        "note": "M3/M4 from desk_roi_plan; M7 Gate B twin $40/n≥20",
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
    cfg = cfg or {}
    rows = [
        tower_master_row(b, fill_tax=fill_tax, cfg=cfg, root=root)
        for b in (bots or [])
        if isinstance(b, dict)
    ]
    desk_open = round(sum(float(r.get("open_risk") or 0) for r in rows), 2)
    desk_cap = _finite(cfg.get("max_open_risk")) or 100.0
    desk_util = round(desk_open / desk_cap, 4) if desk_cap else None
    m1_ready = sum(1 for r in rows if (r.get("passing") or {}).get("M1"))
    meme = next((b for b in (bots or []) if isinstance(b, dict) and b.get("id") == "memecoin"), None)
    stopbleed = meme_stopbleed_measure(meme)
    rescue = firm_roi_rescue(bots, cfg=cfg)
    bleed = None
    misplaced = None
    plan = None
    graduation = None
    retirement = None
    hillclimb = None
    profit_lock = None
    try:
        import desk_roi_plan
        bleed = desk_roi_plan.firm_bleed_ratio(bots)
        misplaced = desk_roi_plan.capital_misplaced(bots, cfg)
        baseline_store = desk_roi_plan.load_baseline(root)
        baseline = baseline_store.get("latest") if isinstance(baseline_store, dict) else None
        # Auto-capture W0 once so staff always have a compare point.
        if root and not baseline and bots:
            try:
                baseline = desk_roi_plan.capture_baseline(
                    root, bots=bots, cfg=cfg, label="W0",
                )
            except Exception:
                baseline = None
        weekly = None
        graduation = None
        retirement = None
        try:
            # Refresh Chicago-day scorecard once per day for hillclimb reviews.
            from datetime import datetime
            from zoneinfo import ZoneInfo
            today = datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d")
            latest = desk_roi_plan.latest_weekly_scorecard(root)
            if root and bots and (
                not isinstance(latest, dict) or str(latest.get("label") or "") != today
            ):
                weekly = desk_roi_plan.capture_weekly_scorecard(
                    root, bots=bots, cfg=cfg, label=today,
                )
            else:
                weekly = latest
        except Exception:
            weekly = None
        try:
            if root and rows:
                desk_roi_plan.capture_graduation_week(root, rows)
            graduation = desk_roi_plan.graduation_board(root)
        except Exception:
            graduation = None
        try:
            retirement = desk_roi_plan.meme_retirement_clock(meme)
        except Exception:
            retirement = None
        hillclimb = None
        try:
            if root and bots:
                from datetime import datetime
                from zoneinfo import ZoneInfo
                today = datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d")
                latest_hc = desk_roi_plan.hillclimb_kill_status(root).get("latest")
                if not isinstance(latest_hc, dict) or str(latest_hc.get("label") or "") != today:
                    desk_roi_plan.capture_hillclimb_week(root, bots=bots, label=today)
            hillclimb = desk_roi_plan.hillclimb_kill_status(root)
        except Exception:
            hillclimb = None
        profit_lock = None
        try:
            if root and bots:
                from datetime import datetime
                from zoneinfo import ZoneInfo
                today = datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d")
                latest_pl = desk_roi_plan.profit_lock_status(root).get("latest")
                if not isinstance(latest_pl, dict) or str(latest_pl.get("label") or "") != today:
                    desk_roi_plan.capture_profit_lock(root, bots=bots, label=today)
            profit_lock = desk_roi_plan.profit_lock_status(root)
        except Exception:
            profit_lock = None
        plan = {
            "bleed": bleed,
            "capital_misplaced": misplaced,
            "fit_firm": desk_roi_plan.fit_buy_rate(root),
            "clv_completeness": desk_roi_plan.clv_completeness(root),
            "sports_hard_stop_shadow": desk_roi_plan.sports_hard_stop_shadow_summary(root),
            "weekly_scorecard": weekly,
            "graduation": graduation,
            "meme_retirement": retirement,
            "hillclimb_kill": hillclimb,
            "profit_lock": profit_lock,
            "baseline": baseline,
            "fee_floors_locked": True,
        }
    except Exception:
        plan = None
    return {
        "paper_only": True,
        "version": MASTER_VERSION,
        "bars": dict(MASTER_BARS),
        "desk_open_risk": desk_open,
        "desk_cap": desk_cap,
        "M5_desk_util": desk_util,
        "roi_rescue": rescue,
        "bleed": bleed,
        "capital_misplaced": misplaced,
        "roi_plan": plan,
        "graduation": graduation,
        "meme_retirement": retirement,
        "hillclimb_kill": hillclimb,
        "profit_lock": profit_lock,
        "towers_m1_pass": m1_ready,
        "towers": rows,
        "stopbleed": stopbleed,
        "priority": [
            "revert last lever if hillclimb kill trips",
            "profit-lock 0.5× after weekly target",
            "memecoin retirement clock before any volume talk",
            "Master graduation = 2 Chicago weeks all M1–M7",
            "sports hard-stop shadow → promote after n≥30",
            "feed idle BTC/commodity risk when gates clear",
        ],
        "note": (
            "Trading Masters — dual scoreboard for volume vs taxed EV. "
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
