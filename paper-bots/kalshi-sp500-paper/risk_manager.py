"""
risk_manager.py - the safety rules. Every trade must pass check_can_trade().

Rules (Market_Context.md + Strategy.md):
  1. Skip news days: Fed decision, CPI, jobs report, GDP/PCE, election day and
     the day after, market holidays and half days  (dates in calendar.json).
  2. Max 1 trade per day (daily strategy).
  3. Daily loss limit $50: once today's realised loss reaches $50, stop for the day.
  4. Kill switch: if the paper bankroll is at or below $400, halt everything
     until a human reviews it.
  5. Stake: floor($25 / ask) contracts, and never more than you can afford.
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, "config.json")))


def load_calendar(path=None):
    """Return {date_string: [reasons]} for every skip day in calendar.json."""
    cal = json.load(open(path or os.path.join(HERE, CFG["calendar_file"])))
    skip = {}
    for reason, days in cal.items():
        if reason.startswith("_"):
            continue  # metadata like _sources
        for d in days:
            skip.setdefault(d, []).append(reason)
    return skip


SKIP_DAYS = load_calendar()


def news_skip_reason(day):
    """Why `day` (a datetime.date) is a no-trade day, or None if it is fine."""
    if day.weekday() >= 5:
        return "WEEKEND"
    r = SKIP_DAYS.get(str(day))
    return "+".join(r) if r else None


def stake_contracts(ask, max_stake=None, bankroll=None):
    """floor(max_stake / ask), capped so cost never exceeds the bankroll."""
    max_stake = CFG["max_stake_dollars"] if max_stake is None else max_stake
    n = math.floor(max_stake / ask + 1e-9)
    if bankroll is not None:
        n = min(n, math.floor(max(bankroll, 0) / ask + 1e-9))
    return max(n, 0)


def check_can_trade(day, bankroll, trades_today, realised_pnl_today, cfg=CFG, ignore_calendar=False):
    """Return (ok, reason). ok=False means do NOT trade."""
    if bankroll <= cfg["kill_switch_bankroll"]:
        return False, f"KILL SWITCH: bankroll ${bankroll:.2f} <= ${cfg['kill_switch_bankroll']:.2f}. Halted for human review."
    if not ignore_calendar:
        r = news_skip_reason(day)
        if r:
            return False, f"skip day ({r})"
    if trades_today >= cfg["max_trades_per_day"]:
        return False, f"already made {trades_today} trade(s) today (max {cfg['max_trades_per_day']})"
    if realised_pnl_today <= -cfg["daily_loss_limit"]:
        return False, f"daily loss limit hit (${realised_pnl_today:.2f})"
    return True, "ok"


if __name__ == "__main__":
    import datetime as dt
    assert news_skip_reason(dt.date(2026, 10, 28)) and "FOMC" in news_skip_reason(dt.date(2026, 10, 28))
    assert "CPI" in news_skip_reason(dt.date(2026, 11, 10))
    assert news_skip_reason(dt.date(2026, 10, 27)) is None
    assert news_skip_reason(dt.date(2026, 10, 31)) == "WEEKEND"
    assert stake_contracts(0.85) == 29 and stake_contracts(0.80) == 31 and stake_contracts(0.90) == 27
    assert check_can_trade(dt.date(2026, 10, 27), 399, 0, 0)[0] is False
    assert check_can_trade(dt.date(2026, 10, 27), 500, 1, 0)[0] is False
    assert check_can_trade(dt.date(2026, 10, 27), 500, 0, -50)[0] is False
    assert check_can_trade(dt.date(2026, 10, 27), 500, 0, 0)[0] is True
    print("risk_manager self-test OK; Oct 28 2026 ->", news_skip_reason(dt.date(2026, 10, 28)))
