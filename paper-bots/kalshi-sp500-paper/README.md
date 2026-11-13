# Kalshi S&P

Paper only. Pretend money. This tower places no real orders and holds no exchange keys.

Daily KXINXU paper bot. Scan paper-fills inside its own clock window. Brief is read-only.

- Tower id: `kalshi-sp`
- Script: `bot.py`
- Venue floor: `kalshi_inx` 0.02 (locked, never lower)
- Vault tower: it spends desk cash and has a tower risk share.

## Buy rules

- Up to 3 scans/day 12:00–14:00 CT
- Safest YES/NO ask in the 80–92¢ band; venue kalshi_inx edge
- Stake floor($25 / ask); correlation + learning clear
- Adapt layer still logs vol/performance for desk study
- Pre-FOMC calm after 12:00 CT day before; post-print +30m on macro days

## Sell rules

- Model-flip: bid under 50¢ → paper sell at bid when enabled
- Else hold to 3 PM CT Kalshi settlement

## Failsafes

- Desk entry_gate on scan (not settle/brief)
- Weekend + news/holiday calendar
- Max 3 trades/day; bot daily loss −$50
- Kill switch bankroll ≤ $400; paper_mode required
- Correlation veto + starve; pause file

The same rules are listed in the desk's BOT_PLANS in `pimp_desk.py`. If this page and the code ever disagree, the code wins and this page gets fixed.
