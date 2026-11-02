"""Risk rules for Sized Kalshi — reuses the S&P calendar + kill/daily limits."""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SIBLING = os.path.join(os.path.dirname(HERE), "kalshi-sp500-paper")
CFG = json.load(open(os.path.join(HERE, "config.json")))

# Prefer sibling calendar (canonical news days); fall back to local symlink.
_CAL = os.path.join(HERE, CFG.get("calendar_file", "calendar.json"))
if not os.path.isfile(_CAL):
    _CAL = os.path.join(SIBLING, "calendar.json")


def load_calendar(path=None):
    cal = json.load(open(path or _CAL))
    skip = {}
    for reason, days in cal.items():
        if reason.startswith("_"):
            continue
        for d in days:
            skip.setdefault(d, []).append(reason)
    return skip


SKIP_DAYS = load_calendar()


def news_skip_reason(day):
    if day.weekday() >= 5:
        return "WEEKEND"
    r = SKIP_DAYS.get(str(day))
    return "+".join(r) if r else None


def _taker_fee(contracts, price, rate=None):
    rate = CFG.get("taker_fee_rate", 0.07) if rate is None else rate
    raw = rate * contracts * price * (1 - price)
    return math.ceil(raw * 100 - 1e-12) / 100.0


def stake_contracts(ask, max_stake=None, bankroll=None):
    """Fallback fixed-ticket sizing when desk Kelly is unavailable."""
    if ask is None or ask <= 0:
        return 0
    max_stake = CFG["max_stake_dollars"] if max_stake is None else max_stake
    n = math.floor(max_stake / ask + 1e-9)
    if bankroll is not None:
        while n >= 1:
            if n * ask + _taker_fee(n, ask) <= float(bankroll) + 1e-9:
                break
            n -= 1
    return max(n, 0)


def check_can_trade(day, bankroll, trades_today, realised_pnl_today, cfg=CFG, ignore_calendar=False):
    if bankroll <= cfg["kill_switch_bankroll"]:
        return False, (
            f"KILL SWITCH: bankroll ${bankroll:.2f} <= ${cfg['kill_switch_bankroll']:.2f}. "
            "Halted for human review."
        )
    if not ignore_calendar:
        r = news_skip_reason(day)
        if r:
            return False, f"skip day ({r})"
    if trades_today >= cfg["max_trades_per_day"]:
        return False, f"already made {trades_today} trade(s) today (max {cfg['max_trades_per_day']})"
    if realised_pnl_today <= -cfg["daily_loss_limit"]:
        return False, f"daily loss limit hit (${realised_pnl_today:.2f})"
    return True, "ok"


# Keep sibling on path for shared feed helpers when tests import this module alone.
if SIBLING not in sys.path:
    sys.path.insert(0, SIBLING)
