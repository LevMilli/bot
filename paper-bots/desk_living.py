"""
desk_living.py — Living Trading Upgrade spine (paper only).

Feature-store rows, CompletedEligibleFills, Chicago-day helpers, CLI entry_gate honor.
Never softens venue min_edge floors. No live orders. No profit guarantee.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

CT = ZoneInfo("America/Chicago")
FEATURE_STORE_NAME = "desk_feature_store.jsonl"
COMPLETIONS_NAME = "desk_completions.json"
MAX_FEATURE_ROWS_READ = 5000
MAX_COMPLETION_ROWS = 2000
FEE_CLEAR = frozenset({"sports-gap", "btc15m", "commodity-15m"})
BETTING_TOWERS = (
    "sports-gap",
    "btc15m",
    "commodity-15m",
    "memecoin",
    "kalshi-sp",
    "kalshi-sized",
)
INSIGHT_HELPER_DIGESTS = (
    "tip_radar_digest.json",
    "skip_historian_digest.json",
    "timer_heartbeat_digest.json",
    "empty_card_bee_digest.json",
    "clv_closer_digest.json",
    "injury_wire_digest.json",
    "eia_scout_digest.json",
    "calib_nag_digest.json",
    "hard_stop_clerk_digest.json",
    "near_miss_clerk_digest.json",
    "bleed_clerk_digest.json",
    "distance_clerk_digest.json",
    "bookkeeper_clerk_digest.json",
    "reporter_clerk_digest.json",
    "quant_clerk_digest.json",
    "skip_twin_clerk_digest.json",
    "sunday_living_packet.json",
    "clerk_pulse_digest.json",
    "calendar_digest.json",
)
INSIGHT_BETTING_MIN_RATIO = 3.0


def _root(root: str | None = None) -> str:
    return root or os.path.dirname(os.path.abspath(__file__))


def chicago_today(now: datetime | None = None):
    """America/Chicago calendar date (living upgrade P0 — never host TZ)."""
    now = now or datetime.now(CT)
    if now.tzinfo is None:
        now = now.replace(tzinfo=CT)
    return now.astimezone(CT).date()


def chicago_today_iso(now: datetime | None = None) -> str:
    return chicago_today(now).isoformat()


def honor_desk_entry_gate(root: str | None = None) -> str:
    """CLI/standalone bots: if desk entry_gate would block, set DESK_BLOCK_ENTRIES=1.

    Returns the block reason (empty if entries allowed). Exits still run when blocked.
    """
    if os.environ.get("DESK_BLOCK_ENTRIES") == "1":
        return os.environ.get("DESK_BLOCK_REASON") or "DESK_BLOCK_ENTRIES=1"
    try:
        import pimp_desk
        reason = pimp_desk.entry_gate(root or _root())
    except Exception as exc:
        return ""  # fail-open on desk import only — timer path still authoritative
    if reason:
        os.environ["DESK_BLOCK_ENTRIES"] = "1"
        os.environ["DESK_BLOCK_REASON"] = str(reason)[:240]
        return str(reason)
    return ""


def feature_store_path(root: str | None = None) -> str:
    return os.path.join(_root(root), FEATURE_STORE_NAME)


def record_decision_features(
    root: str | None = None,
    *,
    bot: str,
    action: str,
    series: str = "",
    side: str = "",
    ask=None,
    bid=None,
    fee=None,
    model_p=None,
    z=None,
    edge=None,
    depth=None,
    skip_codes: list | None = None,
    fill_id: str = "",
    note: str = "",
    extra: dict | None = None,
) -> dict:
    """Append one decision feature row (buy or skip). Paper only."""
    row = {
        "at": datetime.now(CT).isoformat(timespec="seconds"),
        "chicago_day": chicago_today_iso(),
        "bot": str(bot or "")[:40],
        "action": str(action or "skip")[:20],
        "series": str(series or "")[:40],
        "side": str(side or "")[:20],
        "ask": _f(ask),
        "bid": _f(bid),
        "fee": _f(fee),
        "model_p": _f(model_p),
        "z": _f(z),
        "edge": _f(edge),
        "depth": _f(depth),
        "skip_codes": [str(c)[:40] for c in (skip_codes or [])][:12],
        "fill_id": str(fill_id or "")[:80],
        "note": str(note or "")[:160],
        "paper_only": True,
        "fee_floors_locked": True,
    }
    if isinstance(extra, dict):
        for k, v in list(extra.items())[:12]:
            if k in row:
                continue
            row[str(k)[:40]] = v if isinstance(v, (str, int, float, bool)) or v is None else str(v)[:80]
    path = feature_store_path(root)
    try:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, default=str) + "\n")
    except OSError:
        return {"recorded": False, "row": row}
    return {"recorded": True, "row": row}


def record_skip_twin_features(
    root: str | None = None,
    *,
    bot: str,
    ticker: str,
    would_pnl,
    soft: str | list | None = None,
    note: str = "",
    extra: dict | None = None,
) -> dict:
    """Join a labeled near-miss / skip-twin outcome into the feature store.

    Observe-only learn row — does not arm soft gates or soften floors.
    """
    pnl = _f(would_pnl)
    soft_key = (
        ",".join(str(x) for x in soft)
        if isinstance(soft, (list, tuple))
        else str(soft or "")
    )[:40]
    payload = {
        "twin": True,
        "would_pnl": pnl,
        "soft": soft_key,
        "ticker": str(ticker or "")[:80],
    }
    if isinstance(extra, dict):
        payload.update({str(k)[:40]: v for k, v in list(extra.items())[:8]})
    return record_decision_features(
        root,
        bot=bot or "unknown",
        action="skip_twin",
        fill_id=str(ticker or "")[:80],
        skip_codes=["SKIP_TWIN", soft_key] if soft_key else ["SKIP_TWIN"],
        note=str(note or f"skip twin would_pnl={pnl}")[:160],
        extra=payload,
    )


def record_eval_features(
    root: str | None = None,
    *,
    bot: str,
    action: str,
    ev: dict | None = None,
    ticker: str = "",
    series: str = "",
    reasons: list | None = None,
    note: str = "",
) -> dict:
    """Convenience: map an evaluate/candidate dict into a feature-store row."""
    ev = ev if isinstance(ev, dict) else {}
    codes = []
    for r in reasons or ev.get("reasons") or []:
        codes.append(str(r)[:40])
    return record_decision_features(
        root,
        bot=bot,
        action=action,
        series=series or str(ev.get("series") or "")[:40],
        side=str(ev.get("side") or "")[:20],
        ask=ev.get("ask"),
        bid=ev.get("bid"),
        fee=ev.get("fee"),
        model_p=ev.get("p") if ev.get("p") is not None else ev.get("model_p") or ev.get("confidence"),
        z=ev.get("z"),
        edge=ev.get("edge") if ev.get("edge") is not None else ev.get("gap"),
        depth=ev.get("depth"),
        skip_codes=codes,
        fill_id=str(ev.get("fill_id") or ticker or ev.get("ticker") or "")[:80],
        note=note or "; ".join(codes)[:160],
        extra={
            "ticker": str(ticker or ev.get("ticker") or "")[:80],
            "lane": str(ev.get("lane") or "")[:20],
            "minutes_left": _f(ev.get("min_left") if ev.get("min_left") is not None else ev.get("minutes_left")),
        },
    )


FEATURE_QUIET_HOURS = 6.0


def feature_store_coverage(root: str | None = None, *, limit: int = MAX_FEATURE_ROWS_READ) -> dict:
    path = feature_store_path(root)
    n = 0
    buys = 0
    skips = 0
    last_at = None
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as handle:
                for i, line in enumerate(handle):
                    if i >= int(limit):
                        break
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(row, dict):
                        continue
                    n += 1
                    act = str(row.get("action") or "").lower()
                    if act == "buy":
                        buys += 1
                    else:
                        skips += 1
                    stamp = row.get("at")
                    if stamp:
                        last_at = str(stamp)
        except OSError:
            pass
    return {
        "paper_only": True,
        "n": n,
        "buys": buys,
        "skips": skips,
        "last_at": last_at,
        "path": os.path.basename(path),
        "fee_floors_locked": True,
        "note": "Decision feature store for living AI learning. Floors locked.",
    }


def feature_quiet_pager(
    root: str | None = None,
    *,
    now: datetime | None = None,
    quiet_hours: float = FEATURE_QUIET_HOURS,
) -> dict:
    """Weekday pager copy when feature store is quiet ≥ threshold (never auto-pages)."""
    alert = feature_store_quiet_alert(root, now=now, quiet_hours=quiet_hours)
    page = bool(alert.get("quiet") and alert.get("alert"))
    copy = ""
    if page:
        copy = (
            f"**FEATURE QUIET PAGE** (Chicago weekday)\n"
            f"{alert.get('alert')}\n"
            f"age_hours={alert.get('age_hours')} n={alert.get('n')} "
            f"last_at={alert.get('last_at')}\n"
            f"_floors locked · paper only · staff ack — never invent fills_"
        )
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "auto_page": False,
        "page": page,
        "copy": copy,
        "alert": alert,
        "label": (
            "feature quiet PAGE"
            if page
            else "feature quiet ok"
        ),
        "note": "Staff pager copy only — never auto-posts; never softens floors.",
    }


def feature_store_quiet_alert(
    root: str | None = None,
    *,
    now: datetime | None = None,
    quiet_hours: float = FEATURE_QUIET_HOURS,
) -> dict:
    """Weekday alert when feature store has been quiet too long (learn data starved)."""
    now = now or datetime.now(CT)
    if now.tzinfo is None:
        now = now.replace(tzinfo=CT)
    now = now.astimezone(CT)
    cov = feature_store_coverage(root)
    last_at = cov.get("last_at")
    age_h = None
    if last_at:
        try:
            stamp = datetime.fromisoformat(str(last_at).replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=CT)
            age_h = round((now - stamp.astimezone(CT)).total_seconds() / 3600.0, 2)
        except ValueError:
            age_h = None
    weekday = now.weekday() < 5  # Mon–Fri Chicago
    quiet = bool(
        weekday
        and (age_h is None or age_h + 1e-12 >= float(quiet_hours))
    )
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "weekday": weekday,
        "quiet": quiet,
        "age_hours": age_h,
        "quiet_hours": float(quiet_hours),
        "n": cov.get("n"),
        "last_at": last_at,
        "alert": (
            f"WEEKDAY ALERT: feature store quiet ≥{quiet_hours:.0f}h — "
            "learn loop starved (floors still locked)."
            if quiet
            else ""
        ),
        "note": "Observe-only coverage alert. Never softens venue floors.",
    }


def completions_path(root: str | None = None) -> str:
    return os.path.join(_root(root), COMPLETIONS_NAME)


def record_completion(
    root: str | None = None,
    *,
    bot: str,
    ticker: str = "",
    side: str = "",
    pnl=None,
    contracts=None,
    fill_id: str = "",
    kind: str = "close",
    eligible: bool = True,
    note: str = "",
) -> dict:
    """Record a completed fee-clear (or other) paper close for Completions KPI."""
    path = completions_path(root)
    store = _load_json(path, {"paper_only": True, "rows": [], "by_day": {}})
    day = chicago_today_iso()
    row = {
        "at": datetime.now(CT).isoformat(timespec="seconds"),
        "chicago_day": day,
        "bot": str(bot or "")[:40],
        "ticker": str(ticker or "")[:80],
        "side": str(side or "")[:20],
        "pnl": _f(pnl),
        "contracts": _f(contracts),
        "fill_id": str(fill_id or "")[:80],
        "kind": str(kind or "close")[:40],
        "eligible": bool(eligible) and str(bot) in FEE_CLEAR,
        "fee_clear": str(bot) in FEE_CLEAR,
        "note": str(note or "")[:160],
        "paper_only": True,
        "fee_floors_locked": True,
    }
    rows = list(store.get("rows") or [])
    rows.append(row)
    store["rows"] = rows[-MAX_COMPLETION_ROWS:]
    by_day = store.get("by_day") if isinstance(store.get("by_day"), dict) else {}
    day_rows = list(by_day.get(day) or [])
    day_rows.append(row)
    by_day[day] = day_rows[-500:]
    store["by_day"] = by_day
    store["last_at"] = row["at"]
    _save_json(path, store)
    return {"recorded": True, "row": row}


def completions_summary(root: str | None = None, *, day: str | None = None) -> dict:
    path = completions_path(root)
    store = _load_json(path, {"paper_only": True, "rows": [], "by_day": {}})
    day = day or chicago_today_iso()
    by_day = store.get("by_day") if isinstance(store.get("by_day"), dict) else {}
    today_rows = [r for r in (by_day.get(day) or []) if isinstance(r, dict)]
    eligible = [r for r in today_rows if r.get("eligible")]
    pnl_sum = round(sum(float(_f(r.get("pnl")) or 0) for r in eligible), 4)
    return {
        "paper_only": True,
        "chicago_day": day,
        "completions_today": len(today_rows),
        "eligible_completions_today": len(eligible),
        "eligible_pnl_today": pnl_sum,
        "fee_clear_towers": sorted(FEE_CLEAR),
        "fee_floors_locked": True,
        "note": (
            "CompletedEligibleFills = fee-clear closes today. "
            "Optimize with M1 guardrail — never softer floors."
        ),
    }


def living_ai_health(root: str | None = None, bots: list | None = None) -> dict:
    """Masters AI health: adapt snapshot + calib raise_phi tickets across fee-clear."""
    adapt = {}
    try:
        import desk_adapt
        adapt = desk_adapt.adapt_summary(root) or {}
    except Exception:
        adapt = {}
    boards = {}
    raise_phi = []
    try:
        import desk_roi_plan
        for name, latest_fn, report_fn in (
            ("btc", desk_roi_plan.latest_btc_calibration, desk_roi_plan.btc_calibration_report),
            ("sports", desk_roi_plan.latest_sports_calibration, desk_roi_plan.sports_calibration_report),
            ("commodity", desk_roi_plan.latest_commodity_calibration, desk_roi_plan.commodity_calibration_report),
        ):
            card = None
            try:
                card = latest_fn(root)
            except Exception:
                card = None
            if not isinstance(card, dict):
                try:
                    card = report_fn(bots)
                except Exception:
                    card = {}
            boards[name] = {
                "action": (card or {}).get("action"),
                "miscalibrated": bool((card or {}).get("miscalibrated")),
                "hi_n": (card or {}).get("hi_n"),
                "hi_hit_rate": (card or {}).get("hi_hit_rate"),
            }
            if str((card or {}).get("action") or "") == "raise_phi":
                raise_phi.append(name)
    except Exception:
        boards = {}
        raise_phi = []
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "grok_buys": False,
        "adapt_version": adapt.get("version"),
        "adapt_bots_n": len(adapt.get("by_bot") or {}),
        "adapt_recent_vol_n": len(adapt.get("recent_vol") or []),
        "calib_boards": boards,
        "raise_phi_tickets": raise_phi,
        "raise_phi_n": len(raise_phi),
        "auto_write_phi": False,
        "note": (
            "Living AI health — Wilson adapt + calib raise_Φ tickets. "
            "Staff dual-control only; never silent Φ write; never softer floors."
        ),
    }


def teller_living_chip(
    root: str | None = None,
    bots: list | None = None,
    *,
    remember: bool = False,
) -> dict:
    """One teller memory_line from swarm + completions (paper observe)."""
    swarm = insight_swarm_ratio(root)
    comp = completions_chip(root)
    floors_ok = True
    try:
        import desk_profit
        floors = desk_profit.venue_floors_locked() or {}
        floors_ok = bool(floors.get("all_ok"))
    except Exception:
        floors_ok = True
    swarm_bit = (
        f"swarm {swarm.get('insight_n')}:{swarm.get('betting_n')} "
        f"{'ok' if swarm.get('pass') else 'thin'}"
    )
    fill_bit = (
        f"eligible fills today {comp.get('eligible_completions_today')}"
        if comp.get("eligible_completions_today") is not None
        else "eligible fills n/a"
    )
    line = f"{swarm_bit} · {fill_bit} · floors={'locked' if floors_ok else 'CHECK'}"
    if remember:
        try:
            import teller_memory
            teller_memory.remember(
                root,
                kind="facts",
                text=line[:200],
                bot_id="desk",
                source="living_teller_chip",
            )
        except Exception:
            pass
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "live_orders_enabled": False,
        "swarm_pass": swarm.get("pass"),
        "eligible_completions_today": comp.get("eligible_completions_today"),
        "floors_ok": floors_ok,
        "memory_line": line,
        "label": line,
        "note": "Teller living chip — grounded on swarm + Completions; never invents PnL.",
    }


def completions_chip(root: str | None = None) -> dict:
    """Eligible completions today — teller / Masters one-liner."""
    summary = completions_summary(root) or {}
    n = summary.get("eligible_completions_today")
    pnl = summary.get("eligible_pnl_today")
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "chicago_day": summary.get("chicago_day"),
        "eligible_completions_today": n,
        "eligible_pnl_today": pnl,
        "completions_today": summary.get("completions_today"),
        "label": f"completions today eligible={n} pnl={pnl}",
        "note": summary.get("note") or (
            "CompletedEligibleFills = fee-clear closes today. Never softer floors."
        ),
    }


def clerk_pulse_chip(root: str | None = None) -> dict:
    """Last clerk-pulse age / digest health chip."""
    digest: dict = {}
    age_sec = None
    try:
        from helpers import clerk_pulse
        path = clerk_pulse.digest_path(root)
        marker = os.path.join(
            os.path.dirname(path),
            getattr(clerk_pulse, "RUN_MARKER", "clerk_pulse_at.txt"),
        )
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as handle:
                digest = json.load(handle)
        if os.path.isfile(marker):
            age_sec = int(max(0.0, time.time() - os.path.getmtime(marker)))
        if not isinstance(digest, dict):
            digest = {}
    except Exception:
        digest = {}
    cadence = None
    try:
        from helpers import clerk_pulse as _cp
        cadence = getattr(_cp, "CADENCE_SEC", 300)
    except Exception:
        cadence = 300
    stale = age_sec is not None and cadence is not None and age_sec > int(cadence) * 2
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "age_sec": age_sec,
        "cadence_sec": cadence,
        "stale": stale,
        "refreshed_n": digest.get("refreshed_n") or digest.get("n"),
        "at": digest.get("at"),
        "label": (
            f"clerk pulse age={age_sec}s "
            + ("STALE" if stale else "ok" if age_sec is not None else "n/a")
        ),
        "note": digest.get("note") or "5m insight clerk pulse — observe-only digests.",
    }


def dual_control_chip(root: str | None = None) -> dict:
    """Dual-control signed checklist chip (paper arm only)."""
    status: dict = {}
    try:
        import desk_roi_plan
        status = desk_roi_plan.dual_control_status(root) or {}
    except Exception:
        status = {}
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "live_orders_enabled": False,
        "auto_promote": False,
        "signed_n": status.get("signed_n"),
        "items_n": status.get("items_n"),
        "checklist_complete": bool(status.get("checklist_complete")),
        "two_staff": bool(status.get("two_staff")),
        "arm_ready_paper": bool(status.get("arm_ready_paper")),
        "label": (
            f"dual-control signed={status.get('signed_n')}/{status.get('items_n')} "
            f"two_staff={bool(status.get('two_staff'))} "
            f"arm_ready_paper={bool(status.get('arm_ready_paper'))}"
        ),
        "note": status.get("note") or (
            "Both staff + full checklist before any future live path."
        ),
    }


def ruin_drill_chip(root: str | None = None) -> dict:
    """Ruin drill monthly practice chip."""
    status: dict = {}
    try:
        import desk_roi_plan
        status = desk_roi_plan.ruin_drill_status(root) or {}
    except Exception:
        status = {}
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "live_orders_enabled": False,
        "active": bool(status.get("active")),
        "level": status.get("level"),
        "practiced_this_month": bool(status.get("practiced_this_month")),
        "last_practice_at": status.get("last_practice_at"),
        "label": (
            f"ruin drill active={bool(status.get('active'))} "
            f"level={status.get('level')} "
            f"practiced_month={bool(status.get('practiced_this_month'))}"
        ),
        "note": status.get("note") or (
            "Practice soft/hard this Chicago month for dual-control."
        ),
    }


def calendar_scanner_chip(root: str | None = None) -> dict:
    """Upcoming high-impact calendar events chip."""
    digest: dict = {}
    try:
        from helpers import calendar_scanner
        path = calendar_scanner.digest_path(root)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as handle:
                digest = json.load(handle)
        if not isinstance(digest, dict) or digest.get("n") is None:
            digest = calendar_scanner.scan(root) or {}
    except Exception:
        digest = {}
    events = digest.get("events") if isinstance(digest.get("events"), list) else []
    if not events and isinstance(digest.get("upcoming"), list):
        events = digest.get("upcoming") or []
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "n": digest.get("n") if digest.get("n") is not None else len(events),
        "events": events[:8],
        "nearest": events[0] if events else None,
        "label": (
            f"calendar n={digest.get('n') if digest.get('n') is not None else len(events)} "
            f"next={(events[0] or {}).get('title') if events else None}"
        ),
        "note": digest.get("note") or "Observe-only calendar scanner — never places alone.",
    }


def eia_blackout_chip(root: str | None = None) -> dict:
    """Commodity ±45m EIA/inventory blackout chip."""
    status: dict = {}
    try:
        from helpers import eia_blackout
        events = eia_blackout.load_calendar_events(root)
        # Probe primary energy series used on commodity tower.
        crude = eia_blackout.energy_blackout("CL", events)
        gas = eia_blackout.energy_blackout("NG", events)
        blocked = bool(crude.get("blocked") or gas.get("blocked"))
        hits = list(crude.get("hits") or []) + list(gas.get("hits") or [])
        status = {
            "blocked": blocked,
            "window_min": getattr(eia_blackout, "EIA_WINDOW_MIN", 45),
            "crude": crude,
            "natgas": gas,
            "hits_n": len(hits),
            "note": (
                "Commodity blackout ±45m around inventory prints — never softens 0.05."
            ),
        }
    except Exception:
        status = {}
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "blocked": bool(status.get("blocked")),
        "window_min": status.get("window_min") or 45,
        "hits_n": status.get("hits_n"),
        "crude_blocked": bool((status.get("crude") or {}).get("blocked")),
        "natgas_blocked": bool((status.get("natgas") or {}).get("blocked")),
        "label": (
            f"EIA blackout {'ACTIVE' if status.get('blocked') else 'clear'} "
            f"hits={status.get('hits_n')} window={status.get('window_min') or 45}m"
        ),
        "note": status.get("note") or "±45m inventory blackout for energy series.",
    }


def living_compact_card(
    root: str | None = None,
    bots: list | None = None,
    *,
    board: dict | None = None,
) -> dict:
    """One-line Masters summary across living chips (no recursive board build)."""
    if isinstance(board, dict):
        src = board
    else:
        swarm = insight_swarm_ratio(root)
        timer = timer_heartbeat_chip(root)
        green = green_day_board(root, bots=bots)
        bleed = bleed_chip(root, bots=bots)
        quiet = feature_store_quiet_alert(root)
        src = {
            "insight_swarm": swarm,
            "timer_heartbeat": timer,
            "green_day": green,
            "bleed": bleed,
            "feature_quiet": quiet,
        }
    swarm = src.get("insight_swarm") if isinstance(src.get("insight_swarm"), dict) else {}
    timer = src.get("timer_heartbeat") if isinstance(src.get("timer_heartbeat"), dict) else {}
    green = src.get("green_day") if isinstance(src.get("green_day"), dict) else {}
    bleed = src.get("bleed") if isinstance(src.get("bleed"), dict) else {}
    quiet = src.get("feature_quiet") if isinstance(src.get("feature_quiet"), dict) else {}
    parts = [
        f"swarm {swarm.get('insight_n')}:{swarm.get('betting_n')}",
        f"timer={'alive' if timer.get('alive') else 'DEAD' if timer.get('alive') is False else 'n/a'}",
        f"green={green.get('green_n')}",
        f"bleed={bleed.get('ratio')}",
        f"quiet={'yes' if quiet.get('quiet') else 'no'}",
    ]
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "live_orders_enabled": False,
        "parts": parts,
        "label": " · ".join(str(p) for p in parts),
        "note": "Compact living card — floors locked; paper only.",
    }


def skip_twin_clerk_chip(root: str | None = None) -> dict:
    """Skip-twin clerk digest — labeled near-miss feature join."""
    digest: dict = {}
    try:
        from helpers import skip_twin_clerk
        path = skip_twin_clerk.digest_path(root)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as handle:
                digest = json.load(handle)
        if not isinstance(digest, dict) or digest.get("n") is None:
            digest = skip_twin_clerk.write_digest_from_desk(root)
    except Exception:
        digest = {}
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "auto_promote": False,
        "n": digest.get("n"),
        "labeled_n": digest.get("labeled_n"),
        "shadow_ev": digest.get("shadow_ev"),
        "promote_ready": bool(digest.get("promote_ready")),
        "decision": digest.get("decision") or "",
        "label": (
            f"skip-twin n={digest.get('n')} labeled={digest.get('labeled_n')} "
            f"ev={digest.get('shadow_ev')} ready={bool(digest.get('promote_ready'))}"
        ),
        "note": digest.get("note") or (
            "Near-miss would_pnl twins for learn — soft allowlist stays z|p."
        ),
    }


def clv_closer_chip(root: str | None = None) -> dict:
    """CLV closer clerk digest chip (sports beat-close completeness)."""
    digest: dict = {}
    try:
        from helpers import clv_closer
        path = clv_closer.digest_path(root)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as handle:
                digest = json.load(handle)
        if not isinstance(digest, dict) or digest.get("n") is None:
            digest = clv_closer.write_digest_from_desk(root)
    except Exception:
        digest = {}
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "n": digest.get("n"),
        "complete": digest.get("complete"),
        "completeness": digest.get("completeness"),
        "pass": digest.get("pass"),
        "label": (
            f"CLV closer n={digest.get('n')} complete={digest.get('complete')} "
            f"rate={digest.get('completeness')} "
            + ("ok" if digest.get("pass") else "gaps" if digest.get("pass") is False else "n/a")
        ),
        "note": digest.get("note") or (
            "Feeds green_boost evidence — never softens sports 0.06."
        ),
    }


def timer_digest_chip(root: str | None = None) -> dict:
    """Timer heartbeat helper digest chip (alive/dead)."""
    digest: dict = {}
    try:
        from helpers import timer_heartbeat
        path = timer_heartbeat.digest_path(root)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as handle:
                digest = json.load(handle)
        if not isinstance(digest, dict) or digest.get("alive") is None:
            # Prefer lightweight health without full snapshot when possible.
            try:
                import pimp_desk
                health = pimp_desk.timer_health(root) or {}
                digest = timer_heartbeat.write_digest(
                    root,
                    alive=bool(health.get("alive")),
                    detail=str(health.get("detail") or health.get("alert") or ""),
                )
            except Exception:
                digest = timer_heartbeat.probe_from_snapshot(root)
    except Exception:
        digest = {}
    alive = digest.get("alive")
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "alive": alive,
        "status": digest.get("status") or (
            "unknown" if alive is None else ("alive" if alive else "dead")
        ),
        "detail": digest.get("detail") or "",
        "label": (
            f"timer digest {digest.get('status') or ('alive' if alive else 'dead' if alive is False else 'n/a')}"
        ),
        "note": digest.get("note") or "Life support #1 — dead timer = dead city.",
    }


def near_miss_clerk_chip(root: str | None = None) -> dict:
    """Near-miss clerk digest chip (z|p soft allowlist observe)."""
    digest: dict = {}
    try:
        from helpers import near_miss_clerk
        path = near_miss_clerk.digest_path(root)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as handle:
                digest = json.load(handle)
        if not isinstance(digest, dict) or digest.get("n") is None:
            digest = near_miss_clerk.write_digest_from_desk(root)
    except Exception:
        digest = {}
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "auto_promote": False,
        "n": digest.get("n"),
        "labeled_n": digest.get("labeled_n"),
        "shadow_ev": digest.get("shadow_ev"),
        "promote_ready": bool(digest.get("promote_ready")),
        "decision": digest.get("decision") or "",
        "label": (
            f"near-miss clerk n={digest.get('n')} labeled={digest.get('labeled_n')} "
            f"ev={digest.get('shadow_ev')} ready={bool(digest.get('promote_ready'))}"
        ),
        "note": digest.get("note") or (
            "Soft allowlist z|p only — never edge, never softer fee floors."
        ),
    }


def hard_stop_clerk_chip(root: str | None = None) -> dict:
    """Sports hard-stop clerk digest chip (shadow until staff)."""
    digest: dict = {}
    try:
        from helpers import hard_stop_clerk
        path = hard_stop_clerk.digest_path(root)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as handle:
                digest = json.load(handle)
        if not isinstance(digest, dict) or digest.get("n") is None:
            digest = hard_stop_clerk.write_digest_from_desk(root)
    except Exception:
        digest = {}
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "auto_promote": False,
        "n": digest.get("n"),
        "n_with_pnl": digest.get("n_with_pnl"),
        "shadow_expectancy": digest.get("shadow_expectancy"),
        "promote_ready": bool(digest.get("promote_ready")),
        "live": bool(digest.get("live")),
        "staff_approved": bool(digest.get("staff_approved")),
        "decision": digest.get("decision") or "",
        "label": (
            f"hard-stop clerk n={digest.get('n_with_pnl')} "
            f"ev={digest.get('shadow_expectancy')} "
            f"ready={bool(digest.get('promote_ready'))} live={bool(digest.get('live'))}"
        ),
        "note": digest.get("note") or (
            "Live sells stay staff-gated; code default SPORTS_HARD_STOP_LIVE=False."
        ),
    }


def bleed_clerk_chip(root: str | None = None, bots: list | None = None) -> dict:
    """Bleed clerk digest chip (ratio + misplaced capital)."""
    digest: dict = {}
    try:
        from helpers import bleed_clerk
        path = bleed_clerk.digest_path(root)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as handle:
                digest = json.load(handle)
        if not isinstance(digest, dict) or digest.get("bleed_ratio") is None:
            digest = bleed_clerk.write_digest_from_desk(root, bots=bots)
    except Exception:
        digest = {}
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "bleed_ratio": digest.get("bleed_ratio"),
        "bleed_pass": digest.get("bleed_pass"),
        "misplaced_usd": digest.get("misplaced_usd"),
        "share_of_cap": digest.get("share_of_cap"),
        "label": (
            f"bleed clerk ratio={digest.get('bleed_ratio')} "
            f"pass={digest.get('bleed_pass')} "
            f"misplaced={digest.get('misplaced_usd')}"
        ),
        "note": digest.get("note") or (
            "Recycle open risk on red towers toward fee-clear — floors locked."
        ),
    }


def bookkeeper_chip(root: str | None = None) -> dict:
    """Completions + fee-ledger completeness chip."""
    digest: dict = {}
    try:
        from helpers import bookkeeper_clerk
        path = bookkeeper_clerk.digest_path(root)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as handle:
                digest = json.load(handle)
        if not isinstance(digest, dict) or digest.get("eligible_completions_today") is None:
            digest = bookkeeper_clerk.write_digest_from_desk(root)
    except Exception:
        digest = {}
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "eligible_completions_today": digest.get("eligible_completions_today"),
        "eligible_pnl_today": digest.get("eligible_pnl_today"),
        "fee_ledger_n": digest.get("fee_ledger_n"),
        "fee_ledger_complete": digest.get("fee_ledger_complete"),
        "label": (
            f"bookkeeper fills={digest.get('eligible_completions_today')} "
            f"fee_ledger={digest.get('fee_ledger_n')} "
            f"complete={digest.get('fee_ledger_complete')}"
        ),
        "note": digest.get("note") or (
            "Taxed Completions + fee ledger — never invent fills or soften floors."
        ),
    }


def reporter_chip(root: str | None = None) -> dict:
    """Weekly scorecard / Sunday packet mirror chip."""
    digest: dict = {}
    try:
        from helpers import reporter_clerk
        path = reporter_clerk.digest_path(root)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as handle:
                digest = json.load(handle)
        if not isinstance(digest, dict) or digest.get("present") is None:
            digest = reporter_clerk.write_digest_from_desk(root)
    except Exception:
        digest = {}
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "auto_publish": False,
        "present": bool(digest.get("present")),
        "label_week": digest.get("label"),
        "m1": digest.get("m1"),
        "keys": digest.get("keys") if isinstance(digest.get("keys"), list) else [],
        "label": (
            f"reporter scorecard={'yes' if digest.get('present') else 'no'} "
            f"week={digest.get('label')} m1={digest.get('m1')}"
        ),
        "note": digest.get("note") or (
            "Sunday packet mirror — staff publishes; never paints PnL."
        ),
    }


def empty_card_bee_chip(root: str | None = None) -> dict:
    """Empty CARD 3s latency bee digest chip."""
    digest: dict = {}
    try:
        from helpers import empty_card_bee
        path = empty_card_bee.digest_path(root)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as handle:
                digest = json.load(handle)
        if not isinstance(digest, dict) or digest.get("n") is None:
            digest = empty_card_bee.write_digest_from_desk(root)
    except Exception:
        digest = {}
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "bar_sec": digest.get("bar_sec") or 3.0,
        "n": digest.get("n"),
        "breaches": digest.get("breaches"),
        "label": (
            f"empty bee n={digest.get('n')} breaches={digest.get('breaches')} "
            f"bar={digest.get('bar_sec') or 3.0}s"
        ),
        "note": digest.get("note") or "Empty CARD bee — speed without softer floors.",
    }


def skip_historian_chip(root: str | None = None) -> dict:
    """Top skip-code frequencies chip (BUDGET≠EDGE)."""
    digest: dict = {}
    try:
        from helpers import skip_historian
        path = skip_historian.digest_path(root)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as handle:
                digest = json.load(handle)
        if not isinstance(digest, dict) or digest.get("n_events") is None:
            digest = skip_historian.write_digest_from_desk(root)
    except Exception:
        digest = {}
    top = digest.get("top") if isinstance(digest.get("top"), list) else []
    head = top[0] if top and isinstance(top[0], dict) else {}
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "n_events": digest.get("n_events"),
        "top": top[:8],
        "label": (
            f"skip historian n={digest.get('n_events')} "
            f"top={head.get('code')}×{head.get('n')}"
            if head.get("code") is not None
            else f"skip historian n={digest.get('n_events')}"
        ),
        "note": digest.get("note") or (
            "Observe-only skip historian. BUDGET≠EDGE — never soften floors."
        ),
    }


def distance_clerk_chip(root: str | None = None) -> dict:
    """Empty CARD latency + firm queue distance chip."""
    digest: dict = {}
    try:
        from helpers import distance_clerk
        path = distance_clerk.digest_path(root)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as handle:
                digest = json.load(handle)
        if not isinstance(digest, dict) or digest.get("firm_offers_n") is None:
            digest = distance_clerk.write_digest_from_desk(root)
    except Exception:
        digest = {}
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "empty_card_pass": digest.get("empty_card_pass"),
        "empty_card_last_sec": digest.get("empty_card_last_sec"),
        "firm_offers_n": digest.get("firm_offers_n"),
        "firm_deferred_n": digest.get("firm_deferred_n"),
        "remaining_risk": digest.get("remaining_risk"),
        "label": (
            f"distance empty_ok={digest.get('empty_card_pass')} "
            f"offers={digest.get('firm_offers_n')} "
            f"def={digest.get('firm_deferred_n')} "
            f"risk_left={digest.get('remaining_risk')}"
        ),
        "note": digest.get("note") or (
            "Empty CARD + firm queue distance — recycle risk; floors locked."
        ),
    }


def quant_clerk_chip(root: str | None = None) -> dict:
    """M3 fit→buy / M4 latency walk-forward chip."""
    digest: dict = {}
    try:
        from helpers import quant_clerk
        path = quant_clerk.digest_path(root)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as handle:
                digest = json.load(handle)
        if not isinstance(digest, dict) or (
            digest.get("fit_rate") is None and digest.get("latency_p50") is None
        ):
            digest = quant_clerk.write_digest_from_desk(root)
    except Exception:
        digest = {}
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "auto_write": False,
        "fit_rate": digest.get("fit_rate"),
        "fit_n": digest.get("fit_n"),
        "fit_pass": digest.get("fit_pass"),
        "latency_p50": digest.get("latency_p50"),
        "latency_pass": digest.get("latency_pass"),
        "towers": digest.get("towers") if isinstance(digest.get("towers"), list) else [],
        "label": (
            f"quant fit={digest.get('fit_rate')} "
            f"lat_p50={digest.get('latency_p50')} "
            f"fit_ok={digest.get('fit_pass')}"
        ),
        "note": digest.get("note") or (
            "Walk-forward quant clerk — never LLM buys, never softer floors."
        ),
    }


def injury_wire_chip(root: str | None = None) -> dict:
    """Injury/news wire + staff inbox chip."""
    digest: dict = {}
    inbox_n = 0
    try:
        from helpers import injury_wire
        path = injury_wire.digest_path(root)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as handle:
                digest = json.load(handle)
        if not isinstance(digest, dict):
            digest = {}
        if digest.get("n") is None:
            digest = injury_wire.write_digest_from_desk(root)
        inbox = injury_wire.load_inbox(root) or {}
        rows = inbox.get("rows") if isinstance(inbox, dict) else None
        if isinstance(rows, list):
            inbox_n = len(rows)
        elif isinstance(inbox, list):
            inbox_n = len(inbox)
    except Exception:
        digest = {}
    headlines = digest.get("headlines") if isinstance(digest.get("headlines"), list) else []
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "n": digest.get("n") if digest.get("n") is not None else len(headlines),
        "inbox_n": inbox_n,
        "headlines": headlines[:6],
        "label": (
            f"injury wire n={digest.get('n') or len(headlines)} inbox={inbox_n}"
        ),
        "note": digest.get("note") or (
            "Observe-only injury/news wire. Never buys; never waives sports floor."
        ),
    }


def eia_scout_chip(root: str | None = None) -> dict:
    """7-day crude/natgas inventory calendar chip."""
    digest: dict = {}
    try:
        from helpers import eia_scout
        path = eia_scout.digest_path(root)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as handle:
                digest = json.load(handle)
        if not isinstance(digest, dict) or digest.get("n") is None:
            digest = eia_scout.write_digest_from_desk(root)
    except Exception:
        digest = {}
    events = digest.get("events") if isinstance(digest.get("events"), list) else []
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "n": digest.get("n") if digest.get("n") is not None else len(events),
        "next_eta_hours": digest.get("next_eta_hours"),
        "scout_days": digest.get("scout_days"),
        "events": events[:6],
        "label": (
            f"EIA scout n={digest.get('n') or len(events)} "
            f"next={digest.get('next_eta_hours')}h"
        ),
        "note": digest.get("note") or (
            "Observe-only EIA week scout — never softens commodity 0.05."
        ),
    }


def tip_radar_chip(root: str | None = None) -> dict:
    """T-5 / T-15 / T-180 tip windows chip from tip_radar digest / quote cache."""
    digest = {}
    try:
        from helpers import tip_radar
        path = tip_radar.digest_path(root)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as handle:
                digest = json.load(handle)
        if not isinstance(digest, dict) or not digest.get("n"):
            games = tip_radar.games_from_quote_cache(root)
            digest = tip_radar.build_digest(games)
    except Exception:
        digest = {}
    games = digest.get("games") if isinstance(digest.get("games"), list) else []
    t5 = sum(1 for g in games if isinstance(g, dict) and g.get("priority") == "T-5")
    t15 = sum(1 for g in games if isinstance(g, dict) and g.get("priority") == "T-15")
    t180 = sum(1 for g in games if isinstance(g, dict) and g.get("priority") == "T-180")
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "n": digest.get("n") if digest.get("n") is not None else len(games),
        "t5": t5,
        "t15": t15,
        "t180": t180,
        "nearest": games[0] if games else None,
        "label": f"tip radar n={digest.get('n') or len(games)} T-5={t5} T-15={t15} T-180={t180}",
        "note": digest.get("note") or "Observe-only tip radar. Never waives sports 0.06.",
    }


def calib_nag_chip(root: str | None = None, bots: list | None = None) -> dict:
    """raise_phi calibration ticket count chip (staff dual-control only)."""
    digest = {}
    try:
        from helpers import calib_nag
        path = calib_nag.digest_path(root)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as handle:
                digest = json.load(handle)
        if not isinstance(digest, dict) or digest.get("tickets_n") is None:
            digest = calib_nag.write_digest_from_desk(root, bots=bots)
    except Exception:
        digest = {}
    tickets = digest.get("tickets") if isinstance(digest.get("tickets"), list) else []
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "auto_write_phi": False,
        "tickets_n": digest.get("tickets_n") if digest.get("tickets_n") is not None else len(tickets),
        "tickets": tickets[:6],
        "boards": digest.get("boards") if isinstance(digest.get("boards"), list) else [],
        "label": f"calib raise_phi tickets={digest.get('tickets_n') or len(tickets)}",
        "note": digest.get("note") or (
            "raise_phi is a staff ticket — never silent Φ write, never softer floors."
        ),
    }


def bleed_chip(root: str | None = None, bots: list | None = None) -> dict:
    """Firm bleed ratio + misplaced capital chip."""
    bleed = {}
    misplaced = {}
    try:
        import desk_roi_plan
        bleed = desk_roi_plan.firm_bleed_ratio(bots) or {}
        misplaced = desk_roi_plan.capital_misplaced(bots) or {}
    except Exception:
        bleed, misplaced = {}, {}
    ratio = bleed.get("ratio")
    ok = bleed.get("pass")
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "ratio": ratio,
        "red_usd": bleed.get("red_usd"),
        "green_usd": bleed.get("green_usd"),
        "target_lt": bleed.get("target_lt") or 0.5,
        "pass": ok,
        "misplaced_usd": misplaced.get("misplaced_usd") or misplaced.get("misplaced"),
        "label": (
            f"bleed ratio={ratio} "
            + ("ok" if ok else "hot" if ok is False else "n/a")
            + f" misplaced={misplaced.get('misplaced_usd') or misplaced.get('misplaced')}"
        ),
        "note": bleed.get("note") or "Bleed uses Chicago today PnL; quiet $0 ignored.",
    }


def clv_chip(root: str | None = None) -> dict:
    """Sports CLV completeness / beat-close evidence chip."""
    status = {}
    try:
        import desk_roi_plan
        status = desk_roi_plan.clv_completeness(root) or {}
    except Exception:
        status = {}
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "n": status.get("n"),
        "complete": status.get("complete"),
        "rate": status.get("rate"),
        "settled_rate": status.get("settled_rate"),
        "pass": status.get("pass"),
        "label": (
            f"CLV complete={status.get('complete')}/{status.get('n')} "
            f"rate={status.get('rate')} "
            + ("ok" if status.get("pass") else "gaps" if status.get("pass") is False else "n/a")
        ),
        "note": status.get("note") or (
            "Every sports settle should log entry fair + clv — never softens 0.06."
        ),
    }


def skip_regret_chip(root: str | None = None) -> dict:
    """Labeled skip-regret twin chip — never auto-loosens floors."""
    card = {}
    try:
        import desk_roi_plan
        card = desk_roi_plan.latest_skip_regret_weekly(root) or {}
        if not card:
            # Observe-only summary without writing a weekly card.
            try:
                import desk_top25
                summary = desk_top25.skip_regret_summary(root) or {}
            except Exception:
                summary = {}
            card = {
                "n": summary.get("n"),
                "labeled_n": summary.get("labeled_n"),
                "avg_would_pnl": summary.get("avg_would_pnl"),
                "green_twin": bool(summary.get("green_twin")),
                "decision": "reject",
                "auto_promote": False,
                "loosen_soft_gates": False,
                "fee_floors_locked": True,
            }
    except Exception:
        card = {}
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "n": card.get("n"),
        "labeled_n": card.get("labeled_n"),
        "avg_would_pnl": card.get("avg_would_pnl"),
        "green_twin": bool(card.get("green_twin")),
        "decision": card.get("decision") or "reject",
        "auto_promote": False,
        "loosen_soft_gates": False,
        "label": (
            f"skip-regret labeled={card.get('labeled_n')} "
            f"avg={card.get('avg_would_pnl')} "
            f"{card.get('decision') or 'reject'}"
        ),
        "note": card.get("note") or (
            "Skip-regret twin: staff-only soft gate review; fee floors locked."
        ),
    }


def hard_stop_chip(root: str | None = None) -> dict:
    """Sports hard-stop shadow exits readiness chip."""
    status = {}
    try:
        import desk_roi_plan
        status = desk_roi_plan.sports_hard_stop_shadow_summary(root) or {}
    except Exception:
        status = {}
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "n": status.get("n"),
        "n_with_pnl": status.get("n_with_pnl"),
        "shadow_expectancy": status.get("shadow_expectancy"),
        "promote_ready": bool(status.get("promote_ready")),
        "live": bool(status.get("live")),
        "auto_promote": False,
        "decision": status.get("decision") or "reject",
        "label": (
            f"hard-stop n={status.get('n_with_pnl')} "
            f"ev={status.get('shadow_expectancy')} "
            f"ready={bool(status.get('promote_ready'))} "
            f"live={bool(status.get('live'))}"
        ),
        "note": status.get("note") or (
            "Shadow-only until staff promote; code default live stays False."
        ),
    }


def timer_heartbeat_chip(root: str | None = None) -> dict:
    """Alive/dead paper timer chip for desk snapshot."""
    status = {}
    try:
        import pimp_desk
        status = pimp_desk.timer_health(root) or {}
    except Exception:
        status = {}
    alive = bool(status.get("alive"))
    age = status.get("age")
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "alive": alive,
        "age_sec": age,
        "weekday_alert": bool(status.get("weekday_alert")),
        "alert": status.get("alert") or "",
        "label": (
            f"timer {'alive' if alive else 'DEAD'}"
            + (f" age={age}s" if age is not None else "")
        ),
        "note": status.get("detail") or "Discord paper_timer heartbeat.",
    }


def helper_gate_a_board(root: str | None = None) -> dict:
    """Attributed helper fills Gate A readiness (observe-only until staff)."""
    status = {}
    try:
        import desk_roi_plan
        status = desk_roi_plan.helper_promote_status(root) or {}
    except Exception:
        status = {}
    helpers = status.get("helpers") if isinstance(status.get("helpers"), list) else []
    ready_n = sum(1 for h in helpers if isinstance(h, dict) and h.get("promote_ready"))
    armed_n = sum(1 for h in helpers if isinstance(h, dict) and h.get("armed"))
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "auto_promote": False,
        "places_orders": False,
        "helpers_n": len(helpers),
        "ready_n": ready_n,
        "armed_n": armed_n,
        "helpers": helpers[:12],
        "label": f"helper Gate A ready={ready_n}/{len(helpers)} armed={armed_n}",
        "note": status.get("note") or (
            "Helpers never place alone until Gate A + staff promote."
        ),
    }


def empty_card_chip(root: str | None = None) -> dict:
    """Empty-market CARD latency chip (3s bar) for HUD."""
    status = {}
    try:
        import desk_roi_plan
        status = desk_roi_plan.empty_card_status(root) or {}
    except Exception:
        status = {}
    p50 = status.get("p50_s") or status.get("p50") or status.get("last_sec")
    ok = status.get("pass")
    if ok is None and p50 is not None:
        try:
            ok = float(p50) <= 3.0
        except (TypeError, ValueError):
            ok = None
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "n": status.get("n"),
        "p50_s": p50,
        "max_s": status.get("max_s"),
        "pass": ok,
        "bar_sec": status.get("bar_sec") or 3.0,
        "label": (
            f"empty CARD p50={p50}s "
            + ("ok" if ok else "slow" if ok is False else "n/a")
        ),
        "note": status.get("note") or "Empty CARD <3s bar — speed without softer floors.",
    }


def near_miss_chip(root: str | None = None) -> dict:
    """Near-miss soft z|p promote readiness chip (observe-only)."""
    status = {}
    try:
        import desk_roi_plan
        status = desk_roi_plan.near_miss_promote_status(root) or {}
    except Exception:
        status = {}
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "n": status.get("n"),
        "labeled_n": status.get("labeled_n"),
        "shadow_ev": status.get("shadow_ev"),
        "promote_ready": bool(status.get("promote_ready")),
        "soft_live": status.get("soft_live"),
        "decision": status.get("decision"),
        "auto_promote": False,
        "label": (
            f"near-miss n={status.get('n')} labeled={status.get('labeled_n')} "
            f"ev={status.get('shadow_ev')} ready={bool(status.get('promote_ready'))}"
        ),
        "note": status.get("note") or (
            "Soft allowlist z|p only — never edge / fee floors."
        ),
    }


def firm_queue_chip(root: str | None = None) -> dict:
    """Compact firm-queue HUD: offers / accepted / deferred / remaining risk."""
    status = {}
    try:
        import desk_roi_plan
        status = desk_roi_plan.firm_queue_status(root) or {}
    except Exception:
        status = {}
    offers_n = status.get("offers_n")
    accepted_n = status.get("accepted_n")
    deferred_n = status.get("deferred_n")
    remaining = status.get("remaining_risk")
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "offers_n": offers_n,
        "accepted_n": accepted_n,
        "deferred_n": deferred_n,
        "remaining_risk": remaining,
        "ttl_sec": status.get("ttl_sec"),
        "label": (
            f"firm queue offers={offers_n} acc={accepted_n} def={deferred_n} "
            f"risk_left={remaining}"
        ),
        "note": status.get("note") or (
            "Firm queue ranks fee-clear fits — deferred so best edge spends desk risk first."
        ),
    }


def green_day_board(root: str | None = None, bots: list | None = None) -> dict:
    """Fee-clear green-day / selective +1 readiness for HUD (floors locked)."""
    fee_clear = []
    green_n = 0
    red_n = 0
    for bot in bots or []:
        if not isinstance(bot, dict):
            continue
        bot_id = str(bot.get("id") or "")
        if bot_id not in FEE_CLEAR:
            continue
        today = _f(bot.get("today"))
        row = {
            "bot": bot_id,
            "today": today,
            "green": today is not None and today >= 0,
            "selective_eligible": today is not None and today >= 0,
        }
        fee_clear.append(row)
        if today is None:
            continue
        if today >= 0:
            green_n += 1
        else:
            red_n += 1
    boost = {}
    try:
        import desk_roi_plan
        boost = desk_roi_plan.sports_green_boost_status(root, bots=bots) or {}
    except Exception:
        boost = {}
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "fee_clear_towers": sorted(FEE_CLEAR),
        "towers": fee_clear,
        "green_n": green_n,
        "red_n": red_n,
        "all_fee_clear_green": bool(fee_clear) and red_n == 0 and green_n == len(fee_clear),
        "sports_green_boost": {
            "ready": bool(boost.get("ready")),
            "green_boost": int(boost.get("green_boost") or 0),
            "auto_promote": False,
        },
        "note": (
            "Selective +1 only on fee-clear green days; sports green_boost stays 0 "
            "until CLV+M1 gate ready. Never softens venue floors."
        ),
    }


def skip_taxonomy_chip(root: str | None = None) -> dict:
    """Top stable skip codes for teller rail / city chip (observe-only)."""
    board = {}
    try:
        import desk_more
        board = desk_more.skip_leaderboard(root) or {}
    except Exception:
        board = {}
    top = list(board.get("stable_top") or board.get("top") or [])[:5]
    head = top[0] if top and isinstance(top[0], dict) else {}
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "day": board.get("day"),
        "top": top,
        "top_code": head.get("code"),
        "top_n": head.get("n"),
        "weekend_share": board.get("weekend_share"),
        "label": (
            f"top skip {head.get('code')} ×{head.get('n')}"
            if head.get("code")
            else "skip taxonomy quiet"
        ),
        "note": board.get("note") or "Observe-only skip taxonomy chip.",
    }


def insight_swarm_ratio(root: str | None = None) -> dict:
    """Insight:betting headcount audit — living hire order requires ≥3:1 until M1≥0."""
    helpers = {}
    for name in INSIGHT_HELPER_DIGESTS:
        path = os.path.join(_root(root), "helpers", name)
        key = name.replace("_digest.json", "").replace(".json", "")
        helpers[key] = os.path.isfile(path)
    insight_n = sum(1 for v in helpers.values() if v)
    betting_n = len(BETTING_TOWERS)
    ratio = round(insight_n / betting_n, 4) if betting_n else None
    ok = bool(ratio is not None and ratio + 1e-12 >= INSIGHT_BETTING_MIN_RATIO)
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "insight_n": insight_n,
        "betting_n": betting_n,
        "ratio": ratio,
        "min_ratio": INSIGHT_BETTING_MIN_RATIO,
        "pass": ok,
        "insight_helpers": helpers,
        "betting_towers": list(BETTING_TOWERS),
        "note": (
            "Insight swarm ≥3:1 vs betting towers until firm M1 ≥ 0. "
            "Hire observe-only clerks first — never meme/INX spam."
            if not ok
            else "Insight:betting headcount meets ≥3:1 living hire order. Floors locked."
        ),
    }


def living_upgrade_board(root: str | None = None, bots: list | None = None) -> dict:
    """Masters card: data + completions health for the living upgrade."""
    feat = feature_store_coverage(root)
    quiet = feature_store_quiet_alert(root)
    comp = completions_summary(root)
    ai = living_ai_health(root, bots=bots)
    swarm = insight_swarm_ratio(root)
    helpers = swarm.get("insight_helpers") or {}
    hillclimb = None
    dual = None
    ruin = None
    try:
        import desk_roi_plan
        hillclimb = desk_roi_plan.hillclimb_lever_status(root)
        dual = desk_roi_plan.dual_control_status(root)
        ruin = desk_roi_plan.ruin_drill_status(root)
    except Exception:
        hillclimb = None
        dual = None
        ruin = None
    board = {
        "paper_only": True,
        "feature_store": feat,
        "feature_quiet": quiet,
        "feature_quiet_pager": feature_quiet_pager(root),
        "completions": comp,
        "living_ai": ai,
        "insight_swarm": swarm,
        "hillclimb_lever": hillclimb,
        "dual_control": dual,
        "ruin_drill": ruin,
        "skip_taxonomy": skip_taxonomy_chip(root),
        "green_day": green_day_board(root, bots=bots),
        "firm_queue": firm_queue_chip(root),
        "empty_card": empty_card_chip(root),
        "near_miss": near_miss_chip(root),
        "timer_heartbeat": timer_heartbeat_chip(root),
        "helper_gate_a": helper_gate_a_board(root),
        "skip_regret": skip_regret_chip(root),
        "hard_stop": hard_stop_chip(root),
        "bleed": bleed_chip(root, bots=bots),
        "clv": clv_chip(root),
        "tip_radar": tip_radar_chip(root),
        "calib_nag": calib_nag_chip(root, bots=bots),
        "injury_wire": injury_wire_chip(root),
        "eia_scout": eia_scout_chip(root),
        "skip_historian": skip_historian_chip(root),
        "distance_clerk": distance_clerk_chip(root),
        "quant_clerk": quant_clerk_chip(root),
        "bookkeeper": bookkeeper_chip(root),
        "reporter": reporter_chip(root),
        "empty_card_bee": empty_card_bee_chip(root),
        "near_miss_clerk": near_miss_clerk_chip(root),
        "hard_stop_clerk": hard_stop_clerk_chip(root),
        "bleed_clerk": bleed_clerk_chip(root, bots=bots),
        "skip_twin_clerk": skip_twin_clerk_chip(root),
        "clv_closer": clv_closer_chip(root),
        "timer_digest": timer_digest_chip(root),
        "calendar_scanner": calendar_scanner_chip(root),
        "eia_blackout": eia_blackout_chip(root),
        "clerk_pulse": clerk_pulse_chip(root),
        "dual_control_chip": dual_control_chip(root),
        "ruin_drill_chip": ruin_drill_chip(root),
        "completions_chip": completions_chip(root),
        "teller_living": teller_living_chip(root, bots=bots),
        "fee_floors_assert": fee_floors_assert(root),
        "dual_control_gaps": dual_control_gaps_page(root),
        "hillclimb_chip": hillclimb_chip(root),
        "digest_inventory": digest_inventory(root),
        "ruin_drill_page": ruin_drill_page(root),
        "insight_helper_digests": helpers,
        "insight_helpers_present": int(swarm.get("insight_n") or 0),
        "chicago_today": chicago_today_iso(),
        "fee_floors_locked": True,
        "insight_first": True,
        "grok_buys": False,
        "live_orders_enabled": False,
        "note": "Living Trading Upgrade board — more eligible completions + learn data.",
    }
    board["compact"] = living_compact_card(root, bots=bots, board=board)
    return board


def ruin_drill_page(root: str | None = None) -> dict:
    """Staff markdown when ruin drill not practiced this Chicago month."""
    status: dict = {}
    try:
        import desk_roi_plan
        status = desk_roi_plan.ruin_drill_status(root) or {}
    except Exception:
        status = {}
    practiced = bool(status.get("practiced_this_month"))
    active = bool(status.get("active"))
    page = bool(active or not practiced)
    lines = [
        "**RUIN DRILL** (paper vault practice — never enables live)",
        f"active={active} level={status.get('level')} "
        f"practiced_this_month={practiced} "
        f"last={status.get('last_practice_at')}",
        "",
        "Levels:",
        "- soft — block new entries; exits/settles still run",
        "- hard — soft + pause every paper bot",
        "- nuclear — hard + recommend flatten / cancel-on-pause habit",
        "",
        "Staff: `python3 tools/staff_ruin_drill.py set soft` then clear when done.",
        "",
        "_floors locked · LIVE_ORDERS_ENABLED=False · staff ack only_",
    ]
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "live_orders_enabled": False,
        "auto_page": False,
        "page": page,
        "practiced_this_month": practiced,
        "active": active,
        "level": status.get("level"),
        "copy": "\n".join(lines),
        "label": (
            f"ruin page active={active} practiced_month={practiced}"
        ),
        "note": status.get("note") or (
            "Practice soft/hard this Chicago month for dual-control."
        ),
    }


def seed_missing_digests(root: str | None = None, *, bots: list | None = None) -> dict:
    """Staff seed empty observe digests for missing insight helpers (never places)."""
    inv_before = digest_inventory(root)
    seeded: list[str] = []
    errors: list[dict] = []
    for key in inv_before.get("missing") or []:
        try:
            if key == "sunday_living_packet":
                from helpers import sunday_packet
                sunday_packet.write_packet(root)
                seeded.append(key)
                continue
            if key == "calendar":
                from helpers import calendar_scanner
                calendar_scanner.scan(root)
                seeded.append(key)
                continue
            if key == "clerk_pulse":
                from helpers import clerk_pulse
                clerk_pulse.refresh_clerks(root, bots=bots)
                seeded.append(key)
                continue
            if key == "timer_heartbeat":
                from helpers import timer_heartbeat
                timer_heartbeat.probe_from_snapshot(root)
                seeded.append(key)
                continue
            mod = __import__(f"helpers.{key}", fromlist=["*"])
            if hasattr(mod, "write_digest_from_desk"):
                mod.write_digest_from_desk(root)
                seeded.append(key)
            elif hasattr(mod, "write_digest"):
                mod.write_digest(root)
                seeded.append(key)
            else:
                errors.append({"helper": key, "error": "no_write"})
        except Exception as exc:  # noqa: BLE001
            errors.append({"helper": key, "error": type(exc).__name__})
    inv_after = digest_inventory(root)
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "may_place_alone": False,
        "seeded": seeded,
        "seeded_n": len(seeded),
        "errors": errors,
        "before": {
            "present_n": inv_before.get("present_n"),
            "missing": inv_before.get("missing"),
        },
        "after": {
            "present_n": inv_after.get("present_n"),
            "missing": inv_after.get("missing"),
            "pass": inv_after.get("pass"),
            "ratio": inv_after.get("ratio"),
        },
        "note": "Seeded empty observe digests only — never places; floors locked.",
    }


def living_board_export(root: str | None = None, bots: list | None = None) -> dict:
    """Compact JSON export of living board for staff paste / archive."""
    board = living_upgrade_board(root, bots=bots)
    keep = (
        "chicago_today", "fee_floors_locked", "live_orders_enabled", "compact",
        "insight_swarm", "digest_inventory", "feature_quiet", "feature_quiet_pager",
        "dual_control_gaps", "hillclimb_chip", "ruin_drill_chip", "completions_chip",
        "timer_heartbeat", "bleed", "clv", "green_day", "firm_queue",
    )
    slim = {k: board.get(k) for k in keep if k in board}
    slim["paper_only"] = True
    slim["export"] = "living_board_v1"
    slim["note"] = "Staff export — never invent fills; never soften floors; never enable live."
    return slim


def dual_control_gaps_page(root: str | None = None) -> dict:
    """Staff checklist gaps copy for unsigned dual-control items (never auto-pages)."""
    status: dict = {}
    try:
        import desk_roi_plan
        status = desk_roi_plan.dual_control_status(root) or {}
    except Exception:
        status = {}
    items = status.get("items") if isinstance(status.get("items"), list) else []
    gaps = [
        {
            "id": str(it.get("id") or ""),
            "label": str(it.get("label") or "")[:120],
        }
        for it in items
        if isinstance(it, dict) and not it.get("signed")
    ]
    page = bool(gaps) and not bool(status.get("arm_ready_paper"))
    lines = [
        "**DUAL-CONTROL GAPS** (paper checklist — never enables live)",
        f"signed={status.get('signed_n')}/{status.get('items_n')} "
        f"two_staff={bool(status.get('two_staff'))} "
        f"arm_ready_paper={bool(status.get('arm_ready_paper'))}",
        "",
    ]
    for g in gaps:
        lines.append(f"- [ ] `{g.get('id')}` — {g.get('label')}")
    if not gaps:
        lines.append("- all checklist items signed (still paper-only; live lock stays False)")
    lines.append("")
    lines.append("_floors locked · LIVE_ORDERS_ENABLED=False · staff ack only_")
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "live_orders_enabled": False,
        "auto_page": False,
        "page": page,
        "gaps_n": len(gaps),
        "gaps": gaps,
        "signed_n": status.get("signed_n"),
        "items_n": status.get("items_n"),
        "copy": "\n".join(lines),
        "label": (
            f"dual-control gaps={len(gaps)} signed={status.get('signed_n')}/{status.get('items_n')}"
        ),
        "note": status.get("note") or (
            "Unsigned dual-control items — staff signs via tools/staff_dual_control.py."
        ),
    }


def hillclimb_chip(root: str | None = None) -> dict:
    """Hillclimb lever status chip — active lever only when staff-set."""
    status: dict = {}
    try:
        import desk_roi_plan
        status = desk_roi_plan.hillclimb_lever_status(root) or {}
    except Exception:
        status = {}
    active = status.get("active") if isinstance(status.get("active"), dict) else None
    name = None
    if active:
        name = active.get("name") or active.get("lever") or active.get("id")
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "auto_promote": False,
        "auto_revert": bool(status.get("auto_revert")),
        "week": status.get("week"),
        "active": active,
        "active_name": name,
        "active_this_week": bool(status.get("active_this_week") or active),
        "kill": status.get("kill"),
        "label": (
            f"hillclimb lever={name} week={status.get('week')}"
            if name
            else f"hillclimb none week={status.get('week')}"
        ),
        "note": status.get("note") or (
            "One allowlisted lever per Chicago week — floors locked."
        ),
    }


def digest_inventory(root: str | None = None) -> dict:
    """Count insight helper digests present vs expected (≥3:1 hire order)."""
    present = []
    missing = []
    base = os.path.join(_root(root), "helpers")
    for name in INSIGHT_HELPER_DIGESTS:
        path = os.path.join(base, name)
        key = name.replace("_digest.json", "").replace(".json", "")
        if os.path.isfile(path):
            present.append(key)
        else:
            missing.append(key)
    expected_n = len(INSIGHT_HELPER_DIGESTS)
    present_n = len(present)
    betting_n = len(BETTING_TOWERS)
    ratio = round(present_n / betting_n, 4) if betting_n else None
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "expected_n": expected_n,
        "present_n": present_n,
        "missing_n": len(missing),
        "present": present,
        "missing": missing,
        "betting_n": betting_n,
        "ratio": ratio,
        "min_ratio": INSIGHT_BETTING_MIN_RATIO,
        "pass": bool(ratio is not None and ratio + 1e-12 >= INSIGHT_BETTING_MIN_RATIO),
        "label": (
            f"digest inventory {present_n}/{expected_n} "
            f"missing={len(missing)} ratio={ratio}"
        ),
        "note": (
            "Insight digests present vs expected. Hire observe clerks first — floors locked."
        ),
    }


def fee_floors_assert(root: str | None = None, cfg: dict | None = None) -> dict:
    """Staff assert: runtime venue edges at/above locked floors."""
    floors: dict = {}
    try:
        import desk_profit
        # Prefer explicit cfg; avoid heavy snapshot loads during board builds/tests.
        floors = desk_profit.venue_floors_locked(cfg if isinstance(cfg, dict) else None) or {}
    except Exception as exc:  # noqa: BLE001
        floors = {"paper_only": True, "locked": True, "all_ok": False, "error": type(exc).__name__}
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "live_orders_enabled": False,
        "all_ok": bool(floors.get("all_ok")),
        "venues": floors.get("venues") if isinstance(floors.get("venues"), dict) else {},
        "label": (
            "fee floors OK (0.06/0.05/0.02)"
            if floors.get("all_ok")
            else "fee floors CHECK — live edge below locked floor"
        ),
        "note": floors.get("note") or (
            "Venue min_edge floors are locked — selective volume never softens them."
        ),
    }


def living_self_check(root: str | None = None) -> dict:
    """Staff health probe for living spine (never places / never softens)."""
    board = living_upgrade_board(root)
    swarm = board.get("insight_swarm") if isinstance(board.get("insight_swarm"), dict) else {}
    quiet = board.get("feature_quiet") if isinstance(board.get("feature_quiet"), dict) else {}
    timer = board.get("timer_heartbeat") if isinstance(board.get("timer_heartbeat"), dict) else {}
    floors = bool(board.get("fee_floors_locked"))
    floors_assert = fee_floors_assert(root)
    ok = bool(
        floors
        and board.get("live_orders_enabled") is False
        and board.get("grok_buys") is False
        and floors_assert.get("all_ok")
    )
    return {
        "paper_only": True,
        "fee_floors_locked": floors,
        "live_orders_enabled": False,
        "ok": ok,
        "swarm_pass": swarm.get("pass"),
        "swarm_ratio": swarm.get("ratio"),
        "feature_quiet": bool(quiet.get("quiet")),
        "timer_alive": timer.get("alive"),
        "floors_assert": floors_assert,
        "chips_n": sum(
            1
            for k, v in board.items()
            if isinstance(v, dict) and v.get("fee_floors_locked") is True
        ),
        "chicago_today": board.get("chicago_today"),
        "note": "Living self_check — observe-only. Floors must stay locked.",
    }


def _f(v: Any):
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _load_json(path: str, default: dict) -> dict:
    if not os.path.isfile(path):
        return dict(default)
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else dict(default)
    except (OSError, json.JSONDecodeError):
        return dict(default)


def _save_json(path: str, data: dict) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)


if __name__ == "__main__":
    assert chicago_today_iso()
    print("desk_living self_check ok", living_upgrade_board())
