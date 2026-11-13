# Crypto hourly

Shadow paper tower for Kalshi's hourly SOL, XRP, DOGE and BNB markets. Paper only. It spends no desk cash.

## Series
- Hourly "above $X" strikes: KXSOLD, KXXRPD, KXDOGED, KXBNBD.
- Hourly ranges: KXSOL, KXXRP, KXDOGE, KXBNB.
- A series with no open markets is noted in the check ("no open markets: ...") and skipped. On the day this was built, KXSOL had none.

## How it prices a market
1. **Spot:** the Coinbase price for the coin right now.
2. **How far it can move:** realized volatility from Coinbase 5-minute candles for closes under an hour away, 1-hour candles for closes 4 hours or more away, and a straight blend in between. Held between 30% and 300% a year.
3. **Fair value:** the chance spot ends above (or below, or inside) the line at the close, with a small extra spread for the gap between Coinbase and the index Kalshi settles on.
4. Only closes 10 minutes to 30 hours away are priced.

## When it buys
- Edge = fair − ask − Kalshi fee must be at least the locked BTC floor **0.05**. Edge above **0.20** is logged, not bought.
- $25 fixed ticket from a $500 sleeve, max 3 open, one per event, one new buy per check.
- At most 2 open bets the same way (up or down) for the same close hour, since these coins move together.

## Exits
- **Model flip:** sell at the bid when bid − fee beats the model fair by 2¢.
- **Otherwise:** hold to the Kalshi result.

## Known limits
There is no option market for these coins, so big jumps are only partly priced. Count after 50 settled results; promotion needs Levi's OK.

Engine: `../kalshi_shadow_tower.py`. Model: `hourly_model.py`. Registry row: `../new_towers.py`.
