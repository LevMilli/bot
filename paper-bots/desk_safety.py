"""Safety locks and honest-number checks for the paper desk. Paper only.

This file adds guards and read-only reports. It never changes how a tower
buys, sells, sizes or settles. Nothing here places an order, reads a secret
value, or turns any switch on.

What it holds:

- LOCKED_FLOORS: the venue edge floors that may never go lower. A second,
  hand-written copy, so a change to desk_profit.DEFAULT_VENUE_MIN_EDGE that
  lowers or drops a floor is caught at startup and in tests.
- RISK_LOCKS: the desk limits that stay put (daily stop, open risk, max open,
  small stakes, Kelly, quiet hours).
- startup_check(): logs one line with every locked floor and refuses to start
  the desk if a floor is missing or lower than its lock.
- exchange_key_names(): names (never values) of exchange-key style variables
  that are set. The desk logs a warning; it does not refuse (see PROPOSALS).
- practice_status() / promotion_card() / demotion_check() / retire_check():
  the 50-results rule and the promotion card. Reports only. Promotion is a
  staff action that needs Levi's OK; nothing here promotes a tower.
- secret_hits(): pattern names for text that looks like an API secret. Used
  by the repo scan test. It never returns the matched text.
"""
from __future__ import annotations

import datetime as dt
import logging
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

log = logging.getLogger("desk_safety")

# Locked edge floors. These numbers only ever go up, never down.
LOCKED_FLOORS = {
    "kalshi_sports": 0.06,
    "kalshi_btc15m": 0.05,
    "kalshi_commodity15m": 0.05,
    "kalshi_inx": 0.02,
    "solana_dex": 0.02,
    "coinbase_spot": 0.05,
    "binance_btc_carry": 0.02,
    "coinbase_btc_carry": 0.02,
    "kalshi_econ": 0.05,
    "equity_qqq": 0.02,
}

# Desk limits that stay where they are (plan steps 951-956).
RISK_LOCKS = {
    "paper_only": True,
    "daily_loss_stop": 150.0,
    "max_open_risk": 100.0,
    "max_open_positions": 12,
    "stake_lo_max": 20.0,
    "stake_hi_prob": 0.8,
    "kelly_fraction": 0.25,
    "quiet_start": "22:00",
    "quiet_end": "07:00",
}

# Shadow tower rules.
SHADOW_TICKET = 25.0
SHADOW_SLEEVE = 500.0
RESULTS_TO_COUNT = 50          # a practice tower counts only after this many settled results
DEMOTE_WINDOW = 30             # results below the cautious bound before a demotion flag
RETIRE_AFTER_DAYS = 183        # about 6 months to reach 50 results

_EPS = 1e-12


class SafetyError(RuntimeError):
    """Raised when a lock is broken. The desk does not start."""


# ------------------------------------------------------------------ floors
def floor_problems(defaults: dict | None = None) -> list[str]:
    """Plain lines for every locked floor that is missing or lower than its lock."""
    if defaults is None:
        import desk_profit
        defaults = desk_profit.DEFAULT_VENUE_MIN_EDGE
    out = []
    for key, lock in LOCKED_FLOORS.items():
        if key not in defaults:
            out.append(f"{key} floor is missing (locked at {lock:.2f})")
            continue
        try:
            value = float(defaults[key])
        except (TypeError, ValueError):
            out.append(f"{key} floor is not a number (locked at {lock:.2f})")
            continue
        if value + _EPS < lock:
            out.append(f"{key} floor is {value:.2f}, lower than its lock {lock:.2f}")
    return out


def assert_floors_locked(defaults: dict | None = None) -> None:
    problems = floor_problems(defaults)
    if problems:
        raise SafetyError("Desk will not start. " + "; ".join(problems) + ".")


def floors_line(defaults: dict | None = None) -> str:
    """One log line listing every locked floor, so each deploy proves the floors."""
    if defaults is None:
        import desk_profit
        defaults = desk_profit.DEFAULT_VENUE_MIN_EDGE
    parts = [f"{key} {float(defaults.get(key, 0.0)):.2f}" for key in LOCKED_FLOORS]
    return "Locked floors: " + ", ".join(parts) + ". Paper only, real money off."


# ------------------------------------------------------------------ keys
# Names that look like a key for a real exchange or wallet. Only the name is
# ever looked at; the value is never read or printed.
_KEY_NAME = re.compile(
    r"^(KALSHI|COINBASE|CB|BINANCE|KRAKEN|ALPACA|POLYMARKET|POLY|SOLANA|PHANTOM|WALLET|HYPERLIQUID|BYBIT|OKX)"
    r"_?.*(KEY|SECRET|PRIVATE|PASSPHRASE|SEED|MNEMONIC|TOKEN)",
)


def exchange_key_names(environ=None) -> list[str]:
    """Sorted names of set variables that look like exchange or wallet keys."""
    env = os.environ if environ is None else environ
    return sorted(name for name in env if _KEY_NAME.match(str(name).upper()) and env.get(name))


# ------------------------------------------------------------------ startup
def startup_check(logger: logging.Logger | None = None, defaults: dict | None = None,
                  environ=None) -> str:
    """Run once when the desk starts. Logs the floors line and returns it.

    Raises SafetyError when a locked floor is missing or lowered. A set
    exchange-key name is logged by name only, as a warning.
    """
    logger = logger or log
    assert_floors_locked(defaults)
    line = floors_line(defaults)
    logger.info(line)
    names = exchange_key_names(environ)
    if names:
        logger.warning(
            "Exchange-style key names are set (%s). The desk never uses them and places no orders.",
            ", ".join(names),
        )
    return line


# ------------------------------------------------------------------ 50 results
def practice_status(settled: int) -> dict:
    """Count toward 50 for a practice tower. Ready only at 50 or more."""
    n = max(0, int(settled or 0))
    ready = n >= RESULTS_TO_COUNT
    return {
        "settled": n,
        "need": RESULTS_TO_COUNT,
        "ready": ready,
        "line": (f"{n} of {RESULTS_TO_COUNT} results. Counts now, still needs Levi's OK to promote."
                 if ready else f"{n} of {RESULTS_TO_COUNT} results. Practice only, does not count yet."),
    }


def mark_ready(settled: int) -> dict:
    """Code check for the 50-results rule. Refuses under 50."""
    status = practice_status(settled)
    if not status["ready"]:
        raise SafetyError(f"Cannot mark ready: {status['settled']} of {RESULTS_TO_COUNT} results.")
    return status


def can_promote(settled: int, levi_ok: bool) -> tuple[bool, str]:
    """Promotion needs 50 results and Levi's sign-off. Never automatic."""
    if int(settled or 0) < RESULTS_TO_COUNT:
        return False, f"Needs {RESULTS_TO_COUNT} results, has {int(settled or 0)}."
    if levi_ok is not True:
        return False, "Needs Levi's OK."
    return True, "Has 50 results and Levi's OK."


def wilson_low(wins: int, n: int, z: float = 1.96) -> float:
    """Low end of the Wilson 95% range for a win rate. 0 when there are no results."""
    if n <= 0:
        return 0.0
    p = wins / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (centre - margin) / denom)


def _pnl(row) -> float | None:
    if isinstance(row, (int, float)):
        return float(row)
    if isinstance(row, dict):
        for key in ("pnl", "pl", "profit", "realized"):
            if row.get(key) is not None:
                try:
                    return float(row[key])
                except (TypeError, ValueError):
                    return None
    return None


def _fee(row) -> float:
    if isinstance(row, dict):
        for key in ("fee", "fees", "order_fee"):
            if row.get(key) is not None:
                try:
                    return float(row[key])
                except (TypeError, ValueError):
                    return 0.0
    return 0.0


def promotion_card(tower_id: str, results: list) -> dict:
    """One-page promotion card. Every result counts, losses included.

    A flat result (exactly $0) counts as a result but not as a win.
    """
    pnls = [p for p in (_pnl(r) for r in results or []) if p is not None]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    n = len(pnls)
    fees = round(sum(_fee(r) for r in results or []), 2)
    total = round(sum(pnls), 2)
    low = wilson_low(len(wins), n)
    ok, why = can_promote(n, levi_ok=False)
    return {
        "tower": tower_id,
        "results": n,
        "need": RESULTS_TO_COUNT,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / n, 4) if n else 0.0,
        "cautious_win_rate": round(low, 4),
        "avg_win": round(sum(wins) / len(wins), 2) if wins else 0.0,
        "avg_loss": round(sum(losses) / len(losses), 2) if losses else 0.0,
        "fees": fees,
        "total_pnl": total,
        "ready": n >= RESULTS_TO_COUNT,
        "promote": False,          # never automatic
        "needs_levi_ok": True,
        "line": (f"{tower_id}: {n} results, {len(wins)} won, {len(losses)} lost, "
                 f"total ${total:+.2f} after ${fees:.2f} fees. "
                 + ("Has 50 results; promotion needs Levi's OK." if n >= RESULTS_TO_COUNT else why)),
    }


def demotion_check(results: list, bound: float, window: int = DEMOTE_WINDOW) -> dict:
    """Flag a vault tower whose last ``window`` results win less often than ``bound``.

    Report only. Demotion is a staff action. Losses stay on the lifetime record.
    """
    pnls = [p for p in (_pnl(r) for r in results or []) if p is not None]
    recent = pnls[-window:]
    if len(recent) < window:
        return {"flag": False, "results": len(recent), "line": f"Only {len(recent)} of {window} recent results."}
    rate = sum(1 for p in recent if p > 0) / len(recent)
    flag = rate + _EPS < float(bound)
    return {
        "flag": flag,
        "results": len(recent),
        "win_rate": round(rate, 4),
        "bound": float(bound),
        "keeps_losses": True,
        "line": (f"Last {window} results won {rate:.0%}, under the {bound:.0%} bound. Suggest a move back to practice."
                 if flag else f"Last {window} results won {rate:.0%}, at or over the {bound:.0%} bound."),
    }


def retire_check(first_seen: dt.date, settled: int, today: dt.date) -> dict:
    """Flag a practice tower that has not reached 50 results in about 6 months. Report only."""
    days = (today - first_seen).days
    flag = days >= RETIRE_AFTER_DAYS and int(settled or 0) < RESULTS_TO_COUNT
    return {
        "flag": flag,
        "days": days,
        "settled": int(settled or 0),
        "line": (f"{int(settled or 0)} results after {days} days. Suggest retiring it and keeping its data."
                 if flag else f"{int(settled or 0)} results after {days} days."),
    }


# ------------------------------------------------------------------ secrets
SECRET_PATTERNS = {
    "openai-style key": re.compile(r"sk-[A-Za-z0-9_-]{32,}"),
    "xai key": re.compile(r"xai-[A-Za-z0-9]{32,}"),
    "github token": re.compile(r"(gh[pousr]_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{40,})"),
    "aws key id": re.compile(r"AKIA[0-9A-Z]{16}"),
    "private key block": re.compile(r"-----BEGIN ([A-Z]+ )?PRIVATE KEY-----"),
    "discord bot token": re.compile(r"[MN][A-Za-z0-9]{23}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{27}"),
    "discord webhook": re.compile(r"discord(app)?\.com/api/webhooks/[0-9]{17,}/[A-Za-z0-9_-]{30,}"),
    "slack token": re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
}


def secret_hits(text: str) -> list[str]:
    """Names of secret patterns found in ``text``. Never the matched text itself."""
    return sorted(name for name, pat in SECRET_PATTERNS.items() if pat.search(text or ""))
