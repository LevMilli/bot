# A20. Time machine replay

## What
Replays a tower's rules on prices that Market snapshots and the Kalshi tape already recorded, and shows what would have happened, after fees.

## On what
Any tower whose rule can run on a top-of-book row: first the 15-minute towers (once B19 records faster), then weather, gas, Nasdaq and S&P.

## How often
On demand and once a night. Trades nothing.

## Edge and floor
Uses each tower's own locked floor. A replay can never change a live setting; it only writes a report.

## Steps
1. Read `market-snapshots-paper/recordings/*.jsonl.gz` and the tape log.
2. Run a rule on each snapshot in time order; settle on the recorded Kalshi result.
3. Report trades, wins, losses, total after fees and the 95% low end, the same way the scorekeeper does.
4. Check: replaying the live rule on last week must land close to the live book. If not, the replay is wrong, not the tower.

## Risks
Snapshots every 15 minutes are too slow for 15-minute markets. Replays never fully match live fills.

## Blocked on
B19 (faster recordings for 15m) for the 15-minute towers.
