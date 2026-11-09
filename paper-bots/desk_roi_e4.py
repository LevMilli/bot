"""
desk_roi_e4.py — E3–E4 money-path boards (selective kill, tip funnel, Gate A pilot,
eligible-fill / throughput vs M1).

Imported and re-exported by desk_roi_plan. Paper only. Fee floors locked.
Never softens venue min_edge. Never arms LIVE_ORDERS. No tip invent.
"""
from __future__ import annotations

import math
import os
import time
from typing import Any

SELECTIVE_ATTEMPT_NAME = "desk_selective_attempts.json"
SELECTIVE_KILL_NAME = "desk_selective_kill.json"
TIP_FUNNEL_NAME = "desk_tip_funnel.json"

SELECTIVE_KILL_GREEN_DAYS = 5
SELECTIVE_ATTEMPT_MAX = 4000
MAX_TIP_FUNNEL_ROWS = 8000
TIP_FUNNEL_LEAGUES = ("NFL", "NCAAF", "NBA", "WNBA", "MLB", "NHL")
TIP_FUNNEL_STAGES = (
    "games_seen", "fee_clear", "sized", "bought", "block_budget", "block_edge",
)
FEE_CLEAR = ("sports-gap", "btc15m", "commodity-15m")
HELPER_GATE_A_MIN_N = 20
HELPER_FILLS_NAME = "desk_helper_fills.json"
FILL_TAX_DEFAULT = 0.01
FIT_JOURNAL = "desk_fit_journal.json"

LOCKED_VENUE_FLOORS = {
    "kalshi_sports": 0.06,
    "kalshi_btc15m": 0.05,
    "kalshi_commodity15m": 0.05,
    "kalshi_inx": 0.02,
    "solana_dex": 0.02,
    "coinbase_spot": 0.05,
    "binance_btc_carry": 0.02,
    "kalshi_econ": 0.05,
}

INCUBATION_IDEA_BANK_ONLY = frozenset({
    "weather", "econ", "economy", "economics", "polymarket", "poly",
})
INCUBATION_IDEA_BANK_PREFIXES = (
    "KXHIGHTEMP", "KXLOWTEMP", "KXTEMP", "KXWEATHER", "KXHURRICANE",
    "KXGDP", "KXGPD", "KXECON", "KXCPI", "KXPPI", "KXJOB", "KXUNEMP",
    "KXFED", "KXRATES", "POLY", "PM-",
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
    import json
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        pass
    return dict(empty)


def _save(path: str, state: dict) -> None:
    import json
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _chicago_day() -> str:
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d")
    except Exception:
        return time.strftime("%Y-%m-%d", time.gmtime())


def _series_key(series: str | None) -> str:
    return str(series or "").strip().upper()


# ---- Selective +1 attempt journal + 5-green-day kill ------------------------

def _selective_attempt_store(root: str | None = None) -> dict:
    return _load(
        _path(SELECTIVE_ATTEMPT_NAME, root),
        {"paper_only": True, "rows": [], "by_bot": {}},
    )


def _selective_kill_store(root: str | None = None) -> dict:
    return _load(
        _path(SELECTIVE_KILL_NAME, root),
        {"paper_only": True, "green_days": {}, "killed": {}},
    )


def note_selective_green_day(
    root: str | None,
    bot: str,
    *,
    taxed_ev,
) -> dict:
    """Upsert one Chicago green-day taxed-EV card per fee-clear tower."""
    bot_id = str(bot or "").strip()
    ev = _finite(taxed_ev)
    if not bot_id or ev is None or ev + 1e-12 < 0.0:
        return {"recorded": False, "reason": "need green taxed_ev ≥ 0"}
    if bot_id not in FEE_CLEAR:
        return {"recorded": False, "reason": "fee-clear towers only"}
    day = _chicago_day()
    path = _path(SELECTIVE_KILL_NAME, root)
    store = _selective_kill_store(root)
    green = store.get("green_days") if isinstance(store.get("green_days"), dict) else {}
    days = [d for d in (green.get(bot_id) or []) if isinstance(d, dict)]
    found = False
    for d in days:
        if str(d.get("day") or "") == day:
            d["taxed_ev"] = round(float(ev), 4)
            d["at"] = _now()
            found = True
            break
    if not found:
        days.append({
            "day": day,
            "taxed_ev": round(float(ev), 4),
            "at": _now(),
            "paper_only": True,
        })
    days = sorted(days, key=lambda d: str(d.get("day") or ""))[-60:]
    green[bot_id] = days
    store["green_days"] = green
    store["paper_only"] = True
    store["fee_floors_locked"] = True
    _save(path, store)
    return {"recorded": True, "bot": bot_id, "day": day, "taxed_ev": round(float(ev), 4)}


def record_selective_attempt(
    root: str | None,
    bot: str,
    *,
    edge=None,
    z=None,
    depth=None,
    league: str | None = None,
    today=None,
    boosted: bool = False,
    note: str = "",
) -> dict:
    """Log every selective +1 attempt (edge/z/depth). Paper only; never softens floors."""
    bot_id = str(bot or "").strip()
    if not bot_id:
        return {"recorded": False, "reason": "bot required"}
    row = {
        "at": _now(),
        "chicago_day": _chicago_day(),
        "bot": bot_id[:40],
        "edge": _finite(edge),
        "z": _finite(z),
        "depth": _finite(depth),
        "league": str(league or "")[:20] or None,
        "today": _finite(today),
        "boosted": bool(boosted),
        "note": str(note or "")[:120],
        "paper_only": True,
        "fee_floors_locked": True,
    }
    path = _path(SELECTIVE_ATTEMPT_NAME, root)
    store = _selective_attempt_store(root)
    rows = list(store.get("rows") or [])
    rows.append(row)
    store["rows"] = rows[-SELECTIVE_ATTEMPT_MAX:]
    by = store.get("by_bot") if isinstance(store.get("by_bot"), dict) else {}
    brow = list(by.get(bot_id) or [])
    brow.append(row)
    by[bot_id] = brow[-800:]
    store["by_bot"] = by
    store["last_at"] = row["at"]
    store["paper_only"] = True
    _save(path, store)
    today_n = _finite(today)
    if today_n is not None and today_n + 1e-12 >= 0.0:
        note_selective_green_day(root, bot_id, taxed_ev=today_n)
    return {"recorded": True, "row": row}


def selective_kill_status(
    root: str | None = None,
    *,
    bots: list | None = None,
) -> dict:
    """Kill selective +1 when tower taxed EV worsens over 5 green Chicago days vs prior 5."""
    if bots:
        for bot in bots:
            if not isinstance(bot, dict):
                continue
            bid = str(bot.get("id") or "")
            today = _finite(bot.get("today"))
            if bid in FEE_CLEAR and today is not None and today + 1e-12 >= 0.0:
                note_selective_green_day(root, bid, taxed_ev=today)
    store = _selective_kill_store(root)
    green = store.get("green_days") if isinstance(store.get("green_days"), dict) else {}
    killed_map = store.get("killed") if isinstance(store.get("killed"), dict) else {}
    by_bot = {}
    any_killed = False
    need = SELECTIVE_KILL_GREEN_DAYS
    for bot_id in FEE_CLEAR:
        days = [
            d for d in (green.get(bot_id) or [])
            if isinstance(d, dict) and _finite(d.get("taxed_ev")) is not None
        ]
        days = sorted(days, key=lambda d: str(d.get("day") or ""))
        cur = days[-need:] if len(days) >= need else []
        prior = days[-(2 * need):-need] if len(days) >= 2 * need else []
        cur_vals = [float(_finite(d.get("taxed_ev")) or 0) for d in cur]
        prior_vals = [float(_finite(d.get("taxed_ev")) or 0) for d in prior]
        cur_mean = round(sum(cur_vals) / len(cur_vals), 4) if cur_vals else None
        prior_mean = round(sum(prior_vals) / len(prior_vals), 4) if prior_vals else None
        ready = len(cur_vals) >= need and len(prior_vals) >= need
        killed = bool(
            ready
            and cur_mean is not None
            and prior_mean is not None
            and cur_mean < prior_mean - 1e-12
        )
        if killed:
            any_killed = True
            killed_map[bot_id] = {
                "at": _now(),
                "cur_mean": cur_mean,
                "prior_mean": prior_mean,
                "green_n": len(days),
                "reason": (
                    f"taxed EV worsened over {need} green days "
                    f"({cur_mean} < prior {prior_mean})"
                ),
            }
        elif bot_id in killed_map and not killed:
            killed_map.pop(bot_id, None)
        by_bot[bot_id] = {
            "bot": bot_id,
            "killed": killed,
            "green_n": len(days),
            "need_green": need * 2,
            "cur_mean": cur_mean,
            "prior_mean": prior_mean,
            "ready": ready,
            "fee_floors_locked": True,
        }
    store["killed"] = killed_map
    store["last_at"] = _now()
    store["paper_only"] = True
    store["fee_floors_locked"] = True
    _save(_path(SELECTIVE_KILL_NAME, root), store)
    attempts = _selective_attempt_store(root)
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": False,
        "auto_promote": False,
        "live_orders_enabled": False,
        "killed": any_killed,
        "killed_bots": sorted(killed_map.keys()),
        "by_bot": by_bot,
        "green_window": need,
        "attempts_n": len(list(attempts.get("rows") or [])),
        "label": (
            f"selective_kill={'ON' if any_killed else 'off'} "
            f"bots={','.join(sorted(killed_map.keys())) or 'none'} "
            f"attempts={len(list(attempts.get('rows') or []))}"
        ),
        "note": (
            f"Selective +1 kill when tower taxed EV worsens over {need} green "
            "Chicago days vs prior window. Force base max_buys only when killed. "
            "Floors locked."
        ),
    }


def selective_kill_active(root: str | None, bot: str) -> bool:
    """True when this tower's selective +1 is killed (use base max_buys only)."""
    st = selective_kill_status(root)
    row = (st.get("by_bot") or {}).get(str(bot or ""))
    return bool(isinstance(row, dict) and row.get("killed"))


# ---- Tip-window fill funnels per league ------------------------------------

def record_tip_funnel(root: str | None, league: str, stage: str) -> dict:
    """Count tip-window funnel stage for one league (NFL…NHL)."""
    lg = str(league or "").strip().upper()
    st = str(stage or "").strip().lower()
    if lg not in TIP_FUNNEL_LEAGUES:
        return {"recorded": False, "reason": f"league not tracked ({lg})"}
    if st not in TIP_FUNNEL_STAGES:
        return {"recorded": False, "reason": f"unknown stage ({st})"}
    path = _path(TIP_FUNNEL_NAME, root)
    store = _load(path, {"paper_only": True, "rows": [], "by_league": {}})
    row = {
        "at": _now(),
        "chicago_day": _chicago_day(),
        "league": lg,
        "stage": st,
        "paper_only": True,
        "fee_floors_locked": True,
    }
    rows = list(store.get("rows") or [])
    rows.append(row)
    store["rows"] = rows[-MAX_TIP_FUNNEL_ROWS:]
    by = store.get("by_league") if isinstance(store.get("by_league"), dict) else {}
    lg_row = by.get(lg) if isinstance(by.get(lg), dict) else {
        "league": lg, **{s: 0 for s in TIP_FUNNEL_STAGES},
    }
    lg_row[st] = int(lg_row.get(st) or 0) + 1
    lg_row["league"] = lg
    by[lg] = lg_row
    store["by_league"] = by
    store["last_at"] = row["at"]
    store["paper_only"] = True
    _save(path, store)
    return {"recorded": True, "league": lg, "stage": st, "count": lg_row[st]}


def tip_funnel_board(root: str | None = None) -> dict:
    store = _load(_path(TIP_FUNNEL_NAME, root), {"paper_only": True, "rows": [], "by_league": {}})
    by = store.get("by_league") if isinstance(store.get("by_league"), dict) else {}
    leagues = []
    for lg in TIP_FUNNEL_LEAGUES:
        row = by.get(lg) if isinstance(by.get(lg), dict) else {}
        counts = {s: int(row.get(s) or 0) for s in TIP_FUNNEL_STAGES}
        seen = counts["games_seen"]
        bought = counts["bought"]
        block_sum = counts["block_budget"] + counts["block_edge"]
        leagues.append({
            "league": lg,
            **counts,
            "buy_rate": round(bought / seen, 4) if seen else None,
            "budget_share": (
                round(counts["block_budget"] / block_sum, 4) if block_sum else None
            ),
        })
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "stages": list(TIP_FUNNEL_STAGES),
        "leagues": leagues,
        "rows_n": len(list(store.get("rows") or [])),
        "label": (
            "tip_funnel "
            + " ".join(
                f"{r['league']}={r['bought']}/{r['games_seen']}"
                for r in leagues if r["games_seen"] or r["bought"]
            )
            or "tip_funnel empty"
        ),
        "note": (
            "Tip-window fill funnel per league: games_seen → fee_clear → sized → bought; "
            "block_budget vs block_edge share. Floors locked."
        ),
    }


# ---- Gate A pilot densify (btc15m calendar_scanner) -------------------------

def gate_a_pilot_btc_calendar(root: str | None = None) -> dict:
    """Pilot densify: calendar_scanner attributions on btc15m (observe; no staff arm)."""
    try:
        import desk_roi_plan as drp
        gate = drp.helper_gate_a(root, "calendar_scanner")
    except Exception:
        gate = {"ready": False, "n": 0, "n_to_ready": HELPER_GATE_A_MIN_N}
    store = _load(_path(HELPER_FILLS_NAME, root), {"paper_only": True, "rows": []})
    rows = [r for r in (store.get("rows") or []) if isinstance(r, dict)]
    cal_btc = [
        r for r in rows
        if str(r.get("helper") or "") == "calendar_scanner"
        and str(r.get("bot") or "") == "btc15m"
    ]
    taxed = []
    for r in cal_btc:
        pt = _finite(r.get("pnl_taxed"))
        if pt is not None:
            taxed.append(float(pt))
            continue
        pnl = _finite(r.get("pnl"))
        if pnl is None:
            continue
        n = _finite(r.get("contracts")) or 1.0
        taxed.append(float(pnl) - FILL_TAX_DEFAULT * max(1.0, n))
    n = len(taxed)
    exp = round(sum(taxed) / n, 4) if n else None
    min_n = int(HELPER_GATE_A_MIN_N)
    btc_all = [r for r in rows if str(r.get("bot") or "") == "btc15m"]
    coverage = round(n / len(btc_all), 4) if btc_all else None
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "places_orders": False,
        "staff_arm": False,
        "helper": "calendar_scanner",
        "bot": "btc15m",
        "n": n,
        "n_to_ready": max(0, min_n - n),
        "min_n": min_n,
        "taxed_ev": exp,
        "coverage_pct": None if coverage is None else round(coverage * 100.0, 2),
        "coverage": coverage,
        "gate_a": gate,
        "ready": bool(n >= min_n and exp is not None and exp + 1e-12 >= 0.0),
        "label": (
            f"gate_a_pilot btc/calendar n={n}/{min_n} ev={exp} "
            f"cov={None if coverage is None else round(coverage * 100.0, 1)}% "
            "(observe · no staff arm)"
        ),
        "note": (
            "Gate A pilot densify on btc15m calendar_scanner tags. "
            "Observe only — never staff-arms autonomy."
        ),
    }


# ---- Eligible-fill funnel + throughput vs M1 -------------------------------

def eligible_fill_funnel(root: str | None = None, bots: list | None = None) -> dict:
    """Eligible (= fee-clear + floor + green-day rules) buys vs all buys."""
    fit = _load(_path(FIT_JOURNAL, root), {"paper_only": True, "rows": []})
    rows = [r for r in (fit.get("rows") or []) if isinstance(r, dict)]
    by_bot: dict[str, dict] = {}
    weekday_eligible = 0
    weekday_all = 0
    for r in rows:
        bot = str(r.get("bot") or "")
        if not bot:
            continue
        outcome = str(r.get("outcome") or "")
        is_buy = outcome == "buy"
        is_fit = outcome in ("fit", "buy", "block")
        if not is_fit:
            continue
        day = str(r.get("chicago_day") or r.get("at") or "")[:10]
        is_weekday = True
        try:
            from datetime import datetime
            if len(day) >= 10:
                d = datetime.strptime(day[:10], "%Y-%m-%d")
                is_weekday = d.weekday() < 5
        except Exception:
            is_weekday = True
        slot = by_bot.setdefault(bot, {
            "bot": bot,
            "all_buys": 0,
            "eligible_buys": 0,
            "fits": 0,
            "blocks": 0,
            "fee_clear": bot in FEE_CLEAR,
        })
        slot["fits"] += 1
        if outcome == "block":
            slot["blocks"] += 1
        if is_buy:
            slot["all_buys"] += 1
            if is_weekday:
                weekday_all += 1
            if bot in FEE_CLEAR:
                slot["eligible_buys"] += 1
                if is_weekday:
                    weekday_eligible += 1
    towers = sorted(by_bot.values(), key=lambda r: (-int(r["eligible_buys"]), r["bot"]))
    try:
        import desk_roi_plan as drp
        m1 = drp.firm_taxed_m1(bots)
    except Exception:
        m1 = {"expectancy_taxed": None, "n": 0}
    elig = sum(int(t["eligible_buys"]) for t in towers)
    all_b = sum(int(t["all_buys"]) for t in towers)
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "towers": towers,
        "eligible_buys": elig,
        "all_buys": all_b,
        "weekday_eligible_buys": weekday_eligible,
        "weekday_all_buys": weekday_all,
        "eligible_share": round(elig / all_b, 4) if all_b else None,
        "m1": m1.get("expectancy_taxed"),
        "m1_n": m1.get("n"),
        "label": f"eligible_fill {elig}/{all_b} weekday={weekday_eligible}/{weekday_all}",
        "note": (
            "Eligible fills = fee-clear buys under locked floors + green-day rules. "
            "Secondary to M1 — never softer floors."
        ),
    }


def throughput_vs_m1_board(
    root: str | None = None,
    *,
    bots: list | None = None,
) -> dict:
    """Throughput scoreboard secondary to firm M1 — publish both."""
    funnel = eligible_fill_funnel(root, bots=bots)
    try:
        import desk_roi_plan as drp
        m1 = drp.firm_taxed_m1(bots)
        selective = drp.selective_throughput_observe(root, bots=bots)
    except Exception:
        m1 = {"expectancy_taxed": None, "n": 0}
        selective = {"boosted_n": 0}
    kill = selective_kill_status(root, bots=bots)
    firm_exp = _finite(m1.get("expectancy_taxed"))
    m1_holds = int(m1.get("n") or 0) >= 10 and firm_exp is not None and firm_exp + 1e-12 >= 0.0
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "live_orders_enabled": False,
        "primary": "M1",
        "m1": firm_exp,
        "m1_n": m1.get("n"),
        "m1_holds": m1_holds,
        "secondary": "eligible_fills",
        "eligible_buys": funnel.get("eligible_buys"),
        "all_buys": funnel.get("all_buys"),
        "weekday_eligible_buys": funnel.get("weekday_eligible_buys"),
        "eligible_share": funnel.get("eligible_share"),
        "selective_boosted_n": selective.get("boosted_n"),
        "selective_kill": {
            "killed": kill.get("killed"),
            "killed_bots": kill.get("killed_bots"),
            "label": kill.get("label"),
        },
        "funnel": funnel,
        "label": (
            f"throughput_vs_m1 m1={'hold' if m1_holds else 'thin'} "
            f"ev={firm_exp} eligible={funnel.get('eligible_buys')}/"
            f"{funnel.get('all_buys')} "
            f"(M1 primary · fills secondary)"
        ),
        "note": (
            "Throughput scoreboard is secondary to M1. "
            "If eligible fills↑ and M1↓ → kill lever. Floors locked."
        ),
    }


# ---- Incubation idea-bank blocks (weather/econ/Polymarket) ------------------

def incubation_idea_bank_only(series: str | None) -> bool:
    """True when series/category is weather/econ/Polymarket — idea bank only."""
    raw = str(series or "").strip()
    if not raw:
        return False
    low = raw.lower()
    if low in INCUBATION_IDEA_BANK_ONLY:
        return True
    key = _series_key(series)
    if not key:
        return False
    for prefix in INCUBATION_IDEA_BANK_PREFIXES:
        if key.startswith(str(prefix).upper()):
            return True
    for token in ("weather", "econ", "economy", "economics", "polymarket"):
        if low == token or low.startswith(token + "/") or low.startswith(token + ":"):
            return True
    return False


def incubation_blocks_auto(series: str | None) -> str:
    """Non-empty when series must not enter main AUTO (idea-bank only)."""
    if incubation_idea_bank_only(series):
        key = _series_key(series) or str(series or "").strip()
        return (
            f"incubation idea-bank only: {key} "
            "(weather/econ/Polymarket) — refuse main AUTO"
        )
    return ""
