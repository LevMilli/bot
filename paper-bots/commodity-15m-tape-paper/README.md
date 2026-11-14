# commodity-15m-tape

Shadow paper twin of Commodity 15m for idea B4 from Part B of the ideas doc. Paper only. It spends no desk cash and never buys with real money.

## The one difference
Same as the Commodity 15m mirror, plus the tape check and the per-order fee.

## Everything else
- Runs on the shared 15-minute engine (kalshi_shadow_tower.py) with its settings from fifteen_twins.py.
- Reads the same market data as Commodity 15m, read-only, and keeps its own ledger in this folder.
- $25 fixed ticket from a $500 sleeve. Locked edge floor 0.05.
- Results count only after 50 settled bets, and losses always count.
- Promotion needs Levi's OK. The original Commodity 15m tower is unchanged.
