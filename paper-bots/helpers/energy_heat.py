"""
Energy heat insight helper — WTI / Brent / NatGas observe + EIA regime.

Ranks energy 15m series by vol prior + recent |z|, joins commodity-curve
EIA regime when present. Never places fills. Never softens 0.05.
"""
from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone

from helpers import HELPER_ONLY, PAPER_ONLY, assert_helper_only

DIGEST_NAME = "energy_heat_digest.json"
DESK_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENERGY_SERIES = ("KXWTI15M", "KXBRENT15M", "KXNATGAS15M")


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
    for known in ENERGY_SERIES:
        if key.startswith(known):
            return known
    return ""


def load_feature_zs(root: str | None = None, *, limit_lines: int = 8000) -> dict[str, list[float]]:
    path = os.path.join(root or DESK_ROOT, "desk_feature_store.jsonl")
    out: dict[str, list[float]] = {s: [] for s in ENERGY_SERIES}
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


def load_curve_regimes(root: str | None = None) -> dict[str, dict]:
    """Optional desk_commodity_curve.json EIA/roll marks — never invent."""
    path = os.path.join(root or DESK_ROOT, "desk_commodity_curve.json")
    out: dict[str, dict] = {}
    if not os.path.isfile(path):
        return out
    try:
        with open(path, encoding="utf-8") as handle:
            blob = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return out
    rows = blob.get("rows") or blob.get("quotes") or blob.get("strikes") or []
    if isinstance(blob, list):
        rows = blob
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        series = _series_key(str(row.get("series") or row.get("label") or row.get("ticker") or ""))
        if not series:
            continue
        out[series] = {
            "eia_regime": str(row.get("eia_regime") or row.get("regime") or "")[:32] or None,
            "roll_yield": _finite(row.get("roll_yield")),
        }
    return out


def score_series(
    zs: dict[str, list[float]] | None = None,
    *,
    regimes: dict | None = None,
) -> list[dict]:
    assert PAPER_ONLY and HELPER_ONLY
    try:
        import desk_more
        prior_fn = desk_more.series_vol_prior
    except Exception:
        prior_fn = lambda _s: 0.0  # noqa: E731
    zs = zs if isinstance(zs, dict) else {}
    regimes = regimes if isinstance(regimes, dict) else {}
    rows = []
    for series in ENERGY_SERIES:
        samples = [float(x) for x in (zs.get(series) or []) if _finite(x) is not None]
        prior = float(prior_fn(series) or 0.0)
        mean_abs = (sum(samples) / len(samples)) if samples else None
        z_term = math.tanh((mean_abs or 0.0) / 10.0)
        reg = regimes.get(series) if isinstance(regimes.get(series), dict) else {}
        eia = str(reg.get("eia_regime") or "").strip().lower()
        # Small observe-only bump for non-neutral EIA / material roll — never a floor soften.
        eia_term = 0.04 if eia in ("draw", "build", "surprise", "hot") else 0.0
        roll = _finite(reg.get("roll_yield"))
        roll_term = min(0.03, abs(float(roll))) if roll is not None else 0.0
        heat = round(prior + z_term + eia_term + roll_term, 4)
        rows.append({
            "series": series,
            "family": "energy",
            "vol_prior": round(prior, 4),
            "n": len(samples),
            "mean_abs_z": round(mean_abs, 4) if mean_abs is not None else None,
            "heat": heat,
            "thin": len(samples) < 5,
            "eia_regime": reg.get("eia_regime"),
            "roll_yield": reg.get("roll_yield"),
        })
    rows.sort(key=lambda r: float(r.get("heat") or 0), reverse=True)
    return rows


def build_digest(
    rows: list | None = None,
    *,
    now: datetime | None = None,
) -> dict:
    assert_helper_only("energy_heat")
    assert PAPER_ONLY and HELPER_ONLY
    now = now or datetime.now(timezone.utc)
    rows = [r for r in (rows or []) if isinstance(r, dict)]
    hot = rows[0] if rows else None
    return {
        "helper": "energy_heat",
        "at": now.isoformat(),
        "paper_only": True,
        "may_place_alone": False,
        "floors_locked": True,
        "n": len(rows),
        "hottest": hot.get("series") if hot else None,
        "hottest_heat": hot.get("heat") if hot else None,
        "series": rows,
        "note": (
            "Observe-only energy heat (vol prior + |z| + EIA/roll when present). "
            "Never softens commodity 0.05. Never LIVE."
        ),
    }


def write_digest_from_desk(root: str | None = None) -> dict:
    root = root or DESK_ROOT
    digest = build_digest(
        score_series(load_feature_zs(root), regimes=load_curve_regimes(root)),
    )
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
