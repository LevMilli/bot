"""
NHL Poisson audit insight helper — pickcenter vs nhl_model gap (observe-only).

Reads sports-gap quote_cache NHL summaries offline. Never places fills.
Never softens venue min_edge. Paper / helper-only.
"""
from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime, timezone

from helpers import HELPER_ONLY, PAPER_ONLY, assert_helper_only

DIGEST_NAME = "nhl_poisson_audit_digest.json"
DESK_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def digest_path(root: str | None = None) -> str:
    return os.path.join(root or DESK_ROOT, "helpers", DIGEST_NAME)


def _finite(x):
    try:
        n = float(x)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(n):
        return None
    return n


def _ml_to_prob(ml) -> float | None:
    n = _finite(ml)
    if n is None or abs(n) < 1e-12:
        return None
    if n > 0:
        return 100.0 / (n + 100.0)
    return (-n) / ((-n) + 100.0)


def pickcenter_fair_home(summary: dict) -> float | None:
    """De-vigged ESPN pickcenter home win prob. None if incomplete — never invent."""
    pc = summary.get("pickcenter") if isinstance(summary, dict) else None
    if not isinstance(pc, list) or not pc:
        return None
    row = pc[0] if isinstance(pc[0], dict) else None
    if not row:
        return None
    try:
        home = row.get("homeTeamOdds") or {}
        away = row.get("awayTeamOdds") or {}
        ph = _ml_to_prob(home.get("moneyLine"))
        pa = _ml_to_prob(away.get("moneyLine"))
    except Exception:
        return None
    if ph is None or pa is None or ph + pa <= 0:
        return None
    return float(ph) / float(ph + pa)


def _competition_game(summary: dict) -> dict | None:
    """ESPN summary competitions live under header.competitions (or root)."""
    if not isinstance(summary, dict):
        return None
    comps = summary.get("competitions")
    if not isinstance(comps, list) or not comps:
        header = summary.get("header") if isinstance(summary.get("header"), dict) else {}
        comps = header.get("competitions")
    if not isinstance(comps, list) or not comps:
        return None
    comp = comps[0] if isinstance(comps[0], dict) else None
    if not comp:
        return None
    teams = {}
    for c in comp.get("competitors") or []:
        if not isinstance(c, dict):
            continue
        side = str(c.get("homeAway") or "").lower()
        if side in ("home", "away"):
            teams[side] = {
                "score": c.get("score"),
                "team": (c.get("team") or {}),
            }
    if "home" not in teams or "away" not in teams:
        return None
    status = comp.get("status") or summary.get("status") or {}
    # nhl_model expects status.period/clock; finals often only have type.completed.
    if isinstance(status, dict) and status.get("period") is None:
        typ = status.get("type") if isinstance(status.get("type"), dict) else {}
        if typ.get("completed") or str(typ.get("state") or "") == "post":
            status = {**status, "period": 3, "clock": 0}
    return {
        "status": status,
        "home": teams["home"],
        "away": teams["away"],
    }


def audit_summary(summary: dict, *, nhl_model=None) -> dict | None:
    """One NHL summary → pickcenter fair vs Poisson model. Skip incomplete."""
    assert PAPER_ONLY and HELPER_ONLY
    if not isinstance(summary, dict):
        return None
    fair_pc = pickcenter_fair_home(summary)
    game = _competition_game(summary)
    if fair_pc is None or game is None:
        return None
    model = None
    if nhl_model is not None:
        try:
            model = float(nhl_model(summary, game))
        except Exception:
            model = None
    if model is None or not math.isfinite(model):
        return None
    if not (0.0 <= model <= 1.0):
        return None
    wipe = abs(model - 0.0) < 1e-12 or abs(model - 1.0) < 1e-12
    gap = float(model) - float(fair_pc)
    event = summary.get("header") if isinstance(summary.get("header"), dict) else {}
    name = str(
        event.get("id")
        or (summary.get("boxscore") or {}).get("teams")
        or "nhl"
    )[:80]
    return {
        "event": name,
        "pickcenter_fair": round(float(fair_pc), 4),
        "nhl_model": round(float(model), 4),
        "gap": round(gap, 4),
        "abs_gap": round(abs(gap), 4),
        "wipe_01": wipe,
    }


def load_nhl_summaries(root: str | None = None, *, limit: int = 40) -> list[dict]:
    """Offline NHL ESPN summaries from sports-gap quote_cache."""
    path = os.path.join(root or DESK_ROOT, "sports-gap-paper", "quote_cache.json")
    if not os.path.isfile(path):
        return []
    try:
        with open(path, encoding="utf-8") as handle:
            cache = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(cache, dict):
        return []
    rows = []
    for url, slot in cache.items():
        if "hockey/nhl/summary" not in str(url).lower():
            continue
        if not isinstance(slot, dict):
            continue
        body = slot.get("body")
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except json.JSONDecodeError:
                continue
        if isinstance(body, dict):
            rows.append(body)
        if len(rows) >= int(limit):
            break
    return rows


def _import_nhl_model():
    gap_path = os.path.join(DESK_ROOT, "sports-gap-paper", "gap_bot.py")
    if not os.path.isfile(gap_path):
        return None
    try:
        import importlib.util
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        spec = importlib.util.spec_from_file_location("gap_bot_nhl_audit", gap_path)
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        return getattr(mod, "nhl_model", None)
    except Exception:
        return None


def build_digest(
    audits: list | None = None,
    *,
    now: datetime | None = None,
) -> dict:
    assert_helper_only("nhl_poisson_audit")
    assert PAPER_ONLY and HELPER_ONLY
    now = now or datetime.now(timezone.utc)
    rows = [r for r in (audits or []) if isinstance(r, dict)]
    wipe_n = sum(1 for r in rows if r.get("wipe_01"))
    avg_abs = (
        round(sum(float(r.get("abs_gap") or 0) for r in rows) / len(rows), 4)
        if rows else None
    )
    return {
        "helper": "nhl_poisson_audit",
        "at": now.isoformat(),
        "paper_only": True,
        "may_place_alone": False,
        "floors_locked": True,
        "n": len(rows),
        "wipe_01_n": wipe_n,
        "avg_abs_gap": avg_abs,
        "audits": rows[:24],
        "note": (
            "Observe-only NHL Poisson audit: pickcenter de-vig vs nhl_model. "
            "Wipe 0/1 finals flagged. Never softens sports 0.06. Never LIVE."
        ),
    }


def write_digest_from_desk(root: str | None = None) -> dict:
    root = root or DESK_ROOT
    model = _import_nhl_model()
    audits = []
    for summary in load_nhl_summaries(root):
        row = audit_summary(summary, nhl_model=model)
        if row:
            audits.append(row)
    digest = build_digest(audits)
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
