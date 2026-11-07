"""
desk_roi_e5e7.py — E5–E7 densify boards (eligible weekly funnel, insight:betting
ratio, edge08 vs main expectancy, fee-clear cadence health, lock helpers).

NEW boards only — does not rewrite PR #354/#355/#356 surfaces.
Paper only. Fee floors locked. Soft-max tip invent exhausted — no tip wrappers.
"""
from __future__ import annotations

import math
import os
import time
from typing import Any

FEE_CLEAR = ("sports-gap", "btc15m", "commodity-15m")
LOSER_NEVER_SELECTIVE = frozenset({
    "memecoin", "kalshi-sp", "kalshi-sized", "kalshi-sp500",
})

# Target AUTO cadences (pimp_desk.AUTO) — observe health only; never waive floors.
FEE_CLEAR_CADENCE_SEC = {
    "btc15m": 60,
    "commodity-15m": 90,
    "sports-gap": 180,
}
# Prior BTC era was 90s — keep 60s only when M4 healthy + M1 non-worse.
BTC_PRIOR_CADENCE_SEC = 90

MAIN_BTC_VENUE_EDGE = 0.05
EDGE08_VENUE_EDGE = 0.08


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


def _chicago_day() -> str:
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d")
    except Exception:
        return time.strftime("%Y-%m-%d", time.gmtime())


def _weekday_iso(day: str) -> bool:
    try:
        from datetime import datetime
        return datetime.strptime(day[:10], "%Y-%m-%d").weekday() < 5
    except Exception:
        return True


# ---- Lock helpers (451 / 452 / 456) ----------------------------------------

def near_miss_edge_relax_forever_zero(root: str | None = None) -> dict:
    """Step 451 lock: near-miss edge_relax is forever 0 (z|p soft only)."""
    try:
        import desk_roi_plan as drp
        relax = drp.effective_near_miss_relax(root)
        allow = set(getattr(drp, "NEAR_MISS_SOFT_ALLOW", frozenset({"z", "p"})))
    except Exception as exc:
        return {
            "ok": False,
            "edge_relax": None,
            "fee_floors_locked": True,
            "reason": f"unavailable: {exc}",
        }
    edge = _finite(relax.get("edge_relax"))
    ok = edge is not None and abs(edge) < 1e-12
    return {
        "ok": ok,
        "edge_relax": 0.0 if ok else edge,
        "soft": relax.get("soft"),
        "z_relax": relax.get("z_relax"),
        "p_relax": relax.get("p_relax"),
        "soft_allow": sorted(allow),
        "fee_floors_locked": True,
        "paper_only": True,
        "note": "Near-miss edge relax remains 0 forever. Soft allowlist z|p only.",
    }


def skip_regret_never_edge_floor(root: str | None = None) -> dict:
    """Step 452 lock: skip-regret candidates never include EDGE/fee floors."""
    try:
        import desk_roi_plan as drp
        cands = drp.skip_regret_candidates(root)
        fee_gates = set(getattr(drp, "SKIP_REGRET_FEE_GATES", frozenset()))
        soft_allow = set(getattr(drp, "SKIP_REGRET_SOFT_ALLOW", frozenset()))
    except Exception as exc:
        return {
            "ok": False,
            "fee_floors_locked": True,
            "reason": f"unavailable: {exc}",
        }
    softs = {
        str(c.get("soft") or "").strip().lower()
        for c in (cands.get("candidates") or [])
        if isinstance(c, dict)
    }
    edge_leak = sorted(
        s for s in softs
        if s in fee_gates or "edge" in s or "fee" in s or s == "floor"
    )
    return {
        "ok": not edge_leak,
        "edge_leaks": edge_leak,
        "candidate_softs": sorted(softs),
        "rejected_fee_gates": list(cands.get("rejected_fee_gates") or []),
        "soft_allow": sorted(soft_allow),
        "fee_gates": sorted(fee_gates),
        "fee_floors_locked": True,
        "paper_only": True,
        "note": (
            "Skip-regret candidates limited to Z/P/DEPTH/NEWS timing — "
            "never EDGE floor."
        ),
    }


def selective_never_expands_meme_inx() -> dict:
    """Step 456 lock: selective_max_buys never boosts meme or INX towers."""
    import desk_more
    checks = []
    ok = True
    for bot, base in (
        ("memecoin", 2),
        ("kalshi-sp", 1),
        ("kalshi-sized", 1),
        ("btc15m", 3),
        ("commodity-15m", 3),
        ("sports-gap", 4),
    ):
        green = desk_more.selective_max_buys(bot, base=base, today=10.0, green_boost=1)
        red = desk_more.selective_max_buys(bot, base=base, today=-1.0, green_boost=1)
        expands = green > base
        if bot in LOSER_NEVER_SELECTIVE or bot not in desk_more.FEE_CLEAR_TOWERS:
            row_ok = green == base and red == base and not expands
        else:
            row_ok = green == base + 1 and red == base
        ok = ok and row_ok
        checks.append({
            "bot": bot,
            "base": base,
            "green": green,
            "red": red,
            "expands": expands,
            "ok": row_ok,
        })
    return {
        "ok": ok,
        "fee_clear_towers": list(desk_more.FEE_CLEAR_TOWERS),
        "never_selective": sorted(LOSER_NEVER_SELECTIVE),
        "checks": checks,
        "fee_floors_locked": True,
        "paper_only": True,
        "note": "Selective volume never expands meme or INX. Fee-clear green +1 only.",
    }


# ---- Weekly eligible-fill funnel (step 499; CLI densify vs #354) ------------

def weekly_eligible_fill_report(
    root: str | None = None,
    *,
    bots: list | None = None,
    days: int = 7,
) -> dict:
    """Weekly eligible-vs-all completions funnel. Observe only; floors locked.

    Prefers desk_completions ledger (independent of PR #354 fit-journal funnel).
    When desk_roi_e4.eligible_fill_funnel is importable, attaches it as sibling
    observe — never rewrites that function.
    """
    days_n = max(1, min(int(days or 7), 31))
    try:
        import desk_living
        path = desk_living.completions_path(root)
        store = _load(path, {"paper_only": True, "rows": [], "by_day": {}})
    except Exception:
        store = {"rows": [], "by_day": {}}

    from datetime import datetime, timedelta
    try:
        from zoneinfo import ZoneInfo
        today = datetime.now(ZoneInfo("America/Chicago")).date()
    except Exception:
        today = datetime.utcnow().date()
    window = {(today - timedelta(days=i)).isoformat() for i in range(days_n)}

    by_day = store.get("by_day") if isinstance(store.get("by_day"), dict) else {}
    rows: list[dict] = []
    for day, day_rows in by_day.items():
        if str(day)[:10] not in window:
            continue
        for r in day_rows or []:
            if isinstance(r, dict):
                rows.append(r)
    if not rows:
        # Fallback: scan flat rows with chicago_day.
        for r in store.get("rows") or []:
            if not isinstance(r, dict):
                continue
            day = str(r.get("chicago_day") or "")[:10]
            if day in window:
                rows.append(r)

    all_n = len(rows)
    elig = [r for r in rows if r.get("eligible")]
    inelig = [r for r in rows if not r.get("eligible")]
    weekday_elig = 0
    weekday_all = 0
    by_bot: dict[str, dict] = {}
    for r in rows:
        bot = str(r.get("bot") or "unknown")[:40]
        day = str(r.get("chicago_day") or "")[:10]
        wd = _weekday_iso(day) if day else True
        slot = by_bot.setdefault(bot, {
            "bot": bot,
            "all": 0,
            "eligible": 0,
            "fee_clear": bot in FEE_CLEAR,
        })
        slot["all"] += 1
        if wd:
            weekday_all += 1
        if r.get("eligible"):
            slot["eligible"] += 1
            if wd:
                weekday_elig += 1

    try:
        import desk_roi_plan as drp
        m1 = drp.firm_taxed_m1(bots)
    except Exception:
        m1 = {"expectancy_taxed": None, "n": 0}

    e4_sibling = None
    try:
        from desk_roi_e4 import eligible_fill_funnel  # optional sibling (#354)
        e4_sibling = eligible_fill_funnel(root, bots=bots)
    except Exception:
        e4_sibling = None

    elig_n = len(elig)
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "window_days": days_n,
        "chicago_today": _chicago_day(),
        "all_completions": all_n,
        "eligible_completions": elig_n,
        "ineligible_completions": len(inelig),
        "eligible_share": round(elig_n / all_n, 4) if all_n else None,
        "weekday_eligible": weekday_elig,
        "weekday_all": weekday_all,
        "towers": sorted(by_bot.values(), key=lambda r: (-int(r["eligible"]), r["bot"])),
        "m1": m1.get("expectancy_taxed"),
        "m1_n": m1.get("n"),
        "e4_funnel_sibling": e4_sibling,
        "label": (
            f"weekly_eligible {elig_n}/{all_n} "
            f"weekday={weekday_elig}/{weekday_all} "
            f"m1={m1.get('expectancy_taxed')}"
        ),
        "note": (
            "Weekly eligible-fill funnel (completions ledger). Secondary to M1. "
            "Never softer floors. No tip invent."
        ),
    }


# ---- Insight:betting headcount ratio board (step 76 / hire order) -----------

def insight_betting_ratio_board(
    root: str | None = None,
    *,
    bots: list | None = None,
) -> dict:
    """Insight:betting headcount dashboard — ≥3:1 until firm M1≥0. Not a tip invent."""
    try:
        import desk_living
        swarm = desk_living.insight_swarm_ratio(root)
        min_ratio = float(
            swarm.get("min_ratio")
            or getattr(desk_living, "INSIGHT_BETTING_MIN_RATIO", 3.0)
        )
    except Exception as exc:
        return {
            "paper_only": True,
            "fee_floors_locked": True,
            "observe_only": True,
            "ok": False,
            "pass": False,
            "reason": f"swarm unavailable: {exc}",
            "target_ratio": 3.0,
            "note": "Insight:betting ≥3:1 until firm M1≥0. Hire clerks first.",
        }
    try:
        import desk_roi_plan as drp
        m1 = drp.firm_taxed_m1(bots)
    except Exception:
        m1 = {"expectancy_taxed": None, "n": 0}
    firm_exp = _finite(m1.get("expectancy_taxed"))
    m1_nonneg = firm_exp is not None and firm_exp + 1e-12 >= 0.0
    ratio = _finite(swarm.get("ratio"))
    ratio_ok = ratio is not None and ratio + 1e-12 >= min_ratio
    # Gate softens only when firm M1 already ≥0 — still report ratio.
    required = not m1_nonneg
    board_pass = ratio_ok if required else True
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "insight_n": swarm.get("insight_n"),
        "betting_n": swarm.get("betting_n"),
        "ratio": ratio,
        "min_ratio": min_ratio,
        "target_ratio": min_ratio,
        "pass": board_pass,
        "ok": board_pass,
        "ratio_meets_target": ratio_ok,
        "required_until_m1_nonneg": required,
        "m1": firm_exp,
        "m1_n": m1.get("n"),
        "m1_nonneg": m1_nonneg,
        "insight_helpers": swarm.get("insight_helpers"),
        "betting_towers": swarm.get("betting_towers"),
        "label": (
            f"insight:betting {swarm.get('insight_n')}:{swarm.get('betting_n')} "
            f"ratio={ratio} (need ≥{min_ratio}:1 until M1≥0; "
            f"m1={'ok' if m1_nonneg else 'thin/red'})"
        ),
        "note": (
            "Insight:betting headcount ≥3:1 until firm M1≥0. "
            "Observe board only — never tip invent; never meme/INX spam."
        ),
    }


# ---- Shadow edge08 vs main expectancy (step 454) ---------------------------

def _btc_main_history(root: str | None, bots: list | None) -> list:
    """Collect btc15m main-book closed/history rows without private desk helpers."""
    if bots:
        for b in bots:
            if isinstance(b, dict) and b.get("id") == "btc15m":
                hist = list(b.get("history") or [])
                if hist:
                    return hist
                closed = list(b.get("closed") or [])
                if closed:
                    return closed
    # Fallback: paper account closed list under btc15m-signal/.
    for name in ("account.json", "state.json", "paper_state.json"):
        path = _path(os.path.join("btc15m-signal", name), root)
        data = _load(path, {})
        closed = data.get("closed") if isinstance(data, dict) else None
        if isinstance(closed, list) and closed:
            return [r for r in closed if isinstance(r, dict)]
        hist = data.get("history") if isinstance(data, dict) else None
        if isinstance(hist, list) and hist:
            return [r for r in hist if isinstance(r, dict)]
    return []


def edge08_vs_main_expectancy_board(
    root: str | None = None,
    *,
    bots: list | None = None,
) -> dict:
    """Compare BTC edge08 shadow expectancy vs main 0.05 floor book. Observe only."""
    try:
        import desk_roi_plan as drp
        shadow = drp.btc_edge08_shadow_status(root)
    except Exception as exc:
        shadow = {
            "n": 0,
            "expectancy": None,
            "promote_ready": False,
            "reason": f"shadow unavailable: {exc}",
        }

    main_n = 0
    main_ev = None
    try:
        import desk_profit
        hist = _btc_main_history(root, bots)
        if hist:
            exp = desk_profit.bot_expectancy(hist, window_days=30, fill_tax=0.01)
            main_n = int(exp.get("n") or 0)
            main_ev = _finite(exp.get("expectancy"))
    except Exception:
        pass

    shadow_n = int(shadow.get("n") or 0)
    shadow_ev = _finite(shadow.get("expectancy"))
    delta = None
    if shadow_ev is not None and main_ev is not None:
        delta = round(shadow_ev - main_ev, 4)
    thin = shadow_n < 30 or main_n < 10
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "bot": "btc15m",
        "main_venue_edge": MAIN_BTC_VENUE_EDGE,
        "shadow_venue_edge": EDGE08_VENUE_EDGE,
        "main_n": main_n,
        "main_expectancy": main_ev,
        "shadow_n": shadow_n,
        "shadow_expectancy": shadow_ev,
        "delta_shadow_minus_main": delta,
        "evidence_thin": thin,
        "promote_ready": bool(shadow.get("promote_ready")),
        "n_to_promote": shadow.get("n_to_promote"),
        "label": (
            f"edge08_vs_main shadow_ev={shadow_ev} n={shadow_n} "
            f"main_ev={main_ev} n={main_n} Δ={delta}"
            + (" THIN" if thin else "")
        ),
        "note": (
            "Shadow edge08 (0.08) vs main 0.05 floor book. Raise-only promote at "
            "n≥30 EV≥0.5. Never softens floor. Observe densify step 454."
        ),
    }


# ---- Fee-clear cadence health observe (steps 508–510) ----------------------

def fee_clear_cadence_health_board(
    root: str | None = None,
    *,
    bots: list | None = None,
) -> dict:
    """Observe fee-clear AUTO cadence vs M4 latency bars. Never waive floors."""
    try:
        import desk_roi_plan as drp
        m1 = drp.firm_taxed_m1(bots)
    except Exception:
        drp = None  # type: ignore
        m1 = {"expectancy_taxed": None, "n": 0}

    towers = []
    all_ok = True
    for bot_id, cadence in FEE_CLEAR_CADENCE_SEC.items():
        lat = {"n": 0, "p50_s": None, "bar_s": 20.0, "pass": False}
        if drp is not None:
            try:
                lat = drp.latency_p50(root, bot=bot_id)
            except Exception:
                pass
        m4_ok = bool(lat.get("pass"))
        # BTC 60s keep-rule: M4 healthy (observe flag). Prior era 90s noted.
        keep_faster = True
        if bot_id == "btc15m":
            keep_faster = m4_ok or int(lat.get("n") or 0) < 5  # thin → no kill yet
        row_ok = keep_faster
        all_ok = all_ok and (row_ok if int(lat.get("n") or 0) >= 5 else True)
        towers.append({
            "bot": bot_id,
            "cadence_sec": cadence,
            "prior_cadence_sec": BTC_PRIOR_CADENCE_SEC if bot_id == "btc15m" else None,
            "m4_n": lat.get("n"),
            "m4_p50_s": lat.get("p50_s"),
            "m4_bar_s": lat.get("bar_s"),
            "m4_pass": m4_ok,
            "keep_cadence": keep_faster,
            "ok": row_ok if int(lat.get("n") or 0) >= 5 else None,
        })

    firm_exp = _finite(m1.get("expectancy_taxed"))
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "towers": towers,
        "cadence_targets": dict(FEE_CLEAR_CADENCE_SEC),
        "m1": firm_exp,
        "m1_n": m1.get("n"),
        "all_ok": all_ok,
        "label": (
            "fee_clear_cadence "
            + " ".join(
                f"{t['bot']}={t['cadence_sec']}s"
                f"{'/M4ok' if t.get('m4_pass') else '/M4?'}"
                for t in towers
            )
        ),
        "note": (
            "Cadence health observe: BTC 60s keep iff M4 healthy; commodity 90s; "
            "sports 180s (+ tip densify without waiving edge). Floors locked."
        ),
    }
