"""
desk_roi_post_e3e7.py — Post #354–#357 money-path boards (latency stage densify,
speed KPIs, INX pre-noon warm helpers, firm M1 gap, M5 annotation helpers).

NEW boards only — does not rewrite PR #354/#355/#356/#357 surfaces.
Paper only. Fee floors locked. Soft-max tip invent exhausted — no tip wrappers.
"""
from __future__ import annotations

import json
import math
import os
import time
from typing import Any

FEE_CLEAR = ("sports-gap", "btc15m", "commodity-15m")
LOSER_TOWERS = frozenset({"memecoin", "kalshi-sp", "kalshi-sized", "kalshi-sp500"})

# Locked venue floors (never soften).
LOCKED_FEE_FLOORS = {
    "kalshi_sports": 0.06,
    "kalshi_btc15m": 0.05,
    "kalshi_commodity15m": 0.05,
    "kalshi_inx": 0.02,
    "solana_dex": 0.02,
    "coinbase_spot": 0.05,
    "binance_btc_carry": 0.02,
    "kalshi_econ": 0.05,
}

SPEED_KPI_NAME = "desk_speed_kpi.json"
MAX_SPEED_ROWS = 4000
M1_GAP_ALERT_USD = 1.0

# Stage aliases → board columns (ms).
BOOK_STAGES = frozenset({"book", "kalshi", "book_fetch"})
EVAL_STAGES = frozenset({"evaluate", "eval"})
SPOT_STAGES = frozenset({"spot", "espn"})


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


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _load(path: str, empty: dict) -> dict:
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        pass
    return dict(empty)


def _save(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
    os.replace(tmp, path)


def _chicago_day() -> str:
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d")
    except Exception:
        return time.strftime("%Y-%m-%d", time.gmtime())


def fee_floors_locked_check() -> dict:
    """Assert locked floors match desk_profit defaults (sports 0.06 / BTC+cmd 0.05 / INX 0.02)."""
    try:
        import desk_profit
        defaults = dict(desk_profit.DEFAULT_VENUE_MIN_EDGE)
    except Exception as exc:
        return {
            "ok": False,
            "fee_floors_locked": True,
            "reason": f"desk_profit unavailable: {exc}",
            "expected": dict(LOCKED_FEE_FLOORS),
        }
    mismatches = []
    for venue, floor in LOCKED_FEE_FLOORS.items():
        got = _finite(defaults.get(venue))
        if got is None or abs(got - float(floor)) > 1e-12:
            mismatches.append({"venue": venue, "expected": floor, "got": got})
    return {
        "ok": not mismatches,
        "fee_floors_locked": True,
        "paper_only": True,
        "expected": dict(LOCKED_FEE_FLOORS),
        "mismatches": mismatches,
        "note": "Venue floors locked: sports 0.06 / BTC+commodity 0.05 / INX+DEX 0.02.",
    }


# ---- Latency stage board (#502–504 densify) --------------------------------

def latency_stage_board(root: str | None = None, *, days: int = 7) -> dict:
    """Weekly book_fetch_ms / evaluate_ms (and spot/espn) per fee-clear tower."""
    days_n = max(1, min(int(days or 7), 31))
    try:
        import desk_roi_plan as drp
        state = drp.load_latency(root)
    except Exception:
        state = {"rows": []}
    rows = [r for r in (state.get("rows") or []) if isinstance(r, dict)]

    from datetime import datetime, timedelta
    try:
        from zoneinfo import ZoneInfo
        today = datetime.now(ZoneInfo("America/Chicago")).date()
    except Exception:
        today = datetime.utcnow().date()
    window = {(today - timedelta(days=i)).isoformat() for i in range(days_n)}

    towers: dict[str, dict] = {}
    for bot in FEE_CLEAR:
        towers[bot] = {
            "bot": bot,
            "book_fetch_ms": None,
            "evaluate_ms": None,
            "spot_espn_ms": None,
            "book_n": 0,
            "evaluate_n": 0,
            "spot_espn_n": 0,
            "stages": {},
        }

    def _day_of(row: dict) -> str:
        at = str(row.get("at") or "")
        if len(at) >= 10 and at[4] == "-":
            return at[:10]
        return ""

    for r in rows:
        bot = str(r.get("bot") or "")
        if bot not in towers:
            continue
        day = _day_of(r)
        # Keep rows without day (tests / synthetic) inside window.
        if day and day not in window:
            continue
        sec = _finite(r.get("seconds"))
        if sec is None or sec < 0:
            continue
        stage = str(r.get("stage") or "").strip().lower()
        if not stage:
            continue
        slot = towers[bot]
        stages = slot["stages"]
        stages[stage] = int(stages.get(stage) or 0) + 1
        ms = round(sec * 1000.0, 1)
        if stage in BOOK_STAGES:
            prev = slot["book_fetch_ms"]
            n = int(slot["book_n"])
            slot["book_fetch_ms"] = round(((prev or 0) * n + ms) / (n + 1), 1)
            slot["book_n"] = n + 1
        elif stage in EVAL_STAGES:
            prev = slot["evaluate_ms"]
            n = int(slot["evaluate_n"])
            slot["evaluate_ms"] = round(((prev or 0) * n + ms) / (n + 1), 1)
            slot["evaluate_n"] = n + 1
        elif stage in SPOT_STAGES:
            prev = slot["spot_espn_ms"]
            n = int(slot["spot_espn_n"])
            slot["spot_espn_ms"] = round(((prev or 0) * n + ms) / (n + 1), 1)
            slot["spot_espn_n"] = n + 1

    tower_list = [towers[b] for b in FEE_CLEAR]
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "window_days": days_n,
        "chicago_today": _chicago_day(),
        "towers": tower_list,
        "by_bot": towers,
        "label": (
            "latency_stage "
            + " ".join(
                f"{t['bot']}:book={t['book_fetch_ms']} eval={t['evaluate_ms']}"
                for t in tower_list
            )
        ),
        "note": (
            "Weekly latency stage board — book_fetch_ms / evaluate_ms per fee-clear "
            "tower (espn/kalshi sports; spot/book BTC+commodity). Floors locked."
        ),
    }


# ---- Speed KPIs (#498, #562–564) -------------------------------------------

def _empty_speed() -> dict:
    return {
        "paper_only": True,
        "version": 1,
        "tip_alarms": [],
        "decisions": [],
        "exits": [],
        "risk_freed": [],
        "prefetch": [],
        "last_at": None,
    }


def load_speed_kpi(root: str | None = None) -> dict:
    return _load(_path(SPEED_KPI_NAME, root), _empty_speed())


def save_speed_kpi(state: dict, root: str | None = None) -> None:
    _save(_path(SPEED_KPI_NAME, root), state)


def record_tip_alarm(
    root: str | None,
    *,
    bot: str = "sports-gap",
    league: str = "",
    tip_at_ms: float | None = None,
    note: str = "",
) -> dict:
    """Journal a tip-alarm moment for tip_to_decision_ms (observe only)."""
    state = load_speed_kpi(root)
    row = {
        "at": _now(),
        "at_ms": float(tip_at_ms) if tip_at_ms is not None else time.time() * 1000.0,
        "bot": str(bot or "sports-gap")[:40],
        "league": str(league or "")[:20],
        "note": str(note or "")[:120],
        "paper_only": True,
    }
    rows = list(state.get("tip_alarms") or [])
    rows.append(row)
    state["tip_alarms"] = rows[-MAX_SPEED_ROWS:]
    state["last_at"] = row["at"]
    save_speed_kpi(state, root)
    return row


def record_fee_clear_decision(
    root: str | None,
    *,
    bot: str,
    decision_at_ms: float | None = None,
    fee_clear: bool = True,
    note: str = "",
) -> dict:
    """Journal first fee-clear decision after a tip alarm."""
    state = load_speed_kpi(root)
    row = {
        "at": _now(),
        "at_ms": float(decision_at_ms) if decision_at_ms is not None else time.time() * 1000.0,
        "bot": str(bot or "")[:40],
        "fee_clear": bool(fee_clear),
        "note": str(note or "")[:120],
        "paper_only": True,
    }
    rows = list(state.get("decisions") or [])
    rows.append(row)
    state["decisions"] = rows[-MAX_SPEED_ROWS:]
    state["last_at"] = row["at"]
    save_speed_kpi(state, root)
    return row


def record_exit_signal(
    root: str | None,
    *,
    bot: str,
    ticker: str = "",
    exit_at_ms: float | None = None,
    note: str = "",
) -> dict:
    state = load_speed_kpi(root)
    row = {
        "at": _now(),
        "at_ms": float(exit_at_ms) if exit_at_ms is not None else time.time() * 1000.0,
        "bot": str(bot or "")[:40],
        "ticker": str(ticker or "")[:60],
        "note": str(note or "")[:120],
        "paper_only": True,
    }
    rows = list(state.get("exits") or [])
    rows.append(row)
    state["exits"] = rows[-MAX_SPEED_ROWS:]
    state["last_at"] = row["at"]
    save_speed_kpi(state, root)
    return row


def record_risk_freed(
    root: str | None,
    *,
    bot: str,
    ticker: str = "",
    freed_at_ms: float | None = None,
    note: str = "",
) -> dict:
    state = load_speed_kpi(root)
    row = {
        "at": _now(),
        "at_ms": float(freed_at_ms) if freed_at_ms is not None else time.time() * 1000.0,
        "bot": str(bot or "")[:40],
        "ticker": str(ticker or "")[:60],
        "note": str(note or "")[:120],
        "paper_only": True,
    }
    rows = list(state.get("risk_freed") or [])
    rows.append(row)
    state["risk_freed"] = rows[-MAX_SPEED_ROWS:]
    state["last_at"] = row["at"]
    save_speed_kpi(state, root)
    return row


def record_prefetch_hit(
    root: str | None,
    *,
    bot: str,
    tip_books: int = 0,
    hit: bool = False,
    free_risk: float | None = None,
) -> dict:
    """Observe fill-capacity inputs: tip books × prefetch hit × free risk."""
    state = load_speed_kpi(root)
    row = {
        "at": _now(),
        "bot": str(bot or "")[:40],
        "tip_books": max(0, int(tip_books or 0)),
        "prefetch_hit": bool(hit),
        "free_risk": _finite(free_risk),
        "paper_only": True,
    }
    rows = list(state.get("prefetch") or [])
    rows.append(row)
    state["prefetch"] = rows[-MAX_SPEED_ROWS:]
    state["last_at"] = row["at"]
    save_speed_kpi(state, root)
    return row


def tip_to_decision_ms(root: str | None = None) -> dict:
    """Speed KPI: tip alarm → first fee-clear decision (ms). Observe only."""
    state = load_speed_kpi(root)
    alarms = [r for r in (state.get("tip_alarms") or []) if isinstance(r, dict)]
    decisions = [
        r for r in (state.get("decisions") or [])
        if isinstance(r, dict) and r.get("fee_clear")
    ]
    pairs = []
    used = set()
    for a in alarms:
        a_ms = _finite(a.get("at_ms"))
        if a_ms is None:
            continue
        best = None
        best_i = None
        for i, d in enumerate(decisions):
            if i in used:
                continue
            d_ms = _finite(d.get("at_ms"))
            if d_ms is None or d_ms < a_ms:
                continue
            lag = d_ms - a_ms
            if best is None or lag < best:
                best = lag
                best_i = i
        if best is not None and best_i is not None:
            used.add(best_i)
            pairs.append(round(best, 1))
    n = len(pairs)
    avg = round(sum(pairs) / n, 1) if n else None
    p50 = None
    if n:
        s = sorted(pairs)
        p50 = s[n // 2]
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "n": n,
        "samples_ms": pairs[-40:],
        "avg_ms": avg,
        "p50_ms": p50,
        "label": f"tip_to_decision_ms n={n} p50={p50} avg={avg}",
        "note": (
            "Tip alarm → first fee-clear decision (ms). Observe only — never force buys."
        ),
    }


def exit_to_risk_freed_ms(root: str | None = None) -> dict:
    """Speed KPI: exit signal → risk freed (ms). Observe only."""
    state = load_speed_kpi(root)
    exits = [r for r in (state.get("exits") or []) if isinstance(r, dict)]
    freed = [r for r in (state.get("risk_freed") or []) if isinstance(r, dict)]
    pairs = []
    used = set()
    for e in exits:
        e_ms = _finite(e.get("at_ms"))
        tick = str(e.get("ticker") or "")
        if e_ms is None:
            continue
        best = None
        best_i = None
        for i, f in enumerate(freed):
            if i in used:
                continue
            if tick and str(f.get("ticker") or "") and str(f.get("ticker") or "") != tick:
                continue
            f_ms = _finite(f.get("at_ms"))
            if f_ms is None or f_ms < e_ms:
                continue
            lag = f_ms - e_ms
            if best is None or lag < best:
                best = lag
                best_i = i
        if best is not None and best_i is not None:
            used.add(best_i)
            pairs.append(round(best, 1))
    n = len(pairs)
    avg = round(sum(pairs) / n, 1) if n else None
    p50 = sorted(pairs)[n // 2] if n else None
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "n": n,
        "samples_ms": pairs[-40:],
        "avg_ms": avg,
        "p50_ms": p50,
        "label": f"exit_to_risk_freed_ms n={n} p50={p50} avg={avg}",
        "note": (
            "Exit signal → risk freed (ms). Observe only — never waive floors for speed."
        ),
    }


def fill_capacity_observe(
    root: str | None = None,
    *,
    bots: list | None = None,
    cfg: dict | None = None,
) -> dict:
    """Measure fill capacity: tip_books × prefetch_hit × free_risk. Observe only."""
    state = load_speed_kpi(root)
    rows = [r for r in (state.get("prefetch") or []) if isinstance(r, dict)]
    tip_books = sum(int(r.get("tip_books") or 0) for r in rows)
    hits = sum(1 for r in rows if r.get("prefetch_hit"))
    hit_rate = round(hits / len(rows), 4) if rows else None
    free_risk = None
    if bots is not None:
        cfg = cfg or {}
        desk_cap = _finite(cfg.get("max_open_risk")) or 100.0
        open_risk = sum(
            max(0.0, float(_finite(b.get("open_risk")) or 0.0))
            for b in bots if isinstance(b, dict)
        )
        free_risk = round(max(0.0, float(desk_cap) - open_risk), 4)
    else:
        frees = [_finite(r.get("free_risk")) for r in rows]
        frees = [f for f in frees if f is not None]
        free_risk = round(sum(frees) / len(frees), 4) if frees else None
    capacity = None
    if tip_books and hit_rate is not None and free_risk is not None:
        capacity = round(float(tip_books) * float(hit_rate) * float(free_risk), 4)
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "tip_books": tip_books,
        "prefetch_rows": len(rows),
        "prefetch_hits": hits,
        "prefetch_hit_rate": hit_rate,
        "free_risk": free_risk,
        "fill_capacity": capacity,
        "label": (
            f"fill_capacity tip_books={tip_books} hit={hit_rate} "
            f"free_risk={free_risk} → {capacity}"
        ),
        "note": (
            "Fill capacity observe = tip_books × prefetch_hit × free_risk. "
            "Never force buys; floors locked."
        ),
    }


# ---- Firm taxed M1 vs Σ tower M1 (#778–779 / #795) -------------------------

def firm_tower_m1_gap_alert(
    bots: list | None = None,
    *,
    fill_tax: float = 0.01,
    threshold: float = M1_GAP_ALERT_USD,
) -> dict:
    """Alert when |firm taxed M1 − Σ tower M1| > $1. Observe only."""
    try:
        import desk_roi_plan as drp
        firm = drp.firm_taxed_m1(bots, fill_tax=fill_tax)
    except Exception as exc:
        return {
            "paper_only": True,
            "fee_floors_locked": True,
            "observe_only": True,
            "alert": False,
            "ok": False,
            "reason": f"unavailable: {exc}",
        }
    by = [t for t in (firm.get("by_tower") or []) if isinstance(t, dict)]
    firm_m1 = _finite(firm.get("expectancy_taxed"))
    # Dollar totals for integrity reconciliation.
    firm_total = 0.0
    tower_totals = []
    for bot in bots or []:
        if not isinstance(bot, dict):
            continue
        bot_id = str(bot.get("id") or "")
        local = 0.0
        n = 0
        for h in bot.get("history") or []:
            if not isinstance(h, dict):
                continue
            p = _finite(h.get("pnl") if h.get("pnl") is not None else h.get("pnl_usd"))
            if p is None:
                continue
            contracts = _finite(h.get("contracts")) or 1.0
            taxed = p - float(fill_tax) * max(1.0, contracts)
            local += taxed
            firm_total += taxed
            n += 1
        if n:
            tower_totals.append({"bot": bot_id, "total_taxed": round(local, 4), "n": n})
    sum_tower_total = round(sum(t["total_taxed"] for t in tower_totals), 4)
    recon_gap = round(firm_total - sum_tower_total, 4)

    sum_tower_m1 = round(
        sum(float(_finite(t.get("expectancy_taxed")) or 0.0) for t in by),
        4,
    )
    firm_val = float(firm_m1) if firm_m1 is not None else 0.0
    m1_gap = round(firm_val - sum_tower_m1, 4)
    # Alert on either reconciliation integrity gap or M1 sum gap.
    thr = float(threshold)
    alert = abs(m1_gap) > thr + 1e-12 or abs(recon_gap) > thr + 1e-12
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "firm_m1": firm_m1,
        "sum_tower_m1": sum_tower_m1,
        "m1_gap": m1_gap,
        "firm_total_taxed": round(firm_total, 4),
        "sum_tower_total_taxed": sum_tower_total,
        "reconciliation_gap": recon_gap,
        "threshold_usd": thr,
        "by_tower": by,
        "alert": alert,
        "ok": not alert,
        "label": (
            f"firm_m1_gap={'ALERT' if alert else 'ok'} "
            f"firm={firm_m1} Σtower={sum_tower_m1} gap={m1_gap} "
            f"recon={recon_gap}"
        ),
        "note": (
            "Firm taxed M1 vs Σ tower M1 reconciliation — alert if |gap|>$1. "
            "Firm M1 > lonely tower vanity. Floors locked."
        ),
    }


# ---- M5 idle-pass vs BUDGET starvation (#663 / #694) -----------------------

def m5_idle_vs_budget_annotation(
    bot_id: str,
    *,
    util: float | None,
    open_risk: float,
    root: str | None = None,
    m5_lo: float = 0.15,
    m5_hi: float = 0.85,
) -> dict:
    """Distinguish M5 idle-pass from BUDGET-starvation on Masters tooltip."""
    bid = str(bot_id or "")
    util_f = _finite(util)
    risk = max(0.0, float(_finite(open_risk) or 0.0))
    budget_n = 0
    skip_n = 0
    top_code = None
    try:
        import desk_more
        board = desk_more.skip_leaderboard(root) if root is not None else {}
        if not isinstance(board, dict):
            board = {}
        by_bot = board.get("by_bot") if isinstance(board.get("by_bot"), dict) else {}
        bot_codes = by_bot.get(bid) if isinstance(by_bot.get(bid), dict) else {}
        # Prefer per-bot codes; fall back to firm stable_top when bot has no rows.
        if bot_codes:
            ranked = sorted(
                ((str(k), int(v)) for k, v in bot_codes.items()),
                key=lambda kv: -kv[1],
            )
            for code, n in ranked:
                stable = desk_more.stable_skip_code(code)
                skip_n += n
                if stable == "BUDGET" or code == "BUDGET":
                    budget_n += n
                if top_code is None and n > 0:
                    top_code = stable or code
        else:
            stable = board.get("stable_top") if isinstance(board.get("stable_top"), list) else []
            for row in stable:
                if not isinstance(row, dict):
                    continue
                code = str(row.get("code") or "")
                n = int(row.get("n") or 0)
                skip_n += n
                if code == "BUDGET":
                    budget_n += n
                if top_code is None and n > 0:
                    top_code = code
    except Exception:
        pass

    in_band = util_f is not None and float(m5_lo) <= float(util_f) <= float(m5_hi)
    budget_starved = bool(
        risk <= 1e-9
        and skip_n > 0
        and (budget_n >= max(1, skip_n // 2) or top_code == "BUDGET")
    )
    if in_band:
        annotation = "util_in_band"
        m5_pass = True
    elif risk <= 1e-9 and budget_starved:
        annotation = "BUDGET_starvation"
        # Still counts as M5 pass bit (util calm) but Masters must surface starvation.
        m5_pass = True
    elif risk <= 1e-9:
        annotation = "idle_pass"
        m5_pass = True
    else:
        annotation = "util_out_of_band"
        m5_pass = False

    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "bot": bid,
        "M5_tower_util": util_f,
        "open_risk": round(risk, 4),
        "m5_pass": m5_pass,
        "m5_annotation": annotation,
        "budget_skip_n": budget_n,
        "skip_n": skip_n,
        "top_skip": top_code,
        "tooltip": (
            f"M5 {annotation}"
            + (f" (BUDGET skips={budget_n}/{skip_n})" if budget_starved else "")
        ),
        "note": (
            "M5 idle-pass must not hide BUDGET starvation — annotate on Masters. "
            "Never soften floors to chase util."
        ),
    }


# ---- Distance-to-zero stance tags (#733) -----------------------------------

def distance_to_zero_stance(
    *,
    now_pnl: float | None,
    bots: list | None = None,
) -> dict:
    """Recommended stance: bleed_stop | fee_clear_earn | idle (never force buys)."""
    fee_today = 0.0
    loser_today = 0.0
    for bot in bots or []:
        if not isinstance(bot, dict):
            continue
        bid = str(bot.get("id") or "")
        today = _finite(bot.get("today"))
        if today is None:
            today = _finite(bot.get("realized")) or 0.0
        if bid in FEE_CLEAR:
            fee_today += float(today)
        elif bid in LOSER_TOWERS:
            loser_today += float(today)
    pnl = float(_finite(now_pnl) or 0.0)
    if loser_today < -1.0 or (pnl < 0 and loser_today < -0.25):
        stance = "bleed_stop"
    elif fee_today > 0.5:
        stance = "fee_clear_earn"
    else:
        stance = "idle"
    return {
        "recommended_stance": stance,
        "fee_clear_today": round(fee_today, 4),
        "loser_today": round(loser_today, 4),
        "force_buys": False,
        "note": (
            "Stance tags only — bleed_stop | fee_clear_earn | idle. Never force buys."
        ),
    }
