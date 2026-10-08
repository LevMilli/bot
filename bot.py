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
import io
import json
import logging
import os
import re
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("picksbot")


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
        if "reminded_at" not in cols:
            _conn.execute("ALTER TABLE picks ADD COLUMN reminded_at TEXT")
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
                  since: Optional[str] = None) -> list[dict]:
    """Per-bettor totals, sorted by net profit (best first)."""
    sql = "SELECT * FROM picks WHERE guild_id = ?"
    args: list = [guild_id]
    if bettor_key:
        sql += " AND bettor_key = ?"
        args.append(bettor_key)
    if since:
        sql += " AND status != 'open' AND settled_at >= ?"
        args.append(since)
    sql += " ORDER BY id"

    out: dict[str, dict] = {}
    for p in db().execute(sql, args):
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
    e.add_field(name="Cost", value=money(p["cost"]))
    e.add_field(name="Max payout", value=money(p["payout"]))
    e.add_field(name="Status", value=label)
    if p["status"] != "open":
        e.add_field(name="Net", value=signed((p["returned"] or 0.0) - p["cost"]))
    if p["slip_url"]:
        e.add_field(name="Slip", value=f"[View]({p['slip_url']})")
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
            label=label, style=style, custom_id=f"settle:{pick_id}:{status}"))
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


async def ask_claude(system: str, user_text: str) -> tuple[str, list[str]]:
    """Returns (answer text, source urls)."""
    messages = [{"role": "user", "content": user_text}]
    tools = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}]
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
        self.add_dynamic_items(SettleButton, LogSlipButton)
        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)  # shows up instantly in that server
        else:
            await self.tree.sync()  # global: can take up to an hour to appear
        self.scheduler_task = asyncio.create_task(self.scheduler())

    async def on_ready(self):
        log.info("Logged in as %s | Claude features: %s | receipts channels: %d",
                 self.user, "on" if ai_enabled() else "off",
                 len(self.receipt_channels))

    # ---- scheduled posts ---------------------------------------------------

    async def scheduler(self):
        await self.wait_until_ready()
        while not self.is_closed():
            try:
                await self.run_schedules()
            except Exception:
                log.exception("Scheduled post failed")
            await asyncio.sleep(300)

    async def run_schedules(self, now: Optional[datetime] = None):
        now = now or datetime.now(TZ)
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
    e = discord.Embed(title=f"{s['name']} · {record_line(s)}",
                      color=0x2ECC71 if s["net"] >= 0 else 0xE74C3C)
    e.add_field(name="Staked", value=money(s["staked"]))
    e.add_field(name="Returned", value=money(s["returned"]))
    e.add_field(name="Net", value=signed(s["net"]))
    e.add_field(name="ROI", value=f"{s['roi']:+.1f}%")
    e.add_field(name="Open", value=f"{s['open']} ({money(s['open_risk'])} at risk)")
    rate = hit_rate(leg_counts(interaction.guild_id, key))
    if rate:
        e.add_field(name="Legs", value=rate)
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


@bot.tree.command(name="leaderboard", description="Everyone ranked by net profit")
@app_commands.guild_only()
async def leaderboard_cmd(interaction: discord.Interaction):
    stats = [s for s in compute_stats(interaction.guild_id)
             if s["wins"] + s["losses"] + s["pushes"] > 0]
    if not stats:
        await interaction.response.send_message("No settled picks yet.")
        return
    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, s in enumerate(stats[:25]):
        rank = medals[i] if i < 3 else f"`{i + 1}.`"
        lines.append(f"{rank} **{s['name']}** · {record_line(s)} · "
                     f"{signed(s['net'])} · ROI {s['roi']:+.1f}%")
    e = discord.Embed(title="Leaderboard", description="\n".join(lines), color=BRAND)
    e.set_footer(text="Settled picks only · record is W-L(-Push)")
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
    db().execute("DELETE FROM picks WHERE id = ?", (pick_id,))
    db().commit()
    await interaction.response.send_message(
        f"Deleted pick #{pick_id} ({p['bettor_name']}: {clip(p['description'], 80)}).")


@bot.tree.command(name="export", description="Download every pick as a CSV")
@app_commands.guild_only()
async def export_cmd(interaction: discord.Interaction):
    rows = db().execute(
        "SELECT * FROM picks WHERE guild_id = ? ORDER BY id", (interaction.guild_id,)
    ).fetchall()
    if not rows:
        await interaction.response.send_message("No picks to export yet.", ephemeral=True)
        return
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Pick #", "Logged (UTC)", "Bettor", "Platform", "Sport", "Description",
                     "Legs", "Legs Hit", "Cost", "Max Payout", "Status", "Returned", "Net",
                     "Settled (UTC)", "Slip"])
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
            p["settled_at"] or "", p["slip_url"] or "",
        ])
    data = io.BytesIO(buf.getvalue().encode("utf-8-sig"))  # BOM so Excel reads it right
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
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
        "Run `/recap` any time to see this week so far.")


@bot.tree.command(name="recap", description="The last 7 days: who's up, best hit, worst beat")
@app_commands.guild_only()
async def recap_cmd(interaction: discord.Interaction):
    await interaction.response.send_message(embed=build_recap(interaction.guild_id))


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
        "`/pick` log a bet · `/leg` grade a parlay leg · `/result` settle it\n"
        "`/open` what's pending · `/record` your stats · `/leaderboard` who's up\n"
        "`/edit` `/delete` fix mistakes · `/export` download everything as a spreadsheet"))
    e.add_field(name="Slips", inline=False, value=(
        "Post a slip screenshot in the receipts channel and I'll log it. "
        "(Admins: `/receipts` in that channel.)"))
    e.add_field(name="Recaps", inline=False, value=(
        "`/recap` the last 7 days. Weekly recap and open-pick reminders post automatically "
        "once an admin runs `/recapchannel`."))
    e.add_field(name="Players", inline=False, value=(
        "`/player add` · `/player note` · `/player view` · `/player list` · `/player remove`"))
    e.add_field(name="Questions", inline=False, value=(
        "@mention me with a question about a player, team or matchup and I'll look it up."))
    await interaction.response.send_message(embed=e, ephemeral=True)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction,
                               error: app_commands.AppCommandError):
    log.exception("Command failed", exc_info=error)
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
