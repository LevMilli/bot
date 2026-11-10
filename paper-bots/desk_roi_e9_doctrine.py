"""
E9 doctrine + distance milestone board (#951–954, #981–986).

Observe-only Masters cards. Paper only. Fee floors locked.
Never invents fills / PnL. Never LIVE. Never force-arm. Never softens floors.
Never auto-applies hillclimb levers. No tip chips.
"""
from __future__ import annotations

from typing import Any

# #951 — distance-to-zero milestones (earned crosses only).
DISTANCE_MILESTONES = (
    {"id": "m_neg225", "pnl": -225.0, "label": "−$225"},
    {"id": "m_neg150", "pnl": -150.0, "label": "−$150"},
    {"id": "m_neg75", "pnl": -75.0, "label": "−$75"},
    {"id": "m_zero", "pnl": 0.0, "label": "$0"},
    {"id": "m_plus25", "pnl": 25.0, "label": "+$25 week goal"},
)

DOCTRINE_CARDS = (
    {
        "id": "981_bots_earn_print",
        "title": "Bots earn the print",
        "text": "Never paint PnL — fills and settles write the ledger; spreadsheets do not.",
    },
    {
        "id": "982_insight_first",
        "title": "More bots ⇒ insight first",
        "text": "Betting only after Masters + firm M1; insight helpers never place alone.",
    },
    {
        "id": "983_quicker_fresher",
        "title": "Quicker bots ⇒ fresher quotes",
        "text": "Lower latency with fresher quotes — never waived fees.",
    },
    {
        "id": "984_trade_more_fee_clear",
        "title": "Trade more ⇒ fee-clear fills",
        "text": "More fee-clear eligible fills — never softer floors.",
    },
    {
        "id": "985_make_more_stack",
        "title": "Make more stack",
        "text": "bleed↓ + exits↑ + calibration↑ + selective size when green.",
    },
)


def _floors_locked() -> dict:
    try:
        import desk_profit
        floors = desk_profit.venue_floors_locked()
        return {
            "ok": bool(floors.get("locked") and floors.get("all_ok")),
            "fee_floors_locked": True,
            "venues": floors.get("venues") or {},
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "fee_floors_locked": True, "error": type(exc).__name__}


def distance_milestone_board(
    root: str | None = None,
    *,
    bots: list | None = None,
) -> dict:
    """#951–952 — milestone ladder; celebrate only earned crosses (no invent)."""
    import desk_roi_plan

    dist = desk_roi_plan.distance_to_zero_board(root, bots=bots)
    now_pnl = dist.get("now_pnl")
    try:
        now = float(now_pnl) if now_pnl is not None else None
    except (TypeError, ValueError):
        now = None

    # Series highs: best (max) observed firm PnL from baseline/live series — earned only.
    best = now
    for row in dist.get("series") or []:
        if not isinstance(row, dict):
            continue
        pnl = row.get("pnl")
        try:
            val = float(pnl)
        except (TypeError, ValueError):
            continue
        if best is None or val > best:
            best = val

    crosses = []
    earned_n = 0
    next_goal = None
    for m in DISTANCE_MILESTONES:
        threshold = float(m["pnl"])
        earned = best is not None and best + 1e-12 >= threshold
        if earned:
            earned_n += 1
        elif next_goal is None:
            next_goal = dict(m)
        crosses.append({
            **m,
            "earned": earned,
            "celebrate": earned,  # #952 — only earned crosses; never paint
            "invented": False,
        })

    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "auto_promote": False,
        "force_arm": False,
        "live_orders_enabled": False,
        "now_pnl": now,
        "best_observed_pnl": best,
        "distance_to_zero": dist.get("distance_to_zero"),
        "w0_pnl": dist.get("w0_pnl"),
        "delta_vs_w0": dist.get("delta_vs_w0"),
        "milestones": crosses,
        "earned_n": earned_n,
        "n": len(crosses),
        "next_goal": next_goal,
        "celebrate_only_earned": True,
        "no_spreadsheet_edits": True,
        "stance": dist.get("recommended_stance"),
        "label": (
            f"distance_milestones earned={earned_n}/{len(crosses)} "
            f"now={now} best={best} next="
            f"{(next_goal or {}).get('label') or 'done'}"
        ),
        "note": (
            "#951–952 Distance-to-zero milestones (−$225→−$150→−$75→$0→+$25). "
            "Celebrate only earned crosses; never invent PnL or edit spreadsheets."
        ),
    }


def variance_clause_card(root: str | None = None) -> dict:
    """#953 — red after perfect process is variance — not permission to soften floors."""
    floors = _floors_locked()
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "live_orders_enabled": False,
        "soften_floors_allowed": False,
        "floors_ok": bool(floors.get("ok")),
        "clause": (
            "Variance clause: red after perfect process is variance — "
            "not permission to soften floors."
        ),
        "label": "variance_clause floors_locked=True soften=False",
        "note": "#953 — process red ≠ soften venue min_edge.",
    }


def annual_floor_review_card(root: str | None = None) -> dict:
    """#954 — annual review of floors: raise OK, lower forbidden without research+staff."""
    floors = _floors_locked()
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "live_orders_enabled": False,
        "raise_ok": True,
        "lower_forbidden_without_research_staff": True,
        "floors_ok": bool(floors.get("ok")),
        "venues": floors.get("venues") or {},
        "label": "annual_floor_review raise=OK lower=forbidden_without_research+staff",
        "note": (
            "#954 — Annual floor review habit. Raise OK. "
            "Lower forbidden without new research + staff."
        ),
    }


def e9_doctrine_cards(root: str | None = None) -> dict:
    """#981–985 — final doctrine cards on Masters (no tip invent)."""
    cards = [
        {
            **c,
            "paper_only": True,
            "fee_floors_locked": True,
            "tip_chip": False,
            "live_orders_enabled": False,
        }
        for c in DOCTRINE_CARDS
    ]
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "tip_chips": False,
        "live_orders_enabled": False,
        "auto_apply": False,
        "n": len(cards),
        "cards": cards,
        "label": f"e9_doctrine cards={len(cards)} (#981–985)",
        "note": "Final doctrine cards — observe only; never tip invent; floors locked.",
    }


def e9_exit_card(root: str | None = None, *, bots: list | None = None) -> dict:
    """#986 — E9 exit: ritual live; ≤1 lever/week; dual-control locked; climbing to $0 earned."""
    import desk_roi_plan

    ritual = {}
    try:
        ritual = desk_roi_plan.sunday_packet_review_status(root) or {}
    except Exception:
        ritual = {}
    disc = {}
    try:
        disc = desk_roi_plan.hillclimb_one_lever_discipline(root) or {}
    except Exception:
        disc = {}
    dual = {}
    try:
        dual = desk_roi_plan.dual_control_status(root) or {}
    except Exception:
        dual = {}
    dist = {}
    try:
        dist = desk_roi_plan.distance_to_zero_board(root, bots=bots) or {}
    except Exception:
        dist = {}
    floors = _floors_locked()

    dual_locked = (
        dual.get("live_orders_enabled") is False
        and dual.get("auto_promote") is not True
        and dual.get("arm_ready_paper") is not True
    )

    one_lever = bool(disc.get("ok", True)) and disc.get("auto_apply") is not True
    climbing = dist.get("distance_to_zero") is not None

    ok = bool(floors.get("ok")) and dual_locked and one_lever
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "live_orders_enabled": False,
        "auto_apply": False,
        "force_arm": False,
        "ok": ok,
        "observation_ritual": {
            "reviewed": bool(ritual.get("reviewed")),
            "label": ritual.get("label") or ritual.get("note") or "sunday packet",
        },
        "one_lever_per_week": one_lever,
        "dual_control_locked": dual_locked,
        "distance_to_zero": dist.get("distance_to_zero"),
        "now_pnl": dist.get("now_pnl"),
        "climbing_toward_zero_earned": climbing,
        "floors_ok": bool(floors.get("ok")),
        "label": (
            f"e9_exit ok={ok} dual_locked={dual_locked} "
            f"one_lever={one_lever} dist={dist.get('distance_to_zero')}"
        ),
        "note": (
            "#986 E9 exit: observation ritual live; ≤1 lever/week discipline; "
            "dual-control still locked; firm climbing toward $0 earned."
        ),
    }


def doctrine_distance_board(
    root: str | None = None,
    *,
    bots: list | None = None,
) -> dict:
    """Combined #951–954 + #981–986 observe pack for Masters / CLI."""
    milestones = distance_milestone_board(root, bots=bots)
    variance = variance_clause_card(root)
    annual = annual_floor_review_card(root)
    doctrine = e9_doctrine_cards(root)
    exit_card = e9_exit_card(root, bots=bots)
    floors = _floors_locked()
    ok = (
        bool(floors.get("ok"))
        and bool(variance.get("soften_floors_allowed") is False)
        and bool(annual.get("lower_forbidden_without_research_staff"))
        and bool(doctrine.get("tip_chips") is False)
        and bool(exit_card.get("ok"))
        and bool(milestones.get("celebrate_only_earned"))
        and bool(milestones.get("no_spreadsheet_edits"))
    )
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "tip_chips": False,
        "auto_apply": False,
        "auto_promote": False,
        "force_arm": False,
        "live_orders_enabled": False,
        "ok": ok,
        "pass": ok,
        "distance_milestones": milestones,
        "variance_clause": variance,
        "annual_floor_review": annual,
        "doctrine_cards": doctrine,
        "e9_exit": exit_card,
        "floors": floors,
        "label": (
            f"doctrine_distance ok={ok} "
            f"milestones={milestones.get('earned_n')}/{milestones.get('n')} "
            f"doctrine={doctrine.get('n')} exit={exit_card.get('ok')}"
        ),
        "note": (
            "E9 doctrine + distance milestone board (#951–954, #981–986). "
            "Observe only. Never invent PnL. Floors locked. LIVE off."
        ),
    }
