# QQQ momentum

Shadow paper tower for QQQ shares. Paper only: no broker is connected and it spends no desk cash.

## The rule
From Zarattini, Aziz & Barbon (2024), "Beat the Market: An Effective Intraday Momentum Strategy for SPY", applied to QQQ:

- **Normal range ("noise area"):** for each time of day, the average move from the open over the last 14 sessions. Upper band = the higher of today's open and yesterday's close × (1 + that move). Lower band = the lower of the two × (1 − that move).
- **Checks:** only at HH:00 and HH:30, from 10:00 to 15:30 New York time, on 5-minute closes.
- **Entry:** long when the close is above the upper band, short when below the lower band. It must clear the band by at least 2% of the band's width (the locked `equity_qqq` 0.02 floor), so a touch does not count.
- **Exit:** a trailing stop at the band or VWAP, whichever is tighter. It can flip to the other side at the same check if that band breaks.
- **Always flat at the 16:00 close** (earlier on half days).

## Costs and size
- $0.0035 a share commission plus 1¢ a share slippage on each side (a full spread, a bit pessimistic for QQQ).
- Fixed $25 ticket in fractional paper shares, one position at a time, $500 paper sleeve.

## Honesty
- A check is acted on only if its 5-minute bar closed in the last 10 minutes. A missed check is logged, never back-filled.
- Published replications find this style of edge thin or gone on QQQ after costs, and opening-range versions are very sensitive to slippage. Treat this as a test, not a money-maker. It needs 50+ trades before the scorekeeper grades it.
- Real money later would need a broker API (for example Alpaca) and a separate review. Note that most brokers do not allow fractional short sales.

## Data
Public Yahoo Finance 5-minute bars (30 days, regular hours), cached 4 minutes. Each check appends its bands and decision to `research.jsonl`.

Model: `qqq_model.py`. Registry row: `../new_towers.py`.
