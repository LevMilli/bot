"""Paper control desk for the staff dashboard.

PAPER ONLY. Reads local files the paper bots already write, saves desk limits in
pimp-trading.json, and runs the existing one-shot scripts. No API keys, no wallet,
no order endpoint, and no live-trading switch.

run_scheduled() is one pass of the timer the Discord bot calls. It does not
contain strategy. It calls run_bot, which already applies the saved desk limits.
A script that exits 0 with no trade is a finished check.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
import logging
import math
import os
import re
import subprocess
import sys
import threading
from zoneinfo import ZoneInfo

log = logging.getLogger("pimpdesk")

ROOT = os.path.dirname(os.path.abspath(__file__))
CT = ZoneInfo("America/Chicago")
CONFIRM = "RESET PAPER"

DEFAULTS = {
    "paper_only": True,
    "stake_hi_min": 10.0,
    "stake_hi_max": 30.0,
    "stake_hi_prob": 0.8,
    "stake_lo_max": 9.99,
    "daily_loss_stop": 50.0,
    "max_open_risk": 100.0,
    "max_open_positions": 4,
}

# Fixed commands. Nothing from the request is concatenated onto these.
ACTIONS = {
    "sports-gap": {
        "run": {"argv": ("gap_bot.py",), "entry": True, "timeout": 75, "label": "Run one check"},
    },
    "kalshi-sp": {
        "run": {"argv": ("bot.py", "scan"), "entry": True, "timeout": 75, "label": "Run one check"},
        "settle": {"argv": ("bot.py", "settle"), "entry": False, "timeout": 75, "label": "Settle paper"},
        "brief": {"argv": ("bot.py", "brief", "--dry-run"), "entry": False, "timeout": 75, "label": "Morning brief"},
    },
    "btc15m": {
        "run": {"argv": ("btc15m_signal.py",), "entry": False, "timeout": 75, "label": "Run one check"},
    },
    "memecoin": {
        "run": {"argv": ("bot.py",), "entry": True, "timeout": 120, "label": "Run one check"},
    },
}

# One automatic pass. Intervals are seconds. Clock times are America/Chicago.
# Daily slots run once per Chicago day, the first time the process is up inside
# the window. The Kalshi scan uses the desk's paper scan (no --any-time) and
# only starts from 12:30 to 14:55 CT, the script's own entry window. An earlier
# scan would exit without a paper fill. The morning brief stays the desk's dry run.
# Settle is the desk's paper settle, once at 4:00 PM CT, after the 3:00 PM
# contract time, so a closed paper trade can land in the state file.
# Memecoin runs three times a day. Stake size stays inside each script.
AUTO_RETRY_SEC = 900
AUTO = (
    {"id": "sports-gap", "action": "run", "every_sec": 300},
    {"id": "btc15m", "action": "run", "every_sec": 300},
    {"id": "kalshi-sp", "action": "brief", "at_ct": "08:00", "until_ct": "12:29"},
    {"id": "kalshi-sp", "action": "run", "at_ct": "12:30", "until_ct": "14:55"},
    {"id": "kalshi-sp", "action": "settle", "at_ct": "16:00", "until_ct": "23:30"},
    {"id": "memecoin", "action": "run", "at_ct": "09:00", "until_ct": "14:59"},
    {"id": "memecoin", "action": "run", "at_ct": "15:00", "until_ct": "20:59"},
    {"id": "memecoin", "action": "run", "at_ct": "21:00", "until_ct": "23:59"},
)

BOTS = (
    {
        "id": "sports-gap",
        "name": "Sports gap",
        "folder": "sports-gap-paper",
        "script": "gap_bot.py",
        "blurb": "ESPN live win probability against Kalshi game prices. One run paper-fills or skips.",
        "state": "state.json",
        "kind": "sports",
        "log": "paper_trades.md",
        "empty": "No paper account yet. A check writes state.json and paper_trades.md.",
    },
    {
        "id": "kalshi-sp",
        "name": "Kalshi S&P",
        "folder": "kalshi-sp500-paper",
        "script": "bot.py",
        "blurb": "Daily KXINXU paper bot. Scan paper-fills inside its own clock window. Brief is read-only.",
        "state": "paper_state.json",
        "kind": "kalshi",
        "log": "Trade_Ledger.md",
        "empty": "No paper_state.json yet. A scan inside the bot's window writes one.",
    },
    {
        "id": "btc15m",
        "name": "BTC 15m signal",
        "folder": "btc15m-signal",
        "script": "btc15m_signal.py",
        "blurb": "Prints BUY or SKIP from public prices. It keeps no paper position and places nothing.",
        "state": "",
        "kind": "btc",
        "log": "",
        "empty": "Signal only. There is no cash file and no trade log.",
    },
    {
        "id": "memecoin",
        "name": "Memecoin",
        "folder": "memecoin-paper",
        "script": "bot.py",
        "blurb": "Solana meme-coin paper desk. Public DexScreener and RugCheck reads, paper fills only.",
        "state": "positions.json",
        "kind": "meme",
        "log": "trades.csv",
        "empty": "No positions.json yet. A check writes positions.json, trades.csv, and checks.csv.",
    },
)

_LOCKS: dict[str, threading.Lock] = {}
_BUSY = "A check is already running for this bot."
_ENV_KEEP = {
    "PATH", "HOME", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "TMPDIR", "TEMP", "TMP",
    "USER", "LOGNAME", "SYSTEMROOT", "WINDIR", "PATHEXT", "PYTHONPATH", "PYTHONHOME",
    "VIRTUAL_ENV", "PYTHONUTF8", "SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE",
    "CURL_CA_BUNDLE",
}


def _lock(bot_id: str) -> threading.Lock:
    lock = _LOCKS.get(bot_id)
    if lock is None:
        lock = threading.Lock()
        _LOCKS[bot_id] = lock
    return lock


def _root(root: str | None) -> str:
    return os.path.realpath(root or ROOT)


def _under(root: str, *parts: str) -> str:
    base = _root(root)
    path = os.path.realpath(os.path.join(base, *parts))
    if path != base and not path.startswith(base + os.sep):
        raise RuntimeError("path escapes the paper desk")
    return path


def _clean(value, limit: int = 180) -> str:
    text = "".join(ch for ch in str(value or "") if ch == "\n" or ch >= " ")
    return text.strip()[:limit]


def _num(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _read_json(path: str):
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _atomic_write(path: str, text: str) -> None:
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.replace(tmp, path)


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _today() -> dt.date:
    return dt.datetime.now(CT).date()


def _mtime(path: str):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def _fmt_epoch(stamp) -> str:
    if not stamp:
        return ""
    when = dt.datetime.fromtimestamp(stamp, dt.timezone.utc)
    return when.strftime("%Y-%m-%d %H:%M UTC")


def _day_hit(text: str, day: dt.date) -> bool:
    return str(text or "")[:10] == day.isoformat()


def config_path(root: str | None = None) -> str:
    return _under(root, "pimp-trading.json")


def runs_path(root: str | None = None) -> str:
    return _under(root, "pimp-runs.json")


def load_settings(root: str | None = None) -> dict:
    raw = _read_json(config_path(root)) or {}
    cfg = dict(DEFAULTS)
    for key in DEFAULTS:
        if key in raw and key not in ("paper_only", "stake_hi_prob"):
            cfg[key] = raw[key]
    cfg["paper_only"] = True
    cfg["stake_hi_prob"] = 0.8
    checked, err = parse_settings(cfg)
    return checked if checked and not err else dict(DEFAULTS)


def parse_settings(raw: dict):
    if not isinstance(raw, dict):
        return None, "Limits have to be numbers."
    try:
        hi_min = float(raw.get("stake_hi_min"))
        hi_max = float(raw.get("stake_hi_max"))
        lo_max = float(raw.get("stake_lo_max"))
        loss = float(raw.get("daily_loss_stop"))
        risk = float(raw.get("max_open_risk"))
        positions = int(float(raw.get("max_open_positions")))
    except (TypeError, ValueError):
        return None, "Enter a number in every limit."
    if not all(math.isfinite(n) for n in (hi_min, hi_max, lo_max, loss, risk)):
        return None, "Enter finite numbers."
    if hi_min < 10 or hi_max > 30 or hi_min > hi_max:
        return None, "At 80% or higher, the paper stake stays between $10 and $30."
    if not (0 < lo_max < 10):
        return None, "Below 80%, the paper stake stays under $10."
    if not (1 <= loss <= 100000):
        return None, "Daily loss stop stays between $1 and $100000."
    if not (1 <= risk <= 1000000):
        return None, "Max open risk stays between $1 and $1000000."
    if not (1 <= positions <= 50):
        return None, "Max open positions stays between 1 and 50."
    return {
        "paper_only": True,
        "stake_hi_min": round(hi_min, 2),
        "stake_hi_max": round(hi_max, 2),
        "stake_hi_prob": 0.8,
        "stake_lo_max": round(lo_max, 2),
        "daily_loss_stop": round(loss, 2),
        "max_open_risk": round(risk, 2),
        "max_open_positions": positions,
    }, None


def save_settings(raw: dict, root: str | None = None):
    cfg, err = parse_settings(raw)
    if err:
        return None, err
    payload = {
        "_comment": "Dashboard-owned paper limits. Paper only. This file is not the picks database.",
        **cfg,
    }
    _atomic_write(config_path(root), json.dumps(payload, indent=2) + "\n")
    return cfg, None


def limits_text(cfg: dict) -> str:
    hi_min = cfg["stake_hi_min"]
    hi_max = cfg["stake_hi_max"]
    lo_max = cfg["stake_lo_max"]
    return (
        f"At a model probability of 80% or higher, a paper stake stays between ${hi_min:.2f} and ${hi_max:.2f}. "
        f"Below that, it stays under ${lo_max:.2f}. "
        f"Daily loss stop ${cfg['daily_loss_stop']:.2f}. "
        f"Max open risk ${cfg['max_open_risk']:.2f}. "
        f"Max open positions {cfg['max_open_positions']}. "
        "These limits gate a new entry check. Each bot still sizes with the paper rule in its own script. "
        "Realized P/L is closed paper trades in the local files. Past paper results stay in the past."
    )


def _tail_text(path: str, max_bytes: int = 65536) -> str:
    try:
        size = os.path.getsize(path)
    except OSError:
        return ""
    try:
        with open(path, "rb") as handle:
            handle.seek(max(0, size - max_bytes))
            data = handle.read().decode("utf-8", "replace")
    except OSError:
        return ""
    if size > max_bytes:
        data = data.split("\n", 1)[-1]
    return data


def _log_lines(path: str, limit: int = 8) -> list:
    if not path or not os.path.isfile(path):
        return []
    if path.endswith(".csv"):
        return []
    lines = []
    for line in _tail_text(path).splitlines():
        text = _clean(line, 220)
        if not text or text.startswith("#") or set(text) <= set("|-: "):
            continue
        lines.append(text)
    return lines[-limit:]


def _csv_tail(path: str, limit: int = 12) -> list:
    if not os.path.isfile(path):
        return []
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as handle:
            header = handle.readline()
            if size > 200000:
                handle.seek(max(0, size - 65536))
                rest = handle.read().decode("utf-8", "replace")
                if not rest.startswith(header.decode("utf-8", "replace")[:12]):
                    rest = rest.split("\n", 1)[-1]
                text = header.decode("utf-8", "replace") + rest
            else:
                handle.seek(0)
                text = handle.read().decode("utf-8", "replace")
    except OSError:
        return []
    try:
        rows = list(csv.DictReader(io.StringIO(text)))
    except csv.Error:
        return []
    return rows[-limit:]


def _load_runs(root: str) -> dict:
    data = _read_json(runs_path(root)) or {}
    return data if isinstance(data, dict) else {}


def _save_run(root: str, bot_id: str, row: dict) -> None:
    runs = _load_runs(root)
    runs[bot_id] = row
    _atomic_write(runs_path(root), json.dumps(runs, indent=2) + "\n")


def _child_env() -> dict:
    env = {key: os.environ[key] for key in _ENV_KEEP if os.environ.get(key)}
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PAPER_ONLY"] = "1"
    return env


def _folder_ok(root: str, folder: str, script: str) -> bool:
    try:
        cwd = _under(root, folder)
    except RuntimeError:
        return False
    return os.path.isfile(os.path.join(cwd, script))


def _kalshi_paper(root: str) -> bool:
    cfg = _read_json(_under(root, "kalshi-sp500-paper", "config.json")) or {}
    return cfg.get("paper_mode") is True


def _meme_paper(root: str) -> bool:
    path = _under(root, "memecoin-paper", "config.py")
    if not os.path.isfile(path):
        return False
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    except OSError:
        return False
    return re.search(r"(?m)^PAPER\s*=\s*True\b", text) is not None


def _kalshi_skip(root: str, state: dict | None) -> str:
    day = _today()
    reasons = []
    if day.weekday() >= 5:
        reasons.append("WEEKEND")
    cal = _read_json(_under(root, "kalshi-sp500-paper", "calendar.json")) or {}
    key = day.isoformat()
    for name, days in cal.items():
        if str(name).startswith("_") or not isinstance(days, list):
            continue
        if key in days:
            reasons.append(str(name))
    if reasons:
        line = f"{key} CT skip: {', '.join(reasons)}."
    else:
        line = f"{key} CT is not on the skip calendar."
    if state and state.get("halted"):
        line += " The paper account is halted by its own kill switch."
    return line


def _btc_skip(summary: str) -> str:
    if not summary:
        return "No check yet. Skip and news status show up after a run."
    lines = [_clean(line, 240) for line in summary.splitlines()]
    news = next((line for line in lines if line.lower().startswith("news")), "")
    signal = next((line for line in lines if line.upper().startswith("SIGNAL:")), "")
    picked = [line for line in (news, signal) if line]
    return " ".join(picked)[:400] or "The last run did not include a skip line."


def _sports_positions(state: dict, day: dt.date):
    open_rows, trades, today, risk = [], [], 0.0, 0.0
    open_all = [pos for pos in (state.get("open") or []) if isinstance(pos, dict)]
    for pos in open_all:
        cost = _num(pos.get("cost")) or 0.0
        risk += cost
        title = _clean(f"{pos.get('contracts') or '?'} YES {pos.get('team') or pos.get('ticker') or 'contract'}")
        detail = _clean(f"{pos.get('game') or ''} · cost ${cost:.2f} · {pos.get('opened') or ''}")
        open_rows.append({"title": title, "detail": detail, "cost": round(cost, 2)})
    open_rows = open_rows[:20]
    closed = [pos for pos in (state.get("closed") or []) if isinstance(pos, dict)]
    for pos in closed[-12:]:
        pnl = _num(pos.get("pnl"))
        trades.append({
            "when": _clean(pos.get("closed") or "", 40),
            "what": _clean(f"{pos.get('team') or ''} {pos.get('game') or ''} {pos.get('exit') or ''}"),
            "pnl": None if pnl is None else round(pnl, 2),
        })
    realized = 0.0
    seen = False
    for pos in closed:
        pnl = _num(pos.get("pnl"))
        if pnl is None:
            continue
        realized += pnl
        seen = True
        if _day_hit(pos.get("closed"), day):
            today += pnl
    return open_rows, trades, (round(realized, 2) if seen else 0.0), round(today, 2), round(risk, 2), len(open_all)


def _kalshi_positions(state: dict, day: dt.date):
    open_rows, trades, today, risk = [], [], 0.0, 0.0
    open_all = [pos for pos in (state.get("open") or []) if isinstance(pos, dict)]
    for pos in open_all:
        cost = _num(pos.get("cost")) or 0.0
        risk += cost
        title = _clean(f"{pos.get('contracts') or '?'} {pos.get('side') or ''} {pos.get('ticker') or 'contract'}")
        detail = _clean(f"ask {pos.get('ask')} · cost ${cost:.2f} · {pos.get('day') or ''}")
        open_rows.append({"title": title, "detail": detail, "cost": round(cost, 2)})
    open_rows = open_rows[:20]
    closed = [pos for pos in (state.get("closed") or []) if isinstance(pos, dict)]
    for pos in closed[-12:]:
        pnl = _num(pos.get("pnl"))
        when = str(pos.get("settled_at") or pos.get("day") or "")
        trades.append({
            "when": _clean(when, 40),
            "what": _clean(f"{pos.get('ticker') or ''} {pos.get('side') or ''} {pos.get('status') or ''}"),
            "pnl": None if pnl is None else round(pnl, 2),
        })
    realized = 0.0
    for pos in closed:
        pnl = _num(pos.get("pnl"))
        if pnl is None:
            continue
        realized += pnl
        when = str(pos.get("settled_at") or pos.get("day") or "")
        if _day_hit(when, day) or str(pos.get("day") or "") == day.isoformat():
            today += pnl
    return open_rows, trades, round(realized, 2), round(today, 2), round(risk, 2), len(open_all)


def _meme_positions(state: dict, trades_path: str, day: dt.date):
    open_rows, risk = [], 0.0
    open_all = [pos for pos in (state.get("open") or []) if isinstance(pos, dict)]
    for pos in open_all:
        cost = _num(pos.get("cost_usd")) or 0.0
        risk += cost
        title = _clean(f"{pos.get('symbol') or 'token'} · ${cost:.2f}")
        detail = _clean(f"{pos.get('mint') or ''} · {pos.get('entry_iso') or ''}")
        open_rows.append({"title": title, "detail": detail, "cost": round(cost, 2)})
    open_rows = open_rows[:20]
    trades, today = [], 0.0
    all_rows = _csv_tail(trades_path, 5000)
    for row in all_rows:
        pnl = _num(row.get("pnl_usd"))
        if pnl is not None and _day_hit(row.get("ts"), day):
            today += pnl
    for row in all_rows[-12:]:
        pnl = _num(row.get("pnl_usd"))
        side = _clean(row.get("side") or "", 12)
        trades.append({
            "when": _clean(row.get("ts") or "", 40),
            "what": _clean(f"{side} {row.get('symbol') or ''} {row.get('reason') or ''}"),
            "pnl": None if pnl is None else round(pnl, 2),
        })
    realized = _num(state.get("realized_pnl_usd"))
    return open_rows, trades, (None if realized is None else round(realized, 2)), round(today, 2), round(risk, 2), len(open_all)


def _bot_view(spec: dict, root: str, runs: dict, day: dt.date) -> dict:
    present = _folder_ok(root, spec["folder"], spec["script"])
    actions = []
    if present and spec["id"] in ACTIONS:
        for action_id, action in ACTIONS[spec["id"]].items():
            actions.append({"id": action_id, "label": action["label"], "entry": action["entry"], "confirm": False})
        actions.append({"id": "reset", "label": "Reset paper state", "entry": False, "confirm": True})
    view = {
        "id": spec["id"],
        "name": spec["name"],
        "blurb": spec["blurb"],
        "present": present,
        "empty": "" if present else "Not on this checkout.",
        "has_state": False,
        "cash": None,
        "realized": None,
        "today": 0.0,
        "open_risk": 0.0,
        "open_count": 0,
        "positions": [],
        "trades": [],
        "log": [],
        "last_check": "",
        "last_epoch": 0,
        "skip": "",
        "read_error": "",
        "last_run": runs.get(spec["id"]) if isinstance(runs.get(spec["id"]), dict) else None,
        "actions": actions,
    }
    if not present:
        view["empty"] = "The script is not in this checkout."
        return view
    run = view["last_run"] or {}
    if spec["kind"] == "btc":
        view["skip"] = _btc_skip(str(run.get("summary") or ""))
        view["empty"] = spec["empty"]
        if run.get("at"):
            view["last_check"] = str(run.get("at"))
        return view
    state_path = _under(root, spec["folder"], spec["state"])
    stamp = _mtime(state_path) or 0
    log_path = _under(root, spec["folder"], spec["log"]) if spec["log"] else ""
    log_stamp = _mtime(log_path) or 0
    view["last_epoch"] = max(stamp, log_stamp)
    view["last_check"] = _fmt_epoch(view["last_epoch"]) or (str(run.get("at") or "") if run else "")
    view["log"] = _log_lines(log_path)
    state = _read_json(state_path) if os.path.isfile(state_path) else None
    if os.path.isfile(state_path) and state is None:
        view["read_error"] = "The state file is there but could not be read."
        view["empty"] = view["read_error"]
        return view
    if state is None:
        view["empty"] = spec["empty"]
        if spec["kind"] == "kalshi":
            view["skip"] = _kalshi_skip(root, None)
        elif spec["kind"] == "sports":
            view["skip"] = "No news calendar on this bot. Skip lines land in the log after a check."
        else:
            view["skip"] = "No news calendar on this bot."
        return view
    view["has_state"] = True
    view["empty"] = ""
    if spec["kind"] == "sports":
        positions, trades, realized, today, risk, count = _sports_positions(state, day)
        view["cash"] = _num(state.get("cash"))
        view["skip"] = "No news calendar on this bot. The log lines are the skip record."
    elif spec["kind"] == "kalshi":
        positions, trades, realized, today, risk, count = _kalshi_positions(state, day)
        view["cash"] = _num(state.get("bankroll"))
        view["skip"] = _kalshi_skip(root, state)
    else:
        trades_path = _under(root, spec["folder"], "trades.csv")
        positions, trades, realized, today, risk, count = _meme_positions(state, trades_path, day)
        view["cash"] = _num(state.get("cash_usd"))
        view["skip"] = "No news calendar on this bot. Rug skips are in the last run summary."
    if view["cash"] is not None:
        view["cash"] = round(view["cash"], 2)
    view["positions"] = positions
    view["trades"] = trades
    view["realized"] = realized
    view["today"] = today
    view["open_risk"] = risk
    view["open_count"] = count
    return view


def _sized_view() -> dict:
    return {
        "id": "kalshi-sized",
        "name": "Sized Kalshi",
        "blurb": "The sized Kalshi paper bot is not in this checkout, so this panel has no script to run for it.",
        "present": False,
        "empty": "Not on this checkout. Desk stake bounds are saved here for when that bot is on main.",
        "has_state": False,
        "cash": None,
        "realized": None,
        "today": 0.0,
        "open_risk": 0.0,
        "open_count": 0,
        "positions": [],
        "trades": [],
        "log": [],
        "last_check": "",
        "last_epoch": 0,
        "skip": "",
        "read_error": "",
        "last_run": None,
        "actions": [],
    }


def entry_gate(root: str | None = None, bots: list | None = None) -> str:
    cfg = load_settings(root)
    rows = bots if bots is not None else snapshot(root)["bots"]
    open_risk = round(sum(float(b.get("open_risk") or 0) for b in rows), 2)
    open_count = int(sum(int(b.get("open_count") or 0) for b in rows))
    today = round(sum(float(b.get("today") or 0) for b in rows), 2)
    if today <= -float(cfg["daily_loss_stop"]):
        return (
            f"Daily loss stop is hit (${abs(today):.2f} against ${cfg['daily_loss_stop']:.2f}). "
            "Entry checks stay off until the next Chicago day. Settle, the morning brief, and the BTC signal still run."
        )
    if open_count >= int(cfg["max_open_positions"]):
        return (
            f"Max open positions is reached ({open_count} of {cfg['max_open_positions']}). "
            "Entry checks stay off. Settle, the morning brief, and the BTC signal still run."
        )
    if open_risk >= float(cfg["max_open_risk"]) - 1e-9:
        return (
            f"Max open risk is reached (${open_risk:.2f} of ${cfg['max_open_risk']:.2f}). "
            "Entry checks stay off. Settle, the morning brief, and the BTC signal still run."
        )
    return ""


def snapshot(root: str | None = None) -> dict:
    root = _root(root)
    cfg = load_settings(root)
    runs = _load_runs(root)
    day = _today()
    bots = [_bot_view(spec, root, runs, day) for spec in BOTS]
    bots.append(_sized_view())
    cashes = [b["cash"] for b in bots if b.get("cash") is not None]
    realized_rows = [b["realized"] for b in bots if b.get("realized") is not None]
    last_epoch = max((b.get("last_epoch") or 0) for b in bots)
    last_check = _fmt_epoch(last_epoch)
    if not last_check:
        stamps = [str((b.get("last_run") or {}).get("at") or "") for b in bots]
        last_check = max(stamps) if any(stamps) else ""
    public = []
    for bot in bots:
        row = dict(bot)
        row.pop("last_epoch", None)
        public.append(row)
    return {
        "paper_only": True,
        "banner": "PAPER ONLY. This desk does not trade real money. No Kalshi API key, no wallet, no live order. The same paper checks also run on a timer.",
        "limits": cfg,
        "limits_text": limits_text(cfg),
        "desk": {
            "cash": None if not cashes else round(sum(cashes), 2),
            "realized": None if not realized_rows else round(sum(realized_rows), 2),
            "today": round(sum(float(b.get("today") or 0) for b in bots), 2),
            "open_risk": round(sum(float(b.get("open_risk") or 0) for b in bots), 2),
            "open_count": int(sum(int(b.get("open_count") or 0) for b in bots)),
            "last_check": last_check,
            "gate": entry_gate(root, bots),
        },
        "timer": timer_text(),
        "bots": public,
    }


def _clip_out(text: str, limit: int = 6000) -> str:
    text = text.replace("\x00", "")
    if len(text) <= limit:
        return text.strip()
    return ("…\n" + text[-(limit - 2):]).strip()


def _paper_ok(root: str, bot_id: str) -> str:
    if bot_id == "kalshi-sp" and not _kalshi_paper(root):
        return "Kalshi config is not paper_mode. This desk will not start it."
    if bot_id == "memecoin" and not _meme_paper(root):
        return "Memecoin PAPER is not True. This desk will not start it."
    return ""


def run_bot(bot_id: str, action: str = "run", root: str | None = None) -> dict:
    root = _root(root)
    spec = ACTIONS.get(bot_id, {}).get(action or "run")
    folder = next((b["folder"] for b in BOTS if b["id"] == bot_id), "")
    if not spec or not folder:
        return {"ok": False, "error": "That action is not on this desk."}
    for part in spec["argv"]:
        if "/" in part or "\\" in part or part == "..":
            return {"ok": False, "error": "That action is not on this desk."}
    if not _folder_ok(root, folder, spec["argv"][0]):
        return {"ok": False, "error": "That script is not on this checkout."}
    refused = _paper_ok(root, bot_id)
    if refused:
        return {"ok": False, "error": refused}
    if spec["entry"]:
        gate = entry_gate(root)
        if gate:
            row = {"at": _now(), "ok": False, "blocked": True, "summary": gate, "exit": None, "action": action}
            _save_run(root, bot_id, row)
            return {"ok": False, "error": gate, "blocked": True, "summary": gate}
    lock = _lock(bot_id)
    if not lock.acquire(blocking=False):
        return {"ok": False, "error": _BUSY}
    try:
        cwd = _under(root, folder)
        script = os.path.join(cwd, spec["argv"][0])
        timed_out = False
        try:
            proc = subprocess.Popen(
                [sys.executable, script, *spec["argv"][1:]],
                cwd=cwd,
                env=_child_env(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            try:
                out, _ = proc.communicate(timeout=spec["timeout"])
            except subprocess.TimeoutExpired:
                proc.kill()
                out, _ = proc.communicate()
                timed_out = True
        except OSError as exc:
            return {"ok": False, "error": f"Could not start the paper script ({exc.__class__.__name__})."}
        summary = _clip_out(out or "")
        if timed_out:
            summary = _clip_out(f"Stopped after {spec['timeout']}s.\n{summary}")
        ok = (not timed_out) and proc.returncode == 0
        row = {"at": _now(), "ok": ok, "summary": summary, "exit": proc.returncode, "action": action}
        _save_run(root, bot_id, row)
        if not summary:
            summary = "The script finished with no output."
        error = "" if ok else (summary.splitlines()[-1] if summary else "The paper script did not finish cleanly.")
        return {"ok": ok, "error": error, "summary": summary, "exit": proc.returncode}
    finally:
        lock.release()


def timer_text() -> str:
    """Plain schedule for the desk. No forecast and no profit language."""
    return (
        "On a timer, America/Chicago. Sports gap about every 5 minutes. "
        "BTC 15-minute signal about every 5 minutes. "
        "Kalshi morning brief once at 8:00 AM, dry run. "
        "Kalshi paper scan once at 12:30 PM, inside that bot's own window. "
        "Kalshi paper settle once at 4:00 PM. "
        "Memecoin at 9:00 AM, 3:00 PM, and 9:00 PM. "
        "No edge is a finished check with zero paper trades."
    )


def _slot_key(slot: dict) -> str:
    if "every_sec" in slot:
        return f"{slot['id']}:{slot['action']}"
    return f"{slot['id']}:{slot['action']}:{slot['at_ct']}"


def _hhmm(text: str) -> dt.time:
    hour, minute = str(text).split(":")
    return dt.time(int(hour), int(minute))


def _window_open(now_ct: dt.datetime, slot: dict) -> bool:
    day = now_ct.date()
    start = dt.datetime.combine(day, _hhmm(slot["at_ct"]), CT)
    end = dt.datetime.combine(day, _hhmm(slot["until_ct"]), CT)
    return start <= now_ct <= end


def auto_path(root: str | None = None) -> str:
    return _under(root, "pimp-auto.json")


def _load_auto(root: str) -> dict:
    data = _read_json(auto_path(root)) or {}
    return data if isinstance(data, dict) else {}


def _iso(when: dt.datetime) -> str:
    return when.astimezone(dt.timezone.utc).isoformat(timespec="seconds")


def _parsed(text: str):
    try:
        when = dt.datetime.fromisoformat(str(text))
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=dt.timezone.utc)
    return when


def due_slots(now: dt.datetime, root: str) -> list:
    """Paper checks that should run at `now`. Does not start a script."""
    now_ct = now.astimezone(CT)
    saved = _load_auto(root)
    day = now_ct.date().isoformat()
    due = []
    for slot in AUTO:
        key = _slot_key(slot)
        if "every_sec" in slot:
            prev = _parsed(saved.get(key) or "")
            if prev is not None and (now - prev).total_seconds() < float(slot["every_sec"]):
                continue
            due.append(slot)
            continue
        if not _window_open(now_ct, slot):
            continue
        if saved.get(key) == day:
            continue
        prev = _parsed(saved.get(key + ":retry") or "")
        if prev is not None and (now - prev).total_seconds() < AUTO_RETRY_SEC:
            continue
        due.append(slot)
    return due


def _remember(saved: dict, slot: dict, now: dt.datetime, result: dict) -> None:
    if result.get("error") == _BUSY:
        return
    key = _slot_key(slot)
    if "every_sec" in slot:
        saved[key] = _iso(now)
        return
    if result.get("ok"):
        saved[key] = now.astimezone(CT).date().isoformat()
        saved.pop(key + ":retry", None)
        return
    saved[key + ":retry"] = _iso(now)


def run_scheduled(now: dt.datetime | None = None, root: str | None = None) -> list:
    """Run each paper check that is due, then return. One call does not loop.

    Uses run_bot, so the saved daily-loss, max-open, and stake settings stay
    in one place and the commands stay the paper scripts. A script that exits 0
    is a finished check, including a check that found no edge. This does not
    place a live order.
    """
    root = _root(root)
    if now is None:
        now = dt.datetime.now(dt.timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=dt.timezone.utc)
    slots = due_slots(now, root)
    if not slots:
        return []
    saved = _load_auto(root)
    results = []
    for slot in slots:
        bot_id = slot["id"]
        action = slot["action"]
        result = run_bot(bot_id, action, root)
        _remember(saved, slot, now, result)
        row = {
            "bot": bot_id,
            "action": action,
            "ok": bool(result.get("ok")),
            "blocked": bool(result.get("blocked")),
            "error": result.get("error") or "",
            "summary": result.get("summary") or "",
        }
        results.append(row)
        head = _clean(row["summary"] or row["error"], 180)
        if result.get("error") == _BUSY:
            log.info("paper timer %s %s still running", bot_id, action)
        elif row["blocked"]:
            log.info("paper timer %s %s skipped, desk limit already hit: %s", bot_id, action, head)
        elif row["ok"]:
            log.info("paper timer %s %s finished: %s", bot_id, action, head or "no output")
        else:
            log.warning("paper timer %s %s did not finish: %s", bot_id, action, head or "no output")
    _atomic_write(auto_path(root), json.dumps(saved, indent=2) + "\n")
    return results


def _unlink(path: str) -> bool:
    if not os.path.isfile(path):
        return False
    os.remove(path)
    return True


def reset_bot(bot_id: str, root: str | None = None) -> dict:
    root = _root(root)
    folder = next((b["folder"] for b in BOTS if b["id"] == bot_id), "")
    if not folder:
        return {"ok": False, "error": "That bot is not on this desk."}
    if not _folder_ok(root, folder, next(b["script"] for b in BOTS if b["id"] == bot_id)):
        return {"ok": False, "error": "That script is not on this checkout."}
    lock = _lock(bot_id)
    if not lock.acquire(blocking=False):
        return {"ok": False, "error": _BUSY}
    try:
        removed = []
        if bot_id == "sports-gap":
            cwd = _under(root, folder)
            script = os.path.join(cwd, "gap_bot.py")
            try:
                proc = subprocess.run(
                    [sys.executable, script, "--reset"],
                    cwd=cwd,
                    env=_child_env(),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=20,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                return {"ok": False, "error": "Reset stopped after 20s."}
            removed.append(_clip_out(proc.stdout or "Paper state reset.", 400))
            if proc.returncode != 0:
                return {"ok": False, "error": removed[-1] or "Reset did not finish."}
        elif bot_id == "kalshi-sp":
            for name in ("paper_state.json", "Trade_Ledger.md"):
                if _unlink(_under(root, folder, name)):
                    removed.append(name)
        elif bot_id == "memecoin":
            for name in ("positions.json", "trades.csv", "checks.csv"):
                if _unlink(_under(root, folder, name)):
                    removed.append(name)
        elif bot_id == "btc15m":
            removed.append("no account file")
        else:
            return {"ok": False, "error": "That bot is not on this desk."}
        runs = _load_runs(root)
        runs.pop(bot_id, None)
        _atomic_write(runs_path(root), json.dumps(runs, indent=2) + "\n")
        if removed:
            note = "Reset paper state: " + ", ".join(removed)
        else:
            note = "Paper state was already empty."
        return {"ok": True, "error": "", "summary": note}
    finally:
        lock.release()
