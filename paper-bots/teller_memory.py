"""
teller_memory — shared vault consciousness v0 (facts, mistakes, wins).

Paper only. Grounded lines for teller dialogue; never invents live P&L.
Helpers / city UI read; desk snapshot may refresh from bot cards.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any

MEMORY_NAME = "teller_memory.json"
MAX_PER_KIND = 40
KINDS = ("facts", "mistakes", "wins")


def _root(root: str | None) -> str:
    if root:
        return root
    return os.path.dirname(os.path.abspath(__file__))


def memory_path(root: str | None = None) -> str:
    return os.path.join(_root(root), MEMORY_NAME)


def _empty() -> dict:
    return {
        "paper_only": True,
        "facts": [],
        "mistakes": [],
        "wins": [],
        "updated_at": None,
        "note": "Shared teller memory — facts/mistakes/wins from paper desk only.",
    }


def load_memory(root: str | None = None) -> dict:
    path = memory_path(root)
    if not os.path.isfile(path):
        return _empty()
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            return _empty()
    except (OSError, json.JSONDecodeError):
        return _empty()
    out = _empty()
    out["updated_at"] = data.get("updated_at")
    out["note"] = data.get("note") or out["note"]
    for kind in KINDS:
        rows = data.get(kind)
        if isinstance(rows, list):
            out[kind] = [r for r in rows if isinstance(r, dict)][-MAX_PER_KIND:]
    out["paper_only"] = True
    return out


def save_memory(state: dict, root: str | None = None) -> str:
    path = memory_path(root)
    payload = dict(state)
    payload["paper_only"] = True
    for kind in KINDS:
        rows = payload.get(kind) or []
        if not isinstance(rows, list):
            rows = []
        payload[kind] = [r for r in rows if isinstance(r, dict)][-MAX_PER_KIND:]
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    os.replace(tmp, path)
    return path


def remember(
    root: str | None,
    kind: str,
    text: str,
    *,
    bot_id: str | None = None,
    source: str = "desk",
) -> dict | None:
    """Append one memory row. kind ∈ facts|mistakes|wins."""
    key = str(kind or "").strip().lower()
    if key not in KINDS:
        return None
    line = " ".join(str(text or "").split())[:200]
    if not line:
        return None
    state = load_memory(root)
    row = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "bot": (bot_id or "")[:40] or None,
        "text": line,
        "source": str(source or "desk")[:40],
        "paper_only": True,
    }
    state.setdefault(key, []).append(row)
    state[key] = state[key][-MAX_PER_KIND:]
    state["updated_at"] = row["at"]
    save_memory(state, root)
    return row


def ingest_from_bots(root: str | None, bots: list | None) -> dict:
    """
    Refresh light facts from live bot cards (no invented P&L).
    Idempotent-ish: only adds when a distinct fact line is new.
    """
    state = load_memory(root)
    existing = {
        (str(r.get("bot") or ""), str(r.get("text") or ""))
        for kind in KINDS
        for r in (state.get(kind) or [])
        if isinstance(r, dict)
    }
    added = 0
    for bot in bots or []:
        if not isinstance(bot, dict):
            continue
        bot_id = str(bot.get("id") or "")
        if not bot_id:
            continue
        today = bot.get("today")
        try:
            today_f = float(today) if today is not None else None
        except (TypeError, ValueError):
            today_f = None
        if today_f is not None and today_f <= -20:
            text = f"{bot_id} red day ${today_f:.2f} — entries cautious."
            key = (bot_id, text)
            if key not in existing:
                remember(root, "mistakes", text, bot_id=bot_id, source="snapshot")
                existing.add(key)
                added += 1
        elif today_f is not None and today_f >= 5:
            text = f"{bot_id} green day ${today_f:.2f} on paper."
            key = (bot_id, text)
            if key not in existing:
                remember(root, "wins", text, bot_id=bot_id, source="snapshot")
                existing.add(key)
                added += 1
        skip = str(bot.get("skip") or "").strip()
        if skip and "weekend" in skip.lower():
            text = f"{bot_id}: weekend skip is normal, not broken."
            key = (bot_id, text)
            if key not in existing:
                remember(root, "facts", text, bot_id=bot_id, source="snapshot")
                existing.add(key)
                added += 1
        board = bot.get("skip_board") or []
        if isinstance(board, list) and board:
            top = board[0] if isinstance(board[0], dict) else {}
            code = str(top.get("code") or "")
            n = top.get("n")
            if code and n:
                text = f"{bot_id} top skip {code} ×{n} today."
                key = (bot_id, text)
                if key not in existing:
                    remember(root, "facts", text, bot_id=bot_id, source="snapshot")
                    existing.add(key)
                    added += 1
    state = load_memory(root)
    state["last_ingest_added"] = added
    return state


def dialogue_line(root: str | None, bot_id: str | None = None) -> str:
    """One grounded line for teller HUD — prefer this bot, else shared."""
    state = load_memory(root)
    bid = str(bot_id or "")
    pool: list[tuple[str, dict]] = []
    for kind in ("wins", "mistakes", "facts"):
        for row in reversed(state.get(kind) or []):
            if not isinstance(row, dict):
                continue
            pool.append((kind, row))
    if bid:
        for kind, row in pool:
            if str(row.get("bot") or "") == bid and row.get("text"):
                return f"[{kind[:-1] if kind.endswith('s') else kind}] {row['text']}"
    for kind, row in pool:
        if row.get("text"):
            label = kind[:-1] if kind.endswith("s") else kind
            return f"[{label}] {row['text']}"
    return "Shared memory empty — waiting on the next paper check."


def tower_cash_line(bot: dict | None) -> str:
    """Teller line for this tower's recorded cash. Blank when none was recorded."""
    if not isinstance(bot, dict):
        return ""
    bot_id = str(bot.get("id") or "").strip()
    if not bot_id or "cash" not in bot or bot.get("cash") is None:
        return ""
    try:
        number = float(bot.get("cash"))
    except (TypeError, ValueError):
        return ""
    if number != number:  # NaN
        return ""
    return f"{bot_id} cash ${number:.2f}"


def cash_book(bots: list | None) -> dict:
    """One row per tower. The city side and the vault both read this book.

    A tower with no recorded cash stays null. The total adds only recorded
    rows. It never fills a blank with zero or with another tower's cash.
    """
    rows = []
    for bot in bots or []:
        if not isinstance(bot, dict):
            continue
        bot_id = str(bot.get("id") or "")
        if not bot_id:
            continue
        number = None
        if "cash" in bot and bot.get("cash") is not None:
            try:
                number = round(float(bot.get("cash")), 2)
            except (TypeError, ValueError):
                number = None
        rows.append({"id": bot_id, "cash": number})
    vals = [row["cash"] for row in rows if row["cash"] is not None]
    return {
        "paper_only": True,
        "rows": rows,
        "cash": None if not vals else round(sum(vals), 2),
        "note": "Recorded paper cash only. A tower with no cash stays blank.",
    }


def memory_summary(root: str | None = None) -> dict:
    state = load_memory(root)
    recent = []
    for kind in KINDS:
        for row in (state.get(kind) or [])[-3:]:
            if isinstance(row, dict) and row.get("text"):
                recent.append(
                    {
                        "kind": kind,
                        "bot": row.get("bot"),
                        "text": row.get("text"),
                        "at": row.get("at"),
                    }
                )
    recent.sort(key=lambda r: str(r.get("at") or ""), reverse=True)
    return {
        "paper_only": True,
        "n_facts": len(state.get("facts") or []),
        "n_mistakes": len(state.get("mistakes") or []),
        "n_wins": len(state.get("wins") or []),
        "updated_at": state.get("updated_at"),
        "recent": recent[:8],
        "note": state.get("note"),
    }


def self_check() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        remember(tmp, "facts", "Paper desk never invents live fills.", bot_id="desk")
        remember(tmp, "wins", "btc15m paper buy cleared fee gates.", bot_id="btc15m")
        remember(tmp, "mistakes", "memecoin red day — stop-bleed on.", bot_id="memecoin")
        ingest_from_bots(
            tmp,
            [
                {"id": "sports-gap", "today": -22.0, "skip": "weekend"},
                {"id": "btc15m", "today": 6.5, "skip_board": [{"code": "EDGE", "n": 3}]},
            ],
        )
        summary = memory_summary(tmp)
        assert summary["n_facts"] >= 1
        assert summary["n_wins"] >= 1
        assert summary["n_mistakes"] >= 1
        line = dialogue_line(tmp, "btc15m")
        assert "btc15m" in line.lower() or "win" in line.lower()
        assert os.path.isfile(memory_path(tmp))
        book = cash_book([
            {"id": "btc15m", "cash": 97.19},
            {"id": "fed-watch", "cash": None},
            {"id": "sports-gap"},
        ])
        assert book["cash"] == 97.19
        assert book["rows"][1]["cash"] is None
        assert book["rows"][2]["cash"] is None
        assert tower_cash_line({"id": "btc15m", "cash": 97.19}) == "btc15m cash $97.19"
        assert tower_cash_line({"id": "fed-watch", "cash": None}) == ""


if __name__ == "__main__":
    self_check()
    print("teller_memory self_check ok")
