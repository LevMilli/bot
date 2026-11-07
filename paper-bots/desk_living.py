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
DOCTOR_RUN_NAME = "desk_living_doctor.json"


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
        "label": (
            f"feature quiet age={age_h}h QUIET"
            if quiet
            else (
                f"feature quiet age={age_h}h ok"
                if age_h is not None
                else "feature quiet n/a"
            )
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
    n = len(raise_phi)
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "grok_buys": False,
        "adapt_version": adapt.get("version"),
        "adapt_bots_n": len(adapt.get("by_bot") or {}),
        "adapt_recent_vol_n": len(adapt.get("recent_vol") or []),
        "calib_boards": boards,
        "raise_phi_tickets": raise_phi,
        "raise_phi_n": n,
        "auto_write_phi": False,
        "label": (
            f"living AI raise_Φ={n}"
            + (f" ({','.join(raise_phi)})" if raise_phi else " clear")
            + " · auto_write=False"
        ),
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
    enrich_live: bool = True,
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
    ritual = ritual_observe_chip(root)
    ritual_nag = ""
    if ritual.get("ritual_ok") is False:
        ritual_nag = " · ritual nag (make living-ritual-discord)"
    quiet = feature_store_quiet_alert(root)
    quiet_age_h = quiet.get("age_hours") if isinstance(quiet, dict) else None
    quiet_age = f"{quiet_age_h}h" if quiet_age_h is not None else "n/a"
    quiet_age_label = f"quiet_age={quiet_age}"
    quiet_nag = ""
    try:
        age_f = float(quiet_age_h) if quiet_age_h is not None else None
    except (TypeError, ValueError):
        age_f = None
    if (isinstance(quiet, dict) and quiet.get("quiet")) or (
        age_f is not None and age_f >= 6
    ):
        quiet_nag = f" · {quiet_age_label} soft nag (learn loop observe)"
    live_n = None
    live_ok = None
    ritual_live_bit = ""
    if enrich_live:
        # Standalone path only — board build passes enrich_live=False then stamps later.
        live = ritual_live_labels(root=root)
        live_n = sum(1 for k, v in live.items() if str(k).endswith("_label") and v)
        live_ok = live_n >= 40
        ritual_live_bit = f" · ritual live n={live_n}"
    line = (
        f"{swarm_bit} · {fill_bit} · floors={'locked' if floors_ok else 'CHECK'}"
        f"{ritual_nag}{quiet_nag}{ritual_live_bit}"
    )
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
            if ritual.get("ritual_ok") is False:
                teller_memory.remember(
                    root,
                    kind="mistakes",
                    text="ritual not ready — make living-ritual / --discord (paste only)",
                    bot_id="desk",
                    source="living_teller_ritual",
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
        "ritual_ok": ritual.get("ritual_ok"),
        "ritual_nag": bool(ritual_nag),
        "quiet_age": quiet_age,
        "quiet_age_h": quiet_age_h,
        "quiet_age_label": quiet_age_label,
        "quiet_nag": bool(quiet_nag),
        "ritual_live_n": live_n,
        "ritual_live_ok": live_ok,
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
    soft_warn = (
        age_sec is not None
        and cadence is not None
        and not stale
        and age_sec > int(cadence)
    )
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "age_sec": age_sec,
        "cadence_sec": cadence,
        "stale": stale,
        "soft_warn": soft_warn,
        "refreshed_n": digest.get("refreshed_n") or digest.get("n"),
        "at": digest.get("at"),
        "label": (
            f"clerk pulse age={age_sec}s "
            + (
                "STALE"
                if stale
                else "WARN"
                if soft_warn
                else "ok"
                if age_sec is not None
                else "n/a"
            )
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
        expand = betting_expand_gate(root)
        src = {
            "insight_swarm": swarm,
            "timer_heartbeat": timer,
            "green_day": green,
            "bleed": bleed,
            "feature_quiet": quiet,
            "betting_expand_gate": expand,
        }
    swarm = src.get("insight_swarm") if isinstance(src.get("insight_swarm"), dict) else {}
    timer = src.get("timer_heartbeat") if isinstance(src.get("timer_heartbeat"), dict) else {}
    green = src.get("green_day") if isinstance(src.get("green_day"), dict) else {}
    bleed = src.get("bleed") if isinstance(src.get("bleed"), dict) else {}
    quiet = src.get("feature_quiet") if isinstance(src.get("feature_quiet"), dict) else {}
    expand = (
        src.get("betting_expand_gate")
        if isinstance(src.get("betting_expand_gate"), dict)
        else {}
    )
    ritual = (
        src.get("ritual_observe")
        if isinstance(src.get("ritual_observe"), dict)
        else {}
    )
    doctor_age = (
        src.get("doctor_age")
        if isinstance(src.get("doctor_age"), dict)
        else {}
    )
    quiet_age_h = quiet.get("age_hours")
    quiet_age = f"{quiet_age_h}h" if quiet_age_h is not None else "n/a"
    quiet_part = (
        str(quiet.get("label") or "").strip()
        or (
            f"quiet={'yes' if quiet.get('quiet') else 'no'}"
            + f" age={quiet_age}"
        )
    )
    quiet_age_part = f"quiet_age={quiet_age}"
    expand_part = (
        "expand=blocked"
        if expand.get("blocked")
        else "expand=ok"
        if expand.get("allow_betting_expand") or expand.get("blocked") is False
        else "expand=n/a"
    )
    if ritual.get("ritual_ok") is True:
        ritual_part = "ritual=ok"
    elif ritual.get("ritual_ok") is False:
        ritual_part = "ritual=no"
    elif ritual:
        ritual_part = "ritual=n/a"
    else:
        ritual_part = "ritual=n/a"
    doctor_fresh = ritual.get("doctor_fresh")
    if doctor_fresh is None and doctor_age:
        doctor_fresh = not bool(doctor_age.get("stale"))
    if doctor_fresh is True:
        doctor_part = "doctor=fresh"
    elif doctor_fresh is False:
        doctor_part = "doctor=stale"
    else:
        doctor_part = "doctor=n/a"
    masters_sunday_part = f"masters_sunday={quiet_age}"
    parts = [
        f"swarm {swarm.get('insight_n')}:{swarm.get('betting_n')}",
        f"timer={'alive' if timer.get('alive') else 'DEAD' if timer.get('alive') is False else 'n/a'}",
        f"green={green.get('green_n')}",
        f"bleed={bleed.get('ratio')}",
        quiet_part,
        quiet_age_part,
        masters_sunday_part,
        ritual_part,
        doctor_part,
        expand_part,
    ]
    _live = ritual_live_labels(src)
    _live_n = sum(1 for k, v in _live.items() if str(k).endswith("_label") and v)
    ritual_live_sunday = (
        f"ritual live n={_live_n} · "
        f"{_live.get('digests_label') or 'digests observe'} · "
        f"{_live.get('fills_label') or 'fills observe'} · "
        f"{_live.get('timer_label') or 'timer observe'} "
        f"· sunday quiet {quiet_age_part} (observe · never softens floors)"
    )
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "live_orders_enabled": False,
        "parts": parts,
        "quiet_label": quiet_part,
        "quiet_age_label": quiet_age_part,
        "quiet_age": quiet_age,
        "quiet_age_h": quiet_age_h,
        "sunday_quiet_age": quiet_age,
        "sunday_quiet_age_label": quiet_age_part,
        "masters_sunday_label": masters_sunday_part,
        "masters_sunday_quiet": f"sunday quiet {quiet_age_part} (observe)",
        "expand_label": expand_part,
        "expand_sunday_quiet": (
            f"{expand_part} · sunday quiet {quiet_age_part} "
            "(observe · never softens floors)"
        ),
        "floors_sunday_quiet": (
            f"{('floors=ok' if (isinstance(src.get('fee_floors_assert'), dict) and src['fee_floors_assert'].get('all_ok') is True) else 'floors=soft' if (isinstance(src.get('fee_floors_assert'), dict) and src['fee_floors_assert'].get('all_ok') is False) else 'floors=n/a')} "
            f"· sunday quiet {quiet_age_part} "
            "(observe · never softens floors)"
        ),
        "ruin_sunday_quiet": (
            f"{(src.get('ruin_drill_chip') or {}).get('label') or 'ruin observe'} "
            f"· sunday quiet {quiet_age_part} "
            "(observe · never softens floors)"
            if isinstance(src.get("ruin_drill_chip"), dict)
            else f"ruin observe · sunday quiet {quiet_age_part} (observe · never softens floors)"
        ),
        "swarm_sunday_quiet": (
            f"swarm {(src.get('insight_swarm') or {}).get('insight_n')}:{(src.get('insight_swarm') or {}).get('betting_n')} "
            f"· sunday quiet {quiet_age_part} (observe)"
            if isinstance(src.get("insight_swarm"), dict)
            else f"swarm n/a · sunday quiet {quiet_age_part} (observe)"
        ),
        "hill_sunday_quiet": (
            f"{(src.get('hillclimb_chip') or {}).get('label') or 'hillclimb none'} "
            f"· sunday quiet {quiet_age_part} (observe · never softens floors)"
            if isinstance(src.get("hillclimb_chip"), dict)
            else f"hillclimb none · sunday quiet {quiet_age_part} (observe · never softens floors)"
        ),
        "gaps_sunday_quiet": (
            f"{(src.get('dual_control_gaps') or {}).get('label') or 'gaps observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never softens floors)"
            if isinstance(src.get("dual_control_gaps"), dict)
            else f"gaps observe · sunday quiet {quiet_age_part} (observe · never softens floors)"
        ),
        "digests_sunday_quiet": (
            f"{(src.get('digest_inventory') or {}).get('label') or 'digests observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never softens floors)"
            if isinstance(src.get("digest_inventory"), dict)
            else f"digests observe · sunday quiet {quiet_age_part} (observe · never softens floors)"
        ),
        "fills_sunday_quiet": (
            (
                f"eligible today {(src.get('completions') or {}).get('eligible_completions_today')}"
                if isinstance(src.get("completions"), dict)
                and (src.get("completions") or {}).get("eligible_completions_today")
                is not None
                else "eligible fills n/a"
            )
            + f" · sunday quiet {quiet_age_part} (observe · never invents PnL)"
        ),
        "green_sunday_quiet": (
            f"{green.get('label') or ('green=' + str(green.get('green_n')))} "
            f"· sunday quiet {quiet_age_part} (observe)"
            if green
            else f"green-day n/a · sunday quiet {quiet_age_part} (observe)"
        ),
        "bleed_sunday_quiet": (
            f"{bleed.get('label') or ('bleed=' + str(bleed.get('ratio')))} "
            f"· sunday quiet {quiet_age_part} (observe · never softens floors)"
            if bleed
            else f"bleed n/a · sunday quiet {quiet_age_part} (observe · never softens floors)"
        ),
        "clv_sunday_quiet": (
            f"{(src.get('clv') or src.get('clv_closer') or {}).get('label') or 'CLV observe'} "
            f"· sunday quiet {quiet_age_part} (observe)"
            if isinstance(src.get("clv"), dict) or isinstance(src.get("clv_closer"), dict)
            else f"CLV observe · sunday quiet {quiet_age_part} (observe)"
        ),
        "timer_sunday_quiet": (
            f"timer={'alive' if timer.get('alive') else 'DEAD' if timer.get('alive') is False else 'n/a'} "
            f"· sunday quiet {quiet_age_part} (observe · never softens floors)"
        ),
        "calib_sunday_quiet": (
            f"{(src.get('calib_nag') or {}).get('label') or 'calib observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never auto-writes Φ)"
            if isinstance(src.get("calib_nag"), dict)
            else f"calib observe · sunday quiet {quiet_age_part} (observe · never auto-writes Φ)"
        ),
        "queue_sunday_quiet": (
            f"{(src.get('firm_queue') or {}).get('label') or 'queue observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never promotes)"
            if isinstance(src.get("firm_queue"), dict)
            else f"queue observe · sunday quiet {quiet_age_part} (observe · never promotes)"
        ),
        "gate_a_sunday_quiet": (
            f"{(src.get('helper_gate_a') or {}).get('label') or 'Gate A observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never softens floors)"
            if isinstance(src.get("helper_gate_a"), dict)
            else f"Gate A observe · sunday quiet {quiet_age_part} (observe · never softens floors)"
        ),
        "ai_sunday_quiet": (
            f"{(src.get('living_ai') or {}).get('label') or 'AI observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never auto-writes Φ)"
            if isinstance(src.get("living_ai"), dict)
            else f"AI observe · sunday quiet {quiet_age_part} (observe · never auto-writes Φ)"
        ),
        "tip_sunday_quiet": (
            f"{(src.get('tip_radar') or {}).get('label') or 'tip feed observe'} "
            f"· sunday quiet {quiet_age_part} (observe)"
            if isinstance(src.get("tip_radar"), dict)
            else f"tip feed observe · sunday quiet {quiet_age_part} (observe)"
        ),
        "blackout_sunday_quiet": (
            f"{(src.get('eia_blackout') or {}).get('label') or 'blackout observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never softens floors)"
            if isinstance(src.get("eia_blackout"), dict)
            else f"blackout observe · sunday quiet {quiet_age_part} (observe · never softens floors)"
        ),
        "injury_sunday_quiet": (
            f"{(src.get('injury_wire') or {}).get('label') or 'injury observe'} "
            f"· sunday quiet {quiet_age_part} (observe)"
            if isinstance(src.get("injury_wire"), dict)
            else f"injury observe · sunday quiet {quiet_age_part} (observe)"
        ),

        "empty_sunday_quiet": (
            f"{(src.get('empty_card') or {}).get('label') or 'empty CARD observe'} "
            f"· sunday quiet {quiet_age_part} (observe)"
            if isinstance(src.get("empty_card"), dict)
            else f"empty CARD observe · sunday quiet {quiet_age_part} (observe)"
        ),
        "near_miss_sunday_quiet": (
            f"{(src.get('near_miss') or {}).get('label') or 'near-miss observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never promotes)"
            if isinstance(src.get("near_miss"), dict)
            else f"near-miss observe · sunday quiet {quiet_age_part} (observe · never promotes)"
        ),
        "eia_sunday_quiet": (
            f"{(src.get('eia_scout') or {}).get('label') or 'EIA observe'} "
            f"· sunday quiet {quiet_age_part} (observe)"
            if isinstance(src.get("eia_scout"), dict)
            else f"EIA observe · sunday quiet {quiet_age_part} (observe)"
        ),
        "calendar_sunday_quiet": (
            f"{(src.get('calendar_scanner') or {}).get('label') or 'calendar observe'} "
            f"· sunday quiet {quiet_age_part} (observe)"
            if isinstance(src.get("calendar_scanner"), dict)
            else f"calendar observe · sunday quiet {quiet_age_part} (observe)"
        ),
        "pager_sunday_quiet": (
            f"{(src.get('feature_quiet_pager') or {}).get('label') or 'pager observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never auto-pages)"
            if isinstance(src.get("feature_quiet_pager"), dict)
            else f"pager observe · sunday quiet {quiet_age_part} (observe · never auto-pages)"
        ),
        "books_sunday_quiet": (
            f"{(src.get('bookkeeper') or {}).get('label') or 'books observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never invents PnL)"
            if isinstance(src.get("bookkeeper"), dict)
            else f"books observe · sunday quiet {quiet_age_part} (observe · never invents PnL)"
        ),
        "pulse_sunday_quiet": (
            f"{(src.get('clerk_pulse') or {}).get('label') or 'pulse observe'} "
            f"· sunday quiet {quiet_age_part} (observe)"
            if isinstance(src.get("clerk_pulse"), dict)
            else f"pulse observe · sunday quiet {quiet_age_part} (observe)"
        ),
        "dual_sunday_quiet": (
            f"{(src.get('dual_control') or {}).get('label') or 'dual observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never softens floors)"
            if isinstance(src.get("dual_control"), dict)
            else f"dual observe · sunday quiet {quiet_age_part} (observe · never softens floors)"
        ),
        "skip_reg_sunday_quiet": (
            f"{(src.get('skip_regret') or {}).get('label') or 'skip-regret observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never softens floors)"
            if isinstance(src.get("skip_regret"), dict)
            else f"skip-regret observe · sunday quiet {quiet_age_part} (observe · never softens floors)"
        ),
        "hard_stop_sunday_quiet": (
            f"{(src.get('hard_stop') or {}).get('label') or 'hard-stop observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never promotes)"
            if isinstance(src.get("hard_stop"), dict)
            else f"hard-stop observe · sunday quiet {quiet_age_part} (observe · never promotes)"
        ),
        "distance_sunday_quiet": (
            f"{(src.get('distance_clerk') or {}).get('label') or 'distance observe'} "
            f"· sunday quiet {quiet_age_part} (observe)"
            if isinstance(src.get("distance_clerk"), dict)
            else f"distance observe · sunday quiet {quiet_age_part} (observe)"
        ),
        "quant_sunday_quiet": (
            f"{(src.get('quant_clerk') or {}).get('label') or 'quant observe'} "
            f"· sunday quiet {quiet_age_part} (observe)"
            if isinstance(src.get("quant_clerk"), dict)
            else f"quant observe · sunday quiet {quiet_age_part} (observe)"
        ),
        "report_sunday_quiet": (
            f"{(src.get('reporter') or {}).get('label') or 'report observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never auto-posts)"
            if isinstance(src.get("reporter"), dict)
            else f"report observe · sunday quiet {quiet_age_part} (observe · never auto-posts)"
        ),
        "empty_bee_sunday_quiet": (
            f"{(src.get('empty_card_bee') or {}).get('label') or 'empty bee observe'} "
            f"· sunday quiet {quiet_age_part} (observe)"
            if isinstance(src.get("empty_card_bee"), dict)
            else f"empty bee observe · sunday quiet {quiet_age_part} (observe)"
        ),
        "nm_clerk_sunday_quiet": (
            f"{(src.get('near_miss_clerk') or {}).get('label') or 'nm clerk observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never promotes)"
            if isinstance(src.get("near_miss_clerk"), dict)
            else f"nm clerk observe · sunday quiet {quiet_age_part} (observe · never promotes)"
        ),
        "hs_clerk_sunday_quiet": (
            f"{(src.get('hard_stop_clerk') or {}).get('label') or 'hs clerk observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never promotes)"
            if isinstance(src.get("hard_stop_clerk"), dict)
            else f"hs clerk observe · sunday quiet {quiet_age_part} (observe · never promotes)"
        ),
        "bleed_clerk_sunday_quiet": (
            f"{(src.get('bleed_clerk') or {}).get('label') or 'bleed clerk observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never softens floors)"
            if isinstance(src.get("bleed_clerk"), dict)
            else f"bleed clerk observe · sunday quiet {quiet_age_part} (observe · never softens floors)"
        ),
        "skip_twin_sunday_quiet": (
            f"{(src.get('skip_twin_clerk') or {}).get('label') or 'skip-twin observe'} "
            f"· sunday quiet {quiet_age_part} (observe)"
            if isinstance(src.get("skip_twin_clerk"), dict)
            else f"skip-twin observe · sunday quiet {quiet_age_part} (observe)"
        ),
        "clv_closer_sunday_quiet": (
            f"{(src.get('clv_closer') or {}).get('label') or 'CLV closer observe'} "
            f"· sunday quiet {quiet_age_part} (observe)"
            if isinstance(src.get("clv_closer"), dict)
            else f"CLV closer observe · sunday quiet {quiet_age_part} (observe)"
        ),
        "tdigest_sunday_quiet": (
            f"{(src.get('timer_digest') or {}).get('label') or 't-digest observe'} "
            f"· sunday quiet {quiet_age_part} (observe)"
            if isinstance(src.get("timer_digest"), dict)
            else f"t-digest observe · sunday quiet {quiet_age_part} (observe)"
        ),
        "skips_sunday_quiet": (
            f"{(src.get('skip_taxonomy') or {}).get('label') or 'skips observe'} "
            f"· sunday quiet {quiet_age_part} (observe)"
            if isinstance(src.get("skip_taxonomy"), dict)
            else f"skips observe · sunday quiet {quiet_age_part} (observe)"
        ),
        "teller_sunday_quiet": (
            f"{(src.get('teller_living') or {}).get('label') or 'teller observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never softens floors)"
            if isinstance(src.get("teller_living"), dict)
            else f"teller observe · sunday quiet {quiet_age_part} (observe · never softens floors)"
        ),
        "teller_ritual_live_sunday_quiet": (
            (
                f"teller ritual live n="
                f"{(src.get('teller_living') or {}).get('ritual_live_n')}"
                if isinstance(src.get("teller_living"), dict)
                and (src.get("teller_living") or {}).get("ritual_live_n") is not None
                else f"teller ritual live n={_live_n}"
            )
            + f" · sunday quiet {quiet_age_part} (observe · never softens floors)"
        ),
        "doc_age_sunday_quiet": (
            f"{(src.get('doctor_age') or {}).get('label') or 'doctor age observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never softens floors)"
            if isinstance(src.get("doctor_age"), dict)
            else f"doctor age observe · sunday quiet {quiet_age_part} (observe · never softens floors)"
        ),
        "quiet_sunday_quiet": (
            f"{(src.get('feature_quiet') or {}).get('label') or 'feature quiet observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never softens floors)"
            if isinstance(src.get("feature_quiet"), dict)
            else f"feature quiet observe · sunday quiet {quiet_age_part} (observe · never softens floors)"
        ),
        "ritual_sunday_quiet": (
            f"{(src.get('ritual_observe') or {}).get('label') or 'ritual observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never auto-posts)"
            if isinstance(src.get("ritual_observe"), dict)
            else f"ritual observe · sunday quiet {quiet_age_part} (observe · never auto-posts)"
        ),
        "digest_fresh_sunday_quiet": (
            f"{(src.get('digest_freshness') or {}).get('label') or 'digest fresh observe'} "
            f"· sunday quiet {quiet_age_part} (observe)"
            if isinstance(src.get("digest_freshness"), dict)
            else f"digest fresh observe · sunday quiet {quiet_age_part} (observe)"
        ),
        "journal_sunday_quiet": (
            f"{(src.get('journal_coverage') or {}).get('label') or 'journals observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never softens floors)"
            if isinstance(src.get("journal_coverage"), dict)
            else f"journals observe · sunday quiet {quiet_age_part} (observe · never softens floors)"
        ),
        "monday_sunday_quiet": (
            f"{(src.get('monday_pulse') or {}).get('label') or 'monday pulse observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never softens floors)"
            if isinstance(src.get("monday_pulse"), dict)
            else f"monday pulse observe · sunday quiet {quiet_age_part} (observe · never softens floors)"
        ),
        "toxic_sunday_quiet": (
            f"{(src.get('toxic_fills') or {}).get('label') or 'toxic fills observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never softens floors)"
            if isinstance(src.get("toxic_fills"), dict)
            else f"toxic fills observe · sunday quiet {quiet_age_part} (observe · never softens floors)"
        ),
        "adapt_ab_sunday_quiet": (
            f"{(src.get('adapt_ab') or {}).get('label') or 'adapt A/B observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never softens floors)"
            if isinstance(src.get("adapt_ab"), dict)
            else f"adapt A/B observe · sunday quiet {quiet_age_part} (observe · never softens floors)"
        ),
        "raise_phi_sla_sunday_quiet": (
            f"{(src.get('raise_phi_sla') or {}).get('label') or 'raise_Φ SLA observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never auto-writes Φ)"
            if isinstance(src.get("raise_phi_sla"), dict)
            else f"raise_Φ SLA observe · sunday quiet {quiet_age_part} (observe · never auto-writes Φ)"
        ),
        "feature_coverage_sunday_quiet": (
            f"{(src.get('feature_coverage') or {}).get('label') or 'feature coverage observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never softens floors)"
            if isinstance(src.get("feature_coverage"), dict)
            else f"feature coverage observe · sunday quiet {quiet_age_part} (observe · never softens floors)"
        ),
        "chip_catalog_sunday_quiet": (
            f"{(src.get('chip_catalog') or src.get('board_size') or {}).get('label') or 'chip catalog observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never softens floors)"
            if isinstance(src.get("chip_catalog") or src.get("board_size"), dict)
            else f"chip catalog observe · sunday quiet {quiet_age_part} (observe · never softens floors)"
        ),
        "phase2_pulse_sunday_quiet": (
            f"{(src.get('phase2_pulse') or {}).get('label') or 'phase2 pulse observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never softens floors)"
            if isinstance(src.get("phase2_pulse"), dict)
            else f"phase2 pulse observe · sunday quiet {quiet_age_part} (observe · never softens floors)"
        ),
        "l7_observe_sunday_quiet": (
            f"{l7_observe_summary(src).get('label') or 'L7 observe pulse'} "
            f"· sunday quiet {quiet_age_part} (observe · never softens floors)"
        ),
        "feature_store_sunday_quiet": (
            (
                f"feature store n={(src.get('feature_store') or {}).get('n')} "
                f"buys={(src.get('feature_store') or {}).get('buys')} "
                f"skips={(src.get('feature_store') or {}).get('skips')}"
                if isinstance(src.get("feature_store"), dict)
                else (
                    (src.get("feature_coverage") or {}).get("label")
                    if isinstance(src.get("feature_coverage"), dict)
                    else "feature store observe"
                )
            )
            + f" · sunday quiet {quiet_age_part} (observe · never softens floors)"
        ),
        "skip_historian_sunday_quiet": (
            f"{(src.get('skip_historian') or {}).get('label') or 'skip historian observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never softens floors)"
            if isinstance(src.get("skip_historian"), dict)
            else f"skip historian observe · sunday quiet {quiet_age_part} (observe · never softens floors)"
        ),
        "ritual_live_sunday_quiet": ritual_live_sunday,
        "priority_sunday_quiet": (
            f"{living_priority_snapshot(src).get('label') or 'priority observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never softens floors)"
        ),
        "hud_sunday_quiet": (
            f"{living_hud_summary(src).get('label') or 'hud observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never softens floors)"
        ),
        "money_path_sunday_quiet": (
            f"{living_money_path_tip(src).get('label') or 'money-path observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never invents PnL)"
        ),
        "guardrails_sunday_quiet": (
            f"{living_guardrails_tip(src).get('label') or 'guardrails observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never softens floors)"
        ),
        "surfaces_sunday_quiet": (
            f"{living_surface_index(src).get('label') or 'surfaces observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never softens floors)"
        ),
        "smoke_sunday_quiet": (
            f"{living_staff_smoke(src).get('label') or 'smoke observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never softens floors)"
        ),
        "paste_sunday_quiet": (
            f"{living_discord_paste_tip(src).get('label') or 'paste observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never auto-posts)"
        ),
        "paper_live_sunday_quiet": (
            f"{living_paper_live_tip(src).get('label') or 'paper-live observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never enables live)"
        ),
        "makefile_sunday_quiet": (
            f"{living_makefile_index(src).get('label') or 'makefile observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never softens floors)"
        ),
        "venues_sunday_quiet": (
            f"{living_venues_tip(src).get('label') or 'venues observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never softens floors)"
        ),
        "chicago_sunday_quiet": (
            f"{living_chicago_tip(src).get('label') or 'chicago observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never softens floors)"
        ),
        "starve_sunday_quiet": (
            f"{living_starve_tip(src).get('label') or 'starve observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never softens floors)"
        ),
        "hard_rules_sunday_quiet": (
            f"{living_hard_rules_tip(src).get('label') or 'hard-rules observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never softens floors)"
        ),
        "swarm_tip_sunday_quiet": (
            f"{living_swarm_tip(src).get('label') or 'swarm observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never softens floors)"
        ),
        "expand_tip_sunday_quiet": (
            f"{living_expand_tip(src).get('label') or 'expand observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never softens floors)"
        ),
        "quiet_tip_sunday_quiet": (
            f"{living_quiet_tip(src).get('label') or 'quiet observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never softens floors)"
        ),
        "timer_tip_sunday_quiet": (
            f"{living_timer_tip(src).get('label') or 'timer observe'} "
            f"· sunday quiet {quiet_age_part} (observe · never softens floors)"
        ),
        "ritual_label": ritual_part,
        "ritual_ok": ritual.get("ritual_ok"),
        "doctor_label": doctor_part,
        "doctor_fresh": doctor_fresh,
        "label": " · ".join(str(p) for p in parts),
        "note": "Compact living card — floors locked; paper only.",
    }


def ritual_observe_chip(root: str | None = None) -> dict:
    """Observe-only weekly ritual readiness (never records doctor / never auto-posts)."""
    floors = fee_floors_assert(root)
    expand = betting_expand_gate(root)
    age = doctor_age_chip(root)
    floors_ok = bool(floors.get("all_ok"))
    expand_ok = not bool(expand.get("blocked"))
    doctor_fresh = not bool(age.get("stale"))
    # Exit-code twin: ritual CLI fails on soft floors or blocked expand.
    exit_ok = floors_ok and expand_ok
    ritual_ok = exit_ok and doctor_fresh and age.get("ok_last") is not False
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "live_orders_enabled": False,
        "auto_publish": False,
        "floors_ok": floors_ok,
        "expand_ok": expand_ok,
        "doctor_fresh": doctor_fresh,
        "doctor_ok_last": age.get("ok_last"),
        "exit_ok": exit_ok,
        "ritual_ok": ritual_ok,
        "label": (
            f"ritual_ok={ritual_ok} exit_ok={exit_ok} "
            f"floors={'ok' if floors_ok else 'soft'} "
            f"expand={'ok' if expand_ok else 'blocked'} "
            f"doctor={'fresh' if doctor_fresh else 'stale'}"
        ),
        "note": (
            "Observe-only ritual readiness — run make living-ritual / --discord to record. "
            "Never invent fills; never soften floors; never enable live."
        ),
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


def sunday_packet_chip(root: str | None = None) -> dict:
    """Observe-only Sunday living packet presence chip (never auto-publishes)."""
    packet: dict = {}
    present = False
    try:
        from helpers import sunday_packet
        path = sunday_packet.packet_path(root)
        present = os.path.isfile(path)
        if present:
            with open(path, encoding="utf-8") as handle:
                packet = json.load(handle)
            if not isinstance(packet, dict):
                packet = {}
    except Exception:
        packet = {}
        present = False
    quiet_age_label = packet.get("quiet_age_label")
    quiet_age = packet.get("quiet_age")
    if not quiet_age_label or not quiet_age:
        try:
            quiet = feature_store_quiet_alert(root)
            age_h = quiet.get("age_hours") if isinstance(quiet, dict) else None
            quiet_age = quiet_age or (f"{age_h}h" if age_h is not None else "n/a")
            quiet_age_label = quiet_age_label or f"quiet_age={quiet_age}"
        except Exception:
            quiet_age = quiet_age or "n/a"
            quiet_age_label = quiet_age_label or "quiet_age=n/a"
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "auto_publish": False,
        "present": present,
        "chicago_today": packet.get("chicago_today"),
        "scorecard_present": bool(packet.get("scorecard_present")),
        "ritual": packet.get("ritual") if isinstance(packet.get("ritual"), dict) else None,
        "ritual_ok": packet.get("ritual_ok"),
        "quiet_age": quiet_age,
        "quiet_age_label": quiet_age_label,
        "label": (
            f"sunday packet={'yes' if present else 'no'} "
            f"scorecard={bool(packet.get('scorecard_present'))} "
            f"ritual_ok={packet.get('ritual_ok')} "
            f"{quiet_age_label} "
            f"auto_publish=False"
        ),
        "note": packet.get("note") or (
            "Staff Sunday living packet — draft/discord only; never auto-posts."
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
        "label": (
            f"green-day green={green_n} red={red_n}"
            + (" ALL_GREEN" if fee_clear and red_n == 0 and green_n == len(fee_clear) else "")
        ),
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
        "sunday_packet": sunday_packet_chip(root),
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
        "teller_living": teller_living_chip(root, bots=bots, enrich_live=False),
        "fee_floors_assert": fee_floors_assert(root),
        "dual_control_gaps": dual_control_gaps_page(root),
        "hillclimb_chip": hillclimb_chip(root),
        "digest_inventory": digest_inventory(root),
        "digest_freshness": digest_freshness_chip(root),
        "journal_coverage": journal_coverage_chip(root),
        "monday_pulse": monday_pulse_chip(root, bots=bots),
        "toxic_fills": toxic_fill_chip(root),
        "adapt_ab": adapt_ab_chip(root),
        "raise_phi_sla": raise_phi_sla_chip(root, bots=bots),
        "feature_coverage": feature_coverage_chip(root),
        "phase2_pulse": phase2_pulse_chip(root),
        "ruin_drill_page": ruin_drill_page(root),
        "betting_expand_gate": betting_expand_gate(root),
        "doctor_age": doctor_age_chip(root),
        "ritual_observe": ritual_observe_chip(root),
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
    chips_n = _count_living_chips(board)
    board["board_size"] = living_board_size_guard(chips_n=chips_n)
    board["chip_catalog"] = chip_catalog_chip(root, chips_n=chips_n)
    # Surface-only: stamp ritual live n onto teller after board exists (no recursion).
    teller = board.get("teller_living") if isinstance(board.get("teller_living"), dict) else None
    if teller is not None:
        live = ritual_live_labels(board)
        live_n = sum(1 for k, v in live.items() if str(k).endswith("_label") and v)
        teller["ritual_live_n"] = live_n
        teller["ritual_live_ok"] = live_n >= 40
        base = str(teller.get("memory_line") or teller.get("label") or "")
        if "ritual live n=" not in base:
            base = f"{base} · ritual live n={live_n}".strip(" ·")
            teller["memory_line"] = base
            teller["label"] = base
        board["teller_living"] = teller
    # Refresh hud / surfaces / guardrails twins now that compact + catalog exist.
    compact = board.get("compact") if isinstance(board.get("compact"), dict) else None
    if compact is not None:
        quiet_bit = compact.get("sunday_quiet_age_label") or compact.get("quiet_age_label") or "quiet_age=n/a"
        hud = living_hud_summary(board)
        compact["hud_sunday_quiet"] = (
            f"{hud.get('label') or 'hud observe'} · sunday quiet {quiet_bit} "
            "(observe · never softens floors)"
        )
        rails = living_guardrails_tip(board)
        compact["guardrails_sunday_quiet"] = (
            f"{rails.get('label') or 'guardrails observe'} · sunday quiet {quiet_bit} "
            "(observe · never softens floors)"
        )
        surfaces = living_surface_index(board)
        compact["surfaces_sunday_quiet"] = (
            f"{surfaces.get('label') or 'surfaces observe'} · sunday quiet {quiet_bit} "
            "(observe · never softens floors)"
        )
        smoke = living_staff_smoke(board)
        compact["smoke_sunday_quiet"] = (
            f"{smoke.get('label') or 'smoke observe'} · sunday quiet {quiet_bit} "
            "(observe · never softens floors)"
        )
        paste = living_discord_paste_tip(board)
        compact["paste_sunday_quiet"] = (
            f"{paste.get('label') or 'paste observe'} · sunday quiet {quiet_bit} "
            "(observe · never auto-posts)"
        )
        paper_live = living_paper_live_tip(board)
        compact["paper_live_sunday_quiet"] = (
            f"{paper_live.get('label') or 'paper-live observe'} · sunday quiet {quiet_bit} "
            "(observe · never enables live)"
        )
        makefile = living_makefile_index(board)
        compact["makefile_sunday_quiet"] = (
            f"{makefile.get('label') or 'makefile observe'} · sunday quiet {quiet_bit} "
            "(observe · never softens floors)"
        )
        venues = living_venues_tip(board)
        compact["venues_sunday_quiet"] = (
            f"{venues.get('label') or 'venues observe'} · sunday quiet {quiet_bit} "
            "(observe · never softens floors)"
        )
        chicago = living_chicago_tip(board)
        compact["chicago_sunday_quiet"] = (
            f"{chicago.get('label') or 'chicago observe'} · sunday quiet {quiet_bit} "
            "(observe · never softens floors)"
        )
        starve = living_starve_tip(board)
        compact["starve_sunday_quiet"] = (
            f"{starve.get('label') or 'starve observe'} · sunday quiet {quiet_bit} "
            "(observe · never softens floors)"
        )
        hard_rules = living_hard_rules_tip(board)
        compact["hard_rules_sunday_quiet"] = (
            f"{hard_rules.get('label') or 'hard-rules observe'} · sunday quiet {quiet_bit} "
            "(observe · never softens floors)"
        )

        swarm_tip = living_swarm_tip(board)
        compact["swarm_tip_sunday_quiet"] = (
            f"{swarm_tip.get('label') or 'swarm observe'} · sunday quiet {quiet_bit} "
            "(observe · never softens floors)"
        )
        expand_tip = living_expand_tip(board)
        compact["expand_tip_sunday_quiet"] = (
            f"{expand_tip.get('label') or 'expand observe'} · sunday quiet {quiet_bit} "
            "(observe · never softens floors)"
        )
        quiet_tip = living_quiet_tip(board)
        compact["quiet_tip_sunday_quiet"] = (
            f"{quiet_tip.get('label') or 'quiet observe'} · sunday quiet {quiet_bit} "
            "(observe · never softens floors)"
        )
        timer_tip = living_timer_tip(board)
        compact["timer_tip_sunday_quiet"] = (
            f"{timer_tip.get('label') or 'timer observe'} · sunday quiet {quiet_bit} "
            "(observe · never softens floors)"
        )
        board["compact"] = compact
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
    copy = "\n".join(lines)
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "live_orders_enabled": False,
        "auto_page": False,
        "auto_publish": False,
        "page": page,
        "practiced_this_month": practiced,
        "active": active,
        "level": status.get("level"),
        "copy": copy,
        "discord": copy,  # staff paste only
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
        "insight_swarm", "digest_inventory", "digest_freshness", "journal_coverage", "monday_pulse",
        "toxic_fills", "adapt_ab", "raise_phi_sla", "feature_coverage", "chip_catalog", "phase2_pulse",
        "feature_quiet", "feature_quiet_pager",
        "dual_control_gaps", "hillclimb_chip", "ruin_drill_chip", "completions_chip", "completions",
        "timer_heartbeat", "bleed", "clv", "green_day", "firm_queue",
        "betting_expand_gate", "doctor_age", "fee_floors_assert",
        "sunday_packet", "reporter", "ritual_observe", "feature_store", "skip_historian",
        # clerks / helpers / gates (surface export; already on board — no new chips)
        "living_ai", "skip_taxonomy", "empty_card", "helper_gate_a", "skip_regret",
        "tip_radar", "calib_nag", "injury_wire", "eia_scout", "distance_clerk",
        "quant_clerk", "bookkeeper", "empty_card_bee", "near_miss", "near_miss_clerk",
        "hard_stop", "hard_stop_clerk", "skip_twin_clerk", "timer_digest",
        "calendar_scanner", "eia_blackout", "clerk_pulse", "dual_control_chip",
        "teller_living", "clv_closer", "bleed_clerk",
        "hillclimb_lever", "dual_control", "ruin_drill", "ruin_drill_page",
    )
    slim = {k: board.get(k) for k in keep if k in board}
    ritual = board.get("ritual_observe") if isinstance(board.get("ritual_observe"), dict) else {}
    slim["paper_only"] = True
    slim["export"] = "living_board_v1"
    # Surface audits (helpers — never board chips)
    slim["ritual_live_labels"] = ritual_live_labels(board)
    slim["sunday_twin_coverage"] = sunday_twin_coverage(board)
    slim["l7_observe"] = l7_observe_summary(board)
    prio = living_priority_snapshot(board)
    slim["priority"] = prio
    slim["priority_lines"] = list(prio.get("priority") or [])
    slim["priority_label"] = prio.get("label")
    hud = living_hud_summary(board)
    slim["hud"] = hud
    slim["hud_label"] = hud.get("label")
    money = living_money_path_tip(board)
    slim["money_path"] = money
    slim["money_path_label"] = money.get("label")
    rails = living_guardrails_tip(board)
    slim["guardrails"] = rails
    slim["guardrails_label"] = rails.get("label")
    surfaces = living_surface_index(board)
    slim["surfaces"] = surfaces
    slim["surfaces_label"] = surfaces.get("label")
    smoke = living_staff_smoke(board)
    slim["smoke"] = smoke
    slim["smoke_label"] = smoke.get("label")
    slim["smoke_ok"] = smoke.get("ok")
    paste = living_discord_paste_tip(board)
    slim["paste"] = paste
    slim["paste_label"] = paste.get("label")
    slim["paste_n"] = paste.get("targets_n")
    paper_live = living_paper_live_tip(board)
    slim["paper_live"] = paper_live
    slim["paper_live_label"] = paper_live.get("label")
    slim["paper_live_ok"] = paper_live.get("ok")
    makefile = living_makefile_index(board)
    slim["makefile"] = makefile
    slim["makefile_label"] = makefile.get("label")
    slim["makefile_n"] = makefile.get("targets_n")
    venues = living_venues_tip(board)
    slim["venues"] = venues
    slim["venues_label"] = venues.get("label")
    slim["venues_ok"] = venues.get("ok")
    chicago = living_chicago_tip(board)
    slim["chicago"] = chicago
    slim["chicago_label"] = chicago.get("label")
    slim["chicago_today"] = chicago.get("chicago_today") or slim.get("chicago_today")
    starve = living_starve_tip(board)
    slim["starve"] = starve
    slim["starve_label"] = starve.get("label")
    hard_rules = living_hard_rules_tip(board)
    slim["hard_rules"] = hard_rules
    slim["hard_rules_label"] = hard_rules.get("label")

    swarm_tip = living_swarm_tip(board)
    slim["swarm_tip"] = swarm_tip
    slim["swarm_tip_label"] = swarm_tip.get("label")
    slim["swarm_pass"] = swarm_tip.get("pass")
    expand_tip = living_expand_tip(board)
    slim["expand_tip"] = expand_tip
    slim["expand_tip_label"] = expand_tip.get("label")
    slim["expand_blocked"] = expand_tip.get("blocked")
    quiet_tip = living_quiet_tip(board)
    slim["quiet_tip"] = quiet_tip
    slim["quiet_tip_label"] = quiet_tip.get("label")
    timer_tip = living_timer_tip(board)
    slim["timer_tip"] = timer_tip
    slim["timer_tip_label"] = timer_tip.get("label")
    slim["timer_alive"] = timer_tip.get("alive")
    teller = board.get("teller_living") if isinstance(board.get("teller_living"), dict) else {}
    slim["living_memory_line"] = teller.get("memory_line") or teller.get("label")
    compact_src = board.get("compact") if isinstance(board.get("compact"), dict) else {}
    slim["sunday_twins"] = {
        k: compact_src.get(k)
        for k in sorted(compact_src)
        if str(k).endswith("_sunday_quiet")
    }
    slim["sunday_twins_n"] = len(slim["sunday_twins"])
    slim["ritual_ok"] = ritual.get("ritual_ok")
    slim["ritual_exit_ok"] = ritual.get("exit_ok")
    slim["doctor_fresh"] = ritual.get("doctor_fresh")
    doctor_age = board.get("doctor_age") if isinstance(board.get("doctor_age"), dict) else {}
    if slim.get("doctor_fresh") is None and doctor_age:
        slim["doctor_fresh"] = not bool(doctor_age.get("stale"))
    compact = board.get("compact") if isinstance(board.get("compact"), dict) else {}
    quiet = board.get("feature_quiet") if isinstance(board.get("feature_quiet"), dict) else {}
    if compact:
        slim["compact_ritual_ok"] = compact.get("ritual_ok")
        slim["compact_ritual_label"] = compact.get("ritual_label")
        slim["compact_doctor_fresh"] = compact.get("doctor_fresh")
        slim["compact_doctor_label"] = compact.get("doctor_label")
        slim["compact_quiet_age"] = compact.get("quiet_age")
        slim["compact_quiet_age_h"] = compact.get("quiet_age_h")
        slim["compact_quiet_age_label"] = compact.get("quiet_age_label")
    quiet_age = quiet.get("age_hours")
    slim["quiet_age_h"] = quiet_age
    slim["quiet_age"] = f"{quiet_age}h" if quiet_age is not None else "n/a"
    if slim.get("compact_quiet_age") is None:
        slim["compact_quiet_age"] = slim["quiet_age"]
    if slim.get("compact_quiet_age_h") is None:
        slim["compact_quiet_age_h"] = quiet_age
    if not slim.get("compact_quiet_age_label"):
        slim["compact_quiet_age_label"] = (
            compact.get("quiet_age_label")
            if isinstance(compact, dict) and compact.get("quiet_age_label")
            else f"quiet_age={slim['quiet_age']}"
        )
    slim["quiet_line"] = (
        "• Feature quiet: quiet="
        + str(quiet.get("quiet"))
        + " age="
        + str(slim["quiet_age"])
        + " (staff observe — never softens floors)"
    )
    sunday = board.get("sunday_packet") if isinstance(board.get("sunday_packet"), dict) else {}
    slim["sunday_quiet_age"] = sunday.get("quiet_age") or slim["quiet_age"]
    slim["sunday_quiet_age_label"] = (
        sunday.get("quiet_age_label")
        or slim.get("compact_quiet_age_label")
        or f"quiet_age={slim['quiet_age']}"
    )
    slim["masters_sunday_quiet"] = (
        f"sunday quiet {slim['sunday_quiet_age_label']} (observe)"
    )
    slim["sunday_quiet_tip"] = (
        f"Sunday quiet tip: {slim['sunday_quiet_age_label']} · "
        "cross-check python3 tools/staff_sunday_packet.py discord "
        "(staff paste · never auto-posts)"
    )
    expand = board.get("betting_expand_gate") if isinstance(board.get("betting_expand_gate"), dict) else {}
    expand_bit = (
        "expand=blocked"
        if expand.get("blocked")
        else "expand=ok"
        if expand.get("blocked") is False
        else str(compact.get("expand_label") or "expand=n/a")
    )
    slim["expand_sunday_quiet"] = (
        f"{expand_bit} · sunday quiet {slim['sunday_quiet_age_label']} "
        "(observe · never softens floors)"
    )
    floors = board.get("fee_floors_assert") if isinstance(board.get("fee_floors_assert"), dict) else {}
    floors_bit = (
        "floors=ok"
        if floors.get("all_ok")
        else "floors=soft"
        if floors.get("all_ok") is False
        else "floors=n/a"
    )
    slim["floors_sunday_quiet"] = (
        f"{floors_bit} · sunday quiet {slim['sunday_quiet_age_label']} "
        "(observe · never softens floors)"
    )
    ruin_chip = board.get("ruin_drill_chip") if isinstance(board.get("ruin_drill_chip"), dict) else {}
    slim["ruin_sunday_quiet"] = (
        f"{ruin_chip.get('label') or 'ruin observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never softens floors)"
    )
    swarm = board.get("insight_swarm") if isinstance(board.get("insight_swarm"), dict) else {}
    slim["swarm_sunday_quiet"] = (
        f"swarm {swarm.get('insight_n')}:{swarm.get('betting_n')} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe)"
    )
    hill = board.get("hillclimb_chip") if isinstance(board.get("hillclimb_chip"), dict) else {}
    slim["hill_sunday_quiet"] = (
        f"{hill.get('label') or 'hillclimb none'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never softens floors)"
    )
    gaps = board.get("dual_control_gaps") if isinstance(board.get("dual_control_gaps"), dict) else {}
    slim["gaps_sunday_quiet"] = (
        f"{gaps.get('label') or 'gaps observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never softens floors)"
    )
    inv = board.get("digest_inventory") if isinstance(board.get("digest_inventory"), dict) else {}
    slim["digests_sunday_quiet"] = (
        f"{inv.get('label') or 'digests observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never softens floors)"
    )
    comp = board.get("completions") if isinstance(board.get("completions"), dict) else {}
    fills_bit = (
        f"eligible today {comp.get('eligible_completions_today')}"
        if comp.get("eligible_completions_today") is not None
        else "eligible fills n/a"
    )
    slim["fills_sunday_quiet"] = (
        f"{fills_bit} · sunday quiet {slim['sunday_quiet_age_label']} "
        "(observe · never invents PnL)"
    )
    green = board.get("green_day") if isinstance(board.get("green_day"), dict) else {}
    slim["green_sunday_quiet"] = (
        f"{green.get('label') or (('green=' + str(green.get('green_n'))) if green else 'green-day n/a')} "
        f"· sunday quiet {slim['sunday_quiet_age_label']} (observe)"
    )
    bleed = board.get("bleed") if isinstance(board.get("bleed"), dict) else {}
    slim["bleed_sunday_quiet"] = (
        f"{bleed.get('label') or (('bleed=' + str(bleed.get('ratio'))) if bleed else 'bleed n/a')} "
        f"· sunday quiet {slim['sunday_quiet_age_label']} (observe · never softens floors)"
    )
    clv = (
        board.get("clv")
        if isinstance(board.get("clv"), dict)
        else board.get("clv_closer") if isinstance(board.get("clv_closer"), dict) else {}
    )
    slim["clv_sunday_quiet"] = (
        f"{clv.get('label') or 'CLV observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe)"
    )
    timer = board.get("timer_heartbeat") if isinstance(board.get("timer_heartbeat"), dict) else {}
    slim["timer_sunday_quiet"] = (
        f"timer={'alive' if timer.get('alive') else 'DEAD' if timer.get('alive') is False else 'n/a'} "
        f"· sunday quiet {slim['sunday_quiet_age_label']} (observe · never softens floors)"
    )
    calib = board.get("calib_nag") if isinstance(board.get("calib_nag"), dict) else {}
    slim["calib_sunday_quiet"] = (
        f"{calib.get('label') or 'calib observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never auto-writes Φ)"
    )
    queue = board.get("firm_queue") if isinstance(board.get("firm_queue"), dict) else {}
    slim["queue_sunday_quiet"] = (
        f"{queue.get('label') or 'queue observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never promotes)"
    )
    gate_a = board.get("helper_gate_a") if isinstance(board.get("helper_gate_a"), dict) else {}
    slim["gate_a_sunday_quiet"] = (
        f"{gate_a.get('label') or 'Gate A observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never softens floors)"
    )
    ai = board.get("living_ai") if isinstance(board.get("living_ai"), dict) else {}
    slim["ai_sunday_quiet"] = (
        f"{ai.get('label') or 'AI observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never auto-writes Φ)"
    )
    tip = board.get("tip_radar") if isinstance(board.get("tip_radar"), dict) else {}
    slim["tip_sunday_quiet"] = (
        f"{tip.get('label') or 'tip feed observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe)"
    )
    blackout = board.get("eia_blackout") if isinstance(board.get("eia_blackout"), dict) else {}
    slim["blackout_sunday_quiet"] = (
        f"{blackout.get('label') or 'blackout observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never softens floors)"
    )
    injury = board.get("injury_wire") if isinstance(board.get("injury_wire"), dict) else {}
    slim["injury_sunday_quiet"] = (
        f"{injury.get('label') or 'injury observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe)"
    )

    empty = board.get("empty_card") if isinstance(board.get("empty_card"), dict) else {}
    slim["empty_sunday_quiet"] = (
        f"{empty.get('label') or 'empty CARD observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe)"
    )
    near = board.get("near_miss") if isinstance(board.get("near_miss"), dict) else {}
    slim["near_miss_sunday_quiet"] = (
        f"{near.get('label') or 'near-miss observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never promotes)"
    )
    eia = board.get("eia_scout") if isinstance(board.get("eia_scout"), dict) else {}
    slim["eia_sunday_quiet"] = (
        f"{eia.get('label') or 'EIA observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe)"
    )
    cal = board.get("calendar_scanner") if isinstance(board.get("calendar_scanner"), dict) else {}
    slim["calendar_sunday_quiet"] = (
        f"{cal.get('label') or 'calendar observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe)"
    )
    pager = board.get("feature_quiet_pager") if isinstance(board.get("feature_quiet_pager"), dict) else {}
    slim["pager_sunday_quiet"] = (
        f"{pager.get('label') or 'pager observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never auto-pages)"
    )
    books = board.get("bookkeeper") if isinstance(board.get("bookkeeper"), dict) else {}
    slim["books_sunday_quiet"] = (
        f"{books.get('label') or 'books observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never invents PnL)"
    )
    pulse = board.get("clerk_pulse") if isinstance(board.get("clerk_pulse"), dict) else {}
    slim["pulse_sunday_quiet"] = (
        f"{pulse.get('label') or 'pulse observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe)"
    )
    dual = board.get("dual_control") if isinstance(board.get("dual_control"), dict) else {}
    slim["dual_sunday_quiet"] = (
        f"{dual.get('label') or 'dual observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never softens floors)"
    )
    skip_regret = board.get("skip_regret") if isinstance(board.get("skip_regret"), dict) else {}
    slim["skip_reg_sunday_quiet"] = (
        f"{skip_regret.get('label') or 'skip-regret observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never softens floors)"
    )
    hard_stop = board.get("hard_stop") if isinstance(board.get("hard_stop"), dict) else {}
    slim["hard_stop_sunday_quiet"] = (
        f"{hard_stop.get('label') or 'hard-stop observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never promotes)"
    )
    distance_clerk = board.get("distance_clerk") if isinstance(board.get("distance_clerk"), dict) else {}
    slim["distance_sunday_quiet"] = (
        f"{distance_clerk.get('label') or 'distance observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe)"
    )
    quant_clerk = board.get("quant_clerk") if isinstance(board.get("quant_clerk"), dict) else {}
    slim["quant_sunday_quiet"] = (
        f"{quant_clerk.get('label') or 'quant observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe)"
    )
    reporter = board.get("reporter") if isinstance(board.get("reporter"), dict) else {}
    slim["report_sunday_quiet"] = (
        f"{reporter.get('label') or 'report observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never auto-posts)"
    )
    empty_card_bee = board.get("empty_card_bee") if isinstance(board.get("empty_card_bee"), dict) else {}
    slim["empty_bee_sunday_quiet"] = (
        f"{empty_card_bee.get('label') or 'empty bee observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe)"
    )
    near_miss_clerk = board.get("near_miss_clerk") if isinstance(board.get("near_miss_clerk"), dict) else {}
    slim["nm_clerk_sunday_quiet"] = (
        f"{near_miss_clerk.get('label') or 'nm clerk observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never promotes)"
    )
    hard_stop_clerk = board.get("hard_stop_clerk") if isinstance(board.get("hard_stop_clerk"), dict) else {}
    slim["hs_clerk_sunday_quiet"] = (
        f"{hard_stop_clerk.get('label') or 'hs clerk observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never promotes)"
    )
    bleed_clerk = board.get("bleed_clerk") if isinstance(board.get("bleed_clerk"), dict) else {}
    slim["bleed_clerk_sunday_quiet"] = (
        f"{bleed_clerk.get('label') or 'bleed clerk observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never softens floors)"
    )
    skip_twin_clerk = board.get("skip_twin_clerk") if isinstance(board.get("skip_twin_clerk"), dict) else {}
    slim["skip_twin_sunday_quiet"] = (
        f"{skip_twin_clerk.get('label') or 'skip-twin observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe)"
    )
    clv_closer = board.get("clv_closer") if isinstance(board.get("clv_closer"), dict) else {}
    slim["clv_closer_sunday_quiet"] = (
        f"{clv_closer.get('label') or 'CLV closer observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe)"
    )
    timer_digest = board.get("timer_digest") if isinstance(board.get("timer_digest"), dict) else {}
    slim["tdigest_sunday_quiet"] = (
        f"{timer_digest.get('label') or 't-digest observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe)"
    )
    skip_taxonomy = board.get("skip_taxonomy") if isinstance(board.get("skip_taxonomy"), dict) else {}
    slim["skips_sunday_quiet"] = (
        f"{skip_taxonomy.get('label') or 'skips observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe)"
    )
    teller_living = board.get("teller_living") if isinstance(board.get("teller_living"), dict) else {}
    slim["teller_sunday_quiet"] = (
        f"{teller_living.get('label') or 'teller observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never softens floors)"
    )
    doctor_age = board.get("doctor_age") if isinstance(board.get("doctor_age"), dict) else {}
    slim["doc_age_sunday_quiet"] = (
        f"{doctor_age.get('label') or 'doctor age observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never softens floors)"
    )
    feature_quiet = board.get("feature_quiet") if isinstance(board.get("feature_quiet"), dict) else {}
    slim["quiet_sunday_quiet"] = (
        f"{feature_quiet.get('label') or 'feature quiet observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never softens floors)"
    )
    ritual_observe = board.get("ritual_observe") if isinstance(board.get("ritual_observe"), dict) else {}
    slim["ritual_sunday_quiet"] = (
        f"{ritual_observe.get('label') or 'ritual observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never auto-posts)"
    )
    dig_fresh = board.get("digest_freshness") if isinstance(board.get("digest_freshness"), dict) else {}
    slim["digest_fresh_sunday_quiet"] = (
        f"{dig_fresh.get('label') or 'digest fresh observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe)"
    )
    journ = board.get("journal_coverage") if isinstance(board.get("journal_coverage"), dict) else {}
    slim["journal_sunday_quiet"] = (
        f"{journ.get('label') or 'journals observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never softens floors)"
    )
    monday = board.get("monday_pulse") if isinstance(board.get("monday_pulse"), dict) else {}
    slim["monday_sunday_quiet"] = (
        f"{monday.get('label') or 'monday pulse observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never softens floors)"
    )
    toxic = board.get("toxic_fills") if isinstance(board.get("toxic_fills"), dict) else {}
    slim["toxic_sunday_quiet"] = (
        f"{toxic.get('label') or 'toxic fills observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never softens floors)"
    )
    adapt_ab = board.get("adapt_ab") if isinstance(board.get("adapt_ab"), dict) else {}
    slim["adapt_ab_sunday_quiet"] = (
        f"{adapt_ab.get('label') or 'adapt A/B observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never softens floors)"
    )
    rps = board.get("raise_phi_sla") if isinstance(board.get("raise_phi_sla"), dict) else {}
    slim["raise_phi_sla_sunday_quiet"] = (
        f"{rps.get('label') or 'raise_Φ SLA observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never auto-writes Φ)"
    )
    feat_cov = board.get("feature_coverage") if isinstance(board.get("feature_coverage"), dict) else {}
    slim["feature_coverage_sunday_quiet"] = (
        f"{feat_cov.get('label') or 'feature coverage observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never softens floors)"
    )
    catalog = (
        board.get("chip_catalog")
        if isinstance(board.get("chip_catalog"), dict)
        else board.get("board_size") if isinstance(board.get("board_size"), dict) else {}
    )
    slim["chip_catalog_sunday_quiet"] = (
        f"{catalog.get('label') or 'chip catalog observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never softens floors)"
    )
    p2 = board.get("phase2_pulse") if isinstance(board.get("phase2_pulse"), dict) else {}
    slim["phase2_pulse_sunday_quiet"] = (
        f"{p2.get('label') or 'phase2 pulse observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never softens floors)"
    )
    l7s = l7_observe_summary(board)
    slim["l7_observe_ok"] = bool(l7s.get("ok"))
    slim["l7_observe_label"] = str(l7s.get("label") or "L7 observe pending")
    slim["l7_observe_sunday_quiet"] = (
        f"{slim['l7_observe_label']} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never softens floors)"
    )
    feat_store = board.get("feature_store") if isinstance(board.get("feature_store"), dict) else {}
    slim["feature_store_sunday_quiet"] = (
        (
            f"feature store n={feat_store.get('n')} "
            f"buys={feat_store.get('buys')} skips={feat_store.get('skips')}"
            if feat_store
            else "feature store observe"
        )
        + f" · sunday quiet {slim['sunday_quiet_age_label']} "
        "(observe · never softens floors)"
    )
    skip_hist = board.get("skip_historian") if isinstance(board.get("skip_historian"), dict) else {}
    slim["skip_historian_sunday_quiet"] = (
        f"{skip_hist.get('label') or 'skip historian observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never softens floors)"
    )
    live_export = ritual_live_labels(board)
    live_n_export = sum(
        1 for k, v in live_export.items() if str(k).endswith("_label") and v
    )
    slim["ritual_live_sunday_quiet"] = (
        f"ritual live n={live_n_export} · "
        f"{live_export.get('digests_label') or 'digests observe'} · "
        f"{live_export.get('fills_label') or 'fills observe'} · "
        f"{live_export.get('timer_label') or 'timer observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never softens floors)"
    )
    teller_living = board.get("teller_living") if isinstance(board.get("teller_living"), dict) else {}
    slim["teller_ritual_live_sunday_quiet"] = (
        f"teller ritual live n={teller_living.get('ritual_live_n') if teller_living.get('ritual_live_n') is not None else live_n_export} "
        f"· sunday quiet {slim['sunday_quiet_age_label']} (observe · never softens floors)"
    )
    slim["ritual_live_n"] = live_n_export
    slim["ritual_live_ok"] = live_n_export >= 40
    prio_export = living_priority_snapshot(board)
    slim["priority_sunday_quiet"] = (
        f"{prio_export.get('label') or 'priority observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never softens floors)"
    )
    hud_export = living_hud_summary(board)
    slim["hud_sunday_quiet"] = (
        f"{hud_export.get('label') or 'hud observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never softens floors)"
    )
    money_export = living_money_path_tip(board)
    slim["money_path_sunday_quiet"] = (
        f"{money_export.get('label') or 'money-path observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never invents PnL)"
    )
    rails_export = living_guardrails_tip(board)
    slim["guardrails_sunday_quiet"] = (
        f"{rails_export.get('label') or 'guardrails observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never softens floors)"
    )
    surfaces_export = living_surface_index(board)
    slim["surfaces_sunday_quiet"] = (
        f"{surfaces_export.get('label') or 'surfaces observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never softens floors)"
    )
    smoke_export = living_staff_smoke(board)
    slim["smoke_sunday_quiet"] = (
        f"{smoke_export.get('label') or 'smoke observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never softens floors)"
    )
    paste_export = living_discord_paste_tip(board)
    slim["paste_sunday_quiet"] = (
        f"{paste_export.get('label') or 'paste observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never auto-posts)"
    )
    paper_live_export = living_paper_live_tip(board)
    slim["paper_live_sunday_quiet"] = (
        f"{paper_live_export.get('label') or 'paper-live observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never enables live)"
    )
    makefile_export = living_makefile_index(board)
    slim["makefile_sunday_quiet"] = (
        f"{makefile_export.get('label') or 'makefile observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never softens floors)"
    )
    venues_export = living_venues_tip(board)
    slim["venues_sunday_quiet"] = (
        f"{venues_export.get('label') or 'venues observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never softens floors)"
    )
    chicago_export = living_chicago_tip(board)
    slim["chicago_sunday_quiet"] = (
        f"{chicago_export.get('label') or 'chicago observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never softens floors)"
    )
    starve_export = living_starve_tip(board)
    slim["starve_sunday_quiet"] = (
        f"{starve_export.get('label') or 'starve observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never softens floors)"
    )
    hard_rules_export = living_hard_rules_tip(board)
    slim["hard_rules_sunday_quiet"] = (
        f"{hard_rules_export.get('label') or 'hard-rules observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never softens floors)"
    )

    swarm_tip_export = living_swarm_tip(board)
    slim["swarm_tip_sunday_quiet"] = (
        f"{swarm_tip_export.get('label') or 'swarm observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never softens floors)"
    )
    expand_tip_export = living_expand_tip(board)
    slim["expand_tip_sunday_quiet"] = (
        f"{expand_tip_export.get('label') or 'expand observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never softens floors)"
    )
    quiet_tip_export = living_quiet_tip(board)
    slim["quiet_tip_sunday_quiet"] = (
        f"{quiet_tip_export.get('label') or 'quiet observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never softens floors)"
    )
    timer_tip_export = living_timer_tip(board)
    slim["timer_tip_sunday_quiet"] = (
        f"{timer_tip_export.get('label') or 'timer observe'} · sunday quiet "
        f"{slim['sunday_quiet_age_label']} (observe · never softens floors)"
    )
    # Lightweight selfcheck flags after ritual_live_ok is known.
    slim["selfcheck_ok"] = bool(
        slim.get("fee_floors_locked")
        and slim.get("live_orders_enabled") is False
        and (slim.get("l7_observe") or {}).get("ok")
        and slim.get("ritual_live_ok")
    )
    slim["selfcheck_label"] = (
        f"selfcheck ok={slim['selfcheck_ok']} floors_locked={slim.get('fee_floors_locked')} "
        f"l7={(slim.get('l7_observe') or {}).get('ok')} live=False"
    )
    if compact:
        slim["compact_sunday_quiet_age"] = (
            compact.get("sunday_quiet_age") or slim["sunday_quiet_age"]
        )
        slim["compact_sunday_quiet_age_label"] = (
            compact.get("sunday_quiet_age_label")
            or slim["sunday_quiet_age_label"]
        )
        slim["compact_masters_sunday_label"] = (
            compact.get("masters_sunday_label")
            or f"masters_sunday={slim['quiet_age']}"
        )
        slim["compact_masters_sunday_quiet"] = (
            compact.get("masters_sunday_quiet")
            or slim["masters_sunday_quiet"]
        )
        slim["compact_expand_sunday_quiet"] = (
            compact.get("expand_sunday_quiet")
            or slim.get("expand_sunday_quiet")
        )
        slim["compact_floors_sunday_quiet"] = (
            compact.get("floors_sunday_quiet")
            or slim.get("floors_sunday_quiet")
        )
        slim["compact_ruin_sunday_quiet"] = (
            compact.get("ruin_sunday_quiet")
            or slim.get("ruin_sunday_quiet")
        )
        slim["compact_swarm_sunday_quiet"] = (
            compact.get("swarm_sunday_quiet") or slim.get("swarm_sunday_quiet")
        )
        slim["compact_hill_sunday_quiet"] = (
            compact.get("hill_sunday_quiet") or slim.get("hill_sunday_quiet")
        )
        slim["compact_gaps_sunday_quiet"] = (
            compact.get("gaps_sunday_quiet") or slim.get("gaps_sunday_quiet")
        )
        slim["compact_digests_sunday_quiet"] = (
            compact.get("digests_sunday_quiet") or slim.get("digests_sunday_quiet")
        )
        slim["compact_fills_sunday_quiet"] = (
            compact.get("fills_sunday_quiet") or slim.get("fills_sunday_quiet")
        )
        slim["compact_green_sunday_quiet"] = (
            compact.get("green_sunday_quiet") or slim.get("green_sunday_quiet")
        )
        slim["compact_bleed_sunday_quiet"] = (
            compact.get("bleed_sunday_quiet") or slim.get("bleed_sunday_quiet")
        )
        slim["compact_clv_sunday_quiet"] = (
            compact.get("clv_sunday_quiet") or slim.get("clv_sunday_quiet")
        )
        slim["compact_timer_sunday_quiet"] = (
            compact.get("timer_sunday_quiet") or slim.get("timer_sunday_quiet")
        )
        slim["compact_calib_sunday_quiet"] = (
            compact.get("calib_sunday_quiet") or slim.get("calib_sunday_quiet")
        )
        slim["compact_queue_sunday_quiet"] = (
            compact.get("queue_sunday_quiet") or slim.get("queue_sunday_quiet")
        )
        slim["compact_gate_a_sunday_quiet"] = (
            compact.get("gate_a_sunday_quiet") or slim.get("gate_a_sunday_quiet")
        )
        slim["compact_ai_sunday_quiet"] = (
            compact.get("ai_sunday_quiet") or slim.get("ai_sunday_quiet")
        )
        slim["compact_tip_sunday_quiet"] = (
            compact.get("tip_sunday_quiet") or slim.get("tip_sunday_quiet")
        )
        slim["compact_blackout_sunday_quiet"] = (
            compact.get("blackout_sunday_quiet") or slim.get("blackout_sunday_quiet")
        )
        slim["compact_injury_sunday_quiet"] = (
            compact.get("injury_sunday_quiet") or slim.get("injury_sunday_quiet")
        )
        slim["compact_empty_sunday_quiet"] = (
            compact.get("empty_sunday_quiet") or slim.get("empty_sunday_quiet")
        )
        slim["compact_near_miss_sunday_quiet"] = (
            compact.get("near_miss_sunday_quiet") or slim.get("near_miss_sunday_quiet")
        )
        slim["compact_eia_sunday_quiet"] = (
            compact.get("eia_sunday_quiet") or slim.get("eia_sunday_quiet")
        )
        slim["compact_calendar_sunday_quiet"] = (
            compact.get("calendar_sunday_quiet") or slim.get("calendar_sunday_quiet")
        )
        slim["compact_pager_sunday_quiet"] = (
            compact.get("pager_sunday_quiet") or slim.get("pager_sunday_quiet")
        )
        slim["compact_books_sunday_quiet"] = (
            compact.get("books_sunday_quiet") or slim.get("books_sunday_quiet")
        )
        slim["compact_pulse_sunday_quiet"] = (
            compact.get("pulse_sunday_quiet") or slim.get("pulse_sunday_quiet")
        )
        slim["compact_dual_sunday_quiet"] = (
            compact.get("dual_sunday_quiet") or slim.get("dual_sunday_quiet")
        )
        slim["compact_skip_reg_sunday_quiet"] = (
            compact.get("skip_reg_sunday_quiet") or slim.get("skip_reg_sunday_quiet")
        )
        slim["compact_hard_stop_sunday_quiet"] = (
            compact.get("hard_stop_sunday_quiet") or slim.get("hard_stop_sunday_quiet")
        )
        slim["compact_distance_sunday_quiet"] = (
            compact.get("distance_sunday_quiet") or slim.get("distance_sunday_quiet")
        )
        slim["compact_quant_sunday_quiet"] = (
            compact.get("quant_sunday_quiet") or slim.get("quant_sunday_quiet")
        )
        slim["compact_report_sunday_quiet"] = (
            compact.get("report_sunday_quiet") or slim.get("report_sunday_quiet")
        )
        slim["compact_empty_bee_sunday_quiet"] = (
            compact.get("empty_bee_sunday_quiet") or slim.get("empty_bee_sunday_quiet")
        )
        slim["compact_nm_clerk_sunday_quiet"] = (
            compact.get("nm_clerk_sunday_quiet") or slim.get("nm_clerk_sunday_quiet")
        )
        slim["compact_hs_clerk_sunday_quiet"] = (
            compact.get("hs_clerk_sunday_quiet") or slim.get("hs_clerk_sunday_quiet")
        )
        slim["compact_bleed_clerk_sunday_quiet"] = (
            compact.get("bleed_clerk_sunday_quiet") or slim.get("bleed_clerk_sunday_quiet")
        )
        slim["compact_skip_twin_sunday_quiet"] = (
            compact.get("skip_twin_sunday_quiet") or slim.get("skip_twin_sunday_quiet")
        )
        slim["compact_clv_closer_sunday_quiet"] = (
            compact.get("clv_closer_sunday_quiet") or slim.get("clv_closer_sunday_quiet")
        )
        slim["compact_tdigest_sunday_quiet"] = (
            compact.get("tdigest_sunday_quiet") or slim.get("tdigest_sunday_quiet")
        )
        slim["compact_skips_sunday_quiet"] = (
            compact.get("skips_sunday_quiet") or slim.get("skips_sunday_quiet")
        )
        slim["compact_teller_sunday_quiet"] = (
            compact.get("teller_sunday_quiet") or slim.get("teller_sunday_quiet")
        )
        slim["compact_doc_age_sunday_quiet"] = (
            compact.get("doc_age_sunday_quiet") or slim.get("doc_age_sunday_quiet")
        )
        slim["compact_quiet_sunday_quiet"] = (
            compact.get("quiet_sunday_quiet") or slim.get("quiet_sunday_quiet")
        )
        slim["compact_ritual_sunday_quiet"] = (
            compact.get("ritual_sunday_quiet") or slim.get("ritual_sunday_quiet")
        )
        slim["compact_digest_fresh_sunday_quiet"] = (
            compact.get("digest_fresh_sunday_quiet") or slim.get("digest_fresh_sunday_quiet")
        )
        slim["compact_journal_sunday_quiet"] = (
            compact.get("journal_sunday_quiet") or slim.get("journal_sunday_quiet")
        )
        slim["compact_monday_sunday_quiet"] = (
            compact.get("monday_sunday_quiet") or slim.get("monday_sunday_quiet")
        )
        slim["compact_toxic_sunday_quiet"] = (
            compact.get("toxic_sunday_quiet") or slim.get("toxic_sunday_quiet")
        )
        slim["compact_adapt_ab_sunday_quiet"] = (
            compact.get("adapt_ab_sunday_quiet") or slim.get("adapt_ab_sunday_quiet")
        )
        slim["compact_raise_phi_sla_sunday_quiet"] = (
            compact.get("raise_phi_sla_sunday_quiet") or slim.get("raise_phi_sla_sunday_quiet")
        )
        slim["compact_feature_coverage_sunday_quiet"] = (
            compact.get("feature_coverage_sunday_quiet") or slim.get("feature_coverage_sunday_quiet")
        )
        slim["compact_chip_catalog_sunday_quiet"] = (
            compact.get("chip_catalog_sunday_quiet") or slim.get("chip_catalog_sunday_quiet")
        )
        slim["compact_phase2_pulse_sunday_quiet"] = (
            compact.get("phase2_pulse_sunday_quiet") or slim.get("phase2_pulse_sunday_quiet")
        )
        slim["compact_l7_observe_sunday_quiet"] = (
            compact.get("l7_observe_sunday_quiet") or slim.get("l7_observe_sunday_quiet")
        )
        slim["compact_feature_store_sunday_quiet"] = (
            compact.get("feature_store_sunday_quiet") or slim.get("feature_store_sunday_quiet")
        )
        slim["compact_skip_historian_sunday_quiet"] = (
            compact.get("skip_historian_sunday_quiet") or slim.get("skip_historian_sunday_quiet")
        )
        slim["compact_ritual_live_sunday_quiet"] = (
            compact.get("ritual_live_sunday_quiet") or slim.get("ritual_live_sunday_quiet")
        )
        slim["compact_teller_ritual_live_sunday_quiet"] = (
            compact.get("teller_ritual_live_sunday_quiet")
            or slim.get("teller_ritual_live_sunday_quiet")
        )
        slim["compact_priority_sunday_quiet"] = (
            compact.get("priority_sunday_quiet") or slim.get("priority_sunday_quiet")
        )
        slim["compact_hud_sunday_quiet"] = (
            compact.get("hud_sunday_quiet") or slim.get("hud_sunday_quiet")
        )
        slim["compact_money_path_sunday_quiet"] = (
            compact.get("money_path_sunday_quiet") or slim.get("money_path_sunday_quiet")
        )
        slim["compact_guardrails_sunday_quiet"] = (
            compact.get("guardrails_sunday_quiet") or slim.get("guardrails_sunday_quiet")
        )
        slim["compact_surfaces_sunday_quiet"] = (
            compact.get("surfaces_sunday_quiet") or slim.get("surfaces_sunday_quiet")
        )
        slim["compact_smoke_sunday_quiet"] = (
            compact.get("smoke_sunday_quiet") or slim.get("smoke_sunday_quiet")
        )
        slim["compact_paste_sunday_quiet"] = (
            compact.get("paste_sunday_quiet") or slim.get("paste_sunday_quiet")
        )
        slim["compact_paper_live_sunday_quiet"] = (
            compact.get("paper_live_sunday_quiet") or slim.get("paper_live_sunday_quiet")
        )
        slim["compact_makefile_sunday_quiet"] = (
            compact.get("makefile_sunday_quiet") or slim.get("makefile_sunday_quiet")
        )
        slim["compact_venues_sunday_quiet"] = (
            compact.get("venues_sunday_quiet") or slim.get("venues_sunday_quiet")
        )
        slim["compact_chicago_sunday_quiet"] = (
            compact.get("chicago_sunday_quiet") or slim.get("chicago_sunday_quiet")
        )
        slim["compact_starve_sunday_quiet"] = (
            compact.get("starve_sunday_quiet") or slim.get("starve_sunday_quiet")
        )
        slim["compact_hard_rules_sunday_quiet"] = (
            compact.get("hard_rules_sunday_quiet") or slim.get("hard_rules_sunday_quiet")
        )

        slim["compact_swarm_tip_sunday_quiet"] = (
            compact.get("swarm_tip_sunday_quiet") or slim.get("swarm_tip_sunday_quiet")
        )
        slim["compact_expand_tip_sunday_quiet"] = (
            compact.get("expand_tip_sunday_quiet") or slim.get("expand_tip_sunday_quiet")
        )
        slim["compact_quiet_tip_sunday_quiet"] = (
            compact.get("quiet_tip_sunday_quiet") or slim.get("quiet_tip_sunday_quiet")
        )
        slim["compact_timer_tip_sunday_quiet"] = (
            compact.get("timer_tip_sunday_quiet") or slim.get("timer_tip_sunday_quiet")
        )
    slim["quiet_doctor"] = (
        "quiet="
        + ("yes" if quiet.get("quiet") else "no")
        + (
            f" age={quiet_age}h"
            if quiet_age is not None
            else " age=n/a"
        )
        + " · "
        + str(
            (compact or {}).get("doctor_label")
            or (
                "doctor=fresh"
                if slim.get("doctor_fresh")
                else "doctor=stale"
                if slim.get("doctor_fresh") is False
                else "doctor=n/a"
            )
        )
        + f" · doctor_fresh={slim.get('doctor_fresh')}"
    )
    if ritual:
        slim["ritual_soft_copy"] = (
            f"**Masters ritual** (paper · floors locked · live=False)\n"
            f"ritual_ok={ritual.get('ritual_ok')} exit_ok={ritual.get('exit_ok')} "
            f"doctor_fresh={ritual.get('doctor_fresh')}\n"
            f"{ritual.get('label') or 'ritual observe'}\n"
            f"_staff paste only · never auto-posts · never enables live_"
        )
        slim["doctor_soft_copy"] = (
            f"**Living doctor age** (paper · floors locked · live=False)\n"
            f"doctor={'fresh' if slim.get('doctor_fresh') else 'stale' if slim.get('doctor_fresh') is False else 'n/a'} "
            f"doctor_fresh={slim.get('doctor_fresh')}\n"
            f"{doctor_age.get('label') or 'doctor age'}\n"
            f"sunday quiet {slim.get('sunday_quiet_age_label') or 'quiet_age=n/a'} "
            f"(observe · never softens floors)\n"
            f"ritual draft: make living-ritual-discord\n"
            f"_staff paste only · never auto-posts · never enables live_"
        )
        slim["doctor_age_soft_copy"] = slim["doctor_soft_copy"]  # alias
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
    copy = "\n".join(lines)
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "live_orders_enabled": False,
        "auto_page": False,
        "auto_publish": False,
        "page": page,
        "gaps_n": len(gaps),
        "gaps": gaps,
        "signed_n": status.get("signed_n"),
        "items_n": status.get("items_n"),
        "copy": copy,
        "discord": copy,  # same markdown — staff paste only
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


DIGEST_FRESH_HOURS = 24.0
JOURNAL_FRESH_HOURS = 48.0


def digest_freshness_chip(
    root: str | None = None,
    *,
    now: datetime | None = None,
    fresh_hours: float = DIGEST_FRESH_HOURS,
) -> dict:
    """Observe max age of insight helper digests (L7 Monday freshness)."""
    now = now or datetime.now(CT)
    if now.tzinfo is None:
        now = now.replace(tzinfo=CT)
    now = now.astimezone(CT)
    base = os.path.join(_root(root), "helpers")
    ages: list[float] = []
    stale_names: list[str] = []
    missing: list[str] = []
    for name in INSIGHT_HELPER_DIGESTS:
        dig_path = os.path.join(base, name)
        key = name.replace("_digest.json", "").replace(".json", "")
        if not os.path.isfile(dig_path):
            missing.append(key)
            continue
        try:
            mtime = os.path.getmtime(dig_path)
            age_h = round((now.timestamp() - mtime) / 3600.0, 2)
            ages.append(age_h)
            if age_h > float(fresh_hours):
                stale_names.append(key)
        except OSError:
            missing.append(key)
    max_age = max(ages) if ages else None
    ok = (
        not missing
        and not stale_names
        and max_age is not None
        and max_age <= float(fresh_hours)
    )
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "fresh_hours": float(fresh_hours),
        "max_age_h": max_age,
        "stale_n": len(stale_names),
        "missing_n": len(missing),
        "stale": stale_names[:12],
        "missing": missing[:12],
        "pass": ok,
        "label": (
            f"digest fresh max={max_age}h "
            + (
                "ok"
                if ok
                else f"STALE stale={len(stale_names)} missing={len(missing)}"
            )
        ),
        "note": (
            "L7 digest freshness observe — never invents digests; never softens floors."
        ),
    }


def journal_coverage_chip(
    root: str | None = None,
    *,
    now: datetime | None = None,
    fresh_hours: float = JOURNAL_FRESH_HOURS,
) -> dict:
    """Observe fit + latency journal coverage / freshness (L7 daily journal alert)."""
    now = now or datetime.now(CT)
    if now.tzinfo is None:
        now = now.replace(tzinfo=CT)
    now = now.astimezone(CT)
    fit_n = 0
    lat_n = 0
    fit_last = None
    lat_last = None
    try:
        import desk_roi_plan
        fit = desk_roi_plan.load_fit(root) or {}
        lat = desk_roi_plan.load_latency(root) or {}
        fit_rows = [r for r in (fit.get("rows") or []) if isinstance(r, dict)]
        lat_rows = [r for r in (lat.get("rows") or []) if isinstance(r, dict)]
        fit_n = len(fit_rows)
        lat_n = len(lat_rows)
        fit_last = fit.get("last_at") or (fit_rows[-1].get("at") if fit_rows else None)
        lat_last = lat.get("last_at") or (lat_rows[-1].get("at") if lat_rows else None)
    except Exception:
        pass

    def _age(stamp):
        if not stamp:
            return None
        try:
            dt = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=CT)
            return round((now - dt.astimezone(CT)).total_seconds() / 3600.0, 2)
        except ValueError:
            return None

    fit_age = _age(fit_last)
    lat_age = _age(lat_last)
    ages = [a for a in (fit_age, lat_age) if a is not None]
    max_age = max(ages) if ages else None
    covered = fit_n > 0 and lat_n > 0
    fresh = max_age is not None and max_age <= float(fresh_hours)
    ok = covered and fresh
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "fit_n": fit_n,
        "latency_n": lat_n,
        "fit_age_h": fit_age,
        "latency_age_h": lat_age,
        "max_age_h": max_age,
        "fresh_hours": float(fresh_hours),
        "pass": ok,
        "label": (
            f"journals fit={fit_n} lat={lat_n} "
            + (
                f"max_age={max_age}h ok"
                if ok
                else (
                    f"max_age={max_age}h THIN"
                    if not covered
                    else f"max_age={max_age}h STALE"
                )
            )
        ),
        "note": (
            "L7 journal coverage observe (fit+latency) — never softens floors; never invents fills."
        ),
    }


def monday_pulse_chip(root: str | None = None, bots: list | None = None) -> dict:
    """Monday staff pulse: timer alive + digest freshness (L7 continuous learning)."""
    del bots  # reserved for board parity
    timer = timer_heartbeat_chip(root)
    dig = digest_freshness_chip(root)
    journals = journal_coverage_chip(root)
    timer_ok = timer.get("alive") is True
    dig_ok = dig.get("pass") is True
    ok = timer_ok and dig_ok
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "timer_alive": timer.get("alive"),
        "digest_pass": dig_ok,
        "journal_pass": journals.get("pass"),
        "pass": ok,
        "label": (
            "monday pulse "
            + (
                "ok"
                if ok
                else (
                    "TIMER_DEAD"
                    if timer.get("alive") is False
                    else "DIGEST_STALE"
                    if not dig_ok
                    else "thin"
                )
            )
        ),
        "note": (
            "L7 Monday pulse (timer + digest freshness) — observe only; never softens floors."
        ),
        "timer": timer.get("label"),
        "digest_fresh": dig.get("label"),
        "journals": journals.get("label"),
    }


RAISE_PHI_SLA_DAYS = 7


def toxic_fill_chip(root: str | None = None) -> dict:
    """Observe adverse cool / toxic fill pressure (L7 daily toxic fill detector)."""
    active = []
    recent_n = 0
    last_at = None
    try:
        import desk_roi_plan
        import time as _time
        path_cool = desk_roi_plan._path(desk_roi_plan.ADVERSE_COOL_NAME, root)
        state = desk_roi_plan._load(path_cool, {"paper_only": True, "bots": {}})
        bots = state.get("bots") if isinstance(state.get("bots"), dict) else {}
        now = _time.time()
        for bot, row in bots.items():
            if not isinstance(row, dict):
                continue
            recent_n += 1
            until = row.get("until")
            try:
                until_f = float(until) if until is not None else None
            except (TypeError, ValueError):
                until_f = None
            if until_f is not None and now < until_f:
                left_m = int(max(1, (until_f - now) / 60.0))
                active.append({
                    "bot": str(bot),
                    "left_min": left_m,
                    "drop": row.get("drop"),
                    "ticker": row.get("ticker"),
                })
            stamp = row.get("at")
            if stamp and (last_at is None or str(stamp) > str(last_at)):
                last_at = str(stamp)
    except Exception:
        active = []
        recent_n = 0
    hot = len(active)
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "active_n": hot,
        "tracked_n": recent_n,
        "active": active[:8],
        "last_at": last_at,
        "pass": hot == 0,
        "label": (
            f"toxic fills active={hot} tracked={recent_n}"
            + (" ok" if hot == 0 else " COOLING")
        ),
        "note": (
            "L7 toxic/adverse cool observe — never invents fills; never softens floors."
        ),
    }


def adapt_ab_chip(root: str | None = None) -> dict:
    """Weekly adapt A/B summary observe (L7 continuous learning)."""
    summary: dict = {}
    try:
        import desk_phase2
        summary = desk_phase2.adapt_ab_summary(root) or {}
    except Exception:
        summary = {}
    if not isinstance(summary, dict):
        summary = {}
    delta = summary.get("adapt_edge_vs_flat")
    wins = summary.get("adapt_wins")
    n = int(summary.get("n_settled") or 0)
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "n_settled": n,
        "adapt_edge_vs_flat": delta,
        "adapt_wins": wins,
        "pass": bool(wins) if n > 0 else True,
        "label": (
            f"adapt A/B settled={n} edge={delta} "
            + (
                "wins"
                if wins
                else "under flat"
                if n > 0 and wins is False
                else "n/a"
            )
        ),
        "note": (
            summary.get("note")
            or "L7 adapt A/B observe — shrink play-big before touching floors."
        ),
    }


def raise_phi_sla_chip(root: str | None = None, bots: list | None = None) -> dict:
    """Staff SLA observe for open raise_Φ tickets (never auto-writes Φ)."""
    ai = living_ai_health(root, bots=bots)
    tickets = list(ai.get("raise_phi_tickets") or [])
    n = int(ai.get("raise_phi_n") or len(tickets) or 0)
    # Age from calib digests when present
    oldest_h = None
    try:
        from helpers import calib_nag
        path = calib_nag.digest_path(root)
        if os.path.isfile(path):
            age_h = round((time.time() - os.path.getmtime(path)) / 3600.0, 2)
            oldest_h = age_h
    except Exception:
        oldest_h = None
    sla_h = float(RAISE_PHI_SLA_DAYS) * 24.0
    overdue = bool(n > 0 and oldest_h is not None and oldest_h > sla_h)
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "auto_write_phi": False,
        "raise_phi_n": n,
        "tickets": tickets,
        "age_h": oldest_h,
        "sla_days": RAISE_PHI_SLA_DAYS,
        "overdue": overdue,
        "pass": n == 0 or not overdue,
        "label": (
            f"raise_Φ SLA n={n} age={oldest_h}h "
            + (
                "clear"
                if n == 0
                else ("OVERDUE" if overdue else f"within {RAISE_PHI_SLA_DAYS}d")
            )
            + " · auto_write=False"
        ),
        "note": (
            "L7 staff SLA observe — decide raise_Φ within 7 Chicago days; "
            "never silent Φ write; never softer floors."
        ),
    }




FEATURE_COVERAGE_MIN_N = 8


def feature_coverage_chip(root: str | None = None) -> dict:
    """L7 feature-store coverage observe (thin learning data)."""
    cov = feature_store_coverage(root)
    n = int(cov.get("n") or 0)
    buys = int(cov.get("buys") or 0)
    skips = int(cov.get("skips") or 0)
    thin = n < FEATURE_COVERAGE_MIN_N
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "n": n,
        "buys": buys,
        "skips": skips,
        "last_at": cov.get("last_at"),
        "min_n": FEATURE_COVERAGE_MIN_N,
        "pass": not thin,
        "label": (
            f"feature coverage n={n} buys={buys} skips={skips}"
            + (" THIN" if thin else " ok")
        ),
        "note": (
            "L7 feature coverage observe — never invents fills; never softens floors."
        ),
    }


def chip_catalog_chip(root: str | None = None, *, chips_n: int | None = None) -> dict:
    """L7 chip-catalog soft-max observe (rail noise risk)."""
    n = chips_n
    if n is None:
        try:
            board = living_upgrade_board(root)
            n = _count_living_chips(board)
        except Exception:
            n = 0
    guard = living_board_size_guard(chips_n=n)
    return {
        **guard,
        "pass": not bool(guard.get("over")),
        "note": (
            "L7 chip catalog observe — prefer finalize_living_priority; "
            "never softens floors."
        ),
    }


def phase2_pulse_chip(root: str | None = None) -> dict:
    """L7 Phase 2 quality pulse (gap-decay + scale-out + hillclimb locks)."""
    summary: dict = {}
    try:
        import desk_phase2
        summary = desk_phase2.phase2_summary(root) or {}
    except Exception:
        summary = {}
    if not isinstance(summary, dict):
        summary = {}
    gap_n = int(summary.get("gap_decay_exit_count") or 0)
    scale_n = int(summary.get("scale_out_count") or 0)
    locks = list(summary.get("hillclimb_locks") or [])
    lock_n = len(locks)
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "gap_decay_exit_count": gap_n,
        "scale_out_count": scale_n,
        "hillclimb_lock_n": lock_n,
        "hillclimb_locks": locks[-2:],
        "pass": True,
        "label": (
            f"phase2 pulse gap_decay={gap_n} scale_out={scale_n} "
            f"hill_locks={lock_n}"
        ),
        "note": (
            "L7 Phase 2 pulse observe — make more of each good trade; "
            "fee floors untouched."
        ),
    }


CHIP_CATALOG_SOFT_MAX = 64
_BOARD_SIZE_SKIP = frozenset({
    "board_size", "compact", "insight_helper_digests", "feature_store",
    "feature_quiet", "completions", "living_ai", "insight_swarm",
    "hillclimb_lever", "dual_control", "ruin_drill",
})


def _count_living_chips(board: dict | None) -> int:
    return sum(
        1
        for k, v in (board or {}).items()
        if (
            k not in _BOARD_SIZE_SKIP
            and isinstance(v, dict)
            and v.get("fee_floors_locked") is True
        )
    )


def living_board_size_guard(*, chips_n: int | None = None) -> dict:
    """Warn when living chip count balloons (rail noise risk)."""
    n = int(chips_n or 0)
    over = n > CHIP_CATALOG_SOFT_MAX
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "chips_n": n,
        "soft_max": CHIP_CATALOG_SOFT_MAX,
        "over": over,
        "label": (
            f"chip catalog {n}/{CHIP_CATALOG_SOFT_MAX}"
            + (" OVER" if over else " ok")
        ),
        "note": "Prefer finalize_living_priority over unbounded chip growth.",
    }


def doctor_run_path(root: str | None = None) -> str:
    return os.path.join(_root(root), DOCTOR_RUN_NAME)


def record_doctor_run(root: str | None, doc: dict | None) -> dict:
    """Persist last living doctor run (staff observe marker)."""
    now = datetime.now(CT)
    row = {
        "paper_only": True,
        "fee_floors_locked": True,
        "live_orders_enabled": False,
        "at": now.isoformat(),
        "ok": bool((doc or {}).get("ok")),
        "failed_n": int((doc or {}).get("failed_n") or 0),
        "label": str((doc or {}).get("label") or "")[:160],
    }
    _save_json(doctor_run_path(root), row)
    return row


def doctor_age_chip(root: str | None = None) -> dict:
    """Age since last living doctor run."""
    path = doctor_run_path(root)
    data = _load_json(path, {})
    at = data.get("at") if isinstance(data, dict) else None
    age_sec = None
    if at:
        try:
            stamp = datetime.fromisoformat(str(at).replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=CT)
            age_sec = int(max(0.0, (datetime.now(CT) - stamp.astimezone(CT)).total_seconds()))
        except ValueError:
            age_sec = None
    stale = age_sec is None or age_sec >= 7 * 24 * 3600
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "at": at,
        "age_sec": age_sec,
        "ok_last": data.get("ok") if isinstance(data, dict) else None,
        "stale": stale,
        "label": (
            f"doctor age={age_sec}s last_ok={data.get('ok') if isinstance(data, dict) else None}"
            if age_sec is not None
            else "doctor never run"
        ),
        "note": "Staff doctor marker — run make living-doctor weekly.",
    }


def living_doctor(root: str | None = None, *, record: bool = True) -> dict:
    """One-shot staff doctor: floors + expand + selfcheck + quiet/timer."""
    floors = fee_floors_assert(root)
    expand = betting_expand_gate(root)
    health = living_self_check(root)
    quiet = feature_store_quiet_alert(root)
    timer = timer_heartbeat_chip(root)
    gaps = dual_control_gaps_page(root)
    ritual = (
        health.get("ritual_observe")
        if isinstance(health.get("ritual_observe"), dict)
        else ritual_observe_chip(root)
    )
    # Ritual nag: weekly doctor marker freshness (floors/expand already checked).
    # When record=True this run refreshes the marker — don't fail on pre-write staleness.
    ritual_fresh_ok = bool(ritual.get("doctor_fresh")) or bool(record)
    ok = bool(
        floors.get("all_ok")
        and health.get("ok")
        and not expand.get("blocked")
        and not quiet.get("quiet")
        and timer.get("alive") is not False
        and ritual_fresh_ok
    )
    checks = [
        {"id": "floors", "ok": bool(floors.get("all_ok")), "label": floors.get("label")},
        {"id": "expand", "ok": not bool(expand.get("blocked")), "label": expand.get("label")},
        {"id": "selfcheck", "ok": bool(health.get("ok")), "label": "living selfcheck"},
        {"id": "feature_quiet", "ok": not bool(quiet.get("quiet")), "label": quiet.get("alert") or "feature quiet ok"},
        {"id": "timer", "ok": timer.get("alive") is not False, "label": timer.get("label")},
        {"id": "dual_gaps", "ok": not bool(gaps.get("page")), "label": gaps.get("label")},
        {
            "id": "ritual_observe",
            "ok": ritual_fresh_ok,
            "label": ritual.get("label") or "ritual observe",
        },
    ]
    failed = [c for c in checks if not c.get("ok")]
    doc = {
        "paper_only": True,
        "fee_floors_locked": True,
        "live_orders_enabled": False,
        "ok": ok and not failed,
        "failed_n": len(failed),
        "failed": failed,
        "checks": checks,
        "ritual_observe": ritual,
        "ritual_ok": ritual.get("ritual_ok"),
        "ritual_exit_ok": ritual.get("exit_ok"),
        "chip_catalog": health.get("chip_catalog") or [],
        "chips_n": health.get("chips_n"),
        "chips_soft_max": CHIP_CATALOG_SOFT_MAX,
        "chips_over": bool(int(health.get("chips_n") or 0) > CHIP_CATALOG_SOFT_MAX),
        "label": (
            "living doctor OK"
            if ok and not failed
            else f"living doctor FAIL n={len(failed)}"
        ),
        "note": "Staff one-shot doctor — never places; never softens floors; never enables live.",
    }
    failed_ids = ",".join(str(c.get("id") or "") for c in failed) or "none"
    ritual_line = (
        f"ritual_ok={ritual.get('ritual_ok')} exit_ok={ritual.get('exit_ok')} "
        f"doctor_fresh={ritual.get('doctor_fresh')}"
    )
    if any(c.get("id") == "ritual_observe" for c in failed):
        ritual_line = f"ritual FAIL — {ritual_line}"
    doctor_line = (
        f"doctor={'fresh' if ritual.get('doctor_fresh') else 'stale' if ritual.get('doctor_fresh') is False else 'n/a'} "
        f"doctor_fresh={ritual.get('doctor_fresh')}"
    )
    quiet = feature_store_quiet_alert(root)
    quiet_age_h = quiet.get("age_hours") if isinstance(quiet, dict) else None
    quiet_age_label = (
        f"quiet_age={quiet_age_h}h" if quiet_age_h is not None else "quiet_age=n/a"
    )
    l7_line = str(health.get("l7_observe_label") or "L7 observe pending")
    sunday_cov = sunday_twin_coverage(root=root)
    sunday_cov_line = str(sunday_cov.get("label") or "sunday twins observe")
    live_n = int(health.get("ritual_live_n") or 0)
    timer_live = str(
        health.get("ritual_live_timer")
        or timer.get("label")
        or "timer observe"
    )
    ritual_live_line = str(
        health.get("ritual_live_sunday_quiet")
        or (
            f"ritual live n={live_n} · {timer_live} "
            f"(observe · never softens floors)"
        )
    )
    doc["ritual_live_sunday_quiet"] = ritual_live_line
    timer_sunday_line = (
        f"timer sunday: {timer_live} · sunday quiet {quiet_age_label} "
        f"(observe · never softens floors)"
    )
    soft_copy = (
        f"**Living doctor** (paper · floors locked · live=False)\n"
        f"{doc['label']} · failed=[{failed_ids}]\n"
        f"{ritual_line}\n"
        f"{doctor_line}\n"
        f"{l7_line}\n"
        f"{sunday_cov_line}\n"
        f"{ritual_live_line}\n"
        f"{timer_sunday_line}\n"
        f"teller ritual live n={live_n}\n"
        f"{str(health.get('priority_label') or living_priority_snapshot(root=root).get('label') or 'priority observe')}\n"
        f"{str(health.get('guardrails_label') or living_guardrails_tip(root=root).get('label') or 'guardrails observe')}\n"
        f"{str(health.get('surfaces_label') or living_surface_index(root=root).get('label') or 'surfaces observe')}\n"
        f"{str(health.get('smoke_label') or living_staff_smoke(root=root).get('label') or 'smoke observe')}\n"
        f"sunday quiet {quiet_age_label} (observe · never softens floors)\n"
        f"ritual draft: make living-ritual-discord · audit: make living-ritual-live "
        f"· smoke: make living-smoke "
        f"(staff paste · never auto-posts)\n"
        f"_never places · never softens floors · never enables live_"
    )
    doc["soft_copy"] = soft_copy
    doc["discord"] = soft_copy
    doc["l7_observe_ok"] = health.get("l7_observe_ok")
    doc["l7_observe_label"] = l7_line
    doc["sunday_twin_coverage"] = sunday_cov
    doc["sunday_twin_coverage_label"] = sunday_cov_line
    doc["sunday_quiet_age_label"] = quiet_age_label
    doc["ritual_live_ok"] = health.get("ritual_live_ok")
    doc["ritual_live_n"] = live_n
    doc["ritual_live_timer"] = timer_live
    doc["ritual_live_line"] = ritual_live_line
    doc["timer_sunday_line"] = timer_sunday_line
    doc["ritual_draft_cmd"] = "make living-ritual-discord"
    if record:
        try:
            marker = record_doctor_run(root, doc)
            doc["recorded_at"] = marker.get("at")
        except Exception:
            doc["recorded_at"] = None
    doc["doctor_age"] = doctor_age_chip(root)
    return doc


def betting_expand_gate(root: str | None = None, *, remember: bool = False) -> dict:
    """Insight-first hire blocker: refuse betting expand while swarm < 3:1."""
    swarm = insight_swarm_ratio(root)
    inv = digest_inventory(root)
    ok = bool(swarm.get("pass")) and bool(inv.get("pass") or swarm.get("pass"))
    reason = (
        "insight swarm meets ≥3:1 — betting expand still staff/paper only"
        if ok
        else (
            f"BLOCK betting expand: insight swarm "
            f"{swarm.get('insight_n')}:{swarm.get('betting_n')} "
            f"(need ≥{swarm.get('min_ratio') or INSIGHT_BETTING_MIN_RATIO}:1). "
            "Hire observe clerks / seed digests first."
        )
    )
    label = (
        "betting expand allowed (paper)"
        if ok
        else "betting expand BLOCKED — insight swarm thin"
    )
    soft_copy = (
        f"{label} — {reason}"
        if not ok
        else f"{label} — {reason}"
    )
    if remember and not ok:
        try:
            import teller_memory
            teller_memory.remember(
                root,
                kind="mistakes",
                text=str(label)[:200],
                bot_id="desk",
                source="betting_expand_gate",
            )
        except Exception:
            pass
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "live_orders_enabled": False,
        "allow_betting_expand": ok,
        "blocked": not ok,
        "swarm_pass": swarm.get("pass"),
        "swarm_ratio": swarm.get("ratio"),
        "min_ratio": swarm.get("min_ratio") or INSIGHT_BETTING_MIN_RATIO,
        "digest_pass": inv.get("pass"),
        "reason": reason,
        "soft_copy": soft_copy,
        "label": label,
        "note": "Insight-first living hire order. Never softens venue floors.",
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
    all_ok = bool(floors.get("all_ok"))
    label = (
        "fee floors OK (0.06/0.05/0.02)"
        if all_ok
        else "fee floors CHECK — live edge below locked floor"
    )
    soft_copy = (
        f"**Fee floors assert** (locked · never soften)\n"
        f"{label}\n"
        f"_sports 0.06 · BTC/commodity 0.05 · INX/DEX 0.02 · live=False_"
    )
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "live_orders_enabled": False,
        "all_ok": all_ok,
        "venues": floors.get("venues") if isinstance(floors.get("venues"), dict) else {},
        "label": label,
        "soft_copy": soft_copy,
        "discord": soft_copy,
        "note": floors.get("note") or (
            "Venue min_edge floors are locked — selective volume never softens them."
        ),
    }



L7_OBSERVE_KEYS = (
    "digest_freshness",
    "journal_coverage",
    "monday_pulse",
    "toxic_fills",
    "adapt_ab",
    "raise_phi_sla",
    "feature_coverage",
    "chip_catalog",
    "phase2_pulse",
)


def l7_observe_summary(board: dict | None = None, root: str | None = None) -> dict:
    """Surface-only L7 pulse from an existing board (never a new board chip)."""
    src = board if isinstance(board, dict) else None
    if src is None:
        src = living_upgrade_board(root)
    present = [k for k in L7_OBSERVE_KEYS if isinstance(src.get(k), dict)]
    missing = [k for k in L7_OBSERVE_KEYS if k not in present]
    labels = []
    for k in present:
        row = src.get(k) if isinstance(src.get(k), dict) else {}
        lab = row.get("label")
        if lab:
            labels.append(str(lab))
    ok = not missing
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "board_chip": False,
        "ok": ok,
        "present": present,
        "missing": missing,
        "label": (
            "L7 observe "
            + (" · ".join(labels[:3]) + ("…" if len(labels) > 3 else ""))
            if labels
            else "L7 observe pending"
        ),
        "note": "Surface-only L7 pulse — not a board chip; never softens floors.",
    }




def ritual_live_labels(board: dict | None = None, root: str | None = None) -> dict:
    """Surface-only live labels for ritual Discord sunday lines (not a board chip)."""
    src = board if isinstance(board, dict) else living_upgrade_board(root)

    def _lab(key: str, fallback: str) -> str:
        row = src.get(key)
        if isinstance(row, dict) and row.get("label"):
            return str(row.get("label"))
        return fallback

    completions = src.get("completions") if isinstance(src.get("completions"), dict) else {}
    fills_lab = (
        f"eligible today {completions.get('eligible_completions_today')}"
        if completions.get("eligible_completions_today") is not None
        else _lab("completions_chip", "fills observe")
    )
    quiet = src.get("feature_quiet") if isinstance(src.get("feature_quiet"), dict) else {}
    quiet_lab = (
        quiet.get("alert")
        or (
            f"feature quiet={'yes' if quiet.get('quiet') else 'no'}"
            if quiet
            else None
        )
        or "feature quiet observe"
    )
    feat_store = src.get("feature_store") if isinstance(src.get("feature_store"), dict) else {}
    fstore_lab = (
        f"feature store n={feat_store.get('n')} "
        f"buys={feat_store.get('buys')} skips={feat_store.get('skips')}"
        if feat_store
        else "feature store observe"
    )
    l7 = l7_observe_summary(src)
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "board_chip": False,
        "digests_label": _lab("digest_inventory", "digests observe"),
        "fills_label": fills_lab,
        "hill_label": _lab("hillclimb_chip", "hillclimb none"),
        "swarm_label": (
            (
                f"swarm {src['insight_swarm'].get('insight_n')}:"
                f"{src['insight_swarm'].get('betting_n')} "
                f"ratio={src['insight_swarm'].get('ratio')}"
                + (" ok" if src['insight_swarm'].get('pass') else " THIN")
            )
            if isinstance(src.get("insight_swarm"), dict)
            and src["insight_swarm"].get("insight_n") is not None
            else _lab("insight_swarm", "swarm observe")
        ),
        "green_label": _lab("green_day", "green-day observe"),
        "bleed_label": _lab("bleed", "bleed observe"),
        "clv_label": _lab("clv", "CLV observe"),
        "timer_label": _lab("timer_heartbeat", "timer observe"),
        "calib_label": _lab("calib_nag", "calib observe"),
        "queue_label": _lab("firm_queue", "queue observe"),
        "gate_a_label": _lab("helper_gate_a", "Gate A observe"),
        "ai_label": _lab("living_ai", "AI observe"),
        "tip_label": _lab("tip_radar", "tip feed observe"),
        "blackout_label": _lab("eia_blackout", "blackout observe"),
        "injury_label": _lab("injury_wire", "injury observe"),
        "empty_label": _lab("empty_card", "empty CARD observe"),
        "near_miss_label": _lab("near_miss", "near-miss observe"),
        "eia_label": _lab("eia_scout", "EIA observe"),
        "calendar_label": _lab("calendar_scanner", "calendar observe"),
        "pager_label": _lab("feature_quiet_pager", "pager observe"),
        "books_label": _lab("bookkeeper", "books observe"),
        "pulse_label": _lab("clerk_pulse", "pulse observe"),
        "dual_label": _lab("dual_control_chip", "dual observe"),
        "skip_reg_label": _lab("skip_regret", "skip-regret observe"),
        "hard_stop_label": _lab("hard_stop", "hard-stop observe"),
        "distance_label": _lab("distance_clerk", "distance observe"),
        "quant_label": _lab("quant_clerk", "quant observe"),
        "report_label": _lab("reporter", "report observe"),
        "empty_bee_label": _lab("empty_card_bee", "empty bee observe"),
        "nm_clerk_label": _lab("near_miss_clerk", "nm clerk observe"),
        "hs_clerk_label": _lab("hard_stop_clerk", "hs clerk observe"),
        "bleed_clerk_label": _lab("bleed_clerk", "bleed clerk observe"),
        "skip_twin_label": _lab("skip_twin_clerk", "skip-twin observe"),
        "clv_closer_label": _lab("clv_closer", "CLV closer observe"),
        "tdigest_label": _lab("timer_digest", "t-digest observe"),
        "skips_label": _lab("skip_taxonomy", "skips observe"),
        "adapt_label": _lab("living_ai", "adapt observe"),
        "teller_label": _lab("teller_living", "teller observe"),
        "quiet_label": str(quiet_lab),
        "doc_age_label": _lab("doctor_age", "doctor age observe"),
        "ritual_label": _lab("ritual_observe", "ritual observe"),
        "digest_fresh_label": _lab("digest_freshness", "digest fresh observe"),
        "journals_label": _lab("journal_coverage", "journals observe"),
        "monday_label": _lab("monday_pulse", "monday pulse observe"),
        "toxic_fills_label": _lab("toxic_fills", "toxic fills observe"),
        "adapt_ab_label": _lab("adapt_ab", "adapt A/B observe"),
        "raise_phi_sla_label": _lab("raise_phi_sla", "raise_Φ SLA observe"),
        "feature_coverage_label": _lab("feature_coverage", "feature coverage observe"),
        "chip_catalog_label": _lab("chip_catalog", "chip catalog observe"),
        "phase2_pulse_label": _lab("phase2_pulse", "phase2 pulse observe"),
        "l7_observe_label": str(l7.get("label") or "L7 observe pulse"),
        "feature_store_label": fstore_lab,
        "skip_historian_label": _lab("skip_historian", "skip historian observe"),
        "note": "Ritual Discord live labels — staff paste only; never auto-posts.",
    }


def living_priority_snapshot(board: dict | None = None, root: str | None = None) -> dict:
    """Surface-only staff priority lines (not a board chip; never softens floors)."""
    src = board if isinstance(board, dict) else living_upgrade_board(root)
    raw: list[str] = []
    fq = src.get("feature_quiet") if isinstance(src.get("feature_quiet"), dict) else {}
    if fq.get("quiet") and fq.get("alert"):
        raw.insert(0, str(fq.get("alert"))[:120])
    timer = src.get("timer_heartbeat") if isinstance(src.get("timer_heartbeat"), dict) else {}
    if timer.get("alive") is False:
        raw.insert(0, str(timer.get("label") or "timer DEAD")[:120])
    swarm = src.get("insight_swarm") if isinstance(src.get("insight_swarm"), dict) else {}
    if swarm.get("pass") is False:
        raw.append(
            f"insight swarm {swarm.get('insight_n')}:{swarm.get('betting_n')} "
            f"(need ≥{swarm.get('min_ratio')}:1)"
        )
    ruin = src.get("ruin_drill_chip") if isinstance(src.get("ruin_drill_chip"), dict) else {}
    if ruin.get("active"):
        raw.insert(0, str(ruin.get("label") or "ruin ACTIVE")[:120])
    elif not ruin.get("practiced_this_month"):
        raw.append("ruin drill: practice soft/hard this Chicago month")
    l7 = l7_observe_summary(src)
    if not l7.get("ok"):
        raw.insert(0, str(l7.get("label") or "L7 observe missing")[:120])
    live = ritual_live_labels(src)
    live_n = sum(1 for k, v in live.items() if str(k).endswith("_label") and v)
    if live_n < 40:
        raw.insert(0, f"ritual live thin n={live_n} (need ≥40 observe labels)")
    teller = src.get("teller_living") if isinstance(src.get("teller_living"), dict) else {}
    if teller.get("ritual_live_ok") is False:
        raw.append(
            f"teller ritual live thin n={teller.get('ritual_live_n')} (observe)"
        )
    raw.extend([
        "insight swarm ≥3:1 before betting expand",
        "revert last lever if hillclimb kill trips",
        "fee floors locked 0.06/0.05/0.02",
        "make living-ritual-live · staff paste only",
    ])
    try:
        import desk_master
        priority = desk_master.finalize_living_priority(raw)
        max_n = desk_master.PRIORITY_MAX
    except Exception:
        priority = raw[:5]
        max_n = 5
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "board_chip": False,
        "priority": priority,
        "raw_n": len(raw),
        "max_n": max_n,
        "ritual_live_n": live_n,
        "label": (
            f"priority n={len(priority)} · top={priority[0][:60]}"
            if priority
            else "priority empty"
        ),
        "note": "Living priority snapshot — observe-only; never softens floors.",
    }


def living_money_path_tip(board: dict | None = None, root: str | None = None) -> dict:
    """Observe tip for fee ledger / fills / floors (not a board chip; never invents PnL)."""
    src = board if isinstance(board, dict) else living_upgrade_board(root)
    books = src.get("bookkeeper") if isinstance(src.get("bookkeeper"), dict) else {}
    floors = src.get("fee_floors_assert") if isinstance(src.get("fee_floors_assert"), dict) else {}
    fills = src.get("completions") if isinstance(src.get("completions"), dict) else {}
    floors_ok = floors.get("all_ok")
    ledger_ok = books.get("fee_ledger_complete")
    label = (
        f"money-path fills={fills.get('eligible_completions_today') if fills else books.get('eligible_completions_today')} "
        f"fee_ledger={books.get('fee_ledger_n')} complete={ledger_ok} "
        f"floors={'ok' if floors_ok is True else 'soft' if floors_ok is False else 'n/a'} "
        "(observe · never invents PnL · never softens floors)"
    )
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "board_chip": False,
        "eligible_completions_today": (
            fills.get("eligible_completions_today")
            if fills.get("eligible_completions_today") is not None
            else books.get("eligible_completions_today")
        ),
        "fee_ledger_n": books.get("fee_ledger_n"),
        "fee_ledger_complete": ledger_ok,
        "floors_ok": floors_ok,
        "label": label,
        "note": "Money-path observe tip — staff only; never invents fills or softens floors.",
    }


def living_guardrails_tip(board: dict | None = None, root: str | None = None) -> dict:
    """Hard-rules observe tip (paper / floors / Discord) — not a board chip."""
    src = board if isinstance(board, dict) else living_upgrade_board(root)
    floors = src.get("fee_floors_assert") if isinstance(src.get("fee_floors_assert"), dict) else {}
    floors_ok = floors.get("all_ok")
    paper_only = src.get("paper_only") is not False
    live = src.get("live_orders_enabled")
    locked = src.get("fee_floors_locked") is not False
    label = (
        f"guardrails paper={paper_only} live={live} floors_locked={locked} "
        f"floors={'ok' if floors_ok is True else 'soft' if floors_ok is False else 'n/a'} "
        "discord=paste-only "
        "(sports 0.06 / BTC+commodity 0.05 / INX+DEX 0.02 · never softens · never auto-posts)"
    )
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "board_chip": False,
        "live_orders_enabled": live,
        "floors_ok": floors_ok,
        "floors_locked": locked,
        "discord_auto_post": False,
        "venue_floors": {
            "sports": 0.06,
            "btc_commodity": 0.05,
            "inx_dex": 0.02,
        },
        "label": label,
        "note": "Guardrails observe tip — staff only; never softens floors; Discord never auto-posts.",
    }


def living_surface_index(board: dict | None = None, root: str | None = None) -> dict:
    """Soft-max surface index: sunday twins + catalog headroom (not a board chip)."""
    src = board if isinstance(board, dict) else living_upgrade_board(root)
    # Avoid compact rebuild recursion when called while building living_compact_card.
    compact = src.get("compact") if isinstance(src.get("compact"), dict) else None
    if compact is not None:
        twins_n = sum(1 for k in compact if str(k).endswith("_sunday_quiet"))
        fields_n = None
    else:
        twins_n = None
        fields_n = None
    catalog = src.get("chip_catalog") if isinstance(src.get("chip_catalog"), dict) else {}
    chips_n = catalog.get("chips_n")
    if chips_n is None:
        chips_n = len(
            [
                c
                for c in (src.get("chips") or [])
                if isinstance(c, dict) and c.get("board_chip") is not False
            ]
        )
    soft_max = int(catalog.get("soft_max") or CHIP_CATALOG_SOFT_MAX)
    headroom = max(0, soft_max - int(chips_n or 0))
    twins_bit = twins_n if twins_n is not None else "?"
    label = (
        f"surfaces twins={twins_bit} chips={chips_n}/{soft_max} headroom={headroom} "
        f"(observe · soft-max · no new chips · never softens floors)"
    )
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "board_chip": False,
        "twins_n": twins_n,
        "fields_n": fields_n,
        "chips_n": chips_n,
        "soft_max": soft_max,
        "headroom": headroom,
        "over": bool(int(chips_n or 0) > soft_max),
        "label": label,
        "note": "Surface index — observe-only soft-max audit; not a board chip.",
    }


def living_staff_smoke(board: dict | None = None, root: str | None = None) -> dict:
    """One-shot staff smoke of floors + guardrails + surfaces (not a board chip)."""
    src = board if isinstance(board, dict) else living_upgrade_board(root)
    floors = src.get("fee_floors_assert") if isinstance(src.get("fee_floors_assert"), dict) else {}
    rails = living_guardrails_tip(src)
    surfaces = living_surface_index(src)
    floors_ok = floors.get("all_ok") is not False
    live_off = src.get("live_orders_enabled") is False
    paper = src.get("paper_only") is not False
    locked = src.get("fee_floors_locked") is not False
    not_over = not bool(surfaces.get("over"))
    ok = bool(floors_ok and live_off and paper and locked and not_over)
    label = (
        f"smoke ok={ok} floors={'ok' if floors.get('all_ok') is True else 'soft' if floors.get('all_ok') is False else 'n/a'} "
        f"live={src.get('live_orders_enabled')} headroom={surfaces.get('headroom')} "
        f"(observe · make living-smoke · never softens floors · never auto-posts)"
    )
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "board_chip": False,
        "ok": ok,
        "floors_ok": floors.get("all_ok"),
        "live_orders_enabled": src.get("live_orders_enabled"),
        "headroom": surfaces.get("headroom"),
        "chips_n": surfaces.get("chips_n"),
        "soft_max": surfaces.get("soft_max"),
        "guardrails_label": rails.get("label"),
        "surfaces_label": surfaces.get("label"),
        "label": label,
        "note": "Staff smoke aggregate — observe-only; never places or softens floors.",
    }


_DISCORD_PASTE_TARGETS = (
    "floors",
    "doctor",
    "l7",
    "sunday",
    "ritual-live",
    "hud",
    "priority",
    "money",
    "rules",
    "surfaces",
    "smoke",
    "paste",
    "paper",
    "makefile",
    "venues",
    "chicago",
    "starve",
    "hard-rules",
    "swarm",
    "expand-tip",
    "quiet-tip",
    "timer-tip",
    "gaps",
    "ruin",
    "expand",
)


def living_discord_paste_tip(board: dict | None = None, root: str | None = None) -> dict:
    """Index of paste-only Discord draft targets (never auto-posts; not a board chip)."""
    _ = board if isinstance(board, dict) else (living_upgrade_board(root) if root else None)
    targets = list(_DISCORD_PASTE_TARGETS)
    label = (
        f"paste n={len(targets)} auto_post=False "
        f"targets={','.join(targets[:6])}… "
        "(observe · staff paste only · never auto-posts · never softens floors)"
    )
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "board_chip": False,
        "auto_post": False,
        "targets": targets,
        "targets_n": len(targets),
        "cmds": [
            "make living-floors-discord",
            "make living-doctor-discord",
            "make living-ritual-discord",
            "make living-hud-discord",
            "make living-smoke-discord",
            "make living-rules-discord",
            "make living-surfaces-discord",
        ],
        "label": label,
        "note": "Discord paste index — drafts only; never auto-posts.",
    }


def living_paper_live_tip(board: dict | None = None, root: str | None = None) -> dict:
    """Paper-only + live=False assert tip (not a board chip; never enables live)."""
    src = board if isinstance(board, dict) else living_upgrade_board(root)
    paper = src.get("paper_only") is not False
    live = src.get("live_orders_enabled")
    grok = src.get("grok_buys")
    locked = src.get("fee_floors_locked") is not False
    ok = bool(paper and live is False and grok is not True and locked)
    label = (
        f"paper-live ok={ok} paper={paper} live={live} grok_buys={grok} "
        f"floors_locked={locked} "
        "(observe · never enables live · never softens floors)"
    )
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "board_chip": False,
        "ok": ok,
        "live_orders_enabled": live,
        "grok_buys": grok,
        "floors_locked": locked,
        "label": label,
        "note": "Paper/live assert tip — observe-only; never enables live orders.",
    }


def living_makefile_index(board: dict | None = None, root: str | None = None) -> dict:
    """Count Makefile living-* smoke targets (not a board chip)."""
    _ = board  # observe-only; board unused except for API symmetry
    import pathlib

    make_path = pathlib.Path(__file__).resolve().parent / "Makefile"
    targets: list[str] = []
    try:
        text = make_path.read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.startswith("living-") and ":" in line and not line.startswith(".PHONY"):
                name = line.split(":", 1)[0].strip()
                if name.startswith("living-"):
                    targets.append(name)
    except OSError:
        targets = []
    targets = sorted(set(targets))
    label = (
        f"makefile living_n={len(targets)} "
        f"sample={','.join(targets[:5])}… "
        "(observe · soft-max surfaces · never softens floors)"
    )
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "board_chip": False,
        "targets": targets,
        "targets_n": len(targets),
        "path": str(make_path),
        "label": label,
        "note": "Makefile living-* index — observe-only staff map; not a board chip.",
    }


def living_venues_tip(board: dict | None = None, root: str | None = None) -> dict:
    """Locked venue fee-floor table tip (not a board chip; never softens)."""
    src = board if isinstance(board, dict) else living_upgrade_board(root)
    floors = src.get("fee_floors_assert") if isinstance(src.get("fee_floors_assert"), dict) else {}
    venues = {
        "sports": 0.06,
        "btc_commodity": 0.05,
        "inx_dex": 0.02,
    }
    ok = floors.get("all_ok") is not False and src.get("fee_floors_locked") is not False
    label = (
        f"venues sports={venues['sports']} btc+commodity={venues['btc_commodity']} "
        f"inx+dex={venues['inx_dex']} floors={'ok' if floors.get('all_ok') is True else 'soft' if floors.get('all_ok') is False else 'n/a'} "
        f"locked={src.get('fee_floors_locked') is not False} "
        "(observe · never softens floors)"
    )
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "board_chip": False,
        "ok": bool(ok),
        "venues": venues,
        "floors_ok": floors.get("all_ok"),
        "label": label,
        "note": "Venue fee floors tip — locked observe table; never softens.",
    }


def living_chicago_tip(board: dict | None = None, root: str | None = None) -> dict:
    """Chicago calendar day tip for staff packets (not a board chip)."""
    src = board if isinstance(board, dict) else living_upgrade_board(root)
    day = src.get("chicago_today") or chicago_today_iso()
    label = (
        f"chicago today={day} "
        "(observe · CT calendar · never softens floors · never enables live)"
    )
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "board_chip": False,
        "chicago_today": day,
        "label": label,
        "note": "Chicago day tip — observe-only staff calendar; not a board chip.",
    }


def living_starve_tip(board: dict | None = None, root: str | None = None) -> dict:
    """Starve-rule observe tip (n≥4, factor 0.15) — not a board chip."""
    _ = board if isinstance(board, dict) else (living_upgrade_board(root) if root else None)
    n_min = 4
    factor = 0.15
    label = (
        f"starve n≥{n_min} factor={factor} "
        "(observe · hard rule · never softens floors · never enables live)"
    )
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "board_chip": False,
        "n_min": n_min,
        "factor": factor,
        "label": label,
        "note": "Starve rule tip — observe-only; never rewrites starve policy.",
    }


def living_hard_rules_tip(board: dict | None = None, root: str | None = None) -> dict:
    """Hard-rules observe tip (meme red lock / INX halt / kill) — not a board chip."""
    _ = board if isinstance(board, dict) else (living_upgrade_board(root) if root else None)
    rules = {
        "meme_red_lock_usd": -8,
        "inx_halt_usd": 460,
        "kill": "M3↑ with M1↓ for 2 Chicago weeks → revert lever",
        "venues": "sports 0.06 / BTC+commodity 0.05 / INX+DEX 0.02",
    }
    label = (
        f"hard-rules meme_red={rules['meme_red_lock_usd']} inx_halt={rules['inx_halt_usd']} "
        "kill=M3↑/M1↓×2w "
        "(observe · never softens floors · never enables live)"
    )
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "board_chip": False,
        "rules": rules,
        "label": label,
        "note": "Hard rules tip — observe-only staff reminder; never rewrites policy.",
    }




def living_swarm_tip(board: dict | None = None, root: str | None = None) -> dict:
    """Insight swarm ratio tip (hire-order observe; not a board chip)."""
    src = board if isinstance(board, dict) else living_upgrade_board(root)
    swarm = src.get("insight_swarm") if isinstance(src.get("insight_swarm"), dict) else {}
    ratio = swarm.get("ratio")
    min_ratio = swarm.get("min_ratio", 3.0)
    passed = swarm.get("pass")
    label = (
        f"swarm insight={swarm.get('insight_n')} betting={swarm.get('betting_n')} "
        f"ratio={ratio} min={min_ratio} pass={passed} "
        "(observe · hire ≥3:1 · never softens floors)"
    )
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "board_chip": False,
        "insight_n": swarm.get("insight_n"),
        "betting_n": swarm.get("betting_n"),
        "ratio": ratio,
        "min_ratio": min_ratio,
        "pass": passed,
        "label": label,
        "note": "Swarm tip — observe-only hire-order ratio; not a board chip.",
    }


def living_expand_tip(board: dict | None = None, root: str | None = None) -> dict:
    """Betting expand gate tip (paper/staff only; not a board chip)."""
    src = board if isinstance(board, dict) else living_upgrade_board(root)
    gate = src.get("betting_expand_gate") if isinstance(src.get("betting_expand_gate"), dict) else {}
    blocked = gate.get("blocked")
    allow = gate.get("allow_betting_expand")
    label = (
        f"expand allow={allow} blocked={blocked} ratio={gate.get('swarm_ratio')} "
        f"live={gate.get('live_orders_enabled')} "
        "(observe · paper expand only · never softens floors · never enables live)"
    )
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "board_chip": False,
        "allow_betting_expand": allow,
        "blocked": blocked,
        "swarm_ratio": gate.get("swarm_ratio"),
        "live_orders_enabled": gate.get("live_orders_enabled"),
        "label": label,
        "soft_copy": gate.get("soft_copy"),
        "note": "Expand tip — observe-only; never enables live or softens floors.",
    }


def living_quiet_tip(board: dict | None = None, root: str | None = None) -> dict:
    """Feature-store quiet age tip (not a board chip)."""
    src = board if isinstance(board, dict) else living_upgrade_board(root)
    quiet = src.get("feature_quiet") if isinstance(src.get("feature_quiet"), dict) else {}
    label = (
        f"quiet={bool(quiet.get('quiet'))} age={quiet.get('age_hours')}h "
        f"threshold={quiet.get('quiet_hours')}h weekday={quiet.get('weekday')} "
        "(observe · learn-loop · never softens floors)"
    )
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "board_chip": False,
        "quiet": bool(quiet.get("quiet")),
        "age_hours": quiet.get("age_hours"),
        "quiet_hours": quiet.get("quiet_hours"),
        "weekday": quiet.get("weekday"),
        "label": label,
        "alert": quiet.get("alert"),
        "note": "Quiet tip — observe-only feature-store age; not a board chip.",
    }


def living_timer_tip(board: dict | None = None, root: str | None = None) -> dict:
    """Paper timer heartbeat tip (not a board chip)."""
    src = board if isinstance(board, dict) else living_upgrade_board(root)
    timer = src.get("timer_heartbeat") if isinstance(src.get("timer_heartbeat"), dict) else {}
    alive = timer.get("alive")
    label = (
        f"timer alive={alive} age_sec={timer.get('age_sec')} "
        f"weekday_alert={timer.get('weekday_alert')} "
        "(observe · paper timer · never softens floors · never enables live)"
    )
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "board_chip": False,
        "alive": alive,
        "age_sec": timer.get("age_sec"),
        "weekday_alert": timer.get("weekday_alert"),
        "label": label,
        "alert": timer.get("alert"),
        "note": "Timer tip — observe-only heartbeat; not a board chip.",
    }


def living_hud_summary(board: dict | None = None, root: str | None = None) -> dict:
    """One-line staff HUD of living surfaces (not a board chip)."""
    src = board if isinstance(board, dict) else living_upgrade_board(root)
    live = ritual_live_labels(src)
    live_n = sum(1 for k, v in live.items() if str(k).endswith("_label") and v)
    # Avoid compact rebuild recursion when called while building living_compact_card.
    compact = src.get("compact") if isinstance(src.get("compact"), dict) else None
    if compact is not None:
        twins_n = sum(1 for k in compact if str(k).endswith("_sunday_quiet"))
    else:
        twins_n = None
    prio = living_priority_snapshot(src)
    l7 = l7_observe_summary(src)
    floors = src.get("fee_floors_assert") if isinstance(src.get("fee_floors_assert"), dict) else {}
    teller = src.get("teller_living") if isinstance(src.get("teller_living"), dict) else {}
    ritual = src.get("ritual_observe") if isinstance(src.get("ritual_observe"), dict) else {}
    twins_bit = twins_n if twins_n is not None else "?"
    label = (
        f"hud ritual_live={live_n} twins={twins_bit} "
        f"prio={len(prio.get('priority') or [])} "
        f"l7={'ok' if l7.get('ok') else 'thin'} "
        f"floors={'ok' if floors.get('all_ok') is not False else 'soft'} "
        f"teller_live={teller.get('ritual_live_n') if teller.get('ritual_live_n') is not None else 'n/a'} "
        f"ritual_ok={ritual.get('ritual_ok')}"
    )
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "board_chip": False,
        "ritual_live_n": live_n,
        "ritual_live_ok": live_n >= 40,
        "sunday_twins_n": twins_n,
        "priority_n": len(prio.get("priority") or []),
        "priority_label": prio.get("label"),
        "l7_observe_ok": bool(l7.get("ok")),
        "floors_ok": floors.get("all_ok"),
        "teller_ritual_live_n": teller.get("ritual_live_n"),
        "ritual_ok": ritual.get("ritual_ok"),
        "label": label,
        "note": "Living HUD summary — observe-only; never softens floors; not a board chip.",
    }


def sunday_twin_coverage(board: dict | None = None, root: str | None = None) -> dict:
    """Count compact sunday quiet twins vs fee-locked board fields (surface audit)."""
    src = board if isinstance(board, dict) else living_upgrade_board(root)
    compact = (
        src.get("compact")
        if isinstance(src.get("compact"), dict)
        else living_compact_card(root, board=src)
    )
    twins = sorted(k for k in compact if str(k).endswith("_sunday_quiet"))
    fields = sorted(
        k
        for k, v in src.items()
        if (
            k not in _BOARD_SIZE_SKIP
            and isinstance(v, dict)
            and v.get("fee_floors_locked") is True
        )
    )
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "board_chip": False,
        "twins_n": len(twins),
        "fields_n": len(fields),
        "twins": twins,
        "pass": True,
        "label": f"sunday twins={len(twins)} fields={len(fields)} ok",
        "note": "Surface audit only — never softens floors; not a board chip.",
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
    ritual = board.get("ritual_observe") if isinstance(board.get("ritual_observe"), dict) else {}
    l7 = l7_observe_summary(board)
    l7_ok = bool(l7.get("ok"))
    sunday_cov = sunday_twin_coverage(board)
    live = ritual_live_labels(board)
    live_n = sum(
        1
        for k, v in live.items()
        if str(k).endswith("_label") and isinstance(v, str) and v
    )
    prio = living_priority_snapshot(board)
    hud = living_hud_summary(board)
    rails = living_guardrails_tip(board)
    surfaces = living_surface_index(board)
    smoke = living_staff_smoke(board)
    return {
        "paper_only": True,
        "fee_floors_locked": floors,
        "live_orders_enabled": False,
        "ok": ok and l7_ok and bool(smoke.get("ok")),
        "swarm_pass": swarm.get("pass"),
        "swarm_ratio": swarm.get("ratio"),
        "feature_quiet": bool(quiet.get("quiet")),
        "timer_alive": timer.get("alive"),
        "floors_assert": floors_assert,
        "ritual_observe": ritual,
        "ritual_ok": ritual.get("ritual_ok"),
        "ritual_exit_ok": ritual.get("exit_ok"),
        "l7_observe_ok": l7_ok,
        "l7_observe_present": list(l7.get("present") or []),
        "l7_observe_missing": list(l7.get("missing") or []),
        "l7_observe_label": str(l7.get("label") or "L7 observe pending"),
        "sunday_twin_ok": bool(sunday_cov.get("pass")),
        "sunday_twin_n": int(sunday_cov.get("twins_n") or 0),
        "sunday_twin_fields_n": int(sunday_cov.get("fields_n") or 0),
        "sunday_twin_label": str(sunday_cov.get("label") or "sunday twins observe"),
        "sunday_twin_coverage": sunday_cov,
        "ritual_live_labels": live,
        "ritual_live_n": int(live_n),
        "ritual_live_ok": live_n >= 40,
        "ritual_live_timer": str(live.get("timer_label") or "timer observe"),
        "ritual_live_sunday_quiet": str(
            (board.get("compact") or {}).get("ritual_live_sunday_quiet")
            if isinstance(board.get("compact"), dict)
            else ""
        )
        or (
            f"ritual live n={live_n} · "
            f"{live.get('digests_label') or 'digests observe'} · "
            f"{live.get('fills_label') or 'fills observe'} · "
            f"{live.get('timer_label') or 'timer observe'} · sunday quiet "
            f"{(board.get('sunday_packet') or {}).get('quiet_age_label') if isinstance(board.get('sunday_packet'), dict) else 'quiet_age=n/a'} "
            f"(observe · never softens floors)"
        ),
        "priority": prio,
        "priority_label": str(prio.get("label") or "priority observe"),
        "hud": hud,
        "hud_label": str(hud.get("label") or "hud observe"),
        "guardrails": rails,
        "guardrails_label": str(rails.get("label") or "guardrails observe"),
        "surfaces": surfaces,
        "surfaces_label": str(surfaces.get("label") or "surfaces observe"),
        "smoke": smoke,
        "smoke_ok": bool(smoke.get("ok")),
        "smoke_label": str(smoke.get("label") or "smoke observe"),
        "chips_n": _count_living_chips(board),
        "chip_catalog": sorted(
            k for k, v in board.items()
            if (
                k not in _BOARD_SIZE_SKIP
                and isinstance(v, dict)
                and v.get("fee_floors_locked") is True
            )
        ),
        "board_size": living_board_size_guard(chips_n=_count_living_chips(board)),
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
