# CPI nowcast

Shadow paper tower for Kalshi's monthly CPI markets: headline and core CPI, month-over-month (KXCPI, KXCPICORE) and year-over-year (KXCPIYOY, KXCPICOREYOY). Paper only. It spends no desk cash.

## How it prices a market
1. **Best guess:** the [Cleveland Fed inflation nowcast](https://www.clevelandfed.org/indicators-and-data/inflation-nowcasting), updated each business day.
2. **Usual miss:** measured from the Cleveland Fed's own charts over the last ~3 years, by business days left before the BLS release (about 0.11 points close to release, up to about 0.2 a month out). Widened 25% for fat tails. Core nowcasts run about 0.02 high, so that bias is removed.
3. **Rounding:** BLS prints one decimal, so "above 0.2%" needs 0.25% or more.

## When it buys
- Only the month the nowcast covers, only when the nowcast is under 5 days old, and never in the last 2 hours before the release.
- Edge = fair − ask − Kalshi fee must be at least the locked econ floor **0.05**. An edge above **0.15** means the model and the market strongly disagree; that is logged, not bought.
- $25 fixed ticket from a $500 sleeve, max 3 open, one per event, one new buy per check.

## Exits
- **Model flip:** sell at the bid when bid − fee beats the model fair by 2¢.
- **Otherwise:** hold to the Kalshi result.

The two Cleveland files are about 8MB each, so the tower refreshes them at most every 6 hours and keeps only the last 3 months in `nowcast_cache.json`.

Engine: `../kalshi_shadow_tower.py`. Model: `cpi_model.py`. Registry row: `../new_towers.py`.
