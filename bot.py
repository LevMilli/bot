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
BOT_VERSION = "2026-10-08 r8"   # shown in /help and the startup log, so you can tell which upload is live


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
                          ("live_checked_at", "TEXT"), ("hof_posted", "TEXT")):
            if col not in cols:
                _conn.execute(f"ALTER TABLE picks ADD COLUMN {col} {kind}")
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
                  sport: Optional[str] = None) -> list[dict]:
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
        description=clip(p["description"], 2000),
        color=color,
    )
    field = legs_field(p["id"])
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
    if p["notes"]:
        e.add_field(name="Notes", value=clip(p["notes"], 300), inline=False)
    if field and p["status"] == "open":
        e.set_footer(text=f"Grade legs with /leg pick_id:{p['id']}")
    return e


def one_liner(p: sqlite3.Row) -> str:
    return (f"`#{p['id']}` **{p['bettor_name']}** · {p['platform']} · "
            f"{money(p['cost'])} → {money(p['payout'])} · {clip(p['description'], 80)}")


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
        lines.append(f"{who} `#{p['id']}` {clip(p['description'], 70)} ({local_day(p['created_at'])})")
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
        put(ws, r, 5, p["description"], wrap=True)
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
  "description": one short line summarizing the play, e.g. "4-pick Power Play" or "3-leg NFL combo",
  "legs": ["one string per leg, e.g. 'Josh Allen over 249.5 pass yds'"],
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
                          "home": c.get("homeAway") == "home",
                          "short": t.get("shortDisplayName") or t.get("displayName") or "?",
                          "aliases": {norm_team(x) for x in (t.get("displayName"), t.get("shortDisplayName"),
                                      t.get("location"), t.get("abbreviation")) if x},
                          "nickname": norm_team(t.get("name") or "")})
        if len(teams) == 2:
            events.append({"id": str(ev.get("id")), "date": ev.get("date") or "", "teams": teams,
                           "state": status.get("state") or "pre", "status_name": status.get("name") or "",
                           "final": bool(status.get("completed")) and status.get("state") == "post",
                           "week": (ev.get("week") or {}).get("number"),
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
        if not ev["final"] or any(t["score"] is None for t in ev["teams"]):
            continue
        result = judge(leg, ev, i)
        if result:
            out[n] = (result, score_line(ev))
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
        return f"🔴 {away['short']} {away['score']:g}, {home['short']} {home['score']:g} (live)"
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
    lines = [today_line(e) for e in events]
    more = len(lines) - 25
    e = discord.Embed(title=f"{LEAGUE_NAMES.get(path, path)} · {day.astimezone(TZ):%a %b %-d}", color=BRAND,
                      description=clip("\n".join(lines[:25]) + (f"\n…and {more} more" if more > 0 else ""), 4000))
    e.set_footer(text="Times are Central")
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
                     f"{clip(p['description'], 55)}{net}")
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
        self.add_dynamic_items(SettleButton, LogSlipButton, FollowButton, ChallengeButton, PickemButton)
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
            if not items or not leagues_for(p["sport"]) or not any(parse_simple_leg(t) for _, t in items):
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
                    lambda n: post_backups(self, n)):
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
        if message.author.bot or message.guild is None:
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


@bot.tree.command(name="leaderboard", description="Everyone ranked by net profit (this season, if one's running)")
@app_commands.guild_only()
@app_commands.describe(period="Optional: season (default), last 7 days, this month or all time",
                       sport="Optional: one sport only")
@app_commands.choices(period=LEADERBOARD_PERIODS, sport=SPORT_CHOICES)
async def leaderboard_cmd(interaction: discord.Interaction, period: Optional[app_commands.Choice[str]] = None,
                          sport: Optional[app_commands.Choice[str]] = None):
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
    sport_name = sport.value if sport else None
    stats = [s for s in compute_stats(gid, since=since, until=until, sport=sport_name)
             if s["wins"] + s["losses"] + s["pushes"] > 0]
    title = f"Leaderboard · {label}" + (f" · {sport_name}" if sport_name else "")
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
        lines.append(f"{rank} **{s['name']}** · {record_line(s)} · "
                     f"{signed(s['net'])} · ROI {s['roi']:+.1f}%" + (f" · {streak}" if streak else ""))
    e = discord.Embed(title=title, description="\n".join(lines), color=BRAND)
    e.set_footer(text="Settled picks only · record is W-L(-Push) · pick a period or sport to filter")
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
        "`/edit` and `/delete` fix mistakes, or `/undo` the pick you just logged. `/open` shows everything still "
        "pending, `/exposure` groups it by game, and `/history` pages back through old picks."))
    auto = discord.Embed(title="⚡ What the bot does on its own", color=BRAND, description=(
        "• **Reads slips** posted in the receipts channel and logs them for you.\n"
        "• **Grades picks the moment games end:** moneylines, spreads and totals settle within minutes "
        "of the final whistle. Everything else is looked up 48 hours after it's logged. "
        "If it gets one wrong, fix it with `/leg` or `/result`.\n"
        "• **Hall of Fame:** big wins get reposted in the hall of fame channel.\n"
        "• **Pings you** about picks open 3+ days.\n"
        "• **Sunday 8 PM:** weekly recap, plus the 🔥 Hot Hand and 🧊 Ice Cold roles.\n"
        "• **Every morning:** today's games, in the channel an admin picked with `/todaypost`.\n"
        "• **The 1st of each month:** monthly awards.\n"
        "• **Shouts out** new badges and 5, 10, 15 and 20-win streaks.\n"
        "• **Nightly backup** of every pick, in the channel an admin picked with `/backups`."))
    group = discord.Embed(title="🤝 With the group", color=BRAND, description=(
        "👍 **Tail** / 👎 **Fade** buttons on any open pick (not your own). `/tailfade` shows who's worth following.\n"
        "`/challenge @someone` head-to-head bet for bragging rights. `/h2h` shows your record against them.\n"
        "`/lock` your lock of the week. One per week, and you can change it until it's graded. "
        "`/locks` shows this week and the standings.\n"
        "`/awards` this month's awards so far · `/season standings` this season's leaderboard.\n"
        "**Pick'em:** tap a team on each game a mod posts; no money, just bragging rights. "
        "`/pickem mine` and `/pickem standings`.\n"
        "**Survivor:** pick one NFL team a week with `/survivor pick`. Each team once; lose or skip and you're out.\n"
        "**@PIMP-BOT** plus a question about a player, team or matchup gets a researched answer."))
    numbers = discord.Embed(title="📊 Your numbers", color=BRAND, description=(
        "`/record` your W-L, profit, ROI, streak and leg hit rate · `/compare @someone` side by side\n"
        "`/leaderboard` filter by week, month, season or sport\n"
        "`/stats` your record split by sport, platform and parlay size\n"
        "`/chart` profit graph, for everyone or just you\n"
        "`/odds` convert -150, +200, 2.5, 45¢ or 60% into break-even % and payout · `/parlay` stack legs\n"
        "`/today` today's games · `/pings` DM before your games start and at halftime\n"
        "`/remind` DM yourself later: `2h`, `6pm`, `tomorrow 9am` · `/reminders` see or cancel\n"
        "`/achievements` your badges · `/card` a shareable image of your profile\n"
        "`/export` everything as an Excel file\n"
        "`/bankroll` units on your pick cards · `/limit` private weekly loss heads-up\n"
        "`/player note` scouting notes on a player · `/player view` notes plus how the group's legs on them went"))
    tips = discord.Embed(title="💡 Tips", color=0xF1C40F, description=(
        "• **Always fill in the sport.** It's how the bot finds the right game to grade for free.\n"
        "• **One leg per item.** Write `Bills ML; Chiefs -3; Over 44.5`, not one long sentence.\n"
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
        f"{champ}🆕 Season **{name}** starts now. `/leaderboard` shows this season; all-time stats stay.",
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
        f"Season: {season['name'] if season else 'none'} · Survivor: {pool['name'] if pool else 'none'}"))
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
    await interaction.response.send_message(embed=e, ephemeral=True)


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
