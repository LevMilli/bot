# A1. Maker quote simulator

## What
A pretend resting bid one or two cents under the ask, on the 15-minute and daily Kalshi markets the towers already price. It counts as filled only when the public Kalshi tape shows trades at or through our price after we posted, and only for the size that traded.

## On what
BTC 15m (KXBTC15M, KXETH15M) and Crypto ladder (KXBTCD, KXETHD) first. More 15m stays frozen, so its markets are read but never touched.

## How often
Every 1 minute, inside the same buy windows as the tower it copies.

## Edge and floor
Edge is measured at our bid, not the ask: fair minus our bid minus the maker fee. It must clear the copied tower's locked floor (0.05 for 15m and the crypto ladder). Never lower.

## Pretend fills (strict)
- Our bid fills only for volume printed at or below our price after the post time.
- A fill right before the price moves against us is still a fill. Adverse selection is the main risk, and we must see it.
- Unfilled quotes are logged as "no fill"; they never count as wins.

## Steps
1. Log-only: write each quote and whether the tape would have filled it to `quotes.jsonl`. No book.
2. Two weeks later, grade the logged fills after fees in the what-if lab.
3. Only if positive after fees: a $25 ticket, $500 practice book, shadow_only. Promotion needs 50 results and Levi's OK.

## Risks
Fills are uncertain and lean toward bad ones. The tape reader only looks back 5 minutes. Needs B19's denser recordings to replay.
