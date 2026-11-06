#!/usr/bin/env python3
"""
Staff UX — compact living upgrade status (never enables live / never softens floors).

Usage (from paper-bots/):
  python3 tools/staff_living_status.py
  python3 tools/staff_living_status.py json
  python3 tools/staff_living_status.py pager
  python3 tools/staff_living_status.py priority
  python3 tools/staff_living_status.py selfcheck
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import desk_living
import desk_master


def _board(root: str) -> dict:
    return desk_living.living_upgrade_board(root) or {}


def _text(board: dict) -> str:
    compact = board.get("compact") if isinstance(board.get("compact"), dict) else {}
    swarm = board.get("insight_swarm") if isinstance(board.get("insight_swarm"), dict) else {}
    quiet = board.get("feature_quiet") if isinstance(board.get("feature_quiet"), dict) else {}
    dual = board.get("dual_control_chip") if isinstance(board.get("dual_control_chip"), dict) else {}
    ruin = board.get("ruin_drill_chip") if isinstance(board.get("ruin_drill_chip"), dict) else {}
    lines = [
        "Living upgrade status (paper only · floors locked · live=False)",
        f"compact: {compact.get('label') or '—'}",
        (
            f"swarm: {swarm.get('insight_n')}:{swarm.get('betting_n')} "
            f"pass={swarm.get('pass')}"
        ),
        (
            f"feature quiet: quiet={quiet.get('quiet')} "
            f"age_h={quiet.get('age_hours')} alert={quiet.get('alert') or 'ok'}"
        ),
        f"dual-control: {dual.get('label') or '—'}",
        f"ruin: {ruin.get('label') or '—'}",
        f"chicago_today: {board.get('chicago_today')}",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Staff living upgrade status.")
    parser.add_argument(
        "action",
        nargs="?",
        default="text",
        choices=("text", "json", "pager", "priority", "selfcheck"),
    )
    parser.add_argument("--root", default=ROOT)
    args = parser.parse_args()
    root = args.root
    board = _board(root)

    if args.action == "selfcheck":
        print(json.dumps(desk_living.living_self_check(root), indent=2, sort_keys=True, default=str))
        return 0
    if args.action == "json":
        print(json.dumps({
            "paper_only": True,
            "fee_floors_locked": True,
            "live_orders_enabled": False,
            "compact": board.get("compact"),
            "insight_swarm": board.get("insight_swarm"),
            "feature_quiet": board.get("feature_quiet"),
            "feature_quiet_pager": board.get("feature_quiet_pager"),
            "dual_control_chip": board.get("dual_control_chip"),
            "ruin_drill_chip": board.get("ruin_drill_chip"),
            "timer_heartbeat": board.get("timer_heartbeat"),
            "chicago_today": board.get("chicago_today"),
        }, indent=2, sort_keys=True, default=str))
        return 0
    if args.action == "pager":
        pager = board.get("feature_quiet_pager")
        if not isinstance(pager, dict):
            pager = desk_living.feature_quiet_pager(root)
        if pager.get("page") and pager.get("copy"):
            print(pager["copy"])
        else:
            print(json.dumps({
                "page": False,
                "auto_page": False,
                "fee_floors_locked": True,
                "note": pager.get("note") or "No feature-quiet page.",
            }, indent=2))
        return 0
    if args.action == "priority":
        living = board
        raw: list[str] = []
        fq = living.get("feature_quiet") if isinstance(living.get("feature_quiet"), dict) else {}
        if fq.get("quiet") and fq.get("alert"):
            raw.insert(0, str(fq.get("alert"))[:120])
        timer = living.get("timer_heartbeat") if isinstance(living.get("timer_heartbeat"), dict) else {}
        if timer.get("alive") is False:
            raw.insert(0, str(timer.get("label") or "timer DEAD")[:120])
        swarm = living.get("insight_swarm") if isinstance(living.get("insight_swarm"), dict) else {}
        if swarm.get("pass") is False:
            raw.append(
                f"insight swarm {swarm.get('insight_n')}:{swarm.get('betting_n')} "
                f"(need ≥{swarm.get('min_ratio')}:1)"
            )
        ruin = living.get("ruin_drill_chip") if isinstance(living.get("ruin_drill_chip"), dict) else {}
        if ruin.get("active"):
            raw.insert(0, str(ruin.get("label") or "ruin ACTIVE")[:120])
        elif not ruin.get("practiced_this_month"):
            raw.append("ruin drill: practice soft/hard this Chicago month")
        raw.extend([
            "insight swarm ≥3:1 before betting expand",
            "revert last lever if hillclimb kill trips",
            "fee floors locked 0.06/0.05/0.02",
        ])
        print(json.dumps({
            "paper_only": True,
            "fee_floors_locked": True,
            "priority": desk_master.finalize_living_priority(raw),
            "max_n": desk_master.PRIORITY_MAX,
        }, indent=2))
        return 0
    print(_text(board))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
