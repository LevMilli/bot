# more-15m-tp15

Shadow paper twin of More 15m for idea B5 from Part B of the ideas doc. Paper only. It spends no desk cash and never buys with real money.

## The one difference
Same as More 15m, plus a take-profit: sell at the bid once it is 15 cents above the entry ask (capped at 99 cents).

## Everything else
- Runs on the shared 15-minute engine (kalshi_shadow_tower.py) with its settings from fifteen_twins.py.
- Reads the same market data as More 15m, read-only, and keeps its own ledger in this folder.
- $25 fixed ticket from a $500 sleeve. Locked edge floor 0.05.
- Results count only after 50 settled bets, and losses always count.
- Promotion needs Levi's OK. The original More 15m tower is unchanged.
