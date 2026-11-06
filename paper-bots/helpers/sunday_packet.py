"""
Sunday living packet — observe-only staff draft from living board + scorecard.

Never auto-publishes. Never paints PnL. Never softens venue floors.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from helpers import HELPER_ONLY, PAPER_ONLY, assert_helper_only

PACKET_NAME = "sunday_living_packet.json"
DESK_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def packet_path(root: str | None = None) -> str:
    return os.path.join(root or DESK_ROOT, "helpers", PACKET_NAME)


def build_packet(root: str | None = None, *, now: datetime | None = None) -> dict:
    assert_helper_only("sunday_packet")
    assert PAPER_ONLY and HELPER_ONLY
    now = now or datetime.now(timezone.utc)
    living = {}
    scorecard = {}
    try:
        import desk_living
        living = desk_living.living_upgrade_board(root) or {}
    except Exception:
        living = {}
    try:
        import desk_roi_plan
        scorecard = desk_roi_plan.latest_weekly_scorecard(root) or {}
    except Exception:
        scorecard = {}
    swarm = living.get("insight_swarm") if isinstance(living.get("insight_swarm"), dict) else {}
    ai = living.get("living_ai") if isinstance(living.get("living_ai"), dict) else {}
    comp = living.get("completions") if isinstance(living.get("completions"), dict) else {}
    quiet = living.get("feature_quiet") if isinstance(living.get("feature_quiet"), dict) else {}
    dual = living.get("dual_control") if isinstance(living.get("dual_control"), dict) else {}
    ruin = living.get("ruin_drill") if isinstance(living.get("ruin_drill"), dict) else {}
    doctor_age = living.get("doctor_age") if isinstance(living.get("doctor_age"), dict) else {}
    return {
        "helper": "sunday_packet",
        "at": now.isoformat(),
        "paper_only": True,
        "may_place_alone": False,
        "floors_locked": True,
        "auto_publish": False,
        "live_orders_enabled": False,
        "chicago_today": living.get("chicago_today"),
        "scorecard_label": (
            scorecard.get("label") or scorecard.get("chicago_week") or scorecard.get("week")
        ),
        "scorecard_present": bool(scorecard),
        "insight_swarm": {
            "pass": swarm.get("pass"),
            "ratio": swarm.get("ratio"),
            "insight_n": swarm.get("insight_n"),
            "betting_n": swarm.get("betting_n"),
        },
        "living_ai": {
            "raise_phi_n": ai.get("raise_phi_n"),
            "raise_phi_tickets": ai.get("raise_phi_tickets") or [],
            "auto_write_phi": False,
        },
        "completions": {
            "eligible_completions_today": comp.get("eligible_completions_today"),
            "eligible_pnl_today": comp.get("eligible_pnl_today"),
        },
        "feature_quiet": {
            "quiet": quiet.get("quiet"),
            "alert": quiet.get("alert") or "",
        },
        "dual_control": {
            "signed_n": dual.get("signed_n"),
            "items_n": dual.get("items_n"),
            "arm_ready_paper": dual.get("arm_ready_paper"),
            "live_orders_enabled": False,
        },
        "ruin_drill": {
            "practiced_this_month": ruin.get("practiced_this_month"),
            "active": ruin.get("active"),
        },
        "doctor_age": {
            "stale": doctor_age.get("stale"),
            "age_sec": doctor_age.get("age_sec"),
            "label": doctor_age.get("label"),
        },
        "ritual": {
            "cli": "python3 tools/staff_living_ritual.py --discord",
            "make": "make living-ritual-discord",
            "auto_publish": False,
        },
        "staff_checklist": [
            "Confirm venue floors still locked (0.06/0.05/0.02)",
            "Review raise_Φ tickets — staff dual-control only",
            "Review Completions vs firm M1 (never optimize raw buys)",
            "Insight swarm ≥3:1 before betting expand",
            "Ruin drill soft/hard practiced this Chicago month",
            "One hillclimb lever max this week if allowlisted",
            "Run weekly living ritual (make living-ritual / --discord) — paste only, never auto-post",
        ],
        "note": (
            "Sunday living packet draft — staff publishes. "
            "Cross-check weekly ritual Discord before paste. "
            "Never invent fills; never soften floors; never enable live."
        ),
    }


def format_discord(packet: dict | None = None) -> str:
    """Staff-facing Discord/markdown copy — never auto-posts."""
    p = packet if isinstance(packet, dict) else {}
    swarm = p.get("insight_swarm") if isinstance(p.get("insight_swarm"), dict) else {}
    ai = p.get("living_ai") if isinstance(p.get("living_ai"), dict) else {}
    comp = p.get("completions") if isinstance(p.get("completions"), dict) else {}
    dual = p.get("dual_control") if isinstance(p.get("dual_control"), dict) else {}
    ruin = p.get("ruin_drill") if isinstance(p.get("ruin_drill"), dict) else {}
    quiet = p.get("feature_quiet") if isinstance(p.get("feature_quiet"), dict) else {}
    doctor_age = p.get("doctor_age") if isinstance(p.get("doctor_age"), dict) else {}
    ritual = p.get("ritual") if isinstance(p.get("ritual"), dict) else {}
    lines = [
        "**Sunday living packet** (draft — staff publishes)",
        f"_paper only · floors locked · live={bool(p.get('live_orders_enabled'))}_",
        "",
        f"• Chicago day: `{p.get('chicago_today')}`",
        f"• Scorecard: `{p.get('scorecard_label') or '—'}` present={bool(p.get('scorecard_present'))}",
        (
            f"• Insight swarm: {swarm.get('insight_n')}:{swarm.get('betting_n')} "
            f"ratio={swarm.get('ratio')} pass={swarm.get('pass')}"
        ),
        (
            f"• Completions today: n={comp.get('eligible_completions_today')} "
            f"pnl={comp.get('eligible_pnl_today')}"
        ),
        f"• raise_Φ tickets: {ai.get('raise_phi_n')} (auto_write_phi=False)",
        (
            f"• Dual-control signed: {dual.get('signed_n')}/{dual.get('items_n')} "
            f"arm_ready_paper={dual.get('arm_ready_paper')}"
        ),
        (
            f"• Ruin drill practiced_this_month={ruin.get('practiced_this_month')} "
            f"active={ruin.get('active')}"
        ),
        f"• Feature quiet: {quiet.get('alert') or ('quiet' if quiet.get('quiet') else 'ok')}",
        f"• Doctor age: {doctor_age.get('label') or '—'}",
        (
            f"• Weekly ritual draft: `{ritual.get('make') or 'make living-ritual-discord'}` "
            f"(paste only · auto_publish=False)"
        ),
        "",
        "**Staff checklist**",
    ]
    for item in p.get("staff_checklist") or []:
        lines.append(f"- [ ] {item}")
    lines.append("")
    lines.append(str(p.get("note") or "Never invent fills; never soften floors; never enable live."))
    return "\n".join(lines)


def write_packet(root: str | None = None) -> dict:
    packet = build_packet(root)
    path = packet_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(packet, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)
    # Keep reporter digest in sync as a thin mirror.
    try:
        from helpers import reporter_clerk
        reporter_clerk.write_digest(root, scorecard={
            "label": packet.get("scorecard_label"),
            "m1": None,
            "packet": True,
        })
    except Exception:
        pass
    return packet


def write_digest_from_desk(root: str | None = None) -> dict:
    """Clerk-pulse compatible alias."""
    return write_packet(root)


if __name__ == "__main__":
    print(json.dumps(write_packet(), indent=2, sort_keys=True)[:500])
