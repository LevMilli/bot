# Sized Kalshi

Paper only. Pretend money. This tower places no real orders and holds no exchange keys.

KXINXU paper bot with desk Kelly-lite stake (80–92¢ band). Own bankroll; model-flip + settle.

- Tower id: `kalshi-sized`
- Script: `bot.py`
- Venue floor: `kalshi_inx` 0.02 (locked, never lower)
- Vault tower: it spends desk cash and has a tower risk share.

## Buy rules

- KXINXU 3 PM CT; S&P forced scans 12:05 / 13:05 / 13:40 CT; sized window retries on NO TRADE
- Ask band 80–92¢; order-book confirm
- Desk Kelly-lite stake (not fixed $25); venue kalshi_inx edge
- Anti-double vs kalshi-sp same ticker; residual edge ≥ venue + 1¢
- Correlation veto vs BTC / fixed Kalshi; learning skip clear
- Adapt: safe on high vol; bigger only on proven ≥80% record
- Pre-FOMC calm / post-print +30m macro gates

## Sell rules

- Model-flip: side bid collapses under 50¢ → paper sell
- Else settle when Kalshi resolves yes/no

## Failsafes

- Desk entry_gate (daily loss / max open / open risk)
- News calendar + kill switch / 1 trade/day / daily loss $50
- Correlation + starve; paper_mode required
- Pause file

The same rules are listed in the desk's BOT_PLANS in `pimp_desk.py`. If this page and the code ever disagree, the code wins and this page gets fixed.
