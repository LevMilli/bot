# A4. EIA crude inventory

## What
Kalshi weekly US crude oil inventories (KXEIACRUDEW).

## How often
Every 30 minutes. Buys only between the Tuesday evening industry (API) estimate and 2 hours before the Wednesday EIA print.

## Fair price
Last week's EIA level plus the typical weekly change, updated by the API estimate. Spread fitted to past API vs EIA misses.

## Edge and floor
Econ floor 0.05 after fee, trust cap 0.25. $25 ticket, max 2 open.

## Steps
1. Log-only for 2 weeks (2 prints). Grade in the what-if lab.
2. Practice book only if positive after fees; 50 results and Levi's OK. At one print a week with a few strikes, 50 results take months.

## Risks
API and EIA often disagree. Thin books.

## Blocked on
A free, allowed source for the API estimate. Not found yet.
