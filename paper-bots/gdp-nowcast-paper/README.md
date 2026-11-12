# GDP nowcast

Shadow paper tower for Kalshi's quarterly GDP markets (KXGDP): "Will BEA's first estimate of real GDP growth be above X%?" Paper only. It spends no desk cash.

## How it prices a market
1. **Best guess:** the [Atlanta Fed GDPNow](https://www.atlantafed.org/cqer/research/gdpnow) estimate for the quarter, from its public spreadsheet.
2. **Usual miss and run-high:** measured from GDPNow's own archive since 2014 (2020 left out), by days left before BEA's first print. A quarter out it misses by about 1.6 points and runs about 0.8 high on average; in the last month the miss is about 0.9 and the run-high is near zero. The tower removes that average run-high and uses the miss as its uncertainty. The table is recomputed on every refresh.
3. **Rounding:** BEA prints one decimal, so "above 3.0%" needs 3.05% or more.

## When it buys
- Only in the last 45 days before the print. Earlier rows are logged for the calibration lab, never bought.
- Only for the quarter GDPNow covers, only when GDPNow is under 10 days old, and never in the last 2 hours before the release.
- Edge = fair − ask − Kalshi fee must be at least the locked econ floor **0.05**. An edge above **0.15** is logged, not bought.
- $25 fixed ticket from a $500 sleeve, max 2 open, one per event, one new buy per check.

## Exits
- **Model flip:** sell at the bid when bid − fee beats the model fair by 2¢.
- **Otherwise:** hold to the Kalshi result.

The spreadsheet is about 11MB, so the tower refreshes it at most every 8 hours and keeps the small result in `gdpnow_cache.json`.

Engine: `../kalshi_shadow_tower.py`. Model: `gdp_model.py`. Registry row: `../new_towers.py`.
