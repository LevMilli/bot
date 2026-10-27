"""
logger.py - writes the human-readable records:
  * Trade_Ledger.md : one table row per paper trade (opened, then settled)
  * Learning.md     : dated notes (skips, invalidations, settlements, lessons)
Files are only ever APPENDED to, never rewritten, so history can't be lost.
Dry runs never write here (bot.py checks --dry-run before calling these).
"""
import os
import json
import datetime as dt
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, "config.json")))
CT = ZoneInfo("America/Chicago")
LEDGER = os.path.join(HERE, CFG["ledger_file"])
LEARNING = os.path.join(HERE, CFG["learning_file"])

LEDGER_HEADER = """# Trade_Ledger.md - PAPER trades only (no real money)
Strategy Version 1: KXINXU 3 PM CT contract; buy at 12:30 PM CT the highest-priced side with ask 80-90c;
stake floor($25/ask); hold to settlement; taker fee = ceil-to-cent(0.07*C*P*(1-P)). Times are CT.

| Logged (CT) | Day | Action | Contract | Side | Contracts | Price | Fee | Cost | Result | P&L | Bankroll after |
|---|---|---|---|---|---|---|---|---|---|---|---|
"""

LEARNING_HEADER = """# Learning.md - what the paper bot noticed
Dated, append-only notes: skipped days and why, invalidations (contract fell under 50c),
settlements, and lessons for the next strategy review. Times are CT.

"""


def now_ct():
    return dt.datetime.now(CT).strftime("%Y-%m-%d %H:%M %Z")


def ensure_files():
    """Create both files with headers if they don't exist yet."""
    if not os.path.exists(LEDGER):
        open(LEDGER, "w").write(LEDGER_HEADER)
    if not os.path.exists(LEARNING):
        open(LEARNING, "w").write(LEARNING_HEADER)


def ledger_open(pos, bankroll_after):
    ensure_files()
    with open(LEDGER, "a") as f:
        f.write(f"| {now_ct()} | {pos['day']} | BUY (paper) | {pos['ticker']} | {pos['side'].upper()} | "
                f"{pos['contracts']} | ${pos['ask']:.2f} | ${pos['fee']:.2f} | ${pos['cost']:.2f} | open | - | ${bankroll_after:.2f} |\n")


def ledger_settle(pos, bankroll_after):
    ensure_files()
    with open(LEDGER, "a") as f:
        f.write(f"| {now_ct()} | {pos['day']} | SETTLE | {pos['ticker']} | {pos['side'].upper()} | "
                f"{pos['contracts']} | ${pos['ask']:.2f} | ${pos['fee']:.2f} | ${pos['cost']:.2f} | "
                f"{pos['status'].upper()} (market said {pos['result']}) | ${pos['pnl']:+.2f} | ${bankroll_after:.2f} |\n")


def learn(note, tag="note"):
    ensure_files()
    with open(LEARNING, "a") as f:
        f.write(f"- **{now_ct()}** [{tag}] {note}\n")


if __name__ == "__main__":
    ensure_files()
    print("logger OK:", os.path.exists(LEDGER), os.path.exists(LEARNING))
