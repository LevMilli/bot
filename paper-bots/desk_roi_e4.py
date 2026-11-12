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
HELPER_ADVICE_LOG_NAME = "desk_helper_advice_log.json"
FILL_TAX_DEFAULT = 0.01
FIT_JOURNAL = "desk_fit_journal.json"
MAX_ADVICE_LOG_ROWS = 4000
ADVICE_DECISIONS = frozenset({"accept", "reject"})

LOCKED_VENUE_FLOORS = {
    "kalshi_sports": 0.06,
    "kalshi_btc15m": 0.05,
    "kalshi_commodity15m": 0.05,
    "kalshi_inx": 0.02,
    "solana_dex": 0.02,
    "coinbase_spot": 0.05,
    "binance_btc_carry": 0.02,
    "kalshi_econ": 0.05,
    "equity_qqq": 0.02,
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


def gate_a_pilot_sports_clv(root: str | None = None) -> dict:
    """Second Gate A pilot densify (#892): clv_closer tags on sports-gap.

    Observe only — never staff-arms autonomy. Floors locked.
    """
    try:
        import desk_roi_plan as drp
        gate = drp.helper_gate_a(root, "clv_closer")
    except Exception:
        gate = {"ready": False, "n": 0, "n_to_ready": HELPER_GATE_A_MIN_N}
    store = _load(_path(HELPER_FILLS_NAME, root), {"paper_only": True, "rows": []})
    rows = [r for r in (store.get("rows") or []) if isinstance(r, dict)]
    clv_sports = [
        r for r in rows
        if str(r.get("helper") or "") in ("clv_closer", "clv", "sports_clv")
        and str(r.get("bot") or "") in ("sports-gap", "sports")
    ]
    taxed = []
    for r in clv_sports:
        pt = _finite(r.get("pnl_taxed"))
        if pt is not None:
            taxed.append(float(pt))
            continue
        pnl = _finite(r.get("pnl"))
        if pnl is None:
            continue
        n_c = _finite(r.get("contracts")) or 1.0
        taxed.append(float(pnl) - FILL_TAX_DEFAULT * max(1.0, n_c))
    n = len(taxed)
    exp = round(sum(taxed) / n, 4) if n else None
    min_n = int(HELPER_GATE_A_MIN_N)
    sports_all = [
        r for r in rows
        if str(r.get("bot") or "") in ("sports-gap", "sports")
    ]
    coverage = round(n / len(sports_all), 4) if sports_all else None
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "places_orders": False,
        "staff_arm": False,
        "helper": "clv_closer",
        "bot": "sports-gap",
        "n": n,
        "n_to_ready": max(0, min_n - n),
        "min_n": min_n,
        "taxed_ev": exp,
        "coverage_pct": None if coverage is None else round(coverage * 100.0, 2),
        "coverage": coverage,
        "gate_a": gate,
        "ready": bool(n >= min_n and exp is not None and exp + 1e-12 >= 0.0),
        "label": (
            f"gate_a_pilot sports/clv n={n}/{min_n} ev={exp} "
            f"cov={None if coverage is None else round(coverage * 100.0, 1)}% "
            "(observe · no staff arm)"
        ),
        "note": (
            "Gate A pilot densify on sports-gap clv_closer tags (#892). "
            "Observe only — never staff-arms autonomy."
        ),
    }


def gate_a_pilots_board(root: str | None = None) -> dict:
    """Combined Gate A pilot board (btc/calendar + sports/clv)."""
    btc = gate_a_pilot_btc_calendar(root)
    sports = gate_a_pilot_sports_clv(root)
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "staff_arm": False,
        "btc_calendar": btc,
        "sports_clv": sports,
        "any_ready": bool(btc.get("ready") or sports.get("ready")),
        "label": (
            f"gate_a_pilots btc_ready={bool(btc.get('ready'))} "
            f"sports_ready={bool(sports.get('ready'))}"
        ),
        "note": "Combined Gate A pilots — observe only; never auto-arm.",
    }


# ---- Helper advice accept/reject log (#897) --------------------------------

def record_helper_advice_decision(
    root: str | None,
    *,
    helper: str,
    bot: str = "",
    decision: str,
    reason: str = "",
    advice: dict | None = None,
    ticker: str = "",
) -> dict:
    """Append one accept/reject of helper advice on a main (observe journal).

    Rejects soften-floor advice via validate_helper_advice. Never places fills.
    """
    dec = str(decision or "").strip().lower()
    if dec not in ADVICE_DECISIONS:
        return {
            "ok": False,
            "reason": "decision must be accept|reject",
            "paper_only": True,
            "fee_floors_locked": True,
        }
    helper_id = str(helper or "").strip()
    if not helper_id:
        return {
            "ok": False,
            "reason": "helper required",
            "paper_only": True,
            "fee_floors_locked": True,
        }
    schema_ok = True
    schema_reason = ""
    if isinstance(advice, dict) and advice:
        try:
            from helpers.advice_schema import validate_helper_advice
            schema_ok, schema_reason = validate_helper_advice(advice)
        except Exception as exc:  # noqa: BLE001
            schema_ok, schema_reason = False, type(exc).__name__
        if not schema_ok and dec == "accept":
            return {
                "ok": False,
                "reason": f"refuse accept — advice schema: {schema_reason}",
                "paper_only": True,
                "fee_floors_locked": True,
                "schema_ok": False,
            }
    path = _path(HELPER_ADVICE_LOG_NAME, root)
    store = _load(path, {"paper_only": True, "rows": [], "fee_floors_locked": True})
    row = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "helper": helper_id[:64],
        "bot": str(bot or "")[:32],
        "ticker": str(ticker or "")[:64],
        "decision": dec,
        "reason": str(reason or "")[:200],
        "schema_ok": schema_ok,
        "schema_reason": str(schema_reason or "")[:120],
        "paper_only": True,
        "fee_floors_locked": True,
        "may_place_alone": False,
    }
    rows = [r for r in (store.get("rows") or []) if isinstance(r, dict)]
    rows.append(row)
    store["rows"] = rows[-MAX_ADVICE_LOG_ROWS:]
    store["last_at"] = row["at"]
    store["paper_only"] = True
    store["fee_floors_locked"] = True
    tmp = path + ".tmp"
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    import json
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(store, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)
    return {"ok": True, "row": row, "n": len(store["rows"]), "paper_only": True}


def helper_advice_log_board(root: str | None = None) -> dict:
    """Observe board for helper advice accept/reject journal (#897)."""
    store = _load(
        _path(HELPER_ADVICE_LOG_NAME, root),
        {"paper_only": True, "rows": [], "fee_floors_locked": True},
    )
    rows = [r for r in (store.get("rows") or []) if isinstance(r, dict)]
    accepts = sum(1 for r in rows if r.get("decision") == "accept")
    rejects = sum(1 for r in rows if r.get("decision") == "reject")
    by_helper: dict[str, dict] = {}
    for r in rows:
        h = str(r.get("helper") or "") or "?"
        bucket = by_helper.setdefault(h, {"helper": h, "accept": 0, "reject": 0})
        if r.get("decision") == "accept":
            bucket["accept"] += 1
        elif r.get("decision") == "reject":
            bucket["reject"] += 1
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "n": len(rows),
        "accept_n": accepts,
        "reject_n": rejects,
        "accept_rate": round(accepts / len(rows), 4) if rows else None,
        "by_helper": sorted(by_helper.values(), key=lambda x: -(x["accept"] + x["reject"])),
        "recent": rows[-12:],
        "label": f"helper advice log n={len(rows)} accept={accepts} reject={rejects}",
        "note": (
            "Mains log accept/reject of helper advice (#897). "
            "Accept requires floors_locked schema. Never places fills."
        ),
    }


def _fill_taxed(row: dict) -> float | None:
    pt = _finite(row.get("pnl_taxed"))
    if pt is not None:
        return float(pt)
    pnl = _finite(row.get("pnl"))
    if pnl is None:
        return None
    n_c = _finite(row.get("contracts")) or 1.0
    return float(pnl) - FILL_TAX_DEFAULT * max(1.0, n_c)


def _last_advice_decision(
    advice_rows: list[dict],
    *,
    helper: str,
    bot: str,
    at: str,
) -> str:
    """Most recent accept|reject for helper(+bot) at or before fill timestamp."""
    helper_id = str(helper or "")
    bot_id = str(bot or "")
    stamp = str(at or "")
    last = ""
    for row in advice_rows:
        if str(row.get("helper") or "") != helper_id:
            continue
        row_bot = str(row.get("bot") or "")
        if bot_id and row_bot and row_bot != bot_id:
            continue
        row_at = str(row.get("at") or "")
        if stamp and row_at and row_at > stamp:
            continue
        dec = str(row.get("decision") or "").strip().lower()
        if dec in ADVICE_DECISIONS:
            last = dec
    return last


def helper_advice_lift_board(root: str | None = None) -> dict:
    """Measure insight advice lift on taxed EV along the Gate A path (#898).

    Join advice accept/reject journal with helper-attributed fills. Observe only —
    never places fills, never staff-arms, never softens floors.
    """
    advice_store = _load(
        _path(HELPER_ADVICE_LOG_NAME, root),
        {"paper_only": True, "rows": [], "fee_floors_locked": True},
    )
    fill_store = _load(
        _path(HELPER_FILLS_NAME, root),
        {"paper_only": True, "rows": []},
    )
    advice_rows = sorted(
        [r for r in (advice_store.get("rows") or []) if isinstance(r, dict)],
        key=lambda r: str(r.get("at") or ""),
    )
    fill_rows = [r for r in (fill_store.get("rows") or []) if isinstance(r, dict)]

    buckets: dict[str, list[float]] = {"accept": [], "reject": [], "none": []}
    by_helper: dict[str, dict] = {}
    linked = 0
    for fill in fill_rows:
        taxed = _fill_taxed(fill)
        if taxed is None:
            continue
        helper = str(fill.get("helper") or "")
        bot = str(fill.get("bot") or "")
        state = _last_advice_decision(
            advice_rows, helper=helper, bot=bot, at=str(fill.get("at") or ""),
        ) or "none"
        if state not in buckets:
            state = "none"
        buckets[state].append(float(taxed))
        if state in ADVICE_DECISIONS:
            linked += 1
        h = helper or "?"
        slot = by_helper.setdefault(
            h,
            {
                "helper": h,
                "accept_n": 0,
                "reject_n": 0,
                "none_n": 0,
                "accept_ev": None,
                "reject_ev": None,
                "lift": None,
                "_accept": [],
                "_reject": [],
            },
        )
        if state == "accept":
            slot["accept_n"] += 1
            slot["_accept"].append(float(taxed))
        elif state == "reject":
            slot["reject_n"] += 1
            slot["_reject"].append(float(taxed))
        else:
            slot["none_n"] += 1

    def _mean(xs: list[float]) -> float | None:
        return round(sum(xs) / len(xs), 4) if xs else None

    accept_ev = _mean(buckets["accept"])
    reject_ev = _mean(buckets["reject"])
    none_ev = _mean(buckets["none"])
    lift = None
    if accept_ev is not None and reject_ev is not None:
        lift = round(accept_ev - reject_ev, 4)
    elif accept_ev is not None and none_ev is not None:
        lift = round(accept_ev - none_ev, 4)

    helper_rows = []
    for slot in by_helper.values():
        a = slot.pop("_accept")
        r = slot.pop("_reject")
        slot["accept_ev"] = _mean(a)
        slot["reject_ev"] = _mean(r)
        if slot["accept_ev"] is not None and slot["reject_ev"] is not None:
            slot["lift"] = round(slot["accept_ev"] - slot["reject_ev"], 4)
        helper_rows.append(slot)
    helper_rows.sort(
        key=lambda x: (
            -(x["accept_n"] + x["reject_n"] + x["none_n"]),
            str(x.get("helper") or ""),
        ),
    )

    thin = len(buckets["accept"]) < 5 or (
        len(buckets["reject"]) < 5 and len(buckets["none"]) < 5
    )
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "staff_arm": False,
        "places_orders": False,
        "advice_n": len(advice_rows),
        "fill_n": len(fill_rows),
        "linked_n": linked,
        "accept_n": len(buckets["accept"]),
        "reject_n": len(buckets["reject"]),
        "none_n": len(buckets["none"]),
        "accept_ev": accept_ev,
        "reject_ev": reject_ev,
        "none_ev": none_ev,
        "lift": lift,
        "evidence_thin": thin,
        "by_helper": helper_rows[:24],
        "gate_a_path": True,
        "label": (
            f"advice_lift lift={lift} accept_n={len(buckets['accept'])} "
            f"reject_n={len(buckets['reject'])} "
            f"{'THIN' if thin else 'ok'} (observe · Gate A path)"
        ),
        "note": (
            "Insight advice lift on helper-fill taxed EV (#898). "
            "Accept vs reject (else vs untagged). Observe only — never arms."
        ),
    }


# Forbidden execution tokens inside helpers/ (#899–900). Digest writers only.
INSIGHT_HELPER_EXEC_FORBIDDEN = (
    "paper_buy(",
    "paper_sell(",
    "paper_buy =",
    "paper_sell =",
    "def paper_buy",
    "def paper_sell",
)
INSIGHT_HELPER_OPEN_WRITE_FORBIDDEN = (
    '["opens"].append',
    "['opens'].append",
    '.get("opens", []).append',
    ".get('opens', []).append",
)
INSIGHT_HELPER_SCAN_SKIP = frozenset({
    "__init__.py",
    "advice_schema.py",  # schema only; no execution
})


def insight_helpers_execution_lock(root: str | None = None) -> dict:
    """#899/#900: insight helpers must not write opens or call paper_buy/sell.

    Static scan of helpers/*.py. Observe / assert only — never places.
    """
    helpers_dir = os.path.join(_root(root), "helpers")
    violations: list[dict] = []
    scanned = 0
    if os.path.isdir(helpers_dir):
        for name in sorted(os.listdir(helpers_dir)):
            if not name.endswith(".py") or name in INSIGHT_HELPER_SCAN_SKIP:
                continue
            path = os.path.join(helpers_dir, name)
            if not os.path.isfile(path):
                continue
            scanned += 1
            try:
                with open(path, encoding="utf-8") as handle:
                    body = handle.read()
            except OSError:
                continue
            for token in INSIGHT_HELPER_EXEC_FORBIDDEN:
                if token in body:
                    violations.append({
                        "helper": name,
                        "rule": "no_paper_buy_sell",
                        "token": token,
                        "plan": "#900",
                    })
            for token in INSIGHT_HELPER_OPEN_WRITE_FORBIDDEN:
                if token in body:
                    violations.append({
                        "helper": name,
                        "rule": "no_opens_write",
                        "token": token,
                        "plan": "#899",
                    })
    ok = not violations
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "places_orders": False,
        "may_place_alone": False,
        "ok": ok,
        "pass": ok,
        "scanned_n": scanned,
        "violation_n": len(violations),
        "violations": violations[:40],
        "label": (
            f"insight_exec_lock ok={ok} scanned={scanned} "
            f"violations={len(violations)} (#899/#900)"
        ),
        "note": (
            "Insight helpers must not write paper_state opens (#899) or call "
            "paper_buy/paper_sell (#900). Digest/observe only."
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
