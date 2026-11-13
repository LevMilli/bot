# Sports gap + Polymarket

Shadow twin for NBA, NFL and NHL game winners that needs two sources to agree before it buys. Paper only. It spends no desk cash.

## How it prices a market
- **ESPN:** live win chance during the game, no-vig moneyline before it (`../ncaab-gap-paper/espn_gap_model.py`).
- **Polymarket:** the moneyline mid for the same game (`../poly-sports-lean-paper/lean_model.py`, read-only).
- **Fair = the lower of the two** for each side.

## When it buys
- Logged only (never bought) if Polymarket is missing, its spread is over 4 cents, its liquidity is under $5k, or the two sources differ by more than 0.15.
- Kalshi spread no wider than 5 cents. Fair under 0.72 logged only; 0.72 to 0.80 needs edge of at least 0.08.
- Edge = fair - Kalshi ask - Kalshi fee must be at least the locked sports floor **0.06** and no more than **0.15**.
- $25 fixed ticket from a $500 sleeve, max 4 open, one per game.

## Exits
- Model flip at the bid, or hold to the Kalshi result.

The existing sports towers are not changed. If this twin beats ESPN-only after 50 settled results, the Polymarket check is a candidate gate for them (needs Levi's OK).
