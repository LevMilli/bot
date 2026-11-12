# Market snapshots

Support building on floor 4. It buys nothing and holds no cash.

## What it does
Every 15 minutes it lists the open markets of 23 Kalshi series the towers watch (weather, gas, crypto daily, Nasdaq, S&P, 10-year Treasury, CPI, GDP and game winners) and saves one compact row per market:

`[ticker, yes_bid, yes_ask, bid_size, ask_size, last, volume, open_interest]`

That builds a real price history the desk does not have today, so later ideas (maker quotes, timing, new towers) can be tested on what the book actually looked like.

## Storage
- `recordings/YYYY-MM-DD.jsonl.gz`, one gzip block per snapshot. On the desk this folder is on the /data volume, so a deploy does not wipe it.
- About 18 KB a snapshot, about 2 MB a day.
- Size cap 150 MB: the oldest days are deleted first. Today's file is never deleted.

## Limits
- Best bid/ask and their sizes only, not the full order book.
- One public read per series per run through the shared Kalshi gateway; up to 200 markets per series.

Model: `snapshot_model.py`. Registry row: `../new_towers.py`.
