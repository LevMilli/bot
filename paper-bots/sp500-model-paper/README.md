# S&P model

Shadow twin that gives the Kalshi S&P 500 markets (KXINXU strikes, KXINX ranges, today's 4pm ET close) a real fair price. Paper only. It spends no desk cash.

## How it prices a market
- Same math as the Nasdaq tower (`../nasdaq-paper/nasdaq_model.py`, read-only), fed with the S&P 500 and the VIX.
- Fair = lognormal chance the index closes above (or inside) each strike, over the trading minutes left.
- Index and VIX from CNBC, with Yahoo as backup. The index quote must be under 5 minutes old.

## When it buys
- Regular hours only, more than 10 minutes before the close.
- Edge = fair - Kalshi ask - Kalshi fee must be at least the locked index floor **0.02** and no more than **0.15**.
- $25 fixed ticket from a $500 sleeve, max 2 open, one per event.
- Rows with an ask from 80 to 90 cents are tagged "vault band", so they can be compared with the Kalshi S&P tower's buys.

## Exits
- Model flip at the bid, or hold to the Kalshi result.

The Kalshi S&P and Sized Kalshi towers are not changed.
