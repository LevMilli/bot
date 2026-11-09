"""
BTC Basis Scout insight helper — funding + premium carry observe (never cash).

Surfaces the BTC carry sleeve stance and ETH/SOL twin research card. Never
opens desk cash. Never softens venue floors. Paper / helper-only.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from helpers import HELPER_ONLY, PAPER_ONLY, assert_helper_only

DIGEST_NAME = "btc_basis_scout_digest.json"
DESK_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def digest_path(root: str | None = None) -> str:
    return os.path.join(root or DESK_ROOT, "helpers", DIGEST_NAME)


def _load_carry_state(root: str | None = None) -> dict:
    path = os.path.join(root or DESK_ROOT, "btc-carry-paper", "paper_account.json")
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _twin_card() -> dict:
    try:
        import desk_roi_plan
        out = desk_roi_plan.funding_carry_twins_observe() or {}
        twins = out.get("twins") if isinstance(out, dict) else None
        return twins if isinstance(twins, dict) else {}
    except Exception:
        return {}


def build_digest(
    state: dict | None = None,
    *,
    twins: dict | None = None,
    now: datetime | None = None,
) -> dict:
    assert_helper_only("btc_basis_scout")
    assert PAPER_ONLY and HELPER_ONLY
    now = now or datetime.now(timezone.utc)
    state = state if isinstance(state, dict) else {}
    twins = twins if isinstance(twins, dict) else {}
    open_rows = [r for r in (state.get("open") or []) if isinstance(r, dict)]
    pos = open_rows[0] if open_rows else {}
    eth = twins.get("eth") if isinstance(twins.get("eth"), dict) else {}
    sol = twins.get("sol") if isinstance(twins.get("sol"), dict) else {}
    eth_stance = str(eth.get("role") or eth.get("stance") or "observe_twin_same_factor")
    sol_stance = str(sol.get("role") or sol.get("stance") or "reject_mean_red")
    return {
        "helper": "btc_basis_scout",
        "at": now.isoformat(),
        "paper_only": True,
        "may_place_alone": False,
        "floors_locked": True,
        "opens_desk_cash": False,
        "second_tower": False,
        "btc_open_n": len(open_rows),
        "funding_pnl": pos.get("funding_pnl"),
        "basis_pnl": pos.get("basis_pnl"),
        "fee_paid": pos.get("fee_paid") if pos.get("fee_paid") is not None else pos.get("rt_fee"),
        "eth_stance": eth_stance,
        "sol_stance": sol_stance,
        "eth_pass": eth.get("pass"),
        "sol_reject": not bool(sol.get("pass")) if sol else True,
        "twins_ok": bool(twins),
        "note": (
            "Observe-only BTC basis scout. ETH is the same-factor twin; SOL reject. "
            "Only BTC carry holds shadow cash — never LIVE."
        ),
    }


def write_digest_from_desk(root: str | None = None) -> dict:
    root = root or DESK_ROOT
    digest = build_digest(_load_carry_state(root), twins=_twin_card())
    path = digest_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(digest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)
    return digest


if __name__ == "__main__":
    print(json.dumps(write_digest_from_desk(), indent=2, sort_keys=True))
