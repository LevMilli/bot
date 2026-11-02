"""
desk_master.py — Trading Masters scoreboard stub (M1–M7).

Paper only. Surfaces dual metrics (volume vs taxed EV) so staff can see whether
throughput upgrades are helping ROI — not a profit guarantee.
"""
from __future__ import annotations

import math
import os
from typing import Any

MASTER_VERSION = 1

# Bars from docs/trading-masters-per-bot-plan.md (Chicago weeks).
MASTER_BARS = {
    "M1_taxed_ev": 0.0,
    "M2_hit_rate": 0.55,
    "M3_fit_buy": 0.40,
    "M5_util_lo": 0.40,
    "M5_util_hi": 0.80,
    "M6_gate_a_n": 20,
}


def _finite(x) -> float | None:
    try:
        n = float(x)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(n):
        return None
    return n


def _taxed_expectancy(history: list, fill_tax: float = 0.01) -> dict:
    rows = [h for h in (history or []) if isinstance(h, dict)]
    pnls = []
    for h in rows:
        p = _finite(h.get("pnl") if h.get("pnl") is not None else h.get("pnl_usd"))
        if p is None:
            continue
        # Crude fill tax: subtract 1¢ * contracts proxy when present, else flat tax once.
        contracts = _finite(h.get("contracts")) or 1.0
        pnls.append(p - float(fill_tax) * max(1.0, contracts))
    n = len(pnls)
    if n <= 0:
        return {"n": 0, "expectancy_taxed": None, "hit_rate": None}
    hits = sum(1 for p in pnls if p > 0)
    return {
        "n": n,
        "expectancy_taxed": round(sum(pnls) / n, 4),
        "hit_rate": round(hits / n, 4),
    }


def tower_master_row(bot: dict, *, fill_tax: float = 0.01, cfg: dict | None = None) -> dict:
    """One tower's master metrics from snapshot bot view."""
    cfg = cfg or {}
    bot_id = str(bot.get("id") or "")
    hist = list(bot.get("history") or [])
    taxed = _taxed_expectancy(hist, fill_tax=fill_tax)
    open_risk = _finite(bot.get("open_risk")) or 0.0
    desk_cap = _finite(cfg.get("max_open_risk")) or 100.0
    shares = cfg.get("tower_risk_budgets") if isinstance(cfg.get("tower_risk_budgets"), dict) else {}
    share = _finite(shares.get(bot_id)) if shares else None
    tower_cap = round(desk_cap * share, 2) if share is not None else None
    util = None
    if tower_cap and tower_cap > 0:
        util = round(min(1.0, open_risk / tower_cap), 4)
    ga = bot.get("gate_a") if isinstance(bot.get("gate_a"), dict) else {}
    m1 = taxed.get("expectancy_taxed")
    m2 = taxed.get("hit_rate")
    n = int(taxed.get("n") or 0)
    ready_bits = {
        "M1": m1 is not None and m1 >= MASTER_BARS["M1_taxed_ev"] and n >= 5,
        "M2": m2 is not None and m2 >= MASTER_BARS["M2_hit_rate"] and n >= 10,
        "M6": bool(ga.get("ready")),
    }
    return {
        "bot": bot_id,
        "paper_only": True,
        "n_settles": n,
        "M1_taxed_ev": m1,
        "M2_hit_rate": m2,
        "M3_fit_buy": None,  # filled when skip/fit journals mature
        "M4_latency_s": None,
        "M5_tower_util": util,
        "M6_gate_a": bool(ga.get("ready")),
        "open_risk": round(open_risk, 2),
        "tower_cap": tower_cap,
        "today": bot.get("today"),
        "passing": ready_bits,
        "note": "M3/M4 stub until fit journals + latency timers land",
    }


def master_summary(
    root: str | None = None,
    *,
    bots: list | None = None,
    cfg: dict | None = None,
    fill_tax: float = 0.01,
) -> dict:
    """Desk-level Trading Masters board."""
    _ = root  # reserved for future journal paths
    cfg = cfg or {}
    rows = [tower_master_row(b, fill_tax=fill_tax, cfg=cfg) for b in (bots or []) if isinstance(b, dict)]
    desk_open = round(sum(float(r.get("open_risk") or 0) for r in rows), 2)
    desk_cap = _finite(cfg.get("max_open_risk")) or 100.0
    desk_util = round(desk_open / desk_cap, 4) if desk_cap else None
    m1_ready = sum(1 for r in rows if (r.get("passing") or {}).get("M1"))
    return {
        "paper_only": True,
        "version": MASTER_VERSION,
        "bars": dict(MASTER_BARS),
        "desk_open_risk": desk_open,
        "desk_cap": desk_cap,
        "M5_desk_util": desk_util,
        "towers_m1_pass": m1_ready,
        "towers": rows,
        "priority": [
            "memecoin stop-bleed before volume",
            "sports tip alarms",
            "feed idle BTC/commodity risk when gates clear",
        ],
        "note": (
            "Trading Masters stub — dual scoreboard for volume vs taxed EV. "
            "No profit guarantee. Fee floors unchanged."
        ),
    }


def self_check() -> None:
    row = tower_master_row(
        {
            "id": "sports-gap",
            "open_risk": 10,
            "history": [{"pnl": 2.0, "contracts": 1}, {"pnl": -1.0, "contracts": 1}] * 6,
            "gate_a": {"ready": False},
        },
        cfg={"max_open_risk": 100, "tower_risk_budgets": {"sports-gap": 0.35}},
    )
    assert row["n_settles"] == 12
    assert row["M1_taxed_ev"] is not None
    assert row["tower_cap"] == 35.0
    summary = master_summary(
        bots=[{"id": "memecoin", "open_risk": 5, "history": [], "gate_a": {}}],
        cfg={"max_open_risk": 100, "tower_risk_budgets": {"memecoin": 0.05}},
    )
    assert summary["version"] == MASTER_VERSION
    assert "towers" in summary


if __name__ == "__main__":
    self_check()
    print("desk_master self_check ok")
