# Data dictionary

Plain meanings of the fields the desk saves for testing ideas. Pretend money only. Every file below is read-only research: nothing in it places an order.

## Window history (`window-history-paper/recordings/YYYY-MM-DD.jsonl.gz`)
One JSON row per line. Three kinds of row.

`kind: "window"`: written once, the first time a 15-minute window is seen.
- `at`: when we saw it (UTC).
- `series`: the Kalshi series, for example `KXSOL15M`.
- `ticker`: the market, for example `KXSOL15M-26NOV131315-15`.
- `event`: Kalshi's event id for the window.
- `close`: when the window closes (UTC).
- `open_price`: the settlement source's price at the open (Kalshi's `floor_strike`). YES wins when the close is at or above it.

`kind: "book"`: once a minute while 14 or fewer minutes are left.
- `at`, `series`, `ticker`: as above.
- `min_left`: minutes left before the close.
- `yes_bids`, `no_bids`: the best 5 bids on each side, best first, as `[price in dollars, contracts]`. Kalshi lists bids only: a YES offer at A is a NO bid at 1 - A.
- `yes_bid`, `yes_ask`, `no_bid`, `no_ask`: the best prices, worked out from the bids.
- `depth`: contracts in all 10 saved levels together. Used for the thin / normal / busy split.

`kind: "result"`: once, a minute or more after the close.
- `result`: `yes` or `no`.
- `open_price`: as above.
- `settle_value`: the settlement source's final value (Kalshi's `expiration_value`).
- `close`: when the window closed.

## Daily report (`window-history-paper/reports/YYYY-MM-DD.json`)
- `quality`: `windows` recorded, `missing_minutes`, `duplicates`, `out_of_order`, and the `worst` windows.
- `market_calibration_15m`: how often YES won at each recorded mid price, all together, `by_minutes_left` (3-minute buckets) and `by_depth` (thin under 100 contracts, normal under 1,000, busy 1,000 or more).
- `tower_calibration`: per shadow tower, per family (`15m` kept apart from `daily`), the last fair the tower logged before each result vs what happened.
- `calibration_flags`: plain lines for any tower and family off by more than 5 points with 50 or more results.
- `decisions`: checks, buys, skips, and skip reasons grouped by their words.
- `results`: how many windows settled.

## Decision row (shared format, `desk_data.decision_row`)
One row for one side of one market at one check.
- `v`: format version (1).
- `tower`: the tower id.
- `at`: check time (UTC).
- `market`: the ticker. `event`: its event id.
- `side`: `yes` or `no`.
- `inputs`: the small facts the tower used (bid, fee, floor, the plain "why" text and so on).
- `fair`: the tower's chance that this side wins, 0 to 1.
- `price`: what it would pay (the ask), 0 to 1.
- `edge`: fair minus price minus Kalshi's fee.
- `action`: `buy`, `skip`, `sell` or `hold`.
- `reason`: why, in plain words. Every skip has one.
- `family`: `15m` or `daily`.
- `minutes_left`, `volume`: only when known.

## Shadow tower research log (`<tower>-paper/research.jsonl`)
Written by the shared engine every check. One line per check: `at`, `note`, `n` (sides priced) and `decisions` (the 60 best sides by edge, each with ticker, side, fair, ask, bid, fee, edge, floor, action, reason, why). `desk_data.from_research` turns these into decision rows.

## Market snapshots (`market-snapshots-paper/recordings/YYYY-MM-DD.jsonl.gz`)
Every 15 minutes: `at`, `cols` and `series` (per series, rows of `[ticker, yes_bid, yes_ask, bid_size, ask_size, last, volume, oi]`).

## Rule versions (`rule_versions.json`)
- `tower`, `version` (`v1`, `v2` ...), `start` (UTC time the change was merged; the desk redeploys right after), `pr`, `note`.
- A trade's rule version is the latest one that started at or before the trade opened. Before the first row it is `v0`.

## Trade export columns (`desk_data.trades_csv`)
`tower, ticker, side, label, opened, closed, contracts, ask, cost, payout, pnl, exit, result, rule_version`. Every closed trade of the month is included. Losses are never filtered out.

## Gap filling
A row filled from public history always carries `filled: true`. Our own trade records are never filled.
