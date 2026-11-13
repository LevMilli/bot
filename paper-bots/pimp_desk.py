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
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from zoneinfo import ZoneInfo

# bot.py loads this file via importlib without putting paper-bots/ on sys.path.
# Keep desk_profit importable in that host path (live /api/pimp-trading.json).
_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)
import desk_profit
from snapshot_schema import SCHEMA_VERSION as SNAPSHOT_SCHEMA_VERSION

log = logging.getLogger("pimpdesk")

ROOT = _ROOT_DIR
CT = ZoneInfo("America/Chicago")
CONFIRM = "RESET PAPER"
QUIET_START = "22:00"
QUIET_END = "07:00"
MANUAL_GAP_SEC = 30
HEARTBEAT_STALE_SEC = 180
# Weekday ops alert when timer has been dead longer than 10 Chicago minutes.
HEARTBEAT_WEEKDAY_ALERT_SEC = 600
IDLE_SPORTS_SEC = 900
# Forced sports AUTO near tip (T−15 / T−5). Fee floors still apply inside gap_bot.
SPORTS_TIP_FORCE_SEC = 45
SPORTS_TIP_FORCE_WINDOW_MIN = 15
# E2 #203 — manage-only pulse when memecoin has open paper (exits before bleed).
MEME_MANAGE_OPEN_SEC = 120
# E1 #110 — commodity calm cadence when ≥2 series already open.
COMMODITY_CALM_OPEN_SEC = 60
COMMODITY_CALM_OPEN_N = 2
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

# Shipped paper defaults.
# Old: edge bar 0.08 after the fee, max open positions 4, daily loss stop $50.
# Safer desk: edge bar 0.06 after the fee, max open positions 12, daily loss stop $150.
# The daily loss stop stays. A bad paper day still ends.
# A paper buy needs the edge after the fee. The hourly count does not waive it.
# Under 80%, a paper fill risks about $20. At 80% or higher, it risks $20 to $100.
PACE_MIN = 6
PACE_TARGET = 12
LEARN_MIN_SETTLES = 8
LEARN_HIT_RATE = 0.40

DEFAULTS = {
    "paper_only": True,
    "stake_hi_min": 20.0,
    "stake_hi_max": 100.0,
    "stake_hi_prob": 0.8,
    "stake_lo_max": 20.0,
    "daily_loss_stop": 150.0,
    "max_open_risk": 100.0,
    "max_open_positions": 12,
    "min_edge": 0.06,
    "pace_min": PACE_MIN,
    "pace_target": PACE_TARGET,
    "week_goal": WEEK_GOAL,
    "quiet_start": QUIET_START,
    "quiet_end": QUIET_END,
    # Desk profit six (venue edge / correlation / kelly / flip / starve / shadow).
    "venue_min_edge": {
        # Fee-aware floors — keep positive EV after fees without starving fill rate.
        "kalshi_sports": 0.06,
        "kalshi_btc15m": 0.05,
        "kalshi_commodity15m": 0.05,
        "kalshi_inx": 0.02,
        "solana_dex": 0.02,
        # Excess return after Coinbase round-trip. Locked. Shadow tower only.
        "coinbase_spot": 0.05,
        # Registry lock for the held BTC carry. Does not change kalshi_btc15m.
        "binance_btc_carry": 0.02,
        # Fed / econ binaries (FedWatch shadow). Locked. Idea-bank for main AUTO.
        "kalshi_econ": 0.05,
        # QQQ intraday shadow shares: close must clear the band by 2% of its width.
        "equity_qqq": 0.02,
    },
    "fill_adverse_tax": 0.01,
    "gate_a_min_n": 20,
    "sizing": "kelly_lite",
    "kelly_fraction": 0.25,
    "correlation_pairs": [
        ["risk_on_btc", "risk_on_equity"],
        ["risk_off_btc", "risk_off_equity"],
    ],
    "model_flip_delta": 0.06,
    "model_flip_exits": True,
    "starve_min_n": 4,
    "starve_expectancy": 0.0,
    "starve_factor": 0.15,
    "expectancy_window_days": 20,
    # Phase 1: soft per-tower share of max_open_risk (sums to 1.0). Desk cap still hard.
    "tower_risk_budgets": {
        "sports-gap": 0.35,
        "btc15m": 0.30,
        "commodity-15m": 0.15,
        "kalshi-sp": 0.08,
        "kalshi-sized": 0.07,
        "memecoin": 0.05,
    },
    "hillclimb_lever": None,  # one of desk_more.HILLCLIMB_LEVERS, or null
    "shadow": {
        "enabled": True,
        "btc15m": [{
            "id": "edge08",
            "params": {"venue_edge": 0.08},
            "promote_after": {"n": 30, "min_expectancy": 0.5},
        }],
    },
}

# Starting paper cash. Written once, on the first run, and never used to invent trades.
ACCOUNT_FILES = {
    "sports-gap": "state.json",
    "kalshi-sp": "paper_state.json",
    "btc15m": "paper_account.json",
    "commodity-15m": "paper_account.json",
    "memecoin": "positions.json",
    "kalshi-sized": "paper_state.json",
    "coinbase-spot": "paper_account.json",
    "btc-carry": "paper_account.json",
    "sports-sharp-lag": "paper_account.json",
    "fed-watch": "paper_account.json",
    "exclusive-set": "paper_account.json",
    "wall-street": "paper_account.json",
}

# Closed paper settlements and the logs that record them. These are the files a
# new image would otherwise replace with the empty copies from git. They are
# bound to the host volume at startup. A file already on that volume wins.
SETTLEMENT_FILES = (
    "sports-gap-paper/state.json",
    "sports-gap-paper/paper_trades.md",
    "btc15m-signal/paper_account.json",
    "commodity-15m-paper/paper_account.json",
    "commodity-15m-paper/index_basis.json",  # learned open offsets survive redeploys
    "kalshi-sp500-paper/paper_state.json",
    "kalshi-sp500-paper/Trade_Ledger.md",
    "kalshi-sp500-paper/Learning.md",
    "kalshi-sized-paper/paper_state.json",
    "kalshi-sized-paper/Trade_Ledger.md",
    "kalshi-sized-paper/Learning.md",
    "memecoin-paper/positions.json",
    "memecoin-paper/trades.csv",
    "memecoin-paper/checks.csv",
    "kalshi_tape.json",
    "kalshi_crypto_history.json",
    "desk_brain_journal.json",
    "desk_adapt_state.json",
    "desk_more_state.json",
    "desk_sports_clv.json",
    "desk_top25_state.json",
    "desk_maker_taker_study.json",
    "desk_phase2_state.json",
    "desk_phase3_state.json",
    "desk_adapt_ab_ledger.json",
    "btc15m-signal/paper_parlays.json",
    # Shadow evidence journals — keep promote n across image bounce.
    "desk_sports_hard_stop_shadow.json",
    "desk_commodity_time_stop_shadow.json",
    "desk_sports_time_final_shadow.json",
    "desk_helper_fills.json",
    "desk_fee_ledger.json",
    "btc15m-signal/shadow_edge08_account.json",
    "coinbase-spot-paper/paper_account.json",
    "btc-carry-paper/paper_account.json",
    "sports-sharp-lag-paper/paper_account.json",
    "fed-watch-paper/paper_account.json",
    "exclusive-set-paper/paper_account.json",
    "exclusive-set-paper/evidence.jsonl",
    "wall-street-paper/paper_account.json",
    "pimp-learning.json",
    "pimp-good.json",
    # Desk controls. Without these on the volume a redeploy clears a staff
    # pause, puts the committed limits back over the ones staff saved, drops
    # promoted shadow params, and forgets which day midnight already ran.
    "pimp-pause.json",
    "pimp-trading.json",
    "pimp-bot-params.json",
    "pimp-midnight.json",
    # Desk ops: run stats per tower per day and the ops checks' memory (desk_ops).
    "pimp-run-stats.json",
    "pimp-ops.json",
    "pimp-audit.json",
    "pimp-runs.json",
    # Lifetime record. Books cleared by the midnight refill or a staff reset
    # keep their closed P/L here, so a lost bankroll still counts.
    "pimp-lifetime.json",
)

# Fixed commands. Nothing from the request is concatenated onto these.
ACTIONS = {
    "sports-gap": {
        # 120s: ESPN + sports tape (capped) + gap scan; 75s was killing tape sync.
        "run": {"argv": ("gap_bot.py",), "entry": True, "timeout": 120, "label": "Run one check"},
    },
    "kalshi-sp": {
        "run": {"argv": ("bot.py", "scan"), "entry": True, "timeout": 75, "label": "Run one check"},
        "settle": {"argv": ("bot.py", "settle"), "entry": False, "timeout": 75, "label": "Settle paper"},
        "brief": {"argv": ("bot.py", "brief", "--dry-run"), "entry": False, "timeout": 75, "label": "Morning brief"},
    },
    "kalshi-sized": {
        "run": {"argv": ("bot.py", "scan"), "entry": True, "timeout": 75, "label": "Run one check"},
        "settle": {"argv": ("bot.py", "settle"), "entry": False, "timeout": 75, "label": "Settle paper"},
        "brief": {"argv": ("bot.py", "brief", "--dry-run"), "entry": False, "timeout": 75, "label": "Morning brief"},
    },
    "btc15m": {
        # entry:True — ROI system: desk daily loss / max open / open risk gate paper buys.
        # Timeout 150s: BTC+ETH 15m + KXBTCD history + tape + optional ≤5m parlay.
        "run": {"argv": ("btc15m_signal.py",), "entry": True, "timeout": 150, "label": "Run one check"},
    },
    "commodity-15m": {
        # Metals/energy 15m paper tower — family tape + settle harness + adapt sizing.
        "run": {"argv": ("bot.py",), "entry": True, "timeout": 150, "label": "Run one check"},
    },
    "memecoin": {
        "run": {"argv": ("bot.py",), "entry": True, "timeout": 120, "label": "Run one check"},
    },
    "coinbase-spot": {
        # Shadow sleeve. Public candles only. Entry gate still blocks new buys.
        "run": {"argv": ("bot.py",), "entry": True, "timeout": 45, "label": "Run one check"},
    },
    "btc-carry": {
        # Shadow sleeve. Public funding archive only. Entry gate blocks a new open.
        "run": {"argv": ("bot.py",), "entry": True, "timeout": 60, "label": "Run one check"},
    },
    "sports-sharp-lag": {
        # Shadow sleeve. Sharp fair vs Kalshi ask. Sports floor 0.06 locked.
        "run": {"argv": ("bot.py",), "entry": True, "timeout": 45, "label": "Run one check"},
    },
    "fed-watch": {
        # Shadow sleeve. CME FedWatch fair vs Kalshi ask. Econ floor 0.05. Idea-bank.
        "run": {"argv": ("bot.py",), "entry": True, "timeout": 45, "label": "Run one check"},
    },
    "exclusive-set": {
        # Shadow logger. Public books only. The script logs and does not buy.
        "run": {"argv": ("bot.py",), "entry": False, "timeout": 75, "label": "Run one check"},
    },
    "wall-street": {
        # Display floor. The script skips. It is not on the timer.
        "run": {"argv": ("bot.py",), "entry": False, "timeout": 15, "label": "Show the floor"},
    },
}

# One automatic pass. Intervals are seconds. Clock times are America/Chicago.
# Daily clock slots: INX run windows retry on NO TRADE (see _remember) so fair/band
# can clear later in-window — max 1 fill/day stays stone in the bots. The Kalshi
# scan uses the desk's paper scan (no --any-time). Forced S&P scans at
# 12:05 / 13:05 / 13:40 CT (up to 3/day) — third slot ends by 14:00 so it still
# clears the stone 60m late-σ entry floor before 15:00 settle (old 14:20 slot was
# always refuse). Morning brief stays dry run. Settle polls flip/exit; 4 PM lands
# closed paper. Memecoin manages exits ~3m (still scans; dual lanes; stop-bleed).
AUTO_RETRY_SEC = 900
AUTO = (
    # Faster sports polls so tip-soon + dual lanes can land multiple fills.
    {"id": "sports-gap", "action": "run", "every_sec": 180},
    # BTC is the busiest Kalshi series — poll every 60s; guidelines unchanged, bid every fit.
    {"id": "btc15m", "action": "run", "every_sec": 60},
    {"id": "commodity-15m", "action": "run", "every_sec": 90},
    # Faster manage ticks so −18% / model-flip stops fire before a full bleed.
    {"id": "memecoin", "action": "run", "every_sec": 180},
    # Shadow research cadence. Does not spend desk cash. Fee floor stays 0.05.
    {"id": "coinbase-spot", "action": "run", "every_sec": 300},
    # Held carry. Funding prints every 8h. The check does not flip the month.
    {"id": "btc-carry", "action": "run", "every_sec": 300},
    # Sharp→Kalshi lag research. Shadow only. Floor stays sports 0.06.
    {"id": "sports-sharp-lag", "action": "run", "every_sec": 300},
    # FedWatch→Kalshi relative value. Shadow + idea-bank. Floor stays econ 0.05.
    {"id": "fed-watch", "action": "run", "every_sec": 300},
    # Exclusive-set logger. Shadow only. No stake. Sports 0.06 / other Kalshi 0.05.
    {"id": "exclusive-set", "action": "run", "every_sec": 300},
    {"id": "kalshi-sp", "action": "brief", "at_ct": "08:00", "until_ct": "11:59"},
    # Forced INX scan slots (plan E1 #123) — up to 3 fee-aware scans / Chicago day.
    # Third window ends ≤14:00 CT so late-σ 60m floor can still clear (15:00 settle).
    {"id": "kalshi-sp", "action": "run", "at_ct": "12:05", "until_ct": "12:25"},
    {"id": "kalshi-sp", "action": "run", "at_ct": "13:05", "until_ct": "13:25"},
    {"id": "kalshi-sp", "action": "run", "at_ct": "13:40", "until_ct": "14:00"},
    # Model-flip / settle polls before 15:00 CT binary settle (mirror sized).
    {"id": "kalshi-sp", "action": "settle", "at_ct": "13:00", "until_ct": "15:55"},
    {"id": "kalshi-sp", "action": "settle", "at_ct": "16:00", "until_ct": "23:30"},
    {"id": "kalshi-sized", "action": "run", "at_ct": "12:05", "until_ct": "14:55"},
    # Model-flip / settle polls — offset from the scan window so one bot never double-locks.
    {"id": "kalshi-sized", "action": "settle", "at_ct": "13:00", "until_ct": "15:55"},
    {"id": "kalshi-sized", "action": "settle", "at_ct": "16:05", "until_ct": "23:30"},
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
        "blurb": "BTC 15-minute paper account. A timer check can paper-buy. It places nothing.",
        "state": "paper_account.json",
        "kind": "btc",
        "log": "",
        "empty": "No paper account yet. A check writes paper_account.json.",
    },
    {
        "id": "commodity-15m",
        "name": "Commodity 15m",
        "folder": "commodity-15m-paper",
        "script": "bot.py",
        "blurb": "Palladium/NatGas/Copper/Brent/WTI/Silver/Gold/Platinum 15m paper tower. Same adapt gates as BTC.",
        "state": "paper_account.json",
        "kind": "btc",
        "log": "",
        "empty": "No paper account yet. A check writes paper_account.json.",
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
    {
        "id": "kalshi-sized",
        "name": "Sized Kalshi",
        "folder": "kalshi-sized-paper",
        "script": "bot.py",
        "blurb": "KXINXU paper bot with desk Kelly-lite stake (80–92¢ band). Own bankroll; model-flip + settle.",
        "state": "paper_state.json",
        "kind": "kalshi",
        "log": "Trade_Ledger.md",
        "empty": "No paper_state.json yet. A scan inside the bot's window writes one.",
    },
    {
        "id": "coinbase-spot",
        "name": "Coinbase spot",
        "folder": "coinbase-spot-paper",
        "script": "bot.py",
        "blurb": (
            "Shadow Coinbase spot paper tower. Public candles only. "
            "Longs only when excess return clears the locked 0.05 floor after taker fees. "
            "Spends no desk cash."
        ),
        "state": "paper_account.json",
        "kind": "spot",
        "log": "",
        "empty": "No paper account yet. A check writes paper_account.json.",
        "shadow_only": True,
    },
    {
        "id": "btc-carry",
        "name": "BTC carry",
        "folder": "btc-carry-paper",
        "script": "bot.py",
        "blurb": (
            "Shadow BTC spot-long / perpetual-short carry. Public archive only. "
            "Unlevered and held. A red month is a mark, not a flip. "
            "Spends no desk cash."
        ),
        "state": "paper_account.json",
        "kind": "carry",
        "log": "",
        "empty": "No paper account yet. A check writes paper_account.json.",
        "shadow_only": True,
    },
    {
        "id": "sports-sharp-lag",
        "name": "Sports Sharp Lag",
        "folder": "sports-sharp-lag-paper",
        "script": "bot.py",
        "blurb": (
            "Shadow sharp-book fair vs Kalshi ask lag. "
            "Buys only when lag edge after fee clears sports floor 0.06. "
            "Spends no desk cash."
        ),
        "state": "paper_account.json",
        "kind": "sports",
        "log": "",
        "empty": "No paper account yet. A check writes paper_account.json.",
        "shadow_only": True,
    },
    {
        "id": "fed-watch",
        "name": "Fed Watch",
        "folder": "fed-watch-paper",
        "script": "bot.py",
        "blurb": (
            "Shadow CME FedWatch fair vs Kalshi Fed ask. "
            "Buys only when edge after fee clears econ floor 0.05. "
            "Idea-bank for main AUTO. Spends no desk cash."
        ),
        "state": "paper_account.json",
        "kind": "macro",
        "log": "",
        "empty": "No paper account yet. A check writes paper_account.json.",
        "shadow_only": True,
    },
    {
        "id": "exclusive-set",
        "name": "Exclusive set",
        "folder": "exclusive-set-paper",
        "script": "bot.py",
        "blurb": (
            "Shadow logger for one Kalshi exclusive set. "
            "Interesting only when ask plus taker fee clears 0.06 on a sports set "
            "and 0.05 on any other Kalshi set. Does not use the 0.02 INX floor. "
            "Does not trade KXINXU. Buys nothing and takes no stake."
        ),
        "state": "paper_account.json",
        "kind": "log",
        "log": "",
        "empty": "No paper account yet. A check writes paper_account.json.",
        "shadow_only": True,
    },
    {
        "id": "wall-street",
        "name": "Wall Street",
        "folder": "wall-street-paper",
        "script": "bot.py",
        "blurb": (
            "One paper floor. Six desks, 120 staff, one book. "
            "The desks do not buy and spend no desk cash."
        ),
        "state": "paper_account.json",
        "kind": "floor",
        "log": "",
        "traders": 120,
        "departments": (
            {"id": "quote", "name": "Quote", "seats": 20, "job": "No client flow arrives, so this desk does not quote."},
            {"id": "research", "name": "Research", "seats": 20, "job": "Writes the skip in one sentence a person can check."},
            {"id": "risk", "name": "Risk", "seats": 20, "job": "Holds the veto. A buy on this floor is a mistake."},
            {"id": "ledger", "name": "Ledger", "seats": 20, "job": "Cash stays at 0 and the position list stays empty."},
            {"id": "control", "name": "Control", "seats": 20, "job": "Paper only. Keeps a key off this floor."},
            {"id": "book", "name": "The book", "seats": 20, "job": "The only book on the floor, and it stays flat."},
        ),
        "empty": "No paper account yet. A check writes paper_account.json.",
        "shadow_only": True,
    },
)

# Normalized buy / sell / failsafe copy for snapshot consumers (city + staff).
# Keep thresholds in sync with each bot script and desk DEFAULTS.
BOT_PLANS = {
    "sports-gap": {
        "buy": [
            "Live or tip-soon (≤180m) ESPN game matched to a Kalshi series",
            "Dual lanes: accurate fair ≥80% OR speed fair ≥72% with +2¢ edge",
            "Up to 4 paper buys per check; home fair outside 0.40–0.60 close band",
            "Spread ≤ 0.05; ask in 0.05–0.95",
            "Kelly-lite / desk stake; correlation + learning clear",
            "Adapt: safe on high vol; bigger only if ≥80% hit with enough settles",
        ],
        "sell": [
            "Hard-stop shadow: bid ≤ entry − 12¢ logged (live sell off until n≥30 promote)",
            "Model-flip: fair moves against side by desk δ → sell at bid",
            "Gap closed: bid − fee ≥ fair → sell at bid",
            "Game final → settle $1 / $0 (ties wait)",
        ],
        "failsafes": [
            "Desk entry_gate (daily loss / max open / open risk)",
            "Bot daily loss stop (desk daily_loss_stop)",
            "Intra-check max open risk + max open / cash / learning skip",
            "Correlation veto + expectancy starve multiplier",
            "Sells/settles before new paper buys each check",
            "Pause file",
        ],
        "exit_quality": "partial",
        "entry_gated": True,
        "stake": "kelly-lite",
    },
    "kalshi-sp": {
        "buy": [
            "Up to 3 scans/day 12:00–14:00 CT",
            "Safest YES/NO ask in the 80–92¢ band; venue kalshi_inx edge",
            "Stake floor($25 / ask); correlation + learning clear",
            "Adapt layer still logs vol/performance for desk study",
            "Pre-FOMC calm after 12:00 CT day before; post-print +30m on macro days",
        ],
        "sell": [
            "Model-flip: bid under 50¢ → paper sell at bid when enabled",
            "Else hold to 3 PM CT Kalshi settlement",
        ],
        "failsafes": [
            "Desk entry_gate on scan (not settle/brief)",
            "Weekend + news/holiday calendar",
            "Max 3 trades/day; bot daily loss −$50",
            "Kill switch bankroll ≤ $400; paper_mode required",
            "Correlation veto + starve; pause file",
        ],
        "exit_quality": "partial",
        "entry_gated": True,
        "stake": "fixed-25",
    },
    "btc15m": {
        "buy": [
            "Track KXBTC15M + KXETH15M + KXBTCD ladder history each check",
            "Confident early (≥10m): BTC + ETH singles under the same fee-aware gates",
            "Volatile: hold + history; ≤5m fee-aware paper parlay (BTC+ETH legs)",
            "p ≥ ask + fee + venue kalshi_btc15m; model p ≥ 80%; brain journal",
            "BTC cushion ≥ $35 / ETH ≥ $1.50; z ≥ 0.60; ask 70–92¢; dual lane",
            "Kelly-lite stake; correlation + learning clear; desk open-risk cap",
            "Adapt: recognize vol → play safe; proven ≥80% record → play bigger",
            "History sweep: metals/energy 15m (palladium, natgas, copper, brent, WTI, silver…)",
        ],
        "sell": [
            "Take-profit: paper-sell when bid ≥ fill + 0.15 (cap 0.99)",
            "Model-flip: side flips or fair collapses by δ → paper sell at bid",
            "Else settle when Kalshi resolves yes/no",
        ],
        "failsafes": [
            "Desk entry_gate (daily loss / max open / open risk)",
            "Full signal checklist (no spot/σ → skip)",
            "News calendar fail-closed (unavailable = skip BUY)",
            "Correlation veto + starve; cash / max 12 opens / learning",
            "Pause file",
        ],
        "exit_quality": "partial",
        "entry_gated": True,
        "stake": "kelly-lite",
    },
    "commodity-15m": {
        "buy": [
            "Open KX*15M metals/energy windows (Pd/NatGas/Cu/Brent/WTI/Ag/Au/Pt)",
            "Spot vs floor_strike; side YES if above else NO",
            "p ≥ ask + fee + venue kalshi_commodity15m; model p ≥ 80%",
            "Cushion/σ gate; ask 70–92¢; ≥8m for early single (else skip)",
            "Kelly-lite + adapt: safe on high/false-conf vol; Wilson CI ≥70% for play-big",
            "Max 1 energy + 1 metal; EIA/inventory blackout on NatGas/Oil",
        ],
        "sell": [
            "Model-flip when side/fair moves against entry (before settle)",
            "Settle when Kalshi resolves yes/no (history settle harness labels windows)",
        ],
        "failsafes": [
            "Desk entry_gate (daily loss / max open / open risk)",
            "No spot / no σ → skip",
            "EIA/inventory ±45m blackout for energy series",
            "Commodity tape family budget; correlation + starve; pause file",
        ],
        "exit_quality": "partial",
        "entry_gated": True,
        "stake": "kelly-lite",
    },
    "memecoin": {
        "buy": [
            "RugCheck facts fail-closed; accurate conf ≥80% or speed ≥72%",
            "Entries refused until taxed EV ≥ 0 — conf−0.5 is not a fee-aware edge",
            "Buy-in $10 at 80% and speed, $17.50 at 85%, $25 at 90%+. Red ceiling $10. Today ≤ −$5 → entries off",
            "Max 6 open on a green day, 1 if today < 0; 8 entries/day; 12h cooldown",
            "Midnight cash reload does not waive the refuse. No size-up. expand_volume stays false",
        ],
        "sell": [
            "Model-flip: price ≤ −6% from entry → out before the hard stop",
            "Liq drop ≥ 35% from entry → full out",
            "Hard stop ≤ −12% from entry → full out",
            "Trail 25% off peak after first ladder; time stop ≥4h and < +20% → out",
            "Ladder +100% sell 50%, +200% sell 25% of original",
        ],
        "failsafes": [
            "Desk entry_gate + pause",
            "Bot daily halt −$150; PAPER must be True",
            "Red lock today ≤ −$5; max open 6 green / 1 red; 12h cooldown",
            "Facts fail-closed; starved while taxed EV < 0; DEX floor 0.02 stays",
        ],
        "exit_quality": "strong",
        "entry_gated": True,
        "stake": "$10–$25",
    },
    "kalshi-sized": {
        "buy": [
            "KXINXU 3 PM CT; S&P forced scans 12:05 / 13:05 / 13:40 CT; sized window retries on NO TRADE",
            "Ask band 80–92¢; order-book confirm",
            "Desk Kelly-lite stake (not fixed $25); venue kalshi_inx edge",
            "Anti-double vs kalshi-sp same ticker; residual edge ≥ venue + 1¢",
            "Correlation veto vs BTC / fixed Kalshi; learning skip clear",
            "Adapt: safe on high vol; bigger only on proven ≥80% record",
            "Pre-FOMC calm / post-print +30m macro gates",
        ],
        "sell": [
            "Model-flip: side bid collapses under 50¢ → paper sell",
            "Else settle when Kalshi resolves yes/no",
        ],
        "failsafes": [
            "Desk entry_gate (daily loss / max open / open risk)",
            "News calendar + kill switch / 1 trade/day / daily loss $50",
            "Correlation + starve; paper_mode required",
            "Pause file",
        ],
        "exit_quality": "partial",
        "entry_gated": True,
        "stake": "kelly-lite",
    },
    "coinbase-spot": {
        "buy": [
            "Shadow sleeve only — spends no desk cash and takes no tower risk share",
            "ETH-USD and SOL-USD longs; BTC-USD is research-only (btc15m owns that factor)",
            "Public Coinbase 15m candles; no API key",
            "Edge = 25% of the last 15m move minus round-trip US intro taker 0.90% + 0.10% slip each side",
            "Buy only if z ≥ 2 and edge ≥ locked coinbase_spot 0.05",
            "Skip when btc15m holds YES; spot cash book does not short",
            "Fixed $25 ticket from the shadow $500 sleeve; max 1 open",
        ],
        "sell": [
            "Stop at −1.5% from entry",
            "Take-profit when price move covers round-trip plus the 0.05 floor",
            "Model-flip when z ≤ −2 against the long",
            "Time stop at 24h",
        ],
        "failsafes": [
            "Desk entry_gate still blocks new buys",
            "Floor cannot be lowered; haircut cannot be raised above 0.25; taker cannot be cut below 0.90%",
            "Learning skip after 8 settles under 40% hits",
            "Incubation: 50 fee-aware settles before any staff graduate; no auto-promote",
            "Pause file; a Coinbase key in the environment refuses the check",
        ],
        "exit_quality": "partial",
        "entry_gated": True,
        "stake": "fixed-25",
    },
    "wall-street": {
        "buy": [
            "The floor does not buy. Six desks and 120 staff share one book, not 120 strategies",
            "Shadow display only — spends no desk cash and takes no tower risk share",
            "A check always skips",
        ],
        "sell": [
            "Nothing is open, so there is nothing to sell",
            "A position found on this book is a mistake and stays unfilled",
        ],
        "failsafes": [
            "Paper only. No key, no wallet, no desk cash",
            "Not on the auto timer",
            "Pause file",
        ],
        "exit_quality": "partial",
        "entry_gated": True,
        "stake": "none",
    },
    "sports-sharp-lag": {
        "buy": [
            "Shadow sleeve only — spends no desk cash and takes no tower risk share",
            "Pinnacle no-vig fair (The Odds API, ODDS_API_KEY) vs Kalshi ask, pre-game only",
            "Edge = sharp_fair − ask − Kalshi fee; buy only if edge ≥ locked sports 0.06",
            "Fixed $25 ticket in whole contracts from the shadow $500 sleeve; max 1 open",
            "No key or no matched game → waits; never invent fills",
        ],
        "sell": [
            "Holds to the Kalshi result: $1 per contract on YES",
            "Model-flip when sharp fair collapses through the ask",
        ],
        "failsafes": [
            "Desk entry_gate still blocks new buys",
            "Sports floor 0.06 cannot be lowered",
            "Incubation: 50 fee-aware settles before any staff graduate; no auto-promote",
            "No tower_risk_budgets share while shadow_only",
        ],
        "exit_quality": "partial",
        "entry_gated": True,
        "stake": "fixed-25",
    },
    "fed-watch": {
        "buy": [
            "Shadow sleeve only — spends no desk cash and takes no tower risk share",
            "Polymarket Fed decision mid vs Kalshi KXFEDDECISION YES/NO ask, same meeting and outcome",
            "Edge = Polymarket fair − Kalshi ask − Kalshi fee; buy only if edge ≥ locked econ 0.05",
            "Fixed $25 ticket in whole contracts from the shadow $500 sleeve; max 1 open",
            "Polymarket spread over 4¢ or no matching meeting → skip; never invent fills",
            "Idea-bank: KXFED/rates refuse main AUTO graduation",
        ],
        "sell": [
            "Holds to the Kalshi result: $1 per contract when our side wins",
            "Model-flip when the Polymarket fair collapses through the ask",
        ],
        "failsafes": [
            "Desk entry_gate still blocks new buys",
            "Econ floor 0.05 cannot be lowered",
            "Incubation idea-bank only — staff graduate to main AUTO refused",
            "No tower_risk_budgets share while shadow_only",
        ],
        "exit_quality": "partial",
        "entry_gated": True,
        "stake": "fixed-25",
    },
    "exclusive-set": {
        "buy": [
            "The tower does not buy. It logs a mutually exclusive Kalshi set and leaves the book flat",
            "Shadow only — spends no desk cash and takes no tower risk share",
            "Interesting only when the sum of public ask plus taker fee is below $1 by the floor",
            "Sports set floor 0.06. Any other Kalshi set floor 0.05. The INX 0.02 floor is not used",
            "KXINXU is refused. One-sided books are skipped. Observe examples are not evidence",
            "Stake stays 0",
        ],
        "sell": [
            "Nothing is open, so there is nothing to sell",
            "A logged basket is not a position. Staff review is the backstop",
        ],
        "failsafes": [
            "Paper only. No key and no desk cash",
            "Stake stays 0. No tower_risk_budgets share while shadow_only",
            "Sports floor 0.06 and the other-set floor 0.05 cannot be lowered",
            "dutch_book_observe examples do not count as evidence",
            "Incubation n≥50 before any desk share. This build does not buy",
            "Pause file",
        ],
        "exit_quality": "partial",
        "entry_gated": True,
        "stake": "none",
    },
    "btc-carry": {
        "buy": [
            "Shadow sleeve only — spends no desk cash and takes no tower risk share",
            "Long BTC spot and short the BTC perpetual, same notional, leverage 1",
            "Public Binance archive funding and 8h premium index; no key",
            "Spot taker 0.10% and perp taker 0.05%. Round trip 0.30%, paid once to open",
            "Open only when both marks exist. Then hold. Do not flip the month",
        ],
        "sell": [
            "A red funding month is marked and is not a close",
            "Flipping every month is refused. That path pays the 0.30% round trip every month",
            "The sleeve does not add a second leg after a red month",
            "Staff close is the backstop. Nothing here auto-promotes",
        ],
        "failsafes": [
            "Desk entry gate blocks a new open. An open hold still marks",
            "Spot taker stays 0.10% and perp taker stays 0.05%. The Coinbase 0.90% taker is not used",
            "kalshi_btc15m 0.05 is not this book and is not lowered",
            "Leverage above 1 is put back to 1. Notional stays the $500 sleeve",
            "Pass bar: after-fee monthly median stays positive. A monthly flip is a reject",
            "Pause file. A Binance key in the environment refuses the check",
        ],
        "exit_quality": "partial",
        "entry_gated": True,
        "stake": "sleeve-500",
    },
}


def bot_plans(bot_id: str, cfg: dict | None = None) -> dict:
    """Stable plan block for one bot id. Optional cfg annotates live desk thresholds."""
    base = BOT_PLANS.get(bot_id) or {
        "buy": [],
        "sell": [],
        "failsafes": [],
        "exit_quality": "none",
        "entry_gated": False,
        "stake": "unknown",
    }
    plans = {
        "buy": list(base["buy"]),
        "sell": list(base["sell"]),
        "failsafes": list(base["failsafes"]),
        "exit_quality": base["exit_quality"],
        "entry_gated": bool(base["entry_gated"]),
        "stake": base["stake"],
    }
    if cfg and bot_id == "sports-gap":
        edge = desk_profit.bot_venue_edge("sports-gap", cfg)
        plans["buy"] = [
            line.replace(
                "venue kalshi_sports (NHL +0.02)",
                f"venue kalshi_sports {edge:g} (NHL +0.02)",
            )
            if "venue kalshi_sports" in line else line
            for line in plans["buy"]
        ]
        loss = cfg.get("daily_loss_stop", DEFAULTS["daily_loss_stop"])
        plans["failsafes"] = [
            line.replace("desk daily_loss_stop", f"${float(loss):.0f} desk daily_loss_stop")
            if "desk daily_loss_stop" in line else line
            for line in plans["failsafes"]
        ]
    if cfg and bot_id in ("sports-gap", "btc15m"):
        mode = str(cfg.get("sizing") or DEFAULTS["sizing"])
        plans["stake"] = "kelly-lite" if mode == "kelly_lite" else "desk-curve"
    return plans


def bot_gates_hit(view: dict, desk_gate: str = "") -> list:
    """Live gate labels for this bot row (not invented fills)."""
    hits = []
    if view.get("present") is False:
        hits.append("absent")
    if view.get("paused"):
        hits.append("paused")
    if view.get("read_error"):
        hits.append("state read error")
    if (view.get("last_run") or {}).get("blocked"):
        hits.append("run blocked")
    skip = str(view.get("skip") or "")
    # A carry HOLD is the trade. The skip chip is for a check that bought nothing.
    low = skip.lower()
    if skip and "signal: hold" not in low and not low.startswith("holding unlevered"):
        hits.append("skip")
    plans = view.get("plans") or {}
    if desk_gate and plans.get("entry_gated"):
        hits.append("desk entry gate")
    if view.get("starved"):
        hits.append("starved")
    if view.get("correlation_blocked"):
        hits.append("correlation veto")
    return hits


# Desk-wide ROI operating system. Paper only — protects bankroll and edge habits.
ROI_POLICY = {
    "name": "desk-roi-system",
    "version": 2,
    "paper_only": True,
    "banner": (
        "ROI SYSTEM (paper). Prefer ≥80% model/confidence entries, venue edge after costs, "
        "Kelly-lite inside open-risk, correlation veto, model-flip exits, expectancy starve. "
        "Pace never waives edge."
    ),
    "rules": [
        {"id": "R1", "text": "Paper only — no live keys, wallets, or real orders."},
        {"id": "R2", "text": "Edge after fees/slippage must clear the venue (or desk) bar."},
        {"id": "R3", "text": "Desk entry_gate blocks new entries on daily loss / max opens / open risk."},
        {"id": "R4", "text": "Stake from Kelly-lite (capped by curve + open risk) unless a fixed ticket applies."},
        {"id": "R5", "text": "Exit plan exists before entry (model-flip and/or stop/trail/time/liq/settle)."},
        {"id": "R6", "text": "Learning skip on cold market×bucket (≥8 settles, <40% hits)."},
        {"id": "R7", "text": "Pause file is honored."},
        {"id": "R8", "text": "Quiet hours hold alerts only — not a trade halt."},
        {"id": "R9", "text": "Pace never waives edge."},
        {"id": "R10", "text": "One position key — no duplicate game/ticker/mint."},
        {"id": "R11", "text": "City/staff read snapshot only — never re-parse bot files."},
        {"id": "R12", "text": "Tower 5 is Sized Kalshi (Kelly-lite KXINXU) when present — no fake substitute."},
        {"id": "R13", "text": "Correlation veto — paired directional factors cannot stack when the open book is as good or better."},
        {"id": "R14", "text": "Fee-aware venue_min_edge per book (sports/BTC/INX/DEX/Coinbase spot)."},
        {"id": "R15", "text": "Model-flip exits fire before hard stops / settle-only waits."},
        {"id": "R16", "text": "Expectancy starve throttles losers after enough settles."},
        {"id": "R17", "text": "Shadow bots spend no desk cash; promote only after expectancy gates."},
        {"id": "R18", "text": "Midnight (CT) does not refill cash or clear P&L. Traded numbers stay on the book."},
    ],
    "risk": {
        "daily_loss_stop": DEFAULTS["daily_loss_stop"],
        "max_open_positions": DEFAULTS["max_open_positions"],
        "max_open_risk": DEFAULTS["max_open_risk"],
        "min_edge": DEFAULTS["min_edge"],
        "venue_min_edge": dict(DEFAULTS["venue_min_edge"]),
        "sizing": DEFAULTS["sizing"],
        "kelly_fraction": DEFAULTS["kelly_fraction"],
        "correlation_pairs": [list(p) for p in DEFAULTS["correlation_pairs"]],
        "model_flip_delta": DEFAULTS["model_flip_delta"],
        "starve_min_n": DEFAULTS["starve_min_n"],
        "starve_expectancy": DEFAULTS["starve_expectancy"],
        "starve_factor": DEFAULTS["starve_factor"],
        "stake_lo_max": DEFAULTS["stake_lo_max"],
        "stake_hi_min": DEFAULTS["stake_hi_min"],
        "stake_hi_max": DEFAULTS["stake_hi_max"],
        "stake_hi_prob": DEFAULTS["stake_hi_prob"],
        "learn_min_settles": LEARN_MIN_SETTLES,
        "learn_hit_rate": LEARN_HIT_RATE,
    },
    "exit_ladder": {
        "strong": "Active stop + scale-out + trail/time/liq",
        "partial": "Model-flip / gap-close path + settle",
        "weak": "Settle-only with hard entry filters",
        "absent": "No script on this checkout",
    },
    "waivers": {
        "kalshi-sp": ["fixed_ticket_25"],
        "btc15m": [],
        "memecoin": ["fixed_ticket_25"],
        "coinbase-spot": ["fixed_ticket_25", "shadow_only"],
        "btc-carry": ["shadow_only"],
        "sports-sharp-lag": ["fixed_ticket_25", "shadow_only"],
        "fed-watch": ["fixed_ticket_25", "shadow_only"],
        "exclusive-set": ["shadow_only"],
        "wall-street": ["shadow_only"],
    },
    "target_exit_quality": {
        "sports-gap": "partial",
        "kalshi-sp": "partial",
        "btc15m": "partial",
        "memecoin": "strong",
        "kalshi-sized": "partial",
        "coinbase-spot": "partial",
        "btc-carry": "partial",
        "sports-sharp-lag": "partial",
        "fed-watch": "partial",
        "exclusive-set": "partial",
        "wall-street": "partial",
    },
}


def bot_roi_compliance(bot_id: str, plans: dict | None = None) -> dict:
    """Grade one bot against ROI_POLICY targets (structural, not live P&L)."""
    plans = plans or bot_plans(bot_id)
    target = (ROI_POLICY.get("target_exit_quality") or {}).get(bot_id, "partial")
    quality = plans.get("exit_quality") or "none"
    order = {"strong": 3, "partial": 2, "weak": 1, "absent": 0, "none": -1}
    ok_exit = order.get(quality, -1) >= order.get(target, 2)
    entry_ok = bool(plans.get("entry_gated"))
    # Legacy absent checkout: still compliant if placeholder-only.
    if bot_id == "kalshi-sized" and quality == "absent":
        entry_ok = True
        ok_exit = True
    has_buy = bool(plans.get("buy"))
    has_sell = bool(plans.get("sell"))
    has_fail = bool(plans.get("failsafes"))
    waivers = list((ROI_POLICY.get("waivers") or {}).get(bot_id) or [])
    ok = ok_exit and entry_ok and has_buy and has_sell and has_fail
    return {
        "bot": bot_id,
        "ok": ok,
        "exit_quality": quality,
        "target_exit_quality": target,
        "entry_gated": bool(plans.get("entry_gated")),
        "waivers": waivers,
        "gaps": [
            *([] if ok_exit else [f"exit_quality {quality} below target {target}"]),
            *([] if entry_ok else ["entry_gated required by ROI system"]),
            *([] if has_buy else ["missing buy plan"]),
            *([] if has_sell else ["missing sell plan"]),
            *([] if has_fail else ["missing failsafes"]),
        ],
    }


def roi_system(cfg: dict | None = None, bots: list | None = None) -> dict:
    """Public ROI system block for snapshot consumers."""
    cfg = cfg or DEFAULTS
    risk = dict(ROI_POLICY["risk"])
    risk.update({
        "daily_loss_stop": cfg.get("daily_loss_stop", risk["daily_loss_stop"]),
        "max_open_positions": cfg.get("max_open_positions", risk["max_open_positions"]),
        "max_open_risk": cfg.get("max_open_risk", risk["max_open_risk"]),
        "min_edge": cfg.get("min_edge", risk["min_edge"]),
        "venue_min_edge": dict(cfg.get("venue_min_edge") or risk.get("venue_min_edge") or {}),
        "sizing": cfg.get("sizing", risk.get("sizing")),
        "kelly_fraction": cfg.get("kelly_fraction", risk.get("kelly_fraction")),
        "correlation_pairs": list(cfg.get("correlation_pairs") or risk.get("correlation_pairs") or []),
        "model_flip_delta": cfg.get("model_flip_delta", risk.get("model_flip_delta")),
        "starve_min_n": cfg.get("starve_min_n", risk.get("starve_min_n")),
        "starve_expectancy": cfg.get("starve_expectancy", risk.get("starve_expectancy")),
        "starve_factor": cfg.get("starve_factor", risk.get("starve_factor")),
        "stake_lo_max": cfg.get("stake_lo_max", risk["stake_lo_max"]),
        "stake_hi_min": cfg.get("stake_hi_min", risk["stake_hi_min"]),
        "stake_hi_max": cfg.get("stake_hi_max", risk["stake_hi_max"]),
    })
    compliance = []
    for bot_id in list(BOT_PLANS.keys()):
        plans = None
        if bots:
            row = next((b for b in bots if b.get("id") == bot_id), None)
            if row:
                plans = row.get("plans")
        compliance.append(bot_roi_compliance(bot_id, plans))
    capital = desk_profit.capital_weights(bots or [])
    return {
        "name": ROI_POLICY["name"],
        "version": ROI_POLICY["version"],
        "paper_only": True,
        "banner": ROI_POLICY["banner"],
        "rules": list(ROI_POLICY["rules"]),
        "risk": risk,
        "exit_ladder": dict(ROI_POLICY["exit_ladder"]),
        "waivers": {k: list(v) for k, v in (ROI_POLICY.get("waivers") or {}).items()},
        "compliance": compliance,
        "capital": capital,
        "ok": all(row.get("ok") for row in compliance),
    }


_LOCKS: dict[str, threading.Lock] = {}
_FILE_LOCK = threading.RLock()
# realpath(desk root) -> realpath(volume directory) once settlements are bound.
_BOUND_DURABLE: dict[str, str] = {}
_BUSY = "A check is already running for this bot."
_HHMM = re.compile(r"^(\d{2}):(\d{2})$")
_ENV_KEEP = {
    "PATH", "HOME", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "TMPDIR", "TEMP", "TMP",
    "USER", "LOGNAME", "SYSTEMROOT", "WINDIR", "PATHEXT", "PYTHONPATH", "PYTHONHOME",
    "VIRTUAL_ENV", "PYTHONUTF8", "SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE",
    "CURL_CA_BUNDLE",
    # Tower feed settings. Desk secrets (DESK_SERVICE_KEY, webhooks) stay out.
    "ODDS_API_KEY", "ODDS_API_BOOKMAKER", "ODDS_REFRESH_MINUTES", "ODDS_API_MIN_LEFT",
    "ODDS_LOOKAHEAD_HOURS", "FED_PM_MAX_SPREAD",
    # Fill-check knobs (strict_fill.py / public_http.py).
    "PAPER_STRICT_FILL", "PAPER_REQUOTE_SECONDS", "PAPER_DEPTH_SHARE", "PAPER_MAX_SLIP",
    "PAPER_MEME_MAX_SLIP", "PAPER_COINBASE_MAX_SLIP", "PAPER_SPOT_FALLBACK_SLIP",
    "PUBLIC_HTTP_GAP_SECONDS", "KALSHI_TAPE_BUDGET_SEC",
    "KALSHI_READS_PER_SEC", "KALSHI_CACHE_SECONDS", "KALSHI_GATEWAY_MAX_WAIT", "KALSHI_GATEWAY_DIR",
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
    for part in parts:
        if not part or part in (".", "..") or part != os.path.basename(part):
            raise RuntimeError("path escapes the paper desk")
    joined = os.path.abspath(os.path.join(base, *parts))
    if joined != base and not joined.startswith(base + os.sep):
        raise RuntimeError("path escapes the paper desk")
    if os.path.islink(joined):
        target = os.path.realpath(joined)
        allowed = _allowed_durable(base)
        if allowed and (target == allowed or target.startswith(allowed + os.sep)):
            return joined
        raise RuntimeError("path escapes the paper desk")
    path = os.path.realpath(joined)
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


def _follow_link(path: str) -> str:
    if path and os.path.islink(path):
        return os.path.realpath(path)
    return path


def _durable_target(path: str) -> str:
    """Follow a settlement symlink so a save updates the volume, not the link."""
    if not path or not os.path.islink(path):
        return path
    path = os.path.realpath(path)
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    return path


def _atomic_write(path: str, text: str) -> None:
    path = _durable_target(path)
    folder = os.path.dirname(path) or "."
    with _FILE_LOCK:
        os.makedirs(folder, exist_ok=True)
        # Unique per process and thread: two writers sharing one ".tmp" name
        # raced on Railway (FileNotFoundError on pimp-good.json.tmp).
        tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
        os.replace(tmp, path)


def _mount_points() -> set[str]:
    found = set()
    try:
        with open("/proc/mounts", encoding="utf-8", errors="replace") as handle:
            lines = handle.read().splitlines()
    except OSError:
        return found
    for line in lines:
        parts = line.split()
        if len(parts) < 2:
            continue
        raw = parts[1]
        raw = (
            raw.replace("\\040", " ")
            .replace("\\011", "\t")
            .replace("\\012", "\n")
            .replace("\\134", "\\")
        )
        try:
            found.add(os.path.realpath(raw))
        except OSError:
            continue
    return found


def settlement_dir() -> str | None:
    """Where closed paper settlements survive a new image.

    PAPER_DATA_DIR wins when it is set. Otherwise a real mount at /data is
    used. A /data directory created inside the image is not a mount, and
    keeping files there would lose them on the next deploy.
    """
    explicit = os.environ.get("PAPER_DATA_DIR", "").strip()
    if explicit:
        return explicit
    if os.path.realpath("/data") in _mount_points():
        return "/data/paper-bots"
    return None


def _allowed_durable(base: str) -> str:
    bound = _BOUND_DURABLE.get(os.path.realpath(base)) or ""
    if bound:
        return bound
    if os.path.realpath(base) != os.path.realpath(ROOT):
        return ""
    if os.environ.get("PAPER_KEEP_SETTLEMENTS") == "0":
        return ""
    durable = settlement_dir()
    if not durable:
        return ""
    try:
        return os.path.realpath(durable)
    except OSError:
        return ""


def _path_inside(path: str, parent: str) -> bool:
    try:
        path = os.path.realpath(path)
        parent = os.path.realpath(parent)
    except OSError:
        return False
    return path == parent or path.startswith(parent + os.sep)


def _same_settlement_link(local: str, remote: str) -> bool:
    if not os.path.islink(local):
        return False
    try:
        return os.path.realpath(local) == os.path.realpath(remote)
    except OSError:
        return False


def _point_settlement(local: str, remote: str) -> None:
    os.makedirs(os.path.dirname(remote), exist_ok=True)
    folder = os.path.dirname(local)
    if folder:
        os.makedirs(folder, exist_ok=True)
    if _same_settlement_link(local, remote):
        return
    # Build the link aside, then swap it in: two binders at once used to race
    # between remove and symlink (FileExistsError on kalshi_crypto_history.json).
    tmp = f"{local}.{os.getpid()}.{threading.get_ident()}.link"
    if os.path.lexists(tmp):
        os.remove(tmp)
    os.symlink(os.path.abspath(remote), tmp)
    os.replace(tmp, local)


def _copy_settlement(src: str, dest: str) -> None:
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".keep"
    shutil.copy2(src, tmp)
    os.replace(tmp, dest)


_LINKED: set = set()


def _bind_settlement(local: str, remote: str) -> None:
    remote_ready = os.path.isfile(remote) and not os.path.islink(remote)
    local_file = os.path.isfile(local) and not os.path.islink(local)
    if local_file and remote_ready and local in _LINKED:
        # This process linked it earlier, so the plain file is not from the image:
        # a writer saved over the link (atomic replace) instead of through it.
        # That save is the newest state. Keep it on the volume, then re-link.
        # (A fresh image always arrives in a new process, where the volume wins.)
        log.info("paper settlement %s: saved over the link; keeping that save on the volume", local)
        _copy_settlement(local, remote)
        _point_settlement(local, remote)
        return
    _LINKED.add(local)
    if remote_ready:
        _point_settlement(local, remote)
        return
    if local_file:
        _copy_settlement(local, remote)
        _point_settlement(local, remote)
        return
    _point_settlement(local, remote)


def keep_closed_settlements(root: str | None = None, durable: str | None = None) -> list:
    """Keep closed paper settlements on the volume so a push cannot wipe them.

    The copy already on the volume wins. The empty file shipped in a new image
    is replaced with a symlink to that copy. A desk root other than this
    checkout is left alone unless the caller passes durable, so a unit test
    cannot retarget the real accounts.
    """
    root = _root(root)
    with _FILE_LOCK:
        if durable is None:
            if os.path.realpath(root) != os.path.realpath(ROOT):
                return []
            if os.environ.get("PAPER_KEEP_SETTLEMENTS") == "0":
                return []
            durable = settlement_dir()
        if not durable:
            return []
        durable = os.path.abspath(durable)
        if _path_inside(durable, root):
            return []
        try:
            os.makedirs(durable, exist_ok=True)
            bound = os.path.realpath(durable)
        except OSError:
            log.exception("paper settlement folder")
            return []
        if _path_inside(bound, root):
            return []
        _BOUND_DURABLE[os.path.realpath(root)] = bound
        linked = []
        for rel in SETTLEMENT_FILES:
            if not rel or rel.startswith(("/", "\\")) or ".." in rel.split("/"):
                continue
            local = os.path.join(root, *rel.split("/"))
            remote = os.path.join(bound, *rel.split("/"))
            if _path_inside(os.path.dirname(remote), root):
                continue
            try:
                _bind_settlement(local, remote)
            except OSError:
                log.exception("paper settlement %s", rel)
                continue
            linked.append(rel)
        return linked


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


def _ct_date(text) -> dt.date | None:
    """The Central-time date of a stored timestamp (the desk's day runs midnight to midnight CT).

    Timestamps are stored in UTC (with +00:00, Z, " UTC", or no zone at all on the desk's UTC
    server), so their first ten characters are the UTC date. Comparing those to the CT date
    started the day at 6 PM CT and kept the evening's trades in "today" until 6 AM.
    A bare date (YYYY-MM-DD) is already a day and is used as is.
    """
    raw = str(text or "").strip()
    if not raw:
        return None
    if len(raw) == 10:
        try:
            return dt.date.fromisoformat(raw)
        except ValueError:
            return None
    try:
        when = dt.datetime.fromtimestamp(float(raw), dt.timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        try:
            when = dt.datetime.fromisoformat(raw.replace(" UTC", "+00:00").replace("Z", "+00:00"))
        except ValueError:
            try:
                return dt.date.fromisoformat(raw[:10])
            except ValueError:
                return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=dt.timezone.utc)
    return when.astimezone(CT).date()


def _day_hit(text: str, day: dt.date) -> bool:
    return _ct_date(text) == day


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
    # Nested defaults merge when file omits new keys.
    if not isinstance(cfg.get("venue_min_edge"), dict):
        cfg["venue_min_edge"] = dict(DEFAULTS["venue_min_edge"])
    else:
        merged = dict(DEFAULTS["venue_min_edge"])
        merged.update(cfg["venue_min_edge"])
        cfg["venue_min_edge"] = merged
    if not isinstance(cfg.get("shadow"), dict):
        cfg["shadow"] = dict(DEFAULTS["shadow"])
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
        edge = float(raw.get("min_edge", DEFAULTS["min_edge"]))
        pace_min = int(float(raw.get("pace_min", DEFAULTS["pace_min"])))
        pace_target = int(float(raw.get("pace_target", DEFAULTS["pace_target"])))
    except (TypeError, ValueError):
        return None, "Enter a number in every limit."
    if not all(math.isfinite(n) for n in (hi_min, hi_max, lo_max, loss, risk, edge)):
        return None, "Enter finite numbers."
    if hi_min < 20 or hi_max > 100 or hi_min > hi_max:
        return None, "At 80% or higher, the paper stake stays between $20 and $100."
    if round(lo_max, 2) != 20 or lo_max > hi_min:
        return None, "Below 80%, the paper stake stays near $20."
    if loss == 0:
        return None, "A daily loss stop of zero is refused."
    if not (1 <= loss <= 100000):
        return None, "Daily loss stop stays between $1 and $100000."
    if not (1 <= risk <= 1000000):
        return None, "Max open risk stays between $1 and $1000000."
    if not (1 <= positions <= 50):
        return None, "Max open positions stays between 1 and 50."
    if not (0.0 <= edge <= 0.20):
        return None, "The edge bar stays between 0 and 0.20."
    if not (1 <= pace_min <= pace_target <= 48):
        return None, "The paper pace stays between 1 and 48, and the target is at least the minimum."
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
    venue, venue_err = desk_profit.parse_venue_min_edge(
        raw.get("venue_min_edge", DEFAULTS["venue_min_edge"])
    )
    if venue_err:
        return None, venue_err
    pairs, pairs_err = desk_profit.parse_correlation_pairs(
        raw.get("correlation_pairs", DEFAULTS["correlation_pairs"])
    )
    if pairs_err:
        return None, pairs_err
    shadow, shadow_err = desk_profit.parse_shadow(raw.get("shadow", DEFAULTS["shadow"]))
    if shadow_err:
        return None, shadow_err
    sizing = str(raw.get("sizing") or DEFAULTS["sizing"]).strip().lower()
    if sizing not in ("curve", "kelly_lite"):
        return None, "sizing must be curve or kelly_lite."
    try:
        kelly = float(raw.get("kelly_fraction", DEFAULTS["kelly_fraction"]))
        flip_delta = float(raw.get("model_flip_delta", DEFAULTS["model_flip_delta"]))
        starve_n = int(float(raw.get("starve_min_n", DEFAULTS["starve_min_n"])))
        starve_ev = float(raw.get("starve_expectancy", DEFAULTS["starve_expectancy"]))
        starve_factor = float(raw.get("starve_factor", DEFAULTS["starve_factor"]))
        exp_days = int(float(raw.get("expectancy_window_days", DEFAULTS["expectancy_window_days"])))
        fill_tax = float(raw.get("fill_adverse_tax", DEFAULTS.get("fill_adverse_tax", 0.01)))
        gate_a_n = int(float(raw.get("gate_a_min_n", DEFAULTS.get("gate_a_min_n", 20))))
    except (TypeError, ValueError):
        return None, "Profit-six limits have to be numbers."
    if not (0.05 <= kelly <= 1.0):
        return None, "kelly_fraction stays between 0.05 and 1.0."
    if not (0.0 <= flip_delta <= 0.50):
        return None, "model_flip_delta stays between 0 and 0.50."
    if not (3 <= starve_n <= 200):
        return None, "starve_min_n stays between 3 and 200."
    if not math.isfinite(starve_ev) or starve_ev < -100 or starve_ev > 100:
        return None, "starve_expectancy stays between -100 and 100."
    if not (0.0 <= starve_factor <= 1.0):
        return None, "starve_factor stays between 0 and 1."
    if not (5 <= exp_days <= 90):
        return None, "expectancy_window_days stays between 5 and 90."
    if not (0.0 <= fill_tax <= 0.05):
        return None, "fill_adverse_tax stays between 0 and 0.05."
    if not (5 <= gate_a_n <= 200):
        return None, "gate_a_min_n stays between 5 and 200."
    model_flip_exits = bool(raw.get("model_flip_exits", DEFAULTS["model_flip_exits"]))
    tower_budgets_raw = raw.get("tower_risk_budgets", DEFAULTS.get("tower_risk_budgets"))
    tower_budgets: dict = {}
    if tower_budgets_raw is None:
        tower_budgets = dict(DEFAULTS.get("tower_risk_budgets") or {})
    elif not isinstance(tower_budgets_raw, dict):
        return None, "tower_risk_budgets must be a map of bot id → share."
    else:
        total_share = 0.0
        for bot_id, share in tower_budgets_raw.items():
            try:
                s = float(share)
            except (TypeError, ValueError):
                return None, "tower_risk_budgets shares must be numbers."
            if not math.isfinite(s) or s < 0 or s > 1:
                return None, "each tower_risk_budgets share stays between 0 and 1."
            tower_budgets[str(bot_id)] = round(s, 4)
            total_share += s
        if total_share > 1.0001:
            return None, "tower_risk_budgets shares must sum to ≤ 1.0."
    hillclimb_lever = raw.get("hillclimb_lever", DEFAULTS.get("hillclimb_lever"))
    if hillclimb_lever in ("", None):
        hillclimb_lever = None
    else:
        hillclimb_lever = str(hillclimb_lever)
        try:
            import desk_more
            if hillclimb_lever not in desk_more.HILLCLIMB_LEVERS:
                return None, f"hillclimb_lever must be one of {list(desk_more.HILLCLIMB_LEVERS)} or null."
        except Exception:
            pass
    return {
        "paper_only": True,
        "stake_hi_min": round(hi_min, 2),
        "stake_hi_max": round(hi_max, 2),
        "stake_hi_prob": 0.8,
        "stake_lo_max": round(lo_max, 2),
        "daily_loss_stop": round(loss, 2),
        "max_open_risk": round(risk, 2),
        "max_open_positions": positions,
        "min_edge": round(edge, 4),
        "pace_min": pace_min,
        "pace_target": pace_target,
        "week_goal": round(goal, 2),
        "quiet_start": quiet_start,
        "quiet_end": quiet_end,
        "venue_min_edge": venue,
        "sizing": sizing,
        "kelly_fraction": round(kelly, 4),
        "correlation_pairs": pairs,
        "model_flip_delta": round(flip_delta, 4),
        "model_flip_exits": model_flip_exits,
        "starve_min_n": starve_n,
        "starve_expectancy": round(starve_ev, 4),
        "starve_factor": round(starve_factor, 4),
        "expectancy_window_days": exp_days,
        "fill_adverse_tax": round(fill_tax, 4),
        "gate_a_min_n": gate_a_n,
        "tower_risk_budgets": tower_budgets,
        "hillclimb_lever": hillclimb_lever,
        "shadow": shadow,
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
        f"Below that, a paper stake is about ${lo_max:.2f}, and the fill buys enough contracts to land near that amount. "
        f"Daily loss stop ${cfg['daily_loss_stop']:.2f} (the old default was $50.00). The stop stays on. "
        f"Max open risk ${cfg['max_open_risk']:.2f}. "
        f"Max open positions {cfg['max_open_positions']} (the old default was 4). "
        f"Edge bar {float(cfg.get('min_edge') or 0):.2f} after the fee (the old default was 0.08). "
        "A paper buy needs that edge. The trades counted this hour do not waive it. "
        "The BTC 15-minute check and the sports gap check use these dollar stakes and buy whole contracts near that amount. "
        "These limits also gate a new entry check. "
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


# Combined manage+buy scripts still run when the desk gate hits, with entries off.
_MANAGE_WHEN_GATED = frozenset({"sports-gap", "memecoin", "btc15m", "btc-carry"})


def _child_env(
    block_entries: bool = False,
    shadow: dict | None = None,
    *,
    block_reason: str = "",
) -> dict:
    env = {key: os.environ[key] for key in _ENV_KEEP if os.environ.get(key)}
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PAPER_ONLY"] = "1"
    if block_entries:
        env["DESK_BLOCK_ENTRIES"] = "1"
        # Prefer-1: pass the real entry_gate line so manage-when-gated children
        # densify ruin / daily-loss / max-open — never bland DESK_BLOCK_ENTRIES=1.
        why = str(block_reason or os.environ.get("DESK_BLOCK_REASON") or "").strip()
        if why:
            env["DESK_BLOCK_REASON"] = why[:240]
    if shadow:
        env["DESK_SHADOW"] = "1"
        env["DESK_SHADOW_ID"] = str(shadow.get("id") or "")
        if shadow.get("account"):
            env["DESK_SHADOW_ACCOUNT"] = str(shadow["account"])
        params = shadow.get("params") if isinstance(shadow.get("params"), dict) else {}
        if params.get("venue_edge") is not None:
            env["DESK_SHADOW_VENUE_EDGE"] = str(params["venue_edge"])
    return env


def _folder_ok(root: str, folder: str, script: str) -> bool:
    try:
        cwd = _under(root, folder)
    except RuntimeError:
        return False
    return os.path.isfile(os.path.join(cwd, script))


def _kalshi_paper(root: str, folder: str = "kalshi-sp500-paper") -> bool:
    cfg = _read_json(_under(root, folder, "config.json")) or {}
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


def _kalshi_skip_run_body(summary: str) -> str:
    """Prefer densified CARD / NO TRADE from the last INX scan (sports #414 sibling)."""
    if not summary:
        return ""
    for line in str(summary).splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("CARD: "):
            body = _clean(stripped[6:], 220)
            if body:
                return body[:400]
        upper = stripped.upper()
        if upper.startswith("NO TRADE"):
            parts = stripped.split(":", 1)
            if len(parts) == 2 and parts[1].strip():
                return _clean(parts[1].strip(), 400)
    return ""


def _kalshi_tower_folder(bot_id: str | None = None, folder: str | None = None) -> str:
    """Resolve INX paper folder — sized must not inherit S&P staff-clear truth."""
    if folder:
        return folder
    if bot_id == "kalshi-sized":
        return "kalshi-sized-paper"
    return "kalshi-sp500-paper"


def _kalshi_drawdown_halt_line(
    root: str,
    state: dict | None,
    *,
    bot_id: str | None = None,
    folder: str | None = None,
) -> str:
    """Entry-block truth when bankroll ≤ drawdown_halt (halted flag stays kill-only)."""
    if not state or state.get("halted"):
        return ""
    bankroll = _num(state.get("bankroll"))
    tower = _kalshi_tower_folder(bot_id, folder)
    cfg = _read_json(_under(root, tower, "config.json")) or {}
    dd_halt = _num(cfg.get("drawdown_halt_bankroll"))
    start = _num(cfg.get("starting_bankroll")) or 500.0
    under_dd = (
        bankroll is not None
        and dd_halt is not None
        and float(bankroll) <= float(dd_halt) + 1e-9
    )
    if not under_dd:
        return ""
    # Staff waived soft DD for buys — still densify so $444 idle ≠ healthy empty settle.
    if bool(cfg.get("staff_clear_drawdown_halt")):
        return (
            f"Staff cleared soft drawdown halt: bankroll ${float(bankroll):.2f} ≤ "
            f"${float(dd_halt):.2f} (start ${float(start):.0f}). "
            "Paper buys may resume; kill $400 + fee/band/daily-loss stay stone."
        )
    return (
        f"Tower drawdown halt: bankroll ${float(bankroll):.2f} ≤ "
        f"${float(dd_halt):.2f} (start ${float(start):.0f}). New buys off; exits still run."
    )


def _kalshi_skip(
    root: str,
    state: dict | None,
    summary: str = "",
    *,
    bot_id: str | None = None,
    folder: str | None = None,
) -> str:
    # Drawdown / kill beat bland settle CARD ("No open paper positions") so $444
    # idle is not read as a healthy empty book.
    tower = _kalshi_tower_folder(bot_id, folder)
    dd = _kalshi_drawdown_halt_line(root, state, bot_id=bot_id, folder=tower)
    if dd:
        return dd
    run_skip = _kalshi_skip_run_body(summary)
    if run_skip:
        low = run_skip.lower()
        if "no open paper" in low or low in ("no paper buy.", "paper buy."):
            pass  # fall through to calendar / kill densify
        else:
            return run_skip
    day = _today()
    reasons = []
    if day.weekday() >= 5:
        reasons.append("WEEKEND")
    cal = _read_json(_under(root, tower, "calendar.json")) or {}
    key = day.isoformat()
    for name, days in cal.items():
        if str(name).startswith("_") or not isinstance(days, list):
            continue
        if key in days:
            reasons.append(str(name))
    if reasons:
        line = f"{key} CT skip: {', '.join(reasons)}."
    else:
        # Tradable day — do not put a "not on skip calendar" line in why/skip (looks like a block).
        line = ""
    if state and state.get("halted"):
        halt = "The paper account is halted by its own kill switch."
        line = f"{line} {halt}".strip() if line else halt
    return line


def next_inx_scan_line(bot_id: str, now: dt.datetime | None = None) -> str:
    """
    Heartbeat for KXINXU towers: next scan / settle window in America/Chicago.
    Morning idle is schedule-true, not a broken desk.
    """
    now = now or dt.datetime.now(CT)
    if now.tzinfo is None:
        now = now.replace(tzinfo=CT)
    else:
        now = now.astimezone(CT)
    slots = [s for s in AUTO if s.get("id") == bot_id and "at_ct" in s]
    if not slots:
        return ""
    # Prefer run (scan) slots for the heartbeat; fall back to any.
    runs = [s for s in slots if s.get("action") == "run"] or slots
    hm = now.hour * 60 + now.minute

    def _mins(hhmm: str) -> int:
        h, m = str(hhmm).split(":")
        return int(h) * 60 + int(m)

    for s in runs:
        start = _mins(s["at_ct"])
        until = _mins(s.get("until_ct") or s["at_ct"])
        if start <= hm <= until:
            label = "scan" if s.get("action") == "run" else s.get("action")
            return f"In {label} window until {s.get('until_ct')} CT."
    # Next future run today, else first run tomorrow.
    future = sorted(
        (s for s in runs if _mins(s["at_ct"]) > hm),
        key=lambda s: _mins(s["at_ct"]),
    )
    if future:
        s = future[0]
        label = "scan" if s.get("action") == "run" else s.get("action")
        return f"Next {label} {s['at_ct']} CT."
    s = sorted(runs, key=lambda x: _mins(x["at_ct"]))[0]
    label = "scan" if s.get("action") == "run" else s.get("action")
    return f"Next {label} tomorrow {s['at_ct']} CT."


def inx_in_run_window(bot_id: str, now: dt.datetime | None = None) -> bool:
    """True when an INX tower's AUTO run/scan window is open (CT)."""
    now = now or dt.datetime.now(CT)
    if now.tzinfo is None:
        now = now.replace(tzinfo=CT)
    else:
        now = now.astimezone(CT)
    return any(
        isinstance(slot, dict)
        and str(slot.get("id") or "") == bot_id
        and str(slot.get("action") or "") == "run"
        and "at_ct" in slot
        and _window_open(now, slot)
        for slot in AUTO
    )


def _inx_bland_settle_summary(summary: str) -> bool:
    """Empty-book settle output — must not wipe a densified in-window scan tip."""
    text = str(summary or "").strip()
    if not text:
        return True
    low = text.lower()
    if "no trade" in low or low.startswith("card:"):
        return False
    # Sole / leading empty settle lines from bot.py settle with nothing open.
    first = text.splitlines()[0].strip().lower().rstrip(".")
    return first in ("no open paper positions", "no open paper position")


def _inx_densified_scan_summary(summary: str) -> bool:
    """Prior scan tip worth keeping over overlapping empty settle."""
    low = str(summary or "").lower()
    return (
        "no trade" in low
        or "card:" in low
        or "inx fair" in low
        or "staff cleared soft drawdown" in low
        or "drawdown halt" in low
    )

def _btc_skip_card_body(summary: str) -> str:
    """Prefer densified evaluate CARD (#397) over generic no-buy boilerplate."""
    for line in str(summary or "").splitlines():
        stripped = line.strip()
        if not stripped.startswith("CARD: "):
            continue
        body = _clean(stripped[6:], 220)
        if not body:
            continue
        low = body.lower()
        # Empty-market / buy-count boilerplate is not a skip reason.
        if low.startswith("checked ") and (
            "no paper buy" in low
            or "paper buy" in low
            or "no open windows" in low
        ):
            continue
        if low in ("no paper buy.", "paper buy."):
            continue
        return body
    return ""


def _btc_skip(summary: str) -> str:
    """Tower skip strip for BTC/commodity/carry. A HOLD is the trade, not a skip."""
    if not summary:
        return "No check yet. Skip and news status show up after a run."
    lines = [_clean(line, 240) for line in summary.splitlines()]
    news = next((line for line in lines if line.lower().startswith("news")), "")
    signals = [line for line in lines if line.upper().startswith("SIGNAL:")]
    skips = [line for line in signals if "SKIP" in line.upper()]
    holds = [
        line for line in signals
        if "HOLD" in line.upper() and "SKIP" not in line.upper()
    ]
    if skips:
        picked = [line for line in (news, *skips) if line]
        return " ".join(picked)[:400]
    if holds:
        return ""
    signal = signals[0] if signals else ""
    picked = [line for line in (news, signal) if line]
    if picked:
        return " ".join(picked)[:400]
    card_skip = _btc_skip_card_body(summary)
    if card_skip and card_skip.lower().startswith("holding unlevered"):
        return ""
    if card_skip:
        return card_skip[:400]
    # No-window / ladder-only lines beat bland CARD + "did not include a skip
    # line" lie (#499 sports twin).
    for line in lines:
        low = line.lower()
        if "no open" in low and "window" in low:
            return line[:400]
        if "no open windows" in low:
            return line[:400]
    return "The last run did not include a skip line."


def _sports_skip(summary: str) -> str:
    """Tower skip strip for sports-gap. Prefer densified CARD evaluate reason (#400 sibling)."""
    if not summary:
        return "No check yet. Skip and news status show up after a run."
    for line in str(summary).splitlines():
        stripped = line.strip()
        if not stripped.startswith("CARD: "):
            continue
        body = _clean(stripped[6:], 220)
        if not body:
            continue
        low = body.lower()
        # Boilerplate empty/buy CARDs are not skip densify.
        if "lanes clear" in low:
            continue
        if low.startswith("no paper buy") or low.startswith("paper buy"):
            continue
        # "No live or tip-soon games…" IS the skip reason — never lie as
        # "did not include a skip line" (#498 INX tip twin).
        return body[:400]
    return "The last run did not include a skip line."


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
    stored_why = _clean(pos.get("why") or "", 180)
    if stored_why:
        why = stored_why
    elif gap is None:
        why = "The reason was not stored with this trade."
    else:
        why = f"Paper buy. The fair price beat the ask by {gap * 100:.1f} points after the fee."
    terms = _trade_terms(pos, cost)
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
        "fill_untaxed": None if _num(ask) is None else round(_num(ask), 4),
        "fill_tax": desk_profit.FILL_ADVERSE_TAX,
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
        "risk": terms["risk"],
        "reward": terms["reward"],
        "risk_reward": terms["risk_reward"],
        "payout": None,
        "exit_reason": "",
        "closed_at": "",
        "confidence": _confidence(_num(prob)),
        "edge": edge_after_fee(prob, ask),
        # Prove-it drawer (pass through when bots stored adapt diagnostics).
        "prove": {
            "cushion": pos.get("cushion"),
            "sigma": pos.get("sigma"),
            "adapt_mult": pos.get("adapt_mult"),
            "adapt_notes": list(pos.get("adapt_notes") or [])[:8],
            "play_safe": pos.get("play_safe"),
            "play_big": pos.get("play_big"),
            "vol_regime": pos.get("vol_regime"),
            "vol_score": pos.get("vol_score"),
            "history_n": pos.get("history_n"),
            "history_hit": pos.get("history_hit"),
            "history_ci_low": pos.get("history_ci_low"),
            "fee": None if _num(fee) is None else round(_num(fee), 4),
            "ask": None if _num(ask) is None else round(_num(ask), 4),
            "fill_tax": desk_profit.FILL_ADVERSE_TAX,
            "edge": edge_after_fee(prob, ask),
        },
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
        side = str(pos.get("side") or "yes").upper()
        name = pos.get("team") or pos.get("label") or pos.get("ticker") or "contract"
        title = _clean(f"{pos.get('contracts') or '?'} {side} {name}")
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
    if spec["kind"] == "floor":
        summary = str(run.get("summary") or "")
        if run.get("at"):
            view["last_check"] = str(run.get("at"))
        state_path = _under(root, spec["folder"], spec["state"]) if spec.get("state") else ""
        state, _problem = _read_state(state_path) if state_path else (None, "")
        traders = int(spec.get("traders") or 120)
        if isinstance(state, dict):
            view["has_state"] = True
            view["empty"] = ""
            view["cash"] = 0.0
            try:
                n = int(state.get("traders"))
            except (TypeError, ValueError):
                n = traders
            view["traders"] = n if n >= 100 else traders
            view["last_epoch"] = _mtime(state_path) or 0
            if not view["last_check"]:
                view["last_check"] = _fmt_epoch(view["last_epoch"])
        else:
            view["empty"] = spec["empty"]
            view["traders"] = traders
        view["skip"] = "floor does not trade"
        view["departments"] = [dict(row) for row in (spec.get("departments") or ())]
        line = f"{view['traders']} traders on six desks. One book. It does not trade."
        view["why"] = card_copy(summary) or line
        return _finish_bot(view, spec, root)
    if spec["kind"] in ("btc", "spot", "carry", "log", "shadow"):
        summary = str(run.get("summary") or "")
        view["skip"] = _btc_skip(summary)
        if spec["kind"] == "btc":
            view["warning"] = _btc_calendar_warning(summary)
        if run.get("at"):
            view["last_check"] = str(run.get("at"))
        state_path = _under(root, spec["folder"], spec["state"]) if spec.get("state") else ""
        state, _problem = _read_state(state_path) if state_path else (None, "")
        if isinstance(state, dict):
            positions, trades, realized, today, risk, count, history = _sports_positions(state, day)
            view["has_state"] = True
            view["empty"] = ""
            view["cash"] = _num(state.get("cash"))
            if view["cash"] is not None:
                view["cash"] = round(view["cash"], 2)
            view["positions"] = positions
            view["trades"] = trades
            view["history"] = history
            view["realized"] = realized
            view["today"] = today
            view["open_risk"] = risk
            view["open_count"] = count
            view["last_epoch"] = _mtime(state_path) or 0
            if not view["last_check"]:
                view["last_check"] = _fmt_epoch(view["last_epoch"])
        else:
            view["empty"] = spec["empty"]
        view["why"] = card_copy(summary) if summary.strip() else ""
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
            view["skip"] = _kalshi_skip(
                root, None, bot_id=spec["id"], folder=spec.get("folder"),
            )
        view["why"] = plain_reason(view["skip"]) if view["skip"] else ""
        return _finish_bot(view, spec, root)
    view["has_state"] = True
    view["empty"] = ""
    view["warning"] = _calendar_warning(root, spec["id"])
    summary = str(run.get("summary") or "")
    if spec["kind"] == "sports":
        positions, trades, realized, today, risk, count, history = _sports_positions(state, day)
        view["cash"] = _num(state.get("cash"))
    elif spec["kind"] == "kalshi":
        positions, trades, realized, today, risk, count, history = _kalshi_positions(state, day)
        view["cash"] = _num(state.get("bankroll"))
        # Prefer densified CARD/NO TRADE from last scan over calendar-only (#414 sibling).
        # Sized reads its own config — never inherit S&P staff-clear tip (#501 twin).
        view["skip"] = _kalshi_skip(
            root, state, summary=summary, bot_id=spec["id"], folder=spec.get("folder"),
        )
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
    view["why"] = card_copy(summary) if summary.strip() else ""
    # Sports: why already densifies CARD; skip stayed "" forever (#400 sibling).
    if spec["kind"] == "sports" and not view.get("skip"):
        view["skip"] = _sports_skip(summary)
    # Kalshi: prefer drawdown/kill/staff-clear densify over settle boilerplate why.
    if spec["kind"] == "kalshi":
        skip = str(view.get("skip") or "")
        why_low = str(view.get("why") or "").lower()
        skip_low = skip.lower()
        if skip and (
            "drawdown halt" in skip_low
            or "staff cleared soft drawdown" in skip_low
            or "kill switch" in skip_low
            or not why_low.strip()
            or "no open paper" in why_low
            or "no paper buy" in why_low
        ):
            view["why"] = plain_reason(skip)
    view["outside"] = _outside(root, spec["id"], stamp)
    _save_good_bot(root, spec["id"], view)
    return _finish_bot(view, spec, root)


def _sized_view() -> dict:
    view = {
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
        "plans": bot_plans("kalshi-sized"),
    }
    view["gates_hit"] = bot_gates_hit(view)
    return view


def entry_gate(root: str | None = None, bots: list | None = None) -> str:
    cfg = load_settings(root)
    rows = bots if bots is not None else snapshot(root)["bots"]
    # Shadow rows never count toward desk open risk / cash gates.
    live = [b for b in rows if not b.get("shadow_only")]
    open_risk = round(sum(float(b.get("open_risk") or 0) for b in live), 2)
    open_count = int(sum(int(b.get("open_count") or 0) for b in live))
    today = round(sum(float(b.get("today") or 0) for b in live), 2)
    try:
        import desk_roi_plan
        ruin = desk_roi_plan.ruin_drill_blocks_entries(root)
        if ruin:
            return ruin
    except Exception:
        pass
    if today <= -float(cfg["daily_loss_stop"]):
        return (
            f"Daily loss stop is hit (${abs(today):.2f} against ${cfg['daily_loss_stop']:.2f}). "
            "Entry checks stay off until the next Chicago day. Settle and the morning brief still run."
        )
    if open_count >= int(cfg["max_open_positions"]):
        return (
            f"Max open positions is reached ({open_count} of {cfg['max_open_positions']}). "
            "Entry checks stay off. Settle and the morning brief still run."
        )
    if open_risk >= float(cfg["max_open_risk"]) - 1e-9:
        return (
            f"Max open risk is reached (${open_risk:.2f} of ${cfg['max_open_risk']:.2f}). "
            "Entry checks stay off. Settle and the morning brief still run."
        )
    return ""


def desk_open_summary(root: str | None = None, bots: list | None = None) -> dict:
    """How many vault bets are open right now, counted the same way as ``entry_gate``.

    Used for the "desk open" log line so the evening report can show the day's
    highest open count against the max-open-positions limit. Read only.
    """
    cfg = load_settings(root)
    rows = bots
    if rows is None:
        base = _root(root)
        runs = _load_runs(base)
        day = _today()
        rows = [_bot_view(spec, base, runs, day) for spec in BOTS]
    live = [b for b in rows if not b.get("shadow_only")]
    by_bot = {str(b.get("id")): int(b.get("open_count") or 0) for b in live if int(b.get("open_count") or 0)}
    return {
        "open": int(sum(int(b.get("open_count") or 0) for b in live)),
        "max_open": int(cfg["max_open_positions"]),
        "open_risk": round(sum(float(b.get("open_risk") or 0) for b in live), 2),
        "max_open_risk": float(cfg["max_open_risk"]),
        "by_bot": by_bot,
    }


def _report_closed_rows(spec: dict, base: str, view: dict, day: dt.date,
                        first_day: dt.date | None = None) -> tuple[list, int, bool]:
    """(closed rows from ``first_day`` to ``day``, settled results ever, rows match the tower's today number).

    Reads the same closed list the tower card reads. Read only. ``first_day`` defaults to ``day``.
    """
    import desk_report

    if first_day is not None and first_day != day:
        rows, settled, _same = _report_closed_rows(spec, base, view, day)
        state = None
        if spec.get("state") and spec.get("kind") in ("sports", "btc", "spot", "carry", "log", "shadow", "kalshi"):
            state, _problem = _read_state(_under(base, spec["folder"], spec["state"]))
        if isinstance(state, dict) and isinstance(state.get("closed"), list):
            src = _dedupe_pos([p for p in state["closed"] if isinstance(p, dict)])
            key = ("settled_at", "day") if spec.get("kind") == "kalshi" else ("closed",)
            pick = []
            for p in src:
                when = next((p.get(k) for k in key if p.get(k)), "")
                d = _ct_date(str(when or ""))
                if d is not None and first_day <= d <= day:
                    pick.append(p)
        else:
            pick = [r for r in (view.get("history") or []) if isinstance(r, dict)
                    and (desk_report.ct_date(r.get("closed_at")) or dt.date.min) >= first_day
                    and (desk_report.ct_date(r.get("closed_at")) or dt.date.max) <= day]
        return pick, settled, False

    kind = spec.get("kind")
    state = None
    if spec.get("state") and kind in ("sports", "btc", "spot", "carry", "log", "shadow", "kalshi"):
        state, _problem = _read_state(_under(base, spec["folder"], spec["state"]))
    if isinstance(state, dict) and isinstance(state.get("closed"), list):
        closed = _dedupe_pos([p for p in state["closed"] if isinstance(p, dict)])
        if kind == "kalshi":
            today = [p for p in closed if _day_hit(str(p.get("settled_at") or p.get("day") or ""), day)
                     or str(p.get("day") or "") == day.isoformat()]
        else:
            today = [p for p in closed if _day_hit(str(p.get("closed") or ""), day)]
        settled = sum(1 for p in closed if _num(p.get("pnl") if p.get("pnl") is not None else p.get("pnl_usd")) is not None)
        return today, settled, True
    history = [r for r in (view.get("history") or []) if isinstance(r, dict)]
    today = [r for r in history if desk_report.ct_date(r.get("closed_at")) == day]
    settled = sum(1 for r in history if r.get("pnl") is not None)
    return today, settled, False


def desk_report_card(root: str | None = None, now: dt.datetime | None = None) -> dict:
    """Read-only desk report card for the evening report (plan steps 886-925). See desk_report.py."""
    import desk_report
    import new_towers

    cfg = load_settings(root)
    base = _root(root)
    runs = _load_runs(base)
    day = _today() if now is None else now.astimezone(CT).date()
    views, closed_by_bot, settled, checked = [], {}, {}, set()
    for spec in BOTS:
        view = _bot_view(spec, base, runs, day)
        views.append(view)
        try:
            rows, n, same = _report_closed_rows(spec, base, view, day)
        except Exception:  # noqa: BLE001 - a bad file shows as an error, never stops the card
            rows, n, same = [], 0, False
            view["read_error"] = view.get("read_error") or "Could not read closed trades."
        closed_by_bot[spec["id"]], settled[spec["id"]] = rows, n
        if same:
            checked.add(spec["id"])
    gate = entry_gate(base, views)
    return desk_report.report_card(
        views, closed_by_bot, gate, cfg, settled_by_bot=settled,
        research_ids=set(new_towers.RESEARCH) | {s["id"] for s in BOTS if s.get("kind") == "floor"},
        checked_ids=checked, now=now, city_url=str(cfg.get("city_url") or ""),
    )


def desk_period_card(root: str | None = None, days: int = 7, now: dt.datetime | None = None) -> dict:
    """Read-only week (days=7) or month (days=30) totals per tower, with a cautious lower bound."""
    import desk_report

    base = _root(root)
    runs = _load_runs(base)
    day = _today() if now is None else now.astimezone(CT).date()
    first = day - dt.timedelta(days=max(1, int(days)) - 1)
    views, rows_by_bot = [], {}
    for spec in BOTS:
        view = _bot_view(spec, base, runs, day)
        views.append(view)
        try:
            rows, _n, _same = _report_closed_rows(spec, base, view, day, first_day=first)
        except Exception:  # noqa: BLE001
            rows = []
        rows_by_bot[spec["id"]] = rows
    return desk_report.period_card(views, rows_by_bot, first, day)


def venue_min_edge(venue: str, cfg: dict | None = None) -> float:
    return desk_profit.venue_min_edge(venue, cfg or load_settings(), DEFAULTS["min_edge"])


def correlation_blocks(
    root: str | None,
    bot_id: str,
    side: str,
    edge=None,
    bots: list | None = None,
) -> str:
    """Return a human reason when a correlated open book blocks this fill."""
    cfg = load_settings(root)
    rows = bots
    if rows is None:
        # Lightweight: rebuild bot views without full snapshot recursion.
        runs = _load_runs(root)
        day = _today()
        rows = [_bot_view(spec, root, runs, day) for spec in BOTS]
    open_rows = desk_profit.open_risk_factor_rows(rows)
    return desk_profit.correlation_veto_reason(
        bot_id, side, edge, open_rows, cfg.get("correlation_pairs")
    )


def kelly_lite_dollars(
    prob,
    edge,
    cfg: dict | None = None,
    open_risk_used: float = 0.0,
    ask=None,
    starve_mult: float = 1.0,
) -> float:
    cfg = cfg or DEFAULTS
    curve = paper_stake_dollars(prob, cfg)
    return desk_profit.kelly_lite_dollars(
        prob,
        edge,
        cfg=cfg,
        open_risk_used=open_risk_used,
        ask=ask,
        curve_dollars=curve,
        starve_mult=starve_mult,
    )


def tower_open_risk(bot_id: str, root: str | None = None, bots: list | None = None) -> float:
    """Open risk currently used by one tower (paper positions)."""
    rows = bots
    if rows is None:
        try:
            rows = snapshot(root)["bots"]
        except Exception:
            rows = []
    for bot in rows or []:
        if bot.get("id") == bot_id and not bot.get("shadow_only"):
            try:
                return float(bot.get("open_risk") or 0.0)
            except (TypeError, ValueError):
                return 0.0
    return 0.0


def tower_budget_blocks(
    bot_id: str,
    stake: float,
    root: str | None = None,
    cfg: dict | None = None,
    bots: list | None = None,
) -> str:
    """Block a fill that would blow this tower's soft risk share (desk cap still hard)."""
    cfg = cfg or load_settings(root)
    try:
        import desk_more
        used = tower_open_risk(bot_id, root=root, bots=bots)
        return desk_more.tower_budget_blocks(bot_id, used, stake, cfg)
    except Exception:
        return ""


def stake_dollars_for(
    bot_id: str,
    prob,
    edge=None,
    cfg: dict | None = None,
    open_risk_used: float = 0.0,
    ask=None,
    root: str | None = None,
    vol_kwargs: dict | None = None,
    return_plan: bool = False,
):
    """Unified stake: Kelly-lite → expectancy starve → vol/learn adapt.

    All bots share adapt: play safe on high volatility; size up only when the
    tower's own settled record is consistently ≥80% accurate with Wilson CI.
    Set return_plan=True to also get the adapt plan for prove-it drawers.
    Phase 1: also soft-cap by per-tower risk budget share of desk open-risk.
    """
    cfg = cfg or (load_settings(root) if root is not None else dict(DEFAULTS))
    starve_mult = 1.0
    history = []
    bot_open = 0.0
    if root is not None:
        try:
            runs = _load_runs(root)
            day = _today()
            for spec in BOTS:
                if spec["id"] != bot_id:
                    continue
                view = _bot_view(spec, root, runs, day)
                history = list(view.get("history") or [])
                try:
                    bot_open = float(view.get("open_risk") or 0.0)
                except (TypeError, ValueError):
                    bot_open = 0.0
                exp = desk_profit.bot_expectancy(
                    history,
                    window_days=int(cfg.get("expectancy_window_days") or 20),
                )
                starve_mult = float(desk_profit.starve_state(exp, cfg).get("starve_factor") or 1.0)
                break
        except Exception:
            starve_mult = 1.0
    base = kelly_lite_dollars(
        prob, edge, cfg=cfg, open_risk_used=open_risk_used, ask=ask, starve_mult=starve_mult
    )
    empty_plan = {"mult": 1.0, "play_safe": False, "play_big": False, "notes": [], "vol": {}, "perf": {}}
    try:
        import desk_adapt
        series = None
        if isinstance(vol_kwargs, dict):
            series = vol_kwargs.get("series")
        adapted, plan = desk_adapt.adapt_stake(
            base,
            history=history,
            window_days=int(cfg.get("expectancy_window_days") or 20),
            vol_kwargs=vol_kwargs or ({"ask": ask} if ask is not None else None),
            series=series,
        )
        if root is not None:
            try:
                desk_adapt.remember_vol(root, bot_id, str((vol_kwargs or {}).get("ticker") or bot_id), plan.get("vol") or {}, plan)
            except Exception:
                pass
        # Soft-cap by per-tower budget so one red tower cannot silence the desk.
        try:
            import desk_more
            info = desk_more.tower_budget_remaining(bot_id, bot_open, cfg)
            if info["cap"] > 0 and float(adapted) > info["left"] + 1e-9:
                plan = dict(plan)
                notes = list(plan.get("notes") or [])
                notes.append(
                    f"tower budget cap {info['left']:.2f} left of {info['cap']:.2f}"
                )
                plan["notes"] = notes
                plan["tower_budget"] = info
                adapted = float(info["left"])
                if 0 < adapted < 1.0:
                    adapted = 0.0
        except Exception:
            pass
        # Phase 10: profit-lock harvest — 0.5× after Chicago-week firm target.
        try:
            import desk_roi_plan
            pl_mult = float(desk_roi_plan.profit_lock_size_mult(root))
            if pl_mult < 1.0 - 1e-12:
                plan = dict(plan)
                notes = list(plan.get("notes") or [])
                notes.append(f"profit-lock harvest → {pl_mult:.2f}× size")
                plan["notes"] = notes
                plan["profit_lock_mult"] = pl_mult
                adapted = round(float(adapted) * pl_mult, 2)
                if 0 < adapted < 1.0:
                    adapted = 0.0
        except Exception:
            pass
        # Phase 2: adapt A/B ledger — what stake would have been without adapt.
        try:
            import desk_phase2
            plan = dict(plan)
            plan["stake_flat"] = round(float(base), 2)
            plan["stake_adapt"] = round(float(adapted), 2)
            if root is not None:
                desk_phase2.record_adapt_ab(
                    root,
                    bot=bot_id,
                    ticker=str((vol_kwargs or {}).get("ticker") or ""),
                    stake_flat=float(base),
                    stake_adapt=float(adapted),
                    mult=float(plan.get("mult") or 1.0),
                    regime=str((plan.get("vol") or {}).get("regime") or ""),
                    play_safe=bool(plan.get("play_safe")),
                    play_big=bool(plan.get("play_big")),
                    fill_id=str((vol_kwargs or {}).get("fill_id") or ""),
                )
        except Exception:
            pass
        if return_plan:
            return float(adapted), plan
        return float(adapted)
    except Exception:
        capped = float(base)
        try:
            import desk_more
            info = desk_more.tower_budget_remaining(bot_id, bot_open, cfg)
            if info["cap"] > 0:
                capped = min(capped, float(info["left"]))
                if 0 < capped < 1.0:
                    capped = 0.0
        except Exception:
            pass
        try:
            import desk_roi_plan
            pl_mult = float(desk_roi_plan.profit_lock_size_mult(root))
            if pl_mult < 1.0 - 1e-12:
                capped = round(float(capped) * pl_mult, 2)
                if 0 < capped < 1.0:
                    capped = 0.0
                empty_plan = dict(empty_plan)
                empty_plan["profit_lock_mult"] = pl_mult
                empty_plan["notes"] = list(empty_plan.get("notes") or []) + [
                    f"profit-lock harvest → {pl_mult:.2f}× size"
                ]
        except Exception:
            pass
        if return_plan:
            return capped, empty_plan
        return capped


def bot_expectancy(history, window_days: int = 20) -> dict:
    return desk_profit.bot_expectancy(history, window_days=window_days)


def shadow_account_path(root: str, bot_id: str, variant_id: str) -> str:
    folder = next((b["folder"] for b in BOTS if b["id"] == bot_id), None)
    if not folder:
        raise RuntimeError(f"unknown bot {bot_id}")
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", variant_id)[:40]
    return _under(root, folder, f"shadow_{safe}_account.json")


def load_shadow_account(root: str, bot_id: str, variant_id: str) -> dict:
    path = shadow_account_path(root, bot_id, variant_id)
    data = _read_json(path) or {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("cash", 100.0)
    data.setdefault("open", [])
    data.setdefault("closed", [])
    data["paper_only"] = True
    data["shadow"] = True
    data["shadow_id"] = variant_id
    return data


def save_shadow_account(root: str, bot_id: str, variant_id: str, state: dict) -> None:
    path = shadow_account_path(root, bot_id, variant_id)
    payload = dict(state)
    payload["paper_only"] = True
    payload["shadow"] = True
    payload["shadow_id"] = variant_id
    _write_json(path, payload)


def shadow_profiles(cfg: dict | None = None) -> list:
    cfg = cfg or DEFAULTS
    shadow = cfg.get("shadow") if isinstance(cfg.get("shadow"), dict) else {}
    if not shadow.get("enabled", True):
        return []
    rows = []
    for bot_id, profiles in shadow.items():
        if bot_id == "enabled" or not isinstance(profiles, list):
            continue
        for prof in profiles:
            if isinstance(prof, dict) and prof.get("id"):
                rows.append({"bot": bot_id, **prof})
    return rows


def promote_shadow(
    root: str | None,
    bot_id: str,
    variant_id: str,
    who: str = "",
    *,
    force: bool = False,
) -> tuple:
    """Copy winning shadow venue_edge into pimp-bot-params.json overlay. Paper only.

    Requires promote_ready (n/EV bars) unless force=True. Never softens venue
    floors (BTC/commodity 0.05 / sports 0.06 / INX+DEX 0.02).
    """
    root = _root(root)
    cfg = load_settings(root)
    prof = None
    for row in shadow_profiles(cfg):
        if row.get("bot") == bot_id and row.get("id") == variant_id:
            prof = row
            break
    if not prof:
        return None, "Unknown shadow profile."
    state = load_shadow_account(root, bot_id, variant_id)
    exp = desk_profit.bot_expectancy(state.get("closed") or [], window_days=int(cfg.get("expectancy_window_days") or 20))
    if not force and not desk_profit.shadow_promote_ready(exp, prof.get("promote_after")):
        return None, (
            f"Shadow {variant_id} not ready "
            f"(n={exp.get('n')}, EV={exp.get('expectancy')})."
        )
    params = dict(prof.get("params") or {})
    venue_edge = desk_profit._num(params.get("venue_edge"))
    # Raise-only vs locked floors — refuse any soften.
    floors = desk_profit.venue_floors_locked().get("venues") or {}
    btc_floor = float(((floors.get("kalshi_btc15m") or {}).get("floor")) or 0.05)
    if venue_edge is not None and venue_edge + 1e-12 < btc_floor and bot_id == "btc15m":
        return None, f"cannot soften BTC venue_edge below floor {btc_floor}"
    path = _under(root, "pimp-bot-params.json")
    overlay = _read_json(path) or {}
    if not isinstance(overlay, dict):
        overlay = {}
    bot_overlay = dict(overlay.get(bot_id) or {})
    bot_overlay.update(params)
    bot_overlay["promoted_from_shadow"] = variant_id
    bot_overlay["promoted_at"] = central_text()
    bot_overlay["force_promoted"] = bool(force)
    overlay[bot_id] = bot_overlay
    _write_json(path, overlay)
    audit(root, who or "unknown", f"Promoted shadow {bot_id}/{variant_id}", None, bot_overlay)
    return overlay, None


def shadow_snapshot_rows(root: str, cfg: dict) -> list:
    rows = []
    for prof in shadow_profiles(cfg):
        bot_id = prof["bot"]
        variant = prof["id"]
        try:
            state = load_shadow_account(root, bot_id, variant)
        except Exception:
            continue
        closed = state.get("closed") if isinstance(state.get("closed"), list) else []
        open_rows = state.get("open") if isinstance(state.get("open"), list) else []
        exp = desk_profit.bot_expectancy(
            closed, window_days=int(cfg.get("expectancy_window_days") or 20)
        )
        rows.append({
            "bot": bot_id,
            "variant_id": variant,
            "active": True,
            "cash": float(state.get("cash") or 0),
            "open_count": len(open_rows),
            "n": exp.get("n") or 0,
            "expectancy": exp.get("expectancy"),
            "promote_ready": desk_profit.shadow_promote_ready(exp, prof.get("promote_after")),
            "params": dict(prof.get("params") or {}),
            "shadow_only": True,
        })
    return rows


def _enrich_bot_profit_fields(bot: dict, cfg: dict, capital: dict) -> dict:
    """Attach expectancy / starve / venue / sizing fields for city + staff."""
    if bot.get("present") is False:
        bot.setdefault("expectancy", None)
        bot.setdefault("expectancy_n", 0)
        bot.setdefault("starved", False)
        bot.setdefault("capital_weight", 0)
        bot.setdefault("venue_min_edge", None)
        bot.setdefault("sizing_mode", "none")
        bot.setdefault("shadow", None)
        return bot
    window = int(cfg.get("expectancy_window_days") or 20)
    exp = desk_profit.bot_expectancy(bot.get("history") or [], window_days=window)
    starve = desk_profit.starve_state(exp, cfg)
    tax = float(cfg.get("fill_adverse_tax") if cfg.get("fill_adverse_tax") is not None else desk_profit.FILL_ADVERSE_TAX)
    exp_taxed = desk_profit.bot_expectancy(bot.get("history") or [], window_days=window, fill_tax=tax)
    gate = desk_profit.gate_a(
        bot.get("history") or [],
        min_n=int(cfg.get("gate_a_min_n") or desk_profit.GATE_A_MIN_N),
        window_days=window,
        fill_tax=tax,
    )
    bot["expectancy"] = exp.get("expectancy")
    bot["expectancy_taxed"] = exp_taxed.get("expectancy")
    bot["expectancy_n"] = exp.get("n") or 0
    bot["expectancy_hit_rate"] = exp.get("hit_rate")
    bot["expectancy_window"] = exp.get("window")
    bot["fill_tax"] = tax
    bot["avg_win"] = exp.get("avg_win")
    bot["avg_loss"] = exp.get("avg_loss")
    bot["starved"] = bool(starve.get("starved"))
    bot["starve_reason"] = starve.get("starve_reason") or ""
    bot["starve_factor"] = starve.get("starve_factor")
    bot["gate_a"] = gate
    bot["capital_weight"] = float((capital.get("weights") or {}).get(bot.get("id"), 0) or 0)
    bot["venue_min_edge"] = desk_profit.bot_venue_edge(str(bot.get("id") or ""), cfg)
    if bot.get("id") == "wall-street":
        # A staffed floor has no market and no stake. Do not borrow the desk edge.
        bot["venue_min_edge"] = None
        bot["sizing_mode"] = "none"
        bot["capital_weight"] = 0
        bot["risk_factors_open"] = []
        return bot
    if bot.get("id") == "exclusive-set":
        bot["sizing_mode"] = "none"
        bot["capital_weight"] = 0
        bot["risk_factors_open"] = []
        return bot
    if str(bot.get("id") or "") in _ZERO_STAKE_IDS:
        bot["sizing_mode"] = "none"
        bot["capital_weight"] = 0
        bot["risk_factors_open"] = []
        return bot
    mode = str(cfg.get("sizing") or "kelly_lite")
    stake = (bot.get("plans") or {}).get("stake") or ""
    if stake.startswith("fixed"):
        bot["sizing_mode"] = "fixed"
    elif mode == "kelly_lite":
        bot["sizing_mode"] = "kelly_lite"
    else:
        bot["sizing_mode"] = "curve"
    factors = []
    for pos in bot.get("positions") or []:
        factor = pos.get("risk_factor") or desk_profit.risk_factor_for(
            str(bot.get("id") or ""), pos.get("side")
        )
        if factor and factor not in factors:
            factors.append(factor)
    bot["risk_factors_open"] = factors
    return bot


def snapshot(root: str | None = None, q: str = "", filt: str = "all", page: int = 1) -> dict:
    root = _root(root)
    keep_closed_settlements(root)
    ensure_paper_accounts(root)
    cfg = load_settings(root)
    runs = _load_runs(root)
    day = _today()
    bots = [_bot_view(spec, root, runs, day) for spec in BOTS]
    if not any(b.get("id") == "kalshi-sized" for b in bots):
        bots.append(_sized_view())
    # Expectancy pass (needs history) before capital weights.
    prelim = []
    for bot in bots:
        window = int(cfg.get("expectancy_window_days") or 20)
        exp = desk_profit.bot_expectancy(bot.get("history") or [], window_days=window)
        starve = desk_profit.starve_state(exp, cfg)
        row = dict(bot)
        row["expectancy"] = exp.get("expectancy")
        row["starved"] = bool(starve.get("starved"))
        prelim.append(row)
    capital = desk_profit.capital_weights(prelim)
    for bot in bots:
        _enrich_bot_profit_fields(bot, cfg, capital)
    gate = entry_gate(root, bots)
    corr_pressure = sorted({
        r["factor"] for r in desk_profit.open_risk_factor_rows(bots)
    })
    shadow_rows = shadow_snapshot_rows(root, cfg)
    for bot in bots:
        bot["gates_hit"] = bot_gates_hit(bot, gate)
        matches = [s for s in shadow_rows if s.get("bot") == bot.get("id")]
        bot["shadow"] = matches[0] if matches else None
    # Vault cash, realized, and today use the same towers: the ones that spend
    # desk cash. Shadow books stay on their own line so a research win cannot
    # hide a desk loss, and a research loss is not dropped from its own book.
    money_bots = _desk_money_bots(bots)
    cashes = [b["cash"] for b in money_bots if b.get("cash") is not None]
    realized_rows = [b["realized"] for b in money_bots if b.get("realized") is not None]
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
    desk_row = _desk_row(public, cashes, realized_rows, last_check, gate, cfg, root)
    desk_row["bankroll"] = bankroll_roll(public)
    try:
        import desk_lifetime
        desk_lifetime.backfill_once(root)
        lifetime = desk_lifetime.lifetime_board(root, public)
        for bot in public:
            bot["lifetime"] = lifetime["bots"].get(bot.get("id") or "")
        desk_row["lifetime"] = lifetime["desk"]
    except Exception as exc:  # noqa: BLE001 - snapshot must never fail on the lifetime board
        desk_row["lifetime"] = {"paper_only": True, "error": type(exc).__name__}
    book = _book(public, q=q, filt=filt, page=page)
    changes = _changes(root, public)
    roi = roi_system(cfg, public)
    desk_row["ops"] = {
        **(desk_row.get("ops") or {}),
        "roi_ok": bool(roi.get("ok")),
        "roi_version": roi.get("version"),
        "correlation_pressure": corr_pressure,
        "starved_bots": [b["id"] for b in public if b.get("starved")],
        "shadow_count": len(shadow_rows),
    }
    desk_row["capital"] = capital
    desk_row["shadow_leaderboard"] = shadow_rows
    try:
        import kalshi_tape
        desk_row["kalshi_tape"] = kalshi_tape.tape_summary(root)
    except Exception as exc:  # noqa: BLE001 — snapshot must never fail closed on tape
        desk_row["kalshi_tape"] = {
            "paper_only": True,
            "error": type(exc).__name__,
            "tracked_series": [],
            "trade_count": 0,
            "recent": [],
        }
    try:
        import desk_brain
        desk_row["brain"] = desk_brain.brain_summary(root)
    except Exception as exc:  # noqa: BLE001
        desk_row["brain"] = {
            "paper_only": True,
            "error": type(exc).__name__,
            "decision_count": 0,
            "recent": [],
            "loop": ["observe", "score", "rank", "gate", "size", "fill", "learn"],
        }
    try:
        import kalshi_history
        desk_row["crypto_history"] = kalshi_history.history_summary(root)
    except Exception as exc:  # noqa: BLE001
        desk_row["crypto_history"] = {"paper_only": True, "error": type(exc).__name__, "snapshot_count": 0}
    try:
        import kalshi_parlay
        desk_row["crypto_parlays"] = kalshi_parlay.parlay_summary(
            kalshi_parlay.parlay_path(root)
        )
    except Exception as exc:  # noqa: BLE001
        desk_row["crypto_parlays"] = {"paper_only": True, "error": type(exc).__name__, "open_count": 0}
    try:
        import desk_adapt
        desk_row["adapt"] = desk_adapt.adapt_summary(root)
    except Exception as exc:  # noqa: BLE001
        desk_row["adapt"] = {"paper_only": True, "error": type(exc).__name__}
    try:
        import desk_more
        desk_row["more"] = desk_more.more_summary(root, bots=public, cfg=cfg)
        # Surface skip board on brain too when journal empty.
        if isinstance(desk_row.get("brain"), dict) and not desk_row["brain"].get("skip_leaderboard"):
            desk_row["brain"]["skip_leaderboard"] = desk_row["more"].get("skip_leaderboard")
        # E0 #3 — every tower card gets today's skip codes (by bot).
        by_bot = ((desk_row["more"].get("skip_leaderboard") or {}).get("by_bot") or {})
        for bot in public:
            raw = by_bot.get(bot.get("id") or "") or {}
            ranked = sorted(
                ((str(code), int(n)) for code, n in raw.items()),
                key=lambda kv: -kv[1],
            )[:5]
            bot["skip_board"] = [
                {"code": desk_more.stable_skip_code(code), "n": n}
                for code, n in ranked
            ]
    except Exception as exc:  # noqa: BLE001
        desk_row["more"] = {"paper_only": True, "error": type(exc).__name__}
    try:
        import desk_top25
        desk_row["top25"] = desk_top25.top25_summary(
            root, bots=public, health=timer_health(root), cfg=cfg,
        )
        # Gate B beside Gate A.
        desk_row["gate_b"] = desk_row["top25"].get("gate_b")
    except Exception as exc:  # noqa: BLE001
        desk_row["top25"] = {"paper_only": True, "error": type(exc).__name__}
        desk_row["gate_b"] = {"paper_only": True, "error": type(exc).__name__}
    try:
        import desk_phase2
        desk_row["phase2"] = desk_phase2.phase2_summary(root)
    except Exception as exc:  # noqa: BLE001
        desk_row["phase2"] = {"paper_only": True, "error": type(exc).__name__}
    try:
        import desk_phase3
        desk_row["phase3"] = desk_phase3.phase3_summary(root)
    except Exception as exc:  # noqa: BLE001
        desk_row["phase3"] = {"paper_only": True, "error": type(exc).__name__}
    # Gate A live-readiness + prove-it drawer + fill-tax board honesty.
    tax = float(cfg.get("fill_adverse_tax") if cfg.get("fill_adverse_tax") is not None else desk_profit.FILL_ADVERSE_TAX)
    try:
        import desk_master
        desk_row["master"] = desk_master.master_summary(
            root, bots=public, cfg=cfg, fill_tax=tax,
        )
    except Exception as exc:  # noqa: BLE001
        desk_row["master"] = {"paper_only": True, "error": type(exc).__name__}
    try:
        import teller_memory
        teller_memory.ingest_from_bots(root, public)
        desk_row["teller_memory"] = teller_memory.memory_summary(root)
        for bot in public:
            bot["memory_line"] = teller_memory.dialogue_line(root, bot.get("id"))
    except Exception as exc:  # noqa: BLE001
        desk_row["teller_memory"] = {"paper_only": True, "error": type(exc).__name__}
    tip = sports_tip_alarm_from_cache(root)
    desk_row["sports_tip"] = tip
    if isinstance(desk_row.get("master"), dict):
        desk_row["master"]["sports_tip"] = tip
    # Living upgrade city lights — insight≥3:1 swarm ratio for tellers / Masters HUD.
    try:
        living = None
        if isinstance(desk_row.get("master"), dict):
            plan = (desk_row["master"].get("roi_plan") or {})
            living = plan.get("living_upgrade") if isinstance(plan, dict) else None
        swarm = (living or {}).get("insight_swarm") if isinstance(living, dict) else None
        if not isinstance(swarm, dict):
            import desk_living
            swarm = desk_living.insight_swarm_ratio(root)
        lights = {
            "paper_only": True,
            "fee_floors_locked": True,
            "pass": bool(swarm.get("pass")),
            "ratio": swarm.get("ratio"),
            "insight_n": swarm.get("insight_n"),
            "betting_n": swarm.get("betting_n"),
            "min_ratio": swarm.get("min_ratio"),
            "color": "green" if swarm.get("pass") else "amber",
            "label": (
                f"Insight swarm {swarm.get('insight_n')}:{swarm.get('betting_n')} "
                f"(≥{swarm.get('min_ratio')}:1)"
            ),
            "note": swarm.get("note") or "",
        }
        desk_row["swarm_lights"] = lights
        if isinstance(desk_row.get("master"), dict):
            desk_row["master"]["swarm_lights"] = lights
        try:
            import teller_memory
            teller_memory.remember(
                root,
                kind="facts",
                text=f"swarm lights {lights['color']}: {lights['label']}"[:200],
                bot_id="desk",
            )
        except Exception:
            pass
    except Exception as exc:  # noqa: BLE001
        desk_row["swarm_lights"] = {"paper_only": True, "error": type(exc).__name__}
    # Completions KPI line for tellers / vault board.
    try:
        import desk_living
        comp = desk_living.completions_summary(root)
        desk_row["completions"] = comp
        if isinstance(desk_row.get("master"), dict):
            desk_row["master"]["completions"] = desk_row["master"].get("completions") or comp
        try:
            import teller_memory
            teller_memory.remember(
                root,
                kind="facts",
                text=(
                    f"eligible completions today "
                    f"{comp.get('eligible_completions_today') or 0} "
                    f"(pnl {float(comp.get('eligible_pnl_today') or 0):+.2f})"
                )[:200],
                bot_id="desk",
            )
        except Exception:
            pass
    except Exception as exc:  # noqa: BLE001
        desk_row["completions"] = {"paper_only": True, "error": type(exc).__name__}
    # Dual-control paper checklist HUD — live orders stay hard-disabled.
    try:
        import desk_roi_plan
        dc = desk_roi_plan.dual_control_status(root)
        desk_row["dual_control"] = dc
        if isinstance(desk_row.get("master"), dict):
            desk_row["master"]["dual_control"] = desk_row["master"].get("dual_control") or dc
            desk_row["master"]["live_orders_enabled"] = False
    except Exception as exc:  # noqa: BLE001
        desk_row["dual_control"] = {"paper_only": True, "live_orders_enabled": False, "error": type(exc).__name__}
    try:
        import desk_roi_plan
        ruin = desk_roi_plan.ruin_drill_status(root)
        desk_row["ruin_drill"] = ruin
        if isinstance(desk_row.get("master"), dict):
            desk_row["master"]["ruin_drill"] = desk_row["master"].get("ruin_drill") or ruin
    except Exception as exc:  # noqa: BLE001
        desk_row["ruin_drill"] = {"paper_only": True, "error": type(exc).__name__}
    # Skip taxonomy chip for teller rail / city HUD.
    try:
        import desk_living
        chip = desk_living.skip_taxonomy_chip(root)
        desk_row["skip_taxonomy"] = chip
        if isinstance(desk_row.get("master"), dict):
            desk_row["master"]["skip_taxonomy"] = chip
        try:
            import teller_memory
            if chip.get("top_code"):
                teller_memory.remember(
                    root,
                    kind="facts",
                    text=f"desk {chip.get('label')}"[:200],
                    bot_id="desk",
                )
        except Exception:
            pass
    except Exception as exc:  # noqa: BLE001
        desk_row["skip_taxonomy"] = {"paper_only": True, "error": type(exc).__name__}
    try:
        import desk_living
        gd = desk_living.green_day_board(root, bots=public)
        desk_row["green_day"] = gd
        if isinstance(desk_row.get("master"), dict):
            desk_row["master"]["green_day"] = desk_row["master"].get("green_day") or gd
    except Exception as exc:  # noqa: BLE001
        desk_row["green_day"] = {"paper_only": True, "error": type(exc).__name__}
    try:
        import desk_living
        fq = desk_living.firm_queue_chip(root)
        desk_row["firm_queue"] = fq
        if isinstance(desk_row.get("master"), dict):
            desk_row["master"]["firm_queue"] = desk_row["master"].get("firm_queue") or fq
    except Exception as exc:  # noqa: BLE001
        desk_row["firm_queue"] = {"paper_only": True, "error": type(exc).__name__}
    try:
        import desk_living
        ec = desk_living.empty_card_chip(root)
        nm = desk_living.near_miss_chip(root)
        desk_row["empty_card"] = ec
        desk_row["near_miss"] = nm
        if isinstance(desk_row.get("master"), dict):
            desk_row["master"]["empty_card"] = desk_row["master"].get("empty_card") or ec
            desk_row["master"]["near_miss"] = desk_row["master"].get("near_miss") or nm
    except Exception as exc:  # noqa: BLE001
        desk_row["empty_card"] = {"paper_only": True, "error": type(exc).__name__}
        desk_row["near_miss"] = {"paper_only": True, "error": type(exc).__name__}
    try:
        import desk_living
        th = desk_living.timer_heartbeat_chip(root)
        ga = desk_living.helper_gate_a_board(root)
        desk_row["timer_heartbeat"] = th
        desk_row["helper_gate_a"] = ga
        if isinstance(desk_row.get("master"), dict):
            desk_row["master"]["timer_heartbeat"] = (
                desk_row["master"].get("timer_heartbeat") or th
            )
            desk_row["master"]["helper_gate_a"] = (
                desk_row["master"].get("helper_gate_a") or ga
            )
    except Exception as exc:  # noqa: BLE001
        desk_row["timer_heartbeat"] = {"paper_only": True, "error": type(exc).__name__}
        desk_row["helper_gate_a"] = {"paper_only": True, "error": type(exc).__name__}
    try:
        import desk_living
        sr = desk_living.skip_regret_chip(root)
        hs = desk_living.hard_stop_chip(root)
        desk_row["skip_regret"] = sr
        desk_row["hard_stop"] = hs
        if isinstance(desk_row.get("master"), dict):
            desk_row["master"]["skip_regret"] = desk_row["master"].get("skip_regret") or sr
            desk_row["master"]["hard_stop"] = desk_row["master"].get("hard_stop") or hs
    except Exception as exc:  # noqa: BLE001
        desk_row["skip_regret"] = {"paper_only": True, "error": type(exc).__name__}
        desk_row["hard_stop"] = {"paper_only": True, "error": type(exc).__name__}
    try:
        import desk_living
        bl = desk_living.bleed_chip(root, bots=bots)
        cv = desk_living.clv_chip(root)
        desk_row["bleed"] = bl
        desk_row["clv"] = cv
        if isinstance(desk_row.get("master"), dict):
            desk_row["master"]["bleed"] = desk_row["master"].get("bleed") or bl
            desk_row["master"]["clv"] = desk_row["master"].get("clv") or cv
    except Exception as exc:  # noqa: BLE001
        desk_row["bleed"] = {"paper_only": True, "error": type(exc).__name__}
        desk_row["clv"] = {"paper_only": True, "error": type(exc).__name__}
    try:
        import desk_living
        tr = desk_living.tip_radar_chip(root)
        cn = desk_living.calib_nag_chip(root, bots=bots)
        desk_row["tip_radar"] = tr
        desk_row["calib_nag"] = cn
        if isinstance(desk_row.get("master"), dict):
            desk_row["master"]["tip_radar"] = desk_row["master"].get("tip_radar") or tr
            desk_row["master"]["calib_nag"] = desk_row["master"].get("calib_nag") or cn
    except Exception as exc:  # noqa: BLE001
        desk_row["tip_radar"] = {"paper_only": True, "error": type(exc).__name__}
        desk_row["calib_nag"] = {"paper_only": True, "error": type(exc).__name__}
    try:
        import desk_living
        iw = desk_living.injury_wire_chip(root)
        es = desk_living.eia_scout_chip(root)
        ls = desk_living.line_shopper_chip(root)
        bs = desk_living.btc_basis_scout_chip(root)
        nhl = desk_living.nhl_poisson_audit_chip(root)
        dv = desk_living.dvol_regime_chip(root)
        mx = desk_living.multi_ex_disagree_chip(root)
        fs = desk_living.funding_scout_chip(root)
        mh = desk_living.metals_heat_chip(root)
        eh = desk_living.energy_heat_chip(root)
        ib = desk_living.inx_band_occupancy_chip(root)
        e8 = desk_living.e8_pack_chips(root)
        desk_row["injury_wire"] = iw
        desk_row["eia_scout"] = es
        desk_row["line_shopper"] = ls
        desk_row["btc_basis_scout"] = bs
        desk_row["nhl_poisson_audit"] = nhl
        desk_row["dvol_regime"] = dv
        desk_row["multi_ex_disagree"] = mx
        desk_row["funding_scout"] = fs
        desk_row["metals_heat"] = mh
        desk_row["energy_heat"] = eh
        desk_row["inx_band_occupancy"] = ib
        desk_row.update(e8)
        if isinstance(desk_row.get("master"), dict):
            desk_row["master"]["injury_wire"] = desk_row["master"].get("injury_wire") or iw
            desk_row["master"]["eia_scout"] = desk_row["master"].get("eia_scout") or es
            desk_row["master"]["line_shopper"] = desk_row["master"].get("line_shopper") or ls
            desk_row["master"]["btc_basis_scout"] = (
                desk_row["master"].get("btc_basis_scout") or bs
            )
            desk_row["master"]["nhl_poisson_audit"] = (
                desk_row["master"].get("nhl_poisson_audit") or nhl
            )
            desk_row["master"]["dvol_regime"] = desk_row["master"].get("dvol_regime") or dv
            desk_row["master"]["multi_ex_disagree"] = (
                desk_row["master"].get("multi_ex_disagree") or mx
            )
            desk_row["master"]["funding_scout"] = (
                desk_row["master"].get("funding_scout") or fs
            )
            desk_row["master"]["metals_heat"] = desk_row["master"].get("metals_heat") or mh
            desk_row["master"]["energy_heat"] = desk_row["master"].get("energy_heat") or eh
            desk_row["master"]["inx_band_occupancy"] = (
                desk_row["master"].get("inx_band_occupancy") or ib
            )
            for name, chip in e8.items():
                desk_row["master"][name] = desk_row["master"].get(name) or chip
    except Exception as exc:  # noqa: BLE001
        desk_row["injury_wire"] = {"paper_only": True, "error": type(exc).__name__}
        desk_row["eia_scout"] = {"paper_only": True, "error": type(exc).__name__}
        desk_row["line_shopper"] = {"paper_only": True, "error": type(exc).__name__}
        desk_row["btc_basis_scout"] = {"paper_only": True, "error": type(exc).__name__}
        desk_row["nhl_poisson_audit"] = {"paper_only": True, "error": type(exc).__name__}
        desk_row["dvol_regime"] = {"paper_only": True, "error": type(exc).__name__}
        desk_row["multi_ex_disagree"] = {"paper_only": True, "error": type(exc).__name__}
        desk_row["funding_scout"] = {"paper_only": True, "error": type(exc).__name__}
        desk_row["metals_heat"] = {"paper_only": True, "error": type(exc).__name__}
        desk_row["energy_heat"] = {"paper_only": True, "error": type(exc).__name__}
        desk_row["inx_band_occupancy"] = {"paper_only": True, "error": type(exc).__name__}
        try:
            from helpers import e8_digest_pack
            for name in e8_digest_pack.HELPER_NAMES:
                desk_row[name] = {"paper_only": True, "error": type(exc).__name__}
        except Exception:
            pass
    try:
        import desk_living
        sh = desk_living.skip_historian_chip(root)
        dc = desk_living.distance_clerk_chip(root)
        qc = desk_living.quant_clerk_chip(root)
        desk_row["skip_historian"] = sh
        desk_row["distance_clerk"] = dc
        desk_row["quant_clerk"] = qc
        if isinstance(desk_row.get("master"), dict):
            desk_row["master"]["skip_historian"] = (
                desk_row["master"].get("skip_historian") or sh
            )
            desk_row["master"]["distance_clerk"] = (
                desk_row["master"].get("distance_clerk") or dc
            )
            desk_row["master"]["quant_clerk"] = (
                desk_row["master"].get("quant_clerk") or qc
            )
    except Exception as exc:  # noqa: BLE001
        desk_row["skip_historian"] = {"paper_only": True, "error": type(exc).__name__}
        desk_row["distance_clerk"] = {"paper_only": True, "error": type(exc).__name__}
        desk_row["quant_clerk"] = {"paper_only": True, "error": type(exc).__name__}
    try:
        import desk_living
        bk = desk_living.bookkeeper_chip(root)
        rp = desk_living.reporter_chip(root)
        sun = desk_living.sunday_packet_chip(root)
        bee = desk_living.empty_card_bee_chip(root)
        desk_row["bookkeeper"] = bk
        desk_row["reporter"] = rp
        desk_row["sunday_packet"] = sun
        desk_row["empty_card_bee"] = bee
        if isinstance(desk_row.get("master"), dict):
            desk_row["master"]["bookkeeper"] = desk_row["master"].get("bookkeeper") or bk
            desk_row["master"]["reporter"] = desk_row["master"].get("reporter") or rp
            desk_row["master"]["sunday_packet"] = (
                desk_row["master"].get("sunday_packet") or sun
            )
            desk_row["master"]["empty_card_bee"] = (
                desk_row["master"].get("empty_card_bee") or bee
            )
    except Exception as exc:  # noqa: BLE001
        desk_row["bookkeeper"] = {"paper_only": True, "error": type(exc).__name__}
        desk_row["reporter"] = {"paper_only": True, "error": type(exc).__name__}
        desk_row["sunday_packet"] = {"paper_only": True, "error": type(exc).__name__}
        desk_row["empty_card_bee"] = {"paper_only": True, "error": type(exc).__name__}
    try:
        import desk_living
        nmc = desk_living.near_miss_clerk_chip(root)
        hsc = desk_living.hard_stop_clerk_chip(root)
        blc = desk_living.bleed_clerk_chip(root, bots=bots)
        desk_row["near_miss_clerk"] = nmc
        desk_row["hard_stop_clerk"] = hsc
        desk_row["bleed_clerk"] = blc
        if isinstance(desk_row.get("master"), dict):
            desk_row["master"]["near_miss_clerk"] = (
                desk_row["master"].get("near_miss_clerk") or nmc
            )
            desk_row["master"]["hard_stop_clerk"] = (
                desk_row["master"].get("hard_stop_clerk") or hsc
            )
            desk_row["master"]["bleed_clerk"] = desk_row["master"].get("bleed_clerk") or blc
    except Exception as exc:  # noqa: BLE001
        desk_row["near_miss_clerk"] = {"paper_only": True, "error": type(exc).__name__}
        desk_row["hard_stop_clerk"] = {"paper_only": True, "error": type(exc).__name__}
        desk_row["bleed_clerk"] = {"paper_only": True, "error": type(exc).__name__}
    try:
        import desk_living
        stc = desk_living.skip_twin_clerk_chip(root)
        clc = desk_living.clv_closer_chip(root)
        tdc = desk_living.timer_digest_chip(root)
        desk_row["skip_twin_clerk"] = stc
        desk_row["clv_closer"] = clc
        desk_row["timer_digest"] = tdc
        if isinstance(desk_row.get("master"), dict):
            desk_row["master"]["skip_twin_clerk"] = (
                desk_row["master"].get("skip_twin_clerk") or stc
            )
            desk_row["master"]["clv_closer"] = desk_row["master"].get("clv_closer") or clc
            desk_row["master"]["timer_digest"] = desk_row["master"].get("timer_digest") or tdc
    except Exception as exc:  # noqa: BLE001
        desk_row["skip_twin_clerk"] = {"paper_only": True, "error": type(exc).__name__}
        desk_row["clv_closer"] = {"paper_only": True, "error": type(exc).__name__}
        desk_row["timer_digest"] = {"paper_only": True, "error": type(exc).__name__}
    try:
        import desk_living
        cal = desk_living.calendar_scanner_chip(root)
        ebo = desk_living.eia_blackout_chip(root)
        living_board = None
        if isinstance(desk_row.get("master"), dict):
            plan = (desk_row["master"].get("roi_plan") or {})
            living_board = plan.get("living_upgrade") if isinstance(plan, dict) else None
        compact = desk_living.living_compact_card(root, bots=bots, board=living_board)
        desk_row["calendar_scanner"] = cal
        desk_row["eia_blackout"] = ebo
        desk_row["living_compact"] = compact
        if isinstance(desk_row.get("master"), dict):
            desk_row["master"]["calendar_scanner"] = (
                desk_row["master"].get("calendar_scanner") or cal
            )
            desk_row["master"]["eia_blackout"] = (
                desk_row["master"].get("eia_blackout") or ebo
            )
            desk_row["master"]["compact"] = desk_row["master"].get("compact") or compact
    except Exception as exc:  # noqa: BLE001
        desk_row["calendar_scanner"] = {"paper_only": True, "error": type(exc).__name__}
        desk_row["eia_blackout"] = {"paper_only": True, "error": type(exc).__name__}
        desk_row["living_compact"] = {"paper_only": True, "error": type(exc).__name__}
    try:
        import desk_living
        pulse = desk_living.clerk_pulse_chip(root)
        dcc = desk_living.dual_control_chip(root)
        rdc = desk_living.ruin_drill_chip(root)
        desk_row["clerk_pulse"] = pulse
        desk_row["dual_control_chip"] = dcc
        desk_row["ruin_drill_chip"] = rdc
        if isinstance(desk_row.get("master"), dict):
            desk_row["master"]["clerk_pulse"] = desk_row["master"].get("clerk_pulse") or pulse
            desk_row["master"]["dual_control_chip"] = (
                desk_row["master"].get("dual_control_chip") or dcc
            )
            desk_row["master"]["ruin_drill_chip"] = (
                desk_row["master"].get("ruin_drill_chip") or rdc
            )
    except Exception as exc:  # noqa: BLE001
        desk_row["clerk_pulse"] = {"paper_only": True, "error": type(exc).__name__}
        desk_row["dual_control_chip"] = {"paper_only": True, "error": type(exc).__name__}
        desk_row["ruin_drill_chip"] = {"paper_only": True, "error": type(exc).__name__}
    try:
        import desk_living
        cc = desk_living.completions_chip(root)
        desk_row["completions_chip"] = cc
        if isinstance(desk_row.get("master"), dict):
            desk_row["master"]["completions_chip"] = (
                desk_row["master"].get("completions_chip") or cc
            )
        try:
            import teller_memory
            if int(cc.get("eligible_completions_today") or 0) > 0:
                teller_memory.remember(
                    root,
                    kind="facts",
                    text=str(cc.get("label") or "completions")[:200],
                    bot_id="desk",
                )
        except Exception:
            pass
    except Exception as exc:  # noqa: BLE001
        desk_row["completions_chip"] = {"paper_only": True, "error": type(exc).__name__}
    try:
        import desk_living
        tl = desk_living.teller_living_chip(root, bots=bots, remember=True)
        desk_row["teller_living"] = tl
        desk_row["living_memory_line"] = tl.get("memory_line")
        desk_row["fee_floors_assert"] = desk_living.fee_floors_assert(root)
        desk_row["betting_expand_gate"] = desk_living.betting_expand_gate(
            root, bots=bots, remember=True,
        )
        # Snapshot path observes doctor without rewriting the weekly marker.
        desk_row["living_doctor"] = desk_living.living_doctor(root, record=False)
        desk_row["doctor_age"] = desk_living.doctor_age_chip(root)
        desk_row["ritual_observe"] = desk_living.ritual_observe_chip(root)
        # Prefer Masters-built soft_copy when present; else build observe draft.
        ritual_soft = None
        if isinstance(desk_row.get("master"), dict):
            ritual_soft = desk_row["master"].get("ritual_soft_copy") or desk_row["master"].get(
                "ritual_discord"
            )
        if not ritual_soft and isinstance(desk_row.get("ritual_observe"), dict):
            r = desk_row["ritual_observe"]
            ritual_soft = (
                f"**Masters ritual** (paper · floors locked · live=False)\n"
                f"ritual_ok={r.get('ritual_ok')} exit_ok={r.get('exit_ok')} "
                f"doctor_fresh={r.get('doctor_fresh')}\n"
                f"{r.get('label') or 'ritual observe'}\n"
                f"_staff paste only · never auto-posts · never enables live_"
            )
        desk_row["ritual_soft_copy"] = ritual_soft
        desk_row["ritual_discord"] = ritual_soft
        doctor_soft = None
        if isinstance(desk_row.get("master"), dict):
            doctor_soft = desk_row["master"].get("doctor_soft_copy")
        if not doctor_soft:
            age = desk_row.get("doctor_age") if isinstance(desk_row.get("doctor_age"), dict) else {}
            r = desk_row.get("ritual_observe") if isinstance(desk_row.get("ritual_observe"), dict) else {}
            fresh = r.get("doctor_fresh")
            if fresh is None and age:
                fresh = not bool(age.get("stale"))
            doctor_soft = (
                f"**Living doctor age** (paper · floors locked · live=False)\n"
                f"doctor={'fresh' if fresh else 'stale' if fresh is False else 'n/a'} "
                f"doctor_fresh={fresh}\n"
                f"{age.get('label') or 'doctor age'}\n"
                f"ritual draft: make living-ritual-discord\n"
                f"_staff paste only · never auto-posts · never enables live_"
            )
        desk_row["doctor_soft_copy"] = doctor_soft
        desk_row["doctor_fresh"] = (
            (desk_row.get("ritual_observe") or {}).get("doctor_fresh")
            if isinstance(desk_row.get("ritual_observe"), dict)
            else None
        )
        desk_row["living_ai"] = desk_living.living_ai_health(root, bots=bots)
        desk_row["feature_quiet"] = desk_living.feature_store_quiet_alert(root)
        desk_row["feature_quiet_pager"] = desk_living.feature_quiet_pager(root)
        if isinstance(desk_row.get("master"), dict):
            desk_row["master"]["teller_living"] = (
                desk_row["master"].get("teller_living") or tl
            )
            desk_row["master"]["fee_floors_assert"] = (
                desk_row["master"].get("fee_floors_assert")
                or desk_row["fee_floors_assert"]
            )
            desk_row["master"]["betting_expand_gate"] = (
                desk_row["master"].get("betting_expand_gate")
                or desk_row["betting_expand_gate"]
            )
            desk_row["master"]["living_doctor"] = (
                desk_row["master"].get("living_doctor")
                or desk_row["living_doctor"]
            )
            desk_row["master"]["ritual_observe"] = (
                desk_row["master"].get("ritual_observe") or desk_row["ritual_observe"]
            )
            desk_row["master"]["ritual_soft_copy"] = (
                desk_row["master"].get("ritual_soft_copy") or ritual_soft
            )
            desk_row["master"]["ritual_discord"] = (
                desk_row["master"].get("ritual_discord") or ritual_soft
            )
            desk_row["master"]["doctor_soft_copy"] = (
                desk_row["master"].get("doctor_soft_copy") or doctor_soft
            )
            if desk_row["master"].get("doctor_fresh") is None:
                desk_row["master"]["doctor_fresh"] = desk_row.get("doctor_fresh")
            desk_row["master"]["living_ai"] = (
                desk_row["master"].get("living_ai") or desk_row["living_ai"]
            )
            desk_row["master"]["feature_quiet"] = (
                desk_row["master"].get("feature_quiet") or desk_row["feature_quiet"]
            )
            desk_row["master"]["feature_quiet_pager"] = (
                desk_row["master"].get("feature_quiet_pager")
                or desk_row["feature_quiet_pager"]
            )
        # Prefer living line on desk teller when present.
        for bot in bots or []:
            if isinstance(bot, dict) and str(bot.get("id") or "") == "desk":
                bot["memory_line"] = tl.get("memory_line") or bot.get("memory_line")
    except Exception as exc:  # noqa: BLE001
        desk_row["teller_living"] = {"paper_only": True, "error": type(exc).__name__}
        desk_row["betting_expand_gate"] = {"paper_only": True, "error": type(exc).__name__}
    try:
        import desk_living
        gaps = desk_living.dual_control_gaps_page(root)
        hc = desk_living.hillclimb_chip(root)
        inv = desk_living.digest_inventory(root)
        desk_row["dual_control_gaps"] = gaps
        desk_row["hillclimb_chip"] = hc
        desk_row["digest_inventory"] = inv
        if isinstance(desk_row.get("master"), dict):
            desk_row["master"]["dual_control_gaps"] = (
                desk_row["master"].get("dual_control_gaps") or gaps
            )
            desk_row["master"]["hillclimb_chip"] = (
                desk_row["master"].get("hillclimb_chip") or hc
            )
            desk_row["master"]["digest_inventory"] = (
                desk_row["master"].get("digest_inventory") or inv
            )
    except Exception as exc:  # noqa: BLE001
        desk_row["dual_control_gaps"] = {"paper_only": True, "error": type(exc).__name__}
        desk_row["hillclimb_chip"] = {"paper_only": True, "error": type(exc).__name__}
        desk_row["digest_inventory"] = {"paper_only": True, "error": type(exc).__name__}
    try:
        desk_row["venue_floors"] = desk_profit.venue_floors_locked(cfg)
    except Exception as exc:  # noqa: BLE001
        desk_row["venue_floors"] = {"paper_only": True, "error": type(exc).__name__}
    gate_rows = []
    prove_rows = []
    for bot in public:
        ga = bot.get("gate_a") if isinstance(bot.get("gate_a"), dict) else desk_profit.gate_a(
            bot.get("history") or [],
            min_n=int(cfg.get("gate_a_min_n") or desk_profit.GATE_A_MIN_N),
            fill_tax=tax,
        )
        gate_rows.append({
            "bot": bot.get("id"),
            "ready": bool(ga.get("ready")),
            "n": ga.get("n"),
            "expectancy_taxed": ga.get("expectancy_taxed"),
            "reason": ga.get("reason"),
        })
        for pos in list(bot.get("positions") or [])[:8]:
            prove = pos.get("prove") if isinstance(pos.get("prove"), dict) else {}
            if not prove and not pos.get("adapt_mult") and not pos.get("ticker"):
                continue
            prove_rows.append({
                "bot": bot.get("id"),
                "ticker": pos.get("ticker"),
                "side": pos.get("side"),
                "ask": pos.get("ask"),
                "fill": pos.get("fill"),
                "fill_untaxed": pos.get("fill_untaxed"),
                "edge": pos.get("edge"),
                "prove": prove or {
                    "adapt_mult": pos.get("adapt_mult"),
                    "adapt_notes": pos.get("adapt_notes"),
                    "play_safe": pos.get("play_safe"),
                    "play_big": pos.get("play_big"),
                    "cushion": pos.get("cushion"),
                    "sigma": pos.get("sigma"),
                    "history_n": pos.get("history_n"),
                    "history_hit": pos.get("history_hit"),
                    "fill_tax": tax,
                },
            })
    desk_row["gate_a"] = {
        "paper_only": True,
        "fill_tax": tax,
        "min_n": int(cfg.get("gate_a_min_n") or desk_profit.GATE_A_MIN_N),
        "any_ready": any(r.get("ready") for r in gate_rows),
        "bots": gate_rows,
        "note": "Gate A = taxed paper EV ≥ 0 with enough settles. Not a live switch.",
    }
    desk_row["prove_it"] = {
        "paper_only": True,
        "fill_tax_default": tax,
        "open": prove_rows[:40],
    }
    desk_row["ops"] = {
        **(desk_row.get("ops") or {}),
        "fill_tax": tax,
        "gate_a_ready_bots": [r["bot"] for r in gate_rows if r.get("ready")],
    }
    # City cards (plan 806-885). Read only: plain lines for each tower card.
    try:
        import city_card
        city_card.attach(
            public, desk_row, cfg, specs=BOTS, auto=AUTO, saved_auto=_load_auto(root),
            day=day, now=dt.datetime.now(dt.timezone.utc), ct_date=_ct_date,
        )
    except Exception as exc:  # noqa: BLE001 - snapshot must never fail on the city cards
        desk_row["city"] = {"paper_only": True, "real_money": "off", "error": type(exc).__name__}
    return {
        "paper_only": True,
        # City snapshot schema version (snapshot_schema.py). New keys are fine; a renamed key bumps it.
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "banner": "PAPER ONLY. This desk does not trade real money. No Kalshi API key, no wallet, no live order. The same paper checks also run on a timer.",
        "roi_system": roi,
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
            "fill_tax": "Board fills add a +1¢ adverse tax vs stored ask so ROI stays honest.",
            "gate_a": "Gate A = taxed paper EV ≥ 0 with enough settles — not a live switch.",
            "prove_it": "Prove-it shows cushion/σ/fee/adapt mult/history for each open fill.",
            "skip_leaderboard": "Top reasons we did not buy today. WEEKEND on Sat/Sun is normal, not broken.",
            "tower_budgets": "Soft per-tower share of desk open-risk so one tower cannot silence the others.",
            "near_miss": "Shadow-only near-miss lane studies one soft gate miss without eating desk risk.",
            "clv": "Sports closing-line value: entry fair minus later fair/close.",
            "hillclimb": "Change one sizing/edge lever per week; revert if taxed EV falls two weeks.",
            "fill_tax_education": (
                "Board fills add a +1¢ adverse tax vs stored ask so ROI stays honest. "
                "Untaxed paper wins are not live-ready."
            ),
            "gate_b": "Gate B = peak-to-trough drawdown within bound with enough settles — readiness only.",
            "top25": "Top-25 shortlist hooks: skip-regret, budgets, watchdog, playbooks, doctor.",
            "phase3": (
                "Phase 3 expansion: KXBTCD ladder companion scoring + paper parlay "
                "joint EV with same-direction crypto correlation haircut."
            ),
            "master": (
                "Trading Masters scoreboard (M1–M7): taxed EV vs volume. "
                "Stub — no profit guarantee; fee floors unchanged."
            ),
            "guest": "Guest mode (?guest=1) is read-only — no staff actions.",
            "teller_memory": (
                "Shared vault memory (facts/mistakes/wins) grounded in paper cards — "
                "consciousness v0, not a live advisor."
            ),
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
    if bot_id == "kalshi-sized" and not _kalshi_paper(root, "kalshi-sized-paper"):
        return "Sized Kalshi config is not paper_mode. This desk will not start it."
    if bot_id == "memecoin" and not _meme_paper(root):
        return "Memecoin PAPER is not True. This desk will not start it."
    if bot_id == "coinbase-spot" and not _coinbase_paper(root):
        return "Coinbase spot config is not paper-only. This desk will not start it."
    if bot_id == "btc-carry" and not _btc_carry_paper(root):
        return "BTC carry config is not paper-only. This desk will not start it."
    if bot_id == "wall-street" and not _wall_street_paper(root):
        return "Wall Street config is not paper-only. This desk will not start it."
    if bot_id == "exclusive-set" and not _exclusive_set_paper(root):
        return "Exclusive set config is not paper-only. This desk will not start it."
    if bot_id in _ZERO_STAKE_IDS and not _zero_stake_paper(root, bot_id):
        return "Shadow logger config is not paper-only. This desk will not start it."
    return ""


def _zero_stake_paper(root: str, bot_id: str) -> bool:
    folder = next((row["folder"] for row in BOTS if row["id"] == bot_id), "")
    cfg = _read_json(_under(root, folder, "config.json")) or {}
    return cfg.get("paper_only") is True and cfg.get("live_orders") is not True


def _exclusive_set_paper(root: str) -> bool:
    cfg = _read_json(_under(root, "exclusive-set-paper", "config.json")) or {}
    return cfg.get("paper_only") is True and cfg.get("live_orders") is not True


def _wall_street_paper(root: str) -> bool:
    cfg = _read_json(_under(root, "wall-street-paper", "config.json")) or {}
    return cfg.get("paper_only") is True and cfg.get("live_orders") is not True


def _coinbase_paper(root: str) -> bool:
    cfg = _read_json(_under(root, "coinbase-spot-paper", "config.json")) or {}
    return cfg.get("paper_only") is True and cfg.get("live_orders") is not True


def _btc_carry_paper(root: str) -> bool:
    cfg = _read_json(_under(root, "btc-carry-paper", "config.json")) or {}
    return cfg.get("paper_only") is True and cfg.get("live_orders") is not True


def _log_tape(root: str | None, bot_id: str) -> None:
    """Tally plus settled-window lines for the 15-minute towers. Log only."""
    try:
        import desk_tape_log
        if bot_id not in desk_tape_log.TAPE_BOTS:
            return
        base = _root(root)
        log.info("%s", desk_tape_log.tally_line(base, bot_id))
        for line in desk_tape_log.window_lines(base):
            log.info("%s", line)
        for line in desk_tape_log.trade_lines(base):
            log.info("%s", line)
    except Exception as exc:  # noqa: BLE001 - logging must never stop the timer
        log.info("tape log skipped for %s: %s", bot_id, type(exc).__name__)


def run_bot(bot_id: str, action: str = "run", root: str | None = None, manual: bool = False,
            stake=None, prob=None, shadow_profile: dict | None = None) -> dict:
    root = _root(root)
    keep_closed_settlements(root)
    ensure_paper_accounts(root)
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
    if bot_paused(root, bot_id) and not shadow_profile:
        return {"ok": False, "error": "Paused.", "blocked": True, "summary": "Paused."}
    warning = _calendar_warning(root, bot_id) if spec["entry"] or bot_id == "btc15m" else ""
    block_entries = False
    gate_note = ""
    shadow_env = None
    if shadow_profile:
        variant = str(shadow_profile.get("id") or "")
        account = shadow_account_path(root, bot_id, variant)
        if not os.path.isfile(account):
            save_shadow_account(root, bot_id, variant, {
                "cash": 100.0, "open": [], "closed": [], "paper_only": True,
            })
        shadow_env = {
            "id": variant,
            "account": account,
            "params": dict(shadow_profile.get("params") or {}),
        }
    if spec["entry"] and not shadow_profile:
        gate = entry_gate(root)
        if gate:
            if bot_id in _MANAGE_WHEN_GATED:
                # Exits/settles still run; scripts honor DESK_BLOCK_ENTRIES for new buys.
                block_entries = True
                gate_note = gate
            else:
                would = [{"what": "unknown", "why": gate, "bot": bot_id}]
                row = {"at": _now(), "ok": False, "blocked": True, "summary": gate, "exit": None, "action": action,
                       "would_have": would}
                _save_run(root, bot_id, row)
                return {"ok": False, "error": gate, "blocked": True, "summary": gate, "would_have": would}
        if stake not in (None, "") and not block_entries:
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
        started = time.monotonic()
        try:
            proc = subprocess.Popen(
                [sys.executable, script, *spec["argv"][1:]],
                cwd=cwd,
                env=_child_env(
                    block_entries=block_entries,
                    shadow=shadow_env,
                    block_reason=gate_note,
                ),
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
        if block_entries and gate_note:
            summary = _clip_out(
                f"Desk entry_gate blocked new paper buys; exits still ran.\n{gate_note}\n{summary}"
            )
        ok = (not timed_out) and proc.returncode == 0
        # INX settle overlaps the sized/S&P scan window. Empty settle must not
        # clobber densified NO TRADE / late-σ CARD tip (#497 twin densify).
        kept_scan_tip = False
        if (
            ok
            and action == "settle"
            and bot_id in ("kalshi-sp", "kalshi-sized")
            and _inx_bland_settle_summary(summary)
            and inx_in_run_window(bot_id)
        ):
            prev_row = _load_runs(root).get(bot_id)
            prev = prev_row if isinstance(prev_row, dict) else {}
            prev_sum = str(prev.get("summary") or "")
            if _inx_densified_scan_summary(prev_sum):
                summary = prev_sum
                kept_scan_tip = True
        row = {"at": _now(), "ok": ok, "summary": summary, "exit": proc.returncode, "action": action,
               "warning": warning, "entries_blocked": bool(block_entries),
               "secs": round(time.monotonic() - started, 2)}
        if kept_scan_tip:
            row["kept_scan_tip"] = True
            row["action"] = "run"  # tip stays scan-truth while settle found nothing open
        _save_run(root, bot_id, row)
        if not summary:
            summary = "The script finished with no output."
        error = "" if ok else (summary.splitlines()[-1] if summary else "The paper script did not finish cleanly.")
        error = public_error(error)
        if manual:
            _mark_manual(root, bot_id)
        spec_row = next(b for b in BOTS if b["id"] == bot_id)
        _note_state_mtime(root, bot_id, spec_row["folder"], spec_row.get("state") or "")
        return {
            "ok": ok, "error": error, "summary": summary, "exit": proc.returncode,
            "warning": warning, "entries_blocked": bool(block_entries),
            "kept_scan_tip": kept_scan_tip,
        }
    finally:
        lock.release()


def timer_text() -> str:
    """Plain schedule for the desk. No forecast and no profit language."""
    return (
        "On a timer, America/Chicago. Sports gap about every 3 minutes (dual lanes); "
        "about every 45 seconds when a cached tip is inside T−15 (fee-aware still). "
        "BTC 15-minute signal about every 60 seconds — scores every open KXBTC15M window "
        "and syncs the Kalshi public trade tape for desk series. "
        "Commodity 15m about every 90 seconds. "
        "Kalshi morning brief once at 8:00 AM, dry run. "
        "Kalshi paper scans forced at 12:05, 13:05, and 13:40 CT (up to 3/day). "
        "Kalshi paper settle once at 4:00 PM. "
        "Coinbase spot shadow about every 5 minutes (public candles, no desk cash). "
        "BTC carry shadow about every 5 minutes (public funding archive, no desk cash). "
        "Exclusive set shadow about every 5 minutes (public Kalshi books, log only, no buy). "
        "Memecoin about every 3 minutes (manage exits, then scan; dual lanes; stop-bleed); "
        "about every 2 minutes when open paper needs manage. "
        "Commodity about every 90 seconds; about every 60 seconds when ≥2 series are open. "
        "No edge is a finished check with zero paper trades. "
        "Numbers only move while the Discord bot paper timer is alive."
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
            if slot["id"] == "sports-gap":
                gap = _sports_auto_gap_sec(root, gap, now=now)
            elif slot["id"] == "memecoin":
                gap = _meme_auto_gap_sec(root, gap)
            elif slot["id"] == "commodity-15m":
                gap = _commodity_auto_gap_sec(root, gap)
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


def _inx_run_should_retry(result: dict) -> bool:
    """NO TRADE / empty scan inside an INX window — retry; do not burn the day stamp.

    Max 1 fill/day stays stone in the tower risk_manager. Late-σ refuse ends
    retries for that slot (no legal entry left before 15:00 settle).
    """
    if result.get("blocked"):
        return True
    if not result.get("ok"):
        return False
    summary = str(result.get("summary") or "").lower()
    if "refuse late" in summary and "entry floor" in summary:
        return False
    if "no trade" in summary:
        return True
    if "no paper buy" in summary:
        return True
    if "no candidate cleared" in summary:
        return True
    return False


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
    # INX run windows: NO TRADE must not consume the daily stamp — fair/band can
    # clear later in-window (stone late-σ / fee / max-1 stay locked).
    if (
        slot.get("id") in ("kalshi-sp", "kalshi-sized")
        and slot.get("action") == "run"
        and _inx_run_should_retry(result)
    ):
        saved[key + ":retry"] = _iso(now)
        saved.pop(key, None)
        return
    # A finished check (fill / late-σ / hard fail) waits for the next clock slot.
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
    keep_closed_settlements(root)
    ensure_paper_accounts(root)
    if now is None:
        now = dt.datetime.now(dt.timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=dt.timezone.utc)
    # Phase 0: settle open 15m history labels ≤1× / 10m so adapt can learn without stalling.
    try:
        import kalshi_history
        marker = _under(root, "desk_settle_harness_at.txt")
        due = True
        if os.path.isfile(marker):
            try:
                age = now.timestamp() - os.path.getmtime(marker)
                due = age >= 600
            except OSError:
                due = True
        if due:
            kalshi_history.settle_open_windows(root, limit=12)
            try:
                with open(marker, "w", encoding="utf-8") as handle:
                    handle.write(_iso(now) + "\n")
            except OSError:
                pass
    except Exception:
        pass
    # E3 helper — calendar scanner digest (never places).
    try:
        from helpers import calendar_scanner
        calendar_scanner.run_if_due(root, now)
    except Exception:
        pass
    # Living upgrade — refresh insight clerk digests on a 5m cadence (observe-only).
    try:
        from helpers import clerk_pulse
        clerk_pulse.run_if_due(root, now)
    except Exception:
        pass
    touch_heartbeat(root, now)
    # Broke towers only: once per Chicago day in the early window, reload ammo + reset P&L.
    # Winners and towers with open paper stay untouched.
    results = list(run_midnight_broke_reload(root, now))
    slots = due_slots(now, root)
    saved = _load_auto(root)
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
            "entries_blocked": bool(result.get("entries_blocked")),
            "error": result.get("error") or "",
            "summary": result.get("summary") or "",
        }
        head = _clean(row["summary"] or row["error"], 180)
        tail = traceback_tail(row["summary"])
        if tail and not row["ok"]:
            head = _clean(tail, 300)
        if result.get("error") == _BUSY:
            log.info("paper timer %s %s still running", bot_id, action)
        elif row["blocked"]:
            log.info("paper timer %s %s skipped, desk limit already hit: %s", bot_id, action, head)
        elif row["ok"]:
            log.info("paper timer %s %s finished: %s", bot_id, action, head or "no output")
            _log_tape(root, bot_id)
        else:
            log.warning("paper timer %s %s did not finish: %s", bot_id, action, head or "no output")
        return row

    if slots:
        workers = max(1, min(4, len(slots)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_one, slot) for slot in slots]
            for fut in as_completed(futures):
                results.append(fut.result())
    # Shadow BTC variants — same timer cadence, separate cash, never desk-gated.
    cfg = load_settings(root)
    for prof in shadow_profiles(cfg):
        if prof.get("bot") != "btc15m":
            continue
        key = f"shadow:btc15m:{prof.get('id')}"
        prev = _parsed(saved.get(key) or "")
        if prev is not None and (now - prev).total_seconds() < 300:
            continue
        result = run_bot("btc15m", "run", root, shadow_profile=prof)
        saved[key] = _iso(now)
        results.append({
            "bot": "btc15m",
            "action": "shadow",
            "shadow_id": prof.get("id"),
            "ok": bool(result.get("ok")),
            "blocked": bool(result.get("blocked")),
            "entries_blocked": False,
            "error": result.get("error") or "",
            "summary": result.get("summary") or "",
        })
    # Auto shadow densify — catch-up (~10m) and forced tick (~15m / ops alert).
    # Best-effort; never arms LIVE / force / tip invent; Discord never auto-posts.
    try:
        import desk_roi_plan
        catchup_marker = _under(root, "desk_shadow_catchup_at.txt")
        tick_marker = _under(root, "desk_shadow_tick_at.txt")
        catchup_due = True
        tick_due = True
        if os.path.isfile(catchup_marker):
            try:
                catchup_due = (now.timestamp() - os.path.getmtime(catchup_marker)) >= 600
            except OSError:
                catchup_due = True
        if os.path.isfile(tick_marker):
            try:
                tick_due = (now.timestamp() - os.path.getmtime(tick_marker)) >= 900
            except OSError:
                tick_due = True
        force_tick = False
        try:
            ops = desk_roi_plan.shadow_ops_alerts(root)
            alerts = ops.get("alerts") or []
            force_tick = any(
                a in ("shadow_edge08_missing", "heartbeat_missing", "heartbeat_stale")
                for a in alerts
            )
        except Exception:
            force_tick = False
        if tick_due or force_tick:
            # Includes catch-up + sports-gap smoke; paper-only.
            tick_out = run_shadow_tick(root, now, run_bots=True)
            try:
                with open(tick_marker, "w", encoding="utf-8") as handle:
                    handle.write(_iso(now) + "\n")
            except OSError:
                pass
            try:
                with open(catchup_marker, "w", encoding="utf-8") as handle:
                    handle.write(_iso(now) + "\n")
            except OSError:
                pass
            results.append({
                "bot": "shadow-tick",
                "action": "auto",
                "ok": bool(tick_out.get("ok")),
                "blocked": False,
                "entries_blocked": False,
                "error": tick_out.get("error") or "",
                "summary": (
                    f"auto shadow-tick labeled_n={tick_out.get('labeled_n')} "
                    f"sports={sum(1 for r in (tick_out.get('shadow_rows') or []) if r.get('bot') == 'sports-gap')} "
                    f"commodity={sum(1 for r in (tick_out.get('shadow_rows') or []) if r.get('bot') == 'commodity-15m')}"
                )[:180],
                "live_orders_enabled": False,
                "shadow_rows": tick_out.get("shadow_rows") or [],
            })
        elif catchup_due:
            catchup = desk_roi_plan.run_shadow_catchup(root)
            try:
                with open(catchup_marker, "w", encoding="utf-8") as handle:
                    handle.write(_iso(now) + "\n")
            except OSError:
                pass
            results.append({
                "bot": "shadow-catchup",
                "action": "auto",
                "ok": bool(catchup.get("ok")),
                "blocked": False,
                "entries_blocked": False,
                "error": catchup.get("error") or "",
                "summary": (
                    f"auto catch-up labeled_n={catchup.get('labeled_n')} "
                    f"backfilled={catchup.get('backfilled')} repaired={catchup.get('repaired')}"
                )[:180],
                "live_orders_enabled": False,
            })
    except Exception:
        pass
    if results:
        _atomic_write(auto_path(root), json.dumps(saved, indent=2) + "\n")
    # Phase 0/1 recycle: remember sticky opens so staff/ops can free risk.
    try:
        import desk_more
        bots = snapshot(root).get("bots") or []
        sticky = desk_more.sticky_positions(bots)
        desk_more.remember_sticky(root, sticky)
    except Exception:
        bots = []
        sticky = []
    # Top25 #5 — global rank minute across recent brain candidates.
    try:
        import desk_brain
        import desk_top25
        summary = desk_brain.brain_summary(root)
        cand = []
        for row in summary.get("recent") or []:
            if not isinstance(row, dict):
                continue
            if row.get("action") not in ("observe", "buy", "candidate", "skip"):
                continue
            if row.get("edge") is None:
                continue
            cand.append({
                "bot": row.get("bot"),
                "ticker": row.get("ticker"),
                "side": row.get("side"),
                "edge": row.get("edge"),
                "confidence": row.get("confidence"),
                "depth": row.get("depth"),
                "stake_est": row.get("stake_est") or 20,
                "venue": {
                    "btc15m": "kalshi_btc15m",
                    "commodity-15m": "kalshi_commodity15m",
                    "sports-gap": "kalshi_sports",
                }.get(str(row.get("bot") or ""), ""),
            })
        cfg = load_settings(root)
        used = 0.0
        for b in bots or []:
            if b.get("shadow_only"):
                continue
            try:
                used += float(b.get("open_risk") or 0)
            except (TypeError, ValueError):
                pass
        left = max(0.0, float(cfg.get("max_open_risk") or 100) - used)
        if cand:
            desk_top25.global_rank_minute(cand, left, root=root)
        desk_top25.sticky_settle_sla(len(sticky), root=root)
    except Exception:
        pass
    return results


def run_due(root: str | None = None, now: dt.datetime | None = None) -> dict:
    """One manual pass of whatever is due. It does not wait for the timer, and it is rate limited."""
    root = _root(root)
    if not _rate_ok(root, "*due*"):
        return {"ok": False, "error": "Run now is rate limited. Wait 30 seconds.", "rows": []}
    rows = run_scheduled(now, root)
    _mark_manual(root, "*due*")
    return {"ok": True, "error": "", "rows": rows}


def run_shadow_tick(
    root: str | None = None,
    now: dt.datetime | None = None,
    *,
    run_bots: bool = True,
) -> dict:
    """One-shot paper shadow smoke — densify edge08 + sports + commodity + carry + coinbase + meme + INX.

    Forces a DESK_SHADOW edge08 pass (bypasses 5m cadence), smokes sports-gap,
    commodity-15m, btc-carry, coinbase-spot, memecoin, and INX paper settles
    (hard-stop / t-final / t-stop / near-miss densify), touches heartbeat,
    best-effort history settle. Never sets LIVE_ORDERS. Floors stay locked.
    Writes tick+catchup markers so doctor isn't false-stale.
    """
    root = _root(root)
    if now is None:
        now = dt.datetime.now(dt.timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=dt.timezone.utc)
    keep_closed_settlements(root)
    ensure_paper_accounts(root)
    # Ensure edge08 shadow account materializes even if bot script is offline.
    edge08_path = None
    try:
        edge08_path = shadow_account_path(root, "btc15m", "edge08")
        if not os.path.isfile(edge08_path):
            save_shadow_account(root, "btc15m", "edge08", load_shadow_account(root, "btc15m", "edge08"))
    except Exception:
        edge08_path = None
    history_settle = {"settled": 0, "attempted": 0}
    history_path = None
    try:
        import kalshi_history
        history_path = kalshi_history.ensure_history_file(root)
        history_settle = kalshi_history.settle_open_windows(root, limit=12)
    except Exception as exc:  # noqa: BLE001
        history_settle = {"settled": 0, "attempted": 0, "error": type(exc).__name__}
    touch_heartbeat(root, now)
    shadow_rows: list = []
    if run_bots:
        cfg = load_settings(root)
        for prof in shadow_profiles(cfg):
            if prof.get("bot") != "btc15m":
                continue
            # Force one pass — ignore cadence (smoke densify).
            try:
                result = run_bot("btc15m", "run", root, shadow_profile=prof)
            except Exception as exc:  # noqa: BLE001
                result = {"ok": False, "error": type(exc).__name__, "blocked": False, "summary": ""}
            shadow_rows.append({
                "bot": "btc15m",
                "action": "shadow",
                "shadow_id": prof.get("id"),
                "ok": bool(result.get("ok")),
                "blocked": bool(result.get("blocked")),
                "error": result.get("error") or "",
                "summary": result.get("summary") or "",
            })
        # Sports-gap paper smoke — densify hard-stop / t-final / near-miss without
        # waiting for the 180s due-slot. Main paper account; no DESK_SHADOW env;
        # never LIVE.
        try:
            sports = run_bot("sports-gap", "run", root)
        except Exception as exc:  # noqa: BLE001
            sports = {"ok": False, "error": type(exc).__name__, "blocked": False, "summary": ""}
        shadow_rows.append({
            "bot": "sports-gap",
            "action": "shadow-smoke",
            "shadow_id": None,
            "ok": bool(sports.get("ok")),
            "blocked": bool(sports.get("blocked")),
            "error": sports.get("error") or "",
            "summary": sports.get("summary") or "",
            "paper_only": True,
            "live_orders_enabled": False,
        })
        # Commodity-15m paper smoke — densify time-stop without waiting for 90s slot.
        # Main paper account; no DESK_SHADOW env; never LIVE.
        try:
            commodity = run_bot("commodity-15m", "run", root)
        except Exception as exc:  # noqa: BLE001
            commodity = {"ok": False, "error": type(exc).__name__, "blocked": False, "summary": ""}
        shadow_rows.append({
            "bot": "commodity-15m",
            "action": "shadow-smoke",
            "shadow_id": None,
            "ok": bool(commodity.get("ok")),
            "blocked": bool(commodity.get("blocked")),
            "error": commodity.get("error") or "",
            "summary": commodity.get("summary") or "",
            "paper_only": True,
            "live_orders_enabled": False,
        })
        # BTC carry shadow sleeve — densify hold/flat CARD without waiting for 300s slot.
        # Shadow-only; spends no desk cash; never LIVE.
        try:
            carry = run_bot("btc-carry", "run", root)
        except Exception as exc:  # noqa: BLE001
            carry = {"ok": False, "error": type(exc).__name__, "blocked": False, "summary": ""}
        shadow_rows.append({
            "bot": "btc-carry",
            "action": "shadow-smoke",
            "shadow_id": None,
            "ok": bool(carry.get("ok")),
            "blocked": bool(carry.get("blocked")),
            "error": carry.get("error") or "",
            "summary": carry.get("summary") or "",
            "paper_only": True,
            "live_orders_enabled": False,
        })
        # Coinbase spot shadow sleeve — densify long-only / min_z CARD (300s twin of carry).
        # Shadow-only; spends no desk cash; never LIVE; fee floor 0.05 stays locked.
        try:
            coinbase = run_bot("coinbase-spot", "run", root)
        except Exception as exc:  # noqa: BLE001
            coinbase = {"ok": False, "error": type(exc).__name__, "blocked": False, "summary": ""}
        shadow_rows.append({
            "bot": "coinbase-spot",
            "action": "shadow-smoke",
            "shadow_id": None,
            "ok": bool(coinbase.get("ok")),
            "blocked": bool(coinbase.get("blocked")),
            "error": coinbase.get("error") or "",
            "summary": coinbase.get("summary") or "",
            "paper_only": True,
            "live_orders_enabled": False,
        })
        # Memecoin paper smoke — densify tip CARD between 180s AUTO slots so why
        # is not blank while the tower is armed (sports/coinbase twin). Main
        # paper account; no DESK_SHADOW env; never LIVE; fee floor 0.05 locked.
        try:
            meme = run_bot("memecoin", "run", root)
        except Exception as exc:  # noqa: BLE001
            meme = {"ok": False, "error": type(exc).__name__, "blocked": False, "summary": ""}
        shadow_rows.append({
            "bot": "memecoin",
            "action": "shadow-smoke",
            "shadow_id": None,
            "ok": bool(meme.get("ok")),
            "blocked": bool(meme.get("blocked")),
            "error": meme.get("error") or "",
            "summary": meme.get("summary") or "",
            "paper_only": True,
            "live_orders_enabled": False,
        })
        # INX paper smoke — settle outside scan windows; during AUTO run windows
        # smoke the real paper scan so tip why is not settle "No open paper"
        # while the tower is in-window (#496 firm-queue twin). Never LIVE.
        now_ct = now.astimezone(CT) if isinstance(now, dt.datetime) else dt.datetime.now(CT)
        for inx_bot in ("kalshi-sp", "kalshi-sized"):
            in_run = any(
                isinstance(slot, dict)
                and str(slot.get("id") or "") == inx_bot
                and str(slot.get("action") or "") == "run"
                and _window_open(now_ct, slot)
                for slot in AUTO
            )
            action = "run" if in_run else "settle"
            try:
                inx = run_bot(inx_bot, action, root)
            except Exception as exc:  # noqa: BLE001
                inx = {"ok": False, "error": type(exc).__name__, "blocked": False, "summary": ""}
            shadow_rows.append({
                "bot": inx_bot,
                "action": "scan-smoke" if in_run else "settle-smoke",
                "shadow_id": None,
                "ok": bool(inx.get("ok")),
                "blocked": bool(inx.get("blocked")),
                "error": inx.get("error") or "",
                "summary": inx.get("summary") or "",
                "paper_only": True,
                "live_orders_enabled": False,
            })
    catchup = {}
    try:
        import desk_roi_plan
        catchup = desk_roi_plan.run_shadow_catchup(root)
    except Exception as exc:  # noqa: BLE001
        catchup = {"ok": False, "error": type(exc).__name__, "labeled_n": 0, "backfilled": 0, "repaired": 0}
    # CLI tick path writes markers (same as run_scheduled) so doctor isn't false-stale.
    try:
        stamp = _iso(now) + "\n"
        for name in ("desk_shadow_tick_at.txt", "desk_shadow_catchup_at.txt"):
            try:
                with open(_under(root, name), "w", encoding="utf-8") as handle:
                    handle.write(stamp)
            except OSError:
                pass
    except Exception:
        pass
    ops = {}
    try:
        import desk_roi_plan
        ops = desk_roi_plan.shadow_ops_alerts(root)
    except Exception:
        ops = {}
    return {
        "ok": True,
        "paper_only": True,
        "observe_only": True,
        "auto_promote": False,
        "fee_floors_locked": True,
        "live_orders_enabled": False,
        "live": False,
        "heartbeat_touched": True,
        "shadow_edge08_path": edge08_path,
        "shadow_edge08_present": bool(edge08_path and os.path.isfile(edge08_path)),
        "history_path": history_path,
        "history_present": bool(history_path and os.path.isfile(history_path)),
        "history_settle": history_settle,
        "shadow_rows": shadow_rows,
        "sports_smoked": any(r.get("bot") == "sports-gap" for r in shadow_rows),
        "commodity_smoked": any(r.get("bot") == "commodity-15m" for r in shadow_rows),
        "btc_carry_smoked": any(r.get("bot") == "btc-carry" for r in shadow_rows),
        "coinbase_smoked": any(r.get("bot") == "coinbase-spot" for r in shadow_rows),
        "memecoin_smoked": any(r.get("bot") == "memecoin" for r in shadow_rows),
        "inx_sp_smoked": any(r.get("bot") == "kalshi-sp" for r in shadow_rows),
        "inx_sized_smoked": any(r.get("bot") == "kalshi-sized" for r in shadow_rows),
        "catchup": catchup,
        "shadow_ops": ops,
        "labeled_n": catchup.get("labeled_n"),
        "backfilled": catchup.get("backfilled"),
        "repaired": catchup.get("repaired"),
        "note": (
            "Shadow tick — paper DESK_SHADOW edge08 + sports-gap + commodity-15m "
            "+ btc-carry + coinbase-spot + memecoin + INX scan-or-settle smoke "
            "+ catch-up densify. Never LIVE_ORDERS; never tip invent; Discord "
            "never auto-posts."
        ),
    }


def _unlink(path: str) -> bool:
    """Delete a paper file. A settlement symlink and the volume file both go."""
    if os.path.islink(path):
        target = os.path.realpath(path)
        os.remove(path)
        if target and os.path.isfile(target):
            os.remove(target)
        return True
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
        try:
            import desk_lifetime
            spec = next(b for b in BOTS if b["id"] == bot_id)
            view = _bot_view(spec, root, _load_runs(root), _today())
            desk_lifetime.bank_before_reset(root, view, _today().isoformat(), source="reset")
        except Exception:  # noqa: BLE001 - a reset still runs; the audit row stays
            pass
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
        elif bot_id in ("kalshi-sp", "kalshi-sized"):
            for name in ("paper_state.json", "Trade_Ledger.md"):
                if _unlink(_under(root, folder, name)):
                    removed.append(name)
        elif bot_id == "memecoin":
            for name in ("positions.json", "trades.csv", "checks.csv"):
                if _unlink(_under(root, folder, name)):
                    removed.append(name)
        elif bot_id == "btc15m":
            if _unlink(_under(root, folder, "paper_account.json")):
                removed.append("paper_account.json")
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


def paper_fill(bid, ask, *, adverse: float | None = None):
    """Paper fills pay the ask (+ optional adverse tax for board honesty). Mid never used."""
    ask_n = _num(ask)
    if ask_n is None:
        return None
    tax = desk_profit.FILL_ADVERSE_TAX if adverse is None else float(adverse)
    if tax < 0:
        tax = 0.0
    # Snapshot boards show taxed fill; ledger bots still store raw ask separately.
    return round(min(0.99, ask_n + tax), 4)


def edge_after_fee(fair, ask):
    fair_n, ask_n = _num(fair), _num(ask)
    if fair_n is None or ask_n is None:
        return None
    return round(fair_n - ask_n - kalshi_fee(ask_n), 4)


SPORTS_CASH = 100.0
OLD_SPORTS_CASH = 14.0


def lift_sports_starter(state: dict) -> bool:
    """Raise the empty $14 sports starter to $100. Any other paper cash stays."""
    if not isinstance(state, dict):
        return False
    if state.get("open") or state.get("closed"):
        return False
    cash = _num(state.get("cash"))
    if cash is None or abs(cash - OLD_SPORTS_CASH) > 0.001:
        return False
    state["cash"] = SPORTS_CASH
    state["paper_only"] = True
    return True


def lift_memecoin_broke(state: dict) -> bool:
    """Do not mint meme cash. A low balance is the real result, not a reason to refill.

    Levi, 2026-11-13: pretend cash that appears on its own hides the loss.
    """
    return False
    if not isinstance(state, dict):
        return False
    if state.get("open"):
        return False
    cash = _num(state.get("cash_usd"))
    if cash is None or cash >= 10.0 - 1e-9:
        return False
    state["cash_usd"] = 100.0
    state["paper_only"] = True
    state["reloaded_from"] = round(cash, 2)
    state["reloaded_at"] = central_text()
    return True


# Starter cash / minimum “ammo” for midnight broke-tower reloads (Chicago day).
TOWER_STARTER_CASH = {
    "sports-gap": 100.0,
    "btc15m": 100.0,
    "commodity-15m": 100.0,
    "memecoin": 100.0,
    "kalshi-sp": 500.0,
    "kalshi-sized": 500.0,
    "coinbase-spot": 500.0,
    "btc-carry": 500.0,
    "sports-sharp-lag": 500.0,
    "fed-watch": 500.0,
    "exclusive-set": 0.0,
    "wall-street": 0.0,
}
TOWER_MIN_AMMO = {
    "sports-gap": 10.0,
    "btc15m": 10.0,
    "commodity-15m": 10.0,
    "memecoin": 10.0,
    "kalshi-sp": 20.0,
    "kalshi-sized": 20.0,
    "coinbase-spot": 25.0,
    "btc-carry": 500.0,
    "sports-sharp-lag": 25.0,
    "fed-watch": 25.0,
    "exclusive-set": 0.0,
    "wall-street": 0.0,
}

# Paper shadows that log a missing series and buy nothing. Filled at import.
_ZERO_STAKE_IDS = frozenset()


def _install_shadow_loggers() -> None:
    """Register the active log-only towers (paused ones stay off). Does not change a buy plan."""
    global BOTS, AUTO, SETTLEMENT_FILES, _ZERO_STAKE_IDS
    import shadow_missing

    _ZERO_STAKE_IDS = frozenset(spec["id"] for spec in shadow_missing.ACTIVE)
    bots = list(BOTS)
    insert_at = next(i for i, row in enumerate(bots) if row["id"] == "wall-street")
    for offset, spec in enumerate(shadow_missing.ACTIVE):
        bots.insert(insert_at + offset, {
            "id": spec["id"],
            "name": spec["name"],
            "folder": spec["folder"],
            "script": "bot.py",
            "blurb": (
                "Shadow logger. Reads the public series and logs the open book. "
                "A series the public API does not list is named on the card and skipped. "
                "Buys nothing and takes no stake."
            ),
            "state": "paper_account.json",
            "kind": "log",
            "log": "",
            "empty": "No paper account yet. A check writes paper_account.json.",
            "shadow_only": True,
        })
        ACCOUNT_FILES[spec["id"]] = "paper_account.json"
        ACTIONS[spec["id"]] = {
            "run": {"argv": ("bot.py",), "entry": False, "timeout": 45, "label": "Run one check"},
        }
        BOT_PLANS[spec["id"]] = {
            "buy": [
                "The tower does not buy. It logs and leaves the book flat",
                "Shadow only — spends no desk cash and takes no tower risk share",
                spec["rule"],
                "A series the public API does not list is named on the card and skipped. No ticker, fill, or fair is invented",
                "Stake stays 0",
            ],
            "sell": [
                "Nothing is open, so there is nothing to sell",
                "A log line is not a position. Staff review is the backstop",
            ],
            "failsafes": [
                "Paper only. No key and no desk cash",
                "Stake stays 0. No tower_risk_budgets share while shadow_only",
                spec["floor_line"],
                "Incubation n≥50 before any desk share. This build does not buy",
                "Pause file",
            ],
            "exit_quality": "partial",
            "entry_gated": True,
            "stake": "none",
        }
        ROI_POLICY["waivers"][spec["id"]] = ["shadow_only"]
        ROI_POLICY["target_exit_quality"][spec["id"]] = "partial"
        TOWER_STARTER_CASH[spec["id"]] = 0.0
        TOWER_MIN_AMMO[spec["id"]] = 0.0
    BOTS = tuple(bots)
    slots = list(AUTO)
    after = next(i for i, slot in enumerate(slots) if slot.get("id") == "exclusive-set")
    for offset, spec in enumerate(shadow_missing.ACTIVE):
        slots.insert(after + 1 + offset, {
            "id": spec["id"],
            "action": "run",
            "every_sec": 300,
        })
    AUTO = tuple(slots)
    extra = []
    for spec in shadow_missing.ACTIVE:
        extra.append(f"{spec['folder']}/paper_account.json")
        extra.append(f"{spec['folder']}/evidence.jsonl")
    SETTLEMENT_FILES = tuple(list(SETTLEMENT_FILES) + extra)


_install_shadow_loggers()


def _new_tower_ids() -> set:
    import new_towers

    return set(new_towers.BY_ID)


def _install_new_towers() -> None:
    """Register the new Kalshi shadow towers from new_towers.py. Shadow only, $25 ticket."""
    global BOTS, AUTO, SETTLEMENT_FILES, _ZERO_STAKE_IDS
    import new_towers

    # Research rows (calibration lab) hold no cash and never buy.
    _ZERO_STAKE_IDS = frozenset(set(_ZERO_STAKE_IDS) | set(new_towers.RESEARCH))
    bots = list(BOTS)
    insert_at = next(i for i, row in enumerate(bots) if row["id"] == "wall-street")
    for offset, spec in enumerate(new_towers.ACTIVE):
        bots.insert(insert_at + offset, {
            "id": spec["id"],
            "name": spec["name"],
            "folder": spec["folder"],
            "script": "bot.py",
            "blurb": spec["blurb"],
            "state": "paper_account.json",
            "kind": "shadow",
            "category": spec.get("kind") or "macro",
            "log": "",
            "empty": "No paper account yet. A check writes paper_account.json.",
            "shadow_only": True,
        })
        ACCOUNT_FILES[spec["id"]] = "paper_account.json"
        research = bool(spec.get("research"))  # like exclusive-set: a zero-stake logger
        ACTIONS[spec["id"]] = {
            "run": {"argv": ("bot.py",), "entry": True, "timeout": int(spec.get("timeout") or 60),
                    "label": "Run one check"},
        }
        if research:
            BOT_PLANS[spec["id"]] = {
                "buy": list(spec["buy"]),
                "sell": list(spec["sell"]),
                "failsafes": list(spec["failsafes"]) + ["Zero cash, never buys", "Pause file"],
                "exit_quality": "partial",
                "entry_gated": True,
                "stake": "none",
            }
            ROI_POLICY["waivers"][spec["id"]] = ["research_only", "shadow_only"]
            ROI_POLICY["target_exit_quality"][spec["id"]] = "partial"
            TOWER_STARTER_CASH[spec["id"]] = 0.0
            TOWER_MIN_AMMO[spec["id"]] = 0.0
            continue
        BOT_PLANS[spec["id"]] = {
            "buy": list(spec["buy"]),
            "sell": list(spec["sell"]),
            "failsafes": list(spec["failsafes"]) + ["No tower_risk_budgets share while shadow_only", "Pause file"],
            "exit_quality": "partial",
            "entry_gated": True,
            "stake": "fixed-25",
        }
        ROI_POLICY["waivers"][spec["id"]] = ["fixed_ticket_25", "shadow_only"]
        ROI_POLICY["target_exit_quality"][spec["id"]] = "partial"
        TOWER_STARTER_CASH[spec["id"]] = 500.0
        TOWER_MIN_AMMO[spec["id"]] = 25.0
    BOTS = tuple(bots)
    slots = list(AUTO)
    after = max(i for i, slot in enumerate(slots) if "every_sec" in slot)
    for offset, spec in enumerate(new_towers.ACTIVE):
        slots.insert(after + 1 + offset, {
            "id": spec["id"],
            "action": "run",
            "every_sec": int(spec.get("every_sec") or 300),
        })
    AUTO = tuple(slots)
    SETTLEMENT_FILES = tuple(
        list(SETTLEMENT_FILES)
        + [f"{spec['folder']}/paper_account.json" for spec in new_towers.ACTIVE]
        + [f"{spec['folder']}/{name}" for spec in new_towers.ACTIVE for name in spec.get("keep") or ()]
        # The fair-vs-ask research log feeds the calibration lab and the what-if lab.
        + [f"{spec['folder']}/{name}" for spec in new_towers.ACTIVE if not spec.get("research")
           for name in ("research.jsonl", "research.jsonl.1")]
    )


_install_new_towers()


def midnight_path(root: str | None = None) -> str:
    return _under(root, "pimp-midnight.json")


def tower_doing_good(bot: dict) -> bool:
    """Winners / healthy towers stay untouched at midnight.

    A mid-day cash top-up does not count as “doing good” if the book is still
    underwater — those towers get a full P&L reset at Chicago midnight.
    """
    if not isinstance(bot, dict) or not bot.get("present"):
        return True
    bot_id = str(bot.get("id") or "")
    # Carry pays the 0.15% entry leg once ($499.25 of a $500 sleeve). That is the
    # hold, not a broke book. A midnight reload would flatten it and the next
    # check would pay the fee again.
    if bot_id == "btc-carry":
        return True
    # Zero-stake logger. A midnight reload would mint cash this tower does not have.
    if bot_id == "exclusive-set":
        return True
    if bot_id in _ZERO_STAKE_IDS:
        return True
    starter = float(TOWER_STARTER_CASH.get(bot_id) or 100.0)
    min_ammo = float(TOWER_MIN_AMMO.get(bot_id) or 10.0)
    if int(bot.get("open_count") or 0) > 0:
        return True
    cash = _num(bot.get("cash"))
    if cash is None:
        return True
    today = float(bot.get("today") or 0.0)
    realized = _num(bot.get("realized"))
    if realized is None:
        realized = 0.0
    # Green book with at least starter cash (or better).
    if cash + 1e-9 >= starter and realized >= -1e-9 and today >= -1e-9:
        return True
    # Still armed and not underwater — leave the working bankroll alone.
    if cash + 1e-9 >= min_ammo and realized >= -1e-9 and today >= -1e-9:
        return True
    return False


def tower_needs_midnight_reload(bot: dict) -> bool:
    """Never. A midnight refill hides a real loss and mints pretend cash.

    Levi, 2026-11-13: the traded book stays. Out of ammo means it cannot buy, not that
    the scoreboard goes back to zero.
    """
    return False
    if not isinstance(bot, dict) or not bot.get("present"):
        return False
    bot_id = str(bot.get("id") or "")
    if bot_id == "btc-carry":
        return False
    if bot_id == "exclusive-set":
        return False
    if bot_id in _ZERO_STAKE_IDS:
        return False
    if int(bot.get("open_count") or 0) > 0:
        return False
    if tower_doing_good(bot):
        return False
    starter = float(TOWER_STARTER_CASH.get(bot_id) or 100.0)
    min_ammo = float(TOWER_MIN_AMMO.get(bot_id) or 10.0)
    cash = _num(bot.get("cash"))
    if cash is None:
        return False
    today = float(bot.get("today") or 0.0)
    realized = _num(bot.get("realized"))
    if realized is None:
        realized = 0.0
    # Do not mint fresh ammo for structural INX / sticky sports losers.
    if bot_id in ("kalshi-sp", "kalshi-sized", "sports-gap") and realized < -1e-9:
        return False
    if cash + 1e-9 < min_ammo:
        return True
    # Underwater after a losing day/book — even if cash was topped up mid-day.
    if (realized < -1e-9 or today < -1e-9) and cash + 1e-9 <= starter + 1e-9:
        return True
    if cash + 1e-9 < starter * 0.5 and realized < -1e-9:
        return True
    return False


def _learn_tower_before_midnight(root: str, bot: dict, day: str) -> int:
    """Push closed P&L into desk learning so the next bankroll can skip cold buckets."""
    bot_id = str(bot.get("id") or "")
    n = 0
    for idx, row in enumerate(list(bot.get("history") or [])[-80:]):
        if not isinstance(row, dict):
            continue
        pnl = _num(row.get("pnl"))
        if pnl is None:
            continue
        fill = _clean(row.get("fill_id") or row.get("when") or row.get("closed_at") or str(idx), 80)
        record_learning(root, {
            "result": "hit" if pnl > 0 else "miss",
            "market": bot_id,
            "prob": row.get("prob") or row.get("ask") or row.get("prob_exit") or 0.5,
            "stake": abs(pnl) if abs(pnl) >= 0.01 else 1.0,
            "fill_id": f"midnight-learn:{bot_id}:{day}:{fill}",
            "at": central_text(),
        })
        n += 1
    today = float(bot.get("today") or 0.0)
    realized = _num(bot.get("realized"))
    if realized is None:
        realized = today
    record_learning(root, {
        "result": "hit" if (today >= 0 and realized >= 0) else "miss",
        "market": bot_id,
        "prob": 0.5,
        "stake": max(1.0, abs(float(realized or 0.0)), abs(today)),
        "fill_id": f"midnight-dayroll:{bot_id}:{day}",
        "at": central_text(),
    })
    return n + 1


def _archive_tower_file(root: str, folder: str, name: str, day: str) -> str:
    """Move a paper file aside (keep evidence) before a fresh account write."""
    src = _under(root, folder, name)
    if not os.path.isfile(src) and not os.path.islink(src):
        return ""
    # With a /data volume the archive lives there too, so a redeploy keeps it.
    durable = _allowed_durable(_root(root))
    arch_dir = os.path.join(durable or _root(root), "midnight-archive", day)
    os.makedirs(arch_dir, exist_ok=True)
    safe = f"{folder.replace(os.sep, '_')}__{name}"
    dest = os.path.join(arch_dir, safe)
    if os.path.islink(src):
        # A settlement link points at the real book on the volume. Moving the
        # link would archive a pointer to the live file, and the next
        # keep_closed_settlements pass would bind the fresh account back to the
        # old one. Copy the real file, clear it, and keep the link so the fresh
        # write lands on the volume.
        real = os.path.realpath(src)
        if os.path.isfile(real):
            shutil.copy2(real, dest)
            _unlink(real)
        else:
            dest = ""
        return dest
    # Prefer rename; fall back to copy+unlink for cross-device volumes.
    try:
        os.replace(src, dest)
    except OSError:
        shutil.copy2(src, dest)
        _unlink(src)
    return dest


def reload_broke_tower(root: str, bot: dict, day: str, who: str = "midnight") -> dict:
    """Archive P&L files, learn, reload starter cash — one tower only."""
    root = _root(root)
    bot_id = str(bot.get("id") or "")
    spec = next((b for b in BOTS if b["id"] == bot_id), None)
    if not spec:
        return {"ok": False, "bot": bot_id, "error": "unknown bot"}
    folder = spec["folder"]
    before_cash = _num(bot.get("cash"))
    before_today = float(bot.get("today") or 0.0)
    before_realized = _num(bot.get("realized"))
    learned = _learn_tower_before_midnight(root, bot, day)
    try:
        import desk_lifetime
        desk_lifetime.bank_before_reset(root, bot, day, source="midnight")
    except Exception:  # noqa: BLE001 - the archive copy still keeps the evidence
        pass
    archived = []
    state_name = ACCOUNT_FILES.get(bot_id) or spec.get("state") or ""
    extras = {
        "sports-gap": ("paper_trades.md",),
        "kalshi-sp": ("Trade_Ledger.md",),
        "kalshi-sized": ("Trade_Ledger.md",),
        "memecoin": ("trades.csv", "checks.csv"),
        "btc15m": (),
        "commodity-15m": (),
    }.get(bot_id, ())
    for name in (state_name, *extras):
        if not name:
            continue
        dest = _archive_tower_file(root, folder, name, day)
        if dest:
            archived.append(os.path.basename(dest))
    # Fresh starter account (P&L zeroed). Learning rows stay in pimp-learning.json.
    body = _account_body(bot_id)
    body["paper_only"] = True
    body["midnight_reloaded_at"] = central_text()
    body["midnight_reloaded_day"] = day
    body["midnight_reloaded_from_cash"] = before_cash
    path = _under(root, folder, state_name)
    _write_json(path, body)
    after_cash = (
        _num(body.get("cash"))
        or _num(body.get("bankroll"))
        or _num(body.get("cash_usd"))
        or float(TOWER_STARTER_CASH.get(bot_id) or 0)
    )
    note = (
        f"Midnight reload {bot_id}: cash {before_cash} → {after_cash}, "
        f"today {before_today:+.2f}, realized {before_realized}, learned {learned}, "
        f"archived {len(archived)} file(s)."
    )
    audit(
        root,
        who or "midnight",
        note[:120],
        before={"cash": before_cash, "today": before_today, "realized": before_realized},
        after={"cash": after_cash, "day": day, "archived": archived},
    )
    return {
        "ok": True,
        "bot": bot_id,
        "error": "",
        "summary": note,
        "before_cash": before_cash,
        "after_cash": after_cash,
        "learned": learned,
        "archived": archived,
    }


# The 2026-11-13 midnight pass cleared real losses and wrote starter cash.
# Put that night's archived books back. Later nights do not wipe, so this is once.
UNDO_WIPE_DAY = "2026-11-13"
_WIPE_EXTRAS = {
    "sports-gap": ("paper_trades.md",),
    "kalshi-sp": ("Trade_Ledger.md",),
    "kalshi-sized": ("Trade_Ledger.md",),
    "memecoin": ("trades.csv", "checks.csv"),
}


def _put_archived_file(src: str, dest: str) -> None:
    """Copy an archived book onto the live path, including through a volume link."""
    if os.path.islink(dest):
        real = os.path.realpath(dest)
        os.makedirs(os.path.dirname(real), exist_ok=True)
        shutil.copy2(src, real)
        return
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    shutil.copy2(src, dest)


def _wipe_was_fresh(state: dict, day: str) -> bool:
    if not isinstance(state, dict):
        return False
    if str(state.get("midnight_reloaded_day") or "") != day:
        return False
    if state.get("open"):
        return False
    closed = state.get("closed")
    return not (isinstance(closed, list) and closed)


def _row_key(row: dict) -> tuple:
    return (
        str(row.get("fill_id") or ""),
        str(row.get("ticker") or row.get("mint") or ""),
        str(row.get("opened") or ""),
        str(row.get("closed") or ""),
        str(row.get("cost") or ""),
    )


def _merge_traded_after_wipe(archive: dict, live: dict) -> dict:
    """Real book, plus any trade that happened after the wipe. The minted cash stays out."""
    out = dict(archive)
    for key in ("midnight_reloaded_at", "midnight_reloaded_day", "midnight_reloaded_from_cash"):
        out.pop(key, None)
    arch_closed = [p for p in (archive.get("closed") or []) if isinstance(p, dict)]
    live_closed = [p for p in (live.get("closed") or []) if isinstance(p, dict)]
    seen = {_row_key(p) for p in arch_closed}
    new_closed = [p for p in live_closed if _row_key(p) not in seen]
    if "closed" in archive or new_closed:
        out["closed"] = arch_closed + new_closed
    arch_open = [p for p in (archive.get("open") or []) if isinstance(p, dict)]
    live_open = [p for p in (live.get("open") or []) if isinstance(p, dict)]
    open_seen = {_row_key(p) for p in arch_open}
    new_open = [p for p in live_open if _row_key(p) not in open_seen]
    if "open" in archive or new_open:
        out["open"] = arch_open + new_open
    cash_key = "cash_usd" if "cash_usd" in archive else "cash" if "cash" in archive else ""
    if cash_key:
        pnl = 0.0
        for row in new_closed:
            n = _num(row.get("pnl"))
            if n is not None:
                pnl += n
        spent = 0.0
        for row in new_open:
            n = _num(row.get("cost"))
            if n is not None:
                spent += n
        out[cash_key] = round(float(archive.get(cash_key) or 0) + pnl - spent, 2)
    if "realized_pnl_usd" in archive:
        extra = 0.0
        for row in new_closed:
            n = _num(row.get("pnl"))
            if n is not None:
                extra += n
        out["realized_pnl_usd"] = round(float(archive.get("realized_pnl_usd") or 0) + extra, 2)
    return out


def undo_midnight_wipe(root: str | None = None, day: str = UNDO_WIPE_DAY) -> list:
    """Put the archived books back over the one wipe that cleared them.

    Does not invent a number. If the live file is not that wipe, it is left alone.
    """
    root = _root(root)
    restored = []
    try:
        import desk_lifetime
    except Exception:  # noqa: BLE001
        desk_lifetime = None
    for spec in BOTS:
        bot_id = spec["id"]
        state_name = ACCOUNT_FILES.get(bot_id) or spec.get("state") or ""
        if not state_name:
            continue
        folder = spec["folder"]
        safe = folder.replace(os.sep, "_")
        names = [state_name, *_WIPE_EXTRAS.get(bot_id, ())]
        found = {}
        for base in (root, _allowed_durable(root)):
            if not base:
                continue
            day_dir = os.path.join(base, "midnight-archive", day)
            for name in names:
                path = os.path.join(day_dir, f"{safe}__{name}")
                if os.path.isfile(path) and name not in found:
                    found[name] = path
        if state_name not in found:
            continue
        live = _under(root, folder, state_name)
        state, problem = _read_state(live)
        if problem or str((state or {}).get("midnight_reloaded_day") or "") != day:
            continue
        archive_state, archive_problem = _read_state(found[state_name])
        if archive_problem or not isinstance(archive_state, dict):
            continue
        # A new closed trade after the wipe is real. Keep it. Do not keep the minted cash.
        trade_log = _under(root, folder, "trades.csv")
        new_trade_lines = []
        if os.path.isfile(trade_log):
            new_trade_lines = [ln for ln in open(trade_log, encoding="utf-8").read().splitlines() if ln.strip()]
        if _wipe_was_fresh(state, day) and len(new_trade_lines) <= 1:
            for name, src in found.items():
                _put_archived_file(src, _under(root, folder, name))
        else:
            merged = _merge_traded_after_wipe(archive_state, state)
            _write_json(live, merged)
            for name, src in found.items():
                if name == state_name:
                    continue
                dest = _under(root, folder, name)
                if name == "trades.csv" and len(new_trade_lines) > 1:
                    prior = [ln for ln in open(src, encoding="utf-8").read().splitlines() if ln.strip()]
                    header = prior[:1] or new_trade_lines[:1]
                    extra = [ln for ln in new_trade_lines[1:] if ln not in prior]
                    body = "\n".join(header + prior[1:] + extra) + "\n"
                    if os.path.islink(dest):
                        real = os.path.realpath(dest)
                        os.makedirs(os.path.dirname(real), exist_ok=True)
                        dest = real
                    with open(dest, "w", encoding="utf-8") as handle:
                        handle.write(body)
                elif not os.path.isfile(dest):
                    _put_archived_file(src, dest)
        if desk_lifetime is not None:
            desk_lifetime.mark_wipe_restored(root, bot_id, day)
        restored.append(bot_id)
        log.info("undo wipe %s: archived %s book put back", bot_id, day)
    if restored:
        audit(root, "undo-wipe", f"Put {day} books back: {', '.join(restored)}"[:120],
              before={"day": day}, after={"restored": restored})
    return restored


def run_midnight_broke_reload(root: str | None = None, now: dt.datetime | None = None) -> list:
    """Once per Chicago day (00:00–06:00 CT): leave every book as traded."""
    root = _root(root)
    if now is None:
        now = dt.datetime.now(dt.timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=dt.timezone.utc)
    now_ct = now.astimezone(CT)
    if not (0 <= now_ct.hour < 6):
        return []
    day = now_ct.date().isoformat()
    marker = _read_json(midnight_path(root)) or {}
    if isinstance(marker, dict) and marker.get("day") == day:
        return []
    ensure_paper_accounts(root)
    runs = _load_runs(root)
    bots = [_bot_view(spec, root, runs, now_ct.date()) for spec in BOTS]
    if not any(b.get("id") == "kalshi-sized" for b in bots):
        bots.append(_sized_view())
    reloaded = []
    left_alone = []
    waiting_open = []
    rows = []
    for bot in bots:
        bot_id = str(bot.get("id") or "")
        if not bot.get("present"):
            left_alone.append(bot_id)
            continue
        if int(bot.get("open_count") or 0) > 0 and not tower_doing_good(bot):
            # Flat required before a P&L wipe — open books wait for the next day.
            waiting_open.append(bot_id)
            left_alone.append(bot_id)
            continue
        if tower_doing_good(bot):
            left_alone.append(bot_id)
            continue
        if not tower_needs_midnight_reload(bot):
            left_alone.append(bot_id)
            continue
        result = reload_broke_tower(root, bot, day, who="midnight")
        reloaded.append(bot_id)
        rows.append({
            "bot": bot_id,
            "action": "midnight-reload",
            "ok": bool(result.get("ok")),
            "blocked": False,
            "entries_blocked": False,
            "error": result.get("error") or "",
            "summary": result.get("summary") or "",
        })
        log.info("midnight reload %s: %s", bot_id, _clean(result.get("summary") or "", 180))
    _write_json(midnight_path(root), {
        "day": day,
        "at": central_text(now_ct),
        "reloaded": reloaded,
        "left_alone": left_alone,
        "waiting_open": waiting_open,
        "paper_only": True,
    })
    if not rows and left_alone:
        rows.append({
            "bot": "desk",
            "action": "midnight-reload",
            "ok": True,
            "blocked": False,
            "entries_blocked": False,
            "error": "",
            "summary": (
                f"Midnight pass {day}: books left as traded "
                f"(left alone {len(left_alone)}; waiting open {len(waiting_open)}). "
                f"No cash added, no P&L cleared."
            ),
        })
    return rows


def _account_body(bot_id: str) -> dict:
    if bot_id == "sports-gap":
        return {"cash": SPORTS_CASH, "open": [], "closed": [], "runs": 0, "paper_only": True}
    if bot_id in ("kalshi-sp", "kalshi-sized"):
        return {
            "bankroll": 500.0,
            "open": [],
            "closed": [],
            "halted": False,
            "created": dt.datetime.now().isoformat(timespec="seconds"),
            "paper_only": True,
        }
    if bot_id in ("btc15m", "commodity-15m"):
        return {"cash": 100.0, "open": [], "closed": [], "paper_only": True}
    if bot_id == "coinbase-spot":
        return {
            "cash": 500.0,
            "open": [],
            "closed": [],
            "paper_only": True,
            "shadow_only": True,
            "live_orders": False,
        }
    if bot_id == "btc-carry":
        return {
            "cash": 500.0,
            "open": [],
            "closed": [],
            "paper_only": True,
            "shadow_only": True,
            "live_orders": False,
            "entry_fees": 0,
        }
    if bot_id == "wall-street":
        return {
            "cash": 0.0,
            "open": [],
            "closed": [],
            "paper_only": True,
            "shadow_only": True,
            "live_orders": False,
            "traders": 120,
        }
    if bot_id == "exclusive-set" or bot_id in _ZERO_STAKE_IDS:
        return {
            "cash": 0.0,
            "open": [],
            "closed": [],
            "paper_only": True,
            "shadow_only": True,
            "live_orders": False,
            "stake_usd": 0.0,
            "buys": 0,
        }
    if bot_id in _new_tower_ids():
        return {
            "cash": float(TOWER_STARTER_CASH.get(bot_id) or 500.0),
            "open": [],
            "closed": [],
            "checks": 0,
            "paper_only": True,
            "shadow_only": True,
            "live_orders": False,
        }
    if bot_id == "memecoin":
        return {
            "cash_usd": 100.0,
            "open": [],
            "cooldown": {},
            "realized_pnl_usd": 0.0,
            "paper_only": True,
        }
    return {"paper_only": True}


def ensure_paper_accounts(root: str | None = None) -> list:
    """Write each bot's starting paper account once. Never invent trades.

    Also puts back the 2026-11-13 wipe, once, so that loss stays on the total.

    An existing account is left alone, except the empty $14 sports starter,
    which is raised to $100 so a paper buy can land near $20.
    """
    root = _root(root)
    try:
        undo_midnight_wipe(root)
    except Exception:  # noqa: BLE001 - a restore miss must not block the timer
        log.exception("undo midnight wipe failed")
    made = []
    for spec in BOTS:
        name = ACCOUNT_FILES.get(spec["id"])
        if not name or not _folder_ok(root, spec["folder"], spec["script"]):
            continue
        path = _under(root, spec["folder"], name)
        if os.path.exists(path):
            if spec["id"] == "sports-gap":
                state, problem = _read_state(path)
                if isinstance(state, dict) and not problem and lift_sports_starter(state):
                    _write_json(path, state)
            elif spec["id"] == "memecoin":
                state, problem = _read_state(path)
                if isinstance(state, dict) and not problem and lift_memecoin_broke(state):
                    _write_json(path, state)
            continue
        _write_json(path, _account_body(spec["id"]))
        made.append(spec["id"])
    return made


def risk_reward(stake, max_payout) -> dict:
    """Risk is the stake. Reward is max payout minus stake. Ratio is reward / risk."""
    risk = _num(stake)
    payout = _num(max_payout)
    if risk is None:
        return {"risk": None, "reward": None, "risk_reward": None}
    risk = round(risk, 2)
    if payout is None:
        return {"risk": risk, "reward": None, "risk_reward": None}
    reward = round(payout - risk, 2)
    ratio = None if risk <= 0 else round(reward / risk, 4)
    return {"risk": risk, "reward": reward, "risk_reward": ratio}


def _trade_terms(pos: dict, cost) -> dict:
    stored = risk_reward(pos.get("risk"), None)
    risk = stored["risk"]
    if risk is None:
        risk = _num(cost)
        if risk is not None:
            risk = round(risk, 2)
    reward = _num(pos.get("reward"))
    if reward is None and risk is not None and not pos.get("mint") and "cost_usd" not in pos:
        contracts = _num(pos.get("contracts"))
        ask = _num(pos.get("ask"))
        if ask is None:
            ask = _num(pos.get("entry_price"))
        if contracts is not None and contracts > 0 and ask is not None and 0 < ask < 1:
            reward = round(contracts * 1.0 - risk, 2)
    ratio = _num(pos.get("risk_reward"))
    if ratio is None and reward is not None and risk is not None and risk > 0:
        ratio = round(reward / risk, 4)
    return {
        "risk": risk,
        "reward": None if reward is None else round(reward, 2),
        "risk_reward": None if ratio is None else round(ratio, 4),
    }


def prob_bucket(prob) -> str:
    """Ten-point probability bucket, such as 0.6-0.7. Blank when the probability was not stored."""
    value = _num(prob)
    if value is None:
        return ""
    value = min(max(value, 0.0), 0.999999)
    lo = math.floor(value * 10) / 10
    hi = round(lo + 0.1, 1)
    return f"{lo:.1f}-{hi:.1f}"


def learning_path(root: str | None = None) -> str:
    return _under(root, "pimp-learning.json")


def load_learning(root: str | None = None) -> list:
    data = _read_json(learning_path(root)) or {}
    rows = data.get("rows") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def record_learning(root: str | None, row: dict) -> None:
    """Append one learning row for a fill. Hit or miss only when that result is real.

    A failsafe reason may be stored with no hit or miss. That row is not a win.
    A missing market, bucket, or stake is not invented. The same fill id is not
    written twice. Optional side + hour_ct enable learning-skip v2.
    """
    if not isinstance(row, dict):
        return
    result = str(row.get("result") or "")
    if result not in ("hit", "miss"):
        result = ""
    reason = _clean(row.get("reason"), 120)
    if not result and not reason:
        return
    market = _clean(row.get("market"), 40)
    bucket = _clean(row.get("bucket") or prob_bucket(row.get("prob")), 16)
    stake = _num(row.get("stake"))
    if not market or not bucket or stake is None:
        return
    fill_id = _clean(row.get("fill_id"), 80)
    side = _clean(str(row.get("side") or "").upper(), 8)
    hour_ct = row.get("hour_ct")
    try:
        hour_ct = int(hour_ct) if hour_ct is not None else None
        if hour_ct is not None and not (0 <= hour_ct <= 23):
            hour_ct = None
    except (TypeError, ValueError):
        hour_ct = None
    if hour_ct is None:
        when = _ct_when(row.get("at") or "")
        if when is not None:
            hour_ct = int(when.astimezone(CT).hour)
    with _FILE_LOCK:
        rows = load_learning(root)
        if fill_id and any(str(item.get("fill_id") or "") == fill_id for item in rows):
            return
        item = {
            "at": _clean(row.get("at") or central_text(), 40),
            "market": market,
            "bucket": bucket,
            "stake": round(stake, 2),
            "fill_id": fill_id,
        }
        if result:
            item["result"] = result
        if reason:
            item["reason"] = reason
        if side:
            item["side"] = side
        if hour_ct is not None:
            item["hour_ct"] = hour_ct
        rows.append(item)
        _write_json(learning_path(root), {"paper_only": True, "rows": rows[-2000:]})


def learning_skip(rows, market, bucket, side=None, hour_ct=None) -> str:
    """Skip cold paper buckets under 40% hits after ≥8 settles.

    v2 (when side + hour_ct provided): market × side × hour × bucket first;
    falls back to classic market × bucket when the fine sample is thin.
    Count only — not a smarter model. Fee floors unchanged.
    """
    market = _clean(market, 40)
    bucket = _clean(bucket, 16)
    if not market or not bucket or not isinstance(rows, list):
        return ""
    side_n = _clean(str(side or "").upper(), 8)
    try:
        hour_n = int(hour_ct) if hour_ct is not None else None
        if hour_n is not None and not (0 <= hour_n <= 23):
            hour_n = None
    except (TypeError, ValueError):
        hour_n = None

    def _rate(same: list) -> tuple[int, int]:
        hits = sum(1 for row in same if row.get("result") == "hit")
        return hits, len(same)

    # Fine key first (ROI plan Phase 4 learning skip v2).
    if side_n and hour_n is not None:
        fine = [
            row for row in rows
            if isinstance(row, dict)
            and row.get("market") == market
            and row.get("bucket") == bucket
            and str(row.get("side") or "").upper() == side_n
            and row.get("hour_ct") == hour_n
            and row.get("result") in ("hit", "miss")
        ]
        hits, n = _rate(fine)
        if n >= LEARN_MIN_SETTLES and (hits / n) + 1e-12 < LEARN_HIT_RATE:
            return (
                f"Skipping {market} {side_n} hour={hour_n} CT in {bucket}. "
                f"Fine paper bucket has {hits}/{n} hits under 40% (learn v2)."
            )

    same = [
        row for row in rows
        if isinstance(row, dict) and row.get("market") == market and row.get("bucket") == bucket
        and row.get("result") in ("hit", "miss")
    ]
    hits, n = _rate(same)
    if n < LEARN_MIN_SETTLES:
        return ""
    if (hits / n) + 1e-12 >= LEARN_HIT_RATE:
        return ""
    return (
        f"Skipping {market} in the {bucket} probability bucket. "
        f"That paper bucket has {hits} hits out of {n} settles, which is under 40%. "
        "This is only a count of paper settles."
    )


def _hour_window(now: dt.datetime | None = None):
    local = (now or dt.datetime.now(CT)).astimezone(CT)
    start = local.replace(minute=0, second=0, microsecond=0)
    return start, start + dt.timedelta(hours=1)


def _in_hour(text, start, end) -> bool:
    when = _ct_when(text)
    if when is None:
        return False
    return start <= when < end


def hour_trade_count(root: str | None = None, now: dt.datetime | None = None) -> int:
    """Paper trades opened or settled in this Chicago hour. One trade counts once. Nothing is invented."""
    root = _root(root)
    start, end = _hour_window(now)
    seen = set()

    def take(key, opened, closed):
        if not key:
            return
        if _in_hour(opened, start, end) or _in_hour(closed, start, end):
            seen.add(key)

    for bot_id, filename in (
        ("sports-gap", "state.json"),
        ("kalshi-sp", "paper_state.json"),
        ("kalshi-sized", "paper_state.json"),
        ("btc15m", "paper_account.json"),
    ):
        folder = next((spec["folder"] for spec in BOTS if spec["id"] == bot_id), "")
        if not folder:
            continue
        try:
            state, _problem = _read_state(_under(root, folder, filename))
        except RuntimeError:
            continue
        if not isinstance(state, dict):
            continue
        for pos in list(state.get("open") or []) + list(state.get("closed") or []):
            if not isinstance(pos, dict):
                continue
            key = str(pos.get("fill_id") or "") or f"{bot_id}|{pos.get('ticker')}|{pos.get('opened') or pos.get('entry_time')}"
            take(
                key,
                pos.get("opened") or pos.get("entry_time") or "",
                pos.get("closed") or pos.get("settled_at") or "",
            )
    try:
        meme_path = _under(root, "memecoin-paper", "trades.csv")
    except RuntimeError:
        meme_path = ""
    for raw in _csv_tail(meme_path, 5000) if meme_path else []:
        if not isinstance(raw, dict):
            continue
        side = str(raw.get("side") or "").upper()
        if side not in ("BUY", "SELL"):
            continue
        if not _in_hour(raw.get("ts") or "", start, end):
            continue
        seen.add("meme:" + str(raw.get("mint") or raw.get("symbol") or raw.get("ts") or ""))
    return len(seen)


def edge_for_hour(count, saved_edge, pace_min=PACE_MIN, pace_target=PACE_TARGET):
    """Saved edge after fees. An hour under the pace target does not waive it.

    count, pace_min, and pace_target stay so older callers keep working.
    They do not change the bar.
    """
    return round(float(saved_edge), 4), False


def hour_pace(root: str | None = None, now: dt.datetime | None = None, cfg: dict | None = None) -> dict:
    cfg = cfg or load_settings(root)
    count = hour_trade_count(root, now)
    target = int(cfg.get("pace_target") or PACE_TARGET)
    minimum = int(cfg.get("pace_min") or PACE_MIN)
    saved = float(cfg.get("min_edge") if cfg.get("min_edge") is not None else DEFAULTS["min_edge"])
    edge, loose = edge_for_hour(count, saved, minimum, target)
    note = (
        f"This hour has {count} paper trades. "
        f"The edge bar stays at {saved:.2f} after the fee. "
        "The hour count does not waive it."
    )
    return {
        "count": count,
        "target": target,
        "minimum": minimum,
        "line": f"{count} of {target} this hour",
        "edge": edge,
        "loosened": loose,
        "saved_edge": round(saved, 4),
        "note": note,
    }


_ISO_STAMP = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}")
_RUN_ID = re.compile(r"\brun\s+[0-9a-f]{6,}\b", re.I)


def _raw_card(text: str) -> bool:
    raw = str(text or "")
    low = raw.lower()
    if _ISO_STAMP.search(raw) or _RUN_ID.search(raw):
        return True
    if "managing open" in low or "scanning for candidates" in low or "solana tokens" in low:
        return True
    stripped = raw.strip()
    return stripped.startswith("{") or stripped.startswith("[")


def _meme_card(text: str) -> str:
    raw = str(text or "")
    low = raw.lower()
    if "solana" not in low and "paper entries" not in low and "managing open paper positions" not in low:
        return ""
    checked = None
    found = re.search(r"tokens checked:\s*(\d+)", low)
    if found:
        checked = int(found.group(1))
    else:
        nums = [int(n) for n in re.findall(r"(\d+)\s+solana tokens", low)]
        if nums:
            checked = nums[0]
    if checked is None:
        first = "Checked Solana tokens."
    else:
        word = "token" if checked == 1 else "tokens"
        first = f"Checked {checked} Solana {word}."
    buys = re.findall(r"PAPER BUY\s+([A-Za-z0-9]+)", raw)
    entries = re.search(r"paper entries:\s*(\d+)", low)
    n_entries = int(entries.group(1)) if entries else len(buys)
    if n_entries <= 0 and not buys:
        second = "No paper buy."
    elif len(buys) == 1:
        second = f"Paper buy {buys[0]}."
    elif buys:
        second = f"{len(buys)} paper buys."
    elif n_entries == 1:
        second = "Paper buy."
    else:
        second = f"{n_entries} paper buys."
    return f"{first} {second}"


def _sports_card(text: str) -> str:
    raw = str(text or "")
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        return ""
    try:
        data = json.loads(raw[start:end + 1])
    except json.JSONDecodeError:
        return ""
    if not isinstance(data, dict) or "live_games" not in data and "trades" not in data:
        return ""
    trades = data.get("trades") or []
    if trades:
        word = "trade" if len(trades) == 1 else "trades"
        return f"Paper buy. {len(trades)} paper {word} this check."
    if data.get("live_games") == 0:
        return "No live games, so this check bought nothing."
    return "No paper buy."


def _btc_card(text: str) -> str:
    low = str(text or "").lower()
    if "btc" not in low and "signal:" not in low and "kxbtc" not in low:
        return ""
    if "paper buy" in low and "no paper buy" not in low:
        return "Checked all open BTC 15-minute markets. Paper buy."
    if "paper buy" in low or "signal:" in low or "skip:" in low or "no open kxbtc" in low:
        return "Checked all open BTC 15-minute markets. No paper buy."
    return ""


def traceback_tail(text: str) -> str:
    """The real error at the end of a Python traceback ("ValueError: ..."), or ""."""
    raw = str(text or "")
    if "Traceback (most recent call last)" not in raw:
        return ""
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    for line in reversed(lines):
        if line.startswith(("File ", "^", "~", "raise ", "Traceback")):
            continue
        name = line.split(":", 1)[0]
        if name.replace(".", "").replace("_", "").isalnum() and (name.endswith(("Error", "Exception", "Exit", "Timeout"))
                                                                  or "." in name):
            return line
    return lines[-1] if lines else ""


def card_copy(text: str) -> str:
    """One or two plain sentences for a bot card. No run id and no ISO timestamp."""
    raw = str(text or "")
    if not raw.strip():
        return ""
    tail = traceback_tail(raw)
    if tail:
        kind = tail.split(":", 1)[0].rsplit(".", 1)[-1]
        return _clean(f"The last check hit an error ({kind}) and stopped without trading. "
                      "The next check tries again.", 220)
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.startswith("CARD: "):
            return _clean(stripped[6:], 220)
        if stripped.startswith("Skipping "):
            return _clean(stripped, 220)
    for builder in (_meme_card, _sports_card, _btc_card):
        sentence = builder(raw)
        if sentence:
            return sentence
    reason = plain_reason(raw)
    if _raw_card(reason):
        return "The check finished. No paper buy."
    return reason


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
    if "max open" in low or "open risk" in low:
        return (
            "Book is full — new paper buys are off until an open position exits. "
            "Stops, ladders, and settles still run."
        )
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


def paper_stake_dollars(prob, cfg: dict | None = None) -> float:
    """Paper dollars for one fill. Under 80% this is about $20.

    At 80% or higher the stake scales from the saved minimum ($20) to the
    saved maximum ($100). Nothing here places an order.
    """
    cfg = cfg or DEFAULTS
    lo = float(cfg.get("stake_lo_max") if cfg.get("stake_lo_max") is not None else DEFAULTS["stake_lo_max"])
    hi_min = float(cfg.get("stake_hi_min") if cfg.get("stake_hi_min") is not None else DEFAULTS["stake_hi_min"])
    hi_max = float(cfg.get("stake_hi_max") if cfg.get("stake_hi_max") is not None else DEFAULTS["stake_hi_max"])
    bar = float(cfg.get("stake_hi_prob") if cfg.get("stake_hi_prob") is not None else DEFAULTS["stake_hi_prob"])
    chance = _num(prob)
    if chance is None or chance + 1e-12 < bar:
        return round(lo, 2)
    if hi_max < hi_min:
        hi_max = hi_min
    span = 1.0 - bar
    if span <= 0:
        return round(hi_max, 2)
    t = (float(chance) - bar) / span
    if t < 0:
        t = 0.0
    elif t > 1:
        t = 1.0
    return round(hi_min + t * (hi_max - hi_min), 2)


def contracts_for_stake(per, dollars) -> int:
    """Whole contracts whose cost lands near `dollars` without going over.

    A budget that cannot buy one contract returns 0. It does not pad up to 1.
    """
    price = _num(per)
    budget = _num(dollars)
    if price is None or budget is None or price <= 0 or budget <= 0:
        return 0
    return max(int(math.floor((budget + 1e-9) / price)), 0)


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
    path = _follow_link(path)
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
    if bot_id in ("kalshi-sp", "kalshi-sized"):
        folder = "kalshi-sized-paper" if bot_id == "kalshi-sized" else "kalshi-sp500-paper"
        path = _under(root, folder, "calendar.json")
        if bot_id == "kalshi-sized" and not os.path.isfile(path):
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


def sports_tip_alarm_from_cache(
    root: str | None = None,
    now: dt.datetime | None = None,
    window_min: float | None = None,
) -> dict:
    """Offline tip-alarm from sports-gap quote_cache. No network. Fee floors unchanged.

    Returns active=True when any pregame tip is inside the forward window (default T−15).
    Band is 5 when nearest tip ≤5m, else 15 when ≤window.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=dt.timezone.utc)
    window = float(SPORTS_TIP_FORCE_WINDOW_MIN if window_min is None else window_min)
    path = _under(root, "sports-gap-paper", "quote_cache.json")
    data = _read_json(path)
    nearest = None
    n_pre = 0
    n_tip = 0
    sample = ""
    if isinstance(data, dict):
        for payload in data.values():
            if not isinstance(payload, dict):
                continue
            body = payload.get("body")
            if isinstance(body, str):
                try:
                    body = json.loads(body)
                except (TypeError, ValueError, json.JSONDecodeError):
                    continue
            if not isinstance(body, dict):
                continue
            for event in body.get("events") or []:
                if not isinstance(event, dict):
                    continue
                comps = (event.get("competitions") or [{}])
                comp = comps[0] if comps and isinstance(comps[0], dict) else {}
                status = (comp.get("status") or event.get("status") or {})
                stype = status.get("type") if isinstance(status, dict) else {}
                if not isinstance(stype, dict):
                    stype = {}
                if str(stype.get("state") or "") != "pre":
                    continue
                n_pre += 1
                raw = comp.get("date") or event.get("date")
                if not raw:
                    continue
                try:
                    when = dt.datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                except ValueError:
                    continue
                if when.tzinfo is None:
                    when = when.replace(tzinfo=dt.timezone.utc)
                eta = (when - now).total_seconds() / 60.0
                if eta <= 0 or eta > window:
                    continue
                n_tip += 1
                if nearest is None or eta < nearest:
                    nearest = eta
                    sample = _clean(event.get("name") or event.get("shortName") or "", 80)
    band = None
    if nearest is not None:
        if nearest <= 5:
            band = 5
        elif nearest <= window:
            band = 15
    return {
        "paper_only": True,
        "active": band is not None,
        "band": band,
        "n_pre": n_pre,
        "n_tip": n_tip,
        "nearest_eta_min": round(nearest, 2) if nearest is not None else None,
        "sample": sample,
        "force_sec": SPORTS_TIP_FORCE_SEC,
        "window_min": window,
        "note": "Forced AUTO cadence only — venue min_edge still required inside gap_bot.",
    }


def _sports_auto_gap_sec(root: str, base_gap: float, now: dt.datetime | None = None) -> float:
    """Sports cadence: tip-force (45s) > normal > idle stretch. Never loosens fees."""
    tip = sports_tip_alarm_from_cache(root, now=now)
    if tip.get("active"):
        return float(SPORTS_TIP_FORCE_SEC)
    if _sports_idle(root):
        return max(float(base_gap), float(IDLE_SPORTS_SEC))
    return float(base_gap)


def _meme_open_count(root: str) -> int:
    state = _read_json(_under(root, "memecoin-paper", "positions.json"))
    if not isinstance(state, dict):
        return 0
    return len([p for p in (state.get("open") or []) if isinstance(p, dict)])


def _commodity_open_count(root: str) -> int:
    state = _read_json(_under(root, "commodity-15m-paper", "paper_account.json"))
    if not isinstance(state, dict):
        return 0
    return len([p for p in (state.get("open") or []) if isinstance(p, dict)])


def _meme_auto_gap_sec(root: str, base_gap: float) -> float:
    """Faster manage ticks when meme book is open — exits still fee-aware."""
    if _meme_open_count(root) > 0:
        return float(MEME_MANAGE_OPEN_SEC)
    return float(base_gap)


def _commodity_auto_gap_sec(root: str, base_gap: float) -> float:
    """Calm-regime faster poll when ≥2 commodity series already open."""
    if _commodity_open_count(root) >= int(COMMODITY_CALM_OPEN_N):
        return float(COMMODITY_CALM_OPEN_SEC)
    return float(base_gap)


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


def touch_heartbeat(root: str | None = None, now: dt.datetime | None = None) -> None:
    when = now or dt.datetime.now(dt.timezone.utc)
    _write_json(heartbeat_path(root), {"at": _iso(when), "paper_only": True})


def tower_watchdog(root: str | None = None, now: dt.datetime | None = None) -> list:
    """New audit notes for towers that timed out, failed twice, or stalled (desk_watchdog)."""
    import desk_watchdog

    root = _root(root)
    alive = bool(timer_health(root, now=now).get("alive"))
    return desk_watchdog.check(sys.modules[__name__], root, now=now, timer_alive=alive)


def ops_check(root: str | None = None, now: dt.datetime | None = None) -> list:
    """Desk-wide notes: run stats, slow towers, daily summary, disk, memory, clock, backups (desk_ops)."""
    import desk_ops

    return desk_ops.check(sys.modules[__name__], _root(root), now=now)


def timer_health(root: str | None = None, now: dt.datetime | None = None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=dt.timezone.utc)
    data = _read_json(heartbeat_path(root)) or {}
    when = _parsed(str(data.get("at") or ""))
    weekday = now.astimezone(CT).weekday() < 5
    if when is None:
        alert = "WEEKDAY ALERT: no paper timer heartbeat yet — start Discord paper_timer." if weekday else ""
        if not alert:
            alert = "No timer loop yet."
        return {
            "alive": False,
            "detail": "No timer loop yet.",
            "age": None,
            "alert": alert,
            "weekday": weekday,
            "weekday_alert": bool(weekday),
        }
    age = int((now - when).total_seconds())
    alive = age <= HEARTBEAT_STALE_SEC
    alert = ""
    weekday_alert = False
    if not alive:
        alert = "Paper timer looks dead. The last loop is too old."
        if weekday and age >= HEARTBEAT_WEEKDAY_ALERT_SEC:
            weekday_alert = True
            alert = (
                f"WEEKDAY ALERT: paper timer dead {age // 60}m "
                f"(>{HEARTBEAT_WEEKDAY_ALERT_SEC // 60}m) — restart Discord paper_timer."
            )
    return {
        "alive": alive,
        "detail": "Timer alive." if alive else "Last loop is too old.",
        "age": age,
        "alert": alert,
        "weekday": weekday,
        "weekday_alert": weekday_alert,
    }


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
    best = _next_at(bot_id, root, now)
    return central_text(best) if best is not None else ""


def _next_at(bot_id: str, root: str, now: dt.datetime):
    """The next scheduled check as a datetime (None if no timer slot)."""
    now_ct = now.astimezone(CT)
    if now.tzinfo is None:
        now = now.replace(tzinfo=dt.timezone.utc)
    saved = _load_auto(root)
    best = None
    for slot in AUTO:
        if slot["id"] != bot_id:
            continue
        if "every_sec" in slot:
            prev = _parsed(saved.get(_slot_key(slot)) or "")
            gap = float(slot["every_sec"])
            if bot_id == "sports-gap":
                gap = _sports_auto_gap_sec(root, gap, now=now)
            elif bot_id == "memecoin":
                gap = _meme_auto_gap_sec(root, gap)
            elif bot_id == "commodity-15m":
                gap = _commodity_auto_gap_sec(root, gap)
            when = now if prev is None else prev + dt.timedelta(seconds=gap)
            if when < now:
                when = now
        else:
            # Clock window: never advertise a past start while the window is still
            # open (sized/S&P HUD showed "1:00 PM" at 2:39 CT — settle start).
            start = dt.datetime.combine(now_ct.date(), _hhmm(slot["at_ct"]), CT)
            end = dt.datetime.combine(now_ct.date(), _hhmm(slot["until_ct"]), CT)
            key = _slot_key(slot)
            day = now_ct.date().isoformat()
            if saved.get(key) == day or now_ct > end:
                when = start + dt.timedelta(days=1)
            elif now_ct < start:
                when = start
            else:
                # Inside an open, not-yet-finished window → due now (or after retry).
                retry = _parsed(saved.get(key + ":retry") or "")
                if retry is not None:
                    when = retry + dt.timedelta(seconds=float(AUTO_RETRY_SEC))
                    if when.tzinfo is None:
                        when = when.replace(tzinfo=dt.timezone.utc)
                    when_ct = when.astimezone(CT)
                    if when_ct < now_ct:
                        when = now
                        when_ct = now_ct
                    if when_ct > end:
                        when = start + dt.timedelta(days=1)
                else:
                    when = now
        if best is None or when < best:
            best = when
    return best


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
    view["book_id"] = {
        "sports": "sports", "kalshi": "kalshi", "btc": "bitcoin", "meme": "meme", "spot": "coinbase",
        "carry": "btc-carry",
        "floor": "wallstreet",
    }.get(spec.get("kind"), "kalshi")
    view["shadow_only"] = bool(spec.get("shadow_only"))
    view["paused"] = bot_paused(root, spec["id"])
    view["next_run"] = _next_for(spec["id"], root, now)
    if view["next_run"] and view["next_run"] != "Paused":
        nxt_at = _next_at(spec["id"], root, now)
        view["next_run_at"] = nxt_at.isoformat(timespec="seconds") if nxt_at is not None else ""
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
    if spec.get("id") == "wall-street":
        n = int(view.get("traders") or spec.get("traders") or 120)
        view["traders"] = n
        view["departments"] = [dict(row) for row in (spec.get("departments") or ())]
        view["idle_copy"] = f"{n} traders on six desks. One book. It does not trade."
        if not view.get("why"):
            view["why"] = view["idle_copy"]
        view["skip"] = view.get("skip") or "floor does not trade"
    elif not view.get("positions") and not view.get("trades"):
        view["idle_copy"] = f"No paper trades yet. Last check {view['central_check']}. No edge."
    else:
        view["idle_copy"] = ""
    # INX towers: surface next scan heartbeat so morning idle is not read as broken.
    if spec.get("id") in ("kalshi-sp", "kalshi-sized"):
        heartbeat = next_inx_scan_line(str(spec.get("id")))
        view["next_scan"] = heartbeat
        if heartbeat:
            if view.get("idle_copy"):
                view["idle_copy"] = f"{view['idle_copy']} {heartbeat}"
            why = str(view.get("why") or "")
            if why and "Next scan" not in why and "In scan window" not in why and "Next " not in why:
                # Keep CARD why; densify schedule on no-buy / empty-settle / staff-clear DD.
                # Empty settle must not lead the why outside/inside scan (#497 twin) —
                # lead with next-scan heartbeat so HUD is not a false empty-book miss.
                why_low = why.lower()
                # In an open scan window, empty settle must not lead the tip —
                # sized/S&P HUD was reading as "In scan window… Settle…" while
                # the real skip was late-σ / fair-p NO TRADE (#497 twin).
                in_scan = heartbeat.lower().startswith("in scan window")
                if "no open paper" in why_low:
                    if in_scan and str(view.get("skip") or "").strip():
                        view["why"] = plain_reason(view.get("skip") or "")
                    elif in_scan:
                        view["why"] = f"{heartbeat} Waiting on scan tip."
                    else:
                        view["why"] = f"{heartbeat} Settle smoke: empty book."
                elif (
                    "no paper buy" in why_low
                    or "check finished" in why_low
                    or "staff cleared soft drawdown" in why_low
                    or not why.strip()
                ):
                    # Outside the entry window, schedule is why the book is idle.
                    # Soft-DD staff-clear is resume truth — not a "we're down so we
                    # don't trade" lead (HUD sibling after #506 tip densify).
                    if "staff cleared soft drawdown" in why_low and not in_scan:
                        view["why"] = f"{heartbeat} {why}".strip()
                    else:
                        view["why"] = f"{why} {heartbeat}".strip()
            elif not why:
                view["why"] = heartbeat
    if not view.get("why") and view.get("skip"):
        view["why"] = plain_reason(view.get("skip") or "")
    summary = str(run.get("summary") or "")
    # Full book / desk gate: prefer a clear "waiting on exits" line over a dead BLOCKED look.
    open_n = int(view.get("open_count") or 0)
    why_low = str(view.get("why") or "").lower()
    entry_skip_look = any(
        token in why_low
        for token in (
            "speed floor",
            "ask+fee",
            "ask+fee+buf",
            "no paper buy",
            " < ",  # p/z gate fragments like "p 0.619 < …" / "z 0.30 < …"
            "checked all open",
        )
    )
    if open_n > 0 and (
        run.get("entries_blocked")
        or "max open" in summary.lower()
        or "open risk" in summary.lower()
        or "max_open" in (view.get("skip") or "").lower()
        # Holding inventory: never let entry-gate CARD steal the why (BTC HUD sibling).
        or entry_skip_look
        or not why_low.strip()
    ):
        if "holding" not in why_low and "sell plan" not in why_low:
            view["why"] = (
                f"Holding {open_n} open paper position(s); "
                "sell plan still runs each check. Entry skips stay observe-only while risk is open."
            )
        if run.get("ok") and not view.get("paused") and not view.get("read_error"):
            view["status"] = "running"
    if not view.get("warning") and spec.get("id") == "btc15m":
        view["warning"] = _btc_calendar_warning(summary)
    if view.get("data_error"):
        view["feed"] = "api down"
    elif "no live games" in summary.lower():
        view["feed"] = "no games"
    else:
        view["feed"] = source_status(1 if view.get("positions") else 0, view.get("data_error") or "")
    view["plans"] = bot_plans(spec["id"], load_settings(root))
    view["gates_hit"] = bot_gates_hit(view)
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
        stamp = _ct_date(row.get("when"))
        if stamp is None or not (start <= stamp <= end):
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


def _chart_now(now: dt.datetime | None = None) -> dt.datetime:
    if now is None:
        now = dt.datetime.now(CT)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=CT)
    else:
        now = now.astimezone(CT)
    return now.replace(microsecond=0)


def _months_back(when: dt.datetime, months: int) -> dt.datetime:
    """The same Chicago clock time, N calendar months earlier. No extra day is invented."""
    month = when.month - int(months)
    year = when.year
    while month <= 0:
        month += 12
        year -= 1
    day = when.day
    while day >= 1:
        try:
            return when.replace(year=year, month=month, day=day)
        except ValueError:
            day -= 1
    raise ValueError("no calendar day")


def chart_windows(now: dt.datetime | None = None) -> list:
    """YTD, 3M, 6M, 9M, and 12M. Starts and ends are America/Chicago."""
    now = _chart_now(now)
    ytd = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    specs = [("ytd", "YTD", ytd)]
    for count, key, label in ((3, "3m", "3M"), (6, "6m", "6M"), (9, "9m", "9M"), (12, "12m", "12M")):
        specs.append((key, label, _months_back(now, count)))
    end = now.isoformat(timespec="seconds")
    return [{
        "id": key,
        "label": label,
        "start": start.isoformat(timespec="seconds"),
        "end": end,
    } for key, label, start in specs]


def curve_in_window(points: list, start: str, end: str) -> list:
    """Settled points whose real timestamps fall in the window. Untimed points stay out."""
    start_at = _ct_when(start)
    end_at = _ct_when(end)
    if start_at is None or end_at is None:
        return []
    chosen = []
    for point in points or []:
        if not isinstance(point, dict):
            continue
        when = _ct_when(point.get("t"))
        if when is None:
            continue
        if start_at <= when <= end_at:
            chosen.append(point)
    return chosen


def _open_line(bots: list) -> dict:
    """Open paper trades only. No settled P/L, and no made-up path."""
    opens = []
    for bot in bots:
        for pos in bot.get("positions") or []:
            if not isinstance(pos, dict):
                continue
            raw = str(pos.get("when") or "")
            when = _ct_when(raw)
            stake = _num(pos.get("cost"))
            title = _clean(pos.get("title") or "", 120)
            opens.append({
                "t": when.isoformat(timespec="seconds") if when is not None else "",
                "name": title or _curve_name(pos),
                "stake": None if stake is None else round(stake, 2),
            })
    return {
        "label": "Live · not settled",
        "settled": False,
        "n": len(opens),
        "opens": opens,
    }


def _thin_curve(points: list) -> list:
    """Keep real settles. A long book keeps each older Chicago day at its last settle."""
    if len(points) <= 2000:
        return points
    timed = []
    untimed = []
    for point in points:
        when = _ct_when(point.get("t"))
        if when is None:
            untimed.append(point)
        else:
            timed.append((when, point))
    if not timed:
        return points[-2000:]
    last = timed[-1][0]
    floor = _months_back(last, 12)
    recent_cut = last - dt.timedelta(days=21)
    recent = []
    daily = {}
    order = []
    for when, point in timed:
        if when < floor:
            continue
        if when >= recent_cut:
            recent.append(point)
            continue
        day = when.astimezone(CT).date().isoformat()
        if day not in daily:
            order.append(day)
        daily[day] = point
    return [daily[day] for day in order] + recent[-1600:] + untimed


def _equity_curve(bots: list) -> list:
    """Cumulative settled paper P/L. No point is invented when nothing has settled.

    Each point is one settled paper slip. The chart can name that slip without
    adding a dot that was not a trade. Open trades are not on this line.
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
    return _thin_curve(points)


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


def _desk_money_bots(bots: list) -> list:
    """Towers whose paper cash is the vault. Shadow books are not added in."""
    return [b for b in bots if not b.get("shadow_only")]


def bankroll_roll(bots: list) -> dict:
    """Desk vault versus shadow books. Losses stay in whichever book made them."""
    desk = _desk_money_bots(bots)
    shadow = [b for b in bots if b.get("shadow_only")]

    def _ids(rows: list) -> list:
        return [str(b.get("id") or "") for b in rows if b.get("id")]

    def _sum(rows: list, key: str):
        vals = []
        for bot in rows:
            number = bot.get(key)
            if number is None:
                continue
            try:
                vals.append(float(number))
            except (TypeError, ValueError):
                continue
        if not vals:
            return None
        return round(sum(vals), 2)

    missing = [str(b.get("id") or "") for b in desk if b.get("cash") is None and b.get("id")]
    return {
        "paper_only": True,
        "towers": _ids(desk),
        "connected": [str(b.get("id") or "") for b in desk if b.get("cash") is not None and b.get("id")],
        "missing": missing,
        "cash": _sum(desk, "cash"),
        "realized": _sum(desk, "realized"),
        "today": round(sum(float(b.get("today") or 0) for b in desk), 2),
        "open_risk": round(sum(float(b.get("open_risk") or 0) for b in desk), 2),
        "open_count": int(sum(int(b.get("open_count") or 0) for b in desk)),
        "shadow_towers": _ids(shadow),
        "shadow_cash": _sum(shadow, "cash"),
        "shadow_realized": _sum(shadow, "realized"),
        "shadow_today": round(sum(float(b.get("today") or 0) for b in shadow), 2),
        "note": (
            "Vault cash is only towers that spend desk cash. "
            "Shadow towers keep their own books and are not added in."
        ),
    }


def _desk_row(bots: list, cashes: list, realized_rows: list, last_check: str, gate: str, cfg: dict, root: str) -> dict:
    day = _today()
    # Headline cash, P&L, week, and the chart are the desk book only.
    # Shadow towers still run; they do not move this total.
    money_bots = _desk_money_bots(bots)
    cashes = [b["cash"] for b in money_bots if b.get("cash") is not None]
    realized_rows = [b["realized"] for b in money_bots if b.get("realized") is not None]
    week, wins, losses, swing = _week_pnl(money_bots, day)
    goal = float(cfg.get("week_goal") or 0)
    if goal <= 0:
        bar = 0
    else:
        bar = max(0, min(100, int(round(100 * week / goal))))
    trades_today = 0
    for row in _flatten(money_bots):
        when = str(row.get("when") or "")
        if _day_hit(when, day):
            trades_today += 1
    # Earliest by time, not by text ("10:41 AM" sorts before "5:15 AM" as text).
    nxt, nxt_at = "", None
    for bot in bots:
        text = bot.get("next_run") or ""
        if not text or text == "Paused":
            continue
        at = _parsed(bot.get("next_run_at") or "")
        if at is not None and at.tzinfo is None:
            at = at.replace(tzinfo=dt.timezone.utc)
        if at is None:
            if not nxt:
                nxt = text
            continue
        if nxt_at is None or at < nxt_at:
            nxt, nxt_at = text, at
    central = _central_from_text(last_check)
    curve = _equity_curve(money_bots)
    spikes = _equity_spikes(curve)
    pace = hour_pace(root, cfg=cfg)
    now = _chart_now()
    return {
        "cash": None if not cashes else round(sum(cashes), 2),
        "realized": None if not realized_rows else round(sum(realized_rows), 2),
        "today": round(sum(float(bot.get("today") or 0) for bot in money_bots), 2),
        "open_risk": round(sum(float(bot.get("open_risk") or 0) for bot in money_bots), 2),
        "open_count": int(sum(int(bot.get("open_count") or 0) for bot in money_bots)),
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
        "chart": {
            "zone": "America/Chicago",
            "default": "ytd",
            "ranges": chart_windows(now),
            "open_line": _open_line(money_bots),
        },
        "spikes": spikes,
        "news": news_calendar(root),
        "paused_all": bool(_load_pause(root).get("all")),
        "pace_line": pace["line"],
        "pace_count": pace["count"],
        "pace_target": pace["target"],
        "pace_loosened": pace["loosened"],
        "pace_note": pace["note"],
        "ops": {
            "entry_gate": gate,
            "entry_gated_bots": [
                b["id"] for b in bots
                if (b.get("plans") or {}).get("entry_gated") and b.get("present")
            ],
            "strong_exits": [
                b["id"] for b in bots
                if (b.get("plans") or {}).get("exit_quality") == "strong"
            ],
            "weak_exits": [
                b["id"] for b in bots
                if (b.get("plans") or {}).get("exit_quality") in ("weak", "partial")
                and b.get("present")
            ],
        },
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
    header = ["Book", "State", "Ticker or game", "Side", "Contracts", "Stake", "Risk", "Reward", "Risk/reward",
              "Entry price", "Fee", "Model probability", "Score at entry", "Why it opened", "Price source", "Price time",
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
            _cell(row.get("risk")),
            _cell(row.get("reward")),
            _cell(row.get("risk_reward")),
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
        table.append(["", "", "No paper trades yet.", "", "", "", "", "", "", "", "", "", "", "No edge.", "", "", "", "", "", ""])
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
