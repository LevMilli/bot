# Freshness inspector

Support building (idea A26). It buys nothing, holds no cash, and is display only.

## What it does
Every 15 minutes:

1. Building check. For every building, research ones too, it shows the last run, the next run and a status: on time, late, last run failed, never ran, paused or no timer. A timer building is late when its last run is older than 3 gaps (at least the gap plus 30 minutes). Kalshi S&P and Sized Kalshi run in clock windows, so they are late only after 4 days (weekends are fine).
2. Price age at buy. For each paper trade that stored both the time its price was read and the buy time, it measures the gap. Over 60 seconds is flagged stale. Trades that stored only one time are counted as "not stored".

## Limits
- No network reads. It only reads the desk's run file and state files.
- Most towers today stamp the price time and the buy time with the same clock reading, so the price-age check mostly shows 0 seconds. A real quote age needs each tower to store the quote's own time (see the proposals).
- Display only. It never blocks a buy or restarts a tower.

Model: `fresh_model.py`. Writes `freshness.json`. Registry row: `../new_towers.py`.
