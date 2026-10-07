"""
Picks Bot - a Discord bot that tracks a group's sports bets.

What it does
  * /pick          log a pick (Kalshi, PrizePicks, sportsbook, anything)
  * /result        settle a pick: win / loss / push / void (or reopen it)
  * /open          list picks that are still waiting on a result
  * /record        one person's record, money staked, net profit and ROI
  * /leaderboard   everyone ranked by net profit
  * /edit /delete  fix or remove a pick
  * /export        download every pick as a CSV (opens in Excel / Sheets)
  * /receipts      turn the current channel into a "receipts" channel

In a receipts channel, anyone can just post a screenshot of a slip. If an
ANTHROPIC_API_KEY is set, the bot reads the slip and logs it automatically.
Without a key, it replies with a "Log this slip" button that opens a short
form instead.

Setup is in README.md.
"""

from __future__ import annotations

import base64
import csv
import io
import json
import logging
import os
import re
import sqlite3
from datetime import datetime, timezone
from typing import Optional

import discord
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN", "")
GUILD_ID = os.getenv("GUILD_ID", "").strip()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001").strip()
DB_PATH = os.getenv("DB_PATH", "picks.db")

log = logging.getLogger("picksbot")

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
            """
        )
        _conn.commit()
    return _conn


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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


def compute_stats(guild_id: int, bettor_key: Optional[str] = None) -> list[dict]:
    """Per-bettor totals, sorted by net profit (best first)."""
    sql = "SELECT * FROM picks WHERE guild_id = ?"
    args: list = [guild_id]
    if bettor_key:
        sql += " AND bettor_key = ?"
        args.append(bettor_key)
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


def receipt_channel_ids() -> set[int]:
    return {r["channel_id"] for r in db().execute("SELECT channel_id FROM receipt_channels")}


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


def record_line(s: dict) -> str:
    rec = f"{s['wins']}-{s['losses']}"
    if s["pushes"]:
        rec += f"-{s['pushes']}"
    return rec


def pick_embed(p: sqlite3.Row) -> discord.Embed:
    label, color = STATUS[p["status"]]
    e = discord.Embed(
        title=clip(f"Pick #{p['id']} · {p['bettor_name']}", 256),
        description=clip(p["description"], 2000),
        color=color,
    )
    if p["legs"]:
        legs = "\n".join(f"• {leg}" for leg in p["legs"].splitlines() if leg.strip())
        e.add_field(name="Legs", value=clip(legs, 1024), inline=False)
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


def can_edit(interaction: discord.Interaction, p: sqlite3.Row) -> bool:
    """The bettor, whoever logged it, or a moderator."""
    if interaction.user.id in (p["logged_by"], p["bettor_id"]):
        return True
    perms = getattr(interaction.user, "guild_permissions", None)
    return bool(perms and perms.manage_messages)


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
# Reading slip screenshots (optional - needs ANTHROPIC_API_KEY)
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

_anthropic = None


def vision_enabled() -> bool:
    return bool(ANTHROPIC_API_KEY)


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
    global _anthropic
    if _anthropic is None:
        import anthropic  # imported lazily so the bot runs without it
        _anthropic = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    media_type = (attachment.content_type or "").split(";")[0].strip()
    data = base64.standard_b64encode(await attachment.read()).decode()
    reply = await _anthropic.messages.create(
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


# --------------------------------------------------------------------------
# The bot
# --------------------------------------------------------------------------

class PicksBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True  # needed to see screenshots people post
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.receipt_channels: set[int] = set()

    async def setup_hook(self):
        self.receipt_channels = receipt_channel_ids()
        self.add_dynamic_items(SettleButton, LogSlipButton)
        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)  # shows up instantly in that server
        else:
            await self.tree.sync()  # global: can take up to an hour to appear

    async def on_ready(self):
        log.info("Logged in as %s | slip reading: %s | receipts channels: %d",
                 self.user, "on" if vision_enabled() else "off (manual form)",
                 len(self.receipt_channels))

    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return
        if message.channel.id not in self.receipt_channels:
            return
        images = [a for a in message.attachments
                  if (a.content_type or "").split(";")[0].strip() in IMAGE_TYPES]
        for attachment in images[:4]:
            await self.handle_slip(message, attachment)

    async def handle_slip(self, message: discord.Message, attachment: discord.Attachment):
        slip = None
        if vision_enabled() and attachment.size <= MAX_IMAGE_BYTES:
            try:
                async with message.channel.typing():
                    slip = await read_slip(attachment)
            except Exception:
                log.exception("Could not read slip %s", attachment.url)

        # Couldn't read it (or reading is off): let the poster fill in a short form.
        if slip is None or slip["cost"] is None:
            note = "Got it. Tap below to log this slip."
            if vision_enabled():
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
        leg_text = "\n".join(part.strip() for part in legs.split(";") if part.strip())
    pick_id = insert_pick(
        guild_id=interaction.guild_id, bettor_key=key, bettor_name=name,
        bettor_id=bettor_id, logged_by=interaction.user.id, platform=platform.value,
        sport=sport, description=description, legs=leg_text, cost=cost, payout=payout,
    )
    p = get_pick(interaction.guild_id, pick_id)
    await interaction.response.send_message(embed=pick_embed(p), view=settle_view(pick_id))


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
    view = settle_view(pick_id) if p["status"] == "open" else discord.utils.MISSING
    await interaction.response.send_message(embed=pick_embed(p), view=view)


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


@bot.tree.command(name="record", description="Someone's record, profit and ROI")
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
    e = discord.Embed(title="Leaderboard", description="\n".join(lines), color=0x5865F2)
    e.set_footer(text="Settled picks only · record is W-L(-Push)")
    await interaction.response.send_message(embed=e)


@bot.tree.command(name="edit", description="Fix a pick's details")
@app_commands.guild_only()
@app_commands.describe(pick_id="The pick number", description="New one-line description",
                       cost="New amount risked", payout="New max payout",
                       legs="New legs, separated by semicolons")
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
    p = get_pick(interaction.guild_id, pick_id)
    if was_standard and ("cost" in updates or "payout" in updates):
        p = settle_pick(interaction.guild_id, pick_id, p["status"])
    view = settle_view(pick_id) if p["status"] == "open" else discord.utils.MISSING
    await interaction.response.send_message(embed=pick_embed(p), view=view)


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
                     "Legs", "Cost", "Max Payout", "Status", "Returned", "Net",
                     "Settled (UTC)", "Slip"])
    for p in rows:
        settled = p["status"] != "open"
        writer.writerow([
            p["id"], p["created_at"], p["bettor_name"], p["platform"], p["sport"] or "",
            p["description"], (p["legs"] or "").replace("\n", " | "),
            f"{p['cost']:.2f}", f"{p['payout']:.2f}", p["status"],
            f"{p['returned']:.2f}" if settled else "",
            f"{(p['returned'] or 0.0) - p['cost']:.2f}" if settled else "",
            p["settled_at"] or "", p["slip_url"] or "",
        ])
    data = io.BytesIO(buf.getvalue().encode("utf-8-sig"))  # BOM so Excel reads it right
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    await interaction.response.send_message(
        f"{len(rows)} picks.", file=discord.File(data, filename=f"picks_{stamp}.csv"))


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
               if vision_enabled() else
               "I'll reply to each screenshot with a button to log it.")
        msg = f"Slip logging is **on** for this channel. {how}"
    db().commit()
    await interaction.response.send_message(msg)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction,
                               error: app_commands.AppCommandError):
    log.exception("Command failed", exc_info=error)
    msg = "Something went wrong running that. Check the bot's console for details."
    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("DISCORD_TOKEN is missing. Copy .env.example to .env and fill it in.")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    bot.run(TOKEN, log_handler=None)
