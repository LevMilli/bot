# Soccer & tennis lean

Shadow paper tower for Kalshi soccer and tennis game winners. Paper only. It spends no desk cash.

Leagues: EPL, La Liga, Champions League, Bundesliga, Serie A, Ligue 1, MLS, ATP and WTA.

## How it prices a market
- **Fair price:** Polymarket's moneyline mid for the same game. It's free, so it uses no Odds API credits (those stay with sports-sharp-lag).
- **Soccer:** Polymarket has three Yes/No markets (team, draw, team). Their mids are scaled to add up to 1 and mapped to Kalshi's team / Tie / team markets.
- **Tennis:** Polymarket's two-player market maps to Kalshi's two player markets by last name and first initial.
- **Matching:** the Kalshi event date must be within a day of Polymarket's start, and every Kalshi side must match exactly one Polymarket side. Names are compared after dropping accents and club words like "FC". A few nicknames (Man City, PSG, M'gladbach and so on) are mapped by hand. If anything is ambiguous, the game is skipped.

## When it buys
- Pre-game only: 10 minutes to 48 hours before start.
- Polymarket spread no wider than 3¢ and liquidity at least $5k on every side.
- Edge = fair − Kalshi ask − Kalshi fee must be at least the locked sports floor **0.06**. An edge above **0.15** usually means a bad match or news one venue has not priced; it is logged, not bought.
- $25 fixed ticket from a $500 sleeve, max 3 open, one per event, one new buy per check.

## Exits
- **Model flip:** sell at the bid when bid − fee beats the model fair by 2¢.
- **Otherwise:** hold to the Kalshi result.

Engine: `../kalshi_shadow_tower.py`. Matcher: `match_model.py`. Registry row: `../new_towers.py`.
