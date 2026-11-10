"""
E9 chaos drills (#968–979) — observe-only fail-closed pack.

Paper only. Fee floors locked. Never LIVE. Never force-arm. Never softens
venue min_edge. Never auto-applies hillclimb levers. Never invents fills.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Callable
from unittest import mock

LOCKED_FLOOR_EXPECT = {
    "kalshi_sports": 0.06,
    "kalshi_btc15m": 0.05,
    "kalshi_commodity15m": 0.05,
    "kalshi_inx": 0.02,
    "solana_dex": 0.02,
}


def _floors_ok() -> dict:
    import desk_profit
    floors = desk_profit.venue_floors_locked()
    locked = bool(floors.get("locked") and floors.get("all_ok"))
    soft = []
    for venue, floor in LOCKED_FLOOR_EXPECT.items():
        live = float(desk_profit.venue_min_edge(venue, {}))
        if live + 1e-12 < float(floor):
            soft.append({"venue": venue, "live": live, "floor": floor})
            locked = False
    return {
        "ok": locked,
        "fee_floors_locked": True,
        "softened": soft,
        "live_orders_enabled": False,
    }


def _row(drill_id: str, ok: bool, *, detail: str, evidence: dict | None = None) -> dict:
    return {
        "id": drill_id,
        "ok": bool(ok),
        "pass": bool(ok),
        "detail": str(detail)[:240],
        "evidence": evidence or {},
        "paper_only": True,
        "fee_floors_locked": True,
        "live_orders_enabled": False,
        "auto_apply": False,
        "force_arm": False,
    }


def drill_timer_dead(root: str | None = None) -> dict:
    """#968 — kill timer; ensure watchdog pages."""
    import desk_living
    import pimp_desk

    with tempfile.TemporaryDirectory() as tmp:
        # Missing heartbeat → not alive + alert text for weekday paging path.
        empty = desk_living.timer_heartbeat_chip(tmp)
        empty_ok = empty.get("alive") is False

        # Stale heartbeat → DEAD.
        stale_at = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        path = pimp_desk.heartbeat_path(tmp)
        os.makedirs(os.path.dirname(path) or tmp, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"at": stale_at}, handle)
        dead = desk_living.timer_heartbeat_chip(tmp)
        dead_ok = dead.get("alive") is False and "DEAD" in str(dead.get("label") or "")
        health = pimp_desk.timer_health(tmp)
        page_ok = health.get("alive") is False and bool(health.get("alert"))

    ok = empty_ok and dead_ok and page_ok
    return _row(
        "968_timer_dead",
        ok,
        detail="timer dead/missing pages via heartbeat chip + timer_health alert",
        evidence={
            "empty_alive": empty.get("alive"),
            "dead_label": dead.get("label"),
            "alert": health.get("alert"),
        },
    )


def drill_calendar_fail_closed(root: str | None = None) -> dict:
    """#969 — calendar CDN down; BTC fail-closed (no invent)."""
    import desk_more

    # Calendar-unavailable FP must not invent a real news blackout wipe of soft densify.
    soft = desk_more.is_near_miss(
        reasons=["calendar unavailable (fail-closed)"],
        p=0.78,
        edge=0.08,
        min_edge=0.05,
    )
    soft_ok = bool(soft.get("near_miss")) and soft.get("shadow_only") is True

    # Real news window stays hard (fail-closed for entries).
    hard = desk_more.is_near_miss(
        reasons=["news window blackout FOMC"],
        p=0.78,
        edge=0.08,
        min_edge=0.05,
    )
    hard_ok = hard.get("near_miss") is False

    # No invented fair required by the API.
    invent_ok = "fair" not in soft and "fair" not in hard
    ok = soft_ok and hard_ok and invent_ok
    return _row(
        "969_calendar_cdn",
        ok,
        detail="calendar unavailable stays fail-closed; real news stays hard; no invented fair",
        evidence={"soft": soft, "hard": hard},
    )


def drill_eia_energy_block(root: str | None = None) -> dict:
    """#970 — EIA print; energy blocked."""
    from helpers import eia_blackout

    now = datetime(2026, 11, 9, 18, 0, tzinfo=timezone.utc)
    events = [{"title": "EIA Crude Oil Inventories", "when": "2026-11-09T18:10:00+00:00"}]
    hits = eia_blackout.inventory_hits(events, now=now, window_min=45)
    blocked = eia_blackout.is_energy_series("KXNATGAS15M") and bool(hits)
    far = eia_blackout.inventory_hits(
        events,
        now=datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc),
        window_min=45,
    )
    ok = blocked and not far
    return _row(
        "970_eia_energy",
        ok,
        detail="EIA window blocks NatGas/oil; far events do not",
        evidence={"hits_n": len(hits), "far_n": len(far)},
    )


def drill_open_risk_firm_queue(root: str | None = None) -> dict:
    """#971 — desk open-risk full; firm queue defers correctly."""
    import desk_roi_plan

    with tempfile.TemporaryDirectory() as tmp:
        desk_roi_plan.offer_firm_candidates(
            tmp,
            [
                {
                    "bot": "btc15m",
                    "ticker": "KXBTC15M-T1",
                    "side": "yes",
                    "edge": 0.08,
                    "confidence": 0.7,
                    "depth": 20,
                    "stake_est": 25.0,
                },
                {
                    "bot": "commodity-15m",
                    "ticker": "KXTEST-T1",
                    "side": "yes",
                    "edge": 0.07,
                    "confidence": 0.6,
                    "depth": 10,
                    "stake_est": 20.0,
                },
            ],
        )
        card = desk_roi_plan.rebuild_firm_queue(
            tmp,
            remaining_risk=0.0,
            cfg={"max_open_risk": 100.0},
            bots=[
                {"id": "btc15m", "open_risk": 60.0, "history": []},
                {"id": "sports-gap", "open_risk": 50.0, "history": []},
            ],
            note="chaos open-risk full",
        )
        deferred_n = int(card.get("deferred_n") or 0)
        block = desk_roi_plan.firm_queue_blocks(tmp, "commodity-15m", "KXTEST-T1")
        headroom = desk_roi_plan.desk_open_risk_headroom(
            tmp,
            local_bot="commodity-15m",
            local_open_risk=10.0,
            max_open_risk=100.0,
            bots=[
                {"id": "btc15m", "open_risk": 60.0},
                {"id": "sports-gap", "open_risk": 50.0},
                {"id": "commodity-15m", "open_risk": 0.0},
            ],
        )
        full = float(headroom.get("remaining") or 0) <= 1e-9
        ok = deferred_n >= 1 and bool(block) and full
    return _row(
        "971_open_risk_queue",
        ok,
        detail="full desk open-risk defers firm-queue tickets",
        evidence={
            "deferred_n": deferred_n,
            "block": block or "",
            "remaining": headroom.get("remaining"),
        },
    )


def drill_meme_red_entries_off(root: str | None = None) -> dict:
    """#972 — meme red lock → entries off (stone −$5; plan −$8 still trips)."""
    import desk_master
    import desk_more

    rescue = desk_master.firm_roi_rescue(
        [{"id": "memecoin", "today": -8.0, "cash": 90.0, "realized": -8.0}],
    )
    flags = rescue.get("flags") or []
    hit = any(
        f.get("bot") == "memecoin" and f.get("action") == "entries_off"
        for f in flags if isinstance(f, dict)
    )
    shares = desk_more.effective_tower_shares(
        {}, meme_today=-8.0, today_by_bot={"memecoin": -8.0},
    )
    starved = float(shares.get("memecoin") or 1) <= float(desk_more.MEME_RED_SHARE) + 1e-9
    lock_ok = float(desk_more.MEME_RED_LOCK_USD) == 5.0
    ok = hit and starved and lock_ok
    return _row(
        "972_meme_red",
        ok,
        detail="meme today≤−$5 → entries_off + share starve (−$8 still trips)",
        evidence={
            "hit": hit,
            "meme_share": shares.get("memecoin"),
            "lock_usd": desk_more.MEME_RED_LOCK_USD,
        },
    )


def drill_inx_drawdown_halt(root: str | None = None) -> dict:
    """#973 — INX cash ≤$460 → entries off (no staff-clear here)."""
    import desk_master

    # Empty temp root so workspace tower configs cannot soft-clear the halt.
    with tempfile.TemporaryDirectory() as tmp:
        rescue = desk_master.firm_roi_rescue(
            [
                {"id": "kalshi-sp", "today": 0.0, "cash": 455.0, "realized": 0.0},
                {"id": "kalshi-sized", "today": 0.0, "cash": 450.0, "realized": 0.0},
            ],
            root=tmp,
            cfg={"staff_clear_drawdown_halt": False},
        )
        flags = [f for f in (rescue.get("flags") or []) if isinstance(f, dict)]
        hit = any(
            f.get("bot") in ("kalshi-sp", "kalshi-sized") and f.get("action") == "entries_off"
            for f in flags
        )
    return _row(
        "973_inx_halt",
        hit,
        detail="INX cash≤$460 → entries_off without staff clear",
        evidence={"flags": flags[:4]},
    )


def drill_sports_red_cap1(root: str | None = None) -> dict:
    """#974 — sports ≤−$10 → accurate_only_cap1 (max 1 buy style)."""
    import desk_master

    rescue = desk_master.firm_roi_rescue(
        [{"id": "sports-gap", "today": -12.0, "cash": 80.0, "realized": -12.0}],
    )
    flags = rescue.get("flags") or []
    hit = any(
        f.get("bot") == "sports-gap" and f.get("action") == "accurate_only_cap1"
        for f in flags if isinstance(f, dict)
    )
    return _row(
        "974_sports_red",
        hit,
        detail="sports red ≤−$10 → accurate_only_cap1",
        evidence={"flags": [f for f in flags if isinstance(f, dict)][:3]},
    )


def drill_profit_lock_half(root: str | None = None) -> dict:
    """#975 — profit-lock on → size_mult 0.5."""
    import desk_roi_plan

    with tempfile.TemporaryDirectory() as tmp:
        path = desk_roi_plan._path(desk_roi_plan.PROFIT_LOCK, tmp)
        week = desk_roi_plan._chicago_week_id()
        desk_roi_plan._save(path, {
            "paper_only": True,
            "target_usd": float(desk_roi_plan.PROFIT_LOCK_TARGET_USD),
            "latest": {
                "week": week,
                "week_pnl": 50.0,
                "target_usd": float(desk_roi_plan.PROFIT_LOCK_TARGET_USD),
                "safe_mode": True,
                "size_mult": float(desk_roi_plan.PROFIT_LOCK_SIZE_MULT),
                "fee_floors_locked": True,
            },
            "weeks": {
                week: {"week": week, "week_pnl": 50.0, "locked": True},
            },
        })
        status = desk_roi_plan.profit_lock_status(tmp)
        mult = desk_roi_plan.profit_lock_size_mult(tmp)
        ok = bool(status.get("safe_mode")) and abs(mult - 0.5) < 1e-9
    return _row(
        "975_profit_lock",
        ok,
        detail="profit-lock safe_mode → size_mult 0.5",
        evidence={"safe_mode": status.get("safe_mode"), "size_mult": mult},
    )


def drill_daily_r_settle_only(root: str | None = None) -> dict:
    """#976 — daily R hit → settle-only (commodity budget stays 2.0R)."""
    import desk_roi_plan

    msg = desk_roi_plan.daily_r_blocks("commodity-15m", 40.0)
    budget = desk_roi_plan.daily_r_budget_for("commodity-15m")
    ok = bool(msg) and "settle-only" in msg and abs(float(budget) - 2.0) < 1e-9
    return _row(
        "976_daily_r",
        ok,
        detail="daily R hit → settle-only; commodity budget 2.0R",
        evidence={"msg": msg, "commodity_budget_r": budget},
    )


def drill_hillclimb_kill_revert(root: str | None = None) -> dict:
    """#977 — hillclimb kill flag → staff revert path (never auto-apply)."""
    import desk_roi_plan

    with tempfile.TemporaryDirectory() as tmp:
        desk_roi_plan.staff_mark_sunday_packet_reviewed(tmp, who="chaos")
        pick = desk_roi_plan.staff_pick_hillclimb_lever(tmp, "VOL_SAFE", note="chaos")
        weeks = [
            {"label": "2026-11-01", "m1": 1.0, "m3": 0.2, "fills_n": 5, "lever": "VOL_SAFE"},
            {"label": "2026-11-08", "m1": 0.4, "m3": 0.5, "fills_n": 9, "lever": "VOL_SAFE"},
        ]
        status = desk_roi_plan.evaluate_hillclimb_kill(weeks)
        path = desk_roi_plan._path(desk_roi_plan.HILLCLIMB_KILL, tmp)
        desk_roi_plan._save(path, {
            "paper_only": True,
            "weeks": weeks,
            "status": status,
            "latest": weeks[-1],
        })
        ok_kill = bool(status.get("kill")) and status.get("auto_revert") is not True
        pm = desk_roi_plan.staff_hillclimb_kill_postmortem(
            tmp, who="chaos", note="chaos drill revert", demote=True,
        )
        ok = (
            bool(pick.get("ok"))
            and ok_kill
            and bool(pm.get("ok"))
            and desk_roi_plan.active_hillclimb_lever(tmp) is None
            and pm.get("auto_revert") is False
        )
    return _row(
        "977_hillclimb_kill",
        ok,
        detail="kill flag → postmortem demote; never auto-revert params",
        evidence={
            "kill": status.get("kill"),
            "demoted": (pm.get("row") or {}).get("demoted"),
            "pick_ok": pick.get("ok"),
        },
    )


def drill_ruin_nuclear(root: str | None = None) -> dict:
    """#978 — ruin nuclear; pause all / block entries."""
    import desk_roi_plan
    import pimp_desk

    with tempfile.TemporaryDirectory() as tmp:
        with mock.patch.object(pimp_desk, "set_pause", return_value={"ok": True}):
            out = desk_roi_plan.set_ruin_drill(tmp, "nuclear", who="chaos", note="chaos")
        st = desk_roi_plan.ruin_drill_status(tmp)
        block = desk_roi_plan.ruin_drill_blocks_entries(tmp)
        ok = (
            bool(out.get("ok"))
            and st.get("level") == "nuclear"
            and st.get("pause_all_bots") is True
            and st.get("block_entries") is True
            and bool(block)
            and st.get("live_orders_enabled") is not True
        )
        with mock.patch.object(pimp_desk, "set_pause", return_value={"ok": True}):
            desk_roi_plan.clear_ruin_drill(tmp, who="chaos", note="chaos clear")
    return _row(
        "978_ruin_nuclear",
        ok,
        detail="ruin nuclear blocks entries + pause_all; LIVE stays False",
        evidence={"block": block, "level": st.get("level")},
    )


def drill_post_chaos_floors(root: str | None = None) -> dict:
    """#979 — after chaos drills, floors never softened."""
    floors = _floors_ok()
    return _row(
        "979_floors_locked",
        bool(floors.get("ok")),
        detail="venue floors still locked post-chaos",
        evidence=floors,
    )


CHAOS_DRILLS: tuple[tuple[str, Callable[..., dict]], ...] = (
    ("968_timer_dead", drill_timer_dead),
    ("969_calendar_cdn", drill_calendar_fail_closed),
    ("970_eia_energy", drill_eia_energy_block),
    ("971_open_risk_queue", drill_open_risk_firm_queue),
    ("972_meme_red", drill_meme_red_entries_off),
    ("973_inx_halt", drill_inx_drawdown_halt),
    ("974_sports_red", drill_sports_red_cap1),
    ("975_profit_lock", drill_profit_lock_half),
    ("976_daily_r", drill_daily_r_settle_only),
    ("977_hillclimb_kill", drill_hillclimb_kill_revert),
    ("978_ruin_nuclear", drill_ruin_nuclear),
    ("979_floors_locked", drill_post_chaos_floors),
)


def run_chaos_drill_pack(root: str | None = None) -> dict:
    """Run all E9 chaos drills (#968–979). Observe-only; never LIVE."""
    rows = []
    for _id, fn in CHAOS_DRILLS:
        try:
            rows.append(fn(root))
        except Exception as exc:  # noqa: BLE001
            rows.append(_row(_id, False, detail=f"EXCEPTION {type(exc).__name__}: {exc}"))
    passed = sum(1 for r in rows if r.get("ok"))
    failed = [r["id"] for r in rows if not r.get("ok")]
    floors = _floors_ok()
    ok = passed == len(rows) and bool(floors.get("ok"))
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_apply": False,
        "auto_promote": False,
        "force_arm": False,
        "live_orders_enabled": False,
        "ok": ok,
        "pass": ok,
        "n": len(rows),
        "passed_n": passed,
        "failed": failed,
        "drills": rows,
        "floors": floors,
        "label": (
            f"chaos_drills ok={ok} passed={passed}/{len(rows)} "
            f"failed={failed or 'none'} (#968–979)"
        ),
        "note": (
            "E9 chaos drill pack — fail-closed observe. "
            "Never softens floors. Never LIVE. Never auto-applies levers."
        ),
    }


def chaos_drill_board(root: str | None = None) -> dict:
    """Masters/CLI observe wrapper — same pack, no tip invent."""
    return run_chaos_drill_pack(root)
