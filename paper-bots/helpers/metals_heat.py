"""
Metals heat insight helper — gold/silver/platinum/palladium/copper observe.

Ranks metal 15m series by vol prior + recent |z| from the feature store.
Never places fills. Never softens commodity 0.05. Paper / helper-only.
"""
from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone

from helpers import HELPER_ONLY, PAPER_ONLY, assert_helper_only

DIGEST_NAME = "metals_heat_digest.json"
DESK_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
METAL_SERIES = (
    "KXGOLD15M",
    "KXSILVER15M",
    "KXPLATINUM15M",
    "KXPALLADIUM15M",
    "KXCOPPER15M",
)


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


def _series_key(raw: str) -> str:
    key = str(raw or "").strip().upper()
    for known in METAL_SERIES:
        if key.startswith(known):
            return known
    return ""


def load_feature_zs(root: str | None = None, *, limit_lines: int = 8000) -> dict[str, list[float]]:
    """Recent |z| samples per metal series from feature store. Never invent."""
    path = os.path.join(root or DESK_ROOT, "desk_feature_store.jsonl")
    out: dict[str, list[float]] = {s: [] for s in METAL_SERIES}
    if not os.path.isfile(path):
        return out
    try:
        with open(path, encoding="utf-8") as handle:
            for i, line in enumerate(handle):
                if i >= int(limit_lines):
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(row, dict):
                    continue
                series = _series_key(str(row.get("series") or row.get("family") or ""))
                if not series:
                    continue
                z = _finite(row.get("z") if row.get("z") is not None else row.get("abs_z"))
                if z is None:
                    continue
                out[series].append(abs(float(z)))
    except OSError:
        return out
    return out


def score_series(zs: dict[str, list[float]] | None = None) -> list[dict]:
    """Heat score = vol prior + tanh(mean|z|/10)."""
    assert PAPER_ONLY and HELPER_ONLY
    try:
        import desk_more
        prior_fn = desk_more.series_vol_prior
    except Exception:
        prior_fn = lambda _s: 0.0  # noqa: E731
    zs = zs if isinstance(zs, dict) else {}
    rows = []
    for series in METAL_SERIES:
        samples = [float(x) for x in (zs.get(series) or []) if _finite(x) is not None]
        prior = float(prior_fn(series) or 0.0)
        mean_abs = (sum(samples) / len(samples)) if samples else None
        z_term = math.tanh((mean_abs or 0.0) / 10.0)
        heat = round(prior + z_term, 4)
        rows.append({
            "series": series,
            "family": "metal",
            "vol_prior": round(prior, 4),
            "n": len(samples),
            "mean_abs_z": round(mean_abs, 4) if mean_abs is not None else None,
            "heat": heat,
            "thin": len(samples) < 5,
        })
    rows.sort(key=lambda r: float(r.get("heat") or 0), reverse=True)
    return rows


def build_digest(
    rows: list | None = None,
    *,
    now: datetime | None = None,
) -> dict:
    assert_helper_only("metals_heat")
    assert PAPER_ONLY and HELPER_ONLY
    now = now or datetime.now(timezone.utc)
    rows = [r for r in (rows or []) if isinstance(r, dict)]
    hot = rows[0] if rows else None
    return {
        "helper": "metals_heat",
        "at": now.isoformat(),
        "paper_only": True,
        "may_place_alone": False,
        "floors_locked": True,
        "n": len(rows),
        "hottest": hot.get("series") if hot else None,
        "hottest_heat": hot.get("heat") if hot else None,
        "series": rows,
        "note": (
            "Observe-only metals heat (vol prior + recent |z|). "
            "Never softens commodity 0.05. Never LIVE."
        ),
    }


def write_digest_from_desk(root: str | None = None) -> dict:
    root = root or DESK_ROOT
    digest = build_digest(score_series(load_feature_zs(root)))
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
