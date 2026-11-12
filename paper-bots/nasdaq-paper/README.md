# Nasdaq

Shadow paper tower for Kalshi end-of-day Nasdaq 100 markets: KXNASDAQ100U ("above X" strikes) and KXNASDAQ100 (ranges), for today's 4pm ET close. Paper only. It spends no desk cash.

## How it prices a market
1. **Level:** the live Nasdaq 100 index (^NDX).
2. **Volatility:** the Nasdaq volatility index (^VXN), held to 8%–80%. It is applied only to the trading minutes left until 4pm ET (252 days × 390 minutes a year), because the index only moves while the market is open.
3. **Fair value:** the lognormal chance the close lands above a strike, below it, or inside a range.

## When it buys
- Only during regular hours on a weekday, and more than **10 minutes** before the close.
- Only when the ^NDX quote is under **5 minutes** old.
- Edge = fair − ask − Kalshi fee must be at least the locked index floor **0.02**. An edge above **0.15** is logged but not bought.
- $25 fixed ticket from a $500 sleeve, max 2 open, one per event, one new buy per check.

## Exits
- **Model flip:** sell at the bid when bid − fee beats the model fair by 2¢.
- **Otherwise:** hold to the Kalshi result.

Engine: `../kalshi_shadow_tower.py`. Model: `nasdaq_model.py`. Registry row: `../new_towers.py`.
