"""
alerts.py - turns bot results into short plain-text messages.
It only FORMATS text and returns it; it never sends anything anywhere.
Whoever runs the bot can read/forward the text themselves.
"""


def money(x):
    return f"${x:,.2f}"


def format_brief(day, skip_reason, risk_ok, risk_msg, state, event_ticker, candidates, upcoming, now_str):
    lines = [f"MORNING BRIEF - {day:%a %b %d, %Y} (generated {now_str})",
             "Mode: PAPER ONLY (no real orders, no keys)",
             f"Paper bankroll: {money(state['bankroll'])}   Open positions: {len(state['open'])}"
             f"   Halted: {'YES' if state.get('halted') else 'no'}"]
    if skip_reason:
        lines.append(f"Today: NO TRADE - skip day ({skip_reason}).")
    elif not risk_ok:
        lines.append(f"Today: NO TRADE - {risk_msg}")
    else:
        lines.append("Today: tradable. Scan runs at 12:30 PM CT; settles 3:00 PM CT.")
    lines.append(f"Contract family: {event_ticker or 'not listed yet'}")
    if candidates:
        lines.append("Right now in the 80-90c band (prices will move before 12:30):")
        for c in candidates[:5]:
            lines.append(f"  - {c['side'].upper()} {c['ticker']} ask {c['ask']*100:.0f}c (spread {c['spread']*100:.0f}c)")
    elif event_ticker:
        lines.append("Right now: nothing in the 80-90c band.")
    if upcoming:
        lines.append("Upcoming skip days (next 14 days): " + "; ".join(f"{d} {r}" for d, r in upcoming))
    return "\n".join(lines)


def format_trade_note(pos, bankroll_after, dry_run=False):
    tag = "WOULD BUY (dry run, nothing recorded)" if dry_run else "PAPER BUY"
    side = pos["side"].upper()
    win = pos["contracts"] * 1.0 - pos["cost"] - pos["fee"]
    loss = -(pos["cost"] + pos["fee"])
    return (f"{tag}: {pos['contracts']} x {side} on {pos['ticker']} at {pos['ask']*100:.0f}c\n"
            f"  cost {money(pos['cost'])} + fee {money(pos['fee'])}; if right: {money(win)}, if wrong: {money(loss)}\n"
            f"  settles 3:00 PM CT; bankroll after entry {money(bankroll_after)}")


def format_settle_note(pos, bankroll_after):
    return (f"SETTLED: {pos['ticker']} {pos['side'].upper()} -> market result '{pos['result']}' -> "
            f"{pos['status'].upper()} {pos['pnl']:+.2f}. Bankroll {money(bankroll_after)}")


def format_skip_note(day, reason):
    # CARD line densifies desk why/skip (pimp_desk card_copy / _kalshi_skip).
    return f"NO TRADE {day}: {reason}\nCARD: {reason}"
