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
import shutil
import subprocess
import sys
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from zoneinfo import ZoneInfo

log = logging.getLogger("pimpdesk")

ROOT = os.path.dirname(os.path.abspath(__file__))
CT = ZoneInfo("America/Chicago")
CONFIRM = "RESET PAPER"
QUIET_START = "22:00"
QUIET_END = "07:00"
MANUAL_GAP_SEC = 30
HEARTBEAT_STALE_SEC = 180
IDLE_SPORTS_SEC = 900
LOG_CAP_BYTES = 256 * 1024
PAGE_SIZE = 20
STALE_PRICE_SEC = 30
DISAGREE = 0.15
WEEK_GOAL = 25.0
VIEW_ROLES = {"developer", "owner", "admin", "mod"}
SAVE_ROLES = {"developer", "owner"}
RUN_ROLES = {"developer"}

# A live-order switch is not built. Two people would have to confirm any future one.
LIVE_SWITCH_BUILT = False

DEFAULTS = {
    "paper_only": True,
    "stake_hi_min": 10.0,
    "stake_hi_max": 30.0,
    "stake_hi_prob": 0.8,
    "stake_lo_max": 9.99,
    "daily_loss_stop": 50.0,
    "max_open_risk": 100.0,
    "max_open_positions": 4,
    "week_goal": WEEK_GOAL,
    "quiet_start": QUIET_START,
    "quiet_end": QUIET_END,
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
_FILE_LOCK = threading.RLock()
_BUSY = "A check is already running for this bot."
_HHMM = re.compile(r"^(\d{2}):(\d{2})$")
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
    with _FILE_LOCK:
        os.makedirs(folder, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
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


def audit_path(root: str | None = None) -> str:
    return _under(root, "pimp-audit.json")


def pause_path(root: str | None = None) -> str:
    return _under(root, "pimp-pause.json")


def notes_path(root: str | None = None) -> str:
    return _under(root, "pimp-notes.json")


def heartbeat_path(root: str | None = None) -> str:
    return _under(root, "pimp-heartbeat.json")


def good_path(root: str | None = None) -> str:
    return _under(root, "pimp-good.json")


def backup_meta_path(root: str | None = None) -> str:
    return _under(root, "pimp-backup.json")


def seen_path(root: str | None = None) -> str:
    return _under(root, "pimp-seen.json")


def manual_path(root: str | None = None) -> str:
    return _under(root, "pimp-manual.json")


def watch_path(root: str | None = None) -> str:
    return _under(root, "pimp-watch.json")


def alert_path(root: str | None = None) -> str:
    return _under(root, "pimp-alerts.json")


def recap_path(root: str | None = None) -> str:
    return _under(root, "pimp-recap.json")


def _lock_file(path: str) -> None:
    """Best-effort owner-only mode. Some hosts reject chmod, and that is fine."""
    try:
        os.chmod(path, 0o600)
    except OSError:
        return


def _write_json(path: str, payload) -> None:
    _atomic_write(path, json.dumps(payload, indent=2) + "\n")
    _lock_file(path)


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
    if loss == 0:
        return None, "A daily loss stop of zero is refused."
    if not (1 <= loss <= 100000):
        return None, "Daily loss stop stays between $1 and $100000."
    if not (1 <= risk <= 1000000):
        return None, "Max open risk stays between $1 and $1000000."
    if not (1 <= positions <= 50):
        return None, "Max open positions stays between 1 and 50."
    try:
        goal = float(raw.get("week_goal", DEFAULTS["week_goal"]))
    except (TypeError, ValueError):
        return None, "The week goal has to be a number."
    if not math.isfinite(goal) or goal < 0 or goal > 1000000:
        return None, "The week goal stays between $0 and $1000000."
    quiet_start = str(raw.get("quiet_start") or DEFAULTS["quiet_start"])
    quiet_end = str(raw.get("quiet_end") or DEFAULTS["quiet_end"])
    if _hhmm_ok(quiet_start) is None or _hhmm_ok(quiet_end) is None:
        return None, "Quiet hours use 24-hour times like 22:00."
    return {
        "paper_only": True,
        "stake_hi_min": round(hi_min, 2),
        "stake_hi_max": round(hi_max, 2),
        "stake_hi_prob": 0.8,
        "stake_lo_max": round(lo_max, 2),
        "daily_loss_stop": round(loss, 2),
        "max_open_risk": round(risk, 2),
        "max_open_positions": positions,
        "week_goal": round(goal, 2),
        "quiet_start": quiet_start,
        "quiet_end": quiet_end,
    }, None


def save_settings(raw: dict, root: str | None = None, who: str = ""):
    before = load_settings(root)
    cfg, err = parse_settings(raw)
    if err:
        return None, err
    payload = {
        "_comment": "Dashboard-owned paper limits. Paper only. This file is not the picks database.",
        **cfg,
    }
    path = config_path(root)
    _write_json(path, payload)
    audit(root, who or "unknown", "Saved paper limits", before, cfg)
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
    with _FILE_LOCK:
        runs = _load_runs(root)
        prev = runs.get(bot_id)
        same = isinstance(prev, dict) and prev == row
        if same:
            return
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


def _fill_row(pos: dict, title: str, detail: str, cost: float, when: str) -> dict:
    ask = pos.get("ask")
    if ask in (None, "") and pos.get("entry_price") not in (None, ""):
        ask = pos.get("entry_price")
    bid = pos.get("bid")
    fee = pos.get("fee")
    if fee in (None, "") and pos.get("entry_fee") not in (None, ""):
        fee = pos.get("entry_fee")
    prob = pos.get("fair_at_entry")
    if prob in (None, "") and pos.get("model_entry") not in (None, ""):
        prob = pos.get("model_entry")
    gap = _num(pos.get("gap_at_entry"))
    if gap is None:
        why = "The reason was not stored with this trade."
    else:
        why = f"Paper buy. The fair price beat the ask by {gap * 100:.1f} points after the fee."
    contracts = pos.get("contracts")
    if contracts in (None, "") and pos.get("tokens") not in (None, ""):
        contracts = pos.get("tokens")
    priced_at = _clean(pos.get("price_at") or pos.get("entry_iso") or "", 40)
    return {
        "title": title,
        "detail": detail,
        "cost": round(cost, 2),
        "bid": None if _num(bid) is None else round(_num(bid), 4),
        "ask": None if _num(ask) is None else round(_num(ask), 4),
        "fee": None if _num(fee) is None else round(_num(fee), 4),
        "fill": paper_fill(bid, ask),
        "source": _clean(pos.get("price_source") or "", 180),
        "priced_at": priced_at,
        "priced_central": _central_from_text(priced_at) if priced_at else "",
        "prob": None if _num(prob) is None else round(_num(prob), 4),
        "prob_exit": None if _num(pos.get("fair_at_exit")) is None else round(_num(pos.get("fair_at_exit")), 4),
        "score": _clean(pos.get("score_at_entry") or "", 80),
        "fill_id": _clean(pos.get("fill_id") or "", 80),
        "ticker": _clean(pos.get("ticker") or pos.get("symbol") or "", 40),
        "game": _clean(pos.get("game") or pos.get("event") or "", 120),
        "side": _clean(pos.get("side") or "", 24),
        "contracts": None if contracts in (None, "") else contracts,
        "team": _clean(pos.get("team") or pos.get("symbol") or "", 60),
        "when": _clean(when, 40),
        "why": why,
        "why_open": why,
        "payout": None,
        "exit_reason": "",
        "closed_at": "",
        "confidence": _confidence(_num(prob)),
        "edge": edge_after_fee(prob, ask),
    }


def _closed_row(pos: dict, when: str, what: str) -> dict:
    pnl = _num(pos.get("pnl"))
    if pnl is None:
        pnl = _num(pos.get("pnl_usd"))
    exit_why = _clean(pos.get("exit") or pos.get("reason") or pos.get("status") or "", 120)
    if pnl is None:
        why = "Settled paper trade. The result was not stored."
        result = "unknown"
    elif pnl > 0:
        why = "Paper win. " + (exit_why or "The source settled it.")
        result = "won"
    elif pnl < 0:
        why = "Paper loss. " + (exit_why or "The source settled it.")
        result = "lost"
    else:
        why = "Paper trade settled flat."
        result = "flat"
    row = _fill_row(pos, what, exit_why, _num(pos.get("cost")) or _num(pos.get("cost_usd")) or 0.0, when)
    payout = _num(pos.get("payout"))
    if payout is None:
        payout = _num(pos.get("payout_usd"))
    closed_at = _central_from_text(when) if str(when or "").strip() else ""
    row["what"] = what
    row["pnl"] = None if pnl is None else round(pnl, 2)
    row["why"] = why
    row["result"] = result
    row["exit_reason"] = exit_why or "unknown"
    row["payout"] = None if payout is None else round(payout, 2)
    row["closed_at"] = closed_at
    if closed_at:
        row["when"] = closed_at
    if pos.get("fair_at_exit") not in (None, ""):
        row["prob_exit"] = None if _num(pos.get("fair_at_exit")) is None else round(_num(pos.get("fair_at_exit")), 4)
    return row


def _dedupe_pos(rows: list) -> list:
    """Drop a second copy of the same fill. Rows with no fill id all stay."""
    seen = set()
    out = []
    for pos in rows:
        if not isinstance(pos, dict):
            continue
        key = str(pos.get("fill_id") or "")
        if key:
            if key in seen:
                continue
            seen.add(key)
        out.append(pos)
    return out


def _sports_positions(state: dict, day: dt.date):
    open_rows, trades, history, today, risk = [], [], [], 0.0, 0.0
    open_all = _dedupe_pos([pos for pos in (state.get("open") or []) if isinstance(pos, dict)])
    for pos in open_all:
        cost = _num(pos.get("cost")) or 0.0
        risk += cost
        title = _clean(f"{pos.get('contracts') or '?'} YES {pos.get('team') or pos.get('ticker') or 'contract'}")
        detail = _clean(f"{pos.get('game') or ''} · cost ${cost:.2f} · {pos.get('opened') or ''}")
        open_rows.append(_fill_row(pos, title, detail, cost, str(pos.get("opened") or "")))
    closed = _dedupe_pos([pos for pos in (state.get("closed") or []) if isinstance(pos, dict)])
    for pos in closed:
        pnl = _num(pos.get("pnl"))
        when = str(pos.get("closed") or "")
        what = _clean(f"{pos.get('team') or ''} {pos.get('game') or ''} {pos.get('exit') or ''}")
        history.append(_closed_row(pos, when, what))
        if pnl is None:
            continue
        if _day_hit(when, day):
            today += pnl
    trades = history[-12:]
    realized = round(sum(row["pnl"] for row in history if row.get("pnl") is not None), 2) if history else 0.0
    if history and all(row.get("pnl") is None for row in history):
        realized = 0.0
    return open_rows, trades, realized, round(today, 2), round(risk, 2), len(open_all), history


def _kalshi_positions(state: dict, day: dt.date):
    open_rows, history, today, risk = [], [], 0.0, 0.0
    open_all = _dedupe_pos([pos for pos in (state.get("open") or []) if isinstance(pos, dict)])
    for pos in open_all:
        cost = _num(pos.get("cost")) or 0.0
        risk += cost
        ask = pos.get("ask")
        title = _clean(f"{pos.get('contracts') or '?'} {pos.get('side') or ''} {pos.get('ticker') or 'contract'}")
        detail = _clean(f"ask {ask if ask not in (None, '') else 'unknown'} · cost ${cost:.2f} · {pos.get('day') or ''}")
        open_rows.append(_fill_row(pos, title, detail, cost, str(pos.get("entry_time") or pos.get("day") or "")))
    closed = _dedupe_pos([pos for pos in (state.get("closed") or []) if isinstance(pos, dict)])
    for pos in closed:
        when = str(pos.get("settled_at") or pos.get("day") or "")
        what = _clean(f"{pos.get('ticker') or ''} {pos.get('side') or ''} {pos.get('status') or ''}")
        row = _closed_row(pos, when, what)
        history.append(row)
        if row.get("pnl") is None:
            continue
        if _day_hit(when, day) or str(pos.get("day") or "") == day.isoformat():
            today += row["pnl"]
    trades = history[-12:]
    realized = round(sum(row["pnl"] for row in history if row.get("pnl") is not None), 2)
    return open_rows, trades, realized, round(today, 2), round(risk, 2), len(open_all), history


def _meme_positions(state: dict, trades_path: str, day: dt.date):
    open_rows, history, risk = [], [], 0.0
    open_all = _dedupe_pos([pos for pos in (state.get("open") or []) if isinstance(pos, dict)])
    for pos in open_all:
        cost = _num(pos.get("cost_usd")) or 0.0
        risk += cost
        title = _clean(f"{pos.get('symbol') or 'token'} · ${cost:.2f}")
        detail = _clean(f"{pos.get('mint') or ''} · {pos.get('entry_iso') or ''}")
        row = _fill_row(pos, title, detail, cost, str(pos.get("entry_iso") or ""))
        if row["ask"] is None and _num(pos.get("entry_fill_price")) is not None:
            row["ask"] = round(_num(pos.get("entry_fill_price")), 4)
            row["fill"] = row["ask"]
        elif row["ask"] is None and _num(pos.get("fill_price_usd")) is not None:
            row["ask"] = round(_num(pos.get("fill_price_usd")), 4)
            row["fill"] = row["ask"]
        if not row["side"]:
            row["side"] = "buy"
        if not row["source"]:
            row["source"] = "https://api.dexscreener.com"
        if row["why_open"] == "The reason was not stored with this trade." and pos.get("confidence") not in (None, ""):
            row["why_open"] = f"Paper buy. Confidence {pos.get('confidence')}."
            row["why"] = row["why_open"]
        open_rows.append(row)
    all_rows = _csv_tail(trades_path, 5000)
    today = 0.0
    pnl_rows = []
    for raw in all_rows:
        side = _clean(raw.get("side") or "", 12)
        what = _clean(f"{side} {raw.get('symbol') or ''} {raw.get('reason') or ''}")
        row = _closed_row({
            "pnl": raw.get("pnl_usd"),
            "reason": raw.get("reason"),
            "exit": raw.get("reason"),
            "cost_usd": raw.get("usd"),
            "payout": raw.get("usd") if side.upper() == "SELL" else None,
            "ask": raw.get("fill_price_usd"),
            "fee": raw.get("fee_usd"),
            "price_source": raw.get("source") or "https://api.dexscreener.com",
            "price_at": raw.get("ts") or "",
            "ticker": raw.get("symbol") or "",
            "symbol": raw.get("symbol") or "",
            "side": side,
            "fill_id": f"{raw.get('ts')}|{raw.get('symbol')}|{side}|{raw.get('usd')}",
        }, str(raw.get("ts") or ""), what)
        history.append(row)
        if row.get("pnl") is not None:
            pnl_rows.append(row["pnl"])
            if _day_hit(raw.get("ts"), day):
                today += row["pnl"]
    trades = [row for row in history if row.get("pnl") is not None][-12:] or history[-12:]
    realized = round(sum(pnl_rows), 2) if pnl_rows else _num(state.get("realized_pnl_usd"))
    if realized is not None:
        realized = round(realized, 2)
    return open_rows, trades, realized, round(today, 2), round(risk, 2), len(open_all), history


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
        "history": [],
        "log": [],
        "last_check": "",
        "last_epoch": 0,
        "skip": "",
        "read_error": "",
        "data_error": "",
        "why": "",
        "would_have": [],
        "outside": False,
        "last_run": runs.get(spec["id"]) if isinstance(runs.get(spec["id"]), dict) else None,
        "actions": actions,
    }
    if not present:
        view["empty"] = "The script is not in this checkout."
        view["why"] = "That script is not on this checkout, so this check bought nothing."
        return _finish_bot(view, spec, root)
    run = view["last_run"] or {}
    if spec["kind"] == "btc":
        summary = str(run.get("summary") or "")
        view["skip"] = _btc_skip(summary)
        view["empty"] = spec["empty"]
        view["why"] = plain_reason(view["skip"]) if view["skip"] else ""
        view["warning"] = _btc_calendar_warning(summary)
        if run.get("at"):
            view["last_check"] = str(run.get("at"))
        return _finish_bot(view, spec, root)
    state_path = _under(root, spec["folder"], spec["state"])
    stamp = _mtime(state_path) or 0
    log_path = _under(root, spec["folder"], spec["log"]) if spec["log"] else ""
    log_stamp = _mtime(log_path) or 0
    view["last_epoch"] = max(stamp, log_stamp)
    view["last_check"] = _fmt_epoch(view["last_epoch"]) or (str(run.get("at") or "") if run else "")
    cap_log(log_path)
    view["log"] = _log_lines(log_path)
    state, problem = _read_state(state_path)
    if problem:
        view["read_error"] = (
            "The state file was half-written, so it was rejected."
            if problem == "half" else "The state file is there but could not be read."
        )
        view["data_error"] = view["read_error"]
        good = _last_good_bot(root, spec["id"])
        if good:
            for key in ("cash", "realized", "today", "open_risk", "open_count", "positions", "trades", "history"):
                if key in good:
                    view[key] = good[key]
            view["has_state"] = bool(good.get("has_state"))
            view["read_error"] = view["read_error"] + " Showing the last good numbers."
            view["empty"] = ""
        else:
            view["empty"] = view["read_error"]
        view["why"] = plain_reason(view["read_error"])
        return _finish_bot(view, spec, root)
    if state is None:
        view["empty"] = spec["empty"]
        view["warning"] = _calendar_warning(root, spec["id"])
        if spec["kind"] == "kalshi":
            view["skip"] = _kalshi_skip(root, None)
        view["why"] = plain_reason(view["skip"]) if view["skip"] else ""
        return _finish_bot(view, spec, root)
    view["has_state"] = True
    view["empty"] = ""
    view["warning"] = _calendar_warning(root, spec["id"])
    if spec["kind"] == "sports":
        positions, trades, realized, today, risk, count, history = _sports_positions(state, day)
        view["cash"] = _num(state.get("cash"))
    elif spec["kind"] == "kalshi":
        positions, trades, realized, today, risk, count, history = _kalshi_positions(state, day)
        view["cash"] = _num(state.get("bankroll"))
        view["skip"] = _kalshi_skip(root, state)
    else:
        trades_path = _under(root, spec["folder"], "trades.csv")
        cap_log(trades_path)
        positions, trades, realized, today, risk, count, history = _meme_positions(state, trades_path, day)
        view["cash"] = _num(state.get("cash_usd"))
    if view["cash"] is not None:
        view["cash"] = round(view["cash"], 2)
    view["positions"] = positions
    view["trades"] = trades
    view["history"] = history
    view["realized"] = realized
    view["today"] = today
    view["open_risk"] = risk
    view["open_count"] = count
    summary = str(run.get("summary") or "")
    view["why"] = plain_reason(summary) if summary.strip() else ""
    view["outside"] = _outside(root, spec["id"], stamp)
    _save_good_bot(root, spec["id"], view)
    return _finish_bot(view, spec, root)


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
        "history": [],
        "log": [],
        "last_check": "",
        "last_epoch": 0,
        "skip": "",
        "read_error": "",
        "data_error": "",
        "why": "The sized Kalshi paper bot is not in this checkout.",
        "would_have": [],
        "outside": False,
        "last_run": None,
        "actions": [],
        "book_id": "kalshi",
        "status": "skipped",
        "next_run": "",
        "paused": False,
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


def snapshot(root: str | None = None, q: str = "", filt: str = "all", page: int = 1) -> dict:
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
    desk_row = _desk_row(public, cashes, realized_rows, last_check, entry_gate(root, bots), cfg, root)
    book = _book(public, q=q, filt=filt, page=page)
    changes = _changes(root, public)
    return {
        "paper_only": True,
        "banner": "PAPER ONLY. This desk does not trade real money. No Kalshi API key, no wallet, no live order. The same paper checks also run on a timer.",
        "limits": cfg,
        "limits_text": limits_text(cfg),
        "desk": desk_row,
        "books": _books(public),
        "book": book,
        "changes": changes,
        "timer": timer_text(),
        "health": timer_health(root),
        "quiet": in_quiet(cfg=cfg),
        "checklist": security_checklist(root),
        "live_switch": live_switch_status(),
        "legend": {
            "gap": "Gap is the fair price minus the ask, after the Kalshi fee.",
            "fee": "Fee is the Kalshi taker fee, rounded up to the cent.",
            "fair": "Fair price is the model probability. Unknown means it was not stored.",
        },
        "audit": audit_rows(root)[:12],
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


def run_bot(bot_id: str, action: str = "run", root: str | None = None, manual: bool = False,
            stake=None, prob=None) -> dict:
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
    if bot_paused(root, bot_id):
        return {"ok": False, "error": "Paused.", "blocked": True, "summary": "Paused."}
    warning = _calendar_warning(root, bot_id) if spec["entry"] or bot_id == "btc15m" else ""
    if spec["entry"]:
        gate = entry_gate(root)
        if gate:
            would = [{"what": "unknown", "why": gate, "bot": bot_id}]
            row = {"at": _now(), "ok": False, "blocked": True, "summary": gate, "exit": None, "action": action,
                   "would_have": would}
            _save_run(root, bot_id, row)
            return {"ok": False, "error": gate, "blocked": True, "summary": gate, "would_have": would}
        if stake not in (None, ""):
            refused_stake = stake_allowed(stake, prob, load_settings(root))
            if refused_stake:
                return {"ok": False, "error": refused_stake, "blocked": True}
    if manual and not _rate_ok(root, bot_id):
        return {"ok": False, "error": "Run now is rate limited. Wait 30 seconds."}
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
        row = {"at": _now(), "ok": ok, "summary": summary, "exit": proc.returncode, "action": action,
               "warning": warning}
        _save_run(root, bot_id, row)
        if not summary:
            summary = "The script finished with no output."
        error = "" if ok else (summary.splitlines()[-1] if summary else "The paper script did not finish cleanly.")
        error = public_error(error)
        if manual:
            _mark_manual(root, bot_id)
        spec_row = next(b for b in BOTS if b["id"] == bot_id)
        _note_state_mtime(root, bot_id, spec_row["folder"], spec_row.get("state") or "")
        return {"ok": ok, "error": error, "summary": summary, "exit": proc.returncode, "warning": warning}
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
        if bot_paused(root, slot["id"]):
            continue
        if "every_sec" in slot:
            prev = _parsed(saved.get(key) or "")
            gap = float(slot["every_sec"])
            if slot["id"] == "sports-gap" and _sports_idle(root):
                gap = max(gap, IDLE_SPORTS_SEC)
            if prev is not None and (now - prev).total_seconds() < gap:
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
    if result.get("blocked"):
        saved[key + ":retry"] = _iso(now)
        return
    # A finished check, or a hard failure, waits for the next clock slot.
    saved[key] = now.astimezone(CT).date().isoformat()
    saved.pop(key + ":retry", None)


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
    touch_heartbeat(root, now)
    slots = due_slots(now, root)
    if not slots:
        return []
    saved = _load_auto(root)
    results = []
    saved_lock = threading.Lock()

    def _one(slot: dict) -> dict:
        bot_id = slot["id"]
        action = slot["action"]
        result = run_bot(bot_id, action, root)
        with saved_lock:
            _remember(saved, slot, now, result)
        row = {
            "bot": bot_id,
            "action": action,
            "ok": bool(result.get("ok")),
            "blocked": bool(result.get("blocked")),
            "error": result.get("error") or "",
            "summary": result.get("summary") or "",
        }
        head = _clean(row["summary"] or row["error"], 180)
        if result.get("error") == _BUSY:
            log.info("paper timer %s %s still running", bot_id, action)
        elif row["blocked"]:
            log.info("paper timer %s %s skipped, desk limit already hit: %s", bot_id, action, head)
        elif row["ok"]:
            log.info("paper timer %s %s finished: %s", bot_id, action, head or "no output")
        else:
            log.warning("paper timer %s %s did not finish: %s", bot_id, action, head or "no output")
        return row

    workers = max(1, min(4, len(slots)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_one, slot) for slot in slots]
        for fut in as_completed(futures):
            results.append(fut.result())
    _atomic_write(auto_path(root), json.dumps(saved, indent=2) + "\n")
    return results


def run_due(root: str | None = None, now: dt.datetime | None = None) -> dict:
    """One manual pass of whatever is due. It does not wait for the timer, and it is rate limited."""
    root = _root(root)
    if not _rate_ok(root, "*due*"):
        return {"ok": False, "error": "Run now is rate limited. Wait 30 seconds.", "rows": []}
    rows = run_scheduled(now, root)
    _mark_manual(root, "*due*")
    return {"ok": True, "error": "", "rows": rows}


def _unlink(path: str) -> bool:
    if not os.path.isfile(path):
        return False
    os.remove(path)
    return True


def reset_bot(bot_id: str, root: str | None = None, who: str = "") -> dict:
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
        spec_row = next(b for b in BOTS if b["id"] == bot_id)
        _note_state_mtime(root, bot_id, spec_row["folder"], spec_row.get("state") or "")
        audit(root, who or "unknown", note)
        return {"ok": True, "error": "", "summary": note}
    finally:
        lock.release()


def _hhmm_ok(text: str):
    match = _HHMM.match(str(text or ""))
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour > 23 or minute > 59:
        return None
    return dt.time(hour, minute)


def central_text(when: dt.datetime | None = None) -> str:
    when = (when or dt.datetime.now(CT)).astimezone(CT)
    hour = when.strftime("%I").lstrip("0") or "12"
    return f"{when.strftime('%B')} {when.day}, {when.year}, {hour}:{when.strftime('%M %p')} Central"


_CENTRAL_WHEN = re.compile(
    r"^(January|February|March|April|May|June|July|August|September|October|November|December)"
    r" (\d{1,2}), (\d{4}), (\d{1,2}):(\d{2}) (AM|PM) Central$"
)
_MONTH_NUM = {
    name: number for number, name in enumerate(
        ("January", "February", "March", "April", "May", "June",
         "July", "August", "September", "October", "November", "December"),
        1,
    )
}


def _ct_when(text: str):
    """Parse a desk timestamp into America/Chicago. Unknown text stays unknown."""
    raw = str(text or "").strip()
    if not raw or raw == "no check yet":
        return None
    if raw.endswith(" CT"):
        wall = raw[:-3].strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                return dt.datetime.strptime(wall, fmt).replace(tzinfo=CT)
            except ValueError:
                continue
    match = _CENTRAL_WHEN.match(raw)
    if match:
        hour = int(match.group(4)) % 12
        if match.group(6) == "PM":
            hour += 12
        try:
            return dt.datetime(
                int(match.group(3)), _MONTH_NUM[match.group(1)], int(match.group(2)),
                hour, int(match.group(5)), tzinfo=CT,
            )
        except ValueError:
            return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        try:
            day = dt.date.fromisoformat(raw)
        except ValueError:
            return None
        return dt.datetime(day.year, day.month, day.day, tzinfo=CT)
    stamp = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    parsed = _parsed(stamp)
    if parsed is not None:
        return parsed.astimezone(CT)
    for fmt in ("%Y-%m-%d %H:%M:%S UTC", "%Y-%m-%d %H:%M UTC"):
        try:
            return dt.datetime.strptime(raw, fmt).replace(tzinfo=dt.timezone.utc).astimezone(CT)
        except ValueError:
            continue
    return None


def _date_only(text: str) -> bool:
    return re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(text or "").strip()) is not None


def _central_from_text(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return "no check yet"
    if "Central" in raw:
        return raw
    if raw.endswith(" CT"):
        wall = raw[:-3].strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                when = dt.datetime.strptime(wall, fmt).replace(tzinfo=CT)
            except ValueError:
                continue
            return central_text(when)
    for fmt in ("%Y-%m-%d %H:%M:%S UTC", "%Y-%m-%d %H:%M UTC", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            when = dt.datetime.strptime(raw.replace("+00:00", "Z") if raw.endswith("Z") else raw, fmt)
        except ValueError:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=dt.timezone.utc)
        return central_text(when)
    parsed = _parsed(raw)
    if parsed is not None:
        return central_text(parsed)
    return raw


def kalshi_fee(price: float) -> float:
    return math.ceil(round(0.07 * float(price) * (1 - float(price)) * 100, 6)) / 100


def paper_fill(bid, ask):
    """Paper fills pay the ask. The mid is never used. A missing ask stays unknown."""
    ask_n = _num(ask)
    if ask_n is None:
        return None
    return round(ask_n, 4)


def edge_after_fee(fair, ask):
    fair_n, ask_n = _num(fair), _num(ask)
    if fair_n is None or ask_n is None:
        return None
    return round(fair_n - ask_n - kalshi_fee(ask_n), 4)


def _confidence(prob) -> str:
    if prob is None:
        return ""
    if prob + 1e-12 >= 0.8:
        return "80%+"
    return "under 80%"


def price_age_flag(stamp, now=None) -> str:
    when = stamp if isinstance(stamp, dt.datetime) else _parsed(stamp)
    if when is None:
        return "unknown"
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=dt.timezone.utc)
    if (now - when).total_seconds() > STALE_PRICE_SEC:
        return "stale"
    return ""


def disagree_flag(espn_p, kalshi_p) -> str:
    left, right = _num(espn_p), _num(kalshi_p)
    if left is None or right is None:
        return ""
    if abs(left - right) >= DISAGREE:
        return "ESPN and Kalshi disagree"
    return ""


def clock_skew(source_time, local_time=None) -> str:
    src = source_time if isinstance(source_time, dt.datetime) else _parsed(source_time)
    if src is None:
        return "Clock skew: unknown"
    local = local_time or dt.datetime.now(dt.timezone.utc)
    if local.tzinfo is None:
        local = local.replace(tzinfo=dt.timezone.utc)
    return f"Clock skew: {abs((local - src).total_seconds()):.0f}s"


def settle_call(source_state, home_score, away_score) -> str:
    """Settle only when the source says the game is final, and hold a tie."""
    if str(source_state or "").lower() not in ("post", "final", "settled"):
        return "wait"
    try:
        home, away = int(home_score), int(away_score)
    except (TypeError, ValueError):
        return "wait"
    if home == away:
        return "hold"
    return "settle"


def source_status(live_games, error: str = "") -> str:
    if error:
        return "api down"
    try:
        live = int(live_games or 0)
    except (TypeError, ValueError):
        live = 0
    if live <= 0:
        return "no games"
    return "live"


def public_get(url: str, opener, tries: int = 3, sleep=None):
    """Retry a public GET, then mark it failed. The error string has no URL and no token."""
    last = "failed"
    for i in range(max(1, int(tries))):
        try:
            data = opener(url)
        except Exception as exc:
            last = exc.__class__.__name__
            data = None
        if data is not None:
            return data, ""
        if sleep:
            sleep(i)
    return None, last or "failed"


def _only_calendar_note(low: str) -> bool:
    """A missing calendar is a warning. It is not a reason the check bought nothing."""
    if "news calendar" not in low and "no news calendar" not in low and "news window" not in low:
        return False
    outcomes = ("no live", "no edge", "no trade", "gap <", "signal:", "paper buy", "max open", "loss stop", "data error")
    return not any(mark in low for mark in outcomes)


def plain_reason(text: str) -> str:
    low = str(text or "").lower()
    if not low.strip():
        return "No check yet, so there is no trade to explain."
    if _only_calendar_note(low):
        return ""
    if "half-written" in low or "could not be read" in low or "data error" in low:
        return "A data error stopped this check. Nothing was guessed."
    if "no live" in low:
        return "No live games, so this check bought nothing."
    if "max open" in low:
        return "The open-position limit blocked a new paper buy."
    if "loss stop" in low or "daily loss" in low:
        return "The daily loss stop blocked a new paper buy."
    if "gap <" in low or "no trade" in low or "no edge" in low:
        return "No edge, so this check bought nothing."
    if low.startswith("signal: skip") or "skip" in low:
        return _clean(text, 220)
    return _clean(text, 220)


def public_error(text: str) -> str:
    raw = str(text or "")
    if not raw.strip():
        return ""
    lowered = raw.lower()
    if "traceback" in lowered or "/home/" in raw or "/users/" in lowered or "api_key" in lowered or "token" in lowered:
        return "That check failed."
    if re.search(r"(^|[\\/\s])(secret|password|wallet)([\\/\s]|$)", lowered):
        return "That check failed."
    return _clean(raw, 300)


def role_can(role: str, op: str) -> bool:
    role = str(role or "").strip().lower()
    if role not in VIEW_ROLES:
        return False
    if op in ("view", "export", "search", "note", "seen"):
        return True
    if op in ("save", "pause", "reset"):
        return role in SAVE_ROLES
    if op == "run":
        return role in RUN_ROLES
    return False


def auth_error(role: str, op: str) -> str:
    if role_can(role, op):
        return ""
    if str(role or "").strip().lower() not in VIEW_ROLES:
        return "Staff only."
    if op == "run":
        return "Developer only. No trade button below developer."
    if op in ("save", "pause", "reset"):
        return "Owner or developer only."
    return "Staff only."


def confirm_reset(text: str) -> str:
    if str(text or "") != CONFIRM:
        return "Type RESET PAPER to delete the paper account."
    return ""


def stake_allowed(amount, prob, cfg: dict | None = None) -> str:
    cfg = cfg or dict(DEFAULTS)
    number = _num(amount)
    if number is None:
        return "Stake has to be a number."
    if number < 0:
        return "Stake cannot be negative."
    chance = _num(prob)
    if chance is None:
        chance = 0.0
    if chance + 1e-12 >= float(cfg["stake_hi_prob"]):
        ceiling = float(cfg["stake_hi_max"])
        if number > ceiling + 1e-9:
            return f"Stake ${number:.2f} is above the saved max ${ceiling:.2f}."
    else:
        ceiling = float(cfg["stake_lo_max"])
        if number > ceiling + 1e-9:
            return f"Stake ${number:.2f} is above the saved max ${ceiling:.2f}."
    return ""


def live_switch_status() -> dict:
    return {
        "built": LIVE_SWITCH_BUILT,
        "paper_only": True,
        "needs": "Two people would both have to confirm any future live-order switch. This desk does not build that switch.",
    }


def page_has_key(page: str) -> bool:
    return re.search(
        r"(api[_-]?key|private[_-]?key|wallet[_-]?secret)\s*[:=]\s*['\"][^'\"]+",
        page or "",
        re.I,
    ) is not None


def in_quiet(now: dt.datetime | None = None, cfg: dict | None = None) -> bool:
    cfg = cfg or DEFAULTS
    now_ct = (now or dt.datetime.now(CT)).astimezone(CT)
    start = _hhmm_ok(str(cfg.get("quiet_start") or QUIET_START))
    end = _hhmm_ok(str(cfg.get("quiet_end") or QUIET_END))
    if start is None or end is None or start == end:
        return False
    minute = now_ct.hour * 60 + now_ct.minute
    begin = start.hour * 60 + start.minute
    stop = end.hour * 60 + end.minute
    if begin < stop:
        return begin <= minute < stop
    return minute >= begin or minute < stop


def audit(root: str | None, who: str, what: str, before=None, after=None) -> None:
    root = _root(root)
    path = audit_path(root)
    data = _read_json(path) or {}
    rows = data.get("rows") if isinstance(data.get("rows"), list) else []
    rows.append({
        "at": central_text(),
        "who": _clean(who, 60) or "unknown",
        "what": _clean(what, 120),
        "before": before,
        "after": after,
    })
    _write_json(path, {"rows": rows[-200:]})


def audit_rows(root: str | None) -> list:
    data = _read_json(audit_path(root)) or {}
    rows = data.get("rows") if isinstance(data.get("rows"), list) else []
    return list(reversed(rows))


def _read_state(path: str):
    tmp = path + ".tmp"
    if not os.path.isfile(path):
        if os.path.isfile(tmp):
            return None, "half"
        return None, ""
    try:
        if os.path.isfile(tmp) and os.path.getmtime(tmp) > os.path.getmtime(path):
            return None, "half"
    except OSError:
        return None, "half"
    try:
        with open(path, "rb") as handle:
            blob = handle.read()
    except OSError:
        return None, "read"
    text = blob.decode("utf-8", "replace").strip()
    if not text.endswith("}") and not text.endswith("]"):
        return None, "half"
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None, "half"
    if not isinstance(data, dict):
        return None, "half"
    return data, ""


def cap_log(path: str) -> None:
    if not path or not os.path.isfile(path):
        return
    try:
        size = os.path.getsize(path)
    except OSError:
        return
    if size <= LOG_CAP_BYTES:
        return
    try:
        with open(path, "rb") as handle:
            handle.seek(max(0, size - (LOG_CAP_BYTES // 2)))
            tail = handle.read().decode("utf-8", "replace").split("\n", 1)[-1]
    except OSError:
        return
    _atomic_write(path, "# Paper log capped.\n" + tail)


def _last_good_bot(root: str, bot_id: str) -> dict:
    data = _read_json(good_path(root)) or {}
    row = data.get(bot_id)
    return row if isinstance(row, dict) else {}


def _save_good_bot(root: str, bot_id: str, view: dict) -> None:
    data = _read_json(good_path(root)) or {}
    if not isinstance(data, dict):
        data = {}
    data[bot_id] = {
        "has_state": True,
        "cash": view.get("cash"),
        "realized": view.get("realized"),
        "today": view.get("today"),
        "open_risk": view.get("open_risk"),
        "open_count": view.get("open_count"),
        "positions": view.get("positions") or [],
        "trades": view.get("trades") or [],
        "history": view.get("history") or [],
    }
    _write_json(good_path(root), data)


def _load_pause(root: str) -> dict:
    data = _read_json(pause_path(root)) or {}
    return data if isinstance(data, dict) else {}


def bot_paused(root: str, bot_id: str) -> bool:
    data = _load_pause(root)
    if data.get("all"):
        return True
    bots = data.get("bots") if isinstance(data.get("bots"), dict) else {}
    return bool(bots.get(bot_id))


def set_pause(root: str | None, bot_id: str = "", on: bool = True, who: str = "", all_bots: bool = False) -> dict:
    root = _root(root)
    data = _load_pause(root)
    bots = data.get("bots") if isinstance(data.get("bots"), dict) else {}
    if all_bots:
        data["all"] = bool(on)
        what = "Paused every paper bot." if on else "Resumed every paper bot."
    else:
        if bot_id not in {b["id"] for b in BOTS}:
            return {"ok": False, "error": "That bot is not on this desk."}
        if on:
            bots[bot_id] = True
        else:
            bots.pop(bot_id, None)
        data["bots"] = bots
        what = f"{'Paused' if on else 'Resumed'} {bot_id}."
    data["bots"] = bots
    _write_json(pause_path(root), data)
    audit(root, who or "unknown", what)
    return {"ok": True, "error": "", "summary": what}


def _notes(root: str) -> dict:
    data = _read_json(notes_path(root)) or {}
    return data if isinstance(data, dict) else {}


def annotate(root: str | None, bot_id: str, trade_id: str, note: str = "", skipped=None, stake_idea=None, who: str = "") -> dict:
    root = _root(root)
    if bot_id not in {b["id"] for b in BOTS}:
        return {"ok": False, "error": "That bot is not on this desk."}
    key = f"{bot_id}:{_clean(trade_id, 80) or 'desk'}"
    data = _notes(root)
    row = data.get(key) if isinstance(data.get(key), dict) else {}
    row["note"] = _clean(note, 400)
    if skipped is not None:
        row["skipped"] = bool(skipped)
    if stake_idea not in (None, ""):
        idea = _num(stake_idea)
        if idea is None:
            return {"ok": False, "error": "Your stake idea has to be a number."}
        row["stake_idea"] = round(idea, 2)
    row["who"] = _clean(who, 60) or "unknown"
    row["at"] = central_text()
    data[key] = row
    _write_json(notes_path(root), data)
    return {"ok": True, "error": "", "note": row}


def _calendar_warning(root: str, bot_id: str) -> str:
    """Missing calendar is shown on the card. It does not stop the paper check."""
    if bot_id == "kalshi-sp":
        path = _under(root, "kalshi-sp500-paper", "calendar.json")
        if not os.path.isfile(path):
            return "News calendar did not load."
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return "News calendar did not load."
        if not isinstance(data, dict):
            return "News calendar did not load."
        return ""
    if bot_id in ("sports-gap", "memecoin"):
        return "No news calendar on this bot."
    return ""


def _btc_calendar_warning(summary: str) -> str:
    low = str(summary or "").lower()
    if "news calendar failed" in low or "news calendar unavailable" in low or "news calendar did not load" in low:
        return "News calendar did not load."
    return ""


def news_calendar(root: str | None = None) -> dict:
    path = _under(root, "kalshi-sp500-paper", "calendar.json")
    source = "kalshi-sp500-paper/calendar.json"
    data = _read_json(path)
    if not isinstance(data, dict):
        return {"loaded": False, "source": source, "events": []}
    events = []
    for name, days in data.items():
        if str(name).startswith("_") or not isinstance(days, list):
            continue
        for day in days:
            events.append({"name": str(name), "when": str(day), "source": source})
    events.sort(key=lambda row: row["when"])
    return {"loaded": True, "source": source, "events": events[:40]}


def _sports_idle(root: str) -> bool:
    run = _load_runs(root).get("sports-gap")
    if not isinstance(run, dict):
        return False
    text = str(run.get("summary") or "").lower()
    return "no live games" in text or '"live_games": 0' in text or '"live_games":0' in text


def _rate_ok(root: str, bot_id: str, now: dt.datetime | None = None) -> bool:
    now = now or dt.datetime.now(dt.timezone.utc)
    data = _read_json(manual_path(root)) or {}
    prev = _parsed(str(data.get(bot_id) or ""))
    if prev is not None and (now - prev).total_seconds() < MANUAL_GAP_SEC:
        return False
    return True


def _mark_manual(root: str, bot_id: str) -> None:
    data = _read_json(manual_path(root)) or {}
    if not isinstance(data, dict):
        data = {}
    data[bot_id] = _iso(dt.datetime.now(dt.timezone.utc))
    _write_json(manual_path(root), data)


def touch_heartbeat(root: str, now: dt.datetime | None = None) -> None:
    when = now or dt.datetime.now(dt.timezone.utc)
    _write_json(heartbeat_path(root), {"at": _iso(when), "paper_only": True})


def timer_health(root: str | None = None, now: dt.datetime | None = None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=dt.timezone.utc)
    data = _read_json(heartbeat_path(root)) or {}
    when = _parsed(str(data.get("at") or ""))
    if when is None:
        return {"alive": False, "detail": "No timer loop yet.", "age": None, "alert": ""}
    age = int((now - when).total_seconds())
    alive = age <= HEARTBEAT_STALE_SEC
    alert = "" if alive else "Paper timer looks dead. The last loop is too old."
    return {"alive": alive, "detail": "Timer alive." if alive else "Last loop is too old.", "age": age, "alert": alert}


def _note_state_mtime(root: str, bot_id: str, folder: str, state_name: str) -> None:
    stamp = 0.0
    if state_name:
        try:
            stamp = _mtime(_under(root, folder, state_name)) or 0.0
        except RuntimeError:
            stamp = 0.0
    data = _read_json(watch_path(root)) or {}
    if not isinstance(data, dict):
        data = {}
    data[bot_id] = stamp
    _write_json(watch_path(root), data)


def _outside(root: str, bot_id: str, stamp) -> bool:
    data = _read_json(watch_path(root)) or {}
    if not isinstance(data, dict) or bot_id not in data:
        return False
    try:
        prev = float(data.get(bot_id) or 0)
    except (TypeError, ValueError):
        prev = 0.0
    return abs(float(stamp or 0) - prev) > 1


def _next_for(bot_id: str, root: str, now: dt.datetime) -> str:
    if bot_paused(root, bot_id):
        return "Paused"
    now_ct = now.astimezone(CT)
    saved = _load_auto(root)
    best = None
    for slot in AUTO:
        if slot["id"] != bot_id:
            continue
        if "every_sec" in slot:
            prev = _parsed(saved.get(_slot_key(slot)) or "")
            gap = float(slot["every_sec"])
            if bot_id == "sports-gap" and _sports_idle(root):
                gap = max(gap, float(IDLE_SPORTS_SEC))
            when = now if prev is None else prev + dt.timedelta(seconds=gap)
            if when < now:
                when = now
        else:
            start = dt.datetime.combine(now_ct.date(), _hhmm(slot["at_ct"]), CT)
            end = dt.datetime.combine(now_ct.date(), _hhmm(slot["until_ct"]), CT)
            key = _slot_key(slot)
            if now_ct > end or saved.get(key) == now_ct.date().isoformat():
                start = start + dt.timedelta(days=1)
            when = start
        if best is None or when < best:
            best = when
    return central_text(best) if best is not None else ""


def _apply_notes(root: str, bot_id: str, row: dict) -> dict:
    data = _notes(root)
    key = f"{bot_id}:{row.get('fill_id') or row.get('ticker') or row.get('title') or 'desk'}"
    note = data.get(key) if isinstance(data.get(key), dict) else {}
    if not note:
        return row
    row = dict(row)
    row["note"] = note.get("note") or ""
    row["skipped_by_you"] = bool(note.get("skipped"))
    if note.get("stake_idea") is not None:
        row["stake_idea"] = note.get("stake_idea")
        bot_stake = _num(row.get("cost"))
        idea = _num(note.get("stake_idea"))
        if bot_stake is not None and idea is not None:
            row["stake_compare"] = f"You ${idea:.2f}. Bot ${bot_stake:.2f}."
    return row


def _quote_flags(row: dict, now: dt.datetime) -> dict:
    row = dict(row)
    row["price_label"] = "unknown" if row.get("ask") is None else f"{float(row['ask']):.2f}"
    if row.get("bid") is None:
        row["bid_label"] = "unknown"
    else:
        row["bid_label"] = f"{float(row['bid']):.2f}"
    if row.get("fee") is None:
        row["fee_label"] = "unknown"
    else:
        row["fee_label"] = f"{float(row['fee']):.2f}"
    row["stale"] = price_age_flag(row.get("priced_at"), now) == "stale"
    row["clock"] = clock_skew(row.get("priced_at"), now)
    fair = row.get("prob")
    ask = row.get("ask")
    if fair is not None and ask is not None:
        row["disagree"] = disagree_flag(fair, ask)
    else:
        row["disagree"] = ""
    if row.get("source"):
        row["source_line"] = f"{row['source']} · {row.get('priced_at') or 'time unknown'}"
    else:
        row["source_line"] = "Source unknown."
    return row


def _finish_bot(view: dict, spec: dict, root: str) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    view["book_id"] = {"sports": "sports", "kalshi": "kalshi", "btc": "bitcoin", "meme": "meme"}.get(spec.get("kind"), "kalshi")
    view["paused"] = bot_paused(root, spec["id"])
    view["next_run"] = _next_for(spec["id"], root, now)
    view["central_check"] = _central_from_text(view.get("last_check") or "")
    run = view.get("last_run") or {}
    if view.get("paused"):
        status = "skipped"
    elif view.get("read_error"):
        status = "error"
    elif run.get("blocked"):
        status = "blocked"
    elif run.get("ok") is False:
        status = "error"
    elif run.get("ok"):
        status = "running"
    else:
        status = "skipped"
    view["status"] = status
    def _named(rows):
        named = []
        for row in rows or []:
            row = dict(row)
            row["bot"] = spec["id"]
            row["name"] = spec["name"]
            if row.get("priced_at") and not row.get("priced_central"):
                row["priced_central"] = _central_from_text(row["priced_at"])
            named.append(_apply_notes(root, spec["id"], _quote_flags(row, now)))
        return named
    view["positions"] = _named(view.get("positions"))
    view["trades"] = _named(view.get("trades"))
    view["history"] = _named(view.get("history"))
    would = list((run.get("would_have") or []))
    for line in view.get("log") or []:
        low = line.lower()
        if any(word in low for word in ("max open", "not enough paper cash", "loss stop", "would buy")):
            would.append({"what": _clean(line, 180), "why": "A limit blocked a paper buy.", "bot": spec["id"]})
    view["would_have"] = would[:12]
    if not view.get("positions") and not view.get("trades"):
        view["idle_copy"] = f"No paper trades yet. Last check {view['central_check']}. No edge."
    else:
        view["idle_copy"] = ""
    if not view.get("why") and view.get("skip"):
        view["why"] = plain_reason(view.get("skip") or "")
    if not view.get("warning") and spec.get("id") == "btc15m":
        view["warning"] = _btc_calendar_warning(str((view.get("last_run") or {}).get("summary") or ""))
    summary = str(run.get("summary") or "")
    if view.get("data_error"):
        view["feed"] = "api down"
    elif "no live games" in summary.lower():
        view["feed"] = "no games"
    else:
        view["feed"] = source_status(1 if view.get("positions") else 0, view.get("data_error") or "")
    return view


def _books(bots: list) -> list:
    order = (("sports", "Sports"), ("kalshi", "Kalshi"), ("bitcoin", "Bitcoin"), ("meme", "Meme coin"))
    out = []
    for book_id, name in order:
        rows = [bot for bot in bots if bot.get("book_id") == book_id or (book_id == "kalshi" and bot.get("id") == "kalshi-sized")]
        out.append({
            "id": book_id,
            "name": name,
            "bots": [bot["id"] for bot in rows],
            "cash": None if not any(bot.get("cash") is not None for bot in rows) else round(sum(float(bot.get("cash") or 0) for bot in rows if bot.get("cash") is not None), 2),
            "today": round(sum(float(bot.get("today") or 0) for bot in rows), 2),
            "open_risk": round(sum(float(bot.get("open_risk") or 0) for bot in rows), 2),
        })
    return out


def _flatten(bots: list) -> list:
    rows = []
    for bot in bots:
        for pos in bot.get("positions") or []:
            rows.append({**pos, "bot": bot.get("id"), "name": bot.get("name"), "state": "open", "result": "open"})
        for trade in bot.get("history") or []:
            rows.append({**trade, "bot": bot.get("id"), "name": bot.get("name"), "state": "settled"})
    return rows


def _page_window(rows: list, page: int):
    try:
        page_n = max(1, int(page))
    except (TypeError, ValueError):
        page_n = 1
    total = len(rows)
    pages = max(1, math.ceil(total / PAGE_SIZE)) if total else 1
    if page_n > pages:
        page_n = pages
    start = (page_n - 1) * PAGE_SIZE
    return rows[start:start + PAGE_SIZE], page_n, pages, total


def _book(bots: list, q: str = "", filt: str = "all", page: int = 1) -> dict:
    rows = _flatten(bots)
    needle = str(q or "").strip().lower()
    if needle:
        rows = [row for row in rows if needle in " ".join(
            str(row.get(key) or "") for key in ("team", "ticker", "game", "what", "title", "when", "name")).lower()]
    kind = str(filt or "all").lower()
    if kind == "open":
        chosen = [row for row in rows if row.get("state") == "open"]
        return {"rows": chosen, "page": 1, "pages": 1, "total": len(chosen), "filter": kind, "q": needle}
    if kind == "settled":
        chosen = [row for row in rows if row.get("state") == "settled"]
    elif kind == "wins":
        chosen = [row for row in rows if row.get("result") == "won"]
    elif kind == "losses":
        chosen = [row for row in rows if row.get("result") == "lost"]
    else:
        opens = [row for row in rows if row.get("state") == "open"]
        closed = [row for row in rows if row.get("state") != "open"]
        window, page_n, pages, _total = _page_window(closed, page)
        return {
            "rows": opens + window,
            "page": page_n,
            "pages": pages,
            "total": len(opens) + len(closed),
            "filter": kind,
            "q": needle,
        }
    window, page_n, pages, total = _page_window(chosen, page)
    return {"rows": window, "page": page_n, "pages": pages, "total": total, "filter": kind, "q": needle}


def _week_pnl(bots: list, day: dt.date) -> tuple:
    start = day - dt.timedelta(days=day.weekday())
    end = start + dt.timedelta(days=6)
    total = 0.0
    wins = losses = 0
    biggest = None
    for row in _flatten(bots):
        pnl = _num(row.get("pnl"))
        if pnl is None or row.get("state") != "settled":
            continue
        when = str(row.get("when") or "")[:10]
        try:
            stamp = dt.date.fromisoformat(when)
        except ValueError:
            continue
        if not (start <= stamp <= end):
            continue
        total += pnl
        if pnl > 0:
            wins += 1
        elif pnl < 0:
            losses += 1
        if biggest is None or abs(pnl) > abs(biggest):
            biggest = pnl
    return round(total, 2), wins, losses, None if biggest is None else round(biggest, 2)


def _streak(bots: list) -> dict:
    rows = [row for row in _flatten(bots) if row.get("state") == "settled" and _num(row.get("pnl")) is not None]
    rows.sort(key=lambda row: str(row.get("when") or ""))
    if not rows:
        return {"kind": "none", "n": 0, "text": "No settled paper trades yet."}
    last_pnl = _num(rows[-1].get("pnl")) or 0
    last = 1 if last_pnl > 0 else (-1 if last_pnl < 0 else 0)
    count = 0
    for row in reversed(rows):
        pnl = _num(row.get("pnl")) or 0
        sign = 1 if pnl > 0 else (-1 if pnl < 0 else 0)
        if sign == 0 or sign != last:
            break
        count += 1
    if last > 0:
        word = "win" if count == 1 else "wins"
        return {"kind": "win", "n": count, "text": f"{count} paper {word} in a row."}
    if last < 0:
        word = "loss" if count == 1 else "losses"
        return {"kind": "loss", "n": count, "text": f"{count} paper {word} in a row."}
    return {"kind": "flat", "n": 0, "text": "The last paper trade was flat."}


def _curve_name(row: dict) -> str:
    for key in ("game", "ticker", "team", "symbol", "what", "title"):
        text = _clean(row.get(key) or "", 120)
        if text:
            return text
    return ""


def _curve_clock(row: dict, raw: str, day: bool) -> str:
    """Chicago time already stored on the slip. A date-only slip does not grow a clock."""
    if day:
        try:
            stamp = dt.date.fromisoformat(str(raw or "").strip())
        except ValueError:
            return _clean(raw, 40)
        return f"{stamp.strftime('%B')} {stamp.day}, {stamp.year}"
    clock = _clean(row.get("closed_at") or "", 80)
    if clock and clock != "no check yet":
        return clock
    clock = _central_from_text(raw) if raw else ""
    if clock in ("", "no check yet"):
        return ""
    return _clean(clock, 80)


def _equity_curve(bots: list) -> list:
    """Cumulative settled paper P/L. No point is invented when nothing has settled.

    Each point is one settled paper slip. The chart can name that slip without
    adding a dot that was not a trade.
    """
    rows = [row for row in _flatten(bots) if row.get("state") == "settled" and _num(row.get("pnl")) is not None]
    keyed = []
    for index, row in enumerate(rows):
        when = _ct_when(row.get("when"))
        keyed.append((0 if when is not None else 1, when.timestamp() if when is not None else 0.0, index, row, when))
    keyed.sort(key=lambda item: (item[0], item[1], item[2]))
    total = 0.0
    points = []
    for _rank, _ts, _index, row, when in keyed:
        total = round(total + float(row["pnl"]), 2)
        raw = str(row.get("when") or "")
        day = _date_only(raw)
        stake = _num(row.get("cost"))
        payout = _num(row.get("payout"))
        points.append({
            "t": when.isoformat(timespec="seconds") if when is not None else "",
            "v": total,
            "day": day,
            "when": _curve_clock(row, raw, day),
            "name": _curve_name(row),
            "stake": None if stake is None else round(stake, 2),
            "payout": None if payout is None else round(payout, 2),
            "pnl": round(float(row["pnl"]), 2),
        })
    return points[-180:]


def _stretch_pct(points: list, start_at: int, end_at: int, dollars: float, start: float):
    """Percent move over a stretch. A zero start uses the stakes in the stretch."""
    base = abs(start)
    if base >= 0.01:
        return round(dollars / base * 100.0, 1)
    stake = 0.0
    saw = False
    for point in points[start_at + 1:end_at + 1]:
        number = _num(point.get("stake"))
        if number is None:
            continue
        saw = True
        stake += abs(number)
    if saw and stake >= 0.01:
        return round(dollars / stake * 100.0, 1)
    return None


def _equity_spikes(points: list) -> list:
    """Sharp up or down stretches on the settled curve. Does not add points.

    A step is sharp when it dwarfs the typical step on this curve. Neighboring
    sharp steps that move the same way are one stretch. Percent is the dollar
    move divided by the equity at the start of that stretch.
    """
    vals = []
    for point in points or []:
        number = _num(point.get("v") if isinstance(point, dict) else None)
        if number is None:
            return []
        vals.append(number)
    if len(vals) < 2:
        return []
    steps = []
    for index in range(1, len(vals)):
        delta = round(vals[index] - vals[index - 1], 2)
        if abs(delta) < 0.005:
            continue
        steps.append((index - 1, index, delta))
    if not steps:
        return []
    magnitudes = sorted(abs(delta) for _a, _b, delta in steps)
    median = magnitudes[len(magnitudes) // 2]
    span = max(vals) - min(vals)
    bar = 0.01 if len(steps) == 1 else max(median * 1.8, span * 0.22, 0.01)
    chosen = [step for step in steps if abs(step[2]) + 1e-9 >= bar]
    merged = []
    for start_at, end_at, dollars in chosen:
        if merged and merged[-1][1] == start_at and (merged[-1][2] > 0) == (dollars > 0):
            prev_from, _prev_to, prev_dollars = merged[-1]
            merged[-1] = (prev_from, end_at, round(prev_dollars + dollars, 2))
        else:
            merged.append((start_at, end_at, dollars))
    spikes = []
    for start_at, end_at, dollars in merged:
        start = vals[start_at]
        spikes.append({
            "from": start_at,
            "to": end_at,
            "dollars": dollars,
            "pct": _stretch_pct(points, start_at, end_at, dollars, start),
        })
    return spikes


def _digest(bots: list) -> str:
    parts = []
    for bot in bots:
        parts.append(
            f"{bot.get('id')}:{bot.get('cash')}:{bot.get('today')}:{bot.get('open_count')}:{len(bot.get('history') or [])}"
        )
    return "|".join(parts)


def _changes(root: str, bots: list) -> dict:
    current = _digest(bots)
    saved = _read_json(seen_path(root)) or {}
    previous = str(saved.get("digest") or "")
    if not previous:
        text = "This is the first look saved on this desk."
    elif previous == current:
        text = "Nothing changed since you last looked."
    else:
        text = "The paper book changed since you last looked."
    return {"text": text, "changed": bool(previous and previous != current), "at": saved.get("at") or ""}


def mark_seen(root: str | None = None) -> dict:
    root = _root(root)
    bots = snapshot(root)["bots"]
    payload = {"digest": _digest(bots), "at": central_text()}
    _write_json(seen_path(root), payload)
    return payload


def _desk_row(bots: list, cashes: list, realized_rows: list, last_check: str, gate: str, cfg: dict, root: str) -> dict:
    day = _today()
    week, wins, losses, swing = _week_pnl(bots, day)
    goal = float(cfg.get("week_goal") or 0)
    if goal <= 0:
        bar = 0
    else:
        bar = max(0, min(100, int(round(100 * week / goal))))
    trades_today = 0
    for row in _flatten(bots):
        when = str(row.get("when") or "")
        if _day_hit(when, day):
            trades_today += 1
    nxt = ""
    for bot in bots:
        text = bot.get("next_run") or ""
        if text and text != "Paused" and (not nxt or text < nxt):
            nxt = text
    central = _central_from_text(last_check)
    curve = _equity_curve(bots)
    spikes = _equity_spikes(curve)
    return {
        "cash": None if not cashes else round(sum(cashes), 2),
        "realized": None if not realized_rows else round(sum(realized_rows), 2),
        "today": round(sum(float(bot.get("today") or 0) for bot in bots), 2),
        "open_risk": round(sum(float(bot.get("open_risk") or 0) for bot in bots), 2),
        "open_count": int(sum(int(bot.get("open_count") or 0) for bot in bots)),
        "last_check": last_check,
        "central_check": central,
        "next_check": nxt or "No timer slot.",
        "trades_today": trades_today,
        "status_line": f"Last check {central}. Next check {nxt or 'no timer slot'}. Trades today {trades_today}.",
        "gate": gate,
        "week": week,
        "week_wins": wins,
        "week_losses": losses,
        "biggest_swing": swing,
        "goal": goal,
        "goal_bar": bar,
        "streak": _streak(bots),
        "equity": [point["v"] for point in curve][-40:],
        "curve": curve,
        "spikes": spikes,
        "news": news_calendar(root),
        "paused_all": bool(_load_pause(root).get("all")),
    }


def security_checklist(root: str | None = None, page: str = "") -> list:
    health = timer_health(root)
    backup = _read_json(backup_meta_path(root)) or {}
    keyed = page_has_key(page)
    mounted = os.path.isdir("/data")
    return [
        {"id": "volume", "ok": mounted, "label": "Volume on /data",
         "detail": "Mounted." if mounted else "No /data volume on this machine."},
        {"id": "page", "ok": not keyed, "label": "No key in the page",
         "detail": "No key in the page." if not keyed else "A key-like value is in the page."},
        {"id": "timer", "ok": bool(health.get("alive")), "label": "Timer alive", "detail": health.get("detail") or ""},
        {"id": "backup", "ok": bool(backup.get("at")), "label": "Last backup",
         "detail": str(backup.get("at") or "No paper backup yet.")},
    ]


def backup_paper(root: str | None = None, dest: str | None = None) -> list:
    """Copy paper state next to a picks backup folder. No keys, no wallets."""
    root = _root(root)
    folder = dest or os.path.join(root, "pimp-backup")
    os.makedirs(folder, exist_ok=True)
    copied = []
    for spec in BOTS:
        name = spec.get("state") or ""
        if not name:
            continue
        try:
            src = _under(root, spec["folder"], name)
        except RuntimeError:
            continue
        if not os.path.isfile(src):
            continue
        dest_name = f"paper_{spec['id']}_{name}"
        shutil.copy2(src, os.path.join(folder, dest_name))
        copied.append(dest_name)
    _write_json(backup_meta_path(root), {"at": central_text(), "files": copied, "paper_only": True})
    return copied


def _alert_keys(bots: list) -> tuple:
    opens, closes = [], []
    for bot in bots:
        for index, pos in enumerate(bot.get("positions") or []):
            opens.append(f"{bot.get('id')}|{pos.get('fill_id') or pos.get('title')}|{pos.get('when')}|{index}")
        for index, trade in enumerate(bot.get("history") or []):
            if trade.get("pnl") is None:
                continue
            closes.append(f"{bot.get('id')}|{trade.get('fill_id') or trade.get('what')}|{trade.get('when')}|{trade.get('pnl')}|{index}")
    return opens, closes


def drain_alerts(root: str | None = None, now: dt.datetime | None = None) -> list:
    """Trade open/close lines. Quiet hours hold them. The first look only sets a baseline."""
    root = _root(root)
    now = now or dt.datetime.now(dt.timezone.utc)
    bots = snapshot(root)["bots"]
    opens, closes = _alert_keys(bots)
    saved = _read_json(alert_path(root)) or {}
    queue = list(saved.get("queue") or []) if isinstance(saved.get("queue"), list) else []
    fresh = []
    if saved.get("seen"):
        old_open = set(saved.get("opens") or [])
        old_close = set(saved.get("closes") or [])
        for key in opens:
            if key not in old_open:
                fresh.append("Paper trade opened. " + key.split("|", 2)[1][:140])
        for key in closes:
            if key not in old_close:
                fresh.append("Paper trade closed. " + key.split("|", 2)[1][:140])
        for bot in bots:
            if bot.get("outside"):
                fresh.append(f"Paper state for {bot.get('name')} changed outside a bot run.")
    messages = queue + fresh
    if in_quiet(now, load_settings(root)):
        _write_json(alert_path(root), {"seen": True, "opens": opens, "closes": closes, "queue": messages[-40:]})
        return []
    _write_json(alert_path(root), {"seen": True, "opens": opens, "closes": closes, "queue": []})
    return messages[:20]


def recap_text(root: str | None, now: dt.datetime | None = None, kind: str = "day") -> str:
    now = now or dt.datetime.now(dt.timezone.utc)
    snap = snapshot(root)
    desk = snap["desk"]
    when = central_text(now)
    lines = [
        f"Paper desk recap · {when}",
        desk.get("status_line") or "",
        f"Today's paper P/L {desk.get('today')}. Paper cash {desk.get('cash')}. Open risk {desk.get('open_risk')}.",
        "No real orders. This is paper only.",
    ]
    if kind == "week" or now.astimezone(CT).weekday() == 6:
        swing = desk.get("biggest_swing")
        swing_text = "none" if swing is None else f"{swing}"
        lines.append(
            f"Week: wins {desk.get('week_wins')}, losses {desk.get('week_losses')}, "
            f"biggest paper swing {swing_text}."
        )
    return "\n".join(line for line in lines if line)


def take_recap(root: str | None = None, now: dt.datetime | None = None) -> str:
    root = _root(root)
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=dt.timezone.utc)
    local = now.astimezone(CT)
    if local.hour < 21:
        return ""
    saved = _read_json(recap_path(root)) or {}
    day = local.date().isoformat()
    if saved.get("day") == day:
        return ""
    kind = "week" if local.weekday() == 6 else "day"
    text = recap_text(root, now, kind)
    _write_json(recap_path(root), {"day": day, "kind": kind, "at": central_text(now)})
    return text


def _xlsx_cell(value) -> str:
    text = "" if value is None else str(value)
    text = (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    return f'<c t="inlineStr"><is><t>{text}</t></is></c>'


def export_xlsx(root: str | None = None) -> bytes:
    """A real xlsx workbook of the paper book. Excel opens it. No live orders."""
    snap = snapshot(root)
    header = ["Book", "State", "Ticker or game", "Side", "Contracts", "Stake", "Entry price", "Fee",
              "Model probability", "Score at entry", "Why it opened", "Price source", "Price time",
              "Close time", "Exit reason", "Payout", "P/L"]
    table = [header]

    def _cell(value, missing="unknown"):
        return missing if value in (None, "") else value

    for row in _flatten(snap["bots"]):
        game = row.get("game") or row.get("ticker") or row.get("what") or row.get("title") or ""
        table.append([
            row.get("name") or "",
            row.get("state") or row.get("result") or "",
            _cell(game),
            _cell(row.get("side")),
            _cell(row.get("contracts")),
            _cell(row.get("cost")),
            _cell(row.get("ask")),
            _cell(row.get("fee")),
            _cell(row.get("prob")),
            _cell(row.get("score")),
            _cell(row.get("why_open") or row.get("why")),
            _cell(row.get("source")),
            _cell(row.get("priced_central") or row.get("priced_at")),
            _cell(row.get("closed_at")) if row.get("state") != "open" else "",
            _cell(row.get("exit_reason")) if row.get("state") != "open" else "",
            _cell(row.get("payout")) if row.get("state") != "open" else "",
            "" if row.get("pnl") is None else row.get("pnl"),
        ])
    if len(table) == 1:
        table.append(["", "", "No paper trades yet.", "", "", "", "", "", "", "", "No edge.", "", "", "", "", "", ""])
    sheet_rows = []
    for index, row in enumerate(table, start=1):
        cells = "".join(f'{_xlsx_cell(value)}' for value in row)
        # column letters are applied by Excel from cell order when r is omitted
        sheet_rows.append(f'<row r="{index}">{cells}</row>')
    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(sheet_rows)}</sheetData></worksheet>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '</Types>'
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        '</Relationships>'
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Paper book" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        '</Relationships>'
    )
    blob = io.BytesIO()
    with zipfile.ZipFile(blob, "w", compression=zipfile.ZIP_DEFLATED) as book:
        book.writestr("[Content_Types].xml", content_types)
        book.writestr("_rels/.rels", rels)
        book.writestr("xl/workbook.xml", workbook)
        book.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        book.writestr("xl/worksheets/sheet1.xml", sheet)
    return blob.getvalue()
