# SPY momentum

Shadow paper SPY shares. A twin of QQQ momentum with the same rules on SPY. No broker is connected. It spends no desk cash.

## Rules
- Band = max/min(open, yesterday's close) × (1 ± the 14-day average move from the open at that time of day).
- Checks only at HH:00 and HH:30, 10:00 to 15:30 New York, and only on a bar that closed in the last 10 minutes. A missed check is logged, never filled late.
- Long above the upper band, short below the lower band, clearing it by 2% of the band width (locked equity_qqq floor 0.02).
- Trailing stop at the band or VWAP, whichever is tighter. Always flat by the 16:00 close.
- $25 fixed ticket in fractional paper shares, one position at a time. Costs: $0.0035 a share commission plus 1¢ a share slippage each way.

## Known limits
SPY, QQQ and IWM move together most days, so these towers are close to one bet. Count after 50 settled results; promotion needs Levi's OK.

Code: `../etf_momentum_book.py` (a copy of the QQQ book with the symbol made a setting; it reads `../qqq-momentum-paper/qqq_model.py` without changing it). Registry row: `../new_towers.py`.
