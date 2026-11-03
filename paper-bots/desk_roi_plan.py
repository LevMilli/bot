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
SPORTS_HARD_STOP_SHADOW = "desk_sports_hard_stop_shadow.json"
ADVERSE_COOL_NAME = "desk_adverse_cool.json"
WEEKLY_SCORECARD = "desk_weekly_scorecard.json"
MASTER_GRAD = "desk_master_grad.json"
HILLCLIMB_KILL = "desk_hillclimb_kill.json"
PROFIT_LOCK = "desk_profit_lock.json"
SKIP_REGRET_WEEKLY = "desk_skip_regret_weekly.json"

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

# Phase 10: profit-lock harvest paper analog — hit weekly target → 0.5× size.
PROFIT_LOCK_TARGET_USD = 40.0
PROFIT_LOCK_SIZE_MULT = 0.5

FEE_CLEAR = ("sports-gap", "btc15m", "commodity-15m")
LOSER_IDS = ("memecoin", "kalshi-sp", "kalshi-sized")

# Sports hard-stop shadow: bid ≤ entry − drop triggers a would-have-stopped log.
# Live sell stays OFF until n≥30 and shadow EV ≥ settle baseline (staff promote).
SPORTS_HARD_STOP_DROP = 0.12
SPORTS_HARD_STOP_LIVE = False  # never auto-sell until staff promote
SPORTS_HARD_STOP_PROMOTE_N = 30

# Fee-aware INX research bands only — does NOT change live 80–90¢ config.
INX_RESEARCH_BANDS = (
    {"id": "70_80", "lo": 0.70, "hi": 0.80},
    {"id": "80_90", "lo": 0.80, "hi": 0.90},  # live default (locked until research wins)
    {"id": "90_95", "lo": 0.90, "hi": 0.95},
)


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


# ---- Near-miss weekly card -------------------------------------------------

def near_miss_weekly_card(root: str | None = None) -> dict:
    """
    Staff promote/reject card from shadow near-miss log.
    auto_promote stays False — never softens floors.
    """
    try:
        import desk_more
        state = desk_more.load_more(root)
        rows = [r for r in (state.get("near_miss") or []) if isinstance(r, dict)]
    except Exception:
        rows = []
    n = len(rows)
    by_soft: dict[str, int] = {}
    by_bot: dict[str, int] = {}
    for r in rows:
        soft = r.get("soft")
        key = ",".join(soft) if isinstance(soft, list) else str(soft or "unknown")
        by_soft[key] = int(by_soft.get(key) or 0) + 1
        bot = str(r.get("bot") or "?")
        by_bot[bot] = int(by_bot.get(bot) or 0) + 1
    decision = "reject" if n < 30 else "review"
    card = {
        "paper_only": True,
        "n": n,
        "promote_min_n": 30,
        "auto_promote": False,
        "decision": decision,
        "by_soft": by_soft,
        "by_bot": by_bot,
        "fee_floors_locked": True,
        "note": (
            "Shadow near-miss only. Promote a soft gate only after n≥30 and "
            "shadow EV ≥ baseline — staff review. Never auto-lower min_edge."
        ),
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


def run_inx_band_research(root: str | None, history: list | None = None) -> dict:
    """Score research bands; never writes live config. Live stays 80–90 until staff promote."""
    bands = []
    for b in INX_RESEARCH_BANDS:
        scored = inx_band_research_score(history or [], lo=b["lo"], hi=b["hi"])
        bands.append({**b, **scored, "live_default": b["id"] == "80_90"})
    ranked = sorted(
        [x for x in bands if x.get("n")],
        key=lambda x: (x.get("expectancy_taxed") is not None, x.get("expectancy_taxed") or -999),
        reverse=True,
    )
    report = {
        "paper_only": True,
        "live_band": "80_90",
        "live_changed": False,
        "bands": bands,
        "leader": ranked[0]["id"] if ranked else None,
        "fee_floors_locked": True,
        "note": (
            "Research harness only — does not change kalshi-sp/sized ask band. "
            "Promote only after staff review + Chicago week."
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
    state["live"] = bool(SPORTS_HARD_STOP_LIVE)
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
    return {
        "paper_only": True,
        "n": len(rows),
        "n_with_pnl": n,
        "shadow_expectancy": exp,
        "promote_min_n": SPORTS_HARD_STOP_PROMOTE_N,
        "drop": SPORTS_HARD_STOP_DROP,
        "live": bool(SPORTS_HARD_STOP_LIVE),
        "auto_promote": False,
        "decision": decision,
        "fee_floors_locked": True,
        "note": (
            "Sports hard-stop is shadow-only. Promote to live sell only after "
            f"n≥{SPORTS_HARD_STOP_PROMOTE_N} and shadow EV ≥ 0 — staff gate."
        ),
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
    card = {
        "paper_only": True,
        "label": day,
        "captured_at": _now(),
        "m1": m1.get("expectancy_taxed"),
        "m1_n": m1.get("n"),
        "m3": m3.get("rate"),
        "m3_n_fit": m3.get("n_fit"),
        "fills_n": m3.get("n_buy"),
        "lever": (str(lever).strip()[:80] if lever else None),
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
        "fit_firm": fit_buy_rate(root),
        "fee_floors_locked": True,
        "next_tickets": [
            "sports hard-stop promote after n≥30 (staff; live still False)",
            "INX band promote only after research week artifact",
            "daily R budget per tower after which settle-only",
            "anti-revenge same-market cool after stop/flip",
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


if __name__ == "__main__":
    self_check()
    print("desk_roi_plan self_check ok")
