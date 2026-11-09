# New tower setup

Use this when adding a market the six live towers do not already trade.
Coinbase spot (`coinbase-spot-paper/`) is the worked example.

## Rules that do not move

1. Paper only. No API key, no wallet, no live order.
2. Do not lower a locked floor: sports 0.06, BTC and commodity 0.05, INX and DEX 0.02, Coinbase spot 0.05.
3. A new tower starts **shadow_only**. It spends no desk cash and takes no `tower_risk_budgets` share.
4. Exit plan before any buy. Quality at least **partial** (a stop or model-flip, plus a backstop).
5. Incubation: 50 fee-aware settles, then a person graduates it. No auto-promote.
6. One new tower per change. Do not edit another tower's folder to make the new one fit.

## Steps

1. Scaffold the folder (it only skips until you write a real rule):

   ```bash
   python tools/new_tower.py scaffold weather-kalshi --name "Weather Kalshi" --floor 0.06
   ```

2. Write the fee-aware rule in that folder. Edge is after that venue's fees and slippage. If the honest math almost never buys, ship the skip. Do not loosen the floor to get a fill.
3. Register the tower in the shared desk files listed by the scaffold checklist: venue floor (and the three floor mirrors), `BOTS`, `BOT_PLANS`, `ACTIONS`, `ACCOUNT_FILES`, `AUTO`, starter cash, city beam color, wing room.
4. Check:

   ```bash
   python tools/new_tower.py check weather-kalshi
   ```

5. Tests for the rule, plus `test_pimp_desk.py` so the roster and the timer still match.

## Coinbase spot base (first use of this process)

US Advanced intro taker is 0.90% (16 Sep 2026 schedule). Round trip with 0.10% slippage each side is 2.00%. The tower only keeps 25% of the last 15-minute move as expected capture, then still requires 0.05 of excess return. A bar has to be about 28% with z ≥ 2. Normal ETH and SOL bars skip. BTC-USD is research-only because `btc15m` already owns that factor. Details: `coinbase-spot-paper/README.md`.
