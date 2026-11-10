#!/usr/bin/env python3
"""Scaffold and check a new paper tower.

Creates a shadow-only folder. Does not edit the shared desk registry.
After you wire the registry by hand, `check` confirms the tower is on the
same rails as Coinbase spot: paper only, locked floor, exit plan, no live
risk share while it is still a shadow.

    python tools/new_tower.py scaffold weather-kalshi --name "Weather Kalshi" --floor 0.06
    python tools/new_tower.py check coinbase-spot
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DESK = os.path.dirname(HERE)
ID_OK = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
MIN_FLOOR = 0.02


def scaffold(root: str, bot_id: str, name: str, floor: float) -> dict:
    if not ID_OK.match(bot_id):
        return {"ok": False, "reason": "id must be lowercase kebab-case"}
    if bot_id in (
        "sports-gap", "kalshi-sp", "btc15m", "commodity-15m", "memecoin",
        "kalshi-sized", "coinbase-spot", "btc-carry", "sports-sharp-lag",
        "fed-watch", "wall-street",
    ):
        return {"ok": False, "reason": "that tower already exists"}
    if floor + 1e-12 < MIN_FLOOR or floor > 0.20:
        return {"ok": False, "reason": f"floor stays between {MIN_FLOOR:.2f} and 0.20"}
    folder = os.path.join(root, f"{bot_id}-paper")
    if os.path.exists(folder):
        return {"ok": False, "reason": "folder already exists"}
    os.makedirs(folder)
    cfg = {
        "paper_only": True,
        "live_orders": False,
        "shadow_only": True,
        "venue_min_edge": floor,
        "note": "Scaffold skips every check until a fee-aware rule replaces evaluate.",
    }
    _write(os.path.join(folder, "config.json"), json.dumps(cfg, indent=2) + "\n")
    _write(os.path.join(folder, ".gitignore"), "paper_account.json\nresearch.jsonl\n__pycache__/\n")
    _write(os.path.join(folder, "bot.py"), _BOT.format(bot_id=bot_id, name=name, floor=floor))
    _write(os.path.join(folder, "README.md"), _README.format(bot_id=bot_id, name=name, floor=floor))
    return {
        "ok": True,
        "folder": folder,
        "paper_only": True,
        "checklist": checklist(bot_id, floor),
    }


def checklist(bot_id: str, floor: float) -> list[str]:
    venue = bot_id.replace("-", "_")
    return [
        f"Add venue `{venue}` floor {floor:.2f} to desk_profit.VENUE_KEYS and DEFAULT_VENUE_MIN_EDGE (never below the lock).",
        "Mirror that floor in desk_roi_e4, desk_roi_post_e3e7, and helpers/advice_schema.",
        f"Register `{bot_id}` in pimp_desk BOTS, BOT_PLANS, ACTIONS, ACCOUNT_FILES, AUTO, starter cash.",
        "Mark the spec shadow_only until incubation n≥50. Do not give it a tower_risk_budgets share.",
        "Exit plan at least partial (stop or model-flip plus a backstop) before any buy.",
        "Give the city a beam color and a wing room.",
        f"Run: python tools/new_tower.py check {bot_id}",
        "One tower per PR. Do not soften sports 0.06 / BTC+commodity 0.05 / INX+DEX 0.02 / Coinbase spot 0.05.",
    ]


def check_tower(bot_id: str) -> dict:
    if DESK not in sys.path:
        sys.path.insert(0, DESK)
    import desk_profit
    import pimp_desk

    missing = []
    spec = next((row for row in pimp_desk.BOTS if row.get("id") == bot_id), None)
    if spec is None:
        missing.append("BOTS")
    if bot_id not in pimp_desk.BOT_PLANS:
        missing.append("BOT_PLANS")
    if bot_id not in pimp_desk.ACTIONS:
        missing.append("ACTIONS")
    if bot_id not in pimp_desk.ACCOUNT_FILES:
        missing.append("ACCOUNT_FILES")
    if not any(slot.get("id") == bot_id for slot in pimp_desk.AUTO):
        missing.append("AUTO")
    plans = pimp_desk.BOT_PLANS.get(bot_id) or {}
    if plans.get("exit_quality") not in ("partial", "strong"):
        missing.append("exit quality partial or strong")
    if not plans.get("entry_gated"):
        missing.append("entry_gated")
    venue = desk_profit.BOT_VENUE.get(bot_id)
    if not venue or venue not in desk_profit.DEFAULT_VENUE_MIN_EDGE:
        missing.append("venue floor")
    elif float(desk_profit.DEFAULT_VENUE_MIN_EDGE[venue]) + 1e-12 < MIN_FLOOR:
        missing.append("floor below 0.02")
    if spec and spec.get("shadow_only"):
        if bot_id in (pimp_desk.DEFAULTS.get("tower_risk_budgets") or {}):
            missing.append("shadow tower has a live risk share")
    if spec:
        script = os.path.join(DESK, spec["folder"], spec["script"])
        cfg_path = os.path.join(DESK, spec["folder"], "config.json")
        if not os.path.isfile(script):
            missing.append("script")
        if os.path.isfile(cfg_path):
            with open(cfg_path, encoding="utf-8") as handle:
                cfg = json.load(handle)
            if cfg.get("paper_only") is not True or cfg.get("live_orders") is True:
                missing.append("config paper_only")
    action = (pimp_desk.ACTIONS.get(bot_id) or {}).get("run") or {}
    blob = " ".join(action.get("argv") or []).lower()
    for word in ("api_key", "wallet", "order", "--any-time"):
        if word in blob:
            missing.append(f"argv contains {word}")
    return {
        "ok": not missing,
        "bot": bot_id,
        "missing": missing,
        "paper_only": True,
        "shadow_only": bool(spec and spec.get("shadow_only")),
        "venue": venue,
    }


def _write(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


_BOT = '''#!/usr/bin/env python3
"""{name} — scaffold paper tower. Shadow only. No live orders.

Replace evaluate() with a fee-aware rule before this tower buys anything.
Floor hint: {floor:.2f}. Do not lower a locked venue floor to get fills.
"""
from __future__ import annotations

import sys


def evaluate() -> dict:
    return {{"action": "skip", "reason": "scaffold — no fee-aware rule yet"}}


def main() -> int:
    if "--reset" in sys.argv:
        print("reset paper account")
        return 0
    row = evaluate()
    print("SIGNAL: SKIP " + row["reason"])
    print("CARD: " + row["reason"])
    print("no trade")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

_README = """# {name}

Scaffold for `{bot_id}`. Paper only. Shadow until incubation says otherwise.

Floor hint **{floor:.2f}**. Wire it with `paper-bots/TOWER_SETUP.md`. This folder
does not trade until `evaluate` is a real fee-aware rule and `check` passes.
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scaffold or check a paper tower")
    sub = parser.add_subparsers(dest="cmd", required=True)
    add = sub.add_parser("scaffold")
    add.add_argument("bot_id")
    add.add_argument("--name", default="")
    add.add_argument("--floor", type=float, default=0.05)
    add.add_argument("--root", default=DESK)
    chk = sub.add_parser("check")
    chk.add_argument("bot_id")
    args = parser.parse_args(argv)
    if args.cmd == "scaffold":
        name = args.name or args.bot_id
        out = scaffold(args.root, args.bot_id, name, args.floor)
    else:
        out = check_tower(args.bot_id)
    print(json.dumps(out, indent=2))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
