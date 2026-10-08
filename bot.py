"""
Picks Bot - a Discord bot that tracks a group's sports bets.

Picks
  * /pick          log a pick (Kalshi, PrizePicks, sportsbook, anything)
  * /leg           grade one leg of a parlay: hit / miss / push
  * /result        settle a pick: win / loss / push / void (or reopen it)
  * /open          list picks that are still waiting on a result
  * /record        one person's record, profit, ROI and leg hit rate
  * /leaderboard   everyone ranked by net profit
  * /edit /delete  fix or remove a pick
  * /export        download every pick as a CSV (opens in Excel / Sheets)

Channels
  * /receipts      turn the current channel into a "receipts" channel
  * /recapchannel  post the weekly recap and open-pick reminders here
  * /recap         show the last 7 days right now

Players
  * /player add | note | view | list | remove

Ask
  * @mention the bot with a question and it researches and answers
    (needs ANTHROPIC_API_KEY)

Setup is in README.md.
"""

from __future__ import annotations

import asyncio
import base64
import csv
import hashlib
import io
import json
import logging
import os
import re
import sqlite3
import tempfile
import time
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("picksbot")
BOT_VERSION = "2026-10-08 r11"   # shown in /help and the startup log, so you can tell which upload is live


def env(name: str, default: str) -> str:
    """A setting from the environment; blank counts as not set."""
    return (os.getenv(name) or "").strip() or default


def env_int(name: str, default: int, low: int = 0, high: int = 10**6) -> int:
    try:
        value = int(env(name, str(default)))
        if low <= value <= high:
            return value
    except ValueError:
        pass
    log.warning("%s should be a whole number from %d to %d; using %d", name, low, high, default)
    return default


TOKEN = env("DISCORD_TOKEN", "")
GUILD_ID = env("GUILD_ID", "")
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = env("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
ASK_MODEL = env("ASK_MODEL", "claude-sonnet-5-5")
ASK_DAILY_LIMIT = env_int("ASK_DAILY_LIMIT", 40)
ASK_COOLDOWN_SECONDS = env_int("ASK_COOLDOWN_SECONDS", 20)
DB_PATH = env("DB_PATH", "picks.db")

try:
    TZ = ZoneInfo(env("TIMEZONE", "America/Chicago"))
except Exception:
    log.warning("Unknown TIMEZONE; using America/Chicago")
    TZ = ZoneInfo("America/Chicago")
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_day = env("RECAP_DAY", "sunday").lower()
RECAP_DAY = DAYS.index(_day) if _day in DAYS else DAYS.index("sunday")
RECAP_HOUR = env_int("RECAP_HOUR", 20, 0, 23)        # 8 PM
REMIND_HOUR = env_int("REMIND_HOUR", 12, 0, 23)      # noon
REMIND_AFTER_DAYS = env_int("REMIND_AFTER_DAYS", 3, 1, 365)
AUTOGRADE_AFTER_HOURS = env_int("AUTOGRADE_AFTER_HOURS", 48, 0, 24 * 60)   # 0 turns it off
AUTOGRADE_DAILY_LIMIT = env_int("AUTOGRADE_DAILY_LIMIT", 30)
AUTOGRADE_MAX_TRIES = 3

# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------

_conn: Optional[sqlite3.Connection] = None


def db() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        # Make sure the folder exists (on a cloud host this is the storage volume).
        os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
        _conn = sqlite3.connect(DB_PATH)
        _conn.row_factory = sqlite3.Row
        _conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS picks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id    INTEGER NOT NULL,
                bettor_key  TEXT    NOT NULL,   -- Discord user id, or "label:name"
                bettor_name TEXT    NOT NULL,
                bettor_id   INTEGER,            -- NULL for label-only bettors
                logged_by   INTEGER NOT NULL,
                platform    TEXT    NOT NULL,
                sport       TEXT,
                description TEXT    NOT NULL,
                legs        TEXT,               -- one leg per line
                cost        REAL    NOT NULL,   -- amount risked
                payout      REAL    NOT NULL,   -- total paid back if it wins
                status      TEXT    NOT NULL DEFAULT 'open',
                returned    REAL,               -- amount actually paid back
                slip_url    TEXT,
                created_at  TEXT    NOT NULL,
                settled_at  TEXT
            );
            CREATE TABLE IF NOT EXISTS receipt_channels (
                guild_id   INTEGER NOT NULL,
                channel_id INTEGER NOT NULL PRIMARY KEY
            );
            CREATE TABLE IF NOT EXISTS legs (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                pick_id INTEGER NOT NULL,
                idx     INTEGER NOT NULL,       -- 1, 2, 3... as shown to people
                text    TEXT    NOT NULL,
                status  TEXT    NOT NULL DEFAULT 'open',   -- open / hit / miss / push
                UNIQUE (pick_id, idx)
            );
            CREATE TABLE IF NOT EXISTS settings (
                guild_id INTEGER NOT NULL,
                key      TEXT    NOT NULL,
                value    TEXT,
                PRIMARY KEY (guild_id, key)
            );
            CREATE TABLE IF NOT EXISTS players (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id   INTEGER NOT NULL,
                name       TEXT    NOT NULL,
                name_key   TEXT    NOT NULL,
                team       TEXT,
                sport      TEXT,
                role       TEXT,
                created_by INTEGER,
                created_at TEXT    NOT NULL,
                UNIQUE (guild_id, name_key)
            );
            CREATE TABLE IF NOT EXISTS follows (
                pick_id    INTEGER NOT NULL,
                user_id    INTEGER NOT NULL,
                user_name  TEXT,
                kind       TEXT    NOT NULL,   -- tail / fade
                created_at TEXT    NOT NULL,
                PRIMARY KEY (pick_id, user_id)
            );
            CREATE TABLE IF NOT EXISTS challenges (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id        INTEGER NOT NULL,
                challenger_id   INTEGER NOT NULL,
                challenger_name TEXT    NOT NULL,
                opponent_id     INTEGER NOT NULL,
                opponent_name   TEXT    NOT NULL,
                claim           TEXT    NOT NULL,
                stakes          TEXT,
                status          TEXT    NOT NULL DEFAULT 'pending',
                winner_id       INTEGER,
                created_at      TEXT    NOT NULL,
                settled_at      TEXT
            );
            CREATE TABLE IF NOT EXISTS locks (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id        INTEGER NOT NULL,
                user_id         INTEGER NOT NULL,
                user_name       TEXT    NOT NULL,
                week            TEXT    NOT NULL,   -- e.g. 2026-W41
                text            TEXT    NOT NULL,
                sport           TEXT,
                status          TEXT    NOT NULL DEFAULT 'open',
                why             TEXT,
                created_at      TEXT    NOT NULL,
                settled_at      TEXT,
                autograde_at    TEXT,
                autograde_tries INTEGER,
                UNIQUE (guild_id, user_id, week)
            );
            CREATE TABLE IF NOT EXISTS pickem_rounds (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id    INTEGER NOT NULL,
                league      TEXT    NOT NULL,
                label       TEXT    NOT NULL,
                channel_id  INTEGER,
                created_by  INTEGER,
                created_at  TEXT    NOT NULL,
                finished_at TEXT
            );
            CREATE TABLE IF NOT EXISTS pickem_games (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                round_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                event_id TEXT    NOT NULL,
                league   TEXT    NOT NULL,
                start    TEXT    NOT NULL,
                away     TEXT    NOT NULL,
                home     TEXT    NOT NULL,
                winner   INTEGER,              -- 0 away, 1 home, -1 no result
                score    TEXT
            );
            CREATE TABLE IF NOT EXISTS pickem_picks (
                game_id    INTEGER NOT NULL,
                user_id    INTEGER NOT NULL,
                user_name  TEXT    NOT NULL,
                side       INTEGER NOT NULL,   -- 0 away, 1 home
                created_at TEXT    NOT NULL,
                PRIMARY KEY (game_id, user_id)
            );
            CREATE TABLE IF NOT EXISTS seasons (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id   INTEGER NOT NULL,
                name       TEXT    NOT NULL,
                started_at TEXT    NOT NULL,
                ended_at   TEXT
            );
            CREATE TABLE IF NOT EXISTS pings (
                pick_id  INTEGER NOT NULL,
                event_id TEXT    NOT NULL,
                kind     TEXT    NOT NULL,   -- start / half
                PRIMARY KEY (pick_id, event_id, kind)
            );
            CREATE TABLE IF NOT EXISTS survivor_pools (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id   INTEGER NOT NULL,
                name       TEXT    NOT NULL,
                channel_id INTEGER,
                created_at TEXT    NOT NULL,
                ended_at   TEXT
            );
            CREATE TABLE IF NOT EXISTS survivor_picks (
                pool_id    INTEGER NOT NULL,
                user_id    INTEGER NOT NULL,
                user_name  TEXT    NOT NULL,
                week_key   TEXT    NOT NULL,
                team       TEXT    NOT NULL,
                team_id    TEXT    NOT NULL,
                event_id   TEXT    NOT NULL,
                start      TEXT    NOT NULL,
                result     TEXT,
                created_at TEXT    NOT NULL,
                PRIMARY KEY (pool_id, user_id, week_key)
            );
            CREATE TABLE IF NOT EXISTS reminders (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id   INTEGER,
                user_id    INTEGER NOT NULL,
                channel_id INTEGER,
                text       TEXT    NOT NULL,
                due_at     TEXT    NOT NULL,
                created_at TEXT    NOT NULL,
                sent_at    TEXT
            );
            CREATE TABLE IF NOT EXISTS sweats (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id   INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                pick_id    INTEGER NOT NULL,
                user_id    INTEGER,
                state      TEXT,
                created_at TEXT    NOT NULL,
                ended_at   TEXT
            );
            CREATE TABLE IF NOT EXISTS injury_alerts (
                pick_id INTEGER NOT NULL,
                player  TEXT    NOT NULL,
                status  TEXT    NOT NULL,
                sent_at TEXT    NOT NULL,
                PRIMARY KEY (pick_id, player, status)
            );
            CREATE TABLE IF NOT EXISTS gp_rounds (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id   INTEGER NOT NULL,
                week       TEXT    NOT NULL,
                channel_id INTEGER,
                message_id INTEGER,
                created_at TEXT    NOT NULL,
                UNIQUE (guild_id, week)
            );
            CREATE TABLE IF NOT EXISTS gp_legs (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                round_id   INTEGER NOT NULL,
                user_id    INTEGER NOT NULL,
                user_name  TEXT    NOT NULL,
                text       TEXT    NOT NULL,
                sport      TEXT,
                status     TEXT    NOT NULL DEFAULT 'open',
                why        TEXT,
                created_at TEXT    NOT NULL,
                updated_at TEXT,
                UNIQUE (round_id, user_id)
            );
            CREATE TABLE IF NOT EXISTS cashflows (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id   INTEGER NOT NULL,
                user_id    INTEGER NOT NULL,
                platform   TEXT    NOT NULL,
                kind       TEXT    NOT NULL,   -- deposit / withdraw
                amount     REAL    NOT NULL,
                note       TEXT,
                created_at TEXT    NOT NULL
            );
            CREATE TABLE IF NOT EXISTS coin_tx (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id   INTEGER NOT NULL,
                user_id    INTEGER NOT NULL,
                delta      INTEGER NOT NULL,
                reason     TEXT    NOT NULL,
                ref        TEXT    UNIQUE,
                created_at TEXT    NOT NULL
            );
            CREATE TABLE IF NOT EXISTS markets (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id     INTEGER NOT NULL,
                creator_id   INTEGER NOT NULL,
                creator_name TEXT,
                question     TEXT    NOT NULL,
                closes_at    TEXT,
                status       TEXT    NOT NULL DEFAULT 'open',
                outcome      TEXT,
                channel_id   INTEGER,
                message_id   INTEGER,
                created_at   TEXT    NOT NULL
            );
            CREATE TABLE IF NOT EXISTS market_bets (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                market_id  INTEGER NOT NULL,
                user_id    INTEGER NOT NULL,
                user_name  TEXT    NOT NULL,
                side       TEXT    NOT NULL,
                amount     INTEGER NOT NULL,
                created_at TEXT    NOT NULL
            );
            CREATE TABLE IF NOT EXISTS takes (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id   INTEGER NOT NULL,
                user_id    INTEGER NOT NULL,
                user_name  TEXT    NOT NULL,
                text       TEXT    NOT NULL,
                due_at     TEXT,
                status     TEXT    NOT NULL DEFAULT 'open',
                channel_id INTEGER,
                created_at TEXT    NOT NULL,
                nudged_at  TEXT,
                graded_at  TEXT
            );
            CREATE TABLE IF NOT EXISTS take_votes (
                take_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                vote    TEXT    NOT NULL,
                PRIMARY KEY (take_id, user_id)
            );
            CREATE TABLE IF NOT EXISTS potd (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id   INTEGER NOT NULL,
                day        TEXT    NOT NULL,
                player     TEXT    NOT NULL,
                athlete_id TEXT,
                path       TEXT    NOT NULL,
                stat_key   TEXT    NOT NULL,
                line       REAL    NOT NULL,
                event_id   TEXT,
                start      TEXT    NOT NULL,
                game       TEXT,
                trend      TEXT,
                channel_id INTEGER,
                message_id INTEGER,
                result     TEXT,
                value      REAL,
                created_at TEXT    NOT NULL
            );
            CREATE TABLE IF NOT EXISTS potd_votes (
                potd_id   INTEGER NOT NULL,
                user_id   INTEGER NOT NULL,
                user_name TEXT    NOT NULL,
                side      TEXT    NOT NULL,
                PRIMARY KEY (potd_id, user_id)
            );
            CREATE TABLE IF NOT EXISTS player_notes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id   INTEGER NOT NULL,
                author_id   INTEGER,
                author_name TEXT    NOT NULL,
                text        TEXT    NOT NULL,
                created_at  TEXT    NOT NULL
            );
            """
        )
        # Upgrades for databases made by the first version of the bot.
        cols = {r[1] for r in _conn.execute("PRAGMA table_info(picks)")}
        for col, kind in (("reminded_at", "TEXT"), ("notes", "TEXT"), ("import_key", "TEXT"),
                          ("autograde_at", "TEXT"), ("autograde_tries", "INTEGER"),
                          ("live_checked_at", "TEXT"), ("hof_posted", "TEXT"), ("kalshi_ticker", "TEXT"),
                          ("kalshi_side", "TEXT"), ("kalshi_checked_at", "TEXT"), ("copied_from", "INTEGER"),
                          ("preseason", "INTEGER"), ("hidden", "INTEGER"), ("revealed_at", "TEXT"),
                          ("one_leg_at", "TEXT"), ("reacted", "INTEGER"), ("pp_offered", "TEXT")):
            if col not in cols:
                _conn.execute(f"ALTER TABLE picks ADD COLUMN {col} {kind}")
        leg_cols = {r[1] for r in _conn.execute("PRAGMA table_info(legs)")}
        for col, kind in (("margin", "REAL"), ("note", "TEXT")):
            if col not in leg_cols:
                _conn.execute(f"ALTER TABLE legs ADD COLUMN {col} {kind}")
        lock_cols = {r[1] for r in _conn.execute("PRAGMA table_info(locks)")}
        if "live_checked_at" not in lock_cols:
            _conn.execute("ALTER TABLE locks ADD COLUMN live_checked_at TEXT")
        for p in _conn.execute(
            """SELECT id, legs FROM picks WHERE legs IS NOT NULL
               AND id NOT IN (SELECT DISTINCT pick_id FROM legs)""").fetchall():
            _write_legs(_conn, p["id"], p["legs"])
        _conn.commit()
    return _conn


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_setting(guild_id: int, key: str) -> Optional[str]:
    row = db().execute("SELECT value FROM settings WHERE guild_id = ? AND key = ?",
                       (guild_id, key)).fetchone()
    return row["value"] if row else None


def set_setting(guild_id: int, key: str, value: Optional[str]) -> None:
    if value is None:
        db().execute("DELETE FROM settings WHERE guild_id = ? AND key = ?", (guild_id, key))
    else:
        db().execute("INSERT OR REPLACE INTO settings (guild_id, key, value) VALUES (?, ?, ?)",
                     (guild_id, key, value))
    db().commit()


# ---- picks ----------------------------------------------------------------

def _write_legs(conn: sqlite3.Connection, pick_id: int, legs_text: Optional[str]) -> None:
    conn.execute("DELETE FROM legs WHERE pick_id = ?", (pick_id,))
    lines = [x.strip() for x in (legs_text or "").splitlines() if x.strip()]
    conn.executemany("INSERT INTO legs (pick_id, idx, text) VALUES (?, ?, ?)",
                     [(pick_id, i, t) for i, t in enumerate(lines, start=1)])


def set_legs(pick_id: int, legs_text: Optional[str]) -> None:
    _write_legs(db(), pick_id, legs_text)
    db().commit()


def get_legs(pick_id: int) -> list[sqlite3.Row]:
    return db().execute("SELECT * FROM legs WHERE pick_id = ? ORDER BY idx", (pick_id,)).fetchall()


def insert_pick(
    *,
    guild_id: int,
    bettor_key: str,
    bettor_name: str,
    bettor_id: Optional[int],
    logged_by: int,
    platform: str,
    sport: Optional[str],
    description: str,
    legs: Optional[str],
    cost: float,
    payout: float,
    slip_url: Optional[str] = None,
) -> int:
    cur = db().execute(
        """INSERT INTO picks (guild_id, bettor_key, bettor_name, bettor_id, logged_by,
                              platform, sport, description, legs, cost, payout,
                              slip_url, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (guild_id, bettor_key, bettor_name, bettor_id, logged_by, platform, sport,
         description, legs, cost, payout, slip_url, now_iso()),
    )
    _write_legs(db(), cur.lastrowid, legs)
    db().commit()
    return cur.lastrowid


def get_pick(guild_id: int, pick_id: int) -> Optional[sqlite3.Row]:
    return db().execute(
        "SELECT * FROM picks WHERE id = ? AND guild_id = ?", (pick_id, guild_id)
    ).fetchone()


def default_return(status: str, cost: float, payout: float) -> float:
    """What comes back for a given outcome when no exact amount is supplied."""
    if status == "win":
        return payout
    if status == "loss":
        return 0.0
    return cost  # push / void: stake returned


def settle_pick(guild_id: int, pick_id: int, status: str,
                returned: Optional[float] = None) -> Optional[sqlite3.Row]:
    pick = get_pick(guild_id, pick_id)
    if pick is None:
        return None
    if returned is None and status in ("win", "loss", "push") and pick["status"] == "open":
        propagate_to_copies(pick_id, None, status)
    if status == "open":
        db().execute(
            "UPDATE picks SET status='open', returned=NULL, settled_at=NULL WHERE id=?",
            (pick_id,),
        )
    else:
        if returned is None:
            returned = default_return(status, pick["cost"], pick["payout"])
        db().execute(
            "UPDATE picks SET status=?, returned=?, settled_at=? WHERE id=?",
            (status, returned, now_iso(), pick_id),
        )
    db().commit()
    return get_pick(guild_id, pick_id)


def grade_leg(guild_id: int, pick_id: int, idx: int,
              status: str) -> tuple[Optional[sqlite3.Row], str]:
    """Grade one leg. Settles the pick when the legs decide it.
    Returns (pick, note for the person)."""
    db().execute("UPDATE legs SET status = ? WHERE pick_id = ? AND idx = ?",
                 (status, pick_id, idx))
    db().commit()
    if status != "open":
        propagate_to_copies(pick_id, idx, status)
    pick = get_pick(guild_id, pick_id)
    legs = get_legs(pick_id)
    if pick["status"] != "open" or status == "open":
        return pick, ""
    statuses = [leg["status"] for leg in legs]
    if all(s == "hit" for s in statuses):
        return settle_pick(guild_id, pick_id, "win"), "Every leg hit, so I marked it a **win**."
    if "miss" in statuses:
        if pick["platform"].lower() == "prizepicks":
            return pick, ("A leg missed. Flex entries can still pay out, so settle this one "
                          f"with `/result pick_id:{pick_id}` once it's final.")
        return settle_pick(guild_id, pick_id, "loss"), "A leg missed, so I marked it a **loss**."
    if "open" not in statuses:
        return pick, ("All legs are graded but one pushed, which usually cuts the payout. "
                      f"Settle it with `/result pick_id:{pick_id}` and the `returned` amount.")
    return pick, ""


def compute_stats(guild_id: int, bettor_key: Optional[str] = None,
                  since: Optional[str] = None, until: Optional[str] = None,
                  sport: Optional[str] = None, preseason: bool = True, platform: Optional[str] = None) -> list[dict]:
    """Per-bettor totals, sorted by net profit (best first)."""
    sql = "SELECT * FROM picks WHERE guild_id = ?"
    args: list = [guild_id]
    if bettor_key:
        sql += " AND bettor_key = ?"
        args.append(bettor_key)
    if since:
        sql += " AND status != 'open' AND settled_at >= ?"
        args.append(since)
    if until:
        sql += " AND status != 'open' AND settled_at < ?"
        args.append(until)
    sql += " ORDER BY id"

    out: dict[str, dict] = {}
    for p in db().execute(sql, args):
        if sport and sport_group(p["sport"]) != sport:
            continue
        if not preseason and p["preseason"]:
            continue
        if platform and p["platform"] != platform:
            continue
        s = out.setdefault(p["bettor_key"], {
            "key": p["bettor_key"], "name": p["bettor_name"],
            "wins": 0, "losses": 0, "pushes": 0, "open": 0,
            "staked": 0.0, "returned": 0.0, "open_risk": 0.0,
        })
        s["name"] = p["bettor_name"]  # most recent display name wins
        if p["status"] == "open":
            s["open"] += 1
            s["open_risk"] += p["cost"]
            continue
        if p["status"] == "win":
            s["wins"] += 1
        elif p["status"] == "loss":
            s["losses"] += 1
        else:
            s["pushes"] += 1
        s["staked"] += p["cost"]
        s["returned"] += p["returned"] or 0.0

    for s in out.values():
        s["net"] = s["returned"] - s["staked"]
        s["roi"] = (s["net"] / s["staked"] * 100) if s["staked"] else 0.0
    return sorted(out.values(), key=lambda s: s["net"], reverse=True)


def leg_counts(guild_id: int, bettor_key: Optional[str] = None,
               text_like: Optional[str] = None) -> dict[str, int]:
    sql = """SELECT l.status, COUNT(*) AS n FROM legs l JOIN picks p ON p.id = l.pick_id
             WHERE p.guild_id = ?"""
    args: list = [guild_id]
    if bettor_key:
        sql += " AND p.bettor_key = ?"
        args.append(bettor_key)
    if text_like:
        sql += r" AND lower(l.text) LIKE ? ESCAPE '\'"
        args.append(like_pattern(text_like))
    counts = {"open": 0, "hit": 0, "miss": 0, "push": 0}
    for r in db().execute(sql + " GROUP BY l.status", args):
        counts[r["status"]] = r["n"]
    return counts


def like_pattern(text: str) -> str:
    escaped = text.lower().replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
    return f"%{escaped}%"


def receipt_channel_ids() -> set[int]:
    return {r["channel_id"] for r in db().execute("SELECT channel_id FROM receipt_channels")}


# ---- players --------------------------------------------------------------

def player_key(name: str) -> str:
    return " ".join(name.lower().split())


def get_player(guild_id: int, name: str) -> Optional[sqlite3.Row]:
    return db().execute("SELECT * FROM players WHERE guild_id = ? AND name_key = ?",
                        (guild_id, player_key(name))).fetchone()


def upsert_player(guild_id: int, name: str, created_by: int, team: Optional[str] = None,
                  sport: Optional[str] = None, role: Optional[str] = None) -> tuple[sqlite3.Row, bool]:
    """Returns (player, created)."""
    existing = get_player(guild_id, name)
    if existing is None:
        db().execute(
            """INSERT INTO players (guild_id, name, name_key, team, sport, role, created_by, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (guild_id, " ".join(name.split()), player_key(name), team, sport, role,
             created_by, now_iso()))
        db().commit()
        return get_player(guild_id, name), True
    updates = {k: v for k, v in (("team", team), ("sport", sport), ("role", role)) if v}
    if updates:
        sets = ", ".join(f"{k} = ?" for k in updates)
        db().execute(f"UPDATE players SET {sets} WHERE id = ?", (*updates.values(), existing["id"]))
        db().commit()
    return get_player(guild_id, name), False


def add_player_note(player_id: int, author_id: Optional[int], author_name: str, text: str) -> None:
    db().execute(
        "INSERT INTO player_notes (player_id, author_id, author_name, text, created_at) VALUES (?,?,?,?,?)",
        (player_id, author_id, author_name, text, now_iso()))
    db().commit()


def player_notes(player_id: int, limit: int = 8) -> list[sqlite3.Row]:
    return db().execute(
        "SELECT * FROM player_notes WHERE player_id = ? ORDER BY id DESC LIMIT ?",
        (player_id, limit)).fetchall()


# --------------------------------------------------------------------------
# Formatting helpers
# --------------------------------------------------------------------------

STATUS = {
    "open": ("🟡 Open", 0xF1C40F),
    "win":  ("✅ Win",  0x2ECC71),
    "loss": ("❌ Loss", 0xE74C3C),
    "push": ("➖ Push", 0x95A5A6),
    "void": ("🚫 Void", 0x95A5A6),
}
LEG_ICON = {"open": "⏳", "hit": "✅", "miss": "❌", "push": "➖"}
BRAND = 0x7B3FE4


def money(x: float) -> str:
    return f"${x:,.2f}"


def signed(x: float) -> str:
    return f"{'+' if x >= 0 else '-'}${abs(x):,.2f}"


def parse_money(text: str) -> float:
    """'$1,250.50' -> 1250.5. Raises ValueError on junk or negatives."""
    cleaned = re.sub(r"[,$\s]", "", text or "")
    value = float(cleaned)
    if value < 0 or value != value:  # negative or NaN
        raise ValueError("amount must be zero or more")
    return value


def clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def local_day(iso: str) -> str:
    return datetime.fromisoformat(iso).astimezone(TZ).strftime("%b %d")


def record_line(s: dict) -> str:
    rec = f"{s['wins']}-{s['losses']}"
    if s["pushes"]:
        rec += f"-{s['pushes']}"
    return rec


def hit_rate(c: dict[str, int]) -> Optional[str]:
    graded = c["hit"] + c["miss"]
    if not graded:
        return None
    return f"{c['hit']}/{graded} hit ({c['hit'] / graded * 100:.0f}%)"


def legs_field(pick_id: int) -> Optional[tuple[str, str]]:
    legs = get_legs(pick_id)
    if not legs:
        return None
    hits = sum(1 for leg in legs if leg["status"] == "hit")
    graded = sum(1 for leg in legs if leg["status"] != "open")
    name = f"Legs · {hits}/{len(legs)} hit" if graded else f"Legs ({len(legs)})"
    lines = [f"{LEG_ICON[leg['status']]} `{leg['idx']}` {leg['text']}" for leg in legs]
    return name, clip("\n".join(lines), 1024)


def pick_embed(p: sqlite3.Row) -> discord.Embed:
    label, color = STATUS[p["status"]]
    e = discord.Embed(
        title=clip(f"Pick #{p['id']} · {p['bettor_name']}", 256),
        description=clip(shown_desc(p), 2000),
        color=color,
    )
    field = legs_field(p["id"])
    if field and p["hidden"] and p["status"] == "open":
        field = (f"Legs ({len(get_legs(p['id']))})", "🔒")
    if field:
        e.add_field(name=field[0], value=field[1], inline=False)
    e.add_field(name="Platform", value=p["platform"])
    if p["sport"]:
        e.add_field(name="Sport", value=clip(p["sport"], 100))
    units, warn = units_note(p["guild_id"], p)
    e.add_field(name="Cost", value=money(p["cost"]) + units)
    e.add_field(name="Max payout", value=money(p["payout"]))
    e.add_field(name="Status", value=label)
    if p["status"] != "open":
        e.add_field(name="Net", value=signed((p["returned"] or 0.0) - p["cost"]))
    if p["slip_url"]:
        e.add_field(name="Slip", value=f"[View]({p['slip_url']})")
    crowd = follow_counts(p["id"])
    if crowd["tail"] or crowd["fade"]:
        e.add_field(name="Crowd", value=f"👍 {crowd['tail']} tailing · 👎 {crowd['fade']} fading")
    if warn:
        e.add_field(name="⚠️ Big bet", value=warn, inline=False)
    copies = copy_count(p["id"])
    if copies:
        e.add_field(name="📋 Copied", value=f"by {copies}")
    if p["kalshi_ticker"]:
        e.add_field(name="🟣 Kalshi", value=f"linked ({(p['kalshi_side'] or 'yes').upper()}), settles itself")
    if p["preseason"]:
        e.add_field(name="⚠️ Preseason", value="Stars may sit or play limited minutes")
    if p["notes"]:
        e.add_field(name="Notes", value=clip(p["notes"], 300), inline=False)
    if field and p["status"] == "open":
        e.set_footer(text=f"Grade legs with /leg pick_id:{p['id']}")
    return e


def one_liner(p: sqlite3.Row) -> str:
    return (f"`#{p['id']}` **{p['bettor_name']}** · {p['platform']} · "
            f"{money(p['cost'])} → {money(p['payout'])} · {clip(shown_desc(p), 80)}")


def resolve_bettor(interaction: discord.Interaction,
                   member: Optional[discord.Member],
                   label: Optional[str]) -> tuple[str, str, Optional[int]]:
    """Returns (key, display name, discord id or None)."""
    if label and label.strip():
        name = label.strip()[:60]
        return f"label:{name.lower()}", name, None
    m = member or interaction.user
    return str(m.id), m.display_name, m.id


def is_mod(user) -> bool:
    perms = getattr(user, "guild_permissions", None)
    return bool(perms and perms.manage_messages)


def can_edit(interaction: discord.Interaction, p: sqlite3.Row) -> bool:
    """The bettor, whoever logged it, or a moderator."""
    if interaction.user.id in (p["logged_by"], p["bettor_id"]):
        return True
    return is_mod(interaction.user)


def split_message(text: str, limit: int = 1900) -> list[str]:
    """Split long text into Discord-sized chunks, preferring line breaks."""
    chunks, current = [], ""
    for line in text.splitlines(keepends=True):
        while len(line) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:limit])
            line = line[limit:]
        if len(current) + len(line) > limit:
            chunks.append(current)
            current = ""
        current += line
    if current.strip():
        chunks.append(current)
    return [c.rstrip() for c in chunks if c.strip()]


# --------------------------------------------------------------------------
# Weekly recap and reminders
# --------------------------------------------------------------------------

def build_recap(guild_id: int, days: int = 7) -> discord.Embed:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
    rows = db().execute(
        "SELECT * FROM picks WHERE guild_id = ? AND status != 'open' AND settled_at >= ? ORDER BY id",
        (guild_id, since)).fetchall()
    e = discord.Embed(title=f"Weekly recap · last {days} days", color=BRAND)
    if not rows:
        e.description = "Quiet week. No picks were settled."
    else:
        stats = compute_stats(guild_id, since=since)
        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, s in enumerate(stats[:15]):
            rank = medals[i] if i < 3 else f"`{i + 1}.`"
            lines.append(f"{rank} **{s['name']}** · {record_line(s)} · {signed(s['net'])}")
        e.description = "\n".join(lines)

        def net(p): return (p["returned"] or 0.0) - p["cost"]
        best = max(rows, key=net)
        if net(best) > 0:
            e.add_field(name="💰 Best hit", inline=False, value=clip(
                f"**{best['bettor_name']}** {signed(net(best))} on {best['description']} (`#{best['id']}`)", 1024))
        worst = min(rows, key=net)
        if net(worst) < 0:
            e.add_field(name="🧱 Worst beat", inline=False, value=clip(
                f"**{worst['bettor_name']}** {signed(net(worst))} on {worst['description']} (`#{worst['id']}`)", 1024))
        # Heartbreaker: a lost parlay that missed by a single leg.
        heartbreak = None
        for p in rows:
            if p["status"] != "loss":
                continue
            legs = get_legs(p["id"])
            if len(legs) >= 3 and sum(1 for leg in legs if leg["status"] == "miss") == 1:
                if heartbreak is None or len(legs) > heartbreak[1]:
                    heartbreak = (p, len(legs))
        if heartbreak:
            p, n = heartbreak
            e.add_field(name="💔 Heartbreaker", inline=False, value=clip(
                f"**{p['bettor_name']}** hit {n - 1} of {n} legs on {p['description']} (`#{p['id']}`)", 1024))
        pr = power_rankings(guild_id)[:5]
        if pr:
            e.add_field(name="📊 Power rankings", inline=False, value=clip("\n".join(pr), 1024))
        beats = bad_beats(guild_id, since, 3)
        if beats:
            e.add_field(name="💀 Bad beats", inline=False, value=clip("\n".join(bad_beat_line(r) for r in beats), 1024))
        staked = sum(p["cost"] for p in rows)
        group_net = sum(net(p) for p in rows)
        e.add_field(name="Group", value=f"{len(rows)} settled · {money(staked)} staked · {signed(group_net)}")
        c = leg_counts_since(guild_id, since)
        rate = hit_rate(c)
        if rate:
            e.add_field(name="Legs", value=rate)
    week_locks = locks_for_week(guild_id, week_id())
    if week_locks:
        e.add_field(name=f"🔒 Locks of the week ({sum(1 for r in week_locks if r['status'] == 'win')}"
                         f"/{len(week_locks)} hit)", inline=False,
                    value=clip("\n".join(lock_line(r) for r in week_locks), 1024))
    open_rows = db().execute("SELECT cost FROM picks WHERE guild_id = ? AND status = 'open'",
                             (guild_id,)).fetchall()
    if open_rows:
        e.set_footer(text=f"{len(open_rows)} picks still open · {money(sum(r['cost'] for r in open_rows))} at risk")
    return e


def leg_counts_since(guild_id: int, since: str) -> dict[str, int]:
    counts = {"open": 0, "hit": 0, "miss": 0, "push": 0}
    for r in db().execute(
            """SELECT l.status, COUNT(*) AS n FROM legs l JOIN picks p ON p.id = l.pick_id
               WHERE p.guild_id = ? AND p.status != 'open' AND p.settled_at >= ?
               GROUP BY l.status""", (guild_id, since)):
        counts[r["status"]] = r["n"]
    return counts


def build_reminders(guild_id: int) -> Optional[str]:
    """Picks open too long that haven't been reminded about yet. Marks them reminded."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=REMIND_AFTER_DAYS)).isoformat(timespec="seconds")
    rows = db().execute(
        """SELECT * FROM picks WHERE guild_id = ? AND status = 'open'
           AND created_at <= ? AND reminded_at IS NULL ORDER BY bettor_key, id""",
        (guild_id, cutoff)).fetchall()
    if not rows:
        return None
    lines = [f"⏰ These picks have been open {REMIND_AFTER_DAYS}+ days. "
             "Tap Win / Loss / Push on the pick, or use `/result`:"]
    for p in rows[:25]:
        who = f"<@{p['bettor_id']}>" if p["bettor_id"] else f"**{p['bettor_name']}**"
        lines.append(f"{who} `#{p['id']}` {clip(shown_desc(p), 70)} ({local_day(p['created_at'])})")
    if len(rows) > 25:
        lines.append(f"…and {len(rows) - 25} more. See `/open`.")
    stamp = now_iso()
    db().executemany("UPDATE picks SET reminded_at = ? WHERE id = ?", [(stamp, p["id"]) for p in rows])
    db().commit()
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Importing an existing picks tracker (.xlsx with a Picks Log tab)
# --------------------------------------------------------------------------

def _num(v) -> Optional[float]:
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(re.sub(r"[,$\s¢%]", "", str(v)))
    except ValueError:
        return None


def _day(v) -> Optional[datetime]:
    if isinstance(v, datetime):
        return v
    if hasattr(v, "year") and hasattr(v, "month"):  # a date
        return datetime(v.year, v.month, v.day)
    m = re.match(r"\s*(\d{4})-(\d{1,2})-(\d{1,2})", str(v or ""))
    if m:
        return datetime(int(m[1]), int(m[2]), int(m[3]))
    m = re.match(r"\s*(\d{1,2})/(\d{1,2})/(\d{2,4})", str(v or ""))
    if m:
        year = int(m[3]) + (2000 if int(m[3]) < 100 else 0)
        return datetime(year, int(m[1]), int(m[2]))
    return None


def _status(v) -> Optional[str]:
    t = str(v or "").strip().lower()
    return {"win": "win", "won": "win", "loss": "loss", "lost": "loss", "push": "push",
            "void": "void", "cancelled": "void", "canceled": "void",
            "pending": "open", "open": "open"}.get(t)


def _leg_status(v) -> str:
    t = str(v or "").strip().lower()
    return {"hit": "hit", "won": "hit", "win": "hit", "miss": "miss", "lost": "miss",
            "loss": "miss", "push": "push", "void": "push"}.get(t, "open")


def _header_map(ws, wanted: dict[str, tuple[str, ...]],
                required: tuple[str, ...]) -> tuple[int, dict[str, int]]:
    """Find the header row (within the first 5 rows) and map field -> column number."""
    for r in range(1, 6):
        cells = {c: str(ws.cell(r, c).value or "").strip().lower() for c in range(1, ws.max_column + 1)}
        found = {}
        for field, starts in wanted.items():
            for c, text in cells.items():
                if text and any(text.startswith(s) for s in starts) and c not in found.values():
                    found[field] = c
                    break
        if all(f in found for f in required):
            return r, found
    return 0, {}


def parse_tracker(data: bytes) -> tuple[list[dict], list[str]]:
    """Read picks from a tracker workbook. Returns (picks, problems)."""
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(data), data_only=True)
    wanted = {
        "date": ("date logged", "date placed", "date"), "sport": ("sport",), "platform": ("platform",),
        "event": ("event / matchup", "event/matchup", "matchup", "event (",), "question": ("market question", "pick", "question"),
        "side": ("side",), "price": ("entry price", "price"), "stake": ("stake", "cost"),
        "event_date": ("event date",), "result": ("result", "status"), "payout": ("payout",),
        "pl": ("p/l", "p&l", "profit"),
        "notes": ("notes",), "person": ("person", "bettor"),
    }
    sheets = sorted(wb.worksheets, key=lambda ws: ws.title.lower() != "picks log")
    header_row, cols, log_ws = 0, {}, None
    for ws in sheets:
        if ws.title.lower() in ("combos", "combo legs", "summary", "legs"):
            continue
        header_row, cols = _header_map(ws, wanted, ("stake",))
        if header_row and ("question" in cols or "event" in cols):
            log_ws = ws
            break
    if log_ws is None:
        return [], ["I couldn't find a tab with Stake and Market Question (or Event) columns."]

    # Combos and their legs, if the tracker has them.
    combos: dict[str, dict] = {}
    if "Combos" in wb.sheetnames:
        ws = wb["Combos"]
        hr, cc = _header_map(ws, {"id": ("combo id",), "max": ("max payout",), "status": ("status",),
                                  "actual": ("actual payout",)}, ("id",))
        for r in range(hr + 1, ws.max_row + 1) if hr else []:
            cid = str(ws.cell(r, cc["id"]).value or "").strip().upper()
            if cid:
                combos[cid] = {"max": _num(ws.cell(r, cc["max"]).value) if "max" in cc else None,
                               "status": _status(ws.cell(r, cc["status"]).value) if "status" in cc else None,
                               "actual": _num(ws.cell(r, cc["actual"]).value) if "actual" in cc else None,
                               "legs": []}
    if "Combo Legs" in wb.sheetnames:
        ws = wb["Combo Legs"]
        hr, cc = _header_map(ws, {"id": ("combo id",), "text": ("selection",),
                                  "result": ("leg result", "result")}, ("id", "text"))
        for r in range(hr + 1, ws.max_row + 1) if hr else []:
            cid = str(ws.cell(r, cc["id"]).value or "").strip().upper()
            text = str(ws.cell(r, cc["text"]).value or "").strip()
            if cid in combos and text:
                result = ws.cell(r, cc["result"]).value if "result" in cc else None
                combos[cid]["legs"].append((text, _leg_status(result)))

    def get(r, field):
        return log_ws.cell(r, cols[field]).value if field in cols else None

    picks, problems = [], []
    for r in range(header_row + 1, log_ws.max_row + 1):
        stake = _num(get(r, "stake"))
        question = str(get(r, "question") or "").strip()
        event = str(get(r, "event") or "").strip()
        if stake is None and not question and not event:
            continue  # empty row
        if stake is None:
            problems.append(f"Row {r}: no stake, skipped.")
            continue
        combo_id = None
        m = re.search(r"COMBO-\d+", question.upper())
        if m and m.group(0) in combos:
            combo_id = m.group(0)
        combo = combos.get(combo_id) if combo_id else None
        status = _status(get(r, "result")) or (combo or {}).get("status") or "open"
        returned = _num(get(r, "payout"))
        if returned is None and combo:
            returned = combo["actual"]
        price = _num(get(r, "price"))
        if combo and combo["max"]:
            payout = combo["max"]
        elif price and price > 0:
            payout = round(stake / (price / 100), 2)
        else:
            payout = returned if returned is not None else stake
        pl = _num(get(r, "pl"))
        if pl is not None and status != "open":
            returned = round(stake + pl, 2)  # the platform's own profit figure wins over rounding
        if status == "win" and returned is None:
            returned = payout
        if status in ("push", "void") and returned is None:
            returned = stake
        if status == "loss" and returned is None:
            returned = 0.0
        if returned is not None and returned > payout:
            payout = returned
        side = str(get(r, "side") or "").strip()
        if combo_id:
            description = question
        else:
            description = question or event
            if event and question and event.lower() not in question.lower():
                description = f"{event}: {question}"
            if side:
                description += f" ({side}" + (f" @ {price:g}¢)" if price else ")")
        logged = _day(get(r, "date")) or datetime.now()
        settled = _day(get(r, "event_date")) or logged
        person = str(get(r, "person") or "").strip()
        platform = str(get(r, "platform") or "").strip() or "Kalshi"
        key_src = f"{logged.date()}|{person.lower()}|{stake:.2f}|{description[:120].lower()}"
        picks.append({
            "person": person, "platform": platform[:40],
            "sport": (str(get(r, "sport")).strip()[:60] if get(r, "sport") else None),
            "description": clip(description, 300), "notes": (str(get(r, "notes")).strip() if get(r, "notes") else None),
            "cost": stake, "payout": payout, "status": status,
            "returned": returned if status != "open" else None,
            "created_at": logged.replace(hour=12, tzinfo=TZ).astimezone(timezone.utc).isoformat(timespec="seconds"),
            "settled_at": (settled.replace(hour=23, tzinfo=TZ).astimezone(timezone.utc).isoformat(timespec="seconds")
                           if status != "open" else None),
            "legs": combo["legs"] if combo else [],
            "import_key": "tracker:" + hashlib.sha1(key_src.encode()).hexdigest()[:16],
        })
    return picks, problems


def import_picks(guild_id: int, uploader_id: int, uploader_name: str,
                 picks: list[dict]) -> tuple[dict[str, int], int]:
    """Add parsed picks. Returns (added per person, skipped as already imported)."""
    added: dict[str, int] = {}
    skipped = 0
    for p in picks:
        if db().execute("SELECT 1 FROM picks WHERE guild_id = ? AND import_key = ?",
                        (guild_id, p["import_key"])).fetchone():
            skipped += 1
            continue
        if p["person"]:
            claimed = get_setting(guild_id, f"claim:{p['person'].lower()}")
            if claimed:
                row = db().execute("SELECT bettor_name FROM picks WHERE guild_id = ? AND bettor_key = ? "
                                   "ORDER BY id DESC LIMIT 1", (guild_id, claimed)).fetchone()
                key, name, bid = claimed, (row["bettor_name"] if row else p["person"]), int(claimed)
            else:
                key, name, bid = f"label:{p['person'].lower()}", p["person"], None
        else:
            key, name, bid = str(uploader_id), uploader_name, uploader_id
        cur = db().execute(
            """INSERT INTO picks (guild_id, bettor_key, bettor_name, bettor_id, logged_by, platform, sport,
                                  description, legs, cost, payout, status, returned, created_at, settled_at,
                                  notes, import_key, reminded_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (guild_id, key, name, bid, uploader_id, p["platform"], p["sport"], p["description"],
             "\n".join(t for t, _ in p["legs"]) or None, p["cost"], p["payout"], p["status"],
             p["returned"], p["created_at"], p["settled_at"], p["notes"], p["import_key"],
             now_iso()))  # imported picks don't trigger "open too long" pings
        db().executemany("INSERT INTO legs (pick_id, idx, text, status) VALUES (?,?,?,?)",
                         [(cur.lastrowid, i, t, st) for i, (t, st) in enumerate(p["legs"], start=1)])
        added[name] = added.get(name, 0) + 1
    db().commit()
    return added, skipped


# --------------------------------------------------------------------------
# Excel export: one tab per platform, a Legs tab, and a per-person Summary
# --------------------------------------------------------------------------

SHEET_GROUPS = ["Kalshi", "PrizePicks", "Other"]   # Sportsbook and Other picks go on "Other"
LAST_ROW = 5000                                     # formula ranges reach this far down


def sheet_for(platform: str) -> str:
    return platform if platform in ("Kalshi", "PrizePicks") else "Other"


def build_workbook(guild_id: int) -> io.BytesIO:
    from openpyxl import Workbook
    from openpyxl.formatting.rule import FormulaRule
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    ARIAL, BOLD = Font(name="Arial", size=10), Font(name="Arial", size=10, bold=True)
    WHITE_BOLD = Font(name="Arial", size=10, bold=True, color="FFFFFF")
    HEAD_FILL = PatternFill("solid", fgColor="5B2BB5")
    NAME_FILL = PatternFill("solid", fgColor="E9DDFF")
    TOTAL_BORDER = Border(top=Side(style="thin", color="5B2BB5"))
    MONEY = '$#,##0.00'
    NET = '$#,##0.00;[Red]-$#,##0.00;"-"'
    PCT = '0.0%;[Red]-0.0%;"-"'

    def put(ws, row, col, value, font=ARIAL, fmt=None, fill=None, wrap=False, border=None,
            align=None):
        c = ws.cell(row=row, column=col, value=value)
        c.font = font
        if fmt:
            c.number_format = fmt
        if fill:
            c.fill = fill
        if border:
            c.border = border
        c.alignment = Alignment(vertical="top", wrap_text=wrap, horizontal=align)
        return c

    picks = db().execute("SELECT * FROM picks WHERE guild_id = ? ORDER BY id", (guild_id,)).fetchall()
    # One name per person, so every formula matches all of their rows.
    names: dict[str, str] = {}
    for p in picks:
        names[p["bettor_key"]] = p["bettor_name"]

    wb = Workbook()
    summary = wb.active
    summary.title = "Summary"

    # ---- one tab per platform ----
    headers = ["Pick #", "Date", "Bettor", "Sport", "Description", "Legs", "Legs Hit",
               "Cost", "Max Payout", "Status", "Returned", "Net", "Settled", "Slip", "Notes"]
    widths = [8, 13, 14, 12, 34, 46, 9, 10, 11, 9, 10, 10, 13, 8, 50]
    tabs = {}
    for name in SHEET_GROUPS:
        ws = wb.create_sheet(name)
        tabs[name] = ws
        for col, (h, w) in enumerate(zip(headers, widths), start=1):
            put(ws, 1, col, h, WHITE_BOLD, fill=HEAD_FILL, align="center")
            ws.column_dimensions[get_column_letter(col)].width = w
        ws.freeze_panes = "A2"
    next_row = {name: 2 for name in SHEET_GROUPS}
    for p in picks:
        ws_name = sheet_for(p["platform"])
        ws, r = tabs[ws_name], next_row[ws_name]
        next_row[ws_name] += 1
        legs = get_legs(p["id"])
        legs_text = "\n".join(f"{leg['idx']}. {leg['text']}" +
                               (f" ({leg['status']})" if leg["status"] != "open" else "")
                               for leg in legs)
        sport = p["sport"] or ("" if ws_name != "Other" else p["platform"])
        put(ws, r, 1, p["id"])
        put(ws, r, 2, datetime.fromisoformat(p["created_at"]).astimezone(TZ).date(), fmt="mmm d, yyyy")
        put(ws, r, 3, names[p["bettor_key"]])
        put(ws, r, 4, sport)
        put(ws, r, 5, shown_desc(p), wrap=True)
        put(ws, r, 6, legs_text or None, wrap=True)
        if legs:
            put(ws, r, 7, f"{sum(1 for leg in legs if leg['status'] == 'hit')}/{len(legs)}")
        put(ws, r, 8, p["cost"], fmt=MONEY)
        put(ws, r, 9, p["payout"], fmt=MONEY)
        put(ws, r, 10, p["status"].capitalize())
        if p["status"] != "open":
            put(ws, r, 11, p["returned"] or 0.0, fmt=MONEY)
            put(ws, r, 13, datetime.fromisoformat(p["settled_at"]).astimezone(TZ).date(), fmt="mmm d, yyyy")
        put(ws, r, 12, f'=IF(OR(J{r}="Open",J{r}=""),"",K{r}-H{r})', fmt=NET)
        if p["slip_url"]:
            c = put(ws, r, 14, "View", Font(name="Arial", size=10, color="1155CC", underline="single"))
            c.hyperlink = p["slip_url"]
        if p["notes"]:
            put(ws, r, 15, p["notes"], wrap=True)
    for name, ws in tabs.items():
        last = max(next_row[name] - 1, 2)
        ws.auto_filter.ref = f"A1:O{last}"
        for status, color in (("Win", "D9F2E3"), ("Loss", "F9D9D6"), ("Open", "FFF3C4"), ("Push", "EEEEEE"), ("Void", "EEEEEE")):
            ws.conditional_formatting.add(
                f"J2:J{LAST_ROW}", FormulaRule(formula=[f'$J2="{status}"'], fill=PatternFill("solid", fgColor=color)))

    # ---- one row per leg ----
    legs_ws = wb.create_sheet("Legs")
    for col, (h, w) in enumerate(zip(["Pick #", "Bettor", "Platform", "Leg #", "Leg", "Result"],
                                     [8, 14, 11, 7, 50, 9]), start=1):
        put(legs_ws, 1, col, h, WHITE_BOLD, fill=HEAD_FILL)
        legs_ws.column_dimensions[get_column_letter(col)].width = w
    legs_ws.freeze_panes = "A2"
    r = 2
    for p in picks:
        for leg in get_legs(p["id"]):
            for col, v in enumerate([p["id"], names[p["bettor_key"]], sheet_for(p["platform"]),
                                     leg["idx"], leg["text"], leg["status"].capitalize()], start=1):
                put(legs_ws, r, col, v)
            r += 1
    legs_ws.auto_filter.ref = f"A1:F{max(r - 1, 2)}"

    # ---- summary: whole group, then a section per person ----
    def rng(sheet: str, col: str) -> str:
        return f"{sheet}!${col}$2:${col}${LAST_ROW}"

    def crit(sheet: str, name_ref: Optional[str], col: str = "C") -> str:
        return f",{rng(sheet, col)},{name_ref}" if name_ref else ""

    summary.column_dimensions["A"].width = 16
    for col in "BCDEFG":
        summary.column_dimensions[col].width = 9
    for col in "HIJ":
        summary.column_dimensions[col].width = 12
    for col in "KL":
        summary.column_dimensions[col].width = 10
    put(summary, 1, 1, "Picks Summary", Font(name="Arial", size=14, bold=True, color="5B2BB5"))
    put(summary, 2, 1, f"Exported {datetime.now(TZ).strftime('%b %d, %Y %I:%M %p')}. "
        "These totals are formulas: edit a row on the Kalshi, PrizePicks or Other tab "
        "and this page updates.", Font(name="Arial", size=9, italic=True, color="666666"))

    cols = ["Platform", "Picks", "Wins", "Losses", "Pushes", "Open", "Open $", "Staked",
            "Returned", "Net", "ROI", "Leg Hit %"]
    row = 4
    people = sorted(names.items(), key=lambda kv: -sum(
        ((p["returned"] or 0.0) - p["cost"]) for p in picks
        if p["bettor_key"] == kv[0] and p["status"] != "open"))
    sections = [("Whole group", None)] + [(n, n) for _, n in people]
    for title, person in sections:
        put(summary, row, 1, title, Font(name="Arial", size=11, bold=True), fill=NAME_FILL)
        for col in range(2, len(cols) + 1):
            put(summary, row, col, None, fill=NAME_FILL)
        name_ref = f"$A${row}" if person else None
        row += 1
        for col, h in enumerate(cols, start=1):
            put(summary, row, col, h, WHITE_BOLD, fill=HEAD_FILL, align="left" if col == 1 else "right")
        row += 1
        first = row
        for sheet in SHEET_GROUPS:
            c = crit(sheet, name_ref)
            lc = crit("Legs", name_ref, "B") + f",{rng('Legs', 'C')},\"{sheet}\""
            r = row
            put(summary, r, 1, sheet)
            put(summary, r, 2, f'=COUNTIFS({rng(sheet, "A")},">0"{c})')
            put(summary, r, 3, f'=COUNTIFS({rng(sheet, "J")},"Win"{c})')
            put(summary, r, 4, f'=COUNTIFS({rng(sheet, "J")},"Loss"{c})')
            put(summary, r, 5, f'=COUNTIFS({rng(sheet, "J")},"Push"{c})+COUNTIFS({rng(sheet, "J")},"Void"{c})')
            put(summary, r, 6, f'=COUNTIFS({rng(sheet, "J")},"Open"{c})')
            put(summary, r, 7, f'=SUMIFS({rng(sheet, "H")},{rng(sheet, "J")},"Open"{c})', fmt=MONEY)
            put(summary, r, 8, f'=SUMIFS({rng(sheet, "H")},{rng(sheet, "J")},"<>Open"{c})', fmt=MONEY)
            put(summary, r, 9, f'=SUMIFS({rng(sheet, "K")},{rng(sheet, "J")},"<>Open"{c})', fmt=MONEY)
            put(summary, r, 10, f"=I{r}-H{r}", fmt=NET)
            put(summary, r, 11, f"=IF(H{r}=0,0,J{r}/H{r})", fmt=PCT)
            hits = f'COUNTIFS({rng("Legs", "F")},"Hit"{lc})'
            misses = f'COUNTIFS({rng("Legs", "F")},"Miss"{lc})'
            put(summary, r, 12, f"=IF({hits}+{misses}=0,0,{hits}/({hits}+{misses}))", fmt=PCT)
            row += 1
        last = row - 1
        put(summary, row, 1, "Total", BOLD, border=TOTAL_BORDER)
        for col in range(2, 10):
            letter = get_column_letter(col)
            put(summary, row, col, f"=SUM({letter}{first}:{letter}{last})", BOLD,
                fmt=MONEY if col >= 7 else None, border=TOTAL_BORDER)
        put(summary, row, 10, f"=I{row}-H{row}", BOLD, fmt=NET, border=TOTAL_BORDER)
        put(summary, row, 11, f"=IF(H{row}=0,0,J{row}/H{row})", BOLD, fmt=PCT, border=TOTAL_BORDER)
        lc = crit("Legs", name_ref, "B")
        hits = f'COUNTIFS({rng("Legs", "F")},"Hit"{lc})'
        misses = f'COUNTIFS({rng("Legs", "F")},"Miss"{lc})'
        put(summary, row, 12, f"=IF({hits}+{misses}=0,0,{hits}/({hits}+{misses}))", BOLD, fmt=PCT,
            border=TOTAL_BORDER)
        row += 2
    put(summary, row, 1, "Staked, Returned, Net and ROI count settled picks only. Pushes include "
        "voids. Open $ is money still riding.", Font(name="Arial", size=9, italic=True, color="666666"))
    summary.freeze_panes = "A4"

    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return out


# --------------------------------------------------------------------------
# Buttons (these keep working after the bot restarts)
# --------------------------------------------------------------------------

class SettleButton(discord.ui.DynamicItem[discord.ui.Button],
                   template=r"settle:(?P<pick_id>\d+):(?P<status>win|loss|push)"):
    STYLES = {
        "win": ("Win", discord.ButtonStyle.success),
        "loss": ("Loss", discord.ButtonStyle.danger),
        "push": ("Push", discord.ButtonStyle.secondary),
    }

    def __init__(self, pick_id: int, status: str):
        label, style = self.STYLES[status]
        super().__init__(discord.ui.Button(
            label=label, style=style, custom_id=f"settle:{pick_id}:{status}", row=0))
        self.pick_id = pick_id
        self.status = status

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(int(match["pick_id"]), match["status"])

    async def callback(self, interaction: discord.Interaction):
        p = get_pick(interaction.guild_id, self.pick_id)
        if p is None:
            await interaction.response.send_message(
                "That pick no longer exists.", ephemeral=True)
            return
        if not can_edit(interaction, p):
            await interaction.response.send_message(
                f"Only {p['bettor_name']} or a mod can settle this one.", ephemeral=True)
            return
        p = settle_pick(interaction.guild_id, self.pick_id, self.status)
        await interaction.response.edit_message(content=None, embed=pick_embed(p), view=None)


def settle_view(pick_id: int) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    for status in ("win", "loss", "push"):
        view.add_item(SettleButton(pick_id, status))
    view.add_item(FollowButton(pick_id, "tail"))
    view.add_item(FollowButton(pick_id, "fade"))
    view.add_item(CopyButton(pick_id))
    view.add_item(CardSweatButton(pick_id))
    row = db().execute("SELECT platform, kalshi_ticker FROM picks WHERE id = ?", (pick_id,)).fetchone()
    if row and row["platform"].lower() == "kalshi" and not row["kalshi_ticker"]:
        view.add_item(CardKalshiButton(pick_id))
    return view


class SlipModal(discord.ui.Modal, title="Log this slip"):
    platform = discord.ui.TextInput(label="Platform", default="PrizePicks", max_length=40)
    description = discord.ui.TextInput(
        label="The play", placeholder="e.g. 4-pick power play, NFL Sunday", max_length=200)
    legs = discord.ui.TextInput(
        label="Legs (one per line, optional)", style=discord.TextStyle.paragraph,
        required=False, max_length=900)
    cost = discord.ui.TextInput(label="Cost / entry", placeholder="10", max_length=12)
    payout = discord.ui.TextInput(
        label="Max payout (total back if it hits)", placeholder="100", max_length=12)

    def __init__(self, slip_url: Optional[str]):
        super().__init__()
        self.slip_url = slip_url

    async def on_submit(self, interaction: discord.Interaction):
        try:
            cost = parse_money(self.cost.value)
            payout = parse_money(self.payout.value)
        except ValueError:
            await interaction.response.send_message(
                "Cost and payout need to be plain numbers, like `10` or `$25.50`.",
                ephemeral=True)
            return
        pick_id = insert_pick(
            guild_id=interaction.guild_id,
            bettor_key=str(interaction.user.id),
            bettor_name=interaction.user.display_name,
            bettor_id=interaction.user.id,
            logged_by=interaction.user.id,
            platform=self.platform.value.strip() or "Other",
            sport=None,
            description=self.description.value.strip(),
            legs=self.legs.value.strip() or None,
            cost=cost,
            payout=payout,
            slip_url=self.slip_url,
        )
        p = get_pick(interaction.guild_id, pick_id)
        await interaction.response.edit_message(
            content=None, embed=pick_embed(p), view=settle_view(pick_id))


class LogSlipButton(discord.ui.DynamicItem[discord.ui.Button],
                    template=r"logslip:(?P<author_id>\d+)"):
    def __init__(self, author_id: int):
        super().__init__(discord.ui.Button(
            label="Log this slip", style=discord.ButtonStyle.primary,
            custom_id=f"logslip:{author_id}"))
        self.author_id = author_id

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(int(match["author_id"]))

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Only the person who posted the slip can log it.", ephemeral=True)
            return
        slip_url = None
        ref = interaction.message.reference if interaction.message else None
        if ref and ref.message_id:
            slip_url = (f"https://discord.com/channels/{interaction.guild_id}/"
                        f"{interaction.channel_id}/{ref.message_id}")
        await interaction.response.send_modal(SlipModal(slip_url))


def log_slip_view(author_id: int) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    view.add_item(LogSlipButton(author_id))
    return view


# --------------------------------------------------------------------------
# Claude: reading slips and answering questions (needs ANTHROPIC_API_KEY)
# --------------------------------------------------------------------------

IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_IMAGE_BYTES = 7 * 1024 * 1024  # stays under the API's limit once base64-encoded

SLIP_PROMPT = """This is a screenshot posted in a sports betting group. If it shows a \
bet slip, entry, or position (PrizePicks, Kalshi, a sportsbook, etc.), extract it.

Reply with ONLY a JSON object, no other text:
{
  "is_slip": true or false,
  "platform": "PrizePicks" | "Kalshi" | the sportsbook name | "Other",
  "sport": short sport/league name or null,
  "description": one short line summarizing the play, e.g. "6-pick Power Play" or "5-pick Flex Play" or "3-leg NFL combo",
  "legs": ["one string per leg. Player props as 'Player Name over|under LINE stat' (PrizePicks More = over, \
Less = under), e.g. 'Victor Wembanyama over 23.5 Pts+Rebs+Asts'. Game lines as 'Chiefs ML', 'Chiefs -3.5', \
'Over 44.5'"],
  "cost": number risked (entry fee / stake / cost) or null if not visible,
  "payout": total amount paid back if it wins (or that it did pay), or null if not visible,
  "status": "open" | "win" | "loss" | "push",
  "returned": amount actually paid out if the slip is already settled, else null
}

Use "open" unless the screenshot clearly shows a final result. Numbers must be plain \
numbers with no currency symbols. Never guess an amount you cannot read."""

ASK_SYSTEM = """You are {bot_name}, the assistant in a Discord server where a group of \
friends track their sports picks (Kalshi, PrizePicks and sportsbooks; NFL, CS2 esports \
and more). People @mention you with questions about players, teams, matchups, form, \
injuries and roster news.

Search the web for anything current, like recent results, injuries, lineups and rosters. \
Today is {today}.

How to answer:
- This is Discord: keep it under about 200 words. Lead with the direct answer, then the \
two or three facts that matter most. Short bullets are fine; no headings.
- Focus on players, form and matchups. Don't narrate line or odds movements unless asked.
- Be straight about uncertainty and thin information. Never call anything a lock or \
promise an outcome.
- The group's own scouting notes and records are included below when relevant. Use them, \
and say when you're relying on them."""

_anthropic = None


def ai_enabled() -> bool:
    return bool(ANTHROPIC_API_KEY)


vision_enabled = ai_enabled  # kept for older references


def anthropic_client():
    global _anthropic
    if _anthropic is None:
        import anthropic  # imported lazily so the bot runs without it
        _anthropic = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    return _anthropic


def extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError("no JSON in model reply")
    return json.loads(match.group(0))


def as_amount(value) -> Optional[float]:
    """Coerce a model-supplied number; None if missing or unusable."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return parse_money(str(value))
    except ValueError:
        return None


async def read_slip(attachment: discord.Attachment) -> Optional[dict]:
    """Returns the parsed slip, or None if it couldn't be read as one."""
    media_type = (attachment.content_type or "").split(";")[0].strip()
    data = base64.standard_b64encode(await attachment.read()).decode()
    reply = await anthropic_client().messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image",
                 "source": {"type": "base64", "media_type": media_type, "data": data}},
                {"type": "text", "text": SLIP_PROMPT},
            ],
        }],
    )
    text = "".join(block.text for block in reply.content if block.type == "text")
    slip = extract_json(text)
    if not slip.get("is_slip"):
        return None
    slip["cost"] = as_amount(slip.get("cost"))
    slip["payout"] = as_amount(slip.get("payout"))
    slip["returned"] = as_amount(slip.get("returned"))
    if slip.get("status") not in ("open", "win", "loss", "push"):
        slip["status"] = "open"
    return slip


def build_ask_context(guild_id: int, asker_key: str, question: str) -> str:
    """The group's own data that's relevant to this question."""
    parts = []
    q = player_key(question)
    matched = [p for p in db().execute("SELECT * FROM players WHERE guild_id = ?", (guild_id,))
               if re.search(rf"(?<!\w){re.escape(p['name_key'])}(?!\w)", q)][:5]
    for p in matched:
        meta = " · ".join(x for x in (p["team"], p["sport"], p["role"]) if x)
        lines = [f"Tracked player: {p['name']}" + (f" ({meta})" if meta else "")]
        for n in player_notes(p["id"], 8):
            lines.append(f"  - {local_day(n['created_at'])}, {n['author_name']}: {n['text']}")
        rate = hit_rate(leg_counts(guild_id, text_like=p["name"]))
        if rate:
            lines.append(f"  - The group's legs on this player: {rate}")
        parts.append("\n".join(lines))
    stats = compute_stats(guild_id, asker_key)
    if stats:
        s = stats[0]
        parts.append(f"The person asking ({s['name']}) is {record_line(s)}, "
                     f"net {signed(s['net'])}, ROI {s['roi']:+.1f}%, {s['open']} picks open.")
    return "\n\n".join(parts)


async def ask_claude(system: str, user_text: str, max_searches: int = 5) -> tuple[str, list[str]]:
    """Returns (answer text, source urls)."""
    messages = [{"role": "user", "content": user_text}]
    tools = [{"type": "web_search_20250305", "name": "web_search", "max_uses": max_searches}]
    reply = None
    for _ in range(4):  # long searches can pause; resume up to a few times
        reply = await anthropic_client().messages.create(
            model=ASK_MODEL, max_tokens=1500, system=system, messages=messages, tools=tools)
        if reply.stop_reason != "pause_turn":
            break
        messages = messages[:1] + [{"role": "assistant", "content": reply.content}]
    text = "".join(b.text for b in reply.content if b.type == "text").strip()
    sources: list[str] = []
    for b in reply.content:
        for c in (getattr(b, "citations", None) or []):
            url = getattr(c, "url", None)
            if url and url not in sources:
                sources.append(url)
    return text, sources[:3]


# --------------------------------------------------------------------------
# Free result lookups: ESPN's public scoreboard, for moneylines, spreads and totals.
# Anything else (player props, halves, esports, tennis) falls through to Claude.
# --------------------------------------------------------------------------

ESPN = "https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard"
LEAGUES = [  # (pattern in the pick's sport, ESPN path, extra query params)
    (r"\bwnba\b", "basketball/wnba", {}),
    (r"\bnfl\b", "football/nfl", {}),
    (r"ncaa ?f|college football|\bncaaf\b|\bcfb\b", "football/college-football", {"groups": "80"}),
    (r"\bnba\b", "basketball/nba", {}),
    (r"ncaa ?b|college basketball|\bncaab\b|\bcbb\b", "basketball/mens-college-basketball", {"groups": "50"}),
    (r"\bmlb\b|baseball", "baseball/mlb", {}),
    (r"\bnhl\b|hockey", "hockey/nhl", {}),
    (r"\bmls\b", "soccer/usa.1", {}),
    (r"\bepl\b|premier league", "soccer/eng.1", {}),
    (r"la ?liga", "soccer/esp.1", {}),
    (r"serie a", "soccer/ita.1", {}),
    (r"bundesliga", "soccer/ger.1", {}),
    (r"ligue 1", "soccer/fra.1", {}),
    (r"liga ?mx", "soccer/mex.1", {}),
    (r"champions league|\bucl\b", "soccer/uefa.champions", {}),
]
NO_FREE_LOOKUP = r"esports|\bcs2?\b|counter|valorant|league of legends|dota|tennis|\bwta\b|\batp\b|golf|ufc|mma|boxing|f1|nascar|politic|crypto"
DEFAULT_LEAGUES = ["football/nfl", "basketball/nba", "baseball/mlb", "hockey/nhl", "football/college-football"]
NOT_SIMPLE = re.compile(
    r"\b(1h|2h|1q|2q|3q|4q|half|quarters?|innings?|periods?|sets?|maps?|rounds?|first|1st|2nd|3rd|4th|"
    r"yards?|yds|tds?|touchdowns?|receptions?|rec|rush|rushing|passing|pass|kills|rating|assists?|"
    r"rebounds?|strikeouts?|hits|shots|corners|cards|sacks|interceptions?|threes|3-pointers|"
    r"tie|draw|btts|both teams|anytime|scorer|race to|double|triple|exact|correct score|alt)\b", re.I)

_score_cache: dict[tuple[str, str], tuple[float, list[dict]]] = {}


def leagues_for(sport: Optional[str]) -> list[str]:
    text = (sport or "").lower()
    if re.search(NO_FREE_LOOKUP, text):
        return []
    found = [path for pattern, path, _ in LEAGUES if re.search(pattern, text)]
    return found or DEFAULT_LEAGUES


async def _get_json(url: str, params: dict) -> dict:
    import aiohttp  # comes with discord.py
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10),
                                     headers={"User-Agent": "PicksBot/1.0"}) as session:
        async with session.get(url, params=params) as resp:
            resp.raise_for_status()
            return await resp.json(content_type=None)


def simplify_events(raw: dict) -> list[dict]:
    """Keep what grading needs from an ESPN scoreboard response."""
    events = []
    for ev in raw.get("events") or []:
        comp = (ev.get("competitions") or [{}])[0]
        status = (ev.get("status") or comp.get("status") or {}).get("type") or {}
        teams = []
        for c in comp.get("competitors") or []:
            t = c.get("team") or {}
            try:
                score = float(c.get("score")) if c.get("score") not in (None, "") else None
            except (TypeError, ValueError):
                score = None
            teams.append({"id": str(t.get("id") or t.get("displayName")), "score": score,
                          "name": t.get("displayName") or "",
                          "records": {r.get("name") or r.get("type") or "?": r.get("summary") for r in c.get("records") or []
                                      if r.get("summary")},
                          "home": c.get("homeAway") == "home",
                          "short": t.get("shortDisplayName") or t.get("displayName") or "?",
                          "aliases": {norm_team(x) for x in (t.get("displayName"), t.get("shortDisplayName"),
                                      t.get("location"), t.get("abbreviation")) if x},
                          "nickname": norm_team(t.get("name") or "")})
        leaders = []
        for holder in [comp] + list(comp.get("competitors") or []):
            for cat in holder.get("leaders") or []:
                top = (cat.get("leaders") or [{}])[0]
                ath = top.get("athlete") or {}
                if ath.get("id") and ath.get("displayName"):
                    leaders.append({"category": cat.get("name") or "", "athlete_id": str(ath["id"]),
                                    "name": ath["displayName"]})
        if len(teams) == 2:
            venue = comp.get("venue") or {}
            events.append({"leaders": leaders, "venue": {"name": venue.get("fullName") or "",
                                                         "city": (venue.get("address") or {}).get("city") or "",
                                                         "state": (venue.get("address") or {}).get("state") or "",
                                                         "indoor": bool(venue.get("indoor"))}, "id": str(ev.get("id")), "date": ev.get("date") or "", "teams": teams,
                           "state": status.get("state") or "pre", "status_name": status.get("name") or "",
                           "final": bool(status.get("completed")) and status.get("state") == "post",
                           "week": (ev.get("week") or {}).get("number"),
                           "detail": status.get("shortDetail") or "",
                           "season_type": (ev.get("season") or {}).get("type"),
                           "season": (ev.get("season") or {}).get("year")})
    return events


async def fetch_scoreboard(path: str, day: datetime, params: Optional[dict] = None) -> list[dict]:
    extra = params if params is not None else next((x for _, pth, x in LEAGUES if pth == path), {})
    key = (path, day.strftime("%Y%m%d"), tuple(sorted(extra.items())))
    hit = _score_cache.get(key)
    if hit and hit[0] > time.monotonic():
        return hit[1]
    try:
        raw = await _get_json(ESPN.format(path=path), {"dates": key[1], **extra})
        events = simplify_events(raw)
        # Re-check every 2 minutes while games are on; finished days rarely change.
        ttl = 120 if any(not e["final"] for e in events) else (6 * 3600 if events else 600)
    except Exception:
        log.warning("Scoreboard lookup failed for %s %s", path, key[1])
        events, ttl = [], 300
    _score_cache[key] = (time.monotonic() + ttl, events)
    return events


def norm_team(text: str) -> str:
    t = re.sub(r"[.'’]", "", (text or "").lower())
    t = re.sub(r"\bst\b", "state", t)
    t = re.sub(r"^the ", "", t)
    return " ".join(t.split())


def team_matches(text: str, team: dict) -> bool:
    n = norm_team(text)
    if not n:
        return False
    if n in team["aliases"] or n == team["nickname"]:
        return True
    return bool(team["nickname"]) and n.endswith(" " + team["nickname"])  # "KC Chiefs", "LA Rams"


def parse_simple_leg(text: str) -> Optional[dict]:
    """Moneyline, spread, game total or team total, or None if it's anything else."""
    t = text.strip()
    negate = False
    m = re.search(r"\((yes|no)\b[^)]*\)\s*$", t, re.I)       # Kalshi "(NO @ 20¢)"
    if m:
        negate = m.group(1).lower() == "no"
    m = re.match(r"^\s*(no|yes)\s*[-–:,]\s*(.+)$", t, re.I)   # "No - Penn St. wins by over 48.5"
    if m:
        negate ^= m.group(1).lower() == "no"
        t = m.group(2)
    t = re.sub(r"\s*\([^)]*\)", "", t)                          # drop "(vs Clemson)" and similar
    t = re.sub(r"\s*\([^)]*$", "", t).strip()                    # and a cut-off "(vs B..."
    if ": " in t:
        t = t.rsplit(": ", 1)[1]                                   # "IND Colts at KC Chiefs: Will KC Chiefs win?"
    t = t.rstrip("?! ").strip()
    if NOT_SIMPLE.search(t):
        return None
    num = r"(\d+(?:\.\d+)?)"
    unit = r"(?:\s+(?:total\s+)?(?:points|pts|runs|goals)(?:\s+scored)?)?"
    patterns = [
        (rf"^will (?:the )?(.+?) win$", "ml"),
        (rf"^(.+?) wins? by (?:over|more than) {num}{unit}$", "margin"),
        (rf"^(.+?)\s+([+-]{num[1:-1]})(?:\s+spread)?$", "spread"),
        (r"^(.+?)\s+(?:ml|moneyline|to win|wins|win)$", "ml"),
        (rf"^(over|under)\s+{num}{unit}$", "total"),
        (rf"^(.+?)\s+(over|under)\s+{num}{unit}$", "team_total"),
    ]
    for pattern, kind in patterns:
        m = re.match(pattern, t, re.I)
        if not m:
            continue
        g = m.groups()
        if kind == "ml":
            return {"kind": kind, "team": g[0], "negate": negate}
        if kind in ("margin", "spread"):
            return {"kind": kind, "team": g[0], "line": float(g[1]), "negate": negate}
        if kind == "total":
            return {"kind": kind, "side": g[0].lower(), "line": float(g[1]), "negate": negate}
        return {"kind": kind, "team": g[0], "side": g[1].lower(), "line": float(g[2]), "negate": negate}
    return None


def paren_teams(text: str) -> list[str]:
    out = []
    for inside in re.findall(r"\(([^)]*)\)", text or ""):
        parts = re.split(r"\s+(?:vs\.?|v|at)\s+|\s*[@/]\s*", inside.strip(), flags=re.I)
        if len(parts) == 2 and all(1 < len(x) < 40 for x in parts):
            out += [x.strip() for x in parts]
    return out


async def find_games(team_text: str, leagues: list[str], start: datetime) -> list[tuple[dict, int]]:
    """Games in the days around `start` that this team played: [(event, index of the team)]."""
    matches, team_ids = [], set()
    for path in leagues:
        for offset in range(-1, 4):
            day = (start + timedelta(days=offset)).astimezone(TZ)
            for ev in await fetch_scoreboard(path, day):
                for i, team in enumerate(ev["teams"]):
                    if team_matches(team_text, team):
                        matches.append((ev, i))
                        team_ids.add((path, team["id"]))
    if len(team_ids) != 1:
        return []  # nobody, or more than one team answers to that name
    seen, unique = set(), []
    for ev, i in sorted(matches, key=lambda m: m[0]["date"]):
        if ev["id"] not in seen:
            seen.add(ev["id"])
            unique.append((ev, i))
    return unique


def pick_game(games: list[tuple[dict, int]], logged: datetime) -> Optional[tuple[dict, int]]:
    """The first game starting no more than 18 hours before the bet was logged."""
    floor = logged - timedelta(hours=18)
    for ev, i in games:
        try:
            when = datetime.fromisoformat(ev["date"].replace("Z", "+00:00"))
        except ValueError:
            continue
        if when >= floor:
            return ev, i
    return None


def score_line(ev: dict) -> str:
    away, home = sorted(ev["teams"], key=lambda t: t["home"])
    return f"{away['short']} {away['score']:g}, {home['short']} {home['score']:g} (final)"


def judge(leg: dict, ev: dict, i: Optional[int]) -> Optional[str]:
    if i is not None:
        mine, theirs = ev["teams"][i]["score"], ev["teams"][1 - i]["score"]
    total = sum(t["score"] for t in ev["teams"])
    kind = leg["kind"]
    if kind == "ml":
        result = None if mine == theirs else ("hit" if mine > theirs else "miss")
    elif kind == "spread":
        v = mine - theirs + leg["line"]
        result = "push" if v == 0 else ("hit" if v > 0 else "miss")
    elif kind == "margin":
        result = "hit" if mine - theirs > leg["line"] else "miss"
    else:
        value = total if kind == "total" else mine
        if value == leg["line"]:
            result = "push"
        else:
            result = "hit" if (value > leg["line"]) == (leg["side"] == "over") else "miss"
    if result and leg["negate"] and result != "push":
        result = "miss" if result == "hit" else "hit"
    return result


async def free_grade(p, items: list[tuple[int, str]],
                     context_legs: Optional[list[str]] = None) -> dict[int, tuple[str, str]]:
    """Grade what the public scoreboard can settle. Returns {item number: (result, why)};
    items it can't settle are left out."""
    leagues = leagues_for(p["sport"])
    if not leagues:
        return {}
    logged = datetime.fromisoformat(p["created_at"])
    parsed = {n: parse_simple_leg(text) for n, text in items}
    # Teams named anywhere on the pick, so a bare "Over 44.5" can find its game.
    context_teams = [x["team"] for x in parsed.values() if x and "team" in x]
    for leg_text in (context_legs if context_legs is not None else [leg["text"] for leg in get_legs(p["id"])]):
        x = parse_simple_leg(leg_text)
        if x and "team" in x:
            context_teams.append(x["team"])
    for _, text in items:   # "Over 44.5 (Bills vs Dolphins)"
        context_teams += paren_teams(text)
    out: dict[int, tuple[str, str]] = {}
    for n, leg in parsed.items():
        if not leg:
            continue
        if leg["kind"] == "total":
            games = {}
            for team in set(context_teams):
                found = pick_game(await find_games(team, leagues, logged), logged)
                if found:
                    games[found[0]["id"]] = found
            if len(games) != 1:
                continue
            ev, i = next(iter(games.values()))
            i = None
        else:
            found = pick_game(await find_games(leg["team"], leagues, logged), logged)
            if not found:
                continue
            ev, i = found
        if ev.get("season_type") == 1 and p["id"] and p["id"] > 0:
            mark_preseason(p["id"])
        if not ev["final"] or any(t["score"] is None for t in ev["teams"]):
            continue
        result = judge(leg, ev, i)
        if result:
            out[n] = (result, score_line(ev))
            mg = simple_margin(leg, ev, i)
            if mg is not None and p["id"]:
                _margins[(p["id"], n)] = mg
    out.update(await grade_props(p, items, set(out)))
    return out


GRADE_SYSTEM = """You grade sports bets for a group of friends. Search the web for final \
results and box scores, then decide each item.

- hit: the bettor's side won. miss: it lost. push: landed exactly on the line, or was \
voided or cancelled (player didn't play, game called off).
- unknown: the event isn't final yet, or you can't find the stat. Never guess. A wrong \
grade costs someone money on the scoreboard; unknown just means a person settles it.
- Prediction markets (Kalshi): "(NO @ 20¢)" means the bettor wins if the question \
resolves No; "(YES ...)" means it wins on Yes. A leg written as "No - <statement>" wins \
when the statement is false.
- Player props: "15+ receiving yards" means 15 or more. "over 249.5" means 250 or more.

Reply with ONLY a JSON object, no other text:
{"items": [{"n": 1, "result": "hit" | "miss" | "push" | "unknown", "why": "under 12 words, with the stat or score"}]}"""


def grade_request(p: sqlite3.Row, items: list[tuple[int, str]], single: bool) -> str:
    logged = datetime.fromisoformat(p["created_at"]).astimezone(TZ).strftime("%A, %B %d, %Y")
    lines = [f"Today is {datetime.now(TZ).strftime('%A, %B %d, %Y')}.",
             f"Bet logged {logged} on {p['platform']}" + (f" ({p['sport']})" if p["sport"] else "") + ".",
             f"The bet: {p['description']}"]
    if p["notes"]:
        lines.append(f"Bettor's notes: {clip(p['notes'], 400)}")
    if single:
        lines.append("It has no separate legs, so grade the bet itself as item 1.")
    lines.append("Items to grade:")
    lines += [f"{n}. {text}" for n, text in items]
    return "\n".join(lines)


async def lookup_items(p, items: list[tuple[int, str]], single: bool, allow_ai: bool,
                       context_legs: Optional[list[str]] = None) -> tuple[dict[int, dict], bool]:
    """Free scoreboard first, then Claude for the rest. Returns ({n: {result, why}}, used Claude)."""
    by_n: dict[int, dict] = {}
    try:
        for n, (result, why) in (await free_grade(p, items, context_legs)).items():
            by_n[n] = {"result": result, "why": why}
    except Exception:
        log.exception("Free lookup failed")
    rest = [(n, t) for n, t in items if n not in by_n]
    used_ai = False
    if rest and allow_ai and ai_enabled():
        used_ai = True
        text, _ = await ask_claude(GRADE_SYSTEM, grade_request(p, rest, single),
                                   max_searches=min(3 + len(rest), 10))
        for r in extract_json(text).get("items") or []:
            try:
                n = int(r.get("n"))
            except (TypeError, ValueError):
                continue
            if n in dict(rest):
                by_n[n] = r
    return by_n, used_ai


async def autograde(guild_id: int, pick_id: int,
                    allow_ai: bool = True) -> tuple[Optional[sqlite3.Row], list[str], bool, bool]:
    """Look up results for a pick's open legs and apply them: the free scoreboard first,
    then Claude (if allowed) for whatever's left.
    Returns (pick, one line per item, whether anything was graded, whether Claude was used)."""
    p = get_pick(guild_id, pick_id)
    legs = get_legs(pick_id)
    single = not legs
    items = [(1, p["description"])] if single else [(leg["idx"], leg["text"]) for leg in legs
                                                    if leg["status"] == "open"]
    tries = (p["autograde_tries"] or 0) + 1
    db().execute("UPDATE picks SET autograde_at = ?, autograde_tries = ? WHERE id = ?",
                 (now_iso(), tries, pick_id))
    db().commit()
    if not items:
        return p, [], False, False
    by_n, used_ai = await lookup_items(p, items, single, allow_ai)
    lines, graded = apply_results(guild_id, pick_id, items, by_n, single)
    return get_pick(guild_id, pick_id), lines, graded, used_ai


def grading_message(p: sqlite3.Row, lines: list[str], final_try: bool) -> str:
    head = f"🤖 Looked up results for pick `#{p['id']}` ({p['bettor_name']}): {clip(p['description'], 80)}"
    body = "\n".join(lines)
    if p["status"] != "open":
        net = (p["returned"] or 0.0) - p["cost"]
        tail = (f"Result: **{STATUS[p['status']][0]}** ({signed(net)}). Wrong, or cashed out early? "
                f"Fix it with `/leg` or `/result pick_id:{p['id']}`.")
    elif final_try:
        tail = f"I couldn't settle this one. Settle it with `/result pick_id:{p['id']}`."
    elif p["platform"].lower() == "prizepicks" and any(leg["status"] == "miss" for leg in get_legs(p["id"])):
        tail = f"Flex entries can still pay, so settle it with `/result pick_id:{p['id']}` and the amount returned."
    else:
        tail = "Still open. I'll look again in 12 hours."
    return f"{head}\n{body}\n{tail}"


# ==========================================================================
# Extras: tail/fade, challenges, lock of the week, stats, odds, charts,
# hot-hand roles, monthly awards, bankroll/units, weekly loss limit
# ==========================================================================

# ---- small shared helpers ---------------------------------------------------

def week_id(when: Optional[datetime] = None) -> str:
    d = (when or datetime.now(TZ)).astimezone(TZ).date()
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def week_start(when: Optional[datetime] = None) -> datetime:
    """Monday 00:00 local, as UTC."""
    d = (when or datetime.now(TZ)).astimezone(TZ)
    monday = (d - timedelta(days=d.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return monday.astimezone(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def pick_net(p) -> float:
    return (p["returned"] or 0.0) - p["cost"]


def streak_of(results: list[str]) -> tuple[str, int]:
    """results newest first ('win'/'loss'/...). Pushes and voids are skipped."""
    kind, n = "", 0
    for r in results:
        if r not in ("win", "loss"):
            continue
        if not kind:
            kind = r
        if r != kind:
            break
        n += 1
    return ("W" if kind == "win" else "L" if kind == "loss" else ""), n


def current_streak(guild_id: int, bettor_key: str) -> str:
    rows = db().execute(
        """SELECT status FROM picks WHERE guild_id = ? AND bettor_key = ? AND status != 'open'
           ORDER BY settled_at DESC, id DESC LIMIT 50""", (guild_id, bettor_key)).fetchall()
    kind, n = streak_of([r["status"] for r in rows])
    if not kind:
        return ""
    return f"{'🔥' if kind == 'W' and n >= 3 else '🧊' if kind == 'L' and n >= 3 else ''}{kind}{n}"


def longest_win_streak(statuses_oldest_first: list[str]) -> int:
    best = run = 0
    for s in statuses_oldest_first:
        if s == "win":
            run += 1
            best = max(best, run)
        elif s == "loss":
            run = 0
    return best


# ---- tail / fade ------------------------------------------------------------

def follow_counts(pick_id: int) -> dict[str, int]:
    counts = {"tail": 0, "fade": 0}
    for r in db().execute("SELECT kind, COUNT(*) AS n FROM follows WHERE pick_id = ? GROUP BY kind", (pick_id,)):
        counts[r["kind"]] = r["n"]
    return counts


def set_follow(pick_id: int, user_id: int, user_name: str, kind: str) -> str:
    """Toggle. Returns 'added', 'switched' or 'removed'."""
    row = db().execute("SELECT kind FROM follows WHERE pick_id = ? AND user_id = ?", (pick_id, user_id)).fetchone()
    if row and row["kind"] == kind:
        db().execute("DELETE FROM follows WHERE pick_id = ? AND user_id = ?", (pick_id, user_id))
        outcome = "removed"
    else:
        db().execute("INSERT OR REPLACE INTO follows (pick_id, user_id, user_name, kind, created_at) VALUES (?,?,?,?,?)",
                     (pick_id, user_id, user_name, kind, now_iso()))
        outcome = "switched" if row else "added"
    db().commit()
    return outcome


def tail_units(p) -> float:
    """What tailing a settled pick returned, per unit staked."""
    return pick_net(p) / p["cost"] if p["cost"] else 0.0


def fade_units(p) -> float:
    """Fading counts as an even-money bet against the pick."""
    return {"win": -1.0, "loss": 1.0}.get(p["status"], 0.0)


def tf_line(rec: dict) -> str:
    return f"{rec['w']}-{rec['l']}" + (f"-{rec['p']}" if rec["p"] else "") + f" · {rec['u']:+.1f}u"


def tailfade_for(guild_id: int, bettor_key: str) -> tuple[dict, dict, int]:
    """(tail record, fade record, settled count) if you'd followed every one of their picks."""
    tail = {"w": 0, "l": 0, "p": 0, "u": 0.0}
    fade = {"w": 0, "l": 0, "p": 0, "u": 0.0}
    rows = db().execute("SELECT * FROM picks WHERE guild_id = ? AND bettor_key = ? AND status != 'open'",
                        (guild_id, bettor_key)).fetchall()
    for p in rows:
        if p["status"] == "win":
            tail["w"] += 1; fade["l"] += 1
        elif p["status"] == "loss":
            tail["l"] += 1; fade["w"] += 1
        else:
            tail["p"] += 1; fade["p"] += 1
        tail["u"] += tail_units(p)
        fade["u"] += fade_units(p)
    return tail, fade, len(rows)


def my_follows(guild_id: int, user_id: int) -> tuple[dict, dict]:
    tails = {"w": 0, "l": 0, "p": 0, "u": 0.0}
    fades = {"w": 0, "l": 0, "p": 0, "u": 0.0}
    for r in db().execute(
            """SELECT f.kind, p.* FROM follows f JOIN picks p ON p.id = f.pick_id
               WHERE p.guild_id = ? AND f.user_id = ? AND p.status != 'open'""", (guild_id, user_id)):
        rec = tails if r["kind"] == "tail" else fades
        won = (r["status"] == "win") if r["kind"] == "tail" else (r["status"] == "loss")
        lost = (r["status"] == "loss") if r["kind"] == "tail" else (r["status"] == "win")
        rec["w" if won else "l" if lost else "p"] += 1
        rec["u"] += tail_units(r) if r["kind"] == "tail" else fade_units(r)
    return tails, fades


class FollowButton(discord.ui.DynamicItem[discord.ui.Button],
                   template=r"follow:(?P<pick_id>\d+):(?P<kind>tail|fade)"):
    def __init__(self, pick_id: int, kind: str):
        label, style = (("👍 Tail", discord.ButtonStyle.primary) if kind == "tail"
                        else ("👎 Fade", discord.ButtonStyle.secondary))
        super().__init__(discord.ui.Button(label=label, style=style,
                                           custom_id=f"follow:{pick_id}:{kind}", row=1))
        self.pick_id = pick_id
        self.kind = kind

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(int(match["pick_id"]), match["kind"])

    async def callback(self, interaction: discord.Interaction):
        p = get_pick(interaction.guild_id, self.pick_id)
        if p is None or p["status"] != "open":
            await interaction.response.send_message("That pick is already settled.", ephemeral=True)
            return
        if interaction.user.id == p["bettor_id"]:
            await interaction.response.send_message("You can't tail or fade your own pick.", ephemeral=True)
            return
        set_follow(self.pick_id, interaction.user.id, interaction.user.display_name, self.kind)
        await interaction.response.edit_message(embed=pick_embed(p), view=settle_view(self.pick_id))


# ---- bankroll & units -------------------------------------------------------

def get_bankroll(guild_id: int, user_id) -> Optional[dict]:
    raw = get_setting(guild_id, f"bankroll:{user_id}")
    if not raw:
        return None
    b = json.loads(raw)
    net = db().execute(
        """SELECT COALESCE(SUM(COALESCE(returned, 0) - cost), 0) AS n FROM picks
           WHERE guild_id = ? AND bettor_key = ? AND status != 'open' AND settled_at >= ?""",
        (guild_id, str(user_id), b["since"])).fetchone()["n"]
    b["net"] = net
    b["current"] = b["start"] + net
    b["unit_size"] = max(b["current"], 0) * b["unit_pct"] / 100
    return b


BIG_BET_UNITS = 5


def units_note(guild_id: int, p) -> tuple[str, Optional[str]]:
    """(' · 2.0u' or '', warning or None) for a pick's cost against its bettor's bankroll."""
    if not p["bettor_id"]:
        return "", None
    b = get_bankroll(guild_id, p["bettor_id"])
    if not b or b["unit_size"] <= 0:
        return "", None
    u = p["cost"] / b["unit_size"]
    warn = None
    if p["status"] == "open" and u > BIG_BET_UNITS:
        share = p["cost"] / b["current"] * 100 if b["current"] > 0 else 100
        warn = (f"This is {u:.1f} units, {share:.0f}% of {p['bettor_name']}'s "
                f"{money(b['current'])} bankroll.")
    return f" · {u:.1f}u", warn


def weekly_net(guild_id: int, bettor_key: str, when: Optional[datetime] = None) -> float:
    return db().execute(
        """SELECT COALESCE(SUM(COALESCE(returned, 0) - cost), 0) AS n FROM picks
           WHERE guild_id = ? AND bettor_key = ? AND status != 'open' AND settled_at >= ?""",
        (guild_id, bettor_key, iso(week_start(when)))).fetchone()["n"]


# ---- challenges -------------------------------------------------------------

def get_challenge(guild_id: int, cid: int):
    return db().execute("SELECT * FROM challenges WHERE id = ? AND guild_id = ?", (cid, guild_id)).fetchone()


def challenge_embed(c) -> discord.Embed:
    status = {"pending": "⏳ Waiting for an answer", "accepted": "🤝 On", "declined": "🙅 Declined",
              "cancelled": "🚫 Cancelled", "settled": "🏁 Settled"}[c["status"]]
    color = {"pending": 0xF1C40F, "accepted": BRAND, "settled": 0x2ECC71}.get(c["status"], 0x95A5A6)
    e = discord.Embed(title=f"⚔️ Challenge #{c['id']}: {c['challenger_name']} vs {c['opponent_name']}",
                      description=f"**{c['challenger_name']}** says: {c['claim']}\n"
                                  f"**{c['opponent_name']}** takes the other side.", color=color)
    if c["stakes"]:
        e.add_field(name="Stakes", value=clip(c["stakes"], 1024))
    e.add_field(name="Status", value=status)
    if c["status"] == "settled":
        if c["winner_id"]:
            winner = c["challenger_name"] if c["winner_id"] == c["challenger_id"] else c["opponent_name"]
            e.add_field(name="Winner", value=f"🏆 {winner}")
        else:
            e.add_field(name="Winner", value="➖ Push")
    return e


class ChallengeButton(discord.ui.DynamicItem[discord.ui.Button],
                      template=r"chal:(?P<cid>\d+):(?P<action>accept|decline|cancel|c|o|push)"):
    def __init__(self, cid: int, action: str, label: str = "", style=discord.ButtonStyle.secondary):
        super().__init__(discord.ui.Button(label=label or action, style=style, custom_id=f"chal:{cid}:{action}"))
        self.cid = cid
        self.action = action

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(int(match["cid"]), match["action"])

    async def callback(self, interaction: discord.Interaction):
        c = get_challenge(interaction.guild_id, self.cid)
        if c is None:
            await interaction.response.send_message("That challenge no longer exists.", ephemeral=True)
            return
        uid = interaction.user.id
        a = self.action
        if a in ("accept", "decline"):
            if c["status"] != "pending" or uid != c["opponent_id"]:
                await interaction.response.send_message(
                    f"Only {c['opponent_name']} can answer this, and only while it's waiting.", ephemeral=True)
                return
            db().execute("UPDATE challenges SET status = ? WHERE id = ?",
                         ("accepted" if a == "accept" else "declined", c["id"]))
        elif a == "cancel":
            if c["status"] != "pending" or (uid != c["challenger_id"] and not is_mod(interaction.user)):
                await interaction.response.send_message("Only the challenger can cancel, before it's accepted.",
                                                        ephemeral=True)
                return
            db().execute("UPDATE challenges SET status = 'cancelled' WHERE id = ?", (c["id"],))
        else:
            if c["status"] != "accepted" or (uid not in (c["challenger_id"], c["opponent_id"])
                                             and not is_mod(interaction.user)):
                await interaction.response.send_message("Only the two of you (or a mod) can settle this.",
                                                        ephemeral=True)
                return
            winner = {"c": c["challenger_id"], "o": c["opponent_id"], "push": None}[a]
            db().execute("UPDATE challenges SET status = 'settled', winner_id = ?, settled_at = ? WHERE id = ?",
                         (winner, now_iso(), c["id"]))
        db().commit()
        c = get_challenge(interaction.guild_id, self.cid)
        await interaction.response.edit_message(embed=challenge_embed(c), view=challenge_view(c))


def challenge_view(c):
    if c["status"] not in ("pending", "accepted"):
        return None
    view = discord.ui.View(timeout=None)
    if c["status"] == "pending":
        view.add_item(ChallengeButton(c["id"], "accept", "Accept", discord.ButtonStyle.success))
        view.add_item(ChallengeButton(c["id"], "decline", "Decline", discord.ButtonStyle.danger))
        view.add_item(ChallengeButton(c["id"], "cancel", "Cancel", discord.ButtonStyle.secondary))
    else:
        view.add_item(ChallengeButton(c["id"], "c", clip(f"{c['challenger_name']} won", 80), discord.ButtonStyle.success))
        view.add_item(ChallengeButton(c["id"], "o", clip(f"{c['opponent_name']} won", 80), discord.ButtonStyle.success))
        view.add_item(ChallengeButton(c["id"], "push", "Push", discord.ButtonStyle.secondary))
    return view


# ---- lock of the week ---------------------------------------------------------

LOCK_ICON = {"open": "⏳", "win": "✅", "loss": "❌", "push": "➖"}


def lock_standings(guild_id: int, since: Optional[str] = None, until: Optional[str] = None) -> list[dict]:
    sql = "SELECT * FROM locks WHERE guild_id = ? AND status != 'open'"
    args: list = [guild_id]
    if since:
        sql += " AND settled_at >= ?"
        args.append(since)
    if until:
        sql += " AND settled_at < ?"
        args.append(until)
    out: dict[int, dict] = {}
    for r in db().execute(sql + " ORDER BY id", args):
        s = out.setdefault(r["user_id"], {"id": r["user_id"], "name": r["user_name"], "w": 0, "l": 0, "p": 0})
        s["name"] = r["user_name"]
        s["w" if r["status"] == "win" else "l" if r["status"] == "loss" else "p"] += 1
    for s in out.values():
        s["pct"] = s["w"] / (s["w"] + s["l"]) if s["w"] + s["l"] else 0.0
    return sorted(out.values(), key=lambda s: (-s["w"], -s["pct"], s["l"]))


def locks_for_week(guild_id: int, week: str) -> list:
    return db().execute("SELECT * FROM locks WHERE guild_id = ? AND week = ? ORDER BY id", (guild_id, week)).fetchall()


def lock_line(r) -> str:
    return (f"{LOCK_ICON[r['status']]} **{r['user_name']}**: {clip(r['text'], 80)} `#{r['id']}`"
            + (f" · {clip(r['why'], 50)}" if r["why"] and r["status"] != "open" else ""))


def settle_lock(lock_id: int, status: str, why: Optional[str] = None) -> None:
    db().execute("UPDATE locks SET status = ?, why = ?, settled_at = ? WHERE id = ?",
                 (status, why, None if status == "open" else now_iso(), lock_id))
    db().commit()


# ---- stats breakdowns ---------------------------------------------------------

SPORT_NAMES = [
    ("CS2", r"\bcs2?\b|counter-?strike"), ("Esports", r"esports|valorant|league of legends|dota"),
    ("College FB", r"ncaa ?f|college football|ncaaf|\bcfb\b|ncaa football"), ("NFL", r"\bnfl\b"),
    ("WNBA", r"\bwnba\b"), ("College BB", r"ncaa ?b|college basketball|ncaab"), ("NBA", r"\bnba\b"),
    ("MLB", r"\bmlb\b|baseball"), ("NHL", r"\bnhl\b|hockey"),
    ("Soccer", r"soccer|\bepl\b|premier league|la ?liga|serie a|bundesliga|ligue 1|\bmls\b|champions league|liga ?mx"),
    ("Tennis", r"tennis|\batp\b|\bwta\b"), ("UFC/MMA", r"\bufc\b|\bmma\b|boxing"), ("Golf", r"golf|\bpga\b"),
    ("Multi-sport", r"multi"),
]


def sport_group(sport: Optional[str]) -> str:
    if not sport:
        return "No sport"
    t = sport.lower()
    for name, pattern in SPORT_NAMES:
        if re.search(pattern, t):
            return name
    return clip(re.split(r"\s+-\s+|\(", sport)[0].strip().title() or "Other", 14)


def size_group(n_legs: int) -> str:
    return "Single" if n_legs <= 1 else "2-3 legs" if n_legs <= 3 else "4-5 legs" if n_legs <= 5 else "6+ legs"


def breakdown(rows, keyfn) -> list[tuple[str, dict]]:
    groups: dict[str, dict] = {}
    for p in rows:
        g = groups.setdefault(keyfn(p), {"w": 0, "l": 0, "p": 0, "open": 0, "staked": 0.0, "net": 0.0})
        if p["status"] == "open":
            g["open"] += 1
            continue
        g["w" if p["status"] == "win" else "l" if p["status"] == "loss" else "p"] += 1
        g["staked"] += p["cost"]
        g["net"] += pick_net(p)
    return sorted(groups.items(), key=lambda kv: -(kv[1]["w"] + kv[1]["l"] + kv[1]["p"] + kv[1]["open"]))


def breakdown_lines(groups) -> str:
    lines = []
    width = max((len(k) for k, _ in groups), default=6)
    for k, g in groups[:10]:
        settled = g["w"] + g["l"] + g["p"]
        rec = f"{g['w']}-{g['l']}" + (f"-{g['p']}" if g["p"] else "")
        roi = f"{g['net'] / g['staked'] * 100:+.0f}%" if g["staked"] else "-"
        lines.append(f"`{k:<{width}}` {rec} · {signed(g['net'])} · ROI {roi}" if settled
                     else f"`{k:<{width}}` {g['open']} open")
    return clip("\n".join(lines), 1024)


# ---- odds converter -------------------------------------------------------------

def parse_odds(text: str) -> tuple[float, str]:
    """Returns (implied probability 0-1, how it was read). Raises ValueError."""
    t = text.strip().lower().replace(" ", "")
    if not t:
        raise ValueError
    if "/" in t:
        a, b = t.split("/", 1)
        num, den = float(a), float(b)
        if num <= 0 or den <= 0:
            raise ValueError
        return den / (num + den), f"fractional {text.strip()}"
    if t.endswith("%"):
        p = float(t[:-1]) / 100
        kind = "probability"
    elif t.endswith(("¢", "c")):
        p = float(t.rstrip("¢c")) / 100
        kind = "Kalshi price"
    elif t[0] in "+-":
        v = float(t)
        if abs(v) < 100:
            raise ValueError
        p = 100 / (v + 100) if v > 0 else -v / (-v + 100)
        kind = "American odds"
    else:
        v = float(t)
        if 0 < v < 1:
            p, kind = v, "Kalshi price"
        elif 1 < v <= 30:
            p, kind = 1 / v, "decimal odds"
        elif 30 < v < 100:
            p, kind = v / 100, "Kalshi price"
        elif v >= 100:
            p, kind = 100 / (v + 100), "American odds"
        else:
            raise ValueError
    if not 0 < p < 1:
        raise ValueError
    return p, kind


def odds_embed(text: str, stake: float = 10.0) -> discord.Embed:
    p, kind = parse_odds(text)
    dec = 1 / p
    american = f"+{(dec - 1) * 100:.0f}" if dec >= 2 else f"{-100 / (dec - 1):.0f}"
    e = discord.Embed(title=f"Odds: {text.strip()}", description=f"Read as {kind}.", color=BRAND)
    e.add_field(name="Break-even win %", value=f"{p * 100:.1f}%")
    e.add_field(name="American", value=american)
    e.add_field(name="Decimal", value=f"{dec:.2f}")
    e.add_field(name="Kalshi price", value=f"{p * 100:.0f}¢ per $1 contract")
    e.add_field(name=f"On {money(stake)}", value=f"wins {money(stake * (dec - 1))} · returns {money(stake * dec)}")
    e.set_footer(text="Break-even % ignores fees and vig: you need to hit more often than this to profit.")
    return e


# ---- profit chart ---------------------------------------------------------------

CHART_COLORS = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"]
CHART_SURFACE, CHART_TEXT, CHART_MUTED, CHART_GRID = "#1a1a19", "#ffffff", "#c3c2b7", "#383835"


def chart_series(guild_id: int, days: int, bettor_key: Optional[str] = None) -> dict[str, list]:
    """{name: [(settled datetime, cumulative net), ...]} for the window, up to 8 people."""
    since = iso(datetime.now(timezone.utc) - timedelta(days=days))
    sql = "SELECT * FROM picks WHERE guild_id = ? AND status != 'open' AND settled_at >= ?"
    args: list = [guild_id, since]
    if bettor_key:
        sql += " AND bettor_key = ?"
        args.append(bettor_key)
    rows = db().execute(sql + " ORDER BY settled_at, id", args).fetchall()
    by_key: dict[str, list] = {}
    names: dict[str, str] = {}
    for p in rows:
        by_key.setdefault(p["bettor_key"], []).append(p)
        names[p["bettor_key"]] = p["bettor_name"]
    # Keep the 8 most active; color follows the person, assigned by first appearance.
    keys = sorted(by_key, key=lambda k: -len(by_key[k]))[:8]
    keys = sorted(keys, key=lambda k: by_key[k][0]["settled_at"])
    out = {}
    if not keys:
        return out
    # Start everyone at $0 just before the first pick in view, not at the edge of the window.
    first = min(datetime.fromisoformat(by_key[k][0]["settled_at"]) for k in keys)
    start = first - timedelta(hours=12)
    for k in keys:
        total, pts = 0.0, [(start, 0.0)]
        for p in by_key[k]:
            total += pick_net(p)
            pts.append((datetime.fromisoformat(p["settled_at"]), total))
        out[names[k]] = pts
    return out


def render_chart(series: dict[str, list], title: str) -> io.BytesIO:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

    fig, ax = plt.subplots(figsize=(10, 5.2), dpi=150)
    fig.patch.set_facecolor(CHART_SURFACE)
    ax.set_facecolor(CHART_SURFACE)
    ends = []
    for i, (name, pts) in enumerate(series.items()):
        xs = [p[0].astimezone(TZ) for p in pts] + [datetime.now(TZ)]
        ys = [p[1] for p in pts] + [pts[-1][1]]
        color = CHART_COLORS[i % len(CHART_COLORS)]
        ax.step(xs, ys, where="post", color=color, linewidth=2, label=name, solid_capstyle="round")
        ax.plot([xs[-1]], [ys[-1]], marker="o", markersize=5, color=color,
                markeredgecolor=CHART_SURFACE, markeredgewidth=2)
        ends.append((ys[-1], name, color))
    ax.axhline(0, color=CHART_MUTED, linewidth=1, alpha=0.6)
    ax.grid(axis="y", color=CHART_GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(colors=CHART_MUTED, labelsize=9, length=0)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"-${abs(v):,.0f}" if v < 0 else f"${v:,.0f}"))
    import matplotlib.dates as mdates
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d", tz=TZ))
    ax.set_title(title, color=CHART_TEXT, fontsize=13, loc="left",
                 pad=34 if len(series) > 1 else 14, fontweight="bold")
    if len(series) > 1:  # legend in its own row between the title and the plot
        legend = ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), frameon=False, fontsize=9,
                           labelcolor=CHART_TEXT, ncol=min(8, len(series)), handlelength=1.6,
                           borderaxespad=0.3)
        for line in legend.get_lines():
            line.set_linewidth(3)
    if len(series) <= 4:  # direct labels at the line ends, nudged apart so they don't collide
        ymin, ymax = ax.get_ylim()
        gap = (ymax - ymin) * 0.06
        placed: list[float] = []
        for y, name, color in sorted(ends):
            ly = max([y] + [p + gap for p in placed if abs(p - y) < gap])
            placed.append(ly)
            ax.annotate(f"{name} {signed(y)}", xy=(1.0, ly), xycoords=("axes fraction", "data"),
                        xytext=(6, 0), textcoords="offset points", va="center", fontsize=9, color=CHART_TEXT)
        fig.subplots_adjust(right=0.80)
    out = io.BytesIO()
    fig.savefig(out, format="png", facecolor=CHART_SURFACE, bbox_inches="tight")
    plt.close(fig)
    out.seek(0)
    return out


# ---- monthly awards ---------------------------------------------------------------

def month_bounds(year: int, month: int) -> tuple[str, str]:
    start = datetime(year, month, 1, tzinfo=TZ)
    end = datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=TZ)
    return iso(start), iso(end)


def build_awards(guild_id: int, year: int, month: int) -> discord.Embed:
    start, end = month_bounds(year, month)
    label = datetime(year, month, 1).strftime("%B %Y")
    rows = db().execute(
        """SELECT * FROM picks WHERE guild_id = ? AND status != 'open' AND settled_at >= ? AND settled_at < ?
           ORDER BY settled_at, id""", (guild_id, start, end)).fetchall()
    e = discord.Embed(title=f"🏆 {label} awards", color=0xF1C40F)
    if not rows:
        e.description = f"No picks were settled in {label}."
        return e
    best = max(rows, key=pick_net)
    if pick_net(best) > 0:
        e.add_field(name="💰 Biggest hit", inline=False, value=clip(
            f"**{best['bettor_name']}** {signed(pick_net(best))} on {best['description']} (`#{best['id']}`)", 1024))
    people: dict[str, dict] = {}
    for p in rows:
        s = people.setdefault(p["bettor_key"], {"name": p["bettor_name"], "statuses": [], "staked": 0.0, "net": 0.0,
                                                "legs": 0})
        s["statuses"].append(p["status"])
        s["staked"] += p["cost"]
        s["net"] += pick_net(p)
        s["legs"] += sum(1 for leg in get_legs(p["id"]) if leg["status"] == "hit")
    streaks = sorted(((longest_win_streak(s["statuses"]), s["name"]) for s in people.values()), reverse=True)
    if streaks and streaks[0][0] >= 2:
        e.add_field(name="🔥 Longest win streak", value=f"**{streaks[0][1]}**: {streaks[0][0]} straight")
    eligible = [s for s in people.values() if len(s["statuses"]) >= 3 and s["staked"]]
    if eligible:
        top = max(eligible, key=lambda s: s["net"] / s["staked"])
        e.add_field(name="📈 Best ROI (3+ picks)", value=f"**{top['name']}**: {top['net'] / top['staked'] * 100:+.0f}%")
    legs = max(people.values(), key=lambda s: s["legs"])
    if legs["legs"]:
        e.add_field(name="🎯 Most legs hit", value=f"**{legs['name']}**: {legs['legs']}")
    worst = min(rows, key=pick_net)
    if pick_net(worst) < 0:
        e.add_field(name="🧱 Worst beat", inline=False, value=clip(
            f"**{worst['bettor_name']}** {signed(pick_net(worst))} on {worst['description']} (`#{worst['id']}`)", 1024))
    locks = lock_standings(guild_id, since=start, until=end)
    if locks and locks[0]["w"]:
        s = locks[0]
        e.add_field(name="🔒 Lock of the month", value=f"**{s['name']}**: {s['w']}-{s['l']}" + (f"-{s['p']}" if s["p"] else ""))
    top_net = max(people.values(), key=lambda s: s["net"])
    e.set_footer(text=f"{len(rows)} picks settled · top earner {top_net['name']} {signed(top_net['net'])}")
    return e


# ---- hot-hand roles ---------------------------------------------------------------

ROLE_SPECS = {"hot": ("🔥 Hot Hand", 0xFF6B35), "cold": ("🧊 Ice Cold", 0x5DADE2)}


async def assign_hot_roles(client: discord.Client, guild_id: int) -> Optional[str]:
    """Give the week's best (and worst) earner their role. Returns a line for the recap."""
    if get_setting(guild_id, "hotroles") != "on":
        return None
    since = iso(datetime.now(timezone.utc) - timedelta(days=7))
    stats = [s for s in compute_stats(guild_id, since=since) if not s["key"].startswith("label:")]
    hot = stats[0] if stats and stats[0]["net"] > 0 else None
    cold = stats[-1] if stats and stats[-1]["net"] < 0 and stats[-1] is not hot else None
    try:
        guild = client.get_guild(guild_id) or await client.fetch_guild(guild_id)
        parts = []
        for kind, winner in (("hot", hot), ("cold", cold)):
            name, color = ROLE_SPECS[kind]
            role_id = get_setting(guild_id, f"{kind}_role_id")
            role = guild.get_role(int(role_id)) if role_id else None
            if role is None:
                role = await guild.create_role(name=name, colour=discord.Colour(color),
                                               reason="Weekly Hot Hand / Ice Cold roles")
                set_setting(guild_id, f"{kind}_role_id", str(role.id))
            prev = get_setting(guild_id, f"{kind}_holder")
            if prev and (not winner or prev != winner["key"]):
                try:
                    member = await guild.fetch_member(int(prev))
                    await member.remove_roles(role, reason="New week")
                except discord.NotFound:
                    pass
            if winner:
                member = await guild.fetch_member(int(winner["key"]))
                await member.add_roles(role, reason="Weekly Hot Hand / Ice Cold roles")
                set_setting(guild_id, f"{kind}_holder", winner["key"])
                parts.append(f"{name}: <@{winner['key']}> ({signed(winner['net'])} this week)")
            else:
                set_setting(guild_id, f"{kind}_holder", None)
        return " · ".join(parts) or None
    except discord.Forbidden:
        return ("I couldn't hand out the Hot Hand roles. Give me the **Manage Roles** permission "
                "and drag my role above them in Server Settings → Roles.")


# ==========================================================================
# Instant grading, weekly pick'em, hall of fame
# ==========================================================================

LIVE_WINDOW_DAYS = 5          # picks logged within this many days get checked as games finish
LIVE_RECHECK_MINUTES = 2
HOF_MIN_PROFIT = env_int("HOF_MIN_PROFIT", 100, 1)
HOF_MIN_MULTIPLE = env_int("HOF_MIN_MULTIPLE", 5, 2)
HOF_MIN_LEGS = 3


def apply_results(guild_id: int, pick_id: int, items: list[tuple[int, str]], by_n: dict[int, dict],
                  single: bool, only_graded: bool = False) -> tuple[list[str], bool]:
    """Apply looked-up results to a pick. Returns (one line per item, whether anything was graded)."""
    lines, graded = [], False
    for n, leg_text in items:
        r = by_n.get(n) or {}
        result = str(r.get("result", "unknown")).lower()
        why = clip(str(r.get("why") or "").strip(), 120)
        label = "" if single else f" `{n}` {clip(leg_text, 70)}:"
        if result not in ("hit", "miss", "push"):
            if not only_graded:
                lines.append(f"⏳{label} couldn't confirm" + (f" ({why})" if why else ""))
            continue
        graded = True
        lines.append(f"{LEG_ICON[result]}{label} {why or result}")
        if not single:
            db().execute("UPDATE legs SET note = ?, margin = ? WHERE pick_id = ? AND idx = ?",
                         (why or None, _margins.pop((pick_id, n), None), pick_id, n))
        if single:
            settle_pick(guild_id, pick_id, {"hit": "win", "miss": "loss", "push": "push"}[result])
        else:
            grade_leg(guild_id, pick_id, n, result)
    return lines, graded


def open_items(p) -> tuple[list[tuple[int, str]], bool]:
    legs = get_legs(p["id"])
    if not legs:
        return [(1, p["description"])], True
    return [(leg["idx"], leg["text"]) for leg in legs if leg["status"] == "open"], False


async def recap_channel_for(client: discord.Client, guild_id: int):
    channel_id = get_setting(guild_id, "recap_channel")
    return client.get_channel(int(channel_id)) if channel_id else None


async def post_lock_result(client: discord.Client, lock, status: str, why: Optional[str]) -> None:
    channel = await recap_channel_for(client, lock["guild_id"])
    if channel is not None:
        await channel.send(
            f"🔒 Lock graded: <@{lock['user_id']}> {LOCK_ICON[status]} {clip(lock['text'], 100)}"
            + (f" · {clip(why, 100)}" if why else "")
            + f"\n-# Wrong? Fix it with `/lockresult lock_id:{lock['id']}`.",
            allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=True))


# ---- pick'em -----------------------------------------------------------------------

PICKEM_LEAGUES = [  # (choice name, ESPN path, query params, default days of games)
    ("NFL", "football/nfl", {}, 7),
    ("College football (ranked)", "football/college-football", {}, 7),
    ("NBA", "basketball/nba", {}, 1),
    ("NHL", "hockey/nhl", {}, 1),
    ("MLB", "baseball/mlb", {}, 1),
    ("Premier League", "soccer/eng.1", {}, 7),
    ("MLS", "soccer/usa.1", {}, 7),
]
PICKEM_MAX_GAMES = 25
GAMES_PER_MESSAGE = 5


def pickem_league(path: str) -> tuple:
    return next(x for x in PICKEM_LEAGUES if x[1] == path)


def latest_round(guild_id: int):
    return db().execute("SELECT * FROM pickem_rounds WHERE guild_id = ? ORDER BY id DESC LIMIT 1",
                        (guild_id,)).fetchone()


def round_games(round_id: int) -> list:
    return db().execute("SELECT * FROM pickem_games WHERE round_id = ? ORDER BY start, id", (round_id,)).fetchall()


def game_started(g, now: Optional[datetime] = None) -> bool:
    return (now or datetime.now(timezone.utc)) >= datetime.fromisoformat(g["start"])


def game_line(g, n: int) -> str:
    when = datetime.fromisoformat(g["start"]).astimezone(TZ).strftime("%a %-I:%M %p")
    if g["winner"] is None:
        status = when
    elif g["winner"] == -1:
        status = "no result (tie or postponed)"
    else:
        status = f"✅ {g['home'] if g['winner'] == 1 else g['away']}" + (f" · {g['score']}" if g["score"] else "")
    return f"`{n}` {g['away']} @ {g['home']} · {status}"


class PickemButton(discord.ui.DynamicItem[discord.ui.Button], template=r"pe:(?P<gid>\d+):(?P<side>[01])"):
    def __init__(self, game_id: int, side: int, label: str = "", row: int = 0):
        super().__init__(discord.ui.Button(label=label or str(side), style=discord.ButtonStyle.secondary,
                                           custom_id=f"pe:{game_id}:{side}", row=row))
        self.game_id = game_id
        self.side = side

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(int(match["gid"]), int(match["side"]))

    async def callback(self, interaction: discord.Interaction):
        g = db().execute("SELECT * FROM pickem_games WHERE id = ? AND guild_id = ?",
                         (self.game_id, interaction.guild_id)).fetchone()
        if g is None:
            await interaction.response.send_message("That game isn't in pick'em anymore.", ephemeral=True)
            return
        if game_started(g):
            await interaction.response.send_message("That game has started, so picks are locked.", ephemeral=True)
            return
        db().execute("""INSERT OR REPLACE INTO pickem_picks (game_id, user_id, user_name, side, created_at)
                        VALUES (?,?,?,?,?)""",
                     (g["id"], interaction.user.id, interaction.user.display_name, self.side, now_iso()))
        db().commit()
        mine, other = (g["home"], g["away"]) if self.side == 1 else (g["away"], g["home"])
        made = db().execute("""SELECT COUNT(*) AS n FROM pickem_picks p JOIN pickem_games g ON g.id = p.game_id
                               WHERE g.round_id = ? AND p.user_id = ?""", (g["round_id"], interaction.user.id)
                            ).fetchone()["n"]
        total = len(round_games(g["round_id"]))
        await interaction.response.send_message(
            f"Got it: **{mine}** over {other}. You can change it until kickoff. ({made}/{total} picked)",
            ephemeral=True)


def pickem_view(games: list, first_number: int) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    for i, g in enumerate(games):
        view.add_item(PickemButton(g["id"], 0, clip(f"{first_number + i}. {g['away']}", 80), row=i))
        view.add_item(PickemButton(g["id"], 1, clip(f"@ {g['home']}", 80), row=i))
    return view


def pickem_table(round_id: Optional[int], guild_id: int) -> list[dict]:
    sql = """SELECT p.user_id, p.user_name, p.side, g.winner FROM pickem_picks p
             JOIN pickem_games g ON g.id = p.game_id WHERE g.guild_id = ?"""
    args: list = [guild_id]
    if round_id is not None:
        sql += " AND g.round_id = ?"
        args.append(round_id)
    out: dict[int, dict] = {}
    for r in db().execute(sql + " ORDER BY p.created_at", args):
        s = out.setdefault(r["user_id"], {"id": r["user_id"], "name": r["user_name"], "w": 0, "l": 0, "pending": 0})
        s["name"] = r["user_name"]
        if r["winner"] is None:
            s["pending"] += 1
        elif r["winner"] in (0, 1):
            s["w" if r["side"] == r["winner"] else "l"] += 1
    return sorted(out.values(), key=lambda s: (-s["w"], s["l"], s["name"].lower()))


def table_lines(table: list[dict], limit: int = 15) -> str:
    medals = ["🥇", "🥈", "🥉"]
    return "\n".join(f"{medals[i] if i < 3 else f'`{i + 1}.`'} **{s['name']}** · {s['w']}-{s['l']}"
                     + (f" · {s['pending']} to go" if s["pending"] else "") for i, s in enumerate(table[:limit]))


def round_summary(r) -> discord.Embed:
    games = round_games(r["id"])
    table = pickem_table(r["id"], r["guild_id"])
    done = sum(1 for g in games if g["winner"] is not None)
    e = discord.Embed(title=f"🏈 Pick'em · {r['label']}", color=BRAND,
                      description=table_lines(table) or "No picks yet. Tap a team on the game posts.")
    e.set_footer(text=f"{done}/{len(games)} games final · graded automatically from the scoreboard")
    return e


async def grade_pickem_games(client: discord.Client, now: Optional[datetime] = None) -> None:
    now = now or datetime.now(timezone.utc)
    games = db().execute("SELECT * FROM pickem_games WHERE winner IS NULL AND start <= ?", (iso(now),)).fetchall()
    finished_rounds = set()
    for g in games:
        day = datetime.fromisoformat(g["start"]).astimezone(TZ)
        ev = None
        for offset in (0, -1, 1):  # ESPN files late games under the US Eastern date
            ev = next((e for e in await fetch_scoreboard(g["league"], day + timedelta(days=offset),
                                                         pickem_league(g["league"])[2])
                       if e["id"] == g["event_id"]), None)
            if ev:
                break
        winner = score = None
        if ev and ev["final"] and all(t["score"] is not None for t in ev["teams"]):
            home = next(t for t in ev["teams"] if t["home"])
            away = next(t for t in ev["teams"] if not t["home"])
            winner = -1 if home["score"] == away["score"] else (1 if home["score"] > away["score"] else 0)
            score = f"{away['short']} {away['score']:g}, {home['short']} {home['score']:g}"
        elif now - datetime.fromisoformat(g["start"]) > timedelta(days=3):
            winner = -1  # postponed or never finished: doesn't count
        if winner is not None:
            db().execute("UPDATE pickem_games SET winner = ?, score = ? WHERE id = ?", (winner, score, g["id"]))
            db().commit()
            finished_rounds.add(g["round_id"])
    for rid in finished_rounds:
        r = db().execute("SELECT * FROM pickem_rounds WHERE id = ?", (rid,)).fetchone()
        if r["finished_at"] or any(g["winner"] is None for g in round_games(rid)):
            continue
        db().execute("UPDATE pickem_rounds SET finished_at = ? WHERE id = ?", (now_iso(), rid))
        db().commit()
        channel = client.get_channel(r["channel_id"]) if r["channel_id"] else None
        channel = channel or await recap_channel_for(client, r["guild_id"])
        if channel is None:
            continue
        table = pickem_table(rid, r["guild_id"])
        e = round_summary(r)
        e.title = f"🏁 Pick'em final · {r['label']}"
        content = None
        if table and table[0]["w"]:
            winners = [s["name"] for s in table if (s["w"], s["l"]) == (table[0]["w"], table[0]["l"])]
            content = f"🏆 **{' & '.join(winners)}** {'wins' if len(winners) == 1 else 'tie for'} the week at {table[0]['w']}-{table[0]['l']}!"
        await channel.send(content, embed=e, allowed_mentions=discord.AllowedMentions.none())


# ---- hall of fame -------------------------------------------------------------------

def hof_qualifies(p) -> Optional[str]:
    """Why a win belongs in the hall of fame, or None."""
    net = pick_net(p)
    legs = get_legs(p["id"])
    multiple = (p["returned"] or 0) / p["cost"] if p["cost"] else 0
    if legs and len(legs) >= HOF_MIN_LEGS and all(leg["status"] in ("hit", "push") for leg in legs):
        return f"hit all {len(legs)} legs"
    if multiple >= HOF_MIN_MULTIPLE:
        return f"cashed a {multiple:.1f}x payout"
    if net >= HOF_MIN_PROFIT:
        return f"cashed {signed(net)} profit"
    return None


def hof_embed(p, reason: str) -> discord.Embed:
    e = discord.Embed(title=f"🏆 Hall of Fame · {p['bettor_name']}", description=clip(p["description"], 2000),
                      color=0xF1C40F)
    field = legs_field(p["id"])
    if field:
        e.add_field(name=field[0], value=field[1], inline=False)
    e.add_field(name="Paid", value=f"{money(p['returned'] or 0)} on {money(p['cost'])}")
    e.add_field(name="Net", value=signed(pick_net(p)))
    if p["cost"]:
        e.add_field(name="Multiple", value=f"{(p['returned'] or 0) / p['cost']:.1f}x")
    if p["slip_url"]:
        e.add_field(name="Slip", value=f"[View]({p['slip_url']})")
    e.set_footer(text=f"Pick #{p['id']} · {p['platform']}")
    return e


async def post_hall_of_fame(client: discord.Client) -> None:
    for s in db().execute("SELECT guild_id, value FROM settings WHERE key = 'hof_channel'").fetchall():
        channel = client.get_channel(int(s["value"]))
        since = get_setting(s["guild_id"], "hof_since") or "0"
        rows = db().execute(
            """SELECT * FROM picks WHERE guild_id = ? AND status = 'win' AND hof_posted IS NULL
               AND settled_at >= ? ORDER BY settled_at""", (s["guild_id"], since)).fetchall()
        for p in rows:
            reason = hof_qualifies(p)
            db().execute("UPDATE picks SET hof_posted = ? WHERE id = ?", (now_iso() if reason else "skip", p["id"]))
            db().commit()
            if reason and channel is not None:
                mention = f"<@{p['bettor_id']}>" if p["bettor_id"] else f"**{p['bettor_name']}**"
                await channel.send(f"{mention} {reason}! 🎉", embed=hof_embed(p, reason),
                                   allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=True))


# ==========================================================================
# Game-time pings, today's games, parlay calculator, seasons,
# achievements, profile cards
# ==========================================================================

LEAGUE_NAMES = {
    "football/nfl": "NFL", "football/college-football": "College football", "basketball/nba": "NBA",
    "basketball/wnba": "WNBA", "basketball/mens-college-basketball": "College basketball", "baseball/mlb": "MLB",
    "hockey/nhl": "NHL", "soccer/usa.1": "MLS", "soccer/eng.1": "Premier League", "soccer/esp.1": "La Liga",
    "soccer/ita.1": "Serie A", "soccer/ger.1": "Bundesliga", "soccer/fra.1": "Ligue 1", "soccer/mex.1": "Liga MX",
    "soccer/uefa.champions": "Champions League",
}
TODAY_PARAMS = {"football/college-football": {}, "basketball/mens-college-basketball": {}}  # ranked games only
TODAY_HOUR = env_int("TODAY_HOUR", 10, 0, 23)
PING_MINUTES = 30


# ---- today's games ---------------------------------------------------------------

def event_time(ev) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(ev["date"].replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def today_line(ev) -> str:
    away = next(t for t in ev["teams"] if not t["home"])
    home = next(t for t in ev["teams"] if t["home"])
    if ev["final"] and away["score"] is not None:
        return f"✅ {away['short']} {away['score']:g}, {home['short']} {home['score']:g} (final)"
    if ev.get("state") == "in" and away["score"] is not None:
        return (f"🔴 {away['short']} {away['score']:g}, {home['short']} {home['score']:g} "
                f"({ev.get('detail') or 'live'})")
    when = event_time(ev)
    return f"`{when.astimezone(TZ):%-I:%M %p}` {away['short']} @ {home['short']}" if when else \
        f"{away['short']} @ {home['short']}"


async def today_embed(path: str, day: Optional[datetime] = None) -> Optional[discord.Embed]:
    day = day or datetime.now(TZ)
    events = await fetch_scoreboard(path, day, TODAY_PARAMS.get(path))
    local = day.astimezone(TZ).date()
    events = sorted((e for e in events if (event_time(e) or day).astimezone(TZ).date() == local),
                    key=lambda e: e["date"])
    if not events:
        return None
    b2b = await b2b_team_ids(path, day)
    lines = []
    for ev_ in events:
        tired = [t["short"] for t in ev_["teams"] if t["id"] in b2b]
        lines.append(today_line(ev_) + (f" · 🔁 B2B: {', '.join(tired)}" if tired and ev_.get("state") == "pre" else ""))
    more = len(lines) - 25
    e = discord.Embed(title=f"{LEAGUE_NAMES.get(path, path)} · {day.astimezone(TZ):%a %b %-d}", color=BRAND,
                      description=clip("\n".join(lines[:25]) + (f"\n…and {more} more" if more > 0 else ""), 4000))
    e.set_footer(text="Times are Central" + (" · 🔁 B2B = second night of a back-to-back" if b2b else ""))
    if events and all(x.get("season_type") == 1 for x in events):
        e.title += " · Preseason"
    return e


def group_leagues(guild_id: int) -> list[str]:
    """The leagues this group has bet on in the last 30 days (NFL and NBA if none)."""
    since = iso(datetime.now(timezone.utc) - timedelta(days=30))
    found: list[str] = []
    for r in db().execute("SELECT DISTINCT sport FROM picks WHERE guild_id = ? AND created_at >= ? AND sport IS NOT NULL",
                          (guild_id, since)):
        text = r["sport"].lower()
        for pattern, path, _ in LEAGUES:
            if re.search(pattern, text) and path not in found:
                found.append(path)
    return found or ["football/nfl", "basketball/nba"]


# ---- parlay calculator -----------------------------------------------------------

def parlay_embed(text: str, stake: float = 10.0) -> discord.Embed:
    tokens = [t for t in re.split(r"[\s,;]+", text.strip()) if t]
    if not 2 <= len(tokens) <= 20:
        raise ValueError("need 2 to 20 legs")
    legs = [(t, *parse_odds(t)) for t in tokens]
    prob = 1.0
    for _, p, _ in legs:
        prob *= p
    dec = 1 / prob
    american = f"+{(dec - 1) * 100:,.0f}" if dec >= 2 else f"{-100 / (dec - 1):.0f}"
    e = discord.Embed(title=f"{len(legs)}-leg parlay", color=BRAND)
    e.add_field(name="Combined odds", value=f"{american} · {dec:,.2f} decimal")
    e.add_field(name="Chance all legs hit", value=f"{prob * 100:.2f}%" if prob >= 0.001 else f"1 in {1 / prob:,.0f}")
    e.add_field(name=f"On {money(stake)}", value=f"wins {money(stake * (dec - 1))} · returns {money(stake * dec)}")
    e.add_field(name="Legs", inline=False, value=clip("\n".join(
        f"`{i}` {t} → {p * 100:.0f}% · {1 / p:.2f}x" for i, (t, p, _) in enumerate(legs, start=1)), 1024))
    e.set_footer(text="The chance shown uses the odds as given. Each leg's odds include the book's cut, "
                      "so the true chance is a bit lower.")
    return e


# ---- seasons ---------------------------------------------------------------------

def current_season(guild_id: int):
    return db().execute("SELECT * FROM seasons WHERE guild_id = ? AND ended_at IS NULL ORDER BY id DESC LIMIT 1",
                        (guild_id,)).fetchone()


def season_stats(guild_id: int, season) -> list[dict]:
    return [s for s in compute_stats(guild_id, since=season["started_at"], until=season["ended_at"])
            if s["wins"] + s["losses"] + s["pushes"] > 0]


def season_embed(guild_id: int, season, final: bool = False) -> discord.Embed:
    stats = season_stats(guild_id, season)
    medals = ["🥇", "🥈", "🥉"]
    lines = [f"{medals[i] if i < 3 else f'`{i + 1}.`'} **{s['name']}** · {record_line(s)} · {signed(s['net'])} · "
             f"ROI {s['roi']:+.1f}%" for i, s in enumerate(stats[:20])]
    span = f"{local_day(season['started_at'])} – " + (local_day(season["ended_at"]) if season["ended_at"] else "now")
    e = discord.Embed(title=("🏁 Final: " if final else "Season: ") + season["name"], color=BRAND,
                      description="\n".join(lines) or "No settled picks this season yet.")
    e.set_footer(text=span)
    return e


# ---- achievements ------------------------------------------------------------------

BADGES = [  # (key, name, how to earn it)
    ("first", "First Blood", "Win a pick"),
    ("parlay", "Parlay Hitter", "Hit a parlay with 2+ legs"),
    ("bigleg", "Big Leg Energy", "Hit a parlay with 6+ legs"),
    ("heater", "Heater", "Win 5 picks in a row"),
    ("century", "Century", "Profit $100+ on one pick"),
    ("moon", "Moonshot", "Cash a 10x+ payout"),
    ("green", "Green Month", "Finish a month up with 5+ settled picks"),
    ("regular", "Regular", "Log 25 picks"),
    ("grinder", "Grinder", "Log 100 picks"),
    ("lock", "Lock Master", "Win 3 locks of the week"),
    ("pickem", "Pick'em Champ", "Win a pick'em round"),
    ("rival", "Rival", "Win 3 head-to-head challenges"),
    ("heartbreak", "Heartbreak Kid", "Lose a 4+ leg parlay by a single leg"),
]
BADGE_ICONS = {"first": "🩸", "parlay": "🧩", "bigleg": "💎", "heater": "🔥", "century": "💯", "moon": "🚀",
               "green": "📈", "regular": "🗓️", "grinder": "🏛️", "lock": "🔒", "pickem": "🏈", "rival": "⚔️",
               "heartbreak": "💔"}


def earned_badges(guild_id: int, bettor_key: str) -> set[str]:
    picks = db().execute("SELECT * FROM picks WHERE guild_id = ? AND bettor_key = ? ORDER BY settled_at, id",
                         (guild_id, bettor_key)).fetchall()
    got: set[str] = set()
    if len(picks) >= 25:
        got.add("regular")
    if len(picks) >= 100:
        got.add("grinder")
    settled = [p for p in picks if p["status"] != "open"]
    months: dict[str, list] = {}
    for p in settled:
        legs = get_legs(p["id"])
        if p["status"] == "win":
            got.add("first")
            if len(legs) >= 2:
                got.add("parlay")
            if len(legs) >= 6:
                got.add("bigleg")
            if pick_net(p) >= 100:
                got.add("century")
            if p["cost"] and (p["returned"] or 0) / p["cost"] >= 10:
                got.add("moon")
        if p["status"] == "loss" and len(legs) >= 4 and sum(1 for leg in legs if leg["status"] == "miss") == 1 \
                and all(leg["status"] in ("hit", "miss") for leg in legs):
            got.add("heartbreak")
        months.setdefault(p["settled_at"][:7], []).append(p)
    if longest_win_streak([p["status"] for p in settled]) >= 5:
        got.add("heater")
    if any(len(ps) >= 5 and sum(pick_net(p) for p in ps) > 0 for ps in months.values()):
        got.add("green")
    if not bettor_key.startswith("label:"):
        uid = int(bettor_key)
        if db().execute("SELECT COUNT(*) AS n FROM locks WHERE guild_id = ? AND user_id = ? AND status = 'win'",
                        (guild_id, uid)).fetchone()["n"] >= 3:
            got.add("lock")
        if db().execute("SELECT COUNT(*) AS n FROM challenges WHERE guild_id = ? AND status = 'settled' "
                        "AND winner_id = ?", (guild_id, uid)).fetchone()["n"] >= 3:
            got.add("rival")
        for r in db().execute("SELECT id FROM pickem_rounds WHERE guild_id = ? AND finished_at IS NOT NULL",
                              (guild_id,)):
            table = pickem_table(r["id"], guild_id)
            if table and table[0]["w"] and any(
                    s["id"] == uid for s in table if (s["w"], s["l"]) == (table[0]["w"], table[0]["l"])):
                got.add("pickem")
                break
    return got


def badge_line(got: set[str]) -> str:
    return " ".join(BADGE_ICONS[k] for k, _, _ in BADGES if k in got)


# ---- game-time pings -----------------------------------------------------------------

async def games_for_pick(p) -> list[dict]:
    """The scoreboard games this pick's simple legs are riding on."""
    leagues = leagues_for(p["sport"])
    if not leagues:
        return []
    items, _ = open_items(p)
    teams = [x["team"] for x in (parse_simple_leg(t) for _, t in items) if x and "team" in x]
    logged = datetime.fromisoformat(p["created_at"])
    found: dict[str, dict] = {}
    for team in set(teams):
        hit = pick_game(await find_games(team, leagues, logged), logged)
        if hit:
            found[hit[0]["id"]] = hit[0]
    return list(found.values())


# ---- profile card ----------------------------------------------------------------------

def render_card(name: str, s: dict, streak: str, best, rate: Optional[str], top_sport: Optional[str],
                badges: list[str], series: list, avatar: Optional[bytes]) -> io.BytesIO:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, FancyBboxPatch

    fig = plt.figure(figsize=(12, 6.3), dpi=100)
    fig.patch.set_facecolor(CHART_SURFACE)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1200)
    ax.set_ylim(0, 630)
    ax.axis("off")
    ax.add_patch(FancyBboxPatch((24, 24), 1152, 582, boxstyle="round,pad=0,rounding_size=28",
                                facecolor="#222220", edgecolor=CHART_GRID, linewidth=2))
    ax.add_patch(FancyBboxPatch((60, 592), 1080, 6, boxstyle="round,pad=0,rounding_size=3",
                                facecolor=CHART_COLORS[0], edgecolor="none"))
    # avatar or initials
    cx, cy, r = 130, 495, 70
    placed = False
    if avatar:
        try:
            import numpy as np
            from PIL import Image
            img = Image.open(io.BytesIO(avatar)).convert("RGBA").resize((2 * r, 2 * r))
            arr = np.asarray(img)
            im = ax.imshow(arr, extent=(cx - r, cx + r, cy - r, cy + r), zorder=3)
            im.set_clip_path(Circle((cx, cy), r, transform=ax.transData))
            placed = True
        except Exception:
            placed = False
    if not placed:
        ax.add_patch(Circle((cx, cy), r, facecolor=CHART_COLORS[6], zorder=3))
        initials = "".join(w[0] for w in name.split()[:2]).upper() or "?"
        ax.text(cx, cy, initials, color=CHART_TEXT, fontsize=40, fontweight="bold", ha="center", va="center", zorder=4)
    ax.text(230, 520, clip(name, 22), color=CHART_TEXT, fontsize=34, fontweight="bold", va="center")
    sub = f"{record_line(s)}" + (f"  ·  streak {streak.lstrip('🔥🧊')}" if streak else "") + \
          (f"  ·  {top_sport}" if top_sport else "")
    ax.text(232, 465, sub, color=CHART_MUTED, fontsize=16, va="center")

    def stat(x, label, value, color=CHART_TEXT):
        size = 30 if len(value) <= 8 else 24 if len(value) <= 11 else 19
        ax.text(x, 360, value, color=color, fontsize=size, fontweight="bold", va="center")
        ax.text(x, 315, label.upper(), color=CHART_MUTED, fontsize=11, va="center")

    green, red = "#3fb97a", "#e66767"
    stat(70, "Net", signed(s["net"]), green if s["net"] >= 0 else red)
    stat(370, "ROI", f"{s['roi']:+.1f}%", green if s["roi"] >= 0 else red)
    settled = s["wins"] + s["losses"]
    stat(650, "Win rate", f"{s['wins'] / settled * 100:.0f}%" if settled else "-")
    stat(880, "Legs hit", rate.split(" ")[0] if rate else "-")
    if best is not None and pick_net(best) > 0:
        ax.text(70, 240, "BEST HIT", color=CHART_MUTED, fontsize=11, va="center")
        ax.text(70, 205, clip(f"{signed(pick_net(best))} on {best['description']}", 52), color=CHART_TEXT,
                fontsize=16, va="center")
    if badges:  # wrap onto up to two lines
        ax.text(70, 145, f"BADGES {len(badges)}/{len(BADGES)}", color=CHART_MUTED, fontsize=11, va="center")
        rows: list[list[str]] = [[]]
        for b in badges:
            if rows[-1] and len("  ·  ".join(rows[-1] + [b])) > 78:
                rows.append([])
            rows[-1].append(b)
        if len(rows) > 2:  # say how many didn't fit instead of dropping them silently
            hidden = sum(len(r) for r in rows[2:])
            while rows[1] and len("  ·  ".join(rows[1] + [f"+{hidden + 1} more"])) > 78:
                rows[1].pop()
                hidden += 1
            rows = [rows[0], rows[1] + [f"+{hidden} more"]]
        for k, row in enumerate(rows[:2]):
            ax.text(70, 112 - k * 30, "  ·  ".join(row), color=CHART_TEXT, fontsize=14, va="center")
    ax.text(1150, 50, f"PIMP-BOT · {datetime.now(TZ):%b %-d, %Y}", color=CHART_MUTED, fontsize=10, ha="right",
            va="center")
    if len(series) >= 2:  # small profit sparkline, top right
        spark = fig.add_axes([0.70, 0.64, 0.26, 0.22])
        spark.set_facecolor("#222220")
        xs = [p[0] for p in series]
        ys = [p[1] for p in series]
        spark.step(xs, ys, where="post", color=CHART_COLORS[0], linewidth=2)
        spark.axhline(0, color=CHART_MUTED, linewidth=1, alpha=0.5)
        spark.axis("off")
        spark.set_title("PROFIT", color=CHART_MUTED, fontsize=10, loc="left")
    out = io.BytesIO()
    fig.savefig(out, format="png", facecolor=CHART_SURFACE)
    plt.close(fig)
    out.seek(0)
    return out


async def fetch_avatar(user) -> Optional[bytes]:
    try:
        url = str(user.display_avatar.replace(size=256, format="png").url)
        import aiohttp
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                return await resp.read()
    except Exception:
        return None


# ==========================================================================
# r8: survivor pool, exposure, history/compare/undo, milestones, reminders,
# backups, settings overview
# ==========================================================================

BACKUP_HOUR = env_int("BACKUP_HOUR", 4, 0, 23)
UNDO_MINUTES = 15
NFL = "football/nfl"
SPORT_CHOICES = [app_commands.Choice(name=n, value=n) for n, _ in SPORT_NAMES]


# ---- survivor pool ---------------------------------------------------------------

def active_pool(guild_id: int):
    return db().execute("SELECT * FROM survivor_pools WHERE guild_id = ? AND ended_at IS NULL ORDER BY id DESC LIMIT 1",
                        (guild_id,)).fetchone()


def week_key_of(ev) -> Optional[str]:
    if ev.get("week") is None:
        return None
    return f"{ev.get('season') or ''}-{ev['week']}"


async def upcoming_week(now: Optional[datetime] = None) -> tuple[Optional[str], list[dict]]:
    """The NFL week with the soonest game that hasn't started, and that week's not-started games."""
    now = now or datetime.now(timezone.utc)
    events, seen = [], set()
    days = await asyncio.gather(*(fetch_scoreboard(NFL, now.astimezone(TZ) + timedelta(days=o)) for o in range(8)))
    for day in days:
        for ev in day:
            if ev["id"] not in seen:
                seen.add(ev["id"])
                events.append(ev)
    upcoming = sorted((e for e in events if e.get("state") == "pre" and (event_time(e) or now) > now and week_key_of(e)),
                      key=lambda e: e["date"])
    if not upcoming:
        return None, []
    wk = week_key_of(upcoming[0])
    return wk, [e for e in upcoming if week_key_of(e) == wk]


def survivor_status(pool) -> dict[int, dict]:
    """Per entrant: name, picks (oldest first), alive, out_reason."""
    picks = db().execute("SELECT * FROM survivor_picks WHERE pool_id = ? ORDER BY start", (pool["id"],)).fetchall()
    if not picks:
        return {}
    weeks = []
    for p in picks:
        if p["week_key"] not in weeks:
            weeks.append(p["week_key"])
    first_week = weeks[0]
    # A week is done once every pick made for it is graded.
    done = [w for w in weeks if all(p["result"] for p in picks if p["week_key"] == w)]
    people: dict[int, dict] = {}
    for p in picks:
        s = people.setdefault(p["user_id"], {"name": p["user_name"], "picks": [], "alive": True, "out": None})
        s["name"] = p["user_name"]
        s["picks"].append(p)
    for uid, s in people.items():
        by_week = {p["week_key"]: p for p in s["picks"]}
        if first_week not in by_week:
            s["alive"], s["out"] = False, "joined late"
            continue
        for w in weeks:
            p = by_week.get(w)
            if p is None and w in done:
                s["alive"], s["out"] = False, f"no pick in week {w.split('-')[-1]}"
                break
            if p is not None and p["result"] == "loss":
                s["alive"], s["out"] = False, f"{p['team']} lost (week {w.split('-')[-1]})"
                break
    return people


def survivor_embed(pool) -> discord.Embed:
    people = survivor_status(pool)
    alive = [s for s in people.values() if s["alive"]]
    out = [s for s in people.values() if not s["alive"]]
    icon = {"win": "✅", "loss": "❌", None: "⏳"}
    def trail(s):
        return " ".join(f"{icon[p['result']]}{p['team']}" for p in s["picks"][-6:])
    e = discord.Embed(title=f"💀 Survivor · {pool['name']}", color=BRAND,
                      description=f"**{len(alive)} alive** of {len(people)}" if people else
                      "No picks yet. Everyone picks one team a week with `/survivor pick`.")
    if alive:
        e.add_field(name="Still standing", inline=False,
                    value=clip("\n".join(f"**{s['name']}** · {trail(s)}" for s in alive), 1024))
    if out:
        e.add_field(name="Out", inline=False,
                    value=clip("\n".join(f"~~{s['name']}~~ · {s['out']}" for s in out), 1024))
    e.set_footer(text="Pick one team to win each week. A team can only be used once. Lose or skip a week and you're out.")
    return e


async def grade_survivor(client: discord.Client, now: Optional[datetime] = None) -> None:
    now = now or datetime.now(timezone.utc)
    rows = db().execute("SELECT * FROM survivor_picks WHERE result IS NULL AND start <= ?", (iso(now),)).fetchall()
    for p in rows:
        day = datetime.fromisoformat(p["start"]).astimezone(TZ)
        ev = None
        for offset in (0, -1, 1):
            ev = next((e for e in await fetch_scoreboard(NFL, day + timedelta(days=offset)) if e["id"] == p["event_id"]), None)
            if ev:
                break
        if not ev or not ev["final"] or any(t["score"] is None for t in ev["teams"]):
            continue
        mine = next(t for t in ev["teams"] if t["id"] == p["team_id"])
        theirs = next(t for t in ev["teams"] if t["id"] != p["team_id"])
        result = "win" if mine["score"] > theirs["score"] else "loss"   # a tie counts as a loss
        db().execute("UPDATE survivor_picks SET result = ? WHERE pool_id = ? AND user_id = ? AND week_key = ?",
                     (result, p["pool_id"], p["user_id"], p["week_key"]))
        db().commit()
        if result == "loss":
            pool = db().execute("SELECT * FROM survivor_pools WHERE id = ?", (p["pool_id"],)).fetchone()
            channel = client.get_channel(pool["channel_id"]) if pool["channel_id"] else None
            channel = channel or await recap_channel_for(client, pool["guild_id"])
            if channel is not None:
                alive = sum(1 for s in survivor_status(pool).values() if s["alive"])
                await channel.send(f"💀 <@{p['user_id']}> is out of survivor: the {p['team']} lost "
                                   f"{mine['score']:g}-{theirs['score']:g}. {alive} left standing.",
                                   allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=True))


# ---- exposure ------------------------------------------------------------------------

async def exposure_embed(guild_id: int) -> discord.Embed:
    picks = db().execute("SELECT * FROM picks WHERE guild_id = ? AND status = 'open' ORDER BY id", (guild_id,)).fetchall()
    games: dict[str, dict] = {}
    loose = []
    secret = [p for p in picks if p["hidden"]]
    picks = [p for p in picks if not p["hidden"]]
    for p in picks:
        try:
            evs = await games_for_pick(p)
        except Exception:
            evs = []
        if not evs:
            loose.append(p)
        for ev in evs:
            g = games.setdefault(ev["id"], {"ev": ev, "picks": []})
            g["picks"].append(p)
    e = discord.Embed(title="💸 What's riding", color=BRAND)
    if not picks:
        e.description = "Nothing open right now."
        return e
    total = sum(p["cost"] for p in picks)
    e.description = f"**{len(picks)} open picks · {money(total)} at risk**"
    for g in sorted(games.values(), key=lambda g: g["ev"]["date"])[:20]:
        ev = g["ev"]
        risk = sum(p["cost"] for p in g["picks"])
        who = ", ".join(sorted({p["bettor_name"] for p in g["picks"]}))
        e.add_field(name=clip(today_line(ev).replace("`", ""), 256), inline=False,
                    value=clip(f"{len(g['picks'])} pick{'s' if len(g['picks']) != 1 else ''} · {money(risk)} · {who}\n"
                               + " ".join(f"`#{p['id']}`" for p in g["picks"][:15]), 1024))
    if loose:
        e.add_field(name="Props, esports and other picks", inline=False, value=clip(
            f"{len(loose)} pick{'s' if len(loose) != 1 else ''} · {money(sum(p['cost'] for p in loose))} · "
            + ", ".join(sorted({p['bettor_name'] for p in loose})), 1024))
    if secret:
        e.add_field(name="🔒 Hidden picks", inline=False,
                    value=f"{len(secret)} · {money(sum(p['cost'] for p in secret))} · revealed when they settle")
    e.set_footer(text="A parlay with legs in two games shows under both.")
    return e


# ---- history -------------------------------------------------------------------------

HISTORY_PAGE = 10


def history_rows(guild_id: int, key: Optional[str], status: Optional[str], sport: Optional[str]) -> list:
    sql = "SELECT * FROM picks WHERE guild_id = ?"
    args: list = [guild_id]
    if key:
        sql += " AND bettor_key = ?"
        args.append(key)
    if status == "settled":
        sql += " AND status != 'open'"
    elif status:
        sql += " AND status = ?"
        args.append(status)
    rows = db().execute(sql + " ORDER BY id DESC", args).fetchall()
    if sport:
        rows = [p for p in rows if sport_group(p["sport"]) == sport]
    return rows


def history_embed(rows: list, page: int, title: str) -> discord.Embed:
    pages = max(1, (len(rows) + HISTORY_PAGE - 1) // HISTORY_PAGE)
    page = max(0, min(page, pages - 1))
    chunk = rows[page * HISTORY_PAGE:(page + 1) * HISTORY_PAGE]
    lines = []
    for p in chunk:
        icon = STATUS[p["status"]][0].split()[0]
        net = f" · {signed(pick_net(p))}" if p["status"] != "open" else f" · {money(p['cost'])} riding"
        lines.append(f"{icon} `#{p['id']}` {local_day(p['created_at'])} **{p['bettor_name']}** · "
                     f"{clip(shown_desc(p), 55)}{net}")
    e = discord.Embed(title=title, color=BRAND, description="\n".join(lines) or "Nothing matches.")
    e.set_footer(text=f"Page {page + 1}/{pages} · {len(rows)} picks")
    return e


def history_view(owner_id: int, rows: list, title: str, page: int = 0) -> Optional[discord.ui.View]:
    pages = (len(rows) + HISTORY_PAGE - 1) // HISTORY_PAGE
    if pages <= 1:
        return None
    view = discord.ui.View(timeout=600)
    state = {"page": page}

    def make(delta: int, label: str):
        btn = discord.ui.Button(label=label, style=discord.ButtonStyle.secondary)

        async def cb(interaction: discord.Interaction):
            if interaction.user.id != owner_id:
                await interaction.response.send_message("Run `/history` yourself to page through.", ephemeral=True)
                return
            state["page"] = max(0, min(pages - 1, state["page"] + delta))
            await interaction.response.edit_message(embed=history_embed(rows, state["page"], title), view=view)
        btn.callback = cb
        return btn
    view.add_item(make(-1, "◀ Newer"))
    view.add_item(make(1, "Older ▶"))
    return view


# ---- compare -------------------------------------------------------------------------

def profile_numbers(guild_id: int, key: str) -> Optional[dict]:
    stats = compute_stats(guild_id, key)
    if not stats:
        return None
    s = stats[0]
    settled = db().execute("SELECT * FROM picks WHERE guild_id = ? AND bettor_key = ? AND status != 'open'",
                           (guild_id, key)).fetchall()
    best = max(settled, key=pick_net) if settled else None
    groups = breakdown(settled, lambda p: sport_group(p["sport"]))
    return {"s": s, "streak": current_streak(guild_id, key), "legs": hit_rate(leg_counts(guild_id, key)),
            "best": signed(pick_net(best)) if best is not None and pick_net(best) > 0 else "-",
            "sport": groups[0][0] if groups else "-", "badges": len(earned_badges(guild_id, key))}


# ---- milestones ------------------------------------------------------------------------

async def announce_milestones(client: discord.Client, now: Optional[datetime] = None) -> None:
    now = now or datetime.now(timezone.utc)
    since = iso(now - timedelta(days=2))
    for r in db().execute("SELECT guild_id, value FROM settings WHERE key = 'recap_channel'").fetchall():
        gid = r["guild_id"]
        channel = client.get_channel(int(r["value"]))
        first_run = get_setting(gid, "milestones_init") is None
        if first_run:   # the first time, just record what everyone already has, so nobody gets spammed
            set_setting(gid, "milestones_init", now_iso())
            for x in db().execute("SELECT DISTINCT bettor_key FROM picks WHERE guild_id = ?", (gid,)).fetchall():
                set_setting(gid, f"badges:{x['bettor_key']}", json.dumps(sorted(earned_badges(gid, x["bettor_key"]))))
            continue
        keys = [x["bettor_key"] for x in db().execute(
            "SELECT DISTINCT bettor_key FROM picks WHERE guild_id = ? AND status != 'open' AND settled_at >= ?",
            (gid, since))]
        for key in keys:
            name = db().execute("SELECT bettor_name FROM picks WHERE guild_id = ? AND bettor_key = ? ORDER BY id DESC "
                                "LIMIT 1", (gid, key)).fetchone()["bettor_name"]
            who = f"<@{key}>" if not key.startswith("label:") else f"**{name}**"
            got = earned_badges(gid, key)
            prev = set(json.loads(get_setting(gid, f"badges:{key}") or "[]"))
            set_setting(gid, f"badges:{key}", json.dumps(sorted(got)))
            new_badges = [b for b in BADGES if b[0] in got and b[0] not in prev]
            if channel is not None:
                for k, n, how in new_badges:
                        await channel.send(f"🎖️ {who} unlocked **{BADGE_ICONS[k]} {n}**: {how.lower()}!",
                                           allowed_mentions=discord.AllowedMentions(everyone=False, roles=False,
                                                                                    users=True))
            last = db().execute("SELECT id FROM picks WHERE guild_id = ? AND bettor_key = ? AND status != 'open' "
                                "ORDER BY settled_at DESC, id DESC LIMIT 1", (gid, key)).fetchone()
            rows = db().execute("SELECT status FROM picks WHERE guild_id = ? AND bettor_key = ? AND status != 'open' "
                                "ORDER BY settled_at DESC, id DESC LIMIT 60", (gid, key)).fetchall()
            kind, n = streak_of([x["status"] for x in rows])
            mark = f"{kind}{n}@{last['id']}"
            if kind == "W" and n in (5, 10, 15, 20) and get_setting(gid, f"streakann:{key}") != mark:
                set_setting(gid, f"streakann:{key}", mark)
                if channel is not None and not (n == 5 and any(b[0] == "heater" for b in new_badges)):
                    await channel.send(f"🔥 {who} has won **{n} straight**!",
                                       allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=True))


# ---- reminders ---------------------------------------------------------------------------

def parse_when(text: str, now: Optional[datetime] = None) -> Optional[datetime]:
    """'30m', 'in 2 hours', '6pm', '18:30', 'tomorrow 9am', 'tonight 7'. Returns a local datetime or None."""
    now = (now or datetime.now(TZ)).astimezone(TZ)
    t = " ".join(text.lower().replace(".", "").split())
    m = re.fullmatch(r"(?:in\s+)?(\d+)\s*(m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days)", t)
    if m:
        n, unit = int(m[1]), m[2][0]
        when = now + {"m": timedelta(minutes=n), "h": timedelta(hours=n), "d": timedelta(days=n)}[unit]
    else:
        m = re.fullmatch(r"(today|tomorrow|tonight)?\s*(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", t)
        if not m or (m[1] is None and m[3] is None and m[4] is None):
            return None
        hour, minute = int(m[2]), int(m[3] or 0)
        if hour > 23 or minute > 59 or (m[4] and not 1 <= hour <= 12):
            return None
        if m[4] == "pm" and hour != 12:
            hour += 12
        elif m[4] == "am" and hour == 12:
            hour = 0
        elif not m[4] and m[1] == "tonight" and hour < 12:
            hour += 12
        when = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if m[1] == "tomorrow":
            when += timedelta(days=1)
        elif when <= now:
            when += timedelta(days=1)
    if not now < when <= now + timedelta(days=30):
        return None
    return when


async def send_reminders(client: discord.Client, now: Optional[datetime] = None) -> None:
    now = now or datetime.now(timezone.utc)
    for r in db().execute("SELECT * FROM reminders WHERE sent_at IS NULL AND due_at <= ?", (iso(now),)).fetchall():
        db().execute("UPDATE reminders SET sent_at = ? WHERE id = ?", (now_iso(), r["id"]))
        db().commit()
        text = f"⏰ Reminder: {r['text']}"
        try:
            user = await client.fetch_user(r["user_id"])
            await user.send(text)
        except Exception:
            channel = client.get_channel(r["channel_id"]) if r["channel_id"] else None
            if channel is not None:
                await channel.send(f"<@{r['user_id']}> {text}",
                                   allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=True))


# ---- backups ------------------------------------------------------------------------------

def backup_files(guild_id: int) -> list:
    """A consistent copy of the database plus an Excel export, as discord.Files."""
    stamp = datetime.now(TZ).strftime("%Y-%m-%d")
    folder = tempfile.mkdtemp()
    path = os.path.join(folder, f"picks_backup_{stamp}.db")
    dest = sqlite3.connect(path)
    db().backup(dest)
    dest.close()
    files = []
    if os.path.getsize(path) <= 9 * 1024 * 1024:
        files.append(discord.File(path, filename=f"picks_backup_{stamp}.db"))
    files.append(discord.File(build_workbook(guild_id), filename=f"picks_backup_{stamp}.xlsx"))
    return files


async def post_backups(client: discord.Client, now: Optional[datetime] = None) -> None:
    now = (now or datetime.now(TZ)).astimezone(TZ)
    for r in db().execute("SELECT guild_id, value FROM settings WHERE key = 'backup_channel'").fetchall():
        today = now.date().isoformat()
        if now.hour < BACKUP_HOUR or get_setting(r["guild_id"], "last_backup") == today:
            continue
        set_setting(r["guild_id"], "last_backup", today)
        channel = client.get_channel(int(r["value"]))
        if channel is None:
            continue
        n = db().execute("SELECT COUNT(*) AS n FROM picks WHERE guild_id = ?", (r["guild_id"],)).fetchone()["n"]
        await channel.send(f"🗄️ Nightly backup · {n} picks", files=backup_files(r["guild_id"]))


# ==========================================================================
# r9: free player-prop grading from ESPN box scores, live sweats, trends,
# injury alerts, Kalshi settlement, group parlay, copies, Wrapped, schedule,
# preseason flag
# ==========================================================================

import unicodedata

ESPN_SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/{path}/summary"
ESPN_SEARCH = "https://site.web.api.espn.com/apis/common/v3/search"
ESPN_GAMELOG = "https://site.web.api.espn.com/apis/common/v3/sports/{path}/athletes/{athlete_id}/gamelog"
ESPN_INJURIES = "https://site.api.espn.com/apis/site/v2/sports/{path}/injuries"
LEAGUE_SLUGS = {"basketball/nba": "nba", "basketball/wnba": "wnba", "football/nfl": "nfl",
                "football/college-football": "college-football", "baseball/mlb": "mlb", "hockey/nhl": "nhl",
                "basketball/mens-college-basketball": "mens-college-basketball"}
PROP_PATHS = list(LEAGUE_SLUGS)
_summary_cache: dict[tuple[str, str], tuple[float, Optional[dict]]] = {}
_player_cache: dict[tuple[str, str], tuple[float, list[dict]]] = {}


# ---- stat catalog --------------------------------------------------------------------

# A component is (ESPN keys, ESPN labels, preferred box-score group or None).
C = {
    # basketball
    "pts": (("points",), ("PTS",), None),
    "reb": (("rebounds", "totalRebounds"), ("REB",), None),
    "ast": (("assists",), ("AST",), None),
    "stl": (("steals",), ("STL",), None),
    "blk": (("blocks",), ("BLK",), None),
    "tov": (("turnovers",), ("TO",), None),
    "3pm": (("threePointFieldGoalsMade-threePointFieldGoalsAttempted", "threePointFieldGoalsMade"), ("3PT",), None),
    "fgm": (("fieldGoalsMade-fieldGoalsAttempted",), ("FG",), None),
    "ftm": (("freeThrowsMade-freeThrowsAttempted",), ("FT",), None),
    "oreb": (("offensiveRebounds",), ("OREB",), None),
    "dreb": (("defensiveRebounds",), ("DREB",), None),
    "min": (("minutes",), ("MIN",), None),
    # football
    "pass_yds": (("passingYards",), (), "passing"),
    "pass_td": (("passingTouchdowns",), (), "passing"),
    "pass_cmp": (("completions/passingAttempts", "completions"), ("C/ATT",), "passing"),
    "pass_att": (("completions/passingAttempts#2", "passingAttempts"), ("C/ATT#2",), "passing"),
    "pass_int": (("interceptions",), ("INT",), "passing"),
    "rush_yds": (("rushingYards",), (), "rushing"),
    "rush_att": (("rushingAttempts",), ("CAR",), "rushing"),
    "rush_td": (("rushingTouchdowns",), (), "rushing"),
    "rec": (("receptions",), ("REC",), "receiving"),
    "rec_yds": (("receivingYards",), (), "receiving"),
    "rec_td": (("receivingTouchdowns",), (), "receiving"),
    "targets": (("receivingTargets",), ("TGTS",), "receiving"),
    "long_rec": (("longReception",), (), "receiving"),
    "long_rush": (("longRushing",), (), "rushing"),
    "tackles": (("totalTackles",), (), "defensive"),
    "sacks": (("sacks",), (), "defensive"),
    "def_int": (("interceptions",), ("INT",), "interceptions"),
    "fg_made": (("fieldGoalsMade/fieldGoalAttempts",), ("FG",), "kicking"),
    "kick_pts": (("totalKickingPoints",), ("PTS",), "kicking"),
    # baseball
    "h": (("hits",), ("H",), "batting"),
    "r": (("runs",), ("R",), "batting"),
    "rbi": (("RBIs", "rbis"), ("RBI",), "batting"),
    "hr": (("homeRuns",), ("HR",), "batting"),
    "bb": (("walks",), ("BB",), "batting"),
    "so_bat": (("strikeouts",), ("K", "SO"), "batting"),
    "k": (("strikeouts",), ("K", "SO"), "pitching"),
    "h_allowed": (("hits",), ("H",), "pitching"),
    "er": (("earnedRuns",), ("ER",), "pitching"),
    "bb_allowed": (("walks",), ("BB",), "pitching"),
    "outs": (("fullInnings.partInnings", "innings"), ("IP",), "pitching"),
    # hockey
    "g": (("goals",), ("G",), None),
    "a": (("assists",), ("A",), None),
    "sog": (("shotsTotal",), ("S",), None),
    "saves": (("saves",), ("SV",), "goalies"),
    "blocked": (("blockedShots",), ("BS",), None),
    "hits_nhl": (("hits",), ("HT",), None),
}

# stat key: (display name, family, [(component, weight)], aliases)
STATS = {
    # basketball
    "points": ("Points", "basketball", [("pts", 1)], ["points", "pts", "point"]),
    "rebounds": ("Rebounds", "basketball", [("reb", 1)], ["rebounds", "rebs", "reb", "boards"]),
    "assists": ("Assists", "basketball", [("ast", 1)], ["assists", "asts", "ast", "dimes"]),
    "pra": ("Pts+Rebs+Asts", "basketball", [("pts", 1), ("reb", 1), ("ast", 1)],
            ["pra", "pts+rebs+asts", "pts+reb+ast", "points+rebounds+assists", "p+r+a", "pts rebs asts"]),
    "pr": ("Pts+Rebs", "basketball", [("pts", 1), ("reb", 1)], ["pts+rebs", "pts+reb", "points+rebounds", "p+r", "pr"]),
    "pa": ("Pts+Asts", "basketball", [("pts", 1), ("ast", 1)], ["pts+asts", "pts+ast", "points+assists", "p+a", "pa"]),
    "ra": ("Rebs+Asts", "basketball", [("reb", 1), ("ast", 1)], ["rebs+asts", "reb+ast", "rebounds+assists", "r+a", "ra"]),
    "threes": ("3-PT Made", "basketball", [("3pm", 1)],
               ["3-pt made", "3pt made", "3-pointers made", "3 pointers made", "threes made", "threes", "3pm",
                "3-pointers", "three pointers", "3pt", "3-pt"]),
    "steals": ("Steals", "basketball", [("stl", 1)], ["steals", "stl", "stls"]),
    "blocks": ("Blocked Shots", "basketball", [("blk", 1)], ["blocked shots", "blocks", "blk", "blks"]),
    "stocks": ("Blks+Stls", "basketball", [("blk", 1), ("stl", 1)],
               ["blks+stls", "blocks+steals", "steals+blocks", "stls+blks", "stocks"]),
    "turnovers": ("Turnovers", "basketball", [("tov", 1)], ["turnovers", "tov", "tos"]),
    "fgm": ("FG Made", "basketball", [("fgm", 1)], ["fg made", "field goals made", "fgm"]),
    "ftm": ("Free Throws Made", "basketball", [("ftm", 1)], ["free throws made", "ft made", "ftm"]),
    "oreb": ("Offensive Rebounds", "basketball", [("oreb", 1)], ["offensive rebounds", "off rebounds", "oreb"]),
    "dreb": ("Defensive Rebounds", "basketball", [("dreb", 1)], ["defensive rebounds", "def rebounds", "dreb"]),
    "fantasy": ("Fantasy Score", "basketball",
                [("pts", 1), ("reb", 1.2), ("ast", 1.5), ("blk", 3), ("stl", 3), ("tov", -1)],
                ["fantasy score", "fantasy points", "fantasy pts", "fantasy"]),
    # football
    "pass_yds": ("Pass Yards", "football", [("pass_yds", 1)],
                 ["passing yards", "pass yards", "pass yds", "passing yds", "pass yd", "passing yd"]),
    "pass_td": ("Pass TDs", "football", [("pass_td", 1)],
                ["passing touchdowns", "passing tds", "pass tds", "pass td", "passing td"]),
    "pass_cmp": ("Pass Completions", "football", [("pass_cmp", 1)],
                 ["pass completions", "passing completions", "completions"]),
    "pass_att": ("Pass Attempts", "football", [("pass_att", 1)], ["pass attempts", "passing attempts"]),
    "pass_int": ("INTs Thrown", "football", [("pass_int", 1)],
                 ["interceptions thrown", "ints thrown", "int thrown", "pass interceptions"]),
    "rush_yds": ("Rush Yards", "football", [("rush_yds", 1)],
                 ["rushing yards", "rush yards", "rush yds", "rushing yds", "rush yd"]),
    "rush_att": ("Rush Attempts", "football", [("rush_att", 1)], ["rush attempts", "rushing attempts", "carries"]),
    "rush_td": ("Rush TDs", "football", [("rush_td", 1)], ["rushing touchdowns", "rushing tds", "rush tds", "rush td"]),
    "rec": ("Receptions", "football", [("rec", 1)], ["receptions", "catches", "recs"]),
    "rec_yds": ("Receiving Yards", "football", [("rec_yds", 1)],
                ["receiving yards", "rec yards", "rec yds", "receiving yds", "rec yd"]),
    "rec_td": ("Receiving TDs", "football", [("rec_td", 1)], ["receiving touchdowns", "receiving tds", "rec tds"]),
    "targets": ("Targets", "football", [("targets", 1)], ["targets"]),
    "rush_rec_yds": ("Rush+Rec Yds", "football", [("rush_yds", 1), ("rec_yds", 1)],
                     ["rush+rec yds", "rush+rec yards", "rushing+receiving yards", "rush + rec yds", "scrimmage yards"]),
    "pass_rush_yds": ("Pass+Rush Yds", "football", [("pass_yds", 1), ("rush_yds", 1)],
                      ["pass+rush yds", "pass+rush yards", "passing+rushing yards"]),
    "anytime_td": ("Anytime TD", "football", [("rush_td", 1), ("rec_td", 1)],
                   ["anytime touchdown", "anytime td", "anytime touchdown scorer", "td scorer", "to score a td",
                    "scores a touchdown", "rush+rec tds"]),
    "longest_rec": ("Longest Reception", "football", [("long_rec", 1)], ["longest reception", "longest catch"]),
    "longest_rush": ("Longest Rush", "football", [("long_rush", 1)], ["longest rush"]),
    "tackles": ("Tackles+Ast", "football", [("tackles", 1)],
                ["tackles+ast", "tackles + assists", "tackles+assists", "total tackles", "tackles"]),
    "sacks": ("Sacks", "football", [("sacks", 1)], ["sacks"]),
    "fg_made": ("FG Made", "football", [("fg_made", 1)], ["field goals made", "fg made"]),
    "kick_pts": ("Kicking Points", "football", [("kick_pts", 1)], ["kicking points"]),
    # baseball
    "hits": ("Hits", "baseball", [("h", 1)], ["hits"]),
    "runs": ("Runs", "baseball", [("r", 1)], ["runs scored", "runs"]),
    "rbis": ("RBIs", "baseball", [("rbi", 1)], ["rbis", "rbi", "runs batted in"]),
    "hrr": ("Hits+Runs+RBIs", "baseball", [("h", 1), ("r", 1), ("rbi", 1)],
            ["hits+runs+rbis", "hits+runs+rbi", "h+r+rbi", "hrr"]),
    "home_runs": ("Home Runs", "baseball", [("hr", 1)], ["home runs", "homers", "hr"]),
    "walks": ("Walks", "baseball", [("bb", 1)], ["walks", "batter walks"]),
    "hitter_k": ("Hitter Strikeouts", "baseball", [("so_bat", 1)], ["hitter strikeouts", "batter strikeouts"]),
    "pitcher_k": ("Pitcher Strikeouts", "baseball", [("k", 1)],
                  ["pitcher strikeouts", "strikeouts", "ks", "k's", "pitching strikeouts"]),
    "hits_allowed": ("Hits Allowed", "baseball", [("h_allowed", 1)], ["hits allowed"]),
    "earned_runs": ("Earned Runs Allowed", "baseball", [("er", 1)], ["earned runs allowed", "earned runs", "er"]),
    "walks_allowed": ("Walks Allowed", "baseball", [("bb_allowed", 1)], ["walks allowed"]),
    "pitching_outs": ("Pitching Outs", "baseball", [("outs", 1)], ["pitching outs", "outs recorded", "outs"]),
    # hockey
    "goals": ("Goals", "hockey", [("g", 1)], ["goals"]),
    "nhl_assists": ("Assists", "hockey", [("a", 1)], ["assists"]),
    "nhl_points": ("Points", "hockey", [("g", 1), ("a", 1)], ["points"]),
    "sog": ("Shots on Goal", "hockey", [("sog", 1)], ["shots on goal", "sog", "shots"]),
    "saves": ("Goalie Saves", "hockey", [("saves", 1)], ["goalie saves", "saves"]),
    "blocked_shots": ("Blocked Shots", "hockey", [("blocked", 1)], ["blocked shots"]),
    "nhl_hits": ("Hits", "hockey", [("hits_nhl", 1)], ["hits"]),
}
FAMILY_OF_PATH = {p: p.split("/")[0] for p in LEAGUE_SLUGS}
# Nicknames people actually type.
PLAYER_NICKNAMES = {"wemby": "victor wembanyama", "sga": "shai gilgeous-alexander", "bron": "lebron james",
                    "kd": "kevin durant", "ad": "anthony davis", "cmc": "christian mccaffrey", "giannis": "giannis antetokounmpo",
                    "jjj": "jaren jackson jr", "kat": "karl-anthony towns", "joker": "nikola jokic",
                    "luka": "luka doncic", "ant": "anthony edwards", "steph": "stephen curry", "ohtani": "shohei ohtani"}


def norm_name(text: str) -> str:
    t = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    t = re.sub(r"[.'’`]", "", t).replace("-", " ")
    t = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", t)
    return " ".join(t.split())


_ALIAS_INDEX: list[tuple[str, str]] = sorted(
    ((alias, key) for key, (_, _, _, aliases) in STATS.items() for alias in aliases),
    key=lambda x: -len(x[0]))


def _alias_regex(alias: str) -> str:
    parts = [re.escape(x) for x in re.split(r"\s*\+\s*|\s+", alias)]
    return r"(?<![a-z0-9])" + r"\s*(?:\+|and|\s)\s*".join(parts) + r"(?![a-z0-9])"


def stat_keys_in(text: str) -> list[str]:
    """Every stat this text could mean, most specific alias first (e.g. 'points' is NBA and NHL)."""
    t = text.lower()
    for alias, _ in _ALIAS_INDEX:
        if re.search(_alias_regex(alias), t):
            return [k for a, k in _ALIAS_INDEX if a == alias]
    return []


def parse_prop_leg(text: str) -> Optional[dict]:
    """'Victor Wembanyama More 23.5 PRA', 'Josh Allen over 249.5 pass yds', 'Bam 10.5+ points',
    'No - Josh Allen 250+ passing yards', 'Christian McCaffrey anytime TD'. None if it isn't a player prop."""
    raw = (text or "").strip()
    t = raw
    negate = False
    m = re.search(r"\((yes|no)\b[^)]*\)\s*$", t, re.I)
    if m:
        negate = m.group(1).lower() == "no"
    m = re.match(r"^\s*(no|yes)\s*[-–:,]\s*(.+)$", t, re.I)
    if m:
        negate ^= m.group(1).lower() == "no"
        t = m.group(2)
    t = re.sub(r"\s*\([^)]*\)", " ", t)
    t = re.sub(r"\s*\([^)]*$", " ", t)
    if ": " in t and not re.search(r"\d", t.split(": ", 1)[0]):
        t = t.replace(": ", " ", 1)
    keys = stat_keys_in(t)
    if not keys:
        return None
    low = t.lower()
    side, line = None, None
    m = re.search(r"(\d+(?:\.\d+)?)\s*\+", low)                         # "250+" means 250 or more
    if m:
        v = float(m.group(1))
        side, line = "over", (v - 0.5 if v == int(v) else v)
    if line is None:
        m = re.search(r"\b(?:at least|or more)\b", low)
        n = re.search(r"(\d+(?:\.\d+)?)", low)
        if m and n:
            side, line = "over", float(n.group(1)) - 0.5
    if line is None:
        m = re.search(r"\b([ou])\s?(\d+(?:\.\d+)?)\b", low)               # "o23.5" / "u 7.5"
        if m:
            side, line = ("over" if m.group(1) == "o" else "under"), float(m.group(2))
    if line is None:
        n = re.search(r"(?<![a-z])(\d+(?:\.\d+)?)", low)
        s = re.search(r"\b(over|more|higher|under|less|fewer|lower)\b", low)
        if n and s:
            side = "over" if s.group(1) in ("over", "more", "higher") else "under"
            line = float(n.group(1))
    if line is None and keys[0] == "anytime_td":
        side, line = "over", 0.5
    if line is None or side is None:
        return None
    # The player's name is what's left once the numbers, sides and stat words are gone.
    name = re.sub(r"\b[A-Z]{2,4}\b", lambda mm: " " if mm.group(0).lower() in TEAM_ABBRS else mm.group(0), t).lower()
    for alias, _ in _ALIAS_INDEX:
        name = re.sub(_alias_regex(alias), " ", name)
    name = re.sub(r"\b[ou]\s?(?=\d)", " ", name)
    name = re.sub(r"\d+(?:\.\d+)?\s*\+?", " ", name)
    name = re.sub(r"\b(over|more|higher|under|less|fewer|lower|than|at least|or more|to|record|score|scores|"
                  r"a|an|the|player|props?|o|u|vs|at|@|yes|no|will|get)\b", " ", name)
    name = re.sub(r"[^a-z\s'’.\-]", " ", name)
    name = " ".join(name.split()).strip(" -.'’")
    if not name or len(name) < 3:
        return None
    nn = norm_name(name)
    nn = PLAYER_NICKNAMES.get(nn, nn)
    return {"kind": "prop", "player": nn, "display": name.title() if name.islower() else name, "stats": keys,
            "side": side, "line": line, "negate": negate}


TEAM_ABBRS = {"atl", "bos", "bkn", "cha", "chi", "cle", "dal", "den", "det", "gsw", "hou", "ind", "lac", "lal", "mem",
              "mia", "mil", "min", "nop", "nyk", "okc", "orl", "phi", "phx", "por", "sac", "sas", "tor", "uta", "was",
              "kc", "buf", "ne", "nyj", "bal", "cin", "pit", "jax", "ten", "lv", "lar", "sf", "sea", "ari", "tb", "car",
              "no", "gb", "nyg", "wsh", "sd", "nym", "laa", "lad", "stl", "tex", "nya", "chc", "chw", "cws", "oak",
              "col", "edm", "cgy", "van", "wpg", "mtl", "ott", "nsh", "fla", "nj", "nyr", "nyi", "vgk", "uta", "sj"}


# ---- ESPN lookups ----------------------------------------------------------------------

async def espn_search_players(name: str, paths: list[str]) -> list[dict]:
    """[{id, name, norm, path, team, team_abbr}] for players matching this name in these leagues."""
    key = (name, ",".join(sorted(paths)))
    hit = _player_cache.get(key)
    if hit and hit[0] > time.monotonic():
        return hit[1]
    out: list[dict] = []
    try:
        raw = await _get_json(ESPN_SEARCH, {"query": name, "limit": 10, "type": "player"})
    except Exception:
        log.warning("ESPN player search failed for %r", name)
        return []
    slug_to_path = {v: k for k, v in LEAGUE_SLUGS.items()}
    for it in raw.get("items") or []:
        path = slug_to_path.get(it.get("defaultLeagueSlug") or "")
        if path not in paths:
            continue
        team = ((it.get("teamRelationships") or [{}])[0].get("core") or {})
        out.append({"id": str(it.get("id")), "name": it.get("displayName") or "", "norm": norm_name(it.get("displayName")),
                    "path": path, "team": team.get("displayName") or ((it.get("teamRelationships") or [{}])[0]
                                                                     .get("displayName") or ""),
                    "team_abbr": team.get("abbreviation") or ""})
    _player_cache[key] = (time.monotonic() + 6 * 3600, out)
    return out


def name_score(query: str, candidate: str) -> int:
    """3 exact, 2 same last name and first initial, 1 last name only, 0 no match."""
    if query == candidate:
        return 3
    q, c = query.split(), candidate.split()
    if not q or not c:
        return 0
    if len(q) == 1:
        return 1 if q[0] == c[-1] or q[0] in c else 0
    if q[-1] == c[-1] and q[0][0] == c[0][0]:
        return 2
    return 0


async def resolve_player(name: str, paths: list[str]) -> list[dict]:
    found = await espn_search_players(name, paths)
    if not found:
        return []
    best = max(name_score(name, f["norm"]) for f in found)
    return [f for f in found if name_score(name, f["norm"]) == best] if best else []


async def fetch_summary(path: str, event_id: str) -> Optional[dict]:
    key = (path, event_id)
    hit = _summary_cache.get(key)
    if hit and hit[0] > time.monotonic():
        return hit[1]
    try:
        raw = await _get_json(ESPN_SUMMARY.format(path=path), {"event": event_id})
    except Exception:
        log.warning("ESPN summary failed for %s %s", path, event_id)
        return None
    box = parse_boxscore(raw)
    final = box["state"] == "post"
    _summary_cache[key] = (time.monotonic() + (6 * 3600 if final else 60), box)
    return box


def _period_text(status: dict) -> str:
    t = (status.get("type") or {})
    return t.get("shortDetail") or t.get("detail") or t.get("description") or ""


def parse_boxscore(raw: dict) -> dict:
    """{state, detail, season_type, players: [{name, norm, team, dnp, reason, groups: {group: {key: str}}}]}"""
    comp = ((raw.get("header") or {}).get("competitions") or [{}])[0]
    status = comp.get("status") or {}
    state = (status.get("type") or {}).get("state") or "pre"
    season_type = ((raw.get("header") or {}).get("season") or {}).get("type")
    players: dict[str, dict] = {}
    for team_block in (raw.get("boxscore") or {}).get("players") or []:
        abbr = (team_block.get("team") or {}).get("abbreviation") or ""
        for gi, grp in enumerate(team_block.get("statistics") or []):
            gname = (grp.get("name") or grp.get("type") or "main").lower()
            keys = grp.get("keys") or grp.get("names") or []
            labels = grp.get("labels") or grp.get("names") or []
            for a in grp.get("athletes") or []:
                ath = a.get("athlete") or {}
                pid = str(ath.get("id") or ath.get("displayName"))
                rec = players.setdefault(pid, {"id": pid, "name": ath.get("displayName") or "",
                                               "norm": norm_name(ath.get("displayName") or ""), "team": abbr,
                                               "dnp": True, "reason": "", "groups": {}})
                stats = a.get("stats") or []
                if a.get("reason"):
                    rec["reason"] = a["reason"]
                if stats and not a.get("didNotPlay"):
                    rec["dnp"] = False
                vals: dict[str, str] = {}
                for i, v in enumerate(stats):
                    if i < len(keys):
                        vals[str(keys[i]).lower()] = str(v)
                    if i < len(labels):
                        vals.setdefault("#" + str(labels[i]).upper(), str(v))
                rec["groups"][gname] = vals
    return {"state": state, "detail": _period_text(status), "season_type": season_type,
            "players": list(players.values())}


def _num_from(v: str, second: bool = False) -> Optional[float]:
    """'27' -> 27, '3-7' -> 3 (or 7 with second=True), '21/34' -> 21, '6.2' innings -> outs handled elsewhere."""
    if v is None:
        return None
    s = str(v).strip()
    m = re.match(r"^(-?\d+(?:\.\d+)?)\s*[-/]\s*(\d+(?:\.\d+)?)$", s)
    if m:
        return float(m.group(2) if second else m.group(1))
    try:
        return float(s)
    except ValueError:
        return None


def component_value(groups: dict[str, dict], comp: str) -> Optional[float]:
    keys, labels, pref = C[comp]
    if pref and pref not in groups:
        if pref in ("pitching", "batting", "goalies"):
            return None          # not a pitcher / hitter / goalie in this game
        return 0.0               # football: no line in that group means none of that stat (a WR with 0 carries)
    order = [pref] if pref else list(groups)
    for g in order:
        vals = groups[g]
        for k in keys:
            second = k.endswith("#2")
            k2 = (k[:-2] if second else k).lower()
            if k2 in vals:
                return innings_to_outs(vals[k2]) if comp == "outs" else _num_from(vals[k2], second)
        for lab in labels:
            second = lab.endswith("#2")
            l2 = "#" + (lab[:-2] if second else lab)
            if l2 in vals:
                return innings_to_outs(vals[l2]) if comp == "outs" else _num_from(vals[l2], second)
    return None


def innings_to_outs(v: str) -> Optional[float]:
    m = re.match(r"^(\d+)(?:\.(\d))?$", str(v).strip())
    if not m:
        return None
    return int(m.group(1)) * 3 + int(m.group(2) or 0)


def stat_value(groups: dict[str, dict], stat_key: str) -> Optional[tuple[float, str]]:
    """(value, breakdown) or None when the box score doesn't have it."""
    _, _, parts, _ = STATS[stat_key]
    total, shown = 0.0, []
    for comp, w in parts:
        v = component_value(groups, comp)
        if v is None:
            return None
        total += v * w
        shown.append((comp, v))
    total = round(total, 2)
    detail = "" if len(parts) == 1 else " (" + ", ".join(f"{v:g} {COMP_SHORT.get(c, c)}" for c, v in shown) + ")"
    return total, detail


COMP_SHORT = {"pts": "pts", "reb": "reb", "ast": "ast", "stl": "stl", "blk": "blk", "tov": "TO", "rush_yds": "rush",
              "rec_yds": "rec", "pass_yds": "pass", "rush_td": "rush TD", "rec_td": "rec TD", "h": "H", "r": "R",
              "rbi": "RBI", "g": "G", "a": "A"}


def find_in_box(box: dict, name: str) -> Optional[dict]:
    scored = [(name_score(name, pl["norm"]), pl) for pl in box["players"]]
    best = max((sc for sc, _ in scored), default=0)
    if not best:
        return None
    top = {pl["norm"]: pl for sc, pl in scored if sc == best}
    if len(top) > 1:
        return None      # two players fit a vague name equally: don't guess
    return next(iter(top.values()))


def judge_prop(leg: dict, value: float) -> str:
    if value == leg["line"]:
        r = "push"
    else:
        r = "hit" if (value > leg["line"]) == (leg["side"] == "over") else "miss"
    if leg["negate"] and r != "push":
        r = "miss" if r == "hit" else "hit"
    return r


async def prop_game(leg: dict, paths: list[str], logged: datetime) -> Optional[tuple[str, dict, dict]]:
    """(league path, scoreboard event, player) for the game this prop is on, or None."""
    fams = {STATS[k][1] for k in leg["stats"]}
    paths = [p for p in paths if FAMILY_OF_PATH.get(p) in fams]
    if not paths:
        return None
    cands = await resolve_player(leg["player"], paths)
    games = []
    for c in cands:
        found = pick_game(await find_games(c["team"], [c["path"]], logged), logged) if c["team"] else None
        if found:
            games.append((c["path"], found[0], c))
    if len({g[1]["id"] for g in games}) != 1:
        return None   # no game, or the name fits players in different games
    return games[0]


async def prop_status(leg: dict, paths: list[str], logged: datetime) -> Optional[dict]:
    """Live or final status of a player prop:
    {result: hit/miss/push/None, value, line, stat, player, detail, state, why, event, path, preseason}"""
    found = await prop_game(leg, paths, logged)
    if not found:
        return None
    path, ev, cand = found
    fam = FAMILY_OF_PATH[path]
    stat_key = next((k for k in leg["stats"] if STATS[k][1] == fam), None)
    if stat_key is None:
        return None
    out = {"result": None, "value": None, "line": leg["line"], "stat": STATS[stat_key][0], "player": cand["name"],
           "state": ev.get("state", "pre"), "detail": "", "why": "", "event": ev, "path": path,
           "preseason": ev.get("season_type") == 1, "stat_key": stat_key}
    if ev.get("state") == "pre":
        return out
    box = await fetch_summary(path, ev["id"])
    if not box:
        return out
    out["state"], out["detail"] = box["state"], box["detail"]
    if box.get("season_type") == 1:
        out["preseason"] = True
    pl = find_in_box(box, norm_name(cand["name"])) or find_in_box(box, leg["player"])
    if pl is None:
        if box["state"] == "post":
            out["why"] = f"{cand['name']} isn't in the box score"
        return out
    if pl["dnp"]:
        if box["state"] == "post":
            out["result"] = "push"
            out["why"] = f"{pl['name']} didn't play" + (f" ({pl['reason'].lower()})" if pl["reason"] else "")
        return out
    got = stat_value(pl["groups"], stat_key)
    if got is None:
        return out
    value, detail = got
    out["value"] = value
    out["why"] = f"{pl['name']} {value:g} {STATS[stat_key][0]}{detail}"
    if box["state"] == "post":
        out["result"] = judge_prop(leg, value)
    elif (leg["side"] == "over") != leg["negate"] and value > leg["line"]:
        out["result"] = "hit"        # an over that's already cleared can't lose
    elif (leg["side"] == "under") != leg["negate"] and value > leg["line"]:
        out["result"] = "miss"       # an under that's already gone over can't win
    return out


def prop_of(text: str) -> Optional[dict]:
    """The player prop in this leg, if it is one. 'Donovan Mitchell over 13.5 points' also reads as a
    team total, so a team-total shape still counts as a prop (a real team name won't match any player)."""
    prop = parse_prop_leg(text)
    if not prop:
        return None
    simple = parse_simple_leg(text)
    return prop if not simple or simple["kind"] == "team_total" else None


async def grade_props(p, items: list[tuple[int, str]], skip: set[int]) -> dict[int, tuple[str, str]]:
    paths = [x for x in leagues_for(p["sport"]) if x in PROP_PATHS]
    if not paths:
        return {}
    logged = datetime.fromisoformat(p["created_at"])
    out: dict[int, tuple[str, str]] = {}
    for n, text in items:
        if n in skip:
            continue
        leg = prop_of(text)
        if not leg:
            continue
        try:
            st = await prop_status(leg, paths, logged)
        except Exception:
            log.exception("Prop lookup failed for %r", text)
            continue
        if st and st["preseason"] and p["id"] and p["id"] > 0:
            mark_preseason(p["id"])
        if st and st["result"] and st["value"] is not None and st["state"] == "post" and p["id"]:
            _margins[(p["id"], n)] = bettor_margin(leg, st["value"])
        if st and st["result"]:
            out[n] = (st["result"], st["why"] + ("" if st["state"] == "post" else " (already decided, game still on)"))
    return out


def mark_preseason(pick_id: int) -> None:
    db().execute("UPDATE picks SET preseason = 1 WHERE id = ? AND (preseason IS NULL OR preseason = 0)", (pick_id,))
    db().commit()




# ---- live leg progress (shared by /sweat, /schedule and the group parlay) ------------------

BAR_CELLS = 10


def progress_bar(value: float, line: float, side: str) -> str:
    target = line if line > 0 else 1
    filled = max(0, min(BAR_CELLS, int(round(value / target * BAR_CELLS))))
    if side == "under":
        return "▰" * filled + "▱" * (BAR_CELLS - filled) + " (stay under)"
    return "▰" * filled + "▱" * (BAR_CELLS - filled)


def short_game(ev: dict) -> str:
    away = next(t for t in ev["teams"] if not t["home"])
    home = next(t for t in ev["teams"] if t["home"])
    if ev.get("state") in ("in", "post") and away["score"] is not None:
        tail = "final" if ev.get("final") else (ev.get("detail") or "live")
        return f"{away['short']} {away['score']:g}, {home['short']} {home['score']:g} · {tail}"
    when = event_time(ev)
    return f"{away['short']} @ {home['short']} · {when.astimezone(TZ):%a %-I:%M %p}" if when else \
        f"{away['short']} @ {home['short']}"


def simple_live_result(leg: dict, ev: dict, i: Optional[int]) -> Optional[str]:
    """Who's ahead right now on a moneyline/spread/total ('hit' means it's winning at the moment)."""
    if ev.get("state") != "in" or any(t["score"] is None for t in ev["teams"]):
        return None
    try:
        return judge(leg, ev, i)
    except Exception:
        return None


async def leg_progress(p) -> list[dict]:
    """One entry per leg (or the pick itself when it has no legs):
    {n, text, status, line (what to show), event, path, final}"""
    legs = get_legs(p["id"])
    items = [(1, p["description"], p["status"] if p["status"] != "open" else "open")] if not legs else \
        [(leg["idx"], leg["text"], leg["status"]) for leg in legs]
    leagues = leagues_for(p["sport"])
    prop_paths = [x for x in leagues if x in PROP_PATHS]
    logged = datetime.fromisoformat(p["created_at"])
    context_teams = [x["team"] for x in (parse_simple_leg(t) for _, t, _ in items) if x and "team" in x]
    out = []
    for n, text, status in items:
        entry = {"n": n, "text": text, "status": status, "line": "", "event": None, "path": None, "live": None}
        simple = parse_simple_leg(text) if leagues else None
        prop = prop_of(text) if prop_paths else None
        try:
            found = None
            if simple:
                team = simple.get("team") or (context_teams[0] if len(set(context_teams)) == 1 else None)
                found = pick_game(await find_games(team, leagues, logged), logged) if team else None
            if found or (simple and not prop):
                if found:
                    ev, i = found
                    entry["event"] = ev
                    entry["line"] = short_game(ev)
                    now_r = simple_live_result(simple, ev, None if simple["kind"] == "total" else i)
                    entry["live"] = {"hit": "ahead", "miss": "behind"}.get(now_r or "", None)
            elif prop:
                st = await prop_status(prop, prop_paths, logged)
                if st:
                    entry["event"], entry["path"] = st["event"], st["path"]
                    if st["value"] is not None:
                        unit = STATS[st["stat_key"]][0]
                        entry["line"] = (f"{st['value']:g} / {st['line']:g} {unit} "
                                         f"{progress_bar(st['value'], st['line'], prop['side'])}"
                                         + (f" · {st['detail']}" if st["detail"] and st["state"] != "post" else ""))
                    elif st["why"]:
                        entry["line"] = st["why"]
                    else:
                        entry["line"] = short_game(st["event"])
                    if st["result"] and status == "open":
                        entry["live"] = st["result"]
        except Exception:
            log.exception("Progress lookup failed for %r", text)
        out.append(entry)
    return out


def progress_icon(e: dict) -> str:
    if e["status"] != "open":
        return LEG_ICON.get(e["status"], STATUS.get(e["status"], ("⏳",))[0][:1])
    ev = e["event"]
    if e["live"] in ("hit", "ahead"):
        return "🟢"
    if e["live"] in ("miss", "behind"):
        return "🔴"
    if ev and ev.get("state") == "in":
        return "⏱️"
    return "⏳"


# ---- sweats --------------------------------------------------------------------------------

SWEAT_HOURS = 36


def sweat_embed(p, entries: list[dict], ended: bool = False) -> discord.Embed:
    hits = sum(1 for e in entries if e["status"] == "hit" or (e["status"] == "open" and e["live"] == "hit"))
    misses = sum(1 for e in entries if e["status"] == "miss")
    lines = []
    for e in entries:
        lines.append(f"{progress_icon(e)} **{clip(e['text'], 70)}**" + (f"\n　{e['line']}" if e["line"] else ""))
    color = 0xE74C3C if misses else (0x2ECC71 if p["status"] == "win" else BRAND)
    title = f"🥵 Sweat · Pick #{p['id']} · {p['bettor_name']}"
    e = discord.Embed(title=clip(title, 256), color=color,
                      description=clip(f"*{p['description']}*\n\n" + "\n".join(lines), 4000))
    if len(entries) > 1:
        e.add_field(name="Legs", value=f"{hits}/{len(entries)} cashing" + (f" · {misses} dead" if misses else ""))
    e.add_field(name="Riding", value=f"{money(p['cost'])} → {money(p['payout'])}")
    if p["status"] != "open":
        e.add_field(name="Result", value=f"{STATUS[p['status']][0]} ({signed(pick_net(p))})")
    e.set_footer(text=("Done" if ended or p["status"] != "open" else "Live · updates every 2 minutes") +
                 f" · {datetime.now(TZ):%-I:%M %p}  ·  🟢 cleared or winning  🔴 dead or losing  ⏱️ live  ⏳ not started")
    return e


class SweatButton(discord.ui.DynamicItem[discord.ui.Button], template=r"sw:(?P<pid>\d+):(?P<act>ref|stop)"):
    def __init__(self, pick_id: int, act: str):
        label, style = {"ref": ("🔄 Refresh", discord.ButtonStyle.secondary),
                        "stop": ("🛑 Stop", discord.ButtonStyle.secondary)}[act]
        super().__init__(discord.ui.Button(label=label, style=style, custom_id=f"sw:{pick_id}:{act}"))
        self.pick_id, self.act = pick_id, act

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(int(match["pid"]), match["act"])

    async def callback(self, interaction: discord.Interaction):
        p = get_pick(interaction.guild_id, self.pick_id)
        if p is None:
            await interaction.response.send_message("That pick no longer exists.", ephemeral=True)
            return
        if self.act == "stop":
            if not can_edit(interaction, p):
                await interaction.response.send_message("Only the bettor or a mod can stop this sweat.", ephemeral=True)
                return
            db().execute("UPDATE sweats SET ended_at = ? WHERE message_id = ?", (now_iso(), interaction.message.id))
            db().commit()
            await interaction.response.edit_message(view=None)
            return
        await interaction.response.defer()
        entries = await leg_progress(p)
        await interaction.message.edit(embed=sweat_embed(p, entries), view=sweat_view(p["id"]))


def sweat_view(pick_id: int) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    view.add_item(SweatButton(pick_id, "ref"))
    view.add_item(SweatButton(pick_id, "stop"))
    return view


def sweat_state(entries: list[dict]) -> dict:
    return {str(e["n"]): (e["status"] if e["status"] != "open" else
                          (e["live"] if e["live"] in ("hit", "miss") else "open")) for e in entries}


async def start_sweat(channel, p, user_id: int):
    entries = await leg_progress(p)
    msg = await channel.send(embed=sweat_embed(p, entries), view=sweat_view(p["id"]))
    db().execute("""INSERT INTO sweats (guild_id, channel_id, message_id, pick_id, user_id, state, created_at)
                    VALUES (?,?,?,?,?,?,?)""",
                 (p["guild_id"], channel.id, msg.id, p["id"], user_id, json.dumps(sweat_state(entries)), now_iso()))
    db().commit()
    return msg


async def update_sweats(client: discord.Client, now: Optional[datetime] = None) -> None:
    now = now or datetime.now(timezone.utc)
    cutoff = iso(now - timedelta(hours=SWEAT_HOURS))
    for s in db().execute("SELECT * FROM sweats WHERE ended_at IS NULL").fetchall():
        p = get_pick(s["guild_id"], s["pick_id"])
        channel = client.get_channel(s["channel_id"])
        if p is None or channel is None:
            db().execute("UPDATE sweats SET ended_at = ? WHERE id = ?", (now_iso(), s["id"]))
            db().commit()
            continue
        entries = await leg_progress(p)
        state = sweat_state(entries)
        old = json.loads(s["state"] or "{}")
        done = p["status"] != "open" or s["created_at"] < cutoff
        try:
            await channel.get_partial_message(s["message_id"]).edit(
                embed=sweat_embed(p, entries, ended=done), view=None if done else sweat_view(p["id"]))
        except Exception:
            log.warning("Couldn't edit sweat %s", s["id"])
            done = True
        # Shout when a leg clears or dies (only decided legs, never a score that's just swinging).
        total = len(entries)
        cleared = sum(1 for v in state.values() if v == "hit")
        for e in entries:
            before, after = old.get(str(e["n"])), state[str(e["n"])]
            if before == after or total < 2:
                continue
            if after == "hit":
                left = sum(1 for v in state.values() if v == "open")
                text = (f"✅ **{p['bettor_name']}**: {clip(e['text'], 80)} cleared (pick #{p['id']})"
                        + (f" · {left} to go" if left else " · 🎉 that's all of them!"))
            elif after == "miss":
                text = f"❌ **{p['bettor_name']}**: {clip(e['text'], 80)} is dead (pick #{p['id']})"
            else:
                continue
            try:
                await channel.send(text, allowed_mentions=discord.AllowedMentions.none())
            except Exception:
                pass
        db().execute("UPDATE sweats SET state = ?, ended_at = ? WHERE id = ?",
                     (json.dumps(state), now_iso() if done else None, s["id"]))
        db().commit()


# ---- trends (player game logs) ------------------------------------------------------------

_gamelog_cache: dict[tuple, tuple[float, list]] = {}
TREND_WINDOWS = {"5": 5, "10": 10, "20": 20, "all": 82}


async def fetch_gamelog(path: str, athlete_id: str, season: Optional[str] = None) -> tuple[list[dict], list[str]]:
    """Games newest first: [{id, date, opp, at, result, label, preseason, groups}], plus older seasons on offer."""
    key = (path, athlete_id, season)
    hit = _gamelog_cache.get(key)
    if hit and hit[0] > time.monotonic():
        return hit[1]
    params = {"season": season} if season else {}
    raw = await _get_json(ESPN_GAMELOG.format(path=path, athlete_id=athlete_id), params)
    names = [str(x).lower() for x in raw.get("names") or []]
    labels = [str(x).upper() for x in raw.get("labels") or []]
    meta = raw.get("events") or {}
    games = []
    for st in raw.get("seasonTypes") or []:
        label = st.get("displayName") or ""
        pre = "preseason" in label.lower()
        for cat in st.get("categories") or []:
            for ev in cat.get("events") or []:
                eid = str(ev.get("eventId") or "")
                stats = ev.get("stats") or []
                if not eid or not stats:
                    continue
                flat: dict[str, str] = {}
                for i, v in enumerate(stats):
                    if i < len(names):
                        flat.setdefault(names[i], str(v))
                    if i < len(labels):
                        flat.setdefault("#" + labels[i], str(v))
                m = meta.get(eid) or {}
                groups = {g: flat for g in ("main", "passing", "rushing", "receiving", "defensive", "kicking",
                                            "interceptions", "batting", "pitching", "goalies")}
                games.append({"id": eid, "date": m.get("gameDate") or "", "opp": (m.get("opponent") or {}).get(
                    "abbreviation") or "?", "opp_name": (m.get("opponent") or {}).get("displayName") or "", "at": m.get("atVs") or "vs", "result": m.get("gameResult") or "",
                    "label": label, "preseason": pre, "groups": groups})
    games.sort(key=lambda g: g["date"], reverse=True)
    seasons = []
    for f in raw.get("filters") or []:
        if f.get("name") == "season":
            seasons = [str(o.get("value")) for o in f.get("options") or [] if o.get("value")]
    _gamelog_cache[key] = (time.monotonic() + 1800, (games, seasons))
    return games, seasons


async def trend_games(path: str, athlete_id: str, need: int = 20) -> list[dict]:
    games, seasons = await fetch_gamelog(path, athlete_id)
    games = [g for g in games if not g["preseason"]]
    if len(games) < need and len(seasons) > 1:
        try:
            current = seasons[0]
            older = [s for s in seasons if s < current] or seasons[1:]
            more, _ = await fetch_gamelog(path, athlete_id, older[0])
            seen = {g["id"] for g in games}
            games += [g for g in more if not g["preseason"] and g["id"] not in seen]
        except Exception:
            log.warning("Older game log failed for %s", athlete_id)
    return games


def trend_values(games: list[dict], stat_key: str) -> list[tuple[dict, float]]:
    out = []
    for g in games:
        got = stat_value(g["groups"], stat_key)
        if got is not None:
            out.append((g, got[0]))
    return out


def hit_counts(values: list[float], line: float) -> tuple[int, int, int]:
    over = sum(1 for v in values if v > line)
    under = sum(1 for v in values if v < line)
    return over, under, len(values) - over - under


def render_trend(name: str, stat: str, line: float, rows: list[tuple[dict, float]]) -> io.BytesIO:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rows = list(reversed(rows))  # oldest on the left
    fig, ax = plt.subplots(figsize=(10, 4.6), dpi=110)
    fig.patch.set_facecolor(CHART_SURFACE)
    ax.set_facecolor(CHART_SURFACE)
    vals = [v for _, v in rows]
    colors = ["#3fb97a" if v > line else "#e66767" if v < line else CHART_MUTED for v in vals]
    xs = list(range(len(vals)))
    ax.bar(xs, vals, color=colors, width=0.68, zorder=2)
    ax.axhline(line, color=CHART_TEXT, linestyle=(0, (4, 3)), linewidth=1.4, zorder=3)
    for x, v in zip(xs, vals):
        ax.text(x, v, f"{v:g}", color=CHART_TEXT, ha="center", va="bottom", fontsize=8, zorder=4,
                bbox=dict(boxstyle="round,pad=0.15", facecolor=CHART_SURFACE, edgecolor="none", alpha=0.8))
    labels = [f"{(datetime.fromisoformat(g['date'].replace('Z', '+00:00')).astimezone(TZ).strftime('%-m/%-d') if g['date'] else '')}"
              f"\n{'@' if g['at'] == '@' else 'v'}{g['opp']}" for g, _ in rows]
    ax.set_xticks(xs)
    ax.set_xticklabels(labels, fontsize=7.5 if len(xs) > 12 else 9, color=CHART_MUTED)
    ax.tick_params(axis="y", colors=CHART_MUTED, labelsize=9)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(CHART_GRID)
    ax.grid(axis="y", color=CHART_GRID, linewidth=0.6, zorder=0)
    over, under, push = hit_counts(vals, line)
    ax.set_title(f"{name} · {stat} · line {line:g} (dashed) · last {len(vals)}: over {over}, under {under}"
                 + (f", push {push}" if push else ""),
                 color=CHART_TEXT, fontsize=12, loc="left", pad=12)
    fig.tight_layout()
    out = io.BytesIO()
    fig.savefig(out, format="png", facecolor=CHART_SURFACE)
    plt.close(fig)
    out.seek(0)
    return out


def trend_embed(name: str, team: str, stat_key: str, line: float, values: list[tuple[dict, float]],
                window: str) -> discord.Embed:
    n = TREND_WINDOWS[window]
    use = values[:n]
    vals = [v for _, v in use]
    label = STATS[stat_key][0]
    e = discord.Embed(title=clip(f"📈 {name} · {label} · line {line:g}", 256), color=BRAND)
    if not vals:
        e.description = "No games with that stat yet."
        return e
    rows = []
    for k in (5, 10, 20):
        part = [v for _, v in values[:k]]
        if len(part) == k:
            o, u, _ = hit_counts(part, line)
            rows.append(f"**L{len(part)}** · over {o}/{len(part)} ({o / len(part) * 100:.0f}%) · avg {sum(part) / len(part):.1f}")
    allv = [v for _, v in values]
    o, u, _ = hit_counts(allv, line)
    rows.append(f"**All {len(allv)}** · over {o}/{len(allv)} ({o / len(allv) * 100:.0f}%) · avg {sum(allv) / len(allv):.1f}")
    srt = sorted(vals)
    median = srt[len(srt) // 2] if len(srt) % 2 else (srt[len(srt) // 2 - 1] + srt[len(srt) // 2]) / 2
    e.description = (f"{team}\n" if team else "") + "\n".join(rows) + \
        f"\nMedian (last {len(vals)}): **{median:g}** · high {max(vals):g} · low {min(vals):g}"
    recent = []
    for g, v in use[:10]:
        mark = "✅" if v > line else "❌" if v < line else "➖"
        when = datetime.fromisoformat(g["date"].replace("Z", "+00:00")).astimezone(TZ).strftime("%b %-d") if g["date"] else ""
        recent.append(f"{mark} {when} {'@' if g['at'] == '@' else 'vs'} {g['opp']} · **{v:g}**")
    e.add_field(name="Game by game (over)", value=clip("\n".join(recent), 1024), inline=False)
    e.set_footer(text="Free ESPN game logs · preseason left out · past results, not a prediction")
    return e


def stat_choices_for(family: str) -> list[str]:
    return [k for k, v in STATS.items() if v[1] == family]


class TrendView(discord.ui.View):
    def __init__(self, owner_id: int, player: dict, games: list[dict], stat_key: str, line: float, window: str):
        super().__init__(timeout=900)
        self.owner_id, self.player, self.games = owner_id, player, games
        self.stat_key, self.line, self.window = stat_key, line, window
        for w, label in (("5", "L5"), ("10", "L10"), ("20", "L20"), ("all", "All")):
            b = discord.ui.Button(label=label, row=0, style=discord.ButtonStyle.primary if w == window
                                  else discord.ButtonStyle.secondary)
            b.callback = self._window_cb(w)
            self.add_item(b)
        fam = FAMILY_OF_PATH[player["path"]]
        opts = [discord.SelectOption(label=STATS[k][0], value=k, default=(k == stat_key))
                for k in stat_choices_for(fam)][:25]
        sel = discord.ui.Select(placeholder="Switch stat", options=opts, row=1)
        sel.callback = self._stat_cb(sel)
        self.add_item(sel)
        for delta, label in ((-1.0, "Line − 1"), (-0.5, "− 0.5"), (0.5, "+ 0.5"), (1.0, "Line + 1")):
            b = discord.ui.Button(label=label, row=2, style=discord.ButtonStyle.secondary)
            b.callback = self._line_cb(delta)
            self.add_item(b)

    async def _check(self, interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Run `/trend` yourself to play with this one.", ephemeral=True)
            return False
        return True

    async def redraw(self, interaction):
        values = trend_values(self.games, self.stat_key)
        n = TREND_WINDOWS[self.window]
        e = trend_embed(self.player["name"], self.player["team"], self.stat_key, self.line, values, self.window)
        view = TrendView(self.owner_id, self.player, self.games, self.stat_key, self.line, self.window)
        files = []
        if values[:n]:
            png = await asyncio.to_thread(render_trend, self.player["name"], STATS[self.stat_key][0], self.line, values[:n])
            files = [discord.File(png, filename="trend.png")]
            e.set_image(url="attachment://trend.png")
        await interaction.response.edit_message(embed=e, view=view, attachments=files)

    def _window_cb(self, w):
        async def cb(interaction):
            if await self._check(interaction):
                self.window = w
                await self.redraw(interaction)
        return cb

    def _line_cb(self, delta):
        async def cb(interaction):
            if await self._check(interaction):
                self.line = max(0.0, self.line + delta)
                await self.redraw(interaction)
        return cb

    def _stat_cb(self, sel):
        async def cb(interaction):
            if await self._check(interaction):
                self.stat_key = sel.values[0]
                vals = [v for _, v in trend_values(self.games, self.stat_key)[:10]]
                self.line = default_line(vals)
                await self.redraw(interaction)
        return cb


def default_line(vals: list[float]) -> float:
    if not vals:
        return 0.5
    avg = sum(vals) / len(vals)
    return max(0.5, int(avg) + 0.5)


# ---- injury alerts ------------------------------------------------------------------------

INJURY_STATUSES = ("out", "doubtful", "questionable", "day-to-day", "suspension")
_injury_cache: dict[str, tuple[float, dict]] = {}


async def fetch_injuries(path: str) -> dict[str, dict]:
    """{normalized player name: {name, status, comment, team}}"""
    hit = _injury_cache.get(path)
    if hit and hit[0] > time.monotonic():
        return hit[1]
    out: dict[str, dict] = {}
    try:
        raw = await _get_json(ESPN_INJURIES.format(path=path), {})
    except Exception:
        log.warning("Injury report failed for %s", path)
        return out
    for team in raw.get("injuries") or []:
        for inj in team.get("injuries") or []:
            ath = inj.get("athlete") or {}
            status = inj.get("status")
            if isinstance(status, dict):
                status = status.get("name") or status.get("type")
            name = ath.get("displayName") or ""
            if name and status:
                out[norm_name(name)] = {"name": name, "status": str(status), "team": team.get("displayName") or "",
                                        "comment": inj.get("shortComment") or ""}
    _injury_cache[path] = (time.monotonic() + 900, out)
    return out


class InjuryOffButton(discord.ui.DynamicItem[discord.ui.Button], template=r"inj:(?P<gid>\d+):(?P<act>off|on)"):
    def __init__(self, guild_id: int, act: str = "off"):
        super().__init__(discord.ui.Button(label="🔕 Stop injury alerts" if act == "off" else "🔔 Turn them back on",
                                           style=discord.ButtonStyle.secondary, custom_id=f"inj:{guild_id}:{act}"))
        self.guild_id, self.act = guild_id, act

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(int(match["gid"]), match["act"])

    async def callback(self, interaction: discord.Interaction):
        set_setting(self.guild_id, f"injuryalerts:{interaction.user.id}", "off" if self.act == "off" else None)
        view = discord.ui.View(timeout=None)
        view.add_item(InjuryOffButton(self.guild_id, "on" if self.act == "off" else "off"))
        await interaction.response.edit_message(view=view)
        await interaction.followup.send("Injury alerts are off. Tap the button again to turn them back on."
                                        if self.act == "off" else "Injury alerts are back on.", ephemeral=True)


async def run_injury_alerts(client: discord.Client, now: Optional[datetime] = None) -> None:
    now = now or datetime.now(timezone.utc)
    recent = iso(now - timedelta(days=4))
    picks = db().execute("SELECT * FROM picks WHERE status = 'open' AND created_at >= ? AND bettor_id IS NOT NULL",
                         (recent,)).fetchall()
    for p in picks:
        if get_setting(p["guild_id"], f"injuryalerts:{p['bettor_id']}") == "off":
            continue
        paths = [x for x in leagues_for(p["sport"]) if x in PROP_PATHS]
        if not paths:
            continue
        items, _ = open_items(p)
        for n, text in items:
            leg = prop_of(text)
            if not leg:
                continue
            fams = {STATS[k][1] for k in leg["stats"]}
            for path in paths:
                if FAMILY_OF_PATH[path] not in fams:
                    continue
                report = await fetch_injuries(path)
                scored = [(name_score(leg["player"], k), v) for k, v in report.items()]
                best = max((s for s, _ in scored), default=0)
                matches = [v for s, v in scored if s == best and s >= 2]
                if len(matches) != 1:
                    continue
                inj = matches[0]
                status = inj["status"].lower()
                if not any(status.startswith(s) for s in INJURY_STATUSES):
                    continue
                if db().execute("SELECT 1 FROM injury_alerts WHERE pick_id = ? AND player = ? AND status = ?",
                                (p["id"], inj["name"], inj["status"])).fetchone():
                    continue
                db().execute("INSERT INTO injury_alerts (pick_id, player, status, sent_at) VALUES (?,?,?,?)",
                             (p["id"], inj["name"], inj["status"], now_iso()))
                db().commit()
                pp = p["platform"].lower() == "prizepicks"
                text_out = (f"🚑 **{inj['name']}** is listed **{inj['status']}**."
                            + (f"\n> {clip(inj['comment'], 200)}" if inj["comment"] else "")
                            + f"\nHe's on your pick `#{p['id']}`: {clip(p['description'], 80)} → leg: {clip(text, 80)}"
                            + ("\nIf he doesn't play, PrizePicks drops the leg and pays the smaller slip." if pp else ""))
                view = discord.ui.View(timeout=None)
                view.add_item(InjuryOffButton(p["guild_id"], "off"))
                try:
                    user = await client.fetch_user(p["bettor_id"])
                    await user.send(text_out, view=view)
                except Exception:
                    channel = await recap_channel_for(client, p["guild_id"])
                    if channel is not None:
                        await channel.send(f"<@{p['bettor_id']}> " + text_out, allowed_mentions=discord.AllowedMentions(
                            everyone=False, roles=False, users=True))


# ---- Kalshi settlement ----------------------------------------------------------------------

KALSHI_API = "https://api.elections.kalshi.com/trade-api/v2"
KALSHI_DONE = ("settled", "finalized", "determined")
_kalshi_cache: dict[str, tuple[float, Optional[dict]]] = {}


async def kalshi_market(ticker: str, fresh: bool = False) -> Optional[dict]:
    ticker = ticker.upper()
    hit = _kalshi_cache.get(ticker)
    if hit and hit[0] > time.monotonic() and not fresh:
        return hit[1]
    try:
        raw = await _get_json(f"{KALSHI_API}/markets/{ticker}", {})
        m = raw.get("market") or None
    except Exception:
        m = None
    _kalshi_cache[ticker] = (time.monotonic() + 120, m)
    return m


async def kalshi_event_markets(ticker: str) -> list[dict]:
    try:
        raw = await _get_json(f"{KALSHI_API}/events/{ticker.upper()}", {"with_nested_markets": "true"})
    except Exception:
        return []
    ev = raw.get("event") or {}
    return list(raw.get("markets") or ev.get("markets") or [])


def kalshi_refs(text: str) -> list[str]:
    """Possible tickers in a Kalshi link or a pasted ticker, most specific first."""
    t = (text or "").strip()
    parts = [x for x in re.split(r"[/?#&=\s]+", t) if x]
    refs = [x.upper() for x in reversed(parts) if re.match(r"^kx[a-z0-9.\-]+$", x, re.I)]
    if not refs and re.match(r"^[A-Za-z0-9.\-]{4,}$", t):
        refs = [t.upper()]
    return refs


async def kalshi_resolve(text: str) -> tuple[Optional[dict], list[dict]]:
    """(market, []) when the link names one market, or (None, markets) for an event."""
    for ref in kalshi_refs(text):
        m = await kalshi_market(ref)
        if m:
            return m, []
        ms = await kalshi_event_markets(ref)
        if ms:
            return (ms[0], []) if len(ms) == 1 else (None, ms)
    return None, []


def kalshi_label(m: dict) -> str:
    return m.get("yes_sub_title") or m.get("title") or m.get("ticker") or "?"


def kalshi_legs(m: dict) -> list[dict]:
    legs = []
    for x in m.get("mve_selected_legs") or []:
        if isinstance(x, dict) and x.get("market_ticker"):
            legs.append({"ticker": x["market_ticker"], "side": str(x.get("side") or "yes").lower()})
    return legs


def kalshi_outcome(m: dict) -> Optional[str]:
    """'yes', 'no', 'void', or None while it's still running."""
    if (m.get("status") or "").lower() not in KALSHI_DONE:
        return None
    r = (m.get("result") or "").lower()
    if r in ("yes", "no"):
        return r
    return "void" if r in ("void", "", "scalar") else None


async def kalshi_embed(p, m: dict) -> discord.Embed:
    side = (p["kalshi_side"] or "yes").upper()
    out = kalshi_outcome(m)
    status = {"yes": "Resolved YES", "no": "Resolved NO", "void": "Voided"}.get(out or "", (m.get("status") or "open").title())
    e = discord.Embed(title=clip(f"🟣 Kalshi · Pick #{p['id']} · {p['bettor_name']}", 256), color=BRAND,
                      description=clip(f"**{kalshi_label(m)}**\nYour side: **{side}** · Market: {status}", 4000))
    lines = []
    for leg in kalshi_legs(m)[:20]:
        lm = await kalshi_market(leg["ticker"])
        lo = kalshi_outcome(lm) if lm else None
        icon = "⏳" if lo is None else ("➖" if lo == "void" else ("✅" if lo == leg["side"] else "❌"))
        lines.append(f"{icon} {clip(kalshi_label(lm) if lm else leg['ticker'], 90)} ({leg['side'].upper()})")
    if lines:
        e.add_field(name="Legs", value=clip("\n".join(lines), 1024), inline=False)
    e.set_footer(text=f"{m.get('ticker')} · settles itself here when Kalshi does")
    return e


def link_kalshi(pick_id: int, ticker: str, side: str) -> None:
    db().execute("UPDATE picks SET kalshi_ticker = ?, kalshi_side = ?, kalshi_checked_at = NULL WHERE id = ?",
                 (ticker.upper(), side.lower(), pick_id))
    db().commit()


class KalshiSideView(discord.ui.View):
    def __init__(self, owner_id: int, pick_id: int, market: dict):
        super().__init__(timeout=600)
        self.owner_id, self.pick_id, self.market = owner_id, pick_id, market
        for side, style in (("yes", discord.ButtonStyle.success), ("no", discord.ButtonStyle.danger)):
            b = discord.ui.Button(label=f"I bet {side.upper()}", style=style)
            b.callback = self._cb(side)
            self.add_item(b)

    def _cb(self, side):
        async def cb(interaction):
            if interaction.user.id != self.owner_id:
                await interaction.response.send_message("This isn't your link to finish.", ephemeral=True)
                return
            link_kalshi(self.pick_id, self.market["ticker"], side)
            p = get_pick(interaction.guild_id, self.pick_id)
            await interaction.response.edit_message(content="🔗 Linked. I'll settle it the moment Kalshi does.",
                                                    embed=await kalshi_embed(p, self.market), view=None)
        return cb


class KalshiMarketSelect(discord.ui.View):
    def __init__(self, owner_id: int, pick_id: int, markets: list[dict]):
        super().__init__(timeout=600)
        self.owner_id, self.pick_id = owner_id, pick_id
        self.by_ticker = {m["ticker"]: m for m in markets[:25]}
        sel = discord.ui.Select(placeholder="Which market?", options=[
            discord.SelectOption(label=clip(kalshi_label(m), 100), value=m["ticker"],
                                 description=clip(m.get("title") or "", 100) or None) for m in markets[:25]])
        sel.callback = self._cb(sel)
        self.add_item(sel)

    def _cb(self, sel):
        async def cb(interaction):
            if interaction.user.id != self.owner_id:
                await interaction.response.send_message("This isn't your link to finish.", ephemeral=True)
                return
            m = self.by_ticker[sel.values[0]]
            await interaction.response.edit_message(content=f"**{clip(kalshi_label(m), 200)}**: which side did you take?",
                                                    view=KalshiSideView(self.owner_id, self.pick_id, m))
        return cb


async def kalshi_link_flow(interaction: discord.Interaction, p, ref: str, side: Optional[str], followup: bool):
    send = interaction.followup.send if followup else interaction.response.send_message
    market, options = await kalshi_resolve(ref)
    if market is None and not options:
        await send("I couldn't find that on Kalshi. Paste the market's link from the Kalshi site or app, "
                   "or its ticker (it starts with KX).", ephemeral=True)
        return
    if market is None:
        await send("That event has several markets. Pick yours:", view=KalshiMarketSelect(interaction.user.id, p["id"], options),
                   ephemeral=True)
        return
    if side:
        link_kalshi(p["id"], market["ticker"], side)
        await send("🔗 Linked. I'll settle it the moment Kalshi does.", embed=await kalshi_embed(get_pick(p["guild_id"], p["id"]), market),
                   ephemeral=True)
        return
    await send(f"**{clip(kalshi_label(market), 200)}**: which side did you take?",
               view=KalshiSideView(interaction.user.id, p["id"], market), ephemeral=True)


class KalshiLinkModal(discord.ui.Modal, title="Link a Kalshi market"):
    ref = discord.ui.TextInput(label="Kalshi link or ticker", placeholder="https://kalshi.com/markets/... or KX...",
                               max_length=300)
    side = discord.ui.TextInput(label="Your side (yes or no)", placeholder="yes", required=False, max_length=3)

    def __init__(self, pick_id: int):
        super().__init__()
        self.pick_id = pick_id

    async def on_submit(self, interaction: discord.Interaction):
        p = get_pick(interaction.guild_id, self.pick_id)
        side = (self.side.value or "").strip().lower()
        await interaction.response.defer(ephemeral=True)
        await kalshi_link_flow(interaction, p, self.ref.value, side if side in ("yes", "no") else None, followup=True)


async def grade_kalshi(client: discord.Client, now: Optional[datetime] = None) -> None:
    now = now or datetime.now(timezone.utc)
    recheck = iso(now - timedelta(minutes=10))
    rows = db().execute("""SELECT * FROM picks WHERE status = 'open' AND kalshi_ticker IS NOT NULL
                           AND (kalshi_checked_at IS NULL OR kalshi_checked_at <= ?) LIMIT 40""", (recheck,)).fetchall()
    for p in rows:
        db().execute("UPDATE picks SET kalshi_checked_at = ? WHERE id = ?", (iso(now), p["id"]))
        db().commit()
        m = await kalshi_market(p["kalshi_ticker"], fresh=True)
        if not m:
            continue
        legs = get_legs(p["id"])
        klegs = kalshi_legs(m)
        if legs and len(klegs) == len(legs):          # grade combo legs as they land
            for leg, kl in zip(legs, klegs):
                if leg["status"] != "open":
                    continue
                lm = await kalshi_market(kl["ticker"], fresh=True)
                lo = kalshi_outcome(lm) if lm else None
                if lo:
                    db().execute("UPDATE legs SET status = ? WHERE pick_id = ? AND idx = ?",
                                 ("push" if lo == "void" else ("hit" if lo == kl["side"] else "miss"), p["id"], leg["idx"]))
            db().commit()
        out = kalshi_outcome(m)
        if out is None:
            continue
        side = (p["kalshi_side"] or "yes").lower()
        status = "push" if out == "void" else ("win" if out == side else "loss")
        after = settle_pick(p["guild_id"], p["id"], status)
        channel = await recap_channel_for(client, p["guild_id"])
        if channel is not None:
            mention = f"<@{p['bettor_id']}> " if p["bettor_id"] else ""
            await channel.send(
                f"{mention}🟣 Kalshi settled pick `#{p['id']}` ({p['bettor_name']}): {clip(kalshi_label(m), 150)} → "
                f"**{out.upper()}**. Result: **{STATUS[status][0]}** ({signed(pick_net(after))}).",
                allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=True))


# ---- group parlay ---------------------------------------------------------------------------

GP_ROASTS = [
    "💀 {name} had ONE job.", "💀 Thanks for nothing, {name}.", "💀 {name}'s leg just sank the whole ship.",
    "💀 Somebody check on {name}. Actually, don't.", "💀 {name} owes the group an apology.",
    "💀 {name} fumbled the group parlay. Again.", "💀 And {name} picked THAT? Bold. Wrong, but bold.",
]


def gp_round(guild_id: int, create: bool = True, week: Optional[str] = None):
    week = week or week_id()
    r = db().execute("SELECT * FROM gp_rounds WHERE guild_id = ? AND week = ?", (guild_id, week)).fetchone()
    if r is None and create:
        db().execute("INSERT INTO gp_rounds (guild_id, week, created_at) VALUES (?,?,?)", (guild_id, week, now_iso()))
        db().commit()
        r = db().execute("SELECT * FROM gp_rounds WHERE guild_id = ? AND week = ?", (guild_id, week)).fetchone()
    return r


def gp_legs(round_id: int) -> list:
    return db().execute("SELECT * FROM gp_legs WHERE round_id = ? ORDER BY created_at", (round_id,)).fetchall()


def gp_state(legs) -> str:
    if not legs:
        return "empty"
    st = [x["status"] for x in legs]
    if "miss" in st:
        return "busted"
    if "open" in st:
        return "live"
    return "hit" if len(legs) >= 2 else "live"


def gp_embed(r) -> discord.Embed:
    legs = gp_legs(r["id"])
    state = gp_state(legs)
    start = week_start(datetime.fromisoformat(r["created_at"])).astimezone(TZ)
    color = {"busted": 0xE74C3C, "hit": 0x2ECC71}.get(state, BRAND)
    lines = []
    for x in legs:
        lines.append(f"{LEG_ICON[x['status']]} **{x['user_name']}**: {clip(x['text'], 80)}"
                     + (f" · {x['sport']}" if x["sport"] else "") + (f"\n　{clip(x['why'], 90)}" if x["why"] else ""))
    head = {"empty": "Nobody's in yet. Tap **Add my leg**.", "live": "Still alive. 🤞",
            "busted": "💀 Busted.", "hit": "🎉 **IT HIT!** Everybody eats."}[state]
    mult = 1.9091 ** len(legs) if legs else 0
    e = discord.Embed(title=f"🤝 Group Parlay · week of {start:%b %-d}", color=color,
                      description=head + ("\n\n" + "\n".join(lines) if lines else ""))
    if legs:
        e.add_field(name="Legs", value=f"{sum(1 for x in legs if x['status'] == 'hit')}/{len(legs)} hit")
        e.add_field(name="If it hits", value=f"about {mult:,.1f}x at -110 a leg")
    killer = next((x for x in legs if x["status"] == "miss"), None)
    if killer:
        e.add_field(name="Busted by", value=killer["user_name"])
    hist = db().execute("""SELECT r.id FROM gp_rounds r WHERE r.guild_id = ?""", (r["guild_id"],)).fetchall()
    hits = busts = 0
    killers: dict[str, int] = {}
    for h in hist:
        hl = gp_legs(h["id"])
        s = gp_state(hl)
        hits += s == "hit"
        busts += s == "busted"
        for x in hl:
            if x["status"] == "miss":
                killers[x["user_name"]] = killers.get(x["user_name"], 0) + 1
    worst = max(killers.items(), key=lambda kv: kv[1]) if killers else None
    e.set_footer(text=f"All-time: {hits} hit, {busts} busted" + (f" · most busts: {worst[0]} ({worst[1]})" if worst else "")
                 + " · one leg each, change it until your game starts")
    return e


class GPButton(discord.ui.DynamicItem[discord.ui.Button], template=r"gp:(?P<rid>\d+):(?P<act>add|drop|ref|grade)"):
    LOOK = {"add": ("➕ Add / change my leg", discord.ButtonStyle.success), "drop": ("🗑️ Pull my leg", discord.ButtonStyle.secondary),
            "ref": ("🔄", discord.ButtonStyle.secondary), "grade": ("🛠️ Grade (mods)", discord.ButtonStyle.secondary)}

    def __init__(self, round_id: int, act: str):
        label, style = self.LOOK[act]
        super().__init__(discord.ui.Button(label=label, style=style, custom_id=f"gp:{round_id}:{act}"))
        self.round_id, self.act = round_id, act

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(int(match["rid"]), match["act"])

    async def callback(self, interaction: discord.Interaction):
        r = db().execute("SELECT * FROM gp_rounds WHERE id = ?", (self.round_id,)).fetchone()
        if r is None:
            await interaction.response.send_message("That round is gone.", ephemeral=True)
            return
        mine = db().execute("SELECT * FROM gp_legs WHERE round_id = ? AND user_id = ?",
                            (r["id"], interaction.user.id)).fetchone()
        if self.act in ("add", "drop") and r["week"] != week_id():
            await interaction.response.send_message("That week's done. `/groupparlay` opens this week's.", ephemeral=True)
            return
        if self.act == "add":
            if mine and (mine["status"] != "open" or await gp_leg_started(mine)):
                await interaction.response.send_message("Your leg's game already started, so it's locked in.", ephemeral=True)
                return
            await interaction.response.send_modal(GPLegModal(r["id"], mine))
        elif self.act == "drop":
            if not mine:
                await interaction.response.send_message("You don't have a leg in this one.", ephemeral=True)
                return
            if mine["status"] != "open" or await gp_leg_started(mine):
                await interaction.response.send_message("Too late, your game started. You're riding it.", ephemeral=True)
                return
            db().execute("DELETE FROM gp_legs WHERE id = ?", (mine["id"],))
            db().commit()
            await interaction.response.edit_message(embed=gp_embed(r), view=gp_view(r["id"]))
        elif self.act == "ref":
            await interaction.response.edit_message(embed=gp_embed(r), view=gp_view(r["id"]))
        else:
            if not is_mod(interaction.user):
                await interaction.response.send_message("Only mods can grade legs by hand.", ephemeral=True)
                return
            open_legs = [x for x in gp_legs(r["id"])]
            if not open_legs:
                await interaction.response.send_message("No legs yet.", ephemeral=True)
                return
            await interaction.response.send_message("Which leg?", view=GPGradeView(r["id"], open_legs, interaction.message),
                                                    ephemeral=True)


def gp_view(round_id: int) -> discord.ui.View:
    v = discord.ui.View(timeout=None)
    for act in ("add", "drop", "ref", "grade"):
        v.add_item(GPButton(round_id, act))
    return v


async def gp_leg_started(leg) -> bool:
    like = {"id": 0, "created_at": leg["updated_at"] or leg["created_at"], "sport": leg["sport"],
            "description": leg["text"], "status": "open"}
    try:
        simple = parse_simple_leg(leg["text"])
        leagues = leagues_for(leg["sport"])
        logged = datetime.fromisoformat(like["created_at"])
        if simple and simple.get("team") and leagues:
            found = pick_game(await find_games(simple["team"], leagues, logged), logged)
            return bool(found and found[0].get("state") != "pre")
        prop = prop_of(leg["text"])
        if prop:
            g = await prop_game(prop, [x for x in leagues if x in PROP_PATHS], logged)
            return bool(g and g[1].get("state") != "pre")
    except Exception:
        return False
    return False


class GPLegModal(discord.ui.Modal, title="Your leg for the group parlay"):
    leg = discord.ui.TextInput(label="Your leg", max_length=150,
                               placeholder="Chiefs ML · Over 44.5 (Bills vs Dolphins) · Wembanyama over 23.5 PRA")
    sport = discord.ui.TextInput(label="Sport", placeholder="NFL, NBA, CS2...", required=False, max_length=30)

    def __init__(self, round_id: int, existing=None):
        super().__init__()
        self.round_id = round_id
        if existing:
            self.leg.default = existing["text"]
            self.sport.default = existing["sport"] or ""

    async def on_submit(self, interaction: discord.Interaction):
        text, sport = self.leg.value.strip(), (self.sport.value or "").strip() or None
        db().execute("""INSERT INTO gp_legs (round_id, user_id, user_name, text, sport, status, created_at, updated_at)
                        VALUES (?,?,?,?,?,'open',?,?)
                        ON CONFLICT(round_id, user_id) DO UPDATE SET text = excluded.text, sport = excluded.sport,
                        user_name = excluded.user_name, status = 'open', why = NULL, updated_at = excluded.updated_at""",
                     (self.round_id, interaction.user.id, interaction.user.display_name, text, sport, now_iso(), now_iso()))
        db().commit()
        r = db().execute("SELECT * FROM gp_rounds WHERE id = ?", (self.round_id,)).fetchone()
        if interaction.message is not None:
            await interaction.response.edit_message(embed=gp_embed(r), view=gp_view(r["id"]))
        else:
            await interaction.response.send_message("You're in.", ephemeral=True)


class GPGradeView(discord.ui.View):
    def __init__(self, round_id: int, legs: list, board_message):
        super().__init__(timeout=300)
        self.round_id, self.board = round_id, board_message
        self.chosen = None
        sel = discord.ui.Select(placeholder="Pick a leg", options=[
            discord.SelectOption(label=clip(f"{x['user_name']}: {x['text']}", 100), value=str(x["id"])) for x in legs[:25]])
        sel.callback = self._pick(sel)
        self.add_item(sel)
        for res, style in (("hit", discord.ButtonStyle.success), ("miss", discord.ButtonStyle.danger),
                           ("push", discord.ButtonStyle.secondary), ("open", discord.ButtonStyle.secondary)):
            b = discord.ui.Button(label={"open": "Reopen"}.get(res, res.title()), style=style)
            b.callback = self._grade(res)
            self.add_item(b)

    def _pick(self, sel):
        async def cb(interaction):
            self.chosen = int(sel.values[0])
            await interaction.response.defer()
        return cb

    def _grade(self, res):
        async def cb(interaction):
            if self.chosen is None:
                await interaction.response.send_message("Pick a leg first.", ephemeral=True)
                return
            await set_gp_result(interaction.client, self.chosen, res, "graded by a mod" if res != "open" else None)
            r = db().execute("SELECT * FROM gp_rounds WHERE id = ?", (self.round_id,)).fetchone()
            await interaction.response.edit_message(content=f"Done: marked {res}.", view=None)
            if self.board is not None:
                try:
                    await self.board.edit(embed=gp_embed(r), view=gp_view(r["id"]))
                except Exception:
                    pass
        return cb


async def set_gp_result(client, leg_id: int, result: str, why: Optional[str]) -> None:
    leg = db().execute("SELECT * FROM gp_legs WHERE id = ?", (leg_id,)).fetchone()
    if leg is None:
        return
    r = db().execute("SELECT * FROM gp_rounds WHERE id = ?", (leg["round_id"],)).fetchone()
    before = gp_state(gp_legs(r["id"]))
    db().execute("UPDATE gp_legs SET status = ?, why = ? WHERE id = ?", (result, why, leg_id))
    db().commit()
    after = gp_state(gp_legs(r["id"]))
    channel = client.get_channel(r["channel_id"]) if r["channel_id"] else None
    if channel is None:
        return
    import random
    if result == "miss" and before != "busted":
        await channel.send(random.choice(GP_ROASTS).format(name=f"**{leg['user_name']}**")
                           + f" ({clip(leg['text'], 80)}" + (f": {why}" if why else "") + ")",
                           allowed_mentions=discord.AllowedMentions.none())
    if after == "hit" and before != "hit":
        await channel.send(f"🎉🎉 The group parlay **HIT**! {len(gp_legs(r['id']))} legs, every one cashed.")
    if r["message_id"]:
        try:
            await channel.get_partial_message(r["message_id"]).edit(embed=gp_embed(r), view=gp_view(r["id"]))
        except Exception:
            pass


async def grade_group_parlays(client: discord.Client, now: Optional[datetime] = None) -> None:
    now = now or datetime.now(timezone.utc)
    weeks = (week_id(now), week_id(now - timedelta(days=7)))
    for leg in db().execute("""SELECT l.*, r.guild_id FROM gp_legs l JOIN gp_rounds r ON r.id = l.round_id
                               WHERE l.status = 'open' AND r.week IN (?, ?)""", weeks).fetchall():
        like = {"id": 0, "created_at": leg["updated_at"] or leg["created_at"], "sport": leg["sport"],
                "description": leg["text"], "status": "open"}
        try:
            found = await free_grade(like, [(1, leg["text"])], context_legs=[])
        except Exception:
            log.exception("Group parlay grading failed")
            continue
        if 1 in found:
            await set_gp_result(client, leg["id"], found[1][0], found[1][1])


async def post_weekly_group_parlay(client: discord.Client, now: Optional[datetime] = None) -> None:
    now = (now or datetime.now(TZ)).astimezone(TZ)
    if now.weekday() != 0 or now.hour < TODAY_HOUR:
        return
    for row in db().execute("SELECT guild_id, value FROM settings WHERE key = 'recap_channel'").fetchall():
        gid = row["guild_id"]
        if get_setting(gid, "gp_autopost") == "off" or get_setting(gid, "last_gp_week") == week_id(now):
            continue
        set_setting(gid, "last_gp_week", week_id(now))
        channel = client.get_channel(int(row["value"]))
        if channel is None:
            continue
        r = gp_round(gid)
        msg = await channel.send("🤝 New week, new group parlay. One leg each, tap the button to get in.",
                                 embed=gp_embed(r), view=gp_view(r["id"]))
        db().execute("UPDATE gp_rounds SET channel_id = ?, message_id = ? WHERE id = ?", (channel.id, msg.id, r["id"]))
        db().commit()


# ---- copies --------------------------------------------------------------------------------

def copy_count(pick_id: int) -> int:
    return db().execute("SELECT COUNT(*) FROM picks WHERE copied_from = ?", (pick_id,)).fetchone()[0]


def make_copy(src, user, cost: float, payout: float) -> int:
    pid = insert_pick(guild_id=src["guild_id"], bettor_key=str(user.id), bettor_name=user.display_name,
                      bettor_id=user.id, logged_by=user.id, platform=src["platform"], sport=src["sport"],
                      description=clip(f"📋 Copy of #{src['id']} ({src['bettor_name']}): {src['description']}", 200),
                      legs=src["legs"], cost=cost, payout=payout)
    db().execute("UPDATE picks SET copied_from = ?, kalshi_ticker = ?, kalshi_side = ?, preseason = ? WHERE id = ?",
                 (src["id"], src["kalshi_ticker"], src["kalshi_side"], src["preseason"], pid))
    # carry over legs that are already decided
    for leg in get_legs(src["id"]):
        if leg["status"] != "open":
            db().execute("UPDATE legs SET status = ? WHERE pick_id = ? AND idx = ?", (leg["status"], pid, leg["idx"]))
    db().commit()
    return pid


class CopyModal(discord.ui.Modal, title="Copy this pick"):
    cost = discord.ui.TextInput(label="Your stake", max_length=12)
    payout = discord.ui.TextInput(label="Your max payout", max_length=12)

    def __init__(self, src):
        super().__init__()
        self.src_id = src["id"]
        self.cost.default = f"{src['cost']:g}"
        self.payout.default = f"{src['payout']:g}"

    async def on_submit(self, interaction: discord.Interaction):
        src = get_pick(interaction.guild_id, self.src_id)
        try:
            cost, payout = parse_money(self.cost.value), parse_money(self.payout.value)
        except ValueError:
            await interaction.response.send_message("Those amounts didn't read as numbers.", ephemeral=True)
            return
        if src is None or cost <= 0 or payout <= 0:
            await interaction.response.send_message("Can't copy that one.", ephemeral=True)
            return
        await finish_copy(interaction, src, cost, payout)


async def finish_copy(interaction: discord.Interaction, src, cost: float, payout: float):
    pid = make_copy(src, interaction.user, cost, payout)
    p = get_pick(interaction.guild_id, pid)
    await interaction.response.send_message(
        f"📋 **{interaction.user.display_name}** copied **{src['bettor_name']}**'s pick #{src['id']} "
        f"({copy_count(src['id'])} cop{'y' if copy_count(src['id']) == 1 else 'ies'} now). It grades on its own.", embed=pick_embed(p), view=settle_view(pid))


class CopyButton(discord.ui.DynamicItem[discord.ui.Button], template=r"cp:(?P<pid>\d+)"):
    def __init__(self, pick_id: int):
        super().__init__(discord.ui.Button(label="📋 Copy", style=discord.ButtonStyle.secondary,
                                           custom_id=f"cp:{pick_id}", row=1))
        self.pick_id = pick_id

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(int(match["pid"]))

    async def callback(self, interaction: discord.Interaction):
        p = get_pick(interaction.guild_id, self.pick_id)
        if p is None or p["status"] != "open":
            await interaction.response.send_message("That pick is already settled.", ephemeral=True)
            return
        if str(interaction.user.id) == p["bettor_key"]:
            await interaction.response.send_message("That's already your pick.", ephemeral=True)
            return
        if p["hidden"]:
            await interaction.response.send_message("Hidden picks can't be copied.", ephemeral=True)
            return
        await interaction.response.send_modal(CopyModal(p))


class CardSweatButton(discord.ui.DynamicItem[discord.ui.Button], template=r"csw:(?P<pid>\d+)"):
    def __init__(self, pick_id: int):
        super().__init__(discord.ui.Button(label="🥵 Sweat", style=discord.ButtonStyle.secondary,
                                           custom_id=f"csw:{pick_id}", row=1))
        self.pick_id = pick_id

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(int(match["pid"]))

    async def callback(self, interaction: discord.Interaction):
        p = get_pick(interaction.guild_id, self.pick_id)
        if p is None:
            await interaction.response.send_message("That pick no longer exists.", ephemeral=True)
            return
        await interaction.response.defer()
        await start_sweat(interaction.channel, p, interaction.user.id)


class CardKalshiButton(discord.ui.DynamicItem[discord.ui.Button], template=r"ckl:(?P<pid>\d+)"):
    def __init__(self, pick_id: int):
        super().__init__(discord.ui.Button(label="🔗 Kalshi", style=discord.ButtonStyle.secondary,
                                           custom_id=f"ckl:{pick_id}", row=1))
        self.pick_id = pick_id

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(int(match["pid"]))

    async def callback(self, interaction: discord.Interaction):
        p = get_pick(interaction.guild_id, self.pick_id)
        if p is None or not can_edit(interaction, p):
            await interaction.response.send_message("Only the bettor or a mod can link this pick.", ephemeral=True)
            return
        await interaction.response.send_modal(KalshiLinkModal(p["id"]))


def propagate_to_copies(pick_id: int, idx: Optional[int], status: str) -> None:
    """When the original's leg (or the whole single pick) is graded, grade open copies the same way."""
    for c in db().execute("SELECT * FROM picks WHERE copied_from = ? AND status = 'open'", (pick_id,)).fetchall():
        if idx is None:
            if not get_legs(c["id"]) and status in ("win", "loss", "push"):
                settle_pick(c["guild_id"], c["id"], status)
            continue
        leg = db().execute("SELECT * FROM legs WHERE pick_id = ? AND idx = ?", (c["id"], idx)).fetchone()
        if leg and leg["status"] == "open":
            grade_leg(c["guild_id"], c["id"], idx, status)


# ---- Wrapped ---------------------------------------------------------------------------------

def wrapped_data(guild_id: int, key: str, since: Optional[str], until: Optional[str]) -> Optional[dict]:
    sql, args = "SELECT * FROM picks WHERE guild_id = ? AND bettor_key = ?", [guild_id, key]
    if since:
        sql += " AND created_at >= ?"
        args.append(since)
    if until:
        sql += " AND created_at < ?"
        args.append(until)
    picks = db().execute(sql + " ORDER BY id", args).fetchall()
    if not picks:
        return None
    settled = [p for p in picks if p["status"] != "open"]
    s = {"wins": sum(p["status"] == "win" for p in settled), "losses": sum(p["status"] == "loss" for p in settled),
         "pushes": sum(p["status"] not in ("win", "loss") for p in settled)}
    staked = sum(p["cost"] for p in settled)
    net = sum(pick_net(p) for p in settled)
    s.update(net=net, staked=staked, roi=(net / staked * 100) if staked else 0.0)
    months: dict[str, float] = {}
    days: dict[str, float] = {}
    dows: dict[int, list] = {}
    for p in settled:
        when = datetime.fromisoformat(p["settled_at"] or p["created_at"]).astimezone(TZ)
        months[when.strftime("%B %Y")] = months.get(when.strftime("%B %Y"), 0) + pick_net(p)
        days[when.strftime("%a %b %-d")] = days.get(when.strftime("%a %b %-d"), 0) + pick_net(p)
        dows.setdefault(when.weekday(), []).append(pick_net(p))
    best = max(settled, key=pick_net) if settled else None
    heartbreak = None
    for p in settled:
        if p["status"] != "loss":
            continue
        legs = get_legs(p["id"])
        if len(legs) >= 2 and sum(1 for x in legs if x["status"] == "miss") == 1:
            if heartbreak is None or p["payout"] > heartbreak["payout"]:
                heartbreak = p
    worst = min(settled, key=pick_net) if settled else None
    players: dict[str, list] = {}
    sides = {"over": [0, 0], "under": [0, 0]}
    for p in picks:
        for leg in get_legs(p["id"]):
            prop = prop_of(leg["text"])
            if not prop:
                continue
            players.setdefault(prop["player"], []).append(leg["status"])
            if leg["status"] in ("hit", "miss"):
                sides[prop["side"]][0 if leg["status"] == "hit" else 1] += 1
    fav = max(players.items(), key=lambda kv: len(kv[1])) if players else None
    plats: dict[str, int] = {}
    for p in picks:
        plats[p["platform"]] = plats.get(p["platform"], 0) + 1
    tailed = db().execute("""SELECT p.bettor_name AS n, COUNT(*) AS c FROM follows f JOIN picks p ON p.id = f.pick_id
                             WHERE p.guild_id = ? AND f.user_id = ? AND f.kind = 'tail' GROUP BY p.bettor_key
                             ORDER BY c DESC LIMIT 1""", (guild_id, int(key) if key.isdigit() else -1)).fetchone()
    fans = db().execute("""SELECT f.user_name AS n, COUNT(*) AS c FROM follows f JOIN picks p ON p.id = f.pick_id
                           WHERE p.guild_id = ? AND p.bettor_key = ? AND f.kind = 'tail' GROUP BY f.user_id
                           ORDER BY c DESC LIMIT 1""", (guild_id, key)).fetchone()
    copies = db().execute("SELECT COUNT(*) FROM picks WHERE copied_from IN (SELECT id FROM picks WHERE bettor_key = ? "
                          "AND guild_id = ?)", (key, guild_id)).fetchone()[0]
    statuses = [p["status"] for p in sorted(settled, key=lambda p: p["settled_at"] or p["created_at"])]
    return {"name": picks[-1]["bettor_name"], "count": len(picks), "s": s, "months": months, "days": days, "dows": dows,
            "best": best, "worst": worst, "heartbreak": heartbreak, "fav": fav, "sides": sides, "platforms": plats,
            "tailed": tailed, "fans": fans, "copies": copies, "streak": longest_win_streak(statuses),
            "badges": earned_badges(guild_id, key), "sports": breakdown(settled, lambda p: sport_group(p["sport"]))}


DOW_NAMES = ["Mondays", "Tuesdays", "Wednesdays", "Thursdays", "Fridays", "Saturdays", "Sundays"]


def wrapped_pages(d: dict, label: str) -> list[discord.Embed]:
    s = d["s"]
    pages = []

    def page(title, body, color=BRAND):
        e = discord.Embed(title=title, description=body, color=color)
        pages.append(e)
        return e
    page(f"🎁 {d['name']}'s {label} Wrapped",
         f"# {d['count']} picks\nlogged across **{len(d['platforms'])}** platform{'s' if len(d['platforms']) != 1 else ''} "
         f"({', '.join(f'{k} {v}' for k, v in sorted(d['platforms'].items(), key=lambda kv: -kv[1]))}).\n\n"
         f"{money(s['staked'])} put on the line. Let's see how that went. ▶")
    green = s["net"] >= 0
    best_m = max(d["months"].items(), key=lambda kv: kv[1]) if d["months"] else None
    worst_m = min(d["months"].items(), key=lambda kv: kv[1]) if d["months"] else None
    page("💰 The bottom line",
         f"# {signed(s['net'])}\n{record_line(s)} · ROI {s['roi']:+.1f}%\n\n"
         + (f"Best month: **{best_m[0]}** ({signed(best_m[1])})\n" if best_m else "")
         + (f"Worst month: **{worst_m[0]}** ({signed(worst_m[1])})" if worst_m and worst_m != best_m else "")
         + ("\n\n" + ("Green. Respect. 🟢" if green else "Red. It happens. 🔴")),
         0x2ECC71 if green else 0xE74C3C)
    if d["best"] is not None and pick_net(d["best"]) > 0:
        b = d["best"]
        page("🚀 Biggest hit", f"# {signed(pick_net(b))}\n**{b['description']}**\n{money(b['cost'])} → {money(b['returned'] or 0)} "
             f"({(b['returned'] or 0) / b['cost']:.1f}x) · {local_day(b['settled_at'] or b['created_at'])}", 0x2ECC71)
    if d["heartbreak"] is not None:
        h = d["heartbreak"]
        miss = next((x["text"] for x in get_legs(h["id"]) if x["status"] == "miss"), "?")
        page("💔 The one that got away", f"**{h['description']}** would've paid **{money(h['payout'])}**.\n"
             f"Every leg hit except one: *{miss}*.\n\nWe don't talk about it.", 0xE74C3C)
    elif d["worst"] is not None and pick_net(d["worst"]) < 0:
        w = d["worst"]
        page("🧊 Worst beat", f"# {signed(pick_net(w))}\n**{w['description']}**", 0xE74C3C)
    if d["fav"]:
        name, sts = d["fav"]
        hits = sum(1 for x in sts if x == "hit")
        done = sum(1 for x in sts if x in ("hit", "miss"))
        o, u = d["sides"]["over"], d["sides"]["under"]
        page("⭐ Your guy", f"# {name.title()}\nOn **{len(sts)}** of your legs · hit **{hits}/{done}**"
             + (f" ({hits / done * 100:.0f}%)" if done else "")
             + f"\n\nOvers: {o[0]}-{o[1]} · Unders: {u[0]}-{u[1]}"
             + ("\nYou love an over. 📈" if sum(o) > 2 * max(1, sum(u)) else ""))
    if d["dows"]:
        avg = {k: sum(v) for k, v in d["dows"].items()}
        bd, wd = max(avg, key=avg.get), min(avg, key=avg.get)
        bn = max(d["days"].items(), key=lambda kv: kv[1])
        wn = min(d["days"].items(), key=lambda kv: kv[1])
        page("📅 When you bet", f"Best day: **{DOW_NAMES[bd]}** ({signed(avg[bd])})\nWorst day: **{DOW_NAMES[wd]}** "
             f"({signed(avg[wd])})\n\nLuckiest night: **{bn[0]}** ({signed(bn[1])})\nRoughest night: **{wn[0]}** ({signed(wn[1])})")
    crew = []
    if d["tailed"]:
        crew.append(f"You tailed **{d['tailed']['n']}** the most ({d['tailed']['c']} times).")
    if d["fans"]:
        crew.append(f"Your biggest fan: **{d['fans']['n']}** tailed you {d['fans']['c']} times.")
    if d["copies"]:
        crew.append(f"Your picks got copied **{d['copies']}** times. 📋")
    if crew:
        page("👥 The crew", "\n".join(crew))
    top_sport = d["sports"][0][0] if d["sports"] else "-"
    page("🏁 That's a wrap", f"Longest win streak: **{d['streak']}**\nBadges: **{len(d['badges'])}/{len(BADGES)}** "
         f"{' '.join(BADGE_ICONS[k] for k, _, _ in BADGES if k in d['badges'])}\nTop sport: **{top_sport}**\n\n"
         "Here's your card to share. 👇")
    for i, e in enumerate(pages):
        e.set_footer(text=f"{i + 1}/{len(pages)} · PIMP-BOT Wrapped")
    return pages


def render_wrapped(d: dict, label: str) -> io.BytesIO:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch
    s = d["s"]
    fig = plt.figure(figsize=(10.8, 13.5), dpi=100)
    fig.patch.set_facecolor("#1b1030")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1080)
    ax.set_ylim(0, 1350)
    ax.axis("off")
    for k in range(30):  # soft purple glow at the top
        ax.add_patch(FancyBboxPatch((0, 1350 - k * 18), 1080, 18, boxstyle="square,pad=0",
                                    facecolor="#7B3FE4", alpha=max(0.0, 0.5 - k * 0.017), edgecolor="none"))
    ax.text(70, 1230, "WRAPPED", color="#ffffff", fontsize=64, fontweight="bold")
    ax.text(74, 1170, f"{clip(d['name'], 24)} · {label}", color="#d9ccff", fontsize=24)

    def tile(x, y, w, h, big, small, color="#ffffff"):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=26",
                                    facecolor="#2a1a4a", edgecolor="#4b2f86", linewidth=2))
        ax.text(x + 36, y + h / 2 + 18, big, color=color, fontsize=40 if len(big) < 10 else 30, fontweight="bold",
                va="center")
        ax.text(x + 38, y + h / 2 - 52, small.upper(), color="#b9a8e8", fontsize=14, va="center")
    green = "#3fb97a" if s["net"] >= 0 else "#e66767"
    tile(70, 880, 450, 220, signed(s["net"]), "net profit", green)
    tile(560, 880, 450, 220, record_line(s), "record")
    best = d["best"]
    tile(70, 620, 450, 220, signed(pick_net(best)) if best is not None and pick_net(best) > 0 else "-", "biggest hit", "#3fb97a")
    tile(560, 620, 450, 220, f"{s['roi']:+.0f}%", "roi", green)
    fav = d["fav"][0].title() if d["fav"] else "-"
    tile(70, 360, 940, 220, clip(fav, 26), "your guy")
    top = d["sports"][0][0] if d["sports"] else "-"
    tile(70, 100, 450, 220, str(d["count"]), "picks")
    tile(560, 100, 450, 220, clip(top, 12), "top sport")
    ax.text(1010, 50, "PIMP-BOT", color="#b9a8e8", fontsize=14, ha="right")
    out = io.BytesIO()
    fig.savefig(out, format="png", facecolor=fig.get_facecolor())
    plt.close(fig)
    out.seek(0)
    return out


class WrappedView(discord.ui.View):
    def __init__(self, owner_id: int, pages: list[discord.Embed], card: Optional[bytes]):
        super().__init__(timeout=1800)
        self.owner_id, self.pages, self.card, self.i = owner_id, pages, card, 0
        self.prev = discord.ui.Button(label="◀", style=discord.ButtonStyle.secondary)
        self.next = discord.ui.Button(label="Next ▶", style=discord.ButtonStyle.primary)
        self.prev.callback = self._move(-1)
        self.next.callback = self._move(1)
        self.add_item(self.prev)
        self.add_item(self.next)

    def _move(self, delta):
        async def cb(interaction):
            if interaction.user.id != self.owner_id:
                await interaction.response.send_message("Run `/wrapped` to see yours.", ephemeral=True)
                return
            self.i = max(0, min(len(self.pages) - 1, self.i + delta))
            e = self.pages[self.i]
            last = self.i == len(self.pages) - 1
            files = []
            if last and self.card:
                files = [discord.File(io.BytesIO(self.card), filename="wrapped.png")]
                e.set_image(url="attachment://wrapped.png")
            await interaction.response.edit_message(embed=e, view=self, attachments=files)
        return cb


# ---- schedule -----------------------------------------------------------------------------

async def schedule_embed(guild_id: int, key: Optional[str], title: str) -> discord.Embed:
    sql, args = "SELECT * FROM picks WHERE guild_id = ? AND status = 'open'", [guild_id]
    if key:
        sql += " AND bettor_key = ?"
        args.append(key)
    picks = [p for p in db().execute(sql + " ORDER BY id DESC LIMIT 60", args).fetchall()
             if not p["hidden"] or (key and p["bettor_key"] == key)]
    games: dict[str, dict] = {}
    loose = []
    for p in picks:
        found = False
        for e in await leg_progress(p):
            ev = e["event"]
            if not ev:
                continue
            found = True
            g = games.setdefault(ev["id"], {"ev": ev, "picks": {}})
            g["picks"].setdefault(p["id"], [p, 0])[1] += 1
        if not found:
            loose.append(p)
    e = discord.Embed(title=title, color=BRAND)
    if not picks:
        e.description = "No open picks."
        return e
    by_day: dict[str, list] = {}
    for g in sorted(games.values(), key=lambda g: g["ev"]["date"]):
        when = event_time(g["ev"])
        day = when.astimezone(TZ).strftime("%A %b %-d") if when else "Unknown day"
        who = ", ".join(f"#{p['id']} {p['bettor_name']}" + (f" ({n} legs)" if n > 1 else "")
                        for p, n in g["picks"].values())
        by_day.setdefault(day, []).append(f"{today_line(g['ev'])}\n　{clip(who, 200)}")
    for day, lines in list(by_day.items())[:8]:
        e.add_field(name=day, value=clip("\n".join(lines), 1024), inline=False)
    if loose:
        e.add_field(name="No game found (props on other sports, futures...)", inline=False,
                    value=clip(", ".join(f"#{p['id']} {p['bettor_name']}" for p in loose[:30]), 1024))
    e.set_footer(text="Times are Central · 🔴 live · ✅ final")
    return e


class ScheduleView(discord.ui.View):
    def __init__(self, owner_id: int, guild_id: int, mine_key: str, mode: str):
        super().__init__(timeout=900)
        self.owner_id, self.guild_id, self.mine_key, self.mode = owner_id, guild_id, mine_key, mode
        for m, label in (("mine", "👤 Mine"), ("all", "👥 Everyone")):
            b = discord.ui.Button(label=label, style=discord.ButtonStyle.primary if m == mode else discord.ButtonStyle.secondary)
            b.callback = self._go(m)
            self.add_item(b)
        b = discord.ui.Button(label="🔄", style=discord.ButtonStyle.secondary)
        b.callback = self._go(None)
        self.add_item(b)

    def _go(self, mode):
        async def cb(interaction):
            if interaction.user.id != self.owner_id:
                await interaction.response.send_message("Run `/schedule` yourself.", ephemeral=True)
                return
            self.mode = mode or self.mode
            await interaction.response.defer()
            key = self.mine_key if self.mode == "mine" else None
            e = await schedule_embed(self.guild_id, key, "📅 Your games" if key else "📅 Everyone's games")
            await interaction.message.edit(embed=e, view=ScheduleView(self.owner_id, self.guild_id, self.mine_key, self.mode))
        return cb


# ---- settings toggles -------------------------------------------------------------------------

SETTING_TOGGLES = [  # (setting key, label when it's on, value that means on, default on?)
    ("exclude_preseason", "Preseason picks on the leaderboard", "on", False),
    ("gp_autopost", "Post a new group parlay every Monday", "off", True),
]


class SettingsView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=900)
        self.guild_id = guild_id
        pre_out = get_setting(guild_id, "exclude_preseason") == "on"
        gp_on = get_setting(guild_id, "gp_autopost") != "off"
        for key, label, on in (("exclude_preseason", "Preseason on leaderboard", not pre_out),
                               ("gp_autopost", "Monday group parlay", gp_on)):
            b = discord.ui.Button(label=f"{label}: {'ON' if on else 'OFF'}",
                                  style=discord.ButtonStyle.success if on else discord.ButtonStyle.secondary)
            b.callback = self._toggle(key)
            self.add_item(b)

    def _toggle(self, key):
        async def cb(interaction):
            perms = getattr(interaction.user, "guild_permissions", None)
            if not (perms and getattr(perms, "manage_guild", False)):
                await interaction.response.send_message("Admins only.", ephemeral=True)
                return
            if key == "exclude_preseason":
                set_setting(self.guild_id, key, None if get_setting(self.guild_id, key) == "on" else "on")
            else:
                set_setting(self.guild_id, key, None if get_setting(self.guild_id, key) == "off" else "off")
            await interaction.response.edit_message(view=SettingsView(self.guild_id))
        return cb


# ==========================================================================
# r10: insights, calculators, money tracking, inverse bot, one-leg alerts,
# slip reactions, PrizePicks settle offers
# ==========================================================================

def shown_desc(p) -> str:
    """A hidden pick's details stay secret until it settles."""
    if p["hidden"] and p["status"] == "open":
        return "🔒 Hidden pick (revealed when it settles)"
    return p["description"]


# ---- margins: how close a leg came -----------------------------------------------------

_margins: dict[tuple[int, int], float] = {}


def bettor_margin(leg: dict, value: float) -> float:
    """Positive = by how much it cleared, negative = by how much it missed (for the bettor's side)."""
    m = value - leg["line"] if leg["side"] == "over" else leg["line"] - value
    return -m if leg.get("negate") else m


def simple_margin(leg: dict, ev: dict, i: Optional[int]) -> Optional[float]:
    try:
        if i is not None:
            mine, theirs = ev["teams"][i]["score"], ev["teams"][1 - i]["score"]
        total = sum(t["score"] for t in ev["teams"])
        k = leg["kind"]
        if k == "spread":
            m = mine - theirs + leg["line"]
        elif k == "margin":
            m = mine - theirs - leg["line"]
        elif k == "ml":
            m = mine - theirs
        else:
            value = total if k == "total" else mine
            m = value - leg["line"] if leg["side"] == "over" else leg["line"] - value
        return -m if leg.get("negate") else m
    except Exception:
        return None


# ---- PrizePicks payout table -------------------------------------------------------------

PP_POWER = {2: 3.0, 3: 5.0, 4: 10.0, 5: 20.0, 6: 37.5}
PP_FLEX = {3: {3: 3.0, 2: 1.0}, 4: {4: 6.0, 3: 1.5}, 5: {5: 10.0, 4: 2.0, 3: 0.4}, 6: {6: 25.0, 5: 2.0, 4: 0.4}}


def pp_tables(guild_id: Optional[int]) -> tuple[dict, dict]:
    """The standard tables, with any overrides an admin saved."""
    power, flex = dict(PP_POWER), {k: dict(v) for k, v in PP_FLEX.items()}
    if guild_id:
        raw = get_setting(guild_id, "pp_table")
        if raw:
            try:
                saved = json.loads(raw)
                power.update({int(k): float(v) for k, v in (saved.get("power") or {}).items()})
                for k, v in (saved.get("flex") or {}).items():
                    flex[int(k)] = {int(a): float(b) for a, b in v.items()}
            except (ValueError, TypeError):
                pass
    return power, flex


def pp_kind(p) -> str:
    return "flex" if re.search(r"\bflex", (p["description"] or "").lower()) else "power"


def pp_multiplier(guild_id: Optional[int], kind: str, n: int, hits: int) -> Optional[float]:
    power, flex = pp_tables(guild_id)
    if kind == "power":
        return power.get(n) if hits == n else 0.0
    if n not in flex:
        return None
    return flex[n].get(hits, 0.0)


def pp_settlement(p) -> Optional[tuple[float, str]]:
    """(amount back, explanation) from the payout table once every leg is graded.
    A leg that pushed (player didn't play) drops off and the slip pays as a smaller one."""
    legs = get_legs(p["id"])
    if not legs or any(x["status"] == "open" for x in legs):
        return None
    hits = sum(1 for x in legs if x["status"] == "hit")
    n = sum(1 for x in legs if x["status"] != "push")
    kind = pp_kind(p)
    if n < 2:
        return p["cost"], "fewer than 2 picks left, so the entry is refunded"
    mult = pp_multiplier(p["guild_id"], kind, n, hits)
    if mult is None:
        return None
    full = len(legs)
    own_mult = p["payout"] / p["cost"] if p["cost"] else 0
    if n == full and hits == n and own_mult:
        mult = own_mult        # the slip's own multiplier beats the table when everything hit
    note = f"{kind.title()} {hits}/{n}" + (f" (was a {full}-pick, {full - n} dropped)" if n < full else "") + f" = {mult:g}x"
    return round(p["cost"] * mult, 2), note


class PPSettleButton(discord.ui.DynamicItem[discord.ui.Button], template=r"pps:(?P<pid>\d+):(?P<cents>\d+)"):
    def __init__(self, pick_id: int, cents: int):
        super().__init__(discord.ui.Button(label=f"💵 Settle at {money(cents / 100)}", style=discord.ButtonStyle.success,
                                           custom_id=f"pps:{pick_id}:{cents}"))
        self.pick_id, self.cents = pick_id, cents

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(int(match["pid"]), int(match["cents"]))

    async def callback(self, interaction: discord.Interaction):
        p = get_pick(interaction.guild_id, self.pick_id)
        if p is None or p["status"] != "open":
            await interaction.response.send_message("That one's already settled.", ephemeral=True)
            return
        if not can_edit(interaction, p):
            await interaction.response.send_message(f"Only {p['bettor_name']} or a mod can settle it.", ephemeral=True)
            return
        amount = self.cents / 100
        status = "win" if amount > p["cost"] else ("push" if amount == p["cost"] else "loss")
        p = settle_pick(interaction.guild_id, self.pick_id, status, amount)
        await interaction.response.edit_message(content=f"💵 Settled at {money(amount)}.", embed=pick_embed(p), view=None)


async def offer_pp_settlements(client: discord.Client, now: Optional[datetime] = None) -> None:
    rows = db().execute("""SELECT * FROM picks WHERE status = 'open' AND lower(platform) = 'prizepicks'
                           AND pp_offered IS NULL AND id IN (SELECT pick_id FROM legs)""").fetchall()
    for p in rows:
        got = pp_settlement(p)
        if got is None:
            continue
        db().execute("UPDATE picks SET pp_offered = ? WHERE id = ?", (now_iso(), p["id"]))
        db().commit()
        amount, note = got
        channel = await recap_channel_for(client, p["guild_id"])
        if channel is None:
            continue
        view = discord.ui.View(timeout=None)
        view.add_item(PPSettleButton(p["id"], int(round(amount * 100))))
        who = f"<@{p['bettor_id']}>" if p["bettor_id"] else f"**{p['bettor_name']}**"
        await channel.send(f"🧾 {who}, every leg on PrizePicks pick `#{p['id']}` is graded: {note} → **{money(amount)}** "
                           f"back on {money(p['cost'])}. Tap to settle, or use `/result` if the app paid something else "
                           "(payouts change, and goblins/demons pay differently).", view=view,
                           allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=True))


# ---- one leg away ------------------------------------------------------------------------

async def one_leg_alerts(client: discord.Client, now: Optional[datetime] = None) -> None:
    rows = db().execute("""SELECT * FROM picks WHERE status = 'open' AND one_leg_at IS NULL
                           AND id IN (SELECT pick_id FROM legs GROUP BY pick_id HAVING COUNT(*) >= 3)""").fetchall()
    for p in rows:
        legs = get_legs(p["id"])
        open_legs = [x for x in legs if x["status"] == "open"]
        if len(open_legs) != 1 or any(x["status"] == "miss" for x in legs):
            continue
        if p["hidden"]:
            continue
        db().execute("UPDATE picks SET one_leg_at = ? WHERE id = ?", (now_iso(), p["id"]))
        db().commit()
        channel = await recap_channel_for(client, p["guild_id"])
        if channel is None:
            continue
        last = open_legs[0]["text"]
        view = discord.ui.View(timeout=None)
        view.add_item(CardSweatButton(p["id"]))
        await channel.send(f"🚨 **ONE LEG AWAY.** {p['bettor_name']}'s {clip(p['description'], 60)} (`#{p['id']}`) "
                           f"has {len(legs) - 1} legs in and needs **{clip(last, 100)}** for **{money(p['payout'])}**. "
                           "Everybody sweat. 🥵", view=view, allowed_mentions=discord.AllowedMentions.none())


# ---- reactions on the original slip -------------------------------------------------------

REACT = {"win": "✅", "loss": "❌", "push": "➖", "void": "➖"}


def jump_ids(url: Optional[str]) -> Optional[tuple[int, int]]:
    m = re.search(r"/channels/\d+/(\d+)/(\d+)", url or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


async def react_to_slips(client: discord.Client, now: Optional[datetime] = None) -> None:
    now = now or datetime.now(timezone.utc)
    since = iso(now - timedelta(days=7))
    rows = db().execute("""SELECT * FROM picks WHERE status != 'open' AND reacted IS NULL AND slip_url LIKE '%/channels/%'
                           AND settled_at >= ? LIMIT 30""", (since,)).fetchall()
    for p in rows:
        db().execute("UPDATE picks SET reacted = 1 WHERE id = ?", (p["id"],))
        db().commit()
        ids = jump_ids(p["slip_url"])
        channel = client.get_channel(ids[0]) if ids else None
        if channel is None:
            continue
        try:
            msg = channel.get_partial_message(ids[1])
            await msg.add_reaction(REACT.get(p["status"], "➖"))
            if p["status"] == "win" and p["cost"] and (p["returned"] or 0) / p["cost"] >= 5:
                await msg.add_reaction("🔥")
        except Exception:
            log.warning("Couldn't react to slip for pick %s", p["id"])


# ---- inverse bot ----------------------------------------------------------------------------

def fade_net(p) -> float:
    """What fading this pick at fair odds would have made: lose the stake when it wins,
    win stake x (stake / (payout - stake)) when it loses."""
    if p["status"] == "win":
        return -p["cost"]
    if p["status"] == "loss" and p["payout"] > p["cost"] > 0:
        return p["cost"] * p["cost"] / (p["payout"] - p["cost"])
    return 0.0


def inverse_line(picks: list) -> Optional[str]:
    settled = [p for p in picks if p["status"] in ("win", "loss")]
    if not settled:
        return None
    net = sum(fade_net(p) for p in settled)
    staked = sum(p["cost"] for p in settled)
    w = sum(1 for p in settled if p["status"] == "loss")
    l = len(settled) - w
    return f"🙃 **Fade-everyone bot** · {w}-{l} · {signed(net)} · ROI {net / staked * 100:+.1f}%"


# ---- insights -------------------------------------------------------------------------------

def settled_picks(guild_id: int, key: Optional[str] = None, since: Optional[str] = None) -> list:
    sql, args = "SELECT * FROM picks WHERE guild_id = ? AND status != 'open'", [guild_id]
    if key:
        sql += " AND bettor_key = ?"
        args.append(key)
    if since:
        sql += " AND settled_at >= ?"
        args.append(since)
    return db().execute(sql + " ORDER BY settled_at", args).fetchall()


def wl(rows) -> str:
    w = sum(1 for x in rows if x in ("hit", "win"))
    l = sum(1 for x in rows if x in ("miss", "loss"))
    pct = f" ({w / (w + l) * 100:.0f}%)" if w + l else ""
    return f"{w}-{l}{pct}"


def tendencies_pages(guild_id: int, key: str, name: str) -> dict[str, discord.Embed]:
    picks = db().execute("SELECT * FROM picks WHERE guild_id = ? AND bettor_key = ?", (guild_id, key)).fetchall()
    legs = []
    for p in picks:
        for x in get_legs(p["id"]):
            if x["status"] in ("hit", "miss"):
                legs.append((p, x, prop_of(x["text"])))
    pages = {}
    # props
    e = discord.Embed(title=f"🧠 {name}'s tendencies · props", color=BRAND)
    props = [(p, x, pr) for p, x, pr in legs if pr]
    if props:
        sides = {"over": [x["status"] for _, x, pr in props if pr["side"] == "over"],
                 "under": [x["status"] for _, x, pr in props if pr["side"] == "under"]}
        e.description = f"More / over: **{wl(sides['over'])}** · Less / under: **{wl(sides['under'])}**"
        by_stat: dict[str, list] = {}
        for _, x, pr in props:
            by_stat.setdefault(STATS[pr["stats"][0]][0], []).append(x["status"])
        top = sorted(by_stat.items(), key=lambda kv: -len(kv[1]))[:10]
        e.add_field(name="By stat", inline=False, value="\n".join(f"**{k}** · {wl(v)}" for k, v in top))
        by_player: dict[str, list] = {}
        for _, x, pr in props:
            by_player.setdefault(pr["player"].title(), []).append(x["status"])
        ranked = sorted(((k, v) for k, v in by_player.items() if len(v) >= 2),
                        key=lambda kv: (sum(s == "hit" for s in kv[1]) / len(kv[1]), len(kv[1])), reverse=True)
        rate = lambda v: sum(s == "hit" for s in v) / len(v)
        good = [kv for kv in ranked if rate(kv[1]) >= 0.5][:5]
        bad = [kv for kv in ranked[::-1] if rate(kv[1]) < 0.5][:5]
        if good:
            e.add_field(name="✅ Your best players", value="\n".join(f"{k} · {wl(v)}" for k, v in good))
        if bad:
            e.add_field(name="❌ Stop betting", value="\n".join(f"{k} · {wl(v)}" for k, v in bad))
    else:
        e.description = "No graded player props yet."
    pages["props"] = e
    # slips
    e = discord.Embed(title=f"🧠 {name}'s tendencies · slips", color=BRAND)
    settled = [p for p in picks if p["status"] != "open"]
    if settled:
        e.add_field(name="By size", inline=False,
                    value=breakdown_lines(breakdown(settled, lambda p: size_group(len(get_legs(p["id"]))))))
        e.add_field(name="By platform", inline=False, value=breakdown_lines(breakdown(settled, lambda p: p["platform"])))
        mults = breakdown(settled, lambda p: ("Under 2x" if p["payout"] < 2 * p["cost"] else "2x-5x"
                                              if p["payout"] < 5 * p["cost"] else "5x-20x" if p["payout"] < 20 * p["cost"]
                                              else "20x+") if p["cost"] else "?")
        e.add_field(name="By payout size", inline=False, value=breakdown_lines(mults))
    else:
        e.description = "No settled picks yet."
    pages["slips"] = e
    # days
    e = discord.Embed(title=f"🧠 {name}'s tendencies · when", color=BRAND)
    if settled:
        e.add_field(name="By day you logged it", inline=False, value=breakdown_lines(breakdown(
            settled, lambda p: DOW_NAMES[datetime.fromisoformat(p["created_at"]).astimezone(TZ).weekday()])))
        e.add_field(name="By time of day", inline=False, value=breakdown_lines(breakdown(
            settled, lambda p: time_bucket(datetime.fromisoformat(p["created_at"]).astimezone(TZ).hour))))
    else:
        e.description = "No settled picks yet."
    pages["when"] = e
    return pages


def time_bucket(h: int) -> str:
    return "Morning (5-12)" if 5 <= h < 12 else "Afternoon (12-5)" if 12 <= h < 17 else \
        "Evening (5-10)" if 17 <= h < 22 else "Late night (10-5) 🦉"


class TabView(discord.ui.View):
    def __init__(self, owner_id: int, pages: dict[str, discord.Embed], labels: dict[str, str], current: str):
        super().__init__(timeout=900)
        self.owner_id, self.pages, self.labels = owner_id, pages, labels
        for k, label in labels.items():
            b = discord.ui.Button(label=label, style=discord.ButtonStyle.primary if k == current
                                  else discord.ButtonStyle.secondary)
            b.callback = self._go(k)
            self.add_item(b)

    def _go(self, k):
        async def cb(interaction):
            if interaction.user.id != self.owner_id:
                await interaction.response.send_message("Run the command yourself to flip tabs.", ephemeral=True)
                return
            await interaction.response.edit_message(embed=self.pages[k],
                                                    view=TabView(self.owner_id, self.pages, self.labels, k))
        return cb


def luck_embed(guild_id: int, key: str, name: str) -> discord.Embed:
    picks = [p for p in settled_picks(guild_id, key) if p["status"] in ("win", "loss") and p["payout"] > p["cost"] > 0]
    e = discord.Embed(title=f"🍀 {name}'s luck meter", color=BRAND)
    if len(picks) < 5:
        e.description = "Needs at least 5 settled picks with a payout bigger than the stake."
        return e
    expected = sum(p["cost"] / p["payout"] for p in picks)
    actual = sum(1 for p in picks if p["status"] == "win")
    leg_exp = leg_act = 0.0
    nlegs = 0
    for p in picks:
        legs = [x for x in get_legs(p["id"]) if x["status"] in ("hit", "miss")]
        full = get_legs(p["id"])
        if len(full) >= 2 and len(legs) == len(full):
            per = (p["cost"] / p["payout"]) ** (1 / len(full))
            leg_exp += per * len(legs)
            leg_act += sum(1 for x in legs if x["status"] == "hit")
            nlegs += len(legs)
    diff = actual - expected
    sd = max(0.5, sum((p["cost"] / p["payout"]) * (1 - p["cost"] / p["payout"]) for p in picks) ** 0.5)
    z = diff / sd
    mood = ("😇 Running **hot**" if z > 1.5 else "🙂 A little lucky" if z > 0.5 else "😐 Right about even"
            if z > -0.5 else "😕 A little unlucky" if z > -1.5 else "😈 Running **cold**")
    e.description = (f"{mood}\n\nYou've won **{actual}** of {len(picks)} picks. Going by the payouts you took, "
                     f"the odds said about **{expected:.1f}**. That's **{diff:+.1f}** wins vs expected.")
    if nlegs:
        e.add_field(name="Legs", value=f"Hit {leg_act:.0f}/{nlegs} ({leg_act / nlegs * 100:.0f}%) · "
                                       f"the payouts priced each leg at about {leg_exp / nlegs * 100:.0f}%")
    e.set_footer(text="Uses the payout you got as the odds. Luck evens out; edge doesn't.")
    return e


def render_heatmap(name: str, daily: dict, weeks: int = 26) -> io.BytesIO:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch
    today = datetime.now(TZ).date()
    start = today - timedelta(days=today.weekday() + 7 * (weeks - 1))
    fig, ax = plt.subplots(figsize=(12, 3.4), dpi=110)
    fig.patch.set_facecolor(CHART_SURFACE)
    ax.set_facecolor(CHART_SURFACE)
    peak = max([abs(v) for v in daily.values()] + [1])
    for w in range(weeks):
        for d in range(7):
            day = start + timedelta(days=7 * w + d)
            if day > today:
                continue
            v = daily.get(day.isoformat())
            if v is None:
                color, alpha = "#2c2c2a", 1.0
            elif v == 0:
                color, alpha = CHART_MUTED, 0.5
            else:
                color = "#3fb97a" if v > 0 else "#e66767"
                alpha = 0.35 + 0.65 * min(1.0, abs(v) / peak)
            ax.add_patch(FancyBboxPatch((w + 0.08, 6 - d + 0.08), 0.84, 0.84, boxstyle="round,pad=0,rounding_size=0.15",
                                        facecolor=color, alpha=alpha, edgecolor="none"))
    for w in range(0, weeks, 4):
        ax.text(w + 0.1, 7.35, (start + timedelta(days=7 * w)).strftime("%b %-d"), color=CHART_MUTED, fontsize=8)
    for d, lab in ((0, "Mon"), (2, "Wed"), (4, "Fri"), (6, "Sun")):
        ax.text(-0.25, 6 - d + 0.5, lab, color=CHART_MUTED, fontsize=8, ha="right", va="center")
    ax.set_xlim(-1.2, weeks + 0.2)
    ax.set_ylim(-0.2, 8)
    ax.axis("off")
    total = sum(daily.values())
    up = sum(1 for v in daily.values() if v > 0)
    down = sum(1 for v in daily.values() if v < 0)
    ax.set_title(f"{name} · every day you bet · {up} green, {down} red · {signed(total)}", color=CHART_TEXT,
                 fontsize=12, loc="left")
    out = io.BytesIO()
    fig.savefig(out, format="png", facecolor=CHART_SURFACE, bbox_inches="tight")
    plt.close(fig)
    out.seek(0)
    return out


def daily_net(guild_id: int, key: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for p in settled_picks(guild_id, key):
        d = datetime.fromisoformat(p["settled_at"] or p["created_at"]).astimezone(TZ).date().isoformat()
        out[d] = out.get(d, 0.0) + pick_net(p)
    return out


def bad_beats(guild_id: int, since: Optional[str] = None, limit: int = 10) -> list:
    sql = """SELECT l.*, p.bettor_name, p.id AS pid, p.payout, p.cost, p.description FROM legs l JOIN picks p ON p.id = l.pick_id
             WHERE p.guild_id = ? AND l.status = 'miss' AND l.margin IS NOT NULL AND l.margin < 0 AND l.margin >= -1"""
    args: list = [guild_id]
    if since:
        sql += " AND p.created_at >= ?"
        args.append(since)
    return db().execute(sql + " ORDER BY l.margin DESC, p.payout DESC LIMIT ?", args + [limit]).fetchall()


def bad_beat_line(r) -> str:
    return (f"💀 **{r['bettor_name']}** · {clip(r['text'], 70)} · missed by **{abs(r['margin']):g}**"
            + (f" · {clip(r['note'], 60)}" if r["note"] else "") + f" (`#{r['pid']}`, {money(r['payout'])} slip)")


def records_embed(guild_id: int) -> discord.Embed:
    e = discord.Embed(title="📜 The record book", color=BRAND)
    settled = settled_picks(guild_id)
    if not settled:
        e.description = "Nothing settled yet."
        return e
    best = max(settled, key=pick_net)
    worst = min(settled, key=pick_net)
    mult = max((p for p in settled if p["status"] == "win" and p["cost"]), key=lambda p: (p["returned"] or 0) / p["cost"],
               default=None)
    biggest_parlay = None
    for p in settled:
        if p["status"] == "win":
            n = len(get_legs(p["id"]))
            if n and (biggest_parlay is None or n > biggest_parlay[1]):
                biggest_parlay = (p, n)
    streaks = []
    for k in {p["bettor_key"] for p in settled}:
        st = [p["status"] for p in settled if p["bettor_key"] == k]
        name = next(p["bettor_name"] for p in reversed(settled) if p["bettor_key"] == k)
        streaks.append((longest_win_streak(st), name))
    months: dict[tuple[str, str], float] = {}
    days: dict[tuple[str, str], int] = {}
    for p in settled:
        when = datetime.fromisoformat(p["settled_at"] or p["created_at"]).astimezone(TZ)
        months[(p["bettor_name"], when.strftime("%B %Y"))] = months.get((p["bettor_name"], when.strftime("%B %Y")), 0) + pick_net(p)
    for p in db().execute("SELECT * FROM picks WHERE guild_id = ?", (guild_id,)):
        d = datetime.fromisoformat(p["created_at"]).astimezone(TZ).strftime("%b %-d, %Y")
        days[(p["bettor_name"], d)] = days.get((p["bettor_name"], d), 0) + 1
    lines = [f"🚀 **Biggest hit:** {signed(pick_net(best))} · {best['bettor_name']} · {clip(best['description'], 50)}",
             f"🧊 **Worst beat:** {signed(pick_net(worst))} · {worst['bettor_name']} · {clip(worst['description'], 50)}"]
    if mult:
        lines.append(f"🎰 **Biggest multiplier:** {(mult['returned'] or 0) / mult['cost']:.1f}x · {mult['bettor_name']}")
    if biggest_parlay:
        lines.append(f"🧩 **Longest parlay hit:** {biggest_parlay[1]} legs · {biggest_parlay[0]['bettor_name']}")
    if streaks:
        s = max(streaks)
        lines.append(f"🔥 **Longest win streak:** {s[0]} · {s[1]}")
    if months:
        bm = max(months.items(), key=lambda kv: kv[1])
        wm = min(months.items(), key=lambda kv: kv[1])
        lines.append(f"📈 **Best month:** {signed(bm[1])} · {bm[0][0]} ({bm[0][1]})")
        lines.append(f"📉 **Worst month:** {signed(wm[1])} · {wm[0][0]} ({wm[0][1]})")
    if days:
        bd = max(days.items(), key=lambda kv: kv[1])
        lines.append(f"🗓️ **Most picks in a day:** {bd[1]} · {bd[0][0]} ({bd[0][1]})")
    beats = bad_beats(guild_id, limit=1)
    if beats:
        lines.append(f"💀 **Cruelest beat:** missed by {abs(beats[0]['margin']):g} · {beats[0]['bettor_name']} · "
                     f"{clip(beats[0]['text'], 50)}")
    e.description = "\n".join(lines)
    return e


# ---- money: deposits, withdrawals, tax summary ------------------------------------------------

def cash_rows(guild_id: int, user_id: int, year: Optional[int] = None) -> list:
    sql, args = "SELECT * FROM cashflows WHERE guild_id = ? AND user_id = ?", [guild_id, user_id]
    if year:
        sql += " AND created_at >= ? AND created_at < ?"
        args += [iso(datetime(year, 1, 1, tzinfo=TZ)), iso(datetime(year + 1, 1, 1, tzinfo=TZ))]
    return db().execute(sql + " ORDER BY created_at", args).fetchall()


def money_embed(guild_id: int, user_id: int, name: str) -> discord.Embed:
    rows = cash_rows(guild_id, user_id)
    plats: dict[str, dict] = {}
    for r in rows:
        d = plats.setdefault(r["platform"], {"in": 0.0, "out": 0.0})
        d["in" if r["kind"] == "deposit" else "out"] += r["amount"]
    picks = settled_picks(guild_id, str(user_id))
    pl: dict[str, float] = {}
    for p in picks:
        pl[p["platform"]] = pl.get(p["platform"], 0.0) + pick_net(p)
    e = discord.Embed(title=f"🏦 {name}'s money", color=BRAND)
    if not rows and not picks:
        e.description = "Nothing yet. Log money in and out with `/money deposit` and `/money withdraw`."
        return e
    tin = sum(d["in"] for d in plats.values())
    tout = sum(d["out"] for d in plats.values())
    e.description = (f"Deposited **{money(tin)}** · withdrew **{money(tout)}** · cash result **{signed(tout - tin)}**\n"
                     f"Picks tracked here: **{signed(sum(pl.values()))}**")
    for plat in sorted(set(plats) | set(pl)):
        d = plats.get(plat, {"in": 0.0, "out": 0.0})
        e.add_field(name=plat, value=f"In {money(d['in'])} · out {money(d['out'])}\nPicks {signed(pl.get(plat, 0.0))}")
    e.set_footer(text="Only you can see this. Cash result = withdrawn - deposited (what actually hit your bank).")
    return e


def tax_summary(guild_id: int, user_id: int, year: int) -> tuple[discord.Embed, io.BytesIO]:
    since, until = iso(datetime(year, 1, 1, tzinfo=TZ)), iso(datetime(year + 1, 1, 1, tzinfo=TZ))
    picks = db().execute("""SELECT * FROM picks WHERE guild_id = ? AND bettor_key = ? AND status != 'open'
                            AND settled_at >= ? AND settled_at < ? ORDER BY settled_at""",
                         (guild_id, str(user_id), since, until)).fetchall()
    plats: dict[str, dict] = {}
    for p in picks:
        d = plats.setdefault(p["platform"], {"won": 0.0, "lost": 0.0, "n": 0})
        net = pick_net(p)
        d["n"] += 1
        if net > 0:
            d["won"] += net
        elif net < 0:
            d["lost"] += -net
    cash = cash_rows(guild_id, user_id, year)
    e = discord.Embed(title=f"🧾 {year} summary for taxes", color=BRAND)
    tw = sum(d["won"] for d in plats.values())
    tl = sum(d["lost"] for d in plats.values())
    e.description = (f"Winning picks: **{money(tw)}** profit · losing picks: **{money(tl)}** lost · net **{signed(tw - tl)}**\n"
                     f"{len(picks)} settled picks in {year}.")
    for plat, d in sorted(plats.items()):
        e.add_field(name=plat, value=f"{d['n']} picks\nWon {money(d['won'])}\nLost {money(d['lost'])}")
    e.set_footer(text="From what's logged here, so it's only as complete as your logging. Not tax advice: "
                      "check your platforms' tax forms and a tax pro.")
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook()
    ws = wb.active
    ws.title = "Picks"
    ws.append(["Settled", "Platform", "Sport", "Description", "Cost", "Returned", "Net"])
    for c in ws[1]:
        c.font = Font(bold=True)
    for p in picks:
        ws.append([local_day(p["settled_at"] or p["created_at"]), p["platform"], p["sport"] or "", p["description"],
                   p["cost"], p["returned"] or 0.0, None])
        r = ws.max_row
        ws.cell(r, 7).value = f"=F{r}-E{r}"
    ws2 = wb.create_sheet("Deposits & withdrawals")
    ws2.append(["Date", "Platform", "Type", "Amount", "Note"])
    for c in ws2[1]:
        c.font = Font(bold=True)
    for r in cash:
        ws2.append([local_day(r["created_at"]), r["platform"], r["kind"], r["amount"], r["note"] or ""])
    ws3 = wb.create_sheet("Summary")
    ws3.append(["Platform", "Picks", "Won (profit on winners)", "Lost (stakes lost)", "Net"])
    for c in ws3[1]:
        c.font = Font(bold=True)
    for plat, d in sorted(plats.items()):
        ws3.append([plat, d["n"], round(d["won"], 2), round(d["lost"], 2), None])
        r = ws3.max_row
        ws3.cell(r, 5).value = f"=C{r}-D{r}"
    for sheet, widths in ((ws, (12, 12, 14, 48, 10, 10, 10)), (ws2, (12, 12, 12, 10, 30)), (ws3, (14, 8, 22, 18, 10))):
        for i, w in enumerate(widths):
            sheet.column_dimensions[chr(65 + i)].width = w
    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return e, out


# ---- hedge ---------------------------------------------------------------------------------

def hedge_embed(stake: float, payout: float, odds_text: str) -> discord.Embed:
    prob, kind = parse_odds(odds_text)
    dec, label = 1 / prob, f"{odds_text.strip()}"
    equal = payout / dec                     # same profit either way
    even = stake / (dec - 1)                 # get your stake back if the last leg loses
    e = discord.Embed(title="🛡️ Hedge calculator", color=BRAND,
                      description=f"Your bet: {money(stake)} to return **{money(payout)}**. Hedge at **{label}** "
                                  f"({dec:.3f} decimal).")
    def row(h):
        if_bet = payout - stake - h
        if_hedge = h * dec - stake - h
        return f"Bet **{money(h)}** on the other side\nIf your bet hits: {signed(if_bet)}\nIf the hedge hits: {signed(if_hedge)}"
    e.add_field(name="🟰 Lock the same profit", value=row(equal), inline=False)
    if even < equal:
        e.add_field(name="🛟 Just get your stake back", value=row(even), inline=False)
    e.add_field(name="🎲 No hedge", value=f"If your bet hits: {signed(payout - stake)}\nIf it misses: {signed(-stake)}",
                inline=False)
    e.set_footer(text="Math only, not advice. Hedging trades upside for certainty.")
    return e


def pp_calc_embed(guild_id: Optional[int], n: int, kind: str, entry: float, own_mult: Optional[float]) -> discord.Embed:
    power, flex = pp_tables(guild_id)
    e = discord.Embed(title=f"🧮 PrizePicks {n}-pick {kind.title()} Play · {money(entry)} entry", color=BRAND)
    lines = []
    if kind == "power":
        mult = own_mult or power.get(n)
        if not mult:
            e.description = f"No standard {n}-pick Power payout on file."
            return e
        lines.append(f"**{n}/{n}** hit → {mult:g}x = **{money(entry * mult)}**")
        lines.append(f"Anything less → $0")
        be = (1 / mult) ** (1 / n)
        lines.append(f"\nEach pick needs to hit about **{be * 100:.1f}%** of the time to break even.")
    else:
        table = dict(flex.get(n) or {})
        if own_mult:
            table[n] = own_mult
        if not table:
            e.description = f"No standard {n}-pick Flex payout on file (Flex starts at 3 picks)."
            return e
        for hits in sorted(table, reverse=True):
            lines.append(f"**{hits}/{n}** hit → {table[hits]:g}x = **{money(entry * table[hits])}**")
        lines.append("Fewer → $0")
        # break-even per-pick rate: solve sum C(n,k) p^k (1-p)^(n-k) mult_k = 1
        from math import comb
        def ev(pr):
            return sum(comb(n, k) * pr ** k * (1 - pr) ** (n - k) * m for k, m in table.items())
        lo, hi = 0.0, 1.0
        for _ in range(60):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if ev(mid) < 1 else (lo, mid)
        lines.append(f"\nEach pick needs to hit about **{hi * 100:.1f}%** of the time to break even.")
    e.description = "\n".join(lines)
    e.set_footer(text="Standard payouts; PrizePicks changes them and goblins/demons differ. Put your slip's "
                      "multiplier in `multiplier` to use it.")
    return e


class PPCalcView(discord.ui.View):
    def __init__(self, owner_id: int, guild_id: Optional[int], n: int, kind: str, entry: float, own: Optional[float]):
        super().__init__(timeout=900)
        self.owner_id, self.guild_id, self.n, self.kind, self.entry, self.own = owner_id, guild_id, n, kind, entry, own
        for k in range(2, 7):
            b = discord.ui.Button(label=f"{k}-pick", row=0, style=discord.ButtonStyle.primary if k == n
                                  else discord.ButtonStyle.secondary)
            b.callback = self._set(n=k)
            self.add_item(b)
        for kd in ("power", "flex"):
            b = discord.ui.Button(label=kd.title(), row=1, style=discord.ButtonStyle.success if kd == kind
                                  else discord.ButtonStyle.secondary)
            b.callback = self._set(kind=kd)
            self.add_item(b)

    def _set(self, n=None, kind=None):
        async def cb(interaction):
            if interaction.user.id != self.owner_id:
                await interaction.response.send_message("Run `/calc pp` yourself.", ephemeral=True)
                return
            nn, kk = n or self.n, kind or self.kind
            own = self.own if (nn == self.n and kk == self.kind) else None
            await interaction.response.edit_message(embed=pp_calc_embed(self.guild_id, nn, kk, self.entry, own),
                                                    view=PPCalcView(self.owner_id, self.guild_id, nn, kk, self.entry, own))
        return cb


# ---- PIMP Coins ----------------------------------------------------------------------------

COIN = "🪙"
START_COINS = 100
DAILY_COINS = 25
COIN_RULES = {"log": 5, "win": 10, "parlay": 25, "gp": 10, "potd": 15, "take": 20, "surv": 10, "pe": 5, "lock": 15}


def coin_balance(guild_id: int, user_id: int) -> int:
    ensure_wallet(guild_id, user_id)
    return int(db().execute("SELECT COALESCE(SUM(delta), 0) FROM coin_tx WHERE guild_id = ? AND user_id = ?",
                            (guild_id, user_id)).fetchone()[0])


def ensure_wallet(guild_id: int, user_id: int) -> None:
    db().execute("""INSERT OR IGNORE INTO coin_tx (guild_id, user_id, delta, reason, ref, created_at)
                    VALUES (?,?,?,?,?,?)""", (guild_id, user_id, START_COINS, "Welcome bonus", f"start:{user_id}", now_iso()))
    db().commit()


def award(guild_id: int, user_id: int, delta: int, reason: str, ref: Optional[str]) -> bool:
    """Add (or take) coins once per ref. Returns whether anything changed."""
    ensure_wallet(guild_id, user_id)
    cur = db().execute("""INSERT OR IGNORE INTO coin_tx (guild_id, user_id, delta, reason, ref, created_at)
                          VALUES (?,?,?,?,?,?)""", (guild_id, user_id, delta, reason, ref, now_iso()))
    db().commit()
    return cur.rowcount > 0


async def award_coins(client: discord.Client, now: Optional[datetime] = None) -> None:
    now = now or datetime.now(timezone.utc)
    since = iso(now - timedelta(days=3))
    for p in db().execute("SELECT * FROM picks WHERE created_at >= ? AND bettor_id IS NOT NULL AND import_key IS NULL",
                          (since,)).fetchall():
        day = datetime.fromisoformat(p["created_at"]).astimezone(TZ).date().isoformat()
        logged_today = db().execute("SELECT COUNT(*) FROM coin_tx WHERE guild_id = ? AND user_id = ? AND ref LIKE ?",
                                    (p["guild_id"], p["bettor_id"], f"log:{day}:%")).fetchone()[0]
        if logged_today < 3:
            award(p["guild_id"], p["bettor_id"], COIN_RULES["log"], "Logged a pick", f"log:{day}:{p['id']}")
    for p in db().execute("""SELECT * FROM picks WHERE status = 'win' AND settled_at >= ? AND bettor_id IS NOT NULL
                             AND import_key IS NULL""", (since,)).fetchall():
        award(p["guild_id"], p["bettor_id"], COIN_RULES["win"], f"Won pick #{p['id']}", f"win:{p['id']}")
        if len(get_legs(p["id"])) >= 3:
            award(p["guild_id"], p["bettor_id"], COIN_RULES["parlay"], f"Hit a parlay (#{p['id']})", f"parlay:{p['id']}")
    for x in db().execute("""SELECT l.*, r.guild_id FROM gp_legs l JOIN gp_rounds r ON r.id = l.round_id
                             WHERE l.status = 'hit' AND l.created_at >= ?""", (iso(now - timedelta(days=10)),)).fetchall():
        award(x["guild_id"], x["user_id"], COIN_RULES["gp"], "Group parlay leg hit", f"gp:{x['id']}")
    for lk in db().execute("SELECT * FROM locks WHERE status = 'win' AND settled_at >= ?", (since,)).fetchall():
        award(lk["guild_id"], lk["user_id"], COIN_RULES["lock"], "Lock of the week hit", f"lock:{lk['id']}")
    for r in db().execute("""SELECT pp.user_id, g.id AS gid, g.guild_id FROM pickem_picks pp JOIN pickem_games g ON g.id = pp.game_id
                             WHERE g.winner IS NOT NULL AND g.winner = pp.side AND g.start >= ?""", (since,)).fetchall():
        award(r["guild_id"], r["user_id"], COIN_RULES["pe"], "Pick'em pick right", f"pe:{r['gid']}:{r['user_id']}")
    for r in db().execute("""SELECT s.*, p.guild_id FROM survivor_picks s JOIN survivor_pools p ON p.id = s.pool_id
                             WHERE s.result = 'win' AND s.start >= ?""", (iso(now - timedelta(days=10)),)).fetchall():
        award(r["guild_id"], r["user_id"], COIN_RULES["surv"], "Survived a survivor week",
              f"surv:{r['pool_id']}:{r['user_id']}:{r['week_key']}")


def coins_top(guild_id: int, limit: int = 15) -> list:
    return db().execute("""SELECT user_id, SUM(delta) AS bal FROM coin_tx WHERE guild_id = ? GROUP BY user_id
                           ORDER BY bal DESC LIMIT ?""", (guild_id, limit)).fetchall()


# ---- coin markets (parimutuel: the losing side's coins are split among the winners) ----------

MARKET_BETS = (10, 50)


def get_market(mid: int):
    return db().execute("SELECT * FROM markets WHERE id = ?", (mid,)).fetchone()


def market_pools(mid: int) -> dict[str, int]:
    out = {"yes": 0, "no": 0}
    for r in db().execute("SELECT side, SUM(amount) AS a FROM market_bets WHERE market_id = ? GROUP BY side", (mid,)):
        out[r["side"]] = int(r["a"])
    return out


def market_open(m, now: Optional[datetime] = None) -> bool:
    now = now or datetime.now(timezone.utc)
    return m["status"] == "open" and (not m["closes_at"] or datetime.fromisoformat(m["closes_at"]) > now)


def market_embed(m) -> discord.Embed:
    pools = market_pools(m["id"])
    total = pools["yes"] + pools["no"]
    yes_pct = pools["yes"] / total * 100 if total else 50
    bar_n = int(round(yes_pct / 10))
    color = {"resolved": 0x2ECC71, "void": 0x95A5A6}.get(m["status"], BRAND)
    e = discord.Embed(title=clip(f"🎲 {m['question']}", 256), color=color)
    lines = [f"**YES** {COIN}{pools['yes']:,} · **NO** {COIN}{pools['no']:,}",
             "🟩" * bar_n + "🟥" * (10 - bar_n) + f"  {yes_pct:.0f}% of coins on YES"]
    if m["status"] == "resolved":
        lines.insert(0, f"✅ Resolved **{m['outcome'].upper()}**. Winners split the pot.")
    elif m["status"] == "void":
        lines.insert(0, "↩️ Voided. Everyone got their coins back.")
    elif not market_open(m):
        lines.insert(0, "🔒 Betting's closed. Waiting on the result.")
    elif m["closes_at"]:
        lines.append(f"Closes <t:{int(datetime.fromisoformat(m['closes_at']).timestamp())}:R>")
    backers = db().execute("""SELECT user_name, side, SUM(amount) AS a FROM market_bets WHERE market_id = ?
                              GROUP BY user_id, side ORDER BY a DESC LIMIT 8""", (m["id"],)).fetchall()
    e.description = "\n".join(lines)
    if backers:
        e.add_field(name="Biggest bets", value="\n".join(f"{r['user_name']} · {r['side'].upper()} {COIN}{r['a']:,}"
                                                         for r in backers))
    e.set_footer(text=f"Market #{m['id']} · play money only · winners get their stake back plus a share of the losing pot")
    return e


class MarketButton(discord.ui.DynamicItem[discord.ui.Button],
                   template=r"mk:(?P<mid>\d+):(?P<act>yes10|yes50|no10|no50|custom|resolve)"):
    LOOK = {"yes10": (f"YES {COIN}10", discord.ButtonStyle.success), "yes50": (f"YES {COIN}50", discord.ButtonStyle.success),
            "no10": (f"NO {COIN}10", discord.ButtonStyle.danger), "no50": (f"NO {COIN}50", discord.ButtonStyle.danger),
            "custom": ("Other amount", discord.ButtonStyle.secondary), "resolve": ("Resolve", discord.ButtonStyle.secondary)}

    def __init__(self, mid: int, act: str):
        label, style = self.LOOK[act]
        super().__init__(discord.ui.Button(label=label, style=style, custom_id=f"mk:{mid}:{act}",
                                           row=0 if act[:2] in ("ye", "no") else 1))
        self.mid, self.act = mid, act

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(int(match["mid"]), match["act"])

    async def callback(self, interaction: discord.Interaction):
        m = get_market(self.mid)
        if m is None:
            await interaction.response.send_message("That market's gone.", ephemeral=True)
            return
        if self.act == "resolve":
            if interaction.user.id != m["creator_id"] and not is_mod(interaction.user):
                await interaction.response.send_message("Only whoever made it (or a mod) can resolve it.", ephemeral=True)
                return
            if m["status"] in ("resolved", "void"):
                await interaction.response.send_message("Already settled.", ephemeral=True)
                return
            await interaction.response.send_message("How did it end?", view=ResolveView(self.mid, interaction.message),
                                                    ephemeral=True)
            return
        if not market_open(m):
            await interaction.response.send_message("Betting's closed on this one.", ephemeral=True)
            return
        if self.act == "custom":
            await interaction.response.send_modal(MarketBetModal(self.mid))
            return
        amount = int(self.act[-2:])
        side = "yes" if self.act.startswith("yes") else "no"
        await place_market_bet(interaction, m, side, amount, edit=True)


async def place_market_bet(interaction: discord.Interaction, m, side: str, amount: int, edit: bool):
    bal = coin_balance(interaction.guild_id, interaction.user.id)
    if amount <= 0 or amount > bal:
        await interaction.response.send_message(f"You've got {COIN}{bal:,}. Earn more with `/coins daily` and by "
                                                "hitting picks.", ephemeral=True)
        return
    other = db().execute("SELECT 1 FROM market_bets WHERE market_id = ? AND user_id = ? AND side != ?",
                         (m["id"], interaction.user.id, side)).fetchone()
    if other:
        await interaction.response.send_message("You're already on the other side of this one.", ephemeral=True)
        return
    cur = db().execute("INSERT INTO market_bets (market_id, user_id, user_name, side, amount, created_at) VALUES (?,?,?,?,?,?)",
                       (m["id"], interaction.user.id, interaction.user.display_name, side, amount, now_iso()))
    db().commit()
    award(interaction.guild_id, interaction.user.id, -amount, f"Bet on market #{m['id']}", f"mkbet:{cur.lastrowid}")
    if edit and interaction.message is not None:
        await interaction.response.edit_message(embed=market_embed(get_market(m["id"])), view=market_view(m["id"]))
    else:
        await interaction.response.send_message(f"{COIN}{amount} on **{side.upper()}**. Good luck.", ephemeral=True)
        await refresh_market_message(interaction.client, m["id"])


class MarketBetModal(discord.ui.Modal, title="Place a bet"):
    side = discord.ui.TextInput(label="YES or NO", max_length=3)
    amount = discord.ui.TextInput(label="Coins", max_length=7)

    def __init__(self, mid: int):
        super().__init__()
        self.mid = mid

    async def on_submit(self, interaction: discord.Interaction):
        side = self.side.value.strip().lower()
        try:
            amount = int(self.amount.value.strip().replace(",", ""))
        except ValueError:
            amount = 0
        if side not in ("yes", "no") or amount <= 0:
            await interaction.response.send_message("Type YES or NO and a whole number of coins.", ephemeral=True)
            return
        m = get_market(self.mid)
        if m is None or not market_open(m):
            await interaction.response.send_message("Betting's closed on this one.", ephemeral=True)
            return
        await place_market_bet(interaction, m, side, amount, edit=interaction.message is not None)


class ResolveView(discord.ui.View):
    def __init__(self, mid: int, board):
        super().__init__(timeout=300)
        self.mid, self.board = mid, board
        for out, style in (("yes", discord.ButtonStyle.success), ("no", discord.ButtonStyle.danger),
                           ("void", discord.ButtonStyle.secondary)):
            b = discord.ui.Button(label={"void": "Void (refund)"}.get(out, out.upper()), style=style)
            b.callback = self._cb(out)
            self.add_item(b)

    def _cb(self, out):
        async def cb(interaction):
            msg = resolve_market(self.mid, out)
            await interaction.response.edit_message(content=msg, view=None)
            await refresh_market_message(interaction.client, self.mid)
            m = get_market(self.mid)
            channel = interaction.client.get_channel(m["channel_id"]) if m["channel_id"] else None
            if channel is not None:
                await channel.send(f"🎲 Market #{m['id']} **{clip(m['question'], 100)}**: {msg}",
                                   allowed_mentions=discord.AllowedMentions.none())
        return cb


def resolve_market(mid: int, outcome: str) -> str:
    m = get_market(mid)
    if m["status"] in ("resolved", "void"):
        return "Already settled."
    bets = db().execute("SELECT * FROM market_bets WHERE market_id = ?", (mid,)).fetchall()
    pools = market_pools(mid)
    winners = [b for b in bets if b["side"] == outcome]
    if outcome == "void" or not winners:
        for b in bets:
            award(m["guild_id"], b["user_id"], b["amount"], f"Refund, market #{mid}", f"mkref:{b['id']}")
        db().execute("UPDATE markets SET status = 'void', outcome = ? WHERE id = ?", (outcome, mid))
        db().commit()
        return "Voided, everyone got their coins back." if outcome == "void" else \
            f"Resolved {outcome.upper()}, but nobody was on it, so everyone got refunded."
    losers_pot = pools["no" if outcome == "yes" else "yes"]
    win_pot = pools[outcome]
    paid = []
    for b in winners:
        share = b["amount"] + int(losers_pot * b["amount"] / win_pot)
        award(m["guild_id"], b["user_id"], share, f"Won market #{mid}", f"mkwin:{b['id']}")
        paid.append((b["user_name"], share))
    db().execute("UPDATE markets SET status = 'resolved', outcome = ? WHERE id = ?", (outcome, mid))
    db().commit()
    top = sorted(paid, key=lambda x: -x[1])[:5]
    return f"Resolved **{outcome.upper()}**. Paid out: " + ", ".join(f"{n} {COIN}{a:,}" for n, a in top)


def market_view(mid: int) -> Optional[discord.ui.View]:
    m = get_market(mid)
    v = discord.ui.View(timeout=None)
    if m["status"] in ("resolved", "void"):
        return None
    if market_open(m):
        for act in ("yes10", "yes50", "no10", "no50", "custom"):
            v.add_item(MarketButton(mid, act))
    v.add_item(MarketButton(mid, "resolve"))
    return v


async def refresh_market_message(client, mid: int) -> None:
    m = get_market(mid)
    channel = client.get_channel(m["channel_id"]) if m and m["channel_id"] else None
    if channel is None or not m["message_id"]:
        return
    try:
        await channel.get_partial_message(m["message_id"]).edit(embed=market_embed(m), view=market_view(mid))
    except Exception:
        pass


async def close_markets(client: discord.Client, now: Optional[datetime] = None) -> None:
    now = now or datetime.now(timezone.utc)
    for m in db().execute("SELECT * FROM markets WHERE status = 'open' AND closes_at IS NOT NULL AND closes_at <= ?",
                          (iso(now),)).fetchall():
        db().execute("UPDATE markets SET status = 'closed' WHERE id = ?", (m["id"],))
        db().commit()
        await refresh_market_message(client, m["id"])
        channel = client.get_channel(m["channel_id"]) if m["channel_id"] else None
        if channel is not None:
            await channel.send(f"🔒 Betting's closed on market #{m['id']}: **{clip(m['question'], 120)}**. "
                               f"<@{m['creator_id']}>, tap **Resolve** on it once you know the answer.",
                               allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=True))


# ---- hot takes -------------------------------------------------------------------------------

MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


def parse_due(text: str, now: Optional[datetime] = None) -> Optional[datetime]:
    """parse_when, plus '3 weeks', '2 months', 'jan 15', '2027-01-15', 'end of season'-style dates up to 1 year."""
    now = (now or datetime.now(TZ)).astimezone(TZ)
    t = " ".join((text or "").lower().replace(",", " ").split())
    m = re.fullmatch(r"(?:in\s+)?(\d+)\s*(w|wk|wks|week|weeks|mo|mos|month|months)", t)
    if m:
        n = int(m.group(1))
        when = now + (timedelta(weeks=n) if m.group(2).startswith("w") else timedelta(days=30 * n))
        return when if when <= now + timedelta(days=366) else None
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", t)
    if m:
        try:
            when = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), 12, tzinfo=TZ)
        except ValueError:
            return None
        return when if now < when <= now + timedelta(days=366) else None
    m = re.fullmatch(r"([a-z]{3})[a-z]*\.?\s+(\d{1,2})", t)
    if m and m.group(1) in MONTHS:
        mon, day = MONTHS.index(m.group(1)) + 1, int(m.group(2))
        try:
            when = datetime(now.year, mon, day, 12, tzinfo=TZ)
            if when <= now:
                when = when.replace(year=now.year + 1)
        except ValueError:
            return None
        return when
    return parse_when(text, now)


def take_embed(t) -> discord.Embed:
    votes = {r["vote"]: r["n"] for r in db().execute(
        "SELECT vote, COUNT(*) AS n FROM take_votes WHERE take_id = ? GROUP BY vote", (t["id"],))}
    status = {"right": "✅ Called it", "wrong": "❌ Missed", "open": "⏳ Pending"}[t["status"]]
    e = discord.Embed(title=f"🔥 Hot take from {t['user_name']}", color={"right": 0x2ECC71, "wrong": 0xE74C3C}.get(
        t["status"], 0xE67E22), description=f"> {clip(t['text'], 900)}")
    e.add_field(name="Status", value=status)
    if t["due_at"] and t["status"] == "open":
        e.add_field(name="Gets graded", value=f"<t:{int(datetime.fromisoformat(t['due_at']).timestamp())}:D>")
    e.add_field(name="The crowd", value=f"🔥 {votes.get('agree', 0)} agree · 🧊 {votes.get('fade', 0)} fade")
    rec = takes_record(t["guild_id"], t["user_id"])
    e.set_footer(text=f"Take #{t['id']} · {t['user_name']} is {rec} on takes")
    return e


def takes_record(guild_id: int, user_id: int) -> str:
    rows = db().execute("SELECT status FROM takes WHERE guild_id = ? AND user_id = ?", (guild_id, user_id)).fetchall()
    r = sum(1 for x in rows if x["status"] == "right")
    w = sum(1 for x in rows if x["status"] == "wrong")
    return f"{r}-{w}"


class TakeButton(discord.ui.DynamicItem[discord.ui.Button], template=r"tk:(?P<tid>\d+):(?P<act>agree|fade|right|wrong)"):
    LOOK = {"agree": ("🔥 Agree", discord.ButtonStyle.secondary), "fade": ("🧊 Fade", discord.ButtonStyle.secondary),
            "right": ("✅ Called it", discord.ButtonStyle.success), "wrong": ("❌ Missed", discord.ButtonStyle.danger)}

    def __init__(self, tid: int, act: str):
        label, style = self.LOOK[act]
        super().__init__(discord.ui.Button(label=label, style=style, custom_id=f"tk:{tid}:{act}"))
        self.tid, self.act = tid, act

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(int(match["tid"]), match["act"])

    async def callback(self, interaction: discord.Interaction):
        t = db().execute("SELECT * FROM takes WHERE id = ?", (self.tid,)).fetchone()
        if t is None:
            await interaction.response.send_message("That take is gone.", ephemeral=True)
            return
        if self.act in ("agree", "fade"):
            if t["status"] != "open":
                await interaction.response.send_message("Already graded.", ephemeral=True)
                return
            if interaction.user.id == t["user_id"]:
                await interaction.response.send_message("We know you agree with yourself.", ephemeral=True)
                return
            db().execute("INSERT OR REPLACE INTO take_votes (take_id, user_id, vote) VALUES (?,?,?)",
                         (t["id"], interaction.user.id, self.act))
            db().commit()
            await interaction.response.edit_message(embed=take_embed(t), view=take_view(t))
            return
        if interaction.user.id != t["user_id"] and not is_mod(interaction.user):
            await interaction.response.send_message("Only whoever made the take (or a mod) grades it.", ephemeral=True)
            return
        status = "right" if self.act == "right" else "wrong"
        db().execute("UPDATE takes SET status = ?, graded_at = ? WHERE id = ?", (status, now_iso(), t["id"]))
        db().commit()
        if status == "right":
            award(t["guild_id"], t["user_id"], COIN_RULES["take"], f"Called take #{t['id']}", f"take:{t['id']}")
        t = db().execute("SELECT * FROM takes WHERE id = ?", (self.tid,)).fetchone()
        await interaction.response.edit_message(embed=take_embed(t), view=None)


def take_view(t, grading: bool = False) -> Optional[discord.ui.View]:
    if t["status"] != "open":
        return None
    v = discord.ui.View(timeout=None)
    for act in (("agree", "fade", "right", "wrong") if grading else ("agree", "fade")):
        v.add_item(TakeButton(t["id"], act))
    return v


async def takes_due(client: discord.Client, now: Optional[datetime] = None) -> None:
    now = now or datetime.now(timezone.utc)
    for t in db().execute("SELECT * FROM takes WHERE status = 'open' AND due_at <= ? AND nudged_at IS NULL",
                          (iso(now),)).fetchall():
        db().execute("UPDATE takes SET nudged_at = ? WHERE id = ?", (now_iso(), t["id"]))
        db().commit()
        channel = client.get_channel(t["channel_id"]) if t["channel_id"] else None
        channel = channel or await recap_channel_for(client, t["guild_id"])
        if channel is not None:
            await channel.send(f"⏰ <@{t['user_id']}>, time to face the music on your take:", embed=take_embed(t),
                               view=take_view(t, grading=True),
                               allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=True))


# ---- prop of the day ------------------------------------------------------------------------

LEADER_STATS = {  # (sport path family, ESPN leader category) -> stat key
    ("basketball", "points"): "points", ("basketball", "pointsPerGame"): "points",
    ("basketball", "rebounds"): "rebounds", ("basketball", "reboundsPerGame"): "rebounds",
    ("basketball", "assists"): "assists", ("basketball", "assistsPerGame"): "assists",
    ("football", "passingYards"): "pass_yds", ("football", "rushingYards"): "rush_yds",
    ("football", "receivingYards"): "rec_yds", ("hockey", "points"): "nhl_points", ("hockey", "goals"): "sog",
    ("baseball", "homeRuns"): "hits", ("baseball", "avg"): "hits", ("baseball", "battingAverage"): "hits",
}


def potd_line(values: list[float]) -> float:
    if not values:
        return 0.5
    s = sorted(values)
    mid = s[len(s) // 2] if len(s) % 2 else (s[len(s) // 2 - 1] + s[len(s) // 2]) / 2
    return float(int(mid)) + 0.5


async def potd_candidates(guild_id: int, now: datetime) -> list[dict]:
    out = []
    for path in [p for p in group_leagues(guild_id) if p in PROP_PATHS]:
        for ev in await fetch_scoreboard(path, now.astimezone(TZ)):
            start = event_time(ev)
            if ev.get("state") != "pre" or not start or start < now + timedelta(minutes=45):
                continue
            if start.astimezone(TZ).date() != now.astimezone(TZ).date():
                continue
            for ld in ev.get("leaders") or []:
                key = LEADER_STATS.get((FAMILY_OF_PATH[path], ld["category"]))
                if key:
                    out.append({"path": path, "event": ev, "athlete_id": ld["athlete_id"], "name": ld["name"],
                                "stat_key": key})
    return out


def potd_embed(pd) -> discord.Embed:
    votes = {r["side"]: r["n"] for r in db().execute(
        "SELECT side, COUNT(*) AS n FROM potd_votes WHERE potd_id = ? GROUP BY side", (pd["id"],))}
    label = STATS[pd["stat_key"]][0]
    e = discord.Embed(title=f"🎯 Prop of the Day · {pd['player']}", color=BRAND,
                      description=f"# {label} · {pd['line']:g}\nMore or less? Lock it in before tip/kickoff.")
    start = datetime.fromisoformat(pd["start"])
    e.add_field(name="Game", value=f"{pd['game']} · <t:{int(start.timestamp())}:t>")
    e.add_field(name="Votes", value=f"📈 More {votes.get('over', 0)} · 📉 Less {votes.get('under', 0)}")
    if pd["trend"]:
        e.add_field(name="Last 10", value=pd["trend"], inline=False)
    if pd["result"]:
        word = {"over": "MORE ✅", "under": "LESS ✅", "push": "PUSH ➖"}[pd["result"]]
        e.add_field(name="Result", value=f"{pd['player']} had **{pd['value']:g}** → **{word}**", inline=False)
        e.color = 0x2ECC71
    e.set_footer(text="Right answers earn 🪙15 · /potd standings for the leaderboard")
    return e


class PotdButton(discord.ui.DynamicItem[discord.ui.Button], template=r"pd:(?P<pid>\d+):(?P<side>over|under)"):
    def __init__(self, pid: int, side: str):
        super().__init__(discord.ui.Button(label="📈 More" if side == "over" else "📉 Less",
                                           style=discord.ButtonStyle.success if side == "over" else discord.ButtonStyle.danger,
                                           custom_id=f"pd:{pid}:{side}"))
        self.pid, self.side = pid, side

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(int(match["pid"]), match["side"])

    async def callback(self, interaction: discord.Interaction):
        pd = db().execute("SELECT * FROM potd WHERE id = ?", (self.pid,)).fetchone()
        if pd is None or pd["result"] or datetime.fromisoformat(pd["start"]) <= datetime.now(timezone.utc):
            await interaction.response.send_message("Votes are locked: the game's started.", ephemeral=True)
            return
        db().execute("INSERT OR REPLACE INTO potd_votes (potd_id, user_id, user_name, side) VALUES (?,?,?,?)",
                     (pd["id"], interaction.user.id, interaction.user.display_name, self.side))
        db().commit()
        await interaction.response.edit_message(embed=potd_embed(pd), view=potd_view(pd["id"]))


def potd_view(pid: int) -> discord.ui.View:
    v = discord.ui.View(timeout=None)
    v.add_item(PotdButton(pid, "over"))
    v.add_item(PotdButton(pid, "under"))
    return v


async def create_potd(guild_id: int, channel, now: datetime, cand: dict, line: Optional[float] = None):
    values = []
    try:
        games = await trend_games(cand["path"], cand["athlete_id"], need=10)
        values = [v for _, v in trend_values(games, cand["stat_key"])[:10]]
    except Exception:
        log.warning("POTD game log failed")
    use = line if line is not None else potd_line(values)
    trend = ""
    if values:
        o = sum(1 for v in values if v > use)
        trend = f"Over {use:g} in {o} of {len(values)} · avg {sum(values) / len(values):.1f}"
    ev = cand["event"]
    away = next(t for t in ev["teams"] if not t["home"])["short"]
    home = next(t for t in ev["teams"] if t["home"])["short"]
    cur = db().execute("""INSERT INTO potd (guild_id, day, player, athlete_id, path, stat_key, line, event_id, start, game,
                          trend, channel_id, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                       (guild_id, now.astimezone(TZ).date().isoformat(), cand["name"], cand["athlete_id"], cand["path"],
                        cand["stat_key"], use, ev["id"], iso(event_time(ev)), f"{away} @ {home}", trend,
                        channel.id if channel else None, now_iso()))
    db().commit()
    pd = db().execute("SELECT * FROM potd WHERE id = ?", (cur.lastrowid,)).fetchone()
    if channel is not None:
        msg = await channel.send(embed=potd_embed(pd), view=potd_view(pd["id"]))
        db().execute("UPDATE potd SET message_id = ? WHERE id = ?", (msg.id, pd["id"]))
        db().commit()
    return pd


async def post_potd(client: discord.Client, now: Optional[datetime] = None) -> None:
    now = (now or datetime.now(TZ)).astimezone(TZ)
    if now.hour < TODAY_HOUR:
        return
    import random
    for r in db().execute("SELECT guild_id, value FROM settings WHERE key = 'potd_channel'").fetchall():
        gid, day = r["guild_id"], now.date().isoformat()
        if get_setting(gid, "last_potd") == day:
            continue
        set_setting(gid, "last_potd", day)
        channel = client.get_channel(int(r["value"]))
        cands = await potd_candidates(gid, now.astimezone(timezone.utc))
        if not cands or channel is None:
            continue
        rng = random.Random(f"{gid}:{day}")
        await create_potd(gid, channel, now.astimezone(timezone.utc), rng.choice(cands))


async def grade_potd(client: discord.Client, now: Optional[datetime] = None) -> None:
    now = now or datetime.now(timezone.utc)
    for pd in db().execute("SELECT * FROM potd WHERE result IS NULL AND start <= ?", (iso(now),)).fetchall():
        leg = {"player": norm_name(pd["player"]), "stats": [pd["stat_key"]], "side": "over", "line": pd["line"],
               "negate": False}
        try:
            st = await prop_status(leg, [pd["path"]], datetime.fromisoformat(pd["start"]) - timedelta(hours=1))
        except Exception:
            continue
        if not st or st["state"] != "post" or st["value"] is None:
            if st and st["state"] == "post" and st["result"] == "push" and st["value"] is None:   # didn't play
                db().execute("UPDATE potd SET result = 'push', value = 0 WHERE id = ?", (pd["id"],))
                db().commit()
            continue
        v = st["value"]
        result = "push" if v == pd["line"] else ("over" if v > pd["line"] else "under")
        db().execute("UPDATE potd SET result = ?, value = ? WHERE id = ?", (result, v, pd["id"]))
        db().commit()
        right = [r for r in db().execute("SELECT * FROM potd_votes WHERE potd_id = ?", (pd["id"],)) if r["side"] == result]
        for r in right:
            award(pd["guild_id"], r["user_id"], COIN_RULES["potd"], "Prop of the Day", f"potd:{pd['id']}:{r['user_id']}")
        pd = db().execute("SELECT * FROM potd WHERE id = ?", (pd["id"],)).fetchone()
        channel = client.get_channel(pd["channel_id"]) if pd["channel_id"] else None
        if channel is None:
            continue
        if pd["message_id"]:
            try:
                await channel.get_partial_message(pd["message_id"]).edit(embed=potd_embed(pd), view=None)
            except Exception:
                pass
        total = db().execute("SELECT COUNT(*) FROM potd_votes WHERE potd_id = ?", (pd["id"],)).fetchone()[0]
        word = {"over": "MORE", "under": "LESS", "push": "a PUSH"}[result]
        await channel.send(f"🎯 Prop of the Day: {pd['player']} had **{v:g}** {STATS[pd['stat_key']][0]} "
                           f"(line {pd['line']:g}) → **{word}**. {len(right)} of {total} got it"
                           + (": " + ", ".join(r["user_name"] for r in right[:10]) if right else "") + ".",
                           allowed_mentions=discord.AllowedMentions.none())


def potd_standings(guild_id: int) -> list[tuple[str, int, int]]:
    rows = db().execute("""SELECT v.user_name, v.side, p.result FROM potd_votes v JOIN potd p ON p.id = v.potd_id
                           WHERE p.guild_id = ? AND p.result IN ('over', 'under')""", (guild_id,)).fetchall()
    rec: dict[str, list[int]] = {}
    for r in rows:
        x = rec.setdefault(r["user_name"], [0, 0])
        x[0 if r["side"] == r["result"] else 1] += 1
    return sorted(((n, w, l) for n, (w, l) in rec.items()), key=lambda t: (t[1] / max(1, t[1] + t[2]), t[1]), reverse=True)


# ---- hidden picks ---------------------------------------------------------------------------

async def reveal_hidden(client: discord.Client, now: Optional[datetime] = None) -> None:
    for p in db().execute("""SELECT * FROM picks WHERE hidden = 1 AND status != 'open' AND revealed_at IS NULL""").fetchall():
        db().execute("UPDATE picks SET revealed_at = ? WHERE id = ?", (now_iso(), p["id"]))
        db().commit()
        channel = await recap_channel_for(client, p["guild_id"])
        if channel is None:
            continue
        locked = local_day(p["created_at"]) + datetime.fromisoformat(p["created_at"]).astimezone(TZ).strftime(" %-I:%M %p")
        await channel.send(f"🔓 **Revealed:** {p['bettor_name']}'s hidden pick `#{p['id']}`, locked in {locked}.",
                           embed=pick_embed(p), allowed_mentions=discord.AllowedMentions.none())


def private_card(p) -> discord.Embed:
    """The owner's own view of a hidden pick."""
    e = pick_embed(dict(p) | {"hidden": 0})
    e.set_author(name="🔒 Hidden from everyone else until it settles")
    return e


# ---- logging from a DM ------------------------------------------------------------------------

def home_guild_for(client: discord.Client, user) -> Optional[int]:
    if GUILD_ID:
        return int(GUILD_ID)
    mutual = list(getattr(user, "mutual_guilds", None) or [])
    return mutual[0].id if mutual else None


async def handle_dm_slip(client: discord.Client, message: discord.Message, attachment: discord.Attachment) -> None:
    gid = home_guild_for(client, message.author)
    if gid is None:
        await message.reply("I don't share a server with you, so I can't log that.")
        return
    if not ai_enabled():
        await message.reply("Reading slips needs the Claude key, which isn't set up. In the server, use "
                            "`/pick` with `hidden: True` to log it privately.")
        return
    try:
        slip = await read_slip(attachment)
    except Exception:
        log.exception("DM slip read failed")
        slip = None
    if slip is None or slip.get("cost") is None:
        await message.reply("I couldn't read that one. Try a clearer screenshot, or use `/pick hidden:True` in the server.")
        return
    legs = [str(x).strip() for x in (slip.get("legs") or []) if str(x).strip()]
    pid = insert_pick(guild_id=gid, bettor_key=str(message.author.id), bettor_name=message.author.display_name,
                      bettor_id=message.author.id, logged_by=message.author.id,
                      platform=str(slip.get("platform") or "Other")[:40],
                      sport=(str(slip["sport"])[:60] if slip.get("sport") else None),
                      description=str(slip.get("description") or "Slip")[:200], legs="\n".join(legs) or None,
                      cost=slip["cost"], payout=slip["payout"] or 0.0)
    db().execute("UPDATE picks SET hidden = 1 WHERE id = ?", (pid,))
    db().commit()
    if slip["status"] != "open":
        settle_pick(gid, pid, slip["status"], slip["returned"])
    p = get_pick(gid, pid)
    await message.reply(f"🔒 Logged privately as pick `#{pid}`. Nobody sees the details until it settles, then it's "
                        "revealed with the result. I'll grade it like any other pick.", embed=private_card(p))


# ---- right-click menus -------------------------------------------------------------------------

def pick_from_message(guild_id: int, message) -> Optional[sqlite3.Row]:
    for e in getattr(message, "embeds", None) or []:
        m = re.match(r"^(?:Pick|🥵 Sweat · Pick) #(\d+)", e.title or "")
        if m:
            return get_pick(guild_id, int(m.group(1)))
    url = getattr(message, "jump_url", None)
    if url:
        return db().execute("SELECT * FROM picks WHERE guild_id = ? AND slip_url = ? ORDER BY id DESC LIMIT 1",
                            (guild_id, url)).fetchone()
    return None


async def log_message_as_pick(interaction: discord.Interaction, message: discord.Message):
    images = [a for a in getattr(message, "attachments", []) or []
              if (a.content_type or "").split(";")[0].strip() in IMAGE_TYPES]
    mine = message.author.id == interaction.user.id
    if not images:
        if not mine:
            await interaction.response.send_message("That only works on slip screenshots, or on your own messages.",
                                                    ephemeral=True)
            return
        modal = SlipModal(message.jump_url)
        modal.description.default = clip(message.content or "", 200) or None
        await interaction.response.send_modal(modal)
        return
    existing = db().execute("SELECT id FROM picks WHERE guild_id = ? AND slip_url = ?",
                            (interaction.guild_id, message.jump_url)).fetchone()
    if existing:
        await interaction.response.send_message(f"That slip is already pick `#{existing['id']}`.", ephemeral=True)
        return
    if not ai_enabled():
        if not mine:
            await interaction.response.send_message("Reading slips needs the Claude key. Ask them to log it.", ephemeral=True)
            return
        await interaction.response.send_modal(SlipModal(message.jump_url))
        return
    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        slip = await read_slip(images[0])
    except Exception:
        log.exception("Context-menu slip read failed")
        slip = None
    if slip is None or slip.get("cost") is None:
        await interaction.followup.send("I couldn't read that one cleanly. They can log it with `/pick`.", ephemeral=True)
        return
    legs = [str(x).strip() for x in (slip.get("legs") or []) if str(x).strip()]
    pid = insert_pick(guild_id=interaction.guild_id, bettor_key=str(message.author.id),
                      bettor_name=message.author.display_name, bettor_id=message.author.id,
                      logged_by=interaction.user.id, platform=str(slip.get("platform") or "Other")[:40],
                      sport=(str(slip["sport"])[:60] if slip.get("sport") else None),
                      description=str(slip.get("description") or "Slip")[:200], legs="\n".join(legs) or None,
                      cost=slip["cost"], payout=slip["payout"] or 0.0, slip_url=message.jump_url)
    if slip["status"] != "open":
        settle_pick(interaction.guild_id, pid, slip["status"], slip["returned"])
    p = get_pick(interaction.guild_id, pid)
    await interaction.followup.send(f"Logged as pick `#{pid}` for {message.author.display_name}.", ephemeral=True)
    await message.reply(embed=pick_embed(p), view=settle_view(pid) if p["status"] == "open" else None,
                        mention_author=False)


async def copy_from_message(interaction: discord.Interaction, message: discord.Message):
    p = pick_from_message(interaction.guild_id, message)
    if p is None:
        await interaction.response.send_message("I can't find a pick on that message.", ephemeral=True)
        return
    if p["status"] != "open" or p["hidden"]:
        await interaction.response.send_message("That pick can't be copied right now.", ephemeral=True)
        return
    if str(interaction.user.id) == p["bettor_key"]:
        await interaction.response.send_message("That's already your pick.", ephemeral=True)
        return
    await interaction.response.send_modal(CopyModal(p))


# ---- player research: averages, history vs a team, back-to-backs ----------------------------------

MAIN_STATS = {"basketball": ["points", "rebounds", "assists", "pra", "threes", "stocks", "turnovers"],
              "football": ["pass_yds", "pass_td", "rush_yds", "rec", "rec_yds", "rush_rec_yds", "anytime_td"],
              "baseball": ["hits", "hrr", "home_runs", "pitcher_k", "pitching_outs", "earned_runs"],
              "hockey": ["goals", "nhl_assists", "nhl_points", "sog", "saves"]}
B2B_PATHS = ("basketball/nba", "basketball/wnba", "hockey/nhl", "basketball/mens-college-basketball")


def avg_embed(cand: dict, games: list[dict]) -> discord.Embed:
    fam = FAMILY_OF_PATH[cand["path"]]
    e = discord.Embed(title=f"📊 {cand['name']} · averages", color=BRAND,
                      description=(cand["team"] or "") + f"\n{len(games)} games on file (preseason left out)")
    rows = []
    for k in MAIN_STATS[fam]:
        vals = [v for _, v in trend_values(games, k)]
        if not vals or not any(vals):
            continue
        def avg(n):
            part = vals[:n]
            return f"{sum(part) / len(part):.1f}" if part else "-"
        rows.append(f"**{STATS[k][0]}** · L5 {avg(5)} · L10 {avg(10)} · all {avg(len(vals))}")
    e.add_field(name="Stat · last 5 · last 10 · everything on file", value="\n".join(rows) or "No stats yet.", inline=False)
    if games:
        g = games[0]
        when = datetime.fromisoformat(g["date"].replace("Z", "+00:00")).astimezone(TZ).strftime("%b %-d") if g["date"] else ""
        e.set_footer(text=f"Last game: {when} {'@' if g['at'] == '@' else 'vs'} {g['opp']} · pick a stat below for its trend")
    return e


class AvgView(discord.ui.View):
    def __init__(self, owner_id: int, cand: dict, games: list[dict]):
        super().__init__(timeout=900)
        self.owner_id, self.cand, self.games = owner_id, cand, games
        fam = FAMILY_OF_PATH[cand["path"]]
        opts = [discord.SelectOption(label=f"Trend: {STATS[k][0]}", value=k) for k in MAIN_STATS[fam]]
        sel = discord.ui.Select(placeholder="Open a trend chart", options=opts)
        sel.callback = self._cb(sel)
        self.add_item(sel)

    def _cb(self, sel):
        async def cb(interaction):
            if interaction.user.id != self.owner_id:
                await interaction.response.send_message("Run `/player avg` yourself.", ephemeral=True)
                return
            k = sel.values[0]
            values = trend_values(self.games, k)
            line = default_line([v for _, v in values[:10]])
            tv = TrendView(self.owner_id, self.cand, self.games, k, line, "10")
            await tv.redraw(interaction)
        return cb


def vs_embed(cand: dict, games: list[dict], opp: str) -> discord.Embed:
    o = opp.strip().lower()
    hits = [g for g in games if o in (g["opp"] or "").lower() or o in (g.get("opp_name") or "").lower()]
    fam = FAMILY_OF_PATH[cand["path"]]
    e = discord.Embed(title=f"🆚 {cand['name']} vs {opp.upper() if len(opp) <= 4 else opp.title()}", color=BRAND)
    if not hits:
        e.description = "No games against them on file (this season and last)."
        return e
    keys = [k for k in MAIN_STATS[fam] if any(v for _, v in trend_values(hits, k))][:5]
    lines = []
    for g in hits[:10]:
        when = datetime.fromisoformat(g["date"].replace("Z", "+00:00")).astimezone(TZ).strftime("%b %-d, %Y") if g["date"] else ""
        parts = []
        for k in keys:
            got = stat_value(g["groups"], k)
            if got is not None:
                parts.append(f"{got[0]:g} {STATS[k][0]}")
        lines.append(f"{when} {'@' if g['at'] == '@' else 'vs'} {g['opp']} {g['result']} · " + " · ".join(parts))
    e.description = "\n".join(lines)
    avgs = []
    for k in keys:
        vals = [v for _, v in trend_values(hits, k)]
        if vals:
            avgs.append(f"**{STATS[k][0]}** {sum(vals) / len(vals):.1f}")
    e.add_field(name=f"Average in {len(hits)} games", value=" · ".join(avgs) or "-", inline=False)
    return e


async def b2b_team_ids(path: str, day: datetime) -> set[str]:
    """Teams that played the day before `day` (local)."""
    if path not in B2B_PATHS:
        return set()
    out = set()
    for ev in await fetch_scoreboard(path, day.astimezone(TZ) - timedelta(days=1)):
        out |= {t["id"] for t in ev["teams"]}
    return out


# ---- web dashboard ------------------------------------------------------------------------------

WEB_PORT = env("PORT", "")
PUBLIC_DOMAIN = env("RAILWAY_PUBLIC_DOMAIN", "")


def dashboard_key() -> str:
    key = env("DASHBOARD_KEY", "")
    if key:
        return key
    key = get_setting(0, "dashboard_key")
    if not key:
        import secrets
        key = secrets.token_urlsafe(18)
        set_setting(0, "dashboard_key", key)
    return key


def dashboard_url() -> Optional[str]:
    if not PUBLIC_DOMAIN:
        return None
    return f"https://{PUBLIC_DOMAIN}/?key={dashboard_key()}"


def dashboard_data(guild_id: int) -> dict:
    season = current_season(guild_id)
    def board(stats):
        return [{"name": s["name"], "record": record_line(s), "net": round(s["net"], 2), "roi": round(s["roi"], 1),
                 "streak": current_streak(guild_id, s["key"]), "open": s["open"]}
                for s in stats if s["wins"] + s["losses"] + s["pushes"] > 0]
    series = chart_series(guild_id, 3650)
    recent = [{"id": p["id"], "who": p["bettor_name"], "what": shown_desc(p), "platform": p["platform"],
               "status": p["status"], "net": round(pick_net(p), 2), "when": local_day(p["settled_at"] or p["created_at"])}
              for p in db().execute("""SELECT * FROM picks WHERE guild_id = ? AND status != 'open'
                                       ORDER BY settled_at DESC LIMIT 25""", (guild_id,))]
    open_ = [{"id": p["id"], "who": p["bettor_name"], "what": shown_desc(p), "platform": p["platform"],
              "cost": p["cost"], "payout": p["payout"]}
             for p in db().execute("SELECT * FROM picks WHERE guild_id = ? AND status = 'open' ORDER BY id DESC LIMIT 40",
                                   (guild_id,))]
    r = gp_round(guild_id, create=False)
    gp = [{"who": x["user_name"], "leg": x["text"], "status": x["status"]} for x in gp_legs(r["id"])] if r else []
    names = {}
    for p in db().execute("SELECT bettor_id, bettor_name FROM picks WHERE guild_id = ? AND bettor_id IS NOT NULL", (guild_id,)):
        names[p["bettor_id"]] = p["bettor_name"]
    coins = [{"who": names.get(u["user_id"], "Member"), "coins": int(u["bal"])} for u in coins_top(guild_id, 10)]
    rec = records_embed(guild_id).description or ""
    return {"version": BOT_VERSION, "season": season["name"] if season else None,
            "leaderboard": board(season_stats(guild_id, season) if season else compute_stats(guild_id)),
            "alltime": board(compute_stats(guild_id)),
            "series": {k: [[x.astimezone(TZ).strftime("%Y-%m-%d %H:%M"), round(y, 2)] for x, y in v] for k, v in series.items()},
            "recent": recent, "open": open_, "groupparlay": gp, "coins": coins,
            "records": [re.sub(r"\*\*", "", line) for line in rec.split("\n") if line]}


DASHBOARD_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>PIMP-BOT Dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
:root{--bg:#141413;--card:#1f1f1d;--line:#383835;--text:#f5f4ee;--muted:#b4b2a7;--brand:#7B3FE4;--up:#3fb97a;--down:#e66767}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
header{padding:28px 20px 8px;max-width:1100px;margin:auto;display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap}
h1{margin:0;font-size:26px;letter-spacing:.5px}h1 span{color:var(--brand)}.muted{color:var(--muted)}
main{max-width:1100px;margin:auto;padding:12px 16px 40px;display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(320px,1fr))}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px 18px}
.wide{grid-column:1/-1}h2{font-size:14px;text-transform:uppercase;letter-spacing:1px;color:var(--muted);margin:0 0 10px}
table{width:100%;border-collapse:collapse}td,th{padding:7px 4px;border-bottom:1px solid var(--line);text-align:left;font-size:14px}
th{color:var(--muted);font-weight:500}td.num{text-align:right;font-variant-numeric:tabular-nums}
.up{color:var(--up)}.down{color:var(--down)}.pill{font-size:12px;padding:2px 8px;border-radius:99px;background:#2c2c2a}
.tabs button{background:#2c2c2a;color:var(--text);border:0;border-radius:99px;padding:6px 12px;margin-right:6px;cursor:pointer}
.tabs button.on{background:var(--brand)}ul{margin:0;padding-left:18px}li{margin:4px 0}
canvas{max-height:340px}
</style></head><body>
<header><h1>PIMP<span>-</span>BOT</h1><div class="muted" id="meta">loading…</div></header>
<main>
<section class="card wide"><h2>Profit over time</h2><canvas id="chart"></canvas></section>
<section class="card"><h2>Leaderboard</h2><div class="tabs"><button id="t1" class="on">Season</button><button id="t2">All time</button></div><table id="lb"></table></section>
<section class="card"><h2>Open picks</h2><table id="open"></table></section>
<section class="card"><h2>Recent results</h2><table id="recent"></table></section>
<section class="card"><h2>Group parlay</h2><ul id="gp"></ul></section>
<section class="card"><h2>🪙 Coins</h2><table id="coins"></table></section>
<section class="card"><h2>Record book</h2><ul id="records"></ul></section>
</main>
<script>
const q=new URLSearchParams(location.search);const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const money=n=>(n<0?'-':'+')+'$'+Math.abs(n).toFixed(2);const cls=n=>n>0?'up':n<0?'down':'';
const COLORS=['#3987e5','#d95926','#199e70','#c98500','#d55181','#008300','#9085e9','#e66767'];
let data,chart;
function lb(rows){document.getElementById('lb').innerHTML='<tr><th>#</th><th>Name</th><th>Record</th><th class=num>Net</th><th class=num>ROI</th></tr>'+
 rows.map((r,i)=>`<tr><td>${['🥇','🥈','🥉'][i]||i+1}</td><td>${esc(r.name)} <span class=muted>${esc(r.streak)}</span></td><td>${esc(r.record)}</td><td class="num ${cls(r.net)}">${money(r.net)}</td><td class="num ${cls(r.roi)}">${r.roi.toFixed(1)}%</td></tr>`).join('')}
async function load(){
 const r=await fetch('/api/data?'+q.toString());if(!r.ok){document.getElementById('meta').textContent='Wrong or missing key.';return}
 data=await r.json();document.getElementById('meta').textContent=(data.season?'Season: '+data.season+' · ':'')+'version '+data.version+' · updated '+new Date().toLocaleTimeString();
 lb(data.season?data.leaderboard:data.alltime);
 document.getElementById('open').innerHTML='<tr><th>#</th><th>Who</th><th>Pick</th><th class=num>Risk → Pays</th></tr>'+data.open.map(p=>`<tr><td>${p.id}</td><td>${esc(p.who)}</td><td>${esc(p.what)}</td><td class=num>$${p.cost.toFixed(2)} → $${p.payout.toFixed(2)}</td></tr>`).join('');
 document.getElementById('recent').innerHTML=data.recent.map(p=>`<tr><td>${esc(p.when)}</td><td>${esc(p.who)}</td><td>${esc(p.what)}</td><td class="num ${cls(p.net)}">${money(p.net)}</td></tr>`).join('');
 document.getElementById('gp').innerHTML=data.groupparlay.map(l=>`<li>${{hit:'✅',miss:'❌',push:'➖'}[l.status]||'⏳'} <b>${esc(l.who)}</b>: ${esc(l.leg)}</li>`).join('')||'<li class=muted>No legs this week yet.</li>';
 document.getElementById('coins').innerHTML=data.coins.map((c,i)=>`<tr><td>${i+1}</td><td>${esc(c.who)}</td><td class=num>🪙${c.coins.toLocaleString()}</td></tr>`).join('');
 document.getElementById('records').innerHTML=data.records.map(x=>`<li>${esc(x)}</li>`).join('');
 const sets=Object.entries(data.series).map(([name,pts],i)=>({label:name,data:pts.map(p=>({x:p[0],y:p[1]})),borderColor:COLORS[i%8],backgroundColor:COLORS[i%8],stepped:true,pointRadius:0,borderWidth:2}));
 if(chart)chart.destroy();
 chart=new Chart(document.getElementById('chart'),{type:'line',data:{datasets:sets},options:{parsing:false,animation:false,
  scales:{x:{type:'category',labels:[...new Set(sets.flatMap(s=>s.data.map(p=>p.x)))].sort(),ticks:{color:'#b4b2a7',maxTicksLimit:8},grid:{color:'#2c2c2a'}},
  y:{ticks:{color:'#b4b2a7',callback:v=>'$'+v},grid:{color:'#2c2c2a'}}},plugins:{legend:{labels:{color:'#f5f4ee'}}}}});
}
document.getElementById('t1').onclick=e=>{lb(data.season?data.leaderboard:data.alltime);e.target.classList.add('on');document.getElementById('t2').classList.remove('on')};
document.getElementById('t2').onclick=e=>{lb(data.alltime);e.target.classList.add('on');document.getElementById('t1').classList.remove('on')};
load();setInterval(load,120000);
</script></body></html>"""


def dashboard_guild() -> Optional[int]:
    if GUILD_ID:
        return int(GUILD_ID)
    row = db().execute("SELECT guild_id, COUNT(*) AS n FROM picks GROUP BY guild_id ORDER BY n DESC LIMIT 1").fetchone()
    return row["guild_id"] if row else None


async def start_dashboard() -> None:
    if not WEB_PORT:
        return
    from aiohttp import web

    def authed(request) -> bool:
        import hmac
        return hmac.compare_digest(request.query.get("key", ""), dashboard_key())

    async def index(request):
        if not authed(request):
            return web.Response(text="PIMP-BOT is running. Ask an admin for the dashboard link (/dashboard).",
                                content_type="text/plain")
        return web.Response(text=DASHBOARD_HTML, content_type="text/html")

    async def data(request):
        if not authed(request):
            return web.json_response({"error": "bad key"}, status=403)
        gid = int(request.query.get("guild") or dashboard_guild() or 0)
        return web.json_response(dashboard_data(gid))

    async def health(request):
        return web.Response(text="ok")

    app = web.Application()
    app.add_routes([web.get("/", index), web.get("/api/data", data), web.get("/health", health)])
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(WEB_PORT)).start()
    log.info("Dashboard listening on port %s", WEB_PORT)


# ==========================================================================
# r11: sports data (box, matchup, standings, rankings, golf, UFC, F1, CS2,
# injuries, weather, consensus), player splits and minutes, deeper insights,
# Kelly and slip odds, leaderboard by units/platform with movement arrows,
# power rankings, Claudia vs the group, starting-lineup check
# ==========================================================================

ESPN_STANDINGS = "https://site.api.espn.com/apis/v2/sports/{path}/standings"
ESPN_RANKINGS = "https://site.api.espn.com/apis/site/v2/sports/{path}/rankings"
ESPN_BOARD = "https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard"
GEOCODE = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST = "https://api.open-meteo.com/v1/forecast"
LIQUIPEDIA = "https://liquipedia.net/counterstrike/api.php"
_misc_cache: dict[str, tuple[float, object]] = {}
SPORT_LEAGUES = [app_commands.Choice(name=n, value=p) for p, n in LEAGUE_NAMES.items()][:25]


async def cached_json(url: str, params: dict, ttl: int) -> dict:
    key = url + "?" + "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    hit = _misc_cache.get(key)
    if hit and hit[0] > time.monotonic():
        return hit[1]
    data = await _get_json(url, params)
    _misc_cache[key] = (time.monotonic() + ttl, data)
    return data


async def next_game(team_text: str, paths: list[str]) -> Optional[tuple[str, dict, int]]:
    """(league path, event, team index) for this team's next (or current) game within a week."""
    now = datetime.now(timezone.utc)
    for path in paths:
        games = await find_games(team_text, [path], now - timedelta(days=1))
        upcoming = [(ev, i) for ev, i in games if not ev["final"]]
        if upcoming:
            ev, i = upcoming[0]
            return path, ev, i
        later = []
        for offset in range(4, 8):
            for ev in await fetch_scoreboard(path, (now + timedelta(days=offset)).astimezone(TZ)):
                for i, t in enumerate(ev["teams"]):
                    if team_matches(team_text, t) and not ev["final"]:
                        later.append((ev, i))
        if later:
            ev, i = sorted(later, key=lambda x: x[0]["date"])[0]
            return path, ev, i
    return None


# ---- weather -----------------------------------------------------------------------------------

async def kickoff_weather(city: str, state: str, when: datetime) -> Optional[dict]:
    try:
        geo = await cached_json(GEOCODE, {"name": city, "count": 5, "country_code": "US" if state else ""}, 86400 * 7)
        results = geo.get("results") or []
        if state:
            results = [r for r in results if (r.get("admin1") or "").lower().startswith(US_STATES.get(state, state).lower()[:4])] or results
        if not results:
            return None
        lat, lon = results[0]["latitude"], results[0]["longitude"]
        day = when.astimezone(timezone.utc).date().isoformat()
        fc = await cached_json(FORECAST, {"latitude": lat, "longitude": lon, "timezone": "UTC", "start_date": day,
                                          "end_date": day, "temperature_unit": "fahrenheit", "wind_speed_unit": "mph",
                                          "hourly": "temperature_2m,precipitation_probability,wind_speed_10m,wind_gusts_10m"},
                               1800)
        hourly = fc.get("hourly") or {}
        times = hourly.get("time") or []
        target = when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:00")
        if target not in times:
            return None
        k = times.index(target)
        def at(name):
            vals = hourly.get(name) or []
            return vals[k] if k < len(vals) else None
        return {"temp": at("temperature_2m"), "rain": at("precipitation_probability"), "wind": at("wind_speed_10m"),
                "gust": at("wind_gusts_10m")}
    except Exception:
        log.warning("Weather lookup failed for %s", city)
        return None


US_STATES = {"AL": "Alabama", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado", "CT": "Connecticut",
             "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
             "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan",
             "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "NE": "Nebraska", "NV": "Nevada", "NJ": "New Jersey",
             "NY": "New York", "NC": "North Carolina", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
             "SC": "South Carolina", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VA": "Virginia", "WA": "Washington",
             "WI": "Wisconsin", "WV": "West Virginia", "ID": "Idaho", "NM": "New Mexico", "AK": "Alaska", "HI": "Hawaii"}


def weather_line(w: dict) -> str:
    bits = []
    if w.get("temp") is not None:
        bits.append(f"{w['temp']:.0f}°F")
    if w.get("wind") is not None:
        bits.append(f"wind {w['wind']:.0f} mph" + (f" (gusts {w['gust']:.0f})" if w.get("gust") and w["gust"] >= w["wind"] + 8 else ""))
    if w.get("rain") is not None:
        bits.append(f"{w['rain']:.0f}% chance of rain")
    flag = ""
    if (w.get("wind") or 0) >= 15 or (w.get("gust") or 0) >= 25:
        flag = " · 🌬️ windy, can hurt passing and kicking"
    elif (w.get("rain") or 0) >= 60:
        flag = " · 🌧️ likely wet"
    elif w.get("temp") is not None and w["temp"] <= 25:
        flag = " · 🥶 cold"
    return ", ".join(bits) + flag


# ---- matchup ------------------------------------------------------------------------------------

async def team_injuries(path: str, team_name: str) -> list[dict]:
    out = []
    try:
        raw = await cached_json(ESPN_INJURIES.format(path=path), {}, 900)
    except Exception:
        return out
    for team in raw.get("injuries") or []:
        if norm_team(team.get("displayName") or "") != norm_team(team_name):
            continue
        for inj in team.get("injuries") or []:
            status = inj.get("status")
            if isinstance(status, dict):
                status = status.get("name")
            ath = (inj.get("athlete") or {}).get("displayName")
            if ath and status and str(status).lower() != "active":
                out.append({"name": ath, "status": str(status)})
    return out


async def matchup_embed(guild_id: Optional[int], path: str, ev: dict) -> discord.Embed:
    away = next(t for t in ev["teams"] if not t["home"])
    home = next(t for t in ev["teams"] if t["home"])
    when = event_time(ev)
    e = discord.Embed(title=f"🆚 {away['short']} @ {home['short']}", color=BRAND,
                      description=(today_line(ev) + (f"\n{when.astimezone(TZ):%A %b %-d, %-I:%M %p} Central" if when and
                                                     ev.get("state") == "pre" else "")))
    for t in (away, home):
        rec = " · ".join(f"{k} {v}" for k, v in (t.get("records") or {}).items())
        e.add_field(name=t["short"], value=rec or "-")
    v = ev.get("venue") or {}
    if v.get("name"):
        line = v["name"] + (f", {v['city']}" if v.get("city") else "")
        if v.get("indoor"):
            line += " · 🏟️ indoors"
        elif when and v.get("city") and ev.get("state") == "pre" and when - datetime.now(timezone.utc) < timedelta(days=7):
            w = await kickoff_weather(v["city"], v.get("state") or "", when)
            if w:
                line += f"\n🌤️ Kickoff: {weather_line(w)}"
        e.add_field(name="Venue", value=clip(line, 1024), inline=False)
    b2b = await b2b_team_ids(path, when or datetime.now(timezone.utc))
    tired = [t["short"] for t in ev["teams"] if t["id"] in b2b]
    if tired and ev.get("state") == "pre":
        e.add_field(name="🔁 Back-to-back", value=", ".join(tired) + " played yesterday", inline=False)
    for t in (away, home):
        inj = await team_injuries(path, t.get("name") or t["short"])
        if inj:
            e.add_field(name=f"🚑 {t['short']} injuries", inline=False,
                        value=clip(", ".join(f"{x['name']} ({x['status']})" for x in inj[:12]), 1024))
    if guild_id:
        cons = consensus_for(guild_id, ev)
        if cons:
            e.add_field(name="👥 The group's open picks on this game", value=clip(cons, 1024), inline=False)
    return e


# ---- consensus ----------------------------------------------------------------------------------

def leg_side(text: str, ev: dict) -> Optional[str]:
    """Which side of this game a leg is on: a team's short name, 'Over' or 'Under'."""
    leg = parse_simple_leg(text)
    if not leg:
        return None
    if leg["kind"] == "total":
        side = leg["side"].title()
        if leg["negate"]:
            side = "Under" if side == "Over" else "Over"
        return f"{side} {leg['line']:g}"
    for i, t in enumerate(ev["teams"]):
        if team_matches(leg["team"], t):
            if leg["kind"] == "team_total":
                return f"{t['short']} team total {leg['side']}"
            backed = t if not leg["negate"] else ev["teams"][1 - i]
            return backed["short"]
    return None


def consensus_for(guild_id: int, ev: dict) -> str:
    counts: dict[str, list[str]] = {}
    for p in db().execute("SELECT * FROM picks WHERE guild_id = ? AND status = 'open' AND (hidden IS NULL OR hidden = 0)",
                          (guild_id,)).fetchall():
        texts = [x["text"] for x in get_legs(p["id"]) if x["status"] == "open"] or [p["description"]]
        teams_here = {norm_team(t["short"]) for t in ev["teams"]} | {a for t in ev["teams"] for a in t["aliases"]}
        for text in texts:
            side = leg_side(text, ev)
            if not side:
                continue
            leg = parse_simple_leg(text)
            if leg["kind"] == "total" and not any(team_matches(x, t) for x in paren_teams(text) + [
                    (parse_simple_leg(o) or {}).get("team", "") for o in texts] for t in ev["teams"]):
                continue
            counts.setdefault(side, []).append(p["bettor_name"])
    total = sum(len(v) for v in counts.values())
    lines = []
    for side, who in sorted(counts.items(), key=lambda kv: -len(kv[1])):
        pct = len(who) / total * 100
        bar = "█" * max(1, int(round(pct / 10)))
        lines.append(f"**{side}** {bar} {pct:.0f}% ({', '.join(sorted(set(who)))})")
    return "\n".join(lines)


async def consensus_embed(guild_id: int) -> discord.Embed:
    e = discord.Embed(title="👥 Group consensus · tonight", color=BRAND)
    now = datetime.now(TZ)
    found = 0
    for path in group_leagues(guild_id):
        for ev in await fetch_scoreboard(path, now):
            if ev["final"]:
                continue
            c = consensus_for(guild_id, ev)
            if c and found < 20:
                found += 1
                e.add_field(name=clip(today_line(ev).replace("`", ""), 256), value=clip(c, 1024), inline=False)
    if not found:
        e.description = "Nobody has an open moneyline, spread or total on today's games."
    e.set_footer(text="Built from open picks (hidden picks left out)")
    return e


# ---- standings & rankings -------------------------------------------------------------------------

def _stat(entry: dict, name: str) -> str:
    for s in entry.get("stats") or []:
        if s.get("name") == name or s.get("type") == name:
            return s.get("displayValue") or s.get("summary") or str(s.get("value", ""))
    return ""


async def standings_groups(path: str) -> list[tuple[str, list[dict]]]:
    raw = await cached_json(ESPN_STANDINGS.format(path=path), {}, 1800)
    groups = []
    def walk(node):
        if node.get("standings", {}).get("entries"):
            groups.append((node.get("name") or node.get("abbreviation") or "Standings", node["standings"]["entries"]))
        for ch in node.get("children") or []:
            walk(ch)
    walk(raw)
    return groups


def standings_embed(path: str, name: str, entries: list[dict]) -> discord.Embed:
    def seed(en):
        try:
            return float(_stat(en, "playoffSeed") or 99)
        except ValueError:
            return 99.0
    rows = sorted(entries, key=lambda en: (seed(en), -float(_stat(en, "winPercent") or 0)))
    lines = []
    for k, en in enumerate(rows):
        t = en.get("team") or {}
        w, l = _stat(en, "wins"), _stat(en, "losses")
        gb, strk = _stat(en, "gamesBehind"), _stat(en, "streak")
        ties = _stat(en, "ties")
        rec = f"{w}-{l}" + (f"-{ties}" if ties and ties != "0" else "")
        lines.append(f"`{k + 1:>2}` **{t.get('displayName') or t.get('name')}** {rec}"
                     + (f" · GB {gb}" if gb and gb not in ("-", "0") else "") + (f" · {strk}" if strk else ""))
        if path in ("basketball/nba", "basketball/wnba") and k in (5, 9) or path == "football/nfl" and k == 6 \
                or path == "hockey/nhl" and k == 7 or path == "baseball/mlb" and k == 5:
            lines.append("── playoff line ──" if not (path == "basketball/nba" and k == 5) else "── play-in ──")
    e = discord.Embed(title=f"🏆 {LEAGUE_NAMES.get(path, path)} · {name}", color=BRAND,
                      description=clip("\n".join(lines), 4000))
    e.set_footer(text="Seeded order where ESPN provides it")
    return e


class StandingsView(discord.ui.View):
    def __init__(self, owner_id: int, path: str, groups: list):
        super().__init__(timeout=900)
        self.owner_id, self.path, self.groups = owner_id, path, groups
        sel = discord.ui.Select(placeholder="Conference / division", options=[
            discord.SelectOption(label=clip(n, 100), value=str(k)) for k, (n, _) in enumerate(groups[:25])])
        sel.callback = self._cb(sel)
        self.add_item(sel)

    def _cb(self, sel):
        async def cb(interaction):
            n, entries = self.groups[int(sel.values[0])]
            await interaction.response.edit_message(embed=standings_embed(self.path, n, entries), view=self)
        return cb


async def rankings_embed(path: str) -> discord.Embed:
    raw = await cached_json(ESPN_RANKINGS.format(path=path), {}, 3600)
    polls = raw.get("rankings") or []
    poll = next((p for p in polls if "ap" in (p.get("shortName") or p.get("name") or "").lower()), polls[0] if polls else None)
    e = discord.Embed(title=f"📋 {LEAGUE_NAMES.get(path, path)} · {(poll or {}).get('name') or 'Rankings'}", color=BRAND)
    if not poll:
        e.description = "No poll out right now."
        return e
    lines = []
    for r in (poll.get("ranks") or [])[:25]:
        t = r.get("team") or {}
        cur, prev = r.get("current"), r.get("previous")
        move = ""
        if isinstance(prev, int) and prev and isinstance(cur, int):
            move = f" ▲{prev - cur}" if prev > cur else (f" ▼{cur - prev}" if cur > prev else "")
        elif not prev:
            move = " 🆕"
        lines.append(f"`{cur:>2}` **{t.get('location') or t.get('nickname')}** {r.get('recordSummary') or ''}{move}")
    e.description = "\n".join(lines)
    return e


# ---- golf, UFC, F1 --------------------------------------------------------------------------------

async def golf_embed() -> discord.Embed:
    raw = await cached_json(ESPN_BOARD.format(path="golf/pga"), {}, 300)
    ev = (raw.get("events") or [None])[0]
    if not ev:
        return discord.Embed(title="⛳ PGA Tour", description="No tournament this week.", color=BRAND)
    comp = (ev.get("competitions") or [{}])[0]
    state = ((ev.get("status") or {}).get("type") or {})
    rows = sorted(comp.get("competitors") or [], key=lambda c: c.get("order") or 999)
    lines = []
    for c in rows[:15]:
        a = c.get("athlete") or {}
        rounds = [str(int(x["value"])) for x in c.get("linescores") or [] if isinstance(x, dict) and x.get("value")]
        lines.append(f"`{c.get('order') or '-':>3}` **{a.get('displayName')}** {c.get('score') or ''}"
                     + (f" · {'-'.join(rounds)}" if rounds else ""))
    e = discord.Embed(title=f"⛳ {ev.get('name')}", color=BRAND,
                      description=(state.get("detail") or state.get("description") or "") + "\n" + "\n".join(lines))
    return e


async def ufc_embed() -> discord.Embed:
    raw = await cached_json(ESPN_BOARD.format(path="mma/ufc"), {}, 600)
    ev = (raw.get("events") or [None])[0]
    if not ev:
        return discord.Embed(title="🥊 UFC", description="No card on the schedule.", color=BRAND)
    lines = []
    for comp in reversed(ev.get("competitions") or []):          # main event first
        cs = sorted(comp.get("competitors") or [], key=lambda c: c.get("order") or 9)
        if len(cs) != 2:
            continue
        def who(c):
            a = c.get("athlete") or {}
            rec = next((r.get("summary") for r in c.get("records") or [] if r.get("type") == "total"), "")
            return f"{'🏆 ' if c.get('winner') else ''}{a.get('displayName')}" + (f" ({rec})" if rec else "")
        st = ((comp.get("status") or {}).get("type") or {})
        tail = st.get("detail") if st.get("state") == "post" else ""
        wc = (comp.get("type") or {}).get("abbreviation") or ""
        lines.append(f"**{who(cs[0])}** vs **{who(cs[1])}** · {wc}" + (f" · {tail}" if tail else ""))
    when = event_time(ev)
    e = discord.Embed(title=f"🥊 {ev.get('name')}", color=BRAND,
                      description=(f"{when.astimezone(TZ):%a %b %-d, %-I:%M %p} Central\n" if when else "") +
                      clip("\n".join(lines[:20]), 3900))
    return e


async def f1_embed() -> discord.Embed:
    raw = await cached_json(ESPN_BOARD.format(path="racing/f1"), {}, 600)
    ev = (raw.get("events") or [None])[0]
    if not ev:
        return discord.Embed(title="🏎️ Formula 1", description="No race weekend on the schedule.", color=BRAND)
    e = discord.Embed(title=f"🏎️ {ev.get('name')}", color=BRAND,
                      description=((ev.get("circuit") or {}).get("fullName") or ""))
    for comp in ev.get("competitions") or []:
        kind = (comp.get("type") or {}).get("abbreviation") or "Session"
        when = event_time(comp) if comp.get("date") else None
        st = ((comp.get("status") or {}).get("type") or {})
        top = sorted(comp.get("competitors") or [], key=lambda c: c.get("order") or 99)[:3]
        podium = " · ".join(f"{c.get('order')}. {(c.get('athlete') or {}).get('displayName')}" for c in top)
        value = (f"{when.astimezone(TZ):%a %-I:%M %p}" if when else "") + (f" · {podium}" if podium and st.get("state") == "post"
                                                                           else ("" if st.get("state") != "in" else " · 🔴 live"))
        e.add_field(name=kind, value=value or "-", inline=False)
    return e


# ---- CS2 (Liquipedia, best effort) ------------------------------------------------------------------

def parse_liquipedia_matches(html: str) -> list[dict]:
    out = []
    for block in re.split(r'<table class="wikitable wikitable-striped infobox_matches_content', html)[1:]:
        teams = re.findall(r'class="team-template-text"[^>]*>\s*<a[^>]*>([^<]+)</a>', block)
        if len(teams) < 2:
            teams = re.findall(r'<span class="name"[^>]*>(?:<a[^>]*>)?([^<]+)', block)
        ts = re.search(r'data-timestamp="(\d+)"', block)
        fmt = re.search(r'<abbr title="Best of (\d+)"', block)
        tour = re.search(r'class="match-filler"[\s\S]*?<a [^>]*title="([^"]+)"', block) or \
            re.search(r'<div class="tournament-text[^"]*"[\s\S]*?<a [^>]*>([^<]+)</a>', block)
        if len(teams) >= 2 and ts:
            out.append({"team1": teams[0].strip(), "team2": teams[1].strip(), "ts": int(ts.group(1)),
                        "bo": fmt.group(1) if fmt else "", "event": (tour.group(1).strip() if tour else "")})
    return out


async def cs2_embed(filter_text: Optional[str] = None) -> discord.Embed:
    e = discord.Embed(title="🎮 CS2 · upcoming matches", color=BRAND)
    try:
        raw = await cached_json(LIQUIPEDIA, {"action": "parse", "page": "Liquipedia:Matches", "format": "json",
                                             "prop": "text"}, 900)
        html = ((raw.get("parse") or {}).get("text") or {}).get("*") or ""
        matches = parse_liquipedia_matches(html)
    except Exception:
        log.warning("Liquipedia unavailable")
        matches = None
    if matches is None:
        e.description = "Liquipedia isn't answering right now (it limits how often bots can ask). Try again in a few minutes."
        return e
    now = time.time()
    matches = [m for m in matches if m["ts"] >= now - 3 * 3600]
    if filter_text:
        f = filter_text.lower()
        matches = [m for m in matches if f in m["team1"].lower() or f in m["team2"].lower() or f in m["event"].lower()]
    lines = [f"<t:{m['ts']}:R> **{m['team1']}** vs **{m['team2']}**" + (f" · Bo{m['bo']}" if m["bo"] else "")
             + (f" · {clip(m['event'], 40)}" if m["event"] else "") for m in matches[:20]]
    e.description = "\n".join(lines) or "No matches found."
    e.set_footer(text="From Liquipedia (CC-BY-SA)")
    return e


# ---- player splits & minutes -----------------------------------------------------------------------

STATS["minutes"] = ("Minutes", "basketball", [("min", 1)], ["minutes played", "minutes", "mins"])
_ALIAS_INDEX[:] = sorted(((alias, key) for key, (_, _, _, aliases) in STATS.items() for alias in aliases),
                         key=lambda x: -len(x[0]))
MAIN_STATS["basketball"].insert(0, "minutes")


def splits_embed(cand: dict, games: list[dict]) -> discord.Embed:
    fam = FAMILY_OF_PATH[cand["path"]]
    home = [g for g in games if g["at"] != "@"]
    away = [g for g in games if g["at"] == "@"]
    wins = [g for g in games if g["result"] == "W"]
    losses = [g for g in games if g["result"] == "L"]
    e = discord.Embed(title=f"🏠✈️ {cand['name']} · splits", color=BRAND, description=f"{len(games)} games on file")
    def avg(gs, k):
        vals = [v for _, v in trend_values(gs, k)]
        return f"{sum(vals) / len(vals):.1f}" if vals else "-"
    rows = []
    for k in MAIN_STATS[fam]:
        if not any(v for _, v in trend_values(games, k)):
            continue
        rows.append(f"**{STATS[k][0]}** · home {avg(home, k)} · away {avg(away, k)} · in wins {avg(wins, k)} · "
                    f"in losses {avg(losses, k)}")
    e.add_field(name=f"Home {len(home)} · away {len(away)} · wins {len(wins)} · losses {len(losses)}",
                value="\n".join(rows) or "-", inline=False)
    return e


# ---- deeper insights ---------------------------------------------------------------------------------

def leg_kind(text: str) -> str:
    prop = prop_of(text)
    if prop:
        return STATS[prop["stats"][0]][0]
    simple = parse_simple_leg(text)
    if simple:
        return {"ml": "Moneyline", "spread": "Spread", "margin": "Win margin", "total": "Game total",
                "team_total": "Team total"}[simple["kind"]]
    return "Other"


def autopsy_embed(guild_id: int, key: str, name: str) -> discord.Embed:
    lost = [p for p in settled_picks(guild_id, key) if p["status"] == "loss"]
    killers: dict[str, int] = {}
    players: dict[str, int] = {}
    one_off = 0
    total_legs = 0
    for p in lost:
        legs = get_legs(p["id"])
        misses = [x for x in legs if x["status"] == "miss"]
        if len(legs) >= 2 and misses:
            total_legs += 1
            if len(misses) == 1:
                one_off += 1
            for x in misses:
                killers[leg_kind(x["text"])] = killers.get(leg_kind(x["text"]), 0) + 1
                pr = prop_of(x["text"])
                if pr:
                    players[pr["player"].title()] = players.get(pr["player"].title(), 0) + 1
    e = discord.Embed(title=f"🔬 {name}'s parlay autopsy", color=0xE74C3C)
    if not total_legs:
        e.description = "No lost parlays with graded legs yet."
        return e
    e.description = (f"{total_legs} lost parlays · **{one_off}** died to a single leg "
                     f"({one_off / total_legs * 100:.0f}%)")
    e.add_field(name="What kills your parlays", value="\n".join(
        f"**{k}** · {v} miss{'es' if v != 1 else ''}" for k, v in sorted(killers.items(), key=lambda kv: -kv[1])[:8]))
    if players:
        e.add_field(name="Repeat offenders", value="\n".join(
            f"**{k}** · {v}" for k, v in sorted(players.items(), key=lambda kv: -kv[1])[:8]))
    e.set_footer(text="Counts every missed leg on losing parlays")
    return e


def risk_numbers(picks: list) -> dict:
    total = peak = 0.0
    drawdown = 0.0
    nets = []
    for p in picks:
        total += pick_net(p)
        nets.append(pick_net(p))
        peak = max(peak, total)
        drawdown = max(drawdown, peak - total)
    stakes = [p["cost"] for p in picks]
    mean_stake = sum(stakes) / len(stakes)
    var = sum((s - mean_stake) ** 2 for s in stakes) / len(stakes)
    weekly: dict[str, float] = {}
    for p in picks:
        wk = week_id(datetime.fromisoformat(p["settled_at"] or p["created_at"]))
        weekly[wk] = weekly.get(wk, 0) + pick_net(p)
    green = sum(1 for v in weekly.values() if v > 0)
    return {"drawdown": drawdown, "peak": peak, "total": total, "mean_stake": mean_stake,
            "stake_cv": (var ** 0.5) / mean_stake if mean_stake else 0, "weeks": len(weekly), "green_weeks": green,
            "best": max(nets), "worst": min(nets)}


def risk_embed(guild_id: int, key: str, name: str) -> discord.Embed:
    picks = settled_picks(guild_id, key)
    e = discord.Embed(title=f"📉 {name}'s risk profile", color=BRAND)
    if len(picks) < 3:
        e.description = "Needs a few more settled picks."
        return e
    r = risk_numbers(picks)
    consistency = r["green_weeks"] / r["weeks"] * 100 if r["weeks"] else 0
    style = ("🎯 Steady grinder" if r["stake_cv"] < 0.5 and consistency >= 50 else
             "🎢 Boom or bust" if r["best"] > 5 * max(1, r["mean_stake"]) else "🎲 Streaky")
    e.description = f"**{style}**"
    e.add_field(name="Biggest drop from a high", value=f"{money(r['drawdown'])} (peak was {signed(r['peak'])})")
    e.add_field(name="Green weeks", value=f"{r['green_weeks']}/{r['weeks']} ({consistency:.0f}%)")
    e.add_field(name="Average stake", value=f"{money(r['mean_stake'])} · sizing {'steady' if r['stake_cv'] < 0.5 else 'all over the place'}")
    bands = breakdown([p for p in picks if p["cost"]], lambda p: (
        "Favorites (under 2x)" if p["payout"] < 2 * p["cost"] else "Plus money (2-5x)" if p["payout"] < 5 * p["cost"]
        else "Longshots (5-20x)" if p["payout"] < 20 * p["cost"] else "Lottery (20x+)"))
    e.add_field(name="ROI by payout size", value=breakdown_lines(bands), inline=False)
    return e


GRADE_SCALE = [(90, "A+"), (80, "A"), (70, "B+"), (60, "B"), (50, "C+"), (40, "C"), (30, "D"), (0, "F")]


def letter(score: float) -> str:
    return next(g for cut, g in GRADE_SCALE if score >= cut)


def report_card(guild_id: int, key: str, name: str, year: int, month: int) -> Optional[dict]:
    since, until = month_bounds(year, month)
    picks = [p for p in settled_picks(guild_id, key) if since <= (p["settled_at"] or "") < until]
    if not picks:
        return None
    wins = sum(1 for p in picks if p["status"] == "win")
    losses = sum(1 for p in picks if p["status"] == "loss")
    staked = sum(p["cost"] for p in picks)
    net = sum(pick_net(p) for p in picks)
    roi = net / staked * 100 if staked else 0
    legs = [x for p in picks for x in get_legs(p["id"]) if x["status"] in ("hit", "miss")]
    leg_rate = sum(1 for x in legs if x["status"] == "hit") / len(legs) * 100 if legs else None
    r = risk_numbers(picks)
    expected = sum(p["cost"] / p["payout"] for p in picks if p["status"] in ("win", "loss") and p["payout"] > p["cost"] > 0)
    luck = wins - expected
    grades = {
        "Profit": letter(max(0, min(100, 55 + roi))),
        "Hit rate": letter(max(0, min(100, (wins / max(1, wins + losses)) * 120))),
        "Legs": letter(max(0, min(100, (leg_rate or 0) * 1.3))) if leg_rate is not None else "-",
        "Discipline": letter(max(0, min(100, 100 - r["stake_cv"] * 80))),
        "Luck": letter(max(0, min(100, 50 + luck * 12))),
    }
    return {"name": name, "month": datetime(year, month, 1).strftime("%B %Y"), "picks": len(picks), "net": net, "roi": roi,
            "record": f"{wins}-{losses}", "leg_rate": leg_rate, "grades": grades}


def render_report_card(rc: dict) -> io.BytesIO:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch
    fig = plt.figure(figsize=(9, 11), dpi=100)
    fig.patch.set_facecolor("#f4efe2")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 900)
    ax.set_ylim(0, 1100)
    ax.axis("off")
    ax.add_patch(FancyBboxPatch((40, 40), 820, 1020, boxstyle="round,pad=0,rounding_size=18", facecolor="#fffdf6",
                                edgecolor="#c9bfa5", linewidth=2))
    ax.text(80, 980, "REPORT CARD", color="#2b2a27", fontsize=34, fontweight="bold", family="serif")
    ax.text(82, 935, f"{rc['name']} · {rc['month']}", color="#6b665a", fontsize=18, family="serif")
    ax.plot([80, 820], [905, 905], color="#c9bfa5", linewidth=1.5)
    colors = {"A": "#1f8a5b", "B": "#3f7fbf", "C": "#c98500", "D": "#d95926", "F": "#c0392b", "-": "#8a857a"}
    y = 830
    for subject, grade in rc["grades"].items():
        ax.text(90, y, subject, color="#2b2a27", fontsize=22, family="serif", va="center")
        ax.text(780, y, grade, color=colors[grade[0]], fontsize=40, fontweight="bold", family="serif", ha="right",
                va="center")
        ax.plot([80, 820], [y - 45, y - 45], color="#e8e1cf", linewidth=1)
        y -= 110
    ax.text(90, 230, f"{rc['picks']} pick{'s' if rc['picks'] != 1 else ''} · {rc['record']} · {signed(rc['net'])} · ROI {rc['roi']:+.0f}%",
            color="#2b2a27", fontsize=17, family="serif")
    if rc["leg_rate"] is not None:
        ax.text(90, 190, f"Legs hit: {rc['leg_rate']:.0f}%", color="#6b665a", fontsize=15, family="serif")
    comment = ("Teacher's note: " + ("Outstanding. Don't let it go to your head." if rc["net"] > 0 and rc["roi"] > 20 else
                                     "Solid month. Keep it boring." if rc["net"] > 0 else
                                     "Rough one. Smaller stakes, fewer longshots." if rc["roi"] < -30 else
                                     "Close to even. The edge is in the details."))
    ax.text(90, 120, comment, color="#8a2b2b", fontsize=15, family="serif", style="italic")
    out = io.BytesIO()
    fig.savefig(out, format="png", facecolor=fig.get_facecolor())
    plt.close(fig)
    out.seek(0)
    return out


CLAUDIA_KEYS = ("label:claudia",)


def claudia_key(guild_id: int) -> Optional[str]:
    row = db().execute("SELECT bettor_key FROM picks WHERE guild_id = ? AND lower(bettor_name) = 'claudia' "
                       "ORDER BY id DESC LIMIT 1", (guild_id,)).fetchone()
    return row["bettor_key"] if row else None


def claudia_embed(guild_id: int) -> discord.Embed:
    key = claudia_key(guild_id)
    e = discord.Embed(title="🤖 Claudia vs the group", color=BRAND)
    if not key:
        e.description = "No picks logged under Claudia yet. Log Claude's picks with `/pick label:Claudia`."
        return e
    stats = {s["key"]: s for s in compute_stats(guild_id)}
    c = stats.get(key)
    rest = [s for k, s in stats.items() if k != key and s["wins"] + s["losses"] + s["pushes"]]
    if not c or not rest:
        e.description = "Not enough settled picks to compare yet."
        return e
    g_staked = sum(s["staked"] for s in rest)
    g_net = sum(s["net"] for s in rest)
    g_w = sum(s["wins"] for s in rest)
    g_l = sum(s["losses"] for s in rest)
    beat = sum(1 for s in rest if c["roi"] > s["roi"])
    e.add_field(name="Claudia", value=f"{record_line(c)} · {signed(c['net'])} · ROI {c['roi']:+.1f}%")
    e.add_field(name="Everyone else", value=f"{g_w}-{g_l} · {signed(g_net)} · ROI {g_net / g_staked * 100 if g_staked else 0:+.1f}%")
    e.description = (f"Claudia's ROI beats **{beat} of {len(rest)}** people." +
                     (" 🤖 The robots are winning." if beat > len(rest) / 2 else " 🧠 Humans still on top."))
    return e


def power_rankings(guild_id: int) -> list[str]:
    now = datetime.now(timezone.utc)
    week = iso(now - timedelta(days=7))
    month = iso(now - timedelta(days=30))
    s7 = {s["key"]: s for s in compute_stats(guild_id, since=week)}
    s30 = {s["key"]: s for s in compute_stats(guild_id, since=month)}
    rows = []
    for k, s in s30.items():
        if s["wins"] + s["losses"] == 0:
            continue
        w = s7.get(k)
        score = s["roi"] * 0.5 + (w["roi"] if w else 0) * 0.5 + min(10, s["wins"] + s["losses"])
        rows.append((score, k, s, w))
    rows.sort(reverse=True, key=lambda r: r[0])
    lines = []
    for n, (_, k, s, w) in enumerate(rows[:10], 1):
        streak = current_streak(guild_id, k)
        if w and w["net"] > 0 and s["net"] > 0:
            blurb = "green week, green month. Tail with confidence."
        elif w and w["net"] > 0:
            blurb = "turning it around this week."
        elif w and w["net"] < 0 and s["net"] > 0:
            blurb = "cooling off after a good month."
        elif not w:
            blurb = "quiet this week."
        else:
            blurb = "rough stretch. Fade candidate."
        sports = breakdown([p for p in settled_picks(guild_id, k, month)], lambda p: sport_group(p["sport"]))
        if sports and sports[0][0] != "No sport":
            blurb += f" Living on {sports[0][0]}."
        lines.append(f"**{n}. {s['name']}** · 30d {signed(s['net'])}" + (f" · {streak}" if streak else "") + f": {blurb}")
    return lines


def rank_movement(guild_id: int, key_order: list[str], since: Optional[str], until_: Optional[str], **kw) -> dict[str, int]:
    """How many places each person moved compared with a week ago."""
    week_ago = iso(datetime.now(timezone.utc) - timedelta(days=7))
    old_until = week_ago if not until_ or until_ > week_ago else until_
    old = [s["key"] for s in compute_stats(guild_id, since=since, until=old_until, **kw)
           if s["wins"] + s["losses"] + s["pushes"] > 0]
    out = {}
    for i, k in enumerate(key_order):
        if k in old:
            out[k] = old.index(k) - i
    return out


# ---- Kelly & slip odds --------------------------------------------------------------------------------

def kelly_embed(prob: float, odds_text: str, bankroll: Optional[float]) -> discord.Embed:
    implied, kind = parse_odds(odds_text)
    dec = 1 / implied
    b = dec - 1
    f = (prob * b - (1 - prob)) / b
    e = discord.Embed(title="📐 Kelly calculator", color=BRAND,
                      description=f"Your chance: **{prob * 100:.1f}%** · odds {odds_text} ({kind}) → the price says "
                                  f"{implied * 100:.1f}%")
    edge = prob * dec - 1
    e.add_field(name="Your edge", value=f"{edge * 100:+.1f}% per dollar")
    if f <= 0:
        e.add_field(name="Bet", value="**Nothing.** At that price there's no edge.", inline=False)
    else:
        for label, frac in (("Full Kelly", 1), ("Half Kelly (most pros)", 0.5), ("Quarter Kelly", 0.25)):
            amt = f" = **{money(bankroll * f * frac)}**" if bankroll else ""
            e.add_field(name=label, value=f"{f * frac * 100:.1f}% of bankroll{amt}", inline=False)
    e.set_footer(text="Kelly is only as good as your chance estimate. Overestimate it and it'll overbet.")
    return e


async def slip_odds(p) -> tuple[list[str], Optional[float]]:
    """Each leg's recent hit rate against its line (props from game logs), and the product."""
    lines, prob = [], 1.0
    known = 0
    paths = [x for x in leagues_for(p["sport"]) if x in PROP_PATHS]
    for leg in get_legs(p["id"]) or []:
        if leg["status"] != "open":
            lines.append(f"{LEG_ICON[leg['status']]} {clip(leg['text'], 60)} (done)")
            if leg["status"] == "miss":
                prob = 0
            known += leg["status"] in ("hit", "miss")
            continue
        prop = prop_of(leg["text"])
        rate = None
        if prop and paths:
            fams = {STATS[k][1] for k in prop["stats"]}
            cands = await resolve_player(prop["player"], [x for x in paths if FAMILY_OF_PATH[x] in fams])
            if len(cands) == 1:
                try:
                    games = await trend_games(cands[0]["path"], cands[0]["id"], need=10)
                    key = next(k for k in prop["stats"] if STATS[k][1] == FAMILY_OF_PATH[cands[0]["path"]])
                    vals = [v for _, v in trend_values(games, key)[:10]]
                    if len(vals) >= 5:
                        over = sum(1 for v in vals if v > prop["line"]) / len(vals)
                        rate = over if prop["side"] == "over" else 1 - over
                        if prop["negate"]:
                            rate = 1 - rate
                        rate = min(0.95, max(0.05, rate))
                except Exception:
                    rate = None
        if rate is None:
            lines.append(f"❔ {clip(leg['text'], 60)} · no data")
            prob = None if prob is not None else None
            continue
        known += 1
        lines.append(f"{'🟢' if rate >= 0.6 else '🟡' if rate >= 0.45 else '🔴'} {clip(leg['text'], 60)} · {rate * 100:.0f}% L10")
        if prob is not None:
            prob *= rate
    if not known or any(x.startswith("❔") for x in lines):
        return lines, None
    return lines, prob


def unit_size_for(guild_id: int, key: str) -> float:
    if key.isdigit():
        b = get_bankroll(guild_id, key)
        if b and b.get("unit_size"):
            start_unit = b["start"] * b["unit_pct"] / 100
            if start_unit > 0:
                return start_unit
    row = db().execute("SELECT AVG(cost) FROM picks WHERE guild_id = ? AND bettor_key = ? AND status != 'open'",
                       (guild_id, key)).fetchone()
    return float(row[0] or 0)


# --------------------------------------------------------------------------
# The bot
# --------------------------------------------------------------------------

class PicksBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True  # needed to see screenshots and questions
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.receipt_channels: set[int] = set()
        self.ask_cooldowns: dict[int, float] = {}

    async def setup_hook(self):
        self.receipt_channels = receipt_channel_ids()
        self.add_dynamic_items(SettleButton, LogSlipButton, FollowButton, ChallengeButton, PickemButton,
                               SweatButton, InjuryOffButton, GPButton, CopyButton, CardSweatButton, CardKalshiButton,
                               PPSettleButton, MarketButton, TakeButton, PotdButton)
        try:
            await start_dashboard()
        except Exception:
            log.exception("Dashboard didn't start")
        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)  # shows up instantly in that server
        else:
            await self.tree.sync()  # global: can take up to an hour to appear
        self.scheduler_task = asyncio.create_task(self.scheduler())

    async def on_ready(self):
        log.info("Logged in as %s | version %s | Claude features: %s | receipts channels: %d",
                 self.user, BOT_VERSION, "on" if ai_enabled() else "off",
                 len(self.receipt_channels))

    # ---- scheduled posts ---------------------------------------------------

    async def scheduler(self):
        await self.wait_until_ready()
        try:
            n = await refresh_guides(self)
            if n:
                log.info("Refreshed %d posted guide(s) for version %s", n, BOT_VERSION)
        except Exception:
            log.exception("Guide refresh failed")
        while not self.is_closed():
            try:
                await self.run_schedules()
            except Exception:
                log.exception("Scheduled post failed")
            await asyncio.sleep(120)

    async def run_autograde(self, now: Optional[datetime] = None, limit: int = 3):
        """Grade picks that are still open AUTOGRADE_AFTER_HOURS after being logged."""
        if not AUTOGRADE_AFTER_HOURS:
            return
        now = now or datetime.now(timezone.utc)
        due = (now - timedelta(hours=AUTOGRADE_AFTER_HOURS)).isoformat(timespec="seconds")
        retry = (now - timedelta(hours=12)).isoformat(timespec="seconds")
        rows = db().execute(
            """SELECT * FROM picks WHERE status = 'open' AND created_at <= ?
               AND COALESCE(autograde_tries, 0) < ? AND (autograde_at IS NULL OR autograde_at <= ?)
               AND (NOT EXISTS (SELECT 1 FROM legs l WHERE l.pick_id = picks.id)
                    OR EXISTS (SELECT 1 FROM legs l WHERE l.pick_id = picks.id AND l.status = 'open'))
               ORDER BY created_at LIMIT ?""",
            (due, AUTOGRADE_MAX_TRIES, retry, limit)).fetchall()
        for p in rows:
            count_key = f"autogrades:{now.astimezone(TZ).date().isoformat()}"
            used = int(get_setting(p["guild_id"], count_key) or 0)
            try:
                pick, lines, graded, used_ai = await autograde(
                    p["guild_id"], p["id"], allow_ai=used < AUTOGRADE_DAILY_LIMIT)
            except Exception:
                log.exception("Auto-grading pick %s failed", p["id"])
                continue
            if used_ai:  # only paid lookups count toward the daily limit
                set_setting(p["guild_id"], count_key, str(used + 1))
            final_try = (pick["autograde_tries"] or 0) >= AUTOGRADE_MAX_TRIES
            if not lines or (not graded and not final_try):
                continue  # nothing new to say; try again later
            channel_id = get_setting(p["guild_id"], "recap_channel")
            channel = self.get_channel(int(channel_id)) if channel_id else None
            if channel is not None:
                mention = f"<@{pick['bettor_id']}> " if pick["bettor_id"] else ""
                for chunk in split_message(mention + grading_message(pick, lines, final_try)):
                    await channel.send(chunk, allowed_mentions=discord.AllowedMentions(
                        everyone=False, roles=False, users=True))

    async def run_lock_grading(self, now: Optional[datetime] = None, limit: int = 3):
        """Grade locks of the week the same way as picks: 48 hours after they're submitted."""
        if not AUTOGRADE_AFTER_HOURS:
            return
        now = now or datetime.now(timezone.utc)
        due = iso(now - timedelta(hours=AUTOGRADE_AFTER_HOURS))
        retry = iso(now - timedelta(hours=12))
        rows = db().execute(
            """SELECT * FROM locks WHERE status = 'open' AND created_at <= ?
               AND COALESCE(autograde_tries, 0) < ? AND (autograde_at IS NULL OR autograde_at <= ?)
               ORDER BY created_at LIMIT ?""", (due, AUTOGRADE_MAX_TRIES, retry, limit)).fetchall()
        for r in rows:
            count_key = f"autogrades:{now.astimezone(TZ).date().isoformat()}"
            used = int(get_setting(r["guild_id"], count_key) or 0)
            tries = (r["autograde_tries"] or 0) + 1
            db().execute("UPDATE locks SET autograde_at = ?, autograde_tries = ? WHERE id = ?",
                         (now_iso(), tries, r["id"]))
            db().commit()
            like = {"id": -r["id"], "created_at": r["created_at"], "platform": "a weekly pick contest",
                    "sport": r["sport"], "description": r["text"], "notes": None}
            try:
                by_n, used_ai = await lookup_items(like, [(1, r["text"])], True,
                                                   used < AUTOGRADE_DAILY_LIMIT, context_legs=[])
            except Exception:
                log.exception("Grading lock %s failed", r["id"])
                continue
            if used_ai:
                set_setting(r["guild_id"], count_key, str(used + 1))
            res = by_n.get(1) or {}
            result = str(res.get("result", "unknown")).lower()
            channel_id = get_setting(r["guild_id"], "recap_channel")
            channel = self.get_channel(int(channel_id)) if channel_id else None
            if result in ("hit", "miss", "push"):
                status = {"hit": "win", "miss": "loss", "push": "push"}[result]
                settle_lock(r["id"], status, clip(str(res.get("why") or ""), 120) or None)
                if channel is not None:
                    await channel.send(
                        f"🔒 Lock graded: <@{r['user_id']}> {LOCK_ICON[status]} {clip(r['text'], 100)}"
                        + (f" · {clip(str(res.get('why')), 100)}" if res.get("why") else "")
                        + f"\n-# Wrong? Fix it with `/lockresult lock_id:{r['id']}`.",
                        allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=True))
            elif tries >= AUTOGRADE_MAX_TRIES and channel is not None:
                await channel.send(
                    f"🔒 I couldn't grade <@{r['user_id']}>'s lock: {clip(r['text'], 100)}. "
                    f"Settle it with `/lockresult lock_id:{r['id']}`.",
                    allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=True))

    async def check_limits(self, now: Optional[datetime] = None):
        """Private heads-up to anyone past the weekly loss limit they set, once a week."""
        now = now or datetime.now(TZ)
        week = week_id(now)
        for r in db().execute("SELECT guild_id, key, value FROM settings WHERE key LIKE 'limit:%'").fetchall():
            uid = r["key"].split(":", 1)[1]
            if get_setting(r["guild_id"], f"limitwarned:{uid}") == week:
                continue
            net = weekly_net(r["guild_id"], uid, now)
            if net > -float(r["value"]):
                continue
            set_setting(r["guild_id"], f"limitwarned:{uid}", week)
            try:
                user = await self.fetch_user(int(uid))
                await user.send(
                    f"Heads-up: you're {signed(net)} this week (since Monday), past the "
                    f"{money(float(r['value']))} weekly limit you set. Nothing's been blocked; this is just "
                    "the reminder you asked for. Change it with `/limit` in the server.")
            except Exception:
                log.info("Couldn't DM user %s about their limit", uid)

    async def run_live_grading(self, now: Optional[datetime] = None, limit: int = 40):
        """Settle picks and locks from the free scoreboard as soon as their games go final."""
        now = now or datetime.now(timezone.utc)
        recent = iso(now - timedelta(days=LIVE_WINDOW_DAYS))
        recheck = iso(now - timedelta(minutes=LIVE_RECHECK_MINUTES))
        picks = db().execute(
            """SELECT * FROM picks WHERE status = 'open' AND created_at >= ?
               AND (live_checked_at IS NULL OR live_checked_at <= ?)
               ORDER BY live_checked_at IS NOT NULL, live_checked_at LIMIT ?""", (recent, recheck, limit)).fetchall()
        for p in picks:
            db().execute("UPDATE picks SET live_checked_at = ? WHERE id = ?", (iso(now), p["id"]))
            db().commit()
            items, single = open_items(p)
            if not items or not leagues_for(p["sport"]) or not any(parse_simple_leg(t) or parse_prop_leg(t)
                                                                    for _, t in items):
                continue
            try:
                found = await free_grade(p, items)
            except Exception:
                log.exception("Live check failed for pick %s", p["id"])
                continue
            if not found:
                continue
            by_n = {n: {"result": r, "why": w} for n, (r, w) in found.items()}
            lines, _ = apply_results(p["guild_id"], p["id"], [(n, t) for n, t in items if n in by_n], by_n,
                                     single, only_graded=True)
            after = get_pick(p["guild_id"], p["id"])
            flex_hold = (after["status"] == "open" and after["platform"].lower() == "prizepicks"
                         and any(leg["status"] == "miss" for leg in get_legs(after["id"])))
            if after["status"] == "open" and not flex_hold:
                continue  # some legs done, the rest still going: say nothing yet
            channel = await recap_channel_for(self, after["guild_id"])
            if channel is not None:
                mention = f"<@{after['bettor_id']}> " if after["bettor_id"] else ""
                msg = grading_message(after, lines, False).replace("🤖 Looked up results for", "⚡ Final:", 1)
                for chunk in split_message(mention + msg):
                    await channel.send(chunk, allowed_mentions=discord.AllowedMentions(
                        everyone=False, roles=False, users=True))
        locks = db().execute(
            """SELECT * FROM locks WHERE status = 'open' AND created_at >= ?
               AND (live_checked_at IS NULL OR live_checked_at <= ?) LIMIT ?""", (recent, recheck, limit)).fetchall()
        for lk in locks:
            db().execute("UPDATE locks SET live_checked_at = ? WHERE id = ?", (iso(now), lk["id"]))
            db().commit()
            if not leagues_for(lk["sport"]) or not parse_simple_leg(lk["text"]):
                continue
            like = {"id": -lk["id"], "created_at": lk["created_at"], "sport": lk["sport"], "description": lk["text"]}
            try:
                found = await free_grade(like, [(1, lk["text"])], context_legs=[])
            except Exception:
                log.exception("Live check failed for lock %s", lk["id"])
                continue
            if 1 in found:
                result, why = found[1]
                status = {"hit": "win", "miss": "loss", "push": "push"}[result]
                settle_lock(lk["id"], status, why)
                await post_lock_result(self, lk, status, why)

    async def run_game_pings(self, now: Optional[datetime] = None):
        """DM people who turned on /pings before their games start and at halftime (one DM per game)."""
        now = now or datetime.now(timezone.utc)
        users = [(r["guild_id"], int(r["key"].split(":", 1)[1]))
                 for r in db().execute("SELECT guild_id, key FROM settings WHERE key LIKE 'pings:%' AND value = 'on'")]
        recent = iso(now - timedelta(days=LIVE_WINDOW_DAYS))
        for guild_id, uid in users:
            picks = db().execute("SELECT * FROM picks WHERE guild_id = ? AND bettor_id = ? AND status = 'open' "
                                 "AND created_at >= ? ORDER BY id", (guild_id, uid, recent)).fetchall()
            due: dict[tuple[str, str], dict] = {}  # (event id, kind) -> {"ev", "picks"}
            for p in picks:
                try:
                    games = await games_for_pick(p)
                except Exception:
                    log.exception("Ping lookup failed for pick %s", p["id"])
                    continue
                for ev in games:
                    when = event_time(ev)
                    if when and ev["state"] == "pre" and timedelta(0) < when - now <= timedelta(minutes=PING_MINUTES):
                        kind = "start"
                    elif ev.get("status_name") == "STATUS_HALFTIME" and all(t["score"] is not None for t in ev["teams"]):
                        kind = "half"
                    else:
                        continue
                    if db().execute("SELECT 1 FROM pings WHERE pick_id = ? AND event_id = ? AND kind = ?",
                                    (p["id"], ev["id"], kind)).fetchone():
                        continue
                    due.setdefault((ev["id"], kind), {"ev": ev, "picks": []})["picks"].append(p)
            for (event_id, kind), item in due.items():
                ev, ps = item["ev"], item["picks"]
                away = next(t for t in ev["teams"] if not t["home"])
                home = next(t for t in ev["teams"] if t["home"])
                if kind == "start":
                    mins = max(1, round((event_time(ev) - now).total_seconds() / 60))
                    head = f"⏰ {away['short']} @ {home['short']} starts in {mins} min."
                else:
                    head = f"🏈 Halftime: {away['short']} {away['score']:g}, {home['short']} {home['score']:g}."
                riding = "\n".join(f"• Pick `#{p['id']}`: {clip(p['description'], 80)}" for p in ps[:10])
                db().executemany("INSERT OR IGNORE INTO pings (pick_id, event_id, kind) VALUES (?,?,?)",
                                 [(p["id"], event_id, kind) for p in ps])
                db().commit()
                try:
                    user = await self.fetch_user(uid)
                    await user.send(f"{head} Riding on it:\n{riding}")
                except Exception:
                    log.info("Couldn't DM user %s a game ping", uid)

    async def post_today(self, now: datetime):
        for r in db().execute("SELECT guild_id, value FROM settings WHERE key = 'today_channel'").fetchall():
            today = now.date().isoformat()
            if now.hour < TODAY_HOUR or get_setting(r["guild_id"], "last_today") == today:
                continue
            set_setting(r["guild_id"], "last_today", today)
            channel = self.get_channel(int(r["value"]))
            if channel is None:
                continue
            embeds = [e for e in [await today_embed(p, now) for p in group_leagues(r["guild_id"])[:10]] if e]
            if embeds:
                await channel.send("📅 Today's games", embeds=embeds)

    async def run_schedules(self, now: Optional[datetime] = None):
        now = now or datetime.now(TZ)
        for job in (self.run_live_grading, lambda n: grade_pickem_games(self, n), lambda n: post_hall_of_fame(self),
                    self.run_game_pings, lambda n: self.post_today(n.astimezone(TZ)),
                    lambda n: grade_survivor(self, n), lambda n: send_reminders(self, n),
                    lambda n: post_backups(self, n), lambda n: update_sweats(self, n),
                    lambda n: run_injury_alerts(self, n), lambda n: grade_kalshi(self, n),
                    lambda n: grade_group_parlays(self, n), lambda n: post_weekly_group_parlay(self, n),
                    lambda n: offer_pp_settlements(self, n), lambda n: one_leg_alerts(self, n),
                    lambda n: react_to_slips(self, n), lambda n: award_coins(self, n), lambda n: close_markets(self, n),
                    lambda n: takes_due(self, n), lambda n: post_potd(self, n), lambda n: grade_potd(self, n),
                    lambda n: reveal_hidden(self, n)):
            try:
                await job(now.astimezone(timezone.utc))
            except Exception:
                log.exception("Live job failed")
        await self.run_autograde(now.astimezone(timezone.utc))
        await self.run_lock_grading(now.astimezone(timezone.utc))
        await self.check_limits(now)
        try:
            await announce_milestones(self, now.astimezone(timezone.utc))
        except Exception:
            log.exception("Milestones failed")
        today = now.date().isoformat()
        rows = db().execute("SELECT guild_id, value FROM settings WHERE key = 'recap_channel'").fetchall()
        for row in rows:
            guild_id, channel = row["guild_id"], self.get_channel(int(row["value"]))
            if channel is None:
                continue
            if (now.weekday() == RECAP_DAY and now.hour >= RECAP_HOUR
                    and get_setting(guild_id, "last_recap") != today):
                set_setting(guild_id, "last_recap", today)
                await channel.send(embed=build_recap(guild_id))
                roles_line = await assign_hot_roles(self, guild_id)
                if roles_line:
                    await channel.send(roles_line, allowed_mentions=discord.AllowedMentions.none())
            last_month = (now.replace(day=1) - timedelta(days=1))
            month_key = last_month.strftime("%Y-%m")
            if (now.day == 1 and now.hour >= REMIND_HOUR
                    and get_setting(guild_id, "last_awards") != month_key):
                set_setting(guild_id, "last_awards", month_key)
                await channel.send(embed=build_awards(guild_id, last_month.year, last_month.month))
            if now.hour >= REMIND_HOUR and get_setting(guild_id, "last_remind") != today:
                set_setting(guild_id, "last_remind", today)
                text = build_reminders(guild_id)
                if text:
                    await channel.send(text, allowed_mentions=discord.AllowedMentions(
                        everyone=False, roles=False, users=True))

    # ---- messages ----------------------------------------------------------

    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if message.guild is None:
            dm_images = [a for a in message.attachments
                         if (a.content_type or "").split(";")[0].strip() in IMAGE_TYPES]
            if dm_images:
                await handle_dm_slip(self, message, dm_images[0])
            return
        images = [a for a in message.attachments
                  if (a.content_type or "").split(";")[0].strip() in IMAGE_TYPES]
        if message.channel.id in self.receipt_channels and images:
            for attachment in images[:4]:
                await self.handle_slip(message, attachment)
            return
        if self.user is not None and self.is_question(message):
            await self.handle_ask(message)

    def bot_role_ids(self, message: discord.Message) -> set[int]:
        return {r.id for r in message.role_mentions
                if r.is_bot_managed() and r.tags and r.tags.bot_id == self.user.id}

    def is_question(self, message: discord.Message) -> bool:
        """An explicit @mention of the bot (or its role), or a reply to one of its answers.
        Replies to pick cards don't count, so "nice hit" doesn't spend a question."""
        if re.search(rf"<@!?{self.user.id}>", message.content) or self.bot_role_ids(message):
            return True
        ref = message.reference.resolved if message.reference else None
        return (isinstance(ref, discord.Message) and ref.author.id == self.user.id
                and not ref.embeds and not ref.components and bool(ref.content))

    async def handle_ask(self, message: discord.Message):
        question = re.sub(rf"<@!?{self.user.id}>", "", message.content)
        for role_id in self.bot_role_ids(message):
            question = question.replace(f"<@&{role_id}>", "")
        question = question.strip()
        if not question:
            await message.reply(
                "Ask me about a player, team or matchup, like "
                f"`@{self.user.display_name} how has donk played on LAN lately?`",
                mention_author=False)
            return
        if not ai_enabled():
            await message.reply("Questions aren't switched on yet: add an `ANTHROPIC_API_KEY` "
                                "variable to the bot on Railway.", mention_author=False)
            return
        wait = self.ask_cooldowns.get(message.author.id, 0) + ASK_COOLDOWN_SECONDS - time.monotonic()
        if wait > 0:
            await message.reply(f"Give me {int(wait) + 1}s before the next question.",
                                mention_author=False)
            return
        count_key = f"asks:{datetime.now(TZ).date().isoformat()}"
        used = int(get_setting(message.guild.id, count_key) or 0)
        if used >= ASK_DAILY_LIMIT:
            await message.reply(f"That's the server's {ASK_DAILY_LIMIT} questions for today. "
                                "Back tomorrow.", mention_author=False)
            return
        self.ask_cooldowns[message.author.id] = time.monotonic()
        set_setting(message.guild.id, count_key, str(used + 1))

        user_text = f"Question from {message.author.display_name}: {question}"
        ref = message.reference.resolved if message.reference else None
        if isinstance(ref, discord.Message) and ref.author.id == self.user.id and ref.content:
            user_text = f"They're replying to your earlier answer:\n{ref.content[:1500]}\n\n" + user_text
        context = build_ask_context(message.guild.id, str(message.author.id), question)
        if context:
            user_text += "\n\nThe group's own data:\n" + context
        system = ASK_SYSTEM.format(bot_name=self.user.display_name,
                                   today=datetime.now(TZ).strftime("%A, %B %d, %Y"))
        try:
            async with message.channel.typing():
                answer, sources = await ask_claude(system, user_text)
        except Exception:
            log.exception("Question failed")
            await message.reply("I couldn't get an answer just now. Try again in a minute.",
                                mention_author=False)
            return
        if sources:
            answer += "\n\n-# Sources: " + " · ".join(f"<{u}>" for u in sources)
        for i, chunk in enumerate(split_message(answer or "I came up empty on that one.")):
            if i == 0:
                await message.reply(chunk, mention_author=False,
                                    allowed_mentions=discord.AllowedMentions.none())
            else:
                await message.channel.send(chunk, allowed_mentions=discord.AllowedMentions.none())

    async def handle_slip(self, message: discord.Message, attachment: discord.Attachment):
        slip = None
        if ai_enabled() and attachment.size <= MAX_IMAGE_BYTES:
            try:
                async with message.channel.typing():
                    slip = await read_slip(attachment)
            except Exception:
                log.exception("Could not read slip %s", attachment.url)

        # Couldn't read it (or reading is off): let the poster fill in a short form.
        if slip is None or slip["cost"] is None:
            note = "Got it. Tap below to log this slip."
            if ai_enabled():
                note = "I couldn't read that one cleanly. Tap below to log it by hand."
            await message.reply(note, view=log_slip_view(message.author.id),
                                mention_author=False)
            return

        legs = [str(leg).strip() for leg in (slip.get("legs") or []) if str(leg).strip()]
        payout = slip["payout"] if slip["payout"] is not None else 0.0
        pick_id = insert_pick(
            guild_id=message.guild.id,
            bettor_key=str(message.author.id),
            bettor_name=message.author.display_name,
            bettor_id=message.author.id,
            logged_by=message.author.id,
            platform=str(slip.get("platform") or "Other")[:40],
            sport=(str(slip["sport"])[:60] if slip.get("sport") else None),
            description=str(slip.get("description") or "Slip")[:200],
            legs="\n".join(legs) or None,
            cost=slip["cost"],
            payout=payout,
            slip_url=message.jump_url,
        )
        if slip["status"] != "open":
            settle_pick(message.guild.id, pick_id, slip["status"], slip["returned"])

        p = get_pick(message.guild.id, pick_id)
        note = None
        if slip["payout"] is None:
            note = f"I couldn't read the payout. Fix it with `/edit pick_id:{pick_id}`."
        view = settle_view(pick_id) if p["status"] == "open" else None
        await message.reply(content=note, embed=pick_embed(p), view=view,
                            mention_author=False)


bot = PicksBot()

PLATFORMS = [
    app_commands.Choice(name=n, value=n)
    for n in ("Kalshi", "PrizePicks", "Sportsbook", "Other")
]
OUTCOMES = [
    app_commands.Choice(name="Win", value="win"),
    app_commands.Choice(name="Loss", value="loss"),
    app_commands.Choice(name="Push", value="push"),
    app_commands.Choice(name="Void", value="void"),
    app_commands.Choice(name="Reopen (undo result)", value="open"),
]
LEG_RESULTS = [
    app_commands.Choice(name="Hit", value="hit"),
    app_commands.Choice(name="Miss", value="miss"),
    app_commands.Choice(name="Push", value="push"),
    app_commands.Choice(name="Not graded yet", value="open"),
]


def view_or_missing(p: sqlite3.Row):
    return settle_view(p["id"]) if p["status"] == "open" else discord.utils.MISSING


# ---- pick commands ----------------------------------------------------------

@bot.tree.command(name="pick", description="Log a pick")
@app_commands.guild_only()
@app_commands.describe(
    platform="Where the bet was placed",
    description="The play in one line, e.g. '3-leg NFL combo'",
    cost="Amount risked",
    payout="Total paid back if it wins (max payout)",
    legs="Optional: the legs, separated by semicolons",
    sport="Optional: NFL, CS2, NBA...",
    member="Optional: log it for another member (defaults to you)",
    label="Optional: log it under a name that isn't a Discord user",
    hidden="Optional: keep the details secret until it settles (proof you called it, no copycats)",
)
@app_commands.choices(platform=PLATFORMS)
async def pick_cmd(
    interaction: discord.Interaction,
    platform: app_commands.Choice[str],
    description: app_commands.Range[str, 1, 200],
    cost: app_commands.Range[float, 0],
    payout: app_commands.Range[float, 0],
    legs: Optional[app_commands.Range[str, 1, 900]] = None,
    sport: Optional[app_commands.Range[str, 1, 60]] = None,
    member: Optional[discord.Member] = None,
    label: Optional[app_commands.Range[str, 1, 60]] = None,
    hidden: Optional[bool] = None,
):
    key, name, bettor_id = resolve_bettor(interaction, member, label)
    leg_text = None
    if legs:
        leg_text = "\n".join(part.strip() for part in legs.split(";") if part.strip()) or None
    pick_id = insert_pick(
        guild_id=interaction.guild_id, bettor_key=key, bettor_name=name,
        bettor_id=bettor_id, logged_by=interaction.user.id, platform=platform.value,
        sport=sport, description=description, legs=leg_text, cost=cost, payout=payout,
    )
    p = get_pick(interaction.guild_id, pick_id)
    if hidden:
        db().execute("UPDATE picks SET hidden = 1 WHERE id = ?", (pick_id,))
        db().commit()
        p = get_pick(interaction.guild_id, pick_id)
        await interaction.response.send_message(embed=private_card(p), view=settle_view(pick_id), ephemeral=True)
        await interaction.followup.send(
            f"🔒 **{name}** locked in a hidden {platform.value} pick (`#{pick_id}`) at "
            f"{datetime.now(TZ):%-I:%M %p}. It's revealed when it settles.")
        return
    await interaction.response.send_message(embed=pick_embed(p), view=settle_view(pick_id))


@bot.tree.command(name="leg", description="Grade one leg of a parlay")
@app_commands.guild_only()
@app_commands.describe(pick_id="The pick number", leg="The leg number shown on the pick",
                       result="How that leg finished")
@app_commands.choices(result=LEG_RESULTS)
async def leg_cmd(interaction: discord.Interaction, pick_id: int, leg: int,
                  result: app_commands.Choice[str]):
    p = get_pick(interaction.guild_id, pick_id)
    if p is None:
        await interaction.response.send_message(f"No pick #{pick_id}.", ephemeral=True)
        return
    if not can_edit(interaction, p):
        await interaction.response.send_message(
            f"Only {p['bettor_name']} or a mod can grade this one.", ephemeral=True)
        return
    legs = get_legs(pick_id)
    if not legs:
        await interaction.response.send_message(
            f"Pick #{pick_id} has no legs listed. Add them with `/edit pick_id:{pick_id} legs:`.",
            ephemeral=True)
        return
    if not 1 <= leg <= len(legs):
        await interaction.response.send_message(
            f"Pick #{pick_id} has legs 1 to {len(legs)}.", ephemeral=True)
        return
    p, note = grade_leg(interaction.guild_id, pick_id, leg, result.value)
    await interaction.response.send_message(content=note or None, embed=pick_embed(p),
                                            view=view_or_missing(p))


@bot.tree.command(name="grade", description="Look up results for a pick's open legs now")
@app_commands.guild_only()
@app_commands.describe(pick_id="The pick number")
async def grade_cmd(interaction: discord.Interaction, pick_id: int):
    p = get_pick(interaction.guild_id, pick_id)
    if p is None:
        await interaction.response.send_message(f"No pick #{pick_id}.", ephemeral=True)
        return
    if not can_edit(interaction, p):
        await interaction.response.send_message(
            f"Only {p['bettor_name']} or a mod can grade this one.", ephemeral=True)
        return
    if p["status"] != "open":
        await interaction.response.send_message(f"Pick #{pick_id} is already settled.", ephemeral=True)
        return
    await interaction.response.defer(thinking=True)
    try:
        pick, lines, _, _ = await autograde(interaction.guild_id, pick_id)
    except Exception:
        log.exception("Grading pick %s failed", pick_id)
        await interaction.followup.send("I couldn't look that up just now. Try again in a minute.")
        return
    if not lines:
        await interaction.followup.send(
            f"Every leg on #{pick_id} is already graded. Settle it with `/result pick_id:{pick_id}`.")
        return
    msg = grading_message(pick, lines, final_try=False).replace(
        "Still open. I'll look again in 12 hours.", "Still open. Try `/grade` again once it's final."
        + ("" if ai_enabled() else " (Without an API key I can only look up moneylines, spreads and "
                                    "totals for major leagues.)"))
    await interaction.followup.send(split_message(msg)[0], embed=pick_embed(pick),
                                    view=view_or_missing(pick))


@bot.tree.command(name="result", description="Settle a pick")
@app_commands.guild_only()
@app_commands.describe(
    pick_id="The pick number (shown as #12 on the pick)",
    outcome="How it finished",
    returned="Optional: exact amount paid back, for partial payouts or cash-outs",
)
@app_commands.choices(outcome=OUTCOMES)
async def result_cmd(
    interaction: discord.Interaction,
    pick_id: int,
    outcome: app_commands.Choice[str],
    returned: Optional[app_commands.Range[float, 0]] = None,
):
    p = get_pick(interaction.guild_id, pick_id)
    if p is None:
        await interaction.response.send_message(f"No pick #{pick_id}.", ephemeral=True)
        return
    if not can_edit(interaction, p):
        await interaction.response.send_message(
            f"Only {p['bettor_name']} or a mod can settle this one.", ephemeral=True)
        return
    p = settle_pick(interaction.guild_id, pick_id, outcome.value, returned)
    await interaction.response.send_message(embed=pick_embed(p), view=view_or_missing(p))


@bot.tree.command(name="open", description="Picks still waiting on a result")
@app_commands.guild_only()
@app_commands.describe(member="Optional: only this member's picks",
                       label="Optional: only picks under this name")
async def open_cmd(interaction: discord.Interaction,
                   member: Optional[discord.Member] = None,
                   label: Optional[str] = None):
    sql = "SELECT * FROM picks WHERE guild_id = ? AND status = 'open'"
    args: list = [interaction.guild_id]
    if member or label:
        key, _, _ = resolve_bettor(interaction, member, label)
        sql += " AND bettor_key = ?"
        args.append(key)
    rows = db().execute(sql + " ORDER BY id", args).fetchall()
    if not rows:
        await interaction.response.send_message("Nothing open right now.")
        return
    lines = [one_liner(p) for p in rows[:20]]
    if len(rows) > 20:
        lines.append(f"…and {len(rows) - 20} more")
    risk = sum(p["cost"] for p in rows)
    e = discord.Embed(title=f"Open picks ({len(rows)})", description="\n".join(lines),
                      color=STATUS["open"][1])
    e.set_footer(text=f"{money(risk)} at risk")
    await interaction.response.send_message(embed=e)


@bot.tree.command(name="record", description="Someone's record, profit, ROI and leg hit rate")
@app_commands.guild_only()
@app_commands.describe(member="Optional: defaults to you",
                       label="Optional: a name that isn't a Discord user")
async def record_cmd(interaction: discord.Interaction,
                     member: Optional[discord.Member] = None,
                     label: Optional[str] = None):
    key, name, _ = resolve_bettor(interaction, member, label)
    stats = compute_stats(interaction.guild_id, key)
    if not stats:
        await interaction.response.send_message(f"No picks logged for {name} yet.")
        return
    s = stats[0]
    streak = current_streak(interaction.guild_id, key)
    e = discord.Embed(title=f"{s['name']} · {record_line(s)}" + (f" · {streak}" if streak else ""),
                      color=0x2ECC71 if s["net"] >= 0 else 0xE74C3C)
    e.add_field(name="Staked", value=money(s["staked"]))
    e.add_field(name="Returned", value=money(s["returned"]))
    e.add_field(name="Net", value=signed(s["net"]))
    e.add_field(name="ROI", value=f"{s['roi']:+.1f}%")
    e.add_field(name="Open", value=f"{s['open']} ({money(s['open_risk'])} at risk)")
    rate = hit_rate(leg_counts(interaction.guild_id, key))
    if rate:
        e.add_field(name="Legs", value=rate)
    season = current_season(interaction.guild_id)
    if season:
        mine = [x for x in season_stats(interaction.guild_id, season) if x["key"] == key]
        e.add_field(name=season["name"], value=f"{record_line(mine[0])} · {signed(mine[0]['net'])}" if mine
                    else "no settled picks yet")
    got = earned_badges(interaction.guild_id, key)
    if got:
        e.add_field(name=f"Badges {len(got)}/{len(BADGES)}", value=badge_line(got) + " · `/achievements`")
    recent = db().execute(
        """SELECT * FROM picks WHERE guild_id = ? AND bettor_key = ? AND status != 'open'
           ORDER BY settled_at DESC, id DESC LIMIT 5""",
        (interaction.guild_id, key)).fetchall()
    if recent:
        lines = [
            f"{STATUS[p['status']][0].split()[0]} `#{p['id']}` "
            f"{signed((p['returned'] or 0.0) - p['cost'])} · {clip(p['description'], 60)}"
            for p in recent
        ]
        e.add_field(name="Last 5 settled", value="\n".join(lines), inline=False)
    await interaction.response.send_message(embed=e)


LEADERBOARD_PERIODS = [app_commands.Choice(name=n, value=v) for n, v in
                       (("This season", "season"), ("Last 7 days", "week"), ("This month", "month"),
                        ("All time", "all"))]


LEADERBOARD_PERIODS = [app_commands.Choice(name=n, value=v) for n, v in
                       (("This season", "season"), ("Last 7 days", "week"), ("This month", "month"),
                        ("All time", "all"))]
RANK_BY = [app_commands.Choice(name="Profit ($)", value="net"), app_commands.Choice(name="Units", value="units"),
           app_commands.Choice(name="ROI", value="roi")]
PRESEASON_CHOICES = [app_commands.Choice(name="Count preseason picks", value="in"),
                     app_commands.Choice(name="Leave preseason out", value="out")]


@bot.tree.command(name="leaderboard", description="Everyone ranked by net profit (this season, if one's running)")
@app_commands.guild_only()
@app_commands.describe(period="Optional: season (default), last 7 days, this month or all time",
                       sport="Optional: one sport only",
                       preseason="Optional: count preseason picks or not (default: the server setting)",
                       rank_by="Optional: profit (default), units or ROI", platform="Optional: one platform")
@app_commands.choices(period=LEADERBOARD_PERIODS, sport=SPORT_CHOICES, preseason=PRESEASON_CHOICES, rank_by=RANK_BY,
                      platform=[app_commands.Choice(name=n, value=n) for n in ("Kalshi", "PrizePicks", "Sportsbook", "Other")])
async def leaderboard_cmd(interaction: discord.Interaction, period: Optional[app_commands.Choice[str]] = None,
                          sport: Optional[app_commands.Choice[str]] = None,
                          preseason: Optional[app_commands.Choice[str]] = None,
                          rank_by: Optional[app_commands.Choice[str]] = None,
                          platform: Optional[app_commands.Choice[str]] = None):
    gid = interaction.guild_id
    mode = period.value if period else "season"
    season = current_season(gid) if mode == "season" else None
    if mode == "season" and season is None:
        mode = "all"
    now = datetime.now(TZ)
    since = until = None
    if season:
        since, until, label = season["started_at"], season["ended_at"], season["name"]
    elif mode == "week":
        since, label = iso(now - timedelta(days=7)), "last 7 days"
    elif mode == "month":
        since, label = iso(now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)), now.strftime("%B")
    else:
        label = "all time"
    include_pre = (preseason.value == "in") if preseason else get_setting(gid, "exclude_preseason") != "on"
    sport_name = sport.value if sport else None
    plat = platform.value if platform else None
    stats = [s for s in compute_stats(gid, since=since, until=until, sport=sport_name, preseason=include_pre,
                                      platform=plat)
             if s["wins"] + s["losses"] + s["pushes"] > 0]
    by = rank_by.value if rank_by else "net"
    for s in stats:
        s["unit"] = unit_size_for(gid, s["key"])
        s["units"] = s["net"] / s["unit"] if s["unit"] else 0.0
    if by != "net":
        stats.sort(key=lambda s: s[by], reverse=True)
    moves = rank_movement(gid, [s["key"] for s in stats], since, until, sport=sport_name, preseason=include_pre,
                          platform=plat) if by == "net" else {}
    title = f"Leaderboard · {label}" + (f" · {sport_name}" if sport_name else "") + (f" · {plat}" if plat else "") \
        + {"units": " · by units", "roi": " · by ROI"}.get(by, "")
    if not stats:
        await interaction.response.send_message(
            f"No settled picks for {label}" + (f" in {sport_name}" if sport_name else "") + " yet."
            + (" Try `/leaderboard period:All time`." if mode != "all" else ""))
        return
    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, s in enumerate(stats[:25]):
        rank = medals[i] if i < 3 else f"`{i + 1}.`"
        streak = current_streak(gid, s["key"]) if not sport_name else ""
        mv = moves.get(s["key"])
        arrow = f" ▲{mv}" if mv and mv > 0 else (f" ▼{-mv}" if mv and mv < 0 else "")
        value = f"{s['units']:+.1f}u" if by == "units" else signed(s["net"])
        lines.append(f"{rank} **{s['name']}**{arrow} · {record_line(s)} · "
                     f"{value} · ROI {s['roi']:+.1f}%" + (f" · {streak}" if streak else ""))
    e = discord.Embed(title=title, description="\n".join(lines), color=BRAND)
    inv_sql, inv_args = "SELECT * FROM picks WHERE guild_id = ? AND status IN ('win', 'loss')", [gid]
    if since:
        inv_sql += " AND settled_at >= ?"
        inv_args.append(since)
    if until:
        inv_sql += " AND settled_at < ?"
        inv_args.append(until)
    inv = [p for p in db().execute(inv_sql, inv_args).fetchall()
           if (not sport_name or sport_group(p["sport"]) == sport_name) and (include_pre or not p["preseason"])
           and (not plat or p["platform"] == plat)]
    inv_text = inverse_line(inv)
    if inv_text:
        e.add_field(name="If you'd faded everybody", value=inv_text, inline=False)
    e.set_footer(text="Settled picks only · record is W-L(-Push) · ▲▼ = places moved this week"
                      + (" · 1 unit = your /bankroll unit, or your average stake" if by == "units" else "")
                      + ("" if include_pre else " · preseason left out"))
    await interaction.response.send_message(embed=e)


@bot.tree.command(name="edit", description="Fix a pick's details")
@app_commands.guild_only()
@app_commands.describe(pick_id="The pick number", description="New one-line description",
                       cost="New amount risked", payout="New max payout",
                       legs="New legs, separated by semicolons (resets leg grades)")
async def edit_cmd(
    interaction: discord.Interaction,
    pick_id: int,
    description: Optional[app_commands.Range[str, 1, 200]] = None,
    cost: Optional[app_commands.Range[float, 0]] = None,
    payout: Optional[app_commands.Range[float, 0]] = None,
    legs: Optional[app_commands.Range[str, 1, 900]] = None,
):
    p = get_pick(interaction.guild_id, pick_id)
    if p is None:
        await interaction.response.send_message(f"No pick #{pick_id}.", ephemeral=True)
        return
    if not can_edit(interaction, p):
        await interaction.response.send_message(
            f"Only {p['bettor_name']} or a mod can edit this one.", ephemeral=True)
        return
    updates: dict = {}
    if description is not None:
        updates["description"] = description
    if cost is not None:
        updates["cost"] = cost
    if payout is not None:
        updates["payout"] = payout
    if legs is not None:
        updates["legs"] = "\n".join(x.strip() for x in legs.split(";") if x.strip()) or None
    if not updates:
        await interaction.response.send_message(
            "Nothing to change. Fill in at least one field.", ephemeral=True)
        return
    # If a settled pick was paid the standard amount, keep it in line with the
    # corrected numbers. A custom amount (partial payout, cash-out) is left alone.
    was_standard = (p["status"] != "open" and
                    p["returned"] == default_return(p["status"], p["cost"], p["payout"]))
    sets = ", ".join(f"{col} = ?" for col in updates)
    db().execute(f"UPDATE picks SET {sets} WHERE id = ?", (*updates.values(), pick_id))
    db().commit()
    if "legs" in updates:
        set_legs(pick_id, updates["legs"])
    p = get_pick(interaction.guild_id, pick_id)
    if was_standard and ("cost" in updates or "payout" in updates):
        p = settle_pick(interaction.guild_id, pick_id, p["status"])
    await interaction.response.send_message(embed=pick_embed(p), view=view_or_missing(p))


@bot.tree.command(name="delete", description="Remove a pick")
@app_commands.guild_only()
@app_commands.describe(pick_id="The pick number")
async def delete_cmd(interaction: discord.Interaction, pick_id: int):
    p = get_pick(interaction.guild_id, pick_id)
    if p is None:
        await interaction.response.send_message(f"No pick #{pick_id}.", ephemeral=True)
        return
    if not can_edit(interaction, p):
        await interaction.response.send_message(
            f"Only {p['bettor_name']} or a mod can delete this one.", ephemeral=True)
        return
    db().execute("DELETE FROM legs WHERE pick_id = ?", (pick_id,))
    db().execute("DELETE FROM follows WHERE pick_id = ?", (pick_id,))
    db().execute("DELETE FROM picks WHERE id = ?", (pick_id,))
    db().commit()
    await interaction.response.send_message(
        f"Deleted pick #{pick_id} ({p['bettor_name']}: {clip(p['description'], 80)}).")


EXPORT_FORMATS = [
    app_commands.Choice(name="Excel (Kalshi, PrizePicks and Summary tabs)", value="xlsx"),
    app_commands.Choice(name="CSV (one plain list)", value="csv"),
]


@bot.tree.command(name="export", description="Download every pick as a spreadsheet")
@app_commands.guild_only()
@app_commands.describe(format="Excel by default")
@app_commands.choices(format=EXPORT_FORMATS)
async def export_cmd(interaction: discord.Interaction,
                     format: Optional[app_commands.Choice[str]] = None):
    rows = db().execute(
        "SELECT * FROM picks WHERE guild_id = ? ORDER BY id", (interaction.guild_id,)
    ).fetchall()
    if not rows:
        await interaction.response.send_message("No picks to export yet.", ephemeral=True)
        return
    stamp = datetime.now(TZ).strftime("%Y-%m-%d")
    if format is None or format.value == "xlsx":
        data = build_workbook(interaction.guild_id)
        people = len({r["bettor_key"] for r in rows})
        await interaction.response.send_message(
            f"{len(rows)} picks from {people} {'person' if people == 1 else 'people'}.",
            file=discord.File(data, filename=f"picks_{stamp}.xlsx"))
        return
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Pick #", "Logged (UTC)", "Bettor", "Platform", "Sport", "Description",
                     "Legs", "Legs Hit", "Cost", "Max Payout", "Status", "Returned", "Net",
                     "Settled (UTC)", "Slip", "Notes"])
    for p in rows:
        settled = p["status"] != "open"
        legs = get_legs(p["id"])
        legs_text = " | ".join(f"{leg['text']} [{leg['status']}]" for leg in legs)
        legs_hit = f"{sum(1 for leg in legs if leg['status'] == 'hit')}/{len(legs)}" if legs else ""
        writer.writerow([
            p["id"], p["created_at"], p["bettor_name"], p["platform"], p["sport"] or "",
            p["description"], legs_text, legs_hit,
            f"{p['cost']:.2f}", f"{p['payout']:.2f}", p["status"],
            f"{p['returned']:.2f}" if settled else "",
            f"{(p['returned'] or 0.0) - p['cost']:.2f}" if settled else "",
            p["settled_at"] or "", p["slip_url"] or "", p["notes"] or "",
        ])
    data = io.BytesIO(buf.getvalue().encode("utf-8-sig"))  # BOM so Excel reads it right
    await interaction.response.send_message(
        f"{len(rows)} picks.", file=discord.File(data, filename=f"picks_{stamp}.csv"))


# ---- channel setup ----------------------------------------------------------

@bot.tree.command(name="receipts",
                  description="Turn slip logging on or off for this channel")
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
async def receipts_cmd(interaction: discord.Interaction):
    channel_id = interaction.channel_id
    if channel_id in bot.receipt_channels:
        db().execute("DELETE FROM receipt_channels WHERE channel_id = ?", (channel_id,))
        bot.receipt_channels.discard(channel_id)
        msg = "Slip logging is **off** for this channel."
    else:
        db().execute("INSERT OR REPLACE INTO receipt_channels (guild_id, channel_id) VALUES (?, ?)",
                     (interaction.guild_id, channel_id))
        bot.receipt_channels.add(channel_id)
        how = ("I'll read each screenshot and log it automatically."
               if ai_enabled() else
               "I'll reply to each screenshot with a button to log it.")
        msg = f"Slip logging is **on** for this channel. {how}"
    db().commit()
    await interaction.response.send_message(msg)


@bot.tree.command(name="recapchannel",
                  description="Post the weekly recap and open-pick reminders in this channel")
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
async def recapchannel_cmd(interaction: discord.Interaction):
    current = get_setting(interaction.guild_id, "recap_channel")
    if current == str(interaction.channel_id):
        set_setting(interaction.guild_id, "recap_channel", None)
        await interaction.response.send_message("Recaps and reminders are **off** for this channel.")
        return
    set_setting(interaction.guild_id, "recap_channel", str(interaction.channel_id))
    day = DAYS[RECAP_DAY].capitalize()
    recap_time = datetime(2000, 1, 1, RECAP_HOUR).strftime("%-I %p")
    remind_time = datetime(2000, 1, 1, REMIND_HOUR).strftime("%-I %p")
    await interaction.response.send_message(
        f"Got it. I'll post the weekly recap here every **{day} at {recap_time}**, and at "
        f"**{remind_time}** each day I'll ping anyone with picks open {REMIND_AFTER_DAYS}+ days. "
        + (f"When I look up results for picks still open after {AUTOGRADE_AFTER_HOURS} hours, I'll post them "
           "here too. " if AUTOGRADE_AFTER_HOURS else "")
        + "Run `/recap` any time to see this week so far.")


@bot.tree.command(name="recap", description="The last 7 days: who's up, best hit, worst beat")
@app_commands.guild_only()
async def recap_cmd(interaction: discord.Interaction):
    await interaction.response.send_message(embed=build_recap(interaction.guild_id))


# ---- importing an existing tracker -------------------------------------------

async def label_autocomplete(interaction: discord.Interaction, current: str):
    rows = db().execute(
        r"""SELECT bettor_name, COUNT(*) AS n FROM picks WHERE guild_id = ? AND bettor_key LIKE 'label:%'
            AND lower(bettor_name) LIKE ? ESCAPE '\' GROUP BY bettor_key ORDER BY n DESC LIMIT 25""",
        (interaction.guild_id, like_pattern(current))).fetchall()
    return [app_commands.Choice(name=f"{r['bettor_name']} ({r['n']} picks)", value=r["bettor_name"])
            for r in rows]


@bot.tree.command(name="import", description="Add picks from an existing tracker spreadsheet (.xlsx)")
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
@app_commands.describe(file="Your tracker, e.g. Kalshi_Picks_Tracker.xlsx")
async def import_cmd(interaction: discord.Interaction, file: discord.Attachment):
    if not file.filename.lower().endswith(".xlsx") or file.size > 10 * 1024 * 1024:
        await interaction.response.send_message("Send an .xlsx file under 10 MB.", ephemeral=True)
        return
    await interaction.response.defer(thinking=True)
    try:
        parsed, problems = parse_tracker(await file.read())
    except Exception:
        log.exception("Import failed")
        await interaction.followup.send("I couldn't read that file. Is it a normal Excel workbook?")
        return
    if not parsed:
        await interaction.followup.send("No picks found. " + " ".join(problems[:3]))
        return
    added, skipped = import_picks(interaction.guild_id, interaction.user.id,
                                  interaction.user.display_name, parsed)
    total = sum(added.values())
    lines = [f"Imported **{total}** picks" + (f" ({skipped} were already in, skipped)" if skipped else "") + ":"]
    lines += [f"• {name}: {n}" for name, n in sorted(added.items(), key=lambda kv: -kv[1])]
    unclaimed = [n for n in added if db().execute(
        "SELECT 1 FROM picks WHERE guild_id = ? AND bettor_key = ?",
        (interaction.guild_id, f"label:{n.lower()}")).fetchone()]
    if unclaimed:
        lines.append("\nTo put these on someone's Discord account, they run `/claim name:<their name>` "
                     "(or a mod adds `member:`). Leave Claudia as a name on its own.")
    if problems:
        lines.append("\n" + "\n".join(problems[:5]))
    await interaction.followup.send("\n".join(lines))


@bot.tree.command(name="claim", description="Link picks logged under a name (like imported ones) to a Discord account")
@app_commands.guild_only()
@app_commands.describe(name="The name on the picks, e.g. Levi",
                       member="Optional: who they belong to (defaults to you; mods can pick anyone)")
@app_commands.autocomplete(name=label_autocomplete)
async def claim_cmd(interaction: discord.Interaction, name: str, member: Optional[discord.Member] = None):
    target = member or interaction.user
    if target.id != interaction.user.id and not is_mod(interaction.user):
        await interaction.response.send_message("Only mods can claim picks for someone else.", ephemeral=True)
        return
    key = f"label:{name.strip().lower()}"
    n = db().execute("SELECT COUNT(*) AS n FROM picks WHERE guild_id = ? AND bettor_key = ?",
                     (interaction.guild_id, key)).fetchone()["n"]
    if not n:
        await interaction.response.send_message(f"No unclaimed picks under the name {name}.", ephemeral=True)
        return
    db().execute("UPDATE picks SET bettor_key = ?, bettor_id = ?, bettor_name = ? WHERE guild_id = ? AND bettor_key = ?",
                 (str(target.id), target.id, target.display_name, interaction.guild_id, key))
    db().commit()
    set_setting(interaction.guild_id, f"claim:{name.strip().lower()}", str(target.id))
    await interaction.response.send_message(
        f"Moved **{n}** picks from {name} onto {target.display_name}'s record.")


# ---- players ----------------------------------------------------------------

player_group = app_commands.Group(name="player", description="Track players and teams",
                                  guild_only=True)


async def player_autocomplete(interaction: discord.Interaction, current: str):
    rows = db().execute(
        r"SELECT name, team FROM players WHERE guild_id = ? AND name_key LIKE ? ESCAPE '\' "
        "ORDER BY name LIMIT 25",
        (interaction.guild_id, like_pattern(current))).fetchall()
    return [app_commands.Choice(name=clip(f"{r['name']}" + (f" ({r['team']})" if r["team"] else ""), 100),
                                value=r["name"]) for r in rows]


def player_embed(guild_id: int, p: sqlite3.Row) -> discord.Embed:
    meta = " · ".join(x for x in (p["team"], p["sport"], p["role"]) if x)
    e = discord.Embed(title=p["name"], description=meta or None, color=BRAND)
    notes = player_notes(p["id"], 8)
    if notes:
        lines = [f"`{local_day(n['created_at'])}` **{n['author_name']}**: {n['text']}" for n in notes]
        e.add_field(name="Notes (newest first)", value=clip("\n".join(lines), 1024), inline=False)
    else:
        e.add_field(name="Notes", value=f"None yet. Add one with `/player note name:{p['name']}`.",
                    inline=False)
    counts = leg_counts(guild_id, text_like=p["name"])
    rate = hit_rate(counts)
    if rate or counts["open"]:
        recent = db().execute(
            r"""SELECT l.*, pk.bettor_name FROM legs l JOIN picks pk ON pk.id = l.pick_id
                WHERE pk.guild_id = ? AND lower(l.text) LIKE ? ESCAPE '\'
                ORDER BY l.id DESC LIMIT 5""",
            (guild_id, like_pattern(p["name"]))).fetchall()
        lines = [f"{LEG_ICON[r['status']]} {clip(r['text'], 60)} · {r['bettor_name']} `#{r['pick_id']}`"
                 for r in recent]
        e.add_field(name=f"Group legs on {p['name']}" + (f" · {rate}" if rate else ""),
                    value=clip("\n".join(lines), 1024), inline=False)
    return e


@player_group.command(name="add", description="Add a player, or update their team, sport or role")
@app_commands.describe(name="Player name or handle", team="Team", sport="NFL, CS2...",
                       role="Position or role, e.g. QB, AWPer, IGL")
@app_commands.autocomplete(name=player_autocomplete)
async def player_add(interaction: discord.Interaction,
                     name: str,
                     team: Optional[app_commands.Range[str, 1, 60]] = None,
                     sport: Optional[app_commands.Range[str, 1, 30]] = None,
                     role: Optional[app_commands.Range[str, 1, 40]] = None):
    if not 1 <= len(name.strip()) <= 60:
        await interaction.response.send_message("Names can be up to 60 characters.", ephemeral=True)
        return
    p, created = upsert_player(interaction.guild_id, name, interaction.user.id, team, sport, role)
    msg = f"Added **{p['name']}**." if created else f"Updated **{p['name']}**."
    await interaction.response.send_message(msg, embed=player_embed(interaction.guild_id, p))


@player_group.command(name="note", description="Add a scouting note to a player")
@app_commands.describe(name="Player name (added if new)", note="What you noticed")
@app_commands.autocomplete(name=player_autocomplete)
async def player_note(interaction: discord.Interaction,
                      name: str,
                      note: app_commands.Range[str, 1, 400]):
    if not 1 <= len(name.strip()) <= 60:
        await interaction.response.send_message("Names can be up to 60 characters.", ephemeral=True)
        return
    p, created = upsert_player(interaction.guild_id, name, interaction.user.id)
    add_player_note(p["id"], interaction.user.id, interaction.user.display_name, note.strip())
    msg = f"Noted on **{p['name']}**." + (" (New player added.)" if created else "")
    await interaction.response.send_message(msg, embed=player_embed(interaction.guild_id, p))


@player_group.command(name="view", description="A player's notes and how the group's legs on them went")
@app_commands.describe(name="Player name")
@app_commands.autocomplete(name=player_autocomplete)
async def player_view(interaction: discord.Interaction, name: str):
    p = get_player(interaction.guild_id, name)
    if p is None:
        await interaction.response.send_message(
            f"No player called {name}. Add them with `/player add`.", ephemeral=True)
        return
    await interaction.response.send_message(embed=player_embed(interaction.guild_id, p))


@player_group.command(name="list", description="Every tracked player")
@app_commands.describe(team="Optional: only this team", sport="Optional: only this sport")
async def player_list(interaction: discord.Interaction, team: Optional[str] = None,
                      sport: Optional[str] = None):
    sql = "SELECT * FROM players WHERE guild_id = ?"
    args: list = [interaction.guild_id]
    if team:
        sql += " AND lower(team) = ?"
        args.append(team.strip().lower())
    if sport:
        sql += " AND lower(sport) = ?"
        args.append(sport.strip().lower())
    rows = db().execute(sql + " ORDER BY lower(team), name", args).fetchall()
    if not rows:
        await interaction.response.send_message("No players tracked yet. Start with `/player add`.")
        return
    groups: dict[str, list[str]] = {}
    for r in rows:
        n = db().execute("SELECT COUNT(*) AS n FROM player_notes WHERE player_id = ?",
                         (r["id"],)).fetchone()["n"]
        label = r["name"] + (f" · {r['role']}" if r["role"] else "") + (f" ({n} notes)" if n else "")
        groups.setdefault(r["team"] or "No team", []).append(label)
    e = discord.Embed(title=f"Tracked players ({len(rows)})", color=BRAND)
    for team_name, names in list(groups.items())[:25]:
        e.add_field(name=clip(team_name, 256), value=clip("\n".join(names), 1024), inline=False)
    await interaction.response.send_message(embed=e)


@player_group.command(name="remove", description="Stop tracking a player (deletes their notes)")
@app_commands.describe(name="Player name")
@app_commands.autocomplete(name=player_autocomplete)
async def player_remove(interaction: discord.Interaction, name: str):
    p = get_player(interaction.guild_id, name)
    if p is None:
        await interaction.response.send_message(f"No player called {name}.", ephemeral=True)
        return
    if interaction.user.id != p["created_by"] and not is_mod(interaction.user):
        await interaction.response.send_message(
            "Only whoever added this player or a mod can remove them.", ephemeral=True)
        return
    db().execute("DELETE FROM player_notes WHERE player_id = ?", (p["id"],))
    db().execute("DELETE FROM players WHERE id = ?", (p["id"],))
    db().commit()
    await interaction.response.send_message(f"Removed **{p['name']}** and their notes.")


bot.tree.add_command(player_group)


# ---- help -------------------------------------------------------------------

@bot.tree.command(name="help", description="Everything this bot can do")
async def help_cmd(interaction: discord.Interaction):
    e = discord.Embed(title="What I can do", color=BRAND)
    e.add_field(name="Picks", inline=False, value=(
        "`/pick` log a bet · `/leg` grade a parlay leg · `/grade` look up results now · `/result` settle it\n"
        "`/open` what's pending · `/exposure` open picks by game · `/history` look back with filters\n"
        "`/record` your stats · `/leaderboard` who's up (by week, month, season or sport)\n"
        "`/edit` `/delete` `/undo` fix mistakes · `/export` Excel file with Kalshi, PrizePicks and per-person tabs\n"
        "`/import` add picks from an old tracker · `/claim` put imported picks on your account"))
    e.add_field(name="Live and props", inline=False, value=(
        "`/sweat` live leg-by-leg tracker · `/schedule` your games · `/trend` player hit rates with a chart\n"
        "Props grade free from box scores · injury DMs for your props · `/kalshi link` auto-settles Kalshi picks\n"
        "`/copy` (or 📋 on a card) · `/groupparlay` one leg each · `/wrapped` season story\n"
        "Right-click a message → Apps → **Log as pick** / **Copy this pick** · DM me a slip to log it privately"))
    e.add_field(name="Games and coins", inline=False, value=(
        "`/coins balance` `daily` `top` `give` · `/market create` yes/no bets with coins · `/take add` hot takes\n"
        "`/potd` Prop of the Day (admins: `/potd here`) · `/insights` · `/calc` · `/money` · `/dashboard` web page"))
    e.add_field(name="Sports info", inline=False, value=(
        "`/sports box` `matchup` `weather` `injuries` `standings` `rankings` `golf` `ufc` `f1` `cs2` `consensus`\n"
        "`/player avg` `vs` `splits` `minutes` · `/trend` · `/leaderboard rank_by:Units` or `platform:`"))
    e.add_field(name="Slips", inline=False, value=(
        "Post a slip screenshot in the receipts channel and I'll log it. "
        "(Admins: `/receipts` in that channel.)"))
    e.add_field(name="Recaps", inline=False, value=(
        "`/recap` the last 7 days. Weekly recap and open-pick reminders post automatically "
        "once an admin runs `/recapchannel`."))
    e.add_field(name="Auto-grading", inline=False, value=(
        f"Picks still open {AUTOGRADE_AFTER_HOURS} hours after they're logged get their results looked up "
        "and settled automatically: moneylines, spreads and totals from the free ESPN scoreboard, "
        "everything else with Claude. The result posts in the recap channel."))
    e.add_field(name="With the group", inline=False, value=(
        "👍/👎 buttons on a pick: tail or fade it · `/tailfade` who's worth following\n"
        "`/challenge` head-to-head bet · `/h2h` your record vs someone\n"
        "`/lock` your lock of the week · `/locks` this week + standings · `/lockresult` fix one\n"
        "`/awards` monthly awards · `/hotroles` weekly 🔥/🧊 roles (admins)\n"
        "`/pickem start` weekly pick'em (mods) · `/pickem mine` · `/pickem standings`\n"
        "`/halloffame` repost big wins in a channel (admins)\n"
        "`/season start` new season (admins) · `/season standings` · `/season list`\n"
        "`/survivor start` NFL survivor pool (mods) · `/survivor pick` · `/survivor standings`"))
    e.add_field(name="Your numbers", inline=False, value=(
        "`/stats` record by sport, platform and parlay size · `/chart` profit graph\n"
        "`/odds` convert odds · `/parlay` parlay calculator · `/today` today's games\n"
        "`/achievements` badges · `/card` shareable profile image · `/pings` game-time DMs\n"
        "`/bankroll` units on your picks · `/limit` weekly loss heads-up (private)\n"
        "`/compare` two people side by side · `/remind` DM yourself later · `/reminders`"))
    e.add_field(name="Setup (admins)", inline=False, value=(
        "`/guide` post and pin the how-to in this channel · `/receipts` · `/recapchannel` · `/import`\n"
        "`/backups` nightly backup to this channel · `/settings` everything that's set up"))
    e.add_field(name="Players", inline=False, value=(
        "`/player add` · `/player note` · `/player view` · `/player list` · `/player remove`"))
    e.add_field(name="Questions", inline=False, value=(
        "@mention me with a question about a player, team or matchup and I'll look it up."))
    e.set_footer(text=f"PIMP-BOT version {BOT_VERSION}")
    await interaction.response.send_message(embed=e, ephemeral=True)


# ---- extras: commands ----------------------------------------------------------

@bot.tree.command(name="tailfade", description="Who's worth tailing or fading, and how your tails and fades went")
@app_commands.guild_only()
@app_commands.describe(member="Optional: one person's tail/fade record", label="Optional: a name that isn't a Discord user")
async def tailfade_cmd(interaction: discord.Interaction, member: Optional[discord.Member] = None,
                       label: Optional[str] = None):
    gid = interaction.guild_id
    if member or label:
        key, name, _ = resolve_bettor(interaction, member, label)
        tail, fade, n = tailfade_for(gid, key)
        if not n:
            await interaction.response.send_message(f"{name} has no settled picks yet.")
            return
        e = discord.Embed(title=f"Tail or fade {name}?", color=BRAND)
        e.add_field(name="👍 Tailing every pick", value=tf_line(tail))
        e.add_field(name="👎 Fading every pick", value=tf_line(fade))
        fans = db().execute(
            """SELECT f.user_name, f.kind, COUNT(*) AS n FROM follows f JOIN picks p ON p.id = f.pick_id
               WHERE p.guild_id = ? AND p.bettor_key = ? GROUP BY f.user_id, f.kind ORDER BY n DESC LIMIT 6""",
            (gid, key)).fetchall()
        if fans:
            e.add_field(name="Who follows them", inline=False, value="\n".join(
                f"{'👍' if r['kind'] == 'tail' else '👎'} {r['user_name']} · {r['n']}" for r in fans))
    else:
        board = []
        for s in compute_stats(gid):
            tail, fade, n = tailfade_for(gid, s["key"])
            if n >= 3:
                board.append((s["name"], tail, fade, n))
        e = discord.Embed(title="Tail or fade", color=BRAND)
        if board:
            tails = sorted(board, key=lambda b: -b[1]["u"])[:5]
            fades = sorted(board, key=lambda b: -b[2]["u"])[:5]
            e.add_field(name="👍 Best to tail", inline=False,
                        value="\n".join(f"**{n}** · {tf_line(t)}" for n, t, _, _ in tails))
            e.add_field(name="👎 Best to fade", inline=False,
                        value="\n".join(f"**{n}** · {tf_line(f)}" for n, _, f, _ in fades))
        else:
            e.description = "Nobody has 3 settled picks yet."
    mine_t, mine_f = my_follows(gid, interaction.user.id)
    if mine_t["w"] + mine_t["l"] + mine_t["p"] + mine_f["w"] + mine_f["l"] + mine_f["p"]:
        e.add_field(name="Your buttons", inline=False,
                    value=f"👍 Tails {tf_line(mine_t)}\n👎 Fades {tf_line(mine_f)}")
    e.set_footer(text="Units: the same stake on every pick. A fade counts as an even-money bet against it.")
    await interaction.response.send_message(embed=e)


@bot.tree.command(name="challenge", description="Challenge someone head-to-head for bragging rights")
@app_commands.guild_only()
@app_commands.describe(opponent="Who you're challenging", claim="Your side, e.g. 'Bills beat the Chiefs Sunday'",
                       stakes="Optional: what's riding on it, e.g. 'loser buys wings'")
async def challenge_cmd(interaction: discord.Interaction, opponent: discord.Member,
                        claim: app_commands.Range[str, 1, 200],
                        stakes: Optional[app_commands.Range[str, 1, 100]] = None):
    if opponent.id == interaction.user.id or getattr(opponent, "bot", False):
        await interaction.response.send_message("Pick a person other than yourself.", ephemeral=True)
        return
    cur = db().execute(
        """INSERT INTO challenges (guild_id, challenger_id, challenger_name, opponent_id, opponent_name, claim,
                                   stakes, created_at) VALUES (?,?,?,?,?,?,?,?)""",
        (interaction.guild_id, interaction.user.id, interaction.user.display_name, opponent.id,
         opponent.display_name, claim, stakes, now_iso()))
    db().commit()
    c = get_challenge(interaction.guild_id, cur.lastrowid)
    await interaction.response.send_message(
        f"<@{opponent.id}>, you've been challenged.", embed=challenge_embed(c), view=challenge_view(c),
        allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=True))


@bot.tree.command(name="h2h", description="Your head-to-head challenge record against someone")
@app_commands.guild_only()
@app_commands.describe(member="Who to compare against")
async def h2h_cmd(interaction: discord.Interaction, member: discord.Member):
    me, them = interaction.user.id, member.id
    rows = db().execute(
        """SELECT * FROM challenges WHERE guild_id = ? AND status IN ('accepted', 'settled', 'pending')
           AND ((challenger_id = ? AND opponent_id = ?) OR (challenger_id = ? AND opponent_id = ?))
           ORDER BY id DESC""", (interaction.guild_id, me, them, them, me)).fetchall()
    if not rows:
        await interaction.response.send_message(
            f"No challenges between you and {member.display_name} yet. Start one with `/challenge`.")
        return
    settled = [r for r in rows if r["status"] == "settled"]
    mine = sum(1 for r in settled if r["winner_id"] == me)
    theirs = sum(1 for r in settled if r["winner_id"] == them)
    pushes = sum(1 for r in settled if r["winner_id"] is None)
    e = discord.Embed(title=f"{interaction.user.display_name} vs {member.display_name}",
                      description=f"**{mine}-{theirs}" + (f"-{pushes}" if pushes else "") + "**"
                      + f" ({interaction.user.display_name} first)", color=BRAND)
    lines = []
    for r in rows[:8]:
        if r["status"] == "settled":
            icon = "➖" if r["winner_id"] is None else ("✅" if r["winner_id"] == me else "❌")
        else:
            icon = "⏳"
        lines.append(f"{icon} `#{r['id']}` {r['challenger_name']}: {clip(r['claim'], 70)}")
    e.add_field(name="Recent", value="\n".join(lines), inline=False)
    await interaction.response.send_message(embed=e)


@bot.tree.command(name="lock", description="Submit your lock of the week (one per week, change it until it's graded)")
@app_commands.guild_only()
@app_commands.describe(pick="Your most confident pick, e.g. 'Bills ML'", sport="Optional but helps grading: NFL, NBA...")
async def lock_cmd(interaction: discord.Interaction, pick: app_commands.Range[str, 1, 150],
                   sport: Optional[app_commands.Range[str, 1, 30]] = None):
    week = week_id()
    row = db().execute("SELECT * FROM locks WHERE guild_id = ? AND user_id = ? AND week = ?",
                       (interaction.guild_id, interaction.user.id, week)).fetchone()
    if row and row["status"] != "open":
        await interaction.response.send_message(
            f"Your lock for {week} is already graded ({LOCK_ICON[row['status']]}). New week starts Monday.",
            ephemeral=True)
        return
    if row:
        db().execute("""UPDATE locks SET text = ?, sport = ?, user_name = ?, created_at = ?, autograde_at = NULL,
                        autograde_tries = 0 WHERE id = ?""",
                     (pick, sport, interaction.user.display_name, now_iso(), row["id"]))
        verb = "changed"
    else:
        db().execute("""INSERT INTO locks (guild_id, user_id, user_name, week, text, sport, created_at)
                        VALUES (?,?,?,?,?,?,?)""",
                     (interaction.guild_id, interaction.user.id, interaction.user.display_name, week, pick, sport,
                      now_iso()))
        verb = "is in"
    db().commit()
    n = len(locks_for_week(interaction.guild_id, week))
    await interaction.response.send_message(
        f"🔒 **{interaction.user.display_name}**'s lock of the week {verb}: {pick}"
        + (f" ({sport})" if sport else "") + f"\n-# {n} lock{'s' if n != 1 else ''} in for {week}. See them with `/locks`.")


@bot.tree.command(name="locks", description="This week's locks and the all-time lock standings")
@app_commands.guild_only()
async def locks_cmd(interaction: discord.Interaction):
    week = week_id()
    rows = locks_for_week(interaction.guild_id, week)
    e = discord.Embed(title=f"🔒 Locks of the week · {week}", color=BRAND,
                      description="\n".join(lock_line(r) for r in rows) if rows
                      else "No locks yet this week. Submit one with `/lock`.")
    table = lock_standings(interaction.guild_id)
    if table:
        medals = ["🥇", "🥈", "🥉"]
        lines = [f"{medals[i] if i < 3 else f'`{i + 1}.`'} **{s['name']}** · {s['w']}-{s['l']}"
                 + (f"-{s['p']}" if s["p"] else "") + f" ({s['pct'] * 100:.0f}%)" for i, s in enumerate(table[:15])]
        e.add_field(name="All-time standings", value="\n".join(lines), inline=False)
    e.set_footer(text="Locks get graded automatically 48 hours after they're submitted. Fix one with /lockresult.")
    await interaction.response.send_message(embed=e)


@bot.tree.command(name="lockresult", description="Settle or fix a lock of the week")
@app_commands.guild_only()
@app_commands.describe(lock_id="The lock number shown in /locks", result="How it finished")
@app_commands.choices(result=[app_commands.Choice(name=n, value=v) for n, v in
                              (("Win", "win"), ("Loss", "loss"), ("Push", "push"), ("Not graded yet", "open"))])
async def lockresult_cmd(interaction: discord.Interaction, lock_id: int, result: app_commands.Choice[str]):
    row = db().execute("SELECT * FROM locks WHERE id = ? AND guild_id = ?", (lock_id, interaction.guild_id)).fetchone()
    if row is None:
        await interaction.response.send_message(f"No lock #{lock_id}.", ephemeral=True)
        return
    if interaction.user.id != row["user_id"] and not is_mod(interaction.user):
        await interaction.response.send_message("Only whoever submitted it or a mod can settle it.", ephemeral=True)
        return
    settle_lock(lock_id, result.value)
    row = db().execute("SELECT * FROM locks WHERE id = ?", (lock_id,)).fetchone()
    await interaction.response.send_message(lock_line(row))


@bot.tree.command(name="stats", description="Your record split by sport, platform and parlay size")
@app_commands.guild_only()
@app_commands.describe(member="Optional: defaults to you", label="Optional: a name that isn't a Discord user")
async def stats_cmd(interaction: discord.Interaction, member: Optional[discord.Member] = None,
                    label: Optional[str] = None):
    key, name, _ = resolve_bettor(interaction, member, label)
    rows = db().execute("SELECT * FROM picks WHERE guild_id = ? AND bettor_key = ?",
                        (interaction.guild_id, key)).fetchall()
    if not rows:
        await interaction.response.send_message(f"No picks logged for {name} yet.")
        return
    leg_counts_by_pick = {r["pick_id"]: r["n"] for r in db().execute(
        "SELECT pick_id, COUNT(*) AS n FROM legs WHERE pick_id IN (SELECT id FROM picks WHERE guild_id = ? "
        "AND bettor_key = ?) GROUP BY pick_id", (interaction.guild_id, key))}
    streak = current_streak(interaction.guild_id, key)
    e = discord.Embed(title=f"{name}'s breakdown" + (f" · {streak}" if streak else ""), color=BRAND)
    e.add_field(name="By sport", value=breakdown_lines(breakdown(rows, lambda p: sport_group(p["sport"]))),
                inline=False)
    e.add_field(name="By platform", value=breakdown_lines(breakdown(rows, lambda p: p["platform"])), inline=False)
    e.add_field(name="By parlay size", inline=False, value=breakdown_lines(
        breakdown(rows, lambda p: size_group(leg_counts_by_pick.get(p["id"], 0)))))
    await interaction.response.send_message(embed=e)


@bot.tree.command(name="odds", description="Convert odds: break-even %, American, decimal, Kalshi price, payout")
@app_commands.describe(value="e.g. -150, +200, 2.5, 45¢, 5/2 or 60%", stake="Optional: stake to show the payout for")
async def odds_cmd(interaction: discord.Interaction, value: app_commands.Range[str, 1, 20],
                   stake: Optional[app_commands.Range[float, 0.01]] = None):
    try:
        e = odds_embed(value, stake or 10.0)
    except (ValueError, ZeroDivisionError):
        await interaction.response.send_message(
            "I couldn't read that. Try `-150`, `+200`, `2.5`, `45¢`, `5/2` or `60%`.", ephemeral=True)
        return
    await interaction.response.send_message(embed=e)


@bot.tree.command(name="chart", description="A graph of profit over time")
@app_commands.guild_only()
@app_commands.describe(member="Optional: just one person", label="Optional: a name that isn't a Discord user",
                       days="How far back (default 90)")
async def chart_cmd(interaction: discord.Interaction, member: Optional[discord.Member] = None,
                    label: Optional[str] = None, days: Optional[app_commands.Range[int, 1, 3650]] = None):
    days = days or 90
    key = name = None
    if member or label:
        key, name, _ = resolve_bettor(interaction, member, label)
    series = chart_series(interaction.guild_id, days, key)
    if not series:
        await interaction.response.send_message(f"No settled picks in the last {days} days.", ephemeral=True)
        return
    await interaction.response.defer(thinking=True)
    title = f"{name or next(iter(series))}'s profit, last {days} days" if (name or len(series) == 1) \
        else f"Profit over the last {days} days"
    png = await asyncio.to_thread(render_chart, series, title)
    note = "" if len(series) < 8 else "\n-# Showing the 8 most active people."
    await interaction.followup.send(content=note or None, file=discord.File(png, filename="profit.png"))


@bot.tree.command(name="hotroles", description="Turn the weekly 🔥 Hot Hand and 🧊 Ice Cold roles on or off")
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
async def hotroles_cmd(interaction: discord.Interaction):
    on = get_setting(interaction.guild_id, "hotroles") == "on"
    set_setting(interaction.guild_id, "hotroles", None if on else "on")
    if on:
        await interaction.response.send_message("Weekly roles are **off**. Existing roles stay until you delete them.")
    else:
        await interaction.response.send_message(
            "Weekly roles are **on**. With the weekly recap, the week's top earner gets **🔥 Hot Hand** and the "
            "biggest loser gets **🧊 Ice Cold**. I need the **Manage Roles** permission, and my role has to sit "
            "above those two in Server Settings → Roles.")


@bot.tree.command(name="awards", description="Monthly awards: biggest hit, longest streak, best ROI and more")
@app_commands.guild_only()
@app_commands.describe(month="Optional, like 2026-09. Defaults to this month so far")
async def awards_cmd(interaction: discord.Interaction, month: Optional[str] = None):
    now = datetime.now(TZ)
    y, m = now.year, now.month
    if month:
        mm = re.match(r"^\s*(\d{4})-(\d{1,2})\s*$", month)
        if not mm or not 1 <= int(mm[2]) <= 12:
            await interaction.response.send_message("Use a month like `2026-09`.", ephemeral=True)
            return
        y, m = int(mm[1]), int(mm[2])
    await interaction.response.send_message(embed=build_awards(interaction.guild_id, y, m))


@bot.tree.command(name="bankroll", description="Set or check your bankroll; picks then show their size in units")
@app_commands.guild_only()
@app_commands.describe(amount="Set your bankroll to this (starts tracking from now)",
                       unit_percent="Optional: one unit as a % of bankroll (default 1)",
                       off="Optional: stop tracking your bankroll")
async def bankroll_cmd(interaction: discord.Interaction, amount: Optional[app_commands.Range[float, 1]] = None,
                       unit_percent: Optional[app_commands.Range[float, 0.1, 10.0]] = None,
                       off: Optional[bool] = None):
    gid, uid = interaction.guild_id, interaction.user.id
    if off:
        set_setting(gid, f"bankroll:{uid}", None)
        await interaction.response.send_message("Bankroll tracking is off.", ephemeral=True)
        return
    if amount is not None:
        set_setting(gid, f"bankroll:{uid}", json.dumps({"start": amount, "unit_pct": unit_percent or 1.0,
                                                        "since": now_iso()}))
    elif unit_percent is not None:
        b = get_bankroll(gid, uid)
        if not b:
            await interaction.response.send_message("Set a bankroll first: `/bankroll amount:500`.", ephemeral=True)
            return
        set_setting(gid, f"bankroll:{uid}", json.dumps({"start": b["start"], "unit_pct": unit_percent,
                                                        "since": b["since"]}))
    b = get_bankroll(gid, uid)
    if not b:
        await interaction.response.send_message("No bankroll set. Start with `/bankroll amount:500`.", ephemeral=True)
        return
    open_risk = db().execute("SELECT COALESCE(SUM(cost), 0) AS n FROM picks WHERE guild_id = ? AND bettor_key = ? "
                             "AND status = 'open'", (gid, str(uid))).fetchone()["n"]
    e = discord.Embed(title=f"{interaction.user.display_name}'s bankroll", color=BRAND)
    e.add_field(name="Started at", value=f"{money(b['start'])} on {local_day(b['since'])}")
    e.add_field(name="Now", value=f"{money(b['current'])} ({signed(b['net'])})")
    e.add_field(name="1 unit", value=f"{money(b['unit_size'])} ({b['unit_pct']:g}%)")
    if b["unit_size"] > 0:
        e.add_field(name="Riding now", value=f"{money(open_risk)} · {open_risk / b['unit_size']:.1f}u")
    e.add_field(name="This week", value=signed(weekly_net(gid, str(uid))))
    e.set_footer(text=f"Picks over {BIG_BET_UNITS} units get a heads-up on their card. Only you see this.")
    await interaction.response.send_message(embed=e, ephemeral=True)


@bot.tree.command(name="limit", description="Set a weekly loss limit; I'll DM you privately if you pass it")
@app_commands.guild_only()
@app_commands.describe(amount="Your weekly loss limit in dollars", off="Optional: turn the limit off")
async def limit_cmd(interaction: discord.Interaction, amount: Optional[app_commands.Range[float, 1]] = None,
                    off: Optional[bool] = None):
    gid, uid = interaction.guild_id, interaction.user.id
    if off:
        set_setting(gid, f"limit:{uid}", None)
        await interaction.response.send_message("Weekly loss limit is off.", ephemeral=True)
        return
    if amount is not None:
        set_setting(gid, f"limit:{uid}", f"{amount:.2f}")
    limit = get_setting(gid, f"limit:{uid}")
    net = weekly_net(gid, str(uid))
    if not limit:
        await interaction.response.send_message(
            f"No limit set. This week (since Monday) you're {signed(net)}. Set one with `/limit amount:100`.",
            ephemeral=True)
        return
    left = float(limit) + net
    await interaction.response.send_message(
        f"Weekly loss limit: **{money(float(limit))}**. This week (since Monday) you're **{signed(net)}**, "
        + (f"{money(left)} before the limit." if left > 0 else "past the limit.")
        + " If you pass it, I'll send you a private DM once that week. Nothing gets blocked.", ephemeral=True)


# ---- pinned guide for the bot's channel ------------------------------------------

def guide_embeds() -> list[discord.Embed]:
    start = discord.Embed(title="🤖 How to use PIMP-BOT", color=BRAND, description=(
        "Everything happens with **/commands**. Type `/` in any channel and pick one from the list. "
        "This channel is the place to use them, so the main chat stays clean.\n\n"
        "**The 30-second version**\n"
        "1. Log a bet with `/pick`, or post your slip screenshot in the receipts channel.\n"
        "2. When it's over, tap **Win**, **Loss** or **Push** on the pick card.\n"
        "3. Check `/record` for your stats and `/leaderboard` for who's up."))
    picks = discord.Embed(title="📝 Logging and settling picks", color=BRAND, description=(
        "`/pick` log a bet. **Cost** is what you paid, **payout** is the total you get back if it hits "
        "(stake included). Put parlay legs in **legs**, separated by `;`, and fill in **sport** "
        "(NFL, NBA, CS2...).\n"
        "`/leg` mark one parlay leg as hit, miss or push. When every leg hits, the pick settles as a win; "
        "when one misses, as a loss.\n"
        "`/result` settle a pick by number. Use **returned** for cash-outs and partial payouts.\n"
        "`/grade` look up the result right now.\n"
        "Add `hidden: True` to keep a pick secret until it settles. Right-click any slip → **Apps → Log as pick**, "
        "or DM me a screenshot to log it privately.\n"
        "`/edit` and `/delete` fix mistakes, or `/undo` the pick you just logged. `/open` shows everything still "
        "pending, `/exposure` groups it by game, and `/history` pages back through old picks."))
    auto = discord.Embed(title="⚡ What the bot does on its own", color=BRAND, description=(
        "• **Reads slips** posted in the receipts channel and logs them for you.\n"
        "• **Grades picks the moment games end:** moneylines, spreads, totals and player props (points, PRA, "
        "pass yards, strikeouts, shots...) settle from the box score within minutes. Linked Kalshi picks settle "
        "when Kalshi does. Everything else is looked up 48 hours after it's logged. "
        "If it gets one wrong, fix it with `/leg` or `/result`.\n"
        "• **Hall of Fame:** big wins get reposted in the hall of fame channel.\n"
        "• **Pings you** about picks open 3+ days, and DMs you if a player on your open props is listed "
        "Out, Doubtful or Questionable.\n"
        "• **Sunday 8 PM:** weekly recap, plus the 🔥 Hot Hand and 🧊 Ice Cold roles.\n"
        "• **Every morning:** today's games, in the channel an admin picked with `/todaypost`.\n"
        "• **The 1st of each month:** monthly awards.\n"
        "• **Shouts out** new badges and 5, 10, 15 and 20-win streaks.\n"
        "• **Nightly backup** of every pick, in the channel an admin picked with `/backups`.\n"
        "• **🚨 One leg away** alerts, ✅/❌ reactions on slips, and a 💵 settle button once a PrizePicks slip is graded."))
    group = discord.Embed(title="🤝 With the group", color=BRAND, description=(
        "👍 **Tail** / 👎 **Fade** buttons on any open pick (not your own). `/tailfade` shows who's worth following.\n"
        "`/challenge @someone` head-to-head bet for bragging rights. `/h2h` shows your record against them.\n"
        "`/lock` your lock of the week. One per week, and you can change it until it's graded. "
        "`/locks` shows this week and the standings.\n"
        "`/awards` this month's awards so far · `/season standings` this season's leaderboard.\n"
        "**Pick'em:** tap a team on each game a mod posts; no money, just bragging rights. "
        "`/pickem mine` and `/pickem standings`.\n"
        "**Group parlay:** `/groupparlay`, one leg each, every week. 📋 **Copy** on any pick card logs your own copy.\n"
        "**🪙 Coins:** earned by playing. Bet them on `/market` yes/no questions. `/potd` Prop of the Day, `/take` hot takes.\n"
        "**Survivor:** pick one NFL team a week with `/survivor pick`. Each team once; lose or skip and you're out.\n"
        "**@PIMP-BOT** plus a question about a player, team or matchup gets a researched answer."))
    numbers = discord.Embed(title="📊 Your numbers", color=BRAND, description=(
        "`/record` your W-L, profit, ROI, streak and leg hit rate · `/compare @someone` side by side\n"
        "`/leaderboard` filter by week, month, season or sport\n"
        "`/stats` your record split by sport, platform and parlay size\n"
        "`/chart` profit graph, for everyone or just you\n"
        "`/odds` convert -150, +200, 2.5, 45¢ or 60% into break-even % and payout · `/parlay` stack legs\n"
        "`/sweat` live tracker for a pick (also the 🥵 button on every card) · `/schedule` when your games start\n"
        "`/trend` a player's hit rate vs a line · `/player avg` and `/player vs` · `/wrapped` season review\n"
        "`/insights` tendencies, luck, heatmap, autopsy, risk, report card, rankings · `/calc` pp, hedge, kelly, slip\n"
        "`/sports` box, matchup, weather, injuries, standings, rankings, golf, UFC, F1, CS2, consensus · `/money` (private)\n"
        "`/today` today's games · `/pings` DM before your games start and at halftime\n"
        "`/remind` DM yourself later: `2h`, `6pm`, `tomorrow 9am` · `/reminders` see or cancel\n"
        "`/achievements` your badges · `/card` a shareable image of your profile\n"
        "`/export` everything as an Excel file\n"
        "`/bankroll` units on your pick cards · `/limit` private weekly loss heads-up\n"
        "`/player note` scouting notes on a player · `/player view` notes plus how the group's legs on them went"))
    tips = discord.Embed(title="💡 Tips", color=0xF1C40F, description=(
        "• **Always fill in the sport.** It's how the bot finds the right game to grade for free.\n"
        "• **One leg per item.** Write `Bills ML; Chiefs -3; Over 44.5 (Bills vs Chiefs)`, not one long sentence. "
        "Props as `Wembanyama over 23.5 PRA`.\n"
        "• **The pick number** (like `#12`) is on every card. Most commands ask for it.\n"
        "• **Cashed out early?** The bot can't see that. Use `/result` with the `returned` amount.\n"
        "• **Bot got a result wrong?** `/leg` or `/result` overrides it.\n"
        "• **Typing `/` shows every option** with a short description, so you don't need to memorize any of this.\n"
        "• `/help` brings up the full command list anytime (only you see it)."))
    tips.set_footer(text="Bet what you can afford to lose. Set a /limit if you want a nudge.")
    return [start, picks, auto, group, numbers, tips]


def guide_version() -> str:
    text = "".join(f"{e.title}{e.description}" for e in guide_embeds())
    return hashlib.sha1(text.encode()).hexdigest()[:10]


async def refresh_guides(client: discord.Client) -> int:
    """After an update, rewrite every posted guide whose text is out of date. Returns how many changed."""
    changed = 0
    current = guide_version()
    rows = db().execute("SELECT guild_id, key, value FROM settings WHERE key LIKE 'guide_msg:%'").fetchall()
    for r in rows:
        if get_setting(r["guild_id"], "guide_version") == current:
            continue
        channel = client.get_channel(int(r["key"].split(":", 1)[1]))
        if channel is None:
            continue
        try:
            msg = await channel.fetch_message(int(r["value"]))
            await msg.edit(embeds=guide_embeds())
            changed += 1
        except Exception:
            log.info("Couldn't refresh the guide in channel %s", r["key"])
    for g in {r["guild_id"] for r in rows}:
        set_setting(g, "guide_version", current)
    return changed


@bot.tree.command(name="guide", description="Post (and pin) the how-to guide in this channel")
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
async def guide_cmd(interaction: discord.Interaction):
    # Update the guide already in this channel if there is one.
    old_id = get_setting(interaction.guild_id, f"guide_msg:{interaction.channel_id}")
    if old_id:
        try:
            old = await interaction.channel.fetch_message(int(old_id))
            await old.edit(embeds=guide_embeds())
            set_setting(interaction.guild_id, "guide_version", guide_version())
            await interaction.response.send_message(
                "Updated the guide that's already in this channel (scroll up or check the pins).", ephemeral=True)
            return
        except (discord.Forbidden, discord.HTTPException, discord.NotFound, AttributeError):
            pass  # gone or not editable: post a fresh one
    # Posted as the command's reply, which works even where the bot can't send regular messages.
    await interaction.response.send_message(embeds=guide_embeds())
    try:
        msg = await interaction.original_response()
        set_setting(interaction.guild_id, f"guide_msg:{interaction.channel_id}", str(msg.id))
        set_setting(interaction.guild_id, "guide_version", guide_version())
        await msg.pin(reason="PIMP-BOT guide")
        note = "Guide posted and pinned. It updates itself whenever the bot gets new features."
    except (discord.Forbidden, discord.HTTPException):
        note = ("Guide posted. I couldn't pin it: give me **Manage Messages** in this channel, "
                "or pin it yourself from the message's ⋯ menu. If an older guide is pinned, unpin it.")
    await interaction.followup.send(note, ephemeral=True)

# ---- pick'em and hall of fame: commands ------------------------------------------

pickem_group = app_commands.Group(name="pickem", description="Weekly pick'em: pick the winners, no money involved",
                                  guild_only=True)


@pickem_group.command(name="start", description="Post the upcoming games for everyone to pick (mods)")
@app_commands.describe(league="Which league", days="How many days of games (default: a week for football and "
                                                   "soccer, today for the others)")
@app_commands.choices(league=[app_commands.Choice(name=n, value=p) for n, p, _, _ in PICKEM_LEAGUES])
async def pickem_start(interaction: discord.Interaction, league: app_commands.Choice[str],
                       days: Optional[app_commands.Range[int, 1, 10]] = None):
    perms = getattr(interaction.user, "guild_permissions", None)
    if not (is_mod(interaction.user) or (perms and getattr(perms, "manage_guild", False))):
        await interaction.response.send_message("Only mods can start a pick'em round.", ephemeral=True)
        return
    name, path, params, default_days = pickem_league(league.value)
    days = days or default_days
    await interaction.response.defer(thinking=True)
    now = datetime.now(timezone.utc)
    today = datetime.now(TZ)
    seen, upcoming = set(), []
    for offset in range(days):
        for ev in await fetch_scoreboard(path, today + timedelta(days=offset), params):
            when = datetime.fromisoformat(ev["date"].replace("Z", "+00:00")) if ev["date"] else None
            if ev["id"] in seen or not when or when <= now or ev.get("state", "pre") != "pre":
                continue
            seen.add(ev["id"])
            upcoming.append((when, ev))
    upcoming.sort(key=lambda x: x[0])
    upcoming = upcoming[:PICKEM_MAX_GAMES]
    if not upcoming:
        await interaction.followup.send(f"No upcoming {name} games in the next {days} day{'s' if days > 1 else ''}.")
        return
    first, last = upcoming[0][0].astimezone(TZ), upcoming[-1][0].astimezone(TZ)
    label = f"{name} · {first:%b %-d}" + (f"–{last:%b %-d}" if last.date() != first.date() else "")
    cur = db().execute("""INSERT INTO pickem_rounds (guild_id, league, label, channel_id, created_by, created_at)
                          VALUES (?,?,?,?,?,?)""",
                       (interaction.guild_id, path, label, interaction.channel_id, interaction.user.id, now_iso()))
    rid = cur.lastrowid
    for when, ev in upcoming:
        away = next(t for t in ev["teams"] if not t["home"])
        home = next(t for t in ev["teams"] if t["home"])
        db().execute("""INSERT INTO pickem_games (round_id, guild_id, event_id, league, start, away, home)
                        VALUES (?,?,?,?,?,?,?)""", (rid, interaction.guild_id, ev["id"], path, iso(when),
                                                    away["short"], home["short"]))
    db().commit()
    games = round_games(rid)
    intro = discord.Embed(title=f"🏈 Pick'em · {label}", color=BRAND, description=(
        f"{len(games)} games. Tap the team you think wins. You can change a pick until that game starts, "
        "then it locks. Results grade themselves from the scoreboard.\n"
        "`/pickem mine` your picks · `/pickem standings` the table"))
    for start in range(0, len(games), GAMES_PER_MESSAGE):
        batch = games[start:start + GAMES_PER_MESSAGE]
        text = "\n".join(game_line(g, start + i + 1) for i, g in enumerate(batch))
        await interaction.followup.send(text, embed=intro if start == 0 else discord.utils.MISSING,
                                        view=pickem_view(batch, start + 1))


@pickem_group.command(name="mine", description="Your picks for the current pick'em round")
async def pickem_mine(interaction: discord.Interaction):
    r = latest_round(interaction.guild_id)
    if r is None:
        await interaction.response.send_message("No pick'em round yet. A mod can start one with `/pickem start`.",
                                                ephemeral=True)
        return
    picks = {row["game_id"]: row["side"] for row in db().execute(
        "SELECT game_id, side FROM pickem_picks WHERE user_id = ?", (interaction.user.id,))}
    lines = []
    for n, g in enumerate(round_games(r["id"]), start=1):
        side = picks.get(g["id"])
        if side is None:
            mark = "🔒 missed" if game_started(g) else "➕ not picked yet"
            lines.append(f"`{n}` {g['away']} @ {g['home']} · {mark}")
            continue
        team = g["home"] if side == 1 else g["away"]
        icon = "⏳" if g["winner"] is None else "➖" if g["winner"] == -1 else ("✅" if g["winner"] == side else "❌")
        lines.append(f"`{n}` {icon} **{team}** ({g['away']} @ {g['home']})")
    await interaction.response.send_message(
        embed=discord.Embed(title=f"Your picks · {r['label']}", description=clip("\n".join(lines), 4000), color=BRAND),
        ephemeral=True)


@pickem_group.command(name="standings", description="This round's pick'em table and the all-time standings")
async def pickem_standings(interaction: discord.Interaction):
    r = latest_round(interaction.guild_id)
    if r is None:
        await interaction.response.send_message("No pick'em round yet. A mod can start one with `/pickem start`.")
        return
    e = round_summary(r)
    overall = pickem_table(None, interaction.guild_id)
    rounds = db().execute("SELECT COUNT(*) AS n FROM pickem_rounds WHERE guild_id = ?",
                          (interaction.guild_id,)).fetchone()["n"]
    if rounds > 1 and overall:
        e.add_field(name=f"All-time ({rounds} rounds)", value=clip(table_lines(overall, 10), 1024), inline=False)
    await interaction.response.send_message(embed=e)


bot.tree.add_command(pickem_group)


@bot.tree.command(name="halloffame", description="Repost big wins in this channel (turn on or off)")
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
async def halloffame_cmd(interaction: discord.Interaction):
    if get_setting(interaction.guild_id, "hof_channel") == str(interaction.channel_id):
        set_setting(interaction.guild_id, "hof_channel", None)
        await interaction.response.send_message("Hall of fame is **off** for this channel.")
        return
    set_setting(interaction.guild_id, "hof_channel", str(interaction.channel_id))
    set_setting(interaction.guild_id, "hof_since", now_iso())
    await interaction.response.send_message(
        f"🏆 This is the **Hall of Fame** now. From here on, any win that hits {HOF_MIN_LEGS}+ legs, pays "
        f"{HOF_MIN_MULTIPLE}x or more, or profits {money(HOF_MIN_PROFIT)}+ gets posted here automatically.")


# ---- pings, today, parlay, seasons, achievements, card: commands ---------------------

@bot.tree.command(name="pings", description="Turn private game-time pings on or off for your open picks")
@app_commands.guild_only()
async def pings_cmd(interaction: discord.Interaction):
    key = f"pings:{interaction.user.id}"
    on = get_setting(interaction.guild_id, key) == "on"
    set_setting(interaction.guild_id, key, None if on else "on")
    await interaction.response.send_message(
        "Game-time pings are **off**." if on else
        f"Game-time pings are **on**. I'll DM you {PING_MINUTES} minutes before a game on one of your open picks "
        "starts, and again at halftime with the score. (Make sure DMs from server members are allowed.)",
        ephemeral=True)


@bot.tree.command(name="today", description="Today's games: start times, live scores and finals")
@app_commands.describe(league="Optional: one league (default: the leagues your group bets on)")
@app_commands.choices(league=[app_commands.Choice(name=n, value=p) for p, n in LEAGUE_NAMES.items()][:25])
async def today_cmd(interaction: discord.Interaction, league: Optional[app_commands.Choice[str]] = None):
    await interaction.response.defer(thinking=True)
    paths = [league.value] if league else (group_leagues(interaction.guild_id) if interaction.guild_id
                                           else ["football/nfl", "basketball/nba"])
    embeds = [e for e in [await today_embed(p) for p in paths[:10]] if e]
    if not embeds:
        await interaction.followup.send("No games today in " + ", ".join(LEAGUE_NAMES.get(p, p) for p in paths) + ".")
        return
    await interaction.followup.send(embeds=embeds)


@bot.tree.command(name="todaypost", description="Post today's games here every morning (turn on or off)")
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
async def todaypost_cmd(interaction: discord.Interaction):
    if get_setting(interaction.guild_id, "today_channel") == str(interaction.channel_id):
        set_setting(interaction.guild_id, "today_channel", None)
        await interaction.response.send_message("Daily games post is **off** for this channel.")
        return
    set_setting(interaction.guild_id, "today_channel", str(interaction.channel_id))
    when = datetime(2000, 1, 1, TODAY_HOUR).strftime("%-I %p")
    names = ", ".join(LEAGUE_NAMES.get(p, p) for p in group_leagues(interaction.guild_id))
    await interaction.response.send_message(
        f"Every morning at **{when}** I'll post today's games here for the leagues your group bets on "
        f"(right now: {names}).")


@bot.tree.command(name="parlay", description="Parlay calculator: combined odds, payout and the chance it hits")
@app_commands.describe(legs="Odds for each leg, separated by spaces: e.g. -110 +150 -200 or 45¢ 60¢ 1.8",
                       stake="Optional: stake to show the payout for (default $10)")
async def parlay_cmd(interaction: discord.Interaction, legs: app_commands.Range[str, 3, 200],
                     stake: Optional[app_commands.Range[float, 0.01]] = None):
    try:
        e = parlay_embed(legs, stake or 10.0)
    except (ValueError, ZeroDivisionError):
        await interaction.response.send_message(
            "Give me 2 to 20 legs separated by spaces, like `-110 +150 -200` or `45¢ 60¢ 1.8`.", ephemeral=True)
        return
    await interaction.response.send_message(embed=e)


season_group = app_commands.Group(name="season", description="Seasons: fresh leaderboards without deleting anything",
                                  guild_only=True)


@season_group.command(name="start", description="End the current season (if any) and start a new one (admins)")
@app_commands.describe(name="e.g. 'NFL 2026' or 'Fall'")
async def season_start(interaction: discord.Interaction, name: app_commands.Range[str, 1, 40]):
    perms = getattr(interaction.user, "guild_permissions", None)
    if not (perms and getattr(perms, "manage_guild", False)):
        await interaction.response.send_message("Only admins can start a season.", ephemeral=True)
        return
    old = current_season(interaction.guild_id)
    embeds = []
    if old:
        db().execute("UPDATE seasons SET ended_at = ? WHERE id = ?", (now_iso(), old["id"]))
        old = db().execute("SELECT * FROM seasons WHERE id = ?", (old["id"],)).fetchone()
        embeds.append(season_embed(interaction.guild_id, old, final=True))
    db().execute("INSERT INTO seasons (guild_id, name, started_at) VALUES (?,?,?)",
                 (interaction.guild_id, name, now_iso()))
    db().commit()
    champ = ""
    if old:
        stats = season_stats(interaction.guild_id, old)
        if stats and stats[0]["net"] > 0:
            champ = f"🏆 **{stats[0]['name']}** wins {old['name']} at {signed(stats[0]['net'])}. "
    await interaction.response.send_message(
        f"{champ}🆕 Season **{name}** starts now. `/leaderboard` shows this season; all-time stats stay."
        + (f" 🎁 **{old['name']} Wrapped** is out: everyone run `/wrapped`!" if old else ""),
        embeds=embeds or discord.utils.MISSING)


@season_group.command(name="list", description="Every season and who won it")
async def season_list(interaction: discord.Interaction):
    rows = db().execute("SELECT * FROM seasons WHERE guild_id = ? ORDER BY id DESC", (interaction.guild_id,)).fetchall()
    if not rows:
        await interaction.response.send_message("No seasons yet. An admin can start one with `/season start`.")
        return
    lines = []
    for r in rows[:20]:
        stats = season_stats(interaction.guild_id, r)
        lead = f"{stats[0]['name']} {signed(stats[0]['net'])}" if stats else "no picks"
        state = "🟢 now" if r["ended_at"] is None else f"🏆 {lead}"
        lines.append(f"**{r['name']}** · {local_day(r['started_at'])} · {state}"
                     + (f" (leading: {lead})" if r["ended_at"] is None and stats else ""))
    await interaction.response.send_message(embed=discord.Embed(title="Seasons", description="\n".join(lines),
                                                                color=BRAND))


async def season_autocomplete(interaction: discord.Interaction, current: str):
    rows = db().execute("SELECT name FROM seasons WHERE guild_id = ? AND lower(name) LIKE ? ORDER BY id DESC LIMIT 25",
                        (interaction.guild_id, f"%{current.lower()}%")).fetchall()
    return [app_commands.Choice(name=r["name"], value=r["name"]) for r in rows]


@season_group.command(name="standings", description="A season's leaderboard (default: the current one)")
@app_commands.describe(name="Optional: which season")
@app_commands.autocomplete(name=season_autocomplete)
async def season_standings(interaction: discord.Interaction, name: Optional[str] = None):
    row = (db().execute("SELECT * FROM seasons WHERE guild_id = ? AND name = ? ORDER BY id DESC LIMIT 1",
                        (interaction.guild_id, name)).fetchone() if name else current_season(interaction.guild_id))
    if row is None:
        await interaction.response.send_message("No season by that name." if name else
                                                "No season running. An admin can start one with `/season start`.",
                                                ephemeral=True)
        return
    await interaction.response.send_message(embed=season_embed(interaction.guild_id, row, final=bool(row["ended_at"])))


bot.tree.add_command(season_group)


@bot.tree.command(name="achievements", description="Badges earned (and what's left to unlock)")
@app_commands.guild_only()
@app_commands.describe(member="Optional: defaults to you", label="Optional: a name that isn't a Discord user")
async def achievements_cmd(interaction: discord.Interaction, member: Optional[discord.Member] = None,
                           label: Optional[str] = None):
    key, name, _ = resolve_bettor(interaction, member, label)
    got = earned_badges(interaction.guild_id, key)
    have = [f"{BADGE_ICONS[k]} **{n}** · {how}" for k, n, how in BADGES if k in got]
    todo = [f"▫️ {n} · {how}" for k, n, how in BADGES if k not in got]
    e = discord.Embed(title=f"{name}'s badges · {len(got)}/{len(BADGES)}", color=BRAND,
                      description="\n".join(have) or "None yet.")
    if todo:
        e.add_field(name="Still to unlock", value=clip("\n".join(todo), 1024), inline=False)
    await interaction.response.send_message(embed=e)


@bot.tree.command(name="card", description="A shareable image of someone's betting profile")
@app_commands.guild_only()
@app_commands.describe(member="Optional: defaults to you", label="Optional: a name that isn't a Discord user")
async def card_cmd(interaction: discord.Interaction, member: Optional[discord.Member] = None,
                   label: Optional[str] = None):
    key, name, _ = resolve_bettor(interaction, member, label)
    stats = compute_stats(interaction.guild_id, key)
    if not stats:
        await interaction.response.send_message(f"No picks logged for {name} yet.", ephemeral=True)
        return
    await interaction.response.defer(thinking=True)
    s = stats[0]
    settled = db().execute("SELECT * FROM picks WHERE guild_id = ? AND bettor_key = ? AND status != 'open'",
                           (interaction.guild_id, key)).fetchall()
    best = max(settled, key=pick_net) if settled else None
    groups = breakdown(settled, lambda p: sport_group(p["sport"]))
    top_sport = groups[0][0] if groups and groups[0][0] != "No sport" else None
    got = earned_badges(interaction.guild_id, key)
    series = chart_series(interaction.guild_id, 3650, key)
    avatar = None if label else await fetch_avatar(member or interaction.user)
    png = await asyncio.to_thread(
        render_card, s["name"], s, current_streak(interaction.guild_id, key), best,
        hit_rate(leg_counts(interaction.guild_id, key)), top_sport,
        [n for k, n, _ in BADGES if k in got], next(iter(series.values()), []), avatar)
    await interaction.followup.send(file=discord.File(png, filename=f"{re.sub(r'[^A-Za-z0-9]+', '_', s['name'])}_card.png"))


# ---- r8 commands ------------------------------------------------------------------------

survivor_group = app_commands.Group(name="survivor", description="NFL survivor pool: pick one team a week to win",
                                    guild_only=True)


@survivor_group.command(name="start", description="Start a survivor pool (mods)")
@app_commands.describe(name="Optional, e.g. 'Survivor 2026'")
async def survivor_start(interaction: discord.Interaction, name: Optional[app_commands.Range[str, 1, 40]] = None):
    perms = getattr(interaction.user, "guild_permissions", None)
    if not (is_mod(interaction.user) or (perms and getattr(perms, "manage_guild", False))):
        await interaction.response.send_message("Only mods can start a survivor pool.", ephemeral=True)
        return
    old = active_pool(interaction.guild_id)
    if old:
        db().execute("UPDATE survivor_pools SET ended_at = ? WHERE id = ?", (now_iso(), old["id"]))
    name = name or f"Survivor {datetime.now(TZ).year}"
    db().execute("INSERT INTO survivor_pools (guild_id, name, channel_id, created_at) VALUES (?,?,?,?)",
                 (interaction.guild_id, name, interaction.channel_id, now_iso()))
    db().commit()
    await interaction.response.send_message(
        f"💀 **{name}** is open!\n"
        "• Each week, pick **one NFL team to win** with `/survivor pick`.\n"
        "• You can **never use the same team twice**.\n"
        "• Change your pick until that game kicks off.\n"
        "• If your team loses (or ties), or you skip a week, **you're out**. Last one standing wins.\n"
        "• Everyone has to get in with a pick this first week. `/survivor standings` shows who's left.")


async def survivor_team_autocomplete(interaction: discord.Interaction, current: str):
    pool = active_pool(interaction.guild_id)
    used = set()
    if pool:
        used = {r["team_id"] for r in db().execute(
            "SELECT team_id FROM survivor_picks WHERE pool_id = ? AND user_id = ? AND result IS NOT NULL",
            (pool["id"], interaction.user.id))}
    _, games = await upcoming_week()
    out = []
    for ev in games:
        for t in ev["teams"]:
            other = next(x for x in ev["teams"] if x is not t)
            if t["id"] in used or (current and current.lower() not in t["short"].lower()):
                continue
            when = event_time(ev).astimezone(TZ)
            out.append(app_commands.Choice(
                name=clip(f"{t['short']} ({'vs' if t['home'] else 'at'} {other['short']}, {when:%a %-I:%M %p})", 100),
                value=t["short"]))
    return out[:25]


@survivor_group.command(name="pick", description="Your survivor pick for this week")
@app_commands.describe(team="A team playing this week that you haven't used")
@app_commands.autocomplete(team=survivor_team_autocomplete)
async def survivor_pick(interaction: discord.Interaction, team: str):
    pool = active_pool(interaction.guild_id)
    if pool is None:
        await interaction.response.send_message("No survivor pool running. A mod can start one with `/survivor start`.",
                                                ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    me = survivor_status(pool).get(interaction.user.id)
    if me and not me["alive"]:
        await interaction.followup.send(f"You're out ({me['out']}). Catch the next pool!", ephemeral=True)
        return
    wk, games = await upcoming_week()
    if not wk:
        await interaction.followup.send("I can't find any upcoming NFL games right now.", ephemeral=True)
        return
    first_week = db().execute("SELECT week_key FROM survivor_picks WHERE pool_id = ? ORDER BY start LIMIT 1",
                              (pool["id"],)).fetchone()
    if first_week and first_week["week_key"] != wk and not me:
        await interaction.followup.send("Entries closed after the first week. Catch the next pool!", ephemeral=True)
        return
    choice = None
    for ev in games:
        for t in ev["teams"]:
            if team_matches(team, t):
                choice = (ev, t)
    if choice is None:
        await interaction.followup.send(f"I can't find {team} among this week's games that haven't started. "
                                        "Pick from the list as you type.", ephemeral=True)
        return
    ev, t = choice
    if db().execute("SELECT 1 FROM survivor_picks WHERE pool_id = ? AND user_id = ? AND team_id = ? AND week_key != ?",
                    (pool["id"], interaction.user.id, t["id"], wk)).fetchone():
        await interaction.followup.send(f"You already used the {t['short']}. Every team only once!", ephemeral=True)
        return
    existing = db().execute("SELECT * FROM survivor_picks WHERE pool_id = ? AND user_id = ? AND week_key = ?",
                            (pool["id"], interaction.user.id, wk)).fetchone()
    if existing and datetime.fromisoformat(existing["start"]) <= datetime.now(timezone.utc):
        await interaction.followup.send(f"Your pick ({existing['team']}) already kicked off, so it's locked.",
                                        ephemeral=True)
        return
    db().execute("""INSERT OR REPLACE INTO survivor_picks (pool_id, user_id, user_name, week_key, team, team_id, event_id,
                    start, created_at) VALUES (?,?,?,?,?,?,?,?,?)""",
                 (pool["id"], interaction.user.id, interaction.user.display_name, wk, t["short"], t["id"], ev["id"],
                  iso(event_time(ev)), now_iso()))
    db().commit()
    other = next(x for x in ev["teams"] if x is not t)
    await interaction.followup.send(
        f"💀 Locked in: **{t['short']}** to beat the {other['short']} "
        f"({event_time(ev).astimezone(TZ):%a %-I:%M %p}). You can change it until kickoff.", ephemeral=True)


@survivor_group.command(name="standings", description="Who's still alive in survivor")
async def survivor_standings(interaction: discord.Interaction):
    pool = active_pool(interaction.guild_id) or db().execute(
        "SELECT * FROM survivor_pools WHERE guild_id = ? ORDER BY id DESC LIMIT 1", (interaction.guild_id,)).fetchone()
    if pool is None:
        await interaction.response.send_message("No survivor pool yet. A mod can start one with `/survivor start`.")
        return
    await interaction.response.send_message(embed=survivor_embed(pool))


bot.tree.add_command(survivor_group)


@bot.tree.command(name="exposure", description="Every open pick grouped by the game it rides on, with money at risk")
@app_commands.guild_only()
async def exposure_cmd(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    await interaction.followup.send(embed=await exposure_embed(interaction.guild_id))


HISTORY_STATUS = [app_commands.Choice(name=n, value=v) for n, v in
                  (("Open", "open"), ("Settled", "settled"), ("Wins", "win"), ("Losses", "loss"), ("Pushes", "push"))]


@bot.tree.command(name="history", description="Look back through picks, with filters")
@app_commands.guild_only()
@app_commands.describe(member="Optional: one person", label="Optional: a name that isn't a Discord user",
                       status="Optional: open, settled, wins...", sport="Optional: one sport")
@app_commands.choices(status=HISTORY_STATUS, sport=SPORT_CHOICES)
async def history_cmd(interaction: discord.Interaction, member: Optional[discord.Member] = None,
                      label: Optional[str] = None, status: Optional[app_commands.Choice[str]] = None,
                      sport: Optional[app_commands.Choice[str]] = None):
    key = name = None
    if member or label:
        key, name, _ = resolve_bettor(interaction, member, label)
    rows = history_rows(interaction.guild_id, key, status.value if status else None, sport.value if sport else None)
    title = "History" + (f" · {name}" if name else "") + (f" · {status.name}" if status else "") + \
            (f" · {sport.name}" if sport else "")
    await interaction.response.send_message(embed=history_embed(rows, 0, title),
                                            view=history_view(interaction.user.id, rows, title) or discord.utils.MISSING)


@bot.tree.command(name="compare", description="Two people side by side")
@app_commands.guild_only()
@app_commands.describe(member="Who to compare", other="Optional: compare against them instead of you")
async def compare_cmd(interaction: discord.Interaction, member: discord.Member, other: Optional[discord.Member] = None):
    a_user, b_user = other or interaction.user, member
    a, b = profile_numbers(interaction.guild_id, str(a_user.id)), profile_numbers(interaction.guild_id, str(b_user.id))
    if not a or not b:
        missing = a_user.display_name if not a else b_user.display_name
        await interaction.response.send_message(f"{missing} has no picks logged yet.", ephemeral=True)
        return
    rows = [("Record", lambda x: record_line(x["s"]), None),
            ("Net", lambda x: signed(x["s"]["net"]), lambda x: x["s"]["net"]),
            ("ROI", lambda x: f"{x['s']['roi']:+.1f}%", lambda x: x["s"]["roi"]),
            ("Win rate", lambda x: (f"{x['s']['wins'] / (x['s']['wins'] + x['s']['losses']) * 100:.0f}%"
                                    if x["s"]["wins"] + x["s"]["losses"] else "-"),
             lambda x: x["s"]["wins"] / (x["s"]["wins"] + x["s"]["losses"]) if x["s"]["wins"] + x["s"]["losses"] else -1),
            ("Streak", lambda x: x["streak"] or "-", None),
            ("Legs hit", lambda x: (x["legs"] or "-").split(" (")[0], None),
            ("Best hit", lambda x: x["best"], None),
            ("Top sport", lambda x: x["sport"], None),
            ("Badges", lambda x: f"{x['badges']}/{len(BADGES)}", lambda x: x["badges"])]
    def col(x, other_x):
        out = []
        for _, show, score in rows:
            mark = " ◀" if score and score(x) > score(other_x) else ""
            out.append(f"{show(x)}{mark}")
        return "\n".join(out)
    e = discord.Embed(title=f"{a_user.display_name} vs {b_user.display_name}", color=BRAND)
    e.add_field(name="​", value="\n".join(f"**{r[0]}**" for r in rows))
    e.add_field(name=a_user.display_name, value=col(a, b))
    e.add_field(name=b_user.display_name, value=col(b, a))
    h2h = db().execute("""SELECT winner_id FROM challenges WHERE guild_id = ? AND status = 'settled'
                          AND ((challenger_id = ? AND opponent_id = ?) OR (challenger_id = ? AND opponent_id = ?))""",
                       (interaction.guild_id, a_user.id, b_user.id, b_user.id, a_user.id)).fetchall()
    if h2h:
        aw = sum(1 for r in h2h if r["winner_id"] == a_user.id)
        bw = sum(1 for r in h2h if r["winner_id"] == b_user.id)
        e.set_footer(text=f"Head-to-head challenges: {a_user.display_name} {aw}-{bw}")
    await interaction.response.send_message(embed=e)


@bot.tree.command(name="undo", description=f"Delete the last pick you logged (within {UNDO_MINUTES} minutes)")
@app_commands.guild_only()
async def undo_cmd(interaction: discord.Interaction):
    cutoff = iso(datetime.now(timezone.utc) - timedelta(minutes=UNDO_MINUTES))
    p = db().execute("SELECT * FROM picks WHERE guild_id = ? AND logged_by = ? AND created_at >= ? AND import_key IS NULL "
                     "ORDER BY id DESC LIMIT 1", (interaction.guild_id, interaction.user.id, cutoff)).fetchone()
    if p is None:
        await interaction.response.send_message(
            f"Nothing you logged in the last {UNDO_MINUTES} minutes. For older picks use `/delete`.", ephemeral=True)
        return
    db().execute("DELETE FROM legs WHERE pick_id = ?", (p["id"],))
    db().execute("DELETE FROM follows WHERE pick_id = ?", (p["id"],))
    db().execute("DELETE FROM pings WHERE pick_id = ?", (p["id"],))
    db().execute("DELETE FROM picks WHERE id = ?", (p["id"],))
    db().commit()
    await interaction.response.send_message(f"↩️ Undid pick `#{p['id']}`: {clip(p['description'], 80)}.", ephemeral=True)


@bot.tree.command(name="remind", description="DM yourself a reminder: 'in 2h', '6pm', 'tomorrow 9am'")
@app_commands.describe(when="e.g. 30m, 2h, 6pm, 18:30, tomorrow 9am, tonight 7", text="What to remind you about")
async def remind_cmd(interaction: discord.Interaction, when: app_commands.Range[str, 1, 40],
                     text: app_commands.Range[str, 1, 200]):
    due = parse_when(when)
    if due is None:
        await interaction.response.send_message(
            "I couldn't read that time. Try `30m`, `2h`, `6pm`, `18:30`, `tomorrow 9am` (up to 30 days out).",
            ephemeral=True)
        return
    db().execute("INSERT INTO reminders (guild_id, user_id, channel_id, text, due_at, created_at) VALUES (?,?,?,?,?,?)",
                 (interaction.guild_id, interaction.user.id, interaction.channel_id, text, iso(due), now_iso()))
    db().commit()
    await interaction.response.send_message(f"⏰ Got it. I'll DM you **{due:%a %b %-d at %-I:%M %p}** Central: {text}",
                                            ephemeral=True)


@bot.tree.command(name="reminders", description="Your upcoming reminders (and cancel one)")
@app_commands.describe(cancel="Optional: the reminder number to cancel")
async def reminders_cmd(interaction: discord.Interaction, cancel: Optional[int] = None):
    if cancel is not None:
        n = db().execute("DELETE FROM reminders WHERE id = ? AND user_id = ? AND sent_at IS NULL",
                         (cancel, interaction.user.id)).rowcount
        db().commit()
        await interaction.response.send_message("Cancelled." if n else "No upcoming reminder with that number.",
                                                ephemeral=True)
        return
    rows = db().execute("SELECT * FROM reminders WHERE user_id = ? AND sent_at IS NULL ORDER BY due_at LIMIT 20",
                        (interaction.user.id,)).fetchall()
    lines = [f"`{r['id']}` {datetime.fromisoformat(r['due_at']).astimezone(TZ):%a %b %-d %-I:%M %p} · {r['text']}"
             for r in rows]
    await interaction.response.send_message("\n".join(lines) or "No upcoming reminders. Set one with `/remind`.",
                                            ephemeral=True)


@bot.tree.command(name="backups", description="Nightly backup of every pick to this channel (turn on or off)")
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
async def backups_cmd(interaction: discord.Interaction):
    if get_setting(interaction.guild_id, "backup_channel") == str(interaction.channel_id):
        set_setting(interaction.guild_id, "backup_channel", None)
        await interaction.response.send_message("Nightly backups are **off** for this channel.")
        return
    set_setting(interaction.guild_id, "backup_channel", str(interaction.channel_id))
    when = datetime(2000, 1, 1, BACKUP_HOUR).strftime("%-I %p")
    await interaction.response.send_message(
        f"🗄️ Nightly backups are **on** here, every night around {when}. Each one is the full database plus an "
        "Excel copy. Here's the first one now. Keep this channel private to admins.",
        files=backup_files(interaction.guild_id))


@bot.tree.command(name="settings", description="Everything the bot is set up to do in this server (admins)")
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
async def settings_cmd(interaction: discord.Interaction):
    gid = interaction.guild_id
    def chan(key):
        v = get_setting(gid, key)
        return f"<#{v}>" if v else "not set"
    receipts = [f"<#{c}>" for c in sorted(bot.receipt_channels)]
    guides = [f"<#{r['key'].split(':', 1)[1]}>" for r in
              db().execute("SELECT key FROM settings WHERE guild_id = ? AND key LIKE 'guide_msg:%'", (gid,))]
    count = lambda sql: db().execute(sql, (gid,)).fetchone()[0]
    open_n = count("SELECT COUNT(*) FROM picks WHERE guild_id = ? AND status = 'open'")
    season = current_season(gid)
    pool = active_pool(gid)
    e = discord.Embed(title="⚙️ PIMP-BOT settings", color=BRAND)
    e.add_field(name="Channels", inline=False, value=(
        f"Receipts: {', '.join(receipts) or 'not set'} (`/receipts`)\n"
        f"Recaps, reminders, results: {chan('recap_channel')} (`/recapchannel`)\n"
        f"Hall of fame: {chan('hof_channel')} (`/halloffame`)\n"
        f"Morning games: {chan('today_channel')} (`/todaypost`)\n"
        f"Backups: {chan('backup_channel')} (`/backups`)\n"
        f"Guide: {', '.join(guides) or 'not posted'} (`/guide`)"))
    e.add_field(name="Features", inline=False, value=(
        f"Claude (slips, questions, prop grading): {'on' if ai_enabled() else 'off: add ANTHROPIC_API_KEY on Railway'}\n"
        f"Auto-grading: {'after ' + str(AUTOGRADE_AFTER_HOURS) + 'h' if AUTOGRADE_AFTER_HOURS else 'off'} · "
        f"paid lookups today: {get_setting(gid, 'autogrades:' + datetime.now(TZ).date().isoformat()) or 0}/{AUTOGRADE_DAILY_LIMIT}\n"
        f"Hot Hand roles: {'on' if get_setting(gid, 'hotroles') == 'on' else 'off'} (`/hotroles`)\n"
        f"Season: {season['name'] if season else 'none'} · Survivor: {pool['name'] if pool else 'none'}\n"
        f"Dashboard: {'on (`/dashboard` for the link)' if dashboard_url() else 'off (generate a domain on Railway)'} · "
        f"Prop of the Day: {chan('potd_channel')}"))
    size = os.path.getsize(DB_PATH) / 1024 if os.path.exists(DB_PATH) else 0
    e.add_field(name="Data", inline=False, value=(
        f"{count('SELECT COUNT(*) FROM picks WHERE guild_id = ?')} picks "
        f"({open_n} open) · "
        f"{count('SELECT COUNT(*) FROM players WHERE guild_id = ?')} players · "
        f"{count('SELECT COUNT(*) FROM locks WHERE guild_id = ?')} locks · "
        f"{count('SELECT COUNT(*) FROM pickem_rounds WHERE guild_id = ?')} pick'em rounds\n"
        f"Database: {size:,.0f} KB at `{DB_PATH}`"
        + ("" if DB_PATH.startswith("/data") else " ⚠️ not on the /data volume")))
    e.set_footer(text=f"Version {BOT_VERSION}")
    await interaction.response.send_message(embed=e, ephemeral=True, view=SettingsView(gid))


# ---- r9 commands -----------------------------------------------------------------------------

async def open_pick_autocomplete(interaction: discord.Interaction, current: str):
    rows = db().execute("""SELECT * FROM picks WHERE guild_id = ? AND status = 'open' AND
                           (bettor_key = ? OR logged_by = ?) ORDER BY id DESC LIMIT 50""",
                        (interaction.guild_id, str(interaction.user.id), interaction.user.id)).fetchall()
    if len(rows) < 5:
        rows = list(rows) + [r for r in db().execute(
            "SELECT * FROM picks WHERE guild_id = ? AND status = 'open' ORDER BY id DESC LIMIT 25",
            (interaction.guild_id,)).fetchall() if r["id"] not in {x["id"] for x in rows}]
    cur = (current or "").lower().lstrip("#")
    out = []
    for r in rows:
        label = clip(f"#{r['id']} · {r['bettor_name']} · {r['description']}", 100)
        if not cur or cur in label.lower():
            out.append(app_commands.Choice(name=label, value=r["id"]))
    return out[:25]


@bot.tree.command(name="sweat", description="Live tracker for a pick: every leg's stats and score, updating by itself")
@app_commands.guild_only()
@app_commands.describe(pick_id="Which pick (defaults to your latest open one)")
@app_commands.autocomplete(pick_id=open_pick_autocomplete)
async def sweat_cmd(interaction: discord.Interaction, pick_id: Optional[int] = None):
    if pick_id is None:
        row = db().execute("SELECT id FROM picks WHERE guild_id = ? AND bettor_key = ? AND status = 'open' "
                           "ORDER BY id DESC LIMIT 1", (interaction.guild_id, str(interaction.user.id))).fetchone()
        pick_id = row["id"] if row else None
    p = get_pick(interaction.guild_id, pick_id) if pick_id else None
    if p is None:
        await interaction.response.send_message("No open pick to sweat. Pass a pick number.", ephemeral=True)
        return
    if p["hidden"] and p["status"] == "open":
        if str(interaction.user.id) != p["bettor_key"]:
            await interaction.response.send_message("That one's hidden until it settles.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        entries = await leg_progress(p)
        await interaction.followup.send(embed=sweat_embed(dict(p) | {"hidden": 0}, entries), ephemeral=True)
        return
    await interaction.response.defer(thinking=True)
    entries = await leg_progress(p)
    msg = await interaction.followup.send(embed=sweat_embed(p, entries), view=sweat_view(p["id"]), wait=True)
    db().execute("""INSERT INTO sweats (guild_id, channel_id, message_id, pick_id, user_id, state, created_at)
                    VALUES (?,?,?,?,?,?,?)""",
                 (p["guild_id"], interaction.channel_id, msg.id, p["id"], interaction.user.id,
                  json.dumps(sweat_state(entries)), now_iso()))
    db().commit()


async def trend_player_autocomplete(interaction: discord.Interaction, current: str):
    if len(current or "") < 3:
        return []
    found = await espn_search_players(norm_name(PLAYER_NICKNAMES.get(norm_name(current), current)), PROP_PATHS)
    return [app_commands.Choice(name=clip(f"{f['name']} · {f['team'] or LEAGUE_SLUGS[f['path']].upper()}", 100),
                                value=clip(f"{f['path']}|{f['id']}|{f['name']}|{f['team']}", 100)) for f in found][:25]


async def trend_stat_autocomplete(interaction: discord.Interaction, current: str):
    fam = None
    raw = getattr(interaction.namespace, "player", None) or ""
    if raw.count("|") >= 3:
        fam = FAMILY_OF_PATH.get(raw.split("|")[0])
    cur = (current or "").lower()
    out = []
    for k, (label, f, _, aliases) in STATS.items():
        if fam and f != fam:
            continue
        if cur and cur not in label.lower() and not any(cur in a for a in aliases):
            continue
        out.append(app_commands.Choice(name=f"{label} ({f})" if not fam else label, value=k))
    return out[:25]


@bot.tree.command(name="trend", description="How often a player has gone over a line lately (free ESPN game logs)")
@app_commands.describe(player="Start typing a name", stat="Points, PRA, pass yards, strikeouts...",
                       line="Optional: the line (default: near their recent average)")
@app_commands.autocomplete(player=trend_player_autocomplete, stat=trend_stat_autocomplete)
async def trend_cmd(interaction: discord.Interaction, player: app_commands.Range[str, 2, 100],
                    stat: str, line: Optional[app_commands.Range[float, 0.0, 1000.0]] = None):
    await interaction.response.defer(thinking=True)
    if player.count("|") >= 3:
        path, pid, name, team = player.split("|", 3)
        cand = {"path": path, "id": pid, "name": name, "team": team}
    else:
        nn = norm_name(player)
        nn = PLAYER_NICKNAMES.get(nn, nn)
        fams = {STATS[stat][1]} if stat in STATS else None
        paths = [p for p in PROP_PATHS if not fams or FAMILY_OF_PATH[p] in fams]
        cands = await resolve_player(nn, paths)
        if len(cands) != 1:
            await interaction.followup.send(
                f"I couldn't pin down **{player}**." + (" Pick one from the list as you type." if cands else ""))
            return
        cand = cands[0]
    fam = FAMILY_OF_PATH.get(cand["path"])
    if stat not in STATS:
        keys = [k for k in stat_keys_in(stat) if STATS[k][1] == fam]
        stat = keys[0] if keys else ""
    if stat not in STATS or STATS[stat][1] != fam:
        await interaction.followup.send("Pick a stat from the list for that sport.")
        return
    try:
        games = await trend_games(cand["path"], cand["id"])
    except Exception:
        log.exception("Game log failed")
        await interaction.followup.send("ESPN's game log isn't answering right now. Try again in a bit.")
        return
    values = trend_values(games, stat)
    if not values:
        await interaction.followup.send(f"No games with {STATS[stat][0]} for {cand['name']} yet.")
        return
    use_line = float(line) if line is not None else default_line([v for _, v in values[:10]])
    e = trend_embed(cand["name"], cand["team"], stat, use_line, values, "10")
    png = await asyncio.to_thread(render_trend, cand["name"], STATS[stat][0], use_line, values[:10])
    e.set_image(url="attachment://trend.png")
    await interaction.followup.send(embed=e, file=discord.File(png, filename="trend.png"),
                                    view=TrendView(interaction.user.id, cand, games, stat, use_line, "10"))


kalshi_group = app_commands.Group(name="kalshi", description="Link picks to Kalshi markets so they settle themselves",
                                  guild_only=True)


@kalshi_group.command(name="link", description="Link a pick to its Kalshi market; it settles when Kalshi does")
@app_commands.describe(pick_id="The pick", link="The market's link from Kalshi, or its ticker (KX...)",
                       side="Optional: the side you took")
@app_commands.choices(side=[app_commands.Choice(name="Yes", value="yes"), app_commands.Choice(name="No", value="no")])
@app_commands.autocomplete(pick_id=open_pick_autocomplete)
async def kalshi_link(interaction: discord.Interaction, pick_id: int, link: app_commands.Range[str, 3, 300],
                      side: Optional[app_commands.Choice[str]] = None):
    p = get_pick(interaction.guild_id, pick_id)
    if p is None or not can_edit(interaction, p):
        await interaction.response.send_message("That's not a pick you can link.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    await kalshi_link_flow(interaction, p, link, side.value if side else None, followup=True)


@kalshi_group.command(name="check", description="Where a linked Kalshi pick stands, leg by leg")
@app_commands.autocomplete(pick_id=open_pick_autocomplete)
async def kalshi_check(interaction: discord.Interaction, pick_id: int):
    p = get_pick(interaction.guild_id, pick_id)
    if p is None or not p["kalshi_ticker"]:
        await interaction.response.send_message(
            "That pick isn't linked to Kalshi yet. Use `/kalshi link` or the 🔗 Kalshi button on its card.", ephemeral=True)
        return
    await interaction.response.defer(thinking=True)
    m = await kalshi_market(p["kalshi_ticker"], fresh=True)
    if not m:
        await interaction.followup.send("Kalshi isn't answering for that market right now.")
        return
    await interaction.followup.send(embed=await kalshi_embed(p, m))


bot.tree.add_command(kalshi_group)


@bot.tree.command(name="groupparlay", description="This week's group parlay: everyone adds one leg")
@app_commands.guild_only()
async def groupparlay_cmd(interaction: discord.Interaction):
    r = gp_round(interaction.guild_id)
    await interaction.response.send_message(embed=gp_embed(r), view=gp_view(r["id"]))
    msg = await interaction.original_response()
    db().execute("UPDATE gp_rounds SET channel_id = ?, message_id = ? WHERE id = ?",
                 (interaction.channel_id, msg.id, r["id"]))
    db().commit()


@bot.tree.command(name="copy", description="Log your own copy of someone's pick")
@app_commands.guild_only()
@app_commands.describe(pick_id="The pick to copy", cost="Optional: your stake (default: theirs)",
                       payout="Optional: your max payout (default: scaled to your stake)")
@app_commands.autocomplete(pick_id=open_pick_autocomplete)
async def copy_cmd(interaction: discord.Interaction, pick_id: int,
                   cost: Optional[app_commands.Range[float, 0.01]] = None,
                   payout: Optional[app_commands.Range[float, 0.01]] = None):
    src = get_pick(interaction.guild_id, pick_id)
    if src is None or src["status"] != "open" or src["hidden"]:
        await interaction.response.send_message("That pick isn't open for copying.", ephemeral=True)
        return
    if str(interaction.user.id) == src["bettor_key"]:
        await interaction.response.send_message("That's already your pick.", ephemeral=True)
        return
    if cost is None and payout is None:
        await interaction.response.send_modal(CopyModal(src))
        return
    c = float(cost) if cost is not None else src["cost"]
    pay = float(payout) if payout is not None else (src["payout"] * c / src["cost"] if src["cost"] else c)
    await finish_copy(interaction, src, c, round(pay, 2))


WRAPPED_PERIODS = [app_commands.Choice(name="This season", value="season"),
                   app_commands.Choice(name="This year", value="year"),
                   app_commands.Choice(name="All time", value="all")]


@bot.tree.command(name="wrapped", description="Your betting year (or season) in review, story style")
@app_commands.guild_only()
@app_commands.describe(member="Optional: defaults to you", label="Optional: a name that isn't a Discord user",
                       period="Optional: this season (default), this year or all time")
@app_commands.choices(period=WRAPPED_PERIODS)
async def wrapped_cmd(interaction: discord.Interaction, member: Optional[discord.Member] = None,
                      label: Optional[str] = None, period: Optional[app_commands.Choice[str]] = None):
    key, name, _ = resolve_bettor(interaction, member, label)
    mode = period.value if period else "season"
    since = until = None
    season = current_season(interaction.guild_id) if mode == "season" else None
    if mode == "season" and season is None:
        last = db().execute("SELECT * FROM seasons WHERE guild_id = ? ORDER BY id DESC LIMIT 1",
                            (interaction.guild_id,)).fetchone()
        season = last
    if season:
        since, until, plabel = season["started_at"], season["ended_at"], season["name"]
    elif mode == "year" or mode == "season":
        y = datetime.now(TZ).year
        since, plabel = iso(datetime(y, 1, 1, tzinfo=TZ)), str(y)
    else:
        plabel = "All-Time"
    d = wrapped_data(interaction.guild_id, key, since, until)
    if d is None:
        await interaction.response.send_message(f"No picks for {name} in {plabel} yet.", ephemeral=True)
        return
    await interaction.response.defer(thinking=True)
    pages = wrapped_pages(d, plabel)
    card = (await asyncio.to_thread(render_wrapped, d, plabel)).getvalue()
    await interaction.followup.send(embed=pages[0], view=WrappedView(interaction.user.id, pages, card))


@bot.tree.command(name="schedule", description="When the games on open picks start, with live scores")
@app_commands.guild_only()
@app_commands.describe(member="Optional: someone else's picks", everyone="Optional: everyone's open picks")
async def schedule_cmd(interaction: discord.Interaction, member: Optional[discord.Member] = None,
                       everyone: Optional[bool] = None):
    await interaction.response.defer(thinking=True)
    who = member or interaction.user
    key = None if everyone else str(who.id)
    title = "📅 Everyone's games" if everyone else ("📅 Your games" if who.id == interaction.user.id
                                                   else f"📅 {who.display_name}'s games")
    e = await schedule_embed(interaction.guild_id, key, title)
    await interaction.followup.send(embed=e, view=ScheduleView(interaction.user.id, interaction.guild_id,
                                                               str(interaction.user.id), "all" if everyone else "mine"))


# ---- r10 commands ----------------------------------------------------------------------------

insights_group = app_commands.Group(name="insights", description="Deeper looks at how you bet", guild_only=True)


@insights_group.command(name="tendencies", description="Your betting habits: over vs under, stat types, players, days")
@app_commands.describe(member="Optional: defaults to you", label="Optional: a name that isn't a Discord user")
async def insights_tendencies(interaction: discord.Interaction, member: Optional[discord.Member] = None,
                              label: Optional[str] = None):
    key, name, _ = resolve_bettor(interaction, member, label)
    pages = tendencies_pages(interaction.guild_id, key, name)
    labels = {"props": "🎯 Props", "slips": "🧾 Slips", "when": "📅 When"}
    await interaction.response.send_message(embed=pages["props"],
                                            view=TabView(interaction.user.id, pages, labels, "props"))


@insights_group.command(name="luck", description="Are you running hot or cold compared to the odds you took?")
@app_commands.describe(member="Optional: defaults to you", label="Optional: a name that isn't a Discord user")
async def insights_luck(interaction: discord.Interaction, member: Optional[discord.Member] = None,
                        label: Optional[str] = None):
    key, name, _ = resolve_bettor(interaction, member, label)
    await interaction.response.send_message(embed=luck_embed(interaction.guild_id, key, name))


@insights_group.command(name="heatmap", description="Calendar of every day you were up or down")
@app_commands.describe(member="Optional: defaults to you", label="Optional: a name that isn't a Discord user",
                       weeks="How far back (default 26 weeks)")
async def insights_heatmap(interaction: discord.Interaction, member: Optional[discord.Member] = None,
                           label: Optional[str] = None, weeks: Optional[app_commands.Range[int, 4, 53]] = None):
    key, name, _ = resolve_bettor(interaction, member, label)
    daily = daily_net(interaction.guild_id, key)
    if not daily:
        await interaction.response.send_message(f"No settled picks for {name} yet.", ephemeral=True)
        return
    await interaction.response.defer(thinking=True)
    png = await asyncio.to_thread(render_heatmap, name, daily, weeks or 26)
    await interaction.followup.send(file=discord.File(png, filename="heatmap.png"))


@insights_group.command(name="badbeats", description="Legs that missed by a hair (half a point, one yard...)")
@app_commands.describe(days="Optional: only the last N days")
async def insights_badbeats(interaction: discord.Interaction, days: Optional[app_commands.Range[int, 1, 3650]] = None):
    since = iso(datetime.now(timezone.utc) - timedelta(days=days)) if days else None
    rows = bad_beats(interaction.guild_id, since, 15)
    e = discord.Embed(title="💀 Bad beat board", color=0xE74C3C,
                      description="\n".join(bad_beat_line(r) for r in rows) or
                      "No near-misses on record yet (props and lines graded from box scores count).")
    await interaction.response.send_message(embed=e)


@insights_group.command(name="records", description="The server's record book: biggest hits, streaks, months")
async def insights_records(interaction: discord.Interaction):
    await interaction.response.send_message(embed=records_embed(interaction.guild_id))


bot.tree.add_command(insights_group)


calc_group = app_commands.Group(name="calc", description="Betting calculators")


@calc_group.command(name="pp", description="PrizePicks payouts for every outcome, and the hit rate each pick needs")
@app_commands.describe(picks="How many picks", play="Power or Flex", entry="Entry fee (default $10)",
                       multiplier="Optional: your slip's top multiplier, e.g. 37.5")
@app_commands.choices(play=[app_commands.Choice(name="Power Play", value="power"),
                            app_commands.Choice(name="Flex Play", value="flex")])
async def calc_pp(interaction: discord.Interaction, picks: app_commands.Range[int, 2, 6],
                  play: app_commands.Choice[str], entry: Optional[app_commands.Range[float, 0.01]] = None,
                  multiplier: Optional[app_commands.Range[float, 1.0, 5000.0]] = None):
    amt = float(entry) if entry else 10.0
    own = float(multiplier) if multiplier else None
    await interaction.response.send_message(
        embed=pp_calc_embed(interaction.guild_id, picks, play.value, amt, own),
        view=PPCalcView(interaction.user.id, interaction.guild_id, picks, play.value, amt, own))


@calc_group.command(name="hedge", description="How much to bet on the other side to lock in profit")
@app_commands.describe(odds="Odds on the hedge side: -150, +120, 1.8, 40¢...",
                       pick_id="Optional: one of your open picks (fills in stake and payout)",
                       stake="Optional: your stake", payout="Optional: what your bet pays back if it hits")
@app_commands.autocomplete(pick_id=open_pick_autocomplete)
async def calc_hedge(interaction: discord.Interaction, odds: app_commands.Range[str, 1, 20], pick_id: Optional[int] = None,
                     stake: Optional[app_commands.Range[float, 0.01]] = None,
                     payout: Optional[app_commands.Range[float, 0.01]] = None):
    if pick_id is not None and interaction.guild_id:
        p = get_pick(interaction.guild_id, pick_id)
        if p is None:
            await interaction.response.send_message("No pick with that number.", ephemeral=True)
            return
        stake, payout = p["cost"], p["payout"]
    if not stake or not payout:
        await interaction.response.send_message("Give me a pick number, or your stake and payout.", ephemeral=True)
        return
    try:
        e = hedge_embed(float(stake), float(payout), odds)
    except (ValueError, ZeroDivisionError):
        await interaction.response.send_message("I couldn't read those odds. Try `-150`, `+120`, `1.8` or `40¢`.",
                                                ephemeral=True)
        return
    await interaction.response.send_message(embed=e, ephemeral=True)


bot.tree.add_command(calc_group)


money_group = app_commands.Group(name="money", description="Private: money in and out of your betting apps",
                                 guild_only=True)
MONEY_PLATFORMS = [app_commands.Choice(name=n, value=n) for n in ("Kalshi", "PrizePicks", "Sportsbook", "Other")]


async def log_cash(interaction: discord.Interaction, kind: str, amount: float, platform: str, note: Optional[str]):
    db().execute("INSERT INTO cashflows (guild_id, user_id, platform, kind, amount, note, created_at) VALUES (?,?,?,?,?,?,?)",
                 (interaction.guild_id, interaction.user.id, platform, kind, amount, note, now_iso()))
    db().commit()
    await interaction.response.send_message(
        f"{'📥 Deposit' if kind == 'deposit' else '📤 Withdrawal'} of {money(amount)} on {platform} logged.",
        embed=money_embed(interaction.guild_id, interaction.user.id, interaction.user.display_name), ephemeral=True)


@money_group.command(name="deposit", description="Log money you put into a betting app (only you see this)")
@app_commands.choices(platform=MONEY_PLATFORMS)
async def money_deposit(interaction: discord.Interaction, amount: app_commands.Range[float, 0.01],
                        platform: app_commands.Choice[str], note: Optional[app_commands.Range[str, 1, 100]] = None):
    await log_cash(interaction, "deposit", float(amount), platform.value, note)


@money_group.command(name="withdraw", description="Log money you took out of a betting app (only you see this)")
@app_commands.choices(platform=MONEY_PLATFORMS)
async def money_withdraw(interaction: discord.Interaction, amount: app_commands.Range[float, 0.01],
                         platform: app_commands.Choice[str], note: Optional[app_commands.Range[str, 1, 100]] = None):
    await log_cash(interaction, "withdraw", float(amount), platform.value, note)


@money_group.command(name="summary", description="Deposits, withdrawals and pick results by app (only you see this)")
async def money_summary(interaction: discord.Interaction):
    await interaction.response.send_message(
        embed=money_embed(interaction.guild_id, interaction.user.id, interaction.user.display_name), ephemeral=True)


@money_group.command(name="tax", description="A year's wins and losses by app, plus an Excel file (only you see this)")
@app_commands.describe(year="Default: this year")
async def money_tax(interaction: discord.Interaction, year: Optional[app_commands.Range[int, 2015, 2100]] = None):
    y = year or datetime.now(TZ).year
    e, xlsx = tax_summary(interaction.guild_id, interaction.user.id, y)
    await interaction.response.send_message(embed=e, file=discord.File(xlsx, filename=f"betting_{y}.xlsx"), ephemeral=True)


@money_group.command(name="undo", description="Remove the last deposit or withdrawal you logged")
async def money_undo(interaction: discord.Interaction):
    row = db().execute("SELECT * FROM cashflows WHERE guild_id = ? AND user_id = ? ORDER BY id DESC LIMIT 1",
                       (interaction.guild_id, interaction.user.id)).fetchone()
    if row is None:
        await interaction.response.send_message("Nothing to undo.", ephemeral=True)
        return
    db().execute("DELETE FROM cashflows WHERE id = ?", (row["id"],))
    db().commit()
    await interaction.response.send_message(f"Removed the {row['kind']} of {money(row['amount'])} on {row['platform']}.",
                                            ephemeral=True)


bot.tree.add_command(money_group)


coins_group = app_commands.Group(name="coins", description="PIMP Coins: play money you earn by playing", guild_only=True)


@coins_group.command(name="balance", description="Your coins (or someone else's)")
async def coins_balance(interaction: discord.Interaction, member: Optional[discord.Member] = None):
    who = member or interaction.user
    bal = coin_balance(interaction.guild_id, who.id)
    recent = db().execute("SELECT * FROM coin_tx WHERE guild_id = ? AND user_id = ? ORDER BY id DESC LIMIT 8",
                          (interaction.guild_id, who.id)).fetchall()
    e = discord.Embed(title=f"{COIN} {who.display_name}: {bal:,} coins", color=0xF1C40F,
                      description="\n".join(f"`{'+' if r['delta'] >= 0 else ''}{r['delta']}` {r['reason']}" for r in recent))
    e.set_footer(text="Earn: log picks, win picks, hit parlays, group parlay, pick'em, survivor, Prop of the Day, "
                      "hot takes, /coins daily")
    await interaction.response.send_message(embed=e)


@coins_group.command(name="daily", description="Claim your daily coins (streaks pay more)")
async def coins_daily(interaction: discord.Interaction):
    today = datetime.now(TZ).date()
    raw = get_setting(interaction.guild_id, f"coinsdaily:{interaction.user.id}")
    last, streak = (raw.split("|") + ["0"])[:2] if raw else ("", "0")
    if last == today.isoformat():
        await interaction.response.send_message("Already claimed today. Come back tomorrow.", ephemeral=True)
        return
    streak_n = int(streak) + 1 if last == (today - timedelta(days=1)).isoformat() else 1
    amount = DAILY_COINS + min(25, 5 * (streak_n - 1))
    award(interaction.guild_id, interaction.user.id, amount, f"Daily claim (day {streak_n})",
          f"daily:{interaction.user.id}:{today.isoformat()}")
    set_setting(interaction.guild_id, f"coinsdaily:{interaction.user.id}", f"{today.isoformat()}|{streak_n}")
    await interaction.response.send_message(
        f"{COIN} +{amount} · day {streak_n} streak · balance {coin_balance(interaction.guild_id, interaction.user.id):,}")


@coins_group.command(name="top", description="Richest people in the server (play money)")
async def coins_top_cmd(interaction: discord.Interaction):
    rows = coins_top(interaction.guild_id)
    medals = ["🥇", "🥈", "🥉"]
    lines = [f"{medals[i] if i < 3 else f'`{i + 1}.`'} <@{r['user_id']}> · {COIN}{int(r['bal']):,}" for i, r in enumerate(rows)]
    await interaction.response.send_message(embed=discord.Embed(title=f"{COIN} Coin leaderboard", color=0xF1C40F,
                                                                description="\n".join(lines) or "Nobody has coins yet."),
                                            allowed_mentions=discord.AllowedMentions.none())


@coins_group.command(name="give", description="Send someone some of your coins")
async def coins_give(interaction: discord.Interaction, member: discord.Member, amount: app_commands.Range[int, 1, 1000000]):
    if member.id == interaction.user.id:
        await interaction.response.send_message("Can't tip yourself.", ephemeral=True)
        return
    bal = coin_balance(interaction.guild_id, interaction.user.id)
    if amount > bal:
        await interaction.response.send_message(f"You've only got {COIN}{bal:,}.", ephemeral=True)
        return
    ref = f"give:{interaction.user.id}:{member.id}:{now_iso()}"
    award(interaction.guild_id, interaction.user.id, -amount, f"Sent to {member.display_name}", ref + ":out")
    award(interaction.guild_id, member.id, amount, f"From {interaction.user.display_name}", ref + ":in")
    await interaction.response.send_message(f"{COIN} {interaction.user.display_name} sent {member.mention} **{amount:,}** coins.",
                                            allowed_mentions=discord.AllowedMentions(users=[member]))


bot.tree.add_command(coins_group)


market_group = app_commands.Group(name="market", description="Yes/no markets on anything, bet with coins",
                                  guild_only=True)


@market_group.command(name="create", description="Open a yes/no market people can bet coins on")
@app_commands.describe(question="e.g. 'Will Levi hit a 6-pick this week?'",
                       closes="Optional: when betting stops (2h, 6pm, tomorrow 9am, 3 weeks, jan 15)")
async def market_create(interaction: discord.Interaction, question: app_commands.Range[str, 5, 200],
                        closes: Optional[app_commands.Range[str, 1, 40]] = None):
    closes_at = None
    if closes:
        when = parse_due(closes)
        if when is None:
            await interaction.response.send_message("I couldn't read that time. Try `2h`, `6pm`, `tomorrow 9am`, `jan 15`.",
                                                    ephemeral=True)
            return
        closes_at = iso(when)
    cur = db().execute("""INSERT INTO markets (guild_id, creator_id, creator_name, question, closes_at, status, channel_id,
                          created_at) VALUES (?,?,?,?,?,'open',?,?)""",
                       (interaction.guild_id, interaction.user.id, interaction.user.display_name, question, closes_at,
                        interaction.channel_id, now_iso()))
    db().commit()
    m = get_market(cur.lastrowid)
    await interaction.response.send_message(embed=market_embed(m), view=market_view(m["id"]))
    msg = await interaction.original_response()
    db().execute("UPDATE markets SET message_id = ? WHERE id = ?", (msg.id, m["id"]))
    db().commit()


@market_group.command(name="list", description="Markets that are still open")
async def market_list(interaction: discord.Interaction):
    rows = db().execute("SELECT * FROM markets WHERE guild_id = ? AND status IN ('open', 'closed') ORDER BY id DESC LIMIT 20",
                        (interaction.guild_id,)).fetchall()
    lines = []
    for m in rows:
        pools = market_pools(m["id"])
        lines.append(f"`#{m['id']}` {clip(m['question'], 70)} · YES {COIN}{pools['yes']:,} / NO {COIN}{pools['no']:,}"
                     + (" · 🔒 closed" if not market_open(m) else ""))
    await interaction.response.send_message(embed=discord.Embed(title="🎲 Open markets", color=BRAND,
                                                                description="\n".join(lines) or "None. `/market create` one!"))


bot.tree.add_command(market_group)


take_group = app_commands.Group(name="take", description="Hot takes the bot holds you to", guild_only=True)


@take_group.command(name="add", description="Put a hot take on the record; the bot brings it back to grade")
@app_commands.describe(take="e.g. 'Bears make the playoffs'", check="When to grade it: 3 weeks, 2 months, jan 15, 2027-01-15")
async def take_add(interaction: discord.Interaction, take: app_commands.Range[str, 5, 300],
                   check: app_commands.Range[str, 1, 40]):
    due = parse_due(check)
    if due is None:
        await interaction.response.send_message("I couldn't read that date. Try `3 weeks`, `2 months`, `jan 15` or "
                                                "`2027-01-15` (up to a year out).", ephemeral=True)
        return
    cur = db().execute("""INSERT INTO takes (guild_id, user_id, user_name, text, due_at, status, channel_id, created_at)
                          VALUES (?,?,?,?,?,'open',?,?)""", (interaction.guild_id, interaction.user.id,
                                                             interaction.user.display_name, take, iso(due),
                                                             interaction.channel_id, now_iso()))
    db().commit()
    t = db().execute("SELECT * FROM takes WHERE id = ?", (cur.lastrowid,)).fetchone()
    await interaction.response.send_message(embed=take_embed(t), view=take_view(t))


@take_group.command(name="list", description="Someone's takes and their record")
async def take_list(interaction: discord.Interaction, member: Optional[discord.Member] = None):
    who = member or interaction.user
    rows = db().execute("SELECT * FROM takes WHERE guild_id = ? AND user_id = ? ORDER BY id DESC LIMIT 15",
                        (interaction.guild_id, who.id)).fetchall()
    icon = {"right": "✅", "wrong": "❌", "open": "⏳"}
    lines = [f"{icon[t['status']]} `#{t['id']}` {clip(t['text'], 90)}" for t in rows]
    e = discord.Embed(title=f"🔥 {who.display_name}'s takes · {takes_record(interaction.guild_id, who.id)}", color=0xE67E22,
                      description="\n".join(lines) or "No takes yet. `/take add` one.")
    await interaction.response.send_message(embed=e)


bot.tree.add_command(take_group)


potd_group = app_commands.Group(name="potd", description="Prop of the Day: everyone votes More or Less", guild_only=True)


@potd_group.command(name="here", description="Post the Prop of the Day in this channel every morning (turn on or off)")
async def potd_here(interaction: discord.Interaction):
    perms = getattr(interaction.user, "guild_permissions", None)
    if not (perms and getattr(perms, "manage_guild", False)):
        await interaction.response.send_message("Admins only.", ephemeral=True)
        return
    if get_setting(interaction.guild_id, "potd_channel") == str(interaction.channel_id):
        set_setting(interaction.guild_id, "potd_channel", None)
        await interaction.response.send_message("Prop of the Day is **off** here.")
        return
    set_setting(interaction.guild_id, "potd_channel", str(interaction.channel_id))
    await interaction.response.send_message(
        "🎯 Prop of the Day is **on** here. Every morning I'll pick a star playing tonight, set the line at their "
        "recent median, and everyone votes More or Less. Right answers earn coins.")


@potd_group.command(name="now", description="Post a Prop of the Day right now (mods)")
async def potd_now(interaction: discord.Interaction):
    if not is_mod(interaction.user):
        await interaction.response.send_message("Mods only.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    cands = await potd_candidates(interaction.guild_id, datetime.now(timezone.utc))
    if not cands:
        await interaction.followup.send("No games later today with a clear star to pick. Try `/potd set`.", ephemeral=True)
        return
    import random
    await create_potd(interaction.guild_id, interaction.channel, datetime.now(timezone.utc), random.choice(cands))
    await interaction.followup.send("Posted.", ephemeral=True)


@potd_group.command(name="set", description="Pick today's prop yourself (mods)")
@app_commands.describe(player="Start typing a name", stat="The stat", line="Optional: the line (default: recent median)")
@app_commands.autocomplete(player=trend_player_autocomplete, stat=trend_stat_autocomplete)
async def potd_set(interaction: discord.Interaction, player: app_commands.Range[str, 2, 100], stat: str,
                   line: Optional[app_commands.Range[float, 0.0, 1000.0]] = None):
    if not is_mod(interaction.user):
        await interaction.response.send_message("Mods only.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    if player.count("|") < 3:
        found = await resolve_player(norm_name(player), PROP_PATHS)
        if len(found) != 1:
            await interaction.followup.send("Pick the player from the list as you type.", ephemeral=True)
            return
        f = found[0]
    else:
        path, pid, name, team = player.split("|", 3)
        f = {"path": path, "id": pid, "name": name, "team": team}
    if stat not in STATS or STATS[stat][1] != FAMILY_OF_PATH[f["path"]]:
        await interaction.followup.send("Pick a stat from the list for that sport.", ephemeral=True)
        return
    found_game = pick_game(await find_games(f["team"], [f["path"]], datetime.now(timezone.utc)), datetime.now(timezone.utc))
    if not found_game or found_game[0].get("state") != "pre":
        await interaction.followup.send(f"I can't find an upcoming game for {f['name']}.", ephemeral=True)
        return
    cand = {"path": f["path"], "event": found_game[0], "athlete_id": f["id"], "name": f["name"], "stat_key": stat}
    await create_potd(interaction.guild_id, interaction.channel, datetime.now(timezone.utc), cand,
                      float(line) if line is not None else None)
    await interaction.followup.send("Posted.", ephemeral=True)


@potd_group.command(name="standings", description="Who's best at Prop of the Day")
async def potd_standings_cmd(interaction: discord.Interaction):
    rows = potd_standings(interaction.guild_id)
    lines = [f"`{i + 1}.` **{n}** · {w}-{l} ({w / max(1, w + l) * 100:.0f}%)" for i, (n, w, l) in enumerate(rows[:20])]
    await interaction.response.send_message(embed=discord.Embed(title="🎯 Prop of the Day standings", color=BRAND,
                                                                description="\n".join(lines) or "No graded props yet."))


bot.tree.add_command(potd_group)


async def player_lookup(interaction: discord.Interaction, player: str) -> Optional[dict]:
    if player.count("|") >= 3:
        path, pid, name, team = player.split("|", 3)
        return {"path": path, "id": pid, "name": name, "team": team}
    nn = norm_name(player)
    found = await resolve_player(PLAYER_NICKNAMES.get(nn, nn), PROP_PATHS)
    return found[0] if len(found) == 1 else None


@player_group.command(name="avg", description="A player's averages: last 5, last 10 and everything on file")
@app_commands.describe(player="Start typing a name")
@app_commands.autocomplete(player=trend_player_autocomplete)
async def player_avg(interaction: discord.Interaction, player: app_commands.Range[str, 2, 100]):
    await interaction.response.defer(thinking=True)
    cand = await player_lookup(interaction, player)
    if cand is None:
        await interaction.followup.send(f"I couldn't pin down **{player}**. Pick from the list as you type.")
        return
    try:
        games = await trend_games(cand["path"], cand["id"])
    except Exception:
        await interaction.followup.send("ESPN's game log isn't answering right now.")
        return
    await interaction.followup.send(embed=avg_embed(cand, games), view=AvgView(interaction.user.id, cand, games))


@player_group.command(name="vs", description="How a player has done against one team")
@app_commands.describe(player="Start typing a name", opponent="Team, e.g. ATL, Hawks, Dallas")
@app_commands.autocomplete(player=trend_player_autocomplete)
async def player_vs(interaction: discord.Interaction, player: app_commands.Range[str, 2, 100],
                    opponent: app_commands.Range[str, 2, 40]):
    await interaction.response.defer(thinking=True)
    cand = await player_lookup(interaction, player)
    if cand is None:
        await interaction.followup.send(f"I couldn't pin down **{player}**. Pick from the list as you type.")
        return
    try:
        games = await trend_games(cand["path"], cand["id"], need=500)
    except Exception:
        await interaction.followup.send("ESPN's game log isn't answering right now.")
        return
    await interaction.followup.send(embed=vs_embed(cand, games, opponent))


@bot.tree.command(name="dashboard", description="Link to the live web dashboard (only you see it)")
@app_commands.guild_only()
async def dashboard_cmd(interaction: discord.Interaction):
    url = dashboard_url()
    if url:
        await interaction.response.send_message(f"📊 Live dashboard: {url}\nKeep the link in the group; anyone with it can "
                                                "see the stats.", ephemeral=True)
    else:
        await interaction.response.send_message(
            "The dashboard isn't switched on yet. In Railway: open the bot's service → **Settings** → **Networking** → "
            "**Generate Domain**. Then run this again.", ephemeral=True)


@bot.tree.context_menu(name="Log as pick")
@app_commands.guild_only()
async def ctx_log_pick(interaction: discord.Interaction, message: discord.Message):
    await log_message_as_pick(interaction, message)


@bot.tree.context_menu(name="Copy this pick")
@app_commands.guild_only()
async def ctx_copy_pick(interaction: discord.Interaction, message: discord.Message):
    await copy_from_message(interaction, message)


# ---- r11 commands ------------------------------------------------------------------------------

sports_group = app_commands.Group(name="sports", description="Scores, standings, injuries, weather and more (free data)")
ALL_PATHS = list(LEAGUE_NAMES)


@sports_group.command(name="box", description="A player's last game, full stat line")
@app_commands.describe(player="Start typing a name")
@app_commands.autocomplete(player=trend_player_autocomplete)
async def sports_box(interaction: discord.Interaction, player: app_commands.Range[str, 2, 100]):
    await interaction.response.defer(thinking=True)
    cand = await player_lookup(interaction, player)
    if cand is None:
        await interaction.followup.send(f"I couldn't pin down **{player}**. Pick from the list as you type.")
        return
    try:
        games, _ = await fetch_gamelog(cand["path"], cand["id"])
    except Exception:
        await interaction.followup.send("ESPN's game log isn't answering right now.")
        return
    if not games:
        await interaction.followup.send(f"No games on file for {cand['name']} yet.")
        return
    g = games[0]
    fam = FAMILY_OF_PATH[cand["path"]]
    parts = []
    for k in MAIN_STATS[fam] + [x for x in ("steals", "blocks", "fantasy", "targets", "rush_att", "runs", "rbis",
                                             "walks", "hits_allowed", "earned_runs", "blocked_shots")
                                 if STATS[x][1] == fam]:
        got = stat_value(g["groups"], k)
        if got is not None and (got[0] or k in MAIN_STATS[fam][:3]):
            parts.append(f"**{STATS[k][0]}** {got[0]:g}")
    when = datetime.fromisoformat(g["date"].replace("Z", "+00:00")).astimezone(TZ).strftime("%a %b %-d") if g["date"] else ""
    e = discord.Embed(title=f"📦 {cand['name']} · {when} {'@' if g['at'] == '@' else 'vs'} {g['opp']} {g['result']}",
                      color=BRAND, description=" · ".join(dict.fromkeys(parts)) or "No stats.")
    if g["preseason"]:
        e.set_footer(text="Preseason game")
    await interaction.followup.send(embed=e)


async def find_team_game(interaction, team: str, league) -> Optional[tuple[str, dict, int]]:
    paths = [league.value] if league else (group_leagues(interaction.guild_id) if interaction.guild_id else DEFAULT_LEAGUES)
    found = await next_game(team, paths)
    if not found and not league:
        found = await next_game(team, [p for p in ALL_PATHS if p not in paths])
    return found


@sports_group.command(name="matchup", description="A team's next game: records, venue, weather, injuries, the group's picks")
@app_commands.describe(team="e.g. Chiefs, Celtics, Ohio State", league="Optional: if the name fits more than one league")
@app_commands.choices(league=SPORT_LEAGUES)
async def sports_matchup(interaction: discord.Interaction, team: app_commands.Range[str, 2, 50],
                         league: Optional[app_commands.Choice[str]] = None):
    await interaction.response.defer(thinking=True)
    found = await find_team_game(interaction, team, league)
    if not found:
        await interaction.followup.send(f"I can't find an upcoming game for **{team}** this week."
                                        + ("" if league else " Try adding the league."))
        return
    path, ev, _ = found
    await interaction.followup.send(embed=await matchup_embed(interaction.guild_id, path, ev))


@sports_group.command(name="weather", description="Kickoff weather for a team's next outdoor game")
@app_commands.describe(team="e.g. Bills, Packers", league="Optional")
@app_commands.choices(league=SPORT_LEAGUES)
async def sports_weather(interaction: discord.Interaction, team: app_commands.Range[str, 2, 50],
                         league: Optional[app_commands.Choice[str]] = None):
    await interaction.response.defer(thinking=True)
    found = await find_team_game(interaction, team, league)
    if not found:
        await interaction.followup.send(f"I can't find an upcoming game for **{team}**.")
        return
    path, ev, _ = found
    v, when = ev.get("venue") or {}, event_time(ev)
    if v.get("indoor"):
        await interaction.followup.send(f"🏟️ {short_game(ev)} is indoors at {v.get('name')}. No weather to worry about.")
        return
    w = await kickoff_weather(v.get("city") or "", v.get("state") or "", when) if v.get("city") and when else None
    if not w:
        await interaction.followup.send(f"No forecast yet for {short_game(ev)} (forecasts go about a week out).")
        return
    await interaction.followup.send(f"🌤️ **{short_game(ev)}** at {v.get('name')}, {v.get('city')}: {weather_line(w)}")


@sports_group.command(name="injuries", description="A team's injury report")
@app_commands.describe(team="e.g. Knicks", league="Optional")
@app_commands.choices(league=SPORT_LEAGUES)
async def sports_injuries(interaction: discord.Interaction, team: app_commands.Range[str, 2, 50],
                          league: Optional[app_commands.Choice[str]] = None):
    await interaction.response.defer(thinking=True)
    found = await find_team_game(interaction, team, league)
    path = found[0] if found else (league.value if league else None)
    name = None
    if found:
        t = found[1]["teams"][found[2]]
        name = t.get("name") or t["short"]
    if not path or not name:
        await interaction.followup.send(f"I couldn't match **{team}** to a team with a game this week.")
        return
    inj = await team_injuries(path, name)
    e = discord.Embed(title=f"🚑 {name} injury report", color=0xE74C3C,
                      description="\n".join(f"**{x['name']}** · {x['status']}" for x in inj[:30]) or "Nobody listed. 🙌")
    await interaction.followup.send(embed=e)


@sports_group.command(name="standings", description="League standings with the playoff line")
@app_commands.choices(league=[c for c in SPORT_LEAGUES if not c.value.startswith("soccer/uefa")])
async def sports_standings(interaction: discord.Interaction, league: app_commands.Choice[str]):
    await interaction.response.defer(thinking=True)
    try:
        groups = await standings_groups(league.value)
    except Exception:
        groups = []
    if not groups:
        await interaction.followup.send("ESPN doesn't have standings for that right now.")
        return
    name, entries = groups[0]
    await interaction.followup.send(embed=standings_embed(league.value, name, entries),
                                    view=StandingsView(interaction.user.id, league.value, groups) if len(groups) > 1
                                    else discord.utils.MISSING)


@sports_group.command(name="rankings", description="College top 25 (AP poll) with movement")
@app_commands.choices(sport=[app_commands.Choice(name="College football", value="football/college-football"),
                             app_commands.Choice(name="College basketball", value="basketball/mens-college-basketball")])
async def sports_rankings(interaction: discord.Interaction, sport: app_commands.Choice[str]):
    await interaction.response.defer(thinking=True)
    try:
        e = await rankings_embed(sport.value)
    except Exception:
        e = discord.Embed(title="Rankings", description="ESPN isn't answering right now.", color=BRAND)
    await interaction.followup.send(embed=e)


@sports_group.command(name="golf", description="This week's PGA Tour leaderboard")
async def sports_golf(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    await interaction.followup.send(embed=await golf_embed())


@sports_group.command(name="ufc", description="The next (or latest) UFC card, fight by fight")
async def sports_ufc(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    await interaction.followup.send(embed=await ufc_embed())


@sports_group.command(name="f1", description="This race weekend's sessions and results")
async def sports_f1(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    await interaction.followup.send(embed=await f1_embed())


@sports_group.command(name="cs2", description="Upcoming CS2 matches (from Liquipedia)")
@app_commands.describe(search="Optional: a team or tournament")
async def sports_cs2(interaction: discord.Interaction, search: Optional[app_commands.Range[str, 2, 40]] = None):
    await interaction.response.defer(thinking=True)
    await interaction.followup.send(embed=await cs2_embed(search))


@sports_group.command(name="consensus", description="Which side the group is on for today's games")
async def sports_consensus(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("Use this in the server.", ephemeral=True)
        return
    await interaction.response.defer(thinking=True)
    await interaction.followup.send(embed=await consensus_embed(interaction.guild_id))


bot.tree.add_command(sports_group)


@player_group.command(name="splits", description="Home vs away, and wins vs losses")
@app_commands.describe(player="Start typing a name")
@app_commands.autocomplete(player=trend_player_autocomplete)
async def player_splits(interaction: discord.Interaction, player: app_commands.Range[str, 2, 100]):
    await interaction.response.defer(thinking=True)
    cand = await player_lookup(interaction, player)
    if cand is None:
        await interaction.followup.send(f"I couldn't pin down **{player}**.")
        return
    games = await trend_games(cand["path"], cand["id"])
    await interaction.followup.send(embed=splits_embed(cand, games))


@player_group.command(name="minutes", description="A basketball player's minutes, game by game (spot role changes)")
@app_commands.describe(player="Start typing a name")
@app_commands.autocomplete(player=trend_player_autocomplete)
async def player_minutes(interaction: discord.Interaction, player: app_commands.Range[str, 2, 100]):
    await interaction.response.defer(thinking=True)
    cand = await player_lookup(interaction, player)
    if cand is None or FAMILY_OF_PATH.get(cand["path"]) != "basketball":
        await interaction.followup.send("Minutes are for basketball players. Pick one from the list as you type.")
        return
    games = await trend_games(cand["path"], cand["id"])
    values = trend_values(games, "minutes")
    if not values:
        await interaction.followup.send("No minutes on file yet.")
        return
    line = default_line([v for _, v in values[:10]])
    e = trend_embed(cand["name"], cand["team"], "minutes", line, values, "10")
    png = await asyncio.to_thread(render_trend, cand["name"], "Minutes", line, values[:10])
    e.set_image(url="attachment://trend.png")
    await interaction.followup.send(embed=e, file=discord.File(png, filename="trend.png"),
                                    view=TrendView(interaction.user.id, cand, games, "minutes", line, "10"))


@insights_group.command(name="autopsy", description="What kills your parlays: the leg types and players that miss")
async def insights_autopsy(interaction: discord.Interaction, member: Optional[discord.Member] = None,
                           label: Optional[str] = None):
    key, name, _ = resolve_bettor(interaction, member, label)
    await interaction.response.send_message(embed=autopsy_embed(interaction.guild_id, key, name))


@insights_group.command(name="risk", description="Drawdown, green weeks, stake sizing and ROI by payout size")
async def insights_risk(interaction: discord.Interaction, member: Optional[discord.Member] = None,
                        label: Optional[str] = None):
    key, name, _ = resolve_bettor(interaction, member, label)
    await interaction.response.send_message(embed=risk_embed(interaction.guild_id, key, name))


@insights_group.command(name="report", description="A month's report card, graded A to F")
@app_commands.describe(month="Optional: YYYY-MM (default: this month)")
async def insights_report(interaction: discord.Interaction, member: Optional[discord.Member] = None,
                          label: Optional[str] = None, month: Optional[app_commands.Range[str, 7, 7]] = None):
    key, name, _ = resolve_bettor(interaction, member, label)
    now = datetime.now(TZ)
    y, m = now.year, now.month
    if month:
        try:
            y, m = int(month[:4]), int(month[5:7])
            datetime(y, m, 1)
        except ValueError:
            await interaction.response.send_message("Use YYYY-MM, like 2026-10.", ephemeral=True)
            return
    rc = report_card(interaction.guild_id, key, name, y, m)
    if rc is None:
        await interaction.response.send_message(f"No settled picks for {name} that month.", ephemeral=True)
        return
    await interaction.response.defer(thinking=True)
    png = await asyncio.to_thread(render_report_card, rc)
    await interaction.followup.send(file=discord.File(png, filename="report_card.png"))


@insights_group.command(name="claudia", description="Claude's picks (logged as Claudia) against everyone else")
async def insights_claudia(interaction: discord.Interaction):
    await interaction.response.send_message(embed=claudia_embed(interaction.guild_id))


@insights_group.command(name="rankings", description="Power rankings: who's hot over the last week and month")
async def insights_rankings(interaction: discord.Interaction):
    lines = power_rankings(interaction.guild_id)
    await interaction.response.send_message(embed=discord.Embed(
        title="📊 Power rankings", color=BRAND, description="\n".join(lines) or "Not enough recent picks."))


@calc_group.command(name="kelly", description="How much of your bankroll a bet is worth, given your chance it hits")
@app_commands.describe(chance="Your honest chance it hits, in percent (e.g. 55)", odds="The price: -110, +150, 2.2, 45¢",
                       bankroll="Optional: your bankroll, to show amounts")
async def calc_kelly(interaction: discord.Interaction, chance: app_commands.Range[float, 1.0, 99.0],
                     odds: app_commands.Range[str, 1, 20], bankroll: Optional[app_commands.Range[float, 1.0]] = None):
    try:
        e = kelly_embed(float(chance) / 100, odds, float(bankroll) if bankroll else None)
    except (ValueError, ZeroDivisionError):
        await interaction.response.send_message("I couldn't read those odds.", ephemeral=True)
        return
    await interaction.response.send_message(embed=e, ephemeral=True)


@calc_group.command(name="slip", description="How often each leg on a pick has hit lately, and the slip's odds")
@app_commands.autocomplete(pick_id=open_pick_autocomplete)
async def calc_slip(interaction: discord.Interaction, pick_id: int):
    p = get_pick(interaction.guild_id, pick_id) if interaction.guild_id else None
    if p is None or not get_legs(p["id"]):
        await interaction.response.send_message("Give me an open pick with legs.", ephemeral=True)
        return
    if p["hidden"] and str(interaction.user.id) != p["bettor_key"]:
        await interaction.response.send_message("That one's hidden.", ephemeral=True)
        return
    await interaction.response.defer(thinking=True, ephemeral=bool(p["hidden"]))
    lines, prob = await slip_odds(p)
    e = discord.Embed(title=f"🎲 Slip odds · pick #{p['id']}", color=BRAND, description="\n".join(lines))
    if prob is not None:
        implied = p["cost"] / p["payout"] if p["payout"] else None
        e.add_field(name="Chance it all hits", value=f"**{prob * 100:.1f}%** (if the legs were independent)")
        if implied:
            e.add_field(name="The payout implies", value=f"{implied * 100:.1f}%")
    else:
        e.add_field(name="Chance it all hits", value="Can't say: some legs have no game-log data (game lines, esports...).")
    e.set_footer(text="Last 10 games against each line. Past results, not a prediction.")
    await interaction.followup.send(embed=e, ephemeral=bool(p["hidden"]))


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction,
                               error: app_commands.AppCommandError):
    log.exception("Command failed", exc_info=error)
    original = getattr(error, "original", error)
    if isinstance(original, discord.Forbidden):
        msg = ("I don't have permission to do that here. Check that my role can **View Channel**, "
               "**Send Messages**, **Embed Links** and **Attach Files** in this channel "
               "(Edit Channel → Permissions → add PIMP-BOT).")
    else:
        msg = "Something went wrong running that. Check the bot's logs for details."
    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("DISCORD_TOKEN is missing. Add it as a variable on Railway "
                         "(or in .env when running locally).")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    bot.run(TOKEN, log_handler=None)
