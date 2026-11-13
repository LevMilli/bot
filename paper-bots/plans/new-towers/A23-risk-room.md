# A23. Risk room

## What
A building that shows the whole city's open paper bets grouped by what they ride on: Bitcoin, Ether, the S&P 500, the Nasdaq 100, metals, weather cities, single games.

## How often
Every 15 minutes. No network reads.

## Edge and floor
None. It never buys and never blocks. The registry row uses the econ floor key only to fit the research pattern.

## What it flags
- stacked: 2 or more towers hold the same underlying.
- same side, same game: 2 or more towers on the same side of one game (Sports gap, Sharp lag, Poly lean).
- heavy: one underlying is 40% or more of all open cost.

## Status
Built log-only: `risk-room-paper/` (writes `risk_room.json`). Tests in `test_plan_buildings.py`.

## Next
After 2 weeks of rows, Levi decides whether the stacking flags should feed the desk's correlation veto. That would change tower behavior, so it is a proposal, not a build.
