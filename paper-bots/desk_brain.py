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


def opportunity_score(edge, confidence, depth=None) -> float:
    """Higher = spend risk first. Depth soft-boosts when present."""
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
        item["_brain_score"] = opportunity_score(
            item.get(edge_key), item.get(conf_key), item.get(depth_key),
        )
        item["_brain_i"] = i
        scored.append(item)
    scored.sort(key=lambda r: (-float(r.get("_brain_score") or 0), r.get("_brain_i", 0)))
    return scored


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
) -> dict:
    """Append one observe/score/gate/buy/skip decision to the durable journal."""
    state = load_journal(root)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    row = {
        "at": now,
        "bot": bot,
        "action": action,  # buy | skip | flip | settle | observe
        "ticker": ticker,
        "side": side,
        "edge": None if edge is None else round(float(edge), 4),
        "confidence": None if confidence is None else round(float(confidence), 4),
        "depth": None if depth is None else float(depth),
        "score": None if score is None else round(float(score), 6),
        "reasons": list(reasons or []),
        "note": note[:240],
    }
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
    return {
        "paper_only": True,
        "version": state.get("version", 1),
        "last_at": state.get("last_at"),
        "decision_count": len(decisions),
        "by_bot": state.get("by_bot") or {},
        "top_skip_gates": [{"gate": g, "n": n} for g, n in top_gates],
        "recent": decisions[-MAX_SUMMARY:],
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


if __name__ == "__main__":
    self_check()
    print("desk_brain self_check ok")
