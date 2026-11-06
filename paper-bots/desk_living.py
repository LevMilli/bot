"""
desk_living.py — Living Trading Upgrade spine (paper only).

Feature-store rows, CompletedEligibleFills, Chicago-day helpers, CLI entry_gate honor.
Never softens venue min_edge floors. No live orders. No profit guarantee.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

CT = ZoneInfo("America/Chicago")
FEATURE_STORE_NAME = "desk_feature_store.jsonl"
COMPLETIONS_NAME = "desk_completions.json"
MAX_FEATURE_ROWS_READ = 5000
MAX_COMPLETION_ROWS = 2000
FEE_CLEAR = frozenset({"sports-gap", "btc15m", "commodity-15m"})
BETTING_TOWERS = (
    "sports-gap",
    "btc15m",
    "commodity-15m",
    "memecoin",
    "kalshi-sp",
    "kalshi-sized",
)
INSIGHT_HELPER_DIGESTS = (
    "tip_radar_digest.json",
    "skip_historian_digest.json",
    "timer_heartbeat_digest.json",
    "empty_card_bee_digest.json",
    "clv_closer_digest.json",
    "injury_wire_digest.json",
    "eia_scout_digest.json",
    "calib_nag_digest.json",
    "hard_stop_clerk_digest.json",
    "near_miss_clerk_digest.json",
    "bleed_clerk_digest.json",
    "distance_clerk_digest.json",
    "bookkeeper_clerk_digest.json",
    "reporter_clerk_digest.json",
    "quant_clerk_digest.json",
    "skip_twin_clerk_digest.json",
    "calendar_digest.json",
)
INSIGHT_BETTING_MIN_RATIO = 3.0


def _root(root: str | None = None) -> str:
    return root or os.path.dirname(os.path.abspath(__file__))


def chicago_today(now: datetime | None = None):
    """America/Chicago calendar date (living upgrade P0 — never host TZ)."""
    now = now or datetime.now(CT)
    if now.tzinfo is None:
        now = now.replace(tzinfo=CT)
    return now.astimezone(CT).date()


def chicago_today_iso(now: datetime | None = None) -> str:
    return chicago_today(now).isoformat()


def honor_desk_entry_gate(root: str | None = None) -> str:
    """CLI/standalone bots: if desk entry_gate would block, set DESK_BLOCK_ENTRIES=1.

    Returns the block reason (empty if entries allowed). Exits still run when blocked.
    """
    if os.environ.get("DESK_BLOCK_ENTRIES") == "1":
        return os.environ.get("DESK_BLOCK_REASON") or "DESK_BLOCK_ENTRIES=1"
    try:
        import pimp_desk
        reason = pimp_desk.entry_gate(root or _root())
    except Exception as exc:
        return ""  # fail-open on desk import only — timer path still authoritative
    if reason:
        os.environ["DESK_BLOCK_ENTRIES"] = "1"
        os.environ["DESK_BLOCK_REASON"] = str(reason)[:240]
        return str(reason)
    return ""


def feature_store_path(root: str | None = None) -> str:
    return os.path.join(_root(root), FEATURE_STORE_NAME)


def record_decision_features(
    root: str | None = None,
    *,
    bot: str,
    action: str,
    series: str = "",
    side: str = "",
    ask=None,
    bid=None,
    fee=None,
    model_p=None,
    z=None,
    edge=None,
    depth=None,
    skip_codes: list | None = None,
    fill_id: str = "",
    note: str = "",
    extra: dict | None = None,
) -> dict:
    """Append one decision feature row (buy or skip). Paper only."""
    row = {
        "at": datetime.now(CT).isoformat(timespec="seconds"),
        "chicago_day": chicago_today_iso(),
        "bot": str(bot or "")[:40],
        "action": str(action or "skip")[:20],
        "series": str(series or "")[:40],
        "side": str(side or "")[:20],
        "ask": _f(ask),
        "bid": _f(bid),
        "fee": _f(fee),
        "model_p": _f(model_p),
        "z": _f(z),
        "edge": _f(edge),
        "depth": _f(depth),
        "skip_codes": [str(c)[:40] for c in (skip_codes or [])][:12],
        "fill_id": str(fill_id or "")[:80],
        "note": str(note or "")[:160],
        "paper_only": True,
        "fee_floors_locked": True,
    }
    if isinstance(extra, dict):
        for k, v in list(extra.items())[:12]:
            if k in row:
                continue
            row[str(k)[:40]] = v if isinstance(v, (str, int, float, bool)) or v is None else str(v)[:80]
    path = feature_store_path(root)
    try:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, default=str) + "\n")
    except OSError:
        return {"recorded": False, "row": row}
    return {"recorded": True, "row": row}


def record_eval_features(
    root: str | None = None,
    *,
    bot: str,
    action: str,
    ev: dict | None = None,
    ticker: str = "",
    series: str = "",
    reasons: list | None = None,
    note: str = "",
) -> dict:
    """Convenience: map an evaluate/candidate dict into a feature-store row."""
    ev = ev if isinstance(ev, dict) else {}
    codes = []
    for r in reasons or ev.get("reasons") or []:
        codes.append(str(r)[:40])
    return record_decision_features(
        root,
        bot=bot,
        action=action,
        series=series or str(ev.get("series") or "")[:40],
        side=str(ev.get("side") or "")[:20],
        ask=ev.get("ask"),
        bid=ev.get("bid"),
        fee=ev.get("fee"),
        model_p=ev.get("p") if ev.get("p") is not None else ev.get("model_p") or ev.get("confidence"),
        z=ev.get("z"),
        edge=ev.get("edge") if ev.get("edge") is not None else ev.get("gap"),
        depth=ev.get("depth"),
        skip_codes=codes,
        fill_id=str(ev.get("fill_id") or ticker or ev.get("ticker") or "")[:80],
        note=note or "; ".join(codes)[:160],
        extra={
            "ticker": str(ticker or ev.get("ticker") or "")[:80],
            "lane": str(ev.get("lane") or "")[:20],
            "minutes_left": _f(ev.get("min_left") if ev.get("min_left") is not None else ev.get("minutes_left")),
        },
    )


def feature_store_coverage(root: str | None = None, *, limit: int = MAX_FEATURE_ROWS_READ) -> dict:
    path = feature_store_path(root)
    n = 0
    buys = 0
    skips = 0
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as handle:
                for i, line in enumerate(handle):
                    if i >= int(limit):
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
                    n += 1
                    act = str(row.get("action") or "").lower()
                    if act == "buy":
                        buys += 1
                    else:
                        skips += 1
        except OSError:
            pass
    return {
        "paper_only": True,
        "n": n,
        "buys": buys,
        "skips": skips,
        "path": os.path.basename(path),
        "fee_floors_locked": True,
        "note": "Decision feature store for living AI learning. Floors locked.",
    }


def completions_path(root: str | None = None) -> str:
    return os.path.join(_root(root), COMPLETIONS_NAME)


def record_completion(
    root: str | None = None,
    *,
    bot: str,
    ticker: str = "",
    side: str = "",
    pnl=None,
    contracts=None,
    fill_id: str = "",
    kind: str = "close",
    eligible: bool = True,
    note: str = "",
) -> dict:
    """Record a completed fee-clear (or other) paper close for Completions KPI."""
    path = completions_path(root)
    store = _load_json(path, {"paper_only": True, "rows": [], "by_day": {}})
    day = chicago_today_iso()
    row = {
        "at": datetime.now(CT).isoformat(timespec="seconds"),
        "chicago_day": day,
        "bot": str(bot or "")[:40],
        "ticker": str(ticker or "")[:80],
        "side": str(side or "")[:20],
        "pnl": _f(pnl),
        "contracts": _f(contracts),
        "fill_id": str(fill_id or "")[:80],
        "kind": str(kind or "close")[:40],
        "eligible": bool(eligible) and str(bot) in FEE_CLEAR,
        "fee_clear": str(bot) in FEE_CLEAR,
        "note": str(note or "")[:160],
        "paper_only": True,
        "fee_floors_locked": True,
    }
    rows = list(store.get("rows") or [])
    rows.append(row)
    store["rows"] = rows[-MAX_COMPLETION_ROWS:]
    by_day = store.get("by_day") if isinstance(store.get("by_day"), dict) else {}
    day_rows = list(by_day.get(day) or [])
    day_rows.append(row)
    by_day[day] = day_rows[-500:]
    store["by_day"] = by_day
    store["last_at"] = row["at"]
    _save_json(path, store)
    return {"recorded": True, "row": row}


def completions_summary(root: str | None = None, *, day: str | None = None) -> dict:
    path = completions_path(root)
    store = _load_json(path, {"paper_only": True, "rows": [], "by_day": {}})
    day = day or chicago_today_iso()
    by_day = store.get("by_day") if isinstance(store.get("by_day"), dict) else {}
    today_rows = [r for r in (by_day.get(day) or []) if isinstance(r, dict)]
    eligible = [r for r in today_rows if r.get("eligible")]
    pnl_sum = round(sum(float(_f(r.get("pnl")) or 0) for r in eligible), 4)
    return {
        "paper_only": True,
        "chicago_day": day,
        "completions_today": len(today_rows),
        "eligible_completions_today": len(eligible),
        "eligible_pnl_today": pnl_sum,
        "fee_clear_towers": sorted(FEE_CLEAR),
        "fee_floors_locked": True,
        "note": (
            "CompletedEligibleFills = fee-clear closes today. "
            "Optimize with M1 guardrail — never softer floors."
        ),
    }


def living_ai_health(root: str | None = None, bots: list | None = None) -> dict:
    """Masters AI health: adapt snapshot + calib raise_phi tickets across fee-clear."""
    adapt = {}
    try:
        import desk_adapt
        adapt = desk_adapt.adapt_summary(root) or {}
    except Exception:
        adapt = {}
    boards = {}
    raise_phi = []
    try:
        import desk_roi_plan
        for name, latest_fn, report_fn in (
            ("btc", desk_roi_plan.latest_btc_calibration, desk_roi_plan.btc_calibration_report),
            ("sports", desk_roi_plan.latest_sports_calibration, desk_roi_plan.sports_calibration_report),
            ("commodity", desk_roi_plan.latest_commodity_calibration, desk_roi_plan.commodity_calibration_report),
        ):
            card = None
            try:
                card = latest_fn(root)
            except Exception:
                card = None
            if not isinstance(card, dict):
                try:
                    card = report_fn(bots)
                except Exception:
                    card = {}
            boards[name] = {
                "action": (card or {}).get("action"),
                "miscalibrated": bool((card or {}).get("miscalibrated")),
                "hi_n": (card or {}).get("hi_n"),
                "hi_hit_rate": (card or {}).get("hi_hit_rate"),
            }
            if str((card or {}).get("action") or "") == "raise_phi":
                raise_phi.append(name)
    except Exception:
        boards = {}
        raise_phi = []
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "grok_buys": False,
        "adapt_version": adapt.get("version"),
        "adapt_bots_n": len(adapt.get("by_bot") or {}),
        "adapt_recent_vol_n": len(adapt.get("recent_vol") or []),
        "calib_boards": boards,
        "raise_phi_tickets": raise_phi,
        "raise_phi_n": len(raise_phi),
        "auto_write_phi": False,
        "note": (
            "Living AI health — Wilson adapt + calib raise_Φ tickets. "
            "Staff dual-control only; never silent Φ write; never softer floors."
        ),
    }


def insight_swarm_ratio(root: str | None = None) -> dict:
    """Insight:betting headcount audit — living hire order requires ≥3:1 until M1≥0."""
    helpers = {}
    for name in INSIGHT_HELPER_DIGESTS:
        path = os.path.join(_root(root), "helpers", name)
        key = name.replace("_digest.json", "").replace(".json", "")
        helpers[key] = os.path.isfile(path)
    insight_n = sum(1 for v in helpers.values() if v)
    betting_n = len(BETTING_TOWERS)
    ratio = round(insight_n / betting_n, 4) if betting_n else None
    ok = bool(ratio is not None and ratio + 1e-12 >= INSIGHT_BETTING_MIN_RATIO)
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "insight_n": insight_n,
        "betting_n": betting_n,
        "ratio": ratio,
        "min_ratio": INSIGHT_BETTING_MIN_RATIO,
        "pass": ok,
        "insight_helpers": helpers,
        "betting_towers": list(BETTING_TOWERS),
        "note": (
            "Insight swarm ≥3:1 vs betting towers until firm M1 ≥ 0. "
            "Hire observe-only clerks first — never meme/INX spam."
            if not ok
            else "Insight:betting headcount meets ≥3:1 living hire order. Floors locked."
        ),
    }


def living_upgrade_board(root: str | None = None, bots: list | None = None) -> dict:
    """Masters card: data + completions health for the living upgrade."""
    feat = feature_store_coverage(root)
    comp = completions_summary(root)
    ai = living_ai_health(root, bots=bots)
    swarm = insight_swarm_ratio(root)
    helpers = swarm.get("insight_helpers") or {}
    return {
        "paper_only": True,
        "feature_store": feat,
        "completions": comp,
        "living_ai": ai,
        "insight_swarm": swarm,
        "insight_helper_digests": helpers,
        "insight_helpers_present": int(swarm.get("insight_n") or 0),
        "chicago_today": chicago_today_iso(),
        "fee_floors_locked": True,
        "insight_first": True,
        "grok_buys": False,
        "note": "Living Trading Upgrade board — more eligible completions + learn data.",
    }


def _f(v: Any):
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _load_json(path: str, default: dict) -> dict:
    if not os.path.isfile(path):
        return dict(default)
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else dict(default)
    except (OSError, json.JSONDecodeError):
        return dict(default)


def _save_json(path: str, data: dict) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)


if __name__ == "__main__":
    assert chicago_today_iso()
    print("desk_living self_check ok", living_upgrade_board())
