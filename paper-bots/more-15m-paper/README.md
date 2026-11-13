# More 15m

Shadow paper tower for Kalshi 15-minute "up or down" markets that no older tower reads: Solana, XRP, Dogecoin, BNB and Hyperliquid (KXSOL15M, KXXRP15M, KXDOGE15M, KXBNB15M, KXHYPE15M), the S&P 500 (KXINX15M, market hours) and two currencies (KXEURUSD15M, KXUSDJPY15M). Paper only. It spends no desk cash.

## How it prices a window
1. **Open price:** Kalshi posts the price at the start of the window as the target.
2. **Live price:** Coinbase mid for the coins (Kraken backup). Hyperliquid's live oracle for the S&P 500 and the currencies.
3. **Offset check:** for the S&P 500 and currencies the live feed is a different print from Kalshi's source, so the bot measures the gap at each window open and only buys once it has seen 3 opens.
4. **Typical move:** the last hour's 1-minute moves (from Hyperliquid), with a minimum per market. No extra cushion (checked against 88 real windows per market, the raw move was right); USD/JPY gets x1.3 because it moved more than its recent history.
5. **Coins move together:** at most 2 open bets in the same direction (all up or all down) across the five coins in one window.
5. **Fair value:** the chance the price finishes at or above the open.

## When it buys
- Only with **3 to 14 minutes** left in the window.
- Edge = fair − ask − Kalshi fee must be at least the locked floor **0.05**. An edge above **0.20** is logged but not bought.
- $25 fixed ticket from a $500 sleeve, max 4 open, one per window, one new buy per check. Up to 2 extra slots when the edge is 0.10 or more.

## Exits
- **Model flip:** sell at the bid when bid − fee beats the model fair by 2¢.
- **Otherwise:** hold to the Kalshi result.

Engine: `../kalshi_shadow_tower.py`. Registry row: `../new_towers.py`.
