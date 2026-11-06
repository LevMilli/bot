"""
Calib Nag insight helper — surfaces BTC/sports raise_Φ calibration tickets (observe-only).

Never places fills. Never writes Φ. Never softens venue floors.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from helpers import HELPER_ONLY, PAPER_ONLY, assert_helper_only

DIGEST_NAME = "calib_nag_digest.json"
DESK_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def digest_path(root: str | None = None) -> str:
    return os.path.join(root or DESK_ROOT, "helpers", DIGEST_NAME)


def _card(name: str, report: dict | None) -> dict:
    rep = report if isinstance(report, dict) else {}
    return {
        "board": name,
        "n": rep.get("n"),
        "hi_n": rep.get("hi_n"),
        "hi_hit_rate": rep.get("hi_hit_rate"),
        "miscalibrated": bool(rep.get("miscalibrated")),
        "action": str(rep.get("action") or "observe")[:40],
        "raise_phi": str(rep.get("action") or "") == "raise_phi",
    }


def build_digest(
    btc: dict | None = None,
    sports: dict | None = None,
    *,
    now: datetime | None = None,
) -> dict:
    assert_helper_only("calib_nag")
    assert PAPER_ONLY and HELPER_ONLY
    now = now or datetime.now(timezone.utc)
    cards = [_card("btc", btc), _card("sports", sports)]
    tickets = [c for c in cards if c.get("raise_phi")]
    return {
        "helper": "calib_nag",
        "at": now.isoformat(),
        "paper_only": True,
        "may_place_alone": False,
        "floors_locked": True,
        "auto_write_phi": False,
        "tickets_n": len(tickets),
        "boards": cards,
        "tickets": tickets,
        "note": (
            "Observe-only calib nag. raise_phi is a staff ticket — never silent Φ write, "
            "never softer floors."
        ),
    }


def write_digest(
    root: str | None = None,
    *,
    btc: dict | None = None,
    sports: dict | None = None,
) -> dict:
    digest = build_digest(btc, sports)
    path = digest_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(digest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)
    return digest


def write_digest_from_desk(root: str | None = None, bots: list | None = None) -> dict:
    btc = sports = {}
    try:
        import desk_roi_plan
        base = root or DESK_ROOT
        btc = desk_roi_plan.latest_btc_calibration(base) or desk_roi_plan.btc_calibration_report(bots)
        sports = (
            desk_roi_plan.latest_sports_calibration(base)
            or desk_roi_plan.sports_calibration_report(bots)
        )
    except Exception:
        btc = sports = {}
    return write_digest(root, btc=btc if isinstance(btc, dict) else {}, sports=sports if isinstance(sports, dict) else {})


if __name__ == "__main__":
    print(write_digest(btc={"n": 20, "hi_n": 20, "hi_hit_rate": 0.5, "miscalibrated": True, "action": "raise_phi"}))
