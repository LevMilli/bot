# A26. Data freshness inspector

## What
Tracks how old the data is behind each tower's decisions and whether every building ran on time.

## How often
Every 15 minutes. No network reads.

## What it shows
- Every building, research ones too: last run, next run, and on time, late, last run failed, never ran, paused or no timer.
- Price age at buy: buy time minus the time the price was read, flagged when over 60 seconds.

## Status
Built log-only: `freshness-inspector-paper/` (writes `freshness.json`). Tests in `test_plan_buildings.py`.

## Limit found while building it
Most towers stamp the price time and the buy time from the same clock reading, so price age is almost always 0 seconds today. A real quote age needs each tower to store the quote's own time. That is a change inside existing towers, so it is listed as a proposal.

## Edge and floor
None. It never blocks a buy.
