"""
desk_brain.py — shared speed / accuracy / logic helpers for paper bots.

Decision loop: observe → score → rank → gate → size → fill → learn.
Paper only. No live orders.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Iterable

JOURNAL_NAME = "desk_brain_journal.json"
MAX_DECISIONS = 800
MAX_SUMMARY = 40


def journal_path(root: str | None = None) -> str:
    base = root or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, JOURNAL_NAME)


def _empty() -> dict:
    return {
        "paper_only": True,
        "version": 1,
        "decisions": [],
        "last_at": None,
        "by_bot": {},
        "gate_counts": {},
    }


def load_journal(root: str | None = None) -> dict:
    path = journal_path(root)
    if not os.path.exists(path):
        return _empty()
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            return _empty()
    except (OSError, json.JSONDecodeError):
        return _empty()
    base = _empty()
    base.update({k: data.get(k, base[k]) for k in base})
    if not isinstance(base.get("decisions"), list):
        base["decisions"] = []
    if not isinstance(base.get("by_bot"), dict):
        base["by_bot"] = {}
    if not isinstance(base.get("gate_counts"), dict):
        base["gate_counts"] = {}
    return base


def save_journal(state: dict, root: str | None = None) -> None:
    path = journal_path(root)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    decisions = list(state.get("decisions") or [])
    if len(decisions) > MAX_DECISIONS:
        decisions = decisions[-MAX_DECISIONS:]
    state = dict(state)
    state["decisions"] = decisions
    state["paper_only"] = True
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
        handle.write("\n")
    os.replace(tmp, path)


def opportunity_score(
    edge,
    confidence,
    depth=None,
    need: float = 10.0,
    series: str | None = None,
) -> float:
    """Higher = spend risk first.

    Phase 1: depth-adjusted edge × confidence
    (`edge × min(1, depth/need) × p`). Missing depth keeps raw edge.
    Vol prior (#471–472) raises effective need on high-σ series (NatGas).
    """
    try:
        import desk_more
        eff_need = desk_more.effective_depth_need(series, need)
        return desk_more.opportunity_score_v2(edge, confidence, depth, need=eff_need)
    except Exception:
        pass
    try:
        e = float(edge)
    except (TypeError, ValueError):
        e = 0.0
    try:
        c = float(confidence)
    except (TypeError, ValueError):
        c = 0.0
    score = max(0.0, e) * max(0.0, min(c, 1.0))
    if depth is not None:
        try:
            d = float(depth)
            if d > 0:
                score *= 1.0 + min(d, 50.0) / 200.0
        except (TypeError, ValueError):
            pass
    return round(score, 6)


def rank_candidates(rows: Iterable[dict], *, edge_key: str = "edge",
                    conf_key: str = "confidence", depth_key: str = "depth") -> list[dict]:
    """Sort candidates best opportunity first (stable on ticker)."""
    scored = []
    for i, row in enumerate(rows or []):
        if not isinstance(row, dict):
            continue
        item = dict(row)
        need = item.get("depth_need")
        try:
            need_f = float(need) if need is not None else 10.0
        except (TypeError, ValueError):
            need_f = 10.0
        item["_brain_score"] = opportunity_score(
            item.get(edge_key),
            item.get(conf_key),
            item.get(depth_key),
            need=need_f,
            series=item.get("series"),
        )
        item["_brain_i"] = i
        scored.append(item)
    scored.sort(key=lambda r: (-float(r.get("_brain_score") or 0), r.get("_brain_i", 0)))
    return scored


def rank_desk_queue(rows: Iterable[dict]) -> list[dict]:
    """Cross-tower rank: requires bot/ticker/side/edge/confidence; optional depth/stake_est."""
    ranked = rank_candidates(rows)
    out = []
    for i, row in enumerate(ranked):
        item = dict(row)
        item["_queue_rank"] = i + 1
        out.append(item)
    return out


def allocate_risk(ranked: Iterable[dict], remaining_risk: float) -> list[dict]:
    """Greedy accept while stake_est fits remaining open-risk budget."""
    try:
        left = float(remaining_risk)
    except (TypeError, ValueError):
        left = 0.0
    if left < 0:
        left = 0.0
    out = []
    for row in ranked or []:
        if not isinstance(row, dict):
            continue
        item = dict(row)
        try:
            stake = float(item.get("stake_est") if item.get("stake_est") is not None else item.get("stake") or 0)
        except (TypeError, ValueError):
            stake = 0.0
        if stake <= 0:
            item["queue_status"] = "deferred"
            item["queue_note"] = "missing stake_est"
            out.append(item)
            continue
        if stake <= left + 1e-9:
            item["queue_status"] = "accepted"
            item["queue_note"] = f"fits risk ({stake:.2f} of {left:.2f})"
            left = round(left - stake, 2)
        else:
            item["queue_status"] = "deferred"
            item["queue_note"] = f"open-risk full (need {stake:.2f}, left {left:.2f})"
        out.append(item)
    return out


def remember_queue(root: str | None, ranked: list[dict], *, note: str = "") -> None:
    """Persist latest global queue snapshot into the brain journal."""
    state = load_journal(root)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    slim = []
    for row in ranked[:40]:
        slim.append({
            "bot": row.get("bot"),
            "ticker": row.get("ticker"),
            "side": row.get("side"),
            "edge": row.get("edge"),
            "confidence": row.get("confidence"),
            "score": row.get("_brain_score"),
            "rank": row.get("_queue_rank"),
            "status": row.get("queue_status"),
            "stake_est": row.get("stake_est"),
        })
    state["global_queue"] = {"at": now, "note": (note or "")[:160], "rows": slim}
    state["last_at"] = now
    save_journal(state, root)


def cheap_gate_order(checks: list[tuple[str, bool, str]]) -> list[str]:
    """
    Run cheap boolean gates in order; return list of failure reasons.
    checks: (name, ok, reason_if_not_ok)
    """
    reasons = []
    for _name, ok, reason in checks:
        if not ok:
            reasons.append(reason)
    return reasons


def explain_buy(bot: str, side: str, ticker: str, edge, confidence, depth=None) -> str:
    parts = [
        f"Bought {side} {ticker}",
        f"edge={float(edge):.3f}" if edge is not None else "edge=?",
        f"p={float(confidence):.3f}" if confidence is not None else "p=?",
    ]
    if depth is not None:
        try:
            parts.append(f"depth={float(depth):.0f}")
        except (TypeError, ValueError):
            pass
    return f"{bot}: " + ", ".join(parts) + "."


def _journal_number(value, places, *, positive=False):
    """A real number already on the ticket. Missing or unreadable stays missing."""
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    if positive and number <= 0:
        return None
    return round(number, places)


def record_decision(
    root: str | None,
    *,
    bot: str,
    action: str,
    ticker: str = "",
    side: str = "",
    edge=None,
    confidence=None,
    depth=None,
    reasons: list | None = None,
    score=None,
    note: str = "",
    fill_id: str = "",
    bid=None,
    stake=None,
    exit_name: str = "",
    fee=None,
    cash=None,
) -> dict:
    """Append one observe/score/gate/buy/skip/close decision to the durable journal."""
    state = load_journal(root)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    row = {
        "at": now,
        "bot": bot,
        "action": action,  # buy | skip | flip | settle | sell | observe
        "ticker": ticker,
        "side": side,
        "edge": None if edge is None else round(float(edge), 4),
        "confidence": None if confidence is None else round(float(confidence), 4),
        "depth": None if depth is None else float(depth),
        "score": None if score is None else round(float(score), 6),
        "reasons": list(reasons or []),
        "note": note[:240],
    }
    fill = str(fill_id or "").strip()
    exit_label = str(exit_name or "").strip()
    if fill:
        row["fill_id"] = fill
    if exit_label:
        row["exit_name"] = exit_label[:120]
    bid_n = _journal_number(bid, 4, positive=True)
    if bid_n is not None:
        row["bid"] = bid_n
    stake_n = _journal_number(stake, 2)
    if stake_n is not None:
        row["stake"] = stake_n
    fee_n = _journal_number(fee, 4)
    if fee_n is not None:
        row["fee"] = fee_n
    cash_n = _journal_number(cash, 2)
    if cash_n is not None:
        row["cash"] = cash_n
    if fill and exit_label:
        for prev in state.get("decisions") or []:
            if (
                isinstance(prev, dict)
                and prev.get("bot") == bot
                and str(prev.get("fill_id") or "") == fill
                and str(prev.get("exit_name") or "") == exit_label
            ):
                return prev
    state.setdefault("decisions", []).append(row)
    state["last_at"] = now
    bot_row = state.setdefault("by_bot", {}).setdefault(
        bot, {"buys": 0, "skips": 0, "flips": 0, "last_at": None},
    )
    if action == "buy":
        bot_row["buys"] = int(bot_row.get("buys") or 0) + 1
    elif action == "skip":
        bot_row["skips"] = int(bot_row.get("skips") or 0) + 1
        for reason in reasons or []:
            key = str(reason).split(":")[0].strip()[:80] or "other"
            state.setdefault("gate_counts", {})
            state["gate_counts"][key] = int(state["gate_counts"].get(key) or 0) + 1
        # Phase 0: canonical skip codes + weekend attribution for staff board.
        try:
            import desk_more
            from datetime import datetime, timezone
            wd = datetime.now(timezone.utc).weekday()
            codes = desk_more.record_skip_codes(
                root, bot=bot, reasons=list(reasons or []), weekday=wd,
            )
            row["skip_codes"] = codes
        except Exception:
            pass
    elif action == "flip":
        bot_row["flips"] = int(bot_row.get("flips") or 0) + 1
    bot_row["last_at"] = now
    save_journal(state, root)
    return row


def brain_summary(root: str | None = None) -> dict:
    state = load_journal(root)
    decisions = list(state.get("decisions") or [])
    gate_counts = state.get("gate_counts") or {}
    top_gates = sorted(
        ((k, int(v)) for k, v in gate_counts.items()),
        key=lambda kv: -kv[1],
    )[:12]
    # Soft global queue: recent observe/buy decisions re-ranked across bots.
    cand = []
    for row in decisions[-120:]:
        if not isinstance(row, dict):
            continue
        if row.get("action") not in ("observe", "buy", "candidate"):
            continue
        if row.get("edge") is None and row.get("confidence") is None:
            continue
        cand.append({
            "bot": row.get("bot"),
            "ticker": row.get("ticker"),
            "side": row.get("side"),
            "edge": row.get("edge"),
            "confidence": row.get("confidence"),
            "depth": row.get("depth"),
            "stake_est": row.get("stake_est"),
            "at": row.get("at"),
        })
    queued = allocate_risk(rank_desk_queue(cand), remaining_risk=100.0)
    stored = state.get("global_queue") if isinstance(state.get("global_queue"), dict) else {}
    skip_board = {}
    try:
        import desk_more
        skip_board = desk_more.skip_leaderboard(root)
    except Exception:
        skip_board = {}
    return {
        "paper_only": True,
        "version": state.get("version", 1),
        "last_at": state.get("last_at"),
        "decision_count": len(decisions),
        "by_bot": state.get("by_bot") or {},
        "top_skip_gates": [{"gate": g, "n": n} for g, n in top_gates],
        "skip_leaderboard": skip_board,
        "recent": decisions[-MAX_SUMMARY:],
        "global_queue": stored.get("rows") or [
            {
                "bot": r.get("bot"),
                "ticker": r.get("ticker"),
                "side": r.get("side"),
                "score": r.get("_brain_score"),
                "rank": r.get("_queue_rank"),
                "status": r.get("queue_status"),
            }
            for r in queued[:20]
        ],
        "loop": ["observe", "score", "rank", "gate", "size", "fill", "learn"],
    }


def quote_fresh(age_sec, budget_sec: float) -> bool:
    """True when quote age is within budget (accuracy gate)."""
    try:
        age = float(age_sec)
        budget = float(budget_sec)
    except (TypeError, ValueError):
        return False
    if age < 0:
        return False
    return age <= budget


def self_check() -> None:
    rows = [
        {"ticker": "a", "edge": 0.04, "confidence": 0.9, "depth": 5},
        {"ticker": "b", "edge": 0.10, "confidence": 0.85, "depth": 20},
        {"ticker": "c", "edge": 0.10, "confidence": 0.85, "depth": 2},
    ]
    ranked = rank_candidates(rows)
    assert ranked[0]["ticker"] == "b"
    assert opportunity_score(0.1, 0.8) == round(0.1 * 0.8, 6)
    assert quote_fresh(3, 5) is True
    assert quote_fresh(9, 5) is False
    reasons = cheap_gate_order([
        ("time", False, "too late"),
        ("band", True, "ask bad"),
    ])
    assert reasons == ["too late"]
    q = rank_desk_queue([
        {"bot": "btc15m", "ticker": "t1", "edge": 0.08, "confidence": 0.9, "stake_est": 40},
        {"bot": "sports-gap", "ticker": "t2", "edge": 0.12, "confidence": 0.85, "stake_est": 30},
    ])
    assert q[0]["_queue_rank"] == 1
    alloc = allocate_risk(q, 50)
    accepted = [r for r in alloc if r.get("queue_status") == "accepted"]
    assert len(accepted) >= 1


if __name__ == "__main__":
    self_check()
    print("desk_brain self_check ok")
