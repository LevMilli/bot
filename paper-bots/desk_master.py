"""
desk_master.py — Trading Masters scoreboard (M1–M7).

Paper only. Surfaces dual metrics (volume vs taxed EV) so staff can see whether
throughput upgrades are helping ROI — not a profit guarantee.

M3/M4 read desk_roi_plan fit + latency journals (no longer stubs).
"""
from __future__ import annotations

import json
import math
import os
from typing import Any

MASTER_VERSION = 3
# Keep Masters rail readable — urgent inserts stay first; drop near-dupes.
PRIORITY_MAX = 16
_PRIORITY_FAMILY_PREFIXES = (
    ("timer", ("timer",)),
    ("bleed", ("bleed",)),
    ("near-miss", ("near-miss", "skip-twin")),
    ("hard-stop", ("hard-stop", "sports hard-stop")),
    ("clv", ("clv",)),
    ("dual", ("dual-control",)),
    ("ruin", ("ruin",)),
    ("empty", ("empty card", "empty bee", "distance empty")),
    ("eia", ("eia ",)),
    ("feature", ("feature quiet", "weekday alert: feature")),
    ("expand", ("betting expand",)),
    ("doctor", ("doctor", "living doctor")),
    ("ritual", ("ritual", "ritual_ok")),
    ("tip", ("tip radar", "tip T")),
    ("pulse", ("clerk pulse",)),
)

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


def _priority_family(line: str) -> str | None:
    low = str(line or "").strip().lower()
    for family, prefixes in _PRIORITY_FAMILY_PREFIXES:
        for prefix in prefixes:
            if low.startswith(prefix):
                return family
    return None


def finalize_living_priority(lines: list | None, *, max_n: int = PRIORITY_MAX) -> list[str]:
    """Dedupe noisy living rail lines; keep first (urgent inserts already front)."""
    out: list[str] = []
    seen_exact: set[str] = set()
    seen_family: set[str] = set()
    for raw in lines or []:
        text = str(raw or "").strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen_exact:
            continue
        family = _priority_family(text)
        if family and family in seen_family:
            continue
        seen_exact.add(key)
        if family:
            seen_family.add(family)
        out.append(text[:160])
        if len(out) >= int(max_n):
            break
    return out


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
    # #663/#694: annotate idle-pass vs BUDGET-starvation (never hide starvation).
    m5_pass = False
    m5_ann = {
        "m5_annotation": "util_out_of_band",
        "tooltip": "M5 util_out_of_band",
        "budget_skip_n": 0,
    }
    try:
        import desk_roi_plan
        m5_ann = desk_roi_plan.m5_idle_vs_budget_annotation(
            bot_id,
            util=util,
            open_risk=open_risk,
            root=root,
            m5_lo=MASTER_BARS["M5_util_lo"],
            m5_hi=MASTER_BARS["M5_util_hi"],
        )
        m5_pass = bool(m5_ann.get("m5_pass"))
    except Exception:
        if util is not None:
            m5_pass = MASTER_BARS["M5_util_lo"] <= util <= MASTER_BARS["M5_util_hi"]
        elif open_risk <= 0:
            m5_pass = True
            m5_ann = {
                "m5_annotation": "idle_pass",
                "tooltip": "M5 idle_pass",
                "budget_skip_n": 0,
            }
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
        "M5_annotation": m5_ann.get("m5_annotation"),
        "M5_tooltip": m5_ann.get("tooltip"),
        "M5_budget_skip_n": m5_ann.get("budget_skip_n"),
        "M6_gate_a": bool(ga.get("ready")),
        "M7_gate_b": m7,
        "open_risk": round(open_risk, 2),
        "tower_cap": tower_cap,
        "today": bot.get("today"),
        "passing": ready_bits,
        "all_codes": all(ready_bits.values()),
        "note": (
            "M3/M4 from desk_roi_plan; M5 annotates idle_pass vs BUDGET_starvation; "
            "M7 Gate B twin $40/n≥20"
        ),
    }


def meme_stopbleed_measure(bot: dict | None = None, *, red_lock_usd: float = 5.0) -> dict:
    """Measure memecoin stop-bleed week after ROI-rescue exits (−12% / flip −6% / red −$5).

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


def _inx_staff_clear_soft_dd(root: str | None, bot_id: str, cfg: dict | None = None) -> bool:
    """True when staff waived soft $460 DD for that INX tower (kill $400 stays stone)."""
    cfg = cfg or {}
    # Explicit desk cfg wins; else read tower config.json.
    # Sized accepts twin key staff_clear_sized_drawdown_halt OR shared staff_clear_drawdown_halt
    # (risk_manager + config.json use the shared key).
    if bot_id == "kalshi-sp" and "staff_clear_drawdown_halt" in cfg:
        return bool(cfg.get("staff_clear_drawdown_halt"))
    if bot_id == "kalshi-sized":
        if "staff_clear_sized_drawdown_halt" in cfg:
            return bool(cfg.get("staff_clear_sized_drawdown_halt"))
        if "staff_clear_drawdown_halt" in cfg:
            return bool(cfg.get("staff_clear_drawdown_halt"))
    folder = {
        "kalshi-sp": "kalshi-sp500-paper",
        "kalshi-sized": "kalshi-sized-paper",
    }.get(bot_id)
    if not folder:
        return False
    try:
        path = os.path.join(root or os.path.dirname(__file__), folder, "config.json")
        with open(path, encoding="utf-8") as handle:
            tower_cfg = json.load(handle)
        return bool(tower_cfg.get("staff_clear_drawdown_halt"))
    except Exception:
        return False


def firm_roi_rescue(
    bots: list | None = None,
    *,
    cfg: dict | None = None,
    root: str | None = None,
) -> dict:
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
        if bot_id == "memecoin" and today is not None and today <= -5:
            flags.append({
                "bot": bot_id,
                "action": "entries_off",
                "why": f"meme red-day lock (today ${today:.2f} ≤ −$5)",
            })
        if bot_id in ("kalshi-sp", "kalshi-sized") and cash is not None and cash <= 460:
            if _inx_staff_clear_soft_dd(root, bot_id, cfg):
                flags.append({
                    "bot": bot_id,
                    "action": "staff_cleared_soft_dd",
                    "why": (
                        f"Staff cleared soft DD (cash ${cash:.2f} ≤ $460); "
                        "paper buys may resume — kill $400 + fee/band/max-1/day stay stone"
                    ),
                })
            else:
                flags.append({
                    "bot": bot_id,
                    "action": "entries_off",
                    "why": f"INX drawdown halt (cash ${cash:.2f} ≤ $460)",
                })
        if bot_id == "sports-gap":
            red = None
            if today is not None and realized is not None:
                red = min(today, realized)
            elif today is not None:
                red = today
            elif realized is not None:
                red = realized
            if red is not None and red <= -10:
                flags.append({
                    "bot": bot_id,
                    "action": "accurate_only_cap1",
                    "why": f"sports red rescue (min(today,realized) ${red:.2f} ≤ −$10)",
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
    rescue = firm_roi_rescue(bots, cfg=cfg, root=root)
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
            # Prefer live bots whenever provided — same-day stale scorecard m1
            # must not lag Masters / hillclimb (#493 sports-calib twin).
            from datetime import datetime
            from zoneinfo import ZoneInfo
            today = datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d")
            if root and bots:
                weekly = desk_roi_plan.capture_weekly_scorecard(
                    root, bots=bots, cfg=cfg, label=today,
                )
            else:
                weekly = desk_roi_plan.latest_weekly_scorecard(root)
        except Exception:
            weekly = None
        try:
            if root and rows:
                desk_roi_plan.capture_graduation_week(root, rows)
            graduation = desk_roi_plan.graduation_board(root, bots=bots)
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
                # Prefer live bots whenever provided — same-day stale hillclimb
                # card must not lag Masters M1 (#488 profit_lock twin).
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
                # Prefer live bots whenever provided — same-day stale week_pnl must
                # not lag bleed_week / cold_harvest (#487 twin).
                profit_lock = desk_roi_plan.capture_profit_lock(
                    root, bots=bots, label=today,
                )
            else:
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
            "commodity_time_stop": desk_roi_plan.commodity_time_stop_shadow_summary(root),
            "sports_time_final": desk_roi_plan.sports_time_final_shadow_summary(root),
            "exit_regret": desk_roi_plan.exit_regret_observe(root, bots=bots),
            "inx_band_promote": desk_roi_plan.inx_band_promote_status(root),
            "correlation": None,
            "weekly_scorecard": weekly,
            "graduation": graduation,
            "meme_retirement": retirement,
            "hillclimb_kill": hillclimb,
            "profit_lock": profit_lock,
            "baseline": baseline,
            "living_upgrade": living,
            "m4_latency": desk_roi_plan.m4_latency_board(root),
            "adverse_selection_autopsy": desk_roi_plan.adverse_selection_autopsy(
                root, bots=bots,
            ),
            "news_gap_autopsy": desk_roi_plan.news_gap_autopsy(root, bots=bots),
            "eia_gap_autopsy": desk_roi_plan.eia_gap_autopsy(root, bots=bots),
            "weekend_inx_autopsy": desk_roi_plan.weekend_inx_autopsy(root, bots=bots),
            "distance_to_zero": desk_roi_plan.distance_to_zero_board(root, bots=bots),
            "firm_heat": desk_roi_plan.firm_heat_map(root, bots=bots),
            "fee_floors_locked": True,
        }
        try:
            import desk_more
            plan["clv_leagues"] = desk_more.clv_by_league(root)
        except Exception:
            plan["clv_leagues"] = None
        try:
            from datetime import datetime
            from zoneinfo import ZoneInfo
            today = datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d")
            # Prefer live journal whenever root is present — same-day stale
            # skip-regret card must not lag new labels (#494 weekly twin).
            if root:
                plan["skip_regret_weekly"] = desk_roi_plan.skip_regret_weekly_card(
                    root, label=today,
                )
            else:
                plan["skip_regret_weekly"] = desk_roi_plan.latest_skip_regret_weekly(root)
        except Exception:
            plan["skip_regret_weekly"] = None
        try:
            plan["skip_regret_candidates"] = desk_roi_plan.skip_regret_candidates(root)
        except Exception:
            plan["skip_regret_candidates"] = None
        try:
            plan["skip_regret_decisions"] = desk_roi_plan.skip_regret_decision_log(root)
        except Exception:
            plan["skip_regret_decisions"] = None
        try:
            from datetime import datetime
            from zoneinfo import ZoneInfo
            today = datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d")
            # Prefer live bots.today whenever provided — same-day stale
            # settle_only=[] must not hide 1.5R profit-lock (#484 twin).
            if root and bots:
                plan["daily_r"] = desk_roi_plan.capture_daily_r_board(
                    root, bots, label=today,
                )
            else:
                plan["daily_r"] = desk_roi_plan.latest_daily_r_board(root)
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
            # Prefer live bots whenever provided — same-day stale week_pnl must
            # not lag bleed_week / profit_lock (#486 twin).
            if root and bots:
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
            # Prefer live bots whenever provided — same-day stale ok=True must
            # not hide live barbell fail (#485 daily_r twin).
            if root and bots:
                plan["capital_os"] = desk_roi_plan.capture_capital_os(
                    root, bots=bots, cfg=cfg, desk_util=desk_util, label=today,
                )
            else:
                plan["capital_os"] = desk_roi_plan.latest_capital_os(root) or (
                    desk_roi_plan.capital_os_status(
                        root, bots=bots, cfg=cfg, desk_util=desk_util,
                    )
                )
        except Exception:
            plan["capital_os"] = None
        try:
            plan["opp_cost"] = desk_roi_plan.opp_cost_summary(root)
        except Exception:
            plan["opp_cost"] = None
        try:
            plan["exit_plans"] = desk_roi_plan.exit_plan_coverage(root, bots=bots)
        except Exception:
            plan["exit_plans"] = None
        try:
            from datetime import datetime
            from zoneinfo import ZoneInfo
            today = datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d")
            # Prefer live bots.today (#485 twin) — same-day stale green_usd lag.
            if root and bots:
                plan["bleed_week"] = desk_roi_plan.capture_bleed_week(
                    root, bots=bots, label=today,
                )
            else:
                plan["bleed_week"] = desk_roi_plan.latest_bleed_week(root) or (
                    desk_roi_plan.firm_bleed_ratio(bots)
                )
        except Exception:
            plan["bleed_week"] = None
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
            plan["raise_phi_decisions"] = desk_roi_plan.raise_phi_decision_log(root)
        except Exception:
            plan["raise_phi_decisions"] = None
        try:
            plan["btc_edge08_shadow"] = desk_roi_plan.btc_edge08_shadow_status(root)
        except Exception:
            plan["btc_edge08_shadow"] = None
        try:
            plan["edge08_vs_main"] = desk_roi_plan.edge08_vs_main_expectancy_board(
                root, bots=bots,
            )
        except Exception:
            plan["edge08_vs_main"] = None
        try:
            plan["insight_betting_ratio"] = desk_roi_plan.insight_betting_ratio_board(
                root, bots=bots,
            )
        except Exception:
            plan["insight_betting_ratio"] = None
        try:
            plan["weekly_eligible_fill"] = desk_roi_plan.weekly_eligible_fill_report(
                root, bots=bots,
            )
        except Exception:
            plan["weekly_eligible_fill"] = None
        try:
            plan["fee_clear_cadence"] = desk_roi_plan.fee_clear_cadence_health_board(
                root, bots=bots,
            )
        except Exception:
            plan["fee_clear_cadence"] = None
        try:
            plan["latency_stage"] = desk_roi_plan.latency_stage_board(root)
        except Exception:
            plan["latency_stage"] = None
        try:
            plan["tip_to_decision_ms"] = desk_roi_plan.tip_to_decision_ms(root)
        except Exception:
            plan["tip_to_decision_ms"] = None
        try:
            plan["exit_to_risk_freed_ms"] = desk_roi_plan.exit_to_risk_freed_ms(root)
        except Exception:
            plan["exit_to_risk_freed_ms"] = None
        try:
            plan["fill_capacity_observe"] = desk_roi_plan.fill_capacity_observe(
                root, bots=bots, cfg=cfg,
            )
        except Exception:
            plan["fill_capacity_observe"] = None
        try:
            plan["firm_tower_m1_gap"] = desk_roi_plan.firm_tower_m1_gap_alert(bots)
        except Exception:
            plan["firm_tower_m1_gap"] = None
        try:
            from datetime import datetime
            from zoneinfo import ZoneInfo
            today = datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d")
            # Prefer live bots whenever provided — same-day stale calib card must
            # not lag live BTC history (#490 commodity twin).
            if root and bots:
                plan["btc_calibration"] = desk_roi_plan.capture_btc_calibration(
                    root, bots=bots, label=today,
                )
            else:
                plan["btc_calibration"] = (
                    desk_roi_plan.latest_btc_calibration(root)
                    or desk_roi_plan.btc_calibration_report(bots)
                )
        except Exception:
            plan["btc_calibration"] = None
        try:
            from datetime import datetime
            from zoneinfo import ZoneInfo
            today = datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d")
            # Prefer live bots whenever provided — same-day stale calib card must
            # not lag live ETH history (#491 btc twin).
            if root and bots:
                plan["eth_calibration"] = desk_roi_plan.capture_eth_calibration(
                    root, bots=bots, label=today,
                )
            else:
                plan["eth_calibration"] = (
                    desk_roi_plan.latest_eth_calibration(root)
                    or desk_roi_plan.eth_calibration_report(bots)
                )
        except Exception:
            plan["eth_calibration"] = None
        try:
            from datetime import datetime
            from zoneinfo import ZoneInfo
            today = datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d")
            # Prefer live bots whenever provided — same-day stale calib card must
            # not lag live sports history (#492 eth twin).
            if root and bots:
                plan["sports_calibration"] = desk_roi_plan.capture_sports_calibration(
                    root, bots=bots, label=today,
                )
            else:
                plan["sports_calibration"] = (
                    desk_roi_plan.latest_sports_calibration(root)
                    or desk_roi_plan.sports_calibration_report(bots)
                )
        except Exception:
            plan["sports_calibration"] = None
        try:
            from datetime import datetime
            from zoneinfo import ZoneInfo
            today = datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d")
            # Prefer live bots whenever provided — same-day stale calib card must
            # not lag live commodity history (#489 hillclimb twin).
            if root and bots:
                plan["commodity_calibration"] = desk_roi_plan.capture_commodity_calibration(
                    root, bots=bots, label=today,
                )
            else:
                plan["commodity_calibration"] = (
                    desk_roi_plan.latest_commodity_calibration(root)
                    or desk_roi_plan.commodity_calibration_report(bots)
                )
        except Exception:
            plan["commodity_calibration"] = None
        try:
            # Prefer live offer book whenever bots are provided — same-day stale
            # capture must not keep cleared offers_n (#495 skip-regret twin).
            if root and bots:
                desk_roi_plan.capture_firm_queue(root, bots=bots, cfg=cfg)
            plan["firm_queue"] = desk_roi_plan.firm_queue_status(root)
        except Exception:
            plan["firm_queue"] = None
        try:
            plan["empty_card"] = desk_roi_plan.empty_card_status(root)
        except Exception:
            plan["empty_card"] = None
        try:
            plan["empty_card_series"] = desk_roi_plan.empty_card_series_board(root)
        except Exception:
            plan["empty_card_series"] = None
        try:
            plan["depth_adjusted_edge"] = desk_roi_plan.depth_adjusted_edge_board(root)
        except Exception:
            plan["depth_adjusted_edge"] = None
        try:
            plan["near_miss_promote"] = desk_roi_plan.near_miss_promote_status(root)
        except Exception:
            plan["near_miss_promote"] = None
        try:
            plan["selective_kill"] = desk_roi_plan.selective_kill_status(
                root, bots=bots,
            )
        except Exception:
            plan["selective_kill"] = None
        try:
            plan["tip_funnel"] = desk_roi_plan.tip_funnel_board(root)
        except Exception:
            plan["tip_funnel"] = None
        try:
            plan["gate_a_pilot"] = desk_roi_plan.gate_a_pilot_btc_calendar(root)
        except Exception:
            plan["gate_a_pilot"] = None
        try:
            plan["eligible_fill_funnel"] = desk_roi_plan.eligible_fill_funnel(
                root, bots=bots,
            )
        except Exception:
            plan["eligible_fill_funnel"] = None
        try:
            plan["throughput_vs_m1"] = desk_roi_plan.throughput_vs_m1_board(
                root, bots=bots,
            )
        except Exception:
            plan["throughput_vs_m1"] = None
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
    if isinstance(completions, dict) and int(completions.get("eligible_completions_today") or 0) > 0:
        priority.append(
            f"eligible completions today {completions.get('eligible_completions_today') or 0}"
        )
    feature_quiet = (living or {}).get("feature_quiet") if isinstance(living, dict) else None
    living_compact = (living or {}).get("compact") if isinstance(living, dict) else None
    quiet_age_label = None
    if isinstance(living_compact, dict) and living_compact.get("quiet_age_label"):
        quiet_age_label = str(living_compact.get("quiet_age_label"))[:80]
    if isinstance(feature_quiet, dict) and feature_quiet.get("quiet") and feature_quiet.get("alert"):
        priority.insert(0, str(feature_quiet.get("alert"))[:120])
    elif isinstance(feature_quiet, dict):
        try:
            age_h = float(feature_quiet.get("age_hours"))
        except (TypeError, ValueError):
            age_h = None
        if age_h is not None and age_h >= 6:
            # Soft rail — pager/alert already fronts when present (family-deduped).
            # Prefer compact quiet_age_label when living board supplied it.
            if quiet_age_label:
                priority.append(f"{quiet_age_label} — learn loop soft warn")
            else:
                priority.append(f"feature quiet age={age_h}h — learn loop soft warn")
        elif quiet_age_label and age_h is not None:
            # Soft observe label when age known but under the warn threshold.
            priority.append(f"{quiet_age_label} (observe)")
    sunday_pkt = (living or {}).get("sunday_packet") if isinstance(living, dict) else None
    if isinstance(sunday_pkt, dict) and sunday_pkt.get("quiet_age_label"):
        sun_label = str(sunday_pkt.get("quiet_age_label"))[:80]
        # Soft observe rail — never pages; staff Sunday cross-check only.
        if sun_label and not any(
            sun_label in str(p) or "sunday quiet" in str(p).lower() for p in priority
        ):
            priority.append(f"sunday quiet {sun_label} (observe)")
    feature_pager = (living or {}).get("feature_quiet_pager") if isinstance(living, dict) else None
    if isinstance(feature_pager, dict) and feature_pager.get("page"):
        priority.insert(0, str(feature_pager.get("label") or "feature quiet PAGE")[:120])
    hillclimb_lever = (living or {}).get("hillclimb_lever") if isinstance(living, dict) else None
    if isinstance(hillclimb_lever, dict):
        active = hillclimb_lever.get("active") if isinstance(hillclimb_lever.get("active"), dict) else None
        if active:
            priority.append(f"hillclimb lever active: {active.get('name') or active.get('lever')}")
    dual_control = (living or {}).get("dual_control") if isinstance(living, dict) else None
    if isinstance(dual_control, dict) and (
        int(dual_control.get("signed_n") or 0) > 0
        or bool(dual_control.get("arm_ready_paper"))
    ):
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
    skip_regret = (living or {}).get("skip_regret") if isinstance(living, dict) else None
    if isinstance(skip_regret, dict) and skip_regret.get("green_twin"):
        priority.append("skip-regret green_twin — staff soft gate review only")
    hard_stop = (living or {}).get("hard_stop") if isinstance(living, dict) else None
    if isinstance(hard_stop, dict) and hard_stop.get("promote_ready"):
        priority.append("sports hard-stop promote_ready — staff arm only")
    bleed = (living or {}).get("bleed") if isinstance(living, dict) else None
    if isinstance(bleed, dict) and bleed.get("pass") is False:
        priority.insert(0, str(bleed.get("label") or "bleed hot")[:120])
    clv = (living or {}).get("clv") if isinstance(living, dict) else None
    if isinstance(clv, dict) and clv.get("pass") is False:
        priority.append(str(clv.get("label") or "CLV gaps")[:120])
    tip = (living or {}).get("tip_radar") if isinstance(living, dict) else None
    if isinstance(tip, dict) and int(tip.get("t5") or 0) > 0:
        priority.append(str(tip.get("label") or "tip T-5")[:120])
    calib = (living or {}).get("calib_nag") if isinstance(living, dict) else None
    if isinstance(calib, dict) and int(calib.get("tickets_n") or 0) > 0:
        priority.insert(0, str(calib.get("label") or "raise_phi tickets")[:120])
    injury = (living or {}).get("injury_wire") if isinstance(living, dict) else None
    if isinstance(injury, dict) and (
        int(injury.get("n") or 0) > 0 or int(injury.get("inbox_n") or 0) > 0
    ):
        priority.append(str(injury.get("label") or "injury wire")[:120])
    eia = (living or {}).get("eia_scout") if isinstance(living, dict) else None
    if isinstance(eia, dict) and eia.get("next_eta_hours") is not None:
        try:
            if float(eia.get("next_eta_hours")) <= 24:
                priority.append(str(eia.get("label") or "EIA soon")[:120])
        except (TypeError, ValueError):
            pass
    distance = (living or {}).get("distance_clerk") if isinstance(living, dict) else None
    if isinstance(distance, dict) and distance.get("empty_card_pass") is False:
        priority.insert(0, str(distance.get("label") or "distance empty slow")[:120])
    quant = (living or {}).get("quant_clerk") if isinstance(living, dict) else None
    if isinstance(quant, dict) and quant.get("fit_pass") is False:
        priority.append(str(quant.get("label") or "quant fit weak")[:120])
    bee = (living or {}).get("empty_card_bee") if isinstance(living, dict) else None
    if isinstance(bee, dict) and int(bee.get("breaches") or 0) > 0:
        priority.insert(0, str(bee.get("label") or "empty CARD breaches")[:120])
    book = (living or {}).get("bookkeeper") if isinstance(living, dict) else None
    if isinstance(book, dict) and book.get("fee_ledger_complete") is False:
        priority.append(str(book.get("label") or "fee ledger gaps")[:120])
    # Clerk digest twins are pruned when ROI chip already covers the family
    # (finalize_living_priority also dedupes by family prefixes).
    twin = (living or {}).get("skip_twin_clerk") if isinstance(living, dict) else None
    if (
        isinstance(twin, dict)
        and twin.get("promote_ready")
        and not (isinstance(near_miss, dict) and near_miss.get("promote_ready"))
    ):
        priority.append("skip-twin promote_ready — staff z|p only")
    doctor_age = (living or {}).get("doctor_age") if isinstance(living, dict) else None
    ritual = (living or {}).get("ritual_observe") if isinstance(living, dict) else None
    doctor_fresh = None
    if isinstance(ritual, dict) and ritual.get("doctor_fresh") is not None:
        doctor_fresh = bool(ritual.get("doctor_fresh"))
    elif isinstance(doctor_age, dict):
        doctor_fresh = not bool(doctor_age.get("stale"))
    # Stale weekly doctor marker — front the rail (family-deduped with doctor_age).
    if doctor_fresh is False:
        priority.insert(
            0,
            (
                f"doctor_fresh=False · "
                f"{(doctor_age or {}).get('label') or 'doctor stale'} · "
                f"make living-doctor"
            )[:120],
        )
    elif isinstance(doctor_age, dict) and doctor_age.get("stale"):
        priority.append(str(doctor_age.get("label") or "doctor stale")[:120])
    if isinstance(ritual, dict) and (
        ritual.get("ritual_ok") is False or ritual.get("exit_ok") is False
    ):
        priority.append(str(ritual.get("label") or "ritual not ready")[:120])
    ritual_soft_copy = None
    doctor_soft_copy = None
    if isinstance(ritual, dict):
        ritual_soft_copy = (
            f"**Masters ritual** (paper · floors locked · live=False)\n"
            f"ritual_ok={ritual.get('ritual_ok')} exit_ok={ritual.get('exit_ok')} "
            f"doctor_fresh={ritual.get('doctor_fresh')}\n"
            f"{ritual.get('label') or 'ritual observe'}\n"
            f"_staff paste only · never auto-posts · never enables live_"
        )
        doctor_soft_copy = (
            f"**Living doctor age** (paper · floors locked · live=False)\n"
            f"doctor={'fresh' if doctor_fresh else 'stale' if doctor_fresh is False else 'n/a'} "
            f"doctor_fresh={doctor_fresh}\n"
            f"{(doctor_age or {}).get('label') or 'doctor age'}\n"
            f"ritual draft: make living-ritual-discord\n"
            f"_staff paste only · never auto-posts · never enables live_"
        )
    eia_bo = (living or {}).get("eia_blackout") if isinstance(living, dict) else None
    if isinstance(eia_bo, dict) and eia_bo.get("blocked"):
        priority.insert(0, str(eia_bo.get("label") or "EIA blackout ACTIVE")[:120])
    cal = (living or {}).get("calendar_scanner") if isinstance(living, dict) else None
    if isinstance(cal, dict) and int(cal.get("n") or 0) > 0:
        priority.append(str(cal.get("label") or "calendar events")[:120])
    pulse = (living or {}).get("clerk_pulse") if isinstance(living, dict) else None
    if isinstance(pulse, dict) and pulse.get("stale"):
        priority.insert(0, str(pulse.get("label") or "clerk pulse STALE")[:120])
    elif isinstance(pulse, dict) and pulse.get("soft_warn"):
        # Soft warn (past cadence, before 2×) — append, do not front the rail.
        priority.append(str(pulse.get("label") or "clerk pulse WARN")[:120])
    ruin_chip = (living or {}).get("ruin_drill_chip") if isinstance(living, dict) else None
    if isinstance(ruin_chip, dict) and ruin_chip.get("active"):
        priority.insert(0, str(ruin_chip.get("label") or "ruin drill ACTIVE")[:120])
    dual_gaps = (living or {}).get("dual_control_gaps") if isinstance(living, dict) else None
    if isinstance(dual_gaps, dict) and dual_gaps.get("page") and int(dual_gaps.get("gaps_n") or 0) > 0:
        priority.append(str(dual_gaps.get("label") or "dual-control gaps")[:120])
    hill_chip = (living or {}).get("hillclimb_chip") if isinstance(living, dict) else None
    if isinstance(hill_chip, dict) and hill_chip.get("active_name"):
        priority.append(str(hill_chip.get("label") or "hillclimb lever")[:120])
    digest_inv = (living or {}).get("digest_inventory") if isinstance(living, dict) else None
    if isinstance(digest_inv, dict) and digest_inv.get("pass") is False:
        priority.append(str(digest_inv.get("label") or "digest inventory thin")[:120])
    expand = (living or {}).get("betting_expand_gate") if isinstance(living, dict) else None
    if isinstance(expand, dict) and expand.get("blocked"):
        priority.insert(0, str(expand.get("label") or "betting expand BLOCKED")[:120])
    priority = finalize_living_priority(priority)
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
        "completions_chip": (
            (living or {}).get("completions_chip")
            if isinstance(living, dict)
            else None
        ),
        "teller_living": (
            (living or {}).get("teller_living")
            if isinstance(living, dict)
            else None
        ),
        "fee_floors_assert": (
            (living or {}).get("fee_floors_assert")
            if isinstance(living, dict)
            else None
        ),
        "feature_quiet": feature_quiet,
        "feature_quiet_pager": (
            (living or {}).get("feature_quiet_pager")
            if isinstance(living, dict)
            else None
        ),
        "priority_max": PRIORITY_MAX,
        "hillclimb_lever": hillclimb_lever,
        "hillclimb_chip": (
            (living or {}).get("hillclimb_chip")
            if isinstance(living, dict)
            else None
        ),
        "dual_control_gaps": (
            (living or {}).get("dual_control_gaps")
            if isinstance(living, dict)
            else None
        ),
        "digest_inventory": (
            (living or {}).get("digest_inventory")
            if isinstance(living, dict)
            else None
        ),
        "ruin_drill_page": (
            (living or {}).get("ruin_drill_page")
            if isinstance(living, dict)
            else None
        ),
        "betting_expand_gate": (
            (living or {}).get("betting_expand_gate")
            if isinstance(living, dict)
            else None
        ),
        "doctor_age": (
            (living or {}).get("doctor_age")
            if isinstance(living, dict)
            else None
        ),
        "ritual_observe": (
            (living or {}).get("ritual_observe")
            if isinstance(living, dict)
            else None
        ),
        "ritual_soft_copy": ritual_soft_copy,
        "ritual_discord": ritual_soft_copy,
        "doctor_soft_copy": doctor_soft_copy,
        "doctor_fresh": doctor_fresh,
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
        "skip_regret": (
            (living or {}).get("skip_regret")
            if isinstance(living, dict)
            else None
        ),
        "hard_stop": (
            (living or {}).get("hard_stop")
            if isinstance(living, dict)
            else None
        ),
        "bleed": (
            (living or {}).get("bleed")
            if isinstance(living, dict)
            else None
        ),
        "clv": (
            (living or {}).get("clv")
            if isinstance(living, dict)
            else None
        ),
        "tip_radar": (
            (living or {}).get("tip_radar")
            if isinstance(living, dict)
            else None
        ),
        "calib_nag": (
            (living or {}).get("calib_nag")
            if isinstance(living, dict)
            else None
        ),
        "injury_wire": (
            (living or {}).get("injury_wire")
            if isinstance(living, dict)
            else None
        ),
        "eia_scout": (
            (living or {}).get("eia_scout")
            if isinstance(living, dict)
            else None
        ),
        "line_shopper": (
            (living or {}).get("line_shopper")
            if isinstance(living, dict)
            else None
        ),
        "btc_basis_scout": (
            (living or {}).get("btc_basis_scout")
            if isinstance(living, dict)
            else None
        ),
        "nhl_poisson_audit": (
            (living or {}).get("nhl_poisson_audit")
            if isinstance(living, dict)
            else None
        ),
        "dvol_regime": (
            (living or {}).get("dvol_regime")
            if isinstance(living, dict)
            else None
        ),
        "multi_ex_disagree": (
            (living or {}).get("multi_ex_disagree")
            if isinstance(living, dict)
            else None
        ),
        "funding_scout": (
            (living or {}).get("funding_scout")
            if isinstance(living, dict)
            else None
        ),
        "metals_heat": (
            (living or {}).get("metals_heat")
            if isinstance(living, dict)
            else None
        ),
        "energy_heat": (
            (living or {}).get("energy_heat")
            if isinstance(living, dict)
            else None
        ),
        "inx_band_occupancy": (
            (living or {}).get("inx_band_occupancy")
            if isinstance(living, dict)
            else None
        ),
        "skip_historian": (
            (living or {}).get("skip_historian")
            if isinstance(living, dict)
            else None
        ),
        "distance_clerk": (
            (living or {}).get("distance_clerk")
            if isinstance(living, dict)
            else None
        ),
        "quant_clerk": (
            (living or {}).get("quant_clerk")
            if isinstance(living, dict)
            else None
        ),
        "bookkeeper": (
            (living or {}).get("bookkeeper")
            if isinstance(living, dict)
            else None
        ),
        "reporter": (
            (living or {}).get("reporter")
            if isinstance(living, dict)
            else None
        ),
        "empty_card_bee": (
            (living or {}).get("empty_card_bee")
            if isinstance(living, dict)
            else None
        ),
        "near_miss_clerk": (
            (living or {}).get("near_miss_clerk")
            if isinstance(living, dict)
            else None
        ),
        "hard_stop_clerk": (
            (living or {}).get("hard_stop_clerk")
            if isinstance(living, dict)
            else None
        ),
        "bleed_clerk": (
            (living or {}).get("bleed_clerk")
            if isinstance(living, dict)
            else None
        ),
        "skip_twin_clerk": (
            (living or {}).get("skip_twin_clerk")
            if isinstance(living, dict)
            else None
        ),
        "clv_closer": (
            (living or {}).get("clv_closer")
            if isinstance(living, dict)
            else None
        ),
        "timer_digest": (
            (living or {}).get("timer_digest")
            if isinstance(living, dict)
            else None
        ),
        "calendar_scanner": (
            (living or {}).get("calendar_scanner")
            if isinstance(living, dict)
            else None
        ),
        "eia_blackout": (
            (living or {}).get("eia_blackout")
            if isinstance(living, dict)
            else None
        ),
        "compact": (
            (living or {}).get("compact")
            if isinstance(living, dict)
            else None
        ),
        "clerk_pulse": (
            (living or {}).get("clerk_pulse")
            if isinstance(living, dict)
            else None
        ),
        "dual_control_chip": (
            (living or {}).get("dual_control_chip")
            if isinstance(living, dict)
            else None
        ),
        "ruin_drill_chip": (
            (living or {}).get("ruin_drill_chip")
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
