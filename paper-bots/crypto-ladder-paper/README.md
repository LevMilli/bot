# Crypto ladder

Shadow paper tower for Kalshi daily crypto strikes: KXBTCD (Bitcoin) and KXETHD (Ethereum), "above $X at 5pm ET". Paper only. It spends no desk cash.

## How it prices a strike
Kalshi settles on the 60-second average of the CF Benchmarks index (BRTI / ERTI) just before 5pm ET.

1. **Spot:** Coinbase's last trade for BTC-USD or ETH-USD. A 0.06% basis allowance covers the gap to the CF index.
2. **Volatility:** Deribit's options. It reads the implied vol at that exact strike from each expiry's smile (out-of-the-money options only), then blends the expiries before and after the Kalshi close by total variance.
3. **Fair value:** the lognormal chance spot ends above the strike (Black-Scholes N(d2), zero rates).

## When it buys
- Only between **15 minutes and 30 hours** before the print.
- Skips a coin when Deribit's underlying and Coinbase disagree by more than 0.5%.
- Edge = fair − ask − Kalshi fee must be at least the locked BTC floor **0.05**. An edge above **0.20** is logged but not bought.
- $25 fixed ticket from a $500 sleeve, max 2 open, one per event, one new buy per check.

## Exits
- **Model flip:** sell at the bid when bid − fee beats the model fair by 2¢.
- **Otherwise:** hold to the Kalshi result.

Engine: `../kalshi_shadow_tower.py`. Model: `ladder_model.py`. Registry row: `../new_towers.py`.
