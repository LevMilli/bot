"""Lifetime paper record per bot. Paper only.

The midnight refill (R18) and the staff reset start a bot on a fresh starter
account. That clears the bot's realized P/L and closed trades, so a bot that
lost its whole bankroll yesterday looks flat today. This file keeps the closed
P/L from every wiped book in ``pimp-lifetime.json`` (on the /data volume when
one is bound) so the lifetime number and the worst drawdown still count it.

Rules:
- A reset row is written before the book is cleared. One row per bot per
  midnight day; staff resets get their own row each time.
- Old wipes are rebuilt from ``midnight-archive/<day>/`` copies, and from audit
  rows when no copy is left. A day already on the ledger is never added twice.
- A missing number stays missing. Nothing is guessed.
"""
from __future__ import annotations

import datetime as dt
import os
import re
import shutil
import tempfile

LEDGER_NAME = "pimp-lifetime.json"
MAX_TRADES_PER_BOT = 5000

_AUDIT_RE = re.compile(r"^Midnight reload ([A-Za-z0-9_-]+):")


def _desk():
    import pimp_desk

    return pimp_desk


def ledger_path(root: str | None = None) -> str:
    return _desk()._under(root, LEDGER_NAME)


def load_ledger(root: str | None = None) -> dict:
    data = _desk()._read_json(ledger_path(root)) or {}
    if not isinstance(data, dict):
        data = {}
    bots = data.get("bots") if isinstance(data.get("bots"), dict) else {}
    keys = data.get("keys") if isinstance(data.get("keys"), list) else []
    return {"paper_only": True, "version": 1, "bots": bots, "keys": keys}


def _save(root: str, ledger: dict) -> None:
    ledger["paper_only"] = True
    _desk()._write_json(ledger_path(root), ledger)


def _closed_rows(bot: dict) -> list:
    desk = _desk()
    rows = []
    for row in bot.get("history") or []:
        if not isinstance(row, dict):
            continue
        pnl = desk._num(row.get("pnl"))
        if pnl is None:
            continue
        rows.append({
            "when": str(row.get("when") or row.get("closed_at") or "")[:40],
            "pnl": round(float(pnl), 2),
            "name": str(row.get("title") or row.get("ticker") or row.get("what") or row.get("name") or "")[:80],
            "fill_id": str(row.get("fill_id") or "")[:80],
        })
    return rows


def _sort_rows(rows: list) -> list:
    desk = _desk()
    keyed = []
    for index, row in enumerate(rows):
        when = desk._ct_when(row.get("when"))
        keyed.append((0 if when is not None else 1, when.timestamp() if when is not None else 0.0, index, row))
    keyed.sort(key=lambda item: (item[0], item[1], item[2]))
    return [item[3] for item in keyed]


def _add_reset(ledger: dict, bot_id: str, key: str, row: dict, trades: list) -> bool:
    if key in ledger["keys"]:
        return False
    book = ledger["bots"].setdefault(bot_id, {"resets": [], "trades": []})
    book.setdefault("resets", [])
    book.setdefault("trades", [])
    row = {**row, "key": key, "trades_n": len(trades)}
    book["resets"].append(row)
    book["trades"].extend({**trade, "reset": key} for trade in _sort_rows(trades))
    if len(book["trades"]) > MAX_TRADES_PER_BOT:
        # Keep the newest rows for the drawdown line; the reset rows keep the totals.
        book["trades"] = book["trades"][-MAX_TRADES_PER_BOT:]
        book["trimmed"] = True
    ledger["keys"].append(key)
    return True


def _reset_row(bot: dict, day: str, source: str) -> dict:
    desk = _desk()
    trades = _closed_rows(bot)
    realized = desk._num(bot.get("realized"))
    pnl_sum = round(sum(t["pnl"] for t in trades), 2) if trades else None
    return {
        "day": day,
        "at": desk.central_text(),
        "source": source,
        "realized": None if realized is None else round(float(realized), 2),
        "today": None if desk._num(bot.get("today")) is None else round(float(bot.get("today")), 2),
        "cash_before": None if desk._num(bot.get("cash")) is None else round(float(bot.get("cash")), 2),
        "starter": float(desk.TOWER_STARTER_CASH.get(str(bot.get("id") or "")) or 0) or None,
        "pnl_sum": pnl_sum,
    }, trades


def bank_before_reset(root: str | None, bot: dict, day: str, source: str = "midnight") -> bool:
    """Write the book that is about to be cleared onto the lifetime ledger."""
    desk = _desk()
    root = desk._root(root)
    bot_id = str(bot.get("id") or "")
    if not bot_id:
        return False
    row, trades = _reset_row(bot, day, source)
    if row["realized"] is None and row["pnl_sum"] is None and not trades:
        return False
    if source == "midnight":
        key = f"{bot_id}:{day}"
    else:
        key = f"{source}:{bot_id}:{row['at']}:{len(load_ledger(root)['keys'])}"
    ledger = load_ledger(root)
    added = _add_reset(ledger, bot_id, key, row, trades)
    if added:
        _save(root, ledger)
    return added


def _archive_dirs(root: str) -> list:
    desk = _desk()
    seen, out = set(), []
    durable = desk._allowed_durable(root)
    for base in (root, durable):
        if not base:
            continue
        folder = os.path.join(base, "midnight-archive")
        real = os.path.realpath(folder)
        if real in seen or not os.path.isdir(folder):
            continue
        seen.add(real)
        out.append(folder)
    return out


def _archive_view(spec: dict, day_dir: str, day: str):
    """Read an archived book with the same view code the desk uses."""
    desk = _desk()
    folder = spec["folder"]
    safe = folder.replace(os.sep, "_")
    state_name = desk.ACCOUNT_FILES.get(spec["id"]) or spec.get("state") or ""
    if not state_name:
        return None
    names = [state_name]
    log = spec.get("log")
    if log:
        names.append(log)
    names += ["trades.csv", "checks.csv", "Trade_Ledger.md", "paper_trades.md"]
    found = {}
    for name in dict.fromkeys(names):
        path = os.path.join(day_dir, f"{safe}__{name}")
        if os.path.isfile(path):
            found[name] = path
    if state_name not in found and not (spec["id"] == "memecoin" and "trades.csv" in found):
        return None
    try:
        when = dt.date.fromisoformat(day)
    except ValueError:
        return None
    tmp = tempfile.mkdtemp(prefix="lifetime-")
    try:
        target = os.path.join(tmp, folder)
        os.makedirs(target, exist_ok=True)
        with open(os.path.join(target, spec["script"]), "w", encoding="utf-8") as handle:
            handle.write("# archive read\n")
        for name, path in found.items():
            shutil.copy2(path, os.path.join(target, name))
        return desk._bot_view(spec, tmp, {}, when)
    except Exception:  # noqa: BLE001 - an unreadable archive is skipped, not guessed
        return None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


_BACKFILLED: set = set()


def backfill_once(root: str | None = None) -> int:
    """Backfill one time per process per root. Snapshots call this."""
    desk = _desk()
    root = desk._root(root)
    real = os.path.realpath(root)
    if real in _BACKFILLED:
        return 0
    _BACKFILLED.add(real)
    try:
        return backfill(root)
    except Exception:  # noqa: BLE001 - the board still shows what it has
        return 0


def backfill(root: str | None = None) -> int:
    """Rebuild wipes that happened before this ledger existed. Safe to run again."""
    desk = _desk()
    root = desk._root(root)
    ledger = load_ledger(root)
    added = 0
    for base in _archive_dirs(root):
        try:
            days = sorted(os.listdir(base))
        except OSError:
            continue
        for day in days:
            day_dir = os.path.join(base, day)
            if not os.path.isdir(day_dir) or not re.match(r"^\d{4}-\d{2}-\d{2}$", day):
                continue
            for spec in desk.BOTS:
                key = f"{spec['id']}:{day}"
                if key in ledger["keys"]:
                    continue
                view = _archive_view(spec, day_dir, day)
                if not view:
                    continue
                row, trades = _reset_row({**view, "id": spec["id"]}, day, "archive")
                row["at"] = ""
                if row["realized"] is None and not trades:
                    continue
                if _add_reset(ledger, spec["id"], key, row, trades):
                    added += 1
    # Audit rows keep the realized number when no archive copy is left.
    audit = desk._read_json(desk.audit_path(root)) or {}
    for entry in audit.get("rows") or []:
        if not isinstance(entry, dict):
            continue
        match = _AUDIT_RE.match(str(entry.get("what") or ""))
        before = entry.get("before") if isinstance(entry.get("before"), dict) else {}
        after = entry.get("after") if isinstance(entry.get("after"), dict) else {}
        day = str(after.get("day") or "")
        if not match or not day:
            continue
        bot_id = match.group(1)
        key = f"{bot_id}:{day}"
        if key in ledger["keys"]:
            continue
        realized = desk._num(before.get("realized"))
        if realized is None:
            continue
        row = {
            "day": day,
            "at": str(entry.get("at") or ""),
            "source": "audit",
            "realized": round(float(realized), 2),
            "today": desk._num(before.get("today")),
            "cash_before": desk._num(before.get("cash")),
            "starter": float(desk.TOWER_STARTER_CASH.get(bot_id) or 0) or None,
            "pnl_sum": None,
        }
        if _add_reset(ledger, bot_id, key, row, []):
            added += 1
    if added:
        _save(root, ledger)
    return added


def _drawdown(values: list) -> float | None:
    if not values:
        return None
    total, peak, worst = 0.0, 0.0, 0.0
    for value in values:
        total += float(value)
        peak = max(peak, total)
        worst = max(worst, peak - total)
    return round(worst, 2)


def _bot_lifetime(bot: dict, book: dict) -> dict:
    desk = _desk()
    resets = [r for r in (book.get("resets") or []) if isinstance(r, dict)]
    banked_trades = [t for t in (book.get("trades") or []) if isinstance(t, dict)]
    current = _closed_rows(bot)
    banked = 0.0
    banked_known = True
    wiped = 0.0
    added = 0.0
    added_known = False
    for row in resets:
        value = desk._num(row.get("realized"))
        if value is None:
            value = desk._num(row.get("pnl_sum"))
        if value is None:
            banked_known = False
            continue
        banked += float(value)
        if value < 0:
            wiped += -float(value)
        starter = desk._num(row.get("starter"))
        cash = desk._num(row.get("cash_before"))
        if starter is not None and cash is not None:
            added += max(0.0, float(starter) - max(0.0, float(cash)))
            added_known = True
    now = desk._num(bot.get("realized"))
    if now is None and current:
        now = sum(t["pnl"] for t in current)
    if now is None and not resets:
        realized = None
    else:
        realized = round(banked + float(now or 0.0), 2)
    series = [t["pnl"] for t in banked_trades] + [t["pnl"] for t in _sort_rows(current)]
    wins = sum(1 for v in series if v > 0)
    losses = sum(1 for v in series if v < 0)
    return {
        "realized": realized,
        "banked": round(banked, 2) if resets else 0.0,
        "current": None if now is None else round(float(now), 2),
        "trades": len(series),
        "wins": wins,
        "losses": losses,
        "max_drawdown": _drawdown(series),
        "resets": len(resets),
        "wiped_losses": round(wiped, 2),
        "cash_added": round(added, 2) if added_known else None,
        "complete": banked_known,
    }


def lifetime_board(root: str | None, bots: list) -> dict:
    """Per-bot lifetime numbers plus a desk total. Reads only; backfill is separate."""
    desk = _desk()
    root = desk._root(root)
    ledger = load_ledger(root)
    per = {}
    desk_rows = []
    for bot in bots:
        bot_id = str(bot.get("id") or "")
        book = ledger["bots"].get(bot_id) or {}
        per[bot_id] = _bot_lifetime(bot, book)
        desk_rows += [{"when": t.get("when"), "pnl": t["pnl"]} for t in (book.get("trades") or []) if isinstance(t, dict) and desk._num(t.get("pnl")) is not None]
        desk_rows += _closed_rows(bot)
    known = [v["realized"] for v in per.values() if v["realized"] is not None]
    series = [float(r["pnl"]) for r in _sort_rows(desk_rows)]
    totals = {
        "realized": round(sum(known), 2) if known else None,
        "trades": len(series),
        "wins": sum(1 for v in series if v > 0),
        "losses": sum(1 for v in series if v < 0),
        "max_drawdown": _drawdown(series),
        "resets": sum(v["resets"] for v in per.values()),
        "wiped_losses": round(sum(v["wiped_losses"] for v in per.values()), 2),
        "cash_added": round(sum(v["cash_added"] or 0.0 for v in per.values()), 2)
        if any(v["cash_added"] is not None for v in per.values()) else None,
        "complete": all(v["complete"] for v in per.values()),
        "note": "Lifetime counts every closed paper trade, including books cleared by the midnight refill or a staff reset.",
    }
    return {"bots": per, "desk": totals}
