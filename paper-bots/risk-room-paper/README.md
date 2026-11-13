# Risk room

Support building (idea A23). It buys nothing, holds no cash, and is display only.

## What it does
Every 15 minutes it reads every tower's open paper positions and groups them by what they ride on: Bitcoin, Ether, the S&P 500, the Nasdaq 100, a metal, a weather city, or one single game.

For each group it shows the open cost, its share of all open cost, and which towers hold it on which side.

## Flags
- stacked: two or more towers hold the same underlying (for example BTC 15m and Crypto ladder both on Bitcoin).
- same side, same game: two or more towers on the same side of one game (Sports gap, Sharp lag and Poly lean).
- heavy: one underlying is 40% or more of all open cost, with at least 2 positions.

## Limits
- Display only. It never blocks, sizes or sells a trade. The desk's own correlation veto is unchanged.
- Direction for Kalshi brackets is the side held (yes/no), not up/down, because a bracket can be either.
- Unknown tickers keep their own series name, so nothing is dropped.

Model: `risk_model.py`. Writes `risk_room.json`. Registry row: `../new_towers.py`.
