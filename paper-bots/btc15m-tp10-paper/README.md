# btc15m-tp10

Shadow paper twin of BTC 15m for idea B5 from Part B of the ideas doc. Paper only. It spends no desk cash and never buys with real money.

## The one difference
Same as the BTC 15m mirror, but the take-profit is 10 cents instead of 15.

## Everything else
- Runs on the shared 15-minute engine (kalshi_shadow_tower.py) with its settings from fifteen_twins.py.
- Reads the same market data as BTC 15m, read-only, and keeps its own ledger in this folder.
- $25 fixed ticket from a $500 sleeve. Locked edge floor 0.05.
- Results count only after 50 settled bets, and losses always count.
- Promotion needs Levi's OK. The original BTC 15m tower is unchanged.
