# A3. Rain today

## What
Kalshi's daily "Will it rain today?" city markets and weekend rain.

## On what
Start with the seven Weather high cities (NY, Chicago, Miami, Austin, Denver, Philadelphia, LA), each with its settlement station checked first, then add cities one at a time.

## How often
Every 10 minutes. Buys only in the afternoon once most of the day is known (the same afternoon lock as Weather high). Earlier rows are logged.

## Fair price
Measured rain so far at the settlement station (0.01 inch counts as rain), plus the National Weather Service hourly chance of rain for the hours left.

## Edge and floor
Econ floor 0.05 after the Kalshi fee, trust cap 0.25. $25 ticket, one per city per day.

## Steps
1. Confirm the series names and the "measurable rain" rule on the public Kalshi API.
2. Build log-only and score fair vs price for 2 weeks.
3. Practice book only if the logged rows are positive after fees. 50 results and Levi's OK before it counts.

## Risks
Trace amounts and station rules. Some city books are thin.

## Blocked on
The exact Kalshi series list for daily rain. Not checked yet.
