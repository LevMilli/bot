# Window history

Support building. It buys nothing and holds no cash. It stays hidden in the city (it never trades).

## What it does
Once a minute, for every Kalshi 15-minute series a tower trades (BTC and ETH, eight commodities, the eight More 15m markets), during the last 14 minutes of each window it saves:

- the top 5 levels of the order book on both sides, plus the best bid and ask,
- the window's open price on the settlement source (Kalshi's `floor_strike`), when the window is first seen,
- after the close: the result and the settlement source's final value (Kalshi's `expiration_value`).

Once a day (after 1:00 UTC) it writes `reports/YYYY-MM-DD.json` for the day before: missing minutes, duplicate rows and out-of-order times per window, 15-minute calibration (market price vs result, by minutes left and by book depth), each shadow tower's calibration from its logged fair prices, and a decision summary (checks, buys, skips by reason).

## Storage
- `recordings/YYYY-MM-DD.jsonl.gz` on the /data volume, so a deploy does not wipe it.
- Days older than 180 days are removed; size cap 300 MB, oldest first. Today's file is never removed.
- Field meanings: `../DATA_DICTIONARY.md`.

## Limits and manners
- Up to 30 Kalshi reads and 20 seconds a run. If the shared Kalshi door is backing off, it sits the minute out so the towers go first.
- Its reads skip the shared 10-second cache in both directions, so it can never hand a tower an older copy of a book.
- The underlying price is only Kalshi's posted open and final values; high and low inside the window are not recorded yet.

## Tools
```
python3 bot.py --day 2026-11-13 KXSOL15M
python3 bot.py --window KXSOL15M-26NOV131815-15
python3 bot.py --chart KXSOL15M-26NOV131815-15 out.svg
```

Model: `recorder.py`. Shared formats: `../desk_data.py`. Registry row: `../new_towers.py`.
