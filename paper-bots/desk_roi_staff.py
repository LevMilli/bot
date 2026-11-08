"""
desk_roi_staff.py — Staff SLA unblock pack (paper observe / no-force arm).

Never enables LIVE_ORDERS. Never auto-applies hillclimb levers.
Never invents tip chips. Fee floors stay locked. Discord never auto-posts.
"""
from __future__ import annotations

import csv
import io
from typing import Any, Callable

import desk_roi_plan as plan

PROMOTE_SLA_NAME = "desk_promote_gate_sla.json"
HILLCLIMB_PICK_JOURNAL = "desk_hillclimb_pick_journal.json"
MAX_HILLCLIMB_PICK_JOURNAL = 200

# Gate → exact no-force make target (observe/arm-ready only).
PROMOTE_READY_MAKE = {
    "near_miss": "make living-near-miss-promote-ready",
    "hard_stop": "make living-hard-stop-promote-ready",
    "green_boost": "make living-green-boost-arm-ready",
    "edge08": "make living-edge08-promote-ready",
    "helper_gate_a": "make living-helper-arm",
    "commodity_time_stop": "make living-commodity-tstop-promote-ready",
    "sports_time_final": "make living-sports-tfinal-promote-ready",
    "inx_band": "make living-inx-band-promote",
}


def _age_days(iso_at) -> float | None:
    raw = str(iso_at or "").strip()
    if not raw:
        return None
    try:
        from datetime import datetime, timezone
        stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return round(max(0.0, (now - stamp).total_seconds() / 86400.0), 3)
    except Exception:
        return None


def _n_ev_from_status(gate: str, st: dict) -> tuple[Any, Any]:
    """Best-effort (n, EV) for pack rows."""
    if gate == "near_miss":
        return st.get("labeled_n"), st.get("shadow_ev")
    if gate == "hard_stop":
        return st.get("n_with_pnl"), st.get("shadow_expectancy")
    if gate == "green_boost":
        return st.get("sports_m1_n"), st.get("sports_m1")
    if gate == "edge08":
        return st.get("n"), st.get("shadow_ev") or st.get("expectancy") or st.get("ev")
    if gate == "helper_gate_a":
        return st.get("ready_n"), None
    if gate in ("commodity_time_stop", "sports_time_final"):
        return st.get("n_with_pnl"), st.get("shadow_expectancy")
    if gate == "inx_band":
        return st.get("n") or st.get("leader_n"), st.get("leader_ev") or st.get("ev")
    return st.get("n"), st.get("shadow_ev") or st.get("shadow_expectancy")


# ---- TC-151 hillclimb pick evidence ----------------------------------------

def hillclimb_pick_evidence_pack(root: str | None = None) -> dict:
    """Evidence pack before staff picks one allowlisted lever.

    auto_pick=False forever. Never writes venue params. Floors locked.
    """
    status = plan.hillclimb_lever_status(root)
    kill = plan.hillclimb_kill_status(root)
    allow = plan.hillclimb_allowlist()
    weeks = [
        w for w in (
            plan._load(
                plan._path(plan.HILLCLIMB_KILL, root),
                {"paper_only": True, "weeks": []},
            ).get("weeks") or []
        )
        if isinstance(w, dict)
    ]
    weeks = sorted(weeks, key=lambda w: str(w.get("label") or ""))
    last_weeks = [
        {
            "label": w.get("label"),
            "m1": w.get("m1"),
            "m3": w.get("m3"),
            "fills_n": w.get("fills_n"),
            "lever": w.get("lever"),
        }
        for w in weeks[-2:]
    ]
    needs = bool(status.get("needs_staff_pick"))
    kill_flag = bool(status.get("kill") or kill.get("kill"))
    thin = needs or kill_flag
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "process_only": True,
        "ticket": "TC-151",
        "auto_pick": False,
        "auto_apply": False,
        "auto_promote": False,
        "live_orders_enabled": False,
        "allowlist": sorted(plan.HILLCLIMB_ALLOWLIST.keys()),
        "allowlist_detail": allow.get("levers"),
        "raise_only": [
            k for k, v in plan.HILLCLIMB_ALLOWLIST.items() if v.get("raise_only")
        ],
        "active": status.get("active"),
        "week": status.get("week"),
        "needs_staff_pick": needs,
        "kill": kill_flag,
        "kill_card": kill,
        "evidence_thin": thin,
        "label": (
            "THIN — needs_staff_pick"
            if needs and not kill_flag
            else (
                "THIN — hillclimb KILL (demote before next pick)"
                if kill_flag
                else status.get("label") or "hillclimb pick evidence"
            )
        ),
        "last_weeks_m1_m3": last_weeks,
        "cli": {
            "list": "python3 tools/staff_hillclimb_pick.py list",
            "status": "python3 tools/staff_hillclimb_pick.py status",
            "pack": "python3 tools/staff_hillclimb_pick.py pack",
            "pick": "python3 tools/staff_hillclimb_pick.py pick <lever> [--note ...]",
            "clear": "python3 tools/staff_hillclimb_pick.py clear",
            "log_accept": (
                "python3 tools/staff_hillclimb_pick.py log accept "
                "--lever <name> --before ... --after ..."
            ),
            "log_defer": (
                "python3 tools/staff_hillclimb_pick.py log defer "
                "--lever <name> --note ..."
            ),
            "make_pick": "make living-hillclimb-pick",
            "make_ready": "make living-hillclimb-pick-ready",
        },
        "note": (
            "TC-151 evidence pack — staff picks one allowlisted lever per Chicago week. "
            "Agent never auto-picks / auto-applies. Floors locked. LIVE off."
        ),
    }


def hillclimb_lever_journal(root: str | None = None, *, limit: int = 12) -> dict:
    """One-lever history card (week / lever / proposed / demote). Never auto-applies."""
    store = plan._load(
        plan._path(plan.HILLCLIMB_LEVER_NAME, root),
        {"paper_only": True, "active": None, "history": []},
    )
    hist = [h for h in (store.get("history") or []) if isinstance(h, dict)]
    tail = hist[-max(1, int(limit)):]
    rows = []
    for h in tail:
        rows.append({
            "week": h.get("week"),
            "lever": h.get("lever"),
            "proposed_value": h.get("proposed_value"),
            "demote_reason": h.get("demote_reason") or h.get("demote_note"),
            "demoted_at": h.get("demoted_at"),
            "at": h.get("at"),
            "note": h.get("note"),
            "raise_only": h.get("raise_only"),
        })
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "auto_promote": False,
        "auto_apply": False,
        "auto_pick": False,
        "active": store.get("active") if isinstance(store.get("active"), dict) else None,
        "n": len(hist),
        "rows": rows,
        "note": "Hillclimb lever journal — history only; no param write.",
    }


def staff_hillclimb_pick_journal(root: str | None = None) -> dict:
    """Staff accept|defer log for hillclimb picks (before/after note). auto_apply=False."""
    store = plan._load(
        plan._path(HILLCLIMB_PICK_JOURNAL, root),
        {"paper_only": True, "rows": [], "latest": None, "auto_apply": False},
    )
    rows = [r for r in (store.get("rows") or []) if isinstance(r, dict)]
    accepts = sum(1 for r in rows if r.get("decision") == "accept")
    defers = sum(1 for r in rows if r.get("decision") == "defer")
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "auto_apply": False,
        "auto_pick": False,
        "auto_promote": False,
        "live_orders_enabled": False,
        "n": len(rows),
        "accepts": accepts,
        "defers": defers,
        "latest": store.get("latest") if isinstance(store.get("latest"), dict) else None,
        "rows_tail": rows[-20:],
        "note": (
            "Staff hillclimb pick journal (accept|defer) with before/after notes. "
            "Never auto-applies lever params; floors locked."
        ),
    }


def staff_log_hillclimb_pick(
    root: str | None,
    decision: str,
    *,
    lever: str = "",
    who: str = "",
    note: str = "",
    before: str = "",
    after: str = "",
) -> dict:
    """Log accept|defer for a hillclimb pick. Never writes venue params."""
    dec = str(decision or "").strip().lower()
    if dec not in ("accept", "defer"):
        return {
            "ok": False,
            "reason": "decision must be accept|defer",
            "auto_apply": False,
            "fee_floors_locked": True,
        }
    row = {
        "paper_only": True,
        "at": plan._now(),
        "week": plan._chicago_week_id(),
        "decision": dec,
        "lever": str(lever or "")[:80],
        "who": str(who or "")[:40],
        "note": str(note or "")[:200],
        "before": str(before or "")[:200],
        "after": str(after or "")[:200],
        "auto_apply": False,
        "fee_floors_locked": True,
        "live_orders_enabled": False,
    }
    path = plan._path(HILLCLIMB_PICK_JOURNAL, root)
    store = plan._load(
        path,
        {"paper_only": True, "rows": [], "latest": None, "auto_apply": False},
    )
    rows = [r for r in (store.get("rows") or []) if isinstance(r, dict)]
    rows.append(row)
    store["rows"] = rows[-MAX_HILLCLIMB_PICK_JOURNAL:]
    store["latest"] = row
    store["auto_apply"] = False
    store["paper_only"] = True
    store["fee_floors_locked"] = True
    store["last_at"] = row["at"]
    plan._save(path, store)
    return {
        "ok": True,
        "row": row,
        "n": len(store["rows"]),
        "auto_apply": False,
        "auto_pick": False,
        "fee_floors_locked": True,
        "live_orders_enabled": False,
        "reason": f"logged {dec}",
    }


# ---- Promote-ready pack + safe batch ---------------------------------------

def staff_promote_ready_pack(
    root: str | None = None,
    *,
    bots: list | None = None,
) -> dict:
    """Unified promote-ready pack with exact make commands. Observe / no-force."""
    dist = plan.promote_distance_observe(root, bots=bots)
    sla = promote_gate_sla(root, bots=bots, refresh=True)
    sla_by = {
        str(r.get("gate")): r
        for r in (sla.get("gates") or [])
        if isinstance(r, dict)
    }
    # Per-gate status enrichments (n / EV).
    status_map = {
        "near_miss": plan.near_miss_promote_status(root),
        "hard_stop": plan.sports_hard_stop_shadow_summary(root),
        "green_boost": plan.sports_green_boost_status(root, bots=bots),
        "edge08": plan.btc_edge08_shadow_status(root),
        "helper_gate_a": plan.helper_promote_status(root),
        "commodity_time_stop": plan.commodity_time_stop_shadow_summary(root),
        "sports_time_final": plan.sports_time_final_shadow_summary(root),
        "inx_band": plan.inx_band_promote_status(root),
    }
    items = []
    for row in dist.get("gates") or []:
        if not isinstance(row, dict):
            continue
        gate = str(row.get("gate") or "")
        st = status_map.get(gate) or {}
        ready = bool(row.get("promote_ready"))
        thin = bool(row.get("evidence_thin"))
        n, ev = _n_ev_from_status(gate, st)
        age = sla_by.get(gate) or {}
        blocked_reason = None
        if not ready:
            blocked_reason = (
                st.get("reason")
                or st.get("label")
                or row.get("label")
                or "not promote_ready (need n≥30 EV≥0 or green weeks)"
            )
        items.append({
            "gate": gate,
            "n": n,
            "ev": ev,
            "ready": ready,
            "evidence_thin": thin,
            "n_to_promote": row.get("n_to_promote"),
            "make_command": PROMOTE_READY_MAKE.get(gate),
            "blocked_reason": blocked_reason,
            "force_forbidden_until_ready": True,
            "ready_age_days": age.get("ready_age_days"),
            "thin_age_days": age.get("thin_age_days"),
            "first_seen_ready_at": age.get("first_seen_ready_at"),
            "thin_since": age.get("thin_since"),
            "label": row.get("label") or st.get("label"),
        })
    ready_n = sum(1 for i in items if i.get("ready"))
    thin_n = sum(1 for i in items if i.get("evidence_thin"))
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "live_orders_enabled": bool(plan.LIVE_ORDERS_ENABLED),
        "force_default": False,
        "items": items,
        "gates": items,
        "ready_n": ready_n,
        "thin_n": thin_n,
        "sla": sla,
        "label": f"promote_ready_pack ready={ready_n}/{len(items)} thin={thin_n}",
        "discord_draft": _promote_pack_discord_draft(items),
        "auto_publish": False,
        "note": (
            "Staff promote-ready pack — paste make *-promote-ready when ready. "
            "force_forbidden_until_ready. Prefer living-staff-promote-batch-ready "
            "over STAFF FORCE living-staff-promote-batch. LIVE off; floors locked."
        ),
    }


def _promote_pack_discord_draft(items: list) -> str:
    lines = [
        "**Promote-ready pack** (paper · floors locked · never auto-posts)",
        "_draft only — Discord never auto-posts_",
        "",
    ]
    for it in items:
        mark = "READY" if it.get("ready") else "THIN"
        cmd = it.get("make_command") or "—"
        age = ""
        if it.get("ready") and it.get("ready_age_days") is not None:
            age = f" ready_age={it['ready_age_days']}d"
        elif (not it.get("ready")) and it.get("thin_age_days") is not None:
            age = f" thin_age={it['thin_age_days']}d"
        lines.append(
            f"- `{it.get('gate')}` **{mark}** n={it.get('n')} EV={it.get('ev')}"
            f"{age} → `{cmd}`"
        )
    lines.append("")
    lines.append("_force_forbidden_until_ready · LIVE_ORDERS_ENABLED=False_")
    return "\n".join(lines)


def _arm_near_miss_preferred(
    root: str | None,
    *,
    note: str,
    force: bool,
    bots: list | None,
) -> dict:
    """Arm soft-z|p matching evidence; never hardcode z when only soft-p is ready."""
    preferred = (plan.near_miss_preferred_first_soft(root) or {}).get("preferred")
    if not preferred:
        soft_p = plan.near_miss_soft_p_status(root, bots=bots) or {}
        if soft_p.get("soft_p_ready"):
            preferred = "p"
    if not preferred:
        return {
            "ok": False,
            "live": False,
            "reason": "no soft band promote-ready (need z|p n≥30 EV≥0)",
            "auto_promote": False,
            "fee_floors_locked": True,
        }
    return plan.staff_promote_near_miss_soft(
        root, str(preferred), note=note, force=force, bots=bots,
    )


def staff_batch_arm_promotes_ready(
    root: str | None = None,
    *,
    force: bool = False,
    note: str = "",
    bots: list | None = None,
    inx_band_id: str | None = None,
) -> dict:
    """Arm ONLY gates that already pass ready. force=False default.

    force=True is a labeled override request that still refuses soft floors and
    still refuses thin samples in this ready-batch path (use staff_batch_arm_promotes
    STAFF FORCE for the separate force batch). LIVE stays off.
    """
    note_s = str(note or "staff batch promote-ready")[:200]
    force_req = bool(force)
    # Ready-batch never passes force=True into arm helpers — thin stays blocked.
    arm_force = False
    floors_locked = True
    if not floors_locked:
        return {
            "ok": False,
            "armed": [],
            "blocked": [{"gate": "*", "reason": "floors not locked"}],
            "force": force_req,
            "force_applied": False,
            "fee_floors_locked": True,
            "live_orders_enabled": False,
            "auto_promote": False,
            "paper_only": True,
            "reason": "refuse — fee floors must stay locked",
        }

    attempts: list[tuple[str, Callable[[], dict]]] = [
        (
            "hard_stop",
            lambda: plan.staff_set_sports_hard_stop_live(
                root, True, note=note_s, force=arm_force,
            ),
        ),
        (
            "green_boost",
            lambda: plan.staff_set_sports_green_boost(
                root, True, note=note_s, force=arm_force, bots=bots,
            ),
        ),
        (
            "near_miss",
            lambda: _arm_near_miss_preferred(
                root, note=note_s, force=arm_force, bots=bots,
            ),
        ),
        (
            "edge08",
            lambda: plan.staff_promote_btc_edge08(
                root, who="staff-ready-batch", note=note_s, force=arm_force,
            ),
        ),
        (
            "commodity_time_stop",
            lambda: plan.staff_set_commodity_time_stop_live(
                root, True, note=note_s, force=arm_force,
            ),
        ),
        (
            "sports_time_final",
            lambda: plan.staff_set_sports_time_final_live(
                root, True, note=note_s, force=arm_force,
            ),
        ),
        (
            "inx_band",
            lambda: plan.staff_promote_inx_leader(
                root, note=note_s,
            )
            if not inx_band_id
            else plan.staff_promote_inx_band(
                root, inx_band_id, note=note_s, force=arm_force,
            ),
        ),
    ]
    # Helper: arm each ready helper (Gate A).
    helper_board = plan.helper_promote_status(root)
    for hrow in helper_board.get("helpers") or []:
        if not isinstance(hrow, dict):
            continue
        hid = str(hrow.get("helper") or "")
        if not hid:
            continue

        def _arm_helper(helper_id=hid):
            return plan.staff_set_helper_autonomy(
                root, helper_id, True, note=note_s, force=arm_force,
            )

        attempts.append((f"helper:{hid}", _arm_helper))

    armed = []
    blocked = []
    for gate, fn in attempts:
        try:
            out = fn()
        except Exception as exc:
            blocked.append({
                "gate": gate,
                "reason": f"error: {exc}",
                "ok": False,
                "force_requested": force_req,
            })
            continue
        if out.get("ok"):
            armed.append({
                "gate": gate,
                "ok": True,
                "reason": out.get("reason"),
                "result": out,
            })
        else:
            blocked.append({
                "gate": gate,
                "ok": False,
                "reason": out.get("reason") or "not promote_ready",
                "force_requested": force_req,
                "thin_refused": True,
                "result": {
                    k: out.get(k)
                    for k in (
                        "reason", "ok", "fee_floors_locked", "auto_promote",
                        "live", "staff_approved",
                    )
                    if k in out
                },
            })

    override_note = None
    if force_req:
        override_note = (
            "STAFF OVERRIDE REQUESTED (force=True) — ready-batch still refuses "
            "thin samples and never softens fee floors. Use "
            "make living-staff-promote-batch only as explicit STAFF FORCE path."
        )

    return {
        "paper_only": True,
        "ok": len(blocked) == 0 and len(armed) > 0,
        "armed": armed,
        "blocked": blocked,
        "armed_n": len(armed),
        "blocked_n": len(blocked),
        "force": force_req,
        "force_default": False,
        "force_applied": False,  # never force-arms thin in this path
        "override_note": override_note,
        "fee_floors_locked": True,
        "live_orders_enabled": bool(plan.LIVE_ORDERS_ENABLED),
        "auto_promote": False,
        "note": note_s,
        "label": (
            f"batch_ready armed={len(armed)} blocked={len(blocked)} "
            f"force_req={force_req}"
        ),
    }


def staff_disarm_thin_promotes(
    root: str | None = None,
    *,
    note: str = "",
    bots: list | None = None,
) -> dict:
    """Disarm staff promotes that are live/armed while evidence is still thin.

    Safety rollback for prior force-arms with n≪30 / not promote_ready.
    Never enables LIVE_ORDERS. Never softens floors. Never tip invent.
    """
    note_s = str(
        note
        or "disarm thin force-arms — need n≥30 EV≥0 before re-arm"
    )[:200]
    dist = plan.promote_distance_observe(root, bots=bots)
    by_gate = {
        str(r.get("gate")): r
        for r in (dist.get("gates") or [])
        if isinstance(r, dict)
    }
    cleared: list[dict] = []
    kept: list[dict] = []
    skipped: list[dict] = []

    def _thin(gate: str) -> bool:
        row = by_gate.get(gate) or {}
        if row.get("evidence_thin") is True:
            return True
        if row.get("promote_ready") is False and row.get("armed"):
            return True
        return False

    # hard_stop
    if plan.sports_hard_stop_is_live(root):
        if _thin("hard_stop") or not (
            by_gate.get("hard_stop") or {}
        ).get("promote_ready"):
            res = plan.staff_set_sports_hard_stop_live(
                root, False, note=note_s, force=False,
            )
            cleared.append({"gate": "hard_stop", "result": res})
        else:
            kept.append({"gate": "hard_stop", "reason": "promote_ready"})
    else:
        skipped.append({"gate": "hard_stop", "reason": "not_live"})

    # green_boost
    gb = plan.sports_green_boost_status(root, bots=bots)
    if bool(gb.get("staff_approved")) or bool(gb.get("live")):
        if _thin("green_boost") or not gb.get("ready"):
            res = plan.staff_set_sports_green_boost(
                root, False, note=note_s, force=False, bots=bots,
            )
            cleared.append({"gate": "green_boost", "result": res})
        else:
            kept.append({"gate": "green_boost", "reason": "ready"})
    else:
        skipped.append({"gate": "green_boost", "reason": "not_armed"})

    # near_miss soft
    nm = plan.near_miss_promote_status(root)
    if bool(nm.get("staff_approved")) or bool(nm.get("live")):
        if _thin("near_miss") or not nm.get("promote_ready"):
            res = plan.staff_clear_near_miss_promote(root, note=note_s)
            cleared.append({"gate": "near_miss", "result": res})
        else:
            kept.append({"gate": "near_miss", "reason": "promote_ready"})
    else:
        skipped.append({"gate": "near_miss", "reason": "not_armed"})

    # inx band
    inx = plan.inx_band_promote_status(root)
    inx_armed = bool(inx.get("staff_approved")) or bool(inx.get("live"))
    if inx_armed:
        # INX band promote without research / ready → clear
        ready_inx = bool((by_gate.get("inx_band") or {}).get("promote_ready"))
        if _thin("inx_band") or not ready_inx:
            res = plan.staff_clear_inx_band_promote(root, note=note_s)
            cleared.append({"gate": "inx_band", "result": res})
        else:
            kept.append({"gate": "inx_band", "reason": "promote_ready"})
    else:
        skipped.append({"gate": "inx_band", "reason": "not_armed"})

    # edge08 overlay promote is raise-only arm via pimp_desk — no thin disarm API here.
    skipped.append({
        "gate": "edge08",
        "reason": "no_thin_disarm_api (raise-only overlay; staff clears via pimp)",
    })

    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "live_orders_enabled": bool(plan.LIVE_ORDERS_ENABLED),
        "auto_promote": False,
        "force_default": False,
        "observe_only": False,
        "safety_rollback": True,
        "note": note_s,
        "cleared": cleared,
        "kept": kept,
        "skipped": skipped,
        "cleared_n": len(cleared),
        "kept_n": len(kept),
        "ok": True,
        "label": (
            f"disarm_thin cleared={len(cleared)} kept={len(kept)} "
            f"skipped={len(skipped)}"
        ),
    }


def export_near_miss_shadow_csv(
    root: str | None = None,
    *,
    path: str | None = None,
) -> dict:
    """Observe CSV of labeled near-miss shadow rows. Never arms."""
    rows = plan._near_miss_rows(root)
    summary = plan.near_miss_promote_status(root)
    fields = (
        "at", "ticker", "bot", "side", "soft", "z", "p", "edge",
        "ask", "entry_price", "league", "series",
        "would_pnl", "labeled_at", "note", "label_note",
    )
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        item = dict(row)
        if isinstance(item.get("soft"), list):
            item["soft"] = ",".join(str(x) for x in item["soft"])
        writer.writerow({k: item.get(k) for k in fields})
    text = buf.getvalue()
    out_path = path or plan._path("desk_near_miss_shadow.csv", root)
    try:
        with open(out_path, "w", encoding="utf-8") as handle:
            handle.write(text)
        wrote = True
    except OSError as exc:
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
        "note": "Near-miss shadow CSV — observe only; never arms soft gates.",
    }


def export_edge08_shadow_csv(
    root: str | None = None,
    *,
    path: str | None = None,
) -> dict:
    """Observe CSV summarizing edge08 shadow promote board. Never arms."""
    status = plan.btc_edge08_shadow_status(root)
    fields = (
        "bot", "variant_id", "n", "n_to_promote", "promote_ready",
        "evidence_thin", "shadow_ev", "ev", "expectancy", "label", "reason",
    )
    row = {k: status.get(k) for k in fields}
    # Prefer a single summary row; attach known numeric aliases.
    if row.get("shadow_ev") is None:
        row["shadow_ev"] = status.get("ev") or status.get("expectancy")
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerow(row)
    text = buf.getvalue()
    out_path = path or plan._path("desk_btc_edge08_shadow.csv", root)
    try:
        with open(out_path, "w", encoding="utf-8") as handle:
            handle.write(text)
        wrote = True
    except OSError as exc:
        return {
            "ok": False,
            "wrote": False,
            "path": None,
            "n": 1,
            "csv": text,
            "summary": status,
            "reason": f"write failed: {exc}",
            "paper_only": True,
            "auto_promote": False,
            "fee_floors_locked": True,
        }
    return {
        "ok": True,
        "wrote": wrote,
        "path": out_path,
        "n": 1,
        "csv": text,
        "summary": status,
        "paper_only": True,
        "auto_promote": False,
        "fee_floors_locked": True,
        "note": "Edge08 shadow CSV — observe only; never raises venue params here.",
    }


def export_green_boost_evidence(
    root: str | None = None,
    *,
    bots: list | None = None,
    path: str | None = None,
) -> dict:
    """Observe export of green_boost readiness evidence. Never arms."""
    status = plan.sports_green_boost_status(root, bots=bots)
    fields = (
        "ready", "evidence_thin", "sports_m1", "sports_m1_n", "clv_n",
        "clv_beat_rate", "weeks_n", "weeks_required", "weeks_ok", "clv_ok",
        "hist_ok", "staff_armed", "green_boost", "missing", "label",
    )
    row = {k: status.get(k) for k in fields}
    if isinstance(row.get("missing"), list):
        row["missing"] = ",".join(str(x) for x in row["missing"])
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerow(row)
    text = buf.getvalue()
    out_path = path or plan._path("desk_sports_green_boost_evidence.csv", root)
    try:
        with open(out_path, "w", encoding="utf-8") as handle:
            handle.write(text)
        wrote = True
    except OSError as exc:
        return {
            "ok": False,
            "wrote": False,
            "path": None,
            "csv": text,
            "summary": status,
            "reason": f"write failed: {exc}",
            "paper_only": True,
            "auto_promote": False,
            "fee_floors_locked": True,
        }
    return {
        "ok": True,
        "wrote": wrote,
        "path": out_path,
        "csv": text,
        "summary": status,
        "paper_only": True,
        "auto_promote": False,
        "fee_floors_locked": True,
        "note": "Green_boost evidence CSV — observe only; never arms selective +1.",
    }


# ---- Dual-control observe --------------------------------------------------

def dual_control_observe_board(root: str | None = None) -> dict:
    """Densified dual-control observe board. Never writes LIVE enable."""
    status = plan.dual_control_status(root)
    ruin = plan.ruin_drill_status(root)
    # Assert code lock — board must never flip this.
    live_flag = bool(plan.LIVE_ORDERS_ENABLED)
    assert live_flag is False  # hard invariant for this observe board
    items = status.get("items") if isinstance(status.get("items"), list) else []
    gaps = [
        {"id": it.get("id"), "label": it.get("label")}
        for it in items
        if isinstance(it, dict) and not it.get("signed")
    ]
    next_cmds = [
        "python3 tools/staff_dual_control.py status",
        "python3 tools/staff_dual_control.py items",
        "python3 tools/staff_dual_control.py sign --who <primary> --role primary --item <id>",
        "python3 tools/staff_dual_control.py sign --who <secondary> --role secondary",
        "make living-dual-control-status",
    ]
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "live_orders_enabled": False,
        "code_live_lock": True,
        "LIVE_ORDERS_ENABLED": False,
        "writes_live_enable": False,
        "signed_n": status.get("signed_n"),
        "items_n": status.get("items_n"),
        "two_staff": status.get("two_staff"),
        "checklist_complete": status.get("checklist_complete"),
        "arm_ready_paper": status.get("arm_ready_paper"),
        "primary": status.get("primary"),
        "secondary": status.get("secondary"),
        "items": items,
        "gaps": gaps,
        "gap_n": len(gaps),
        "ruin_practiced_this_month": bool(ruin.get("practiced_this_month")),
        "ruin": {
            "practiced_this_month": ruin.get("practiced_this_month"),
            "active": ruin.get("active"),
            "level": ruin.get("level"),
        },
        "next_staff_sign_commands": next_cmds,
        "label": (
            f"dual_control observe signed={status.get('signed_n')}/"
            f"{status.get('items_n')} two_staff={status.get('two_staff')} "
            f"gaps={len(gaps)} LIVE=False"
        ),
        "note": (
            "Dual-control observe board — checklist gaps + ruin practice. "
            "arm_ready_paper is NOT a live unlock. LIVE_ORDERS_ENABLED stays False."
        ),
    }


def densify_ops_dual_slice(ops: dict | None, root: str | None = None) -> dict:
    """Patch ops_observe dual_control projection onto real dual_control_status keys."""
    out = dict(ops or {})
    dual = plan.dual_control_status(root)
    board = dual_control_observe_board(root)
    out["dual_control"] = {
        "observe_only": True,
        "deferred": True,
        "live_orders_enabled": False,
        "signed_n": dual.get("signed_n"),
        "items_n": dual.get("items_n"),
        "two_staff": dual.get("two_staff"),
        "arm_ready_paper": dual.get("arm_ready_paper"),
        "checklist_complete": dual.get("checklist_complete"),
        "gaps": board.get("gaps"),
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
        },
        "observe_board": board,
        "note": "LIVE_ORDERS dual-control deferred — densified observe keys.",
    }
    return out


# ---- Observation week clocks + staff dashboard -----------------------------

def observation_week_clock(
    root: str | None = None,
    *,
    bots: list | None = None,
) -> dict:
    """Chicago observation-week clocks for M1 / graduation / meme / cold / kill."""
    week = plan._chicago_week_id()
    day = plan._chicago_day()
    days_into = None
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("America/Chicago"))
        days_into = int(now.isocalendar().weekday)  # Mon=1 … Sun=7
    except Exception:
        days_into = None
    m1 = plan.firm_taxed_m1(bots)
    green = plan.sports_green_boost_status(root, bots=bots)
    grad = plan.graduation_board(root, bots=bots)
    meme_bot = None
    for b in bots or []:
        if isinstance(b, dict) and str(b.get("id") or "") == "memecoin":
            meme_bot = b
            break
    meme = plan.meme_retirement_clock(meme_bot)
    cold = plan.cold_harvest_status(root)
    hill = plan.hillclimb_lever_status(root)
    kill = plan.hillclimb_kill_status(root)
    weeks_to_green = None
    if not green.get("ready"):
        have = int(green.get("weeks_n") or 0)
        need = int(green.get("weeks_required") or 2)
        weeks_to_green = max(0, need - have)
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "live_orders_enabled": False,
        "chicago_week": week,
        "chicago_day": day,
        "days_into_week": days_into,
        "firm_taxed_m1": {
            "n": m1.get("n"),
            "expectancy_taxed": m1.get("expectancy_taxed"),
            "by_tower": m1.get("by_tower"),
        },
        "green_boost": {
            "ready": green.get("ready"),
            "missing": green.get("missing"),
            "weeks_n": green.get("weeks_n"),
            "weeks_required": green.get("weeks_required"),
            "weeks_to_ready": weeks_to_green,
            "label": green.get("label"),
        },
        "graduation": {
            "masters_n": grad.get("masters_n"),
            "masters": grad.get("masters"),
            "weeks_required": grad.get("weeks_required"),
            "denial_codes": grad.get("denial_codes"),
            "towers": {
                k: {
                    "status": v.get("status"),
                    "consecutive_all_pass_weeks": v.get("consecutive_all_pass_weeks"),
                    "denial_codes": v.get("denial_codes"),
                }
                for k, v in (grad.get("towers") or {}).items()
                if isinstance(v, dict)
            },
        },
        "meme_retirement": meme,
        "cold_harvest": {
            "cold_total": cold.get("cold_total"),
            "weeks_n": cold.get("weeks_n"),
            "latest": cold.get("latest"),
        },
        "hillclimb": {
            "needs_staff_pick": hill.get("needs_staff_pick"),
            "kill": hill.get("kill"),
            "week": hill.get("week"),
            "active": hill.get("active"),
            "kill_window": kill.get("status"),
            "label": hill.get("label"),
        },
        "label": (
            f"obs_week={week} day={day} m1={m1.get('expectancy_taxed')} "
            f"green_to_ready={weeks_to_green} "
            f"hill={'needs_staff_pick' if hill.get('needs_staff_pick') else 'ok'}"
        ),
        "note": (
            "Observation-week clock — M1 hold, graduation streaks, meme retirement, "
            "cold harvest, hillclimb kill / needs_staff_pick. Floors locked; LIVE off."
        ),
    }


def promote_gate_sla(
    root: str | None = None,
    *,
    bots: list | None = None,
    refresh: bool = True,
) -> dict:
    """Persist first_seen_ready_at / thin_since; surface ready-but-unarmed vs thin ages."""
    path = plan._path(PROMOTE_SLA_NAME, root)
    store = plan._load(
        path,
        {"paper_only": True, "gates": {}, "fee_floors_locked": True},
    )
    gates_state = store.get("gates") if isinstance(store.get("gates"), dict) else {}
    dist = plan.promote_distance_observe(root, bots=bots)
    now = plan._now()
    out_rows = []
    if refresh:
        for row in dist.get("gates") or []:
            if not isinstance(row, dict):
                continue
            gate = str(row.get("gate") or "")
            if not gate:
                continue
            prev = gates_state.get(gate) if isinstance(gates_state.get(gate), dict) else {}
            ready = bool(row.get("promote_ready"))
            thin = bool(row.get("evidence_thin"))
            # Armed? best-effort from promote artifacts when known.
            armed = False
            if gate == "hard_stop":
                armed = plan.sports_hard_stop_is_live(root)
            elif gate == "near_miss":
                armed = plan.near_miss_soft_live(root) is not None
            elif gate == "near_miss_soft_p":
                armed = plan.near_miss_soft_live(root) == "p"
            elif gate == "green_boost":
                armed = bool(plan.sports_green_boost_status(root, bots=bots).get("staff_armed"))
            elif gate == "commodity_time_stop":
                armed = plan.commodity_time_stop_is_live(root)
            elif gate == "sports_time_final":
                armed = plan.sports_time_final_is_live(root)
            elif gate == "helper_gate_a":
                # Any helper with staff autonomy already armed.
                try:
                    board = plan.helper_promote_status(root)
                    helpers = board.get("helpers") or board.get("board") or []
                    if isinstance(helpers, list):
                        armed = any(bool(h.get("armed")) for h in helpers if isinstance(h, dict))
                    elif isinstance(helpers, dict):
                        armed = any(
                            bool(h.get("armed"))
                            for h in helpers.values()
                            if isinstance(h, dict)
                        )
                except Exception:
                    armed = False
            elif gate == "inx_band":
                try:
                    armed = bool(plan.inx_band_promote_status(root).get("staff_approved"))
                except Exception:
                    armed = False
            elif gate == "edge08":
                # Staff promote stamps pimp-bot-params.json overlay.
                try:
                    import pimp_desk
                    path = pimp_desk._under(pimp_desk._root(root), "pimp-bot-params.json")
                    overlay = pimp_desk._read_json(path) or {}
                    if not isinstance(overlay, dict):
                        overlay = {}
                    bot = overlay.get("btc15m") if isinstance(overlay.get("btc15m"), dict) else {}
                    armed = (
                        str(bot.get("promoted_from_shadow") or "") == "edge08"
                        or float(bot.get("venue_edge") or 0) + 1e-12 >= 0.08
                    )
                except Exception:
                    armed = False
            first_ready = prev.get("first_seen_ready_at")
            thin_since = prev.get("thin_since")
            if ready and not first_ready:
                first_ready = now
            if not ready:
                first_ready = None  # reset when no longer ready
            if thin and not thin_since:
                thin_since = now
            if not thin:
                thin_since = None
            entry = {
                "gate": gate,
                "ready": ready,
                "evidence_thin": thin,
                "armed": armed,
                "first_seen_ready_at": first_ready,
                "thin_since": thin_since,
                "ready_but_unarmed": bool(ready and not armed),
                "updated_at": now,
            }
            gates_state[gate] = entry
        store["gates"] = gates_state
        store["paper_only"] = True
        store["fee_floors_locked"] = True
        store["auto_promote"] = False
        store["last_at"] = now
        plan._save(path, store)

    for gate, entry in sorted(gates_state.items()):
        if not isinstance(entry, dict):
            continue
        ready_age = (
            _age_days(entry.get("first_seen_ready_at"))
            if entry.get("ready_but_unarmed") or entry.get("ready")
            else None
        )
        thin_age = _age_days(entry.get("thin_since")) if entry.get("evidence_thin") else None
        out_rows.append({
            **entry,
            "ready_age_days": ready_age,
            "thin_age_days": thin_age,
        })
    ready_unarmed = [r for r in out_rows if r.get("ready_but_unarmed")]
    thin_rows = [r for r in out_rows if r.get("evidence_thin")]
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "live_orders_enabled": False,
        "gates": out_rows,
        "ready_but_unarmed_n": len(ready_unarmed),
        "thin_n": len(thin_rows),
        "label": (
            f"promote_sla ready_unarmed={len(ready_unarmed)} thin={len(thin_rows)}"
        ),
        "note": (
            "Promote-gate SLA ages — ready-but-unarmed vs thin. Never auto-arms."
        ),
    }


def staff_dashboard(
    root: str | None = None,
    *,
    bots: list | None = None,
) -> dict:
    """One paste: observation clock + promote pack + hillclimb + dual + floors."""
    obs = observation_week_clock(root, bots=bots)
    promote = staff_promote_ready_pack(root, bots=bots)
    hill = hillclimb_pick_evidence_pack(root)
    dual = dual_control_observe_board(root)
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "auto_apply": False,
        "auto_pick": False,
        "live_orders_enabled": bool(plan.LIVE_ORDERS_ENABLED),
        "LIVE_ORDERS_ENABLED": False,
        "force_default": False,
        "tip_invent": False,
        "observation_week_clock": obs,
        "promote_ready_pack": promote,
        "hillclimb_pick_evidence": hill,
        "dual_control_observe": dual,
        "promote_gate_sla": promote.get("sla"),
        "floors_locked": True,
        "label": (
            f"staff_dashboard obs={obs.get('chicago_week')} "
            f"promote_ready={promote.get('ready_n')} "
            f"hill={'needs_staff_pick' if hill.get('needs_staff_pick') else 'ok'} "
            f"dual_gaps={dual.get('gap_n')} LIVE=False"
        ),
        "note": (
            "Staff SLA dashboard — observe packs only. Never LIVE. Never force-default. "
            "Never tip invent. Never auto-apply hillclimb."
        ),
    }
