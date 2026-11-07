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
SPORTS_CALIB_NAME = "desk_sports_calibration.json"
COMMODITY_CALIB_NAME = "desk_commodity_calibration.json"
RAISE_PHI_DECISIONS = "desk_raise_phi_decisions.json"
FIRM_QUEUE_NAME = "desk_firm_queue.json"
EMPTY_CARD_NAME = "desk_empty_card.json"
BLEED_WEEK_NAME = "desk_bleed_week.json"
NEAR_MISS_PROMOTE_NAME = "desk_near_miss_promote.json"

MAX_FIT_ROWS = 4000
MAX_LAT_ROWS = 4000
MAX_HARD_STOP_ROWS = 2000

# Adverse selection cool-off: fast mark-down after entry → pause that bot briefly.
ADVERSE_MARK_DROP = 0.05  # 5¢ adverse vs entry ask/bid
ADVERSE_COOL_MINUTES = 20

# Phase 6: Master only after 2 consecutive Chicago weeks of all M-codes.
GRADUATION_WEEKS_REQUIRED = 2
GRADUATION_CODES = ("M1", "M2", "M3", "M4", "M5", "M6", "M7")

# Phase 7: meme sleeve retirement clock (recommend pause; staff re-arms).
MEME_RETIRE_WINDOW_DAYS = 20
MEME_RETIRE_MIN_N = 10

# Phase 11: hillclimb kill — M3↑ with M1↓ for 2 Chicago weeks → revert lever.
HILLCLIMB_KILL_WEEKS = 2
# Phase 11: one lever per Chicago week from allowlist (raise-only on fee floors).
HILLCLIMB_ALLOWLIST = {
    "VOL_SAFE": {
        "kind": "adapt_threshold",
        "raise_only": False,
        "note": "desk_adapt VOL_SAFE play-safe threshold experiment",
    },
    "HIT_FOR_BIG": {
        "kind": "adapt_threshold",
        "raise_only": False,
        "note": "desk_adapt HIT_FOR_BIG proven-80 threshold experiment",
    },
    "venue_min_edge_btc": {
        "kind": "venue_floor",
        "raise_only": True,
        "venue": "kalshi_btc15m",
        "note": "BTC venue min_edge — raise only, never soften floor",
    },
    "min_cushion_btc": {
        "kind": "btc_gate",
        "raise_only": True,
        "note": "BTC min cushion — raise only",
    },
    "kelly_fraction": {
        "kind": "sizing",
        "raise_only": False,
        "note": "Kelly fraction within desk bounds (0.05–1.0)",
    },
}

# Phase 10: profit-lock harvest paper analog — hit weekly target → 0.5× size.
PROFIT_LOCK_TARGET_USD = 40.0
PROFIT_LOCK_SIZE_MULT = 0.5

# Phase 7: daily R budget — hit +budget → settle-only for that tower (exits still on).
DAILY_R_USD = 20.0  # 1R paper unit
DAILY_R_BUDGET = {
    "sports-gap": 1.5,
    "btc15m": 2.0,
    "commodity-15m": 1.5,
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
    rows = list(state.get("rows") or [])
    rows.append(row)
    state["rows"] = rows[-MAX_LAT_ROWS:]
    bot_row = state.setdefault("by_bot", {}).setdefault(bot, {"n": 0, "sum": 0.0})
    bot_row["n"] = int(bot_row.get("n") or 0) + 1
    bot_row["sum"] = float(bot_row.get("sum") or 0) + float(sec)
    state["last_at"] = row["at"]
    save_latency(state, root)
    return row


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
    p50 = vals[n // 2] if n else None
    # Sports bar 45s; 15m towers 20s — caller passes bot for bar pick.
    bar = 45.0 if bot == "sports-gap" else 20.0
    return {
        "paper_only": True,
        "bot": bot,
        "n": n,
        "p50_s": round(p50, 3) if p50 is not None else None,
        "bar_s": bar,
        "pass": p50 is not None and n >= 5 and p50 <= bar,
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


# ---- BTC calibration report (Phase 4) --------------------------------------

def _btc_history_rows(bots: list | None) -> list:
    rows = []
    for bot in bots or []:
        if not isinstance(bot, dict):
            continue
        if str(bot.get("id") or "") not in ("btc15m", "btc"):
            continue
        for h in bot.get("history") or []:
            if isinstance(h, dict):
                rows.append(h)
    return rows


def btc_calibration_report(
    bots: list | None = None,
    *,
    min_n: int = BTC_CALIB_MIN_N,
) -> dict:
    """Bucket BTC model-p vs realized hit rate. Flag high-p miscalibration.

    Plan: if labeled ~80% wins ~55%, raise Φ — never size on miscalibration.
    """
    rows = _btc_history_rows(bots)
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
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "bot": "btc15m",
        "n": sum(b["n"] for b in buckets),
        "hi_label": BTC_CALIB_HI_LABEL,
        "hi_n": hi_n,
        "hi_hit_rate": hi_rate,
        "hi_hit_floor": BTC_CALIB_HI_HIT_FLOOR,
        "miscalibrated": miscal,
        "action": action,
        "buckets": buckets,
        "auto_promote": False,
        "note": (
            "BTC calibration: high-p (≥80%) bucket must hit ≥70% once n≥20. "
            "Miscalibration → raise Φ / fix model — never size up on fake confidence."
            if miscal
            else "BTC calibration board. Fee floors locked; no auto param write."
        ),
    }


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
) -> dict:
    """Log an idle/empty-market CARD loop for the <3s bar."""
    sec = _finite(seconds)
    if sec is None or sec < 0:
        return {"recorded": False, "reason": "bad seconds"}
    bot_id = str(bot or "").strip()
    if not bot_id:
        return {"recorded": False, "reason": "missing bot"}
    row = {
        "at": _now(),
        "bot": bot_id[:40],
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
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "n": len(secs),
        "p50_s": p50,
        "max_s": round(max(secs), 3) if secs else None,
        "bar_sec": EMPTY_CARD_BAR_SEC,
        "pass": ok,
        "by_bot": by_bot,
        "recent": rows[-8:],
        "note": (
            f"Empty-market CARD bar {EMPTY_CARD_BAR_SEC:.0f}s — "
            "prefetch books; idle loops should exit fast."
            if ok
            else (
                f"Empty-market CARD p50 {p50}s > {EMPTY_CARD_BAR_SEC:.0f}s bar — "
                "speed up idle path / prefetch."
            )
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


# ---- Near-miss weekly card + staff soft-gate promote -----------------------

def _near_miss_rows(root: str | None) -> list[dict]:
    try:
        import desk_more
        state = desk_more.load_more(root)
        return [r for r in (state.get("near_miss") or []) if isinstance(r, dict)]
    except Exception:
        return []


def label_near_miss_outcome(
    root: str | None,
    *,
    ticker: str,
    would_pnl,
    bot: str | None = None,
    note: str = "",
) -> dict:
    """Attach settle / would-have PnL to shadow near-miss rows (staff or settle hook)."""
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
    out_rows = []
    for row in rows:
        if not isinstance(row, dict):
            out_rows.append(row)
            continue
        item = dict(row)
        if str(item.get("ticker") or "") == tick and (
            not bot_id or str(item.get("bot") or "") == bot_id
        ):
            item["would_pnl"] = round(float(pnl), 4)
            item["labeled_at"] = _now()
            if note:
                item["label_note"] = str(note)[:120]
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


def near_miss_promote_status(root: str | None = None) -> dict:
    """Masters board: n≥30 + shadow EV ≥ baseline before staff may arm one soft gate.

    Soft allowlist is z|p only — never edge / fee floors. auto_promote=False forever.
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
        "z_relax": NEAR_MISS_Z_RELAX if soft_live == "z" else 0.0,
        "p_relax": NEAR_MISS_P_RELAX if soft_live == "p" else 0.0,
        "by_soft": by_soft,
        "by_bot": by_bot,
        "label": (
            f"near_miss={'ready' if ready else 'THIN'} "
            f"labeled={labeled_n}/{NEAR_MISS_PROMOTE_N} "
            f"ev={shadow_ev} n_to={n_to} soft_live={soft_live or 'none'}"
        ),
        "note": (
            "Near-miss shadow: staff may arm soft-z first after "
            f"n≥{NEAR_MISS_PROMOTE_N} labeled with shadow EV ≥ {baseline}. "
            "Soft-p is second arm only after z holds M1. "
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
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "soft_p_ready": ready,
        "evidence_thin": not ready,
        "promote_ready": bool(base.get("promote_ready")),
        "z_armed": z_armed,
        "soft_live": soft,
        "m1_holds": bool(m1.get("holds")),
        "m1": m1,
        "labeled_n": base.get("labeled_n"),
        "n_to_promote": base.get("n_to_promote"),
        "shadow_ev": base.get("shadow_ev"),
        "reason": reason,
        "label": (
            f"soft-p ready"
            if ready
            else f"soft-p THIN — {reason[:72]}"
        ),
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
    """Staff arm one soft near-miss gate (z|p). Requires promote_ready unless force.

    Soft-p is second arm only: soft-z must already be live and firm M1 must hold
    (unless force — deferred on money-path CLI).
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
    if key == "p" and not force:
        soft_p = near_miss_soft_p_status(root, bots=bots)
        if not soft_p.get("soft_p_ready"):
            return {
                "ok": False,
                "live": False,
                "staff_approved": False,
                "reason": soft_p.get("reason") or "soft-p not ready",
                "soft_p": soft_p,
                "summary": summary,
                "auto_promote": False,
                "fee_floors_locked": True,
                "force": False,
            }
    if not force and not summary.get("promote_ready"):
        return {
            "ok": False,
            "live": False,
            "staff_approved": False,
            "reason": (
                f"not promote_ready (need labeled n≥{NEAR_MISS_PROMOTE_N} "
                f"with shadow EV ≥ {NEAR_MISS_PROMOTE_MIN_EV})"
            ),
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
        "shadow_n": summary.get("labeled_n"),
        "shadow_ev": summary.get("shadow_ev"),
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


SKIP_REGRET_SOFT_ALLOW = frozenset({"z", "p", "cushion", "depth", "latency"})
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
            "Skip-regret candidates filtered to non-fee soft gates only. "
            "Fee/edge floors never appear as loosen targets."
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

def sports_green_boost_status(
    root: str | None = None,
    *,
    bots: list | None = None,
) -> dict:
    """green_boost=1 only when sports M1≥0 for 2 Chicago weeks and CLV≥52%.

    Default boost stays 0 until ready. auto_promote=False forever.
    """
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
    # Last two weekly scorecards with sports_m1.
    store = _load(_path(WEEKLY_SCORECARD, root), {"paper_only": True, "cards": []})
    cards = [c for c in (store.get("cards") or []) if isinstance(c, dict)]
    cards = sorted(cards, key=lambda c: str(c.get("label") or ""))
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
        missing.append(f"weeks {len(sports_weeks)}/{SPORTS_GREEN_BOOST_WEEKS}")
    if not hist_ok:
        missing.append(f"sports_m1_n {sports_n}/{SPORTS_M1_MIN_N}")
    if not clv_ok:
        missing.append(f"clv {clv_n}/{SPORTS_CLV_MIN_N} rate={clv_rate}")
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
        "flagged_n": len(flags),
        "flags": flags,
        "pass": len(flags) == 0,
        "note": (
            "Green-or-gone: red towers with open risk / loser Gate A false get "
            "starve-or-exit flags on Masters. No volume expand."
        ),
    }


# ---- Sports CLV completeness -----------------------------------------------

def clv_row_complete(row: dict | None) -> bool:
    """True when a sports CLV journal row has the fields needed for M2/CLV learning."""
    if not isinstance(row, dict):
        return False
    if row.get("fair_entry") is None and row.get("entry_fair") is None:
        return False
    if row.get("clv") is None and row.get("fair_close") is None and row.get("close_fair") is None:
        # Allow open rows that only have entry fair (pre-settle); still "complete enough" for entry log.
        return True
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
    settled = [
        r for r in rows
        if r.get("clv") is not None or r.get("fair_close") is not None or r.get("close_fair") is not None
    ]
    settled_ok = sum(
        1 for r in settled
        if (r.get("fair_entry") is not None or r.get("entry_fair") is not None) and r.get("clv") is not None
    )
    return {
        "paper_only": True,
        "n": n,
        "complete": ok,
        "settled_n": len(settled),
        "settled_complete": settled_ok,
        "rate": round(ok / n, 4) if n else None,
        "settled_rate": round(settled_ok / len(settled), 4) if settled else None,
        "pass": (n == 0) or (ok == n and (not settled or settled_ok == len(settled))),
        "note": "Every sports settle should log entry fair + clv.",
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
            "kind": "gap_decay+scale_out+hard_stop_shadow+settle",
            "hard_stop_drop": SPORTS_HARD_STOP_DROP,
            "hard_stop_live": bool(SPORTS_HARD_STOP_LIVE),
            "hard_stop_shadow": True,
            "gap_decay": True,
            "scale_out": True,
            "settle_backstop": True,
            "auto_promote": False,
            "fee_floors_locked": True,
            "note": (
                "Sports exits: gap-decay + scale-out + hard-stop shadow "
                f"(−{SPORTS_HARD_STOP_DROP:.0%} bid); live hard-stop stays staff-gated."
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
            "kind": "model_flip+settle",
            "model_flip": True,
            "settle_backstop": True,
            "series_corr_haircut": True,
            "fee_floors_locked": True,
            "note": "Commodity exits: model-flip; settle is backstop; WTI↔Brent haircut on entry.",
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
    daily = latest_daily_r_board(root) or {}
    if not daily and bots:
        daily = capture_daily_r_board(root, bots=bots) if root else {
            "towers": {},
            "settle_only": [],
            "note": "ephemeral daily R (no root)",
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
            "status": {
                k: dual.get(k)
                for k in ("paper_only", "armed", "live", "live_orders_enabled", "checklist", "note")
                if k in dual
            },
            "note": "LIVE_ORDERS dual-control deferred — observe status only.",
        },
        "label": (
            f"ops={'ok' if not alerts else 'ALERT'} "
            f"incub={incubating}/{ready_grad} masters={masters} "
            f"ruin={ruin.get('level') or 'off'} cold_w={cold.get('weeks_n')} "
            f"btc_n={calib.get('n')}"
        ),
        "note": (
            "Ops observe — incubation / ruin drill / cold harvest / Master graduation / "
            "BTC calibration. Dual-control LIVE_ORDERS remain deferred."
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
            "Promote-distance observe across INX / hard-stop / green_boost / "
            "near-miss / edge08 / helper Gate A. Evidence catch-up deferred; "
            "no force; dual-control LIVE_ORDERS still off."
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
    hard = sports_hard_stop_shadow_summary(root)
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
        "selective_throughput": selective,
        "label": (
            f"E2 exit-quality cover={coverage.get('n_with_plan')}/"
            f"{coverage.get('n_open')} sports_n={sports.get('n')} "
            f"btc_comm_n={fee_clear.get('n')} "
            f"hs_shadow={hard.get('n_with_pnl')} selective_m1={selective.get('m1_holds')}"
        ),
        "note": (
            "E2 exit-quality observe / selective throughput after M1. "
            "Never softens floors; never arms LIVE_ORDERS; no tip invent."
        ),
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
    if entry is None or b is None or d is None or entry <= 0 or b <= 0:
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
    # Shadow PnL if we sold at bid − approx fee (Kalshi-style ceil omitted; 1¢ tax).
    contracts_n = _finite(contracts) or 1.0
    cost_n = _finite(cost)
    bid_n = _finite(bid) or 0.0
    fee_approx = math.ceil(round(0.07 * bid_n * (1.0 - bid_n) * 100, 6)) / 100 if bid_n else 0.0
    proceeds = round(contracts_n * max(0.0, bid_n - fee_approx), 2)
    shadow_pnl = None if cost_n is None else round(proceeds - cost_n, 2)
    row = {
        "at": _now(),
        "ticker": ticker,
        "side": side,
        "league": league,
        "entry_price": gate.get("entry"),
        "bid": gate.get("bid"),
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
    state = _load(path, {"paper_only": True, "bots": {}})
    until = time.time() + ADVERSE_COOL_MINUTES * 60
    state.setdefault("bots", {})[str(bot)] = {
        "until": until,
        "at": _now(),
        "ticker": ticker,
        "entry": entry,
        "mark": mark,
        "drop": round(drop, 4),
        "note": str(note or "")[:160],
    }
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
    """Lane for one series: main | incubation | ready_to_graduate | graduated."""
    key = _series_key(series)
    store = load_incubation(root)
    graduated = {str(s).upper() for s in (store.get("graduated") or [])}
    row = (store.get("series") or {}).get(key) if key else None
    row = row if isinstance(row, dict) else {}
    n = int(row.get("n") or 0)
    pnls = [p for p in (row.get("pnls") or []) if _finite(p) is not None]
    exp = round(sum(pnls) / len(pnls), 4) if pnls else None
    if key and key in graduated:
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
        "promote_ready": lane == "ready_to_graduate",
        "auto_promote": False,
        "main_tape": key in INCUBATION_MAIN_SERIES or lane in ("main", "graduated"),
        "fee_floors_locked": True,
        "note": (
            f"Incubation: need n≥{INCUBATION_MIN_N} fee-aware settles before staff graduate. "
            "Paper trades allowed; no auto-promote."
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
    """Force a series into incubation (even if it was on the main list)."""
    key = _series_key(series)
    if not key:
        return {"ok": False, "reason": "no series"}
    store = load_incubation(root)
    graduated = [s for s in (store.get("graduated") or []) if str(s).upper() != key]
    store["graduated"] = graduated
    series_map = store.setdefault("series", {})
    if key not in series_map:
        series_map[key] = {"series": key, "n": 0, "pnls": [], "bots": {}, "enrolled_at": _now()}
    series_map[key]["note"] = str(note or "")[:160]
    store["series"] = series_map
    _save(_path(INCUBATION_NAME, root), store)
    return {"ok": True, **incubation_status(root, key)}


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
    status = incubation_status(root, series)
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
        "fill_id": str(fill_id or "")[:80],
        "note": str(note or "")[:160],
        "paper_only": True,
        "helper_only": True,
        "places_orders": False,
        "fee_floors_locked": True,
    }
    path = _path(HELPER_FILLS_NAME, root)
    store = _load(path, {"paper_only": True, "rows": [], "by_helper": {}})
    rows = list(store.get("rows") or [])
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
    """Persist fee + fill-tax row so firm ROI can be audited."""
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
        "fill_id": str(fill_id or "")[:80],
        "note": str(note or "")[:160],
        "paper_only": True,
        "fee_floors_locked": True,
    }
    path = _path(FEE_LEDGER_NAME, root)
    store = _load(path, {"paper_only": True, "rows": [], "by_bot": {}})
    rows = list(store.get("rows") or [])
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


def graduation_board(root: str | None = None, *, store: dict | None = None) -> dict:
    """Consecutive all-pass weeks per tower → master / week_1 / not_ready."""
    if store is None:
        store = _load(_path(MASTER_GRAD, root), {"paper_only": True, "weeks": []})
    weeks = [w for w in (store.get("weeks") or []) if isinstance(w, dict)]
    weeks = sorted(weeks, key=lambda w: str(w.get("label") or ""))
    bots: set[str] = set()
    for w in weeks:
        towers = w.get("towers") if isinstance(w.get("towers"), dict) else {}
        bots.update(str(b) for b in towers.keys())
    board = {}
    for bot in sorted(bots):
        streak = 0
        for w in reversed(weeks):
            towers = w.get("towers") if isinstance(w.get("towers"), dict) else {}
            card = towers.get(bot) if isinstance(towers.get(bot), dict) else None
            if card and card.get("all"):
                streak += 1
            else:
                break
        if streak >= GRADUATION_WEEKS_REQUIRED:
            status = "master"
        elif streak == 1:
            status = "week_1"
        else:
            status = "not_ready"
        board[bot] = {
            "bot": bot,
            "consecutive_all_pass_weeks": streak,
            "weeks_required": GRADUATION_WEEKS_REQUIRED,
            "status": status,
            "graduated": status == "master",
            "auto_promote": False,
        }
    masters = sorted(b for b, r in board.items() if r.get("graduated"))
    return {
        "paper_only": True,
        "weeks_n": len(weeks),
        "weeks_required": GRADUATION_WEEKS_REQUIRED,
        "towers": board,
        "masters": masters,
        "masters_n": len(masters),
        "auto_promote": False,
        "fee_floors_locked": True,
        "note": (
            "Phase 6 graduation board. Master = "
            f"{GRADUATION_WEEKS_REQUIRED} consecutive all-pass weeks. No auto-promote."
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
        "note": (
            "One lever per Chicago week. venue_min_edge_btc / min_cushion_btc "
            "are raise-only. Midweek thrash banned."
        ),
    }


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
        "allowlist": sorted(HILLCLIMB_ALLOWLIST.keys()),
        "active": active,
        "week": week,
        "active_this_week": same_week,
        "needs_staff_pick": needs_staff_pick,
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

    Midweek thrash banned unless force=True (tests) or demote first.
    Raise-only levers reject proposed_value below locked floor.
    """
    name = str(lever or "").strip()
    meta = HILLCLIMB_ALLOWLIST.get(name)
    if not meta:
        return {
            "ok": False,
            "reason": f"lever not on allowlist: {name}",
            "allowlist": sorted(HILLCLIMB_ALLOWLIST.keys()),
            "auto_promote": False,
            "fee_floors_locked": True,
        }
    week = _chicago_week_id()
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
        "auto_promote": False,
        "fee_floors_locked": True,
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
        "fee_floors_locked": True,
        "reason": f"picked {name} for {week}",
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
    # Prefer profit-lock week accumulator when present; else firm today as thin proxy.
    pl_store = _load(
        _path(PROFIT_LOCK, root),
        {"paper_only": True, "weeks": {}, "latest": None},
    )
    weeks_pl = pl_store.get("weeks") if isinstance(pl_store.get("weeks"), dict) else {}
    week_row = weeks_pl.get(week_id) if isinstance(weeks_pl.get(week_id), dict) else {}
    week_pnl = _finite(week_row.get("week_pnl"))
    if week_pnl is None:
        # Ensure profit-lock has today's snap, then re-read.
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
    store.setdefault("cards", []).append(card)
    store["cards"] = store["cards"][-52:]
    store["latest"] = card
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
        "weekly_scorecard": latest_weekly_scorecard(root),
        "graduation": graduation_board(root),
        "hillclimb_kill": hillclimb_kill_status(root),
        "profit_lock": profit_lock_status(root),
        "skip_regret_weekly": latest_skip_regret_weekly(root),
        "daily_r": latest_daily_r_board(root),
        "inx_band_promote": inx_band_promote_status(root),
        "incubation": incubation_board(root),
        "ruin_drill": ruin_drill_status(root),
        "fee_ledger": fee_ledger_summary(root),
        "fee_ledger_completeness": fee_ledger_completeness(root, bots=bots),
        "stale_world": stale_world_status(root, bots=bots),
        "helper_gate_a": helper_promote_status(root),
        "cold_harvest": cold_harvest_status(root),
        "hillclimb_lever": hillclimb_lever_status(root),
        "dual_control": dual_control_status(root),
        "quarterly_rebaseline": quarterly_rebaseline_status(root),
        "capital_os": capital_os_status(root, bots=bots, cfg=cfg),
        "opp_cost": opp_cost_summary(root),
        "idea_review": idea_review_status(root),
        "sports_green_boost": sports_green_boost_status(root, bots=bots),
        "green_or_gone": green_or_gone_status(bots),
        "btc_calibration": btc_calibration_report(bots),
        "firm_queue": firm_queue_status(root),
        "empty_card": empty_card_status(root),
        "near_miss_promote": near_miss_promote_status(root),
        "near_miss_soft_p": near_miss_soft_p_status(root, bots=bots),
        "exit_quality": exit_quality_observe(root, bots=bots),
        "selective_throughput": selective_throughput_observe(root, bots=bots),
        "promote_distance": promote_distance_observe(root, bots=bots),
        "firm_health": firm_health_observe(root, bots=bots, cfg=cfg),
        "ops": ops_observe(root, bots=bots),
        "fit_firm": fit_buy_rate(root),
        "sticky_sla": sticky,
        "fee_floors_locked": True,
        "next_tickets": [
            "staff hillclimb pick (TC-151 process)",
            "dual-control / LIVE_ORDERS (deferred)",
            "force-armed evidence catch-up (deferred)",
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
