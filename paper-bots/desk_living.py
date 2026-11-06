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


def living_upgrade_board(root: str | None = None) -> dict:
    """Masters card: data + completions health for the living upgrade."""
    feat = feature_store_coverage(root)
    comp = completions_summary(root)
    return {
        "paper_only": True,
        "feature_store": feat,
        "completions": comp,
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
