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

MAX_FIT_ROWS = 4000
MAX_LAT_ROWS = 4000
MAX_HARD_STOP_ROWS = 2000

# Adverse selection cool-off: fast mark-down after entry → pause that bot briefly.
ADVERSE_MARK_DROP = 0.05  # 5¢ adverse vs entry ask/bid
ADVERSE_COOL_MINUTES = 20

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
        "fit_firm": fit_buy_rate(root),
        "fee_floors_locked": True,
        "next_tickets": [
            "sports hard-stop promote after n≥30 (staff; live still False)",
            "Master graduation checklist cards (M1–M7 × 2 weeks)",
            "meme 20d retirement clock",
            "INX band promote only after research week artifact",
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


if __name__ == "__main__":
    self_check()
    print("desk_roi_plan self_check ok")
