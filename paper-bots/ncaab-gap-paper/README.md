# NCAAB gap

Shadow paper tower for Kalshi men's college basketball game winners (KXNCAAMBGAME). Paper only. It spends no desk cash.

## How it prices a market
- **Fair price:** ESPN's live win chance while the game is on. Before tip-off, the sportsbook moneyline on ESPN with the vig taken out.
- **Matching:** the Kalshi event date (ET) must match the ESPN game date, and both team names must match one Kalshi side each. Anything ambiguous is skipped.
- ESPN's Division I scoreboard (groups=50) is read once a check; at most 25 game summaries, live games first.

## When it buys
- Live games, or tip-off within 3 hours. Kalshi spread no wider than 5 cents.
- Sides with fair under 0.72 are logged only. Fair 0.72 to 0.80 needs edge of at least 0.08.
- Edge = fair - Kalshi ask - Kalshi fee must be at least the locked sports floor **0.06** and no more than the **0.20** trust cap. Ask no higher than 92 cents.
- $25 fixed ticket from a $500 sleeve, max 6 open, one per game, one new buy per check.

## Exits
- Model flip: sell at the bid when bid - fee beats the model fair by 2 cents. Otherwise hold to the Kalshi result.

Model: `espn_gap_model.py` (also used by Sports gap + Polymarket). Engine: `../kalshi_shadow_tower.py`. Registry row: `../new_towers.py`.
