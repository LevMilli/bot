"""
E8 remaining insight digests — observe-only pack (#829–880 leftovers).

Each digest wraps existing desk_* boards. Never places fills. Never softens
floors. Never LIVE / tip invent. may_place_alone=False forever here.
"""
from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone
from typing import Any, Callable

from helpers import HELPER_ONLY, PAPER_ONLY, assert_helper_only

DESK_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _finite(x):
    try:
        n = float(x)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(n):
        return None
    return n


def _write(path: str, digest: dict) -> dict:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(digest, handle, indent=2, sort_keys=True, default=str)
        handle.write("\n")
    os.replace(tmp, path)
    return digest


def _base(helper: str, note: str, *, now: datetime | None = None, **fields: Any) -> dict:
    assert_helper_only(helper)
    assert PAPER_ONLY and HELPER_ONLY
    now = now or datetime.now(timezone.utc)
    out = {
        "helper": helper,
        "at": now.isoformat(),
        "paper_only": True,
        "may_place_alone": False,
        "floors_locked": True,
        "note": note,
    }
    out.update(fields)
    return out


def digest_path_for(helper: str, root: str | None = None) -> str:
    return os.path.join(root or DESK_ROOT, "helpers", f"{helper}_digest.json")


# ---- builders (payload from desk; never invent marks) ----------------------

def build_inx_dual_ev_lab(payload: dict | None = None, *, now=None) -> dict:
    p = payload if isinstance(payload, dict) else {}
    return _base(
        "inx_dual_ev_lab",
        "Observe-only INX dual-EV lab (Φ fair vs residual). Never softens kalshi_inx 0.02.",
        now=now,
        fair_best=p.get("fair_best"),
        residual_best=p.get("residual_best"),
        agree=p.get("agree"),
        n_candidates=p.get("n_candidates"),
        thin=bool(p.get("thin", True)),
        band=p.get("band") or [0.80, 0.92],
    )


def build_meme_rug_auditor(payload: dict | None = None, *, now=None) -> dict:
    p = payload if isinstance(payload, dict) else {}
    return _base(
        "meme_rug_auditor",
        "Observe-only meme rug auditor. Never opens desk cash; floors locked.",
        now=now,
        scanned=p.get("scanned"),
        facts_pass=p.get("facts_pass"),
        confidence_ge=p.get("confidence_ge"),
        entries=p.get("entries"),
        open_n=p.get("open_n"),
        thin=bool(p.get("thin", True)),
    )


def build_meme_liq_cliff(payload: dict | None = None, *, now=None) -> dict:
    p = payload if isinstance(payload, dict) else {}
    return _base(
        "meme_liq_cliff",
        "Observe-only meme liquidity cliff. Never softens meme floors.",
        now=now,
        open_n=p.get("open_n"),
        min_liq_usd=p.get("min_liq_usd"),
        cliff_hits=p.get("cliff_hits"),
        thin=bool(p.get("thin", True)),
    )


def build_opp_cost_clock(payload: dict | None = None, *, now=None) -> dict:
    p = payload if isinstance(payload, dict) else {}
    return _base(
        "opp_cost_clock",
        "Observe-only opp-cost clock. Rank fee-clear; never soften floors.",
        now=now,
        n=p.get("n"),
        bar_sec=p.get("bar_sec"),
        mean_wait_s=p.get("mean_wait_s"),
        max_wait_s=p.get("max_wait_s"),
        recent=(p.get("recent") or [])[:8],
    )


def build_fee_ledger_nag(payload: dict | None = None, *, now=None) -> dict:
    p = payload if isinstance(payload, dict) else {}
    return _base(
        "fee_ledger_nag",
        "Observe-only fee-ledger nag. Completeness for true ROI — never invent fees.",
        now=now,
        hist_n=p.get("hist_n") if p.get("hist_n") is not None else p.get("n"),
        matched=p.get("matched"),
        completeness=p.get("completeness") or p.get("rate"),
        missing_n=len(p.get("missing") or []) if isinstance(p.get("missing"), list) else p.get("missing_n"),
        fee_sum=(p.get("summary") or {}).get("fee_sum") if isinstance(p.get("summary"), dict) else p.get("fee_sum"),
    )


def build_masters_canary(payload: dict | None = None, *, now=None) -> dict:
    p = payload if isinstance(payload, dict) else {}
    return _base(
        "masters_canary",
        "Observe-only Masters M1 canary. Never auto-arms; floors locked.",
        now=now,
        m1=p.get("m1"),
        m1_n=p.get("m1_n"),
        m1_holds=p.get("m1_holds"),
        week_pnl=p.get("week_pnl"),
        alarm=p.get("alarm"),
        label=p.get("label"),
    )


def build_hillclimb_watchdog(payload: dict | None = None, *, now=None) -> dict:
    p = payload if isinstance(payload, dict) else {}
    kill = p.get("kill") if isinstance(p.get("kill"), dict) else {}
    lever = p.get("lever") if isinstance(p.get("lever"), dict) else {}
    return _base(
        "hillclimb_watchdog",
        "Observe-only hillclimb watchdog. Kill/revert is staff — never auto-LIVE.",
        now=now,
        kill_recommend=kill.get("recommend") or kill.get("kill") or kill.get("decision"),
        active_lever=lever.get("lever") or lever.get("active_lever") or lever.get("id"),
        weeks_n=kill.get("weeks_n") or lever.get("weeks_n"),
        label=kill.get("label") or lever.get("label"),
    )


def build_stale_skew_watchdog(payload: dict | None = None, *, now=None) -> dict:
    p = payload if isinstance(payload, dict) else {}
    return _base(
        "stale_skew_watchdog",
        "Observe-only stale/skew watchdog. Exits still run; never soften floors.",
        now=now,
        blocked=p.get("blocked") or [],
        blocked_n=len(p.get("blocked") or []),
        clock_skew_max_s=p.get("clock_skew_max_s"),
        rows=(p.get("rows") or [])[:12],
    )


def build_misplaced_publisher(payload: dict | None = None, *, now=None) -> dict:
    p = payload if isinstance(payload, dict) else {}
    return _base(
        "misplaced_publisher",
        "Observe-only capital-misplaced publisher. Recycle to fee-clear; floors locked.",
        now=now,
        misplaced_usd=p.get("misplaced_usd"),
        share_of_cap=p.get("share_of_cap"),
        rows=(p.get("rows") or [])[:12],
    )


def build_selective_eligibility(payload: dict | None = None, *, now=None) -> dict:
    p = payload if isinstance(payload, dict) else {}
    return _base(
        "selective_eligibility",
        "Observe-only selective eligibility. +1 only on fee-clear greens after M1; never soften.",
        now=now,
        m1_holds=p.get("m1_holds"),
        m1=p.get("m1"),
        boosted_n=p.get("boosted_n"),
        towers=(p.get("towers") or [])[:12],
        label=p.get("label"),
    )


def build_green_boost_readiness(payload: dict | None = None, *, now=None) -> dict:
    p = payload if isinstance(payload, dict) else {}
    return _base(
        "green_boost_readiness",
        "Observe-only sports green_boost readiness. Staff arm only; never auto.",
        now=now,
        ready=p.get("ready"),
        green_boost=p.get("green_boost"),
        sports_m1=p.get("sports_exp") or p.get("sports_m1"),
        clv_ok=p.get("clv_ok"),
        weeks_ok=p.get("weeks_ok"),
        label=p.get("label"),
    )


def build_daily_r_clerk(payload: dict | None = None, *, now=None) -> dict:
    p = payload if isinstance(payload, dict) else {}
    return _base(
        "daily_r_clerk",
        "Observe-only daily R clerk. Budget observe — never invent PnL.",
        now=now,
        board=p.get("board") or p,
        label=p.get("label"),
    )


def build_profit_lock_clerk(payload: dict | None = None, *, now=None) -> dict:
    p = payload if isinstance(payload, dict) else {}
    latest = p.get("latest") if isinstance(p.get("latest"), dict) else p
    return _base(
        "profit_lock_clerk",
        "Observe-only profit-lock clerk. Safe-mode size mult — never LIVE.",
        now=now,
        week_pnl=latest.get("week_pnl"),
        size_mult=latest.get("size_mult"),
        safe_mode=latest.get("safe_mode"),
        target_usd=latest.get("target_usd"),
        label=latest.get("label") or latest.get("week"),
    )


def build_barbell_clerk(payload: dict | None = None, *, now=None) -> dict:
    p = payload if isinstance(payload, dict) else {}
    out = _base(
        "barbell_clerk",
        "Observe-only barbell clerk. Meme≤15% cap / fee-clear≥70% open — floors locked.",
        now=now,
        meme_of_cap=p.get("meme_of_cap"),
        fee_clear_of_open=p.get("fee_clear_of_open"),
        meme_ok=p.get("meme_ok"),
        fee_clear_ok=p.get("fee_clear_ok"),
    )
    out["pass"] = p.get("pass")
    return out


def build_corr_clerk(payload: dict | None = None, *, now=None) -> dict:
    p = payload if isinstance(payload, dict) else {}
    return _base(
        "corr_clerk",
        "Observe-only correlation clerk. Haircuts observe-only — never soften floors.",
        now=now,
        pairs=(p.get("pairs") or p.get("matrix") or p.get("rows") or [])[:16],
        n=p.get("n"),
        note_src=p.get("note"),
    )


def build_incubation_registrar(payload: dict | None = None, *, now=None) -> dict:
    p = payload if isinstance(payload, dict) else {}
    return _base(
        "incubation_registrar",
        "Observe-only incubation registrar. Staff graduate only after n≥50; never auto.",
        now=now,
        incubating_n=p.get("incubating_n"),
        ready_n=p.get("ready_n"),
        graduated=(p.get("graduated") or [])[:12],
        min_n=p.get("min_n"),
        rows=(p.get("rows") or [])[:12],
    )


def build_shadow_edge08_clerk(payload: dict | None = None, *, now=None) -> dict:
    p = payload if isinstance(payload, dict) else {}
    return _base(
        "shadow_edge08_clerk",
        "Observe-only BTC edge08 shadow clerk. Never force-arm; floors locked at 0.08 variant.",
        now=now,
        n=p.get("n"),
        n_to_promote=p.get("n_to_promote"),
        expectancy=p.get("expectancy"),
        promote_ready=p.get("promote_ready"),
        evidence_thin=p.get("evidence_thin"),
        label=p.get("label") or p.get("decision"),
    )


def build_skip_regret_clerk(payload: dict | None = None, *, now=None) -> dict:
    p = payload if isinstance(payload, dict) else {}
    return _base(
        "skip_regret_clerk",
        "Observe-only skip-regret clerk. Fee forever out of regret candidates.",
        now=now,
        n=p.get("n") or len(p.get("candidates") or []),
        candidates=(p.get("candidates") or [])[:12],
        label=p.get("label") or p.get("note"),
    )


def build_ruin_drill_proctor(payload: dict | None = None, *, now=None) -> dict:
    p = payload if isinstance(payload, dict) else {}
    return _base(
        "ruin_drill_proctor",
        "Observe-only ruin-drill proctor. Staff drill only — never invent flatten.",
        now=now,
        active=p.get("active"),
        level=p.get("level"),
        block_entries=p.get("block_entries"),
        pause_all_bots=p.get("pause_all_bots"),
        flatten_recommended=p.get("flatten_recommended"),
        who=p.get("who"),
    )


BUILDERS: dict[str, Callable[..., dict]] = {
    "inx_dual_ev_lab": build_inx_dual_ev_lab,
    "meme_rug_auditor": build_meme_rug_auditor,
    "meme_liq_cliff": build_meme_liq_cliff,
    "opp_cost_clock": build_opp_cost_clock,
    "fee_ledger_nag": build_fee_ledger_nag,
    "masters_canary": build_masters_canary,
    "hillclimb_watchdog": build_hillclimb_watchdog,
    "stale_skew_watchdog": build_stale_skew_watchdog,
    "misplaced_publisher": build_misplaced_publisher,
    "selective_eligibility": build_selective_eligibility,
    "green_boost_readiness": build_green_boost_readiness,
    "daily_r_clerk": build_daily_r_clerk,
    "profit_lock_clerk": build_profit_lock_clerk,
    "barbell_clerk": build_barbell_clerk,
    "corr_clerk": build_corr_clerk,
    "incubation_registrar": build_incubation_registrar,
    "shadow_edge08_clerk": build_shadow_edge08_clerk,
    "skip_regret_clerk": build_skip_regret_clerk,
    "ruin_drill_proctor": build_ruin_drill_proctor,
}

HELPER_NAMES = tuple(BUILDERS.keys())


def _load_inx_dual_ev(root: str) -> dict:
    """Score fair vs residual on feature asks in band — never invent strikes."""
    import desk_inx

    path = os.path.join(root, "desk_feature_store.jsonl")
    cands = []
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as handle:
                for i, line in enumerate(handle):
                    if i >= 8000:
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
                    series = str(row.get("series") or "").upper()
                    if not series.startswith("KXINXU"):
                        continue
                    ask = _finite(row.get("ask") or row.get("yes_ask_dollars") or row.get("yes_ask"))
                    if ask is None:
                        continue
                    if ask > 1.0:
                        ask = ask / 100.0
                    if not (0.80 - 1e-12 <= ask <= 0.92 + 1e-12):
                        continue
                    cands.append({
                        "ticker": str(row.get("ticker") or "")[:48],
                        "ask": ask,
                        "side": str(row.get("side") or "yes"),
                        "strike": row.get("strike"),
                        "model_p": row.get("model_p"),
                    })
        except OSError:
            cands = []
    residual = desk_inx.dual_side_pick(cands, band_lo=0.80, band_hi=0.92)
    fair_best = None
    fair_edge = None
    for c in cands:
        p = _finite(c.get("model_p"))
        ask = _finite(c.get("ask"))
        if p is None or ask is None:
            continue
        fee = desk_inx.taker_fee_one(ask)
        edge = p - ask - fee
        if fair_edge is None or edge > fair_edge:
            fair_edge = edge
            fair_best = {**c, "fair_edge": round(edge, 4), "fee": fee}
    agree = None
    if fair_best and residual:
        agree = str(fair_best.get("ticker") or "") == str(residual.get("ticker") or "")
    return {
        "fair_best": fair_best,
        "residual_best": residual,
        "agree": agree,
        "n_candidates": len(cands),
        "thin": len(cands) < 3,
        "band": [0.80, 0.92],
    }


def _load_meme(root: str) -> tuple[dict, dict]:
    pos_path = os.path.join(root, "memecoin-paper", "positions.json")
    open_n = 0
    if os.path.isfile(pos_path):
        try:
            with open(pos_path, encoding="utf-8") as handle:
                blob = json.load(handle)
            open_n = len(blob.get("open") or []) if isinstance(blob, dict) else 0
        except (OSError, json.JSONDecodeError):
            open_n = 0
    # Feature-store densify rows for memecoin when present.
    scanned = facts = conf = entries = cliff = 0
    path = os.path.join(root, "desk_feature_store.jsonl")
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as handle:
                for i, line in enumerate(handle):
                    if i >= 6000:
                        break
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(row, dict):
                        continue
                    if str(row.get("bot") or "").lower() not in ("memecoin", "meme"):
                        continue
                    scanned += 1
                    if row.get("facts_pass") or "facts" in str(row.get("note") or "").lower():
                        facts += 1
                    if _finite(row.get("confidence")) is not None and float(row["confidence"]) >= 0.8:
                        conf += 1
                    if str(row.get("action") or "") in ("buy", "entry", "fill"):
                        entries += 1
                    liq = _finite(row.get("liquidity") or row.get("liq_usd"))
                    if liq is not None and liq < 25000:
                        cliff += 1
        except OSError:
            pass
    rug = {
        "scanned": scanned,
        "facts_pass": facts,
        "confidence_ge": conf,
        "entries": entries,
        "open_n": open_n,
        "thin": scanned < 5 and open_n == 0,
    }
    liq = {
        "open_n": open_n,
        "min_liq_usd": 25000,
        "cliff_hits": cliff,
        "thin": scanned < 5 and open_n == 0,
    }
    return rug, liq


def _load_payload(helper: str, root: str, bots: list | None = None) -> dict:
    import desk_roi_plan

    if helper == "inx_dual_ev_lab":
        return _load_inx_dual_ev(root)
    if helper == "meme_rug_auditor":
        rug, _ = _load_meme(root)
        return rug
    if helper == "meme_liq_cliff":
        _, liq = _load_meme(root)
        return liq
    if helper == "opp_cost_clock":
        return desk_roi_plan.opp_cost_summary(root) or {}
    if helper == "fee_ledger_nag":
        comp = desk_roi_plan.fee_ledger_completeness(root, bots=bots) or {}
        summary = desk_roi_plan.fee_ledger_summary(root) or {}
        out = dict(comp) if isinstance(comp, dict) else {}
        out["summary"] = summary
        return out
    if helper == "masters_canary":
        m1 = desk_roi_plan.firm_taxed_m1(bots) or {}
        exp = _finite(m1.get("expectancy_taxed"))
        n = int(m1.get("n") or 0)
        holds = n >= 10 and exp is not None and exp + 1e-12 >= 0.0
        pl = desk_roi_plan.profit_lock_status(root) or {}
        latest = pl.get("latest") if isinstance(pl.get("latest"), dict) else {}
        week_pnl = _finite(latest.get("week_pnl"))
        alarm = (exp is not None and exp < 0) or (week_pnl is not None and week_pnl < 0 and n >= 10)
        return {
            "m1": exp,
            "m1_n": n,
            "m1_holds": holds,
            "week_pnl": week_pnl,
            "alarm": bool(alarm),
            "label": f"canary m1={exp} n={n} holds={holds} alarm={bool(alarm)}",
        }
    if helper == "hillclimb_watchdog":
        return {
            "kill": desk_roi_plan.hillclimb_kill_status(root) or {},
            "lever": desk_roi_plan.hillclimb_lever_status(root) or {},
        }
    if helper == "stale_skew_watchdog":
        return desk_roi_plan.stale_world_status(root, bots=bots) or {}
    if helper == "misplaced_publisher":
        return desk_roi_plan.capital_misplaced(bots) or {}
    if helper == "selective_eligibility":
        return desk_roi_plan.selective_throughput_observe(root, bots=bots) or {}
    if helper == "green_boost_readiness":
        return desk_roi_plan.sports_green_boost_status(root, bots=bots) or {}
    if helper == "daily_r_clerk":
        board = desk_roi_plan.latest_daily_r_board(root)
        if not isinstance(board, dict):
            board = {"label": "no daily_r board yet", "thin": True}
        return {"board": board, "label": board.get("label")}
    if helper == "profit_lock_clerk":
        return desk_roi_plan.profit_lock_status(root) or {}
    if helper == "barbell_clerk":
        return desk_roi_plan.barbell_status(bots) or {}
    if helper == "corr_clerk":
        try:
            import desk_profit
            return desk_profit.correlation_matrix(bots) or {}
        except Exception:
            return {"n": 0, "pairs": [], "thin": True}
    if helper == "incubation_registrar":
        return desk_roi_plan.incubation_board(root) or {}
    if helper == "shadow_edge08_clerk":
        return desk_roi_plan.btc_edge08_shadow_status(root) or {}
    if helper == "skip_regret_clerk":
        return desk_roi_plan.skip_regret_candidates(root) or {}
    if helper == "ruin_drill_proctor":
        return desk_roi_plan.ruin_drill_status(root) or {}
    return {}


def write_digest_from_desk(
    helper: str,
    root: str | None = None,
    *,
    bots: list | None = None,
) -> dict:
    if helper not in BUILDERS:
        raise KeyError(helper)
    root = root or DESK_ROOT
    payload = _load_payload(helper, root, bots=bots)
    digest = BUILDERS[helper](payload)
    return _write(digest_path_for(helper, root), digest)


def chip_from_digest(helper: str, digest: dict | None) -> dict:
    d = digest if isinstance(digest, dict) else {}
    label = d.get("label")
    if not label:
        # compact label from a few known keys
        bits = [helper.replace("_", " ")]
        for k in (
            "occupancy", "m1_holds", "ready", "promote_ready", "active",
            "pass_", "alarm", "n", "blocked_n", "misplaced_usd", "thin",
        ):
            if d.get(k) is not None:
                bits.append(f"{k}={d.get(k)}")
        label = " ".join(bits)[:160]
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "may_place_alone": False,
        "helper": helper,
        "label": label,
        "digest": {k: d.get(k) for k in list(d) if k not in ("note",)},
        "note": d.get("note") or f"Observe-only {helper} — never LIVE.",
    }
