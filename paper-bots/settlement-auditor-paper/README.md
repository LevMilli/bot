# Settlement auditor

Support building on the Risk & Compliance floor. It buys nothing and holds no cash.

## What it does
Once a day it rechecks every paper trade that was held to the end against Kalshi's official result. It flags any trade where:
- the recorded result ("yes" or "no") is not Kalshi's result, or
- the payout does not match: our side won but paid $0, or lost but paid out.

Sold trades (model flips, stops, take-profits) are skipped, because they never reached settlement.

## Details
- It reads every desk bot's state file and picks closed rows with a Kalshi ticker, a side and a recorded result.
- Each trade is checked once and remembered in `audit.json`. A mismatch stays listed, and is rechecked each run, until it is fixed.
- At most 40 Kalshi reads per run, through the shared gateway; anything left waits for the next run.
- It is read-only on other bots' books. It never edits a trade.

Model: `audit_model.py`. Registry row: `../new_towers.py`.
