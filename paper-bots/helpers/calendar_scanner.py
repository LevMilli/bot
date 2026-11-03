"""
Calendar scanner helper — refreshes FF cache and writes a digest for mains.

Never places paper fills. Never touches venue min_edge. Paper / helper-only.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from helpers import calendar_cache
from helpers import HELPER_ONLY, PAPER_ONLY

DIGEST_NAME = "calendar_digest.json"
RUN_MARKER = "calendar_scanner_at.txt"
CADENCE_SEC = 15 * 60


def digest_path(root: str | None = None) -> str:
    base = root or calendar_cache.DESK_ROOT
    return os.path.join(base, "helpers", DIGEST_NAME)


def _marker_path(root: str | None = None) -> str:
    base = root or calendar_cache.DESK_ROOT
    return os.path.join(base, "helpers", RUN_MARKER)


def _parse_when(raw: str | None):
    if not raw:
        return None
    try:
        when = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when


def build_digest(events: list, *, now: datetime | None = None, horizon_h: float = 24.0) -> dict:
    """High-impact USD (and peers) inside the next horizon — signal only."""
    assert PAPER_ONLY and HELPER_ONLY
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    upcoming = []
    for ev in events or []:
        if not isinstance(ev, dict):
            continue
        impact = str(ev.get("impact") or "").strip().lower()
        if impact not in ("high", "medium"):
            continue
        when = _parse_when(ev.get("date") or ev.get("when"))
        if when is None:
            continue
        eta_h = (when - now).total_seconds() / 3600.0
        if eta_h < -0.5 or eta_h > float(horizon_h):
            continue
        upcoming.append(
            {
                "title": str(ev.get("title") or ev.get("name") or "")[:120],
                "country": str(ev.get("country") or "")[:8],
                "impact": impact,
                "date": when.isoformat(),
                "eta_h": round(eta_h, 2),
            }
        )
    upcoming.sort(key=lambda row: float(row.get("eta_h") or 0))
    high = [row for row in upcoming if row["impact"] == "high"]
    return {
        "paper_only": True,
        "helper_only": True,
        "places_orders": False,
        "at": now.isoformat(),
        "horizon_h": float(horizon_h),
        "n_upcoming": len(upcoming),
        "n_high": len(high),
        "upcoming": upcoming[:20],
        "note": "Helper digest for BTC/commodity news gates — never places alone.",
    }


def write_digest(digest: dict, root: str | None = None) -> str:
    path = digest_path(root)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    payload = dict(digest)
    payload["paper_only"] = True
    payload["helper_only"] = True
    payload["places_orders"] = False
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    os.replace(tmp, path)
    return path


def scan(root: str | None = None, *, force: bool = False) -> dict:
    """Refresh calendar cache (last-good) and write digest. No fills."""
    assert PAPER_ONLY and HELPER_ONLY
    try:
        from helpers import assert_helper_only
        assert_helper_only("calendar_scanner")
    except Exception:
        pass
    digest_note = "Helper digest — never places alone."
    try:
        import desk_roi_plan
        # Surface Gate A status on digest; scanner still never places.
        gate = desk_roi_plan.helper_gate_a(root, "calendar_scanner")
        digest_note = (
            f"Helper digest — never places alone. Gate A: {gate.get('reason')}"
        )
    except Exception:
        gate = None
    state = calendar_cache.refresh_if_stale(root, force=force)
    events = list(state.get("events") or [])
    digest = build_digest(events)
    digest["cache_error"] = state.get("last_error")
    digest["cache_fetched_at"] = state.get("fetched_at")
    digest["note"] = digest_note
    digest["places_orders"] = False
    if gate is not None:
        digest["helper_gate_a"] = {
            "ready": gate.get("ready"),
            "n": gate.get("n"),
            "expectancy_taxed": gate.get("expectancy_taxed"),
            "auto_promote": False,
        }
    write_digest(digest, root)
    return digest


def run_if_due(root: str | None = None, now: datetime | None = None) -> dict | None:
    """Timer hook: at most once per CADENCE_SEC."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    marker = _marker_path(root)
    try:
        if os.path.isfile(marker) and not force_due(marker, now):
            return None
    except OSError:
        pass
    digest = scan(root)
    try:
        os.makedirs(os.path.dirname(marker) or ".", exist_ok=True)
        with open(marker, "w", encoding="utf-8") as handle:
            handle.write(now.astimezone(timezone.utc).isoformat() + "\n")
    except OSError:
        pass
    return digest


def force_due(marker: str, now: datetime) -> bool:
    try:
        age = now.timestamp() - os.path.getmtime(marker)
    except OSError:
        return True
    return age >= CADENCE_SEC


def self_check() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, "helpers"), exist_ok=True)
        calendar_cache.save_raw(
            {
                "paper_only": True,
                "fetched_at": time.time(),
                "source": calendar_cache.FF_URL,
                "events": [
                    {
                        "country": "USD",
                        "impact": "High",
                        "title": "CPI",
                        "date": (datetime.now(timezone.utc).isoformat()),
                    }
                ],
                "last_error": None,
            },
            tmp,
        )
        digest = scan(tmp)
        assert digest["places_orders"] is False
        assert digest["helper_only"] is True
        assert digest["n_high"] >= 1
        assert os.path.isfile(digest_path(tmp))


if __name__ == "__main__":
    self_check()
    print("helpers.calendar_scanner self_check ok")
