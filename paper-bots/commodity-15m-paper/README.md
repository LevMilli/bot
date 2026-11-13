# Commodity 15m

Paper only. Pretend money. This tower places no real orders and holds no exchange keys.

Palladium/NatGas/Copper/Brent/WTI/Silver/Gold/Platinum 15m paper tower. Same adapt gates as BTC.

- Tower id: `commodity-15m`
- Script: `bot.py`
- Venue floor: `kalshi_commodity15m` 0.05 (locked, never lower)
- Vault tower: it spends desk cash and has a tower risk share.

## Buy rules

- Open KX*15M metals/energy windows (Pd/NatGas/Cu/Brent/WTI/Ag/Au/Pt)
- Spot vs floor_strike; side YES if above else NO
- p ≥ ask + fee + venue kalshi_commodity15m; model p ≥ 80%
- Cushion/σ gate; ask 70–92¢; ≥8m for early single (else skip)
- Kelly-lite + adapt: safe on high/false-conf vol; Wilson CI ≥70% for play-big
- Max 1 energy + 1 metal; EIA/inventory blackout on NatGas/Oil

## Sell rules

- Model-flip when side/fair moves against entry (before settle)
- Settle when Kalshi resolves yes/no (history settle harness labels windows)

## Failsafes

- Desk entry_gate (daily loss / max open / open risk)
- No spot / no σ → skip
- EIA/inventory ±45m blackout for energy series
- Commodity tape family budget; correlation + starve; pause file

The same rules are listed in the desk's BOT_PLANS in `pimp_desk.py`. If this page and the code ever disagree, the code wins and this page gets fixed.
