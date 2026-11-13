# Meme price check

Research building for the Memecoin tower (idea B15). It buys nothing and holds no cash.

## What it does
- Every 15 minutes it reads Memecoin's open positions and the coins it checked recently (`../memecoin-paper/positions.json` and `checks.csv`, read-only), up to 30 coins.
- For each coin it compares DexScreener's price (deepest Solana pair) with Jupiter's price. Both are free and need no key.
- A gap over 2%, or either price missing, counts as a "would block". Missing always counts as a block (fails closed).
- The running tally and the last 200 would-block rows are saved in `price_check.json` (kept across deploys).

The Memecoin tower is not changed. If the tally shows the check is useful, it can be added to Memecoin behind a flag that is off by default (needs Levi's OK).
