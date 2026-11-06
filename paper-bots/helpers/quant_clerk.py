"""
Quant Clerk insight helper — digests M3 fit→buy + M4 latency (observe-only walk-forward).

Never places fills. Never writes live params. Paper / helper-only.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from helpers import HELPER_ONLY, PAPER_ONLY, assert_helper_only

DIGEST_NAME = "quant_clerk_digest.json"
DESK_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEE_CLEAR = ("sports-gap", "btc15m", "commodity-15m")


def digest_path(root: str | None = None) -> str:
    return os.path.join(root or DESK_ROOT, "helpers", DIGEST_NAME)


def build_digest(
    fit: dict | None = None,
    latency: dict | None = None,
    by_tower: list | None = None,
    *,
    now: datetime | None = None,
) -> dict:
    assert_helper_only("quant_clerk")
    assert PAPER_ONLY and HELPER_ONLY
    now = now or datetime.now(timezone.utc)
    fit = fit if isinstance(fit, dict) else {}
    latency = latency if isinstance(latency, dict) else {}
    return {
        "helper": "quant_clerk",
        "at": now.isoformat(),
        "paper_only": True,
        "may_place_alone": False,
        "floors_locked": True,
        "fit_rate": fit.get("rate"),
        "fit_n": fit.get("n_fit"),
        "fit_pass": fit.get("pass"),
        "latency_p50": latency.get("p50") or latency.get("seconds"),
        "latency_pass": latency.get("pass"),
        "towers": (by_tower or [])[:12],
        "auto_write": False,
        "note": (
            "Observe-only quant clerk (walk-forward). Fit→buy + latency for fee-clear — "
            "never LLM buys, never softer floors."
        ),
    }


def write_digest(
    root: str | None = None,
    *,
    fit: dict | None = None,
    latency: dict | None = None,
    by_tower: list | None = None,
) -> dict:
    digest = build_digest(fit, latency, by_tower)
    path = digest_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(digest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)
    return digest


def write_digest_from_desk(root: str | None = None) -> dict:
    fit = latency = {}
    towers = []
    try:
        import desk_roi_plan
        base = root or DESK_ROOT
        fit = desk_roi_plan.fit_buy_rate(base) or {}
        latency = desk_roi_plan.latency_p50(base) or {}
        for bot in FEE_CLEAR:
            towers.append({
                "bot": bot,
                "fit": desk_roi_plan.fit_buy_rate(base, bot=bot),
                "latency": desk_roi_plan.latency_p50(base, bot=bot),
            })
    except Exception:
        fit = latency = {}
        towers = []
    return write_digest(
        root,
        fit=fit if isinstance(fit, dict) else {},
        latency=latency if isinstance(latency, dict) else {},
        by_tower=towers,
    )


if __name__ == "__main__":
    print(write_digest(fit={"rate": 0.5, "n_fit": 20, "pass": True}, latency={"p50": 1.1, "pass": True}))
