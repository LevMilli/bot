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
    living = None
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
        living = None
        try:
            import desk_living
            living = desk_living.living_upgrade_board(root, bots=bots)
        except Exception:
            living = None
        plan = {
            "bleed": bleed,
            "capital_misplaced": misplaced,
            "fit_firm": desk_roi_plan.fit_buy_rate(root),
            "clv_completeness": desk_roi_plan.clv_completeness(root),
            "sports_hard_stop_shadow": desk_roi_plan.sports_hard_stop_shadow_summary(root),
            "inx_band_promote": desk_roi_plan.inx_band_promote_status(root),
            "correlation": None,
            "weekly_scorecard": weekly,
            "graduation": graduation,
            "meme_retirement": retirement,
            "hillclimb_kill": hillclimb,
            "profit_lock": profit_lock,
            "baseline": baseline,
            "living_upgrade": living,
            "fee_floors_locked": True,
        }
        try:
            from datetime import datetime
            from zoneinfo import ZoneInfo
            today = datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d")
            latest_sr = desk_roi_plan.latest_skip_regret_weekly(root)
            if root and (
                not isinstance(latest_sr, dict)
                or str(latest_sr.get("label") or "") != today
            ):
                plan["skip_regret_weekly"] = desk_roi_plan.skip_regret_weekly_card(
                    root, label=today,
                )
            else:
                plan["skip_regret_weekly"] = latest_sr
        except Exception:
            plan["skip_regret_weekly"] = None
        try:
            from datetime import datetime
            from zoneinfo import ZoneInfo
            today = datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d")
            latest_r = desk_roi_plan.latest_daily_r_board(root)
            if root and bots and (
                not isinstance(latest_r, dict)
                or str(latest_r.get("label") or "") != today
            ):
                plan["daily_r"] = desk_roi_plan.capture_daily_r_board(
                    root, bots, label=today,
                )
            else:
                plan["daily_r"] = latest_r
        except Exception:
            plan["daily_r"] = None
        try:
            import desk_profit
            plan["correlation"] = desk_profit.correlation_matrix(bots, cfg=cfg)
        except Exception:
            plan["correlation"] = None
        try:
            plan["incubation"] = desk_roi_plan.incubation_board(root)
        except Exception:
            plan["incubation"] = None
        try:
            plan["ruin_drill"] = desk_roi_plan.ruin_drill_status(root)
        except Exception:
            plan["ruin_drill"] = None
        try:
            plan["fee_ledger"] = desk_roi_plan.fee_ledger_summary(root)
            plan["fee_ledger_completeness"] = desk_roi_plan.fee_ledger_completeness(
                root, bots=bots,
            )
        except Exception:
            plan["fee_ledger"] = None
            plan["fee_ledger_completeness"] = None
        try:
            plan["stale_world"] = desk_roi_plan.stale_world_status(root, bots=bots)
        except Exception:
            plan["stale_world"] = None
        try:
            plan["helper_gate_a"] = desk_roi_plan.helper_promote_status(root)
        except Exception:
            plan["helper_gate_a"] = None
        try:
            from datetime import datetime
            from zoneinfo import ZoneInfo
            today = datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d")
            latest_ch = desk_roi_plan.cold_harvest_status(root).get("latest")
            if root and bots and (
                not isinstance(latest_ch, dict)
                or str(latest_ch.get("label") or "") != today
            ):
                plan["cold_harvest"] = desk_roi_plan.capture_cold_harvest(
                    root, bots=bots, label=today,
                )
            else:
                plan["cold_harvest"] = desk_roi_plan.cold_harvest_status(root)
        except Exception:
            plan["cold_harvest"] = None
        try:
            plan["hillclimb_lever"] = desk_roi_plan.hillclimb_lever_status(root)
        except Exception:
            plan["hillclimb_lever"] = None
        try:
            plan["dual_control"] = desk_roi_plan.dual_control_status(root)
        except Exception:
            plan["dual_control"] = None
        try:
            plan["quarterly_rebaseline"] = desk_roi_plan.quarterly_rebaseline_status(root)
        except Exception:
            plan["quarterly_rebaseline"] = None
        try:
            from datetime import datetime
            from zoneinfo import ZoneInfo
            today = datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d")
            latest_os = desk_roi_plan.latest_capital_os(root)
            if root and bots and (
                not isinstance(latest_os, dict)
                or str(latest_os.get("label") or "") != today
            ):
                plan["capital_os"] = desk_roi_plan.capture_capital_os(
                    root, bots=bots, cfg=cfg, desk_util=desk_util, label=today,
                )
            else:
                plan["capital_os"] = latest_os or desk_roi_plan.capital_os_status(
                    root, bots=bots, cfg=cfg, desk_util=desk_util,
                )
        except Exception:
            plan["capital_os"] = None
        try:
            plan["opp_cost"] = desk_roi_plan.opp_cost_summary(root)
        except Exception:
            plan["opp_cost"] = None
        try:
            plan["idea_review"] = desk_roi_plan.idea_review_status(root)
        except Exception:
            plan["idea_review"] = None
        try:
            plan["sports_green_boost"] = desk_roi_plan.sports_green_boost_status(
                root, bots=bots,
            )
        except Exception:
            plan["sports_green_boost"] = None
        try:
            plan["green_or_gone"] = desk_roi_plan.green_or_gone_status(bots)
        except Exception:
            plan["green_or_gone"] = None
        try:
            from datetime import datetime
            from zoneinfo import ZoneInfo
            today = datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d")
            latest_bc = desk_roi_plan.latest_btc_calibration(root)
            if root and bots and (
                not isinstance(latest_bc, dict)
                or str(latest_bc.get("label") or "") != today
            ):
                plan["btc_calibration"] = desk_roi_plan.capture_btc_calibration(
                    root, bots=bots, label=today,
                )
            else:
                plan["btc_calibration"] = latest_bc or desk_roi_plan.btc_calibration_report(bots)
        except Exception:
            plan["btc_calibration"] = None
        try:
            from datetime import datetime
            from zoneinfo import ZoneInfo
            today = datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d")
            latest_sc = desk_roi_plan.latest_sports_calibration(root)
            if root and bots and (
                not isinstance(latest_sc, dict)
                or str(latest_sc.get("label") or "") != today
            ):
                plan["sports_calibration"] = desk_roi_plan.capture_sports_calibration(
                    root, bots=bots, label=today,
                )
            else:
                plan["sports_calibration"] = (
                    latest_sc or desk_roi_plan.sports_calibration_report(bots)
                )
        except Exception:
            plan["sports_calibration"] = None
        try:
            from datetime import datetime
            from zoneinfo import ZoneInfo
            today = datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d")
            latest_cc = desk_roi_plan.latest_commodity_calibration(root)
            if root and bots and (
                not isinstance(latest_cc, dict)
                or str(latest_cc.get("label") or "") != today
            ):
                plan["commodity_calibration"] = desk_roi_plan.capture_commodity_calibration(
                    root, bots=bots, label=today,
                )
            else:
                plan["commodity_calibration"] = (
                    latest_cc or desk_roi_plan.commodity_calibration_report(bots)
                )
        except Exception:
            plan["commodity_calibration"] = None
        try:
            status_fq = desk_roi_plan.firm_queue_status(root)
            offers_n = int((status_fq or {}).get("offers_n") or 0)
            latest_fq = (status_fq or {}).get("latest")
            if root and offers_n > 0 and not isinstance(latest_fq, dict):
                desk_roi_plan.capture_firm_queue(root, bots=bots, cfg=cfg)
                status_fq = desk_roi_plan.firm_queue_status(root)
            plan["firm_queue"] = status_fq
        except Exception:
            plan["firm_queue"] = None
        try:
            plan["empty_card"] = desk_roi_plan.empty_card_status(root)
        except Exception:
            plan["empty_card"] = None
        try:
            plan["near_miss_promote"] = desk_roi_plan.near_miss_promote_status(root)
        except Exception:
            plan["near_miss_promote"] = None
    except Exception:
        plan = None
    priority = [
        "revert last lever if hillclimb kill trips",
        "profit-lock 0.5× after weekly target",
        "daily R settle-only after tower budget",
        "memecoin retirement clock before any volume talk",
        "Master graduation = 2 Chicago weeks all M1–M7",
        "sports hard-stop shadow → promote after n≥30",
        "feed idle BTC/commodity risk when gates clear",
        "insight swarm ≥3:1 before betting expand",
    ]
    living_ai = (living or {}).get("living_ai") if isinstance(living, dict) else None
    completions = (living or {}).get("completions") if isinstance(living, dict) else None
    if isinstance(living_ai, dict):
        tickets = living_ai.get("raise_phi_tickets") or []
        if tickets:
            priority.insert(
                0,
                "staff raise_Φ tickets: " + ",".join(str(t) for t in tickets[:6]),
            )
        else:
            priority.append("living AI calib observe (no raise_Φ tickets)")
    if isinstance(completions, dict):
        priority.append(
            f"eligible completions today {completions.get('eligible_completions_today') or 0}"
        )
    feature_quiet = (living or {}).get("feature_quiet") if isinstance(living, dict) else None
    if isinstance(feature_quiet, dict) and feature_quiet.get("quiet") and feature_quiet.get("alert"):
        priority.insert(0, str(feature_quiet.get("alert"))[:120])
    hillclimb_lever = (living or {}).get("hillclimb_lever") if isinstance(living, dict) else None
    if isinstance(hillclimb_lever, dict):
        active = hillclimb_lever.get("active") if isinstance(hillclimb_lever.get("active"), dict) else None
        if active:
            priority.append(f"hillclimb lever active: {active.get('name') or active.get('lever')}")
        else:
            priority.append("hillclimb: no staff lever this Chicago week (observe)")
    dual_control = (living or {}).get("dual_control") if isinstance(living, dict) else None
    if isinstance(dual_control, dict):
        priority.append(
            f"dual-control paper {dual_control.get('signed_n') or 0}/"
            f"{dual_control.get('items_n') or 0} signed; "
            f"live_orders={bool(dual_control.get('live_orders_enabled'))}"
        )
    ruin_drill = (living or {}).get("ruin_drill") if isinstance(living, dict) else None
    if isinstance(ruin_drill, dict):
        if ruin_drill.get("active"):
            priority.insert(0, f"ruin drill ACTIVE level={ruin_drill.get('level')}")
        elif not ruin_drill.get("practiced_this_month"):
            priority.append("ruin drill: practice soft/hard this Chicago month")
    green_day = (living or {}).get("green_day") if isinstance(living, dict) else None
    if isinstance(green_day, dict):
        sg = green_day.get("sports_green_boost") or {}
        priority.append(
            f"fee-clear green {green_day.get('green_n') or 0}/"
            f"{len(green_day.get('towers') or [])}; "
            f"sports_green_boost={sg.get('green_boost') or 0}"
        )
    firm_queue = (living or {}).get("firm_queue") if isinstance(living, dict) else None
    if isinstance(firm_queue, dict) and firm_queue.get("offers_n") is not None:
        priority.append(str(firm_queue.get("label") or "firm queue")[:120])
    empty_card = (living or {}).get("empty_card") if isinstance(living, dict) else None
    if isinstance(empty_card, dict) and empty_card.get("pass") is False:
        priority.insert(0, str(empty_card.get("label") or "empty CARD slow")[:120])
    near_miss = (living or {}).get("near_miss") if isinstance(living, dict) else None
    if isinstance(near_miss, dict) and near_miss.get("promote_ready"):
        priority.append("near-miss promote_ready — staff arm z|p only")
    timer_hb = (living or {}).get("timer_heartbeat") if isinstance(living, dict) else None
    if isinstance(timer_hb, dict) and not timer_hb.get("alive"):
        priority.insert(0, str(timer_hb.get("label") or "timer DEAD")[:120])
    gate_a = (living or {}).get("helper_gate_a") if isinstance(living, dict) else None
    if isinstance(gate_a, dict) and int(gate_a.get("ready_n") or 0) > 0:
        priority.append(str(gate_a.get("label") or "helper Gate A")[:120])
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
        "priority": priority,
        "swarm_lights": (
            (living or {}).get("insight_swarm")
            if isinstance(living, dict)
            else None
        ),
        "living_ai": living_ai,
        "completions": completions,
        "feature_quiet": feature_quiet,
        "hillclimb_lever": hillclimb_lever,
        "dual_control": dual_control,
        "ruin_drill": ruin_drill,
        "skip_taxonomy": (
            (living or {}).get("skip_taxonomy")
            if isinstance(living, dict)
            else None
        ),
        "green_day": (
            (living or {}).get("green_day")
            if isinstance(living, dict)
            else None
        ),
        "firm_queue": (
            (living or {}).get("firm_queue")
            if isinstance(living, dict)
            else None
        ),
        "empty_card": (
            (living or {}).get("empty_card")
            if isinstance(living, dict)
            else None
        ),
        "near_miss": (
            (living or {}).get("near_miss")
            if isinstance(living, dict)
            else None
        ),
        "timer_heartbeat": (
            (living or {}).get("timer_heartbeat")
            if isinstance(living, dict)
            else None
        ),
        "helper_gate_a": (
            (living or {}).get("helper_gate_a")
            if isinstance(living, dict)
            else None
        ),
        "live_orders_enabled": False,
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
