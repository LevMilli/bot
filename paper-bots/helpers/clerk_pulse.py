"""
Clerk Pulse — timer cadence that refreshes insight-helper digests (observe-only).

Runs write_digest_from_desk for the living swarm on a fixed cadence.
Never places fills. Never softens venue floors.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from helpers import HELPER_ONLY, PAPER_ONLY, assert_helper_only

RUN_MARKER = "clerk_pulse_at.txt"
DIGEST_NAME = "clerk_pulse_digest.json"
CADENCE_SEC = 5 * 60
DESK_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Modules that expose write_digest_from_desk(root, ...).
CLERK_MODULES = (
    "helpers.tip_radar",
    "helpers.skip_historian",
    "helpers.timer_heartbeat",
    "helpers.empty_card_bee",
    "helpers.clv_closer",
    "helpers.injury_wire",
    "helpers.eia_scout",
    "helpers.calib_nag",
    "helpers.hard_stop_clerk",
    "helpers.near_miss_clerk",
    "helpers.bleed_clerk",
    "helpers.distance_clerk",
    "helpers.bookkeeper_clerk",
    "helpers.reporter_clerk",
    "helpers.quant_clerk",
    "helpers.skip_twin_clerk",
)


def digest_path(root: str | None = None) -> str:
    return os.path.join(root or DESK_ROOT, "helpers", DIGEST_NAME)


def _marker_path(root: str | None = None) -> str:
    return os.path.join(root or DESK_ROOT, "helpers", RUN_MARKER)


def _import_clerk(mod_name: str):
    import importlib
    return importlib.import_module(mod_name)


def refresh_clerks(root: str | None = None, *, bots: list | None = None) -> dict:
    """Refresh all insight digests that support write_digest_from_desk."""
    assert_helper_only("clerk_pulse")
    assert PAPER_ONLY and HELPER_ONLY
    base = root or DESK_ROOT
    refreshed = []
    errors = []
    for mod_name in CLERK_MODULES:
        short = mod_name.rsplit(".", 1)[-1]
        try:
            mod = _import_clerk(mod_name)
            fn = getattr(mod, "write_digest_from_desk", None)
            if not callable(fn):
                fn = getattr(mod, "write_digest", None)
            if not callable(fn):
                continue
            try:
                fn(base, bots=bots)
            except TypeError:
                try:
                    fn(base)
                except TypeError:
                    # tip_radar etc. accept optional kwargs with defaults
                    fn(root=base)
            refreshed.append(short)
        except Exception as exc:
            errors.append({"clerk": short, "error": str(exc)[:120]})
    # Timer heartbeat: always write alive=True when pulse runs (timer called us).
    try:
        from helpers import timer_heartbeat
        timer_heartbeat.write_digest(base, alive=True, detail="clerk_pulse")
        if "timer_heartbeat" not in refreshed:
            refreshed.append("timer_heartbeat")
    except Exception as exc:
        errors.append({"clerk": "timer_heartbeat", "error": str(exc)[:120]})
    now = datetime.now(timezone.utc)
    digest = {
        "helper": "clerk_pulse",
        "at": now.isoformat(),
        "paper_only": True,
        "may_place_alone": False,
        "floors_locked": True,
        "cadence_sec": CADENCE_SEC,
        "refreshed_n": len(refreshed),
        "refreshed": refreshed,
        "errors_n": len(errors),
        "errors": errors[:12],
        "note": "Observe-only clerk pulse. Refreshes insight digests; never softens floors.",
    }
    path = digest_path(base)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(digest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)
    return digest


def run_if_due(root: str | None = None, now: datetime | None = None, *, bots: list | None = None) -> dict | None:
    """Timer hook — refresh digests at most every CADENCE_SEC."""
    assert PAPER_ONLY and HELPER_ONLY
    now = now or datetime.now(timezone.utc)
    if getattr(now, "tzinfo", None) is None:
        now = now.replace(tzinfo=timezone.utc)
    marker = _marker_path(root)
    due = True
    if os.path.isfile(marker):
        try:
            age = now.timestamp() - os.path.getmtime(marker)
            due = age >= float(CADENCE_SEC)
        except OSError:
            due = True
    if not due:
        return None
    out = refresh_clerks(root, bots=bots)
    try:
        os.makedirs(os.path.dirname(marker), exist_ok=True)
        with open(marker, "w", encoding="utf-8") as handle:
            handle.write(now.isoformat() + "\n")
    except OSError:
        pass
    return out


if __name__ == "__main__":
    print(refresh_clerks())
