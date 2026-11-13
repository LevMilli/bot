# Result splits

Research building. It buys nothing, holds no cash, and only suggests.

## What it does
Every 6 hours it takes each trading tower's closed paper trades and cuts them four ways:

| Cut | Answers |
|---|---|
| market | BTC vs ETH windows, metal vs energy, league by league, city by city, coin by coin, SOL / XRP / DOGE / BNB / HYPE / S&P / FX for More 15m |
| exit | held to the result vs sold early, and how often each exit rule fired (stop, take profit, model flip, trail, time) |
| hour | the Central-time hour of the buy: S&P scan times (12:05, 13:05, 13:40), check times, time of day |
| side | yes vs no |

Each group shows trades, wins, losses, total, average, win rate, average win vs average loss, and a 95% range for the average trade.

## Honest numbers
- P&L is after fees and after the desk's 1 cent a contract fill tax, the same as the scorekeeper.
- Losses always stay in every group. Trades with no stored result are counted and listed, never dropped.
- Rows that did not store a buy time go to "buy time not stored"; nothing is guessed.

## Flags (suggest only)
- clearly losing: 50+ trades and even the high end of the range is below $0.
- wins often, loses money: 70%+ of trades won but the total is below $0 (the Commodity 15m problem).

It never pauses a market or a tower. A flag is a question for Levi, not an action.

Model: `split_model.py`. Writes `splits.json`. Registry row: `../new_towers.py`.
