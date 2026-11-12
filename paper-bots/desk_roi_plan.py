"""
desk_roi_plan.py — Positive-ROI plan instrumentation (paper only).

Un-stubs Masters M3 (fit→buy) and M4 (latency), firm bleed / capital-misplaced
metrics, W0 baseline capture, near-miss weekly card, and INX band research harness.

Never softens venue min_edge floors. No profit guarantee.
"""
from __future__ import annotations

import json
import math
import os
import time
from typing import Any

FIT_JOURNAL = "desk_fit_journal.json"
LATENCY_JOURNAL = "desk_latency_journal.json"
BASELINE_NAME = "desk_roi_baseline.json"
NEAR_MISS_WEEKLY = "desk_near_miss_weekly.json"
INX_BAND_RESEARCH = "desk_inx_band_research.json"
INX_BAND_PROMOTE = "desk_inx_band_promote.json"
SPORTS_HARD_STOP_SHADOW = "desk_sports_hard_stop_shadow.json"
SPORTS_HARD_STOP_PROMOTE = "desk_sports_hard_stop_promote.json"
SPORTS_GREEN_BOOST_PROMOTE = "desk_sports_green_boost_promote.json"
COMMODITY_TIME_STOP_SHADOW = "desk_commodity_time_stop_shadow.json"
COMMODITY_TIME_STOP_PROMOTE = "desk_commodity_time_stop_promote.json"
SPORTS_TIME_FINAL_SHADOW = "desk_sports_time_final_shadow.json"
SPORTS_TIME_FINAL_PROMOTE = "desk_sports_time_final_promote.json"
ADVERSE_COOL_NAME = "desk_adverse_cool.json"
WEEKLY_SCORECARD = "desk_weekly_scorecard.json"
MASTER_GRAD = "desk_master_grad.json"
HILLCLIMB_KILL = "desk_hillclimb_kill.json"
PROFIT_LOCK = "desk_profit_lock.json"
SKIP_REGRET_WEEKLY = "desk_skip_regret_weekly.json"
SKIP_REGRET_DECISIONS = "desk_skip_regret_decisions.json"
DAILY_R_NAME = "desk_daily_r.json"
ANTI_REVENGE_NAME = "desk_anti_revenge.json"
INCUBATION_NAME = "desk_incubation.json"
RUIN_DRILL_NAME = "desk_ruin_drill.json"
FEE_LEDGER_NAME = "desk_fee_ledger.json"
HELPER_FILLS_NAME = "desk_helper_fills.json"
HELPER_PROMOTE_NAME = "desk_helper_promote.json"
COLD_HARVEST_NAME = "desk_cold_harvest.json"
HILLCLIMB_LEVER_NAME = "desk_hillclimb_lever.json"
DUAL_CONTROL_NAME = "desk_dual_control.json"
CAPITAL_OS_NAME = "desk_capital_os.json"
OPP_COST_NAME = "desk_opp_cost.json"
IDEA_REVIEW_NAME = "desk_idea_review.json"
BTC_CALIB_NAME = "desk_btc_calibration.json"
ETH_CALIB_NAME = "desk_eth_calibration.json"
SPORTS_CALIB_NAME = "desk_sports_calibration.json"
COMMODITY_CALIB_NAME = "desk_commodity_calibration.json"
RAISE_PHI_DECISIONS = "desk_raise_phi_decisions.json"
FIRM_QUEUE_NAME = "desk_firm_queue.json"
EMPTY_CARD_NAME = "desk_empty_card.json"
BLEED_WEEK_NAME = "desk_bleed_week.json"
NEAR_MISS_PROMOTE_NAME = "desk_near_miss_promote.json"

# E3–E4 boards live in desk_roi_e4 (re-exported for desk_roi_plan.* API).
from desk_roi_e4 import (  # noqa: F401
    INCUBATION_IDEA_BANK_ONLY,
    INCUBATION_IDEA_BANK_PREFIXES,
    LOCKED_VENUE_FLOORS,
    SELECTIVE_KILL_GREEN_DAYS,
    TIP_FUNNEL_LEAGUES,
    TIP_FUNNEL_STAGES,
    eligible_fill_funnel,
    gate_a_pilot_btc_calendar,
    gate_a_pilot_sports_clv,
    gate_a_pilots_board,
    helper_advice_lift_board,
    helper_advice_log_board,
    incubation_blocks_auto,
    incubation_idea_bank_only,
    insight_helpers_execution_lock,
    note_selective_green_day,
    record_helper_advice_decision,
    record_selective_attempt,
    record_tip_funnel,
    selective_kill_active,
    selective_kill_status,
    tip_funnel_board,
    throughput_vs_m1_board,
)

# E5–E7 densify boards (new module — does not rewrite #354/#355/#356 surfaces).
from desk_roi_e5e7 import (  # noqa: F401
    edge08_vs_main_expectancy_board,
    fee_clear_cadence_health_board,
    insight_betting_ratio_board,
    near_miss_edge_relax_forever_zero,
    selective_never_expands_meme_inx,
    skip_regret_never_edge_floor,
    weekly_eligible_fill_report,
)

# Post #354–#357 money-path boards (latency stage / speed KPIs / M1 gap).
from desk_roi_post_e3e7 import (  # noqa: F401
    distance_to_zero_stance,
    exit_to_risk_freed_ms,
    fee_floors_locked_check,
    fill_capacity_observe,
    firm_tower_m1_gap_alert,
    latency_stage_board,
    m5_idle_vs_budget_annotation,
    tip_to_decision_ms,
)

# Staff SLA unblock pack — lazy re-export (avoids circular import with desk_roi_staff).
_STAFF_SLA_EXPORTS = frozenset({
    "dual_control_observe_board",
    "export_edge08_shadow_csv",
    "export_green_boost_evidence",
    "export_near_miss_shadow_csv",
    "hillclimb_lever_journal",
    "hillclimb_pick_evidence_pack",
    "observation_week_clock",
    "promote_gate_sla",
    "staff_batch_arm_promotes_ready",
    "staff_dashboard",
    "staff_disarm_thin_promotes",
    "staff_hillclimb_pick_journal",
    "staff_log_hillclimb_pick",
    "staff_promote_ready_pack",
})


def __getattr__(name: str):
    if name in _STAFF_SLA_EXPORTS:
        import desk_roi_staff as _staff

        return getattr(_staff, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


MAX_FIT_ROWS = 4000
MAX_LAT_ROWS = 4000
MAX_HARD_STOP_ROWS = 2000

# Adverse selection cool-off: fast mark-down after entry → pause that bot briefly.
ADVERSE_MARK_DROP = 0.05  # 5¢ adverse vs entry ask/bid
ADVERSE_COOL_MINUTES = 20

# Phase 6: Master only after 2 consecutive Chicago weeks of all M-codes.
GRADUATION_WEEKS_REQUIRED = 2
GRADUATION_CODES = ("M1", "M2", "M3", "M4", "M5", "M6", "M7")
GRADUATION_DENIAL_CODES = (
    "M1_fail",
    "M2_fail",
    "M3_fail",
    "M4_fail",
    "M5_fail",
    "M6_fail",
    "M7_fail",
    "thin_n",
    "fee_ledger",
    "cli_bypass",
    "news_fail_open",
)

# Phase 7: meme sleeve retirement clock (recommend pause; staff re-arms).
MEME_RETIRE_WINDOW_DAYS = 20
MEME_RETIRE_MIN_N = 10

# Phase 11: hillclimb kill — M3↑ with M1↓ for 2 Chicago weeks → revert lever.
HILLCLIMB_KILL_WEEKS = 2
# Phase 11: one lever per Chicago week from allowlist (raise-only on fee floors).
# E9 #903–922: evidence template fields (success / kill / dry-run) on each lever.
_HILLCLIMB_SUCCESS = "M1 non-worse vs prior Chicago week; optional eligible fills up"
_HILLCLIMB_KILL = "M3↑ with M1↓ over 2 Chicago weeks → revert lever"
_HILLCLIMB_DRY = {
    "mode": "shadow_paper",
    "writes_venue_params": False,
    "applies_live": False,
    "live_orders_enabled": False,
    "fee_floors_locked": True,
}

HILLCLIMB_ALLOWLIST = {
    "VOL_SAFE": {
        "kind": "adapt_threshold",
        "raise_only": False,
        "note": "desk_adapt VOL_SAFE play-safe threshold experiment",
        "success_metrics": _HILLCLIMB_SUCCESS,
        "kill_metrics": _HILLCLIMB_KILL,
        "dry_run": {
            **_HILLCLIMB_DRY,
            "target": "desk_adapt.VOL_SAFE",
            "proposed": {"play_safe": True, "observe_only": True},
        },
    },
    "HIT_FOR_BIG": {
        "kind": "adapt_threshold",
        "raise_only": False,
        "note": "desk_adapt HIT_FOR_BIG proven-80 threshold experiment",
        "success_metrics": _HILLCLIMB_SUCCESS,
        "kill_metrics": _HILLCLIMB_KILL,
        "dry_run": {
            **_HILLCLIMB_DRY,
            "target": "desk_adapt.HIT_FOR_BIG",
            "proposed": {"proven_80": True, "observe_only": True},
        },
    },
    "venue_min_edge_btc": {
        "kind": "venue_floor",
        "raise_only": True,
        "venue": "kalshi_btc15m",
        "note": "BTC venue min_edge — raise only, never soften floor",
        "success_metrics": _HILLCLIMB_SUCCESS,
        "kill_metrics": _HILLCLIMB_KILL,
        "dry_run": {
            **_HILLCLIMB_DRY,
            "target": "venue_min_edge.kalshi_btc15m",
            "proposed": {"min_edge": 0.06, "floor_locked": 0.05, "raise_only": True},
        },
    },
    "min_cushion_btc": {
        "kind": "btc_gate",
        "raise_only": True,
        "note": "BTC min cushion — raise only",
        "success_metrics": _HILLCLIMB_SUCCESS,
        "kill_metrics": _HILLCLIMB_KILL,
        "dry_run": {
            **_HILLCLIMB_DRY,
            "target": "btc.min_cushion",
            "proposed": {"min_cushion": "raise_only", "observe_only": True},
        },
    },
    "kelly_fraction": {
        "kind": "sizing",
        "raise_only": False,
        "note": "Kelly fraction within desk bounds (0.05–1.0)",
        "success_metrics": _HILLCLIMB_SUCCESS,
        "kill_metrics": _HILLCLIMB_KILL,
        "dry_run": {
            **_HILLCLIMB_DRY,
            "target": "sizing.kelly_fraction",
            "proposed": {"kelly_fraction": 0.25, "bounds": [0.05, 1.0]},
        },
    },
}

HILLCLIMB_NONE_LEVER = "NONE"
HILLCLIMB_RITUAL_NAME = "desk_hillclimb_ritual.json"
HILLCLIMB_POSTMORTEM_NAME = "desk_hillclimb_postmortem.json"
HILLCLIMB_WIN_LOCK_NAME = "desk_hillclimb_win_lock.json"
MAX_HILLCLIMB_POSTMORTEM = 200
MAX_HILLCLIMB_WIN_LOCK = 200

# Phase 10: profit-lock harvest paper analog — hit weekly target → 0.5× size.
PROFIT_LOCK_TARGET_USD = 40.0
PROFIT_LOCK_SIZE_MULT = 0.5

# Phase 7: daily R budget — hit +budget → settle-only for that tower (exits still on).
DAILY_R_USD = 20.0  # 1R paper unit
DAILY_R_BUDGET = {
    "sports-gap": 1.5,
    "btc15m": 2.0,
    "commodity-15m": 2.0,
    "kalshi-sp": 1.0,
    "kalshi-sized": 1.0,
    "memecoin": 0.5,
}

# Phase 10: anti-revenge — same market blocked T minutes after stop/flip.
ANTI_REVENGE_MINUTES = 30

# Phase 7: incubation — new series paper-only until N fee-aware settles.
INCUBATION_MIN_N = 50
# Series already graduated / main tape (not incubated by default).
INCUBATION_MAIN_SERIES = frozenset({
    "KXBTC15M", "KXETH15M",
    "KXGOLD15M", "KXSILVER15M", "KXPLATINUM15M", "KXPALLADIUM15M", "KXCOPPER15M",
    "KXNATGAS15M", "KXBRENT15M", "KXWTI15M",
    "KXINXU",
})

# Phase 10: ruin drill levels (paper UX — exits/settles still run unless nuclear pause).
RUIN_LEVELS = ("soft", "hard", "nuclear")

# Phase 10: tax/fee ledger — 1¢ fill tax + venue fee for true ROI honesty.
FILL_TAX_DEFAULT = 0.01
MAX_FEE_LEDGER_ROWS = 4000

# Phase 10: clock-skew / stale-world — skip new entries when last loop or quote is old.
# Bars are ~2× Masters M4 latency bars (sports 45s → 90s; 15m 20s → 40s).
STALE_LOOP_SEC = {
    "sports-gap": 90.0,
    "btc15m": 40.0,
    "commodity-15m": 40.0,
    "kalshi-sp": 40.0,
    "kalshi-sized": 40.0,
}
STALE_LOOP_DEFAULT = 40.0
CLOCK_SKEW_MAX_SEC = 30.0  # matches pimp_desk.STALE_PRICE_SEC

# Phase 8: helper Gate A — helper-attributed taxed EV ≥ 0 before any autonomy story.
HELPER_GATE_A_MIN_N = 20
MAX_HELPER_FILL_ROWS = 4000

# Phase 10: weekly harvest → cold ledger (habit for live; 30–50% of green week PnL).
COLD_HARVEST_PCT_DEFAULT = 0.40
COLD_HARVEST_PCT_MIN = 0.30
COLD_HARVEST_PCT_MAX = 0.50

# Cross-tower firm rank queue — fee-clear sports+btc+commodity only.
# Soft gate: deferred tickets skip new entries so desk risk buys best score.
FIRM_QUEUE_BOTS = frozenset({"sports-gap", "btc15m", "commodity-15m"})
FIRM_QUEUE_TTL_SEC = 180.0
FIRM_QUEUE_DEFAULT_STAKE = 25.0
MAX_FIRM_OFFERS = 200

# Empty-market CARD bar — fee-clear towers should exit idle loops fast.
EMPTY_CARD_BAR_SEC = 3.0
MAX_EMPTY_CARD_ROWS = 500
# 15m series observe boards (plan 422–441): empty rate + median time-to-book.
EMPTY_CARD_SERIES_15M = (
    "KXBTC15M",
    "KXETH15M",
    "KXGOLD15M",
    "KXSILVER15M",
    "KXPLATINUM15M",
    "KXPALLADIUM15M",
    "KXCOPPER15M",
    "KXWTI15M",
    "KXBRENT15M",
    "KXNATGAS15M",
)
_BOT_DEFAULT_SERIES = {
    "btc15m": ("KXBTC15M", "KXETH15M"),
    "commodity-15m": (
        "KXGOLD15M",
        "KXSILVER15M",
        "KXPLATINUM15M",
        "KXPALLADIUM15M",
        "KXCOPPER15M",
        "KXWTI15M",
        "KXBRENT15M",
        "KXNATGAS15M",
    ),
}

# Phase 5: near-miss soft-gate promote (never fee / edge floors).
NEAR_MISS_PROMOTE_N = 30
NEAR_MISS_PROMOTE_MIN_EV = 0.0
NEAR_MISS_SOFT_ALLOW = frozenset({"z", "p"})  # edge forever forbidden
NEAR_MISS_Z_RELAX = 0.05
NEAR_MISS_P_RELAX = 0.02
NEAR_MISS_LIVE = False  # code default — staff file only

# Phase 2: capital allocation OS — barbell + midday util / zero-buy alerts.
BARBELL_MEME_MAX = 0.15          # ≤15% desk risk to meme sleeve
BARBELL_FEE_CLEAR_MIN = 0.70     # ≥70% of open risk in fee-clear towers
MIDDAY_UTIL_ALERT_LT = 0.20      # util below this + EDGE-only skips → starvation alert
ZERO_BUY_ALERT_HOURS = 6.0       # weekday fee-clear quiet with BUDGET skips

# Phase 5: opportunity-cost clock — low-edge blocks high-edge >90s.
OPP_COST_WAIT_SEC = 90.0
MAX_OPP_COST_ROWS = 2000

# Phase 11: idea review cadence — kill stale experiments after 90 Chicago days.
IDEA_REVIEW_DAYS = 90
MAX_IDEA_ROWS = 200

# Phase 4: BTC calibration — labeled high-p buckets must roughly hit.
BTC_CALIB_MIN_N = 20
BTC_CALIB_HI_LABEL = 0.80
BTC_CALIB_HI_HIT_FLOOR = 0.70  # if labeled ≥80% but hits <70% → raise Φ
BTC_CALIB_BUCKETS = (
    (0.50, 0.60),
    (0.60, 0.70),
    (0.70, 0.80),
    (0.80, 0.90),
    (0.90, 1.01),
)

# Sports calibration — fair_at_entry buckets vs hit (parallel to BTC; observe-only).
SPORTS_CALIB_MIN_N = 20
SPORTS_CALIB_HI_LABEL = 0.80
SPORTS_CALIB_HI_HIT_FLOOR = 0.70
SPORTS_CALIB_BUCKETS = BTC_CALIB_BUCKETS

# Commodity calibration — fair/prob buckets vs hit (NatGas/WTI/etc.; observe-only).
COMMODITY_CALIB_MIN_N = 20
COMMODITY_CALIB_HI_LABEL = 0.80
COMMODITY_CALIB_HI_HIT_FLOOR = 0.70
COMMODITY_CALIB_BUCKETS = BTC_CALIB_BUCKETS

# Phase 9: dual-control live checklist — paper stub; never enables live orders.
LIVE_ORDERS_ENABLED = False  # hard lock — stub cannot arm create-order
DUAL_CONTROL_ITEMS = (
    ("gate_a_pilot", "Paper Gate A ready on pilot tower"),
    ("gate_b_pilot", "Gate B twin green on pilot (DD/n)"),
    ("fee_parity", "Live fee table matches paper (+ fill tax)"),
    ("read_only_first", "Read-only armed mode before create-order"),
    ("daily_stop", "Daily live stop ≤ paper stop"),
    ("kill_floor", "Live kill ≤ sleeve floor; cancel-on-pause"),
    ("no_meme_fund", "No funding live from meme sleeve"),
    ("disaster_drill", "Ruin drill soft/hard practiced this month"),
)

FEE_CLEAR = ("sports-gap", "btc15m", "commodity-15m")
LOSER_IDS = ("memecoin", "kalshi-sp", "kalshi-sized")

# Sports hard-stop shadow: bid ≤ entry − drop triggers a would-have-stopped log.
# Live sell stays OFF until n≥30 and shadow EV ≥ settle baseline (staff promote).
SPORTS_HARD_STOP_DROP = 0.12
SPORTS_HARD_STOP_LIVE = False  # never auto-sell until staff promote
SPORTS_HARD_STOP_PROMOTE_N = 30

# Phase 3: commodity optional time-stop before settle (shadow first).
COMMODITY_TIME_STOP_MIN_LEFT = 3.0  # minutes before window close
COMMODITY_TIME_STOP_LIVE = False  # never auto-sell until staff promote
COMMODITY_TIME_STOP_PROMOTE_N = 30
MAX_COMMODITY_TSTOP_ROWS = 2000

# Phase 3 P1: sports time-to-final trim (shadow first).
# Hit when ≤N regulation minutes remain and mark PnL ≤ 0.
SPORTS_TIME_FINAL_MIN_LEFT = 5.0
SPORTS_TIME_FINAL_LIVE = False  # never auto-sell until staff promote
SPORTS_TIME_FINAL_PROMOTE_N = 30
MAX_SPORTS_TFINAL_ROWS = 2000
# Regulation period length (minutes) + count by league for ESPN clock.
SPORTS_PERIOD_MIN = {
    "NFL": 15.0,
    "NCAAF": 15.0,
    "NBA": 12.0,
    "WNBA": 12.0,
    "NCAAB": 20.0,
    "NHL": 20.0,
    "MLB": 20.0,  # coarse per-inning proxy
}
SPORTS_REG_PERIODS = {
    "NFL": 4,
    "NCAAF": 4,
    "NBA": 4,
    "WNBA": 4,
    "NCAAB": 2,
    "NHL": 3,
    "MLB": 9,
}

# Phase 5: sports green_boost only after 2 Chicago weeks M1≥0 + CLV bar.
SPORTS_GREEN_BOOST_WEEKS = 2
SPORTS_CLV_BAR = 0.52
SPORTS_CLV_MIN_N = 20
SPORTS_M1_MIN_N = 20

# Fee-aware INX research bands only — does NOT change live 80–90¢ config.
INX_RESEARCH_BANDS = (
    {"id": "70_80", "lo": 0.70, "hi": 0.80},
    {"id": "80_90", "lo": 0.80, "hi": 0.90},  # live default (locked until research wins)
    {"id": "90_95", "lo": 0.90, "hi": 0.95},
)
INX_LIVE_BAND_DEFAULT = "80_90"
INX_BAND_PROMOTE_MIN_N = 20


def _root(root: str | None = None) -> str:
    return root or os.path.dirname(os.path.abspath(__file__))


def _path(name: str, root: str | None = None) -> str:
    return os.path.join(_root(root), name)


def _finite(x) -> float | None:
    try:
        n = float(x)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(n):
        return None
    return n


def _load(path: str, empty: dict) -> dict:
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        pass
    return dict(empty)


def _save(path: str, state: dict) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ---- M3 fit→buy journal ----------------------------------------------------

def _empty_fit() -> dict:
    return {"paper_only": True, "version": 1, "rows": [], "by_bot": {}}


def load_fit(root: str | None = None) -> dict:
    return _load(_path(FIT_JOURNAL, root), _empty_fit())


def save_fit(state: dict, root: str | None = None) -> None:
    _save(_path(FIT_JOURNAL, root), state)


def record_fit(
    root: str | None,
    *,
    bot: str,
    outcome: str,
    ticker: str = "",
    side: str = "",
    edge=None,
    note: str = "",
) -> dict:
    """
    outcome: fit (gates cleared) | buy (paper fill) | block (fit but desk blocked).
    M3 = buys / (buys + blocks) among fits; also tracks fit→buy including pure fits.
    """
    outcome = str(outcome or "").lower().strip()
    if outcome not in ("fit", "buy", "block"):
        raise ValueError(f"bad fit outcome {outcome}")
    state = load_fit(root)
    row = {
        "at": _now(),
        "bot": bot,
        "outcome": outcome,
        "ticker": ticker,
        "side": side,
        "edge": None if edge is None else round(float(edge), 4),
        "note": str(note or "")[:200],
    }
    rows = list(state.get("rows") or [])
    rows.append(row)
    state["rows"] = rows[-MAX_FIT_ROWS:]
    bot_row = state.setdefault("by_bot", {}).setdefault(
        bot, {"fits": 0, "buys": 0, "blocks": 0},
    )
    if outcome == "fit":
        bot_row["fits"] = int(bot_row.get("fits") or 0) + 1
    elif outcome == "buy":
        bot_row["buys"] = int(bot_row.get("buys") or 0) + 1
        bot_row["fits"] = int(bot_row.get("fits") or 0) + 1
    else:
        bot_row["blocks"] = int(bot_row.get("blocks") or 0) + 1
        bot_row["fits"] = int(bot_row.get("fits") or 0) + 1
    state["last_at"] = row["at"]
    save_fit(state, root)
    return row


def fit_buy_rate(root: str | None = None, bot: str | None = None) -> dict:
    """Fit→buy conversion for one bot or firm-wide."""
    state = load_fit(root)
    if bot:
        rows = [r for r in (state.get("rows") or []) if isinstance(r, dict) and r.get("bot") == bot]
    else:
        rows = [r for r in (state.get("rows") or []) if isinstance(r, dict)]
    fits = [r for r in rows if r.get("outcome") in ("fit", "buy", "block")]
    buys = [r for r in rows if r.get("outcome") == "buy"]
    n_fit = len(fits)
    n_buy = len(buys)
    rate = round(n_buy / n_fit, 4) if n_fit else None
    return {
        "paper_only": True,
        "bot": bot,
        "n_fit": n_fit,
        "n_buy": n_buy,
        "rate": rate,
        "bar": 0.40,
        "pass": rate is not None and n_fit >= 10 and rate >= 0.40,
    }


# ---- M4 latency journal ----------------------------------------------------

def _empty_lat() -> dict:
    return {"paper_only": True, "version": 1, "rows": [], "by_bot": {}}


def load_latency(root: str | None = None) -> dict:
    return _load(_path(LATENCY_JOURNAL, root), _empty_lat())


def save_latency(state: dict, root: str | None = None) -> None:
    _save(_path(LATENCY_JOURNAL, root), state)


def record_latency(
    root: str | None,
    *,
    bot: str,
    seconds: float,
    note: str = "",
    stage: str | None = None,
) -> dict:
    sec = _finite(seconds)
    if sec is None or sec < 0:
        return {}
    state = load_latency(root)
    row = {
        "at": _now(),
        "bot": bot,
        "seconds": round(sec, 3),
        "note": str(note or "")[:120],
    }
    stage_s = str(stage or "").strip()[:40]
    if stage_s:
        row["stage"] = stage_s
    rows = list(state.get("rows") or [])
    rows.append(row)
    state["rows"] = rows[-MAX_LAT_ROWS:]
    bot_row = state.setdefault("by_bot", {}).setdefault(bot, {"n": 0, "sum": 0.0})
    bot_row["n"] = int(bot_row.get("n") or 0) + 1
    bot_row["sum"] = float(bot_row.get("sum") or 0) + float(sec)
    state["last_at"] = row["at"]
    save_latency(state, root)
    return row


def _latency_percentile(vals: list[float], p: float) -> float | None:
    """Inclusive percentile on a sorted list. p in [0, 1]."""
    if not vals:
        return None
    if len(vals) == 1:
        return float(vals[0])
    idx = int(round((len(vals) - 1) * max(0.0, min(1.0, float(p)))))
    return float(vals[idx])


def latency_p50(root: str | None = None, bot: str | None = None) -> dict:
    state = load_latency(root)
    if bot:
        vals = [
            float(r["seconds"])
            for r in (state.get("rows") or [])
            if isinstance(r, dict) and r.get("bot") == bot and _finite(r.get("seconds")) is not None
        ]
    else:
        vals = [
            float(r["seconds"])
            for r in (state.get("rows") or [])
            if isinstance(r, dict) and _finite(r.get("seconds")) is not None
        ]
    vals.sort()
    n = len(vals)
    p50 = _latency_percentile(vals, 0.50)
    p95 = _latency_percentile(vals, 0.95)
    # Sports bar 45s; 15m towers 20s — caller passes bot for bar pick.
    bar = 45.0 if bot == "sports-gap" else 20.0
    return {
        "paper_only": True,
        "bot": bot,
        "n": n,
        "p50_s": round(p50, 3) if p50 is not None else None,
        "p95_s": round(p95, 3) if p95 is not None else None,
        "bar_s": bar,
        "pass": p50 is not None and n >= 5 and p50 <= bar,
    }


def m4_latency_board(root: str | None = None) -> dict:
    """M4 board: sports ≤45s / 15m ≤20s with p50+p95 and Chicago-day breach alert."""
    towers = [
        ("sports-gap", 45.0),
        ("btc15m", 20.0),
        ("commodity-15m", 20.0),
    ]
    day = _chicago_day()
    state = load_latency(root)
    rows = [r for r in (state.get("rows") or []) if isinstance(r, dict)]
    by_bot: dict[str, dict] = {}
    breaches = []
    for bot, bar in towers:
        bot_rows = [r for r in rows if str(r.get("bot") or "") == bot]
        day_rows = [
            r for r in bot_rows
            if _stamp_chicago_day(r.get("at")) == day
        ]
        sample = day_rows if day_rows else bot_rows
        vals = sorted(
            float(r["seconds"])
            for r in sample
            if _finite(r.get("seconds")) is not None
        )
        n = len(vals)
        p50 = _latency_percentile(vals, 0.50)
        p95 = _latency_percentile(vals, 0.95)
        stages: dict[str, int] = {}
        for r in bot_rows:
            st = str(r.get("stage") or "").strip()
            if st:
                stages[st] = int(stages.get(st) or 0) + 1
        ok = p50 is not None and n >= 5 and p50 <= bar
        day_breach = bool(
            day_rows
            and any((_finite(r.get("seconds")) or 0) > bar for r in day_rows)
        )
        if day_breach or (n >= 5 and p50 is not None and p50 > bar):
            breaches.append(bot)
        by_bot[bot] = {
            "bot": bot,
            "n": n,
            "day_n": len(day_rows),
            "p50_s": round(p50, 3) if p50 is not None else None,
            "p95_s": round(p95, 3) if p95 is not None else None,
            "bar_s": bar,
            "pass": ok,
            "day_breach": day_breach,
            "stages": stages,
        }
    alert = bool(breaches)
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "chicago_day": day,
        "towers": by_bot,
        "breaches": breaches,
        "alert": alert,
        "ok": not alert,
        "label": (
            f"m4_latency={'ALERT' if alert else 'ok'} "
            f"breaches={','.join(breaches) or 'none'} day={day}"
        ),
        "note": (
            "M4 latency board — sports p50≤45s, BTC/commodity p50≤20s; "
            "p95 surfaced; Chicago-day breach alert. Floors locked."
        ),
    }



# ---- Firm bleed + capital misplaced ----------------------------------------

def firm_bleed_ratio(bots: list | None = None) -> dict:
    """
    |sum red today| / |sum green today|.
    Want < 0.5 after stop-bleed week. Paper only.
    """
    red = 0.0
    green = 0.0
    by = []
    for bot in bots or []:
        if not isinstance(bot, dict):
            continue
        today = _finite(bot.get("today"))
        if today is None:
            continue
        bot_id = str(bot.get("id") or "")
        by.append({"bot": bot_id, "today": round(today, 2)})
        if today < 0:
            red += abs(today)
        elif today > 0:
            green += today
    ratio = round(red / green, 4) if green > 1e-9 else (None if red <= 0 else 999.0)
    return {
        "paper_only": True,
        "red_usd": round(red, 2),
        "green_usd": round(green, 2),
        "ratio": ratio,
        "target_lt": 0.5,
        "pass": ratio is not None and ratio < 0.5,
        "by_tower": by,
        "note": "Bleed ratio uses Chicago today PnL. Quiet $0 towers ignored.",
    }




def capture_bleed_week(
    root: str | None,
    bots: list | None = None,
    *,
    label: str | None = None,
) -> dict:
    """Persist Chicago-day firm bleed card (target ratio < 0.5). Observe only."""
    day = label or _chicago_day()
    bleed = firm_bleed_ratio(bots)
    misplaced = capital_misplaced(bots)
    board = {
        "paper_only": True,
        "fee_floors_locked": True,
        "board_chip": False,
        "label": day,
        "captured_at": _now(),
        "red_usd": bleed.get("red_usd"),
        "green_usd": bleed.get("green_usd"),
        "ratio": bleed.get("ratio"),
        "target_lt": bleed.get("target_lt"),
        "pass": bleed.get("pass"),
        "by_tower": bleed.get("by_tower"),
        "misplaced_usd": misplaced.get("misplaced_usd"),
        "misplaced_share": misplaced.get("share_of_cap"),
        "label_line": (
            f"bleed week={day} ratio={bleed.get('ratio')} "
            f"pass={bleed.get('pass')} misplaced=${misplaced.get('misplaced_usd')} "
            "(observe · target <0.5 · never softens floors)"
        ),
        "note": (
            "Chicago bleed observe — want |red|/|green| < 0.5. "
            "Recycle misplaced open risk toward fee-clear; never soften floors."
        ),
    }
    path = _path(BLEED_WEEK_NAME, root)
    store = _load(path, {"paper_only": True, "cards": [], "latest": None})
    cards = [c for c in (store.get("cards") or []) if isinstance(c, dict)]
    cards = [c for c in cards if str(c.get("label") or "") != day]
    cards.append(board)
    store["cards"] = cards[-60:]
    store["latest"] = board
    store["paper_only"] = True
    _save(path, store)
    return board


def latest_bleed_week(root: str | None = None) -> dict | None:
    store = _load(_path(BLEED_WEEK_NAME, root), {"paper_only": True, "latest": None})
    latest = store.get("latest")
    return latest if isinstance(latest, dict) else None

def capital_misplaced(bots: list | None = None, cfg: dict | None = None) -> dict:
    """
    Open risk sitting on towers that are red today or Gate A false — dollars that
    should be recycled toward fee-clear green books.
    """
    cfg = cfg or {}
    desk_cap = _finite(cfg.get("max_open_risk")) or 100.0
    misplaced = 0.0
    rows = []
    for bot in bots or []:
        if not isinstance(bot, dict):
            continue
        bot_id = str(bot.get("id") or "")
        open_risk = _finite(bot.get("open_risk")) or 0.0
        today = _finite(bot.get("today"))
        ga = bot.get("gate_a") if isinstance(bot.get("gate_a"), dict) else {}
        red = today is not None and today < 0
        gate_a_false = not bool(ga.get("ready"))
        bad = open_risk > 0 and (red or (bot_id in LOSER_IDS and gate_a_false and red))
        # Count as misplaced when red with open risk, or meme/INX red.
        if open_risk > 0 and red:
            misplaced += open_risk
            rows.append({
                "bot": bot_id,
                "open_risk": round(open_risk, 2),
                "today": today,
                "why": "red_today_with_open_risk",
            })
    share = round(misplaced / desk_cap, 4) if desk_cap else None
    return {
        "paper_only": True,
        "misplaced_usd": round(misplaced, 2),
        "desk_cap": desk_cap,
        "share_of_cap": share,
        "rows": rows[:20],
        "note": "Misplaced = open risk on towers with today < 0. Recycle toward fee-clear.",
    }


# ---- Phase 2 capital OS (barbell + util / zero-buy alerts) -----------------

def barbell_status(bots: list | None = None, cfg: dict | None = None) -> dict:
    """Audit open-risk barbell: meme ≤15% of desk cap; fee-clear ≥70% of open."""
    cfg = cfg or {}
    desk_cap = _finite(cfg.get("max_open_risk")) or 100.0
    meme_risk = 0.0
    fee_clear_risk = 0.0
    total_open = 0.0
    by = []
    for bot in bots or []:
        if not isinstance(bot, dict):
            continue
        bot_id = str(bot.get("id") or "")
        risk = float(_finite(bot.get("open_risk")) or 0.0)
        if risk <= 0:
            continue
        total_open += risk
        if bot_id == "memecoin":
            meme_risk += risk
        if bot_id in FEE_CLEAR:
            fee_clear_risk += risk
        by.append({"bot": bot_id, "open_risk": round(risk, 2)})
    meme_of_cap = round(meme_risk / desk_cap, 4) if desk_cap else None
    fee_of_open = (
        round(fee_clear_risk / total_open, 4) if total_open > 1e-9 else None
    )
    meme_ok = meme_of_cap is None or meme_of_cap <= BARBELL_MEME_MAX + 1e-12
    # Idle desk (no open) passes fee-clear share; once risk is on, need ≥70% fee-clear.
    fee_ok = fee_of_open is None or fee_of_open + 1e-12 >= BARBELL_FEE_CLEAR_MIN
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "desk_cap": desk_cap,
        "total_open": round(total_open, 2),
        "meme_risk": round(meme_risk, 2),
        "fee_clear_risk": round(fee_clear_risk, 2),
        "meme_of_cap": meme_of_cap,
        "fee_clear_of_open": fee_of_open,
        "meme_max": BARBELL_MEME_MAX,
        "fee_clear_min": BARBELL_FEE_CLEAR_MIN,
        "meme_ok": meme_ok,
        "fee_clear_ok": fee_ok,
        "pass": bool(meme_ok and fee_ok),
        "by_tower": by[:12],
        "note": (
            f"Barbell: meme ≤{BARBELL_MEME_MAX:.0%} of desk cap; "
            f"fee-clear ≥{BARBELL_FEE_CLEAR_MIN:.0%} of open risk when deployed."
        ),
    }


def midday_util_alert(
    desk_util=None,
    *,
    skip_board: dict | None = None,
) -> dict:
    """Alert when util <20% and skip board is EDGE-heavy (true starvation).

    DATA/NEWS/WEEKEND dominant → correct idle (no alert).
    """
    util = _finite(desk_util)
    board = skip_board if isinstance(skip_board, dict) else {}
    stable = board.get("stable_top") if isinstance(board.get("stable_top"), list) else []
    top_codes = [
        str(r.get("code") or "").upper()
        for r in stable[:3]
        if isinstance(r, dict)
    ]
    idle_ok = any(c in ("DATA", "NEWS", "WEEKEND", "CAL") for c in top_codes)
    edge_heavy = bool(top_codes) and top_codes[0] == "EDGE"
    alert = bool(
        util is not None
        and util + 1e-12 < MIDDAY_UTIL_ALERT_LT
        and edge_heavy
        and not idle_ok
    )
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "desk_util": util,
        "bar_lt": MIDDAY_UTIL_ALERT_LT,
        "top_codes": top_codes,
        "edge_heavy": edge_heavy,
        "correct_idle": idle_ok and util is not None and util < MIDDAY_UTIL_ALERT_LT,
        "alert": alert,
        "note": (
            "Low util + EDGE-only skips → capital starvation alert. "
            "DATA/NEWS/WEEKEND idle is correct."
            if alert
            else "No midday starvation alert."
        ),
    }


def _hours_since_iso(stamp: str | None) -> float | None:
    if not stamp:
        return None
    try:
        from datetime import datetime, timezone
        text = str(stamp).replace("Z", "+00:00")
        when = datetime.fromisoformat(text)
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return max(0.0, (now - when).total_seconds() / 3600.0)
    except Exception:
        return None


def zero_buy_alert(
    root: str | None = None,
    *,
    bots: list | None = None,
    skip_board: dict | None = None,
    hours: float = ZERO_BUY_ALERT_HOURS,
) -> dict:
    """Weekday alert: fee-clear quiet ≥6h while BUDGET skips dominate.

    Uses fit-journal last buy for fee-clear towers. Not an alert on WEEKEND.
    """
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        now_ct = datetime.now(ZoneInfo("America/Chicago"))
        weekday = now_ct.weekday()  # Mon=0 … Sun=6
    except Exception:
        weekday = time.gmtime().tm_wday
    is_weekend = weekday >= 5
    state = load_fit(root)
    last_buy_at = None
    for r in state.get("rows") or []:
        if not isinstance(r, dict):
            continue
        if str(r.get("outcome") or "") != "buy":
            continue
        if str(r.get("bot") or "") not in FEE_CLEAR:
            continue
        at = str(r.get("at") or "")
        if at and (last_buy_at is None or at > last_buy_at):
            last_buy_at = at
    age_h = _hours_since_iso(last_buy_at)
    board = skip_board if isinstance(skip_board, dict) else {}
    stable = board.get("stable_top") if isinstance(board.get("stable_top"), list) else []
    top = [
        str(r.get("code") or "").upper()
        for r in stable[:5]
        if isinstance(r, dict)
    ]
    budget_heavy = "BUDGET" in top[:2]
    quiet = age_h is None or age_h + 1e-12 >= float(hours)
    alert = bool(not is_weekend and quiet and budget_heavy)
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "is_weekend": is_weekend,
        "last_fee_clear_buy_at": last_buy_at,
        "hours_since_buy": round(age_h, 2) if age_h is not None else None,
        "bar_hours": float(hours),
        "budget_heavy": budget_heavy,
        "top_codes": top,
        "alert": alert,
        "note": (
            f"Zero-buy alert: ≥{hours:.0f}h weekday quiet on fee-clear with BUDGET skips."
            if alert
            else "No zero-buy capital alert."
        ),
    }


def capital_os_status(
    root: str | None = None,
    *,
    bots: list | None = None,
    cfg: dict | None = None,
    desk_util=None,
) -> dict:
    """Masters board: barbell + midday util + zero-buy capital alerts."""
    skip_board = None
    try:
        import desk_more
        skip_board = desk_more.skip_leaderboard(root)
    except Exception:
        skip_board = None
    barbell = barbell_status(bots, cfg)
    util = desk_util
    if util is None and bots and cfg:
        desk_open = sum(float(_finite(b.get("open_risk")) or 0) for b in bots if isinstance(b, dict))
        cap = _finite(cfg.get("max_open_risk")) or 100.0
        util = round(desk_open / cap, 4) if cap else None
    midday = midday_util_alert(util, skip_board=skip_board)
    zero = zero_buy_alert(root, bots=bots, skip_board=skip_board)
    alerts = []
    if midday.get("alert"):
        alerts.append("midday_util")
    if zero.get("alert"):
        alerts.append("zero_buy")
    if not barbell.get("pass"):
        alerts.append("barbell")
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "barbell": barbell,
        "midday_util": midday,
        "zero_buy": zero,
        "alerts": alerts,
        "ok": len(alerts) == 0,
        "note": (
            "Phase 2 capital OS. Starve losers → feed fee-clear; "
            "never raise meme budget to use margin."
        ),
    }


def capture_capital_os(
    root: str | None,
    *,
    bots: list | None = None,
    cfg: dict | None = None,
    desk_util=None,
    label: str | None = None,
) -> dict:
    """Persist today's capital OS snapshot for staff review."""
    day = label or _chicago_day()
    status = capital_os_status(root, bots=bots, cfg=cfg, desk_util=desk_util)
    row = {
        **status,
        "label": day,
        "captured_at": _now(),
    }
    path = _path(CAPITAL_OS_NAME, root)
    store = _load(path, {"paper_only": True, "days": [], "latest": None})
    days = [d for d in (store.get("days") or []) if isinstance(d, dict)]
    days = [d for d in days if str(d.get("label") or "") != day]
    days.append(row)
    store["days"] = days[-60:]
    store["latest"] = row
    store["last_at"] = _now()
    _save(path, store)
    return row


def latest_capital_os(root: str | None = None) -> dict | None:
    store = _load(_path(CAPITAL_OS_NAME, root), {"paper_only": True, "latest": None})
    latest = store.get("latest")
    return latest if isinstance(latest, dict) else None


# ---- BTC / ETH calibration report (Phase 4) --------------------------------

def _btc_history_rows(bots: list | None, *, series: str | None = None) -> list:
    """Closed/history rows from btc15m. Optional series filter (KXBTC15M / KXETH15M)."""
    want = str(series or "").strip().upper()
    rows = []
    for bot in bots or []:
        if not isinstance(bot, dict):
            continue
        if str(bot.get("id") or "") not in ("btc15m", "btc"):
            continue
        for src in (bot.get("history") or [], bot.get("closed") or []):
            for h in src:
                if not isinstance(h, dict):
                    continue
                if want:
                    s = str(h.get("series") or "").upper()
                    ticker = str(h.get("ticker") or "").upper()
                    if want == "KXETH15M":
                        if "ETH" not in s and not ticker.startswith("KXETH"):
                            continue
                    elif want == "KXBTC15M":
                        if "ETH" in s or ticker.startswith("KXETH"):
                            continue
                        if s and "BTC" not in s and not ticker.startswith("KXBTC"):
                            # Keep unlabeled legacy BTC rows when series missing.
                            if s:
                                continue
                rows.append(h)
    return rows


def _crypto15_calibration_report(
    bots: list | None = None,
    *,
    series: str,
    bot_label: str,
    min_n: int = BTC_CALIB_MIN_N,
) -> dict:
    """Shared BTC/ETH calib buckets. Never auto-writes Φ."""
    rows = _btc_history_rows(bots, series=series)
    buckets = []
    hi_hits = 0
    hi_n = 0
    for lo, hi in BTC_CALIB_BUCKETS:
        local = []
        for h in rows:
            p = _finite(h.get("prob") if h.get("prob") is not None else h.get("fair_at_entry"))
            pnl = _finite(h.get("pnl") if h.get("pnl") is not None else h.get("pnl_usd"))
            if p is None or pnl is None:
                continue
            if not (lo <= float(p) < hi):
                continue
            hit = 1.0 if pnl > 0 else 0.0
            local.append(hit)
            if lo + 1e-12 >= BTC_CALIB_HI_LABEL:
                hi_n += 1
                hi_hits += int(hit)
        n = len(local)
        rate = round(sum(local) / n, 4) if n else None
        buckets.append({
            "lo": lo,
            "hi": hi,
            "label_mid": round((lo + min(hi, 1.0)) / 2, 3),
            "n": n,
            "hit_rate": rate,
            "gap": None if rate is None else round(rate - ((lo + min(hi, 1.0)) / 2), 4),
        })
    hi_rate = round(hi_hits / hi_n, 4) if hi_n else None
    miscal = bool(
        hi_n >= int(min_n)
        and hi_rate is not None
        and hi_rate + 1e-12 < BTC_CALIB_HI_HIT_FLOOR
    )
    action = "raise_phi" if miscal else ("observe" if hi_n < int(min_n) else "keep")
    name = "ETH" if "ETH" in series.upper() else "BTC"
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "bot": bot_label,
        "series": series,
        "n": sum(b["n"] for b in buckets),
        "hi_label": BTC_CALIB_HI_LABEL,
        "hi_n": hi_n,
        "hi_hit_rate": hi_rate,
        "hi_hit_floor": BTC_CALIB_HI_HIT_FLOOR,
        "miscalibrated": miscal,
        "action": action,
        "buckets": buckets,
        "auto_promote": False,
        "auto_write_phi": False,
        "note": (
            f"{name} calibration: high-p (≥80%) bucket must hit ≥70% once n≥20. "
            "Miscalibration → raise Φ / fix model — never size up on fake confidence."
            if miscal
            else f"{name} ({series}) calibration board. Fee floors locked; no auto param write."
        ),
    }


def btc_calibration_report(
    bots: list | None = None,
    *,
    min_n: int = BTC_CALIB_MIN_N,
) -> dict:
    """Bucket BTC model-p vs realized hit rate. Flag high-p miscalibration.

    Plan: if labeled ~80% wins ~55%, raise Φ — never size on miscalibration.
    Uses KXBTC15M slice when series tags exist; unlabeled legacy rows stay in.
    """
    return _crypto15_calibration_report(
        bots, series="KXBTC15M", bot_label="btc15m", min_n=min_n,
    )


def eth_calibration_report(
    bots: list | None = None,
    *,
    min_n: int = BTC_CALIB_MIN_N,
) -> dict:
    """KXETH15M calib slice — separate from BTC (Phase 4). Never writes Φ."""
    return _crypto15_calibration_report(
        bots, series="KXETH15M", bot_label="btc15m", min_n=min_n,
    )


def capture_btc_calibration(
    root: str | None,
    *,
    bots: list | None = None,
    label: str | None = None,
) -> dict:
    """Persist today's BTC calibration card for Masters / Sunday review."""
    day = label or _chicago_day()
    report = btc_calibration_report(bots)
    card = {**report, "label": day, "captured_at": _now()}
    path = _path(BTC_CALIB_NAME, root)
    store = _load(path, {"paper_only": True, "cards": [], "latest": None})
    cards = [c for c in (store.get("cards") or []) if isinstance(c, dict)]
    cards = [c for c in cards if str(c.get("label") or "") != day]
    cards.append(card)
    store["cards"] = cards[-60:]
    store["latest"] = card
    store["last_at"] = _now()
    _save(path, store)
    return card


def latest_btc_calibration(root: str | None = None) -> dict | None:
    store = _load(_path(BTC_CALIB_NAME, root), {"paper_only": True, "latest": None})
    latest = store.get("latest")
    return latest if isinstance(latest, dict) else None


def capture_eth_calibration(
    root: str | None,
    *,
    bots: list | None = None,
    label: str | None = None,
) -> dict:
    """Persist today's ETH (KXETH15M) calibration card — never writes Φ."""
    day = label or _chicago_day()
    report = eth_calibration_report(bots)
    card = {**report, "label": day, "captured_at": _now()}
    path = _path(ETH_CALIB_NAME, root)
    store = _load(path, {"paper_only": True, "cards": [], "latest": None})
    cards = [c for c in (store.get("cards") or []) if isinstance(c, dict)]
    cards = [c for c in cards if str(c.get("label") or "") != day]
    cards.append(card)
    store["cards"] = cards[-60:]
    store["latest"] = card
    store["last_at"] = _now()
    _save(path, store)
    return card


def latest_eth_calibration(root: str | None = None) -> dict | None:
    store = _load(_path(ETH_CALIB_NAME, root), {"paper_only": True, "latest": None})
    latest = store.get("latest")
    return latest if isinstance(latest, dict) else None


RAISE_PHI_DECISION_ALLOW = frozenset({"accept", "defer"})
MAX_RAISE_PHI_DECISIONS = 200


def staff_log_raise_phi_decision(
    root: str | None,
    *,
    decision: str,
    board: str = "btc",
    who: str = "",
    note: str = "",
    before_hit_rate=None,
    after_hit_rate=None,
    bots: list | None = None,
) -> dict:
    """Staff accept/defer log for raise_Φ tickets (make-money step 393).

    Never writes Φ. Never softens floors. auto_write_phi stays False.
    """
    dec = str(decision or "").strip().lower()
    if dec not in RAISE_PHI_DECISION_ALLOW:
        return {
            "ok": False,
            "reason": f"decision must be one of {sorted(RAISE_PHI_DECISION_ALLOW)}",
            "auto_write_phi": False,
            "fee_floors_locked": True,
            "paper_only": True,
        }
    board_id = str(board or "btc").strip().lower() or "btc"
    before = _finite(before_hit_rate)
    after = _finite(after_hit_rate)
    # Pull latest board hit rate when caller omits before.
    if before is None:
        try:
            if board_id == "btc":
                card = latest_btc_calibration(root) or btc_calibration_report(bots)
            elif board_id in ("sports", "sports-gap"):
                card = latest_sports_calibration(root) or sports_calibration_report(bots)
            elif board_id in ("commodity", "commodity-15m"):
                card = latest_commodity_calibration(root) or commodity_calibration_report(bots)
            else:
                card = {}
            before = _finite((card or {}).get("hi_hit_rate"))
        except Exception:
            before = None
    row = {
        "at": _now(),
        "board": board_id,
        "decision": dec,
        "who": str(who or "")[:40],
        "note": str(note or "")[:200],
        "before_hit_rate": before,
        "after_hit_rate": after,
        "auto_write_phi": False,
        "fee_floors_locked": True,
        "paper_only": True,
    }
    path = _path(RAISE_PHI_DECISIONS, root)
    store = _load(path, {"paper_only": True, "rows": [], "latest": None})
    rows = [r for r in (store.get("rows") or []) if isinstance(r, dict)]
    rows.append(row)
    store["rows"] = rows[-MAX_RAISE_PHI_DECISIONS:]
    store["latest"] = row
    store["last_at"] = row["at"]
    _save(path, store)
    return {
        "ok": True,
        "row": row,
        "n": len(store["rows"]),
        "auto_write_phi": False,
        "fee_floors_locked": True,
        "paper_only": True,
        "reason": f"logged {dec} for {board_id}",
    }


def raise_phi_decision_log(root: str | None = None) -> dict:
    """Summary of staff raise_Φ accept/defer decisions — never auto-writes Φ."""
    store = _load(
        _path(RAISE_PHI_DECISIONS, root),
        {"paper_only": True, "rows": [], "latest": None},
    )
    rows = [r for r in (store.get("rows") or []) if isinstance(r, dict)]
    accepts = sum(1 for r in rows if r.get("decision") == "accept")
    defers = sum(1 for r in rows if r.get("decision") == "defer")
    latest = store.get("latest") if isinstance(store.get("latest"), dict) else None
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "auto_write_phi": False,
        "n": len(rows),
        "accepts": accepts,
        "defers": defers,
        "latest": latest,
        "rows_tail": rows[-20:],
        "note": (
            "Staff raise_Φ decision log (accept/defer) with before/after hit rates. "
            "Never silent Φ write; never softens floors."
        ),
    }


# ---- BTC edge08 shadow promote (raise-only venue_edge 0.08) -----------------

BTC_EDGE08_BOT = "btc15m"
BTC_EDGE08_VARIANT = "edge08"


def btc_edge08_shadow_status(root: str | None = None) -> dict:
    """Promote-ready board for btc15m/edge08 shadow (n≥30 EV≥0.5). Never auto."""
    try:
        import pimp_desk
        cfg = pimp_desk.load_settings(root)
        rows = pimp_desk.shadow_snapshot_rows(root or _root(root), cfg)
    except Exception as exc:
        return {
            "paper_only": True,
            "fee_floors_locked": True,
            "observe_only": True,
            "auto_promote": False,
            "promote_ready": False,
            "evidence_thin": True,
            "n": 0,
            "n_to_promote": 30,
            "bot": BTC_EDGE08_BOT,
            "variant_id": BTC_EDGE08_VARIANT,
            "label": "edge08 THIN unavailable",
            "reason": f"shadow status unavailable: {exc}",
        }
    edge = next(
        (
            r for r in (rows or [])
            if isinstance(r, dict)
            and r.get("bot") == BTC_EDGE08_BOT
            and r.get("variant_id") == BTC_EDGE08_VARIANT
        ),
        None,
    )
    if not edge:
        return {
            "paper_only": True,
            "fee_floors_locked": True,
            "observe_only": True,
            "auto_promote": False,
            "promote_ready": False,
            "evidence_thin": True,
            "bot": BTC_EDGE08_BOT,
            "variant_id": BTC_EDGE08_VARIANT,
            "n": 0,
            "n_to_promote": 30,
            "expectancy": None,
            "promote_min_n": 30,
            "promote_min_ev": 0.5,
            "venue_edge": 0.08,
            "label": "edge08 THIN n=0/30",
            "reason": "no edge08 shadow account yet",
            "note": (
                "BTC edge08 shadow raises venue_edge to 0.08 (above 0.05 floor). "
                "Staff promote only at n≥30 EV≥0.5. Evidence catch-up deferred."
            ),
        }
    ready = bool(edge.get("promote_ready"))
    n = int(edge.get("n") or 0)
    n_to = max(0, 30 - n)
    ev = edge.get("expectancy")
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "promote_ready": ready,
        "evidence_thin": not ready,
        "bot": BTC_EDGE08_BOT,
        "variant_id": BTC_EDGE08_VARIANT,
        "n": n,
        "n_to_promote": n_to,
        "expectancy": ev,
        "cash": edge.get("cash"),
        "params": edge.get("params") or {"venue_edge": 0.08},
        "venue_edge": float((edge.get("params") or {}).get("venue_edge") or 0.08),
        "promote_min_n": 30,
        "promote_min_ev": 0.5,
        "decision": "review" if ready else "reject",
        "label": (
            f"edge08={'ready' if ready else 'THIN'} n={n}/30 "
            f"ev={ev} n_to={n_to}"
        ),
        "reason": (
            "promote_ready — staff may arm edge08"
            if ready
            else "need n≥30 and EV≥0.5 on edge08 shadow"
        ),
        "note": (
            "Raise-only shadow: venue_edge 0.08 never softens 0.05 floor. "
            "auto_promote=False. No-force CLI when ready."
        ),
    }


def staff_promote_btc_edge08(
    root: str | None = None,
    *,
    who: str = "",
    note: str = "",
    force: bool = False,
) -> dict:
    """Staff promote btc15m/edge08 shadow into params overlay (raise-only)."""
    status = btc_edge08_shadow_status(root)
    if not force and not status.get("promote_ready"):
        return {
            "ok": False,
            "reason": status.get("reason") or "not promote_ready",
            "status": status,
            "auto_promote": False,
            "fee_floors_locked": True,
            "paper_only": True,
        }
    try:
        import pimp_desk
        overlay, err = pimp_desk.promote_shadow(
            root, BTC_EDGE08_BOT, BTC_EDGE08_VARIANT, who=who or "staff", force=force,
        )
    except Exception as exc:
        return {
            "ok": False,
            "reason": f"promote failed: {exc}",
            "status": status,
            "auto_promote": False,
            "fee_floors_locked": True,
            "paper_only": True,
        }
    if err:
        return {
            "ok": False,
            "reason": err,
            "status": status,
            "auto_promote": False,
            "fee_floors_locked": True,
            "paper_only": True,
        }
    return {
        "ok": True,
        "reason": "armed edge08",
        "note": str(note or "")[:200],
        "overlay": (overlay or {}).get(BTC_EDGE08_BOT) if isinstance(overlay, dict) else overlay,
        "status": btc_edge08_shadow_status(root),
        "auto_promote": False,
        "fee_floors_locked": True,
        "paper_only": True,
        "venue_edge": 0.08,
        "floors_ok": True,
    }


# ---- Sports calibration report (living upgrade — parallel to BTC) ----------

def _sports_history_rows(bots: list | None) -> list:
    rows = []
    for bot in bots or []:
        if not isinstance(bot, dict):
            continue
        if str(bot.get("id") or "") not in ("sports-gap", "sports"):
            continue
        for h in bot.get("history") or []:
            if isinstance(h, dict):
                rows.append(h)
    return rows


def sports_calibration_report(
    bots: list | None = None,
    *,
    min_n: int = SPORTS_CALIB_MIN_N,
) -> dict:
    """Bucket sports fair_at_entry vs realized hit. Flag high-p miscalibration.

    Observe-only — never softens 0.06 floor; never auto-writes params.
    """
    rows = _sports_history_rows(bots)
    buckets = []
    hi_hits = 0
    hi_n = 0
    for lo, hi in SPORTS_CALIB_BUCKETS:
        local = []
        for h in rows:
            p = _finite(
                h.get("fair_at_entry")
                if h.get("fair_at_entry") is not None
                else h.get("prob") or h.get("confidence")
            )
            pnl = _finite(h.get("pnl") if h.get("pnl") is not None else h.get("pnl_usd"))
            if p is None or pnl is None:
                continue
            if not (lo <= float(p) < hi):
                continue
            hit = 1.0 if pnl > 0 else 0.0
            local.append(hit)
            if lo + 1e-12 >= SPORTS_CALIB_HI_LABEL:
                hi_n += 1
                hi_hits += int(hit)
        n = len(local)
        rate = round(sum(local) / n, 4) if n else None
        buckets.append({
            "lo": lo,
            "hi": hi,
            "label_mid": round((lo + min(hi, 1.0)) / 2, 3),
            "n": n,
            "hit_rate": rate,
            "gap": None if rate is None else round(rate - ((lo + min(hi, 1.0)) / 2), 4),
        })
    hi_rate = round(hi_hits / hi_n, 4) if hi_n else None
    miscal = bool(
        hi_n >= int(min_n)
        and hi_rate is not None
        and hi_rate + 1e-12 < SPORTS_CALIB_HI_HIT_FLOOR
    )
    action = "raise_phi" if miscal else ("observe" if hi_n < int(min_n) else "keep")
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "bot": "sports-gap",
        "n": sum(b["n"] for b in buckets),
        "hi_label": SPORTS_CALIB_HI_LABEL,
        "hi_n": hi_n,
        "hi_hit_rate": hi_rate,
        "hi_hit_floor": SPORTS_CALIB_HI_HIT_FLOOR,
        "miscalibrated": miscal,
        "action": action,
        "buckets": buckets,
        "auto_promote": False,
        "auto_write_phi": False,
        "note": (
            "Sports calibration: high-fair (≥80%) bucket must hit ≥70% once n≥20. "
            "Miscalibration → fix fair/model — never soften 0.06 or size up on fake confidence."
            if miscal
            else "Sports calibration board (parallel to BTC). Floors locked; no auto param write."
        ),
    }


def capture_sports_calibration(
    root: str | None,
    *,
    bots: list | None = None,
    label: str | None = None,
) -> dict:
    """Persist today's sports calibration card for Masters / Sunday review."""
    day = label or _chicago_day()
    report = sports_calibration_report(bots)
    card = {**report, "label": day, "captured_at": _now()}
    path = _path(SPORTS_CALIB_NAME, root)
    store = _load(path, {"paper_only": True, "cards": [], "latest": None})
    cards = [c for c in (store.get("cards") or []) if isinstance(c, dict)]
    cards = [c for c in cards if str(c.get("label") or "") != day]
    cards.append(card)
    store["cards"] = cards[-60:]
    store["latest"] = card
    store["last_at"] = _now()
    _save(path, store)
    return card


def latest_sports_calibration(root: str | None = None) -> dict | None:
    store = _load(_path(SPORTS_CALIB_NAME, root), {"paper_only": True, "latest": None})
    latest = store.get("latest")
    return latest if isinstance(latest, dict) else None


# ---- Commodity calibration report (living upgrade — parallel to BTC) -------

def _commodity_history_rows(bots: list | None) -> list:
    rows = []
    for bot in bots or []:
        if not isinstance(bot, dict):
            continue
        if str(bot.get("id") or "") not in ("commodity-15m", "commodity"):
            continue
        for h in bot.get("history") or []:
            if isinstance(h, dict):
                rows.append(h)
    return rows


def commodity_calibration_report(
    bots: list | None = None,
    *,
    min_n: int = COMMODITY_CALIB_MIN_N,
) -> dict:
    """Bucket commodity fair/prob vs hit. Flag high-p miscalibration.

    Observe-only — never softens 0.05 floor; never auto-writes params.
    """
    rows = _commodity_history_rows(bots)
    buckets = []
    hi_hits = 0
    hi_n = 0
    for lo, hi in COMMODITY_CALIB_BUCKETS:
        local = []
        for h in rows:
            p = _finite(
                h.get("fair_at_entry")
                if h.get("fair_at_entry") is not None
                else h.get("prob") or h.get("confidence") or h.get("model_p")
            )
            pnl = _finite(h.get("pnl") if h.get("pnl") is not None else h.get("pnl_usd"))
            if p is None or pnl is None:
                continue
            if not (lo <= float(p) < hi):
                continue
            hit = 1.0 if pnl > 0 else 0.0
            local.append(hit)
            if lo + 1e-12 >= COMMODITY_CALIB_HI_LABEL:
                hi_n += 1
                hi_hits += int(hit)
        n = len(local)
        rate = round(sum(local) / n, 4) if n else None
        buckets.append({
            "lo": lo,
            "hi": hi,
            "label_mid": round((lo + min(hi, 1.0)) / 2, 3),
            "n": n,
            "hit_rate": rate,
            "gap": None if rate is None else round(rate - ((lo + min(hi, 1.0)) / 2), 4),
        })
    hi_rate = round(hi_hits / hi_n, 4) if hi_n else None
    miscal = bool(
        hi_n >= int(min_n)
        and hi_rate is not None
        and hi_rate + 1e-12 < COMMODITY_CALIB_HI_HIT_FLOOR
    )
    action = "raise_phi" if miscal else ("observe" if hi_n < int(min_n) else "keep")
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "bot": "commodity-15m",
        "n": sum(b["n"] for b in buckets),
        "hi_label": COMMODITY_CALIB_HI_LABEL,
        "hi_n": hi_n,
        "hi_hit_rate": hi_rate,
        "hi_hit_floor": COMMODITY_CALIB_HI_HIT_FLOOR,
        "miscalibrated": miscal,
        "action": action,
        "buckets": buckets,
        "auto_promote": False,
        "auto_write_phi": False,
        "note": (
            "Commodity calibration: high-fair (≥80%) bucket must hit ≥70% once n≥20. "
            "Miscalibration → fix model — never soften 0.05 or size up on fake confidence."
            if miscal
            else "Commodity calibration board (parallel to BTC/sports). Floors locked; no auto param write."
        ),
    }


def capture_commodity_calibration(
    root: str | None,
    *,
    bots: list | None = None,
    label: str | None = None,
) -> dict:
    """Persist today's commodity calibration card for Masters / Sunday review."""
    day = label or _chicago_day()
    report = commodity_calibration_report(bots)
    card = {**report, "label": day, "captured_at": _now()}
    path = _path(COMMODITY_CALIB_NAME, root)
    store = _load(path, {"paper_only": True, "cards": [], "latest": None})
    cards = [c for c in (store.get("cards") or []) if isinstance(c, dict)]
    cards = [c for c in cards if str(c.get("label") or "") != day]
    cards.append(card)
    store["cards"] = cards[-60:]
    store["latest"] = card
    store["last_at"] = _now()
    _save(path, store)
    return card


def latest_commodity_calibration(root: str | None = None) -> dict | None:
    store = _load(_path(COMMODITY_CALIB_NAME, root), {"paper_only": True, "latest": None})
    latest = store.get("latest")
    return latest if isinstance(latest, dict) else None


# ---- Cross-tower firm rank queue (sports+btc+commodity) --------------------

def _firm_queue_store(root: str | None) -> dict:
    return _load(
        _path(FIRM_QUEUE_NAME, root),
        {"paper_only": True, "offers": {}, "latest": None, "passes": []},
    )


def _firm_offer_key(bot: str, ticker: str, side: str = "") -> str:
    return f"{str(bot or '').strip()}|{str(ticker or '').strip()}|{str(side or '').strip().upper()}"


def _seconds_since_iso(stamp: str | None) -> float | None:
    hours = _hours_since_iso(stamp)
    if hours is None:
        return None
    return float(hours) * 3600.0


def remaining_desk_risk(
    root: str | None = None,
    *,
    cfg: dict | None = None,
    bots: list | None = None,
) -> float:
    """Desk open-risk headroom for firm queue allocate (fail-open to cap)."""
    cap = 100.0
    try:
        if cfg is None:
            import pimp_desk as desk
            cfg = desk.load_settings(root)
        cap = float((cfg or {}).get("max_open_risk") or 100.0)
    except Exception:
        cap = 100.0
    used = 0.0
    rows = bots
    if rows is None:
        try:
            import pimp_desk as desk
            rows = (desk.snapshot(root).get("bots") or [])
        except Exception:
            rows = []
    for bot in rows or []:
        if not isinstance(bot, dict) or bot.get("shadow_only"):
            continue
        try:
            used += float(bot.get("open_risk") or 0)
        except (TypeError, ValueError):
            pass
    return max(0.0, round(float(cap) - float(used), 2))


def offer_firm_candidates(
    root: str | None,
    candidates: list | None,
    *,
    bot: str | None = None,
) -> dict:
    """Upsert fee-clear candidates into the shared firm offer book.

    When ``bot`` is set, replace that tower's prior offers with this batch
    so stale local tickets do not linger until TTL.
    """
    path = _path(FIRM_QUEUE_NAME, root)
    store = _firm_queue_store(root)
    offers = store.get("offers") if isinstance(store.get("offers"), dict) else {}
    bot_id = str(bot or "").strip()
    if bot_id:
        offers = {
            k: v for k, v in offers.items()
            if not (isinstance(v, dict) and str(v.get("bot") or "") == bot_id)
        }
    now = _now()
    accepted = 0
    for row in candidates or []:
        if not isinstance(row, dict):
            continue
        b = str(row.get("bot") or bot_id or "").strip()
        tick = str(row.get("ticker") or "").strip()
        if not b or not tick or b not in FIRM_QUEUE_BOTS:
            continue
        side = str(row.get("side") or "").strip()
        edge = _finite(row.get("edge"))
        conf = _finite(
            row.get("confidence") if row.get("confidence") is not None else row.get("p")
        )
        depth = _finite(row.get("depth"))
        stake = _finite(row.get("stake_est") if row.get("stake_est") is not None else row.get("stake"))
        if stake is None or stake <= 0:
            stake = FIRM_QUEUE_DEFAULT_STAKE
        key = _firm_offer_key(b, tick, side)
        offers[key] = {
            "bot": b,
            "ticker": tick[:80],
            "side": side[:8],
            "edge": edge,
            "confidence": conf,
            "depth": depth,
            "stake_est": round(float(stake), 2),
            "at": now,
            "note": str(row.get("note") or "")[:120],
            "paper_only": True,
        }
        accepted += 1
    if len(offers) > MAX_FIRM_OFFERS:
        oldest = sorted(
            offers.items(),
            key=lambda kv: str((kv[1] or {}).get("at") or ""),
        )
        offers = dict(oldest[-MAX_FIRM_OFFERS:])
    store["offers"] = offers
    store["paper_only"] = True
    store["last_offer_at"] = now
    _save(path, store)
    return {"offered": accepted, "offers_n": len(offers), "bot": bot_id or None}


def rebuild_firm_queue(
    root: str | None,
    *,
    remaining_risk=None,
    cfg: dict | None = None,
    bots: list | None = None,
    note: str = "",
) -> dict:
    """Prune TTL, rank sports+btc+commodity offers, allocate desk risk."""
    path = _path(FIRM_QUEUE_NAME, root)
    store = _firm_queue_store(root)
    offers = store.get("offers") if isinstance(store.get("offers"), dict) else {}
    kept = {}
    cand = []
    for key, row in list(offers.items()):
        if not isinstance(row, dict):
            continue
        bot = str(row.get("bot") or "")
        if bot not in FIRM_QUEUE_BOTS:
            continue
        age = _seconds_since_iso(row.get("at"))
        if age is not None and age > FIRM_QUEUE_TTL_SEC:
            continue
        kept[key] = row
        cand.append({
            "bot": bot,
            "ticker": row.get("ticker"),
            "side": row.get("side"),
            "edge": row.get("edge"),
            "confidence": row.get("confidence"),
            "depth": row.get("depth"),
            "stake_est": row.get("stake_est"),
            "offer_key": key,
        })
    rem = _finite(remaining_risk)
    if rem is None:
        rem = remaining_desk_risk(root, cfg=cfg, bots=bots)
    ranked = []
    alloc = []
    try:
        import desk_brain
        ranked = desk_brain.rank_desk_queue(cand)
        alloc = desk_brain.allocate_risk(ranked, float(rem))
        try:
            desk_brain.remember_queue(
                root, alloc,
                note=(note or "firm cross-tower queue")[:160],
            )
        except Exception:
            pass
    except Exception:
        # Fail soft: mark all accepted so bots keep local rank behavior.
        alloc = []
        for i, row in enumerate(cand):
            item = dict(row)
            item["_queue_rank"] = i + 1
            item["_brain_score"] = None
            item["queue_status"] = "accepted"
            item["queue_note"] = "brain unavailable — fail-open"
            alloc.append(item)
    slim = []
    by_bot: dict[str, dict] = {}
    accepted_n = 0
    deferred_n = 0
    for row in alloc:
        status = str(row.get("queue_status") or "")
        if status == "accepted":
            accepted_n += 1
        elif status == "deferred":
            deferred_n += 1
        bot = str(row.get("bot") or "")
        bucket = by_bot.setdefault(bot, {"accepted": 0, "deferred": 0, "n": 0})
        bucket["n"] += 1
        if status == "accepted":
            bucket["accepted"] += 1
        elif status == "deferred":
            bucket["deferred"] += 1
        slim.append({
            "bot": bot,
            "ticker": row.get("ticker"),
            "side": row.get("side"),
            "edge": row.get("edge"),
            "confidence": row.get("confidence"),
            "depth": row.get("depth"),
            "stake_est": row.get("stake_est"),
            "score": row.get("_brain_score"),
            "rank": row.get("_queue_rank"),
            "status": status,
            "note": row.get("queue_note"),
            "offer_key": row.get("offer_key"),
        })
    card = {
        "paper_only": True,
        "fee_floors_locked": True,
        "at": _now(),
        "ttl_sec": FIRM_QUEUE_TTL_SEC,
        "remaining_risk": round(float(rem), 2),
        "offers_n": len(kept),
        "n": len(slim),
        "accepted_n": accepted_n,
        "deferred_n": deferred_n,
        "by_bot": by_bot,
        "towers": sorted(FIRM_QUEUE_BOTS),
        "rows": slim[:40],
        "note": (
            note
            or "Cross-tower firm queue: buy best sports/btc/commodity score inside desk risk."
        )[:200],
    }
    store["offers"] = kept
    store["latest"] = card
    store["last_at"] = card["at"]
    passes = [p for p in (store.get("passes") or []) if isinstance(p, dict)]
    passes.append({
        "at": card["at"],
        "n": card["n"],
        "accepted_n": accepted_n,
        "deferred_n": deferred_n,
        "remaining_risk": card["remaining_risk"],
    })
    store["passes"] = passes[-80:]
    store["paper_only"] = True
    _save(path, store)
    return card


def firm_queue_status(root: str | None = None) -> dict:
    """Masters board: latest firm rank pass + offer book size (observe-safe)."""
    store = _firm_queue_store(root)
    latest = store.get("latest") if isinstance(store.get("latest"), dict) else None
    offers = store.get("offers") if isinstance(store.get("offers"), dict) else {}
    live_offers = 0
    for row in offers.values():
        if not isinstance(row, dict):
            continue
        if str(row.get("bot") or "") not in FIRM_QUEUE_BOTS:
            continue
        age = _seconds_since_iso(row.get("at"))
        if age is not None and age > FIRM_QUEUE_TTL_SEC:
            continue
        live_offers += 1
    latest_age = _seconds_since_iso((latest or {}).get("at")) if latest else None
    deferred = []
    accepted = []
    for row in (latest or {}).get("rows") or []:
        if not isinstance(row, dict):
            continue
        tip = {
            "bot": row.get("bot"),
            "ticker": row.get("ticker"),
            "rank": row.get("rank"),
            "score": row.get("score"),
            "status": row.get("status"),
        }
        if str(row.get("status") or "") == "deferred":
            deferred.append(tip)
        elif str(row.get("status") or "") == "accepted":
            accepted.append(tip)
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "live_orders_enabled": False,
        "towers": sorted(FIRM_QUEUE_BOTS),
        "ttl_sec": FIRM_QUEUE_TTL_SEC,
        "offers_n": live_offers,
        "latest": latest,
        "latest_age_sec": latest_age,
        "stale": bool(
            latest_age is not None and latest_age > FIRM_QUEUE_TTL_SEC
        ),
        "accepted_n": None if not latest else latest.get("accepted_n"),
        "deferred_n": None if not latest else latest.get("deferred_n"),
        "remaining_risk": None if not latest else latest.get("remaining_risk"),
        "accepted_sample": accepted[:8],
        "deferred_sample": deferred[:8],
        "top": (latest or {}).get("rows") or [],
        "label": (
            f"firm-queue observe offers={live_offers} "
            f"acc={None if not latest else latest.get('accepted_n')} "
            f"def={None if not latest else latest.get('deferred_n')} "
            f"risk_left={None if not latest else latest.get('remaining_risk')}"
        ),
        "note": (
            "Firm queue observe — ranks fee-clear sports+btc+commodity by score; "
            "deferred tickets skip so desk risk buys best edge first. "
            "Never softens floors; never arms LIVE_ORDERS."
        ),
    }


def firm_queue_allows(root: str | None, bot: str, ticker: str) -> dict:
    """Soft allow check. Missing / non-fee-clear / unknown → allow (fail-open)."""
    bot_id = str(bot or "").strip()
    tick = str(ticker or "").strip()
    if not bot_id or not tick or bot_id not in FIRM_QUEUE_BOTS:
        return {"allowed": True, "status": "n/a", "reason": ""}
    latest = firm_queue_status(root).get("latest")
    if not isinstance(latest, dict):
        return {"allowed": True, "status": "empty", "reason": ""}
    age = _seconds_since_iso(latest.get("at"))
    if age is not None and age > FIRM_QUEUE_TTL_SEC:
        return {"allowed": True, "status": "stale", "reason": ""}
    match = None
    for row in latest.get("rows") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("bot") or "") == bot_id and str(row.get("ticker") or "") == tick:
            match = row
            break
    if match is None:
        return {"allowed": True, "status": "missing", "reason": ""}
    status = str(match.get("status") or "")
    if status == "deferred":
        rank = match.get("rank")
        note = str(match.get("note") or "open-risk reserved for higher firm score")
        return {
            "allowed": False,
            "status": "deferred",
            "rank": rank,
            "score": match.get("score"),
            "reason": (
                f"firm-queue deferred rank={rank}: {note}"
            )[:160],
        }
    return {
        "allowed": True,
        "status": status or "accepted",
        "rank": match.get("rank"),
        "score": match.get("score"),
        "reason": "",
    }


def firm_queue_blocks(root: str | None, bot: str, ticker: str) -> str:
    """Non-empty reason when firm queue defers this fee-clear ticket."""
    out = firm_queue_allows(root, bot, ticker)
    if out.get("allowed"):
        return ""
    return str(out.get("reason") or "firm-queue deferred")


def desk_open_risk_headroom(
    root: str | None = None,
    *,
    local_bot: str | None = None,
    local_open_risk=None,
    max_open_risk=None,
    bots: list | None = None,
) -> dict:
    """Desk-wide open-risk headroom (make-money E1 #116).

    When sizing a tower buy, other towers' open risk must count against the
    desk cap — not just the local tower sum. Pass local_open_risk from the
    live in-run state so exits in this check are reflected.
    """
    cap = _finite(max_open_risk)
    rows = bots
    cfg = None
    try:
        import pimp_desk
        cfg = pimp_desk.load_settings(root)
        if cap is None:
            cap = _finite((cfg or {}).get("max_open_risk"))
        if rows is None:
            snap = pimp_desk.snapshot(root)
            rows = (snap.get("bots") if isinstance(snap, dict) else None) or []
            if cfg is None and isinstance(snap, dict):
                cfg = snap.get("cfg")
    except Exception:
        rows = rows or []
    if cap is None or cap <= 0:
        cap = 100.0
    other = 0.0
    local_id = str(local_bot or "").strip()
    for bot in rows or []:
        if not isinstance(bot, dict) or bot.get("shadow_only"):
            continue
        bid = str(bot.get("id") or "")
        if not bid:
            continue
        if local_id and bid == local_id:
            continue
        other += float(_finite(bot.get("open_risk")) or 0.0)
    local = _finite(local_open_risk)
    if local is None and local_id:
        for bot in rows or []:
            if isinstance(bot, dict) and str(bot.get("id") or "") == local_id:
                local = _finite(bot.get("open_risk")) or 0.0
                break
    if local is None:
        local = 0.0
    used = round(float(other) + float(local), 2)
    remaining = round(max(0.0, float(cap) - used), 2)
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "local_bot": local_id or None,
        "local_open_risk": round(float(local), 2),
        "other_open_risk": round(float(other), 2),
        "used": used,
        "cap": float(cap),
        "remaining": remaining,
        "note": (
            "Desk-wide open risk = other towers + local live opens. "
            "Sports/BTC/commodity buys must respect remaining headroom."
        ),
    }


def desk_open_risk_blocks(
    root: str | None,
    *,
    local_bot: str,
    local_open_risk=None,
    add_cost=None,
    max_open_risk=None,
    bots: list | None = None,
) -> str:
    """Non-empty when desk-wide open risk + add_cost would exceed cap."""
    head = desk_open_risk_headroom(
        root,
        local_bot=local_bot,
        local_open_risk=local_open_risk,
        max_open_risk=max_open_risk,
        bots=bots,
    )
    add = float(_finite(add_cost) or 0.0)
    used = float(head.get("used") or 0.0)
    cap = float(head.get("cap") or 100.0)
    if used + add > cap + 1e-9:
        return (
            f"desk max open risk (${used:.2f} + ${add:.2f} > ${cap:.2f}; "
            f"other ${float(head.get('other_open_risk') or 0):.2f} + "
            f"local ${float(head.get('local_open_risk') or 0):.2f})"
        )
    return ""


def capture_firm_queue(
    root: str | None,
    *,
    remaining_risk=None,
    cfg: dict | None = None,
    bots: list | None = None,
    label: str | None = None,
) -> dict:
    """Rebuild + stamp a Masters capture of the firm queue."""
    card = rebuild_firm_queue(
        root, remaining_risk=remaining_risk, cfg=cfg, bots=bots,
        note=f"Masters firm queue {label or _chicago_day()}",
    )
    card = {**card, "label": label or _chicago_day(), "captured_at": _now()}
    path = _path(FIRM_QUEUE_NAME, root)
    store = _firm_queue_store(root)
    store["latest"] = card
    store["last_capture"] = card
    store["last_at"] = card["captured_at"]
    _save(path, store)
    return card


# ---- Empty-market CARD latency (Phase 5) -----------------------------------

def record_empty_card(
    root: str | None,
    *,
    bot: str,
    seconds,
    markets_n: int = 0,
    note: str = "",
    series: str = "",
) -> dict:
    """Log an idle/empty-market CARD loop for the <3s bar."""
    sec = _finite(seconds)
    if sec is None or sec < 0:
        return {"recorded": False, "reason": "bad seconds"}
    bot_id = str(bot or "").strip()
    if not bot_id:
        return {"recorded": False, "reason": "missing bot"}
    series_id = str(series or "").strip().upper()[:40]
    row = {
        "at": _now(),
        "bot": bot_id[:40],
        "series": series_id,
        "seconds": round(float(sec), 3),
        "markets_n": int(markets_n or 0),
        "bar_sec": EMPTY_CARD_BAR_SEC,
        "pass": float(sec) + 1e-12 <= EMPTY_CARD_BAR_SEC,
        "note": str(note or "")[:160],
        "paper_only": True,
        "fee_floors_locked": True,
    }
    path = _path(EMPTY_CARD_NAME, root)
    store = _load(path, {"paper_only": True, "rows": [], "latest": None})
    rows = [r for r in (store.get("rows") or []) if isinstance(r, dict)]
    rows.append(row)
    store["rows"] = rows[-MAX_EMPTY_CARD_ROWS:]
    store["latest"] = row
    store["last_at"] = row["at"]
    store["paper_only"] = True
    _save(path, store)
    return {"recorded": True, "row": row}


def empty_card_status(root: str | None = None, *, bot: str | None = None) -> dict:
    """Masters board: empty-market CARD p50 vs 3s bar."""
    store = _load(_path(EMPTY_CARD_NAME, root), {"paper_only": True, "rows": []})
    rows = [r for r in (store.get("rows") or []) if isinstance(r, dict)]
    if bot:
        rows = [r for r in rows if str(r.get("bot") or "") == str(bot)]
    secs = sorted(
        float(_finite(r.get("seconds")) or 0)
        for r in rows
        if _finite(r.get("seconds")) is not None
    )
    p50 = None
    if secs:
        mid = (len(secs) - 1) // 2
        p50 = round(secs[mid], 3)
    by_bot: dict[str, int] = {}
    for r in rows:
        b = str(r.get("bot") or "")
        by_bot[b] = int(by_bot.get(b) or 0) + 1
    ok = p50 is None or p50 + 1e-12 <= EMPTY_CARD_BAR_SEC
    series_board = empty_card_series_board(root) if root is not None else None
    series_alerts = list((series_board or {}).get("alerts") or [])
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "n": len(secs),
        "p50_s": p50,
        "max_s": round(max(secs), 3) if secs else None,
        "bar_sec": EMPTY_CARD_BAR_SEC,
        "pass": ok and not series_alerts,
        "by_bot": by_bot,
        "recent": rows[-8:],
        "series_alerts": series_alerts,
        "note": (
            f"Empty-market CARD bar {EMPTY_CARD_BAR_SEC:.0f}s — "
            "prefetch books; idle loops should exit fast."
            if ok and not series_alerts
            else (
                f"Empty-market CARD p50 {p50}s > {EMPTY_CARD_BAR_SEC:.0f}s bar — "
                "speed up idle path / prefetch."
                if not ok
                else (
                    "Empty CARD series alert densify: "
                    + ",".join(series_alerts[:6])
                )
            )
        ),
    }


def empty_card_series_board(root: str | None = None) -> dict:
    """Per-series empty CARD rate + median time-to-book (plan 422–441, 511–512).

    Covers KXBTC15M / KXETH15M and commodity 15m series. Alert when empty
    resolve exceeds 3s and data is present. Observe only; floors locked.
    """
    store = _load(_path(EMPTY_CARD_NAME, root), {"paper_only": True, "rows": []})
    rows = [r for r in (store.get("rows") or []) if isinstance(r, dict)]
    buckets: dict[str, list[float]] = {s: [] for s in EMPTY_CARD_SERIES_15M}
    for r in rows:
        sec = _finite(r.get("seconds"))
        if sec is None:
            continue
        series = str(r.get("series") or "").strip().upper()
        tagged = False
        if series in buckets:
            buckets[series].append(float(sec))
            tagged = True
        if tagged:
            continue
        for s in _BOT_DEFAULT_SERIES.get(str(r.get("bot") or ""), ()):
            if s in buckets:
                buckets[s].append(float(sec))
    series_rows = []
    alerts: list[str] = []
    for series in EMPTY_CARD_SERIES_15M:
        secs = sorted(buckets.get(series) or [])
        n = len(secs)
        p50 = round(secs[(n - 1) // 2], 3) if n else None
        max_s = round(max(secs), 3) if n else None
        fail_n = sum(1 for s in secs if s + 1e-12 > EMPTY_CARD_BAR_SEC)
        empty_rate = round(fail_n / n, 4) if n else None
        ok = p50 is None or p50 + 1e-12 <= EMPTY_CARD_BAR_SEC
        if n and not ok:
            alerts.append(series)
        series_rows.append({
            "series": series,
            "n": n,
            "empty_rate": empty_rate,
            "median_time_to_book_s": p50,
            "max_s": max_s,
            "bar_sec": EMPTY_CARD_BAR_SEC,
            "pass": ok,
            "alert": bool(n and not ok),
        })
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "live_orders_enabled": False,
        "board_chip": False,
        "bar_sec": EMPTY_CARD_BAR_SEC,
        "series": series_rows,
        "alerts": alerts,
        "ok": len(alerts) == 0,
        "label": (
            f"empty_card_series={'ok' if not alerts else 'ALERT'} "
            f"alerts={','.join(alerts) or 'none'} "
            f"tracked={len(EMPTY_CARD_SERIES_15M)}"
        ),
        "note": (
            "15m empty-CARD densify — rate + median time-to-book per series; "
            f"alert when empty resolve >{EMPTY_CARD_BAR_SEC:.0f}s (data present). "
            "Floors locked."
        ),
    }


def depth_adjusted_edge_board(
    root: str | None = None,
    *,
    candidates: list | None = None,
    need: float | None = None,
) -> dict:
    """Observe: raw edge rank vs depth-adjusted rank for fee-clear towers.

    Plan 423+ densify. Never changes live ranking or floors.
    """
    import desk_more

    depth_need = float(need) if need is not None else float(desk_more.DEFAULT_DEPTH_NEED)
    rows_in: list[dict] = []
    if candidates:
        rows_in = [c for c in candidates if isinstance(c, dict)]
    else:
        try:
            fq = firm_queue_status(root) if root is not None else {}
            offers = list((fq or {}).get("top") or [])
            if not offers:
                latest = (fq or {}).get("latest") if isinstance(fq, dict) else None
                if isinstance(latest, dict):
                    offers = list(latest.get("rows") or [])
            if not offers:
                store = _firm_queue_store(root) if root is not None else {}
                book = store.get("offers") if isinstance(store.get("offers"), dict) else {}
                offers = [v for v in book.values() if isinstance(v, dict)]
            rows_in = [o for o in offers if isinstance(o, dict)]
        except Exception:
            rows_in = []
    scored: list[dict] = []
    for i, c in enumerate(rows_in):
        bot = str(c.get("bot") or "")
        if bot and bot not in FEE_CLEAR and bot not in FIRM_QUEUE_BOTS:
            continue
        edge = _finite(
            c.get("edge")
            if c.get("edge") is not None
            else (c.get("gap") if c.get("gap") is not None else c.get("score"))
        )
        if edge is None:
            continue
        depth = _finite(c.get("depth"))
        series = str(c.get("series") or "")[:40]
        # #471–472: vol prior raises effective depth need (NatGas high); never softens floor.
        row_need = desk_more.effective_depth_need(series or None, depth_need)
        adj = desk_more.depth_adjusted_edge(edge, depth, need=row_need)
        scored.append({
            "bot": bot or "fee-clear",
            "ticker": str(c.get("ticker") or c.get("key") or "")[:60],
            "series": series,
            "edge": round(float(edge), 6),
            "depth": depth,
            "depth_need": row_need,
            "series_vol_prior": desk_more.series_vol_prior(series or None),
            "depth_adjusted_edge": adj,
            "idx": i,
        })
    raw_order = sorted(range(len(scored)), key=lambda i: (-scored[i]["edge"], i))
    adj_order = sorted(
        range(len(scored)),
        key=lambda i: (-scored[i]["depth_adjusted_edge"], i),
    )
    for rank, i in enumerate(raw_order, start=1):
        scored[i]["raw_rank"] = rank
    for rank, i in enumerate(adj_order, start=1):
        scored[i]["adj_rank"] = rank
    for row in scored:
        row["rank_delta"] = int(row["raw_rank"]) - int(row["adj_rank"])
    changed = sum(1 for r in scored if r.get("raw_rank") != r.get("adj_rank"))
    top_raw = [scored[i] for i in raw_order[:8]]
    top_adj = [scored[i] for i in adj_order[:8]]
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "live_orders_enabled": False,
        "board_chip": False,
        "need": depth_need,
        "vol_prior_raises_need": True,
        "n": len(scored),
        "rank_changed_n": changed,
        "candidates": scored[:40],
        "top_raw": [
            {"ticker": r["ticker"], "bot": r["bot"], "edge": r["edge"], "rank": r["raw_rank"]}
            for r in top_raw
        ],
        "top_depth_adjusted": [
            {
                "ticker": r["ticker"],
                "bot": r["bot"],
                "depth_adjusted_edge": r["depth_adjusted_edge"],
                "depth_need": r.get("depth_need"),
                "rank": r["adj_rank"],
            }
            for r in top_adj
        ],
        "label": (
            f"depth_edge n={len(scored)} changed={changed} need={depth_need:g} "
            f"(vol-prior raises per-series need)"
        ),
        "note": (
            "Depth-adjusted edge ranking observe for fee-clear towers — "
            "vol prior raises effective need on high-σ series (NatGas); "
            "never softens floors; does not invent fills."
        ),
    }


# ---- Opportunity-cost clock (Phase 5) --------------------------------------

def _opp_store(root: str | None) -> dict:
    return _load(
        _path(OPP_COST_NAME, root),
        {"paper_only": True, "rows": [], "pending": {}},
    )


def note_pending_high_edge(
    root: str | None,
    *,
    bot: str,
    ticker: str,
    edge=None,
    reason: str = "",
) -> dict:
    """Remember a high-edge ticket blocked by budget/max-buys for opp-cost clock."""
    tick = str(ticker or "").strip()
    bot_id = str(bot or "").strip()
    if not tick or not bot_id:
        return {"pending": False}
    path = _path(OPP_COST_NAME, root)
    store = _opp_store(root)
    pending = store.get("pending") if isinstance(store.get("pending"), dict) else {}
    key = f"{bot_id}|{tick}"
    prev = pending.get(key) if isinstance(pending.get(key), dict) else None
    if prev and prev.get("first_at"):
        row = prev
    else:
        row = {
            "bot": bot_id,
            "ticker": tick[:80],
            "edge": _finite(edge),
            "first_at": _now(),
            "reason": str(reason or "")[:120],
        }
    row["edge"] = _finite(edge) if _finite(edge) is not None else row.get("edge")
    row["last_at"] = _now()
    row["reason"] = str(reason or row.get("reason") or "")[:120]
    pending[key] = row
    # Cap pending map.
    if len(pending) > 200:
        oldest = sorted(
            pending.items(),
            key=lambda kv: str((kv[1] or {}).get("first_at") or ""),
        )
        pending = dict(oldest[-200:])
    store["pending"] = pending
    store["paper_only"] = True
    _save(path, store)
    return {"pending": True, "key": key, "row": row}


def record_opp_cost(
    root: str | None,
    *,
    bot: str,
    blocked_ticker: str = "",
    blocked_edge=None,
    taken_ticker: str = "",
    taken_edge=None,
    wait_sec=None,
    note: str = "",
) -> dict:
    """Log when a lower-edge fill blocked / delayed a higher-edge ticket > bar."""
    wait = _finite(wait_sec)
    be = _finite(blocked_edge)
    te = _finite(taken_edge)
    if wait is None or wait + 1e-12 < OPP_COST_WAIT_SEC:
        return {"recorded": False, "reason": f"wait < {OPP_COST_WAIT_SEC:.0f}s"}
    # Opportunity cost only if blocked edge clearly beats what was taken/held.
    if be is not None and te is not None and be <= te + 1e-12:
        return {"recorded": False, "reason": "blocked edge not higher than taken"}
    row = {
        "at": _now(),
        "bot": str(bot or "")[:40],
        "blocked_ticker": str(blocked_ticker or "")[:80],
        "blocked_edge": be,
        "taken_ticker": str(taken_ticker or "")[:80],
        "taken_edge": te,
        "wait_sec": round(float(wait), 2),
        "bar_sec": OPP_COST_WAIT_SEC,
        "note": str(note or "")[:160],
        "paper_only": True,
        "fee_floors_locked": True,
    }
    path = _path(OPP_COST_NAME, root)
    store = _opp_store(root)
    rows = list(store.get("rows") or [])
    rows.append(row)
    store["rows"] = rows[-MAX_OPP_COST_ROWS:]
    store["last_at"] = row["at"]
    store.setdefault("pending", store.get("pending") if isinstance(store.get("pending"), dict) else {})
    _save(path, store)
    return {"recorded": True, "row": row}


def flush_opp_cost_on_buy(
    root: str | None,
    *,
    bot: str,
    ticker: str = "",
    edge=None,
) -> dict:
    """After a paper buy, emit opp-cost rows for pending higher-edge tickets past bar."""
    bot_id = str(bot or "").strip()
    te = _finite(edge)
    path = _path(OPP_COST_NAME, root)
    store = _opp_store(root)
    pending = store.get("pending") if isinstance(store.get("pending"), dict) else {}
    kept = {}
    emitted = []
    for key, row in list(pending.items()):
        if not isinstance(row, dict):
            continue
        if str(row.get("bot") or "") != bot_id:
            kept[key] = row
            continue
        # Clear matching ticker (filled or gone).
        if ticker and str(row.get("ticker") or "") == str(ticker):
            continue
        be = _finite(row.get("edge"))
        age_h = _hours_since_iso(row.get("first_at"))
        wait = None if age_h is None else age_h * 3600.0
        if (
            wait is not None
            and wait + 1e-12 >= OPP_COST_WAIT_SEC
            and be is not None
            and (te is None or be > te + 1e-12)
        ):
            out = record_opp_cost(
                root,
                bot=bot_id,
                blocked_ticker=str(row.get("ticker") or ""),
                blocked_edge=be,
                taken_ticker=str(ticker or ""),
                taken_edge=te,
                wait_sec=wait,
                note=str(row.get("reason") or "pending high-edge blocked")[:120],
            )
            if out.get("recorded"):
                emitted.append(out.get("row"))
            continue
        kept[key] = row
    store = _opp_store(root)
    store["pending"] = kept
    _save(path, store)
    return {"emitted": len(emitted), "pending_n": len(kept)}


def opp_cost_summary(root: str | None = None) -> dict:
    store = _load(_path(OPP_COST_NAME, root), {"paper_only": True, "rows": []})
    rows = [r for r in (store.get("rows") or []) if isinstance(r, dict)]
    waits = [float(_finite(r.get("wait_sec")) or 0) for r in rows]
    return {
        "paper_only": True,
        "n": len(rows),
        "bar_sec": OPP_COST_WAIT_SEC,
        "mean_wait_s": round(sum(waits) / len(waits), 2) if waits else None,
        "max_wait_s": round(max(waits), 2) if waits else None,
        "recent": rows[-8:],
        "fee_floors_locked": True,
        "note": (
            f"Opportunity-cost clock: low-edge blocks high-edge for >{OPP_COST_WAIT_SEC:.0f}s. "
            "Rank queue should buy best score inside risk."
        ),
    }


# ---- Idea review cadence 90d (Phase 11) ------------------------------------

def staff_register_idea(
    root: str | None,
    *,
    idea: str,
    lever: str = "",
    note: str = "",
    who: str = "",
) -> dict:
    """Register a hillclimb/experiment idea for 90-day review cadence."""
    title = str(idea or "").strip()
    if not title:
        return {"ok": False, "reason": "idea required"}
    path = _path(IDEA_REVIEW_NAME, root)
    store = _load(path, {"paper_only": True, "ideas": []})
    row = {
        "id": f"idea-{int(time.time())}",
        "idea": title[:120],
        "lever": str(lever or "")[:80],
        "note": str(note or "")[:200],
        "who": str(who or "")[:80],
        "opened_at": _now(),
        "status": "open",
        "paper_only": True,
        "auto_promote": False,
        "fee_floors_locked": True,
    }
    ideas = [i for i in (store.get("ideas") or []) if isinstance(i, dict)]
    ideas.append(row)
    store["ideas"] = ideas[-MAX_IDEA_ROWS:]
    store["last_at"] = row["opened_at"]
    _save(path, store)
    return {"ok": True, "idea": row}


def staff_close_idea(
    root: str | None,
    idea_id: str,
    *,
    decision: str = "kill",
    note: str = "",
    who: str = "",
) -> dict:
    """Close/kill/keep an idea after review."""
    path = _path(IDEA_REVIEW_NAME, root)
    store = _load(path, {"paper_only": True, "ideas": []})
    ideas = [i for i in (store.get("ideas") or []) if isinstance(i, dict)]
    hit = None
    for row in ideas:
        if str(row.get("id") or "") == str(idea_id):
            row["status"] = str(decision or "kill")[:40]
            row["closed_at"] = _now()
            row["close_note"] = str(note or "")[:200]
            row["closed_by"] = str(who or "")[:80]
            hit = row
            break
    if hit is None:
        return {"ok": False, "reason": "idea not found"}
    store["ideas"] = ideas
    store["last_at"] = _now()
    _save(path, store)
    return {"ok": True, "idea": hit}


def idea_review_status(root: str | None = None) -> dict:
    """Flag open ideas older than IDEA_REVIEW_DAYS as stale."""
    store = _load(_path(IDEA_REVIEW_NAME, root), {"paper_only": True, "ideas": []})
    ideas = [i for i in (store.get("ideas") or []) if isinstance(i, dict)]
    open_rows = []
    stale = []
    for row in ideas:
        status = str(row.get("status") or "open")
        if status not in ("open", "active", ""):
            continue
        age_h = _hours_since_iso(row.get("opened_at"))
        age_d = None if age_h is None else age_h / 24.0
        item = {
            **row,
            "age_days": round(age_d, 1) if age_d is not None else None,
            "stale": bool(age_d is not None and age_d + 1e-12 >= IDEA_REVIEW_DAYS),
        }
        open_rows.append(item)
        if item["stale"]:
            stale.append(item)
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "review_days": IDEA_REVIEW_DAYS,
        "open_n": len(open_rows),
        "stale_n": len(stale),
        "open": open_rows[-20:],
        "stale": stale[-12:],
        "auto_promote": False,
        "note": (
            f"Idea review cadence: kill or promote within {IDEA_REVIEW_DAYS}d. "
            "Stale experiments must not linger."
        ),
    }


# ---- W0 baseline -----------------------------------------------------------

def capture_baseline(
    root: str | None,
    *,
    bots: list | None = None,
    cfg: dict | None = None,
    label: str = "W0",
) -> dict:
    """Freeze a Chicago-week baseline artifact from snapshot-like bot rows."""
    cfg = cfg or {}
    bleed = firm_bleed_ratio(bots)
    misplaced = capital_misplaced(bots, cfg)
    towers = []
    for bot in bots or []:
        if not isinstance(bot, dict):
            continue
        towers.append({
            "bot": bot.get("id"),
            "today": bot.get("today"),
            "cash": bot.get("cash"),
            "realized": bot.get("realized"),
            "open_risk": bot.get("open_risk"),
            "gate_a": bool((bot.get("gate_a") or {}).get("ready")),
        })
    artifact = {
        "paper_only": True,
        "label": label,
        "captured_at": _now(),
        "towers": towers,
        "bleed": bleed,
        "capital_misplaced": misplaced,
        "fee_floors_locked": True,
        "note": "Baseline for positive-ROI plan. Compare later weeks; do not invent fills.",
    }
    path = _path(BASELINE_NAME, root)
    existing = _load(path, {"paper_only": True, "baselines": []})
    rows = list(existing.get("baselines") or [])
    rows.append(artifact)
    existing["baselines"] = rows[-24:]
    existing["latest"] = artifact
    existing["last_at"] = artifact["captured_at"]
    _save(path, existing)
    return artifact


def load_baseline(root: str | None = None) -> dict:
    return _load(_path(BASELINE_NAME, root), {"paper_only": True, "baselines": [], "latest": None})


def _firm_pnl_proxy(bots: list | None) -> float:
    """Sum of today (preferred) else realized across bot rows."""
    total = 0.0
    for bot in bots or []:
        if not isinstance(bot, dict):
            continue
        today = _finite(bot.get("today"))
        if today is not None:
            total += today
            continue
        realized = _finite(bot.get("realized"))
        if realized is not None:
            total += realized
    return round(total, 4)


def distance_to_zero_board(
    root: str | None = None,
    *,
    bots: list | None = None,
) -> dict:
    """Distance-to-zero vs W0 baseline series (−$225 class firm PnL climb)."""
    store = load_baseline(root)
    baselines = [b for b in (store.get("baselines") or []) if isinstance(b, dict)]
    latest = store.get("latest") if isinstance(store.get("latest"), dict) else None
    w0 = None
    for b in baselines:
        if str(b.get("label") or "") == "W0":
            w0 = b
            break
    if w0 is None and baselines:
        w0 = baselines[0]
    if w0 is None:
        w0 = latest

    def _artifact_pnl(art: dict | None) -> float | None:
        if not isinstance(art, dict):
            return None
        towers = art.get("towers") if isinstance(art.get("towers"), list) else []
        if towers:
            return round(
                sum((_finite(t.get("today")) or 0.0) for t in towers if isinstance(t, dict)),
                4,
            )
        return None

    w0_pnl = _artifact_pnl(w0)
    now_pnl = _firm_pnl_proxy(bots) if bots is not None else _artifact_pnl(latest)
    if now_pnl is None:
        now_pnl = 0.0
    distance = round(max(0.0, -float(now_pnl)), 4)
    delta_vs_w0 = None
    if w0_pnl is not None:
        delta_vs_w0 = round(float(now_pnl) - float(w0_pnl), 4)
    series = []
    for art in baselines[-24:]:
        pnl = _artifact_pnl(art)
        series.append({
            "label": art.get("label"),
            "captured_at": art.get("captured_at"),
            "pnl": pnl,
            "distance_to_zero": round(max(0.0, -(pnl or 0.0)), 4) if pnl is not None else None,
        })
    if bots is not None:
        series.append({
            "label": "live",
            "captured_at": _now(),
            "pnl": now_pnl,
            "distance_to_zero": distance,
        })
    # #733 stance tags: bleed_stop | fee_clear_earn | idle — never force buys.
    try:
        from desk_roi_post_e3e7 import distance_to_zero_stance
        stance = distance_to_zero_stance(now_pnl=now_pnl, bots=bots)
    except Exception:
        stance = {
            "recommended_stance": "idle",
            "force_buys": False,
            "fee_clear_today": None,
            "loser_today": None,
        }
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "w0_label": (w0 or {}).get("label") if w0 else None,
        "w0_pnl": w0_pnl,
        "now_pnl": now_pnl,
        "distance_to_zero": distance,
        "delta_vs_w0": delta_vs_w0,
        "at_zero": float(now_pnl) >= 0.0,
        "series": series,
        "series_n": len(series),
        "recommended_stance": stance.get("recommended_stance"),
        "stance": stance,
        "force_buys": False,
        "label": (
            f"distance_to_zero={distance} now={now_pnl} "
            f"w0={w0_pnl} delta_vs_w0={delta_vs_w0} "
            f"stance={stance.get('recommended_stance')}"
        ),
        "note": (
            "Distance-to-zero vs W0 (−$225 class). Stance tags: "
            "bleed_stop | fee_clear_earn | idle — never force buys. Floors locked."
        ),
    }


def firm_heat_map(
    root: str | None = None,
    bots: list | None = None,
) -> dict:
    """Open-risk heat by tower for Masters portfolio view."""
    _ = root
    towers = []
    total = 0.0
    for bot in bots or []:
        if not isinstance(bot, dict):
            continue
        bid = str(bot.get("id") or "")
        if not bid:
            continue
        risk = _finite(bot.get("open_risk"))
        if risk is None:
            risk = 0.0
        risk = max(0.0, float(risk))
        total += risk
        today = _finite(bot.get("today"))
        towers.append({
            "bot": bid,
            "open_risk": round(risk, 4),
            "today": today,
            "fee_clear": bid in FEE_CLEAR,
        })
    for t in towers:
        share = (t["open_risk"] / total) if total > 1e-12 else 0.0
        t["share"] = round(share, 4)
        if t["open_risk"] <= 0:
            t["heat"] = "cold"
        elif t.get("today") is not None and float(t["today"]) < 0 and share >= 0.25:
            t["heat"] = "hot"
        elif share >= 0.40:
            t["heat"] = "warm"
        else:
            t["heat"] = "ok"
    towers.sort(key=lambda r: (-float(r.get("open_risk") or 0), str(r.get("bot") or "")))
    hottest = towers[0]["bot"] if towers and float(towers[0].get("open_risk") or 0) > 0 else None
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "total_open_risk": round(total, 4),
        "towers": towers,
        "hottest": hottest,
        "label": (
            f"firm_heat total={round(total, 2)} hottest={hottest or 'none'} "
            f"towers={len(towers)}"
        ),
        "note": (
            "Firm open-risk heat map by tower — recycle hot loser risk into "
            "fee-clear. Floors locked."
        ),
    }


# ---- Near-miss weekly card + staff soft-gate promote -----------------------

def _near_miss_rows(root: str | None) -> list[dict]:
    try:
        import desk_more
        state = desk_more.load_more(root)
        return [r for r in (state.get("near_miss") or []) if isinstance(r, dict)]
    except Exception:
        return []


def near_miss_would_pnl(
    *,
    side: str | None,
    result: str | None,
    stake=None,
    entry_price=None,
) -> float | None:
    """Stake-sized would-have PnL for a near-miss once Kalshi result is yes/no.

    Assumes a paper buy of ``stake`` dollars at ``entry_price`` (default 0.50).
    Won → payout − cost; lost → −cost. Observe/label only — never places.
    """
    res = str(result or "").strip().lower()
    sd = str(side or "").strip().upper()
    if res not in ("yes", "no") or sd not in ("YES", "NO"):
        return None
    try:
        import desk_more
        default_stake = float(desk_more.NEAR_MISS_STAKE)
    except Exception:
        default_stake = 2.0
    stake_n = _finite(stake)
    if stake_n is None or stake_n <= 0:
        stake_n = default_stake
    entry = _finite(entry_price)
    if entry is None or entry <= 0 or entry >= 1:
        entry = 0.5
    contracts = float(stake_n) / float(entry)
    won = (res == "yes" and sd == "YES") or (res == "no" and sd == "NO")
    payout = contracts * (1.0 if won else 0.0)
    return round(payout - float(stake_n), 4)


def label_near_miss_outcome(
    root: str | None,
    *,
    ticker: str,
    would_pnl,
    bot: str | None = None,
    side: str | None = None,
    note: str = "",
    only_unlabeled: bool = False,
    row_at: str | None = None,
    stamp_ask=None,
) -> dict:
    """Attach settle / would-have PnL to shadow near-miss rows (staff or settle hook).

    When ``row_at`` is set, only that row is labeled (per-row ask densify).
    ``stamp_ask`` copies an organic sibling ask onto ask-less rows (never invent).
    """
    tick = str(ticker or "").strip()
    pnl = _finite(would_pnl)
    if not tick or pnl is None:
        return {"labeled": 0, "reason": "need ticker + would_pnl"}
    try:
        import desk_more
        state = desk_more.load_more(root)
        rows = list(state.get("near_miss") or [])
    except Exception:
        return {"labeled": 0, "reason": "no near_miss store"}
    n = 0
    bot_id = str(bot or "").strip()
    side_id = str(side or "").strip().upper()
    at_id = str(row_at or "").strip()
    stamp = _finite(stamp_ask)
    if stamp is not None and not (0.0 < float(stamp) < 1.0):
        stamp = None
    out_rows = []
    for row in rows:
        if not isinstance(row, dict):
            out_rows.append(row)
            continue
        item = dict(row)
        match = str(item.get("ticker") or "") == tick and (
            not bot_id or str(item.get("bot") or "") == bot_id
        )
        if side_id:
            match = match and str(item.get("side") or "").strip().upper() == side_id
        if at_id:
            match = match and str(item.get("at") or "") == at_id
        if match:
            if only_unlabeled and _finite(item.get("would_pnl")) is not None:
                out_rows.append(item)
                continue
            item["would_pnl"] = round(float(pnl), 4)
            item["labeled_at"] = _now()
            if note:
                item["label_note"] = str(note)[:120]
            if stamp is not None:
                own = _finite(item.get("ask"))
                if own is None:
                    own = _finite(item.get("entry_price"))
                if own is None or not (0.0 < float(own) < 1.0):
                    item["ask"] = round(float(stamp), 4)
                    item["entry_price"] = round(float(stamp), 4)
            n += 1
        out_rows.append(item)
    if n:
        try:
            import desk_more
            state["near_miss"] = out_rows
            state["last_at"] = _now()
            desk_more.save_more(state, root)
        except Exception:
            return {"labeled": 0, "reason": "save failed"}
        # Living upgrade: join labeled twin into feature store (observe-only).
        try:
            import desk_living
            soft = None
            for row in out_rows:
                if isinstance(row, dict) and str(row.get("ticker") or "") == tick:
                    soft = row.get("soft")
                    break
            desk_living.record_skip_twin_features(
                root,
                bot=bot_id or "unknown",
                ticker=tick,
                would_pnl=pnl,
                soft=soft,
                note=str(note or "")[:120],
            )
        except Exception:
            pass
    return {"labeled": n, "ticker": tick, "would_pnl": round(float(pnl), 4)}


def label_near_miss_from_result(
    root: str | None,
    *,
    ticker: str,
    result: str,
    bot: str | None = None,
    note: str = "",
) -> dict:
    """Label unlabeled near-miss rows for ticker using Kalshi yes/no result.

    Each unlabeled row keeps its own ask when present; ask-less siblings copy an
    organic sibling ask∈(0,1) before defaulting to 0.5. One-pass save.
    """
    tick = str(ticker or "").strip()
    res = str(result or "").strip().lower()
    if not tick or res not in ("yes", "no"):
        return {"labeled": 0, "reason": "need ticker + yes/no result"}
    try:
        import desk_more
        state = desk_more.load_more(root)
        all_rows = list(state.get("near_miss") or [])
    except Exception:
        return {"labeled": 0, "ticker": tick, "reason": "no near_miss store"}
    bot_filter = str(bot or "").strip()
    # Sibling organic ask per (side, bot) for ask-less legacy densify.
    organic_ask: dict[tuple, float] = {}
    for row in all_rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("ticker") or "") != tick:
            continue
        if bot_filter and str(row.get("bot") or "") != bot_filter:
            continue
        if _finite(row.get("would_pnl")) is not None:
            continue
        side = str(row.get("side") or "YES").strip().upper() or "YES"
        bot_id = str(row.get("bot") or "")
        key = (tick, side, bot_id)
        for field in ("ask", "entry_price"):
            a = _finite(row.get(field))
            if a is not None and 0.0 < float(a) < 1.0:
                organic_ask[key] = float(a)
                break
    labeled = 0
    note_s = str(note or f"settle result={res}")[:120]
    out_rows: list = []
    for row in all_rows:
        if not isinstance(row, dict):
            out_rows.append(row)
            continue
        item = dict(row)
        match = str(item.get("ticker") or "") == tick and (
            not bot_filter or str(item.get("bot") or "") == bot_filter
        )
        if match and _finite(item.get("would_pnl")) is None:
            side = str(item.get("side") or "YES").strip().upper() or "YES"
            bot_id = str(item.get("bot") or "")
            key = (tick, side, bot_id)
            entry = None
            for field in ("ask", "entry_price"):
                a = _finite(item.get(field))
                if a is not None and 0.0 < float(a) < 1.0:
                    entry = float(a)
                    break
            stamp = None
            if entry is None:
                entry = organic_ask.get(key)
                stamp = entry
            pnl = near_miss_would_pnl(
                side=side,
                result=res,
                stake=item.get("stake"),
                entry_price=entry,
            )
            if pnl is not None:
                item["would_pnl"] = round(float(pnl), 4)
                item["labeled_at"] = _now()
                item["label_note"] = note_s
                if stamp is not None:
                    item["ask"] = round(float(stamp), 4)
                    item["entry_price"] = round(float(stamp), 4)
                labeled += 1
        out_rows.append(item)
    if labeled:
        try:
            import desk_more
            state["near_miss"] = out_rows
            state["last_at"] = _now()
            desk_more.save_more(state, root)
        except Exception:
            return {"labeled": 0, "ticker": tick, "reason": "save failed"}
        # Observe twin join once per settle label batch (same as prior path).
        try:
            import desk_living
            twin_pnl = None
            twin_soft = None
            for row in out_rows:
                if (
                    isinstance(row, dict)
                    and str(row.get("ticker") or "") == tick
                    and _finite(row.get("would_pnl")) is not None
                ):
                    twin_pnl = row.get("would_pnl")
                    twin_soft = row.get("soft")
                    break
            if twin_pnl is not None:
                desk_living.record_skip_twin_features(
                    root,
                    bot=bot_filter or "unknown",
                    ticker=tick,
                    would_pnl=twin_pnl,
                    soft=twin_soft,
                    note=note_s,
                )
        except Exception:
            pass
    return {
        "labeled": labeled,
        "ticker": tick,
        "result": res,
        "paper_only": True,
        "auto_promote": False,
    }


def _sports_account_path(root: str | None = None) -> str:
    return os.path.join(_root(root), "sports-gap-paper", "state.json")


def _commodity_account_path(root: str | None = None) -> str:
    return os.path.join(_root(root), "commodity-15m-paper", "paper_account.json")


def _kalshi_yes_bid_from_market(market: dict | None):
    """Parse yes bid dollars from a Kalshi market dict (0.0 is a real quote)."""
    if not isinstance(market, dict):
        return None
    raw = market.get("yes_bid_dollars")
    if raw in (None, ""):
        raw = market.get("yes_bid")
    if raw in (None, ""):
        return None
    try:
        bid = float(raw)
    except (TypeError, ValueError):
        return None
    if bid > 1.5:
        bid = bid / 100.0
    if bid < 0:
        return None
    return bid


def backfill_sports_exit_shadow_from_closed(
    root: str | None = None,
    *,
    fetch_market=None,
    limit: int = 80,
) -> dict:
    """Settle-retro densify: closed sports → hard-stop / time-final shadow rows.

    Uses real Kalshi bids (bid=0 on finalized losers counts). Dedupes by ticker.
    Observe only — never LIVE sells, never arms promotes.
    """
    path = _sports_account_path(root)
    try:
        with open(path, encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, json.JSONDecodeError, TypeError):
        return {
            "ok": True,
            "recorded": 0,
            "hard_stop": 0,
            "time_final": 0,
            "scanned": 0,
            "note": "no sports state",
        }
    closed = [r for r in (state.get("closed") or []) if isinstance(r, dict)]
    hs_path = _path(SPORTS_HARD_STOP_SHADOW, root)
    tf_path = _path(SPORTS_TIME_FINAL_SHADOW, root)
    hs_state = _load(hs_path, {"paper_only": True, "version": 1, "rows": [], "live": False})
    tf_state = _load(tf_path, {"paper_only": True, "version": 1, "rows": [], "live": False})
    hs_seen = {
        str(r.get("ticker") or "")
        for r in (hs_state.get("rows") or [])
        if isinstance(r, dict) and r.get("ticker")
    }
    tf_seen = {
        str(r.get("ticker") or "")
        for r in (tf_state.get("rows") or [])
        if isinstance(r, dict) and r.get("ticker")
    }

    def _default_fetch(ticker: str):
        import urllib.request
        url = (
            "https://api.elections.kalshi.com/trade-api/v2/markets/"
            + str(ticker)
        )
        try:
            with __import__("kalshi_gateway").urlopen(url, timeout=8) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except Exception:
            return None
        market = payload.get("market") if isinstance(payload, dict) else None
        if not isinstance(market, dict):
            market = payload if isinstance(payload, dict) else None
        return market if isinstance(market, dict) else None

    getter = fetch_market or _default_fetch
    hard_n = 0
    tfinal_n = 0
    scanned = 0
    for row in closed[-int(limit) :]:
        tick = str(row.get("ticker") or "").strip()
        if not tick:
            continue
        need_hs = tick not in hs_seen
        need_tf = tick not in tf_seen
        if not need_hs and not need_tf:
            continue
        scanned += 1
        try:
            market = getter(tick)
        except Exception:
            market = None
        api_bid = _kalshi_yes_bid_from_market(market)
        # gap_bot stores entry companion `bid`≈ask at open — never use it as an
        # exit mark. Prefer true exit marks; honor API wipe 0 on settle losers
        # only when no organic mid-open exit exists. When organic exit_mark
        # already hits HS (gap-decay/flip), keep it — live api_bid>0 after exit
        # can recover above threshold and DROP evidence. Inverse: organic exit
        # that never hit must not invent HS from a later API quote.
        exit_mark = None
        for key in ("exit_bid", "mark_bid", "exit_price"):
            if row.get(key) is not None:
                exit_mark = _finite(row.get(key))
                break
        settle_pnl = _finite(row.get("pnl"))
        is_loser = settle_pnl is not None and settle_pnl + 1e-12 < 0.0
        entry = row.get("entry_price")
        bid = None
        organic_exit = exit_mark is not None
        if need_hs and organic_exit:
            if sports_hard_stop_hit(entry, exit_mark).get("hit"):
                bid = exit_mark
            # else: organic mid-open exit never hit — do not invent from later API
        elif need_hs:
            # hold-to-settle / missing exit mark — honest API settle-retro
            if api_bid is not None and api_bid > 0:
                bid = api_bid
            elif api_bid is not None and api_bid <= 0 and is_loser:
                # Finalized wipe on a loser — honest settle-retro densify.
                bid = api_bid
            elif api_bid is not None:
                bid = api_bid
        if bid is None:
            continue
        if need_hs:
            # Finalized API bid=0 always "hits" via threshold pricing. That invents
            # hard-stops on winners that never traded through entry−drop. Only
            # invent threshold wipe stops for known settle losers.
            wipe_quote = bool(bid is not None and bid <= 0)
            if wipe_quote and not is_loser:
                pass  # skip — no mid-game stop evidence
            else:
                rec = record_sports_hard_stop_shadow(
                    root,
                    ticker=tick,
                    side=str(row.get("side") or ""),
                    league=str(row.get("league") or ""),
                    entry_price=entry,
                    bid=bid,
                    contracts=row.get("contracts"),
                    cost=row.get("cost"),
                    note="catchup settle-retro hard-stop — no live sell",
                )
                if rec.get("recorded"):
                    hard_n += 1
                    hs_seen.add(tick)
        # Time-final is NOT settle-retro densified: forcing minutes_left=0 on
        # gap-decay / model-flip closes invents false "near-final" trims. Honest
        # t-final evidence comes from mid-open ticks with real clock rem.
    return {
        "ok": True,
        "paper_only": True,
        "observe_only": True,
        "auto_promote": False,
        "live": False,
        "scanned": scanned,
        "hard_stop": hard_n,
        "time_final": tfinal_n,
        "recorded": hard_n + tfinal_n,
        "note": (
            "Sports exit-shadow catch-up: hard-stop from closed "
            "(API wipe on losers / exit_bid|mark|exit_price; never entry bid). "
            "Time-final settle-retro disabled — mid-open clock only. "
            "Never LIVE; never arms."
        ),
    }


def _parse_commodity_closed_at(raw):
    """Parse commodity paper_sell closed stamp → aware UTC datetime."""
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        from datetime import datetime, timezone
        cleaned = text.replace(" UTC", "").replace("Z", "").strip()
        # "2026-11-08 12:00:00" or ISO
        if "T" in cleaned:
            dt = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
        else:
            dt = datetime.strptime(cleaned[:19], "%Y-%m-%d %H:%M:%S")
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def backfill_commodity_time_stop_from_closed(
    root: str | None = None,
    *,
    limit: int = 80,
) -> dict:
    """Catch-up densify: closed commodity → time-stop shadow when near-close underwater.

    Honest clock from closed_at vs close_time. Sells stamped slightly after the
    bell (≤min_left overshoot) evaluate at close_time for settle-retro parity —
    never invent rem=0 for early flips. Covers model-flip sells that raced ahead
    of mid-open densify. Observe only; never LIVE; never arms.
    """
    path = _commodity_account_path(root)
    try:
        with open(path, encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, json.JSONDecodeError, TypeError):
        return {
            "ok": True,
            "recorded": 0,
            "scanned": 0,
            "paper_only": True,
            "observe_only": True,
            "auto_promote": False,
            "live": False,
            "note": "no commodity account",
        }
    closed = [r for r in (state.get("closed") or []) if isinstance(r, dict)]
    shadow_path = _path(COMMODITY_TIME_STOP_SHADOW, root)
    shadow = _load(shadow_path, {"paper_only": True, "version": 1, "rows": [], "live": False})
    seen = {
        str(r.get("ticker") or "")
        for r in (shadow.get("rows") or [])
        if isinstance(r, dict) and r.get("ticker")
    }
    recorded = 0
    scanned = 0
    for row in closed[-int(limit) :]:
        tick = str(row.get("ticker") or "").strip()
        if not tick or tick in seen:
            continue
        if row.get("time_stop_shadowed"):
            # Already densified mid-open / settle-retro — skip duplicate catchup.
            continue
        close_time = row.get("close_time")
        if not close_time:
            continue
        scanned += 1
        closed_at = _parse_commodity_closed_at(row.get("closed") or row.get("closed_at"))
        # Sell stamped slightly after the bell: evaluate at close_time (rem≈0,
        # settle-retro parity). Overshoot beyond min_left keeps early flips out
        # — never invent rem=0 for sells minutes before settle.
        close_dt = None
        try:
            from datetime import datetime, timezone
            raw = str(close_time).replace("Z", "+00:00")
            close_dt = datetime.fromisoformat(raw)
            if close_dt.tzinfo is None:
                close_dt = close_dt.replace(tzinfo=timezone.utc)
        except Exception:
            close_dt = None
        eval_now = closed_at
        if (
            closed_at is not None
            and close_dt is not None
            and closed_at > close_dt
            and (closed_at - close_dt).total_seconds() / 60.0
            <= float(COMMODITY_TIME_STOP_MIN_LEFT) + 1e-12
        ):
            eval_now = close_dt
        # Prefer true exit marks only — never entry companion `bid` (sports HS
        # #448 sibling). Settled opens carry open-time bid into closed[] without
        # exit_price; using it invents past-bell t-stops on winners.
        bid = None
        for key in ("exit_price", "exit_bid", "mark_bid"):
            if row.get(key) is not None:
                bid = _finite(row.get(key))
                break
        if bid is None:
            continue
        # Winner wipe invent guard (same spirit as sports HS).
        settle_pnl = _finite(row.get("pnl"))
        if bid <= 0 and (settle_pnl is None or settle_pnl + 1e-12 >= 0.0):
            continue
        entry = (
            row.get("entry") if row.get("entry") is not None
            else row.get("price") if row.get("price") is not None
            else row.get("ask") if row.get("ask") is not None
            else row.get("entry_price")
        )
        rec = record_commodity_time_stop_shadow(
            root,
            ticker=tick,
            side=str(row.get("side") or ""),
            series=str(row.get("series") or ""),
            close_time=str(close_time),
            entry_price=entry,
            bid=bid,
            contracts=row.get("contracts"),
            cost=row.get("cost"),
            note="catchup closed time-stop — no live sell",
            now=eval_now,
        )
        if rec.get("recorded"):
            recorded += 1
            seen.add(tick)
    return {
        "ok": True,
        "recorded": recorded,
        "scanned": scanned,
        "paper_only": True,
        "observe_only": True,
        "auto_promote": False,
        "live": False,
        "note": (
            "Commodity time-stop catch-up from closed[] with honest closed_at clock "
            "(past-bell ≤min_left clamps to close_time for settle-retro parity). "
            "Exit marks only (exit_price|exit_bid|mark_bid — never entry companion bid). "
            "Never LIVE; never arms; never invents rem=0 on early flips."
        ),
    }


def repair_sports_time_final_settle_poison(root: str | None = None) -> dict:
    """Drop settle-retro time-final rows invented with forced minutes_left=0.

    Mid-open shadow ticks (real rem>0 notes) stay. Observe only; never LIVE.
    """
    path = _path(SPORTS_TIME_FINAL_SHADOW, root)
    state = _load(path, {"paper_only": True, "version": 1, "rows": [], "live": False})
    rows = [r for r in (state.get("rows") or []) if isinstance(r, dict)]
    kept: list[dict] = []
    removed = 0
    for row in rows:
        note = str(row.get("note") or "").lower()
        rem = _finite(row.get("minutes_left"))
        settle_retro = "settle-retro" in note and "time-final" in note
        forced_final = rem is not None and rem <= 1e-12 and settle_retro
        if forced_final or settle_retro:
            removed += 1
            continue
        kept.append(row)
    if removed:
        state["rows"] = kept[-MAX_SPORTS_TFINAL_ROWS:]
        state["last_at"] = _now()
        state["paper_only"] = True
        state["live"] = sports_time_final_is_live(root)
        _save(path, state)
    return {
        "ok": True,
        "removed": removed,
        "kept": len(kept),
        "paper_only": True,
        "observe_only": True,
        "auto_promote": False,
        "live": False,
        "summary": sports_time_final_shadow_summary(root),
        "note": (
            "Removed settle-retro time-final poison (forced rem=0 invents). "
            "Never LIVE; never arms."
        ),
    }


def repair_sports_hard_stop_settle_poison(root: str | None = None) -> dict:
    """Drop settle-retro hard-stop rows invented on winners / non-hit marks.

    - priced_at_threshold + closed settle pnl≥0 (or closed mark never hit)
    - any settle-retro / catchup settle-retro note + closed settle pnl≥0
      (finalize-path invents; mid-open shadow notes are kept)
    Observe only; never LIVE; never arms.
    """
    path = _path(SPORTS_HARD_STOP_SHADOW, root)
    state = _load(path, {"paper_only": True, "version": 1, "rows": [], "live": False})
    rows = [r for r in (state.get("rows") or []) if isinstance(r, dict)]
    if not rows:
        return {
            "ok": True,
            "removed": 0,
            "kept": 0,
            "paper_only": True,
            "observe_only": True,
            "auto_promote": False,
            "live": False,
            "note": "no hard-stop rows",
        }
    closed_by: dict[str, dict] = {}
    try:
        with open(_sports_account_path(root), encoding="utf-8") as handle:
            sports = json.load(handle)
        for crow in sports.get("closed") or []:
            if not isinstance(crow, dict):
                continue
            tick = str(crow.get("ticker") or "").strip()
            if tick:
                closed_by[tick] = crow
    except (OSError, json.JSONDecodeError, TypeError):
        closed_by = {}
    kept: list[dict] = []
    removed = 0
    for row in rows:
        tick = str(row.get("ticker") or "").strip()
        crow = closed_by.get(tick) if tick else None
        priced_thr = bool(row.get("priced_at_threshold"))
        note_l = str(row.get("note") or "").lower()
        settle_retro = "settle-retro" in note_l
        drop_row = False
        settle_pnl = _finite(crow.get("pnl")) if crow is not None else None
        # Finalize / catch-up settle-retro on a winner is poison — mid-open
        # notes ("shadow hard-stop") stay for honest underwater evidence.
        # Also drop settle-retro when closed organic exit never hit HS (API invent).
        organic_exit_mark = None
        if crow is not None:
            for key in ("exit_bid", "mark_bid", "exit_price"):
                if crow.get(key) is not None:
                    organic_exit_mark = _finite(crow.get(key))
                    break
        if settle_retro and settle_pnl is not None and settle_pnl + 1e-12 >= 0.0:
            drop_row = True
        elif settle_retro and crow is not None and organic_exit_mark is not None:
            entry_c = crow.get("entry_price")
            if entry_c is None:
                entry_c = row.get("entry_price")
            if not sports_hard_stop_hit(entry_c, organic_exit_mark).get("hit"):
                drop_row = True
        elif priced_thr and crow is not None:
            # Winner + threshold invent → poison.
            if settle_pnl is not None and settle_pnl + 1e-12 >= 0.0:
                drop_row = True
            elif settle_pnl is not None and settle_pnl + 1e-12 < 0.0:
                # Honest wipe densify on settle losers — keep. Do not use
                # entry companion `bid` as a "never crossed" check.
                drop_row = False
            else:
                # Unknown settle pnl: only drop when a true exit mark never hit.
                exit_mark = None
                for key in ("exit_bid", "mark_bid", "exit_price"):
                    if crow.get(key) is not None:
                        exit_mark = _finite(crow.get(key))
                        break
                entry = crow.get("entry_price")
                if entry is None:
                    entry = row.get("entry_price")
                if exit_mark is not None:
                    hit = sports_hard_stop_hit(entry, exit_mark)
                    if not hit.get("hit"):
                        drop_row = True
        if drop_row:
            removed += 1
            continue
        kept.append(row)
    if removed:
        state["rows"] = kept[-MAX_HARD_STOP_ROWS:]
        state["last_at"] = _now()
        state["paper_only"] = True
        state["live"] = sports_hard_stop_is_live(root)
        _save(path, state)
    return {
        "ok": True,
        "removed": removed,
        "kept": len(kept),
        "paper_only": True,
        "observe_only": True,
        "auto_promote": False,
        "live": False,
        "summary": sports_hard_stop_shadow_summary(root),
        "note": (
            "Removed settle-retro hard-stop poison (winners / threshold invent / "
            "non-hit marks). Never LIVE; never arms."
        ),
    }


def run_shadow_catchup(root: str | None = None, *, fetch_result=None) -> dict:
    """Best-effort densify: near-miss label + helper backfill + CLV repair.

    Observe only — never arms soft gates, never LIVE_ORDERS, never tip invent.
    Safe to call from money-pulse / ritual / make living-shadow-catchup.
    """
    nm_ask = {"ok": False, "stamped": 0, "relabeled": 0}
    labeled = {"ok": False, "labeled": 0, "labeled_n": 0}
    backfilled = {"ok": False, "recorded": 0}
    fee_ledger_bf = {"ok": False, "recorded": 0}
    repaired = {"ok": False, "repaired": 0}
    sports_exit = {"ok": False, "recorded": 0}
    hs_repair = {"ok": False, "removed": 0}
    tf_repair = {"ok": False, "removed": 0}
    errors: list[str] = []
    # Stamp ask onto ask-less rows BEFORE settle label so pending get honest entry.
    try:
        nm_ask = densify_near_miss_ask_catchup(root)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"nm_ask:{type(exc).__name__}")
        nm_ask = {"ok": False, "stamped": 0, "relabeled": 0, "error": type(exc).__name__}
    try:
        labeled = label_near_miss_catchup(root, fetch_result=fetch_result)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"label:{type(exc).__name__}")
        labeled = {"ok": False, "labeled": 0, "labeled_n": 0, "error": type(exc).__name__}
    try:
        backfilled = backfill_helper_fills_from_btc_closed(root)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"helper:{type(exc).__name__}")
        backfilled = {"ok": False, "recorded": 0, "error": type(exc).__name__}
    try:
        fee_ledger_bf = backfill_fee_ledger_from_closed(root)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"fee_ledger:{type(exc).__name__}")
        fee_ledger_bf = {"ok": False, "recorded": 0, "error": type(exc).__name__}
    try:
        repaired = repair_clv_completeness(root)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"clv:{type(exc).__name__}")
        repaired = {"ok": False, "repaired": 0, "error": type(exc).__name__}
    try:
        hs_repair = repair_sports_hard_stop_settle_poison(root)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"hs_repair:{type(exc).__name__}")
        hs_repair = {"ok": False, "removed": 0, "error": type(exc).__name__}
    try:
        tf_repair = repair_sports_time_final_settle_poison(root)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"tf_repair:{type(exc).__name__}")
        tf_repair = {"ok": False, "removed": 0, "error": type(exc).__name__}
    try:
        sports_exit = backfill_sports_exit_shadow_from_closed(root)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"sports_exit:{type(exc).__name__}")
        sports_exit = {"ok": False, "recorded": 0, "error": type(exc).__name__}
    commodity_tstop = {"ok": False, "recorded": 0}
    try:
        commodity_tstop = backfill_commodity_time_stop_from_closed(root)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"commodity_tstop:{type(exc).__name__}")
        commodity_tstop = {"ok": False, "recorded": 0, "error": type(exc).__name__}
    journals_ensured = {"ok": False, "created": []}
    try:
        journals_ensured = ensure_shadow_densify_journals(root)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"journals:{type(exc).__name__}")
        journals_ensured = {"ok": False, "created": [], "error": type(exc).__name__}
    weekly_m1 = {"ok": False, "repaired": 0}
    try:
        weekly_m1 = repair_weekly_sports_m1(root)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"weekly_m1:{type(exc).__name__}")
        weekly_m1 = {"ok": False, "repaired": 0, "error": type(exc).__name__}
    status = near_miss_promote_status(root)
    # CLI catch-up writes marker so doctor / shadow_ops aren't false-stale.
    try:
        root_s = _root(root)
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + "\n"
        marker = os.path.join(root_s, "desk_shadow_catchup_at.txt")
        with open(marker, "w", encoding="utf-8") as handle:
            handle.write(stamp)
    except OSError:
        pass
    return {
        "ok": True,
        "paper_only": True,
        "observe_only": True,
        "auto_promote": False,
        "fee_floors_locked": True,
        "live": False,
        "live_orders_enabled": False,
        "labeled_n": status.get("labeled_n"),
        "labeled": int(labeled.get("labeled") or 0),
        "backfilled": int(backfilled.get("recorded") or 0),
        "fee_ledger_recorded": int(fee_ledger_bf.get("recorded") or 0),
        "repaired": int(repaired.get("repaired") or 0),
        "sports_exit_shadow": int(sports_exit.get("recorded") or 0),
        "commodity_tstop_shadow": int(commodity_tstop.get("recorded") or 0),
        "hard_stop_poison_removed": int(hs_repair.get("removed") or 0),
        "time_final_poison_removed": int(tf_repair.get("removed") or 0),
        "weekly_sports_m1_repaired": int(weekly_m1.get("repaired") or 0),
        "journals_created": list(journals_ensured.get("created") or []),
        "near_miss_ask_stamped": int(nm_ask.get("stamped") or 0),
        "near_miss_ask_relabeled": int(nm_ask.get("relabeled") or 0),
        "near_miss_ask": nm_ask,
        "near_miss_label": labeled,
        "helper_backfill": backfilled,
        "fee_ledger_backfill": fee_ledger_bf,
        "clv_repair": repaired,
        "hard_stop_repair": hs_repair,
        "time_final_repair": tf_repair,
        "sports_exit": sports_exit,
        "commodity_tstop": commodity_tstop,
        "journals_ensured": journals_ensured,
        "weekly_sports_m1_repair": weekly_m1,
        "errors": errors[:8],
        "note": (
            "Shadow catch-up — labels/backfills/repairs densify evidence only. "
            "Never arms; never LIVE; soft-max tip invent exhausted."
        ),
    }


def ensure_shadow_densify_journals(root: str | None = None) -> dict:
    """Materialize empty densify journals / edge08 / fee ledger if missing.

    Distinguishes *missing* (never created) from *thin* (present, n=0) in
    shadow_ops_alerts. Tick already ensures edge08; catchup must too.
    Never invents promote or fee rows; never LIVE; never arms.
    """
    created: list[str] = []
    specs = (
        (SPORTS_HARD_STOP_SHADOW, {"paper_only": True, "version": 1, "rows": [], "live": False}),
        (COMMODITY_TIME_STOP_SHADOW, {"paper_only": True, "version": 1, "rows": [], "live": False}),
        (SPORTS_TIME_FINAL_SHADOW, {"paper_only": True, "version": 1, "rows": [], "live": False}),
        (FEE_LEDGER_NAME, {"paper_only": True, "rows": [], "by_bot": {}, "live": False}),
        (HELPER_FILLS_NAME, {"paper_only": True, "rows": [], "by_helper": {}, "live": False}),
    )
    for name, blank in specs:
        path = _path(name, root)
        if os.path.isfile(path):
            continue
        try:
            _save(path, dict(blank))
            created.append(name)
        except OSError:
            continue
    # Edge08 shadow account — same missing≠thin contract as journals (#392 leftover).
    try:
        import pimp_desk
        edge08_path = pimp_desk.shadow_account_path(root, "btc15m", "edge08")
        if not os.path.isfile(edge08_path):
            pimp_desk.save_shadow_account(
                root, "btc15m", "edge08",
                pimp_desk.load_shadow_account(root, "btc15m", "edge08"),
            )
            created.append(os.path.basename(edge08_path))
    except Exception:
        pass
    return {
        "ok": True,
        "created": created,
        "created_n": len(created),
        "paper_only": True,
        "observe_only": True,
        "auto_promote": False,
        "live": False,
        "note": (
            "Ensured empty densify journals + edge08 + fee ledger exist (missing→thin). "
            "Never invents evidence; never LIVE; never arms."
        ),
    }


def shadow_ops_alerts(root: str | None = None) -> dict:
    """Observe alerts: heartbeat / edge08 / catch-up age / shadow journals.

    Observe only — never arms LIVE / force / tip invent. Doctor surfaces alerts
    but does not hard-fail on shadow_ops.
    """
    alerts: list[str] = []
    heartbeat = {"present": False, "alive": False, "age": None, "path": None}
    edge08 = {"present": False, "path": None, "shadow_enabled": False}
    catchup = {"present": False, "age": None, "path": None, "stale": False}
    tick = {"present": False, "age": None, "path": None, "stale": False}
    journals = {
        "hard_stop": {"present": False, "path": None, "thin": True},
        "commodity_tstop": {"present": False, "path": None, "thin": True},
        "sports_tfinal": {"present": False, "path": None, "thin": True},
        "near_miss": {"present": False, "path": None, "thin": True, "labeled_n": 0},
        "fee_ledger": {"present": False, "path": None},
    }
    shadow_enabled = True
    try:
        import pimp_desk
        root_s = _root(root)
        hb_path = pimp_desk.heartbeat_path(root)
        heartbeat["path"] = hb_path
        heartbeat["present"] = os.path.isfile(hb_path)
        health = pimp_desk.timer_health(root)
        heartbeat["alive"] = bool(health.get("alive"))
        heartbeat["age"] = health.get("age")
        if not heartbeat["present"]:
            alerts.append("heartbeat_missing")
        elif not heartbeat["alive"]:
            alerts.append("heartbeat_stale")
        cfg = pimp_desk.load_settings(root)
        shadow = cfg.get("shadow") if isinstance(cfg.get("shadow"), dict) else {}
        shadow_enabled = bool(shadow.get("enabled", True))
        edge08["shadow_enabled"] = shadow_enabled
        acct = pimp_desk.shadow_account_path(root, "btc15m", "edge08")
        edge08["path"] = acct
        edge08["present"] = os.path.isfile(acct)
        if shadow_enabled and not edge08["present"]:
            alerts.append("shadow_edge08_missing")
        # Catch-up / tick markers — stale if missing or older than cadence×3.
        now_ts = time.time()
        catchup_path = os.path.join(root_s, "desk_shadow_catchup_at.txt")
        tick_path = os.path.join(root_s, "desk_shadow_tick_at.txt")
        catchup["path"] = catchup_path
        tick["path"] = tick_path
        if os.path.isfile(catchup_path):
            catchup["present"] = True
            try:
                catchup["age"] = round(now_ts - os.path.getmtime(catchup_path), 1)
            except OSError:
                catchup["age"] = None
        if os.path.isfile(tick_path):
            tick["present"] = True
            try:
                tick["age"] = round(now_ts - os.path.getmtime(tick_path), 1)
            except OSError:
                tick["age"] = None
        # Catch-up cadence ~10m → stale at 30m; tick ~15m → stale at 45m.
        if shadow_enabled:
            if (not catchup["present"]) or (
                catchup.get("age") is not None and float(catchup["age"]) >= 1800
            ):
                catchup["stale"] = True
                alerts.append("catchup_stale")
            if (not tick["present"]) or (
                tick.get("age") is not None and float(tick["age"]) >= 2700
            ):
                tick["stale"] = True
                alerts.append("tick_stale")
        # Shadow journals expected in SETTLEMENT_FILES — missing / thin boards.
        hs_path = _path(SPORTS_HARD_STOP_SHADOW, root)
        ts_path = _path(COMMODITY_TIME_STOP_SHADOW, root)
        tf_path = _path(SPORTS_TIME_FINAL_SHADOW, root)
        journals["hard_stop"]["path"] = hs_path
        journals["commodity_tstop"]["path"] = ts_path
        journals["sports_tfinal"]["path"] = tf_path
        journals["hard_stop"]["present"] = os.path.isfile(hs_path)
        journals["commodity_tstop"]["present"] = os.path.isfile(ts_path)
        journals["sports_tfinal"]["present"] = os.path.isfile(tf_path)
        if shadow_enabled:
            if not journals["hard_stop"]["present"]:
                alerts.append("hard_stop_journal_missing")
            if not journals["commodity_tstop"]["present"]:
                alerts.append("commodity_tstop_journal_missing")
            if not journals["sports_tfinal"]["present"]:
                alerts.append("sports_tfinal_journal_missing")
            # Thin promote boards (observe) — journal present but n_with_pnl==0.
            try:
                hs = sports_hard_stop_shadow_summary(root)
                journals["hard_stop"]["thin"] = bool(hs.get("evidence_thin"))
                journals["hard_stop"]["n_with_pnl"] = hs.get("n_with_pnl")
                if journals["hard_stop"]["present"] and int(hs.get("n_with_pnl") or 0) <= 0:
                    alerts.append("hard_stop_promote_thin")
            except Exception:
                pass
            try:
                tstop = commodity_time_stop_shadow_summary(root)
                journals["commodity_tstop"]["thin"] = bool(tstop.get("evidence_thin"))
                journals["commodity_tstop"]["n_with_pnl"] = tstop.get("n_with_pnl")
                if (
                    journals["commodity_tstop"]["present"]
                    and int(tstop.get("n_with_pnl") or 0) <= 0
                ):
                    alerts.append("commodity_tstop_promote_thin")
            except Exception:
                pass
            try:
                tfinal = sports_time_final_shadow_summary(root)
                journals["sports_tfinal"]["thin"] = bool(tfinal.get("evidence_thin"))
                journals["sports_tfinal"]["n_with_pnl"] = tfinal.get("n_with_pnl")
                if (
                    journals["sports_tfinal"]["present"]
                    and int(tfinal.get("n_with_pnl") or 0) <= 0
                ):
                    alerts.append("sports_tfinal_promote_thin")
            except Exception:
                pass
            # Near-miss journal thin / labeled_n=0 (observe densify).
            try:
                nm = near_miss_promote_status(root)
                labeled_n = int(nm.get("labeled_n") or 0)
                total_n = int(nm.get("n") or 0)
                journals["near_miss"]["present"] = True
                journals["near_miss"]["labeled_n"] = labeled_n
                journals["near_miss"]["pending_n"] = max(0, total_n - labeled_n)
                journals["near_miss"]["thin"] = bool(labeled_n <= 0)
                if journals["near_miss"]["thin"]:
                    alerts.append("near_miss_journal_thin")
            except Exception:
                journals["near_miss"]["thin"] = True
                alerts.append("near_miss_journal_thin")
            # Fee ledger durability — SETTLEMENT_FILES copy; gitignore may still churn.
            fee_path = _path(FEE_LEDGER_NAME, root)
            journals["fee_ledger"]["path"] = fee_path
            journals["fee_ledger"]["present"] = os.path.isfile(fee_path)
            if shadow_enabled and not journals["fee_ledger"]["present"]:
                alerts.append("fee_ledger_missing")
    except Exception as exc:  # noqa: BLE001
        alerts.append(f"probe_error:{type(exc).__name__}")
    return {
        "paper_only": True,
        "observe_only": True,
        "auto_promote": False,
        "live_orders_enabled": False,
        "ok": len(alerts) == 0,
        "alerts": alerts,
        "heartbeat": heartbeat,
        "shadow_edge08": edge08,
        "catchup": catchup,
        "tick": tick,
        "journals": journals,
        "shadow_enabled": shadow_enabled,
        "note": (
            "Shadow ops observe — heartbeat / edge08 / catch-up age / "
            "sports+commodity shadow journals / near-miss thin / fee ledger / "
            "thin promote boards. Never arms LIVE_ORDERS."
        ),
    }


def _kalshi_fee_per_contract(ask: float) -> float:
    """Kalshi-style ceil(0.07·p·(1-p)·100)/100 fee for one contract."""
    a = float(ask)
    return math.ceil(round(0.07 * a * (1.0 - a) * 100, 6)) / 100


# p+edge invert is Kalshi fee-clear shape only (BTC/ETH under btc15m, commodity,
# sports). Memecoin stores residual conf−0.5 as "edge" — inverting invents ask.
NEAR_MISS_ASK_EDGE_BOTS = frozenset({"btc15m", "commodity-15m", "sports-gap"})
# Commodity evaluate stores edge = p − ask − fee − edge_buf. Invert only when
# the row's historical edge_buf is known — never guess from live venue settings.
COMMODITY_NEAR_MISS_EDGE_BUF_DEFAULT = 0.05


def recover_near_miss_ask_from_edge(
    p,
    edge,
    *,
    bot: str | None = None,
    edge_buf: float | None = None,
) -> float | None:
    """Recover organic ask from stored soft-p + edge when ask was dropped.

    BTC/ETH/sports: edge = p − ask − fee(ask). Commodity: edge = p − ask − fee
    − edge_buf — require an explicit stored ``edge_buf`` (refuse live venue
    guess). Pre-#408 rows kept edge but dropped ask; invert on a 0.1¢ grid.
    Never invents a quote without both p and edge. Returns ask∈(0,1) or None.

    When ``bot`` is set, refuse non-fee-clear towers (esp. memecoin residual).
    """
    bot_id = str(bot or "").strip()
    if bot is not None and bot_id not in NEAR_MISS_ASK_EDGE_BOTS:
        return None
    p_n = _finite(p)
    e_n = _finite(edge)
    if p_n is None or e_n is None:
        return None
    buf = _finite(edge_buf)
    # Commodity without stored buf → sibling-only (historical buf ≠ live venue).
    if bot_id == "commodity-15m" and buf is None:
        return None
    if buf is None:
        buf = 0.0
    if buf < 0:
        return None
    # ask + fee = p − edge − edge_buf (buf=0 for BTC/sports).
    target = float(p_n) - float(e_n) - float(buf)
    if not (0.0 < target < 2.0):
        return None
    best: float | None = None
    best_err = 1e9
    # 0.1¢ grid covers Kalshi dollar asks; stop on first tight match.
    for i in range(1, 1000):
        ask = i / 1000.0
        got = ask + _kalshi_fee_per_contract(ask)
        err = abs(got - target)
        if err < best_err:
            best_err = err
            best = ask
        if err < 5e-4:
            return round(ask, 4)
    if best is not None and best_err < 1e-3:
        return round(float(best), 4)
    return None


def densify_near_miss_ask_catchup(root: str | None = None) -> dict:
    """Stamp organic ask onto ask-less near-miss rows (sibling or p+edge recover).

    Order: (1) sibling ask/entry on same ticker+side+bot, (2) invert p−edge=ask+fee
    for fee-clear bots only (never memecoin residual). When a labeled row's
    would_pnl matches the default entry=0.5 poison (±stake), recompute with the
    recovered ask.

    Observe only — never LIVE; never arms soft gates.
    """
    try:
        import desk_more
        state = desk_more.load_more(root)
        rows = list(state.get("near_miss") or [])
    except Exception:
        return {
            "ok": True,
            "stamped": 0,
            "relabeled": 0,
            "scanned": 0,
            "paper_only": True,
            "observe_only": True,
            "auto_promote": False,
            "live": False,
            "note": "no near_miss store",
        }
    # Sibling organic ask index (ticker, side, bot) → ask.
    organic: dict[tuple, float] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        tick = str(row.get("ticker") or "").strip()
        if not tick:
            continue
        side = str(row.get("side") or "YES").strip().upper() or "YES"
        bot_id = str(row.get("bot") or "")
        key = (tick, side, bot_id)
        for field in ("ask", "entry_price"):
            a = _finite(row.get(field))
            if a is not None and 0.0 < float(a) < 1.0:
                organic[key] = float(a)
                break

    stamped = 0
    relabeled = 0
    scanned = 0
    out_rows: list = []
    try:
        default_stake = float(desk_more.NEAR_MISS_STAKE)
    except Exception:
        default_stake = 2.0

    for row in rows:
        if not isinstance(row, dict):
            out_rows.append(row)
            continue
        item = dict(row)
        own = _finite(item.get("ask"))
        if own is None:
            own = _finite(item.get("entry_price"))
        if own is not None and 0.0 < float(own) < 1.0:
            out_rows.append(item)
            continue
        scanned += 1
        tick = str(item.get("ticker") or "").strip()
        side = str(item.get("side") or "YES").strip().upper() or "YES"
        bot_id = str(item.get("bot") or "")
        key = (tick, side, bot_id)
        ask = organic.get(key)
        source = "sibling" if ask is not None else None
        if ask is None:
            # Fee-clear invert only — memecoin residual must not mint a fake ask.
            # Commodity: only when row stored historical edge_buf (sibling otherwise).
            ask = recover_near_miss_ask_from_edge(
                item.get("p"),
                item.get("edge"),
                bot=bot_id,
                edge_buf=item.get("edge_buf"),
            )
            if ask is not None:
                source = "p_edge"
        if ask is None or not (0.0 < float(ask) < 1.0):
            out_rows.append(item)
            continue
        ask_r = round(float(ask), 4)
        item["ask"] = ask_r
        item["entry_price"] = ask_r
        item["ask_densify"] = source
        stamped += 1
        # Repair default-entry poison labels (±stake) now that ask is honest.
        wp = _finite(item.get("would_pnl"))
        stake_n = _finite(item.get("stake")) or default_stake
        if wp is not None and abs(abs(float(wp)) - float(stake_n)) < 1e-9:
            # Infer settle result from sign of would_pnl + side.
            won = float(wp) > 0
            if side == "YES":
                result = "yes" if won else "no"
            else:
                result = "no" if won else "yes"
            fresh = near_miss_would_pnl(
                side=side, result=result, stake=stake_n, entry_price=ask_r,
            )
            if fresh is not None and abs(float(fresh) - float(wp)) > 1e-9:
                item["would_pnl"] = round(float(fresh), 4)
                item["ask_densify_relabel"] = True
                relabeled += 1
        out_rows.append(item)

    if stamped:
        try:
            state["near_miss"] = out_rows
            state["last_at"] = _now()
            desk_more.save_more(state, root)
        except Exception:
            return {
                "ok": False,
                "stamped": 0,
                "relabeled": 0,
                "scanned": scanned,
                "paper_only": True,
                "observe_only": True,
                "auto_promote": False,
                "live": False,
                "error": "save failed",
            }
    return {
        "ok": True,
        "stamped": stamped,
        "relabeled": relabeled,
        "scanned": scanned,
        "paper_only": True,
        "observe_only": True,
        "auto_promote": False,
        "fee_floors_locked": True,
        "live": False,
        "note": (
            "Near-miss ask catch-up: sibling organic ask, else fee-clear p+edge "
            "invert (commodity only with stored edge_buf; never live venue "
            "guess / memecoin residual). Repairs ±stake default-entry poison "
            "when ask recovered. Never LIVE."
        ),
    }


def label_near_miss_catchup(
    root: str | None = None,
    *,
    fetch_result=None,
    limit: int = 200,
) -> dict:
    """Observe catch-up: label pending near-miss rows from closed market results.

    ``fetch_result(ticker)`` should return 'yes'/'no'/None. Default hits Kalshi
    public market endpoint. Never arms soft gates. Never LIVE.
    """
    rows = _near_miss_rows(root)
    pending = [
        r for r in rows
        if _finite(r.get("would_pnl")) is None and str(r.get("ticker") or "").strip()
    ]
    # Unique tickers, preserve order.
    seen: set[str] = set()
    tickers: list[str] = []
    for r in pending:
        tick = str(r.get("ticker") or "").strip()
        if tick in seen:
            continue
        seen.add(tick)
        tickers.append(tick)
        if len(tickers) >= int(limit):
            break

    def _default_fetch(ticker: str):
        import json
        import urllib.request
        url = (
            "https://api.elections.kalshi.com/trade-api/v2/markets/"
            + str(ticker)
        )
        try:
            with __import__("kalshi_gateway").urlopen(url, timeout=8) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except Exception:
            return None
        market = payload.get("market") if isinstance(payload, dict) else None
        if not isinstance(market, dict):
            market = payload if isinstance(payload, dict) else {}
        result = str((market or {}).get("result") or "").strip().lower()
        return result if result in ("yes", "no") else None

    getter = fetch_result or _default_fetch
    labeled = 0
    scanned = 0
    unresolved = 0
    samples: list[dict] = []
    for tick in tickers:
        scanned += 1
        try:
            result = getter(tick)
        except Exception:
            result = None
        if result not in ("yes", "no"):
            unresolved += 1
            continue
        out = label_near_miss_from_result(
            root, ticker=tick, result=result, note="catchup-label",
        )
        n = int(out.get("labeled") or 0)
        labeled += n
        if n and len(samples) < 8:
            samples.append({"ticker": tick, "result": result, "labeled": n})
    status = near_miss_promote_status(root)
    return {
        "ok": True,
        "paper_only": True,
        "observe_only": True,
        "auto_promote": False,
        "fee_floors_locked": True,
        "live": False,
        "pending_n": len(pending),
        "scanned": scanned,
        "labeled": labeled,
        "unresolved": unresolved,
        "labeled_n": status.get("labeled_n"),
        "n": status.get("n"),
        "promote_ready": status.get("promote_ready"),
        "samples": samples,
        "note": (
            "Near-miss catch-up labels would_pnl from settled markets. "
            "Never auto-promotes; soft-max tip invent exhausted."
        ),
    }


def _near_miss_row_soft_key(row: dict) -> str:
    """Normalize a near-miss row's soft tag to a single allowlisted key (or '')."""
    soft = row.get("soft")
    if isinstance(soft, list):
        keys = [str(s).strip().lower() for s in soft if str(s).strip()]
        if len(keys) == 1 and keys[0] in NEAR_MISS_SOFT_ALLOW:
            return keys[0]
        return ",".join(keys) if keys else ""
    key = str(soft or "").strip().lower()
    return key if key in NEAR_MISS_SOFT_ALLOW else key


def near_miss_soft_band_status(
    root: str | None = None,
    soft: str = "z",
) -> dict:
    """Per-soft promote board: labeled n≥30 + EV≥baseline inside that soft band only."""
    key = str(soft or "").strip().lower()
    rows = [
        r for r in _near_miss_rows(root)
        if _near_miss_row_soft_key(r) == key
    ]
    labeled = [r for r in rows if _finite(r.get("would_pnl")) is not None]
    pnls = [float(_finite(r.get("would_pnl")) or 0) for r in labeled]
    shadow_ev = round(sum(pnls) / len(pnls), 4) if pnls else None
    baseline = float(NEAR_MISS_PROMOTE_MIN_EV)
    labeled_n = len(labeled)
    n = len(rows)
    ready = bool(
        key in NEAR_MISS_SOFT_ALLOW
        and n >= int(NEAR_MISS_PROMOTE_N)
        and labeled_n >= int(NEAR_MISS_PROMOTE_N)
        and shadow_ev is not None
        and shadow_ev + 1e-12 >= baseline
    )
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "soft": key if key in NEAR_MISS_SOFT_ALLOW else None,
        "n": n,
        "labeled_n": labeled_n,
        "n_to_promote": max(0, int(NEAR_MISS_PROMOTE_N) - labeled_n),
        "shadow_ev": shadow_ev,
        "baseline_ev": baseline,
        "promote_min_n": NEAR_MISS_PROMOTE_N,
        "promote_ready": ready,
        "evidence_thin": not ready,
        "label": (
            f"soft-{key}={'ready' if ready else 'THIN'} "
            f"labeled={labeled_n}/{NEAR_MISS_PROMOTE_N} ev={shadow_ev}"
        ),
        "note": (
            f"Arm soft={key} only when this band alone has "
            f"n≥{NEAR_MISS_PROMOTE_N} labeled with EV ≥ {baseline}."
        ),
    }


def near_miss_preferred_first_soft(root: str | None = None) -> dict:
    """Pick the soft band that actually has promote-ready evidence.

    Prefer z when both bands are ready. Evidence-led: if only soft-p has
    n≥30 EV≥0, return p as the first arm (do not hardcode z).
    """
    z_band = near_miss_soft_band_status(root, "z")
    p_band = near_miss_soft_band_status(root, "p")
    preferred = None
    if z_band.get("promote_ready"):
        preferred = "z"
    elif p_band.get("promote_ready"):
        preferred = "p"
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "preferred": preferred,
        "z": z_band,
        "p": p_band,
        "label": (
            f"preferred={preferred or 'none'} "
            f"z_ready={bool(z_band.get('promote_ready'))} "
            f"p_ready={bool(p_band.get('promote_ready'))}"
        ),
        "note": (
            "Ready-batch arms the preferred soft band only. Soft-p second arm "
            "(after z + M1) is separate from evidence-led first-arm soft-p."
        ),
    }


def near_miss_promote_status(root: str | None = None) -> dict:
    """Masters board: n≥30 + shadow EV ≥ baseline before staff may arm one soft gate.

    Soft allowlist is z|p only — never edge / fee floors. auto_promote=False forever.
    Aggregate promote_ready is informational; arming requires per-soft band ready.
    """
    rows = _near_miss_rows(root)
    n = len(rows)
    labeled = [r for r in rows if _finite(r.get("would_pnl")) is not None]
    pnls = [float(_finite(r.get("would_pnl")) or 0) for r in labeled]
    shadow_ev = round(sum(pnls) / len(pnls), 4) if pnls else None
    by_soft: dict[str, int] = {}
    by_bot: dict[str, int] = {}
    for r in rows:
        soft = r.get("soft")
        key = ",".join(soft) if isinstance(soft, list) else str(soft or "unknown")
        by_soft[key] = int(by_soft.get(key) or 0) + 1
        bot = str(r.get("bot") or "?")
        by_bot[bot] = int(by_bot.get(bot) or 0) + 1
    baseline = float(NEAR_MISS_PROMOTE_MIN_EV)
    ready = bool(
        n >= int(NEAR_MISS_PROMOTE_N)
        and len(labeled) >= int(NEAR_MISS_PROMOTE_N)
        and shadow_ev is not None
        and shadow_ev + 1e-12 >= baseline
    )
    if n < NEAR_MISS_PROMOTE_N or len(labeled) < NEAR_MISS_PROMOTE_N:
        decision = "reject"
    elif shadow_ev is not None and shadow_ev + 1e-12 >= baseline:
        decision = "review"
    else:
        decision = "reject"
    promote = _load(
        _path(NEAR_MISS_PROMOTE_NAME, root),
        {"paper_only": True, "staff_approved": False, "live": False, "soft": None},
    )
    soft_live = None
    if bool(promote.get("staff_approved")) and bool(promote.get("live")):
        soft = str(promote.get("soft") or "").strip().lower()
        if soft in NEAR_MISS_SOFT_ALLOW:
            soft_live = soft
    labeled_n = len(labeled)
    n_to = max(0, int(NEAR_MISS_PROMOTE_N) - labeled_n)
    preferred = near_miss_preferred_first_soft(root)
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "n": n,
        "labeled_n": labeled_n,
        "n_to_promote": n_to,
        "shadow_ev": shadow_ev,
        "baseline_ev": baseline,
        "promote_min_n": NEAR_MISS_PROMOTE_N,
        "promote_ready": ready,
        "evidence_thin": not ready,
        "decision": decision,
        "auto_promote": False,
        "code_default_live": bool(NEAR_MISS_LIVE),
        "staff_approved": bool(promote.get("staff_approved")),
        "live": bool(soft_live),
        "soft_live": soft_live,
        "soft_allow": sorted(NEAR_MISS_SOFT_ALLOW),
        "soft_p_second_arm": soft_live == "z",
        "preferred_soft": preferred.get("preferred"),
        "z_band_ready": bool((preferred.get("z") or {}).get("promote_ready")),
        "p_band_ready": bool((preferred.get("p") or {}).get("promote_ready")),
        "z_relax": NEAR_MISS_Z_RELAX if soft_live == "z" else 0.0,
        "p_relax": NEAR_MISS_P_RELAX if soft_live == "p" else 0.0,
        "by_soft": by_soft,
        "by_bot": by_bot,
        "label": (
            f"near_miss={'ready' if ready else 'THIN'} "
            f"labeled={labeled_n}/{NEAR_MISS_PROMOTE_N} "
            f"ev={shadow_ev} n_to={n_to} soft_live={soft_live or 'none'} "
            f"preferred={preferred.get('preferred') or 'none'}"
        ),
        "note": (
            "Near-miss shadow: arm the soft band that has "
            f"n≥{NEAR_MISS_PROMOTE_N} labeled EV ≥ {baseline} (prefer z when both). "
            "Soft-p second arm only after z holds M1. "
            "Never auto-promote; never lower fee/edge floors. "
            "Evidence catch-up deferred — no-force promote CLI only."
        ),
    }


def near_miss_soft_live(root: str | None = None) -> str | None:
    """Return armed soft key (z|p) or None. Code NEAR_MISS_LIVE stays False."""
    if NEAR_MISS_LIVE:
        return None  # code path never forces a soft; staff file only
    st = near_miss_promote_status(root)
    soft = st.get("soft_live")
    return str(soft) if soft else None


def near_miss_m1_holds(
    root: str | None = None,
    *,
    bots: list | None = None,
    min_n: int = 10,
) -> dict:
    """True when firm taxed M1 ≥ 0 (history or last 2 weekly scorecards)."""
    m1 = firm_taxed_m1(bots)
    exp = _finite(m1.get("expectancy_taxed"))
    n = int(m1.get("n") or 0)
    hist_ok = n >= int(min_n) and exp is not None and exp + 1e-12 >= 0.0
    store = _load(_path(WEEKLY_SCORECARD, root), {"paper_only": True, "cards": []})
    cards = [c for c in (store.get("cards") or []) if isinstance(c, dict)]
    cards = sorted(cards, key=lambda c: str(c.get("label") or ""))
    weeks = [c for c in cards if _finite(c.get("m1")) is not None][-2:]
    weeks_ok = (
        len(weeks) >= 2
        and all((_finite(c.get("m1")) or -1) + 1e-12 >= 0.0 for c in weeks)
    )
    holds = bool(hist_ok or weeks_ok)
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "holds": holds,
        "hist_ok": hist_ok,
        "weeks_ok": weeks_ok,
        "m1": exp,
        "m1_n": n,
        "min_n": int(min_n),
        "week_labels": [str(c.get("label") or "") for c in weeks],
        "note": (
            "Near-miss soft-p second arm needs firm taxed M1≥0 "
            f"(history n≥{min_n} or 2 weekly scorecards)."
        ),
    }


def near_miss_soft_p_status(
    root: str | None = None,
    *,
    bots: list | None = None,
) -> dict:
    """Soft-p second arm readiness: z already live + M1 holds + promote_ready."""
    base = near_miss_promote_status(root)
    soft = base.get("soft_live")
    z_armed = soft == "z"
    already_p = soft == "p"
    m1 = near_miss_m1_holds(root, bots=bots)
    ready = bool(
        z_armed
        and m1.get("holds")
        and base.get("promote_ready")
        and not already_p
    )
    reason = "ready — staff may arm soft-p"
    if already_p:
        reason = "soft-p already armed"
        ready = False
    elif soft is None:
        reason = "soft-z not armed yet — arm z first"
    elif soft != "z":
        reason = f"soft_live={soft} — soft-p requires soft-z first"
    elif not m1.get("holds"):
        reason = "M1 does not hold — defer soft-p"
    elif not base.get("promote_ready"):
        reason = (
            f"not promote_ready (need labeled n≥{NEAR_MISS_PROMOTE_N} "
            f"with shadow EV ≥ {NEAR_MISS_PROMOTE_MIN_EV})"
        )
    # Evidence thin ≠ armability: armed soft-p must not look THIN on SLA boards.
    p_band = near_miss_soft_band_status(root, "p")
    evidence_ready = bool(p_band.get("promote_ready") or base.get("promote_ready"))
    evidence_thin = (not already_p) and (not evidence_ready)
    if already_p:
        label = "soft-p armed"
    elif ready:
        label = "soft-p ready"
    elif evidence_thin:
        label = f"soft-p THIN — {reason[:72]}"
    else:
        label = f"soft-p deferred — {reason[:64]}"
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "soft_p_ready": ready,
        "soft_p_armed": already_p,
        "evidence_thin": evidence_thin,
        "promote_ready": bool(base.get("promote_ready")),
        "z_armed": z_armed,
        "soft_live": soft,
        "m1_holds": bool(m1.get("holds")),
        "m1": m1,
        "labeled_n": base.get("labeled_n"),
        "n_to_promote": base.get("n_to_promote"),
        "shadow_ev": base.get("shadow_ev"),
        "reason": reason,
        "label": label,
        "note": (
            "Soft-p is the second near-miss arm after soft-z holds M1. "
            "Never edge-relax; never softens floors; no force on money-path CLI."
        ),
    }


def effective_near_miss_relax(root: str | None = None) -> dict:
    """Paper z/p floor relax when staff armed a soft near-miss gate."""
    soft = near_miss_soft_live(root)
    return {
        "soft": soft,
        "z_relax": float(NEAR_MISS_Z_RELAX) if soft == "z" else 0.0,
        "p_relax": float(NEAR_MISS_P_RELAX) if soft == "p" else 0.0,
        "edge_relax": 0.0,  # forever zero — fee floors locked
        "auto_promote": False,
        "fee_floors_locked": True,
    }


def staff_promote_near_miss_soft(
    root: str | None,
    soft: str,
    *,
    note: str = "",
    force: bool = False,
    bots: list | None = None,
) -> dict:
    """Staff arm one soft near-miss gate (z|p). Requires that soft's band ready.

    Soft-p paths:
    - Evidence-led first arm when soft-p band alone is promote-ready (and soft-z
      band is not — or soft-z was armed without z-band evidence).
    - Second arm when soft-z is correctly live and firm M1 holds.
    force lifts gates (money-path CLI still defaults force=False).
    """
    key = str(soft or "").strip().lower()
    if key not in NEAR_MISS_SOFT_ALLOW:
        return {
            "ok": False,
            "live": False,
            "reason": f"soft '{key}' not allowed — use one of {sorted(NEAR_MISS_SOFT_ALLOW)}",
            "auto_promote": False,
            "fee_floors_locked": True,
        }
    summary = near_miss_promote_status(root)
    band = near_miss_soft_band_status(root, key)
    soft_live = summary.get("soft_live")
    z_band = near_miss_soft_band_status(root, "z")
    p_band = near_miss_soft_band_status(root, "p")
    if key == "p" and not force:
        # Second arm: z correctly live (z-band ready) → require M1.
        z_correct = bool(soft_live == "z" and z_band.get("promote_ready"))
        # Evidence-led first arm / correction: p-band ready and z-band thin
        # (including wrongly-armed soft-z with zero z samples).
        evidence_first_p = bool(
            p_band.get("promote_ready")
            and not z_band.get("promote_ready")
            and soft_live in (None, "z", "p")
        )
        if z_correct:
            soft_p = near_miss_soft_p_status(root, bots=bots)
            if not soft_p.get("soft_p_ready"):
                return {
                    "ok": False,
                    "live": False,
                    "staff_approved": False,
                    "reason": soft_p.get("reason") or "soft-p not ready",
                    "soft_p": soft_p,
                    "band": band,
                    "summary": summary,
                    "auto_promote": False,
                    "fee_floors_locked": True,
                    "force": False,
                }
        elif not evidence_first_p:
            soft_p = near_miss_soft_p_status(root, bots=bots)
            reason = soft_p.get("reason") or "soft-p not ready"
            if soft_live is None and not p_band.get("promote_ready"):
                reason = (
                    f"soft-p band not promote_ready (need labeled "
                    f"n≥{NEAR_MISS_PROMOTE_N} with EV ≥ {NEAR_MISS_PROMOTE_MIN_EV})"
                )
            elif soft_live is None:
                reason = "soft-z not armed yet — arm z first when z-band ready"
            return {
                "ok": False,
                "live": False,
                "staff_approved": False,
                "reason": reason,
                "soft_p": soft_p,
                "band": band,
                "summary": summary,
                "auto_promote": False,
                "fee_floors_locked": True,
                "force": False,
            }
    if not force and not band.get("promote_ready"):
        return {
            "ok": False,
            "live": False,
            "staff_approved": False,
            "reason": (
                f"soft-{key} band not promote_ready (need labeled "
                f"n≥{NEAR_MISS_PROMOTE_N} with shadow EV ≥ {NEAR_MISS_PROMOTE_MIN_EV})"
            ),
            "band": band,
            "summary": summary,
            "auto_promote": False,
            "fee_floors_locked": True,
        }
    row = {
        "paper_only": True,
        "staff_approved": True,
        "live": True,
        "soft": key,
        "at": _now(),
        "note": str(note or "")[:200],
        "shadow_n": band.get("labeled_n"),
        "shadow_ev": band.get("shadow_ev"),
        "decision": summary.get("decision"),
        "auto_promote": False,
        "code_default_live": bool(NEAR_MISS_LIVE),
        "fee_floors_locked": True,
        "z_relax": NEAR_MISS_Z_RELAX if key == "z" else 0.0,
        "p_relax": NEAR_MISS_P_RELAX if key == "p" else 0.0,
        "edge_relax": 0.0,
    }
    _save(_path(NEAR_MISS_PROMOTE_NAME, root), row)
    return {
        "ok": True,
        "live": True,
        "staff_approved": True,
        "soft": key,
        "reason": f"armed soft={key}",
        "band": near_miss_soft_band_status(root, key),
        "summary": near_miss_promote_status(root),
        "auto_promote": False,
        "fee_floors_locked": True,
    }


def staff_clear_near_miss_promote(root: str | None, *, note: str = "") -> dict:
    """Staff disarm any near-miss soft promote."""
    row = {
        "paper_only": True,
        "staff_approved": False,
        "live": False,
        "soft": None,
        "at": _now(),
        "note": str(note or "cleared")[:200],
        "auto_promote": False,
        "fee_floors_locked": True,
        "edge_relax": 0.0,
    }
    _save(_path(NEAR_MISS_PROMOTE_NAME, root), row)
    return {
        "ok": True,
        "live": False,
        "staff_approved": False,
        "reason": "disarmed",
        "summary": near_miss_promote_status(root),
        "auto_promote": False,
        "fee_floors_locked": True,
    }


def near_miss_weekly_card(root: str | None = None) -> dict:
    """
    Staff promote/reject card from shadow near-miss log.
    auto_promote stays False — never softens floors.
    """
    status = near_miss_promote_status(root)
    card = {
        "paper_only": True,
        "n": status.get("n"),
        "labeled_n": status.get("labeled_n"),
        "shadow_ev": status.get("shadow_ev"),
        "baseline_ev": status.get("baseline_ev"),
        "promote_min_n": NEAR_MISS_PROMOTE_N,
        "promote_ready": status.get("promote_ready"),
        "soft_live": status.get("soft_live"),
        "auto_promote": False,
        "decision": status.get("decision"),
        "by_soft": status.get("by_soft"),
        "by_bot": status.get("by_bot"),
        "fee_floors_locked": True,
        "note": status.get("note"),
    }
    path = _path(NEAR_MISS_WEEKLY, root)
    store = _load(path, {"paper_only": True, "cards": []})
    store.setdefault("cards", []).append({**card, "at": _now()})
    store["cards"] = store["cards"][-52:]
    store["latest"] = card
    store["last_at"] = _now()
    _save(path, store)
    return card


# ---- Skip-regret weekly review (Phase 8 helper loop) -----------------------

def skip_regret_weekly_card(
    root: str | None = None,
    *,
    label: str | None = None,
) -> dict:
    """Weekly twin of soft-gate skip regret — never loosens fee floors."""
    try:
        import desk_top25
        summary = desk_top25.skip_regret_summary(root)
    except Exception:
        summary = {
            "n": 0, "labeled_n": 0, "avg_would_pnl": None,
            "green_twin": False, "loosen_soft_gates": False,
        }
    n = int(summary.get("labeled_n") or 0)
    green = bool(summary.get("green_twin"))
    if n < 20:
        decision = "reject"
    elif green:
        decision = "review"  # staff may loosen one non-fee soft gate
    else:
        decision = "reject"
    day = label or _chicago_day()
    card = {
        "paper_only": True,
        "label": day,
        "n": int(summary.get("n") or 0),
        "labeled_n": n,
        "avg_would_pnl": summary.get("avg_would_pnl"),
        "win_rate": summary.get("win_rate"),
        "green_twin": green,
        "promote_min_n": 20,
        "auto_promote": False,
        "loosen_soft_gates": False,  # never auto; staff only when green_twin
        "decision": decision,
        "fee_floors_locked": True,
        "note": (
            "Skip-regret twin: only consider loosening a non-fee soft gate after "
            "n≥20 labeled with avg would_pnl ≥ 0. Fee floors stay locked. No auto-promote."
        ),
    }
    path = _path(SKIP_REGRET_WEEKLY, root)
    store = _load(path, {"paper_only": True, "cards": []})
    store.setdefault("cards", []).append({**card, "at": _now()})
    store["cards"] = store["cards"][-52:]
    store["latest"] = card
    store["last_at"] = _now()
    _save(path, store)
    return card


def latest_skip_regret_weekly(root: str | None = None) -> dict | None:
    store = _load(
        _path(SKIP_REGRET_WEEKLY, root),
        {"paper_only": True, "cards": [], "latest": None},
    )
    latest = store.get("latest")
    return latest if isinstance(latest, dict) else None


SKIP_REGRET_SOFT_ALLOW = frozenset({"z", "p", "cushion", "depth", "latency", "news"})
SKIP_REGRET_FEE_GATES = frozenset({"edge", "fee", "min_edge", "venue_edge", "floor"})
MAX_SKIP_REGRET_DECISIONS = 200


def skip_regret_candidates(root: str | None = None) -> dict:
    """Non-fee soft-gate skip-regret candidates (make-money step 396). Fee forever out."""
    try:
        import desk_top25
        summary = desk_top25.skip_regret_summary(root)
        rows = [
            r for r in (desk_top25.load_top25(root).get("skip_regret") or [])
            if isinstance(r, dict)
        ]
    except Exception:
        summary = {"n": 0, "labeled_n": 0}
        rows = []
    buckets: dict[str, list] = {}
    for r in rows:
        if r.get("would_pnl") is None:
            continue
        key = str(r.get("soft_gate") or "").strip().lower() or "unknown"
        buckets.setdefault(key, []).append(float(r["would_pnl"]))
    candidates = []
    rejected_fee = []
    for soft, pnls in sorted(buckets.items()):
        if soft in SKIP_REGRET_FEE_GATES or "edge" in soft or "fee" in soft:
            rejected_fee.append(soft)
            continue
        n = len(pnls)
        avg = round(sum(pnls) / n, 4) if n else None
        candidates.append({
            "soft": soft,
            "n": n,
            "avg_would_pnl": avg,
            "fee_gate": False,
        })
    weekly = latest_skip_regret_weekly(root) or {}
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "auto_promote": False,
        "candidates": candidates,
        "rejected_fee_gates": sorted(set(rejected_fee)),
        "soft_allow": sorted(SKIP_REGRET_SOFT_ALLOW),
        "weekly_decision": weekly.get("decision"),
        "green_twin": bool(weekly.get("green_twin") or summary.get("green_twin")),
        "labeled_n": int(summary.get("labeled_n") or 0),
        "note": (
            "Skip-regret candidates filtered to Z/P/DEPTH/NEWS timing only. "
            "Fee/edge floors never appear as loosen targets (step 452 lock)."
        ),
    }


def staff_log_skip_regret_decision(
    root: str | None,
    *,
    decision: str,
    soft: str = "",
    who: str = "",
    note: str = "",
) -> dict:
    """Staff accept/defer for skip-regret soft-gate review. Never softens fee floors."""
    dec = str(decision or "").strip().lower()
    if dec not in ("accept", "defer"):
        return {
            "ok": False,
            "reason": "decision must be accept|defer",
            "auto_promote": False,
            "fee_floors_locked": True,
            "paper_only": True,
        }
    soft_key = str(soft or "").strip().lower()
    if soft_key and (
        soft_key in SKIP_REGRET_FEE_GATES
        or "edge" in soft_key
        or "fee" in soft_key
    ):
        return {
            "ok": False,
            "reason": f"soft '{soft_key}' is a fee/edge gate — forever forbidden",
            "auto_promote": False,
            "fee_floors_locked": True,
            "paper_only": True,
            "loosen_soft_gates": False,
        }
    weekly = latest_skip_regret_weekly(root) or skip_regret_weekly_card(root)
    if dec == "accept" and not weekly.get("green_twin"):
        return {
            "ok": False,
            "reason": "accept requires green_twin weekly card (n≥20 avg would_pnl≥0)",
            "weekly": weekly,
            "auto_promote": False,
            "fee_floors_locked": True,
            "paper_only": True,
            "loosen_soft_gates": False,
        }
    row = {
        "at": _now(),
        "decision": dec,
        "soft": soft_key or None,
        "who": str(who or "")[:40],
        "note": str(note or "")[:200],
        "weekly_label": weekly.get("label"),
        "green_twin": bool(weekly.get("green_twin")),
        "loosen_soft_gates": False,  # log only — never auto-apply soft loosen
        "auto_promote": False,
        "fee_floors_locked": True,
        "paper_only": True,
    }
    path = _path(SKIP_REGRET_DECISIONS, root)
    store = _load(path, {"paper_only": True, "rows": [], "latest": None})
    rows = [r for r in (store.get("rows") or []) if isinstance(r, dict)]
    rows.append(row)
    store["rows"] = rows[-MAX_SKIP_REGRET_DECISIONS:]
    store["latest"] = row
    store["last_at"] = row["at"]
    _save(path, store)
    return {
        "ok": True,
        "row": row,
        "n": len(store["rows"]),
        "auto_promote": False,
        "fee_floors_locked": True,
        "paper_only": True,
        "loosen_soft_gates": False,
        "reason": f"logged {dec}" + (f" soft={soft_key}" if soft_key else ""),
    }


def skip_regret_decision_log(root: str | None = None) -> dict:
    store = _load(
        _path(SKIP_REGRET_DECISIONS, root),
        {"paper_only": True, "rows": [], "latest": None},
    )
    rows = [r for r in (store.get("rows") or []) if isinstance(r, dict)]
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "auto_promote": False,
        "loosen_soft_gates": False,
        "n": len(rows),
        "accepts": sum(1 for r in rows if r.get("decision") == "accept"),
        "defers": sum(1 for r in rows if r.get("decision") == "defer"),
        "latest": store.get("latest") if isinstance(store.get("latest"), dict) else None,
        "note": (
            "Staff skip-regret accept/defer log. Never auto-loosens soft gates; "
            "fee floors locked forever."
        ),
    }


# ---- Daily R budget (settle-only after target) -----------------------------

def daily_r_budget_for(bot_id: str) -> float:
    return float(DAILY_R_BUDGET.get(str(bot_id), 1.0))


def daily_r_status(
    bot_id: str,
    today_pnl=None,
    *,
    r_usd: float = DAILY_R_USD,
) -> dict:
    """Chicago-day R usage. settle_only when today PnL ≥ budget×R (lock the win)."""
    today = _finite(today_pnl)
    budget_r = daily_r_budget_for(bot_id)
    r = float(r_usd) if _finite(r_usd) and float(r_usd) > 0 else DAILY_R_USD
    target_usd = round(budget_r * r, 2)
    used_r = round(today / r, 4) if today is not None else None
    settle_only = bool(today is not None and today + 1e-12 >= target_usd)
    return {
        "paper_only": True,
        "bot": str(bot_id),
        "r_usd": r,
        "budget_r": budget_r,
        "target_usd": target_usd,
        "today_pnl": today,
        "used_r": used_r,
        "settle_only": settle_only,
        "entries_blocked": settle_only,
        "fee_floors_locked": True,
        "note": (
            f"Daily R budget {budget_r}R (${target_usd:.0f}): "
            "after target → settle-only (exits stay on). No profit guarantee."
        ),
    }


def daily_r_blocks(bot_id: str, today_pnl=None, *, r_usd: float = DAILY_R_USD) -> str:
    """Non-empty reason when tower is settle-only after hitting daily R."""
    status = daily_r_status(bot_id, today_pnl, r_usd=r_usd)
    if not status.get("settle_only"):
        return ""
    return (
        f"daily R budget hit for {bot_id}: "
        f"today ${float(status.get('today_pnl') or 0):.2f} ≥ "
        f"{status.get('budget_r')}R (${status.get('target_usd'):.0f}) — settle-only"
    )


def capture_daily_r_board(
    root: str | None,
    bots: list | None = None,
    *,
    label: str | None = None,
    r_usd: float = DAILY_R_USD,
) -> dict:
    """Persist per-tower daily R card for Masters / hillclimb review."""
    day = label or _chicago_day()
    towers = {}
    settle_only = []
    for bot in bots or []:
        if not isinstance(bot, dict):
            continue
        bot_id = str(bot.get("id") or "")
        if not bot_id:
            continue
        row = daily_r_status(bot_id, bot.get("today"), r_usd=r_usd)
        towers[bot_id] = row
        if row.get("settle_only"):
            settle_only.append(bot_id)
    board = {
        "paper_only": True,
        "label": day,
        "captured_at": _now(),
        "r_usd": float(r_usd),
        "towers": towers,
        "settle_only": sorted(settle_only),
        "fee_floors_locked": True,
        "note": "Daily R board — settle-only after tower hits budget×R. Exits remain on.",
    }
    path = _path(DAILY_R_NAME, root)
    store = _load(path, {"paper_only": True, "cards": [], "latest": None})
    cards = [c for c in (store.get("cards") or []) if isinstance(c, dict)]
    cards = [c for c in cards if str(c.get("label") or "") != day]
    cards.append(board)
    store["cards"] = cards[-60:]
    store["latest"] = board
    _save(path, store)
    return board


def latest_daily_r_board(root: str | None = None) -> dict | None:
    store = _load(_path(DAILY_R_NAME, root), {"paper_only": True, "latest": None})
    latest = store.get("latest")
    return latest if isinstance(latest, dict) else None


# ---- Sports green_boost gate (Phase 5) -------------------------------------

def _sports_closed_history_from_account(root: str | None = None) -> list[dict]:
    """Closed sports fills as history rows for firm_taxed_m1 (paper observe)."""
    path = _sports_account_path(root)
    try:
        with open(path, encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, json.JSONDecodeError, TypeError):
        return []
    out: list[dict] = []
    for crow in state.get("closed") or []:
        if not isinstance(crow, dict):
            continue
        pnl = _finite(crow.get("pnl"))
        if pnl is None:
            continue
        contracts = _finite(crow.get("contracts"))
        row = {
            "pnl": pnl,
            "contracts": contracts if contracts is not None else 1.0,
            "ticker": crow.get("ticker"),
            "closed": crow.get("closed"),
            "exit": crow.get("exit"),
            "league": crow.get("league"),
        }
        out.append(row)
    return out


def _bots_with_sports_history(
    root: str | None = None,
    bots: list | None = None,
) -> list:
    """Ensure sports-gap history is present for M1 / green_boost observes.

    gap_bot and some pulse paths call green_boost without a desk snapshot —
    without this hydrate, sports_m1_n stays 0 despite real closed fills.
    Never invents PnL; reads sports-gap-paper/state.json only.
    """
    base: list = [b for b in (bots or []) if isinstance(b, dict)]
    sports = next((b for b in base if str(b.get("id") or "") == "sports-gap"), None)
    hist = list((sports or {}).get("history") or []) if sports else []
    if hist:
        return base
    account_hist = _sports_closed_history_from_account(root)
    if not account_hist:
        return base
    if sports is None:
        base = list(base) + [{
            "id": "sports-gap",
            "history": account_hist,
            "paper_only": True,
        }]
    else:
        sports = dict(sports)
        sports["history"] = account_hist
        base = [
            sports if str(b.get("id") or "") == "sports-gap" else b
            for b in base
        ]
    return base


def _chicago_day_label(closed_at) -> str | None:
    """YYYY-MM-DD Chicago day from a sports closed stamp or ISO string."""
    raw = str(closed_at or "").strip()
    if not raw:
        return None
    # Common sports log: "2026-11-08 00:30:49 CT"
    if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
        return raw[:10]
    try:
        from datetime import datetime, timezone
        from zoneinfo import ZoneInfo
        text = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d")
    except Exception:
        return None


def _weekly_scorecard_upsert_cards(cards: list, card: dict) -> list:
    """Keep one card per label — densify must refresh the day, not append clones."""
    label = str((card or {}).get("label") or "").strip()
    out: list = []
    replaced = False
    for existing in cards or []:
        if not isinstance(existing, dict):
            continue
        if label and str(existing.get("label") or "").strip() == label:
            if not replaced:
                out.append(card)
                replaced = True
            continue
        out.append(existing)
    if not replaced:
        out.append(card)
    return out[-52:]


def _weekly_scorecard_unique_by_label(cards: list) -> list:
    """Latest card per label (by captured_at), ordered by label ascending."""
    best: dict[str, dict] = {}
    order: list[str] = []
    for card in cards or []:
        if not isinstance(card, dict):
            continue
        label = str(card.get("label") or "").strip()
        if not label:
            continue
        prev = best.get(label)
        if prev is None:
            best[label] = card
            order.append(label)
            continue
        if str(card.get("captured_at") or "") >= str(prev.get("captured_at") or ""):
            best[label] = card
    labels = sorted(order)
    return [best[lab] for lab in labels]


def repair_weekly_sports_m1(root: str | None = None, *, fill_tax: float = 0.01) -> dict:
    """Backfill / refresh sports_m1 on weekly/day scorecards from that day's closes.

    Cards captured without sports history left sports_m1=None and starved
    green_boost weeks_ok. Also refresh when a card already has sports_m1 but
    n/expectancy no longer matches that Chicago day's closes (stale copy from
    a prior day DROPs honest week evidence). Day-sliced taxed expectancy only —
    no invent. Observe only; never LIVE; never arms.

    Compacts duplicate same-label cards left by pre-upsert densify appends so
    green_boost cannot count one Chicago day as multiple weeks.
    """
    path = _path(WEEKLY_SCORECARD, root)
    store = _load(path, {"paper_only": True, "cards": []})
    cards = [c for c in (store.get("cards") or []) if isinstance(c, dict)]
    if not cards:
        return {
            "ok": True,
            "repaired": 0,
            "kept": 0,
            "compacted": 0,
            "paper_only": True,
            "observe_only": True,
            "auto_promote": False,
            "note": "no weekly cards",
        }
    before_n = len(cards)
    cards = _weekly_scorecard_unique_by_label(cards)
    compacted = max(0, before_n - len(cards))
    hist = _sports_closed_history_from_account(root)
    by_day: dict[str, list[float]] = {}
    for row in hist:
        day = _chicago_day_label(row.get("closed"))
        if not day:
            continue
        pnl = _finite(row.get("pnl"))
        if pnl is None:
            continue
        contracts = _finite(row.get("contracts")) or 1.0
        taxed = pnl - float(fill_tax) * max(1.0, contracts)
        by_day.setdefault(day, []).append(taxed)
    repaired = 0
    for card in cards:
        label = str(card.get("label") or "").strip()
        day_pnls = by_day.get(label)
        if not day_pnls:
            continue
        new_m1 = round(sum(day_pnls) / len(day_pnls), 4)
        new_n = len(day_pnls)
        old_m1 = _finite(card.get("sports_m1"))
        try:
            old_n = int(card.get("sports_m1_n") or 0)
        except (TypeError, ValueError):
            old_n = 0
        # Skip only when already honest vs today's closes.
        if (
            old_m1 is not None
            and old_n == new_n
            and abs(float(old_m1) - float(new_m1)) < 1e-9
        ):
            continue
        card["sports_m1"] = new_m1
        card["sports_m1_n"] = new_n
        card["sports_m1_repaired"] = True
        repaired += 1
    if repaired or compacted:
        store["cards"] = cards[-52:]
        if isinstance(store.get("latest"), dict):
            latest_label = str((store.get("latest") or {}).get("label") or "")
            for card in reversed(cards):
                if str(card.get("label") or "") == latest_label:
                    store["latest"] = card
                    break
        store["paper_only"] = True
        _save(path, store)
    return {
        "ok": True,
        "repaired": repaired,
        "kept": len(cards),
        "compacted": compacted,
        "paper_only": True,
        "observe_only": True,
        "auto_promote": False,
        "live": False,
        "note": (
            "Backfilled/refreshed sports_m1 from Chicago-day closed fills "
            "(missing or stale n/expectancy); compacted same-label clones. "
            "Never LIVE; never arms."
        ),
    }


def sports_green_boost_status(
    root: str | None = None,
    *,
    bots: list | None = None,
) -> dict:
    """green_boost=1 only when sports M1≥0 for 2 Chicago weeks and CLV≥52%.

    Default boost stays 0 until ready. auto_promote=False forever.
    Hydrates sports-gap history from account when bots omit it (gap_bot path).
    """
    bots = _bots_with_sports_history(root, bots)
    m1 = firm_taxed_m1(bots)
    sports = next(
        (r for r in (m1.get("by_tower") or []) if r.get("bot") == "sports-gap"),
        None,
    )
    sports_exp = _finite((sports or {}).get("expectancy_taxed"))
    sports_n = int((sports or {}).get("n") or 0)
    clv = {"n": 0, "beat_close_rate": None}
    try:
        import desk_more
        clv = desk_more.clv_summary(root)
    except Exception:
        pass
    clv_n = int(clv.get("n") or 0)
    clv_rate = _finite(clv.get("beat_close_rate"))
    # Last two unique-label scorecards with sports_m1.
    # Densify used to append same-day clones; never count one label twice.
    store = _load(_path(WEEKLY_SCORECARD, root), {"paper_only": True, "cards": []})
    cards = _weekly_scorecard_unique_by_label(
        [c for c in (store.get("cards") or []) if isinstance(c, dict)]
    )
    sports_weeks = [
        c for c in cards
        if _finite(c.get("sports_m1")) is not None
    ][-SPORTS_GREEN_BOOST_WEEKS:]
    weeks_ok = (
        len(sports_weeks) >= SPORTS_GREEN_BOOST_WEEKS
        and all(
            (_finite(c.get("sports_m1")) or -1) + 1e-12 >= 0.0
            for c in sports_weeks
        )
    )
    hist_ok = sports_n >= SPORTS_M1_MIN_N and sports_exp is not None and sports_exp + 1e-12 >= 0.0
    clv_ok = (
        clv_n >= SPORTS_CLV_MIN_N
        and clv_rate is not None
        and clv_rate + 1e-12 >= SPORTS_CLV_BAR
    )
    ready = bool(weeks_ok and hist_ok and clv_ok)
    promote = _load(
        _path(SPORTS_GREEN_BOOST_PROMOTE, root),
        {"paper_only": True, "staff_approved": False, "live": False},
    )
    staff_armed = bool(promote.get("staff_approved")) and bool(promote.get("live"))
    # Ready gate or explicit staff arm (force path when evidence thin).
    boost = 1 if (ready or staff_armed) else 0
    missing = []
    if not weeks_ok:
        # Distinguish thin week count vs enough weeks but sports_m1<0 —
        # "weeks 2/2" falsely reads as the weeks bar already cleared.
        if len(sports_weeks) < SPORTS_GREEN_BOOST_WEEKS:
            missing.append(f"weeks {len(sports_weeks)}/{SPORTS_GREEN_BOOST_WEEKS}")
        else:
            neg = [
                f"{c.get('label')}:{_finite(c.get('sports_m1'))}"
                for c in sports_weeks
                if (_finite(c.get("sports_m1")) or -1) + 1e-12 < 0.0
            ]
            missing.append(
                f"weeks_m1<0 ({','.join(neg)})"
                if neg else f"weeks {len(sports_weeks)}/{SPORTS_GREEN_BOOST_WEEKS}"
            )
    if not hist_ok:
        # Same board-truth class as weeks (#428): "sports_m1_n 30/20" reads as
        # the n bar cleared when hist actually fails on expectancy<0 / missing.
        if sports_n < SPORTS_M1_MIN_N:
            missing.append(f"sports_m1_n {sports_n}/{SPORTS_M1_MIN_N}")
        elif sports_exp is None:
            missing.append(f"sports_m1_exp missing (n={sports_n})")
        else:
            missing.append(f"sports_m1<0 ({sports_exp})")
    if not clv_ok:
        # Mirror weeks/hist: n-met + rate fail must not look like clv 25/20 cleared.
        if clv_n < SPORTS_CLV_MIN_N:
            missing.append(f"clv {clv_n}/{SPORTS_CLV_MIN_N} rate={clv_rate}")
        elif clv_rate is None:
            missing.append(f"clv_rate missing (n={clv_n})")
        else:
            missing.append(
                f"clv_rate<{SPORTS_CLV_BAR:g} ({clv_rate} n={clv_n})"
            )
    evidence_thin = not ready
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "ready": ready,
        "evidence_thin": evidence_thin,
        "missing": missing,
        "staff_approved": staff_armed,
        "staff_armed": staff_armed,
        "green_boost": boost,
        "sports_m1": sports_exp,
        "sports_m1_n": sports_n,
        "hist_ok": hist_ok,
        "clv_n": clv_n,
        "clv_beat_rate": clv_rate,
        "clv_bar": SPORTS_CLV_BAR,
        "clv_ok": clv_ok,
        "weeks_n": len(sports_weeks),
        "weeks_required": SPORTS_GREEN_BOOST_WEEKS,
        "weeks_ok": weeks_ok,
        "week_labels": [str(c.get("label") or "") for c in sports_weeks],
        "label": (
            f"green_boost={'1' if boost else '0'} "
            f"{'ready' if ready else 'THIN'} "
            f"armed={staff_armed} missing={','.join(missing) or 'none'}"
        ),
        "note": (
            "Sports selective +1 after 2 Chicago weeks sports M1≥0, "
            f"history n≥{SPORTS_M1_MIN_N}, and CLV beat-close ≥{SPORTS_CLV_BAR:.0%} "
            f"(n≥{SPORTS_CLV_MIN_N}), or staff_set_sports_green_boost. Default boost=0. "
            "Evidence catch-up deferred — no-force CLI only when ready."
        ),
    }


def sports_green_boost(root: str | None = None, bots: list | None = None) -> int:
    """Runtime boost for selective_max_buys — 0 until gate ready or staff arm."""
    try:
        return int(sports_green_boost_status(root, bots=bots).get("green_boost") or 0)
    except Exception:
        return 0


def staff_set_sports_green_boost(
    root: str | None,
    enabled: bool,
    *,
    note: str = "",
    force: bool = False,
    bots: list | None = None,
) -> dict:
    """Staff gate to arm/disarm sports selective +1 boost.

    Enabling requires readiness (2w M1≥0 + CLV≥52%) unless force=True.
    Never auto-called. Does not soften fee floors.
    """
    status = sports_green_boost_status(root, bots=bots)
    if enabled and not force and not status.get("ready"):
        return {
            "ok": False,
            "live": False,
            "staff_approved": False,
            "green_boost": int(status.get("green_boost") or 0),
            "reason": (
                "not ready (need 2 Chicago weeks sports M1≥0, "
                f"hist n≥{SPORTS_M1_MIN_N}, CLV≥{SPORTS_CLV_BAR:.0%})"
            ),
            "status": status,
            "auto_promote": False,
            "fee_floors_locked": True,
        }
    row = {
        "paper_only": True,
        "staff_approved": bool(enabled),
        "live": bool(enabled),
        "at": _now(),
        "note": str(note or "")[:200],
        "ready_at_arm": bool(status.get("ready")),
        "auto_promote": False,
        "fee_floors_locked": True,
    }
    _save(_path(SPORTS_GREEN_BOOST_PROMOTE, root), row)
    after = sports_green_boost_status(root, bots=bots)
    return {
        "ok": True,
        "live": bool(enabled),
        "staff_approved": bool(enabled),
        "green_boost": int(after.get("green_boost") or 0),
        "reason": "armed" if enabled else "disarmed",
        "status": after,
        "auto_promote": False,
        "fee_floors_locked": True,
    }


# ---- Green-or-gone Masters flags (Phase 7) ---------------------------------

def green_or_gone_status(bots: list | None = None) -> dict:
    """Flag towers that are red today with open risk or Gate A false on losers."""
    flags = []
    for bot in bots or []:
        if not isinstance(bot, dict):
            continue
        bot_id = str(bot.get("id") or "")
        if not bot_id:
            continue
        today = _finite(bot.get("today"))
        open_risk = float(_finite(bot.get("open_risk")) or 0.0)
        ga = bot.get("gate_a") if isinstance(bot.get("gate_a"), dict) else {}
        gate_ready = bool(ga.get("ready"))
        reasons = []
        if today is not None and today < 0 and open_risk > 0:
            reasons.append("red_today_with_open_risk")
        if bot_id in LOSER_IDS and today is not None and today < 0:
            reasons.append("loser_red")
        if bot_id in LOSER_IDS and not gate_ready and open_risk > 0:
            reasons.append("loser_gate_a_false_with_risk")
        if reasons:
            flags.append({
                "bot": bot_id,
                "today": today,
                "open_risk": round(open_risk, 2),
                "gate_a": gate_ready,
                "reasons": reasons,
                "action": "starve_or_exit" if open_risk > 0 else "pause_entries",
            })
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "flagged_n": len(flags),
        "flags": flags,
        "pass": len(flags) == 0,
        "label": (
            f"green_or_gone={'pass' if not flags else 'FLAG'} "
            f"flagged={len(flags)}"
        ),
        "note": (
            "Green-or-gone: red towers with open risk / loser Gate A false get "
            "starve-or-exit flags on Masters. No volume expand."
        ),
    }


# ---- Sports CLV completeness -----------------------------------------------

def _clv_has_entry(row: dict) -> bool:
    return row.get("fair_entry") is not None or row.get("entry_fair") is not None


def _clv_has_close(row: dict) -> bool:
    return row.get("fair_close") is not None or row.get("close_fair") is not None


def _clv_is_settled_row(row: dict) -> bool:
    """Settled when exit says settle OR any close/clv field is present."""
    exit_r = str(row.get("exit") or row.get("exit_reason") or "").lower()
    if "settled" in exit_r or exit_r.startswith("settle"):
        return True
    if row.get("clv") is not None or _clv_has_close(row):
        return True
    return False


def clv_row_complete(row: dict | None) -> bool:
    """True when a sports CLV journal row has the fields needed for M2/CLV learning.

    Open/pre-settle rows need entry fair only. Settled rows fail-closed unless
    fair_entry + close_fair (or aliases) + clv are all present.
    """
    if not isinstance(row, dict):
        return False
    if not _clv_has_entry(row):
        return False
    if _clv_is_settled_row(row):
        return _clv_has_close(row) and row.get("clv") is not None
    return True


def clv_completeness(root: str | None = None) -> dict:
    try:
        import desk_more
        state = desk_more.load_clv(root)
        rows = [r for r in (state.get("rows") or []) if isinstance(r, dict)]
    except Exception:
        rows = []
    ok = sum(1 for r in rows if clv_row_complete(r))
    n = len(rows)
    settled = [r for r in rows if _clv_is_settled_row(r)]
    settled_ok = sum(1 for r in settled if clv_row_complete(r))
    missing_close = [
        {
            "ticker": r.get("ticker"),
            "exit": r.get("exit") or r.get("exit_reason"),
            "has_entry": _clv_has_entry(r),
            "has_close": _clv_has_close(r),
            "has_clv": r.get("clv") is not None,
        }
        for r in settled
        if not _clv_has_close(r)
    ][:12]
    alert = "settle_missing_close_fair" if missing_close else None
    settled_pass = (not settled) or settled_ok == len(settled)
    return {
        "paper_only": True,
        "n": n,
        "complete": ok,
        "settled_n": len(settled),
        "settled_complete": settled_ok,
        "rate": round(ok / n, 4) if n else None,
        "settled_rate": round(settled_ok / len(settled), 4) if settled else None,
        "pass": (n == 0) or (ok == n and settled_pass),
        "fail_closed": True,
        "alert": alert,
        "missing_close_fair_n": len(missing_close),
        "missing_close_fair_sample": missing_close,
        "note": (
            "Every sports settle must log fair_entry + close_fair + clv. "
            "Incomplete settled rows fail closed."
        ),
    }


def _shadow_exit_mark_by_ticker(root: str | None = None) -> dict[str, dict]:
    """Ticker → organic mid-open bid from time-final then hard-stop journals (non-wipe only)."""
    out: dict[str, dict] = {}
    for name, src in (
        (SPORTS_TIME_FINAL_SHADOW, "time_final"),
        (SPORTS_HARD_STOP_SHADOW, "hard_stop"),
    ):
        try:
            store = _load(_path(name, root), {"rows": []})
        except Exception:
            continue
        for row in store.get("rows") or []:
            if not isinstance(row, dict):
                continue
            ticker = str(row.get("ticker") or "").strip()
            if not ticker or ticker in out:
                continue
            bid = _finite(row.get("bid"))
            if bid is None or not (0.0 < float(bid) < 1.0):
                continue
            out[ticker] = {
                "bid": float(bid),
                "source": src,
                "side": row.get("side"),
            }
    return out


def _clv_close_is_binary_proxy(row: dict) -> bool:
    """True when close is an exact 0/1 settle wipe (or tagged binary)."""
    kind = str(row.get("clv_kind") or "").strip().lower()
    if kind == "binary":
        return True
    fc = _finite(row.get("fair_close"))
    if fc is None:
        fc = _finite(row.get("close_fair"))
    return fc is not None and (abs(float(fc) - 0.0) < 1e-12 or abs(float(fc) - 1.0) < 1e-12)


def repair_clv_completeness(root: str | None = None) -> dict:
    """Observe repair: recompute clv when both fairs exist; upgrade wipe closes from exit journals.

    Fail-closed when fair_entry or close_fair is missing. Never arms green_boost. Never LIVE.
    Never invents marks — only rewrites binary 0/1 closes when HS/t-final journals hold bid ∈ (0,1).
    """
    try:
        import desk_more
        state = desk_more.load_clv(root)
        rows = list(state.get("rows") or [])
    except Exception:
        return {
            "ok": False,
            "repaired": 0,
            "skipped": 0,
            "reason": "no clv store",
            "paper_only": True,
            "auto_promote": False,
            "fee_floors_locked": True,
        }
    marks = _shadow_exit_mark_by_ticker(root)
    repaired = 0
    mark_upgraded = 0
    skipped = 0
    out: list = []
    for row in rows:
        if not isinstance(row, dict):
            out.append(row)
            continue
        item = dict(row)
        if not _clv_is_settled_row(item):
            out.append(item)
            continue
        # Upgrade binary wipe closes from organic HS/t-final mid-open marks.
        if _clv_has_entry(item) and _clv_close_is_binary_proxy(item):
            ticker = str(item.get("ticker") or "").strip()
            mark = marks.get(ticker) if ticker else None
            if mark and 0.0 < float(mark["bid"]) < 1.0:
                fe = _finite(item.get("fair_entry"))
                if fe is None:
                    fe = _finite(item.get("entry_fair"))
                fc = float(mark["bid"])
                item["fair_close"] = round(fc, 4)
                item["close_fair"] = round(fc, 4)
                if fe is not None:
                    item["clv"] = round(float(fe) - fc, 4)
                item["clv_kind"] = "line"
                item["repaired_at"] = _now()
                item["repair_note"] = (
                    f"clv catch-up from {mark['source']} mark "
                    f"(replaced wipe close; never invent)"
                )
                repaired += 1
                mark_upgraded += 1
                out.append(item)
                continue
        if clv_row_complete(item) and not _clv_close_is_binary_proxy(item):
            out.append(item)
            continue
        if not _clv_has_entry(item):
            skipped += 1
            out.append(item)
            continue
        # Missing close → leave incomplete (fail-closed). Never invent binary 0/1.
        if not _clv_has_close(item):
            skipped += 1
            out.append(item)
            continue
        fe = _finite(item.get("fair_entry"))
        if fe is None:
            fe = _finite(item.get("entry_fair"))
        fc = _finite(item.get("fair_close"))
        if fc is None:
            fc = _finite(item.get("close_fair"))
        if fe is None or fc is None:
            skipped += 1
            out.append(item)
            continue
        if item.get("clv") is None:
            item["clv"] = round(float(fe) - float(fc), 4)
        item["repaired_at"] = _now()
        item["repair_note"] = "clv-completeness catch-up (line only)"
        if not item.get("clv_kind"):
            item["clv_kind"] = "line"
        repaired += 1
        out.append(item)
    if repaired:
        try:
            import desk_more
            state["rows"] = out
            state["last_at"] = _now()
            desk_more.save_clv(state, root)
        except Exception:
            return {
                "ok": False,
                "repaired": 0,
                "skipped": skipped,
                "reason": "save failed",
                "paper_only": True,
                "auto_promote": False,
                "fee_floors_locked": True,
            }
    board = clv_completeness(root)
    return {
        "ok": True,
        "repaired": repaired,
        "mark_upgraded": mark_upgraded,
        "skipped": skipped,
        "completeness": board,
        "paper_only": True,
        "observe_only": True,
        "auto_promote": False,
        "fee_floors_locked": True,
        "live": False,
        "note": (
            "CLV completeness repair — observe only; upgrades wipe closes from "
            "HS/t-final marks; never arms green_boost; never invents."
        ),
    }



# ---- INX band research harness (no live change) ----------------------------

def inx_band_research_score(rows: list, *, lo: float, hi: float, fill_tax: float = 0.01) -> dict:
    """Fee-aware expectancy for settles whose ask sat in [lo, hi). Research only."""
    pnls = []
    for h in rows or []:
        if not isinstance(h, dict):
            continue
        ask = _finite(h.get("ask") if h.get("ask") is not None else h.get("entry_ask"))
        if ask is None or not (lo - 1e-12 <= ask < hi - 1e-12):
            continue
        pnl = _finite(h.get("pnl") if h.get("pnl") is not None else h.get("pnl_usd"))
        if pnl is None:
            continue
        contracts = _finite(h.get("contracts")) or 1.0
        pnls.append(pnl - fill_tax * max(1.0, contracts))
    n = len(pnls)
    if n <= 0:
        return {"n": 0, "expectancy_taxed": None, "hit_rate": None}
    hits = sum(1 for p in pnls if p > 0)
    return {
        "n": n,
        "expectancy_taxed": round(sum(pnls) / n, 4),
        "hit_rate": round(hits / n, 4),
    }


def inx_band_from_id(band_id: str | None) -> dict:
    bid = str(band_id or INX_LIVE_BAND_DEFAULT)
    for b in INX_RESEARCH_BANDS:
        if b["id"] == bid:
            return {"id": b["id"], "lo": float(b["lo"]), "hi": float(b["hi"])}
    return {"id": "80_90", "lo": 0.80, "hi": 0.90}


def inx_live_band(root: str | None = None) -> dict:
    """Effective INX ask band: staff promote artifact or default 80–90."""
    promote = _load(
        _path(INX_BAND_PROMOTE, root),
        {"paper_only": True, "staff_approved": False, "band_id": INX_LIVE_BAND_DEFAULT},
    )
    if bool(promote.get("staff_approved")) and promote.get("band_id"):
        base = inx_band_from_id(str(promote.get("band_id")))
        return {
            **base,
            "staff_approved": True,
            "source": "staff_promote",
            "promoted_at": promote.get("at"),
            "note": promote.get("note") or "",
            "fee_floors_locked": True,
            "live_changed": base["id"] != INX_LIVE_BAND_DEFAULT,
        }
    base = inx_band_from_id(INX_LIVE_BAND_DEFAULT)
    return {
        **base,
        "staff_approved": False,
        "source": "default",
        "fee_floors_locked": True,
        "live_changed": False,
    }


def effective_inx_ask_band(root: str | None, cfg: dict | None = None) -> dict:
    """Band for bots: staff promote overrides CFG; else keep config.json values."""
    cfg = cfg or {}
    live = inx_live_band(root)
    if live.get("staff_approved"):
        return {
            "lo": float(live["lo"]),
            "hi": float(live["hi"]),
            "id": live["id"],
            "source": "staff_promote",
            "staff_approved": True,
            "fee_floors_locked": True,
        }
    lo = _finite(cfg.get("band_min_ask"))
    hi = _finite(cfg.get("band_max_ask"))
    if lo is None:
        lo = 0.80
    if hi is None:
        hi = 0.90
    return {
        "lo": float(lo),
        "hi": float(hi),
        "id": INX_LIVE_BAND_DEFAULT,
        "source": "config",
        "staff_approved": False,
        "fee_floors_locked": True,
    }


def inx_history_from_bots(bots: list | None = None) -> list:
    """Collect kalshi-sp / kalshi-sized settle rows for band research (ask+pnl)."""
    rows = []
    for bot in bots or []:
        if not isinstance(bot, dict):
            continue
        if str(bot.get("id") or "") not in ("kalshi-sp", "kalshi-sized", "kalshi-sp500"):
            continue
        for h in bot.get("history") or []:
            if isinstance(h, dict):
                rows.append(h)
    return rows


def run_inx_band_research(
    root: str | None,
    history: list | None = None,
    *,
    bots: list | None = None,
) -> dict:
    """Score research bands; never writes live config. Live stays 80–90 until staff promote."""
    hist = list(history) if history is not None else inx_history_from_bots(bots)
    live = inx_live_band(root)
    bands = []
    for b in INX_RESEARCH_BANDS:
        scored = inx_band_research_score(hist, lo=b["lo"], hi=b["hi"])
        bands.append({
            **b,
            **scored,
            "live_default": b["id"] == INX_LIVE_BAND_DEFAULT,
            "is_live": b["id"] == live.get("id"),
        })
    ranked = sorted(
        [x for x in bands if x.get("n")],
        key=lambda x: (x.get("expectancy_taxed") is not None, x.get("expectancy_taxed") or -999),
        reverse=True,
    )
    leader_id = ranked[0]["id"] if ranked else None
    leader_n = int((ranked[0].get("n") if ranked else 0) or 0)
    evidence_thin = (not ranked) or leader_n < int(INX_BAND_PROMOTE_MIN_N)
    report = {
        "paper_only": True,
        "live_band": live.get("id") or INX_LIVE_BAND_DEFAULT,
        "live_changed": bool(live.get("live_changed")),
        "staff_approved": bool(live.get("staff_approved")),
        "bands": bands,
        "leader": leader_id,
        "leader_n": leader_n,
        "history_n": len(hist),
        "evidence_thin": evidence_thin,
        "keep_live_band": INX_LIVE_BAND_DEFAULT if evidence_thin else (
            live.get("id") or INX_LIVE_BAND_DEFAULT
        ),
        "promote_min_n": INX_BAND_PROMOTE_MIN_N,
        "n_to_promote": max(0, int(INX_BAND_PROMOTE_MIN_N) - leader_n),
        "fee_floors_locked": True,
        "auto_promote": False,
        "observe_only": True,
        "note": (
            "Research harness only — does not change kalshi-sp/sized ask band. "
            "Evidence thin → keep 80–90 until leader n≥20 beats live. "
            "Promote only via staff_promote_inx_band after artifact + Chicago week "
            "(no force on money-path CLI)."
        ),
        "at": _now(),
    }
    path = _path(INX_BAND_RESEARCH, root)
    store = _load(path, {"paper_only": True, "reports": []})
    store.setdefault("reports", []).append(report)
    store["reports"] = store["reports"][-40:]
    store["latest"] = report
    _save(path, store)
    return report


def staff_promote_inx_leader(
    root: str | None = None,
    *,
    note: str = "",
) -> dict:
    """No-force promote of research leader when promote_ready. Never softens floors."""
    status = inx_band_promote_status(root)
    leader = status.get("leader")
    if not status.get("promote_ready") or not leader:
        return {
            "ok": False,
            "reason": status.get("reason") or "not promote_ready",
            "status": status,
            "auto_promote": False,
            "fee_floors_locked": True,
            "paper_only": True,
            "force": False,
        }
    return staff_promote_inx_band(
        root, str(leader), note=note or f"staff promote leader {leader}", force=False,
    )


def inx_band_promote_status(root: str | None = None) -> dict:
    """Ready when research leader beats live band with n≥20 — never auto-promote.

    Evidence-thin path: keep live 80–90 until leader n≥20 beats live EV.
    """
    store = _load(_path(INX_BAND_RESEARCH, root), {"paper_only": True, "latest": None})
    report = store.get("latest") if isinstance(store.get("latest"), dict) else None
    live = inx_live_band(root)
    live_id = live.get("id") or INX_LIVE_BAND_DEFAULT
    keep_band = INX_LIVE_BAND_DEFAULT
    if not report:
        return {
            "paper_only": True,
            "promote_ready": False,
            "decision": "reject",
            "evidence_thin": True,
            "keep_live_band": keep_band,
            "n_to_promote": INX_BAND_PROMOTE_MIN_N,
            "reason": "no research artifact yet — run_inx_band_research first",
            "live_band": live_id,
            "leader": None,
            "leader_n": 0,
            "auto_promote": False,
            "staff_approved": bool(live.get("staff_approved")),
            "fee_floors_locked": True,
            "observe_only": True,
            "label": (
                f"INX evidence THIN — keep {keep_band} until leader n≥"
                f"{INX_BAND_PROMOTE_MIN_N}"
            ),
            "note": (
                "INX band promote requires research artifact + staff_promote_inx_band. "
                "Never auto-changes config.json. Fee floors locked."
            ),
        }
    bands = {b["id"]: b for b in (report.get("bands") or []) if isinstance(b, dict) and b.get("id")}
    leader_id = report.get("leader")
    leader = bands.get(leader_id) if leader_id else None
    live_row = bands.get(live_id)
    ready = False
    reason = "leader missing or thin sample"
    leader_n = int((leader or {}).get("n") or 0) if leader else 0
    evidence_thin = True
    if isinstance(leader, dict):
        n = leader_n
        exp = _finite(leader.get("expectancy_taxed"))
        live_exp = _finite((live_row or {}).get("expectancy_taxed")) if live_row else None
        if n < INX_BAND_PROMOTE_MIN_N:
            reason = f"leader n={n} < {INX_BAND_PROMOTE_MIN_N} — evidence thin, keep {keep_band}"
            evidence_thin = True
        elif exp is None:
            reason = "leader expectancy missing"
            evidence_thin = True
        elif leader_id == live_id:
            reason = "leader already equals live band — no promote needed"
            evidence_thin = False
        elif live_exp is not None and exp + 1e-12 < live_exp:
            reason = "leader EV below live band EV — keep live band"
            evidence_thin = False
        else:
            ready = True
            evidence_thin = False
            reason = (
                f"leader {leader_id} n={n} EV={exp} beats live "
                f"{live_id} — staff may promote"
            )
    n_to_promote = max(0, int(INX_BAND_PROMOTE_MIN_N) - int(leader_n))
    return {
        "paper_only": True,
        "promote_ready": ready,
        "decision": "review" if ready else "reject",
        "evidence_thin": evidence_thin,
        "keep_live_band": keep_band if (evidence_thin or not ready) else live_id,
        "n_to_promote": n_to_promote if evidence_thin else 0,
        "reason": reason,
        "live_band": live_id,
        "leader": leader_id,
        "leader_n": leader_n,
        "leader_ev": _finite((leader or {}).get("expectancy_taxed")) if leader else None,
        "promote_min_n": INX_BAND_PROMOTE_MIN_N,
        "history_n": int(report.get("history_n") or 0),
        "auto_promote": False,
        "staff_approved": bool(live.get("staff_approved")),
        "effective": live,
        "fee_floors_locked": True,
        "observe_only": True,
        "label": (
            f"INX evidence THIN keep={keep_band} leader_n={leader_n} "
            f"need≥{INX_BAND_PROMOTE_MIN_N}"
            if evidence_thin
            else (
                f"INX promote_ready leader={leader_id} n={leader_n}"
                if ready
                else f"INX reject — {reason[:80]}"
            )
        ),
        "note": (
            "INX band promote requires research artifact + staff_promote_inx_band. "
            "Evidence thin → keep 80–90 until leader n≥20 beats live. "
            "Never auto-changes config.json. Fee floors locked."
        ),
    }


def staff_promote_inx_band(
    root: str | None,
    band_id: str,
    *,
    note: str = "",
    force: bool = False,
) -> dict:
    """Staff gate to lock a research band as live ask band (artifact only)."""
    status = inx_band_promote_status(root)
    bid = str(band_id or "").strip()
    known = {b["id"] for b in INX_RESEARCH_BANDS}
    if bid not in known:
        return {
            "ok": False,
            "reason": f"unknown band_id {bid!r}; choose from {sorted(known)}",
            "auto_promote": False,
            "fee_floors_locked": True,
        }
    if not force:
        if not status.get("promote_ready"):
            return {
                "ok": False,
                "reason": status.get("reason") or "not promote_ready",
                "status": status,
                "auto_promote": False,
                "fee_floors_locked": True,
            }
        if bid != status.get("leader"):
            return {
                "ok": False,
                "reason": f"band_id {bid} is not research leader {status.get('leader')}",
                "status": status,
                "auto_promote": False,
                "fee_floors_locked": True,
            }
    base = inx_band_from_id(bid)
    row = {
        "paper_only": True,
        "staff_approved": True,
        "band_id": base["id"],
        "lo": base["lo"],
        "hi": base["hi"],
        "at": _now(),
        "note": str(note or "")[:200],
        "auto_promote": False,
        "fee_floors_locked": True,
    }
    _save(_path(INX_BAND_PROMOTE, root), row)
    return {
        "ok": True,
        "reason": "armed",
        "band": inx_live_band(root),
        "status": inx_band_promote_status(root),
        "auto_promote": False,
        "fee_floors_locked": True,
    }


def staff_clear_inx_band_promote(root: str | None, *, note: str = "") -> dict:
    """Disarm staff band promote — bots fall back to config.json / default 80–90."""
    row = {
        "paper_only": True,
        "staff_approved": False,
        "band_id": INX_LIVE_BAND_DEFAULT,
        "lo": 0.80,
        "hi": 0.90,
        "at": _now(),
        "note": str(note or "cleared")[:200],
        "auto_promote": False,
        "fee_floors_locked": True,
    }
    _save(_path(INX_BAND_PROMOTE, root), row)
    return {"ok": True, "band": inx_live_band(root), "fee_floors_locked": True}


# ---- Exit plan on fee-clear opens (Phase 3) ---------------------------------

def default_exit_plan(bot: str) -> dict:
    """Canonical exit plan stamped onto new opens — observe/exit quality, not a chip."""
    b = str(bot or "").strip()
    if b in ("sports-gap", "sports"):
        return {
            "kind": "gap_decay+scale_out+hard_stop_shadow+time_final_shadow+settle",
            "hard_stop_drop": SPORTS_HARD_STOP_DROP,
            "hard_stop_live": bool(SPORTS_HARD_STOP_LIVE),
            "hard_stop_shadow": True,
            "time_final_shadow": True,
            "time_final_min_left": SPORTS_TIME_FINAL_MIN_LEFT,
            "time_final_live": bool(SPORTS_TIME_FINAL_LIVE),
            "gap_decay": True,
            "scale_out": True,
            "settle_backstop": True,
            "auto_promote": False,
            "fee_floors_locked": True,
            "note": (
                "Sports exits: gap-decay + scale-out + hard-stop shadow "
                f"(−{SPORTS_HARD_STOP_DROP:.0%} bid) + time-to-final shadow "
                f"(≤{SPORTS_TIME_FINAL_MIN_LEFT:g}m left + underwater); "
                "live hard-stop / time-final stay staff-gated."
            ),
        }
    if b in ("btc15m", "btc", "btc15m-signal"):
        return {
            "kind": "take_profit+model_flip+settle",
            "take_profit": True,
            "model_flip": True,
            "settle_backstop": True,
            "fee_floors_locked": True,
            "note": "BTC exits: take-profit + model-flip; settle is backstop.",
        }
    if b in ("commodity-15m", "commodity"):
        return {
            "kind": "model_flip+time_stop_shadow+settle",
            "model_flip": True,
            "time_stop_shadow": True,
            "time_stop_min_left": COMMODITY_TIME_STOP_MIN_LEFT,
            "time_stop_live": bool(COMMODITY_TIME_STOP_LIVE),
            "settle_backstop": True,
            "series_corr_haircut": True,
            "auto_promote": False,
            "fee_floors_locked": True,
            "note": (
                "Commodity exits: model-flip + time-stop shadow "
                f"(≤{COMMODITY_TIME_STOP_MIN_LEFT:g}m left + underwater mark); "
                "settle is backstop; WTI↔Brent haircut on entry. "
                "Live time-stop stays staff-gated."
            ),
        }
    if b in ("kalshi-sp", "kalshi-sp500", "kalshi_sp", "inx-sp"):
        return {
            "kind": "model_flip+settle",
            "model_flip": True,
            "settle_backstop": True,
            "ask_band": "80-90",
            "fee_floors_locked": True,
            "note": "INX S&P exits: model-flip when fair drifts; settle backstop; band staff-promote gated.",
        }
    if b in ("kalshi-sized", "kalshi_sized", "inx-sized"):
        return {
            "kind": "model_flip+settle",
            "model_flip": True,
            "settle_backstop": True,
            "ask_band": "84-92",
            "fee_floors_locked": True,
            "note": "INX sized exits: model-flip when fair drifts; settle backstop; twin+1¢ edge locked.",
        }
    if b in ("btc-carry", "btc_carry"):
        return {
            "kind": "hold+refuse_monthly_flip",
            "hold": True,
            "red_month_exit": False,
            "monthly_flip": False,
            "staff_close_backstop": True,
            "shadow_only": True,
            "auto_promote": False,
            "fee_floors_locked": True,
            "unlevered": True,
            "note": (
                "Held unlevered BTC carry. A red funding month is a mark, not a flip. "
                "Staff close is the backstop. No auto-promote."
            ),
        }
    if b in ("coinbase-spot", "coinbase"):
        return {
            "kind": "stop+take_profit+model_flip+time",
            "stop_pct": -0.015,
            "take_profit": True,
            "model_flip": True,
            "time_stop_hours": 24,
            "shadow_only": True,
            "auto_promote": False,
            "fee_floors_locked": True,
            "note": (
                "Coinbase spot exits: −1.5% stop, take-profit at round-trip plus 0.05 floor, "
                "model-flip when z flips, 24h time stop. Shadow sleeve. No auto-promote."
            ),
        }
    if b in ("wall-street", "wall_street"):
        return {
            "kind": "no_position",
            "shadow_only": True,
            "auto_promote": False,
            "fee_floors_locked": True,
            "note": "Wall Street houses 120 traders on one floor. The book does not open a position.",
        }
    if b in ("memecoin", "meme"):
        return {
            "kind": "stop+model_flip+ladder+settle",
            "stop_pct": -0.12,
            "model_flip_mom": -0.06,
            "ladder_take_profits": True,
            "settle_backstop": True,
            "fee_floors_locked": True,
            "note": "Meme exits: −12% stop, −6% mom flip, ladder TPs; never expand volume.",
        }
    return {
        "kind": "settle",
        "settle_backstop": True,
        "fee_floors_locked": True,
        "note": "Settle-only backstop until tower-specific exits are stamped.",
    }


def exit_plan_coverage(
    root: str | None = None,
    *,
    bots: list | None = None,
) -> dict:
    """
    Fraction of open fee-clear positions that carry an exit_plan.
    Not a board chip — Masters / money-path observe only.
    """
    _ = root
    opens: list[dict] = []
    if isinstance(bots, list):
        for bot in bots:
            if not isinstance(bot, dict):
                continue
            bid = str(bot.get("id") or bot.get("bot") or "")
            for p in bot.get("open") or bot.get("positions") or []:
                if isinstance(p, dict):
                    row = dict(p)
                    row.setdefault("bot", bid)
                    opens.append(row)
    tracked_ids = set(FEE_CLEAR) | set(LOSER_IDS)
    tracked = [p for p in opens if str(p.get("bot") or "") in tracked_ids]
    fee_clear = [p for p in tracked if str(p.get("bot") or "") in FEE_CLEAR]
    with_plan = [
        p
        for p in tracked
        if isinstance(p.get("exit_plan"), dict) and p.get("exit_plan")
    ]
    n = len(tracked)
    covered = len(with_plan)
    rate = (covered / n) if n else None
    ok = n == 0 or (rate is not None and rate >= 1.0 - 1e-12)
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "board_chip": False,
        "n_open": n,
        "n_fee_clear": len(fee_clear),
        "n_with_plan": covered,
        "coverage": rate,
        "pass": ok,
        "missing_bots": sorted(
            {
                str(p.get("bot") or "")
                for p in tracked
                if not (isinstance(p.get("exit_plan"), dict) and p.get("exit_plan"))
            }
        ),
        "label": (
            f"exit_plan coverage={covered}/{n} "
            f"{'ok' if ok else 'THIN'} "
            "(observe · Phase 3 · never softens floors)"
        ),
        "note": (
            "Every desk open should stamp exit_plan at buy (fee-clear + loser towers). "
            "Missing plans are exit-quality debt — not a reason to soften floors."
        ),
    }


# Explicit settle-backstop waivers — towers that keep settle/staff-close as the
# final backstop while intermediate exits already run (Phase 3 exit gate).
PHASE3_SETTLE_BACKSTOP_WAIVERS = {
    "sports-gap": "gap_decay+scale_out+hard_stop_shadow+time_final_shadow; settle backstop",
    "btc15m": "take_profit+model_flip live; settle backstop",
    "commodity-15m": "model_flip live + time_stop_shadow; settle backstop",
    "kalshi-sp": "model_flip live; settle backstop; post-macro blackout",
    "kalshi-sized": "model_flip live; settle backstop; twin+1¢",
    "memecoin": "−12% stop + mom flip + ladder TP; settle backstop",
    "btc-carry": "shadow hold sleeve — staff close backstop (no monthly flip invent)",
    "coinbase-spot": "shadow stop/TP/flip/time — staff promote gated",
}


def _phase3_has_intermediate_exits(plan: dict | None) -> bool:
    """True when exit plan is not bare settle-only."""
    if not isinstance(plan, dict):
        return False
    kind = str(plan.get("kind") or "").strip().lower()
    if not kind or kind == "settle":
        return False
    flags = (
        "take_profit", "model_flip", "hard_stop_shadow", "time_final_shadow",
        "time_stop_shadow", "gap_decay", "scale_out", "ladder_take_profits",
        "stop_pct", "hold", "red_month_exit",
    )
    if any(plan.get(k) for k in flags):
        return True
    # kind tokens like "stop+take_profit+…" without boolean flags
    parts = [p for p in kind.replace(" ", "").split("+") if p]
    return bool(parts) and parts != ["settle"]


def phase3_exit_gate(
    root: str | None = None,
    *,
    bots: list | None = None,
) -> dict:
    """Phase 3 exit-quality exit gate (master plan).

    Pass when:
      1. Every core tower has intermediate exits (not bare settle-only) OR an
         explicit settle-backstop waiver naming those exits.
      2. BTC take-profit path is honest (default_exit_plan take_profit=True).
      3. Commodity model-flip is live in the plan (flip not shadow-only).
      4. Sports hard-stop + time-final exist as shadow (live stays staff-gated).
      5. exit_plan_coverage passes when opens exist.
      6. Floors stay locked; never arms LIVE_ORDERS here.

    Observe / certify only — does not auto-promote shadows.
    """
    core = list(FEE_CLEAR) + list(LOSER_IDS)
    towers = []
    bare = []
    for bot_id in core:
        plan = default_exit_plan(bot_id)
        intermediate = _phase3_has_intermediate_exits(plan)
        waiver = PHASE3_SETTLE_BACKSTOP_WAIVERS.get(bot_id) or ""
        ok = bool(intermediate) and bool(waiver)
        if not intermediate:
            bare.append(bot_id)
        towers.append({
            "bot": bot_id,
            "kind": plan.get("kind"),
            "intermediate_exits": intermediate,
            "settle_backstop": bool(plan.get("settle_backstop")),
            "waiver": waiver,
            "pass": ok,
        })

    btc_plan = default_exit_plan("btc15m")
    cmd_plan = default_exit_plan("commodity-15m")
    sports_plan = default_exit_plan("sports-gap")
    btc_tp_honest = bool(btc_plan.get("take_profit")) and "take_profit" in str(
        btc_plan.get("kind") or ""
    )
    cmd_flip_live = bool(cmd_plan.get("model_flip"))
    sports_hs_shadow = bool(sports_plan.get("hard_stop_shadow"))
    sports_tf_shadow = bool(sports_plan.get("time_final_shadow"))

    coverage = exit_plan_coverage(root, bots=bots)
    hard = sports_hard_stop_shadow_summary(root)
    tstop = commodity_time_stop_shadow_summary(root)
    tfinal = sports_time_final_shadow_summary(root)
    quality = exit_quality_observe(root, bots=bots)

    shadows = {
        "sports_hard_stop": {
            "promote_ready": bool(hard.get("promote_ready")),
            "live": bool(hard.get("live")),
            "n_with_pnl": int(hard.get("n_with_pnl") or 0),
            "n_to_promote": max(
                0,
                int(hard.get("promote_min_n") or 30) - int(hard.get("n_with_pnl") or 0),
            ),
        },
        "commodity_time_stop": {
            "promote_ready": bool(tstop.get("promote_ready")),
            "live": bool(tstop.get("live")),
            "n_with_pnl": int(tstop.get("n_with_pnl") or 0),
            "n_to_promote": int(tstop.get("n_to_promote") or 0),
        },
        "sports_time_final": {
            "promote_ready": bool(tfinal.get("promote_ready")),
            "live": bool(tfinal.get("live")),
            "n_with_pnl": int(tfinal.get("n_with_pnl") or 0),
            "n_to_promote": int(tfinal.get("n_to_promote") or 0),
        },
    }

    gate_pass = (
        not bare
        and all(t.get("pass") for t in towers)
        and btc_tp_honest
        and cmd_flip_live
        and sports_hs_shadow
        and sports_tf_shadow
        and bool(coverage.get("pass"))
        and bool((fee_floors_locked_check() or {}).get("ok"))
    )
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "live_orders_enabled": False,
        "board_chip": False,
        "phase": "P3",
        "pass": gate_pass,
        "towers": towers,
        "bare_settle_only": bare,
        "btc_tp_honest": btc_tp_honest,
        "commodity_flip_live": cmd_flip_live,
        "sports_hard_stop_shadow": sports_hs_shadow,
        "sports_time_final_shadow": sports_tf_shadow,
        "exit_plan_coverage": {
            "pass": coverage.get("pass"),
            "n_open": coverage.get("n_open"),
            "n_with_plan": coverage.get("n_with_plan"),
            "coverage": coverage.get("coverage"),
        },
        "shadows": shadows,
        "exit_quality": {
            "label": quality.get("label"),
            "exit_regret": quality.get("exit_regret"),
        },
        "waivers": dict(PHASE3_SETTLE_BACKSTOP_WAIVERS),
        "label": (
            f"P3 exit-gate {'PASS' if gate_pass else 'FAIL'} "
            f"towers={sum(1 for t in towers if t.get('pass'))}/{len(towers)} "
            f"btc_tp={btc_tp_honest} cmd_flip={cmd_flip_live} "
            f"cover={coverage.get('n_with_plan')}/{coverage.get('n_open')}"
        ),
        "note": (
            "Phase 3 exit gate — intermediate exits + explicit settle-backstop waivers; "
            "BTC TP honest; commodity flip live; sports HS/t-final shadow (staff-gated live). "
            "Never softens floors; never arms LIVE_ORDERS; shadows stay staff-promote."
        ),
        "decision": (
            "phase3_exit_gate_pass" if gate_pass else "phase3_exit_gate_fail"
        ),
    }


# Phase 4 locked INX band decision — fee-aware research may promote later;
# intuition never invents a new live band without staff + n≥20 leader.
PHASE4_INX_BAND_LOCK = {
    "live_band": INX_LIVE_BAND_DEFAULT,
    "research_bands": tuple(b["id"] for b in INX_RESEARCH_BANDS),
    "promote_min_n": INX_BAND_PROMOTE_MIN_N,
    "note": (
        "Live INX ask band stays 80–90¢ until fee-aware research leader n≥20 "
        "and staff promote. Evidence-thin → keep_live_band (never invent)."
    ),
}


def phase4_calib_gate(
    root: str | None = None,
    *,
    bots: list | None = None,
) -> dict:
    """Phase 4 calibration & CLV exit gate (master plan).

    Pass when infrastructure + locked decisions are honest:
      1. Sports CLV journal complete (completeness pass; bar 52% when n≥20).
      2. Per-league CLV board wired (NFL…NHL) without softening floors.
      3. INX band decision locked — live 80–90 + research harness + dual-side
         pick; evidence-thin keeps live band (no intuition invent).
      4. BTC calibration report publishable; auto_write_phi stays False.
      5. ETH calib slice separate from BTC; sports/commodity calib capture ok.
      6. Learning skip v2 accepts side × hour_ct; adverse cool + depth need=10.
      7. Floors stay locked; never arms LIVE_ORDERS; never auto-writes Φ.

    Observe / certify only — does not change bands or Φ.
    """
    clv = clv_completeness(root)
    clv_journal_ok = bool(clv.get("pass"))

    leagues = None
    league_ids = []
    clv_beat_n = 0
    clv_beat_rate = None
    try:
        import desk_more
        leagues = desk_more.clv_by_league(root)
        for row in (leagues.get("leagues") or []):
            if isinstance(row, dict) and row.get("league"):
                league_ids.append(str(row["league"]))
        summary = desk_more.clv_summary(root)
        clv_beat_n = int(summary.get("n") or 0)
        clv_beat_rate = _finite(summary.get("beat_close_rate"))
    except Exception:
        leagues = None
    # Economic bar: when enough settles, beat-close must clear 52%. Thin → observe.
    clv_bar_ok = (
        clv_beat_n < int(SPORTS_CLV_MIN_N)
        or (
            clv_beat_rate is not None
            and clv_beat_rate + 1e-12 >= float(SPORTS_CLV_BAR)
        )
    )
    expected_leagues = {"NFL", "NCAAF", "NBA", "WNBA", "MLB", "NHL"}
    leagues_ok = bool(expected_leagues.issubset(set(league_ids)))

    inx = inx_band_promote_status(root) or {}
    live_band = str(
        inx.get("live_band")
        or inx.get("keep_live_band")
        or INX_LIVE_BAND_DEFAULT
    )
    artifact_band = str(inx.get("artifact_band") or inx.get("band") or "")
    keep_band = str(inx.get("keep_live_band") or live_band)
    evidence_thin = bool(inx.get("evidence_thin"))
    staff_approved = bool(inx.get("staff_approved") or inx.get("armed"))
    # Locked = live default 80_90 AND (staff arm OR thin keep OR artifact matches).
    inx_locked = (
        live_band == INX_LIVE_BAND_DEFAULT
        and keep_band == INX_LIVE_BAND_DEFAULT
        and (
            staff_approved
            or evidence_thin
            or artifact_band in ("", INX_LIVE_BAND_DEFAULT)
        )
        and float(SPORTS_CLV_BAR) == 0.52  # sanity — bar constant intact
    )
    dual_side_ok = False
    try:
        import desk_inx
        dual_side_ok = callable(getattr(desk_inx, "dual_side_pick", None))
    except Exception:
        dual_side_ok = False
    research_ok = callable(run_inx_band_research) and callable(staff_promote_inx_band)

    btc = btc_calibration_report(bots)
    eth = eth_calibration_report(bots)
    sports = sports_calibration_report(bots)
    commodity = commodity_calibration_report(bots)
    btc_pub = (
        isinstance(btc, dict)
        and btc.get("auto_write_phi") is False
        and "buckets" in btc
        and callable(capture_btc_calibration)
        and callable(latest_btc_calibration)
    )
    eth_ok = (
        isinstance(eth, dict)
        and eth.get("auto_write_phi") is False
        and callable(capture_eth_calibration)
    )
    sports_calib_ok = isinstance(sports, dict) and sports.get("auto_write_phi") is False
    commodity_calib_ok = (
        isinstance(commodity, dict) and commodity.get("auto_write_phi") is False
    )

    learn_v2_ok = False
    try:
        import inspect
        import pimp_desk
        sig = inspect.signature(pimp_desk.learning_skip)
        params = set(sig.parameters)
        learn_v2_ok = {"side", "hour_ct"}.issubset(params)
    except Exception:
        learn_v2_ok = False

    adverse_ok = callable(adverse_cool_blocks) and callable(record_adverse_fill)
    depth_ok = False
    depth_need = None
    try:
        import desk_more
        depth_need = float(desk_more.DEFAULT_DEPTH_NEED)
        depth_ok = abs(depth_need - 10.0) < 1e-9
    except Exception:
        depth_ok = False

    observe = calib_clv_observe(root, bots=bots)
    floors_ok = bool((fee_floors_locked_check() or {}).get("ok"))

    gate_pass = (
        clv_journal_ok
        and clv_bar_ok
        and leagues_ok
        and inx_locked
        and dual_side_ok
        and research_ok
        and btc_pub
        and eth_ok
        and sports_calib_ok
        and commodity_calib_ok
        and learn_v2_ok
        and adverse_ok
        and depth_ok
        and floors_ok
        # calib_clv_observe.ok may alert on selective_m1_thin (P5) — ignore for P4.
        and bool(observe.get("auto_write_phi") is False)
        and bool(observe.get("live_orders_enabled") is False)
    )
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "auto_write_phi": False,
        "live_orders_enabled": False,
        "board_chip": False,
        "phase": "P4",
        "pass": gate_pass,
        "clv_journal": {
            "pass": clv_journal_ok and clv_bar_ok,
            "completeness_pass": clv_journal_ok,
            "n": int(clv.get("n") or 0),
            "settled_n": int(clv.get("settled_n") or 0),
            "completeness_rate": _finite(clv.get("rate")),
            "beat_close_n": clv_beat_n,
            "beat_close_rate": clv_beat_rate,
            "bar": float(SPORTS_CLV_BAR),
            "min_n": int(SPORTS_CLV_MIN_N),
            "bar_ok": clv_bar_ok,
            "fail_closed": bool(clv.get("fail_closed")),
        },
        "clv_leagues": {
            "pass": leagues_ok,
            "leagues": league_ids,
            "expected": sorted(expected_leagues),
            "beat_bar": float(SPORTS_CLV_BAR),
        },
        "inx_band_lock": {
            "pass": inx_locked and dual_side_ok and research_ok,
            "live_band": live_band,
            "keep_live_band": keep_band,
            "artifact_band": artifact_band or None,
            "evidence_thin": evidence_thin,
            "staff_approved": staff_approved,
            "dual_side_pick": dual_side_ok,
            "research_harness": research_ok,
            "lock": dict(PHASE4_INX_BAND_LOCK),
            "label": inx.get("label"),
            "decision": inx.get("decision"),
        },
        "btc_calibration": {
            "pass": btc_pub,
            "n": btc.get("n"),
            "miscalibrated": bool(btc.get("miscalibrated")),
            "action": btc.get("action"),
            "auto_write_phi": False,
            "published": bool(latest_btc_calibration(root) or btc.get("n") is not None),
        },
        "eth_calibration": {
            "pass": eth_ok,
            "n": eth.get("n"),
            "miscalibrated": bool(eth.get("miscalibrated")),
            "auto_write_phi": False,
        },
        "sports_calibration": {
            "pass": sports_calib_ok,
            "n": sports.get("n"),
            "miscalibrated": bool(sports.get("miscalibrated")),
        },
        "commodity_calibration": {
            "pass": commodity_calib_ok,
            "n": commodity.get("n"),
            "miscalibrated": bool(commodity.get("miscalibrated")),
        },
        "learning_skip_v2": learn_v2_ok,
        "adverse_cool": adverse_ok,
        "depth_need": {"pass": depth_ok, "need": depth_need, "expected": 10.0},
        "calib_clv_observe": {
            "ok": observe.get("ok"),
            "alerts": observe.get("alerts"),
            "auto_write_phi": False,
        },
        "label": (
            f"P4 calib-gate {'PASS' if gate_pass else 'FAIL'} "
            f"clv={clv_journal_ok} inx_lock={inx_locked} "
            f"btc_pub={btc_pub} learn_v2={learn_v2_ok} "
            f"depth={depth_need}"
        ),
        "note": (
            "Phase 4 calib/CLV gate — sports CLV journal + 52% bar when n≥20; "
            "INX 80–90 locked until fee-aware staff promote; BTC/ETH calib "
            "publish without auto Φ write; learn v2 + adverse cool + depth=10. "
            "Never softens floors; never arms LIVE_ORDERS."
        ),
        "decision": (
            "phase4_calib_gate_pass" if gate_pass else "phase4_calib_gate_fail"
        ),
    }


# Phase 5 selective-throughput locks — more eligible fills only after M1 holds;
# never invent fills; never auto-promote thin gates; commodity stays 2.0R.
PHASE5_THROUGHPUT_LOCKS = {
    "selective_green_only": True,
    "sports_green_boost_default": 0,
    "sports_green_boost_weeks": SPORTS_GREEN_BOOST_WEEKS,
    "sports_clv_bar": SPORTS_CLV_BAR,
    "near_miss_promote_n": NEAR_MISS_PROMOTE_N,
    "near_miss_auto_promote": False,
    "near_miss_code_live": False,
    "empty_card_bar_sec": EMPTY_CARD_BAR_SEC,
    "commodity_daily_r": 2.0,
    "note": (
        "Selective +1 on fee-clear greens only; sports green_boost stays 0 until "
        "2 Chicago weeks M1≥0 + CLV≥52% n≥20 (staff arm only); near-miss soft "
        "promote only n≥30 labeled EV≥0 with auto_promote=False; empty CARD <3s; "
        "commodity daily R locked at 2.0 ($40)."
    ),
}


def phase5_throughput_gate(
    root: str | None = None,
    *,
    bots: list | None = None,
) -> dict:
    """Phase 5 selective throughput exit gate (master plan).

    Pass when infrastructure + locks are honest:
      1. Selective +1 only on fee-clear greens (red days never boost).
      2. Sports green_boost defaults 0 when evidence thin; auto_promote=False.
      3. Near-miss promote only n≥30 EV≥0 path; code LIVE=False; auto_promote=False.
      4. Firm queue ranks sports+btc+commodity; tip funnel + skip-regret wired.
      5. Empty-market CARD bar 3s; opportunity-cost clock present.
      6. Commodity daily R locked at 2.0; floors locked; M3 not a stub.
      7. Never arms LIVE_ORDERS; never invents fills; never force-arms here.

    Observe / certify only — does not staff-arm, staff-clear, or invent evidence.
    """
    selective = selective_throughput_observe(root, bots=bots)
    # Prove selective_max_buys refuses red-day boost.
    red_ok = False
    green_ok = False
    try:
        import desk_more
        red_ok = int(desk_more.selective_max_buys("btc15m", base=3, today=-1.0, green_boost=1)) == 3
        green_ok = int(desk_more.selective_max_buys("btc15m", base=3, today=1.0, green_boost=1)) == 4
        sports_red = int(
            desk_more.selective_max_buys("sports-gap", base=3, today=-5.0, green_boost=1)
        ) == 3
        loser_no = int(
            desk_more.selective_max_buys("memecoin", base=3, today=5.0, green_boost=1)
        ) == 3
        selective_rules_ok = red_ok and green_ok and sports_red and loser_no
    except Exception:
        selective_rules_ok = False

    boost = sports_green_boost_status(root, bots=bots)
    boost_ok = (
        bool(boost.get("auto_promote") is False)
        and int(boost.get("weeks_required") or 0) == int(SPORTS_GREEN_BOOST_WEEKS)
        and abs(float(boost.get("clv_bar") or 0) - float(SPORTS_CLV_BAR)) < 1e-12
        and (
            # Thin → boost must stay 0 unless already staff-armed (do not clear).
            bool(boost.get("ready"))
            or int(boost.get("green_boost") or 0) == 0
            or bool(boost.get("staff_armed"))
        )
    )
    # Force-arm while thin is staff ops debt — flag but do not clear.
    boost_force_thin = (
        bool(boost.get("evidence_thin"))
        and bool(boost.get("staff_armed"))
        and not bool(boost.get("ready"))
    )

    nm = near_miss_promote_status(root)
    nm_ok = (
        bool(nm.get("auto_promote") is False)
        and bool(NEAR_MISS_LIVE) is False
        and int(nm.get("promote_min_n") or 0) == int(NEAR_MISS_PROMOTE_N)
        and int(NEAR_MISS_PROMOTE_N) >= 30
    )
    # Promote JSON may record evidence-led arm while ephemeral journal is empty
    # in a fresh checkout — trust artifact shadow_n/EV; do not staff-clear.
    nm_promote_art = _load(
        _path(NEAR_MISS_PROMOTE_NAME, root),
        {"paper_only": True, "staff_approved": False, "live": False},
    )
    art_n = int(nm_promote_art.get("shadow_n") or 0)
    art_ev = _finite(nm_promote_art.get("shadow_ev"))
    art_evidence_ok = (
        art_n >= int(NEAR_MISS_PROMOTE_N)
        and art_ev is not None
        and art_ev + 1e-12 >= float(NEAR_MISS_PROMOTE_MIN_EV)
    )
    nm_force_thin = (
        bool(nm.get("live"))
        and bool(nm.get("evidence_thin"))
        and not art_evidence_ok
    )

    firm = firm_queue_status(root) or {}
    firm_ok = (
        isinstance(firm, dict)
        and callable(rebuild_firm_queue)
        and callable(firm_queue_blocks)
        and bool(firm.get("paper_only", True))
    )

    tip = tip_funnel_board(root) or {}
    tip_ok = isinstance(tip, dict) and callable(record_tip_funnel)

    skip_ok = callable(skip_regret_candidates)

    empty = empty_card_status(root) or {}
    empty_ok = (
        isinstance(empty, dict)
        and abs(float(empty.get("bar_sec") or 0) - float(EMPTY_CARD_BAR_SEC)) < 1e-9
        and abs(float(EMPTY_CARD_BAR_SEC) - 3.0) < 1e-9
        and bool(empty.get("pass"))  # n=0 passes; slow CARD fails
    )

    opp = opp_cost_summary(root) or {}
    opp_ok = isinstance(opp, dict) and bool(opp.get("paper_only", True))

    commodity_r = _finite((DAILY_R_BUDGET or {}).get("commodity-15m"))
    r_ok = commodity_r is not None and abs(float(commodity_r) - 2.0) < 1e-9

    # M3 stub gone — fit_buy_rate returns real rate board (not stub note).
    fit = fit_buy_rate(root) or {}
    m3_ok = (
        isinstance(fit, dict)
        and "stub" not in str(fit.get("note") or "").lower()
        and "rate" in fit
    )

    throughput = throughput_vs_m1_board(root, bots=bots) or {}
    throughput_ok = isinstance(throughput, dict)

    floors_ok = bool((fee_floors_locked_check() or {}).get("ok"))

    gate_pass = (
        selective_rules_ok
        and boost_ok
        and nm_ok
        and firm_ok
        and tip_ok
        and skip_ok
        and empty_ok
        and opp_ok
        and r_ok
        and m3_ok
        and throughput_ok
        and floors_ok
        and bool(selective.get("paper_only", True))
        # Force-arm-while-thin is staff debt — still fail closed for P5 certify
        # so we never claim COMPLETE while a thin gate is live-armed.
        and not boost_force_thin
        and not nm_force_thin
    )
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "live_orders_enabled": False,
        "board_chip": False,
        "force_arm": False,
        "invent_fills": False,
        "phase": "P5",
        "pass": gate_pass,
        "locks": dict(PHASE5_THROUGHPUT_LOCKS),
        "selective": {
            "pass": selective_rules_ok,
            "m1_holds": bool(selective.get("m1_holds")),
            "after_m1": bool(selective.get("after_m1")),
            "boosted_n": selective.get("boosted_n"),
            "red_day_no_boost": red_ok if selective_rules_ok else False,
            "green_day_boost": green_ok if selective_rules_ok else False,
            "label": selective.get("label"),
        },
        "sports_green_boost": {
            "pass": boost_ok and not boost_force_thin,
            "green_boost": boost.get("green_boost"),
            "ready": bool(boost.get("ready")),
            "evidence_thin": bool(boost.get("evidence_thin")),
            "staff_armed": bool(boost.get("staff_armed")),
            "force_armed_thin": boost_force_thin,
            "auto_promote": False,
            "missing": boost.get("missing"),
            "label": boost.get("label"),
        },
        "near_miss": {
            "pass": nm_ok and not nm_force_thin,
            "promote_ready": bool(nm.get("promote_ready")),
            "evidence_thin": bool(nm.get("evidence_thin")),
            "labeled_n": nm.get("labeled_n"),
            "n_to_promote": nm.get("n_to_promote"),
            "shadow_ev": nm.get("shadow_ev"),
            "soft_live": nm.get("soft_live"),
            "artifact_shadow_n": art_n,
            "artifact_shadow_ev": art_ev,
            "artifact_evidence_ok": art_evidence_ok,
            "force_armed_thin": nm_force_thin,
            "auto_promote": False,
            "code_live": bool(NEAR_MISS_LIVE),
            "promote_min_n": int(NEAR_MISS_PROMOTE_N),
            "label": nm.get("label"),
        },
        "firm_queue": {
            "pass": firm_ok,
            "label": firm.get("label"),
            "observe_only": bool(firm.get("observe_only", True)),
        },
        "tip_funnel": {
            "pass": tip_ok,
            "label": tip.get("label"),
            "rows_n": tip.get("rows_n"),
        },
        "skip_regret": {"pass": skip_ok},
        "empty_card": {
            "pass": empty_ok,
            "bar_sec": empty.get("bar_sec"),
            "p50_s": empty.get("p50_s"),
            "status_pass": empty.get("pass"),
        },
        "opp_cost": {
            "pass": opp_ok,
            "n": opp.get("n"),
            "label": opp.get("label"),
        },
        "daily_r": {
            "pass": r_ok,
            "commodity": commodity_r,
            "expected_commodity": 2.0,
            "sports": _finite((DAILY_R_BUDGET or {}).get("sports-gap")),
            "btc": _finite((DAILY_R_BUDGET or {}).get("btc15m")),
        },
        "m3_fit": {
            "pass": m3_ok,
            "rate": fit.get("rate"),
            "n_fit": fit.get("n_fit"),
            "stub": False,
        },
        "throughput_vs_m1": {
            "pass": throughput_ok,
            "label": throughput.get("label"),
        },
        "label": (
            f"P5 throughput-gate {'PASS' if gate_pass else 'FAIL'} "
            f"selective={selective_rules_ok} "
            f"boost={boost.get('green_boost')} "
            f"nm_live={nm.get('soft_live') or 'none'} "
            f"cmd_R={commodity_r} "
            f"empty_bar={empty.get('bar_sec')}"
        ),
        "note": (
            "Phase 5 selective throughput gate — green-only +1; sports green_boost "
            "gated on 2w M1 + CLV bar; near-miss n≥30 EV≥0 staff-only; firm queue + "
            "tip funnel + empty CARD <3s + opp-cost; commodity 2.0R locked. "
            "Never softens floors; never arms LIVE_ORDERS; never invents fills; "
            "never force-arms or staff-clears here."
        ),
        "decision": (
            "phase5_throughput_gate_pass"
            if gate_pass
            else "phase5_throughput_gate_fail"
        ),
    }


# Phase 6 Master graduation locks — 2 Chicago weeks M1–M7; never Master on
# volume alone; meme pause/retire is staff-only; commodity stays 2.0R.
PHASE6_GRADUATION_ORDER = (
    "sports-gap",
    "btc15m",
    "commodity-15m",
    "kalshi-sized",
    "kalshi-sp",
    "memecoin",
)
PHASE6_GRADUATION_LOCKS = {
    "weeks_required": GRADUATION_WEEKS_REQUIRED,
    "m_codes": tuple(GRADUATION_CODES),
    "order": PHASE6_GRADUATION_ORDER,
    "masters_exit_n": 3,
    "meme_window_days": MEME_RETIRE_WINDOW_DAYS,
    "meme_auto_retire": False,
    "auto_promote": False,
    "commodity_daily_r": 2.0,
    "note": (
        "Master = 2 consecutive Chicago weeks all M1–M7. Order: sports → BTC → "
        "commodity → sized → S&P → meme. Exit ≥3 Masters; meme Master or "
        "staff-paused via retirement clock. Never Master on volume alone "
        "(thin_n denial). Never auto-promote / auto-retire."
    ),
}


def phase6_graduation_gate(
    root: str | None = None,
    *,
    bots: list | None = None,
) -> dict:
    """Phase 6 Master graduation exit gate (master plan).

    Pass when infrastructure + locks are honest:
      1. Graduation board: weeks_required=2, auto_promote=False, M1–M7 codes.
      2. Capture path + tower Master checklist (desk_master M1–M7) exist.
      3. thin_n denial prevents Master-on-volume-alone.
      4. Badge fail-closed gates (fee_ledger / news / CLI bypass) wired.
      5. Meme retirement clock: recommend_pause only; never auto-retire / expand.
      6. Graduation order covers fee-clear + loser towers.
      7. Commodity daily R locked at 2.0; floors locked; LIVE_ORDERS off.

    Economic exit (≥3 Masters + meme Master|paused) reported separately —
    empty/thin boards still pass the infrastructure gate (no invent fills).

    Observe / certify only — never force-arms, staff-clears, or invents weeks.
    """
    board = graduation_board(root, bots=bots) or {}
    weeks_req = int(board.get("weeks_required") or 0)
    weeks_ok = weeks_req == int(GRADUATION_WEEKS_REQUIRED) == 2
    auto_ok = bool(board.get("auto_promote") is False)
    codes_ok = tuple(GRADUATION_CODES) == ("M1", "M2", "M3", "M4", "M5", "M6", "M7")
    thin_denial_ok = "thin_n" in list(board.get("denial_code_enum") or [])
    capture_ok = callable(capture_graduation_week)

    # Tower Master checklist still exposes M1–M7 on desk_master rows.
    m_row_ok = False
    try:
        import desk_master
        import inspect
        src = inspect.getsource(desk_master.tower_master_row)
        m_row_ok = all(c in src for c in GRADUATION_CODES)
    except Exception:
        m_row_ok = False

    gates = board.get("gates") if isinstance(board.get("gates"), dict) else (
        graduation_gate_flags(root, bots=bots) or {}
    )
    gates_ok = (
        isinstance(gates, dict)
        and "fee_ledger_fail" in gates
        and "news_fail_open" in gates
        and "cli_bypass" in gates
        and bool(gates.get("cli_bypass")) is False
        and bool(LIVE_ORDERS_ENABLED) is False
    )

    order_ok = set(PHASE6_GRADUATION_ORDER) == set(FEE_CLEAR) | set(LOSER_IDS)

    meme_bot = None
    if isinstance(bots, list):
        meme_bot = next(
            (b for b in bots if isinstance(b, dict) and str(b.get("id") or "") == "memecoin"),
            None,
        )
    meme = meme_retirement_clock(meme_bot)
    meme_ok = (
        isinstance(meme, dict)
        and bool(meme.get("retired") is False)  # never auto-retire flag
        and bool(meme.get("expand_volume") is False)
        and int(meme.get("window_days") or 0) == int(MEME_RETIRE_WINDOW_DAYS)
        and "auto" not in str(meme.get("action") or "").lower()
    )

    masters = list(board.get("masters") or [])
    masters_n = int(board.get("masters_n") or len(masters) or 0)
    meme_status = "not_ready"
    meme_tower = (board.get("towers") or {}).get("memecoin") if isinstance(
        board.get("towers"), dict
    ) else None
    if isinstance(meme_tower, dict) and meme_tower.get("status") == "master":
        meme_status = "master"
    elif bool(meme.get("recommend_pause")) or bool(meme.get("retired")):
        meme_status = "paused"
    elif str(meme.get("action") or "") in ("pause_entries", "retired"):
        meme_status = "paused"
    else:
        meme_status = str(
            (meme_tower or {}).get("status") or meme.get("action") or "measuring"
        )

    economic_pass = bool(masters_n >= 3 and meme_status in ("master", "paused"))

    commodity_r = _finite((DAILY_R_BUDGET or {}).get("commodity-15m"))
    r_ok = commodity_r is not None and abs(float(commodity_r) - 2.0) < 1e-9
    floors_ok = bool((fee_floors_locked_check() or {}).get("ok"))

    gate_pass = (
        weeks_ok
        and auto_ok
        and codes_ok
        and thin_denial_ok
        and capture_ok
        and m_row_ok
        and gates_ok
        and order_ok
        and meme_ok
        and r_ok
        and floors_ok
    )
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "live_orders_enabled": False,
        "board_chip": False,
        "force_arm": False,
        "invent_fills": False,
        "phase": "P6",
        "pass": gate_pass,
        "economic_pass": economic_pass,
        "locks": dict(PHASE6_GRADUATION_LOCKS),
        "graduation": {
            "pass": weeks_ok and auto_ok and capture_ok and thin_denial_ok,
            "weeks_required": weeks_req,
            "weeks_n": board.get("weeks_n"),
            "masters": masters,
            "masters_n": masters_n,
            "masters_exit_n": 3,
            "masters_badged": board.get("masters_badged"),
            "status_by_bot": {
                bid: (board.get("towers") or {}).get(bid, {}).get("status")
                for bid in PHASE6_GRADUATION_ORDER
                if isinstance((board.get("towers") or {}).get(bid), dict)
            },
            "denial_code_enum": board.get("denial_code_enum"),
            "auto_promote": False,
        },
        "m_codes": {
            "pass": codes_ok and m_row_ok,
            "codes": list(GRADUATION_CODES),
            "tower_master_row": m_row_ok,
        },
        "badge_gates": {
            "pass": gates_ok,
            "fee_ledger_fail": bool(gates.get("fee_ledger_fail")),
            "news_fail_open": bool(gates.get("news_fail_open")),
            "cli_bypass": bool(gates.get("cli_bypass")),
            "master_badge_fail_closed": bool(gates.get("master_badge_fail_closed")),
            "badge_allowed": bool(gates.get("badge_allowed")),
        },
        "meme": {
            "pass": meme_ok,
            "status": meme_status,
            "recommend_pause": bool(meme.get("recommend_pause")),
            "retired": bool(meme.get("retired")),
            "expand_volume": bool(meme.get("expand_volume")),
            "window_days": meme.get("window_days"),
            "n": meme.get("n"),
            "expectancy_taxed": meme.get("expectancy_taxed"),
            "action": meme.get("action"),
            "auto_retire": False,
        },
        "order": {
            "pass": order_ok,
            "towers": list(PHASE6_GRADUATION_ORDER),
        },
        "daily_r": {
            "pass": r_ok,
            "commodity": commodity_r,
            "expected_commodity": 2.0,
        },
        "label": (
            f"P6 graduation-gate {'PASS' if gate_pass else 'FAIL'} "
            f"infra={gate_pass} economic={economic_pass} "
            f"masters={masters_n}/3 meme={meme_status} "
            f"weeks={weeks_req} cmd_R={commodity_r}"
        ),
        "note": (
            "Phase 6 Master graduation gate — 2 Chicago weeks M1–M7; thin_n "
            "blocks volume-only Master; meme pause via retirement clock "
            "(never auto-retire); exit ≥3 Masters + meme Master|paused is "
            "economic_pass (ops). Never softens floors; never arms LIVE_ORDERS; "
            "never invents fills/weeks; never force-arms or staff-clears."
        ),
        "decision": (
            "phase6_graduation_gate_pass"
            if gate_pass
            else "phase6_graduation_gate_fail"
        ),
    }


# Phase 7 firm portfolio locks — firm ROI > lonely towers; commodity stays 2.0R.
PHASE7_PORTFOLIO_LOCKS = {
    "btc_inx_veto": True,
    "wti_brent_haircut": 0.5,
    "meme_isolated": True,
    "barbell_meme_max": BARBELL_MEME_MAX,
    "barbell_fee_clear_min": BARBELL_FEE_CLEAR_MIN,
    "daily_r": dict(DAILY_R_BUDGET),
    "profit_lock_target_usd": PROFIT_LOCK_TARGET_USD,
    "profit_lock_size_mult": PROFIT_LOCK_SIZE_MULT,
    "incubation_min_n": INCUBATION_MIN_N,
    "meme_window_days": MEME_RETIRE_WINDOW_DAYS,
    "meme_auto_retire": False,
    "auto_promote": False,
    "commodity_daily_r": 2.0,
    "firm_m1_exit_weeks": 2,
    "active_towers_exit_n": 3,
    "note": (
        "Firm portfolio: BTC↔INX hard veto; WTI↔Brent 0.5× haircut; meme isolated; "
        "barbell meme≤15% / fee-clear≥70%; daily R (sports 1.5 / BTC+cmd 2.0); "
        "profit-lock $40 → 0.5×; incubation n≥50; meme pause never auto-retire. "
        "Exit: firm M1≥0 for 2 weeks with ≥3 active towers + retirement path tested."
    ),
}


def phase7_portfolio_gate(
    root: str | None = None,
    *,
    bots: list | None = None,
    cfg: dict | None = None,
) -> dict:
    """Phase 7 firm portfolio construction exit gate (master plan).

    Pass when infrastructure + locks are honest:
      1. Correlation: BTC↔INX veto, WTI↔Brent haircut, meme isolated sleeve.
      2. Daily R budgets locked (sports 1.5R, BTC/cmd 2.0R); settle-only blocks.
      3. Profit-lock harvest: $40 target → 0.5× size; never invents PnL.
      4. Incubation lane: n≥50 fee-aware settles; auto_promote=False.
      5. Meme retirement clock: recommend pause; never auto-retire / expand.
      6. Green-or-gone + capital OS barbell + bleed/heat boards wired.
      7. Commodity daily R locked at 2.0; floors locked; LIVE_ORDERS off.

    Economic exit (firm M1≥0 × 2 weeks with ≥3 active towers + retirement
    path tested) reported as economic_pass — empty boards still pass infra.

    Observe / certify only — never force-arms, staff-clears, or invents fills.
    """
    cfg = cfg or {}
    corr_ok = False
    corr = {}
    try:
        import desk_profit
        corr = desk_profit.correlation_matrix(bots, cfg=cfg) or {}
        hair = desk_profit.SERIES_HAIRCUT_MULT
        pairs = desk_profit.SERIES_HAIRCUT_PAIRS
        corr_ok = (
            bool(corr.get("btc_inx_veto"))
            and bool(corr.get("meme_isolated"))
            and bool(corr.get("fee_floors_locked"))
            and abs(float(hair) - 0.5) < 1e-9
            and ("KXWTI15M", "KXBRENT15M") in tuple(pairs)
            and callable(desk_profit.correlation_veto_reason)
            and callable(desk_profit.series_corr_haircut)
        )
    except Exception:
        corr_ok = False

    r_sports = _finite(DAILY_R_BUDGET.get("sports-gap"))
    r_btc = _finite(DAILY_R_BUDGET.get("btc15m"))
    r_cmd = _finite(DAILY_R_BUDGET.get("commodity-15m"))
    r_ok = (
        r_sports is not None and abs(float(r_sports) - 1.5) < 1e-9
        and r_btc is not None and abs(float(r_btc) - 2.0) < 1e-9
        and r_cmd is not None and abs(float(r_cmd) - 2.0) < 1e-9
        and callable(daily_r_blocks)
        and callable(capture_daily_r_board)
    )

    pl = profit_lock_status(root) or {}
    pl_ok = (
        abs(float(PROFIT_LOCK_TARGET_USD) - 40.0) < 1e-9
        and abs(float(PROFIT_LOCK_SIZE_MULT) - 0.5) < 1e-9
        and callable(capture_profit_lock)
        and callable(profit_lock_size_mult)
        and bool(pl.get("fee_floors_locked", True))
    )

    inc = incubation_board(root) or {}
    inc_ok = (
        int(INCUBATION_MIN_N) >= 50
        and int(inc.get("min_n") or 0) == int(INCUBATION_MIN_N)
        and bool(inc.get("auto_promote") is False)
        and bool(inc.get("fee_floors_locked", True))
    )

    meme_bot = None
    if isinstance(bots, list):
        meme_bot = next(
            (b for b in bots if isinstance(b, dict) and str(b.get("id") or "") == "memecoin"),
            None,
        )
    meme = meme_retirement_clock(meme_bot)
    # Retirement path tested: negative EV window can recommend pause (synthetic probe).
    retire_probe = meme_retirement_clock({
        "id": "memecoin",
        "history": [{"pnl": -1.0, "contracts": 1} for _ in range(max(12, MEME_RETIRE_MIN_N))],
    })
    retire_path_ok = bool(retire_probe.get("recommend_pause")) and bool(
        retire_probe.get("retired") is False
    )
    meme_ok = (
        isinstance(meme, dict)
        and bool(meme.get("retired") is False)
        and bool(meme.get("expand_volume") is False)
        and int(meme.get("window_days") or 0) == int(MEME_RETIRE_WINDOW_DAYS)
        and retire_path_ok
    )

    gog = green_or_gone_status(bots) or {}
    gog_ok = isinstance(gog, dict) and bool(gog.get("fee_floors_locked", True))

    capital = capital_os_status(root, bots=bots, cfg=cfg) or {}
    barbell = capital.get("barbell") if isinstance(capital.get("barbell"), dict) else (
        barbell_status(bots, cfg=cfg) if callable(barbell_status) else {}
    )
    try:
        if not barbell:
            barbell = barbell_status(bots, cfg=cfg) or {}
    except Exception:
        barbell = barbell or {}
    barbell_ok = (
        abs(float(BARBELL_MEME_MAX) - 0.15) < 1e-9
        and abs(float(BARBELL_FEE_CLEAR_MIN) - 0.70) < 1e-9
        and isinstance(barbell, dict)
        and abs(float(barbell.get("meme_max") or BARBELL_MEME_MAX) - 0.15) < 1e-9
    )

    bleed_ok = callable(firm_bleed_ratio) and callable(capture_bleed_week)
    heat_ok = callable(firm_heat_map) and callable(distance_to_zero_board)

    m1 = firm_taxed_m1(bots) or {}
    m1_exp = _finite(m1.get("expectancy_taxed"))
    active_towers = [
        r for r in (m1.get("by_tower") or [])
        if isinstance(r, dict) and int(r.get("n") or 0) > 0
    ]
    # Two Chicago weeks firm M1≥0 — prefer weekly scorecards when present.
    store = _load(_path(WEEKLY_SCORECARD, root), {"paper_only": True, "cards": []})
    cards = [c for c in (store.get("cards") or []) if isinstance(c, dict)]
    cards = sorted(cards, key=lambda c: str(c.get("label") or ""))
    firm_weeks = [
        c for c in cards
        if _finite(c.get("firm_m1") if c.get("firm_m1") is not None else c.get("m1")) is not None
    ][-2:]
    weeks_ok = (
        len(firm_weeks) >= 2
        and all(
            (_finite(c.get("firm_m1") if c.get("firm_m1") is not None else c.get("m1")) or -1)
            + 1e-12 >= 0.0
            for c in firm_weeks
        )
    )
    economic_pass = bool(
        weeks_ok
        and len(active_towers) >= 3
        and m1_exp is not None
        and m1_exp + 1e-12 >= 0.0
        and retire_path_ok
    )

    floors_ok = bool((fee_floors_locked_check() or {}).get("ok"))
    live_off = bool(LIVE_ORDERS_ENABLED) is False

    gate_pass = (
        corr_ok
        and r_ok
        and pl_ok
        and inc_ok
        and meme_ok
        and gog_ok
        and barbell_ok
        and bleed_ok
        and heat_ok
        and floors_ok
        and live_off
    )
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "live_orders_enabled": False,
        "board_chip": False,
        "force_arm": False,
        "invent_fills": False,
        "phase": "P7",
        "pass": gate_pass,
        "economic_pass": economic_pass,
        "locks": dict(PHASE7_PORTFOLIO_LOCKS),
        "correlation": {
            "pass": corr_ok,
            "btc_inx_veto": bool(corr.get("btc_inx_veto")),
            "meme_isolated": bool(corr.get("meme_isolated")),
            "wti_brent_haircut": 0.5,
            "open_n": corr.get("open_n"),
            "label": corr.get("note"),
        },
        "daily_r": {
            "pass": r_ok,
            "sports": r_sports,
            "btc": r_btc,
            "commodity": r_cmd,
            "expected": {"sports-gap": 1.5, "btc15m": 2.0, "commodity-15m": 2.0},
        },
        "profit_lock": {
            "pass": pl_ok,
            "target_usd": float(PROFIT_LOCK_TARGET_USD),
            "size_mult_safe": float(PROFIT_LOCK_SIZE_MULT),
            "safe_mode": bool(pl.get("safe_mode")),
            "size_mult": pl.get("size_mult"),
            "week_pnl": pl.get("week_pnl"),
        },
        "incubation": {
            "pass": inc_ok,
            "min_n": int(INCUBATION_MIN_N),
            "incubating_n": inc.get("incubating_n"),
            "ready_n": inc.get("ready_n"),
            "auto_promote": False,
        },
        "meme_retirement": {
            "pass": meme_ok,
            "recommend_pause": bool(meme.get("recommend_pause")),
            "retired": bool(meme.get("retired")),
            "expand_volume": bool(meme.get("expand_volume")),
            "path_tested": retire_path_ok,
            "auto_retire": False,
            "window_days": meme.get("window_days"),
        },
        "green_or_gone": {
            "pass": gog_ok,
            "board_pass": bool(gog.get("pass")),
            "flagged_n": gog.get("flagged_n"),
            "label": gog.get("label"),
        },
        "barbell": {
            "pass": barbell_ok,
            "meme_max": float(BARBELL_MEME_MAX),
            "fee_clear_min": float(BARBELL_FEE_CLEAR_MIN),
            "label": barbell.get("label") if isinstance(barbell, dict) else None,
        },
        "firm_m1": {
            "expectancy_taxed": m1_exp,
            "active_towers_n": len(active_towers),
            "weeks_n": len(firm_weeks),
            "weeks_ok": weeks_ok,
            "week_labels": [str(c.get("label") or "") for c in firm_weeks],
        },
        "label": (
            f"P7 portfolio-gate {'PASS' if gate_pass else 'FAIL'} "
            f"infra={gate_pass} economic={economic_pass} "
            f"corr={corr_ok} cmd_R={r_cmd} "
            f"pl={PROFIT_LOCK_TARGET_USD:g}/{PROFIT_LOCK_SIZE_MULT:g} "
            f"incub≥{INCUBATION_MIN_N}"
        ),
        "note": (
            "Phase 7 firm portfolio gate — correlation veto/haircut; daily R; "
            "profit-lock $40→0.5×; incubation n≥50; meme pause path tested; "
            "barbell + green-or-gone. Economic exit (firm M1≥0 ×2w, ≥3 towers) "
            "is economic_pass (ops). Never softens floors; never arms LIVE_ORDERS; "
            "never invents fills; never force-arms or staff-clears; never "
            "auto-transfers Kalshi paper wins into meme cash."
        ),
        "decision": (
            "phase7_portfolio_gate_pass"
            if gate_pass
            else "phase7_portfolio_gate_fail"
        ),
    }


# Phase 8 helper evidence locks — scanners feed mains; never place alone until
# Gate A + staff arm; commodity 2.0R / sports 1.5R stay locked.
PHASE8_HELPERS_LOCKS = {
    "helper_gate_a_min_n": HELPER_GATE_A_MIN_N,
    "helper_auto_promote": False,
    "helper_places_orders_default": False,
    "may_place_alone_default": False,
    "skip_regret_auto_loosen": False,
    "ladder_min_p": 0.80,
    "sports_daily_r": 1.5,
    "commodity_daily_r": 2.0,
    "note": (
        "Helpers observe/digest only until Gate A (n≥20, taxed EV≥0) + staff arm. "
        "Skip-regret accept/defer never auto-loosens. Ladder/parlay stay shadow "
        "until Φ≥80 staff promote. ETH calib never auto-writes Φ. "
        "Exit: ≥1 helper-proven promote or documented reject."
    ),
}


def phase8_helpers_gate(
    root: str | None = None,
    *,
    bots: list | None = None,
) -> dict:
    """Phase 8 helper evidence loop exit gate (master plan).

    Pass when infrastructure + locks are honest:
      1. Helper Gate A: n≥20 + taxed EV≥0; auto_promote=False; places_orders=False.
      2. may_place_alone defaults False; autonomy blocked until Gate A + staff arm.
      3. Insight helpers execution lock: no paper_buy/paper_sell / opens.
      4. Skip-regret twin: candidates + accept/defer log; never auto-loosens.
      5. Advice lift board observe-only on Gate A path.
      6. ETH calib publishable without auto Φ write; Phase3 ladder/parlay shadow.
      7. Sports daily R 1.5 + commodity 2.0 locked; floors locked; LIVE off.

    Economic exit (≥1 helper-proven promote OR documented reject) is
    economic_pass — empty boards still pass infra (no invent fills).

    Observe / certify only — never force-arms, staff-clears, or invents evidence.
    """
    gate_a = helper_gate_a(root)
    promote = helper_promote_status(root)
    gate_a_ok = (
        int(HELPER_GATE_A_MIN_N) >= 20
        and int(gate_a.get("min_n") or 0) == int(HELPER_GATE_A_MIN_N)
        and bool(gate_a.get("auto_promote") is False)
        and bool(gate_a.get("places_orders") is False)
        and bool(promote.get("auto_promote") is False)
        and bool(promote.get("places_orders") is False)
        and callable(record_helper_fill)
        and callable(staff_set_helper_autonomy)
    )

    alone_default = helper_may_place_alone(root, "calendar_scanner")
    block_msg = helper_autonomy_blocks(root, "calendar_scanner")
    autonomy_ok = (
        alone_default is False
        and isinstance(block_msg, str)
        and bool(block_msg)  # blocked while thin
    )

    exec_lock = insight_helpers_execution_lock(root) or {}
    exec_ok = (
        bool(exec_lock.get("pass") or exec_lock.get("ok"))
        and bool(exec_lock.get("may_place_alone") is False)
        and bool(exec_lock.get("places_orders") is False)
        and bool(exec_lock.get("auto_promote") is False)
    )

    skip_cands = skip_regret_candidates(root) or {}
    skip_log = skip_regret_decision_log(root) or {}
    skip_ok = (
        bool(skip_cands.get("auto_promote") is False)
        and bool(skip_log.get("auto_promote") is False)
        and bool(skip_log.get("loosen_soft_gates") is False)
        and callable(staff_log_skip_regret_decision)
        and callable(skip_regret_weekly_card)
    )

    advice = helper_advice_lift_board(root) or {}
    advice_log = helper_advice_log_board(root) or {}
    advice_ok = (
        bool(advice.get("auto_promote") is False)
        and bool(advice.get("places_orders") is False)
        and bool(advice.get("gate_a_path") is True)
        and bool(advice.get("staff_arm") is False or advice.get("observe_only"))
    )

    pilots = gate_a_pilots_board(root) or {}
    pilots_ok = (
        bool(pilots.get("auto_promote") is False)
        and bool(pilots.get("staff_arm") is False)
        and bool(pilots.get("observe_only", True))
    )

    eth = eth_calibration_report(bots)
    eth_ok = isinstance(eth, dict) and eth.get("auto_write_phi") is False

    ladder_ok = False
    try:
        import desk_phase3
        ladder_ok = (
            abs(float(desk_phase3.LADDER_MIN_P) - 0.80) < 1e-9
            and callable(getattr(desk_phase3, "evaluate_ladder_rung", None))
        )
    except Exception:
        ladder_ok = False

    r_sports = _finite(DAILY_R_BUDGET.get("sports-gap"))
    r_cmd = _finite(DAILY_R_BUDGET.get("commodity-15m"))
    r_ok = (
        r_sports is not None and abs(float(r_sports) - 1.5) < 1e-9
        and r_cmd is not None and abs(float(r_cmd) - 2.0) < 1e-9
    )

    floors_ok = bool((fee_floors_locked_check() or {}).get("ok"))
    live_off = bool(LIVE_ORDERS_ENABLED) is False

    # Economic: ≥1 helper-proven promote OR documented reject.
    accept_n = int(advice.get("accept_n") or advice_log.get("accept_n") or 0)
    reject_n = int(advice.get("reject_n") or advice_log.get("reject_n") or 0)
    skip_accepts = int(skip_log.get("accepts") or 0)
    skip_defers = int(skip_log.get("defers") or 0)
    ready_n = int(promote.get("ready_n") or 0)
    armed_ready = 0
    for row in promote.get("helpers") or []:
        if isinstance(row, dict) and row.get("armed") and row.get("promote_ready"):
            armed_ready += 1
    documented_decision = bool(
        accept_n >= 1 or reject_n >= 1 or skip_accepts >= 1 or skip_defers >= 1
    )
    proven_promote = bool(armed_ready >= 1)
    economic_pass = bool(documented_decision or proven_promote)

    gate_pass = (
        gate_a_ok
        and autonomy_ok
        and exec_ok
        and skip_ok
        and advice_ok
        and pilots_ok
        and eth_ok
        and ladder_ok
        and r_ok
        and floors_ok
        and live_off
    )
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "live_orders_enabled": False,
        "board_chip": False,
        "force_arm": False,
        "invent_fills": False,
        "places_orders": False,
        "phase": "P8",
        "pass": gate_pass,
        "economic_pass": economic_pass,
        "locks": dict(PHASE8_HELPERS_LOCKS),
        "helper_gate_a": {
            "pass": gate_a_ok,
            "min_n": int(HELPER_GATE_A_MIN_N),
            "ready_n": ready_n,
            "thin_n": promote.get("thin_n"),
            "auto_promote": False,
            "places_orders": False,
            "label": promote.get("label"),
        },
        "autonomy": {
            "pass": autonomy_ok,
            "may_place_alone_default": False,
            "calendar_scanner_alone": alone_default,
            "calendar_scanner_block": block_msg,
        },
        "execution_lock": {
            "pass": exec_ok,
            "ok": exec_lock.get("ok"),
            "violation_n": exec_lock.get("violation_n"),
            "may_place_alone": False,
            "label": exec_lock.get("label"),
        },
        "skip_regret": {
            "pass": skip_ok,
            "candidates_n": len(skip_cands.get("candidates") or []),
            "accepts": skip_accepts,
            "defers": skip_defers,
            "loosen_soft_gates": False,
            "auto_promote": False,
        },
        "advice_lift": {
            "pass": advice_ok,
            "accept_n": accept_n,
            "reject_n": reject_n,
            "lift": advice.get("lift"),
            "gate_a_path": True,
            "staff_arm": bool(advice.get("staff_arm")),
            "label": advice.get("label"),
        },
        "gate_a_pilots": {
            "pass": pilots_ok,
            "any_ready": bool(pilots.get("any_ready")),
            "staff_arm": False,
            "label": pilots.get("label"),
        },
        "eth_calibration": {
            "pass": eth_ok,
            "auto_write_phi": False,
            "n": eth.get("n") if isinstance(eth, dict) else None,
        },
        "ladder_parlay_shadow": {
            "pass": ladder_ok,
            "ladder_min_p": 0.80,
            "shadow_only": True,
        },
        "daily_r": {
            "pass": r_ok,
            "sports": r_sports,
            "commodity": r_cmd,
            "expected": {"sports-gap": 1.5, "commodity-15m": 2.0},
        },
        "economic": {
            "documented_decision": documented_decision,
            "proven_promote": proven_promote,
            "accept_n": accept_n,
            "reject_n": reject_n,
            "skip_accepts": skip_accepts,
            "skip_defers": skip_defers,
            "armed_ready_n": armed_ready,
        },
        "label": (
            f"P8 helpers-gate {'PASS' if gate_pass else 'FAIL'} "
            f"infra={gate_pass} economic={economic_pass} "
            f"gate_a_ready={ready_n} "
            f"advice={accept_n}/{reject_n} "
            f"skip={skip_accepts}/{skip_defers} "
            f"exec_ok={exec_ok}"
        ),
        "note": (
            "Phase 8 helper evidence gate — Gate A n≥20 EV≥0; no place-alone; "
            "exec lock; skip-regret never loosens; advice lift observe; "
            "ETH/ladder shadow. Economic exit (≥1 promote or documented reject) "
            "is economic_pass (ops). Never softens floors; never arms LIVE_ORDERS; "
            "never invents fills; never force-arms or helper auto-buys."
        ),
        "decision": (
            "phase8_helpers_gate_pass"
            if gate_pass
            else "phase8_helpers_gate_fail"
        ),
    }


# Phase 10 ruin drills & harvest locks — soft/hard/nuclear UX; cold 30–50%;
# anti-revenge; stale-world; fee-ledger completeness. No LIVE overrides.
PHASE10_RUIN_LOCKS = {
    "ruin_levels": list(RUIN_LEVELS),
    "cold_harvest_pct_band": [COLD_HARVEST_PCT_MIN, COLD_HARVEST_PCT_MAX],
    "cold_harvest_pct_default": COLD_HARVEST_PCT_DEFAULT,
    "anti_revenge_minutes": ANTI_REVENGE_MINUTES,
    "clock_skew_max_s": CLOCK_SKEW_MAX_SEC,
    "stale_loop_default_s": STALE_LOOP_DEFAULT,
    "fee_ledger_bar": 0.80,
    "one_more_trade_override": False,
    "sports_daily_r": 1.5,
    "commodity_daily_r": 2.0,
    "note": (
        "Ruin soft/hard/nuclear blocks entries (hard/nuclear pause). "
        "Cold harvest 30–50% of green week PnL visible on board. "
        "Anti-revenge + stale-world skip entries; exits still run. "
        "Fee ledger completeness ≥80% once n≥5. "
        "Exit: one full disaster drill passed + harvest rule visible. "
        "Forbidden: one-more-trade overrides after kill."
    ),
}


def phase10_ruin_gate(
    root: str | None = None,
    *,
    bots: list | None = None,
) -> dict:
    """Phase 10 ruin drills & harvest exit gate (master plan).

    Pass when infrastructure + locks are honest:
      1. Soft/hard/nuclear ruin UX: set/clear/status/blocks_entries wired.
      2. Cold harvest 30–50% band + default 40% visible on board.
      3. Anti-revenge same-market cool after stop/flip (minutes locked).
      4. Stale-world / clock-skew skip when loop/quote latency exceeds bar.
      5. Fee ledger completeness path (bar 80%, empty hist passes).
      6. No one-more-trade override after kill (blocks_entries non-empty when armed).
      7. Sports 1.5R + commodity 2.0R locked; floors locked; LIVE off.

    Economic exit (one full disaster drill practiced + harvest rule visible)
    is economic_pass — empty history still passes infra (no invent drills).

    Observe / certify only — never arms LIVE, never invents drills/fills,
    never force-arms or staff-clears.
    """
    ruin = ruin_drill_status(root) or {}
    ruin_ok = (
        tuple(RUIN_LEVELS) == ("soft", "hard", "nuclear")
        and callable(set_ruin_drill)
        and callable(clear_ruin_drill)
        and callable(ruin_drill_blocks_entries)
        and bool(ruin.get("live_orders_enabled") is False)
        and bool(ruin.get("fee_floors_locked") is True)
        and isinstance(ruin.get("levels"), dict)
        and all(k in (ruin.get("levels") or {}) for k in RUIN_LEVELS)
    )

    # Prove blocks fire when soft is armed — always on an isolated temp root so
    # observe/certify never mutates the live desk ruin journal.
    block_probe_ok = False
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as probe_root:
            armed = set_ruin_drill(
                probe_root, "soft", who="phase10_gate", note="infra probe",
            )
            block_msg = ruin_drill_blocks_entries(probe_root)
            cleared = clear_ruin_drill(
                probe_root, who="phase10_gate", note="infra probe clear",
            )
            block_probe_ok = (
                bool(armed.get("ok"))
                and isinstance(block_msg, str)
                and "ruin drill" in block_msg
                and bool(cleared.get("ok"))
                and ruin_drill_blocks_entries(probe_root) == ""
            )
    except Exception:
        block_probe_ok = False

    cold = cold_harvest_status(root) or {}
    band = cold.get("pct_band") or []
    cold_ok = (
        abs(float(COLD_HARVEST_PCT_MIN) - 0.30) < 1e-9
        and abs(float(COLD_HARVEST_PCT_MAX) - 0.50) < 1e-9
        and abs(float(COLD_HARVEST_PCT_DEFAULT) - 0.40) < 1e-9
        and isinstance(band, (list, tuple))
        and len(band) >= 2
        and abs(float(band[0]) - 0.30) < 1e-9
        and abs(float(band[1]) - 0.50) < 1e-9
        and abs(float(cold.get("default_pct") or 0) - 0.40) < 1e-9
        and callable(capture_cold_harvest)
        and bool(cold.get("fee_floors_locked") is True)
    )

    anti = anti_revenge_status(root) or {}
    anti_ok = (
        int(ANTI_REVENGE_MINUTES) >= 15
        and int(anti.get("minutes") or 0) == int(ANTI_REVENGE_MINUTES)
        and callable(anti_revenge_blocks)
        and bool(anti.get("observe_only") is True)
    )

    stale = stale_world_status(root, bots=bots) or {}
    stale_ok = (
        abs(float(CLOCK_SKEW_MAX_SEC) - 30.0) < 1e-9
        and abs(float(STALE_LOOP_DEFAULT) - 40.0) < 1e-9
        and abs(float(stale.get("clock_skew_max_s") or 0) - 30.0) < 1e-9
        and callable(stale_world_blocks)
        and isinstance(stale.get("rows"), list)
    )
    # Probe: over-bar loop must block; under-bar must not.
    try:
        over = stale_world_blocks(root, "btc15m", loop_seconds=STALE_LOOP_SEC.get("btc15m", 40) + 5)
        under = stale_world_blocks(root, "btc15m", loop_seconds=5.0)
        stale_probe_ok = bool(over) and not bool(under)
    except Exception:
        stale_probe_ok = False

    fee = fee_ledger_completeness(root, bots=bots) or {}
    fee_ok = (
        abs(float(fee.get("bar") or 0) - 0.80) < 1e-9
        and bool(fee.get("pass") is True or (fee.get("history_n") or 0) == 0)
        and callable(record_fee_ledger)
        and bool(fee.get("fee_floors_locked") is True)
    )

    r_sports = _finite(DAILY_R_BUDGET.get("sports-gap"))
    r_cmd = _finite(DAILY_R_BUDGET.get("commodity-15m"))
    r_ok = (
        r_sports is not None and abs(float(r_sports) - 1.5) < 1e-9
        and r_cmd is not None and abs(float(r_cmd) - 2.0) < 1e-9
    )
    floors_ok = bool((fee_floors_locked_check() or {}).get("ok"))
    live_off = bool(LIVE_ORDERS_ENABLED) is False

    # No one-more-trade override after kill: entry_gate path + blocks non-empty.
    override_forbidden = True  # PHASE10_RUIN_LOCKS.one_more_trade_override is False
    no_override_ok = (
        override_forbidden is True
        and block_probe_ok
        and callable(ruin_drill_blocks_entries)
    )

    # Economic: one full disaster drill practiced this Chicago month AND harvest
    # rule visible. Empty history → economic_pass False (no invent drills).
    # Temp-root probe never credits practiced_this_month on the live journal.
    history_n = int(ruin.get("history_n") or 0)
    practiced = bool(ruin.get("practiced_this_month"))
    harvest_visible = cold_ok
    harvest_done = bool(
        isinstance(cold.get("latest"), dict)
        and not cold["latest"].get("skipped")
        and float(cold["latest"].get("harvested") or 0) > 0
    )
    disaster_passed = bool(practiced)
    # Plan exit: "One full disaster drill passed; harvest rule visible on board."
    economic_pass = bool(disaster_passed and harvest_visible)

    gate_pass = (
        ruin_ok
        and block_probe_ok
        and cold_ok
        and anti_ok
        and stale_ok
        and stale_probe_ok
        and fee_ok
        and r_ok
        and floors_ok
        and live_off
        and no_override_ok
    )
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "live_orders_enabled": False,
        "board_chip": False,
        "force_arm": False,
        "invent_fills": False,
        "places_orders": False,
        "one_more_trade_override": False,
        "phase": "P10",
        "pass": gate_pass,
        "economic_pass": economic_pass,
        "locks": dict(PHASE10_RUIN_LOCKS),
        "ruin_drill": {
            "pass": ruin_ok and block_probe_ok,
            "levels": list(RUIN_LEVELS),
            "active": bool(ruin.get("active")),
            "history_n": history_n,
            "practiced_this_month": practiced,
            "block_probe_ok": block_probe_ok,
            "live_orders_enabled": False,
        },
        "cold_harvest": {
            "pass": cold_ok,
            "pct_band": [COLD_HARVEST_PCT_MIN, COLD_HARVEST_PCT_MAX],
            "default_pct": COLD_HARVEST_PCT_DEFAULT,
            "cold_total": cold.get("cold_total"),
            "weeks_n": cold.get("weeks_n"),
            "harvest_done": harvest_done,
            "rule_visible": harvest_visible,
        },
        "anti_revenge": {
            "pass": anti_ok,
            "minutes": ANTI_REVENGE_MINUTES,
            "active_n": anti.get("active_n"),
        },
        "stale_world": {
            "pass": stale_ok and stale_probe_ok,
            "clock_skew_max_s": CLOCK_SKEW_MAX_SEC,
            "stale_loop_default_s": STALE_LOOP_DEFAULT,
            "probe_ok": stale_probe_ok,
            "blocked": stale.get("blocked"),
        },
        "fee_ledger": {
            "pass": fee_ok,
            "bar": 0.80,
            "rate": fee.get("rate"),
            "history_n": fee.get("history_n"),
            "ledger_n": fee.get("ledger_n"),
        },
        "daily_r": {
            "pass": r_ok,
            "sports": r_sports,
            "commodity": r_cmd,
            "expected": {"sports-gap": 1.5, "commodity-15m": 2.0},
        },
        "no_override": {
            "pass": no_override_ok,
            "one_more_trade_override": False,
        },
        "economic": {
            "disaster_passed": disaster_passed,
            "harvest_done": harvest_done,
            "harvest_visible": harvest_visible,
        },
        "label": (
            f"P10 ruin-gate {'PASS' if gate_pass else 'FAIL'} "
            f"infra={gate_pass} economic={economic_pass} "
            f"ruin_hist={history_n} practiced={practiced} "
            f"cold_total={cold.get('cold_total')} "
            f"fee_rate={fee.get('rate')}"
        ),
        "note": (
            "Phase 10 ruin drills & harvest gate — soft/hard/nuclear UX; "
            "cold 30–50%; anti-revenge; stale-world; fee completeness. "
            "Economic exit (disaster drill practiced + harvest rule visible) "
            "is economic_pass (ops). Never softens floors; never arms LIVE_ORDERS; "
            "never invents drills/fills; never one-more-trade after kill."
        ),
        "decision": (
            "phase10_ruin_gate_pass"
            if gate_pass
            else "phase10_ruin_gate_fail"
        ),
    }


# Phase 11 continuous hillclimb locks — one allowlisted lever/week forever;
# raise-only floors; no midweek thrash; no auto param write; P9 LIVE blocked.
PHASE11_HILLCLIMB_LOCKS = {
    "allowlist": [
        "VOL_SAFE",
        "HIT_FOR_BIG",
        "venue_min_edge_btc",
        "min_cushion_btc",
        "kelly_fraction",
    ],
    "none_lever": HILLCLIMB_NONE_LEVER,
    "raise_only": ["venue_min_edge_btc", "min_cushion_btc"],
    "idea_review_days": IDEA_REVIEW_DAYS,
    "auto_revert": False,
    "auto_apply": False,
    "parallel_levers": False,
    "midweek_thrash": False,
    "sports_daily_r": 1.5,
    "commodity_daily_r": 2.0,
    "note": (
        "One lever/week from allowlist (or NONE). venue_min_edge_btc / "
        "min_cushion_btc raise-only. Sunday promote/demote; midweek thrash banned. "
        "Kill → staff demote (auto_revert=False). Idea review 90d. Quarterly W rebaseline. "
        "Exit: none — steady state. Forbidden: parallel conflicting lever changes."
    ),
}


def phase11_hillclimb_gate(
    root: str | None = None,
    *,
    bots: list | None = None,
) -> dict:
    """Phase 11 continuous hillclimb steady-state gate (master plan).

    Pass when infrastructure + locks are honest:
      1. Allowlist = VOL_SAFE / HIT_FOR_BIG / venue_min_edge_btc / min_cushion_btc /
         kelly_fraction (+ NONE).
      2. Raise-only on venue_min_edge_btc + min_cushion_btc.
      3. One-lever discipline; midweek thrash blocked; parallel levers forbidden.
      4. Kill flag observe-only with auto_revert=False (staff demote path).
      5. Sunday packet review gate for non-NONE picks.
      6. Idea review cadence 90d; quarterly rebaseline status present.
      7. Sports 1.5R + commodity 2.0R locked; floors locked; LIVE off.

    Plan exit gate is None (forever steady state). economic_pass is ops:
    staff has an active lever (or NONE) this Chicago week — empty stays False.

    Observe / certify only — never auto-picks, never auto-reverts params,
    never arms LIVE, never softens floors.
    """
    _ = bots  # bots unused — hillclimb is desk-journal + constants
    required = (
        "VOL_SAFE",
        "HIT_FOR_BIG",
        "venue_min_edge_btc",
        "min_cushion_btc",
        "kelly_fraction",
    )
    al = hillclimb_allowlist() or {}
    levers = al.get("levers") if isinstance(al.get("levers"), dict) else {}
    allow_ok = (
        all(name in HILLCLIMB_ALLOWLIST for name in required)
        and all(name in levers for name in required)
        and str(al.get("none_lever") or "") == HILLCLIMB_NONE_LEVER
        and bool(HILLCLIMB_ALLOWLIST["venue_min_edge_btc"].get("raise_only"))
        and bool(HILLCLIMB_ALLOWLIST["min_cushion_btc"].get("raise_only"))
        and not bool(HILLCLIMB_ALLOWLIST["VOL_SAFE"].get("raise_only"))
    )

    templates = hillclimb_lever_evidence_templates() or {}
    templates_ok = (
        bool(templates.get("auto_apply") is False)
        and bool(templates.get("observe_only") is True)
        and all(
            (templates.get("templates") or {}).get(n, {}).get("writes_venue_params") is False
            for n in required
        )
    )

    discipline = hillclimb_one_lever_discipline(root) or {}
    discipline_ok = bool(discipline.get("pass") or discipline.get("ok"))

    lever_st = hillclimb_lever_status(root) or {}
    lever_ok = (
        bool(lever_st.get("auto_promote") is False)
        and bool(lever_st.get("auto_revert") is False)
        and bool(lever_st.get("observe_only") is True)
        and bool(lever_st.get("process_only") is True)
        and callable(staff_pick_hillclimb_lever)
        and callable(staff_demote_hillclimb_lever)
    )

    # Midweek thrash banned: second pick same week without force must fail.
    thrash_ok = False
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as probe:
            staff_mark_sunday_packet_reviewed(probe, who="phase11_gate")
            first = staff_pick_hillclimb_lever(
                probe, "VOL_SAFE", note="infra probe", force=False,
            )
            second = staff_pick_hillclimb_lever(
                probe, "HIT_FOR_BIG", note="thrash probe", force=False,
            )
            thrash_ok = bool(first.get("ok")) and not bool(second.get("ok"))
    except Exception:
        thrash_ok = False

    # Raise-only refuse soften: proposed below floor must fail.
    raise_ok = False
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as probe:
            soft = staff_pick_hillclimb_lever(
                probe,
                "venue_min_edge_btc",
                proposed_value=0.03,
                force=True,
                note="raise-only probe",
            )
            raise_ok = not bool(soft.get("ok"))
    except Exception:
        raise_ok = False

    kill = hillclimb_kill_status(root) or {}
    kill_ok = (
        bool(kill.get("auto_revert") is False)
        and bool(kill.get("fee_floors_locked") is True)
        and callable(staff_hillclimb_kill_postmortem)
        and callable(hillclimb_postmortem_board)
    )

    sunday = sunday_packet_review_status(root) or {}
    sunday_ok = (
        callable(staff_mark_sunday_packet_reviewed)
        and "gate_ok" in sunday
        and bool(sunday.get("fee_floors_locked") is True)
    )

    ideas = idea_review_status(root) or {}
    ideas_ok = (
        int(IDEA_REVIEW_DAYS) == 90
        and int(ideas.get("review_days") or 0) == 90
        and bool(ideas.get("auto_promote") is False)
    )

    quarterly = quarterly_rebaseline_status(root) or {}
    quarterly_ok = (
        bool(quarterly.get("fee_floors_locked") is True)
        and "has_quarterly" in quarterly
    )

    e9 = {}
    try:
        e9 = hillclimb_e9_week_board(root) or {}
    except Exception:
        e9 = {}
    e9_ok = True  # optional densify board — presence not required for infra

    r_sports = _finite(DAILY_R_BUDGET.get("sports-gap"))
    r_cmd = _finite(DAILY_R_BUDGET.get("commodity-15m"))
    r_ok = (
        r_sports is not None and abs(float(r_sports) - 1.5) < 1e-9
        and r_cmd is not None and abs(float(r_cmd) - 2.0) < 1e-9
    )
    floors_ok = bool((fee_floors_locked_check() or {}).get("ok"))
    live_off = bool(LIVE_ORDERS_ENABLED) is False

    active_this_week = bool(lever_st.get("active_this_week"))
    economic_pass = bool(active_this_week and discipline_ok)

    gate_pass = (
        allow_ok
        and templates_ok
        and discipline_ok
        and lever_ok
        and thrash_ok
        and raise_ok
        and kill_ok
        and sunday_ok
        and ideas_ok
        and quarterly_ok
        and e9_ok
        and r_ok
        and floors_ok
        and live_off
    )
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "auto_apply": False,
        "auto_revert": False,
        "live_orders_enabled": False,
        "board_chip": False,
        "force_arm": False,
        "invent_fills": False,
        "places_orders": False,
        "parallel_levers": False,
        "midweek_thrash": False,
        "phase": "P11",
        "pass": gate_pass,
        "economic_pass": economic_pass,
        "steady_state": True,
        "locks": dict(PHASE11_HILLCLIMB_LOCKS),
        "allowlist": {
            "pass": allow_ok,
            "levers": list(required),
            "none_lever": HILLCLIMB_NONE_LEVER,
            "raise_only": ["venue_min_edge_btc", "min_cushion_btc"],
        },
        "templates": {
            "pass": templates_ok,
            "auto_apply": False,
            "writes_venue_params": False,
        },
        "discipline": {
            "pass": discipline_ok,
            "ok": discipline.get("ok"),
            "single_entry": discipline.get("single_entry"),
            "off_allowlist": discipline.get("off_allowlist"),
            "lever": discipline.get("lever"),
        },
        "lever_process": {
            "pass": lever_ok and thrash_ok and raise_ok,
            "active_this_week": active_this_week,
            "needs_staff_pick": bool(lever_st.get("needs_staff_pick")),
            "thrash_blocked": thrash_ok,
            "raise_only_blocks_soften": raise_ok,
            "auto_revert": False,
            "label": lever_st.get("label"),
        },
        "kill": {
            "pass": kill_ok,
            "kill": bool(kill.get("kill")),
            "auto_revert": False,
        },
        "sunday_review": {
            "pass": sunday_ok,
            "reviewed": bool(sunday.get("reviewed")),
            "week": sunday.get("week"),
        },
        "idea_review": {
            "pass": ideas_ok,
            "review_days": IDEA_REVIEW_DAYS,
            "open_n": ideas.get("open_n"),
            "stale_n": ideas.get("stale_n"),
        },
        "quarterly": {
            "pass": quarterly_ok,
            "has_quarterly": bool(quarterly.get("has_quarterly")),
        },
        "daily_r": {
            "pass": r_ok,
            "sports": r_sports,
            "commodity": r_cmd,
            "expected": {"sports-gap": 1.5, "commodity-15m": 2.0},
        },
        "economic": {
            "active_this_week": active_this_week,
            "discipline_ok": discipline_ok,
            "steady_state": True,
            "exit_gate": None,
        },
        "label": (
            f"P11 hillclimb-gate {'PASS' if gate_pass else 'FAIL'} "
            f"infra={gate_pass} economic={economic_pass} "
            f"active_week={active_this_week} "
            f"discipline={discipline_ok} "
            f"thrash_blocked={thrash_ok} "
            f"raise_only={raise_ok}"
        ),
        "note": (
            "Phase 11 continuous hillclimb gate — one allowlisted lever/week; "
            "raise-only floors; Sunday review; kill→staff demote; idea 90d; "
            "quarterly W rebaseline. Exit gate is None (steady state). "
            "economic_pass = active lever this Chicago week (ops). "
            "Never softens floors; never arms LIVE_ORDERS; never auto-picks "
            "or auto-reverts params; never parallel conflicting levers."
        ),
        "decision": (
            "phase11_hillclimb_gate_pass"
            if gate_pass
            else "phase11_hillclimb_gate_fail"
        ),
    }


def _exit_kind(text: str | None) -> str:
    t = str(text or "").lower()
    if "scale" in t:
        return "scale_out"
    if "gap" in t and "decay" in t:
        return "gap_decay"
    if "gap closed" in t or "gap-close" in t:
        return "gap_close"
    if "model-flip" in t or "model_flip" in t or "flip" in t:
        return "model_flip"
    if "hard-stop" in t or "hard_stop" in t:
        return "hard_stop"
    if "settled" in t or "settle" in t:
        return "settle"
    if "take-profit" in t or "take_profit" in t or "tp" == t:
        return "take_profit"
    if not t:
        return "unknown"
    return "other"


def _finish_exit_stats(raw: dict, *, min_n: int) -> list:
    out = []
    for k, v in raw.items():
        n = int(v.get("n") or 0)
        hits = int(v.get("hits") or 0)
        out.append({
            "key": k,
            "n": n,
            "hits": hits,
            "hit_rate": round(hits / n, 4) if n else None,
            "expectancy": round(float(v.get("pnl_sum") or 0) / n, 4) if n else None,
            "thin": n < int(min_n),
        })
    out.sort(key=lambda r: -int(r.get("n") or 0))
    return out


def sports_exit_quality_board(
    bots: list | None = None,
    *,
    min_n: int = 5,
) -> dict:
    """E2 observe: sports exit kind hit rates from closed history (paper only)."""
    by_kind: dict[str, dict] = {}
    by_league: dict[str, dict] = {}
    for bot in bots or []:
        if not isinstance(bot, dict):
            continue
        if str(bot.get("id") or "") != "sports-gap":
            continue
        closed = list(bot.get("closed") or bot.get("history") or [])
        for pos in closed:
            if not isinstance(pos, dict):
                continue
            pnl = _finite(pos.get("pnl") if pos.get("pnl") is not None else pos.get("pnl_usd"))
            if pnl is None:
                continue
            kind = _exit_kind(pos.get("exit") or pos.get("exit_reason") or pos.get("reason"))
            league = str(pos.get("league") or "UNK")[:12]
            for bucket, key in ((by_kind, kind), (by_league, league)):
                slot = bucket.setdefault(key, {"n": 0, "hits": 0, "pnl_sum": 0.0})
                slot["n"] += 1
                slot["pnl_sum"] = round(slot["pnl_sum"] + float(pnl), 4)
                if pnl > 0:
                    slot["hits"] += 1
    kinds = _finish_exit_stats(by_kind, min_n=min_n)
    leagues = _finish_exit_stats(by_league, min_n=min_n)
    total_n = sum(int(k.get("n") or 0) for k in kinds)
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "board_chip": False,
        "n": total_n,
        "min_n": int(min_n),
        "by_kind": kinds,
        "by_league": leagues[:12],
        "label": f"sports exit-quality n={total_n} kinds={len(kinds)} (observe)",
        "note": (
            "E2 exit-quality observe — gap-close / flip / scale-out / settle hit rates. "
            "Never softens floors; never arms LIVE_ORDERS."
        ),
    }


def fee_clear_exit_quality_board(
    bots: list | None = None,
    *,
    min_n: int = 5,
) -> dict:
    """E2 observe: BTC + commodity exit kind hit rates (TP / flip / settle)."""
    by_bot: dict[str, dict] = {}
    by_kind: dict[str, dict] = {}
    for bot in bots or []:
        if not isinstance(bot, dict):
            continue
        bid = str(bot.get("id") or "")
        if bid not in ("btc15m", "commodity-15m"):
            continue
        closed = list(bot.get("closed") or bot.get("history") or [])
        for pos in closed:
            if not isinstance(pos, dict):
                continue
            pnl = _finite(pos.get("pnl") if pos.get("pnl") is not None else pos.get("pnl_usd"))
            if pnl is None:
                continue
            kind = _exit_kind(
                pos.get("exit") or pos.get("exit_reason") or pos.get("reason")
                or pos.get("close_reason")
            )
            for bucket, key in ((by_bot, bid), (by_kind, kind)):
                slot = bucket.setdefault(key, {"n": 0, "hits": 0, "pnl_sum": 0.0})
                slot["n"] += 1
                slot["pnl_sum"] = round(slot["pnl_sum"] + float(pnl), 4)
                if pnl > 0:
                    slot["hits"] += 1
    bots_out = _finish_exit_stats(by_bot, min_n=min_n)
    kinds = _finish_exit_stats(by_kind, min_n=min_n)
    total_n = sum(int(k.get("n") or 0) for k in kinds)
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "board_chip": False,
        "n": total_n,
        "min_n": int(min_n),
        "by_bot": bots_out,
        "by_kind": kinds,
        "label": f"btc+commodity exit-quality n={total_n} kinds={len(kinds)} (observe)",
        "note": (
            "E2 fee-clear exit observe — take-profit / model-flip / settle. "
            "Never softens floors; never arms LIVE_ORDERS."
        ),
    }


def selective_throughput_observe(
    root: str | None = None,
    *,
    bots: list | None = None,
) -> dict:
    """E2/E4 observe: selective +1 only when M1 holds on fee-clear greens."""
    m1 = firm_taxed_m1(bots)
    firm_exp = _finite(m1.get("expectancy_taxed"))
    firm_n = int(m1.get("n") or 0)
    m1_holds = firm_n >= 10 and firm_exp is not None and firm_exp + 1e-12 >= 0.0
    boost = sports_green_boost_status(root, bots=bots)
    towers = []
    try:
        import desk_more
        for bot in bots or []:
            if not isinstance(bot, dict):
                continue
            bid = str(bot.get("id") or "")
            if bid not in FEE_CLEAR:
                continue
            today = _finite(bot.get("today"))
            base = 3
            green_boost = int(boost.get("green_boost") or 0) if bid == "sports-gap" else 1
            max_buys = desk_more.selective_max_buys(
                bid, base=base, today=today, green_boost=green_boost,
            )
            towers.append({
                "bot": bid,
                "today": today,
                "green": today is not None and today >= 0,
                "selective_max_buys": max_buys,
                "boosted": max_buys > base,
            })
    except Exception:
        towers = []
    boosted_n = sum(1 for t in towers if t.get("boosted"))
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "board_chip": False,
        "m1_holds": m1_holds,
        "m1": firm_exp,
        "m1_n": firm_n,
        "sports_green_boost": boost.get("green_boost"),
        "sports_green_ready": bool(boost.get("ready") or boost.get("staff_armed")),
        "towers": towers,
        "boosted_n": boosted_n,
        "after_m1": m1_holds,
        "auto_promote": False,
        "live_orders_enabled": False,
        "label": (
            f"selective throughput after_m1={m1_holds} boosted={boosted_n} "
            "(observe · never softens floors)"
        ),
        "note": (
            "Selective +1 only on fee-clear greens when today≥0; "
            "throughput talk only after firm M1 holds. Floors locked."
        ),
    }


def firm_health_observe(
    root: str | None = None,
    *,
    bots: list | None = None,
    cfg: dict | None = None,
) -> dict:
    """Phase 2/7 firm-health pulse: bleed / capital OS / daily R / profit-lock / opp-cost / fees.

    Observe only. Never softens floors. Never arms LIVE_ORDERS.
    """
    bleed_live = firm_bleed_ratio(bots)
    misplaced = capital_misplaced(bots, cfg)
    bleed_card = latest_bleed_week(root) or {}
    capital = capital_os_status(root, bots=bots, cfg=cfg)
    # Prefer live bots.today when provided — a same-day stale latest with
    # settle_only=[] must not hide profit-lock settle-only (#482/#483 sibling).
    daily = latest_daily_r_board(root) or {}
    if bots:
        if root:
            daily = capture_daily_r_board(root, bots=bots)
        else:
            settle_only = []
            towers = {}
            for bot in bots:
                if not isinstance(bot, dict):
                    continue
                bot_id = str(bot.get("id") or "")
                if not bot_id:
                    continue
                row = daily_r_status(bot_id, bot.get("today"))
                towers[bot_id] = row
                if row.get("settle_only"):
                    settle_only.append(bot_id)
            daily = {
                "towers": towers,
                "settle_only": sorted(settle_only),
                "note": "ephemeral daily R (no root)",
            }
    elif not daily:
        daily = {
            "towers": {},
            "settle_only": [],
            "note": "daily R board empty",
        }
    profit = profit_lock_status(root)
    opp = opp_cost_summary(root)
    fees = fee_ledger_completeness(root, bots=bots)
    bleed_pass = bool(bleed_live.get("pass"))
    capital_ok = bool(capital.get("ok"))
    fee_rate = _finite(fees.get("rate"))
    fee_ok = bool(fees.get("pass")) if int(fees.get("history_n") or 0) else True
    alerts = []
    if not bleed_pass:
        alerts.append("bleed")
    if not capital_ok:
        alerts.extend(list(capital.get("alerts") or ["capital_os"]))
    if profit.get("safe_mode"):
        alerts.append("profit_lock_safe")
    if not fee_ok:
        alerts.append("fee_ledger")
    settle_only = list(daily.get("settle_only") or [])
    if settle_only:
        alerts.append("daily_r_settle")
    thin = (not bleed_card) or (
        int(opp.get("n") or 0) == 0 and int(fees.get("history_n") or 0) == 0
    )
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "live_orders_enabled": False,
        "board_chip": False,
        "ok": len(alerts) == 0,
        "evidence_thin": thin,
        "alerts": sorted(set(alerts)),
        "bleed": {
            "ratio": bleed_live.get("ratio"),
            "pass": bleed_pass,
            "red_usd": bleed_live.get("red_usd"),
            "green_usd": bleed_live.get("green_usd"),
            "misplaced_usd": misplaced.get("misplaced_usd"),
            "card_label": bleed_card.get("label"),
            "label_line": bleed_card.get("label_line"),
        },
        "capital_os": {
            "ok": capital_ok,
            "alerts": capital.get("alerts"),
            "barbell_pass": (capital.get("barbell") or {}).get("pass"),
            "midday_alert": (capital.get("midday_util") or {}).get("alert"),
            "zero_buy_alert": (capital.get("zero_buy") or {}).get("alert"),
        },
        "daily_r": {
            "label": daily.get("label"),
            "settle_only": settle_only,
            "r_usd": daily.get("r_usd"),
        },
        "profit_lock": {
            "safe_mode": bool(profit.get("safe_mode")),
            "size_mult": profit.get("size_mult"),
            "week_pnl": profit.get("week_pnl"),
            "target_usd": profit.get("target_usd"),
        },
        "opp_cost": {
            "n": opp.get("n"),
            "mean_wait_s": opp.get("mean_wait_s"),
            "max_wait_s": opp.get("max_wait_s"),
            "bar_sec": opp.get("bar_sec"),
        },
        "fee_ledger": {
            "rate": fee_rate,
            "pass": fee_ok,
            "history_n": fees.get("history_n"),
            "matched": fees.get("matched"),
            "target_gte": fees.get("bar") or 0.80,
        },
        "label": (
            f"firm_health={'ok' if not alerts else 'ALERT'} "
            f"alerts={','.join(alerts) or 'none'} "
            f"bleed={bleed_live.get('ratio')} "
            f"misplaced=${misplaced.get('misplaced_usd')} "
            f"opp_n={opp.get('n')} fee={fee_rate}"
        ),
        "note": (
            "Firm-health observe (bleed <0.5, barbell, daily R settle-only, "
            "profit-lock safe-mode, opp-cost clock, fee-ledger ≥80%). "
            "Never softens floors; never arms LIVE_ORDERS."
        ),
    }


def calib_clv_observe(
    root: str | None = None,
    *,
    bots: list | None = None,
) -> dict:
    """Phase 4 calib + CLV + sticky/green-or-gone flow observe (never writes Φ)."""
    btc = btc_calibration_report(bots)
    eth = eth_calibration_report(bots)
    sports = sports_calibration_report(bots)
    commodity = commodity_calibration_report(bots)
    phi = raise_phi_decision_log(root)
    clv = {"n": 0, "beat_close_rate": None, "avg_clv": None}
    sticky = {"sticky_count": 0, "exit_priority": False, "observe_only": True}
    try:
        import desk_more
        clv = desk_more.clv_summary(root)
        sticky = desk_more.sticky_sla_status(bots)
    except Exception:
        pass
    gog = green_or_gone_status(bots)
    selective = selective_throughput_observe(root, bots=bots)
    alerts = []
    for name, card in (
        ("btc", btc), ("eth", eth), ("sports", sports), ("commodity", commodity),
    ):
        if card.get("miscalibrated") or card.get("action") == "raise_phi":
            alerts.append(f"{name}_raise_phi")
    clv_n = int(clv.get("n") or 0)
    clv_rate = _finite(clv.get("beat_close_rate"))
    if clv_n >= 20 and clv_rate is not None and clv_rate + 1e-12 < 0.52:
        alerts.append("clv_below_52")
    if not gog.get("pass"):
        alerts.append("green_or_gone")
    if sticky.get("exit_priority") and sticky.get("sticky_count"):
        alerts.append("sticky_sla")
    if not selective.get("m1_holds"):
        alerts.append("selective_m1_thin")
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "auto_write_phi": False,
        "live_orders_enabled": False,
        "board_chip": False,
        "ok": len(alerts) == 0,
        "alerts": alerts,
        "btc_calibration": {
            "n": btc.get("n"),
            "series": btc.get("series"),
            "miscalibrated": bool(btc.get("miscalibrated")),
            "action": btc.get("action"),
            "hi_hit_rate": btc.get("hi_hit_rate"),
        },
        "eth_calibration": {
            "n": eth.get("n"),
            "series": eth.get("series"),
            "miscalibrated": bool(eth.get("miscalibrated")),
            "action": eth.get("action"),
            "hi_hit_rate": eth.get("hi_hit_rate"),
        },
        "sports_calibration": {
            "n": sports.get("n"),
            "miscalibrated": bool(sports.get("miscalibrated")),
            "action": sports.get("action"),
            "hi_hit_rate": sports.get("hi_hit_rate"),
        },
        "commodity_calibration": {
            "n": commodity.get("n"),
            "miscalibrated": bool(commodity.get("miscalibrated")),
            "action": commodity.get("action"),
            "hi_hit_rate": commodity.get("hi_hit_rate"),
        },
        "raise_phi_decisions": {
            "n": phi.get("n"),
            "accepts": phi.get("accepts"),
            "defers": phi.get("defers"),
            "auto_write_phi": False,
        },
        "clv": {
            "n": clv_n,
            "avg_clv": clv.get("avg_clv"),
            "beat_close_rate": clv_rate,
            "bar": 0.52,
            "pass": clv_n < 20 or (clv_rate is not None and clv_rate + 1e-12 >= 0.52),
        },
        "clv_leagues": clv.get("by_league") or {},
        "sticky_sla": sticky,
        "green_or_gone": {
            "pass": gog.get("pass"),
            "flagged_n": gog.get("flagged_n"),
            "flags": gog.get("flags"),
        },
        "selective_throughput": {
            "m1_holds": selective.get("m1_holds"),
            "boosted_n": selective.get("boosted_n"),
            "label": selective.get("label"),
        },
        "label": (
            f"calib_clv={'ok' if not alerts else 'ALERT'} "
            f"alerts={','.join(alerts) or 'none'} "
            f"clv={clv_rate} n={clv_n} sticky={sticky.get('sticky_count')} "
            f"gog={gog.get('flagged_n')} selective_m1={selective.get('m1_holds')}"
        ),
        "note": (
            "Calib/CLV observe — BTC/sports/commodity raise_Φ flags never auto-write Φ; "
            "sports CLV bar 52%; sticky exit-priority; green-or-gone starve flags; "
            "selective after M1. Floors locked."
        ),
    }


def baseline_fee_observe(
    root: str | None = None,
    *,
    bots: list | None = None,
    cfg: dict | None = None,
    capture: bool = False,
    label: str | None = None,
) -> dict:
    """W0/baseline artifact + fee-ledger completeness observe (Phase 0 truth)."""
    store = load_baseline(root)
    latest = store.get("latest") if isinstance(store.get("latest"), dict) else None
    if capture and root is not None:
        # Prefer explicit W0 if no baselines yet; else Chicago week tag.
        if label:
            tag = str(label)[:40]
        elif not latest:
            tag = "W0"
        else:
            tag = f"W-{_chicago_week_id()}"[:40]
        latest = capture_baseline(root, bots=bots, cfg=cfg, label=tag)
        store = load_baseline(root)
    fees = fee_ledger_summary(root)
    complete = fee_ledger_completeness(root, bots=bots)
    alerts = []
    if latest is None:
        alerts.append("baseline_missing")
    if not complete.get("pass") and int(complete.get("history_n") or 0) >= 5:
        alerts.append("fee_ledger_thin")
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "live_orders_enabled": False,
        "board_chip": False,
        "ok": len(alerts) == 0,
        "alerts": alerts,
        "baseline": {
            "has_baseline": latest is not None,
            "latest_label": (latest or {}).get("label"),
            "captured_at": (latest or {}).get("captured_at"),
            "baselines_n": len(store.get("baselines") or []),
            "bleed_ratio": ((latest or {}).get("bleed") or {}).get("ratio"),
            "misplaced_usd": ((latest or {}).get("capital_misplaced") or {}).get("misplaced_usd"),
        },
        "fee_ledger": {
            "n": fees.get("n"),
            "fee_sum": fees.get("fee_sum"),
            "fill_tax_sum": fees.get("fill_tax_sum"),
            "completeness": complete,
        },
        "label": (
            f"baseline_fee={'ok' if not alerts else 'ALERT'} "
            f"alerts={','.join(alerts) or 'none'} "
            f"baseline={((latest or {}).get('label') if latest else 'none')} "
            f"fee_n={fees.get('n')} complete={complete.get('rate')}"
        ),
        "note": (
            "Baseline/fee observe — W0 artifact for week-over-week compare; "
            "fee-ledger completeness target ≥80% once n≥5. Floors locked."
        ),
    }


# Money-machine plan slice 1 — Thorp/GS CRB observe + RenTech fee sim.
# Counterfactual only. Never writes kelly_fraction, never LIVE, never softens floors.
LIVE_KELLY_FRACTION = 0.25
HALF_KELLY_FRACTION = 0.50
FEE_CLEAR_CRB_BOTS = ("sports-gap", "btc15m", "commodity-15m")


def fee_sim_probe(
    *,
    venue: str,
    fair: float,
    ask: float,
    contracts: float = 1.0,
) -> dict:
    """Fee-true binary probe: does fair−ask−fee clear the locked venue floor?"""
    import desk_profit

    venue_key = str(venue or "").strip()
    floor = float(desk_profit.DEFAULT_VENUE_MIN_EDGE.get(venue_key) or 0.0)
    p = _finite(fair)
    a = _finite(ask)
    n = _finite(contracts) or 1.0
    if p is None or a is None or not (0.0 < a < 1.0):
        return {
            "ok": False,
            "clear": False,
            "reason": "need fair + ask in (0,1)",
            "venue": venue_key,
            "floor": floor,
            "paper_only": True,
            "fee_floors_locked": True,
        }
    fee = estimate_kalshi_fee(a, n)
    fee_per = fee / n if n else fee
    edge = float(p) - float(a) - float(fee_per)
    clear = edge + 1e-12 >= floor
    return {
        "ok": True,
        "clear": clear,
        "venue": venue_key,
        "fair": round(float(p), 4),
        "ask": round(float(a), 4),
        "fee": round(float(fee), 4),
        "fee_per_contract": round(float(fee_per), 4),
        "edge_after_fee": round(float(edge), 4),
        "floor": floor,
        "contracts": round(float(n), 4),
        "reason": (
            "clears floor" if clear else f"edge {edge:.4f} < floor {floor:g}"
        ),
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "live_orders_enabled": False,
    }


def fee_sim_observe(
    root: str | None = None,
    *,
    probes: list | None = None,
) -> dict:
    """RenTech-style cost gate: kill strategies that cannot clear floors after fees."""
    del root  # reserved for future ledger join; probes are pure math today
    default = probes or [
        {"venue": "kalshi_sports", "fair": 0.62, "ask": 0.52, "label": "sports_lag_ok"},
        {"venue": "kalshi_sports", "fair": 0.55, "ask": 0.52, "label": "sports_thin"},
        {"venue": "kalshi_btc15m", "fair": 0.70, "ask": 0.62, "label": "btc_mid"},
        {"venue": "kalshi_commodity15m", "fair": 0.68, "ask": 0.60, "label": "cmd_mid"},
        {"venue": "kalshi_inx", "fair": 0.88, "ask": 0.84, "label": "inx_band"},
    ]
    rows = []
    clears = 0
    for raw in default:
        if not isinstance(raw, dict):
            continue
        row = fee_sim_probe(
            venue=str(raw.get("venue") or ""),
            fair=float(raw.get("fair") or 0),
            ask=float(raw.get("ask") or 0),
            contracts=float(raw.get("contracts") or 1),
        )
        row["label"] = str(raw.get("label") or row.get("venue") or "")
        if row.get("clear"):
            clears += 1
        rows.append(row)
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "live_orders_enabled": False,
        "ok": True,
        "n": len(rows),
        "clears_n": clears,
        "probes": rows,
        "label": f"fee_sim clears={clears}/{len(rows)} floors_locked",
        "note": (
            "Fee-true probe board — strategies that fail here never get desk cash. "
            "Does not invent fills. Floors locked."
        ),
    }


def dutch_book_probe(
    legs: list | None = None,
    *,
    venue: str = "kalshi_sports",
) -> dict:
    """Exclusive-outcome underround probe after Kalshi fees.

    Buy-all only when sum(ask + fee) < 1 − floor. Overround is the house edge
    (observe, never invent a fade). Floors stay locked.
    """
    import desk_profit

    venue_key = str(venue or "kalshi_sports")
    floor = float(desk_profit.DEFAULT_VENUE_MIN_EDGE.get(venue_key) or 0.0)
    rows = []
    total = 0.0
    for raw in legs or []:
        if not isinstance(raw, dict):
            continue
        ask = _finite(raw.get("ask"))
        if ask is None or not (0.0 < ask < 1.0):
            continue
        fee = estimate_kalshi_fee(ask, 1.0)
        cost = float(ask) + float(fee)
        total += cost
        rows.append({
            "side": str(raw.get("side") or raw.get("game") or ""),
            "ask": round(float(ask), 4),
            "fee": round(float(fee), 4),
            "cost": round(cost, 4),
        })
    if len(rows) < 2:
        return {
            "ok": False,
            "clear": False,
            "reason": "need ≥2 exclusive legs with asks",
            "venue": venue_key,
            "floor": floor,
            "legs": rows,
            "sum_ask_fee": round(total, 4),
            "paper_only": True,
            "fee_floors_locked": True,
            "observe_only": True,
            "auto_promote": False,
            "live_orders_enabled": False,
        }
    edge = 1.0 - total
    clear = edge + 1e-12 >= floor
    return {
        "ok": True,
        "clear": clear,
        "venue": venue_key,
        "floor": floor,
        "legs": rows,
        "sum_ask_fee": round(total, 4),
        "edge": round(edge, 4),
        "reason": (
            "underround clears floor" if clear
            else (
                "overround — house edge" if edge < 0
                else f"underround edge {edge:.4f} < floor {floor:g}"
            )
        ),
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "live_orders_enabled": False,
    }


def dutch_book_observe(
    root: str | None = None,
    *,
    baskets: list | None = None,
) -> dict:
    """Dutch-book / mutual-exclusion completer observe board."""
    del root
    default = baskets or [
        {
            "label": "underround_sports",
            "venue": "kalshi_sports",
            "legs": [{"side": "home", "ask": 0.44}, {"side": "away", "ask": 0.44}],
        },
        {
            "label": "overround_sports",
            "venue": "kalshi_sports",
            "legs": [{"side": "home", "ask": 0.52}, {"side": "away", "ask": 0.52}],
        },
        {
            "label": "thin_underround",
            "venue": "kalshi_sports",
            "legs": [{"side": "home", "ask": 0.47}, {"side": "away", "ask": 0.47}],
        },
    ]
    rows = []
    clears = 0
    for raw in default:
        if not isinstance(raw, dict):
            continue
        probe = dutch_book_probe(raw.get("legs") or [], venue=str(raw.get("venue") or "kalshi_sports"))
        probe["label"] = str(raw.get("label") or "")
        if probe.get("clear"):
            clears += 1
        rows.append(probe)
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "live_orders_enabled": False,
        "ok": True,
        "n": len(rows),
        "clears_n": clears,
        "baskets": rows,
        "label": f"dutch_book clears={clears}/{len(rows)} floors_locked",
        "note": (
            "Exclusive-outcome underround board after fees. "
            "Overround is observe-only (not a short). Floors locked. Never LIVE."
        ),
    }


# Polymarket international taker coefficients (docs.polymarket.com/trading/fees).
# US small-account 0.095 is worse — observe boards default to international.
POLYMARKET_TAKER_RATE = {
    "crypto": 0.07,
    "sports": 0.05,
    "economics": 0.05,
    "econ": 0.05,
    "weather": 0.05,
    "culture": 0.05,
    "other": 0.05,
    "politics": 0.04,
    "finance": 0.04,
    "mentions": 0.04,
    "tech": 0.04,
    "geopolitics": 0.0,
}


def estimate_polymarket_fee(price, category: str = "other", contracts: float = 1.0) -> float:
    """Polymarket international taker: rate × p × (1 − p) × C, ceil to 1¢."""
    p = _finite(price)
    n = _finite(contracts) or 1.0
    if p is None or not (0.0 < p < 1.0) or n <= 0:
        return 0.0
    rate = POLYMARKET_TAKER_RATE.get(str(category or "other").strip().lower())
    if rate is None:
        rate = POLYMARKET_TAKER_RATE["other"]
    raw = float(rate) * float(p) * (1.0 - float(p)) * float(n)
    return math.ceil(round(raw * 100, 6)) / 100.0


def cross_venue_arb_probe(
    row: dict | None = None,
    *,
    kalshi_venue: str = "kalshi_sports",
) -> dict:
    """Kalshi↔Polymarket same-outcome arb probe after both taker fees.

    Buy YES on the cheap book and NO on the other. Incomplete legs skip —
    never invent a complementary ask. Idea-bank / observe only. Never LIVE.
    """
    import desk_profit

    raw = row if isinstance(row, dict) else {}
    venue_key = str(raw.get("kalshi_venue") or kalshi_venue or "kalshi_sports")
    floor = float(desk_profit.DEFAULT_VENUE_MIN_EDGE.get(venue_key) or 0.0)
    category = str(raw.get("poly_category") or raw.get("category") or "other")
    k_yes = _finite(raw.get("kalshi_yes_ask") if raw.get("kalshi_yes_ask") is not None else raw.get("kalshi_ask"))
    p_yes = _finite(raw.get("poly_yes_ask") if raw.get("poly_yes_ask") is not None else raw.get("poly_ask"))
    k_no = _finite(raw.get("kalshi_no_ask"))
    p_no = _finite(raw.get("poly_no_ask"))
    base = {
        "ok": False,
        "clear": False,
        "kalshi_venue": venue_key,
        "floor": floor,
        "poly_category": category,
        "idea_bank_only": True,
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "live_orders_enabled": False,
        "label": str(raw.get("label") or raw.get("outcome") or ""),
    }
    paths = []
    # Path A: Kalshi YES + Poly NO
    if (
        k_yes is not None and p_no is not None
        and 0.0 < k_yes < 1.0 and 0.0 < p_no < 1.0
    ):
        k_fee = estimate_kalshi_fee(k_yes, 1.0)
        p_fee = estimate_polymarket_fee(p_no, category, 1.0)
        cost = float(k_yes) + float(k_fee) + float(p_no) + float(p_fee)
        edge = 1.0 - cost
        paths.append({
            "path": "kalshi_yes+poly_no",
            "cost": round(cost, 4),
            "edge": round(edge, 4),
            "kalshi_fee": round(float(k_fee), 4),
            "poly_fee": round(float(p_fee), 4),
            "clear": edge + 1e-12 >= floor,
        })
    # Path B: Poly YES + Kalshi NO
    if (
        p_yes is not None and k_no is not None
        and 0.0 < p_yes < 1.0 and 0.0 < k_no < 1.0
    ):
        p_fee = estimate_polymarket_fee(p_yes, category, 1.0)
        k_fee = estimate_kalshi_fee(k_no, 1.0)
        cost = float(p_yes) + float(p_fee) + float(k_no) + float(k_fee)
        edge = 1.0 - cost
        paths.append({
            "path": "poly_yes+kalshi_no",
            "cost": round(cost, 4),
            "edge": round(edge, 4),
            "kalshi_fee": round(float(k_fee), 4),
            "poly_fee": round(float(p_fee), 4),
            "clear": edge + 1e-12 >= floor,
        })
    if not paths:
        base["reason"] = "need complete YES+NO asks on both venues — no invent"
        base["paths"] = []
        return base
    best = max(paths, key=lambda r: float(r.get("edge") or -99))
    clear = bool(best.get("clear"))
    base.update({
        "ok": True,
        "clear": clear,
        "paths": paths,
        "best": best,
        "edge": best.get("edge"),
        "reason": (
            "cross-venue arb clears floor" if clear
            else f"best edge {best.get('edge')} < floor {floor:g} (fee wall)"
        ),
    })
    return base


def cross_venue_arb_observe(
    root: str | None = None,
    *,
    pairs: list | None = None,
) -> dict:
    """Kalshi↔Polymarket arb observe board. Idea-bank. Fee-true kill of thin gaps."""
    path = None
    if root:
        cand = os.path.join(root, "desk_poly_arb_pairs.json")
        if os.path.isfile(cand):
            path = cand
    loaded = []
    if path:
        try:
            with open(path, encoding="utf-8") as handle:
                blob = json.load(handle)
            if isinstance(blob, dict):
                loaded = blob.get("pairs") or blob.get("rows") or []
            elif isinstance(blob, list):
                loaded = blob
        except (OSError, json.JSONDecodeError):
            loaded = []
    default = pairs if pairs is not None else loaded
    if not default:
        # Demo fixtures: typical 1¢ mid gap dies after two fees; a fat gap can clear.
        default = [
            {
                "label": "thin_gap_sports",
                "kalshi_venue": "kalshi_sports",
                "poly_category": "sports",
                "kalshi_yes_ask": 0.48,
                "poly_no_ask": 0.50,
            },
            {
                "label": "fat_gap_geopolitics",
                "kalshi_venue": "kalshi_econ",
                "poly_category": "geopolitics",
                "kalshi_yes_ask": 0.40,
                "poly_no_ask": 0.48,
            },
            {
                "label": "incomplete_pair",
                "kalshi_venue": "kalshi_sports",
                "poly_category": "sports",
                "kalshi_yes_ask": 0.45,
            },
        ]
    rows = []
    clears = 0
    for raw in default:
        if not isinstance(raw, dict):
            continue
        probe = cross_venue_arb_probe(raw)
        if probe.get("clear"):
            clears += 1
        rows.append(probe)
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "idea_bank_only": True,
        "auto_promote": False,
        "live_orders_enabled": False,
        "ok": True,
        "n": len(rows),
        "clears_n": clears,
        "pairs": rows,
        "source": path,
        "label": f"poly_arb clears={clears}/{len(rows)} floors_locked",
        "note": (
            "Kalshi↔Polymarket same-outcome arb after both taker fees. "
            "Thin gaps fail the fee wall (research reject as a live tower). "
            "Incomplete legs skipped — no invent. Idea-bank only. Never LIVE."
        ),
    }


POLY_GAMMA = "https://gamma-api.polymarket.com"
POLY_HARVEST_UA = {"User-Agent": "paper-bots-poly-harvest/1.0 (paper-only)"}

# Idea-bank structural match map — same Fed Dec outcomes across venues.
# Asks are live-fetched; never invent a missing leg or fair.
POLY_ARB_MATCH_SEEDS = (
    {
        "label": "fed_dec_no_change",
        "kalshi_ticker": "KXFEDDECISION-26DEC-H0",
        "poly_slug": (
            "will-there-be-no-change-in-fed-interest-rates-after-the-"
            "december-2026-meeting-20260729232808635"
        ),
        "kalshi_venue": "kalshi_econ",
        "poly_category": "finance",
    },
    {
        "label": "fed_dec_cut_25",
        "kalshi_ticker": "KXFEDDECISION-26DEC-C25",
        "poly_slug": (
            "will-the-fed-decrease-interest-rates-by-25-bps-after-the-"
            "december-2026-meeting-20260729232808634"
        ),
        "kalshi_venue": "kalshi_econ",
        "poly_category": "finance",
    },
    {
        "label": "fed_dec_hike_25",
        "kalshi_ticker": "KXFEDDECISION-26DEC-H25",
        "poly_slug": (
            "will-the-fed-increase-interest-rates-by-25-bps-after-the-"
            "december-2026-meeting-20260729232808636"
        ),
        "kalshi_venue": "kalshi_econ",
        "poly_category": "finance",
    },
)


def _http_get_json(url: str, *, opener=None, headers: dict | None = None):
    """GET JSON via opener or urllib. None on miss — never invent."""
    import urllib.request

    opener = opener or (
        lambda u: urllib.request.urlopen(
            urllib.request.Request(u, headers=headers or POLY_HARVEST_UA),
            timeout=12,
        ).read()
    )
    try:
        blob = opener(url)
    except Exception:
        return None
    if blob is None or blob == b"" or blob == "":
        return None
    try:
        if isinstance(blob, bytes):
            return json.loads(blob.decode("utf-8", errors="replace"))
        if isinstance(blob, str):
            return json.loads(blob)
        if isinstance(blob, (dict, list)):
            return blob
    except json.JSONDecodeError:
        return None
    return None


def _kalshi_market_by_ticker(ticker: str, *, opener=None) -> dict | None:
    ticker = str(ticker or "").strip()
    if not ticker:
        return None
    url = f"{KALSHI_PUBLIC}/markets/{ticker}"
    data = _http_get_json(url, opener=opener, headers=MACRO_HARVEST_UA)
    if isinstance(data, dict):
        mkt = data.get("market") if isinstance(data.get("market"), dict) else data
        return mkt if isinstance(mkt, dict) else None
    return None


def _poly_market_by_slug(slug: str, *, opener=None) -> dict | None:
    slug = str(slug or "").strip()
    if not slug:
        return None
    url = f"{POLY_GAMMA}/markets?slug={slug}"
    data = _http_get_json(url, opener=opener, headers=POLY_HARVEST_UA)
    if isinstance(data, list):
        for row in data:
            if isinstance(row, dict) and str(row.get("slug") or "") == slug:
                return row
        return data[0] if data and isinstance(data[0], dict) else None
    if isinstance(data, dict):
        return data
    return None


def _poly_yes_no_asks(market: dict) -> tuple[float | None, float | None]:
    """Binary Poly yes ask + no ask from the same book.

    yes_ask = bestAsk. no_ask = 1 − bestBid (binary complement of the yes bid) —
    same book, not a second venue invent. Missing bid → no_ask None.
    """
    if not isinstance(market, dict):
        return None, None
    yes_ask = _finite(market.get("bestAsk"))
    yes_bid = _finite(market.get("bestBid"))
    if yes_ask is not None:
        if yes_ask > 1.0 + 1e-12 and yes_ask <= 100.0:
            yes_ask = yes_ask / 100.0
        if not (0.0 < yes_ask < 1.0):
            yes_ask = None
    no_ask = None
    if yes_bid is not None:
        if yes_bid > 1.0 + 1e-12 and yes_bid <= 100.0:
            yes_bid = yes_bid / 100.0
        if 0.0 < yes_bid < 1.0:
            no_ask = round(1.0 - float(yes_bid), 4)
            if not (0.0 < no_ask < 1.0):
                no_ask = None
    return yes_ask, no_ask


def _kalshi_yes_no_asks(market: dict) -> tuple[float | None, float | None]:
    """Kalshi yes/no asks from dollars fields. Never invent the other side."""
    if not isinstance(market, dict):
        return None, None
    yes_ask = _kalshi_yes_ask(market)
    no_ask = None
    for key in ("no_ask_dollars", "no_ask"):
        n = _finite(market.get(key))
        if n is None:
            continue
        if n > 1.0 + 1e-12 and n <= 100.0:
            n = n / 100.0
        if 0.0 < n < 1.0:
            no_ask = float(n)
            break
    return yes_ask, no_ask


def poly_kalshi_ask_harvest(
    root: str | None = None,
    *,
    opener=None,
    matches: list | None = None,
) -> dict:
    """Refresh Kalshi↔Polymarket asks for idea-bank match seeds.

    Structural match map only (staff/seed). Live asks from both public books.
    Incomplete legs stay incomplete — never invent a missing venue ask or fair.
    Writes desk_poly_arb_pairs.json for cross_venue_arb_observe.
    """
    root = root or _root()
    seeds = matches if matches is not None else list(POLY_ARB_MATCH_SEEDS)
    # Optional staff override file (tickers/slugs only — no invented prices).
    if matches is None and root:
        path = os.path.join(root, "desk_poly_arb_matches.json")
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as handle:
                    blob = json.load(handle)
                rows = blob.get("matches") if isinstance(blob, dict) else blob
                if isinstance(rows, list) and rows:
                    seeds = [r for r in rows if isinstance(r, dict)]
            except (OSError, json.JSONDecodeError):
                pass

    pairs = []
    complete_n = 0
    incomplete_n = 0
    for seed in seeds:
        if not isinstance(seed, dict):
            continue
        label = str(seed.get("label") or seed.get("kalshi_ticker") or "pair")
        k_ticker = str(seed.get("kalshi_ticker") or "").strip()
        p_slug = str(seed.get("poly_slug") or "").strip()
        venue = str(seed.get("kalshi_venue") or "kalshi_econ")
        category = str(seed.get("poly_category") or "finance")
        k_mkt = _kalshi_market_by_ticker(k_ticker, opener=opener) if k_ticker else None
        p_mkt = _poly_market_by_slug(p_slug, opener=opener) if p_slug else None
        k_yes, k_no = _kalshi_yes_no_asks(k_mkt or {})
        p_yes, p_no = _poly_yes_no_asks(p_mkt or {})
        row = {
            "label": label,
            "kalshi_ticker": k_ticker,
            "poly_slug": p_slug,
            "kalshi_venue": venue,
            "poly_category": category,
            "kalshi_yes_ask": round(k_yes, 4) if k_yes is not None else None,
            "kalshi_no_ask": round(k_no, 4) if k_no is not None else None,
            "poly_yes_ask": round(p_yes, 4) if p_yes is not None else None,
            "poly_no_ask": round(p_no, 4) if p_no is not None else None,
            "source": "live_public_books",
            "idea_bank_only": True,
        }
        # Complete enough for at least one arb path.
        path_a = k_yes is not None and p_no is not None
        path_b = p_yes is not None and k_no is not None
        if path_a or path_b:
            complete_n += 1
        else:
            incomplete_n += 1
        pairs.append(row)

    out_path = os.path.join(root, "desk_poly_arb_pairs.json")
    payload = {
        "paper_only": True,
        "idea_bank_only": True,
        "observe_only": True,
        "fee_floors_locked": True,
        "note": (
            "Live Kalshi↔Polymarket asks for structural match seeds. "
            "Incomplete legs left null — never invent. Idea-bank only."
        ),
        "pairs": pairs,
    }
    try:
        with open(out_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
        wrote = True
    except OSError as exc:
        return {
            "ok": False,
            "paper_only": True,
            "idea_bank_only": True,
            "reason": f"write failed: {exc.__class__.__name__}",
        }

    board = cross_venue_arb_observe(root, pairs=pairs)
    return {
        "ok": True,
        "paper_only": True,
        "idea_bank_only": True,
        "observe_only": True,
        "fee_floors_locked": True,
        "auto_promote": False,
        "live_orders_enabled": False,
        "wrote": wrote,
        "pairs_path": out_path,
        "seed_n": len(seeds),
        "complete_n": complete_n,
        "incomplete_n": incomplete_n,
        "clears_n": int(board.get("clears_n") or 0),
        "board": board,
        "label": (
            f"poly_harvest complete={complete_n}/{len(pairs)} "
            f"clears={board.get('clears_n') or 0} idea_bank"
        ),
        "note": (
            "Public Kalshi+Polymarket asks harvested for Fed Dec match seeds. "
            "Fee wall still kills thin gaps. Never invent missing legs. Never LIVE."
        ),
    }


def cpi_nowcast_probe(row: dict | None = None) -> dict:
    """Cleveland-Fed-style nowcast fair vs Kalshi CPI ask after fees.

    Buy only when nowcast_fair − ask − Kalshi fee ≥ kalshi_econ 0.05.
    Incomplete fair/ask skips — never invent. Idea-bank only (KXCPI).
    """
    import desk_profit

    raw = row if isinstance(row, dict) else {}
    floor = float(desk_profit.DEFAULT_VENUE_MIN_EDGE.get("kalshi_econ") or 0.05)
    fair = _finite(
        raw.get("nowcast_fair") if raw.get("nowcast_fair") is not None else raw.get("fair")
    )
    ask = _finite(raw.get("ask") if raw.get("ask") is not None else raw.get("kalshi_ask"))
    label = str(raw.get("label") or raw.get("strike") or raw.get("ticker") or "cpi")
    base = {
        "ok": False,
        "clear": False,
        "action": "skip",
        "label": label,
        "nowcast_fair": fair,
        "ask": ask,
        "fee": None,
        "edge": None,
        "floor": floor,
        "venue": "kalshi_econ",
        "idea_bank_only": True,
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "live_orders_enabled": False,
    }
    if fair is None or ask is None:
        base["reason"] = "need nowcast_fair + ask — no invent"
        return base
    if not (0.0 < ask < 1.0) or not (0.0 < fair < 1.0):
        base["reason"] = "fair/ask out of range"
        base["ok"] = True
        return base
    fee = estimate_kalshi_fee(ask, 1.0)
    edge = float(fair) - float(ask) - float(fee)
    base.update({
        "ok": True,
        "fee": round(float(fee), 4),
        "edge": round(edge, 4),
        "nowcast_fair": round(float(fair), 4),
        "ask": round(float(ask), 4),
    })
    if edge + 1e-12 < floor:
        base["reason"] = (
            f"cpi edge {edge:.4f} < floor {floor:g} "
            f"(fair {fair:.3f} ask {ask:.3f} fee {fee:.4f})"
        )
        return base
    base["clear"] = True
    base["action"] = "buy"
    base["reason"] = (
        f"cpi nowcast clears floor: fair {fair:.3f} ask {ask:.3f} "
        f"fee {fee:.4f} edge {edge:.4f}"
    )
    return base


def cpi_nowcast_observe(
    root: str | None = None,
    *,
    strikes: list | None = None,
) -> dict:
    """CPI nowcast vs Kalshi observe board. Idea-bank. Floors locked."""
    path = None
    if root:
        cand = os.path.join(root, "desk_cpi_nowcast.json")
        if os.path.isfile(cand):
            path = cand
    loaded = []
    if path:
        try:
            with open(path, encoding="utf-8") as handle:
                blob = json.load(handle)
            if isinstance(blob, dict):
                loaded = blob.get("strikes") or blob.get("quotes") or blob.get("rows") or []
            elif isinstance(blob, list):
                loaded = blob
        except (OSError, json.JSONDecodeError):
            loaded = []
    default = strikes if strikes is not None else loaded
    if not default:
        # Demo: thin nowcast fails econ floor; fat clears; incomplete skipped.
        default = [
            {
                "label": "thin_near_50",
                "strike": "KXCPI-NEAR50",
                "nowcast_fair": 0.55,
                "ask": 0.52,
            },
            {
                "label": "fat_nowcast",
                "strike": "KXCPI-FAT",
                "nowcast_fair": 0.62,
                "ask": 0.50,
            },
            {
                "label": "incomplete",
                "strike": "KXCPI-MISS",
                "ask": 0.48,
            },
        ]
    rows = []
    clears = 0
    for raw in default:
        if not isinstance(raw, dict):
            continue
        probe = cpi_nowcast_probe(raw)
        if probe.get("clear"):
            clears += 1
        rows.append(probe)
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "idea_bank_only": True,
        "auto_promote": False,
        "live_orders_enabled": False,
        "ok": True,
        "n": len(rows),
        "clears_n": clears,
        "strikes": rows,
        "source": path,
        "label": f"cpi_nowcast clears={clears}/{len(rows)} floors_locked",
        "note": (
            "Cleveland-Fed-style CPI nowcast vs Kalshi ask after fees. "
            "KXCPI stays idea-bank for main AUTO. Incomplete fair/ask skipped — "
            "no invent. Floors locked. Never LIVE."
        ),
    }


KALSHI_PUBLIC = "https://api.elections.kalshi.com/trade-api/v2"
MACRO_HARVEST_UA = {"User-Agent": "paper-bots-macro-harvest/1.0 (paper-only)"}


def _kalshi_yes_ask(row: dict) -> float | None:
    """Parse Kalshi yes ask from dollars fields. Never invent."""
    for key in ("yes_ask_dollars", "yes_ask", "ask"):
        n = _finite(row.get(key))
        if n is None:
            continue
        # Legacy integer cents → dollars when clearly out of [0,1].
        if n > 1.0 + 1e-12 and n <= 100.0:
            n = n / 100.0
        if 0.0 < n < 1.0:
            return float(n)
    return None


def _fetch_kalshi_series_markets(
    series: str,
    *,
    opener=None,
    limit: int = 100,
) -> list[dict]:
    """Public Kalshi open markets for one series. Empty on network miss."""
    import urllib.error
    import urllib.request

    series = str(series or "").strip().upper()
    if not series:
        return []
    url = f"{KALSHI_PUBLIC}/markets?series_ticker={series}&status=open&limit={int(limit)}"
    opener = opener or (
        lambda u: __import__("kalshi_gateway").urlopen(
            urllib.request.Request(u, headers=MACRO_HARVEST_UA), timeout=12,
        ).read()
    )
    try:
        blob = opener(url)
    except Exception:
        return []
    if not blob:
        return []
    try:
        if isinstance(blob, bytes):
            data = json.loads(blob.decode("utf-8", errors="replace"))
        elif isinstance(blob, str):
            data = json.loads(blob)
        elif isinstance(blob, dict):
            data = blob
        else:
            return []
    except json.JSONDecodeError:
        return []
    rows = data.get("markets") if isinstance(data, dict) else None
    return [r for r in (rows or []) if isinstance(r, dict)]


def macro_kalshi_harvest(
    root: str | None = None,
    *,
    opener=None,
    limit: int = 100,
) -> dict:
    """Harvest public Kalshi Fed/CPI asks into idea-bank fixtures.

    Writes asks only — FedWatch CME fair and Cleveland CPI nowcast fair are
    left null until staff drops them (never invent). Also builds dutch-book
    baskets for exclusive KXFEDDECISION outcomes at one meeting.
    """
    root = root or _root()
    fed_mkts = _fetch_kalshi_series_markets(
        "KXFEDDECISION", opener=opener, limit=limit,
    )
    # Threshold series is secondary — keep decision markets primary for dutch.
    fed_thr = _fetch_kalshi_series_markets("KXFED", opener=opener, limit=limit)
    cpi_mkts = _fetch_kalshi_series_markets("KXCPI", opener=opener, limit=limit)

    fed_bins: list[dict] = []
    for row in fed_mkts + fed_thr:
        ask = _kalshi_yes_ask(row)
        if ask is None:
            continue
        fed_bins.append({
            "outcome": str(row.get("ticker") or row.get("subtitle") or "fed"),
            "ticker": str(row.get("ticker") or ""),
            "meeting": str(row.get("event_ticker") or ""),
            "title": str(row.get("title") or row.get("subtitle") or "")[:120],
            "ask": round(ask, 4),
            # Fair stays null — CME FedWatch not wired; never invent.
            "fedwatch_fair": None,
            "source": "kalshi_public",
        })

    cpi_rows: list[dict] = []
    for row in cpi_mkts:
        ask = _kalshi_yes_ask(row)
        if ask is None:
            continue
        cpi_rows.append({
            "label": str(row.get("ticker") or "cpi"),
            "strike": str(row.get("ticker") or ""),
            "title": str(row.get("title") or row.get("subtitle") or "")[:120],
            "ask": round(ask, 4),
            # Fair stays null — Cleveland nowcast not wired; never invent.
            "nowcast_fair": None,
            "source": "kalshi_public",
        })

    # Exclusive Fed decision baskets by event for dutch observe.
    by_event: dict[str, list[dict]] = {}
    for row in fed_mkts:
        ask = _kalshi_yes_ask(row)
        if ask is None:
            continue
        event = str(row.get("event_ticker") or "").strip()
        if not event:
            continue
        by_event.setdefault(event, []).append({
            "side": str(row.get("ticker") or row.get("subtitle") or ""),
            "ask": round(ask, 4),
        })
    dutch_baskets = []
    dutch_clears = 0
    for event, legs in sorted(by_event.items()):
        if len(legs) < 2:
            continue
        probe = dutch_book_probe(legs, venue="kalshi_econ")
        probe["label"] = event
        if probe.get("clear"):
            dutch_clears += 1
        dutch_baskets.append(probe)

    tower = os.path.join(root, "fed-watch-paper")
    os.makedirs(tower, exist_ok=True)
    bins_path = os.path.join(tower, "fedwatch_bins.json")
    cpi_path = os.path.join(root, "desk_cpi_nowcast.json")
    bins_payload = {
        "paper_only": True,
        "shadow_only": True,
        "idea_bank_only": True,
        "fee_floors_locked": True,
        "note": (
            "Kalshi public asks only. fedwatch_fair left null until CME "
            "FedWatch is dropped by staff — never invent."
        ),
        "bins": fed_bins,
    }
    cpi_payload = {
        "paper_only": True,
        "idea_bank_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "note": (
            "Kalshi public CPI asks only. nowcast_fair left null until a "
            "Cleveland-style nowcast is dropped — never invent."
        ),
        "strikes": cpi_rows,
    }
    try:
        with open(bins_path, "w", encoding="utf-8") as handle:
            json.dump(bins_payload, handle, indent=2)
            handle.write("\n")
        with open(cpi_path, "w", encoding="utf-8") as handle:
            json.dump(cpi_payload, handle, indent=2)
            handle.write("\n")
        wrote = True
    except OSError as exc:
        return {
            "ok": False,
            "paper_only": True,
            "idea_bank_only": True,
            "reason": f"write failed: {exc.__class__.__name__}",
        }

    # Refresh fed-watch quotes from bins (still no fair → empty quotes).
    quotes_n = 0
    try:
        bot_path = os.path.join(tower, "bot.py")
        if os.path.isfile(bot_path):
            import importlib.util
            spec = importlib.util.spec_from_file_location("fed_watch_harvest", bot_path)
            mod = importlib.util.module_from_spec(spec)
            assert spec.loader is not None
            spec.loader.exec_module(mod)
            harvested = mod.harvest_from_bins(
                root, fed_bins, note="kalshi asks; fair null until CME",
            )
            quotes_n = int(harvested.get("n") or 0)
    except Exception:
        quotes_n = 0

    return {
        "ok": True,
        "paper_only": True,
        "idea_bank_only": True,
        "observe_only": True,
        "fee_floors_locked": True,
        "auto_promote": False,
        "live_orders_enabled": False,
        "wrote": wrote,
        "fed_ask_n": len(fed_bins),
        "cpi_ask_n": len(cpi_rows),
        "fed_quotes_n": quotes_n,
        "waiting_on_fedwatch_fair": True,
        "waiting_on_cpi_nowcast_fair": True,
        "dutch_baskets_n": len(dutch_baskets),
        "dutch_clears_n": dutch_clears,
        "dutch_baskets": dutch_baskets[:12],
        "fedwatch_bins_path": bins_path,
        "cpi_path": cpi_path,
        "label": (
            f"macro_harvest fed_asks={len(fed_bins)} cpi_asks={len(cpi_rows)} "
            f"dutch_clear={dutch_clears}/{len(dutch_baskets)} "
            "waiting_on_external_fair"
        ),
        "note": (
            "Public Kalshi Fed/CPI asks harvested. Fairs stay null until CME "
            "FedWatch / CPI nowcast are staff-dropped — never invent. "
            "Dutch underrounds on exclusive Fed decision legs are fee-true."
        ),
    }


def _fee_clear_probe(
    *,
    fair,
    ask,
    venue: str,
    label: str,
    extra: dict | None = None,
) -> dict:
    """Shared fee-aware fair−ask probe for tower densify observes."""
    import desk_profit

    floor = float(desk_profit.DEFAULT_VENUE_MIN_EDGE.get(venue) or 0.0)
    f = _finite(fair)
    a = _finite(ask)
    row = {
        "ok": False,
        "clear": False,
        "action": "skip",
        "label": label,
        "fair": f,
        "ask": a,
        "fee": None,
        "edge": None,
        "floor": floor,
        "venue": venue,
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "live_orders_enabled": False,
    }
    if extra:
        row.update(extra)
    if f is None or a is None:
        row["reason"] = "need fair + ask — no invent"
        return row
    if not (0.0 < a < 1.0) or not (0.0 < f < 1.0):
        row["ok"] = True
        row["reason"] = "fair/ask out of range"
        return row
    fee = estimate_kalshi_fee(a, 1.0)
    edge = float(f) - float(a) - float(fee)
    row.update({
        "ok": True,
        "fee": round(float(fee), 4),
        "edge": round(edge, 4),
        "fair": round(float(f), 4),
        "ask": round(float(a), 4),
    })
    if edge + 1e-12 < floor:
        row["reason"] = (
            f"edge {edge:.4f} < floor {floor:g} "
            f"(fair {f:.3f} ask {a:.3f} fee {fee:.4f})"
        )
        return row
    row["clear"] = True
    row["action"] = "buy"
    row["reason"] = (
        f"clears floor: fair {f:.3f} ask {a:.3f} fee {fee:.4f} edge {edge:.4f}"
    )
    return row


def btc_vol_binary_probe(row: dict | None = None) -> dict:
    """DVOL/sigma model fair vs btc15m ask. Floor kalshi_btc15m 0.05 locked."""
    raw = row if isinstance(row, dict) else {}
    fair = raw.get("vol_fair") if raw.get("vol_fair") is not None else raw.get("fair")
    ask = raw.get("ask") if raw.get("ask") is not None else raw.get("kalshi_ask")
    dvol = _finite(raw.get("dvol"))
    return _fee_clear_probe(
        fair=fair,
        ask=ask,
        venue="kalshi_btc15m",
        label=str(raw.get("label") or raw.get("ticker") or "btc15m"),
        extra={"dvol": dvol, "kind": "btc_vol_binary"},
    )


def commodity_curve_probe(row: dict | None = None) -> dict:
    """Curve/roll-yield fair vs commodity-15m ask. Floor 0.05 locked."""
    raw = row if isinstance(row, dict) else {}
    fair = (
        raw.get("curve_fair") if raw.get("curve_fair") is not None
        else raw.get("fair")
    )
    ask = raw.get("ask") if raw.get("ask") is not None else raw.get("kalshi_ask")
    roll = _finite(raw.get("roll_yield"))
    regime = str(raw.get("eia_regime") or raw.get("regime") or "")
    return _fee_clear_probe(
        fair=fair,
        ask=ask,
        venue="kalshi_commodity15m",
        label=str(raw.get("label") or raw.get("ticker") or "commodity"),
        extra={
            "roll_yield": roll,
            "eia_regime": regime,
            "kind": "commodity_curve",
        },
    )


FEATURE_STORE_NAME = "desk_feature_store.jsonl"
BTC_VOL_BINARY_NAME = "desk_btc_vol_binary.json"
COMMODITY_CURVE_NAME = "desk_commodity_curve.json"
VOL_CURVE_HARVEST_LIMIT = 50


def _feature_store_rows(root: str | None, *, bots: set[str], limit: int = 200) -> list[dict]:
    """Newest feature-store rows for bots that already logged model_p + ask."""
    path = os.path.join(root or _root(), FEATURE_STORE_NAME)
    if not os.path.isfile(path):
        return []
    want = {str(b) for b in bots}
    matched: list[dict] = []
    try:
        with open(path, encoding="utf-8") as handle:
            lines = handle.readlines()
    except OSError:
        return []
    for ln in reversed(lines):
        try:
            row = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        if str(row.get("bot") or "") not in want:
            continue
        if _finite(row.get("model_p")) is None or _finite(row.get("ask")) is None:
            continue
        matched.append(row)
        if len(matched) >= int(limit):
            break
    matched.reverse()
    return matched


def _eia_regime_from_row(row: dict) -> str:
    codes = row.get("skip_codes") or []
    blob = " ".join(str(c) for c in codes) + " " + str(row.get("note") or "")
    low = blob.lower()
    if "eia" in low or "inventory" in low or "blackout" in low:
        return "eia_blackout"
    return str(row.get("eia_regime") or row.get("regime") or "")


def vol_curve_harvest(
    root: str | None = None,
    *,
    limit: int = VOL_CURVE_HARVEST_LIMIT,
) -> dict:
    """Write BTC/commodity observe fixtures from feature-store (+ closed) rows.

    Only keeps rows that already have model fair + ask. Never invents DVOL,
    roll yield, or missing prices. Floors stay locked. Observe only.
    """
    root = root or _root()
    limit = max(1, int(limit or VOL_CURVE_HARVEST_LIMIT))
    btc_src = _feature_store_rows(root, bots={"btc15m"}, limit=limit * 2)
    cmd_src = _feature_store_rows(root, bots={"commodity-15m"}, limit=limit * 2)
    btc_rows: list[dict] = []
    for row in btc_src:
        fair = _finite(row.get("model_p"))
        ask = _finite(row.get("ask"))
        if fair is None or ask is None:
            continue
        if not (0.0 < fair < 1.0) or not (0.0 < ask < 1.0):
            continue
        btc_rows.append({
            "label": str(row.get("ticker") or row.get("series") or "btc15m"),
            "ticker": str(row.get("ticker") or ""),
            "vol_fair": round(float(fair), 4),
            "ask": round(float(ask), 4),
            "dvol": _finite(row.get("dvol") if row.get("dvol") is not None else row.get("sig_dvol")),
            "z": _finite(row.get("z")),
            "source": "feature_store",
            "at": str(row.get("at") or ""),
        })
        if len(btc_rows) >= limit:
            break
    cmd_rows: list[dict] = []
    for row in cmd_src:
        fair = _finite(row.get("model_p"))
        ask = _finite(row.get("ask"))
        if fair is None or ask is None:
            continue
        if not (0.0 < fair < 1.0) or not (0.0 < ask < 1.0):
            continue
        cmd_rows.append({
            "label": str(row.get("ticker") or row.get("series") or "commodity"),
            "ticker": str(row.get("ticker") or ""),
            "curve_fair": round(float(fair), 4),
            "ask": round(float(ask), 4),
            # Roll yield is not in the feature store — leave null (no invent).
            "roll_yield": _finite(row.get("roll_yield")),
            "eia_regime": _eia_regime_from_row(row),
            "z": _finite(row.get("z")),
            "source": "feature_store",
            "at": str(row.get("at") or ""),
        })
        if len(cmd_rows) >= limit:
            break
    # Supplement commodity from closed fair_at_entry when store is thin.
    if len(cmd_rows) < limit:
        closed_path = os.path.join(root, "commodity-15m-paper", "paper_account.json")
        try:
            with open(closed_path, encoding="utf-8") as handle:
                acc = json.load(handle)
        except (OSError, json.JSONDecodeError):
            acc = {}
        for row in reversed(list(acc.get("closed") or [])):
            if not isinstance(row, dict):
                continue
            fair = _finite(
                row.get("fair_at_entry") if row.get("fair_at_entry") is not None else row.get("fair")
            )
            ask = _finite(row.get("ask"))
            if fair is None or ask is None:
                continue
            if not (0.0 < fair < 1.0) or not (0.0 < ask < 1.0):
                continue
            tick = str(row.get("ticker") or "")
            if any(r.get("ticker") == tick for r in cmd_rows):
                continue
            cmd_rows.append({
                "label": tick or "commodity",
                "ticker": tick,
                "curve_fair": round(float(fair), 4),
                "ask": round(float(ask), 4),
                "roll_yield": None,
                "eia_regime": str(row.get("vol_regime") or ""),
                "z": None,
                "source": "closed_fair_at_entry",
                "at": str(row.get("closed") or row.get("opened") or ""),
            })
            if len(cmd_rows) >= limit:
                break
    btc_path = os.path.join(root, BTC_VOL_BINARY_NAME)
    cmd_path = os.path.join(root, COMMODITY_CURVE_NAME)
    btc_payload = {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "venue": "kalshi_btc15m",
        "floor": 0.05,
        "note": "Harvested model_p+ask from feature store — never invent DVOL",
        "rows": btc_rows,
    }
    cmd_payload = {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "venue": "kalshi_commodity15m",
        "floor": 0.05,
        "note": "Harvested model_p/fair_at_entry+ask — never invent roll yield",
        "rows": cmd_rows,
    }
    try:
        with open(btc_path, "w", encoding="utf-8") as handle:
            json.dump(btc_payload, handle, indent=2)
            handle.write("\n")
        with open(cmd_path, "w", encoding="utf-8") as handle:
            json.dump(cmd_payload, handle, indent=2)
            handle.write("\n")
        wrote = True
    except OSError as exc:
        return {
            "ok": False,
            "paper_only": True,
            "observe_only": True,
            "fee_floors_locked": True,
            "reason": f"write failed: {exc.__class__.__name__}",
            "btc_n": len(btc_rows),
            "commodity_n": len(cmd_rows),
        }
    return {
        "ok": True,
        "paper_only": True,
        "observe_only": True,
        "fee_floors_locked": True,
        "auto_promote": False,
        "live_orders_enabled": False,
        "btc_n": len(btc_rows),
        "commodity_n": len(cmd_rows),
        "btc_path": btc_path,
        "commodity_path": cmd_path,
        "wrote": wrote,
        "note": (
            "Vol/curve harvest from feature-store (+ commodity closed fair_at_entry). "
            "Incomplete fair/ask skipped — no invent. Floors locked. Never LIVE."
        ),
    }


def vol_curve_observe(
    root: str | None = None,
    *,
    btc_rows: list | None = None,
    commodity_rows: list | None = None,
) -> dict:
    """BTC vol-binary + commodity curve densify observe board."""
    btc_path = commodity_path = None
    if root:
        bp = os.path.join(root, BTC_VOL_BINARY_NAME)
        cp = os.path.join(root, COMMODITY_CURVE_NAME)
        if os.path.isfile(bp):
            btc_path = bp
        if os.path.isfile(cp):
            commodity_path = cp

    def _load(path, keys):
        if not path:
            return []
        try:
            with open(path, encoding="utf-8") as handle:
                blob = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return []
        if isinstance(blob, list):
            return blob
        if isinstance(blob, dict):
            for k in keys:
                if isinstance(blob.get(k), list):
                    return blob[k]
        return []

    btc_default = btc_rows if btc_rows is not None else _load(
        btc_path, ("rows", "quotes", "windows"),
    )
    cmd_default = commodity_rows if commodity_rows is not None else _load(
        commodity_path, ("rows", "quotes", "contracts"),
    )
    if not btc_default:
        btc_default = [
            {"label": "thin_dvol", "vol_fair": 0.54, "ask": 0.52, "dvol": 48.0},
            {"label": "fat_dvol", "vol_fair": 0.62, "ask": 0.50, "dvol": 55.0},
            {"label": "incomplete_btc", "ask": 0.51},
        ]
    if not cmd_default:
        cmd_default = [
            {
                "label": "thin_curve",
                "curve_fair": 0.54,
                "ask": 0.52,
                "roll_yield": 0.001,
                "eia_regime": "neutral",
            },
            {
                "label": "fat_backwardation",
                "curve_fair": 0.61,
                "ask": 0.50,
                "roll_yield": -0.012,
                "eia_regime": "draw",
            },
            {"label": "incomplete_cmd", "roll_yield": 0.002},
        ]
    btc_out = []
    btc_clears = 0
    for raw in btc_default:
        if not isinstance(raw, dict):
            continue
        probe = btc_vol_binary_probe(raw)
        if probe.get("clear"):
            btc_clears += 1
        btc_out.append(probe)
    cmd_out = []
    cmd_clears = 0
    for raw in cmd_default:
        if not isinstance(raw, dict):
            continue
        probe = commodity_curve_probe(raw)
        if probe.get("clear"):
            cmd_clears += 1
        cmd_out.append(probe)
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "live_orders_enabled": False,
        "ok": True,
        "btc": {
            "n": len(btc_out),
            "clears_n": btc_clears,
            "rows": btc_out,
            "source": btc_path,
            "floor": 0.05,
            "venue": "kalshi_btc15m",
        },
        "commodity": {
            "n": len(cmd_out),
            "clears_n": cmd_clears,
            "rows": cmd_out,
            "source": commodity_path,
            "floor": 0.05,
            "venue": "kalshi_commodity15m",
        },
        "clears_n": btc_clears + cmd_clears,
        "label": (
            f"vol_curve btc={btc_clears}/{len(btc_out)} "
            f"cmd={cmd_clears}/{len(cmd_out)} floors_locked"
        ),
        "note": (
            "BTC DVOL/vol-binary + commodity curve/EIA densify observe. "
            "Incomplete fair/ask skipped — no invent. Floors stay 0.05. Never LIVE."
        ),
    }


def funding_carry_twins_observe(root: str | None = None) -> dict:
    """ETH observe twin + SOL reject beside the BTC carry sleeve.

    Research rule: ETH is the same factor — a line inside BTC carry, not a
    second tower. SOL 2026 mean is red — reject. Never opens desk cash.
    """
    del root
    tower = os.path.join(_root(), "btc-carry-paper", "bot.py")
    twins = None
    reason = ""
    if os.path.isfile(tower):
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("btc_carry_twins", tower)
            mod = importlib.util.module_from_spec(spec)
            assert spec.loader is not None
            spec.loader.exec_module(mod)
            twins = mod.twin_research_card()
        except Exception as exc:
            reason = f"btc-carry twin import failed: {exc.__class__.__name__}"
    else:
        reason = "btc-carry tower missing"
    if not isinstance(twins, dict):
        return {
            "ok": False,
            "paper_only": True,
            "observe_only": True,
            "fee_floors_locked": True,
            "auto_promote": False,
            "live_orders_enabled": False,
            "second_tower": False,
            "reason": reason or "twin card unavailable",
        }
    return {
        "ok": True,
        "paper_only": True,
        "observe_only": True,
        "fee_floors_locked": True,
        "auto_promote": False,
        "live_orders_enabled": False,
        "second_tower": False,
        "opens_desk_cash": False,
        "twins": twins,
        "label": (
            "funding_twins btc=hold eth=observe sol=reject "
            "no_second_tower floors_locked"
        ),
        "note": twins.get("note") or (
            "ETH observe twin / SOL reject. Only BTC opens the shadow sleeve."
        ),
    }


def half_kelly_crb_observe(
    root: str | None = None,
    *,
    bots: list | None = None,
    cfg: dict | None = None,
) -> dict:
    """GS CRB + Thorp half-Kelly counterfactual vs live kelly_fraction=0.25.

    Observe only. Does not change live sizing, profit-lock, or venue floors.
    """
    import desk_profit

    del root
    cfg = dict(cfg or {})
    live_bots = [b for b in (bots or []) if isinstance(b, dict) and not b.get("shadow_only")]
    desk_open = sum(float(_finite(b.get("open_risk")) or 0.0) for b in live_bots)
    max_risk = float(_finite(cfg.get("max_open_risk")) or 100.0)
    remaining = max(0.0, max_risk - desk_open)
    # Shared probe ticket: fee-clear edge that would size under kelly-lite.
    probe_p, probe_edge, probe_ask = 0.62, 0.08, 0.52
    live_cfg = {**cfg, "sizing": "kelly_lite", "kelly_fraction": LIVE_KELLY_FRACTION}
    half_cfg = {**cfg, "sizing": "kelly_lite", "kelly_fraction": HALF_KELLY_FRACTION}
    live_stake = desk_profit.kelly_lite_dollars(
        probe_p, probe_edge, live_cfg, open_risk_used=desk_open, ask=probe_ask,
    )
    half_stake = desk_profit.kelly_lite_dollars(
        probe_p, probe_edge, half_cfg, open_risk_used=desk_open, ask=probe_ask,
    )
    by_bot = []
    for bot_id in FEE_CLEAR_CRB_BOTS:
        bot = next((b for b in live_bots if str(b.get("id") or "") == bot_id), None)
        open_risk = float(_finite((bot or {}).get("open_risk")) or 0.0) if bot else 0.0
        by_bot.append({
            "bot": bot_id,
            "open_risk": round(open_risk, 2),
            "live_kelly_stake": live_stake,
            "half_kelly_stake": half_stake,
            "delta_usd": round(float(half_stake) - float(live_stake), 2),
        })
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "live_orders_enabled": False,
        "ok": True,
        "live_kelly_fraction": LIVE_KELLY_FRACTION,
        "observe_kelly_fraction": HALF_KELLY_FRACTION,
        "desk_open_risk": round(desk_open, 2),
        "max_open_risk": round(max_risk, 2),
        "remaining_open_risk": round(remaining, 2),
        "probe": {
            "prob": probe_p,
            "edge": probe_edge,
            "ask": probe_ask,
            "note": "Synthetic fee-clear ticket for CRB contrast only",
        },
        "live_kelly_stake": live_stake,
        "half_kelly_stake": half_stake,
        "delta_usd": round(float(half_stake) - float(live_stake), 2),
        "towers": by_bot,
        "label": (
            f"half_kelly_crb live={LIVE_KELLY_FRACTION:g} observe={HALF_KELLY_FRACTION:g} "
            f"Δ=${float(half_stake) - float(live_stake):+.2f} "
            f"open=${desk_open:.2f}/{max_risk:.0f}"
        ),
        "note": (
            "Counterfactual half-Kelly vs live kelly_fraction=0.25 on fee-clear towers. "
            "Does not resize live stakes. Floors locked. Never LIVE."
        ),
    }


def ops_observe(
    root: str | None = None,
    *,
    bots: list | None = None,
) -> dict:
    """Phase 6/7 ops observe: incubation / ruin / cold-harvest / graduation / BTC calib.

    Dual-control status is included as observe-only (LIVE_ORDERS stay deferred).
    """
    incub = incubation_board(root)
    ruin = ruin_drill_status(root)
    cold = cold_harvest_status(root)
    grad = graduation_board(root)
    calib = btc_calibration_report(bots)
    dual = dual_control_status(root)
    incubating = int(incub.get("incubating_n") or 0)
    ready_grad = int(incub.get("ready_n") or 0)
    masters = int((grad.get("masters_n") if isinstance(grad, dict) else None) or 0)
    ruin_active = bool(ruin.get("active"))
    dual_live = bool(dual.get("live_orders_enabled") or dual.get("armed") or dual.get("live"))
    alerts = []
    if ruin_active:
        alerts.append("ruin_drill_active")
    if dual_live:
        alerts.append("dual_control_live")  # unexpected under deferred policy
    if calib.get("miscalibrated"):
        alerts.append("btc_calib")
    shadow_ops = shadow_ops_alerts(root)
    for a in shadow_ops.get("alerts") or []:
        if a and a not in alerts:
            alerts.append(a)
    thin = incubating == 0 and ready_grad == 0 and int(cold.get("weeks_n") or 0) == 0
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "live_orders_enabled": False,
        "board_chip": False,
        "ok": len(alerts) == 0,
        "evidence_thin": thin,
        "alerts": alerts,
        "shadow_ops": shadow_ops,
        "incubation": {
            "incubating_n": incubating,
            "ready_n": ready_grad,
            "graduated_n": incub.get("graduated_n"),
            "min_n": incub.get("min_n"),
        },
        "ruin_drill": {
            "active": ruin_active,
            "level": ruin.get("level"),
            "practiced_this_month": ruin.get("practiced_this_month"),
        },
        "cold_harvest": {
            "cold_total": cold.get("cold_total"),
            "weeks_n": cold.get("weeks_n"),
            "latest": cold.get("latest"),
        },
        "graduation": {
            "masters_n": masters,
            "masters": grad.get("masters") if isinstance(grad, dict) else None,
            "weeks_n": grad.get("weeks_n") if isinstance(grad, dict) else None,
            "towers": grad.get("towers") if isinstance(grad, dict) else None,
        },
        "btc_calibration": {
            "n": calib.get("n"),
            "miscalibrated": bool(calib.get("miscalibrated")),
            "action": calib.get("action"),
            "hi_n": calib.get("hi_n"),
            "hi_hit_rate": calib.get("hi_hit_rate"),
            "hi_label": calib.get("hi_label"),
            "note": calib.get("note"),
        },
        "dual_control": {
            "observe_only": True,
            "deferred": True,
            "live_orders_enabled": False,
            "signed_n": dual.get("signed_n"),
            "items_n": dual.get("items_n"),
            "two_staff": dual.get("two_staff"),
            "arm_ready_paper": dual.get("arm_ready_paper"),
            "checklist_complete": dual.get("checklist_complete"),
            "status": {
                k: dual.get(k)
                for k in (
                    "paper_only",
                    "signed_n",
                    "items_n",
                    "two_staff",
                    "arm_ready_paper",
                    "checklist_complete",
                    "live_orders_enabled",
                    "note",
                )
                if k in dual
            },
            "note": "LIVE_ORDERS dual-control deferred — densified observe keys.",
        },
        "label": (
            f"ops={'ok' if not alerts else 'ALERT'} "
            f"incub={incubating}/{ready_grad} masters={masters} "
            f"ruin={ruin.get('level') or 'off'} cold_w={cold.get('weeks_n')} "
            f"btc_n={calib.get('n')} "
            f"dual={dual.get('signed_n')}/{dual.get('items_n')}"
        ),
        "note": (
            "Ops observe — incubation / ruin drill / cold harvest / Master graduation / "
            "BTC calibration. Dual-control LIVE_ORDERS remain deferred."
        ),
    }


def review_observe(
    root: str | None = None,
    *,
    bots: list | None = None,
) -> dict:
    """Cadence observe: 90d idea review + quarterly rebaseline + corr matrix."""
    ideas = idea_review_status(root)
    quarterly = quarterly_rebaseline_status(root)
    corr = {"fee_floors_locked": True, "note": "correlation_matrix unavailable"}
    try:
        import desk_profit
        corr = desk_profit.correlation_matrix(bots or [])
    except Exception as exc:
        corr = {
            "fee_floors_locked": True,
            "error": str(exc)[:120],
            "note": "correlation_matrix unavailable",
        }
    alerts = []
    if int(ideas.get("stale_n") or 0) > 0:
        alerts.append("idea_stale")
    if not quarterly.get("has_quarterly"):
        alerts.append("quarterly_missing")
    heat = [
        p for p in (corr.get("veto_pairs") or [])
        if isinstance(p, dict) and p.get("heat")
    ]
    if heat:
        alerts.append("corr_heat")
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "live_orders_enabled": False,
        "board_chip": False,
        "ok": len(alerts) == 0,
        "alerts": alerts,
        "idea_review": {
            "open_n": ideas.get("open_n"),
            "stale_n": ideas.get("stale_n"),
            "review_days": ideas.get("review_days"),
            "stale": ideas.get("stale"),
        },
        "quarterly_rebaseline": {
            "has_quarterly": quarterly.get("has_quarterly"),
            "latest": quarterly.get("latest"),
        },
        "correlation": {
            "open_n": corr.get("open_n"),
            "btc_inx_veto": corr.get("btc_inx_veto"),
            "meme_isolated": corr.get("meme_isolated"),
            "series_haircuts": corr.get("series_haircuts"),
            "heat_pairs": heat,
            "veto_pairs": corr.get("veto_pairs"),
        },
        "label": (
            f"review={'ok' if not alerts else 'ALERT'} "
            f"alerts={','.join(alerts) or 'none'} "
            f"ideas_open={ideas.get('open_n')} stale={ideas.get('stale_n')} "
            f"quarterly={quarterly.get('has_quarterly')} heat={len(heat)}"
        ),
        "note": (
            "Review observe — 90d idea cadence, quarterly W rebaseline habit, "
            "BTC↔INX veto + WTI↔Brent haircut matrix. Floors locked."
        ),
    }


def guardrails_observe(
    root: str | None = None,
    *,
    bots: list | None = None,
) -> dict:
    """Entry guardrails observe: empty CARD / stale-world / adverse / anti-revenge."""
    empty = empty_card_status(root)
    stale = stale_world_status(root, bots=bots)
    adverse = adverse_cool_status(root)
    revenge = anti_revenge_status(root)
    alerts = []
    if not empty.get("pass"):
        alerts.append("empty_card")
    if stale.get("blocked"):
        alerts.append("stale_world")
    if int(adverse.get("active_n") or 0) > 0:
        alerts.append("adverse_cool")
    if int(revenge.get("active_n") or 0) > 0:
        alerts.append("anti_revenge")
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "live_orders_enabled": False,
        "board_chip": False,
        "ok": len(alerts) == 0,
        "alerts": alerts,
        "empty_card": {
            "n": empty.get("n"),
            "p50_s": empty.get("p50_s"),
            "bar_sec": empty.get("bar_sec"),
            "pass": empty.get("pass"),
        },
        "stale_world": {
            "blocked": stale.get("blocked"),
            "clock_skew_max_s": stale.get("clock_skew_max_s"),
            "rows": stale.get("rows"),
        },
        "adverse_cool": adverse,
        "anti_revenge": revenge,
        "label": (
            f"guardrails={'ok' if not alerts else 'ALERT'} "
            f"alerts={','.join(alerts) or 'none'} "
            f"empty_p50={empty.get('p50_s')} "
            f"stale={len(stale.get('blocked') or [])} "
            f"adverse={adverse.get('active_n')} revenge={revenge.get('active_n')}"
        ),
        "note": (
            "Guardrails observe — empty CARD <3s, stale-world/clock-skew, "
            "adverse cool-off, anti-revenge same-market block. Floors locked."
        ),
    }


def promote_distance_observe(
    root: str | None = None,
    *,
    bots: list | None = None,
) -> dict:
    """One board: distance-to-promote across money-path staff gates (observe only).

    Never arms LIVE_ORDERS. Never force-promotes. Floors locked.
    """
    inx = inx_band_promote_status(root)
    hard = sports_hard_stop_shadow_summary(root)
    tstop = commodity_time_stop_shadow_summary(root)
    tfinal = sports_time_final_shadow_summary(root)
    green = sports_green_boost_status(root, bots=bots)
    near = near_miss_promote_status(root)
    soft_p = near_miss_soft_p_status(root, bots=bots)
    edge = btc_edge08_shadow_status(root)
    helper = helper_promote_status(root)
    rows = [
        {
            "gate": "inx_band",
            "evidence_thin": bool(inx.get("evidence_thin")),
            "promote_ready": bool(inx.get("promote_ready")),
            "n_to_promote": inx.get("n_to_promote"),
            "label": inx.get("label") or inx.get("reason"),
        },
        {
            "gate": "hard_stop",
            "evidence_thin": bool(hard.get("evidence_thin")),
            "promote_ready": bool(hard.get("promote_ready")),
            "n_to_promote": hard.get("n_to_promote"),
            "label": hard.get("label"),
        },
        {
            "gate": "commodity_time_stop",
            "evidence_thin": bool(tstop.get("evidence_thin")),
            "promote_ready": bool(tstop.get("promote_ready")),
            "n_to_promote": tstop.get("n_to_promote"),
            "label": tstop.get("label"),
        },
        {
            "gate": "sports_time_final",
            "evidence_thin": bool(tfinal.get("evidence_thin")),
            "promote_ready": bool(tfinal.get("promote_ready")),
            "n_to_promote": tfinal.get("n_to_promote"),
            "label": tfinal.get("label"),
        },
        {
            "gate": "green_boost",
            "evidence_thin": bool(green.get("evidence_thin")),
            "promote_ready": bool(green.get("ready")),
            "n_to_promote": None,
            "missing": green.get("missing"),
            "label": green.get("label"),
        },
        {
            "gate": "near_miss",
            "evidence_thin": bool(near.get("evidence_thin")),
            "promote_ready": bool(near.get("promote_ready")),
            "n_to_promote": near.get("n_to_promote"),
            "label": near.get("label"),
        },
        {
            "gate": "near_miss_soft_p",
            "evidence_thin": bool(soft_p.get("evidence_thin")),
            "promote_ready": bool(soft_p.get("soft_p_ready")),
            "n_to_promote": soft_p.get("n_to_promote"),
            "label": soft_p.get("label"),
        },
        {
            "gate": "edge08",
            "evidence_thin": bool(edge.get("evidence_thin")),
            "promote_ready": bool(edge.get("promote_ready")),
            "n_to_promote": edge.get("n_to_promote"),
            "label": edge.get("label"),
        },
        {
            "gate": "helper_gate_a",
            "evidence_thin": bool(helper.get("evidence_thin")),
            "promote_ready": int(helper.get("ready_n") or 0) > 0 and not helper.get("evidence_thin"),
            "n_to_promote": None,
            "thin_n": helper.get("thin_n"),
            "label": helper.get("label"),
        },
    ]
    thin_n = sum(1 for r in rows if r.get("evidence_thin"))
    ready_n = sum(1 for r in rows if r.get("promote_ready"))
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "live_orders_enabled": False,
        "board_chip": False,
        "gates": rows,
        "thin_n": thin_n,
        "ready_n": ready_n,
        "evidence_thin": thin_n > 0,
        "label": f"promote_distance thin={thin_n}/{len(rows)} ready={ready_n}",
        "note": (
            "Promote-distance observe across INX / hard-stop / commodity "
            "time-stop / sports time-final / green_boost / near-miss / "
            "edge08 / helper Gate A. Evidence catch-up deferred; "
            "no force; dual-control LIVE_ORDERS still off."
        ),
    }


def exit_regret_observe(
    root: str | None = None,
    *,
    bots: list | None = None,
) -> dict:
    """E2 KPIs: settle losers that had a shadow exit chance; BTC TP giveback; INX flip save.

    Observe only — does not arm live sells or soften floors.
    """
    sports_settle_losers = 0
    sports_with_shadow = 0
    btc_settle_n = 0
    btc_givebacks: list[float] = []
    inx_flip_n = 0
    inx_flip_save_sum = 0.0
    meme_kinds: dict[str, int] = {}
    for bot in bots or []:
        if not isinstance(bot, dict):
            continue
        bid = str(bot.get("id") or "")
        closed = list(bot.get("closed") or bot.get("history") or [])
        for pos in closed:
            if not isinstance(pos, dict):
                continue
            pnl = _finite(pos.get("pnl") if pos.get("pnl") is not None else pos.get("pnl_usd"))
            kind = _exit_kind(
                pos.get("exit") or pos.get("exit_reason") or pos.get("reason")
                or pos.get("close_reason") or pos.get("status")
            )
            if bid == "sports-gap" and kind == "settle" and pnl is not None and pnl < 0:
                sports_settle_losers += 1
                if pos.get("hard_stop_shadowed") or pos.get("time_final_shadowed"):
                    sports_with_shadow += 1
            if bid == "btc15m" and kind == "settle":
                btc_settle_n += 1
                tp = _finite(pos.get("take_profit"))
                exit_px = _finite(
                    pos.get("exit_price") if pos.get("exit_price") is not None
                    else pos.get("settle_price")
                )
                # Binary settle pays 0 or 1 — use payout/contracts when price missing.
                if exit_px is None:
                    contracts = _finite(pos.get("contracts")) or 0.0
                    payout = _finite(pos.get("payout"))
                    if contracts > 0 and payout is not None:
                        exit_px = round(float(payout) / float(contracts), 4)
                if tp is not None and exit_px is not None and exit_px + 1e-12 < tp:
                    btc_givebacks.append(round(float(tp) - float(exit_px), 4))
            if bid in ("kalshi-sp", "kalshi-sized") and kind == "model_flip":
                inx_flip_n += 1
                cost = _finite(pos.get("cost"))
                if pnl is not None and cost is not None:
                    # Counterfactual full wipe ≈ −cost; save = pnl − (−cost).
                    inx_flip_save_sum = round(inx_flip_save_sum + float(pnl) + float(cost), 4)
            if bid == "memecoin":
                meme_kinds[kind] = int(meme_kinds.get(kind) or 0) + 1
    shadow_share = (
        round(sports_with_shadow / sports_settle_losers, 4)
        if sports_settle_losers else None
    )
    avg_giveback = (
        round(sum(btc_givebacks) / len(btc_givebacks), 4) if btc_givebacks else None
    )
    meme_hist = [
        {"key": k, "n": n} for k, n in sorted(meme_kinds.items(), key=lambda kv: -kv[1])
    ]
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "board_chip": False,
        "sports_settle_losers": sports_settle_losers,
        "sports_settle_losers_with_shadow": sports_with_shadow,
        "sports_shadow_share": shadow_share,
        "btc_settle_n": btc_settle_n,
        "btc_tp_giveback_n": len(btc_givebacks),
        "btc_tp_giveback_avg": avg_giveback,
        "inx_flip_n": inx_flip_n,
        "inx_flip_save_usd": inx_flip_save_sum if inx_flip_n else None,
        "meme_exit_histogram": meme_hist[:12],
        "label": (
            f"exit_regret sports_losers_shadow="
            f"{sports_with_shadow}/{sports_settle_losers} "
            f"btc_giveback_avg={avg_giveback} inx_flip_save={inx_flip_save_sum if inx_flip_n else None}"
        ),
        "note": (
            "E2 exit-regret KPIs — share of sports settle losers that already "
            "logged hard-stop/time-final shadow; BTC settle vs TP giveback (¢); "
            "INX model-flip save vs wipe; meme exit histogram. Floors locked."
        ),
    }


def exit_quality_observe(
    root: str | None = None,
    *,
    bots: list | None = None,
) -> dict:
    """Combined E2 exit-quality + hard-stop shadow + selective observe board."""
    coverage = exit_plan_coverage(root, bots=bots)
    sports = sports_exit_quality_board(bots)
    fee_clear = fee_clear_exit_quality_board(bots)
    regret = exit_regret_observe(root, bots=bots)
    hard = sports_hard_stop_shadow_summary(root)
    tstop = commodity_time_stop_shadow_summary(root)
    tfinal = sports_time_final_shadow_summary(root)
    selective = selective_throughput_observe(root, bots=bots)
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "live_orders_enabled": False,
        "board_chip": False,
        "exit_plan_coverage": coverage,
        "sports_exits": sports,
        "fee_clear_exits": fee_clear,
        "exit_regret": regret,
        "hard_stop_shadow": {
            "n": hard.get("n"),
            "n_with_pnl": hard.get("n_with_pnl"),
            "shadow_expectancy": hard.get("shadow_expectancy"),
            "promote_min_n": hard.get("promote_min_n"),
            "promote_ready": hard.get("promote_ready"),
            "evidence_thin": hard.get("evidence_thin"),
            "n_to_promote": max(
                0,
                int(hard.get("promote_min_n") or 30) - int(hard.get("n_with_pnl") or 0),
            ),
            "live": hard.get("live"),
            "decision": hard.get("decision"),
            "label": hard.get("label"),
        },
        "commodity_time_stop": {
            "n": tstop.get("n"),
            "n_with_pnl": tstop.get("n_with_pnl"),
            "shadow_expectancy": tstop.get("shadow_expectancy"),
            "promote_min_n": tstop.get("promote_min_n"),
            "promote_ready": tstop.get("promote_ready"),
            "evidence_thin": tstop.get("evidence_thin"),
            "n_to_promote": tstop.get("n_to_promote"),
            "live": tstop.get("live"),
            "decision": tstop.get("decision"),
            "label": tstop.get("label"),
        },
        "sports_time_final": {
            "n": tfinal.get("n"),
            "n_with_pnl": tfinal.get("n_with_pnl"),
            "shadow_expectancy": tfinal.get("shadow_expectancy"),
            "promote_min_n": tfinal.get("promote_min_n"),
            "promote_ready": tfinal.get("promote_ready"),
            "evidence_thin": tfinal.get("evidence_thin"),
            "n_to_promote": tfinal.get("n_to_promote"),
            "live": tfinal.get("live"),
            "decision": tfinal.get("decision"),
            "label": tfinal.get("label"),
        },
        "selective_throughput": selective,
        "label": (
            f"E2 exit-quality cover={coverage.get('n_with_plan')}/"
            f"{coverage.get('n_open')} sports_n={sports.get('n')} "
            f"btc_comm_n={fee_clear.get('n')} "
            f"hs_shadow={hard.get('n_with_pnl')} "
            f"tstop={tstop.get('n_with_pnl')} "
            f"regret_shadow={regret.get('sports_settle_losers_with_shadow')}/"
            f"{regret.get('sports_settle_losers')} "
            f"selective_m1={selective.get('m1_holds')}"
        ),
        "note": (
            "E2 exit-quality observe / selective throughput after M1 "
            "(+ commodity time-stop / sports time-final / exit-regret KPIs). "
            "Never softens floors; never arms LIVE_ORDERS; no tip invent."
        ),
    }


# ---- Commodity time-stop shadow (Phase 3) ----------------------------------

def _minutes_to_close(close_time, *, now=None) -> float | None:
    """Minutes until close_time (ISO). None if unparseable / already past."""
    raw = str(close_time or "").strip()
    if not raw:
        return None
    try:
        from datetime import datetime, timezone
        when = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        now_dt = now
        if now_dt is None:
            now_dt = datetime.now(timezone.utc)
        elif isinstance(now_dt, (int, float)):
            now_dt = datetime.fromtimestamp(float(now_dt), tz=timezone.utc)
        left = (when - now_dt).total_seconds() / 60.0
        return round(left, 3)
    except Exception:
        return None


def commodity_time_stop_hit(
    close_time,
    bid,
    entry_price=None,
    *,
    cost=None,
    contracts=None,
    min_left: float = COMMODITY_TIME_STOP_MIN_LEFT,
    now=None,
) -> dict:
    """True when ≤min_left minutes to settle and mark PnL ≤ 0 after approx fee."""
    left = _minutes_to_close(close_time, now=now)
    bid_n = _finite(bid)
    entry = _finite(entry_price)
    contracts_n = _finite(contracts) or 1.0
    cost_n = _finite(cost)
    if cost_n is None and entry is not None:
        cost_n = round(float(entry) * contracts_n, 4)
    fee_approx = 0.0
    # bid=0 is a real quote (finalized loser); only reject missing/negative.
    if bid_n is not None and bid_n > 0:
        fee_approx = math.ceil(round(0.07 * bid_n * (1.0 - bid_n) * 100, 6)) / 100
    mark_pnl = None
    if bid_n is not None and cost_n is not None and bid_n >= 0:
        proceeds = round(contracts_n * max(0.0, bid_n - fee_approx), 4)
        mark_pnl = round(proceeds - cost_n, 4)
    near_close = left is not None and left + 1e-12 <= float(min_left) and left > -1e-9
    underwater = mark_pnl is not None and mark_pnl <= 1e-12
    hit = bool(near_close and underwater and bid_n is not None and bid_n >= 0)
    return {
        "hit": hit,
        "minutes_left": left,
        "min_left_bar": float(min_left),
        "near_close": near_close,
        "underwater": underwater,
        "bid": bid_n,
        "entry": entry,
        "cost": cost_n,
        "contracts": contracts_n,
        "fee_approx": fee_approx,
        "mark_pnl": mark_pnl,
        "shadow_only": not COMMODITY_TIME_STOP_LIVE,
        "live": bool(COMMODITY_TIME_STOP_LIVE),
    }


def record_commodity_time_stop_shadow(
    root: str | None,
    *,
    ticker: str,
    side: str = "",
    series: str = "",
    close_time: str = "",
    entry_price=None,
    bid=None,
    contracts=None,
    cost=None,
    note: str = "",
    now=None,
) -> dict:
    """Log a would-have time-stopped commodity open. Does not sell unless LIVE."""
    gate = commodity_time_stop_hit(
        close_time, bid, entry_price, cost=cost, contracts=contracts, now=now,
    )
    if not gate.get("hit"):
        return {"recorded": False, **gate}
    path = _path(COMMODITY_TIME_STOP_SHADOW, root)
    state = _load(path, {"paper_only": True, "version": 1, "rows": [], "live": False})
    row = {
        "at": _now(),
        "ticker": ticker,
        "side": side,
        "series": series,
        "close_time": str(close_time or "")[:40],
        "minutes_left": gate.get("minutes_left"),
        "min_left_bar": gate.get("min_left_bar"),
        "entry_price": gate.get("entry"),
        "bid": gate.get("bid"),
        "contracts": gate.get("contracts"),
        "cost": gate.get("cost"),
        "mark_pnl": gate.get("mark_pnl"),
        "shadow_pnl": gate.get("mark_pnl"),
        "shadow_only": True,
        "live_sell": False,
        "note": str(note or "")[:160],
    }
    rows = list(state.get("rows") or [])
    rows.append(row)
    state["rows"] = rows[-MAX_COMMODITY_TSTOP_ROWS:]
    state["last_at"] = row["at"]
    state["live"] = commodity_time_stop_is_live(root)
    state["paper_only"] = True
    _save(path, state)
    return {"recorded": True, "row": row, **gate}


def commodity_time_stop_shadow_summary(root: str | None = None) -> dict:
    path = _path(COMMODITY_TIME_STOP_SHADOW, root)
    state = _load(path, {"paper_only": True, "rows": []})
    rows = [r for r in (state.get("rows") or []) if isinstance(r, dict)]
    pnls = [_finite(r.get("shadow_pnl")) for r in rows]
    pnls = [p for p in pnls if p is not None]
    n = len(pnls)
    exp = round(sum(pnls) / n, 4) if n else None
    decision = "reject"
    if n >= COMMODITY_TIME_STOP_PROMOTE_N and exp is not None and exp >= 0:
        decision = "review"
    live = commodity_time_stop_is_live(root)
    promote = _load(
        _path(COMMODITY_TIME_STOP_PROMOTE, root),
        {"paper_only": True, "staff_approved": False, "live": False},
    )
    evidence_thin = n < int(COMMODITY_TIME_STOP_PROMOTE_N)
    n_to_promote = max(0, int(COMMODITY_TIME_STOP_PROMOTE_N) - n)
    ready = decision == "review"
    return {
        "paper_only": True,
        "observe_only": True,
        "n": len(rows),
        "n_with_pnl": n,
        "shadow_expectancy": exp,
        "promote_min_n": COMMODITY_TIME_STOP_PROMOTE_N,
        "n_to_promote": n_to_promote,
        "evidence_thin": evidence_thin,
        "min_left_bar": COMMODITY_TIME_STOP_MIN_LEFT,
        "live": live,
        "code_default_live": bool(COMMODITY_TIME_STOP_LIVE),
        "staff_approved": bool(promote.get("staff_approved")),
        "promote_ready": ready,
        "auto_promote": False,
        "decision": decision,
        "fee_floors_locked": True,
        "label": (
            f"commodity time-stop shadow n={n}/{COMMODITY_TIME_STOP_PROMOTE_N} "
            f"{'THIN' if evidence_thin else ('ready' if ready else 'reject')} "
            f"EV={exp} live={live}"
        ),
        "note": (
            "Commodity time-stop stays shadow-only until staff_set_commodity_time_stop_live. "
            f"Hit when ≤{COMMODITY_TIME_STOP_MIN_LEFT:g}m to close and mark PnL ≤ 0. "
            f"Evidence thin until n≥{COMMODITY_TIME_STOP_PROMOTE_N} and shadow EV ≥ 0. "
            "Code default COMMODITY_TIME_STOP_LIVE stays False."
        ),
    }


def commodity_time_stop_is_live(root: str | None = None) -> bool:
    if COMMODITY_TIME_STOP_LIVE:
        return True
    promote = _load(
        _path(COMMODITY_TIME_STOP_PROMOTE, root),
        {"paper_only": True, "staff_approved": False, "live": False},
    )
    return bool(promote.get("staff_approved")) and bool(promote.get("live"))


def staff_set_commodity_time_stop_live(
    root: str | None,
    enabled: bool,
    *,
    note: str = "",
    force: bool = False,
) -> dict:
    """Staff gate to arm/disarm live commodity time-stop sells."""
    summary = commodity_time_stop_shadow_summary(root)
    if enabled and not force and not summary.get("promote_ready"):
        return {
            "ok": False,
            "live": False,
            "staff_approved": False,
            "reason": (
                f"not promote_ready (need n≥{COMMODITY_TIME_STOP_PROMOTE_N} "
                "with shadow EV ≥ 0)"
            ),
            "summary": summary,
            "auto_promote": False,
            "fee_floors_locked": True,
        }
    row = {
        "paper_only": True,
        "staff_approved": bool(enabled),
        "live": bool(enabled),
        "at": _now(),
        "note": str(note or "")[:200],
        "shadow_n": summary.get("n_with_pnl"),
        "shadow_expectancy": summary.get("shadow_expectancy"),
        "decision": summary.get("decision"),
        "auto_promote": False,
        "code_default_live": bool(COMMODITY_TIME_STOP_LIVE),
        "fee_floors_locked": True,
    }
    _save(_path(COMMODITY_TIME_STOP_PROMOTE, root), row)
    return {
        "ok": True,
        "live": bool(enabled),
        "staff_approved": bool(enabled),
        "reason": "armed" if enabled else "disarmed",
        "summary": commodity_time_stop_shadow_summary(root),
        "auto_promote": False,
        "fee_floors_locked": True,
    }


# ---- Sports time-to-final trim shadow (Phase 3 P1) --------------------------

def _espn_colonless_decimal_minutes_seconds(text) -> float | None:
    """ESPN colon-less decimal clocks are minutes, not seconds.

    NBA/NCAAB often emit ``displayClock="13.5"`` / shortDetail ``13.5 - 4th``.
    Treating that as 13.5s invents near-final (rem≈0.2) while ~13.5m remain.
    Cap at regulation period length (≤20). Whole-second strings like ``90``
    stay seconds (no decimal point).
    """
    raw = str(text or "").strip()
    if not raw or ":" in raw:
        return None
    head = raw.split()[0]
    for sep in ("-", "–", "—"):
        if sep in head:
            left = head.split(sep, 1)[0]
            if "." in left:
                head = left
            break
    head = head.strip()
    if "." not in head:
        return None
    left, _, right = head.partition(".")
    if not left.isdigit() or not right.isdigit():
        return None
    try:
        mins = float(head)
    except Exception:
        return None
    if mins < 0.0 or mins > 20.0 + 1e-9:
        return None
    return mins * 60.0


def _parse_espn_mmss_prefix(text) -> float | None:
    """Parse leading ``m:ss`` / ``mm:ss`` from ESPN shortDetail-style strings.

    Examples: ``3:42 - 4th``, ``0:45-4th Quarter``, ``3.5 - 4th`` (decimal
    minutes). Refuses non-clock junk so we never invent a near-final rem from
    prose alone.
    """
    raw = str(text or "").strip()
    if not raw:
        return None
    head = raw.split()[0]
    for sep in ("-", "–", "—"):
        if sep in head and (
            ":" in head.split(sep, 1)[0] or "." in head.split(sep, 1)[0]
        ):
            head = head.split(sep, 1)[0]
            break
    if ":" not in head:
        # Prefer-1: colon-less decimal minutes (NBA ``13.5 - 4th``) densify.
        return _espn_colonless_decimal_minutes_seconds(head)
    try:
        mm_s, ss_s = head.split(":", 1)
        if not mm_s.isdigit():
            return None
        ss = float(ss_s)
        if ss < 0.0 or ss >= 60.0:
            return None
        total = int(mm_s) * 60.0 + ss
        # Regulation period clocks are ≤20:00 (NHL); refuse longer as non-clock.
        if total > 20.0 * 60.0 + 1e-9:
            return None
        return total
    except Exception:
        return None


def _sports_clock_seconds(status) -> float | None:
    """Parse ESPN status clock into seconds remaining in the current period.

    Empty/whitespace ``displayClock`` is end-of-slice 0:00 — the old
    ``a or b`` chain treated ``""`` as missing and fell through to a full
    ``period_min`` fallback, DROPping time-final densify in the last period.
    Numeric ``clock`` wins when present. When displayClock key is absent,
    parse ``shortDetail``/``detail`` ``m:ss - Nth`` before the conservative
    period_min guess. Empty/whitespace displayClock is end-of-slice 0s;
    unparseable displayClock must NOT invent 0s — fall through to
    shortDetail / End tokens (else None → period_min). End/Halftime/Final
    detail still means 0s left in slice. Colon-less decimal ``displayClock``
    (``13.5``) is minutes — never invent false t-final as seconds.
    """
    if not isinstance(status, dict):
        return None
    clock = status.get("clock")
    if isinstance(clock, (int, float)):
        return float(clock)
    # Some ESPN / cache payloads stringify seconds — do not period_min-DROP.
    if isinstance(clock, str) and str(clock).strip():
        raw = str(clock).strip()
        try:
            return float(raw)
        except ValueError:
            parsed = _parse_espn_mmss_prefix(raw)
            if parsed is not None:
                return float(parsed)
    has_disp = "displayClock" in status or "display_clock" in status
    if has_disp:
        disp = status.get("displayClock")
        if disp is None:
            disp = status.get("display_clock")
        if disp is None or str(disp).strip() == "":
            return 0.0
        try:
            text = str(disp).strip()
            if ":" in text:
                mm, ss = text.split(":", 1)
                return int(mm) * 60.0 + float(ss)
            # Prefer-1: ``13.5`` is 13.5 minutes (NBA), not 13.5 seconds.
            dec = _espn_colonless_decimal_minutes_seconds(text)
            if dec is not None:
                return dec
            return float(text)
        except Exception:
            # Junk displayClock (N/A, --, lone ":") must not invent rem=0 /
            # false t-final — fall through to shortDetail / End tokens.
            pass
    # No usable clock fields — End/Halftime/Final detail still means 0s left.
    typ = status.get("type") if isinstance(status.get("type"), dict) else {}
    blob = " ".join(
        str(typ.get(k) or "")
        for k in ("name", "detail", "shortDetail", "description")
    ).upper()
    if any(
        tok in blob
        for tok in (
            "END OF",
            "END_OF",
            "STATUS_END",
            "HALFTIME",
            "STATUS_HALFTIME",
            "STATUS_FINAL",
            "FINAL",
        )
    ):
        return 0.0
    # ESPN often puts the live clock only in shortDetail ("3:42 - 4th").
    for key in ("shortDetail", "detail", "description"):
        parsed = _parse_espn_mmss_prefix(typ.get(key) or "")
        if parsed is not None:
            return parsed
    # Flattened feeds / gap_bot espn_games densify shortDetail onto status root
    # (and game["detail"]) when type.shortDetail is absent.
    for key in ("shortDetail", "detail", "description"):
        if key in status and not isinstance(status.get(key), dict):
            parsed = _parse_espn_mmss_prefix(status.get(key))
            if parsed is not None:
                return parsed
    return None


def sports_minutes_remaining(
    status,
    league: str | None = None,
    *,
    detail: str | None = None,
) -> float | None:
    """Approx regulation minutes left from ESPN period + clock.

    ``detail`` densifies gap_bot ``espn_games`` game-level shortDetail when the
    competition status blob omitted type.shortDetail (same mm:ss densify).
    """
    if not isinstance(status, dict):
        return None
    status_use = status
    detail_s = str(detail or "").strip()
    if detail_s:
        # Inject into a shallow copy so callers' status dicts stay untouched.
        status_use = dict(status)
        typ = status_use.get("type") if isinstance(status_use.get("type"), dict) else {}
        typ = dict(typ)
        if not str(typ.get("shortDetail") or "").strip():
            typ["shortDetail"] = detail_s
            status_use["type"] = typ
        if not str(status_use.get("shortDetail") or "").strip():
            status_use["shortDetail"] = detail_s
    try:
        period = int(status_use.get("period") or 0)
    except Exception:
        period = 0
    if period <= 0:
        return None
    lg = str(league or "").strip().upper()
    period_min = float(SPORTS_PERIOD_MIN.get(lg) or 15.0)
    reg_n = int(SPORTS_REG_PERIODS.get(lg) or 4)
    clock_s = _sports_clock_seconds(status_use)
    clock_min = (float(clock_s) / 60.0) if clock_s is not None else period_min
    if period > reg_n:
        # OT / extras — already at the final stretch.
        return round(max(0.0, clock_min), 3)
    rem = (reg_n - period) * period_min + clock_min
    return round(max(0.0, rem), 3)


def sports_time_final_hit(
    minutes_left,
    bid,
    entry_price=None,
    *,
    cost=None,
    contracts=None,
    min_left: float = SPORTS_TIME_FINAL_MIN_LEFT,
) -> dict:
    """True when ≤min_left regulation minutes remain and mark PnL ≤ 0."""
    left = _finite(minutes_left)
    bid_n = _finite(bid)
    entry = _finite(entry_price)
    contracts_n = _finite(contracts) or 1.0
    cost_n = _finite(cost)
    if cost_n is None and entry is not None:
        cost_n = round(float(entry) * contracts_n, 4)
    fee_approx = 0.0
    # bid=0 is a real quote (finalized loser); only reject missing/negative.
    if bid_n is not None and bid_n > 0:
        fee_approx = math.ceil(round(0.07 * bid_n * (1.0 - bid_n) * 100, 6)) / 100
    mark_pnl = None
    if bid_n is not None and cost_n is not None and bid_n >= 0:
        proceeds = round(contracts_n * max(0.0, bid_n - fee_approx), 4)
        mark_pnl = round(proceeds - cost_n, 4)
    near_final = left is not None and left + 1e-12 <= float(min_left) and left >= -1e-9
    underwater = mark_pnl is not None and mark_pnl <= 1e-12
    hit = bool(near_final and underwater and bid_n is not None and bid_n >= 0)
    return {
        "hit": hit,
        "minutes_left": left,
        "min_left_bar": float(min_left),
        "near_final": near_final,
        "underwater": underwater,
        "bid": bid_n,
        "entry": entry,
        "cost": cost_n,
        "contracts": contracts_n,
        "fee_approx": fee_approx,
        "mark_pnl": mark_pnl,
        "shadow_only": not SPORTS_TIME_FINAL_LIVE,
        "live": bool(SPORTS_TIME_FINAL_LIVE),
    }


def record_sports_time_final_shadow(
    root: str | None,
    *,
    ticker: str,
    side: str = "",
    league: str = "",
    minutes_left=None,
    entry_price=None,
    bid=None,
    contracts=None,
    cost=None,
    note: str = "",
) -> dict:
    """Log a would-have time-to-final trim. Does not sell unless LIVE."""
    gate = sports_time_final_hit(
        minutes_left, bid, entry_price, cost=cost, contracts=contracts,
    )
    if not gate.get("hit"):
        return {"recorded": False, **gate}
    # Settlement wipe (rem≤0 + bid=0) is not a trim quote — skip so promote EV
    # is not poisoned by full-hold losers. Mid-game bid=0 with rem>0 still logs.
    bid_n = _finite(gate.get("bid"))
    rem_n = _finite(gate.get("minutes_left"))
    if bid_n is not None and bid_n <= 0 and (rem_n is None or rem_n <= 0):
        return {"recorded": False, "skipped": "settle_wipe_not_trim", **gate}
    path = _path(SPORTS_TIME_FINAL_SHADOW, root)
    state = _load(path, {"paper_only": True, "version": 1, "rows": [], "live": False})
    row = {
        "at": _now(),
        "ticker": ticker,
        "side": side,
        "league": league,
        "minutes_left": gate.get("minutes_left"),
        "min_left_bar": gate.get("min_left_bar"),
        "entry_price": gate.get("entry"),
        "bid": gate.get("bid"),
        "contracts": gate.get("contracts"),
        "cost": gate.get("cost"),
        "mark_pnl": gate.get("mark_pnl"),
        "shadow_pnl": gate.get("mark_pnl"),
        "shadow_only": True,
        "live_sell": False,
        "note": str(note or "")[:160],
    }
    rows = list(state.get("rows") or [])
    rows.append(row)
    state["rows"] = rows[-MAX_SPORTS_TFINAL_ROWS:]
    state["last_at"] = row["at"]
    state["live"] = sports_time_final_is_live(root)
    state["paper_only"] = True
    _save(path, state)
    return {"recorded": True, "row": row, **gate}


def sports_time_final_shadow_summary(root: str | None = None) -> dict:
    path = _path(SPORTS_TIME_FINAL_SHADOW, root)
    state = _load(path, {"paper_only": True, "rows": []})
    rows = [r for r in (state.get("rows") or []) if isinstance(r, dict)]
    pnls = [_finite(r.get("shadow_pnl")) for r in rows]
    pnls = [p for p in pnls if p is not None]
    n = len(pnls)
    exp = round(sum(pnls) / n, 4) if n else None
    decision = "reject"
    if n >= SPORTS_TIME_FINAL_PROMOTE_N and exp is not None and exp >= 0:
        decision = "review"
    live = sports_time_final_is_live(root)
    promote = _load(
        _path(SPORTS_TIME_FINAL_PROMOTE, root),
        {"paper_only": True, "staff_approved": False, "live": False},
    )
    evidence_thin = n < int(SPORTS_TIME_FINAL_PROMOTE_N)
    n_to_promote = max(0, int(SPORTS_TIME_FINAL_PROMOTE_N) - n)
    ready = decision == "review"
    return {
        "paper_only": True,
        "observe_only": True,
        "n": len(rows),
        "n_with_pnl": n,
        "shadow_expectancy": exp,
        "promote_min_n": SPORTS_TIME_FINAL_PROMOTE_N,
        "n_to_promote": n_to_promote,
        "evidence_thin": evidence_thin,
        "min_left_bar": SPORTS_TIME_FINAL_MIN_LEFT,
        "live": live,
        "code_default_live": bool(SPORTS_TIME_FINAL_LIVE),
        "staff_approved": bool(promote.get("staff_approved")),
        "promote_ready": ready,
        "auto_promote": False,
        "decision": decision,
        "fee_floors_locked": True,
        "label": (
            f"sports time-final shadow n={n}/{SPORTS_TIME_FINAL_PROMOTE_N} "
            f"{'THIN' if evidence_thin else ('ready' if ready else 'reject')} "
            f"EV={exp} live={live}"
        ),
        "note": (
            "Sports time-to-final stays shadow-only until staff_set_sports_time_final_live. "
            f"Hit when ≤{SPORTS_TIME_FINAL_MIN_LEFT:g}m regulation left and mark PnL ≤ 0. "
            f"Evidence thin until n≥{SPORTS_TIME_FINAL_PROMOTE_N} and shadow EV ≥ 0. "
            "Code default SPORTS_TIME_FINAL_LIVE stays False."
        ),
    }


def sports_time_final_is_live(root: str | None = None) -> bool:
    if SPORTS_TIME_FINAL_LIVE:
        return True
    promote = _load(
        _path(SPORTS_TIME_FINAL_PROMOTE, root),
        {"paper_only": True, "staff_approved": False, "live": False},
    )
    return bool(promote.get("staff_approved")) and bool(promote.get("live"))


def staff_set_sports_time_final_live(
    root: str | None,
    enabled: bool,
    *,
    note: str = "",
    force: bool = False,
) -> dict:
    """Staff gate to arm/disarm live sports time-to-final trims."""
    summary = sports_time_final_shadow_summary(root)
    if enabled and not force and not summary.get("promote_ready"):
        return {
            "ok": False,
            "live": False,
            "staff_approved": False,
            "reason": (
                f"not promote_ready (need n≥{SPORTS_TIME_FINAL_PROMOTE_N} "
                "with shadow EV ≥ 0)"
            ),
            "summary": summary,
            "auto_promote": False,
            "fee_floors_locked": True,
        }
    row = {
        "paper_only": True,
        "staff_approved": bool(enabled),
        "live": bool(enabled),
        "at": _now(),
        "note": str(note or "")[:200],
        "shadow_n": summary.get("n_with_pnl"),
        "shadow_expectancy": summary.get("shadow_expectancy"),
        "decision": summary.get("decision"),
        "auto_promote": False,
        "code_default_live": bool(SPORTS_TIME_FINAL_LIVE),
        "fee_floors_locked": True,
    }
    _save(_path(SPORTS_TIME_FINAL_PROMOTE, root), row)
    return {
        "ok": True,
        "live": bool(enabled),
        "staff_approved": bool(enabled),
        "reason": "armed" if enabled else "disarmed",
        "summary": sports_time_final_shadow_summary(root),
        "auto_promote": False,
        "fee_floors_locked": True,
    }


# ---- Sports hard-stop shadow -----------------------------------------------

def sports_hard_stop_hit(
    entry_price,
    bid,
    *,
    drop: float = SPORTS_HARD_STOP_DROP,
) -> dict:
    """True when live bid has fallen `drop` below entry ask (fee-aware later on sell)."""
    entry = _finite(entry_price)
    b = _finite(bid)
    d = _finite(drop)
    # bid=0 is a real quote (finalized loser / wiped book) — strongest hard-stop.
    # Only reject missing or negative bids; do not treat 0 as "no quote".
    if entry is None or b is None or d is None or entry <= 0 or b < 0:
        return {"hit": False, "drop": d, "entry": entry, "bid": b, "threshold": None}
    threshold = round(entry - float(d), 4)
    hit = b <= threshold + 1e-12
    return {
        "hit": hit,
        "drop": float(d),
        "entry": entry,
        "bid": b,
        "threshold": threshold,
        "shadow_only": not SPORTS_HARD_STOP_LIVE,
        "live": bool(SPORTS_HARD_STOP_LIVE),
    }


def record_sports_hard_stop_shadow(
    root: str | None,
    *,
    ticker: str,
    side: str = "",
    league: str = "",
    entry_price=None,
    bid=None,
    fair=None,
    contracts=None,
    cost=None,
    note: str = "",
) -> dict:
    """Log a would-have hard-stopped sports open. Does not sell unless LIVE flag on."""
    gate = sports_hard_stop_hit(entry_price, bid)
    if not gate.get("hit"):
        return {"recorded": False, **gate}
    path = _path(SPORTS_HARD_STOP_SHADOW, root)
    state = _load(path, {"paper_only": True, "version": 1, "rows": [], "live": False})
    # Shadow PnL if we sold at exit bid − approx fee.
    # Wiped books (bid=0 settle-retro) price the exit at the stop threshold —
    # that is the fill we would have taken when the stop first hit, not the
    # final 0 (which would poison promote EV with full-hold losses).
    contracts_n = _finite(contracts) or 1.0
    cost_n = _finite(cost)
    quote_bid = _finite(bid)
    thr = _finite(gate.get("threshold"))
    exit_bid = quote_bid
    priced_at_threshold = False
    if quote_bid is not None and quote_bid <= 0 and thr is not None and thr > 0:
        exit_bid = thr
        priced_at_threshold = True
    exit_bid = float(exit_bid or 0.0)
    fee_approx = (
        math.ceil(round(0.07 * exit_bid * (1.0 - exit_bid) * 100, 6)) / 100
        if exit_bid > 0
        else 0.0
    )
    proceeds = round(contracts_n * max(0.0, exit_bid - fee_approx), 2)
    shadow_pnl = None if cost_n is None else round(proceeds - cost_n, 2)
    row = {
        "at": _now(),
        "ticker": ticker,
        "side": side,
        "league": league,
        "entry_price": gate.get("entry"),
        "bid": gate.get("bid"),
        "exit_bid": exit_bid,
        "priced_at_threshold": priced_at_threshold,
        "threshold": gate.get("threshold"),
        "drop": gate.get("drop"),
        "fair": _finite(fair),
        "contracts": contracts_n,
        "cost": cost_n,
        "shadow_pnl": shadow_pnl,
        "shadow_only": True,
        "live_sell": False,
        "note": str(note or "")[:160],
    }
    rows = list(state.get("rows") or [])
    rows.append(row)
    state["rows"] = rows[-MAX_HARD_STOP_ROWS:]
    state["last_at"] = row["at"]
    state["live"] = sports_hard_stop_is_live(root)
    _save(path, state)
    return {"recorded": True, "row": row, **gate}


def sports_hard_stop_shadow_summary(root: str | None = None) -> dict:
    path = _path(SPORTS_HARD_STOP_SHADOW, root)
    state = _load(path, {"paper_only": True, "rows": []})
    rows = [r for r in (state.get("rows") or []) if isinstance(r, dict)]
    pnls = [_finite(r.get("shadow_pnl")) for r in rows]
    pnls = [p for p in pnls if p is not None]
    n = len(pnls)
    exp = round(sum(pnls) / n, 4) if n else None
    decision = "reject"
    if n >= SPORTS_HARD_STOP_PROMOTE_N and exp is not None and exp >= 0:
        decision = "review"  # staff may promote; never auto
    live = sports_hard_stop_is_live(root)
    promote = _load(
        _path(SPORTS_HARD_STOP_PROMOTE, root),
        {"paper_only": True, "staff_approved": False, "live": False},
    )
    evidence_thin = n < int(SPORTS_HARD_STOP_PROMOTE_N)
    n_to_promote = max(0, int(SPORTS_HARD_STOP_PROMOTE_N) - n)
    ready = decision == "review"
    return {
        "paper_only": True,
        "observe_only": True,
        "n": len(rows),
        "n_with_pnl": n,
        "shadow_expectancy": exp,
        "promote_min_n": SPORTS_HARD_STOP_PROMOTE_N,
        "n_to_promote": n_to_promote,
        "evidence_thin": evidence_thin,
        "drop": SPORTS_HARD_STOP_DROP,
        "live": live,
        "code_default_live": bool(SPORTS_HARD_STOP_LIVE),
        "staff_approved": bool(promote.get("staff_approved")),
        "promote_ready": ready,
        "auto_promote": False,
        "decision": decision,
        "fee_floors_locked": True,
        "label": (
            f"hard-stop shadow n={n}/{SPORTS_HARD_STOP_PROMOTE_N} "
            f"{'THIN' if evidence_thin else ('ready' if ready else 'reject')} "
            f"EV={exp} live={live}"
        ),
        "note": (
            "Sports hard-stop stays shadow-only until staff_set_sports_hard_stop_live. "
            f"Evidence thin until n≥{SPORTS_HARD_STOP_PROMOTE_N} and shadow EV ≥ 0. "
            "No-force money-path CLI promotes only when promote_ready. "
            "Code default SPORTS_HARD_STOP_LIVE stays False."
        ),
    }


def export_sports_hard_stop_shadow_csv(
    root: str | None = None,
    *,
    path: str | None = None,
) -> dict:
    """Staff promote packet: CSV export of sports hard-stop shadow rows.

    Paper only. Never sells. Never softens floors. make-money plan step 291.
    """
    import csv
    import io

    shadow_path = _path(SPORTS_HARD_STOP_SHADOW, root)
    state = _load(shadow_path, {"paper_only": True, "rows": []})
    rows = [r for r in (state.get("rows") or []) if isinstance(r, dict)]
    summary = sports_hard_stop_shadow_summary(root)
    fields = (
        "at", "ticker", "side", "league", "entry_price", "bid", "threshold",
        "drop", "fair", "contracts", "cost", "shadow_pnl", "shadow_only",
        "live_sell", "note",
    )
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k) for k in fields})
    text = buf.getvalue()
    out_path = path or _path("desk_sports_hard_stop_shadow.csv", root)
    try:
        with open(out_path, "w", encoding="utf-8") as handle:
            handle.write(text)
        wrote = True
    except OSError as exc:
        wrote = False
        out_path = None
        return {
            "ok": False,
            "wrote": False,
            "path": None,
            "n": len(rows),
            "csv": text,
            "summary": summary,
            "reason": f"write failed: {exc}",
            "paper_only": True,
            "auto_promote": False,
            "fee_floors_locked": True,
        }
    return {
        "ok": True,
        "wrote": wrote,
        "path": out_path,
        "n": len(rows),
        "csv": text,
        "summary": summary,
        "paper_only": True,
        "auto_promote": False,
        "fee_floors_locked": True,
        "note": (
            "Hard-stop shadow CSV for staff promote packet. "
            "Does not arm live sells; use staff_set_sports_hard_stop_live."
        ),
    }


def sports_hard_stop_is_live(root: str | None = None) -> bool:
    """Live sells only when code flag OR explicit staff promote file says so."""
    if SPORTS_HARD_STOP_LIVE:
        return True
    promote = _load(
        _path(SPORTS_HARD_STOP_PROMOTE, root),
        {"paper_only": True, "staff_approved": False, "live": False},
    )
    return bool(promote.get("staff_approved")) and bool(promote.get("live"))


def staff_set_sports_hard_stop_live(
    root: str | None,
    enabled: bool,
    *,
    note: str = "",
    force: bool = False,
) -> dict:
    """Staff gate to arm/disarm live hard-stop sells.

    Enabling requires promote_ready (n≥30, shadow EV≥0) unless force=True for tests.
    Never auto-called. Code constant SPORTS_HARD_STOP_LIVE remains False.
    """
    summary = sports_hard_stop_shadow_summary(root)
    if enabled and not force and not summary.get("promote_ready"):
        return {
            "ok": False,
            "live": False,
            "staff_approved": False,
            "reason": (
                f"not promote_ready (need n≥{SPORTS_HARD_STOP_PROMOTE_N} "
                "with shadow EV ≥ 0)"
            ),
            "summary": summary,
            "auto_promote": False,
            "fee_floors_locked": True,
        }
    row = {
        "paper_only": True,
        "staff_approved": bool(enabled),
        "live": bool(enabled),
        "at": _now(),
        "note": str(note or "")[:200],
        "shadow_n": summary.get("n_with_pnl"),
        "shadow_expectancy": summary.get("shadow_expectancy"),
        "decision": summary.get("decision"),
        "auto_promote": False,
        "code_default_live": bool(SPORTS_HARD_STOP_LIVE),
        "fee_floors_locked": True,
    }
    _save(_path(SPORTS_HARD_STOP_PROMOTE, root), row)
    return {
        "ok": True,
        "live": bool(enabled),
        "staff_approved": bool(enabled),
        "reason": "armed" if enabled else "disarmed",
        "summary": sports_hard_stop_shadow_summary(root),
        "auto_promote": False,
        "fee_floors_locked": True,
    }


def staff_batch_arm_promotes(
    root: str | None = None,
    *,
    force: bool = False,
    note: str = "",
    inx_band_id: str = INX_LIVE_BAND_DEFAULT,
    bots: list | None = None,
) -> dict:
    """Staff batch: hard-stop live + green_boost + INX band promote.

    Never auto-called. force=True only when staff explicitly lifts evidence gates.
    Locks fee floors; LIVE_ORDERS stay off (paper sells / paper boost only).
    """
    note_s = str(note or "staff batch promote")[:200]
    hard_stop = staff_set_sports_hard_stop_live(
        root, True, note=note_s, force=force,
    )
    green = staff_set_sports_green_boost(
        root, True, note=note_s, force=force, bots=bots,
    )
    inx = staff_promote_inx_band(
        root, inx_band_id, note=note_s, force=force,
    )
    ok = bool(hard_stop.get("ok") and green.get("ok") and inx.get("ok"))
    return {
        "paper_only": True,
        "ok": ok,
        "hard_stop": hard_stop,
        "green_boost": green,
        "inx_band": inx,
        "inx_band_id": str(inx_band_id),
        "force": bool(force),
        "note": note_s,
        "auto_promote": False,
        "fee_floors_locked": True,
        "live_orders_enabled": False,
        "code_default_hard_stop_live": bool(SPORTS_HARD_STOP_LIVE),
    }


# ---- Adverse selection cool-off --------------------------------------------

def record_adverse_fill(
    root: str | None,
    *,
    bot: str,
    ticker: str = "",
    entry_price=None,
    mark_price=None,
    note: str = "",
) -> dict:
    """If mark dropped ≥ ADVERSE_MARK_DROP vs entry, cool the bot for ADVERSE_COOL_MINUTES."""
    entry = _finite(entry_price)
    mark = _finite(mark_price)
    if entry is None or mark is None or entry <= 0:
        return {"cooled": False, "reason": "bad prices"}
    drop = entry - mark
    if drop + 1e-12 < ADVERSE_MARK_DROP:
        return {"cooled": False, "drop": round(drop, 4)}
    path = _path(ADVERSE_COOL_NAME, root)
    state = _load(path, {"paper_only": True, "bots": {}, "history": []})
    until = time.time() + ADVERSE_COOL_MINUTES * 60
    event = {
        "until": until,
        "at": _now(),
        "ticker": ticker,
        "entry": entry,
        "mark": mark,
        "drop": round(drop, 4),
        "note": str(note or "")[:160],
        "bot": str(bot),
    }
    state.setdefault("bots", {})[str(bot)] = event
    hist = list(state.get("history") or [])
    hist.append({k: event[k] for k in ("at", "bot", "ticker", "entry", "mark", "drop", "note")})
    state["history"] = hist[-500:]
    state["last_at"] = _now()
    _save(path, state)
    return {
        "cooled": True,
        "bot": bot,
        "until": until,
        "minutes": ADVERSE_COOL_MINUTES,
        "drop": round(drop, 4),
    }


def _anti_revenge_key(bot: str, ticker: str) -> str:
    return f"{str(bot)}|{str(ticker).strip().upper()}"


def record_anti_revenge(
    root: str | None,
    *,
    bot: str,
    ticker: str,
    reason: str = "stop",
    note: str = "",
    minutes: int = ANTI_REVENGE_MINUTES,
) -> dict:
    """Block re-entry on the same market for `minutes` after a stop/flip exit."""
    tick = str(ticker or "").strip()
    if not tick:
        return {"cooled": False, "reason": "no ticker"}
    path = _path(ANTI_REVENGE_NAME, root)
    state = _load(path, {"paper_only": True, "markets": {}})
    until = time.time() + max(1, int(minutes)) * 60
    key = _anti_revenge_key(bot, tick)
    state.setdefault("markets", {})[key] = {
        "until": until,
        "at": _now(),
        "bot": str(bot),
        "ticker": tick,
        "reason": str(reason or "stop")[:80],
        "note": str(note or "")[:160],
        "minutes": int(minutes),
    }
    # Prune expired keys opportunistically.
    now = time.time()
    markets = state.get("markets") or {}
    state["markets"] = {
        k: v for k, v in markets.items()
        if isinstance(v, dict) and (_finite(v.get("until")) or 0) > now
    }
    state["markets"][key] = {
        "until": until,
        "at": _now(),
        "bot": str(bot),
        "ticker": tick,
        "reason": str(reason or "stop")[:80],
        "note": str(note or "")[:160],
        "minutes": int(minutes),
    }
    state["last_at"] = _now()
    _save(path, state)
    return {
        "cooled": True,
        "bot": str(bot),
        "ticker": tick,
        "until": until,
        "minutes": int(minutes),
        "reason": str(reason or "stop")[:80],
    }


def anti_revenge_status(root: str | None = None) -> dict:
    """Observe board: same-market anti-revenge cools currently active."""
    path = _path(ANTI_REVENGE_NAME, root)
    state = _load(path, {"paper_only": True, "markets": {}})
    now = time.time()
    active = []
    for key, row in (state.get("markets") or {}).items():
        if not isinstance(row, dict):
            continue
        until = _finite(row.get("until"))
        if until is None or until <= now:
            continue
        active.append({
            "key": str(key),
            "bot": row.get("bot"),
            "ticker": row.get("ticker"),
            "reason": row.get("reason"),
            "left_min": int(max(1, (until - now) / 60.0)),
            "until": until,
            "at": row.get("at"),
        })
    active.sort(key=lambda r: (str(r.get("bot") or ""), str(r.get("ticker") or "")))
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "minutes": ANTI_REVENGE_MINUTES,
        "active_n": len(active),
        "active": active[:40],
        "label": f"anti_revenge active={len(active)} window={ANTI_REVENGE_MINUTES}m",
        "note": (
            f"Anti-revenge blocks same-market re-entry for {ANTI_REVENGE_MINUTES}m "
            "after stop/flip. Floors locked."
        ),
    }


def anti_revenge_blocks(root: str | None, bot: str, ticker: str) -> str:
    """Non-empty reason when same market is in anti-revenge cool-off."""
    tick = str(ticker or "").strip()
    if not tick:
        return ""
    path = _path(ANTI_REVENGE_NAME, root)
    state = _load(path, {"paper_only": True, "markets": {}})
    row = (state.get("markets") or {}).get(_anti_revenge_key(bot, tick))
    if not isinstance(row, dict):
        return ""
    until = _finite(row.get("until"))
    if until is None or time.time() >= until:
        return ""
    left = int(max(1, (until - time.time()) / 60.0))
    why = str(row.get("reason") or "stop")
    return (
        f"anti-revenge: {bot} blocked on {tick} ~{left}m after {why}"
    )


# ---- Incubation lane (Phase 7) ---------------------------------------------

def _series_key(series: str | None) -> str:
    return str(series or "").strip().upper()


def _empty_incubation() -> dict:
    return {"paper_only": True, "series": {}, "graduated": [], "latest": None}


def load_incubation(root: str | None = None) -> dict:
    return _load(_path(INCUBATION_NAME, root), _empty_incubation())


def incubation_status(root: str | None, series: str | None) -> dict:
    """Lane for one series: main | incubation | ready_to_graduate | graduated | idea_bank."""
    key = _series_key(series)
    store = load_incubation(root)
    graduated = {str(s).upper() for s in (store.get("graduated") or [])}
    row = (store.get("series") or {}).get(key) if key else None
    row = row if isinstance(row, dict) else {}
    n = int(row.get("n") or 0)
    pnls = [p for p in (row.get("pnls") or []) if _finite(p) is not None]
    exp = round(sum(pnls) / len(pnls), 4) if pnls else None
    idea_bank = bool(row.get("idea_bank_only")) or incubation_idea_bank_only(key or series)
    auto_block = incubation_blocks_auto(key or series)
    if idea_bank:
        lane = "idea_bank"
    elif key and key in graduated:
        lane = "graduated"
    elif key and key in INCUBATION_MAIN_SERIES and not row:
        lane = "main"
    elif n >= INCUBATION_MIN_N:
        lane = "ready_to_graduate"
    else:
        lane = "incubation" if key else "unknown"
    return {
        "paper_only": True,
        "series": key,
        "lane": lane,
        "n": n,
        "min_n": INCUBATION_MIN_N,
        "expectancy_taxed": exp,
        "promote_ready": lane == "ready_to_graduate" and not idea_bank,
        "auto_promote": False,
        "idea_bank_only": idea_bank,
        "blocks_auto": auto_block,
        "main_tape": (
            not idea_bank
            and (key in INCUBATION_MAIN_SERIES or lane in ("main", "graduated"))
        ),
        "fee_floors_locked": True,
        "note": (
            "Idea-bank only (weather/econ/Polymarket) — refuse main AUTO."
            if idea_bank
            else (
                f"Incubation: need n≥{INCUBATION_MIN_N} fee-aware settles before staff graduate. "
                "Paper trades allowed; no auto-promote."
            )
        ),
    }


def record_incubation_settle(
    root: str | None,
    *,
    series: str,
    bot: str = "",
    pnl=None,
    contracts=None,
    fill_tax: float = 0.01,
    note: str = "",
) -> dict:
    """Count a fee-aware settle toward incubation graduation."""
    key = _series_key(series)
    if not key:
        return {"recorded": False, "reason": "no series"}
    # Main tape series do not need incubation tracking unless explicitly enrolled.
    store = load_incubation(root)
    graduated = {str(s).upper() for s in (store.get("graduated") or [])}
    if key in graduated or (key in INCUBATION_MAIN_SERIES and key not in (store.get("series") or {})):
        return {"recorded": False, "reason": "main_or_graduated", "series": key}
    p = _finite(pnl)
    c = _finite(contracts) or 1.0
    taxed = None if p is None else p - float(fill_tax) * max(1.0, c)
    series_map = store.setdefault("series", {})
    row = series_map.get(key) if isinstance(series_map.get(key), dict) else {
        "series": key, "n": 0, "pnls": [], "bots": {},
    }
    row["n"] = int(row.get("n") or 0) + 1
    if taxed is not None:
        pnls = list(row.get("pnls") or [])
        pnls.append(round(taxed, 4))
        row["pnls"] = pnls[-200:]
    bots = row.get("bots") if isinstance(row.get("bots"), dict) else {}
    if bot:
        bots[str(bot)] = int(bots.get(str(bot)) or 0) + 1
    row["bots"] = bots
    row["last_at"] = _now()
    row["last_note"] = str(note or "")[:120]
    series_map[key] = row
    store["series"] = series_map
    store["latest"] = {"series": key, "n": row["n"], "at": _now()}
    _save(_path(INCUBATION_NAME, root), store)
    status = incubation_status(root, key)
    return {"recorded": True, **status}


def enroll_incubation(root: str | None, series: str, *, note: str = "") -> dict:
    """Force a series into incubation (even if it was on the main list).

    Weather/econ/Polymarket stay idea-bank only — refuse main AUTO.
    """
    key = _series_key(series)
    if not key:
        return {"ok": False, "reason": "no series"}
    idea_bank = incubation_idea_bank_only(key) or incubation_idea_bank_only(series)
    auto_block = incubation_blocks_auto(key)
    store = load_incubation(root)
    graduated = [s for s in (store.get("graduated") or []) if str(s).upper() != key]
    store["graduated"] = graduated
    series_map = store.setdefault("series", {})
    if key not in series_map:
        series_map[key] = {
            "series": key, "n": 0, "pnls": [], "bots": {}, "enrolled_at": _now(),
        }
    series_map[key]["note"] = str(note or "")[:160]
    series_map[key]["idea_bank_only"] = bool(idea_bank)
    if idea_bank:
        series_map[key]["main_auto"] = False
        series_map[key]["blocks_auto"] = auto_block
    store["series"] = series_map
    _save(_path(INCUBATION_NAME, root), store)
    status = incubation_status(root, key)
    return {
        "ok": True,
        **status,
        "main_auto": False if idea_bank else status.get("main_tape"),
        "refused_main_auto": bool(idea_bank),
        "blocks_auto": auto_block,
    }


def staff_graduate_incubation(
    root: str | None,
    series: str,
    *,
    note: str = "",
    force: bool = False,
) -> dict:
    """Staff promote series out of incubation after n≥50 (unless force)."""
    key = _series_key(series)
    status = incubation_status(root, key)
    auto_block = incubation_blocks_auto(key)
    if auto_block and not force:
        return {
            "ok": False,
            "reason": auto_block,
            "status": status,
            "auto_promote": False,
            "fee_floors_locked": True,
            "refused_main_auto": True,
        }
    if not force and not status.get("promote_ready"):
        return {
            "ok": False,
            "reason": f"need n≥{INCUBATION_MIN_N} (have {status.get('n')})",
            "status": status,
            "auto_promote": False,
            "fee_floors_locked": True,
        }
    store = load_incubation(root)
    graduated = [str(s).upper() for s in (store.get("graduated") or [])]
    if key not in graduated:
        graduated.append(key)
    store["graduated"] = graduated[-200:]
    store["last_graduate"] = {
        "series": key, "at": _now(), "note": str(note or "")[:160],
        "n": status.get("n"), "auto_promote": False,
    }
    _save(_path(INCUBATION_NAME, root), store)
    return {
        "ok": True,
        "reason": "graduated",
        "status": incubation_status(root, key),
        "auto_promote": False,
        "fee_floors_locked": True,
    }


def incubation_board(root: str | None = None) -> dict:
    store = load_incubation(root)
    rows = []
    for key, row in (store.get("series") or {}).items():
        if not isinstance(row, dict):
            continue
        rows.append(incubation_status(root, key))
    rows.sort(key=lambda r: (-int(r.get("n") or 0), str(r.get("series") or "")))
    return {
        "paper_only": True,
        "min_n": INCUBATION_MIN_N,
        "incubating_n": sum(1 for r in rows if r.get("lane") == "incubation"),
        "ready_n": sum(1 for r in rows if r.get("lane") == "ready_to_graduate"),
        "graduated": list(store.get("graduated") or []),
        "rows": rows[:40],
        "auto_promote": False,
        "fee_floors_locked": True,
        "note": "New series stay paper-only in incubation until staff graduate after n≥50.",
    }


def incubation_blocks_promote(root: str | None, series: str | None) -> str:
    """Non-empty when series must not leave paper incubation yet."""
    auto = incubation_blocks_auto(series)
    if auto:
        return auto
    status = incubation_status(root, series)
    if status.get("lane") == "idea_bank":
        return (
            f"incubation idea-bank only: {status.get('series')} "
            "— refuse main AUTO (weather/econ/Polymarket)"
        )
    if status.get("lane") in ("main", "graduated", "ready_to_graduate", "unknown"):
        # ready_to_graduate still needs staff — block auto-promote paths
        if status.get("lane") == "ready_to_graduate":
            return (
                f"incubation: {status.get('series')} ready (n={status.get('n')}) "
                "— staff graduate only, no auto-promote"
            )
        return ""
    if status.get("lane") == "incubation":
        return (
            f"incubation: {status.get('series')} paper-only "
            f"(n={status.get('n')}/{INCUBATION_MIN_N}) — no promote"
        )
    return ""


# ---- Ruin drill UX (Phase 10) ----------------------------------------------

def ruin_drill_status(root: str | None = None) -> dict:
    store = _load(
        _path(RUIN_DRILL_NAME, root),
        {"paper_only": True, "active": False, "level": None, "history": []},
    )
    level = store.get("level") if store.get("active") else None
    if level not in RUIN_LEVELS:
        level = None
    history = [h for h in (store.get("history") or []) if isinstance(h, dict)]
    # Dual-control checklist wants a practice this Chicago month.
    practiced_this_month = False
    last_practice_at = None
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("America/Chicago"))
        ym = f"{now.year}-{now.month:02d}"
        for h in reversed(history):
            stamp = str(h.get("at") or "")
            if not stamp:
                continue
            if ym in stamp or stamp.startswith(ym):
                practiced_this_month = True
                last_practice_at = stamp
                break
            # Also accept ISO stamps in current month via parse.
            try:
                when = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                if when.astimezone(ZoneInfo("America/Chicago")).strftime("%Y-%m") == ym:
                    practiced_this_month = True
                    last_practice_at = stamp
                    break
            except ValueError:
                continue
    except Exception:
        practiced_this_month = False
    return {
        "paper_only": True,
        "active": bool(store.get("active")) and level is not None,
        "level": level,
        "block_entries": level in ("soft", "hard", "nuclear"),
        "pause_all_bots": level in ("hard", "nuclear"),
        "flatten_recommended": level == "nuclear",
        "who": store.get("who") or "",
        "staff_note": store.get("note") or "",
        "at": store.get("at"),
        "history_n": len(history),
        "practiced_this_month": practiced_this_month,
        "last_practice_at": last_practice_at,
        "fee_floors_locked": True,
        "live_orders_enabled": False,
        "levels": {
            "soft": "block new entries; exits/settles still run",
            "hard": "soft + pause every paper bot",
            "nuclear": "hard + recommend flatten / cancel-on-pause habit",
        },
        "note": (
            "Ruin drill UX for vault. Soft/hard/nuclear. "
            "No profit guarantee. Exits stay available under soft."
            + (
                ""
                if practiced_this_month
                else " Reminder: practice soft/hard this Chicago month for dual-control."
            )
        ),
    }


def set_ruin_drill(
    root: str | None,
    level: str,
    *,
    who: str = "",
    note: str = "",
) -> dict:
    """Arm a ruin drill level. Soft/hard/nuclear only."""
    lvl = str(level or "").strip().lower()
    if lvl not in RUIN_LEVELS:
        return {
            "ok": False,
            "reason": f"level must be one of {RUIN_LEVELS}",
            "fee_floors_locked": True,
        }
    path = _path(RUIN_DRILL_NAME, root)
    store = _load(path, {"paper_only": True, "active": False, "history": []})
    row = {
        "paper_only": True,
        "active": True,
        "level": lvl,
        "who": str(who or "staff")[:80],
        "note": str(note or "")[:200],
        "at": _now(),
        "block_entries": True,
        "pause_all_bots": lvl in ("hard", "nuclear"),
        "flatten_recommended": lvl == "nuclear",
        "fee_floors_locked": True,
    }
    history = [h for h in (store.get("history") or []) if isinstance(h, dict)]
    history.append({**row, "action": "arm"})
    store.update(row)
    store["history"] = history[-40:]
    _save(path, store)
    # Hard/nuclear also pause every bot via existing pause file when available.
    if row["pause_all_bots"]:
        try:
            import pimp_desk
            pimp_desk.set_pause(root, on=True, all_bots=True, who=f"ruin:{lvl}")
        except Exception:
            pass
    return {"ok": True, **ruin_drill_status(root)}


def clear_ruin_drill(root: str | None, *, who: str = "", note: str = "") -> dict:
    """Clear active ruin drill and resume bots if we paused them."""
    path = _path(RUIN_DRILL_NAME, root)
    store = _load(path, {"paper_only": True, "active": False, "history": []})
    was = store.get("level") if store.get("active") else None
    history = [h for h in (store.get("history") or []) if isinstance(h, dict)]
    history.append({
        "action": "clear",
        "was_level": was,
        "who": str(who or "staff")[:80],
        "note": str(note or "")[:200],
        "at": _now(),
    })
    store = {
        "paper_only": True,
        "active": False,
        "level": None,
        "who": str(who or "staff")[:80],
        "note": str(note or "cleared")[:200],
        "at": _now(),
        "history": history[-40:],
        "fee_floors_locked": True,
    }
    _save(path, store)
    if was in ("hard", "nuclear"):
        try:
            import pimp_desk
            pimp_desk.set_pause(root, on=False, all_bots=True, who="ruin:clear")
        except Exception:
            pass
    return {"ok": True, **ruin_drill_status(root)}


def ruin_drill_blocks_entries(root: str | None = None) -> str:
    """Non-empty when a ruin drill is blocking new entries."""
    status = ruin_drill_status(root)
    if not status.get("active"):
        return ""
    lvl = status.get("level") or "soft"
    return (
        f"ruin drill {lvl}: new entries off"
        + ("; bots paused" if status.get("pause_all_bots") else "")
        + ("; flatten recommended" if status.get("flatten_recommended") else "")
        + ". Settles/exits still run under soft."
    )


# ---- Clock-skew / stale-world skip (Phase 10) ------------------------------

def stale_loop_bar(bot: str) -> float:
    return float(STALE_LOOP_SEC.get(str(bot), STALE_LOOP_DEFAULT))


def last_loop_seconds(root: str | None, bot: str) -> float | None:
    """Most recent recorded loop latency for bot (seconds), if any."""
    state = load_latency(root)
    last = None
    for r in state.get("rows") or []:
        if not isinstance(r, dict):
            continue
        if str(r.get("bot") or "") != str(bot):
            continue
        sec = _finite(r.get("seconds"))
        if sec is None:
            continue
        last = float(sec)
    return last


def stale_world_blocks(
    root: str | None,
    bot: str,
    *,
    loop_seconds=None,
    quote_age_sec=None,
    clock_skew_sec=None,
) -> str:
    """Non-empty reason when world is too stale for new entries (exits still on)."""
    bot_id = str(bot or "")
    if not bot_id:
        return ""
    loop = _finite(loop_seconds)
    if loop is None:
        loop = last_loop_seconds(root, bot_id)
    bar = stale_loop_bar(bot_id)
    if loop is not None and float(loop) > bar:
        return (
            f"stale-world: last loop {float(loop):.1f}s > {bar:.0f}s bar "
            f"({bot_id}); skip new entries"
        )
    age = _finite(quote_age_sec)
    if age is not None and float(age) > CLOCK_SKEW_MAX_SEC:
        return (
            f"stale-world: quote age {float(age):.0f}s > {CLOCK_SKEW_MAX_SEC:.0f}s; "
            "skip new entries"
        )
    skew = _finite(clock_skew_sec)
    if skew is not None and float(skew) > CLOCK_SKEW_MAX_SEC:
        return (
            f"clock-skew: source offset {float(skew):.0f}s > {CLOCK_SKEW_MAX_SEC:.0f}s; "
            "skip new entries"
        )
    return ""


def stale_world_status(root: str | None = None, bots: list | None = None) -> dict:
    """Masters board: per-bot last loop vs stale bar."""
    ids = []
    if bots:
        for b in bots:
            if isinstance(b, dict) and b.get("id"):
                ids.append(str(b["id"]))
    if not ids:
        ids = list(STALE_LOOP_SEC.keys())
    rows = []
    blocked = []
    for bot_id in ids:
        last = last_loop_seconds(root, bot_id)
        bar = stale_loop_bar(bot_id)
        reason = stale_world_blocks(root, bot_id, loop_seconds=last)
        row = {
            "bot": bot_id,
            "last_loop_s": round(last, 3) if last is not None else None,
            "bar_s": bar,
            "stale": bool(reason),
            "reason": reason or "",
        }
        rows.append(row)
        if reason:
            blocked.append(bot_id)
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "clock_skew_max_s": CLOCK_SKEW_MAX_SEC,
        "blocked": blocked,
        "rows": rows,
        "note": (
            "Stale-world skip when last loop > bar or quote/clock skew > "
            f"{CLOCK_SKEW_MAX_SEC:.0f}s. Exits/settles still run."
        ),
    }


# ---- Helper Gate A (Phase 8) -----------------------------------------------

def record_helper_fill(
    root: str | None,
    *,
    helper: str,
    bot: str = "",
    ticker: str = "",
    pnl=None,
    contracts=None,
    fill_tax: float = FILL_TAX_DEFAULT,
    fill_id: str = "",
    note: str = "",
) -> dict:
    """Persist a helper-attributed close for Gate A evidence. Never places alone."""
    helper_id = str(helper or "").strip()
    if not helper_id:
        return {"recorded": False, "reason": "helper required"}
    path = _path(HELPER_FILLS_NAME, root)
    store = _load(path, {"paper_only": True, "rows": [], "by_helper": {}})
    rows = list(store.get("rows") or [])
    fid = str(fill_id or "")[:80]
    if fid:
        for existing in rows:
            if isinstance(existing, dict) and str(existing.get("fill_id") or "") == fid:
                return {
                    "recorded": False,
                    "reason": "fill_id already present",
                    "row": existing,
                    "idempotent": True,
                }
    n = _finite(contracts) or 1.0
    pnl_n = _finite(pnl)
    tax_n = float(fill_tax) * max(1.0, n)
    taxed = None if pnl_n is None else round(pnl_n - tax_n, 4)
    row = {
        "at": _now(),
        "helper": helper_id[:60],
        "bot": str(bot or "")[:40],
        "ticker": str(ticker or "")[:80],
        "pnl": pnl_n,
        "contracts": n,
        "fill_tax": round(tax_n, 4),
        "pnl_taxed": taxed,
        "fill_id": fid,
        "note": str(note or "")[:160],
        "paper_only": True,
        "helper_only": True,
        "places_orders": False,
        "fee_floors_locked": True,
    }
    rows.append(row)
    store["rows"] = rows[-MAX_HELPER_FILL_ROWS:]
    by = store.get("by_helper") if isinstance(store.get("by_helper"), dict) else {}
    hrows = list(by.get(helper_id) or [])
    hrows.append(row)
    by[helper_id] = hrows[-800:]
    store["by_helper"] = by
    store["last_at"] = row["at"]
    _save(path, store)
    return {"recorded": True, "row": row}


def backfill_helper_fills_from_btc_closed(root: str | None = None) -> dict:
    """Catch-up: attribute calendar_scanner (etc.) helper fills from btc closed[].

    Also scans shadow_edge08_account.json closed rows (DESK_SHADOW densify path).
    Idempotent by fill_id. Observe densify for Gate A — never places alone.
    """
    base = _root(root)
    acct_paths = [
        (os.path.join(base, "btc15m-signal", "paper_account.json"), "btc-backfill"),
        (
            os.path.join(base, "btc15m-signal", "shadow_edge08_account.json"),
            "edge08-backfill",
        ),
    ]
    recorded = 0
    skipped = 0
    closed_n = 0
    samples: list[dict] = []
    sources_seen: list[str] = []
    for acct_path, id_prefix in acct_paths:
        try:
            with open(acct_path, encoding="utf-8") as handle:
                acct = json.load(handle)
        except Exception:
            acct = {}
        if not isinstance(acct, dict):
            acct = {}
        closed = [c for c in (acct.get("closed") or []) if isinstance(c, dict)]
        if closed:
            sources_seen.append(os.path.basename(acct_path))
        closed_n += len(closed)
        for pos in closed:
            helper = str(pos.get("helper_source") or "").strip()
            if not helper:
                # Feature-store style tag from buy path.
                if pos.get("calendar_loaded") is True:
                    helper = "calendar_scanner"
                else:
                    skipped += 1
                    continue
            fill_id = str(pos.get("fill_id") or "")
            if not fill_id:
                # Stable synthetic id from ticker+closed so catch-up stays idempotent.
                fill_id = (
                    f"{id_prefix}:{pos.get('ticker') or ''}:"
                    f"{pos.get('closed') or pos.get('at') or ''}"
                )[:80]
            out = record_helper_fill(
                root,
                helper=helper,
                bot="btc15m",
                ticker=str(pos.get("ticker") or ""),
                pnl=pos.get("pnl"),
                contracts=pos.get("contracts"),
                fill_id=fill_id,
                note=f"backfill from {os.path.basename(acct_path)}",
            )
            if out.get("recorded"):
                recorded += 1
                if len(samples) < 8:
                    samples.append({
                        "ticker": pos.get("ticker"),
                        "helper": helper,
                        "fill_id": fill_id,
                        "source": os.path.basename(acct_path),
                    })
            else:
                skipped += 1
    gate = helper_gate_a(root, "calendar_scanner")
    return {
        "ok": True,
        "recorded": recorded,
        "skipped": skipped,
        "closed_n": closed_n,
        "sources": sources_seen,
        "samples": samples,
        "gate_a_calendar": gate,
        "paper_only": True,
        "observe_only": True,
        "auto_promote": False,
        "fee_floors_locked": True,
        "places_orders": False,
        "live": False,
        "note": (
            "Helper fills backfill from btc15m paper + shadow_edge08 closed with "
            "helper_source / calendar_loaded. Gate A still needs staff arm; never LIVE."
        ),
    }


def helper_gate_a(
    root: str | None = None,
    helper: str | None = None,
    *,
    min_n: int = HELPER_GATE_A_MIN_N,
    fill_tax: float = FILL_TAX_DEFAULT,
) -> dict:
    """Gate A for one helper (or firm helpers): n≥min_n and taxed EV ≥ 0."""
    store = _load(_path(HELPER_FILLS_NAME, root), {"paper_only": True, "rows": []})
    rows = [r for r in (store.get("rows") or []) if isinstance(r, dict)]
    if helper:
        rows = [r for r in rows if str(r.get("helper") or "") == str(helper)]
    taxed = []
    for r in rows:
        pt = _finite(r.get("pnl_taxed"))
        if pt is not None:
            taxed.append(float(pt))
            continue
        pnl = _finite(r.get("pnl"))
        if pnl is None:
            continue
        n = _finite(r.get("contracts")) or 1.0
        taxed.append(float(pnl) - float(fill_tax) * max(1.0, n))
    n = len(taxed)
    exp = round(sum(taxed) / n, 4) if n else None
    ready = bool(n >= int(min_n) and exp is not None and exp + 1e-12 >= 0.0)
    n_to = max(0, int(min_n) - n)
    return {
        "gate": "A",
        "helper": helper,
        "ready": ready,
        "evidence_thin": not ready,
        "min_n": int(min_n),
        "n": n,
        "n_to_ready": n_to,
        "expectancy_taxed": exp,
        "fill_tax": float(fill_tax),
        "paper_only": True,
        "observe_only": True,
        "helper_only": True,
        "places_orders": False,
        "auto_promote": False,
        "fee_floors_locked": True,
        "label": (
            f"helper_gate_a={'ready' if ready else 'THIN'} "
            f"n={n}/{min_n} ev={exp} n_to={n_to}"
        ),
        "reason": (
            "helper taxed EV ≥ 0 with enough attributed fills"
            if ready
            else f"need n≥{min_n} and taxed EV≥0 (have n={n}, EV={exp})"
        ),
        "note": "Helpers never place alone until Gate A + staff promote.",
    }


def helper_promote_status(root: str | None = None, helper: str | None = None) -> dict:
    store = _load(
        _path(HELPER_PROMOTE_NAME, root),
        {"paper_only": True, "helpers": {}, "auto_promote": False},
    )
    helpers = store.get("helpers") if isinstance(store.get("helpers"), dict) else {}
    if helper:
        row = helpers.get(str(helper)) if isinstance(helpers.get(str(helper)), dict) else {}
        gate = helper_gate_a(root, helper)
        armed = bool(row.get("staff_approved")) and bool(row.get("autonomy"))
        ready = bool(gate.get("ready"))
        return {
            "paper_only": True,
            "observe_only": True,
            "helper": str(helper),
            "staff_approved": bool(row.get("staff_approved")),
            "autonomy": bool(row.get("autonomy")),
            "armed": armed,
            "gate_a": gate,
            "promote_ready": ready,
            "evidence_thin": not ready,
            "label": gate.get("label") or "",
            "auto_promote": False,
            "places_orders": False,
            "fee_floors_locked": True,
            "note": row.get("note") or "",
            "at": row.get("at"),
        }
    board = []
    for hid in sorted(set(list(helpers.keys()) + [
        str(r.get("helper") or "")
        for r in (_load(_path(HELPER_FILLS_NAME, root), {"rows": []}).get("rows") or [])
        if isinstance(r, dict) and r.get("helper")
    ])):
        if not hid:
            continue
        board.append(helper_promote_status(root, hid))
    thin_n = sum(1 for r in board if r.get("evidence_thin"))
    return {
        "paper_only": True,
        "observe_only": True,
        "helpers": board,
        "evidence_thin": thin_n > 0 or not board,
        "thin_n": thin_n,
        "ready_n": sum(1 for r in board if r.get("promote_ready")),
        "label": (
            f"helper_gate_a board helpers={len(board)} "
            f"ready={sum(1 for r in board if r.get('promote_ready'))} thin={thin_n}"
        ),
        "auto_promote": False,
        "places_orders": False,
        "fee_floors_locked": True,
        "note": "Helper Gate A board. Autonomy requires Gate A ready + staff arm.",
    }


def staff_set_helper_autonomy(
    root: str | None,
    helper: str,
    enabled: bool,
    *,
    note: str = "",
    force: bool = False,
) -> dict:
    """Staff arm/disarm helper autonomy. Requires Gate A unless force (tests)."""
    helper_id = str(helper or "").strip()
    if not helper_id:
        return {"ok": False, "reason": "helper required", "auto_promote": False}
    gate = helper_gate_a(root, helper_id)
    if enabled and not force and not gate.get("ready"):
        return {
            "ok": False,
            "helper": helper_id,
            "autonomy": False,
            "staff_approved": False,
            "reason": gate.get("reason"),
            "gate_a": gate,
            "auto_promote": False,
            "places_orders": False,
            "fee_floors_locked": True,
        }
    path = _path(HELPER_PROMOTE_NAME, root)
    store = _load(path, {"paper_only": True, "helpers": {}, "auto_promote": False})
    helpers = store.get("helpers") if isinstance(store.get("helpers"), dict) else {}
    helpers[helper_id] = {
        "staff_approved": bool(enabled),
        "autonomy": bool(enabled),
        "at": _now(),
        "note": str(note or "")[:200],
        "gate_n": gate.get("n"),
        "gate_ev": gate.get("expectancy_taxed"),
        "auto_promote": False,
        "places_orders": False,
        "fee_floors_locked": True,
    }
    store["helpers"] = helpers
    store["auto_promote"] = False
    store["paper_only"] = True
    _save(path, store)
    return {
        "ok": True,
        "helper": helper_id,
        "autonomy": bool(enabled),
        "staff_approved": bool(enabled),
        "gate_a": gate,
        "auto_promote": False,
        "places_orders": False,
        "fee_floors_locked": True,
        "reason": "armed" if enabled else "disarmed",
    }


def helper_autonomy_blocks(root: str | None, helper: str) -> str:
    """Non-empty when helper must not place alone / claim autonomy."""
    helper_id = str(helper or "").strip()
    if not helper_id:
        return "helper autonomy blocked: helper id required"
    st = helper_promote_status(root, helper_id)
    if st.get("armed") and (st.get("gate_a") or {}).get("ready"):
        return ""
    if not (st.get("gate_a") or {}).get("ready"):
        return (
            f"helper Gate A not ready for {helper_id}: "
            f"{(st.get('gate_a') or {}).get('reason')}"
        )
    return (
        f"helper {helper_id} Gate A ready but staff autonomy not armed "
        "(auto_promote=False)"
    )


def helper_may_place_alone(root: str | None, helper: str) -> bool:
    """True only when Gate A ready AND staff armed. Default False forever for scanners."""
    return helper_autonomy_blocks(root, helper) == ""


# ---- Tax / fee ledger (Phase 10) -------------------------------------------

def estimate_kalshi_fee(price, contracts=1.0) -> float:
    """Kalshi-style ceil(0.07 * p * (1-p) * contracts) per contract aggregate."""
    p = _finite(price)
    n = _finite(contracts) or 1.0
    if p is None or not (0.0 < p < 1.0) or n <= 0:
        return 0.0
    raw = 0.07 * float(p) * (1.0 - float(p)) * float(n)
    return math.ceil(round(raw * 100, 6)) / 100.0


def record_fee_ledger(
    root: str | None,
    *,
    bot: str,
    ticker: str = "",
    side: str = "",
    price=None,
    contracts=None,
    fee=None,
    fill_tax: float = FILL_TAX_DEFAULT,
    pnl=None,
    fill_id: str = "",
    kind: str = "fill",
    note: str = "",
) -> dict:
    """Persist fee + fill-tax row so firm ROI can be audited.

    Idempotent on non-empty fill_id (catchup / re-settle safe). Never invents
    fee rows without a caller; fee floors stay locked.
    """
    path = _path(FEE_LEDGER_NAME, root)
    store = _load(path, {"paper_only": True, "rows": [], "by_bot": {}})
    rows = list(store.get("rows") or [])
    fid = str(fill_id or "")[:80]
    if fid:
        for existing in rows:
            if isinstance(existing, dict) and str(existing.get("fill_id") or "") == fid:
                return {
                    "recorded": False,
                    "reason": "fill_id already present",
                    "row": existing,
                    "idempotent": True,
                }
    n = _finite(contracts) or 1.0
    px = _finite(price)
    fee_n = _finite(fee)
    if fee_n is None:
        fee_n = estimate_kalshi_fee(px, n) if px is not None else 0.0
    tax_n = float(fill_tax) * max(1.0, n)
    pnl_n = _finite(pnl)
    taxed_pnl = None if pnl_n is None else round(pnl_n - tax_n, 4)
    row = {
        "at": _now(),
        "bot": str(bot),
        "ticker": str(ticker or "")[:80],
        "side": str(side or "")[:20],
        "kind": str(kind or "fill")[:40],
        "price": px,
        "contracts": n,
        "fee": round(float(fee_n), 4),
        "fill_tax": round(tax_n, 4),
        "fee_plus_tax": round(float(fee_n) + tax_n, 4),
        "pnl": pnl_n,
        "pnl_taxed": taxed_pnl,
        "fill_id": fid,
        "note": str(note or "")[:160],
        "paper_only": True,
        "fee_floors_locked": True,
    }
    rows.append(row)
    store["rows"] = rows[-MAX_FEE_LEDGER_ROWS:]
    by = store.get("by_bot") if isinstance(store.get("by_bot"), dict) else {}
    bot_rows = list(by.get(str(bot)) or [])
    bot_rows.append(row)
    by[str(bot)] = bot_rows[-500:]
    store["by_bot"] = by
    store["last_at"] = row["at"]
    _save(path, store)
    return {"recorded": True, "row": row}


def backfill_fee_ledger_from_closed(root: str | None = None) -> dict:
    """Catch-up: densify fee ledger from tower closed[] / history.

    Uses stored fee or entry-side price→estimate only (ask|entry|entry_price|
    price). Never invents fee from exit marks (exit_price/exit_bid/mark_bid/
    bid) — settle wipe bids are not fill prices. Never invents closes.
    Idempotent by fill_id (and skips bot+ticker already in ledger).
    Observe densify only.
    """
    base = _root(root)
    sources = (
        (os.path.join(base, "btc15m-signal", "paper_account.json"), "btc15m", "btc"),
        (
            os.path.join(base, "btc15m-signal", "shadow_edge08_account.json"),
            "btc15m",
            "edge08",
        ),
        (
            os.path.join(base, "commodity-15m-paper", "paper_account.json"),
            "commodity-15m",
            "cmd",
        ),
        (os.path.join(base, "sports-gap-paper", "state.json"), "sports-gap", "sports"),
        (
            os.path.join(base, "kalshi-sp500-paper", "paper_state.json"),
            "kalshi-sp",
            "inx",
        ),
        (
            os.path.join(base, "kalshi-sized-paper", "paper_state.json"),
            "kalshi-sized",
            "sized",
        ),
    )
    store = _load(_path(FEE_LEDGER_NAME, root), {"paper_only": True, "rows": []})
    ledger = [r for r in (store.get("rows") or []) if isinstance(r, dict)]
    ledger_keys: set = set()
    for r in ledger:
        fid = str(r.get("fill_id") or "").strip()
        if fid:
            ledger_keys.add(("id", fid))
        tick = str(r.get("ticker") or "").strip()
        bot = str(r.get("bot") or "").strip()
        if tick and bot:
            ledger_keys.add(("bt", bot, tick))

    recorded = 0
    skipped = 0
    closed_n = 0
    samples: list[dict] = []
    sources_seen: list[str] = []
    hist_bots: list[dict] = []

    for acct_path, bot_id, id_prefix in sources:
        try:
            with open(acct_path, encoding="utf-8") as handle:
                acct = json.load(handle)
        except Exception:
            acct = {}
        if not isinstance(acct, dict):
            acct = {}
        closed = [
            c
            for c in list(acct.get("closed") or []) + list(acct.get("history") or [])
            if isinstance(c, dict)
        ]
        if closed:
            sources_seen.append(os.path.basename(acct_path))
        closed_n += len(closed)
        hist_rows: list[dict] = []
        for pos in closed:
            pnl = _finite(pos.get("pnl") if pos.get("pnl") is not None else pos.get("pnl_usd"))
            if pnl is None:
                skipped += 1
                continue
            tick = str(pos.get("ticker") or pos.get("what") or "").strip()
            fee_n = _finite(pos.get("fee"))
            px = None
            # Entry-side fill prices only — exit_price/bid invent wipe-fee rows
            # (Prefer-1 sibling of cmd t-stop entry-bid refuse #449).
            for key in ("ask", "entry", "entry_price", "price"):
                px = _finite(pos.get(key))
                if px is not None:
                    break
            # Never invent fee without a stored fee or an entry-side price.
            if fee_n is None and px is None:
                skipped += 1
                continue
            fill_id = str(pos.get("fill_id") or "").strip()
            if not fill_id:
                fill_id = (
                    f"{id_prefix}:{tick}:"
                    f"{pos.get('closed') or pos.get('at') or pos.get('day') or ''}"
                )[:80]
            if fill_id and ("id", fill_id) in ledger_keys:
                skipped += 1
                hist_rows.append({"ticker": tick, "pnl": pnl, "fill_id": fill_id})
                continue
            if tick and ("bt", bot_id, tick) in ledger_keys:
                skipped += 1
                hist_rows.append({"ticker": tick, "pnl": pnl, "fill_id": fill_id})
                continue
            out = record_fee_ledger(
                root,
                bot=bot_id,
                ticker=tick,
                side=str(pos.get("side") or "")[:20],
                price=px,
                contracts=pos.get("contracts"),
                fee=fee_n,
                pnl=pnl,
                fill_id=fill_id,
                kind="catchup",
                note=f"catchup from {os.path.basename(acct_path)}",
            )
            hist_rows.append({"ticker": tick, "pnl": pnl, "fill_id": fill_id})
            if out.get("recorded"):
                recorded += 1
                ledger_keys.add(("id", fill_id))
                if tick:
                    ledger_keys.add(("bt", bot_id, tick))
                if len(samples) < 8:
                    samples.append({
                        "bot": bot_id,
                        "ticker": tick,
                        "fill_id": fill_id,
                        "source": os.path.basename(acct_path),
                        "fee": (out.get("row") or {}).get("fee"),
                    })
            else:
                skipped += 1
        if hist_rows:
            hist_bots.append({"id": bot_id, "history": hist_rows})

    complete = fee_ledger_completeness(root, bots=hist_bots) if hist_bots else {
        "history_n": 0, "matched": 0, "rate": None,
    }
    return {
        "ok": True,
        "recorded": recorded,
        "skipped": skipped,
        "closed_n": closed_n,
        "sources": sources_seen,
        "samples": samples,
        "completeness": {
            "history_n": complete.get("history_n"),
            "matched": complete.get("matched"),
            "rate": complete.get("rate"),
        },
        "paper_only": True,
        "observe_only": True,
        "auto_promote": False,
        "fee_floors_locked": True,
        "places_orders": False,
        "live": False,
        "note": (
            "Fee ledger catchup from tower closed[]/history with fee or "
            "entry-side ask|entry|entry_price|price (never exit_price/bid invent). "
            "Idempotent by fill_id / bot+ticker. Never LIVE; never invents closes."
        ),
    }


def fee_ledger_summary(root: str | None = None) -> dict:
    store = _load(_path(FEE_LEDGER_NAME, root), {"paper_only": True, "rows": []})
    rows = [r for r in (store.get("rows") or []) if isinstance(r, dict)]
    fee_sum = round(sum(float(_finite(r.get("fee")) or 0) for r in rows), 4)
    tax_sum = round(sum(float(_finite(r.get("fill_tax")) or 0) for r in rows), 4)
    return {
        "paper_only": True,
        "n": len(rows),
        "fee_sum": fee_sum,
        "fill_tax_sum": tax_sum,
        "fee_plus_tax_sum": round(fee_sum + tax_sum, 4),
        "fee_floors_locked": True,
        "note": "Tax/fee ledger for true ROI. Fill tax default 1¢×contracts.",
    }


def fee_ledger_completeness(root: str | None = None, bots: list | None = None) -> dict:
    """Share of closed history rows that have a matching fee-ledger entry."""
    store = _load(_path(FEE_LEDGER_NAME, root), {"paper_only": True, "rows": []})
    ledger = [r for r in (store.get("rows") or []) if isinstance(r, dict)]
    ledger_keys = set()
    for r in ledger:
        fid = str(r.get("fill_id") or "").strip()
        if fid:
            ledger_keys.add(("id", fid))
        tick = str(r.get("ticker") or "").strip()
        bot = str(r.get("bot") or "").strip()
        if tick and bot:
            ledger_keys.add(("bt", bot, tick))
    hist_n = 0
    matched = 0
    missing = []
    for bot in bots or []:
        if not isinstance(bot, dict):
            continue
        bot_id = str(bot.get("id") or "")
        for h in bot.get("history") or []:
            if not isinstance(h, dict):
                continue
            pnl = _finite(h.get("pnl") if h.get("pnl") is not None else h.get("pnl_usd"))
            if pnl is None:
                continue
            hist_n += 1
            fid = str(h.get("fill_id") or "").strip()
            tick = str(h.get("ticker") or h.get("what") or "").strip()
            ok = False
            if fid and ("id", fid) in ledger_keys:
                ok = True
            elif tick and bot_id and ("bt", bot_id, tick) in ledger_keys:
                ok = True
            if ok:
                matched += 1
            elif len(missing) < 12:
                missing.append({"bot": bot_id, "ticker": tick, "fill_id": fid})
    rate = round(matched / hist_n, 4) if hist_n else None
    return {
        "paper_only": True,
        "history_n": hist_n,
        "ledger_n": len(ledger),
        "matched": matched,
        "rate": rate,
        "pass": hist_n == 0 or (rate is not None and rate >= 0.80 and hist_n >= 5),
        "missing_sample": missing,
        "fee_floors_locked": True,
        "bar": 0.80,
        "note": (
            "Completeness = closed history rows with fee-ledger match by fill_id "
            "or bot+ticker. Target ≥80% once n≥5."
        ),
    }


def adverse_cool_blocks(root: str | None, bot: str) -> str:
    """Non-empty reason when bot is in adverse cool-off window."""
    path = _path(ADVERSE_COOL_NAME, root)
    state = _load(path, {"paper_only": True, "bots": {}})
    row = (state.get("bots") or {}).get(str(bot))
    if not isinstance(row, dict):
        return ""
    until = _finite(row.get("until"))
    if until is None or time.time() >= until:
        return ""
    left = int(max(1, (until - time.time()) / 60.0))
    return (
        f"adverse cool-off: {bot} paused ~{left}m after "
        f"{row.get('drop')} drop on {row.get('ticker') or 'fill'}"
    )


def adverse_cool_status(root: str | None = None) -> dict:
    """Observe board: which towers are in adverse cool-off right now."""
    path = _path(ADVERSE_COOL_NAME, root)
    state = _load(path, {"paper_only": True, "bots": {}})
    now = time.time()
    active = []
    for bot, row in (state.get("bots") or {}).items():
        if not isinstance(row, dict):
            continue
        until = _finite(row.get("until"))
        if until is None or until <= now:
            continue
        active.append({
            "bot": str(bot),
            "ticker": row.get("ticker"),
            "drop": row.get("drop"),
            "left_min": int(max(1, (until - now) / 60.0)),
            "until": until,
            "at": row.get("at"),
        })
    active.sort(key=lambda r: str(r.get("bot") or ""))
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "drop_bar": ADVERSE_MARK_DROP,
        "minutes": ADVERSE_COOL_MINUTES,
        "active_n": len(active),
        "active": active,
        "label": (
            f"adverse_cool active={len(active)} "
            f"bar={ADVERSE_MARK_DROP} window={ADVERSE_COOL_MINUTES}m"
        ),
        "note": (
            f"Adverse cool-off after ≥{ADVERSE_MARK_DROP} mark drop — "
            f"{ADVERSE_COOL_MINUTES}m pause. Floors locked."
        ),
    }


def adverse_selection_autopsy(
    root: str | None = None,
    *,
    bots: list | None = None,
) -> dict:
    """Count fills that immediately mark ≤ −5¢ vs entry (adverse selection study)."""
    path = _path(ADVERSE_COOL_NAME, root)
    state = _load(path, {"paper_only": True, "bots": {}, "history": []})
    hist = [r for r in (state.get("history") or []) if isinstance(r, dict)]
    for bot, row in (state.get("bots") or {}).items():
        if not isinstance(row, dict):
            continue
        drop = _finite(row.get("drop"))
        if drop is None or drop + 1e-12 < ADVERSE_MARK_DROP:
            continue
        hist.append({
            "bot": str(bot),
            "ticker": row.get("ticker"),
            "drop": drop,
            "entry": row.get("entry"),
            "mark": row.get("mark"),
            "at": row.get("at"),
            "source": "cool_snapshot",
        })
    for bot in bots or []:
        if not isinstance(bot, dict):
            continue
        bot_id = str(bot.get("id") or "")
        for h in bot.get("history") or []:
            if not isinstance(h, dict):
                continue
            entry = _finite(
                h.get("entry_price")
                if h.get("entry_price") is not None
                else h.get("ask") if h.get("ask") is not None else h.get("entry")
            )
            mark = _finite(
                h.get("exit_price")
                if h.get("exit_price") is not None
                else h.get("mark_price") if h.get("mark_price") is not None else h.get("bid")
            )
            if entry is None or mark is None or entry <= 0:
                continue
            drop = entry - mark
            if drop + 1e-12 < ADVERSE_MARK_DROP:
                continue
            hist.append({
                "bot": bot_id,
                "ticker": h.get("ticker") or h.get("what"),
                "drop": round(drop, 4),
                "entry": entry,
                "mark": mark,
                "at": h.get("closed") or h.get("at"),
                "source": "history",
            })
    seen = set()
    uniq = []
    for r in hist:
        key = (str(r.get("bot")), str(r.get("ticker")), r.get("drop"))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)
    by_bot: dict[str, int] = {}
    for r in uniq:
        b = str(r.get("bot") or "")
        by_bot[b] = int(by_bot.get(b) or 0) + 1
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "drop_bar": ADVERSE_MARK_DROP,
        "n": len(uniq),
        "by_bot": by_bot,
        "sample": uniq[:12],
        "label": f"adverse_selection n={len(uniq)} bar={ADVERSE_MARK_DROP}",
        "note": (
            "Adverse-selection autopsy — fills marking ≤−5¢ vs entry. "
            "Observe only; floors locked."
        ),
    }


def _history_tag_hits(
    bots: list | None,
    *,
    bot_ids: set[str] | frozenset | None = None,
    tag_keys: tuple[str, ...] = (),
    tag_values_truthy: tuple[str, ...] = (),
    note_needles: tuple[str, ...] = (),
) -> list[dict]:
    """Scan bot history/journals for tagged fills (autopsy helpers)."""
    hits = []
    for bot in bots or []:
        if not isinstance(bot, dict):
            continue
        bot_id = str(bot.get("id") or "")
        if bot_ids is not None and bot_id not in bot_ids:
            continue
        for h in list(bot.get("history") or []) + list(bot.get("closed") or []):
            if not isinstance(h, dict):
                continue
            tags = h.get("tags") if isinstance(h.get("tags"), (list, tuple, set)) else []
            tag_set = {str(t).lower() for t in tags}
            flagged = False
            for k in tag_keys:
                if h.get(k) is True or str(h.get(k) or "").lower() in ("1", "true", "yes"):
                    flagged = True
                    break
            for k in tag_values_truthy:
                if k.lower() in tag_set:
                    flagged = True
                    break
            note = str(h.get("note") or h.get("exit") or h.get("reason") or "").lower()
            if not flagged and note_needles and any(n in note for n in note_needles):
                flagged = True
            if not flagged and any(n in tag_set for n in note_needles):
                flagged = True
            if not flagged:
                continue
            hits.append({
                "bot": bot_id,
                "ticker": h.get("ticker") or h.get("what"),
                "at": h.get("closed") or h.get("at") or h.get("when"),
                "pnl": _finite(h.get("pnl") if h.get("pnl") is not None else h.get("pnl_usd")),
                "tags": list(tags)[:8],
            })
    return hits


def news_gap_autopsy(root: str | None = None, *, bots: list | None = None) -> dict:
    """Should-be-zero: BTC fills inside ±30m USD-high news window after fail-closed."""
    hits = _history_tag_hits(
        bots,
        bot_ids=frozenset({"btc15m"}),
        tag_keys=("news_near", "in_news_window", "news_gap", "news_window"),
        tag_values_truthy=("news_near", "news_gap", "in_news_window", "news_window"),
        note_needles=("news window", "news_gap", "usd high-impact", "news near"),
    )
    journal = _load(
        _path("desk_news_gap_autopsy.json", root),
        {"paper_only": True, "rows": []},
    )
    for r in journal.get("rows") or []:
        if isinstance(r, dict):
            hits.append({
                "bot": str(r.get("bot") or "btc15m"),
                "ticker": r.get("ticker"),
                "at": r.get("at"),
                "pnl": _finite(r.get("pnl")),
                "tags": ["journal"],
            })
    n = len(hits)
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "should_be_zero": True,
        "n": n,
        "bad_n": n,
        "pass": n == 0,
        "sample": hits[:12],
        "label": f"news_gap_autopsy n={n} (should be 0)",
        "note": (
            "News-gap loser autopsy — any BTC fill inside ±30m USD-high window "
            "should be zero after fail-closed. Floors locked."
        ),
    }


def eia_gap_autopsy(root: str | None = None, *, bots: list | None = None) -> dict:
    """Should-be-zero: energy fills inside EIA inventory blackout."""
    hits = _history_tag_hits(
        bots,
        bot_ids=frozenset({"commodity-15m"}),
        tag_keys=("eia_blackout", "eia_gap", "in_eia_window"),
        tag_values_truthy=("eia_blackout", "eia_gap", "in_eia_window"),
        note_needles=("eia blackout", "eia_gap", "inventory blackout"),
    )
    journal = _load(
        _path("desk_eia_gap_autopsy.json", root),
        {"paper_only": True, "rows": []},
    )
    for r in journal.get("rows") or []:
        if isinstance(r, dict):
            hits.append({
                "bot": str(r.get("bot") or "commodity-15m"),
                "ticker": r.get("ticker"),
                "at": r.get("at"),
                "pnl": _finite(r.get("pnl")),
                "tags": ["journal"],
            })
    n = len(hits)
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "should_be_zero": True,
        "n": n,
        "bad_n": n,
        "pass": n == 0,
        "sample": hits[:12],
        "label": f"eia_gap_autopsy n={n} (should be 0)",
        "note": (
            "EIA-gap loser autopsy — energy fills inside inventory blackout "
            "should be zero. Floors locked."
        ),
    }


def weekend_inx_autopsy(root: str | None = None, *, bots: list | None = None) -> dict:
    """Should-be-zero: INX (sp/sized) fills on weekend."""
    hits = _history_tag_hits(
        bots,
        bot_ids=frozenset({"kalshi-sp", "kalshi-sized"}),
        tag_keys=("weekend", "weekend_fill", "is_weekend"),
        tag_values_truthy=("weekend", "weekend_fill", "WEEKEND"),
        note_needles=("weekend", "WEEKEND"),
    )
    for bot in bots or []:
        if not isinstance(bot, dict):
            continue
        bot_id = str(bot.get("id") or "")
        if bot_id not in ("kalshi-sp", "kalshi-sized"):
            continue
        for h in list(bot.get("history") or []) + list(bot.get("closed") or []):
            if not isinstance(h, dict):
                continue
            raw = str(h.get("closed") or h.get("at") or h.get("when") or "")[:10]
            if len(raw) < 10 or raw[4] != "-" or raw[7] != "-":
                continue
            try:
                from datetime import datetime
                day = datetime.strptime(raw[:10], "%Y-%m-%d")
                if day.weekday() < 5:
                    continue
            except Exception:
                continue
            hits.append({
                "bot": bot_id,
                "ticker": h.get("ticker") or h.get("what"),
                "at": raw,
                "pnl": _finite(h.get("pnl") if h.get("pnl") is not None else h.get("pnl_usd")),
                "tags": ["weekend_date"],
            })
    journal = _load(
        _path("desk_weekend_inx_autopsy.json", root),
        {"paper_only": True, "rows": []},
    )
    for r in journal.get("rows") or []:
        if isinstance(r, dict):
            hits.append({
                "bot": str(r.get("bot") or "kalshi-sp"),
                "ticker": r.get("ticker"),
                "at": r.get("at"),
                "pnl": _finite(r.get("pnl")),
                "tags": ["journal"],
            })
    seen = set()
    uniq = []
    for r in hits:
        key = (r.get("bot"), r.get("ticker"), r.get("at"))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)
    n = len(uniq)
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "should_be_zero": True,
        "n": n,
        "bad_n": n,
        "pass": n == 0,
        "sample": uniq[:12],
        "label": f"weekend_inx_autopsy n={n} (should be 0)",
        "note": (
            "Weekend INX fill autopsy — sp/sized weekend fills should be zero. "
            "Floors locked."
        ),
    }



def latest_weekly_scorecard(root: str | None = None) -> dict | None:
    path = _path(WEEKLY_SCORECARD, root)
    store = _load(path, {"paper_only": True, "cards": [], "latest": None})
    latest = store.get("latest")
    return latest if isinstance(latest, dict) else None


# ---- Master graduation checklist (Phase 6) ---------------------------------

def _chicago_day() -> str:
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d")
    except Exception:
        return time.strftime("%Y-%m-%d", time.gmtime())


def _stamp_chicago_day(at) -> str:
    """Chicago YYYY-MM-DD for a UTC ``...Z`` stamp from ``_now()``.

    Latency rows are stamped in UTC. Comparing the raw prefix to the Chicago
    day drops every row written after 6 PM CT (UTC has already rolled over).
    Stamps without a zone are taken as already local.
    """
    raw = str(at or "").strip()
    if len(raw) < 10 or raw[4] != "-":
        return ""
    if not raw.endswith("Z"):
        return raw[:10]
    try:
        from datetime import datetime, timezone
        from zoneinfo import ZoneInfo
        when = datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return when.astimezone(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d")
    except Exception:
        return raw[:10]


def tower_codes_from_row(row: dict | None) -> dict:
    """Normalize a tower_master_row into M1–M7 pass bits + all flag."""
    row = row if isinstance(row, dict) else {}
    passing = row.get("passing") if isinstance(row.get("passing"), dict) else {}
    codes = {code: bool(passing.get(code)) for code in GRADUATION_CODES}
    return {
        "bot": str(row.get("bot") or ""),
        "codes": codes,
        "all": all(codes.values()),
        "n_pass": sum(1 for v in codes.values() if v),
        "n_codes": len(GRADUATION_CODES),
    }


def capture_graduation_week(
    root: str | None,
    towers: list | None = None,
    *,
    label: str | None = None,
) -> dict:
    """Persist one Chicago-day graduation card from master tower rows."""
    day = label or _chicago_day()
    tower_map = {}
    for row in towers or []:
        if not isinstance(row, dict):
            continue
        card = tower_codes_from_row(row)
        bot = card.get("bot") or ""
        if not bot:
            continue
        tower_map[bot] = card
    week = {
        "paper_only": True,
        "label": day,
        "captured_at": _now(),
        "towers": tower_map,
        "masters_ready": sorted(
            b for b, c in tower_map.items() if isinstance(c, dict) and c.get("all")
        ),
        "weeks_required": GRADUATION_WEEKS_REQUIRED,
        "auto_promote": False,
        "fee_floors_locked": True,
        "note": (
            "Master only after "
            f"{GRADUATION_WEEKS_REQUIRED} consecutive Chicago weeks with all M1–M7. "
            "Staff gate — never auto-promote."
        ),
    }
    path = _path(MASTER_GRAD, root)
    store = _load(path, {"paper_only": True, "weeks": [], "latest": None})
    weeks = [w for w in (store.get("weeks") or []) if isinstance(w, dict)]
    # Replace same-day card; keep history short.
    weeks = [w for w in weeks if str(w.get("label") or "") != day]
    weeks.append(week)
    store["weeks"] = weeks[-60:]
    store["latest"] = week
    store["board"] = graduation_board(root=None, store=store)
    _save(path, store)
    return week


def _graduation_denial_for_card(card: dict | None, *, n_settles: int | None = None) -> list[str]:
    """Per-tower denial codes from latest M-pass card + thin sample."""
    denials: list[str] = []
    card = card if isinstance(card, dict) else {}
    codes = card.get("codes") if isinstance(card.get("codes"), dict) else {}
    for m in GRADUATION_CODES:
        if codes and not codes.get(m):
            denials.append(f"{m}_fail")
    if n_settles is not None and int(n_settles) < 5:
        denials.append("thin_n")
    return denials


def graduation_gate_flags(
    root: str | None = None,
    *,
    bots: list | None = None,
) -> dict:
    """Fail-closed Master badge gates: fee ledger ≥80%, no news fail-open, no CLI bypass."""
    fees = fee_ledger_completeness(root, bots=bots)
    fee_rate = _finite(fees.get("rate"))
    hist_n = int(fees.get("history_n") or 0)
    fee_fail = bool(
        hist_n >= 5 and (fee_rate is None or fee_rate + 1e-12 < 0.80)
    )
    news = news_gap_autopsy(root, bots=bots)
    news_fail = int(news.get("bad_n") or news.get("n") or 0) > 0
    cli_bypass = bool(LIVE_ORDERS_ENABLED)
    try:
        dc = dual_control_status(root)
        if bool(dc.get("live_orders_enabled")):
            cli_bypass = True
    except Exception:
        pass
    denials = []
    if fee_fail:
        denials.append("fee_ledger")
    if news_fail:
        denials.append("news_fail_open")
    if cli_bypass:
        denials.append("cli_bypass")
    fail_closed = bool(denials)
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "fee_ledger_rate": fee_rate,
        "fee_ledger_fail": fee_fail,
        "news_fail_open": news_fail,
        "cli_bypass": cli_bypass,
        "denial_codes": denials,
        "master_badge_fail_closed": fail_closed,
        "badge_allowed": not fail_closed,
        "note": (
            "Master badge fail-closed when fee ledger <80% (n≥5), "
            "news fail-open fills present, or LIVE/CLI bypass armed."
        ),
    }


def graduation_board(
    root: str | None = None,
    *,
    store: dict | None = None,
    bots: list | None = None,
) -> dict:
    """Consecutive all-pass weeks per tower → master / week_1 / not_ready.

    Adds denial_codes enum + master_badge_fail_closed when fee_ledger <80%
    or known fail-open gates (news / CLI bypass).
    """
    if store is None:
        store = _load(_path(MASTER_GRAD, root), {"paper_only": True, "weeks": []})
    weeks = [w for w in (store.get("weeks") or []) if isinstance(w, dict)]
    weeks = sorted(weeks, key=lambda w: str(w.get("label") or ""))
    bot_ids: set[str] = set()
    for w in weeks:
        towers = w.get("towers") if isinstance(w.get("towers"), dict) else {}
        bot_ids.update(str(b) for b in towers.keys())
    gates = graduation_gate_flags(root, bots=bots)
    gate_denials = list(gates.get("denial_codes") or [])
    badge_fail = bool(gates.get("master_badge_fail_closed"))
    board = {}
    firm_denials: list[str] = list(gate_denials)
    for bot in sorted(bot_ids):
        streak = 0
        last_card = None
        for w in reversed(weeks):
            towers = w.get("towers") if isinstance(w.get("towers"), dict) else {}
            card = towers.get(bot) if isinstance(towers.get(bot), dict) else None
            if card and card.get("all"):
                streak += 1
                if last_card is None:
                    last_card = card
            else:
                if last_card is None:
                    last_card = card
                break
        if streak >= GRADUATION_WEEKS_REQUIRED:
            status = "master"
        elif streak == 1:
            status = "week_1"
        else:
            status = "not_ready"
        n_settles = None
        for b in bots or []:
            if isinstance(b, dict) and str(b.get("id") or "") == bot:
                hist = [h for h in (b.get("history") or []) if isinstance(h, dict)]
                n_settles = len(hist)
                break
        denials = _graduation_denial_for_card(last_card, n_settles=n_settles)
        denials = list(dict.fromkeys(denials + gate_denials))
        for d in denials:
            if d not in firm_denials:
                firm_denials.append(d)
        graduated = status == "master"
        badge_render = graduated and not badge_fail
        board[bot] = {
            "bot": bot,
            "consecutive_all_pass_weeks": streak,
            "weeks_required": GRADUATION_WEEKS_REQUIRED,
            "status": status,
            "graduated": graduated,
            "badge_render": badge_render,
            "denial_codes": denials,
            "auto_promote": False,
        }
    masters = sorted(b for b, r in board.items() if r.get("graduated"))
    masters_badged = sorted(b for b, r in board.items() if r.get("badge_render"))
    return {
        "paper_only": True,
        "weeks_n": len(weeks),
        "weeks_required": GRADUATION_WEEKS_REQUIRED,
        "towers": board,
        "masters": masters,
        "masters_n": len(masters),
        "masters_badged": masters_badged,
        "denial_codes": firm_denials,
        "denial_code_enum": list(GRADUATION_DENIAL_CODES),
        "master_badge_fail_closed": badge_fail,
        "badge_allowed": not badge_fail,
        "gates": gates,
        "auto_promote": False,
        "fee_floors_locked": True,
        "note": (
            "Phase 6 graduation board. Master = "
            f"{GRADUATION_WEEKS_REQUIRED} consecutive all-pass weeks. "
            "Badge fail-closed on fee_ledger/news_fail_open/cli_bypass. No auto-promote."
        ),
    }



# ---- Meme 20d retirement clock (Phase 7) -----------------------------------

def meme_retirement_clock(
    bot: dict | None = None,
    *,
    window_days: int = MEME_RETIRE_WINDOW_DAYS,
    min_n: int = MEME_RETIRE_MIN_N,
    fill_tax: float = 0.01,
) -> dict:
    """Recommend pausing meme entries after window_days of negative taxed EV.

    Never auto-retires and never expands volume — staff must re-arm with a written fix.
    """
    bot = bot if isinstance(bot, dict) else {}
    hist = [h for h in (bot.get("history") or []) if isinstance(h, dict)]
    # Prefer last window_days by closed_at/when when parseable; else last min_n*3 settles.
    cutoff = None
    try:
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo
        cutoff = datetime.now(ZoneInfo("America/Chicago")) - timedelta(days=int(window_days))
    except Exception:
        cutoff = None

    def _row_day(row: dict):
        raw = str(row.get("closed_at") or row.get("when") or row.get("at") or "")[:10]
        if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
            try:
                from datetime import datetime
                from zoneinfo import ZoneInfo
                return datetime.strptime(raw[:10], "%Y-%m-%d").replace(
                    tzinfo=ZoneInfo("America/Chicago")
                )
            except Exception:
                return None
        return None

    windowed = []
    for h in hist:
        pnl = _finite(h.get("pnl") if h.get("pnl") is not None else h.get("pnl_usd"))
        if pnl is None:
            continue
        day = _row_day(h)
        if cutoff is not None and day is not None and day < cutoff:
            continue
        contracts = _finite(h.get("contracts")) or 1.0
        windowed.append(pnl - float(fill_tax) * max(1.0, contracts))
    if cutoff is not None and not any(_row_day(h) for h in hist):
        # No dates → use most recent settles as proxy for the window.
        windowed = []
        for h in hist[-(max(int(min_n) * 3, int(min_n))):]:
            pnl = _finite(h.get("pnl") if h.get("pnl") is not None else h.get("pnl_usd"))
            if pnl is None:
                continue
            contracts = _finite(h.get("contracts")) or 1.0
            windowed.append(pnl - float(fill_tax) * max(1.0, contracts))
    n = len(windowed)
    exp = round(sum(windowed) / n, 4) if n else None
    recommend_pause = bool(n >= int(min_n) and exp is not None and exp < 0)
    return {
        "paper_only": True,
        "bot": str(bot.get("id") or "memecoin"),
        "window_days": int(window_days),
        "min_n": int(min_n),
        "n": n,
        "expectancy_taxed": exp,
        "recommend_pause": recommend_pause,
        "retired": False,  # staff must confirm; never auto-retire
        "expand_volume": False,
        "action": "pause_entries" if recommend_pause else "keep_measuring",
        "fee_floors_locked": True,
        "note": (
            f"Meme retirement clock: after {window_days}d with n≥{min_n} and "
            "taxed EV < 0 → recommend pause_entries. Staff re-arm only. No volume expand."
        ),
    }


def firm_taxed_m1(bots: list | None = None, *, fill_tax: float = 0.01) -> dict:
    """Dollar-weighted firm taxed expectancy across tower histories (M1 proxy)."""
    pnls: list[float] = []
    by = []
    for bot in bots or []:
        if not isinstance(bot, dict):
            continue
        bot_id = str(bot.get("id") or "")
        local: list[float] = []
        for h in bot.get("history") or []:
            if not isinstance(h, dict):
                continue
            p = _finite(h.get("pnl") if h.get("pnl") is not None else h.get("pnl_usd"))
            if p is None:
                continue
            contracts = _finite(h.get("contracts")) or 1.0
            taxed = p - float(fill_tax) * max(1.0, contracts)
            local.append(taxed)
            pnls.append(taxed)
        if local:
            by.append({
                "bot": bot_id,
                "n": len(local),
                "expectancy_taxed": round(sum(local) / len(local), 4),
            })
    n = len(pnls)
    exp = round(sum(pnls) / n, 4) if n else None
    return {
        "paper_only": True,
        "n": n,
        "expectancy_taxed": exp,
        "by_tower": by,
        "fee_floors_locked": True,
        "note": "Firm M1 proxy = mean taxed PnL across all tower settles. No profit guarantee.",
    }


def evaluate_hillclimb_kill(weeks: list) -> dict:
    """Kill when the last two cards show M3 up and M1 down (fills up preferred)."""
    cards = [w for w in weeks if isinstance(w, dict)]
    cards = sorted(cards, key=lambda w: str(w.get("label") or ""))
    if len(cards) < HILLCLIMB_KILL_WEEKS:
        return {
            "kill": False,
            "action": "observe",
            "reason": f"need {HILLCLIMB_KILL_WEEKS} Chicago weeks of hillclimb cards",
            "weeks_n": len(cards),
            "auto_revert": False,
        }
    prev, cur = cards[-2], cards[-1]
    m1_prev = _finite(prev.get("m1"))
    m1_cur = _finite(cur.get("m1"))
    m3_prev = _finite(prev.get("m3"))
    m3_cur = _finite(cur.get("m3"))
    fills_prev = _finite(prev.get("fills_n")) or 0.0
    fills_cur = _finite(cur.get("fills_n")) or 0.0
    if None in (m1_prev, m1_cur, m3_prev, m3_cur):
        return {
            "kill": False,
            "action": "observe",
            "reason": "incomplete M1/M3 on recent weeks",
            "weeks_n": len(cards),
            "auto_revert": False,
        }
    m3_up = m3_cur > m3_prev + 1e-12
    m1_down = m1_cur < m1_prev - 1e-12
    fills_up = fills_cur >= fills_prev
    kill = bool(m3_up and m1_down and fills_up)
    return {
        "kill": kill,
        "action": "revert_lever" if kill else "keep",
        "reason": (
            "M3↑ with M1↓ over 2 Chicago weeks while fills not down — revert last lever"
            if kill
            else "no kill: need M3↑ and M1↓ with fills not down"
        ),
        "m1_prev": m1_prev,
        "m1_cur": m1_cur,
        "m3_prev": m3_prev,
        "m3_cur": m3_cur,
        "fills_prev": int(fills_prev),
        "fills_cur": int(fills_cur),
        "weeks_n": len(cards),
        "labels": [str(prev.get("label") or ""), str(cur.get("label") or "")],
        "lever": cur.get("lever") or prev.get("lever"),
        "auto_revert": False,  # flag only; staff/param thrash ban applies
        "fee_floors_locked": True,
    }


def capture_hillclimb_week(
    root: str | None,
    *,
    bots: list | None = None,
    label: str | None = None,
    lever: str | None = None,
    fill_tax: float = 0.01,
) -> dict:
    """Snapshot firm M1/M3/fills for the Chicago day and evaluate the kill rule."""
    day = label or _chicago_day()
    m1 = firm_taxed_m1(bots, fill_tax=fill_tax)
    m3 = fit_buy_rate(root)
    lever_name = str(lever).strip()[:80] if lever else None
    if not lever_name:
        active = active_hillclimb_lever(root)
        if active and str(active.get("lever") or ""):
            lever_name = str(active.get("lever"))[:80]
    card = {
        "paper_only": True,
        "label": day,
        "captured_at": _now(),
        "m1": m1.get("expectancy_taxed"),
        "m1_n": m1.get("n"),
        "m3": m3.get("rate"),
        "m3_n_fit": m3.get("n_fit"),
        "fills_n": m3.get("n_buy"),
        "lever": lever_name,
        "fee_floors_locked": True,
    }
    path = _path(HILLCLIMB_KILL, root)
    store = _load(path, {"paper_only": True, "weeks": [], "latest": None, "status": None})
    weeks = [w for w in (store.get("weeks") or []) if isinstance(w, dict)]
    weeks = [w for w in weeks if str(w.get("label") or "") != day]
    weeks.append(card)
    store["weeks"] = weeks[-52:]
    store["latest"] = card
    status = evaluate_hillclimb_kill(store["weeks"])
    store["status"] = status
    store["last_at"] = _now()
    _save(path, store)
    return {"card": card, "status": status}


def hillclimb_kill_status(root: str | None = None) -> dict:
    store = _load(
        _path(HILLCLIMB_KILL, root),
        {"paper_only": True, "weeks": [], "status": None},
    )
    status = store.get("status")
    if not isinstance(status, dict):
        status = evaluate_hillclimb_kill(
            [w for w in (store.get("weeks") or []) if isinstance(w, dict)]
        )
    return {
        "paper_only": True,
        "weeks_n": len([w for w in (store.get("weeks") or []) if isinstance(w, dict)]),
        "latest": store.get("latest") if isinstance(store.get("latest"), dict) else None,
        "status": status,
        "kill": bool(status.get("kill")),
        "action": status.get("action"),
        "auto_revert": False,
        "fee_floors_locked": True,
        "note": (
            "Hillclimb kill: if M3 rises while M1 falls for 2 Chicago weeks, "
            "revert the last lever before the next idea. Flag only — no auto param write."
        ),
    }


# ---- Hillclimb lever allowlist (Phase 11) ----------------------------------

def hillclimb_allowlist() -> dict:
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "levers": {
            k: dict(v, name=k) for k, v in HILLCLIMB_ALLOWLIST.items()
        },
        "none_lever": HILLCLIMB_NONE_LEVER,
        "note": (
            "One lever per Chicago week (or NONE). venue_min_edge_btc / min_cushion_btc "
            "are raise-only. Midweek thrash banned. Sunday packet review required (#901)."
        ),
    }


def hillclimb_lever_evidence_templates() -> dict:
    """E9 #903–922: evidence pack templates per allowlisted lever (observe only)."""
    templates = {}
    for name, meta in HILLCLIMB_ALLOWLIST.items():
        templates[name] = {
            "lever": name,
            "kind": meta.get("kind"),
            "raise_only": bool(meta.get("raise_only")),
            "success_metrics": meta.get("success_metrics") or _HILLCLIMB_SUCCESS,
            "kill_metrics": meta.get("kill_metrics") or _HILLCLIMB_KILL,
            "dry_run": dict(meta.get("dry_run") or _HILLCLIMB_DRY),
            "writes_venue_params": False,
            "applies_live": False,
            "note": meta.get("note"),
        }
    templates[HILLCLIMB_NONE_LEVER] = {
        "lever": HILLCLIMB_NONE_LEVER,
        "kind": "observe",
        "raise_only": False,
        "success_metrics": "Observation continues; no param change (#923)",
        "kill_metrics": "N/A — no lever active",
        "dry_run": {
            **_HILLCLIMB_DRY,
            "target": "none",
            "proposed": {"lever": "NONE", "observation_continues": True},
        },
        "writes_venue_params": False,
        "applies_live": False,
        "note": "Valid pick — document why observation continues.",
    }
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_apply": False,
        "templates": templates,
        "levers": sorted(HILLCLIMB_ALLOWLIST.keys()) + [HILLCLIMB_NONE_LEVER],
        "label": f"hillclimb evidence templates n={len(templates)}",
        "note": (
            "E9 evidence templates (#903–922) + NONE (#923). "
            "Dry-run is shadow/paper only — never writes venue params."
        ),
    }


def hillclimb_dry_run_board(lever: str | None = None) -> dict:
    """Dry-run config for one lever (or all) — shadow/paper only (#906+)."""
    templates = hillclimb_lever_evidence_templates()["templates"]
    name = str(lever or "").strip()
    if name:
        row = templates.get(name)
        if not row:
            return {
                "ok": False,
                "reason": f"unknown lever {name}",
                "allowlist": sorted(templates.keys()),
                "paper_only": True,
                "fee_floors_locked": True,
            }
        return {
            "ok": True,
            "paper_only": True,
            "fee_floors_locked": True,
            "observe_only": True,
            "auto_apply": False,
            "lever": name,
            "dry_run": row.get("dry_run"),
            "success_metrics": row.get("success_metrics"),
            "kill_metrics": row.get("kill_metrics"),
            "label": f"hillclimb dry-run {name} (shadow/paper · no param write)",
            "note": "Dry-run only — never applies LIVE or softens floors.",
        }
    return {
        "ok": True,
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_apply": False,
        "by_lever": {
            k: v.get("dry_run") for k, v in templates.items()
        },
        "label": "hillclimb dry-run board (all levers · shadow/paper)",
        "note": "Dry-run only — never applies LIVE or softens floors.",
    }


def sunday_packet_review_status(root: str | None = None) -> dict:
    """#901 — Chicago week Sunday packet review gate for new hillclimb levers."""
    week = _chicago_week_id()
    store = _load(
        _path(HILLCLIMB_RITUAL_NAME, root),
        {"paper_only": True, "reviews": {}, "latest": None},
    )
    reviews = store.get("reviews") if isinstance(store.get("reviews"), dict) else {}
    row = reviews.get(week) if isinstance(reviews.get(week), dict) else None
    reviewed = bool(row and row.get("reviewed"))
    packet_present = False
    try:
        from helpers.sunday_packet import packet_path
        packet_present = os.path.isfile(packet_path(root))
    except Exception:
        packet_present = False
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "week": week,
        "reviewed": reviewed,
        "packet_present": packet_present,
        "latest": row,
        "gate_ok": reviewed,
        "label": (
            f"sunday_review week={week} reviewed={reviewed} "
            f"packet={'yes' if packet_present else 'no'}"
        ),
        "note": (
            "No new hillclimb lever until Sunday packet reviewed this Chicago week (#901). "
            "NONE remains valid without review. force=True for tests only."
        ),
    }


def staff_mark_sunday_packet_reviewed(
    root: str | None,
    *,
    who: str = "",
    note: str = "",
) -> dict:
    """Staff marks Sunday packet reviewed for this Chicago week (#901)."""
    week = _chicago_week_id()
    path = _path(HILLCLIMB_RITUAL_NAME, root)
    store = _load(path, {"paper_only": True, "reviews": {}, "latest": None})
    reviews = store.get("reviews") if isinstance(store.get("reviews"), dict) else {}
    row = {
        "week": week,
        "reviewed": True,
        "at": _now(),
        "who": str(who or "")[:40],
        "note": str(note or "sunday packet reviewed")[:200],
        "paper_only": True,
        "fee_floors_locked": True,
        "auto_promote": False,
    }
    reviews[week] = row
    store["reviews"] = reviews
    store["latest"] = row
    store["paper_only"] = True
    store["fee_floors_locked"] = True
    _save(path, store)
    return {"ok": True, "row": row, "paper_only": True, "fee_floors_locked": True}


def active_hillclimb_lever(root: str | None = None) -> dict | None:
    store = _load(
        _path(HILLCLIMB_LEVER_NAME, root),
        {"paper_only": True, "active": None, "history": []},
    )
    active = store.get("active")
    return active if isinstance(active, dict) else None


def hillclimb_lever_status(root: str | None = None) -> dict:
    active = active_hillclimb_lever(root)
    kill = hillclimb_kill_status(root)
    week = _chicago_week_id()
    same_week = bool(active and str(active.get("week") or "") == week)
    needs_staff_pick = not same_week
    kill_flag = bool(kill.get("kill"))
    # Process ticket TC-151: observe Chicago weeks / staff hillclimb pick.
    # Agent cannot pick for staff — surface distance-to-action only.
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "process_only": True,  # TC-151 — staff must pick; no auto
        "ticket": "TC-151",
        "allowlist": sorted(HILLCLIMB_ALLOWLIST.keys()) + [HILLCLIMB_NONE_LEVER],
        "active": active,
        "week": week,
        "active_this_week": same_week,
        "needs_staff_pick": needs_staff_pick,
        "sunday_review": sunday_packet_review_status(root),
        "evidence_thin": needs_staff_pick or kill_flag,
        "kill": kill_flag,
        "kill_action": (kill.get("status") or {}).get("action") if isinstance(kill.get("status"), dict) else kill.get("action"),
        "auto_promote": False,
        "auto_revert": False,
        "label": (
            f"hillclimb week={week} "
            + (
                f"active={active.get('lever')} KILL"
                if kill_flag and active
                else (
                    f"active={active.get('lever')}"
                    if same_week and active
                    else "THIN — needs staff pick this Chicago week"
                )
            )
        ),
        "note": (
            "TC-151 process: staff picks one allowlisted lever per Chicago week. "
            "Kill flag → demote before next idea. No auto param write; floors locked. "
            "Agent observe-only — never auto-picks."
        ),
    }


def staff_pick_hillclimb_lever(
    root: str | None,
    lever: str,
    *,
    note: str = "",
    proposed_value=None,
    force: bool = False,
) -> dict:
    """Staff picks the single hillclimb lever for this Chicago week.

    #901: new non-NONE lever requires Sunday packet reviewed (unless force).
    #902/#923: NONE is a valid pick (observation continues).
    Midweek thrash banned unless force=True (tests) or demote first.
    Raise-only levers reject proposed_value below locked floor.
    Never writes venue params / never LIVE.
    """
    name = str(lever or "").strip()
    is_none = name.upper() == HILLCLIMB_NONE_LEVER
    if is_none:
        name = HILLCLIMB_NONE_LEVER
        meta = {
            "kind": "observe",
            "raise_only": False,
            "note": "NONE — observation continues (#923)",
        }
    else:
        meta = HILLCLIMB_ALLOWLIST.get(name)
    if not meta:
        return {
            "ok": False,
            "reason": f"lever not on allowlist: {name}",
            "allowlist": sorted(HILLCLIMB_ALLOWLIST.keys()) + [HILLCLIMB_NONE_LEVER],
            "auto_promote": False,
            "fee_floors_locked": True,
        }
    week = _chicago_week_id()
    if not is_none and not force:
        ritual = sunday_packet_review_status(root)
        if not ritual.get("reviewed"):
            return {
                "ok": False,
                "reason": (
                    "Sunday packet not reviewed this Chicago week (#901) — "
                    "mark reviewed or pick NONE"
                ),
                "sunday_review": ritual,
                "auto_promote": False,
                "fee_floors_locked": True,
            }
    path = _path(HILLCLIMB_LEVER_NAME, root)
    store = _load(path, {"paper_only": True, "active": None, "history": []})
    active = store.get("active") if isinstance(store.get("active"), dict) else None
    if (
        active
        and str(active.get("week") or "") == week
        and str(active.get("lever") or "") != name
        and not force
    ):
        return {
            "ok": False,
            "reason": (
                f"midweek thrash banned — active lever this week is "
                f"{active.get('lever')}; demote first or wait for next Chicago week"
            ),
            "active": active,
            "auto_promote": False,
            "fee_floors_locked": True,
        }
    proposed = _finite(proposed_value)
    if meta.get("raise_only") and proposed is not None:
        # Never record a soften below locked BTC floor / cushion habit.
        if name == "venue_min_edge_btc" and proposed + 1e-12 < 0.05:
            return {
                "ok": False,
                "reason": "venue_min_edge_btc raise-only: proposed < locked 0.05 floor",
                "auto_promote": False,
                "fee_floors_locked": True,
            }
        if name == "min_cushion_btc" and proposed + 1e-12 < 0:
            return {
                "ok": False,
                "reason": "min_cushion_btc raise-only: proposed must be ≥ 0",
                "auto_promote": False,
                "fee_floors_locked": True,
            }
    row = {
        "paper_only": True,
        "lever": name,
        "kind": meta.get("kind"),
        "raise_only": bool(meta.get("raise_only")),
        "proposed_value": proposed,
        "week": week,
        "at": _now(),
        "note": str(note or "")[:200] or str(meta.get("note") or "")[:200],
        "staff_approved": True,
        "observation_continues": bool(is_none),
        "auto_promote": False,
        "auto_apply": False,
        "fee_floors_locked": True,
        "writes_venue_params": False,
    }
    hist = [h for h in (store.get("history") or []) if isinstance(h, dict)]
    if active:
        hist.append({**active, "demoted_at": _now(), "demote_reason": "replaced"})
    hist.append(row)
    store["active"] = row
    store["history"] = hist[-52:]
    store["last_at"] = row["at"]
    store["paper_only"] = True
    _save(path, store)
    return {
        "ok": True,
        "active": row,
        "auto_promote": False,
        "auto_apply": False,
        "fee_floors_locked": True,
        "reason": (
            f"picked NONE for {week} — observation continues"
            if is_none
            else f"picked {name} for {week}"
        ),
    }


def staff_clear_hillclimb_lever(
    root: str | None,
    *,
    who: str = "",
    note: str = "",
) -> dict:
    """Demote/clear the active hillclimb lever (paper hygiene). No param write."""
    path = _path(HILLCLIMB_LEVER_NAME, root)
    store = _load(path, {"paper_only": True, "active": None, "history": []})
    active = store.get("active") if isinstance(store.get("active"), dict) else None
    hist = [h for h in (store.get("history") or []) if isinstance(h, dict)]
    if active:
        hist.append({
            **active,
            "demoted_at": _now(),
            "demote_reason": str(note or "staff clear")[:120],
            "demoted_by": str(who or "")[:80],
        })
    store["active"] = None
    store["history"] = hist[-52:]
    store["last_at"] = _now()
    store["paper_only"] = True
    store["fee_floors_locked"] = True
    _save(path, store)
    return {
        "ok": True,
        "cleared": bool(active),
        "was": active,
        "status": hillclimb_lever_status(root),
        "auto_promote": False,
        "fee_floors_locked": True,
        "live_orders_enabled": False,
    }


# ---- E9 #924–931: activate / broadcast / daily / kill postmortem / win lock -

def hillclimb_lever_activation_board(root: str | None = None) -> dict:
    """#924 — assert desk_hillclimb_lever.json has at most one active entry."""
    store = _load(
        _path(HILLCLIMB_LEVER_NAME, root),
        {"paper_only": True, "active": None, "history": []},
    )
    active = store.get("active") if isinstance(store.get("active"), dict) else None
    hist = [h for h in (store.get("history") or []) if isinstance(h, dict)]
    # Guard: refuse silently-stacked actives if a buggy writer ever set a list.
    raw_active = store.get("active")
    stacked = isinstance(raw_active, list)
    n_active = 1 if active and not stacked else (len(raw_active) if stacked else 0)
    ok = (not stacked) and n_active <= 1
    lever = str(active.get("lever") or "") if active else None
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_apply": False,
        "writes_venue_params": False,
        "ok": ok,
        "pass": ok,
        "single_entry": bool(ok and n_active <= 1),
        "activated": bool(active),
        "n_active": n_active,
        "lever": lever,
        "week": (active or {}).get("week") if active else None,
        "history_n": len(hist),
        "label": (
            f"hillclimb_activation ok={ok} lever={lever or 'none'} "
            f"single={ok} (#924)"
        ),
        "note": (
            "Activation is the single active row in desk_hillclimb_lever.json. "
            "Never writes venue params. Never LIVE."
        ),
    }


def hillclimb_lever_masters_broadcast(root: str | None = None) -> dict:
    """#925 — Masters soft_copy for the active lever (staff paste · never auto-post)."""
    status = hillclimb_lever_status(root)
    active = status.get("active") if isinstance(status.get("active"), dict) else None
    kill = bool(status.get("kill"))
    week = status.get("week")
    lever = str((active or {}).get("lever") or "none")
    soft = (
        f"**Hillclimb lever** (paper · floors locked · live=False)\n"
        f"week={week} active={lever} kill={kill} "
        f"sunday_reviewed={(status.get('sunday_review') or {}).get('reviewed')}\n"
        f"{status.get('label') or 'hillclimb observe'}\n"
        f"_staff paste only · never auto-posts · never auto-applies_"
    )
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_publish": False,
        "auto_apply": False,
        "live_orders_enabled": False,
        "week": week,
        "lever": lever if active else None,
        "kill": kill,
        "soft_copy": soft,
        "discord": soft,
        "label": f"hillclimb_broadcast week={week} lever={lever} (#925)",
        "note": "Masters broadcast — observe/paste only; never auto-posts Discord.",
    }


def hillclimb_lever_daily_check(
    root: str | None = None,
    *,
    bots: list | None = None,
) -> dict:
    """#926/#927 — daily M1/M3/fills during lever week + week-2 kill surface."""
    week = _chicago_week_id()
    active = active_hillclimb_lever(root)
    kill = hillclimb_kill_status(root)
    latest = kill.get("latest") if isinstance(kill.get("latest"), dict) else None
    # Prefer live bots snapshot when provided; else last captured card.
    m1 = None
    m3 = None
    fills_n = None
    if bots is not None:
        try:
            snap = capture_hillclimb_week(root, bots=bots, label=_chicago_day())
            card = snap.get("card") if isinstance(snap, dict) else None
            if isinstance(card, dict):
                latest = card
        except Exception:
            pass
    if isinstance(latest, dict):
        m1 = latest.get("m1")
        m3 = latest.get("m3")
        fills_n = latest.get("fills_n")
    weeks = []
    try:
        store = _load(
            _path(HILLCLIMB_KILL, root),
            {"paper_only": True, "weeks": []},
        )
        weeks = [w for w in (store.get("weeks") or []) if isinstance(w, dict)]
    except Exception:
        weeks = []
    # Cards attributed to current active lever (same Chicago week id on active).
    lever = str((active or {}).get("lever") or "") if active else ""
    lever_cards = [
        w for w in weeks
        if str(w.get("lever") or "") == lever and lever
    ]
    week2_ready = len(lever_cards) >= HILLCLIMB_KILL_WEEKS or bool(kill.get("kill"))
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_apply": False,
        "auto_revert": False,
        "week": week,
        "lever": lever or None,
        "active": bool(active),
        "m1": m1,
        "m3": m3,
        "fills_n": fills_n,
        "lever_cards_n": len(lever_cards),
        "kill": bool(kill.get("kill")),
        "kill_action": kill.get("action"),
        "week2_check_ready": week2_ready,
        "latest_card": latest,
        "label": (
            f"hillclimb_daily week={week} lever={lever or 'none'} "
            f"m1={m1} m3={m3} fills={fills_n} kill={bool(kill.get('kill'))} "
            f"(#926/#927)"
        ),
        "note": (
            "Daily lever health during the Chicago week. Week-2 kill via "
            "evaluate_hillclimb_kill — flag only, never auto-reverts."
        ),
    }


def hillclimb_one_lever_discipline(root: str | None = None) -> dict:
    """#930/#931 — never stack two allowlist levers; never invent off-allowlist."""
    activation = hillclimb_lever_activation_board(root)
    active = active_hillclimb_lever(root)
    lever = str((active or {}).get("lever") or "") if active else ""
    off = bool(
        lever
        and lever != HILLCLIMB_NONE_LEVER
        and lever not in HILLCLIMB_ALLOWLIST
    )
    ok = bool(activation.get("ok")) and not off
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "ok": ok,
        "pass": ok,
        "single_entry": bool(activation.get("single_entry")),
        "off_allowlist": off,
        "lever": lever or None,
        "allowlist": sorted(HILLCLIMB_ALLOWLIST.keys()) + [HILLCLIMB_NONE_LEVER],
        "label": (
            f"hillclimb_discipline ok={ok} single={activation.get('single_entry')} "
            f"off_allowlist={off} (#930/#931)"
        ),
        "note": (
            "One allowlisted lever (or NONE) per Chicago week. "
            "Off-allowlist invent forbidden without plan amend."
        ),
    }


def staff_hillclimb_kill_postmortem(
    root: str | None,
    *,
    who: str = "",
    note: str = "",
    demote: bool = True,
) -> dict:
    """#928 — on kill flag: staff revert same day + write postmortem journal.

    Never auto-reverts params. Floors locked. LIVE off.
    """
    kill = hillclimb_kill_status(root)
    if not kill.get("kill") and not note:
        return {
            "ok": False,
            "reason": "no kill flag — refuse empty postmortem",
            "paper_only": True,
            "fee_floors_locked": True,
            "auto_revert": False,
        }
    active = active_hillclimb_lever(root)
    demoted = None
    if demote and active:
        dem = staff_demote_hillclimb_lever(
            root,
            note=note or "kill postmortem",
            reason="kill_rule_revert",
        )
        demoted = dem.get("demoted")
    path = _path(HILLCLIMB_POSTMORTEM_NAME, root)
    store = _load(
        path,
        {"paper_only": True, "rows": [], "fee_floors_locked": True},
    )
    row = {
        "at": _now(),
        "week": _chicago_week_id(),
        "who": str(who or "")[:40],
        "lever": str((active or {}).get("lever") or demoted or ""),
        "kill": bool(kill.get("kill")),
        "kill_action": kill.get("action"),
        "kill_reason": (kill.get("status") or {}).get("reason")
        if isinstance(kill.get("status"), dict)
        else kill.get("reason"),
        "note": str(note or "kill postmortem — reverted")[:240],
        "demoted": demoted,
        "paper_only": True,
        "fee_floors_locked": True,
        "auto_revert": False,
        "auto_apply": False,
    }
    rows = [r for r in (store.get("rows") or []) if isinstance(r, dict)]
    rows.append(row)
    store["rows"] = rows[-MAX_HILLCLIMB_POSTMORTEM:]
    store["latest"] = row
    store["paper_only"] = True
    store["fee_floors_locked"] = True
    _save(path, store)
    return {
        "ok": True,
        "row": row,
        "n": len(store["rows"]),
        "paper_only": True,
        "fee_floors_locked": True,
        "auto_revert": False,
    }


def hillclimb_postmortem_board(root: str | None = None) -> dict:
    """Observe board for kill postmortems (#928)."""
    store = _load(
        _path(HILLCLIMB_POSTMORTEM_NAME, root),
        {"paper_only": True, "rows": []},
    )
    rows = [r for r in (store.get("rows") or []) if isinstance(r, dict)]
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "n": len(rows),
        "latest": store.get("latest") if isinstance(store.get("latest"), dict) else (
            rows[-1] if rows else None
        ),
        "recent": rows[-8:],
        "label": f"hillclimb_postmortem n={len(rows)} (#928)",
        "note": "Kill postmortems — staff revert same day; never auto-reverts params.",
    }


def staff_hillclimb_lock_win(
    root: str | None,
    *,
    who: str = "",
    note: str = "",
    lever: str = "",
) -> dict:
    """#929 — lock a successful lever week with an observe journal (no param write).

    Still one-lever discipline — does not stack or auto-apply.
    """
    active = active_hillclimb_lever(root)
    name = str(lever or (active or {}).get("lever") or "").strip()
    if not name:
        return {
            "ok": False,
            "reason": "lever required",
            "paper_only": True,
            "fee_floors_locked": True,
        }
    if name != HILLCLIMB_NONE_LEVER and name not in HILLCLIMB_ALLOWLIST:
        return {
            "ok": False,
            "reason": f"off-allowlist invent forbidden: {name}",
            "paper_only": True,
            "fee_floors_locked": True,
        }
    path = _path(HILLCLIMB_WIN_LOCK_NAME, root)
    store = _load(
        path,
        {"paper_only": True, "rows": [], "fee_floors_locked": True},
    )
    row = {
        "at": _now(),
        "week": _chicago_week_id(),
        "who": str(who or "")[:40],
        "lever": name[:64],
        "note": str(note or "lock win — one lever discipline")[:240],
        "paper_only": True,
        "fee_floors_locked": True,
        "auto_apply": False,
        "one_lever_discipline": True,
    }
    rows = [r for r in (store.get("rows") or []) if isinstance(r, dict)]
    rows.append(row)
    store["rows"] = rows[-MAX_HILLCLIMB_WIN_LOCK:]
    store["latest"] = row
    store["paper_only"] = True
    store["fee_floors_locked"] = True
    _save(path, store)
    return {
        "ok": True,
        "row": row,
        "n": len(store["rows"]),
        "paper_only": True,
        "fee_floors_locked": True,
        "auto_apply": False,
    }


def hillclimb_win_lock_board(root: str | None = None) -> dict:
    """Observe board for locked lever wins (#929)."""
    store = _load(
        _path(HILLCLIMB_WIN_LOCK_NAME, root),
        {"paper_only": True, "rows": []},
    )
    rows = [r for r in (store.get("rows") or []) if isinstance(r, dict)]
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_apply": False,
        "n": len(rows),
        "latest": store.get("latest") if isinstance(store.get("latest"), dict) else (
            rows[-1] if rows else None
        ),
        "recent": rows[-8:],
        "label": f"hillclimb_win_lock n={len(rows)} (#929)",
        "note": "Win locks are journal-only — still one lever/week; never auto-applies.",
    }


def hillclimb_e9_week_board(
    root: str | None = None,
    *,
    bots: list | None = None,
) -> dict:
    """Combined E9 #924–931 observe board."""
    activation = hillclimb_lever_activation_board(root)
    broadcast = hillclimb_lever_masters_broadcast(root)
    daily = hillclimb_lever_daily_check(root, bots=bots)
    discipline = hillclimb_one_lever_discipline(root)
    post = hillclimb_postmortem_board(root)
    wins = hillclimb_win_lock_board(root)
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_apply": False,
        "auto_revert": False,
        "live_orders_enabled": False,
        "activation": activation,
        "broadcast": broadcast,
        "daily": daily,
        "discipline": discipline,
        "postmortem": post,
        "win_lock": wins,
        "soft_copy": broadcast.get("soft_copy"),
        "label": (
            f"e9_week act={activation.get('lever')} "
            f"daily_kill={daily.get('kill')} disc={discipline.get('ok')}"
        ),
        "note": (
            "E9 lever-week pack (#924–931): single activation, Masters broadcast, "
            "daily M1/M3/fills, kill postmortem, win lock, one-lever discipline."
        ),
    }


def dual_control_status(root: str | None = None) -> dict:
    """Paper dual-control checklist. Live orders stay hard-disabled."""
    store = _load(
        _path(DUAL_CONTROL_NAME, root),
        {
            "paper_only": True,
            "items": {},
            "primary": None,
            "secondary": None,
            "live_orders_enabled": False,
        },
    )
    items_state = store.get("items") if isinstance(store.get("items"), dict) else {}
    items = []
    signed_n = 0
    for item_id, label in DUAL_CONTROL_ITEMS:
        row = items_state.get(item_id) if isinstance(items_state.get(item_id), dict) else {}
        ok = bool(row.get("signed"))
        if ok:
            signed_n += 1
        items.append({
            "id": item_id,
            "label": label,
            "signed": ok,
            "who": row.get("who") or "",
            "at": row.get("at"),
        })
    primary = store.get("primary") if isinstance(store.get("primary"), dict) else None
    secondary = store.get("secondary") if isinstance(store.get("secondary"), dict) else None
    two_staff = bool(primary and secondary and primary.get("who") and secondary.get("who")
                     and str(primary.get("who")) != str(secondary.get("who")))
    checklist_complete = signed_n >= len(DUAL_CONTROL_ITEMS)
    # Even if complete + dual signed, live stays False in this stub.
    arm_ready_paper = checklist_complete and two_staff
    return {
        "paper_only": True,
        "live_orders_enabled": bool(LIVE_ORDERS_ENABLED),
        "code_live_lock": True,
        "items": items,
        "signed_n": signed_n,
        "items_n": len(DUAL_CONTROL_ITEMS),
        "checklist_complete": checklist_complete,
        "primary": primary,
        "secondary": secondary,
        "two_staff": two_staff,
        "arm_ready_paper": arm_ready_paper,
        "auto_promote": False,
        "fee_floors_locked": True,
        "note": (
            "Dual-control stub: both staff + full checklist required before any "
            "future live path. LIVE_ORDERS_ENABLED stays False in code."
        ),
    }


def staff_sign_dual_control(
    root: str | None,
    *,
    who: str,
    role: str = "primary",
    item_id: str | None = None,
    note: str = "",
) -> dict:
    """Sign one checklist item and/or a dual-control role. Never enables live."""
    who_s = str(who or "").strip()
    if not who_s:
        return {"ok": False, "reason": "who required", "live_orders_enabled": False}
    role_s = str(role or "primary").strip().lower()
    if role_s not in ("primary", "secondary"):
        return {"ok": False, "reason": "role must be primary or secondary", "live_orders_enabled": False}
    path = _path(DUAL_CONTROL_NAME, root)
    store = _load(
        path,
        {
            "paper_only": True,
            "items": {},
            "primary": None,
            "secondary": None,
            "live_orders_enabled": False,
        },
    )
    items = store.get("items") if isinstance(store.get("items"), dict) else {}
    if item_id:
        iid = str(item_id).strip()
        known = {k for k, _ in DUAL_CONTROL_ITEMS}
        if iid not in known:
            return {
                "ok": False,
                "reason": f"unknown checklist item: {iid}",
                "live_orders_enabled": False,
            }
        items[iid] = {
            "signed": True,
            "who": who_s[:80],
            "at": _now(),
            "note": str(note or "")[:160],
        }
        store["items"] = items
    store[role_s] = {
        "who": who_s[:80],
        "at": _now(),
        "note": str(note or "")[:160],
    }
    store["live_orders_enabled"] = False  # hard lock
    store["paper_only"] = True
    store["last_at"] = _now()
    _save(path, store)
    status = dual_control_status(root)
    return {
        "ok": True,
        "status": status,
        "live_orders_enabled": False,
        "auto_promote": False,
        "fee_floors_locked": True,
    }


def staff_clear_dual_control(root: str | None, *, who: str = "", note: str = "") -> dict:
    """Reset dual-control signatures (paper hygiene)."""
    path = _path(DUAL_CONTROL_NAME, root)
    store = {
        "paper_only": True,
        "items": {},
        "primary": None,
        "secondary": None,
        "live_orders_enabled": False,
        "cleared_by": str(who or "")[:80],
        "cleared_note": str(note or "")[:160],
        "cleared_at": _now(),
        "fee_floors_locked": True,
    }
    _save(path, store)
    return {"ok": True, "status": dual_control_status(root), "live_orders_enabled": False}


def capture_quarterly_rebaseline(
    root: str | None,
    *,
    bots: list | None = None,
    cfg: dict | None = None,
    label: str | None = None,
) -> dict:
    """Quarterly W-number re-baseline habit (never mythologize a lucky week)."""
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("America/Chicago"))
        q = (now.month - 1) // 3 + 1
        default_label = f"W-{now.year}-Q{q}"
    except Exception:
        default_label = f"W-{time.strftime('%Y')}-Q?"
    tag = str(label or default_label)[:40]
    artifact = capture_baseline(root, bots=bots, cfg=cfg, label=tag)
    artifact["quarterly"] = True
    artifact["fee_floors_locked"] = True
    artifact["note"] = (
        f"Quarterly re-baseline {tag}. Compare future weeks to this artifact — "
        "do not mythologize a lucky week."
    )
    # Also stamp into baseline store meta.
    path = _path(BASELINE_NAME, root)
    store = load_baseline(root)
    store["quarterly_latest"] = artifact
    store["last_quarterly_at"] = _now()
    _save(path, store)
    return artifact


def quarterly_rebaseline_status(root: str | None = None) -> dict:
    store = load_baseline(root)
    latest = store.get("quarterly_latest") if isinstance(store.get("quarterly_latest"), dict) else None
    return {
        "paper_only": True,
        "latest": latest,
        "has_quarterly": latest is not None,
        "fee_floors_locked": True,
        "note": "Quarterly W-number re-baseline habit. Fee floors locked.",
    }


def staff_demote_hillclimb_lever(
    root: str | None,
    *,
    note: str = "",
    reason: str = "staff demote",
) -> dict:
    """Clear the active lever (Sunday demote / kill-rule follow-through)."""
    path = _path(HILLCLIMB_LEVER_NAME, root)
    store = _load(path, {"paper_only": True, "active": None, "history": []})
    active = store.get("active") if isinstance(store.get("active"), dict) else None
    if not active:
        return {
            "ok": True,
            "active": None,
            "reason": "no active lever",
            "auto_promote": False,
            "fee_floors_locked": True,
        }
    hist = [h for h in (store.get("history") or []) if isinstance(h, dict)]
    hist.append({
        **active,
        "demoted_at": _now(),
        "demote_reason": str(reason or "staff demote")[:120],
        "demote_note": str(note or "")[:200],
    })
    store["active"] = None
    store["history"] = hist[-52:]
    store["last_at"] = _now()
    _save(path, store)
    return {
        "ok": True,
        "active": None,
        "demoted": active.get("lever"),
        "reason": "demoted",
        "auto_promote": False,
        "fee_floors_locked": True,
    }


# ---- Profit-lock harvest (Phase 10 paper analog) ---------------------------

def _chicago_week_id(day: str | None = None) -> str:
    """ISO week id in America/Chicago (YYYY-Www)."""
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        if day:
            now = datetime.strptime(str(day)[:10], "%Y-%m-%d").replace(
                tzinfo=ZoneInfo("America/Chicago")
            )
        else:
            now = datetime.now(ZoneInfo("America/Chicago"))
        iso = now.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    except Exception:
        return time.strftime("%Y-W%W", time.gmtime())


def firm_today_pnl(bots: list | None = None) -> dict:
    total = 0.0
    n = 0
    by = []
    for bot in bots or []:
        if not isinstance(bot, dict):
            continue
        today = _finite(bot.get("today"))
        if today is None:
            continue
        bot_id = str(bot.get("id") or "")
        total += today
        n += 1
        by.append({"bot": bot_id, "today": round(today, 2)})
    return {
        "paper_only": True,
        "firm_today": round(total, 2),
        "towers_n": n,
        "by_tower": by,
    }


def capture_profit_lock(
    root: str | None,
    *,
    bots: list | None = None,
    label: str | None = None,
    target_usd: float = PROFIT_LOCK_TARGET_USD,
) -> dict:
    """Accumulate Chicago-week firm today PnL; lock to 0.5× size after target."""
    day = label or _chicago_day()
    week_id = _chicago_week_id(day)
    snap = firm_today_pnl(bots)
    path = _path(PROFIT_LOCK, root)
    store = _load(
        path,
        {
            "paper_only": True,
            "weeks": {},
            "latest": None,
            "target_usd": float(target_usd),
        },
    )
    weeks = store.get("weeks") if isinstance(store.get("weeks"), dict) else {}
    week = weeks.get(week_id) if isinstance(weeks.get(week_id), dict) else {
        "week": week_id, "days": {}, "locked": False,
    }
    days = week.get("days") if isinstance(week.get("days"), dict) else {}
    days[day] = {
        "firm_today": snap.get("firm_today"),
        "captured_at": _now(),
        "by_tower": snap.get("by_tower"),
    }
    week_pnl = round(
        sum(
            float(v.get("firm_today") or 0)
            for v in days.values()
            if isinstance(v, dict)
        ),
        2,
    )
    target = float(target_usd)
    locked = week_pnl + 1e-12 >= target
    status = {
        "paper_only": True,
        "week": week_id,
        "label": day,
        "week_pnl": week_pnl,
        "target_usd": target,
        "days_n": len(days),
        "safe_mode": locked,
        "size_mult": PROFIT_LOCK_SIZE_MULT if locked else 1.0,
        "harvest_pct": 50 if locked else 0,
        "fee_floors_locked": True,
        "note": (
            f"Profit-lock harvest: Chicago week PnL ≥ ${target:.0f} → "
            f"{PROFIT_LOCK_SIZE_MULT}× size (paper safe-mode). Habit for live."
        ),
    }
    week["days"] = days
    week["week_pnl"] = week_pnl
    week["locked"] = locked
    week["status"] = status
    weeks[week_id] = week
    # Keep last ~12 weeks.
    if len(weeks) > 12:
        for old in sorted(weeks.keys())[:-12]:
            weeks.pop(old, None)
    store["weeks"] = weeks
    store["latest"] = status
    store["target_usd"] = target
    store["last_at"] = _now()
    _save(path, store)
    return status


def profit_lock_status(root: str | None = None) -> dict:
    store = _load(
        _path(PROFIT_LOCK, root),
        {"paper_only": True, "latest": None, "target_usd": PROFIT_LOCK_TARGET_USD},
    )
    latest = store.get("latest") if isinstance(store.get("latest"), dict) else None
    if latest is None:
        latest = {
            "paper_only": True,
            "week": _chicago_week_id(),
            "week_pnl": 0.0,
            "target_usd": float(store.get("target_usd") or PROFIT_LOCK_TARGET_USD),
            "safe_mode": False,
            "size_mult": 1.0,
            "harvest_pct": 0,
            "fee_floors_locked": True,
            "note": "No profit-lock capture yet this Chicago week.",
        }
    return {
        "paper_only": True,
        "latest": latest,
        "safe_mode": bool(latest.get("safe_mode")),
        "size_mult": float(latest.get("size_mult") or 1.0),
        "week_pnl": latest.get("week_pnl"),
        "target_usd": latest.get("target_usd"),
        "fee_floors_locked": True,
        "note": latest.get("note"),
    }


def profit_lock_size_mult(root: str | None = None) -> float:
    """Stake multiplier for bots: 0.5 in safe-mode after weekly target, else 1.0."""
    status = profit_lock_status(root)
    mult = _finite(status.get("size_mult"))
    if mult is None or mult <= 0:
        return 1.0
    return float(mult)


def _clamp_harvest_pct(pct) -> float:
    p = _finite(pct)
    if p is None:
        return float(COLD_HARVEST_PCT_DEFAULT)
    return max(float(COLD_HARVEST_PCT_MIN), min(float(COLD_HARVEST_PCT_MAX), float(p)))


def capture_cold_harvest(
    root: str | None,
    *,
    bots: list | None = None,
    label: str | None = None,
    pct: float = COLD_HARVEST_PCT_DEFAULT,
) -> dict:
    """Move 30–50% of positive Chicago-week firm PnL into a cold ledger (paper habit).

    Idempotent per week: re-capture refreshes that week's harvest from current week_pnl.
    Does not change stake sizing (profit-lock owns 0.5×). Fee floors untouched.
    """
    day = label or _chicago_day()
    week_id = _chicago_week_id(day)
    # When bots are provided, refresh profit-lock week first so harvest tracks live
    # green (same-day stale week_pnl must not lag Masters bleed_week — #486 twin).
    if bots:
        try:
            capture_profit_lock(root, bots=bots, label=day)
        except Exception:
            pass
    # Prefer profit-lock week accumulator when present; else firm today as thin proxy.
    pl_store = _load(
        _path(PROFIT_LOCK, root),
        {"paper_only": True, "weeks": {}, "latest": None},
    )
    weeks_pl = pl_store.get("weeks") if isinstance(pl_store.get("weeks"), dict) else {}
    week_row = weeks_pl.get(week_id) if isinstance(weeks_pl.get(week_id), dict) else {}
    week_pnl = _finite(week_row.get("week_pnl"))
    if week_pnl is None and not bots:
        try:
            capture_profit_lock(root, bots=bots, label=day)
            pl_store = _load(
                _path(PROFIT_LOCK, root),
                {"paper_only": True, "weeks": {}, "latest": None},
            )
            weeks_pl = pl_store.get("weeks") if isinstance(pl_store.get("weeks"), dict) else {}
            week_row = weeks_pl.get(week_id) if isinstance(weeks_pl.get(week_id), dict) else {}
            week_pnl = _finite(week_row.get("week_pnl"))
        except Exception:
            week_pnl = None
    if week_pnl is None:
        week_pnl = float(firm_today_pnl(bots).get("firm_today") or 0.0)
    harvest_pct = _clamp_harvest_pct(pct)
    harvested = 0.0
    if float(week_pnl) > 1e-12:
        harvested = round(float(week_pnl) * harvest_pct, 2)
    path = _path(COLD_HARVEST_NAME, root)
    store = _load(
        path,
        {"paper_only": True, "weeks": {}, "cold_total": 0.0, "latest": None},
    )
    weeks = store.get("weeks") if isinstance(store.get("weeks"), dict) else {}
    row = {
        "paper_only": True,
        "week": week_id,
        "label": day,
        "week_pnl": round(float(week_pnl), 2),
        "harvest_pct": harvest_pct,
        "harvested": harvested,
        "skipped": harvested <= 0,
        "at": _now(),
        "fee_floors_locked": True,
        "note": (
            f"Cold harvest {harvest_pct:.0%} of week ${float(week_pnl):.2f} → "
            f"${harvested:.2f} cold (paper habit for live)."
            if harvested > 0
            else "No cold harvest — week PnL ≤ 0."
        ),
    }
    weeks[week_id] = row
    if len(weeks) > 26:
        for old in sorted(weeks.keys())[:-26]:
            weeks.pop(old, None)
    cold_total = round(
        sum(
            float(v.get("harvested") or 0)
            for v in weeks.values()
            if isinstance(v, dict)
        ),
        2,
    )
    store["weeks"] = weeks
    store["cold_total"] = cold_total
    store["latest"] = row
    store["last_at"] = _now()
    store["paper_only"] = True
    store["fee_floors_locked"] = True
    _save(path, store)
    return {
        **row,
        "cold_total": cold_total,
    }


def cold_harvest_status(root: str | None = None) -> dict:
    store = _load(
        _path(COLD_HARVEST_NAME, root),
        {"paper_only": True, "weeks": {}, "cold_total": 0.0, "latest": None},
    )
    latest = store.get("latest") if isinstance(store.get("latest"), dict) else None
    return {
        "paper_only": True,
        "cold_total": round(float(store.get("cold_total") or 0), 2),
        "latest": latest,
        "weeks_n": len(store.get("weeks") or {}),
        "pct_band": [COLD_HARVEST_PCT_MIN, COLD_HARVEST_PCT_MAX],
        "default_pct": COLD_HARVEST_PCT_DEFAULT,
        "fee_floors_locked": True,
        "note": (
            "Weekly harvest 30–50% of green Chicago-week firm PnL into cold ledger. "
            "Habit for live. Does not soften fee floors."
        ),
    }


def capture_weekly_scorecard(
    root: str | None,
    *,
    bots: list | None = None,
    cfg: dict | None = None,
    label: str | None = None,
) -> dict:
    """Persist a Chicago-week firm scorecard (bleed, M1 proxy, Gate A counts)."""
    cfg = cfg or {}
    bots = _bots_with_sports_history(root, bots)
    bleed = firm_bleed_ratio(bots)
    misplaced = capital_misplaced(bots, cfg)
    m1 = firm_taxed_m1(bots)
    sports_row = next(
        (r for r in (m1.get("by_tower") or []) if r.get("bot") == "sports-gap"),
        None,
    )
    sports_today = None
    for bot in bots or []:
        if isinstance(bot, dict) and bot.get("id") == "sports-gap":
            sports_today = _finite(bot.get("today"))
            break
    gate_a_n = 0
    for bot in bots or []:
        if isinstance(bot, dict) and isinstance(bot.get("gate_a"), dict) and bot["gate_a"].get("ready"):
            gate_a_n += 1
    card = {
        "paper_only": True,
        "label": label or _now()[:10],
        "captured_at": _now(),
        "bleed": bleed,
        "capital_misplaced": misplaced,
        "m1": m1.get("expectancy_taxed"),
        "sports_m1": (sports_row or {}).get("expectancy_taxed"),
        "sports_m1_n": (sports_row or {}).get("n"),
        "sports_today": sports_today,
        "gate_a_ready_towers": gate_a_n,
        "fee_floors_locked": True,
        "note": "Weekly scorecard for hillclimb kill rule. No profit guarantee.",
    }
    path = _path(WEEKLY_SCORECARD, root)
    store = _load(path, {"paper_only": True, "cards": []})
    # Upsert by label — master/densify refresh same Chicago day in place.
    # Appending clones made green_boost count one day as multiple weeks.
    existing = [c for c in (store.get("cards") or []) if isinstance(c, dict)]
    store["cards"] = _weekly_scorecard_upsert_cards(existing, card)
    store["latest"] = card
    store["paper_only"] = True
    _save(path, store)
    return card


# ---- Plan summary for master board -----------------------------------------

def plan_summary(
    root: str | None = None,
    *,
    bots: list | None = None,
    cfg: dict | None = None,
) -> dict:
    bleed = firm_bleed_ratio(bots)
    misplaced = capital_misplaced(bots, cfg)
    baseline = load_baseline(root).get("latest")
    sticky = None
    try:
        import desk_more
        sticky = desk_more.sticky_sla_status(bots)
    except Exception:
        sticky = {
            "paper_only": True,
            "fee_floors_locked": True,
            "sticky_count": 0,
            "observe_only": True,
        }
    return {
        "paper_only": True,
        "version": 2,
        "bleed": bleed,
        "capital_misplaced": misplaced,
        "baseline": baseline,
        "clv_completeness": clv_completeness(root),
        "near_miss_weekly": near_miss_weekly_card(root) if root is not None else {
            "n": 0, "decision": "reject", "auto_promote": False,
        },
        "sports_hard_stop_shadow": sports_hard_stop_shadow_summary(root),
        "commodity_time_stop": commodity_time_stop_shadow_summary(root),
        "sports_time_final": sports_time_final_shadow_summary(root),
        "phase3_exits": phase3_exit_gate(root, bots=bots),
        "phase4_calib": phase4_calib_gate(root, bots=bots),
        "phase5_throughput": phase5_throughput_gate(root, bots=bots),
        "phase6_graduation": phase6_graduation_gate(root, bots=bots),
        "phase7_portfolio": phase7_portfolio_gate(root, bots=bots, cfg=cfg),
        "phase8_helpers": phase8_helpers_gate(root, bots=bots),
        "phase10_ruin": phase10_ruin_gate(root, bots=bots),
        "phase11_hillclimb": phase11_hillclimb_gate(root, bots=bots),
        "weekly_scorecard": latest_weekly_scorecard(root),
        "graduation": graduation_board(root, bots=bots),
        # Prefer live bots whenever provided (#488 profit_lock twin).
        "hillclimb_kill": (
            hillclimb_kill_status(root)
            if not (root and bots)
            else (
                capture_hillclimb_week(root, bots=bots),
                hillclimb_kill_status(root),
            )[1]
        ),
        # Prefer live bots whenever provided (#487 cold_harvest twin).
        "profit_lock": (
            capture_profit_lock(root, bots=bots)
            if (root and bots)
            else profit_lock_status(root)
        ),
        # Prefer live journal whenever root is present (#494 Masters twin).
        "skip_regret_weekly": (
            skip_regret_weekly_card(root)
            if root
            else latest_skip_regret_weekly(root)
        ),
        # Prefer live bots.today when provided (#484 firm_health twin).
        "daily_r": (
            capture_daily_r_board(root, bots=bots)
            if (root and bots)
            else latest_daily_r_board(root)
        ),
        "inx_band_promote": inx_band_promote_status(root),
        "incubation": incubation_board(root),
        "ruin_drill": ruin_drill_status(root),
        "fee_ledger": fee_ledger_summary(root),
        "fee_ledger_completeness": fee_ledger_completeness(root, bots=bots),
        "stale_world": stale_world_status(root, bots=bots),
        "helper_gate_a": helper_promote_status(root),
        # Prefer live bots whenever provided (#486 Masters twin).
        "cold_harvest": (
            capture_cold_harvest(root, bots=bots)
            if (root and bots)
            else cold_harvest_status(root)
        ),
        "hillclimb_lever": hillclimb_lever_status(root),
        "hillclimb_e9_week": hillclimb_e9_week_board(root, bots=bots),
        "hillclimb_broadcast": hillclimb_lever_masters_broadcast(root),
        "dual_control": dual_control_status(root),
        "quarterly_rebaseline": quarterly_rebaseline_status(root),
        "capital_os": capital_os_status(root, bots=bots, cfg=cfg),
        "opp_cost": opp_cost_summary(root),
        "idea_review": idea_review_status(root),
        "sports_green_boost": sports_green_boost_status(root, bots=bots),
        "green_or_gone": green_or_gone_status(bots),
        "btc_calibration": btc_calibration_report(bots),
        # Prefer live offer book whenever bots are provided (#495 Masters twin).
        "firm_queue": (
            (
                capture_firm_queue(root, bots=bots, cfg=cfg),
                firm_queue_status(root),
            )[1]
            if (root and bots)
            else firm_queue_status(root)
        ),
        "empty_card": empty_card_status(root),
        "empty_card_series": empty_card_series_board(root),
        "depth_adjusted_edge": depth_adjusted_edge_board(root),
        "near_miss_promote": near_miss_promote_status(root),
        "near_miss_soft_p": near_miss_soft_p_status(root, bots=bots),
        "exit_quality": exit_quality_observe(root, bots=bots),
        "selective_throughput": selective_throughput_observe(root, bots=bots),
        "selective_kill": selective_kill_status(root, bots=bots),
        "tip_funnel": tip_funnel_board(root),
        "gate_a_pilot": gate_a_pilot_btc_calendar(root),
        "gate_a_pilot_sports_clv": gate_a_pilot_sports_clv(root),
        "gate_a_pilots": gate_a_pilots_board(root),
        "helper_advice_log": helper_advice_log_board(root),
        "helper_advice_lift": helper_advice_lift_board(root),
        "insight_helpers_execution_lock": insight_helpers_execution_lock(root),
        "eligible_fill_funnel": eligible_fill_funnel(root, bots=bots),
        "throughput_vs_m1": throughput_vs_m1_board(root, bots=bots),
        "promote_distance": promote_distance_observe(root, bots=bots),
        "firm_health": firm_health_observe(root, bots=bots, cfg=cfg),
        "ops": ops_observe(root, bots=bots),
        "guardrails": guardrails_observe(root, bots=bots),
        "review": review_observe(root, bots=bots),
        "calib_clv": calib_clv_observe(root, bots=bots),
        "baseline_fee": baseline_fee_observe(root, bots=bots, cfg=cfg),
        "fit_firm": fit_buy_rate(root),
        "m4_latency": m4_latency_board(root),
        "adverse_selection_autopsy": adverse_selection_autopsy(root, bots=bots),
        "news_gap_autopsy": news_gap_autopsy(root, bots=bots),
        "eia_gap_autopsy": eia_gap_autopsy(root, bots=bots),
        "weekend_inx_autopsy": weekend_inx_autopsy(root, bots=bots),
        "distance_to_zero": distance_to_zero_board(root, bots=bots),
        "firm_heat": firm_heat_map(root, bots=bots),
        "sticky_sla": sticky,
        "weekly_eligible_fill": weekly_eligible_fill_report(root, bots=bots),
        "insight_betting_ratio": insight_betting_ratio_board(root, bots=bots),
        "edge08_vs_main": edge08_vs_main_expectancy_board(root, bots=bots),
        "fee_clear_cadence": fee_clear_cadence_health_board(root, bots=bots),
        "latency_stage": latency_stage_board(root),
        "tip_to_decision_ms": tip_to_decision_ms(root),
        "exit_to_risk_freed_ms": exit_to_risk_freed_ms(root),
        "fill_capacity_observe": fill_capacity_observe(root, bots=bots, cfg=cfg),
        "firm_tower_m1_gap": firm_tower_m1_gap_alert(bots),
        "fee_floors_locked": True,
        "next_tickets": [
            "staff hillclimb pick (TC-151 process)",
            "dual-control / LIVE_ORDERS (deferred)",
            "force-armed evidence catch-up (deferred)",
            "E8–E9 staff/LIVE deferred (bulk E3–E7 engineerable shipped)",
        ],
        "note": "Positive-ROI plan instrumentation. No profit guarantee.",
    }


def self_check() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        record_fit(tmp, bot="btc15m", outcome="fit", ticker="T1")
        record_fit(tmp, bot="btc15m", outcome="buy", ticker="T1")
        record_fit(tmp, bot="btc15m", outcome="block", ticker="T2")
        # need more for pass bar — rate check shape
        fb = fit_buy_rate(tmp, "btc15m")
        assert fb["n_fit"] == 3
        assert fb["n_buy"] == 1
        assert fb["rate"] == round(1 / 3, 4)
        record_latency(tmp, bot="btc15m", seconds=12.5)
        record_latency(tmp, bot="btc15m", seconds=8.0)
        lat = latency_p50(tmp, "btc15m")
        assert lat["n"] == 2
        assert lat["p50_s"] is not None
        bleed = firm_bleed_ratio([
            {"id": "memecoin", "today": -10},
            {"id": "sports-gap", "today": 20},
        ])
        assert bleed["ratio"] == 0.5
        assert bleed["pass"] is False  # target_lt 0.5 → 0.5 not < 0.5
        mis = capital_misplaced(
            [{"id": "memecoin", "today": -8, "open_risk": 25}],
            {"max_open_risk": 100},
        )
        assert mis["misplaced_usd"] == 25
        base = capture_baseline(tmp, bots=[{"id": "btc15m", "today": 0, "cash": 100}], label="W0")
        assert base["label"] == "W0"
        assert clv_row_complete({"fair_entry": 0.82}) is True
        assert clv_row_complete({"clv": 0.01}) is False
        rep = run_inx_band_research(
            tmp,
            history=[
                {"ask": 0.85, "pnl": 2.0, "contracts": 1},
                {"ask": 0.72, "pnl": -1.0, "contracts": 1},
                {"ask": 0.91, "pnl": 1.5, "contracts": 1},
            ],
        )
        assert rep["live_changed"] is False
        assert rep["live_band"] == "80_90"
        assert len(rep["bands"]) == 3
        assert inx_live_band(tmp)["staff_approved"] is False
        assert inx_band_promote_status(tmp)["auto_promote"] is False
        hit = sports_hard_stop_hit(0.80, 0.65, drop=0.12)
        assert hit["hit"] is True
        miss = sports_hard_stop_hit(0.80, 0.72, drop=0.12)
        assert miss["hit"] is False
        rec = record_sports_hard_stop_shadow(
            tmp, ticker="KXTEST", side="home", entry_price=0.80, bid=0.65,
            contracts=10, cost=8.5,
        )
        assert rec["recorded"] is True
        summ = sports_hard_stop_shadow_summary(tmp)
        assert summ["n"] >= 1
        assert summ["live"] is False
        assert summ["auto_promote"] is False
        assert summ["code_default_live"] is False
        denied = staff_set_sports_hard_stop_live(tmp, True, note="too early")
        assert denied["ok"] is False
        assert sports_hard_stop_is_live(tmp) is False
        cool = record_adverse_fill(
            tmp, bot="btc15m", ticker="T", entry_price=0.80, mark_price=0.70,
        )
        assert cool["cooled"] is True
        assert adverse_cool_blocks(tmp, "btc15m")
        card = capture_weekly_scorecard(
            tmp, bots=[{"id": "sports-gap", "today": 2, "gate_a": {"ready": True}}],
            cfg={"max_open_risk": 100}, label="W-test",
        )
        assert card["gate_a_ready_towers"] == 1
        assert latest_weekly_scorecard(tmp)["label"] == "W-test"
        assert latest_weekly_scorecard(tmp)["fee_floors_locked"] is True
        # Graduation: one all-pass week → week_1; two → master (still no auto-promote).
        all_pass = {
            "bot": "sports-gap",
            "passing": {c: True for c in GRADUATION_CODES},
        }
        capture_graduation_week(tmp, [all_pass], label="2026-11-02")
        board1 = graduation_board(tmp)
        assert board1["towers"]["sports-gap"]["status"] == "week_1"
        capture_graduation_week(tmp, [all_pass], label="2026-11-03")
        board2 = graduation_board(tmp)
        assert board2["towers"]["sports-gap"]["status"] == "master"
        assert board2["towers"]["sports-gap"]["auto_promote"] is False
        retire = meme_retirement_clock(
            {
                "id": "memecoin",
                "history": [{"pnl": -2.0, "contracts": 1} for _ in range(12)],
            }
        )
        assert retire["recommend_pause"] is True
        assert retire["expand_volume"] is False
        assert retire["retired"] is False
        # Hillclimb kill: M3↑ M1↓ with fills up → revert flag (no auto write).
        bots_a = [{"id": "btc15m", "history": [{"pnl": 2.0, "contracts": 1}] * 10}]
        for _ in range(6):
            record_fit(tmp, bot="btc15m", outcome="fit")
            record_fit(tmp, bot="btc15m", outcome="block")
        capture_hillclimb_week(tmp, bots=bots_a, label="2026-11-01", lever="VOL_SAFE")
        bots_b = [{"id": "btc15m", "history": [{"pnl": 0.5, "contracts": 1}] * 10}]
        for _ in range(10):
            record_fit(tmp, bot="btc15m", outcome="fit")
            record_fit(tmp, bot="btc15m", outcome="buy")
        out = capture_hillclimb_week(tmp, bots=bots_b, label="2026-11-08", lever="VOL_SAFE")
        assert out["status"]["kill"] is True
        assert out["status"]["action"] == "revert_lever"
        assert out["status"]["auto_revert"] is False
        assert hillclimb_kill_status(tmp)["kill"] is True
        # Profit-lock: week PnL ≥ target → 0.5× size safe-mode.
        lock = capture_profit_lock(
            tmp,
            bots=[
                {"id": "sports-gap", "today": 25.0},
                {"id": "btc15m", "today": 20.0},
            ],
            label="2026-11-03",
            target_usd=40.0,
        )
        assert lock["safe_mode"] is True
        assert lock["size_mult"] == 0.5
        assert profit_lock_size_mult(tmp) == 0.5
        sr = skip_regret_weekly_card(tmp, label="2026-11-03")
        assert sr["auto_promote"] is False
        assert sr["fee_floors_locked"] is True
        assert latest_skip_regret_weekly(tmp)["label"] == "2026-11-03"
        # Sports 1.5R × $20 = $30 → settle-only at today ≥ 30.
        assert daily_r_blocks("sports-gap", 29.0) == ""
        assert "settle-only" in daily_r_blocks("sports-gap", 30.0)
        board = capture_daily_r_board(
            tmp,
            bots=[{"id": "sports-gap", "today": 35.0}, {"id": "btc15m", "today": 10.0}],
            label="2026-11-03",
        )
        assert "sports-gap" in board["settle_only"]
        assert "btc15m" not in board["settle_only"]
        ar = record_anti_revenge(
            tmp, bot="btc15m", ticker="KXTEST", reason="model-flip", minutes=30,
        )
        assert ar["cooled"] is True
        assert "anti-revenge" in anti_revenge_blocks(tmp, "btc15m", "KXTEST")
        assert anti_revenge_blocks(tmp, "btc15m", "OTHER") == ""
        enroll_incubation(tmp, "KXNEON15M")
        for _ in range(50):
            record_incubation_settle(
                tmp, series="KXNEON15M", bot="commodity-15m", pnl=0.2, contracts=1,
            )
        assert incubation_status(tmp, "KXNEON15M")["promote_ready"] is True
        assert staff_graduate_incubation(tmp, "KXNEON15M")["ok"] is True
        assert incubation_status(tmp, "KXNEON15M")["lane"] == "graduated"
        # Fee ledger: Kalshi-style estimate + completeness vs closed history.
        assert estimate_kalshi_fee(0.50, 1) == 0.02  # ceil(0.07*0.25)=0.02
        bots_fee = []
        for i in range(5):
            tick = f"KXFEE-{i}"
            record_fee_ledger(
                tmp, bot="btc15m", ticker=tick, side="YES",
                price=0.55, contracts=1, fee=0.02, pnl=0.10,
                fill_id=f"fid-{i}", kind="sell",
            )
            bots_fee.append({
                "id": "btc15m",
                "history": [{"ticker": tick, "pnl": 0.10, "fill_id": f"fid-{i}"}],
            })
        # Flatten into one bot with 5 history rows.
        hist = []
        for b in bots_fee:
            hist.extend(b["history"])
        complete = fee_ledger_completeness(tmp, bots=[{"id": "btc15m", "history": hist}])
        assert complete["matched"] == 5
        assert complete["rate"] == 1.0
        assert complete["pass"] is True
        summ = fee_ledger_summary(tmp)
        assert summ["n"] == 5
        assert summ["fill_tax_sum"] == 0.05
        assert summ["fee_floors_locked"] is True
        # Stale-world: last loop over bar → block entries.
        assert stale_world_blocks(tmp, "btc15m") == ""
        record_latency(tmp, bot="btc15m", seconds=55.0)
        assert "stale-world" in stale_world_blocks(tmp, "btc15m")
        assert stale_world_blocks(tmp, "btc15m", loop_seconds=10.0) == ""
        assert "clock-skew" in stale_world_blocks(
            tmp, "btc15m", loop_seconds=1.0, clock_skew_sec=45.0,
        )
        sw = stale_world_status(tmp, bots=[{"id": "btc15m"}])
        assert "btc15m" in sw["blocked"]
        assert sw["fee_floors_locked"] is True
        # Helper Gate A: thin sample blocked; n≥20 taxed EV≥0 + staff arm.
        assert helper_may_place_alone(tmp, "calendar_scanner") is False
        assert "Gate A" in helper_autonomy_blocks(tmp, "calendar_scanner")
        for i in range(HELPER_GATE_A_MIN_N):
            record_helper_fill(
                tmp, helper="calendar_scanner", bot="btc15m",
                ticker=f"KXCAL-{i}", pnl=0.05, contracts=1, fill_id=f"h-{i}",
            )
        gate = helper_gate_a(tmp, "calendar_scanner")
        assert gate["ready"] is True
        assert gate["auto_promote"] is False
        denied = staff_set_helper_autonomy(tmp, "calendar_scanner", True)
        # Without force still ok when ready.
        assert denied["ok"] is True
        assert helper_may_place_alone(tmp, "calendar_scanner") is True
        staff_set_helper_autonomy(tmp, "calendar_scanner", False, note="disarm")
        assert helper_may_place_alone(tmp, "calendar_scanner") is False
        # Cold harvest: 40% of green week PnL → cold ledger.
        capture_profit_lock(
            tmp,
            bots=[{"id": "sports-gap", "today": 30.0}, {"id": "btc15m", "today": 20.0}],
            label="2026-11-03",
        )
        cold = capture_cold_harvest(
            tmp,
            bots=[{"id": "sports-gap", "today": 30.0}, {"id": "btc15m", "today": 20.0}],
            label="2026-11-03",
            pct=0.40,
        )
        assert cold["harvested"] == 20.0  # 40% of 50
        assert cold["cold_total"] == 20.0
        assert cold["fee_floors_locked"] is True
        red = capture_cold_harvest(
            tmp,
            bots=[{"id": "memecoin", "today": -5.0}],
            label="2026-11-10",
            pct=0.40,
        )
        # New week with negative proxy — no add (week_pnl from that week's lock).
        assert red["harvested"] == 0.0 or red.get("skipped") is True
        # Hillclimb lever allowlist: one per week, raise-only floors.
        al = hillclimb_allowlist()
        assert "VOL_SAFE" in al["levers"]
        assert al["levers"]["venue_min_edge_btc"]["raise_only"] is True
        blocked_sun = staff_pick_hillclimb_lever(tmp, "VOL_SAFE", note="week experiment")
        assert blocked_sun["ok"] is False
        staff_mark_sunday_packet_reviewed(tmp, who="selftest")
        pick = staff_pick_hillclimb_lever(tmp, "VOL_SAFE", note="week experiment")
        assert pick["ok"] is True
        thrash = staff_pick_hillclimb_lever(tmp, "HIT_FOR_BIG")
        assert thrash["ok"] is False
        soft = staff_pick_hillclimb_lever(
            tmp, "venue_min_edge_btc", proposed_value=0.03, force=True,
        )
        assert soft["ok"] is False
        assert "0.05" in soft["reason"]
        dem = staff_demote_hillclimb_lever(tmp, note="sunday")
        assert dem["ok"] is True
        assert active_hillclimb_lever(tmp) is None
        none = staff_pick_hillclimb_lever(tmp, "NONE", note="observe")
        assert none["ok"] is True
        assert none["active"]["observation_continues"] is True
        templates = hillclimb_lever_evidence_templates()
        assert "VOL_SAFE" in templates["templates"]
        assert templates["templates"]["VOL_SAFE"]["dry_run"]["writes_venue_params"] is False
        # Dual-control stub: two staff + all items; live stays False.
        assert LIVE_ORDERS_ENABLED is False
        for iid, _ in DUAL_CONTROL_ITEMS:
            staff_sign_dual_control(tmp, who="alice", role="primary", item_id=iid)
        staff_sign_dual_control(tmp, who="bob", role="secondary")
        dc = dual_control_status(tmp)
        assert dc["checklist_complete"] is True
        assert dc["two_staff"] is True
        assert dc["arm_ready_paper"] is True
        assert dc["live_orders_enabled"] is False
        qb = capture_quarterly_rebaseline(
            tmp, bots=[{"id": "btc15m", "today": 1, "cash": 100}], label="W-2026-Q4",
        )
        assert qb["quarterly"] is True
        assert quarterly_rebaseline_status(tmp)["has_quarterly"] is True
        # Barbell: heavy meme open fails; fee-clear heavy passes.
        bad_bar = barbell_status(
            [{"id": "memecoin", "open_risk": 40}, {"id": "btc15m", "open_risk": 10}],
            {"max_open_risk": 100},
        )
        assert bad_bar["meme_ok"] is False
        assert bad_bar["pass"] is False
        good_bar = barbell_status(
            [{"id": "btc15m", "open_risk": 40}, {"id": "sports-gap", "open_risk": 30}],
            {"max_open_risk": 100},
        )
        assert good_bar["pass"] is True
        mid = midday_util_alert(
            0.10, skip_board={"stable_top": [{"code": "EDGE", "n": 5}]},
        )
        assert mid["alert"] is True
        mid_idle = midday_util_alert(
            0.10, skip_board={"stable_top": [{"code": "WEEKEND", "n": 5}]},
        )
        assert mid_idle["alert"] is False
        # Opp-cost: pending high-edge then buy lower after bar.
        note_pending_high_edge(
            tmp, bot="sports-gap", ticker="HIGH", edge=0.12, reason="max buys",
        )
        # Backdate pending first_at past bar.
        path = _path(OPP_COST_NAME, tmp)
        store = _opp_store(tmp)
        for row in (store.get("pending") or {}).values():
            if isinstance(row, dict):
                row["first_at"] = "2026-11-01T00:00:00+00:00"
        _save(path, store)
        flushed = flush_opp_cost_on_buy(
            tmp, bot="sports-gap", ticker="LOW", edge=0.04,
        )
        assert flushed["emitted"] >= 1
        assert opp_cost_summary(tmp)["n"] >= 1
        idea = staff_register_idea(tmp, idea="test edge08", lever="VOL_SAFE", who="ops")
        assert idea["ok"] is True
        ir = idea_review_status(tmp)
        assert ir["open_n"] >= 1
        assert ir["auto_promote"] is False


if __name__ == "__main__":
    self_check()
    print("desk_roi_plan self_check ok")
